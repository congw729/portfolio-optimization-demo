#!/usr/bin/env python3
"""P3x 可选扩展算法：风险平价 / Black-Litterman / 蒙特卡洛模拟

消费方案 A 的 data/params.json 与 data/returns_assetclass.csv
（对照准备清单 §3.3，依赖均为 numpy/pandas，无需新库）。

实现：
  1. 风险平价（Risk Parity）：迭代求解使各资产风险贡献
     RCᵢ = wᵢ(Σw)ᵢ/√(wᵀΣw) 相等（上限 1000 次、容差 1e-6），
     输出权重与 RC 分布；与均值-方差 GMV 对比（不依赖收益预测）；
  2. Black-Litterman：逆优化求市场均衡收益 π = δ·Σ·w_mkt
     （δ=2.5，w_mkt 用等权替代并注明假设），叠加 2 条主观观点
     （① 看好美股权益：SPY/IWM 平均年化收益 8%（高于均衡）；
      ② 黄金低配：GLD 年化收益 1%（低于均衡）），求后验 μ/Σ，
     再解最大夏普组合（禁做空数值优化，与 P3 主口径一致）；
  3. 蒙特卡洛模拟：np.random.dirichlet 生成 6000 个随机组合，
     输出样本点（output/mc_points.csv）供与有效前沿叠加，
     并统计「落在前沿右侧（低效区）的比例」。

用法：
    python scripts/extensions.py

产出：
    output/extensions_summary.csv  各扩展权重与指标汇总表（供汇报 agent 引用）
    output/mc_points.csv           蒙特卡洛样本点（ret/vol，供 viz 叠加）
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 复用 P3 优化器（同目录）：GMV / 切线 / 指标口径保持一致
sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimizer import (  # noqa: E402
    gmv_numeric,
    max_drawdown,
    portfolio_metrics,
    tangency_numeric,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"
OUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. 风险平价
# ---------------------------------------------------------------------------


def risk_parity_weights(
    sigma: np.ndarray, max_iter: int = 1000, tol: float = 1e-6
) -> tuple[np.ndarray, np.ndarray, int]:
    """风险平价：迭代使各资产风险贡献 RCᵢ = wᵢ(Σw)ᵢ/√(wᵀΣw) 相等。

    迭代规则（经典乘性更新）：
      rc_rawᵢ = wᵢ(Σw)ᵢ          （Σᵢ rc_rawᵢ = wᵀΣw = vol²）
      rc_star = vol² / n           （RC 全等时每项 = 总风险²/n）
      wᵢ ← wᵢ · sqrt(rc_star / rc_rawᵢ)，再归一化

    收敛判据：max|rc_raw − rc_star| / rc_star < tol。
    返回 (权重, 标准 RC 分布 RCᵢ=wᵢ(Σw)ᵢ/√(wᵀΣw), 迭代次数)。
    """
    n = sigma.shape[0]
    w = np.ones(n) / n
    rc_raw = np.ones(n)
    for it in range(max_iter):
        sigma_w = sigma @ w
        rc_raw = w * sigma_w  # 未除以 vol 的原始风险贡献
        vol2 = float(w @ sigma_w)
        rc_star = vol2 / n
        rel_diff = float(np.max(np.abs(rc_raw - rc_star)) / max(rc_star, 1e-12))
        if rel_diff < tol:
            break
        # 乘性更新（保护除零：rc_raw 下限 1e-12）
        w = w * np.sqrt(np.maximum(rc_star / np.maximum(rc_raw, 1e-12), 0.0))
        w = w / w.sum()
    vol = np.sqrt(float(w @ sigma @ w))
    rc = w * (sigma @ w) / vol  # 标准 RC 定义（分母为组合波动率）
    return w, rc, it + 1


# ---------------------------------------------------------------------------
# 2. Black-Litterman
# ---------------------------------------------------------------------------


def bl_posterior(
    mu: np.ndarray,
    sigma: np.ndarray,
    w_mkt: np.ndarray,
    delta: float,
    P: np.ndarray,
    Q: np.ndarray,
    tau: float = 0.05,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Black-Litterman 后验收益与协方差。

    逆优化：市场均衡收益 π = δ·Σ·w_mkt（δ 为风险厌恶系数）；
    观点：P·μ = Q + ε，ε~N(0, Ω)，Ω = diag(P·(τΣ)·Pᵀ)（He-Litterman 简化）；
    后验：μ_post = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ · [(τΣ)⁻¹π + PᵀΩ⁻¹Q]
          Σ_post = Σ + [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹
    返回 (μ_post, Σ_post, π)。
    """
    n = len(mu)
    pi = delta * sigma @ w_mkt  # 逆优化均衡收益
    omega = P @ (tau * sigma) @ P.T
    omega = np.diag(np.diag(omega))  # 对角化观点不确定性
    omega = np.maximum(omega, 1e-12 * np.eye(len(Q)))  # 保证正定
    tau_sigma_inv = np.linalg.inv(tau * sigma)
    m_inv = np.linalg.inv(tau_sigma_inv + P.T @ np.linalg.inv(omega) @ P)
    mu_post = m_inv @ (tau_sigma_inv @ pi + P.T @ np.linalg.inv(omega) @ Q)
    sigma_post = sigma + m_inv
    return mu_post, sigma_post, pi


