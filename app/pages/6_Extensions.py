#!/usr/bin/env python3
"""P5b Page 6 Extensions comparison: Risk Parity / BL / Monte Carlo vs Mean-Variance

Controls: comparison dimension selectbox (metrics table / return-risk scatter / risk contribution bars),
          (scatter mode) overlay Monte Carlo cloud checkbox.
Data: output/extensions_summary.csv (pool/combo/note/ret/vol/sharpe/max_dd/w_*/rc_*),
      output/mc_points.csv (Monte Carlo samples), output/portfolios.csv (Mean-Variance reference).
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
    OUT,
    POOLS,
    load_features,
    load_pool,
)

st.set_page_config(page_title="Extensions", layout="wide")
st.title("6️⃣ Extensions — Risk Parity / BL / Monte Carlo vs Mean-Variance")

# ---- Data ----
ext_path = OUT / "extensions_summary.csv"
if not ext_path.exists():
    st.warning("output/extensions_summary.csv not found. Run scripts/extensions.py first.")
    st.stop()
ext = pd.read_csv(ext_path)

mc_path = OUT / "mc_points.csv"
mc = pd.read_csv(mc_path) if mc_path.exists() else pd.DataFrame()

d = load_pool("Portfolio A (Cross-Asset ETFs)")
tickers = d["tickers"]
asset_class = d["params"].get("asset_class", {})
feats = load_features()

# ---- Controls ----
dim = st.selectbox("Comparison Dimension", ["Metrics table", "Return-Risk Scatter", "Risk Contribution Bars"],
                   key="ex_dim")
show_mc = False
if dim == "Return-Risk Scatter":
    show_mc = st.checkbox("Overlay Monte Carlo cloud", value=True, key="ex_mc")

# Methods usable in charts (exclude the Monte Carlo summary row — no single weight)
methods = ext[ext["combo"].str.contains("蒙特卡洛") == False].copy()  # noqa: E712

# ---- ① Metrics table ----
if dim == "Metrics table":
    st.subheader("Portfolio Metrics by Algorithm")
    cols_show = ["combo", "ret", "vol", "sharpe", "max_dd", "note"]
    tbl = ext[cols_show].rename(columns={
        "combo": "Algorithm / Portfolio", "ret": "Annual Return", "vol": "Annual Volatility",
        "sharpe": "Sharpe Ratio", "max_dd": "Max Drawdown", "note": "Note",
    })
    tbl["Annual Return"] = (tbl["Annual Return"] * 100).round(2).astype(str) + "%"
    tbl["Annual Volatility"] = (tbl["Annual Volatility"] * 100).round(2).astype(str) + "%"
    tbl["Max Drawdown"] = (tbl["Max Drawdown"] * 100).round(2).astype(str) + "%"
    st.dataframe(tbl, hide_index=True, width="stretch")
    st.markdown(
        "**Narrative**:\n"
        "- Mean-Variance (GMV/Tangency) relies on return forecasts;\n"
        "- Risk Parity does not need return forecasts — it equalizes risk contributions (RC) using only the covariance;\n"
        "- Black-Litterman starts from the market-equilibrium prior and applies a Bayesian posterior update with subjective views;\n"
        "- Monte Carlo shows the distribution of random weight portfolios (almost all fall to the right of the frontier)."
    )

# ---- ② Return-Risk scatter ----
elif dim == "Return-Risk Scatter":
    fig = go.Figure()
    if show_mc and not mc.empty:
        fig.add_trace(go.Scatter(
            x=mc["vol"], y=mc["ret"], mode="markers",
            marker=dict(size=3, color="rgba(150,150,150,0.4)"),
            name="Monte Carlo portfolios", hoverinfo="skip",
        ))
    # Frontier line (Portfolio A)
    frontier = d["frontier"]
    if not frontier.empty:
        fig.add_trace(go.Scatter(
            x=frontier["vol"], y=frontier["ret"], mode="lines",
            line=dict(color="#4C72B0", width=2), name="Efficient Frontier",
            hovertemplate="vol=%{x:.2%}<br>ret=%{y:.2%}<extra></extra>",
        ))
    # Algorithm points
    labels = {"GMV_数值(禁做空)": "GMV", "切线_数值(禁做空)": "Tangency",
              "风险平价": "Risk Parity", "BL_先验切线(均衡收益)": "BL Prior",
              "BL_后验切线(叠加观点)": "BL Posterior"}
    colors_map = {"GMV": "#55A868", "Tangency": "#C44E52", "Risk Parity": "#8172B2",
                  "BL Prior": "#DD8452", "BL Posterior": "#4C72B0"}
    for _, row in methods.iterrows():
        combo = row["combo"]
        if not np.isfinite(row["vol"]) or not np.isfinite(row["ret"]):
            continue
        label = labels.get(combo, combo)
        fig.add_trace(go.Scatter(
            x=[row["vol"]], y=[row["ret"]], mode="markers+text",
            marker=dict(symbol="star" if label in ("GMV", "Tangency") else "circle",
                        size=16 if label in ("GMV", "Tangency") else 13,
                        color=colors_map.get(label, "#888888"),
                        line=dict(color="white", width=1)),
            text=[label], textposition="top center",
            name=label,
            hovertemplate=f"{label}<br>ret=%{{y:.2%}}<br>vol=%{{x:.2%}}<extra></extra>",
        ))
    fig.update_layout(
        title="Extensions vs Mean-Variance — Return-Risk Plane",
        xaxis_title="Annualized Volatility", yaxis_title="Annualized Return",
        height=560, hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption("Teaching point: Mean-Variance tangency has the highest Sharpe but relies on return forecasts; "
               "Risk Parity is more diversified at similar volatility; the BL posterior position reflects the views; "
               "Monte Carlo cloud almost all lies to the right of the frontier.")

# ---- ③ Risk contribution bars ----
else:
    rp = ext[ext["combo"] == "风险平价"]
    if rp.empty:
        st.warning("No Risk Parity row in extensions_summary.csv. Run scripts/extensions.py first.")
        st.stop()
    rc_cols = [c for c in rp.columns if c.startswith("rc_")]
    rc_vals = rp.iloc[0][rc_cols].to_numpy(dtype=float)
    rc_tickers = [c[3:] for c in rc_cols]  # rc_SPY → SPY
    fig = go.Figure(go.Bar(
        x=rc_tickers, y=rc_vals,
        marker=dict(color=[asset_class.get(t, "#999999") for t in rc_tickers]),
        text=[f"{v:.2%}" for v in rc_vals], textposition="outside",
        hovertemplate="%{x}: RC=%{y:.2%}<extra></extra>",
    ))
    fig.update_layout(
        title="Risk Parity Portfolio — Risk Contributions RCᵢ = wᵢ(Σw)ᵢ/√(wᵀΣw) (equal = converged)",
        xaxis_title="Asset", yaxis_title="Risk Contribution RC",
        height=460, yaxis=dict(tickformat=".0%"),
    )
    st.plotly_chart(fig, width="stretch")

    # Weight comparison table
    st.subheader("Weight Comparison (Risk Parity vs Mean-Variance)")
    rows = []
    for combo in ("GMV_数值(禁做空)", "切线_数值(禁做空)", "风险平价",
                  "BL_后验切线(叠加观点)"):
        row = ext[ext["combo"] == combo]
        if row.empty:
            continue
        r = row.iloc[0]
        w_row = {"Algorithm / Portfolio": combo}
        for t in tickers:
            w_row[t] = f"{r[f'w_{t}']:.1%}" if pd.notna(r.get(f"w_{t}", np.nan)) else "—"
        rows.append(w_row)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Teaching point: Risk Parity does not rely on return forecasts — it equalizes risk across every asset "
               "(low-volatility bonds/gold/commodities naturally receive higher weights).")

st.divider()
st.caption("Data source: output/extensions_summary.csv + output/mc_points.csv (P3x artifacts, read-only)")
