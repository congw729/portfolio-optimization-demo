#!/usr/bin/env python3
"""P4b 派生特征计算（演示角色 feature-engineer 的支撑脚本）

职责（对照编排方案 §1.2）：
  1. 校验 data/params.json 完整性（mu/Sigma/rf/benchmark/asset_class 齐全）；
  2. 计算派生特征：
     - 相关系数矩阵 corr（由 returns CSV 计算）；
     - 按资产类别的收益/波动汇总 asset_class_summary；
     - 60/40 基准组合参数 benchmark_6040（60% SPY 股票 + 40% TLT 债券）；
  3. 校验相关矩阵含至少一个负相关系数（A2 验收断言）；
  4. 输出 data/features.json（供 reporter 引用）。

用法：
    python scripts/features.py [--data-dir data] [--output-dir output]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 60/40 基准组合的资产与权重（方案 A 内选取：SPY 股票 + TLT 长债）
BENCH_6040 = {"SPY": 0.6, "TLT": 0.4}


def load_params(data_dir: Path) -> dict:
    with open(data_dir / "params.json", encoding="utf-8") as f:
        return json.load(f)


def validate_params(params: dict) -> None:
    """校验 params.json 完整性（编排方案 §1.2 关键校验）。"""
    required = ["tickers", "mu", "sigma", "rf", "benchmark", "asset_class"]
    missing = [k for k in required if k not in params]
    assert not missing, f"params.json 缺少字段: {missing}"
    tickers = params["tickers"]
    assert len(tickers) >= 2, "至少需要 2 只资产"
    for t in tickers:
        assert t in params["mu"], f"mu 缺少 {t}"
        assert t in params["sigma"], f"sigma 缺少 {t}"
        assert t in params["asset_class"], f"asset_class 缺少 {t}"
    rf = params["rf"]
    assert 0 < rf < 0.15, f"rf 断言失败: {rf}"
    print(f"[校验] params.json 完整（{len(tickers)} 资产，rf={rf:.4f}）")


def compute_corr(returns: pd.DataFrame, tickers: list[str]) -> dict:
    corr = returns[tickers].corr()
    return {a: {b: round(float(corr.loc[a, b]), 6) for b in tickers}
            for a in tickers}


def summarize_by_class(params: dict, returns: pd.DataFrame) -> dict:
    """按资产类别汇总年化收益/波动率（每类内各资产数值 + 类别均值）。"""
    tickers = params["tickers"]
    mu = params["mu"]
    sigma = np.array([params["sigma"][t] for t in tickers])
    vol = {t: float(np.sqrt(sigma[i, i])) for i, t in enumerate(tickers)}

    classes: dict[str, dict] = {}
    for i, t in enumerate(tickers):
        cls = params["asset_class"][t]
        entry = classes.setdefault(cls, {"assets": [], "mu_list": [], "vol_list": []})
        entry["assets"].append(t)
        entry["mu_list"].append(mu[t])
        entry["vol_list"].append(vol[t])
    summary = {}
    for cls, e in classes.items():
        summary[cls] = {
            "assets": e["assets"],
            "mu_avg": round(float(np.mean(e["mu_list"])), 6),
            "vol_avg": round(float(np.mean(e["vol_list"])), 6),
            "mu_each": {t: round(mu[t], 6) for t in e["assets"]},
            "vol_each": {t: round(vol[t], 6) for t in e["assets"]},
        }
    return summary


def benchmark_6040(params: dict) -> dict:
    """60/40 基准组合参数：ret = wᵀμ_sub，vol = sqrt(wᵀΣ_sub w)，sharpe=(ret-rf)/vol。"""
    tickers = params["tickers"]
    mu = params["mu"]
    sigma = np.array([params["sigma"][t] for t in tickers])
    rf = params["rf"]

    weights = {}
    for t, w in BENCH_6040.items():
        assert t in tickers, f"60/40 基准资产 {t} 不在资产池中"
        weights[t] = w
    idx = [tickers.index(t) for t in BENCH_6040]
    w = np.array([BENCH_6040[t] for t in tickers if t in BENCH_6040])
    # 保持与 idx 顺序一致
    w = np.array([BENCH_6040[tickers[i]] for i in idx])
    mu_sub = np.array([mu[tickers[i]] for i in idx])
    sigma_sub = sigma[np.ix_(idx, idx)]

    ret = float(w @ mu_sub)
    vol = float(np.sqrt(w @ sigma_sub @ w))
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")
    return {
        "weights": weights,
        "ret": round(ret, 6),
        "vol": round(vol, 6),
        "sharpe": round(sharpe, 6),
        "note": "60% 股票(SPY) + 40% 债券(TLT) 再平衡基准，与组合同 rf 口径",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="P4b 派生特征计算（feature-engineer）")
    p.add_argument("--data-dir", default="data", help="数据目录，默认 data/")
    p.add_argument("--output-dir", default="output", help="输出目录，默认 output/")
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) 校验 params.json
    params = load_params(data_dir)
    validate_params(params)
    tickers = params["tickers"]

    # 2) 读取收益率（用于相关矩阵）
    returns = pd.read_csv(data_dir / "returns_assetclass.csv",
                          index_col=0, parse_dates=True)
    returns = returns[tickers]

    # 3) 派生特征
    corr = compute_corr(returns, tickers)
    class_summary = summarize_by_class(params, returns)
    b6040 = benchmark_6040(params)

    # 4) A2 验收：至少一个负相关系数
    corr_df = returns[tickers].corr()
    n_neg = int((corr_df.values < 0).sum() // 2)
    neg_pairs = [
        (tickers[i], tickers[j], round(float(corr_df.iloc[i, j]), 4))
        for i in range(len(tickers)) for j in range(i + 1, len(tickers))
        if corr_df.iloc[i, j] < 0
    ]
    assert n_neg >= 1, "A2 验收失败：相关矩阵无负相关系数"
    print(f"[校验] A2 通过：负相关对数 = {n_neg}（{neg_pairs[:3]}...）")

    features = {
        "tickers": tickers,
        "asset_class": params["asset_class"],
        "corr": corr,
        "asset_class_summary": class_summary,
        "benchmark_6040": b6040,
        "rf": params["rf"],
        "benchmark": params["benchmark"],
        "checks": {
            "has_negative_corr": True,
            "n_neg_pairs": n_neg,
            "neg_pairs": neg_pairs,
        },
        "source": {
            "params": str(data_dir / "params.json"),
            "returns": str(data_dir / "returns_assetclass.csv"),
        },
    }
    out_path = data_dir / "features.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    print(f"[输出] {out_path}")

    print("\n=== 派生特征摘要 ===")
    print(f"  60/40 基准: ret={b6040['ret']:.2%}, vol={b6040['vol']:.2%}, "
          f"sharpe={b6040['sharpe']:.3f}")
    for cls, e in class_summary.items():
        print(f"  类别 {cls}: mu_avg={e['mu_avg']:.2%}, vol_avg={e['vol_avg']:.2%}, "
              f"assets={e['assets']}")
    print("\n[OK] features.json 已生成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
