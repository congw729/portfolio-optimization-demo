#!/usr/bin/env python3
"""P5 可选 Streamlit dashboard：交互式查看组合与有效前沿（不重算数据管道）

读入 P2/P3 产物（data/params*.json + output/frontier*.csv），控件：
  - 资产池选择：方案 A（跨资产类别 ETF）/ 基线（6 只个股）
  - 风险厌恶系数 γ slider：实时求解效用最大化组合 max wᵀμ − 0.5γ·wᵀΣw
  - 禁做空 checkbox：bounds=(0,1) / 无界

运行：
    streamlit run output/dashboard.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# 兼容直接运行（scripts/ 或 output/ 两种启动目录）
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"

POOLS = {
    "方案 A（跨资产类别 ETF）": {
        "params": DATA / "params.json",
        "frontier": OUT / "frontier.csv",
    },
    "基线（6 只个股）": {
        "params": DATA / "params_stocks.json",
        "frontier": OUT / "frontier_stocks.csv",
    },
}


@st.cache_data
def load(pool_key: str) -> dict:
    p = POOLS[pool_key]
    with open(p["params"], encoding="utf-8") as f:
        params = json.load(f)
    frontier = pd.read_csv(p["frontier"])
    tickers = params["tickers"]
    mu = np.array([params["mu"][t] for t in tickers])
    sigma = np.array([params["sigma"][t] for t in tickers])
    rf = params.get("rf", 0.0)
    return {"tickers": tickers, "mu": mu, "sigma": sigma, "rf": rf,
            "frontier": frontier, "params": params}


def solve_utility(mu: np.ndarray, sigma: np.ndarray, gamma: float,
                  no_short: bool) -> np.ndarray:
    """求解效用最大化组合：max wᵀμ − 0.5γ·wᵀΣw，约束权重和=1，可选禁做空。"""
    from scipy.optimize import minimize

    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0.0, 1.0)] * n if no_short else None

    def neg_utility(w: np.ndarray) -> float:
        return -(w @ mu - 0.5 * gamma * (w @ sigma @ w))

    res = minimize(neg_utility, x0=np.ones(n) / n, method="SLSQP",
                   constraints=cons, bounds=bounds,
                   options={"ftol": 1e-12, "maxiter": 500})
    return res.x


def main() -> None:
    st.set_page_config(page_title="投资组合优化 Demo", layout="wide")
    st.title("📊 马科维茨投资组合优化 — 交互式 Demo")
    st.caption("数据来源：yfinance 近 5 年日线（auto_adjust），消费 P2/P3 产物，不重算数据管道")

    with st.sidebar:
        st.header("参数控制")
        pool_key = st.selectbox("资产池", list(POOLS.keys()))
        gamma = st.slider("风险厌恶系数 γ", 0.5, 20.0, 5.0, 0.5,
                          help="γ 越大越保守（更偏向低波动组合）")
        no_short = st.checkbox("禁做空（w≥0）", value=True)
        st.divider()
        st.caption("数据缓存: data/ ｜ 参数: params.json ｜ 前沿: frontier.csv")

    d = load(pool_key)
    tickers, mu, sigma, rf = d["tickers"], d["mu"], d["sigma"], d["rf"]
    frontier = d["frontier"]
    params = d["params"]

    # 实时求解组合
    w = solve_utility(mu, sigma, gamma, no_short)
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ sigma @ w))
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")

    c1, c2, c3 = st.columns(3)
    c1.metric("组合年化收益", f"{ret:.2%}")
    c2.metric("组合年化波动率", f"{vol:.2%}")
    c3.metric("夏普比率", f"{sharpe:.3f}")

    # 有效前沿 + 当前组合
    st.subheader("有效前沿")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC"]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(frontier["vol"], frontier["ret"], color="#4C72B0", lw=2.5,
            label="有效前沿")
    ax.scatter(frontier["vol"], frontier["ret"], color="#4C72B0", s=12)
    ax.scatter([vol], [ret], marker="*", s=320, color="#C44E52", zorder=5,
               edgecolor="white", label=f"当前组合（γ={gamma}, {"禁做空" if no_short else "允许做空"}）")
    # rf 点与 CML
    if vol > 1e-9:
        slope = (ret - rf) / vol
        x_cml = np.linspace(0, max(vol * 1.5, frontier["vol"].max() * 0.9), 40)
        ax.plot(x_cml, rf + slope * x_cml, "--", color="#DD8452", lw=1.5,
                label=f"CML（rf={rf:.2%}）")
    ax.scatter([0], [rf], s=50, color="#DD8452", zorder=4)
    # 单资产点
    single_vol = np.sqrt(np.diag(sigma))
    ax.scatter(single_vol, mu, marker="D", s=55, color="#333333", zorder=4)
    for t, v, r in zip(tickers, single_vol, mu):
        ax.annotate(t, (v, r), textcoords="offset points", xytext=(6, 4),
                    fontsize=8, color="#333333")
    ax.set_xlabel("年化波动率")
    ax.set_ylabel("年化收益")
    ax.set_title(f"有效前沿 — {pool_key}")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)
    st.pyplot(fig)

    # 权重表
    st.subheader("组合权重")
    w_df = pd.DataFrame({"资产": tickers, "类别": [params["asset_class"].get(t, "-") for t in tickers],
                         "权重": w})
    w_df["权重%"] = (w_df["权重"] * 100).round(2)
    st.dataframe(w_df[["资产", "类别", "权重%"]], hide_index=True,
                 use_container_width=True)

    # 按类别汇总
    st.caption("按资产类别汇总权重")
    cat = w_df.groupby("类别")["权重"].sum().sort_values(ascending=False)
    st.bar_chart((cat * 100).round(2))


if __name__ == "__main__":
    main()