# ---------------------------------------------------------------------------
# 3. 蒙特卡洛模拟
# ---------------------------------------------------------------------------


def monte_carlo_portfolios(
    mu: np.ndarray, sigma: np.ndarray, n_sim: int = 6000, seed: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """np.random.dirichlet 生成 n_sim 个随机权重组合，返回 (权重, 收益, 波动)。"""
    rng = np.random.default_rng(seed)
    W = rng.dirichlet(np.ones(len(mu)), size=n_sim)
    rets = W @ mu
    vols = np.sqrt(np.einsum("ij,jk,ik->i", W, sigma, W))
    return W, rets, vols


def mc_inefficient_ratio(frontier_vol: np.ndarray, frontier_ret: np.ndarray,
                         mc_vol: np.ndarray, mc_ret: np.ndarray) -> float:
    """蒙特卡洛样本落在有效前沿右侧（给定收益下波动更大 → 低效）的比例。"""
    if len(frontier_vol) < 2:
        return float("nan")
    # 用线性插值估计每个样本收益对应的前沿波动率
    f_vol = np.interp(mc_ret, frontier_ret, frontier_vol)
    return float(np.mean(mc_vol > f_vol + 1e-9))


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="P3x 可选扩展算法（风险平价/BL/蒙特卡洛）")
    p.add_argument("--params", default=str(DATA / "params.json"),
                   help="参数 JSON，默认 data/params.json")
    p.add_argument("--returns", default=str(DATA / "returns_assetclass.csv"),
                   help="日收益率 CSV，默认 data/returns_assetclass.csv")
    p.add_argument("--n-sim", type=int, default=6000, help="蒙特卡洛样本数，默认 6000")
    p.add_argument("--output-dir", default=str(OUT), help="输出目录，默认 output/")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 读取 P2 参数与日收益率
    with open(args.params, encoding="utf-8") as f:
        params = json.load(f)
    tickers: list[str] = params["tickers"]
    mu = np.array([params["mu"][t] for t in tickers])
    sigma = np.array([params["sigma"][t] for t in tickers])
    rf = params.get("rf", 0.0)
    asset_class = params.get("asset_class", {})
    returns_df = pd.read_csv(args.returns, index_col=0, parse_dates=True)
    returns_df = returns_df[tickers]
    n = len(tickers)

    print(f"=== P3x 扩展算法：{len(tickers)} 资产，rf={rf:.4f} ===")

    # ---- 参照：均值-方差主结果（P3 主口径，禁做空数值优化）----
    w_gmv = gmv_numeric(mu, sigma)
    w_tan = tangency_numeric(mu, sigma, rf)
    m_gmv = portfolio_metrics(w_gmv, mu, sigma, rf, returns_df)
    m_tan = portfolio_metrics(w_tan, mu, sigma, rf, returns_df)

    # ---- 1. 风险平价 ----
    w_rp, rc_rp, n_iter = risk_parity_weights(sigma)
    m_rp = portfolio_metrics(w_rp, mu, sigma, rf, returns_df)
    rc_star = np.sqrt(float(w_rp @ sigma @ w_rp)) / n  # 理论均分值
    rc_rel_diff = float(np.max(np.abs(rc_rp - rc_star)) / rc_star)
    print(f"\n[1] 风险平价：迭代 {n_iter} 次收敛，RC 相对差异={rc_rel_diff:.2e}")
    print(f"    权重: " + ", ".join(f"{t}={w:.1%}" for t, w in zip(tickers, w_rp)))
    print(f"    RC  : " + ", ".join(f"{t}={rc:.2%}" for t, rc in zip(tickers, rc_rp)))

    # ---- 2. Black-Litterman ----
    # 假设：无各 ETF 精确市值权重数据，w_mkt 用等权 1/n 近似市场组合（任务允许，注明假设）
    w_mkt = np.ones(n) / n
    delta = 2.5  # 风险厌恶系数（2-3 区间取中值）
    # 观点 ① 看好美股权益：SPY/IWM 平均年化收益 8%（绝对观点，高于均衡 π）
    # 观点 ② 黄金低配：GLD 年化收益 1%（绝对观点，低于均衡 π ≈ 2.7%）
    P = np.array([[0.5, 0.5, 0.0, 0.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]])
    Q = np.array([0.08, 0.01])
    mu_post, sigma_post, pi = bl_posterior(mu, sigma, w_mkt, delta, P, Q)
    # 后验最大夏普（禁做空，与 P3 主口径一致）；先验切线（均衡收益 π）作对比
    w_bl = tangency_numeric(mu_post, sigma_post, rf)
    w_bl_prior = tangency_numeric(pi, sigma, rf)
    m_bl = portfolio_metrics(w_bl, mu_post, sigma_post, rf, returns_df)
    m_bl_prior = portfolio_metrics(w_bl_prior, pi, sigma, rf, returns_df)
    print(f"\n[2] Black-Litterman：δ={delta}, w_mkt=等权(假设), "
          f"观点①看好美股(SPY/IWM 平均 8%) 观点②黄金低配(GLD 1%)")
    print(f"    均衡收益 π: " + ", ".join(f"{t}={p:.2%}" for t, p in zip(tickers, pi)))
    print(f"    后验收益 μ: " + ", ".join(f"{t}={p:.2%}" for t, p in zip(tickers, mu_post)))
    print(f"    后验权重: " + ", ".join(f"{t}={w:.1%}" for t, w in zip(tickers, w_bl)))

    # ---- 3. 蒙特卡洛模拟 ----
    W_mc, mc_ret, mc_vol = monte_carlo_portfolios(mu, sigma, args.n_sim)
    # 与有效前沿对比：读取 P3 前沿（存在则统计低效比例）
    frontier_path = out_dir / "frontier.csv"
    mc_ineff = float("nan")
    if frontier_path.exists():
        fdf = pd.read_csv(frontier_path)
        mc_ineff = mc_inefficient_ratio(
            fdf["vol"].to_numpy(), fdf["ret"].to_numpy(), mc_vol, mc_ret
        )
    print(f"\n[3] 蒙特卡洛：{args.n_sim} 个随机组合（dirichlet）"
          f"{'，低效比例(前沿右侧)=' + f'{mc_ineff:.1%}' if np.isfinite(mc_ineff) else ''}")
    print(f"    样本收益 {mc_ret.mean():.2%}±{mc_ret.std():.2%}，"
          f"波动 {mc_vol.mean():.2%}±{mc_vol.std():.2%}")

    # ---- 汇总表 output/extensions_summary.csv ----
    rows = []
    for name, w, m, note in (
        ("GMV_数值(禁做空)", w_gmv, m_gmv, "均值-方差主结果：最小方差，分散化基线"),
        ("切线_数值(禁做空)", w_tan, m_tan, "均值-方差主结果：最大夏普"),
        ("风险平价", w_rp, m_rp,
         "不依赖收益预测：各资产风险贡献 RC 相等（迭代收敛）"),
        ("BL_先验切线(均衡收益)", w_bl_prior, m_bl_prior,
         "BL 先验：逆优化 π=δΣw_mkt（等权假设）下的切线组合，无主观观点"),
        ("BL_后验切线(叠加观点)", w_bl, m_bl,
         "BL 后验：叠加『看好美股权益』『黄金低配』观点后的最大夏普组合"),
    ):
        row = {"pool": "assetclass", "combo": name, "note": note}
        row["ret"] = round(m["ret"], 6)
        row["vol"] = round(m["vol"], 6)
        row["sharpe"] = round(m["sharpe"], 6)
        row["max_dd"] = round(m["max_dd"], 6)
        for i, t in enumerate(tickers):
            row[f"w_{t}"] = round(float(w[i]), 6)
        if name == "风险平价":
            for i, t in enumerate(tickers):
                row[f"rc_{t}"] = round(float(rc_rp[i]), 6)
        rows.append(row)
    # 蒙特卡洛统计行（无单一权重，用均值/样本数说明）
    rows.append({
        "pool": "assetclass", "combo": f"蒙特卡洛模拟({args.n_sim}样本)",
        "note": f"dirichlet 随机组合，低效比例(前沿右侧)={mc_ineff:.1%}"
                if np.isfinite(mc_ineff) else "dirichlet 随机组合",
        "ret": round(float(mc_ret.mean()), 6),
        "vol": round(float(mc_vol.mean()), 6),
        "sharpe": float("nan"), "max_dd": float("nan"),
    })
    summary_df = pd.DataFrame(rows)
    summary_path = out_dir / "extensions_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    print(f"\n[OK] 汇总: {summary_path}")

    # 蒙特卡洛样本点（供 viz 前沿叠加）
    mc_points = pd.DataFrame({"ret": mc_ret, "vol": mc_vol})
    mc_points_path = out_dir / "mc_points.csv"
    mc_points.to_csv(mc_points_path, index=False)
    print(f"[OK] 蒙特卡洛样本点: {mc_points_path}")

    # ---- 与均值-方差主结果对比说明 ----
    print("\n=== 与均值-方差主结果（output/portfolios.csv）对比 ===")
    mv_path = out_dir / "portfolios.csv"
    if mv_path.exists():
        mv = pd.read_csv(mv_path)
        gmv_row = mv[mv["combo"] == "GMV_数值(禁做空)"].iloc[0]
        tan_row = mv[mv["combo"] == "切线_数值(禁做空)"].iloc[0]
        print(f"  P3 GMV  : ret={gmv_row['ret']:+.2%}, vol={gmv_row['vol']:.2%}, "
              f"sharpe={gmv_row['sharpe']:.3f}")
        print(f"  P3 切线 : ret={tan_row['ret']:+.2%}, vol={tan_row['vol']:.2%}, "
              f"sharpe={tan_row['sharpe']:.3f}")
    print(f"  风险平价 : ret={m_rp['ret']:+.2%}, vol={m_rp['vol']:.2%}, "
          f"sharpe={m_rp['sharpe']:.3f}  "
          f"（vs GMV: Δret={m_rp['ret']-m_gmv['ret']:+.2%}, "
          f"Δvol={m_rp['vol']-m_gmv['vol']:+.2%}）")
    print(f"  BL 先验 : ret={m_bl_prior['ret']:+.2%}, vol={m_bl_prior['vol']:.2%}, "
          f"sharpe={m_bl_prior['sharpe']:.3f}  （vs 切线: 均衡收益口径）")
    print(f"  BL 后验 : ret={m_bl['ret']:+.2%}, vol={m_bl['vol']:.2%}, "
          f"sharpe={m_bl['sharpe']:.3f}  （叠加观点后美股权重变化: "
          f"SPY+IWM {w_bl_prior[0]+w_bl_prior[1]:.1%}→{w_bl[0]+w_bl[1]:.1%}）")

    # 教学叙事
    print("\n=== 教学叙事（供汇报 agent 引用）===")
    print("  1. 风险平价：不依赖收益预测，只凭协方差把风险均分到每类资产；"
          "与 GMV 相比牺牲少量收益换取风险贡献均衡（债/金天然低波动，被赋予更高权重）。")
    print("  2. Black-Litterman：从市场均衡先验出发，主观观点通过贝叶斯更新改变后验收益，"
          "『看好美股』推高 SPY/IWM 权重、『黄金低配』压低 GLD，展示观点如何影响组合。")
    print("  3. 蒙特卡洛：dirichlet 随机权重组合在收益-风险平面上形成灰点云，"
          "绝大部分落在有效前沿右侧（低效区），直观展示『随机不可战胜优化』。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
