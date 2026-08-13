#!/usr/bin/env python3
"""P5b Page 7 Agent Workflow: 5-agent collaboration DAG + message flow (cluster orchestration).

Source of truth: docs/p4-orchestration-design.md (roles / DAG / message flow).
Read-only page: it only *checks the existence* of data/ and output/ artifacts
(no recomputation), consistent with the rest of the app.
"""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from utils import DATA, OUT  # noqa: E402

st.set_page_config(page_title="Agent Workflow", layout="wide")
st.title("7️⃣ Agent Workflow — 5-Agent Collaboration DAG")

st.caption(
    "Cluster orchestration on jiuwenswarm team mode | Source of truth: "
    "`docs/p4-orchestration-design.md` | Read-only consumption of `data/` & `output/` artifacts"
)

# ---------------------------------------------------------------------------
# Static orchestration model (strictly from docs/p4-orchestration-design.md)
# ---------------------------------------------------------------------------

ROLES = [
    {
        "name": "data-collector",
        "icon": "📥",
        "task": "T1",
        "duty": "Fetch 6 cross-asset ETFs (SPY/IWM/TLT/GLD/EEM/DBC, ~5Y daily) + baseline "
                "6 mega-cap stocks (AAPL/MSFT/GOOGL/AMZN/JPM/XOM); clean & align "
                "(ffill + dropna), compute returns & annualized params, cache to disk. "
                "Cache-first: `--refresh` re-fetches from network.",
        "inputs": "none (network or existing cache); ticker list given by task",
        "outputs": "`data/params.json` (formal: mu/Sigma/rf/benchmark/asset_class), "
                   "`data/returns_assetclass.csv`, `data/closes_assetclass.csv`; "
                   "baseline `data/params_stocks.json`, `data/returns_stocks.csv`, `data/closes_stocks.csv`",
        "script": "`python scripts/fetch_data.py --name assetclass --tickers SPY,IWM,TLT,GLD,EEM,DBC "
                  "--years 5 --rf --benchmark SPY --params-out data/params.json` "
                  "| baseline: `--name stocks --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5`",
        "check": "data-quality report all green: closes_NaN=0, returns_NaN=0, trading days ≥ 750, 0<rf<0.15",
    },
    {
        "name": "feature-engineer",
        "icon": "🧮",
        "task": "T2",
        "duty": "Validate `params.json` completeness (mu/Sigma/rf/benchmark/asset_class), then add "
                "derived features: correlation matrix, per-asset-class return/vol summary, and the "
                "60/40 benchmark portfolio parameters.",
        "inputs": "`data/params.json`, `data/returns_assetclass.csv`",
        "outputs": "`data/features.json` (corr, asset_class_summary, benchmark_6040)",
        "script": "`python scripts/features.py` (derived-feature computation; consumes fetch_data artifacts)",
        "check": "correlation matrix contains ≥1 negative pair; asset_class labels complete",
    },
    {
        "name": "optimizer-engine",
        "icon": "⚙️",
        "task": "T3",
        "duty": "Run Markowitz optimization for Portfolio A and the stock baseline: GMV "
                "(numeric no-short primary + analytic contrast), tangency (max Sharpe), and a "
                "60-point efficient-frontier scan (5% margin / warm start / try-except).",
        "inputs": "`data/params.json`, `data/params_stocks.json`, `data/returns_assetclass.csv`, "
                  "`data/returns_stocks.csv`, `data/features.json` (pre-check correlation & 60/40 params)",
        "outputs": "`output/portfolios.csv` (Portfolio A primary), `output/portfolios_stocks.csv`, "
                   "`output/frontier.csv`, `output/frontier_stocks.csv`",
        "script": "`python scripts/optimizer.py --params data/params.json --returns data/returns_assetclass.csv "
                  "--tag assetclass` | same with `--tag stocks`",
        "check": "weights sum to 1 (±1e-6); GMV vol ≤ any single asset; frontier convexity check; "
                 "correlation negative check before optimizing",
    },
    {
        "name": "viz-agent",
        "icon": "📊",
        "task": "T4",
        "duty": "Consume optimization artifacts and render 5 required charts + optional dashboard: "
                "① efficient frontier scatter (MC cloud + CML + GMV/tangency marks) ② weight bars "
                "colored by asset class ③ drawdown curve (portfolio vs SPY) ④ correlation heatmap "
                "(negative correlation visible) ⑤ two-frontier comparison (baseline stocks vs Portfolio A).",
        "inputs": "`output/frontier.csv`, `output/frontier_stocks.csv`, `output/portfolios.csv`, "
                  "`data/params.json`, `data/returns_*.csv`",
        "outputs": "`output/*.png` (5 charts: frontier, weights, drawdown, correlation heatmap, "
                   "frontier compare), optional `output/dashboard.py`",
        "script": "`python scripts/viz.py`",
        "check": "all 5 charts generated without font issues; heatmap shows negative correlation",
    },
    {
        "name": "reporter",
        "icon": "📝",
        "task": "T5",
        "duty": "Aggregate all artifacts into the final conclusion report: portfolio Sharpe vs "
                "benchmark SPY Sharpe, max drawdown, optimal weights, per-asset-class weight summary, "
                "60/40 benchmark Sharpe comparison, and risk-attribution conclusion.",
        "inputs": "`output/portfolios.csv`, `output/frontier*.csv`, `data/params.json`, "
                  "`data/features.json`, `output/*.png`",
        "outputs": "`output/report.md` (final demo report)",
        "script": "`python scripts/report.py` (reads CSV/JSON, aggregates into Markdown)",
        "check": "conclusion covers all A6 acceptance items (Sharpe / max drawdown / class weights / 60-40)",
    },
]

