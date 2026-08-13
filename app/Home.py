#!/usr/bin/env python3
"""Portfolio Optimization Demo — Interactive Web App Entry (P5b)

Run:
    cd project-demo && streamlit run app/Home.py

Pages (sidebar navigation, 6 pages):
    1_Overview          Key metric cards (portfolios vs SPY vs 60/40 benchmarks)
    2_Efficient_Frontier  Interactive frontier (γ slider / pool switch / short-selling)
    3_Weights           Portfolio weight bars (colored by asset class)
    4_Nav_Drawdown      NAV curve + drawdown curve (date range picker)
    5_Correlation       Plotly heatmap (hover values + negative-correlation marks)
    6_Extensions        Risk Parity / BL / Monte Carlo vs Mean-Variance

Data: read-only consumption of data/ and output/ artifacts; fully offline-capable.
"""

import streamlit as st

from utils import ROOT, load_features

st.set_page_config(
    page_title="Portfolio Optimization Demo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Markowitz Portfolio Optimization — Interactive Demo")
st.caption("Portfolio Optimization Course Demo ｜ Data: ~5Y daily closes (yfinance, auto_adjust) ｜ Pipeline artifacts (read-only)")

st.markdown(
    """
This web app assembles the **P2 data pipeline → P3 portfolio optimization → P3x extensions → P5 visualization** artifacts into an interactive demo:

- **Overview**: key metric cards (GMV / Tangency vs SPY / 60-40 benchmarks)
- **Efficient Frontier**: drag risk-aversion γ to move the optimal portfolio along the frontier
- **Weights**: GMV / Tangency / custom-γ portfolio weights by asset class
- **NAV & Drawdown**: portfolio vs benchmarks NAV curve and drawdown depth
- **Correlation**: hoverable heatmap with negative-correlation highlights (GLD-DBC)
- **Extensions**: Risk Parity / Black-Litterman / Monte Carlo vs Mean-Variance

> Pick a page from the sidebar to start exploring.
"""
)

feats = load_features()
st.divider()
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Data Version**")
    if feats:
        src = feats.get("source", {})
        st.markdown(
            f"- Params: `{src.get('params', 'data/params.json')}`\n"
            f"- Returns: `{src.get('returns', 'data/returns_assetclass.csv')}`\n"
            f"- Features: `data/features.json` (correlation / class summary / 60-40 benchmark)"
        )
    else:
        st.markdown("- Params: `data/params.json`\n- Features: `data/features.json` (not generated; pages degrade gracefully)")
with c2:
    st.markdown("**Engineering Notes**")
    st.markdown(
        "- Consumes `output/portfolios.csv` / `frontier.csv` / `extensions_summary.csv` / `mc_points.csv`\n"
        "- Only the frontier page solves γ in real time (lightweight SLSQP); all other pages read artifacts\n"
        "- The 5 static PNGs remain in `output/` for reports / PPT"
    )

st.info(
    "Project root: `{}` ｜ Run: `streamlit run app/Home.py`".format(ROOT),
    icon="💡",
)
