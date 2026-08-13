#!/usr/bin/env python3
"""P5b Page 3 Weights: portfolio weight bars (colored by asset class)

Controls: portfolio selectbox (GMV numeric / Tangency numeric / custom γ), pool selectbox,
          display mode toggle (detail bars / by-class summary).
Data: output/portfolios.csv (GMV/Tangency weight columns), Page-2 γ real-time solve
      (custom, session_state link), data/features.json (asset_class mapping).
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
    CLASS_COLORS,
    POOLS,
    combo_weights,
    load_pool,
    solve_utility,
)

st.set_page_config(page_title="Weights", layout="wide")
st.title("3️⃣ Weights — Portfolio Weights by Asset Class")

# ---- Controls ----
pool_key = st.selectbox("Asset Pool", list(POOLS.keys()), key="wd_pool")
d = load_pool(pool_key)
tickers = d["tickers"]
params = d["params"]
asset_class = params.get("asset_class", {})

combo_choices = ["GMV (no short)", "Tangency (no short)", "Custom γ (linked to Page 2)"]
combo = st.selectbox("Portfolio", combo_choices, key="wd_combo")

mode = st.radio("Display Mode", ["Detail bars", "By-class summary"], horizontal=True, key="wd_mode")

# ---- Weight source ----
if combo == "Custom γ (linked to Page 2)":
    gamma = st.session_state.get("gamma", 5.0)
    no_short = st.session_state.get("no_short", True)
    w = solve_utility(d["mu"], d["sigma"], gamma, no_short)
    w_label = f"Custom γ={gamma:g}"
else:
    w = combo_weights(d["portfolios"], combo)
    w_label = combo
    gamma = None

if w is None:
    st.warning("Weights not found (artifacts missing). Run scripts/optimizer.py first.")
    st.stop()

# ---- Chart ----
colors = [CLASS_COLORS.get(asset_class.get(t, "equity-us"), "#999999") for t in tickers]

if mode == "Detail bars":
    order = np.argsort(w)
    fig = go.Figure(go.Bar(
        x=[w[i] for i in order], y=[tickers[i] for i in order],
        orientation="h",
        marker=dict(color=[colors[i] for i in order]),
        text=[f"{w[i]:.1%}" for i in order], textposition="outside",
        hovertemplate="%{y}: %{x:.2%}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Portfolio Weights Detail — {w_label} ({pool_key})",
        xaxis_title="Weight", xaxis=dict(range=[0, max(1.0, w.max() * 1.15)]),
        height=max(320, 60 * len(tickers)), margin=dict(l=10, r=10, t=50, b=10),
    )
    # Legend by class
    seen = {}
    for t, c in zip(tickers, colors):
        seen.setdefault(c, asset_class.get(t, "?"))
    for c, label in seen.items():
        fig.add_trace(go.Bar(x=[None], y=[None], marker=dict(color=c), name=label,
                             showlegend=True, hoverinfo="skip"))
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="right", x=1, font=dict(size=11)))
else:
    # By-class summary
    df = pd.DataFrame({"Asset": tickers, "Class": [asset_class.get(t, "-") for t in tickers], "Weight": w})
    cat = df.groupby("Class")["Weight"].sum().sort_values()
    cat_colors = [CLASS_COLORS.get(c, "#999999") for c in cat.index]
    fig = go.Figure(go.Bar(
        x=cat.values, y=cat.index, orientation="h",
        marker=dict(color=cat_colors),
        text=[f"{v:.1%}" for v in cat.values], textposition="outside",
        hovertemplate="%{y}: %{x:.2%}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Weights by Asset Class — {w_label} ({pool_key})",
        xaxis_title="Weight", xaxis=dict(range=[0, max(1.0, cat.max() * 1.15)]),
        height=max(280, 60 * len(cat)), margin=dict(l=10, r=10, t=50, b=10),
    )

st.plotly_chart(fig, width="stretch")

# ---- Weight table ----
st.subheader("Weight Detail Table")
w_df = pd.DataFrame({
    "Asset": tickers,
    "Class": [asset_class.get(t, "-") for t in tickers],
    "Weight": w,
})
w_df["Weight%"] = (w_df["Weight"] * 100).round(2)
st.dataframe(w_df[["Asset", "Class", "Weight%"]], hide_index=True, width="stretch")

# Class summary table
cat_df = pd.DataFrame({
    "Class": cat.index if mode == "By-class summary" else
             w_df.groupby("Class")["Weight"].sum().sort_values(ascending=False).index,
    "Weight%": (cat.values * 100).round(2) if mode == "By-class summary" else
               (w_df.groupby("Class")["Weight"].sum().sort_values(ascending=False).values * 100).round(2),
})
st.caption("By asset class")
st.dataframe(cat_df, hide_index=True, width="stretch")

if gamma is not None:
    st.caption(f"Custom portfolio solved in real time with γ={gamma:g} from Page 2 (session_state link); "
               f"adjust γ on Page 2 and return here to see the update.")