LEADER = {
    "name": "leader",
    "icon": "🧭",
    "task": "—",
    "duty": "Breaks the pipeline into 5 tasks (T1–T5) on the shared board, wires `blocked_by` "
            "dependencies, assigns/verifies results — **writes no code**.",
    "inputs": "pipeline design (docs/p4-orchestration-design.md)",
    "outputs": "5 tasks on the board + acceptance verdicts",
    "script": "none (orchestration only)",
    "check": "DAG chain unlocks in order; final report.md accepted",
}

DEPENDENCIES = [
    ("T1 data-collector", "none", "runs first (network or cache)"),
    ("T2 feature-engineer", "T1", "needs params.json / returns ready"),
    ("T3 optimizer-engine", "T2 (strict)", "consumes features.json (correlation pre-check + 60/40 params)"),
    ("T4 viz-agent", "T3", "needs frontier / portfolios ready"),
    ("T5 reporter", "T3 + T4", "needs optimization results + charts ready"),
]

MESSAGES = [
    ("M1", "data-collector → feature-engineer",
     "`data/params.json` ready (SPY/IWM/TLT/GLD/EEM/DBC, 1254 trading days, rf=3.71%, incl. asset_class) — please compute features"),
    ("M2", "feature-engineer → optimizer-engine",
     "`data/features.json` ready (corr / class summary / 60-40 benchmark), params = `data/params.json` — please optimize"),
    ("M3", "optimizer-engine → viz-agent",
     "`output/frontier.csv` + `portfolios.csv` ready (Portfolio A 59-point frontier, tangency Sharpe 0.999) — please chart"),
    ("M4", "optimizer-engine → reporter",
     "`output/portfolios.csv` ready (GMV/tangency metrics), `frontier_stocks.csv` is baseline — finalize after T4"),
    ("M5", "viz-agent → reporter",
     "`output/*.png` 5 charts generated (incl. two-frontier comparison) — report may cite charts, start final aggregation"),
    ("M6", "reporter → team-leader",
     "`output/report.md` ready (Sharpe / max drawdown / class weights / 60-40 conclusion) — demo deliverable"),
]

ARTIFACT_CHECKS = [
    ("data-collector", [DATA / "params.json", DATA / "returns_assetclass.csv", DATA / "params_stocks.json"]),
    ("feature-engineer", [DATA / "features.json"]),
    ("optimizer-engine", [OUT / "portfolios.csv", OUT / "frontier.csv", OUT / "frontier_stocks.csv"]),
    ("viz-agent", [OUT / "frontier_scatter.png", OUT / "weights_bar.png", OUT / "drawdown_curve.png",
                   OUT / "correlation_heatmap.png", OUT / "frontier_compare.png"]),
    ("reporter", [OUT / "report.md"]),
]


