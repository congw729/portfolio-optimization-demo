#!/usr/bin/env python3
"""P5b Page 5 Correlation heatmap: plotly hover values + negative-correlation marks

Data: data/features.json → corr (Portfolio A pre-computed); baseline derives corr from
      params_stocks.json sigma on the fly (lightweight); when features.json is missing,
      corr is computed from returns on the fly.
Teaching point: Portfolio A contains a negative correlation (GLD-DBC = -0.12),
                SPY-TLT measured +0.68 (stocks and bonds moved together over the last 5Y).
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
    load_features,
    load_pool,
)

st.set_page_config(page_title="Correlation", layout="wide")
st.title("5️⃣ Correlation Heatmap — The Source of Diversification")

pool_key = st.selectbox("Asset Pool", list(POOLS.keys()), key="cr_pool")
d = load_pool(pool_key)
tickers = d["tickers"]
params = d["params"]
feats = load_features()

# ---- Correlation source: features.json → sigma derivation → returns on the fly ----
corr_df = None
if feats and "corr" in feats:
    corr_dict = feats["corr"]
    if all(t in corr_dict for t in tickers):
        corr_df = pd.DataFrame(
            [[corr_dict[a][b] for b in tickers] for a in tickers],
            index=tickers, columns=tickers,
        )

if corr_df is None:
    # Derive corr from sigma: ρ_ij = Σ_ij / sqrt(Σ_ii·Σ_jj)
    s = np.array([[params["sigma"][a][b] for b in tickers] for a in tickers])
    dg = np.sqrt(np.diag(s))
    corr = s / np.outer(dg, dg)
    corr_df = pd.DataFrame(corr, index=tickers, columns=tickers)

# Negative-correlation pairs (GLD-DBC known -0.12; generic detection)
neg_pairs = []
n = len(tickers)
for i in range(n):
    for j in range(i + 1, n):
        if corr_df.iloc[i, j] < -0.05:
            neg_pairs.append((tickers[i], tickers[j], corr_df.iloc[i, j]))

# Strong-positive pairs (teaching annotation)
pos_pairs = []
for a, b in (("SPY", "EEM"), ("SPY", "TLT")):
    if a in tickers and b in tickers:
        pos_pairs.append((a, b, corr_df.loc[a, b]))

# ---- Heatmap ----
fig = go.Figure(go.Heatmap(
    z=corr_df.values,
    x=tickers, y=tickers,
    zmin=-1, zmax=1,
    colorscale="RdBu_r",
    text=corr_df.values.round(3),
    texttemplate="%{text}",
    hovertemplate="%{y} × %{x}<br>ρ = %{z:.3f}<extra></extra>",
    colorbar=dict(title="Correlation ρ", thickness=14),
))

# Negative pairs (red box)
for a, b, v in neg_pairs:
    i, j = tickers.index(a), tickers.index(b)
    fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=i - 0.5, y1=i + 0.5,
                  line=dict(color="#C44E52", width=3))
    fig.add_annotation(x=j, y=i, text=f"{v:.2f}↓", showarrow=False,
                       font=dict(color="white", size=11, weight="bold"))

# Strong-positive pairs (blue box)
for a, b, v in pos_pairs:
    i, j = tickers.index(a), tickers.index(b)
    fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=i - 0.5, y1=i + 0.5,
                  line=dict(color="#4C72B0", width=2.5, dash="dot"))
    fig.add_annotation(x=j, y=i, text=f"{v:.2f}", showarrow=False,
                       font=dict(color="white", size=10))

fig.update_layout(
    title=f"Asset Return Correlation Matrix — {pool_key}",
    height=620,
    margin=dict(l=20, r=20, t=60, b=20),
    xaxis=dict(side="bottom"),
)
st.plotly_chart(fig, width="stretch")

# ---- Teaching annotations ----
st.markdown("### 🔍 Teaching Highlights")
neg_txt = "、".join(f"**{a}-{b} = {v:.2f}**" for a, b, v in neg_pairs) or "none"
pos_txt = "、".join(f"**{a}-{b} = {v:.2f}**" for a, b, v in pos_pairs) or "none"
st.markdown(
    f"- **Negative pairs (red box)**: {neg_txt} — negative correlation = extra diversification (hedging across assets)\n"
    f"- **Strong-positive pairs (blue box)**: {pos_txt} — stocks and bonds moved together over the last 5Y; positive correlation weakens diversification"
)
if pool_key == "Portfolio A (Cross-Asset ETFs)":
    st.caption("Convention: measured correlation matrix from data/features.json (P4b feature-engineer artifact). "
               "GLD-DBC negative + SPY-TLT +0.68 are the v1.2 measured values; the single most informative chart.")
else:
    st.caption("Convention: derived on the fly from data/params_stocks.json covariance (ρ_ij = Σ_ij/√(Σ_ii·Σ_jj)).")
