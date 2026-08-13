#!/usr/bin/env python3
"""app/utils.py — shared utilities for the interactive web app (P5b)

Extracted & extended from the single-page output/dashboard.py:
  - load_pool(): read params/frontier/returns/portfolios/mc artifacts (@st.cache_data)
  - solve_utility(): real-time γ solve of max wᵀμ − 0.5γ·wᵀΣw (reused from dashboard.py)
  - compute_nav / compute_drawdown(): NAV & drawdown convention (aligned with S-1)
  - portfolio_metrics_from_returns(): ret/vol/sharpe/max_dd from daily return series
  - load_features(): read data/features.json (returns None when missing → graceful degrade)

Interfaces are decoupled from P2/P3/P3x artifacts; read-only consumption, fully offline.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

# Compatible with any cwd: ROOT = project-demo/
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"

POOLS = {
    "Portfolio A (Cross-Asset ETFs)": {
        "params": DATA / "params.json",
        "frontier": OUT / "frontier.csv",
        "returns": DATA / "returns_assetclass.csv",
        "portfolios": OUT / "portfolios.csv",
        "mc": OUT / "mc_points.csv",
    },
    "Baseline (6 Stocks)": {
        "params": DATA / "params_stocks.json",
        "frontier": OUT / "frontier_stocks.csv",
        "returns": DATA / "returns_stocks.csv",
        "portfolios": OUT / "portfolios_stocks.csv",
    },
}

# Asset class → color (consistent with scripts/viz.py)
CLASS_COLORS = {
    "equity-us": "#4C72B0",
    "bond": "#DD8452",
    "gold": "#C44E52",
    "equity-em": "#55A868",
    "commodity": "#8172B2",
}


# ---------------------------------------------------------------------------
# Data loading (cached: no re-parse while files unchanged)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def load_pool(pool_key: str) -> dict:
    """Read all artifacts of one pool → dict (tickers/mu/sigma/rf/params/frontier/returns/portfolios/mc)."""
    p = POOLS[pool_key]
    with open(p["params"], encoding="utf-8") as f:
        params = json.load(f)
    tickers: list[str] = params["tickers"]
    mu = np.array([params["mu"][t] for t in tickers])
    sigma = np.array([params["sigma"][t] for t in tickers])
    rf = params.get("rf", 0.0)
    frontier = pd.read_csv(p["frontier"]) if p["frontier"].exists() else pd.DataFrame()
    returns = pd.read_csv(p["returns"], index_col=0, parse_dates=True)
    returns = returns[tickers]
    portfolios = pd.read_csv(p["portfolios"]) if p["portfolios"].exists() else pd.DataFrame()
    mc = pd.read_csv(p["mc"]) if p["mc"].exists() else pd.DataFrame()
    return {
        "tickers": tickers, "mu": mu, "sigma": sigma, "rf": rf,
        "params": params, "frontier": frontier,
        "returns": returns, "portfolios": portfolios, "mc": mc,
    }


@st.cache_data(show_spinner=False)
def load_features() -> dict | None:
    """Read data/features.json; return None when missing (pages degrade)."""
    path = DATA / "features.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_report_lines() -> list[str]:
    """Read key conclusion lines of output/report.md (cited by Overview page)."""
    path = OUT / "report.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith(">")]


# ---------------------------------------------------------------------------
# Portfolio math (real-time γ solve, lightweight)
# ---------------------------------------------------------------------------


def solve_utility(mu: np.ndarray, sigma: np.ndarray, gamma: float,
                  no_short: bool) -> np.ndarray:
    """Solve utility-maximizing portfolio: max wᵀμ − 0.5γ·wᵀΣw, sum(w)=1, optional no-short."""
    from scipy.optimize import minimize

    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    bounds = [(0.0, 1.0)] * n if no_short else None
    res = minimize(
        lambda w: -(w @ mu - 0.5 * gamma * (w @ sigma @ w)),
        x0=np.ones(n) / n, method="SLSQP",
        constraints=cons, bounds=bounds,
        options={"ftol": 1e-12, "maxiter": 500},
    )
    if not res.success:
        raise RuntimeError(f"Utility maximization failed: {res.message}")
    return res.x


# ---------------------------------------------------------------------------
# NAV / Drawdown (S-1 convention)
# ---------------------------------------------------------------------------


def compute_nav(r: pd.Series) -> pd.Series:
    """Cumulative NAV: nav = (1+r).cumprod()."""
    return (1.0 + r).cumprod()


def compute_drawdown(r: pd.Series) -> pd.Series:
    """Drawdown: dd = nav/nav.cummax() − 1."""
    nav = compute_nav(r)
    return nav / nav.cummax() - 1.0


def portfolio_metrics_from_returns(
    w: np.ndarray, mu: np.ndarray, sigma: np.ndarray, rf: float,
    returns_df: pd.DataFrame,
) -> dict:
    """Portfolio metrics: ret/vol/sharpe/max_dd (max_dd from daily return series)."""
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ sigma @ w))
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")
    r_port = returns_df @ w
    max_dd = float(compute_drawdown(r_port).min())
    return {"ret": ret, "vol": vol, "sharpe": sharpe, "max_dd": max_dd}


def get_combo_row(portfolios: pd.DataFrame, combo: str) -> pd.Series | None:
    """Return the row of portfolios.csv matching combo; None when missing."""
    if portfolios.empty:
        return None
    rows = portfolios[portfolios["combo"] == combo]
    return rows.iloc[0] if len(rows) else None


def combo_weights(portfolios: pd.DataFrame, combo: str) -> np.ndarray | None:
    """Extract weight vector from w_* columns of portfolios.csv."""
    row = get_combo_row(portfolios, combo)
    if row is None:
        return None
    w_cols = [c for c in portfolios.columns if c.startswith("w_")]
    return row[w_cols].to_numpy(dtype=float)


def asset_class_colors(params: dict, tickers: list[str]) -> list[str]:
    """Color by asset class (consistent with viz.py)."""
    ac = params.get("asset_class", {})
    return [CLASS_COLORS.get(ac.get(t, "equity-us"), "#999999") for t in tickers]


def benchmark_6040_returns(returns_df: pd.DataFrame, params: dict) -> pd.Series | None:
    """Construct 60/40 benchmark daily returns: 60% SPY + 40% TLT (features.json weights preferred)."""
    feats = load_features()
    w6040 = None
    if feats and "benchmark_6040" in feats and "weights" in feats["benchmark_6040"]:
        w6040 = feats["benchmark_6040"]["weights"]
    if w6040 is None:
        w6040 = {"SPY": 0.6, "TLT": 0.4}
    cols = [t for t in w6040 if t in returns_df.columns]
    if len(cols) != len(w6040):
        return None
    total = sum(w6040[c] for c in cols)
    w = np.array([w6040[c] / total for c in cols])
    return returns_df[cols] @ w
