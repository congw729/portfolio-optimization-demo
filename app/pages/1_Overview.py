#!/usr/bin/env python3
"""P5b Page 1 Overview: key metric cards (portfolios vs SPY vs 60/40)

Data: output/portfolios.csv (GMV/Tangency), data/params.json (SPY single-asset metrics),
      data/features.json (benchmark_6040), output/report.md (conclusion summary).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from utils import (  # noqa: E402
    POOLS,
    benchmark_6040_returns,
    compute_drawdown,
    get_combo_row,
    load_features,
    load_pool,
    load_report_lines,
)

st.set_page_config(page_title="Overview", layout="wide")
st.title("1️⃣ Overview — Key Metrics: Portfolios vs Benchmarks")

pool_key = st.selectbox("Asset Pool", list(POOLS.keys()), key="ov_pool")
d = load_pool(pool_key)
feats = load_features()
rf = d["rf"]
tickers = d["tickers"]
params = d["params"]


def single_asset_metrics(t: str) -> dict:
    """Single-asset metrics: ret/vol from params (annualized), max_dd from daily returns."""
    if t not in tickers or t not in params.get("mu", {}):
        return {"ret": float("nan"), "vol": float("nan"),
                "sharpe": float("nan"), "max_dd": float("nan")}
    i = tickers.index(t)
    ret = float(params["mu"][t])
    vol = float(np.sqrt(params["sigma"][t][i]))
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")
    max_dd = float(compute_drawdown(d["returns"][t]).min())
    return {"ret": ret, "vol": vol, "sharpe": sharpe, "max_dd": max_dd}


def combo_metrics(combo: str) -> dict | None:
    row = get_combo_row(d["portfolios"], combo)
    if row is None:
        return None
    return {"ret": float(row["ret"]), "vol": float(row["vol"]),
            "sharpe": float(row["sharpe"]), "max_dd": float(row["max_dd"])}


def b6040_metrics() -> dict:
    """60/40 benchmark: ret/vol/sharpe from features.json, max_dd constructed on the fly."""
    if feats and "benchmark_6040" in feats:
        b = feats["benchmark_6040"]
        m = {"ret": float(b["ret"]), "vol": float(b["vol"]),
             "sharpe": float(b["sharpe"]), "max_dd": float("nan")}
    else:
        m = {"ret": float("nan"), "vol": float("nan"),
             "sharpe": float("nan"), "max_dd": float("nan")}
    r_6040 = benchmark_6040_returns(d["returns"], params)
    if r_6040 is not None and len(r_6040) > 0:
        m["max_dd"] = float(compute_drawdown(r_6040).min())
    return m


gmv = combo_metrics("GMV_数值(禁做空)")
tan = combo_metrics("切线_数值(禁做空)")
spy = single_asset_metrics("SPY") if "SPY" in tickers else {
    "ret": float("nan"), "vol": float("nan"),
    "sharpe": float("nan"), "max_dd": float("nan")}
b6040 = b6040_metrics()

cards = [
    ("GMV (Min Variance)", gmv, "#4C72B0"),
    ("Tangency (Max Sharpe)", tan, "#C44E52"),
    ("Benchmark SPY", spy, "#333333"),
    ("60/40 Benchmark (SPY+TLT)", b6040, "#DD8452"),
]

cols = st.columns(4)
for col, (title, m, color) in zip(cols, cards):
    with col:
        st.markdown(
            f"<div style='border-left:4px solid {color};padding-left:10px;"
            f"margin-bottom:6px'><b>{title}</b></div>",
            unsafe_allow_html=True,
        )
        st.metric("Annual Return", f"{m['ret']:.2%}" if np.isfinite(m['ret']) else "—")
        st.metric("Annual Volatility", f"{m['vol']:.2%}" if np.isfinite(m['vol']) else "—")
        st.metric("Sharpe Ratio", f"{m['sharpe']:.3f}" if np.isfinite(m['sharpe']) else "—")
        st.metric("Max Drawdown", f"{m['max_dd']:.2%}" if np.isfinite(m['max_dd']) else "—")

st.divider()

# Conclusion summary (citing key lines of report.md)
lines = load_report_lines()
if lines:
    st.subheader("📝 Conclusion Summary (output/report.md)")
    for ln in lines:
        if any(k in ln for k in ("结论", "夏普", "回撤", "60/40", "分散化", "负相关")):
            st.markdown(f"- {ln}")

st.caption(f"Convention: numeric optimization, no shorting (primary) | rf = {rf:.2%} | data window see report.md")
