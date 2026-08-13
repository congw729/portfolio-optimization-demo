#!/usr/bin/env python3
"""P3 马科维茨均值-方差组合优化器（消费 P2 的 data/params.json）

实现（对照准备清单 §3.1/§3.2）：
  - GMV 最小方差组合：数值优化（禁做空，SLSQP）为主口径；解析解（允许做空）作对照；
  - 最大夏普（切线）组合：数值优化禁做空主口径；解析解作对照；
  - 有效前沿扫描：目标收益 min(mu)*1.05 ~ max(mu)*0.95 扫 60 点，
    wᵀμ=t 等式约束 + try/except 跳过不可行点 + warm start；
  - 输出指标：年化收益 / 年化波动率 / 夏普 / 最大回撤（S-1：nav/dd/max_dd）/ 权重向量。

用法：
    python scripts/optimizer.py --params data/params.json \
        --returns data/returns_assetclass.csv --tag assetclass
    python scripts/optimizer.py --params data/params_stocks.json \
        --returns data/returns_stocks.csv --tag stocks

产出（--tag assetclass 为主输出）：
    output/portfolios.csv          组合指标表（方案 A，主输出）
    output/portfolios_<tag>.csv    组合指标表（按 tag 区分）
    output/frontier_<tag>.csv      有效前沿（含权重）
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# ---------------------------------------------------------------------------
# 组合数学
# ---------------------------------------------------------------------------


def gmv_analytic(mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """解析解 GMV（允许做空、无界权重，仅作对照）：w = Σ⁻¹·1 / (1ᵀΣ⁻¹·1)。"""
    ones = np.ones(len(mu))
    w = np.linalg.solve(sigma, ones)
    return w / w.sum()


def tangency_analytic(mu: np.ndarray, sigma: np.ndarray, rf: float) -> np.ndarray:
    """解析解切线组合（允许做空，仅作对照）：w = Σ⁻¹·(μ−rf·1)/(1ᵀΣ⁻¹·(μ−rf·1))。"""
    excess = mu - rf
    w = np.linalg.solve(sigma, excess)
    return w / w.sum()


def gmv_numeric(mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    """数值优化 GMV（禁做空，主口径）：min wᵀΣw s.t. Σw=1, 0≤w≤1。"""
    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0.0, 1.0)] * n
    res = minimize(
        lambda w: w @ sigma @ w,
        x0=np.ones(n) / n,
        method="SLSQP",
        constraints=cons,
        bounds=bounds,
        options={"ftol": 1e-12, "maxiter": 500},
    )
    if not res.success:
        raise RuntimeError(f"GMV 数值优化失败: {res.message}")
    return res.x


def tangency_numeric(mu: np.ndarray, sigma: np.ndarray, rf: float) -> np.ndarray:
    """数值优化最大夏普（禁做空，主口径）：max (wᵀμ−rf)/√(wᵀΣw) 即 min 负值。"""
    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0.0, 1.0)] * n

    def neg_sharpe(w: np.ndarray) -> float:
        vol = np.sqrt(w @ sigma @ w)
        if vol <= 1e-12:
            return 1e12  # 惩罚零波动（防止除零）
        return -(w @ mu - rf) / vol

    res = minimize(
        neg_sharpe,
        x0=np.ones(n) / n,
        method="SLSQP",
        constraints=cons,
        bounds=bounds,
        options={"ftol": 1e-12, "maxiter": 500},
    )
    if not res.success:
        raise RuntimeError(f"切线组合数值优化失败: {res.message}")
    return res.x


def frontier_scan(
    mu: np.ndarray, sigma: np.ndarray, n_points: int = 60, margin: float = 0.05
) -> list[dict]:
    """有效前沿扫描（S-4：5% 余量 + try/except 跳过 + warm start）。

    返回按目标收益升序排列的可行点列表：[{target_ret, vol, w}]。
    """
    n = len(mu)
    lo = float(mu.min()) * (1 + margin)
    hi = float(mu.max()) * (1 - margin)
    targets = np.linspace(lo, hi, n_points)
    cons_base = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0.0, 1.0)] * n
    points: list[dict] = []
    w_prev = np.ones(n) / n  # warm start 初值
    for t in targets:
        try:
            cons = cons_base + [
                {"type": "eq", "fun": lambda w, t=t: float(w @ mu) - t}
            ]
            res = minimize(
                lambda w: w @ sigma @ w,
                x0=w_prev,
                method="SLSQP",
                constraints=cons,
                bounds=bounds,
                options={"ftol": 1e-12, "maxiter": 500},
            )
            if not res.success:
                continue
            w = res.x
            points.append(
                {
                    "target_ret": t,
                    "ret": float(w @ mu),
                    "vol": float(np.sqrt(w @ sigma @ w)),
                    "w": w,
                }
            )
            w_prev = w  # warm start：前一解作初值
        except Exception:
            continue  # 跳过不可行点
    return points


# ---------------------------------------------------------------------------
# 指标计算
# ---------------------------------------------------------------------------


def max_drawdown(returns_series: pd.Series) -> float:
    """最大回撤（S-1 口径）：nav=(1+r).cumprod(); dd=nav/nav.cummax()-1; max_dd=dd.min()。"""
    nav = (1.0 + returns_series).cumprod()
    dd = nav / nav.cummax() - 1.0
    return float(dd.min())


def portfolio_metrics(
    w: np.ndarray, mu: np.ndarray, sigma: np.ndarray, rf: float,
    returns_df: pd.DataFrame | None,
) -> dict:
    """组合指标：年化收益 / 波动率 / 夏普 / 最大回撤（需日收益率序列）。"""
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ sigma @ w))
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")
    max_dd = float("nan")
    if returns_df is not None:
        r = returns_df @ w  # 组合日收益率序列
        max_dd = max_drawdown(r)
    return {"ret": ret, "vol": vol, "sharpe": sharpe, "max_dd": max_dd}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="马科维茨均值-方差组合优化器（P3）")
    p.add_argument("--params", required=True, help="参数 JSON（P2 产出，如 data/params.json）")
    p.add_argument("--returns", required=True, help="日收益率 CSV（如 data/returns_assetclass.csv，用于最大回撤）")
    p.add_argument("--tag", required=True, help="资产池标识（assetclass / stocks）")
    p.add_argument("--output-dir", default="output", help="输出目录，默认 output/")
    p.add_argument("--n-points", type=int, default=60, help="前沿扫描点数，默认 60")
    p.add_argument("--margin", type=float, default=0.05, help="扫描两端余量，默认 0.05")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 读取 P2 参数
    with open(args.params, encoding="utf-8") as f:
        params = json.load(f)
    tickers: list[str] = params["tickers"]
    mu = np.array([params["mu"][t] for t in tickers])
    sigma = np.array([params["sigma"][t] for t in tickers])  # dict: ticker → 行向量
    rf = params.get("rf", 0.0)

    # 日收益率（用于最大回撤；列名与 tickers 对齐）
    returns_df = pd.read_csv(args.returns, index_col=0, parse_dates=True)
    returns_df = returns_df[tickers]

    print(f"=== P3 优化：{args.tag}（{len(tickers)} 资产，rf={rf:.4f}）===")

    # 1) GMV：数值（主口径）+ 解析（对照）
    w_gmv_num = gmv_numeric(mu, sigma)
    w_gmv_ana = gmv_analytic(mu, sigma)

    # 2) 切线：数值（主口径）+ 解析（对照）
    w_tan_num = tangency_numeric(mu, sigma, rf)
    w_tan_ana = tangency_analytic(mu, sigma, rf)

    combos = {
        "GMV (no short)": w_gmv_num,
        "GMV (analytic)": w_gmv_ana,
        "Tangency (no short)": w_tan_num,
        "Tangency (analytic)": w_tan_ana,
    }

    # 3) 组合指标表
    rows = []
    for name, w in combos.items():
        m = portfolio_metrics(w, mu, sigma, rf, returns_df)
        row = {"pool": args.tag, "combo": name}
        row["ret"] = round(m["ret"], 6)
        row["vol"] = round(m["vol"], 6)
        row["sharpe"] = round(m["sharpe"], 6)
        row["max_dd"] = round(m["max_dd"], 6)
        for i, t in enumerate(tickers):
            row[f"w_{t}"] = round(float(w[i]), 6)
        rows.append(row)
        print(
            f"  {name:<28} ret={row['ret']:+.4f}  vol={row['vol']:.4f}  "
            f"sharpe={row['sharpe']:.4f}  max_dd={row['max_dd']:.4f}"
        )

    portfolios_df = pd.DataFrame(rows)
    portfolios_path = out_dir / f"portfolios_{args.tag}.csv"
    portfolios_df.to_csv(portfolios_path, index=False)
    if args.tag == "assetclass":  # 方案 A 作为主输出
        portfolios_df.to_csv(out_dir / "portfolios.csv", index=False)

    # 4) 有效前沿扫描
    points = frontier_scan(mu, sigma, args.n_points, args.margin)
    print(f"  有效前沿：{len(points)}/{args.n_points} 个可行点")
    frontier_rows = []
    for p in points:
        row = {"target_ret": p["target_ret"], "ret": p["ret"], "vol": p["vol"]}
        for i, t in enumerate(tickers):
            row[f"w_{t}"] = p["w"][i]
        frontier_rows.append(row)
    frontier_df = pd.DataFrame(frontier_rows)
    frontier_path = out_dir / f"frontier_{args.tag}.csv"
    frontier_df.to_csv(frontier_path, index=False)
    if args.tag == "assetclass":  # 方案 A 前沿作为主输出 frontier.csv
        frontier_df.to_csv(out_dir / "frontier.csv", index=False)

    # 5) 形状验证摘要（P3 里程碑）
    if len(points) >= 2:
        vols = [p["vol"] for p in points]
        i_gmv = int(np.argmin(vols))
        gmv_pt = points[i_gmv]
        tan_m = portfolio_metrics(w_tan_num, mu, sigma, rf, returns_df)
        print("\n=== 前沿形状验证（P3 里程碑）===")
        print(f"  前沿点数: {len(points)}（目标 ~{args.n_points}，跳过不可行点）")
        print(
            f"  GMV 点: ret={gmv_pt['ret']:+.4f}, vol={gmv_pt['vol']:.4f} "
            f"(前沿最低波动率位置)")
        print(
            f"  切线组合: ret={tan_m['ret']:+.4f}, vol={tan_m['vol']:.4f}, "
            f"sharpe={tan_m['sharpe']:.4f}")
        print(
            f"  GMV 与切线分离: Δvol={tan_m['vol'] - gmv_pt['vol']:+.4f}, "
            f"Δret={tan_m['ret'] - gmv_pt['ret']:+.4f}"
        )
        lo, hi = frontier_df["ret"].min(), frontier_df["ret"].max()
        span = hi - lo
        bend = vols[-1] - vols[i_gmv] if i_gmv < len(vols) - 1 else 0.0
        print(
            f"  前沿跨度: ret∈[{lo:+.4f}, {hi:+.4f}]（Δ={span:.4f}），"
            f"波动率抬升 {bend:.4f} → 弯曲{'明显' if bend > 0.02 else '偏弱'}")

    print(f"\n[OK] 输出: {portfolios_path} / {frontier_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