# ---------------------------------------------------------------------------
# DAG figure (plotly: nodes + arrows, no extra dependency)
# ---------------------------------------------------------------------------
def build_dag_figure() -> go.Figure:
    nodes = {
        "leader": (1.5, 3.0),
        "data-collector": (0.0, 2.0),
        "feature-engineer": (1.0, 2.0),
        "optimizer-engine": (2.0, 2.0),
        "viz-agent": (1.0, 1.0),
        "reporter": (3.0, 1.0),
    }
    colors = {
        "leader": "#555555",
        "data-collector": "#4C72B0",
        "feature-engineer": "#55A868",
        "optimizer-engine": "#C44E52",
        "viz-agent": "#DD8452",
        "reporter": "#8172B2",
    }
    duties = {
        "leader": "breakdown & verify (no code)",
        "data-collector": "fetch → clean → cache",
        "feature-engineer": "derived features",
        "optimizer-engine": "GMV / tangency / frontier",
        "viz-agent": "5 charts + dashboard",
        "reporter": "metrics + conclusions",
    }

    fig = go.Figure()

    # Arrows: (start, end, color) — gray = leader orchestration, dark = hand-off, red = extra dep
    edges = [
        ("leader", "data-collector", "#AAAAAA"),
        ("data-collector", "feature-engineer", "#555555"),
        ("feature-engineer", "optimizer-engine", "#555555"),
        ("optimizer-engine", "viz-agent", "#555555"),
        ("viz-agent", "reporter", "#555555"),
        ("optimizer-engine", "reporter", "#C44E52"),
        ("reporter", "leader", "#AAAAAA"),
    ]
    for s, e, c in edges:
        sx, sy = nodes[s]
        ex, ey = nodes[e]
        fig.add_annotation(
            x=ex, y=ey, ax=sx, ay=sy,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.1,
            arrowwidth=1.8, arrowcolor=c, text="",
        )

    order = list(nodes.keys())
    positions = ["top center"] + ["bottom center"] * (len(order) - 1)
    fig.add_trace(go.Scatter(
        x=[nodes[n][0] for n in order],
        y=[nodes[n][1] for n in order],
        mode="markers+text",
        marker=dict(size=32, color=[colors[n] for n in order],
                    line=dict(color="white", width=2)),
        text=order,
        textposition=positions,
        textfont=dict(size=13, color="#222222"),
        hovertemplate=[f"<b>{n}</b><br>{duties[n]}<extra></extra>" for n in order],
        showlegend=False,
    ))

    fig.update_layout(
        height=480,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False, range=[-1.1, 4.1]),
        yaxis=dict(visible=False, range=[0.4, 3.6]),
    )
    return fig


st.subheader("🕸️ Orchestration DAG")
st.plotly_chart(build_dag_figure(), width="stretch")
st.caption(
    "**Dark arrows** = artifact hand-off along the `blocked_by` chain "
    "(data-collector → feature-engineer → optimizer-engine → viz-agent → reporter). "
    "**Red arrow** = reporter *additionally* depends on optimizer-engine (T3 → T5). "
    "**Gray arrows** = leader breaks down tasks (→ data-collector) and reporter reports back (→ leader, M6)."
)

# ---------------------------------------------------------------------------
# Roles (inputs → outputs → script)
# ---------------------------------------------------------------------------
st.subheader("👥 Roles — Input → Output → Script")

st.markdown(
    f"**{LEADER['icon']} leader** — {LEADER['duty']}"
)
with st.expander("🧭 leader (orchestrator, writes no code)"):
    st.markdown(
        f"- **Input**: {LEADER['inputs']}\n"
        f"- **Output**: {LEADER['outputs']}\n"
        f"- **Script**: {LEADER['script']}\n"
        f"- **Acceptance**: {LEADER['check']}"
    )

for r in ROLES:
    with st.expander(f"{r['icon']} {r['task']} {r['name']}"):
        st.markdown(f"**Duty**: {r['duty']}")
        st.markdown(f"- **Input**: {r['inputs']}")
        st.markdown(f"- **Output**: {r['outputs']}")
        st.markdown(f"- **Script**: {r['script']}")
        st.markdown(f"- **Acceptance**: {r['check']}")

# ---------------------------------------------------------------------------
# Dependency table
# ---------------------------------------------------------------------------
st.subheader("🔗 Dependency Chain (`blocked_by`)")
dep_md = "| Task | blocked_by | Note |\n|---|---|---|\n"
for task, blocked, note in DEPENDENCIES:
    dep_md += f"| {task} | {blocked} | {note} |\n"
st.markdown(dep_md)

# ---------------------------------------------------------------------------
# Message flow
# ---------------------------------------------------------------------------
st.subheader("✉️ Message Flow (path + one-line summary, no data payloads)")
msg_md = "| Step | Sender → Receiver | Message (illustrative) |\n|---|---|---|\n"
for step, route, content in MESSAGES:
    msg_md += f"| {step} | {route} | {content} |\n"
st.markdown(msg_md)
st.caption(
    "Convention: agents forward only the **artifact path + one-line summary** (hard limit ≤2000 chars); "
    "receivers read the actual files. Message contents above are illustrative, from "
    "`docs/p4-orchestration-design.md` §3."
)

# ---------------------------------------------------------------------------
# Current artifact status (read-only existence check)
# ---------------------------------------------------------------------------
st.subheader("📦 Current Artifact Status (read-only)")
st.caption("Checks only whether each agent's key artifact exists on disk — no recomputation.")

rows = []
for agent, paths in ARTIFACT_CHECKS:
    ready = sum(1 for p in paths if p.exists())
    total = len(paths)
    status = "✅ ready" if ready == total else f"⚠️ {ready}/{total} present"
    rows.append((agent, status, ", ".join(p.name for p in paths)))
st.markdown(
    "| Agent | Status | Key artifacts |\n|---|---|---|\n"
    + "".join(f"| {a} | {s} | `{p}` |\n" for a, s, p in rows)
)

st.info(
    "The **Agent Workflow** page is static orchestration metadata; the other pages consume the "
    "artifacts themselves (frontier / weights / correlation / report) read-only.",
    icon="💡",
)
