#!/usr/bin/env python3
"""P5b Page 4 NAV & Drawdown: portfolios vs SPY vs 60/40

Controls: date range picker (default data window), portfolio selectbox (GMV/Tangency/SPY/60-40),
          display mode toggle (NAV / Drawdown / Both).
Data: data/returns_assetclass.csv (daily returns; portfolio daily returns = returns @ w),
      data/returns_stocks.csv (baseline), data/params.json (SPY column),
      data/features.json (benchmark_6040 weights).
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
    benchmark_6040_returns,
    combo_weights,
    compute_drawdown,
    compute_nav,
    load_pool,
)

st.set_page_config(page_title="NAV & Drawdown", layout="wide")
st.title("4️⃣ NAV & Drawdown — Portfolios vs SPY vs 60/40")

pool_key = st.selectbox("Asset Pool", list(POOLS.keys()), key="nd_pool")
d = load_pool(pool_key)
tickers = d["tickers"]
params = d["params"]
returns = d["returns"]

# ---- Portfolio daily return series ----
series = {}
gmv_w = combo_weights(d["portfolios"], "GMV_数值(禁做空)")
tan_w = combo_weights(d["portfolios"], "切线_数值(禁做空)")
if gmv_w is not None:
    series["GMV (Min Variance)"] = returns @ gmv_w
if tan_w is not None:
    series["Tangency (Max Sharpe)"] = returns @ tan_w
if "SPY" in returns.columns:
    series["Benchmark SPY"] = returns["SPY"]
r_6040 = benchmark_6040_returns(returns, params)
if r_6040 is not None:
    series["60/40 Benchmark"] = r_6040

# ---- Controls: date range + portfolio + mode ----
c_ctl = st.columns([2, 2, 2])
with c_ctl[0]:
    main_key = st.selectbox("Primary Series", list(series.keys()), key="nd_main")
with c_ctl[1]:
    mode = st.radio("Display Mode", ["Both (NAV + Drawdown)", "NAV", "Drawdown"], horizontal=True,
                    key="nd_mode")
with c_ctl[2]:
    start_default = returns.index.min().date()
    end_default = returns.index.max().date()
    date_range = st.date_input("Date Range", value=(start_default, end_default),
                               min_value=start_default, max_value=end_default,
                               key="nd_range")

if isinstance(date_range, tuple) and len(date_range) == 2:
    d0, d1 = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    d0, d1 = returns.index.min(), returns.index.max()

# ---- Build NAV / DD ----
def to_nav_dd(name: str) -> tuple[pd.Series, pd.Series]:
    r = series[name]
    r = r[(r.index >= d0) & (r.index <= d1)]
    return compute_nav(r), compute_drawdown(r)


names = [main_key] + [k for k in series if k != main_key]
colors = {"GMV (Min Variance)": "#4C72B0", "Tangency (Max Sharpe)": "#C44E52",
          "Benchmark SPY": "#333333", "60/40 Benchmark": "#DD8452"}

navs = {k: to_nav_dd(k)[0] for k in names}
dds = {k: to_nav_dd(k)[1] for k in names}

fig = go.Figure()

if mode in ("Both (NAV + Drawdown)", "NAV"):
    for k in names:
        fig.add_trace(go.Scatter(
            x=navs[k].index, y=navs[k].values, mode="lines", name=k,
            line=dict(color=colors.get(k, "#888888"), width=2 if k == main_key else 1.5),
            hovertemplate="%{x|%Y-%m-%d}<br>nav=%{y:.3f}<extra></extra>",
        ))
    fig.update_layout(title="Cumulative NAV nav = (1+r).cumprod()",
                      yaxis_title="Cumulative NAV", xaxis_title="Date")

if mode == "Both (NAV + Drawdown)":
    fig.update_layout(height=420)
    st.plotly_chart(fig, width="stretch")

    # Drawdown subplot
    fig2 = go.Figure()
    for k in names:
        dd = dds[k]
        fig2.add_trace(go.Scatter(
            x=dd.index, y=dd.values, mode="lines", name=k,
            fill="tozeroy" if k == main_key else None,
            line=dict(color=colors.get(k, "#888888"), width=1.8 if k == main_key else 1.2),
            hovertemplate="%{x|%Y-%m-%d}<br>dd=%{y:.2%}<extra></extra>",
        ))
        # Mark max drawdown point
        i_min = int(dd.values.argmin())
        fig2.add_annotation(
            x=dd.index[i_min], y=dd.values[i_min],
            text=f"{k} max_dd={dd.values[i_min]:.1%}",
            showarrow=True, arrowhead=2, ax=40, ay=-30, font=dict(size=10),
        )
    fig2.update_layout(title="Drawdown dd = nav/nav.cummax() − 1",
                       yaxis_title="Drawdown", xaxis_title="Date",
                       height=420, yaxis=dict(tickformat=".0%"))
    st.plotly_chart(fig2, width="stretch")
elif mode == "NAV":
    fig.update_layout(height=480)
    st.plotly_chart(fig, width="stretch")
else:  # Drawdown
    fig2 = go.Figure()
    for k in names:
        dd = dds[k]
        fig2.add_trace(go.Scatter(
            x=dd.index, y=dd.values, mode="lines", name=k,
            fill="tozeroy" if k == main_key else None,
            line=dict(color=colors.get(k, "#888888"), width=1.8 if k == main_key else 1.2),
            hovertemplate="%{x|%Y-%m-%d}<br>dd=%{y:.2%}<extra></extra>",
        ))
        i_min = int(dd.values.argmin())
        fig2.add_annotation(
            x=dd.index[i_min], y=dd.values[i_min],
            text=f"{k} max_dd={dd.values[i_min]:.1%}",
            showarrow=True, arrowhead=2, ax=40, ay=-30, font=dict(size=10),
        )
    fig2.update_layout(title="Drawdown dd = nav/nav.cummax() − 1",
                       yaxis_title="Drawdown", xaxis_title="Date",
                       height=480, yaxis=dict(tickformat=".0%"))
    st.plotly_chart(fig2, width="stretch")

# ---- Metrics summary ----
st.subheader("Metric Comparison (selected range)")
rows = []
for k in names:
    r = series[k]
    r = r[(r.index >= d0) & (r.index <= d1)]
    nav, dd = compute_nav(r), compute_drawdown(r)
    rows.append({
        "Series": k,
        "Cumulative Return": f"{(nav.iloc[-1] - 1):.2%}",
        "Max Drawdown": f"{dd.min():.2%}",
        "Annualized Return": f"{r.mean() * 252:.2%}",
        "Annualized Vol": f"{r.std() * np.sqrt(252):.2%}",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

st.caption("Teaching point: compare drawdown depth & recovery of Tangency vs SPY; smoothness of the 60/40 benchmark.")
