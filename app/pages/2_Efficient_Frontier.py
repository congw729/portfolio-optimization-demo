#!/usr/bin/env python3
"""P5b Page 2 Efficient Frontier (core interactive page)

Controls: asset pool selectbox / risk-aversion γ slider / no-short checkbox.
γ change → real-time solve max wᵀμ − 0.5γ·wᵀΣw (lightweight SLSQP) → star/CML/metric cards update.
Data: output/frontier*.csv (frontier), output/mc_points.csv (Monte Carlo cloud),
      data/params*.json (mu/Sigma/rf), data/features.json (asset class colors).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from utils import (  # noqa: E402
    POOLS,
    load_pool,
    solve_utility,
)

st.set_page_config(page_title="Efficient Frontier", layout="wide")
st.title("2️⃣ Efficient Frontier — Drag γ to Move the Portfolio")

# ---- Controls ----
c_ctl = st.columns([2, 2, 1])
with c_ctl[0]:
    pool_key = st.selectbox("Asset Pool", list(POOLS.keys()), key="ef_pool")
with c_ctl[1]:
    gamma = st.slider("Risk-Aversion γ", 0.5, 20.0, 5.0, 0.5, key="gamma",
                      help="Higher γ → more conservative (portfolio moves toward lower volatility)")
with c_ctl[2]:
    no_short = st.checkbox("No Short Selling (w≥0)", value=True, key="no_short")

d = load_pool(pool_key)
tickers, mu, sigma, rf = d["tickers"], d["mu"], d["sigma"], d["rf"]
frontier, mc = d["frontier"], d["mc"]
params = d["params"]

# Real-time solve for current γ
w = solve_utility(mu, sigma, gamma, no_short)
ret = float(w @ mu)
vol = float(np.sqrt(w @ sigma @ w))
sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")

# ---- Chart ----
fig = go.Figure()

# Monte Carlo gray cloud (Portfolio A has mc_points.csv; baseline skips)
if not mc.empty:
    fig.add_trace(go.Scatter(
        x=mc["vol"], y=mc["ret"], mode="markers",
        marker=dict(size=3, color="rgba(150,150,150,0.45)"),
        name="Monte Carlo portfolios", hoverinfo="skip",
    ))

# Efficient frontier line
if not frontier.empty:
    fig.add_trace(go.Scatter(
        x=frontier["vol"], y=frontier["ret"], mode="lines+markers",
        line=dict(color="#4C72B0", width=2.5),
        marker=dict(size=4, color="#4C72B0"),
        name="Efficient Frontier", hovertemplate="vol=%{x:.2%}<br>ret=%{y:.2%}<extra></extra>",
    ))

# CML: from (0, rf) through the current portfolio
if vol > 1e-9:
    slope = (ret - rf) / vol
    x_max = max(vol * 1.8, frontier["vol"].max() * 0.95 if not frontier.empty else vol * 1.8)
    x_cml = np.linspace(0, x_max, 40)
    fig.add_trace(go.Scatter(
        x=x_cml, y=rf + slope * x_cml, mode="lines",
        line=dict(color="#DD8452", dash="dash", width=1.8),
        name=f"CML (rf={rf:.2%})", hoverinfo="skip",
    ))

# Current γ portfolio star
fig.add_trace(go.Scatter(
    x=[vol], y=[ret], mode="markers+text",
    marker=dict(symbol="star", size=22, color="#C44E52", line=dict(color="white", width=1)),
    text=[f"γ={gamma:g}"], textposition="top center",
    name=f"Current portfolio (γ={gamma:g})",
    hovertemplate=f"γ={gamma:g}<br>ret=%{{y:.2%}}<br>vol=%{{x:.2%}}<extra></extra>",
))

# Single assets
single_vol = np.sqrt(np.diag(sigma))
fig.add_trace(go.Scatter(
    x=single_vol, y=mu, mode="markers+text",
    marker=dict(symbol="diamond", size=11, color="#333333"),
    text=tickers, textposition="top right", textfont=dict(size=11),
    name="Single assets",
    hovertemplate="%{text}<br>vol=%{x:.2%}<br>ret=%{y:.2%}<extra></extra>",
))

# rf point
fig.add_trace(go.Scatter(
    x=[0], y=[rf], mode="markers+text",
    marker=dict(symbol="circle", size=12, color="#DD8452"),
    text=[f"rf={rf:.2%}"], textposition="top right",
    name="Risk-free rate", hoverinfo="skip",
))

fig.update_layout(
    title=f"Markowitz Efficient Frontier — {pool_key}",
    xaxis_title="Annualized Volatility",
    yaxis_title="Annualized Return",
    height=600,
    hovermode="closest",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
    margin=dict(l=40, r=20, t=70, b=40),
)
st.plotly_chart(fig, width="stretch")

# ---- Metric cards ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Annual Return", f"{ret:.2%}")
c2.metric("Annual Volatility", f"{vol:.2%}")
c3.metric("Sharpe Ratio", f"{sharpe:.3f}")
c4.metric("Risk-Aversion γ", f"{gamma:g}")

# ---- Weight detail ----
st.subheader("Current Portfolio Weights")
w_df = pd.DataFrame({
    "Asset": tickers,
    "Class": [params.get("asset_class", {}).get(t, "-") for t in tickers],
    "Weight": w,
})
w_df["Weight%"] = (w_df["Weight"] * 100).round(2)
st.dataframe(w_df[["Asset", "Class", "Weight%"]], hide_index=True, width="stretch")

# By-class summary
st.caption("Weights by asset class")
cat = w_df.groupby("Class")["Weight"].sum().sort_values(ascending=False)
cat_df = pd.DataFrame({"Class": cat.index, "Weight%": (cat.values * 100).round(2)})
fig_cat = go.Figure(go.Bar(
    x=cat_df["Weight%"], y=cat_df["Class"], orientation="h",
    marker=dict(color="#4C72B0"),
))
fig_cat.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                      xaxis_title="Weight %", yaxis_title="")
st.plotly_chart(fig_cat, width="stretch")

st.caption("Teaching point: small γ → upper-right (higher return/risk); large γ → lower-left (conservative). Uncheck no-short to see the frontier extend.")
