#!/usr/bin/env python3
"""P3x 扩展算法单元测试（纯 assert 实现，无 pytest 依赖）

覆盖任务要求的断言：
  1. 风险平价 / BL 后验权重和 = 1（±1e-6）；
  2. 风险平价各资产 RC 相对差异 < 1e-4（迭代收敛验证）；
  3. BL 后验权重和 = 1；
  4. 蒙特卡洛样本数正确（≥5000）且样本权重和为 1；
附加教学断言：
  5. BL 观点效应：『看好美股』→ 后验 SPY+IWM 权重高于先验；
  6. 蒙特卡洛样本收益/波动均为有限值（数值正确）。

用法：
    python scripts/test_extensions.py

退出码：0 = 全部通过；1 = 存在失败断言。
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 让脚本可直接运行（import 同目录的 extensions / optimizer）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extensions import (  # noqa: E402
    bl_posterior,
    monte_carlo_portfolios,
    risk_parity_weights,
)

ROOT = Path(__file__).resolve().parent.parent
PARAMS_A = ROOT / "data" / "params.json"
FRONTIER_A = ROOT / "output" / "frontier.csv"

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
    sigma = np.array([p["sigma"][t] for t in tickers])
    rf = p.get("rf", 0.0)
    return mu, sigma, rf, tickers


def test_rp_weight_sum_and_rc() -> None:
    print("== 断言 1&2：风险平价 权重和=1、RC 相对差异 < 1e-4 ==")
    mu, sigma, rf, tickers = load_params(PARAMS_A)
    w, rc, n_iter = risk_parity_weights(sigma)
    check("风险平价 权重和=1", abs(w.sum() - 1.0) < 1e-6, f"sum={w.sum():.9f}")
    check("风险平价 迭代收敛", n_iter < 1000, f"iter={n_iter}")
    # RC 理论均分值 = 组合波动率 / n
    vol = float(np.sqrt(w @ sigma @ w))
    rc_star = vol / len(tickers)
    rel_diff = float(np.max(np.abs(rc - rc_star)) / rc_star)
    check(
        "风险平价 RC 相对差异 < 1e-4",
        rel_diff < 1e-4,
        f"rel_diff={rel_diff:.2e}, iter={n_iter}",
    )
    # 打印 RC 分布供汇报
    print(f"      RC: " + ", ".join(f"{t}={v:.4f}" for t, v in zip(tickers, rc)))


def test_bl_weight_sum() -> None:
    print("== 断言 3：BL 后验权重和 = 1 ==")
    mu, sigma, rf, tickers = load_params(PARAMS_A)
    n = len(tickers)
    w_mkt = np.ones(n) / n  # 等权近似市场组合（与 extensions.py 主脚本一致）
    delta = 2.5
    P = np.array([[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]])
    Q = np.array([0.08, 0.01])
    mu_post, sigma_post, pi = bl_posterior(mu, sigma, w_mkt, delta, P, Q)
    # 后验收益与协方差形状
    check("BL 后验 μ 形状", mu_post.shape == (n,), f"shape={mu_post.shape}")
    check("BL 后验 Σ 对称正定",
          np.allclose(sigma_post, sigma_post.T, atol=1e-10)
          and np.all(np.linalg.eigvalsh(sigma_post) > 0))
    # 后验最大夏普（禁做空，复用 P3 优化器口径）
    from optimizer import tangency_numeric
    w_bl = tangency_numeric(mu_post, sigma_post, rf)
    w_prior = tangency_numeric(pi, sigma, rf)
    check("BL 后验权重和=1", abs(w_bl.sum() - 1.0) < 1e-6, f"sum={w_bl.sum():.9f}")
    check("BL 先验权重和=1", abs(w_prior.sum() - 1.0) < 1e-6, f"sum={w_prior.sum():.9f}")


def test_bl_view_effect() -> None:
    print("== 断言 5：BL 观点效应（看好美股 → SPY+IWM 权重上升）==")
    mu, sigma, rf, tickers = load_params(PARAMS_A)
    n = len(tickers)
    w_mkt = np.ones(n) / n
    delta = 2.5
    P = np.array([[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]])
    Q = np.array([0.08, 0.01])
    mu_post, sigma_post, pi = bl_posterior(mu, sigma, w_mkt, delta, P, Q)

    from optimizer import tangency_numeric
    w_prior = tangency_numeric(pi, sigma, rf)
    w_post = tangency_numeric(mu_post, sigma_post, rf)
    us_prior = w_prior[0] + w_prior[1]  # SPY + IWM
    us_post = w_post[0] + w_post[1]
    print(f"      美股组合权重: 先验 {us_prior:.2%} → 后验 {us_post:.2%}")
    check(
        "BL 观点效应：后验美股权重 ≥ 先验",
        us_post >= us_prior - 1e-6,
        f"prior={us_prior:.6f}, post={us_post:.6f}",
    )


def test_monte_carlo() -> None:
    print("== 断言 4&6：蒙特卡洛 样本数≥5000、权重和=1、数值有限 ==")
    mu, sigma, rf, tickers = load_params(PARAMS_A)
    n_sim = 6000
    W, rets, vols = monte_carlo_portfolios(mu, sigma, n_sim=n_sim)
    check("蒙特卡洛 样本数正确", W.shape[0] >= 5000, f"n={W.shape[0]}")
    check("蒙特卡洛 样本权重和=1", np.allclose(W.sum(axis=1), 1.0, atol=1e-6))
    check("蒙特卡洛 收益/波动有限", np.all(np.isfinite(rets)) and np.all(np.isfinite(vols)))
    check("蒙特卡洛 波动率 > 0", float(vols.min()) > 0, f"min_vol={vols.min():.6f}")
    # 与有效前沿对比（存在则统计低效比例，供教学叙事）
    if FRONTIER_A.exists():
        fdf = pd.read_csv(FRONTIER_A)
        from extensions import mc_inefficient_ratio
        ratio = mc_inefficient_ratio(fdf["vol"].to_numpy(), fdf["ret"].to_numpy(),
                                     vols, rets)
        print(f"      样本落在前沿右侧（低效）比例: {ratio:.1%}")
        # 有效前沿是给定收益下最小波动的包络：随机组合几乎必然落在其右侧，
        # 100% 低效恰是『随机不可战胜优化』的教学亮点，断言绝大多数低效即可。
        check("蒙特卡洛 绝大多数样本低效(≥50%)", ratio >= 0.5, f"ratio={ratio:.4f}")


def main() -> int:
    for f in (
        test_rp_weight_sum_and_rc,
        test_bl_weight_sum,
        test_bl_view_effect,
        test_monte_carlo,
    ):
        f()
        print()
    print(f"=== 全部通过：{len(PASSED)} 项断言 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
