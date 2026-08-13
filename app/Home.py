#!/usr/bin/env python3
"""Portfolio Optimization Demo — Interactive Web App Entry (P5b)

Run:
    cd project-demo && streamlit run app/Home.py

Pages (sidebar navigation, 7 pages):
    1_Overview          Key metric cards (portfolios vs SPY vs 60/40 benchmarks)
    2_Efficient_Frontier  Interactive frontier (γ slider / pool switch / short-selling)
    3_Weights           Portfolio weight bars (colored by asset class)
    4_Nav_Drawdown      NAV curve + drawdown curve (date range picker)
    5_Correlation       Plotly heatmap (hover values + negative-correlation marks)
    6_Extensions        Risk Parity / BL / Monte Carlo vs Mean-Variance
    7_Agent_Workflow    5-agent collaboration DAG + message flow (roles → artifacts)

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
st.caption("Portfolio Optimization Course Demo | Data: ~5Y daily closes (yfinance, auto_adjust) | Pipeline artifacts (read-only)")

st.markdown(
    """
This web app assembles the **P2 data pipeline → P3 portfolio optimization → P3x extensions → P5 visualization** artifacts into an interactive demo:

- **Overview**: key metric cards (GMV / Tangency vs SPY / 60-40 benchmarks)
- **Efficient Frontier**: drag risk-aversion γ to move the optimal portfolio along the frontier
- **Weights**: GMV / Tangency / custom-γ portfolio weights by asset class
- **NAV & Drawdown**: portfolio vs benchmarks NAV curve and drawdown depth
- **Correlation**: hoverable heatmap with negative-correlation highlights (EEM-DBC)
- **Extensions**: Risk Parity / Black-Litterman / Monte Carlo vs Mean-Variance
- **Agent Workflow**: the 5-agent cluster DAG, per-role inputs → outputs → scripts, and the M1–M6 message flow

> Pick a page from the sidebar to start exploring.
"""
)

# ---------------------------------------------------------------------------
# Asset pools (what the "Asset Pool" selectbox options mean)
# ---------------------------------------------------------------------------
st.subheader("📦 Asset Pools")
st.markdown(
    """
Every page has an **Asset Pool** selector with two options:

- **Portfolio A (Cross-Asset ETFs)** — `SPY` / `IWM` / `TLT` / `GLD` / `EEM` / `DBC`
  US equities, long-duration bonds, gold, emerging markets, and commodities.
  Its low/negative correlations (e.g. EEM-DBC = -0.12) teach **asset-class diversification**.

- **Baseline (6 Stocks)** — `AAPL` / `MSFT` / `GOOGL` / `AMZN` / `JPM` / `XOM`
  Six mega-cap stocks, used as a control to show that **asset-class diversification
  reduces risk further than stock-level diversification** (see the two-frontier comparison).
"""
)

# ---------------------------------------------------------------------------
# 5-Agent Collaboration (cluster orchestration overview)
# ---------------------------------------------------------------------------
st.subheader("🤝 5-Agent Collaboration")
st.markdown(
    """
The whole pipeline runs as a **5-agent cluster** on jiuwenswarm team mode: a `leader`
breaks the work into 5 tasks and verifies results (writes no code), while five teammates
claim tasks on the shared board, hand off via `send_message`, and share artifacts through
a common workspace.

**Hand-off chain (DAG)** — each agent only forwards the *artifact path + one-line summary*:

`data-collector → feature-engineer → optimizer-engine → viz-agent → reporter`
*(reporter also depends on optimizer-engine)*
"""
)

role_cards = [
    ("🧭", "leader", "breaks down tasks & verifies — writes no code", "task board + blocked_by"),
    ("📥", "data-collector", "fetch → clean → cache", "data/params.json, returns_*.csv"),
    ("🧮", "feature-engineer", "derived features (corr / class / 60-40)", "data/features.json"),
    ("⚙️", "optimizer-engine", "GMV / tangency / efficient frontier", "output/portfolios.csv, frontier.csv"),
    ("📊", "viz-agent", "5 charts + dashboard", "output/*.png"),
    ("📝", "reporter", "metrics + conclusions", "output/report.md"),
]
cols = st.columns(6)
for col, (icon, role, duty, artifact) in zip(cols, role_cards):
    with col:
        st.markdown(
            f"<div style='border:1px solid #e0e0e0;border-radius:8px;padding:10px 8px;"
            f"min-height:150px;text-align:center'>"
            f"<div style='font-size:22px'>{icon}</div>"
            f"<div style='font-weight:700;margin:4px 0'>{role}</div>"
            f"<div style='font-size:12px;color:#555'>{duty}</div>"
            f"<div style='font-size:11px;color:#888;margin-top:6px'><code>{artifact}</code></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown(
    "👉 Open **Agent Workflow** in the sidebar for the full DAG, per-role *inputs → outputs → scripts*, "
    "and the M1–M6 message flow."
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
    "Project root: `{}` | Run: `streamlit run app/Home.py`".format(ROOT),
    icon="💡",
)
