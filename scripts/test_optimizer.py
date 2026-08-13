#!/usr/bin/env python3
"""P3 优化器单元测试（纯 assert 实现，无 pytest 依赖）

覆盖 P3 里程碑断言：
  1. 权重和 = 1（±1e-6）；
  2. GMV 波动率 ≤ 任一单资产波动率（分散化生效）；
  3. 方案 A 相关矩阵含至少一个负相关系数（A2 验收，实测 DBC-EEM=-0.12）；
  4. 前沿曲线单调凸（波动率随目标收益单调非降）。

用法：
    python scripts/test_optimizer.py
    # 需要先运行 P2b 生成 data/params.json 与 data/returns_assetclass.csv

退出码：0 = 全部通过；1 = 存在失败断言。
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 让脚本可直接运行（import 同目录的 optimizer）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimizer import (  # noqa: E402
    frontier_scan,
    gmv_analytic,
    gmv_numeric,
    tangency_analytic,
    tangency_numeric,
)

ROOT = Path(__file__).resolve().parent.parent
PARAMS_A = ROOT / "data" / "params.json"
PARAMS_STOCKS = ROOT / "data" / "params_stocks.json"
RETURNS_A = ROOT / "data" / "returns_assetclass.csv"
RETURNS_STOCKS = ROOT / "data" / "returns_stocks.csv"

PASSED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        raise AssertionError(f"[FAIL] {name} {detail}")
    PASSED.append(name)
    print(f"  [PASS] {name}")


def load_params(path: Path) -> tuple[np.ndarray, np.ndarray, float, list[str]]:
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    tickers = p["tickers"]
    mu = np.array([p["mu"][t] for t in tickers])
    sigma = np.array([p["sigma"][t] for t in tickers])  # dict: ticker → 行向量
    rf = p.get("rf", 0.0)
    return mu, sigma, rf, tickers


def test_weight_sum_one() -> None:
    print("== 断言 1：权重和 = 1（±1e-6）==")
    for path in (PARAMS_A, PARAMS_STOCKS):
        mu, sigma, rf, tickers = load_params(path)
        for name, w in (
            ("GMV数值", gmv_numeric(mu, sigma)),
            ("GMV解析", gmv_analytic(mu, sigma)),
            ("切线数值", tangency_numeric(mu, sigma, rf)),
            ("切线解析", tangency_analytic(mu, sigma, rf)),
        ):
            check(
                f"{path.stem}-{name} 权重和=1",
                abs(w.sum() - 1.0) < 1e-6,
                f"sum={w.sum():.9f}",
            )
    # 前沿各点
    mu, sigma, rf, _ = load_params(PARAMS_A)
    pts = frontier_scan(mu, sigma)
    assert len(pts) > 0, "方案 A 前沿无可行点"
    for i, p in enumerate(pts):
        check(
            f"frontier-pt{i} 权重和=1",
            abs(p["w"].sum() - 1.0) < 1e-6,
            f"sum={p['w'].sum():.9f}",
        )


def test_gmv_diversification() -> None:
    print("== 断言 2：GMV 波动率 ≤ 任一单资产波动率（分散化生效）==")
    for path in (PARAMS_A, PARAMS_STOCKS):
        mu, sigma, rf, tickers = load_params(path)
        w = gmv_numeric(mu, sigma)
        gmv_vol = float(np.sqrt(w @ sigma @ w))
        single_vols = np.sqrt(np.diag(sigma))
        check(
            f"{path.stem} GMV波动率≤单资产",
            gmv_vol <= single_vols.min() + 1e-9,
            f"gmv_vol={gmv_vol:.6f}, min_single_vol={single_vols.min():.6f}",
        )


def test_negative_correlation() -> None:
    print("== 断言 3：方案 A 相关矩阵含至少一个负相关系数（A2 验收）==")
    closes = pd.read_csv(RETURNS_A, index_col=0, parse_dates=True)
    returns = closes.pct_change().dropna()
    corr = returns.corr()
    n_neg = int((corr.values < 0).sum() // 2)  # 对称矩阵去重
    check(
        "方案A负相关系数存在",
        n_neg >= 1,
        f"负相关对数={n_neg}",
    )
    # 打印实测负相关对
    cols = corr.columns
    pairs = [
        (i, j, corr.iloc[i, j])
        for i in range(len(cols)) for j in range(i + 1, len(cols))
        if corr.iloc[i, j] < 0
    ]
    for i, j, v in pairs:
        print(f"      负相关对: {cols[i]}-{cols[j]} = {v:.4f}")


def test_frontier_monotone_convex() -> None:
    print("== 断言 4：前沿曲线单调凸（波动率随目标收益单调非降）==")
    mu, sigma, rf, _ = load_params(PARAMS_A)
    pts = frontier_scan(mu, sigma)
    assert len(pts) >= 5, f"方案 A 前沿可行点过少: {len(pts)}"
    vols = np.array([p["vol"] for p in pts])
    rets = np.array([p["ret"] for p in pts])

    # 有效前沿 = 从最低波动率点（GMV）往上的部分，波动率应单调非降
    i_gmv = int(np.argmin(vols))
    eff_vols = vols[i_gmv:]
    diffs = np.diff(eff_vols)
    # 允许 1e-6 数值容差（SLSQP 精度），不允许明显下降
    max_drop = -diffs.min() if len(diffs) else 0.0
    check(
        "前沿有效段波动率单调非降",
        (diffs >= -1e-6).all(),
        f"GMV点索引={i_gmv}, 最大下降={max_drop:.2e}, 点数={len(pts)}",
    )
    # 前沿总体形状：波动率范围非退化（弯曲存在）
    span = vols[-1] - vols[i_gmv]
    check(
        "前沿弯曲非退化",
        span > 1e-4,
        f"vol_span={span:.6f}",
    )


def main() -> int:
    for f in (
        test_weight_sum_one,
        test_gmv_diversification,
        test_negative_correlation,
        test_frontier_monotone_convex,
    ):
        f()
        print()
    print(f"=== 全部通过：{len(PASSED)} 项断言 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
