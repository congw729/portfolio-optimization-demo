#!/usr/bin/env python3
"""参数化行情数据管道脚本（P2a 单标的验证 / P2b 全量资产池复用）

流程：联网拉取（或读本地缓存）→ 清洗对齐 → 收益率 → 年化参数 → 落盘缓存
约定：数据缓存优先；带 --refresh 才强制联网刷新（准备清单 §2.4）。

用法示例：
    python scripts/fetch_data.py --name spy         --tickers SPY --years 5
    python scripts/fetch_data.py --name assetclass --tickers SPY,IWM,TLT,GLD,EEM,DBC --years 5
    python scripts/fetch_data.py --name stocks      --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5 --refresh

输出：
    data/closes_<name>.csv    对齐后收盘价（每 ticker 一列，Date 为索引）
    data/returns_<name>.csv   日收益率（pct_change 后 dropna）
    data/params_<name>.json   年化 mu / Sigma / 相关系数（供 P3 优化直接使用）
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 资产类别标签（P2b：供下游按类别聚合 / 热力图）
# ---------------------------------------------------------------------------
ASSET_CLASS = {
    "SPY": "equity-us",
    "IWM": "equity-us",
    "TLT": "bond",
    "GLD": "gold",
    "EEM": "equity-em",
    "DBC": "commodity",
}

# ---------------------------------------------------------------------------
# 参数解析
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="拉取行情 → 清洗对齐 → 收益率 → 年化参数 → 缓存 CSV/JSON"
    )
    parser.add_argument(
        "--name",
        required=True,
        help="缓存文件名标识（如 spy / assetclass / stocks），输出 closes_<name>.csv 等",
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="逗号分隔的 ticker 列表，如 SPY 或 SPY,IWM,TLT",
    )
    parser.add_argument(
        "--years",
        type=float,
        default=5.0,
        help="历史窗口年数（截止日动态化为今天，S-6），默认 5",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="数据缓存目录，默认 data/",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="强制联网刷新，忽略已有缓存",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只打印关键摘要，不打印逐列明细",
    )
    parser.add_argument(
        "--rf",
        action="store_true",
        help="拉取无风险利率 ^IRX（3 个月美债收益率最新值/100，断言 0<rf<0.15）",
    )
    parser.add_argument(
        "--benchmark",
        default=None,
        help="市场基准 ticker（如 SPY），随 params 一并输出",
    )
    parser.add_argument(
        "--params-out",
        default=None,
        help="params JSON 额外输出路径（如 data/params.json，正式参数文件）",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------


def load_from_cache(data_dir: Path, name: str) -> pd.DataFrame | None:
    """若存在缓存则读取收盘价，否则返回 None。"""
    path = data_dir / f"closes_{name}.csv"
    if not path.exists() or path.stat().st_size == 0:
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    print(f"[缓存] 读取 {path}（{len(df)} 行）")
    return df


def fetch_from_network(tickers: list[str], years: float) -> pd.DataFrame:
    """yfinance 拉取，返回每 ticker 一列的收盘价 DataFrame。"""
    import yfinance as yf  # 延迟导入，缓存命中时避免加载

    end = pd.Timestamp.today()
    start = end - pd.DateOffset(years=years)
    print(
        f"[拉取] {tickers}  {start.strftime('%Y-%m-%d')} ~ "
        f"{end.strftime('%Y-%m-%d')}  (auto_adjust=True)"
    )
    raw = yf.download(
        tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError("yfinance 返回空数据，请检查网络或 ticker 代码")

    # 提取 Close 列（兼容单 ticker 单级列 / 多 ticker MultiIndex）
    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw.loc[:, (slice(None), "Close")]
        closes.columns = tickers
    else:
        closes = raw[["Close"]].rename(columns={"Close": tickers[0]})
    return closes


def clean_and_align(closes: pd.DataFrame) -> pd.DataFrame:
    """清洗对齐：前向填充后按共同交易日对齐（准备清单 §2.2）。"""
    cleaned = closes.ffill().dropna(how="any")
    if cleaned.empty:
        raise RuntimeError("清洗后无数据（ffill().dropna(how='any') 后为空）")
    return cleaned


def compute_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """日收益率（简单收益率，课程演示推荐）。"""
    return closes.pct_change().dropna()


def annualize(returns: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """年化期望收益 mu 与年化协方差 Sigma（×252）。"""
    mu = returns.mean() * 252
    sigma = returns.cov() * 252
    return mu, sigma


def quality_report(closes: pd.DataFrame, returns: pd.DataFrame,
                   mu: pd.Series, sigma: pd.DataFrame, quiet: bool) -> dict:
    """数据质量验证：无 NaN、日期连续、年化参数合理。返回报告字典。"""
    std_series = pd.Series(
        sigma.to_numpy().diagonal() ** 0.5, index=sigma.columns
    )
    report: dict = {
        "交易日数": int(len(closes)),
        "日期范围": f"{closes.index.min().date()} ~ {closes.index.max().date()}",
        "closes_NaN": int(closes.isna().sum().sum()),
        "returns_NaN": int(returns.isna().sum().sum()),
        "年化收益_mu": {k: round(float(v), 4) for k, v in mu.items()},
        "年化波动率_std": {
            k: round(float(v), 4) for k, v in std_series.items()
        },
    }

    # 日期连续性：相邻交易日间隔天数，最大间隔 > 7 天视为可疑缺口
    gaps = closes.index.to_series().diff().dt.days
    max_gap = int(gaps.max())
    report["最大相邻间隔_天"] = max_gap
    report["日期连续性"] = "OK（最大间隔 <= 7 天）" if max_gap <= 7 else f"⚠️ 最大间隔 {max_gap} 天，可能有缺失"

    # 年化波动率合理性（15–25% 为权益类常见量级，仅供参考）
    for t in closes.columns:
        s = float(std_series[t])
        flag = "OK" if 0.05 <= s <= 0.60 else "⚠️ 量级异常"
        report.setdefault("波动率量级", {})[t] = f"{s:.2%} ({flag})"

    if not quiet:
        print("\n=== 年化参数（mu / 波动率）===")
        for t in closes.columns:
            print(f"  {t:>8}: 年化收益 {mu[t]:+.2%} | 年化波动率 {std_series[t]:.2%}")
        print("\n=== 年化协方差矩阵（Sigma ×252）===")
        print(sigma.round(6).to_string())
    return report


def _last_close_value(df: pd.DataFrame) -> float:
    """从 yfinance download 结果中提取最后一期 Close 标量（兼容单/多级列）。"""
    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # 多级列（含 Ticker 层级）
        close = close.iloc[:, 0]
    return float(close.iloc[-1])


def fetch_rf() -> float:
    """拉取无风险利率：^IRX（3 个月美债收益率），最新值 / 100，断言 0<rf<0.15。"""
    import yfinance as yf

    df = yf.download("^IRX", period="5d", progress=False)
    if df is None or df.empty:
        raise RuntimeError("^IRX 拉取失败，无风险利率不可用")
    rf = _last_close_value(df) / 100.0
    assert 0 < rf < 0.15, f"无风险利率异常: rf={rf}（预期 0<rf<0.15）"
    return rf


def fetch_benchmark(ticker: str) -> dict:
    """拉取市场基准（如 SPY），返回最新收盘价与近 5 日数据。"""
    import yfinance as yf

    bench = yf.download(ticker, period="5d", auto_adjust=True, progress=False)["Close"]
    if isinstance(bench, pd.DataFrame):  # 多级列（含 Ticker 层级）
        bench = bench.iloc[:, 0]
    return {
        "ticker": ticker,
        "latest_close": float(bench.iloc[-1]),
        "last_5d": [round(float(v), 4) for v in bench.tolist()],
    }


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    args = parse_args(argv)
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # 0) 可选：无风险利率与基准（P2b 需求）
    rf = fetch_rf() if args.rf else None
    benchmark = fetch_benchmark(args.benchmark) if args.benchmark else None
    if rf is not None:
        print(f"[rf] ^IRX 最新值 = {rf * 100:.3f}% → rf = {rf:.5f}（断言通过）")
    if benchmark:
        print(f"[benchmark] {benchmark['ticker']} 最新收盘 = {benchmark['latest_close']:.2f}")

    # 1) 数据获取：缓存优先，--refresh 强制联网
    closes = None if args.refresh else load_from_cache(data_dir, args.name)
    if closes is None:
        closes = fetch_from_network(tickers, args.years)

    # 2) 清洗对齐
    closes = clean_and_align(closes)

    # 3) 收益率
    returns = compute_returns(closes)

    # 4) 年化参数
    mu, sigma = annualize(returns)

    # 5) 落盘缓存
    closes_path = data_dir / f"closes_{args.name}.csv"
    returns_path = data_dir / f"returns_{args.name}.csv"
    params_path = data_dir / f"params_{args.name}.json"
    closes.to_csv(closes_path)
    returns.to_csv(returns_path)

    params = {
        "tickers": tickers,
        "start": str(closes.index.min().date()),
        "end": str(closes.index.max().date()),
        "mu": {k: float(v) for k, v in mu.items()},
        "sigma": {k: list(v) for k, v in sigma.items()},
    }
    if rf is not None:
        params["rf"] = rf
    if benchmark:
        params["benchmark"] = benchmark
    # 资产类别标签（P2b：供下游按类别聚合 / 热力图）
    params["asset_class"] = {
        t: ASSET_CLASS.get(t, "equity-us") for t in tickers
    }
    with params_path.open("w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    if args.params_out:
        out = Path(args.params_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)
        print(f"[params] 已额外输出正式参数文件 {out}")
    print(f"[缓存] 已写入 {closes_path} / {returns_path} / {params_path}")

    # 6) 数据质量报告
    report = quality_report(closes, returns, mu, sigma, args.quiet)
    print("\n=== 数据质量报告 ===")
    for k, v in report.items():
        print(f"  {k}: {v}")

    # 7) 硬性断言：核心链路必须通过，失败即非零退出
    assert report["closes_NaN"] == 0, "收盘价存在 NaN"
    assert report["returns_NaN"] == 0, "收益率存在 NaN"
    assert report["交易日数"] > 0, "无交易日数据"
    print("\n[OK] 数据管道执行完成，质量检查全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
