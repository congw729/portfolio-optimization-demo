# Portfolio Optimization Course Project Demo — Project Preparation Checklist

> Objective: Build a course Project Demo for **Portfolio Optimization (Markowitz mean-variance framework)** using the **jiuwenswarm cluster mode (team mode)**.
> This document is a **complete, executable** preparation checklist covering six dimensions: Environment & Tools, Data Preparation, Algorithm/Model Preparation, Cluster-Mode Demo Design, Demo Assets, and Acceptance & Milestones.
> Every preparation item follows the "What it is + Why it is needed + How to obtain/configure" structure; **uncertain environment dependencies are marked as "⚠️ to verify"**.
>
> Document version: **v1.2** (2026-08-13) ｜ Author: portfolio-planner
> **This is the English version of the Chinese v1.2 document** (`portfolio-optimization-demo-prep.md`); structure, data, code blocks, commands, and tables are kept identical.
> **v1.2 changes**: Back-filled measured correlation data for Scheme A (measured in P2b/P3) — **GLD-DBC measured at -0.12 (negative correlation, replacing the original estimate of 0.3–0.4)**; **SPY-TLT measured at +0.68 (positive correlation; stocks and bonds moved in the same direction over the past 5 years, correcting the earlier "negative correlation between stocks and bonds" assumption)**; §5.1 chart ④ description, GLD/DBC note, and §6 acceptance/milestone wording updated accordingly; version bumped from v1.1 to v1.2. See the change log at the end of this document.

---

## 0. Demo Overview (Read This First)

| Item | Description |
|---|---|
| Demo topic | A complete portfolio-optimization pipeline — "data collection → feature engineering → portfolio optimization → visualization → reporting" — executed collaboratively by a multi-agent cluster |
| Core algorithm | Markowitz mean-variance optimization: efficient frontier, global minimum variance (GMV) portfolio, maximum Sharpe (tangency) portfolio |
| Optional extensions | Risk parity, Black-Litterman, Monte Carlo simulation (bonus items) |
| Demo market | US stocks / US-listed ETFs (yfinance free, risk-free rate readily available); A-shares as an alternative (akshare) |
| Recommended asset pool | **Scheme A (recommended, confirmed)**: SPY / IWM / TLT / GLD / EEM / DBC — a cross-asset-class portfolio (US large-cap + small-cap + long-term bonds + gold + emerging markets + broad commodities); the covariance structure contains positive correlation (equity–equity), negative correlation (**EEM-DBC measured at -0.12**) and near-zero correlation (DBC vs. most others), directly mapping to the course's "asset allocation" theme |
| Benchmark portfolio (kept) | The baseline of 6 individual stocks (AAPL/MSFT/GOOGL/AMZN/JPM/XOM) is retained for comparison, demonstrating the difference between "asset-class diversification vs. single-stock diversification" via dual efficient frontiers |
| Demo format | Cluster mode runs the full pipeline + produces charts (efficient frontier, weight bar chart, drawdown curve, correlation heatmap) + optional Streamlit interactive page |
| Estimated timeline | 5 phases, about **2 weeks (8–12 working days)** (see §6.2) |

---

## 1. Environment & Tools

### 1.1 Python Version

- **What it is**: The entire data pipeline and optimization algorithms are implemented in Python, so the interpreter version must be pinned.
- **Why it is needed**: Recent numpy/pandas/scipy/matplotlib releases have Python-version requirements; Python 3.9 is too old (this machine measured 3.9.6, see below), while the 3.12+ ecosystem is most stable.
- **How to obtain/configure**:
  - Recommended **Python 3.10–3.12** (3.12 is currently mainstream; all dependencies ship prebuilt wheels).
  - Manage multiple versions via `pyenv` / `uv` / `conda`: `uv python install 3.12` or `conda create -n po-demo python=3.12`.
  - ⚠️ to verify: On this machine `/usr/bin/python3` is **Python 3.9.6**, and the system interpreter plus pip may be restricted by PEP 668 (externally-managed-environment). **Do not install packages with the system python3 directly**; a virtual environment is mandatory.
  - **Hands-on guide**: Full installation steps are in the companion document `local-env-setup-uv.md` (a uv-based macOS environment setup guide with per-step verification commands and expected outputs).

### 1.2 Core Python Dependencies (numpy / pandas / scipy / matplotlib / scikit-learn)

- **What it is**: The "big four" for numerical computation, tabular data handling, optimization solving, and plotting, plus a statistical shrinkage-estimation library.
- **Why it is needed**:
  - numpy: vector/matrix operations (covariance matrix, weight vectors);
  - pandas: historical price DataFrames, trading-day alignment, return calculation;
  - scipy.optimize: constrained optimization for the efficient frontier and maximum Sharpe portfolio (SLSQP);
  - matplotlib: efficient frontier scatter plot, weight bar chart, drawdown curve;
  - **scikit-learn**: fallback via **Ledoit-Wolf shrinkage estimation** (`sklearn.covariance.LedoitWolf`) when the covariance matrix is not positive definite; required by review item I-3.
- **How to obtain/configure** (one-shot install in the virtual environment):

  ```bash
  uv pip install --python 3.12 \
    numpy pandas scipy matplotlib seaborn \
    yfinance akshare streamlit jupyter scikit-learn
  ```

  - Also install `seaborn` (nicer charts) and `jupyter` (development/debugging).
  - Pin versions immediately after install: `uv pip freeze > requirements.txt` (see `local-env-setup-uv.md` §3.2).
  - ⚠️ to verify (measured on this machine, system python3.9 environment): numpy 2.0.2 / pandas 2.3.3 / scipy 1.13.1 / matplotlib 3.9.4 are present; **yfinance and scikit-learn are not installed and must be added**. Re-validate the full version set in a dedicated demo virtual environment.

### 1.3 Data Acquisition Libraries: yfinance / akshare

- **What they are**:
  - `yfinance`: free access to Yahoo Finance quotes (US stocks/ETFs/indices/Treasury yields, no API key required).
  - `akshare`: free access to A-share/HK/China bond data (A-share alternative).
- **Why they are needed**: The "data collection agent" of the demo must obtain historical prices from a real source; both libraries are free, pure Python, and require no registration — suitable for a course demo.
- **How to obtain/configure**: `pip install yfinance akshare` (combined with the item above).
  - ⚠️ to verify: yfinance depends on network access to Yahoo Finance; **the domestic network environment may be unstable/blocked**. Test a real download before the demo; cache the data to local CSV in advance (see §2.4) so the demo can run offline.

### 1.4 jiuwenswarm Cluster Mode (Team Mode): Installation & Startup Configuration

- **What it is**: jiuwenswarm's **cluster mode = team mode**: one leader agent + multiple teammate agents collaborating via a task board + message channel (send_message), sharing the `.team/` workspace.
- **Why it is needed**: This is the **core showcase carrier** of the demo — splitting the portfolio-optimization pipeline into multiple agent roles (see §4) to demonstrate multi-agent orchestration.
- **How to obtain/configure**:
  - Install: `pip install jiuwenswarm` (skip if already present).
  - Team configuration lives under `modes.team.<team_name>` in `~/.jiuwenswarm/config/config.yaml`. The current project team (measured config):
    ```yaml
    modes:
      team:
        jiuwen_team:
          team_name: jiuwen_team
          lifecycle: persistent          # team lifecycle
          teammate_mode: build_mode      # teammate autonomous execution mode
          spawn_mode: inprocess          # spawn agents in-process
          enable_swarmflow: false
          worktree: { enabled: true }    # member worktree isolation (for coding)
          transport: { type: inprocess }
          storage: { type: sqlite }
          leader: { member_name: team-leader, display_name: Team Leader, persona: "..." }
          agents: { leader: $agent_leader }
          workspace: { enabled: true }
    ```
  - **Registration/creation mechanism for the 5 teammate roles (review item I-1)**, choose either:
    - **Option 1: static registration in the config.yaml `agents` section** — declare each role under `modes.team.<team_name>.agents` (reuse the `$agent_teammate` template and override member_name / persona):
      ```yaml
      agents:
        leader: $agent_leader
        data-collector:    # data collection agent
          <<: *agent_teammate    # inherit the agent_teammate template (YAML anchor syntax; adjust to actual config schema)
          member_name: data-collector
          display_name: Data Collector
          persona: "Fetch and clean market data"
        feature-engineer:  { member_name: feature-engineer, persona: "..." }
        optimizer-engine:  { member_name: optimizer-engine, persona: "..." }
        viz-agent:         { member_name: viz-agent, persona: "..." }
        reporter:          { member_name: reporter, persona: "..." }
      ```
      ⚠️ to verify: The teammate declaration syntax and template inheritance under the `agents` section must follow the actual schema of the installed `jiuwenswarm` version (the example is illustrative and not yet measured).
    - **Option 2: created at runtime by the leader (recommended; the current team uses this mechanism)** — the leader creates tasks on the task board and assigns member_name; teammates claim tasks autonomously in `build_mode`; a "role" is simply "task claimer + responsibility", requiring no pre-registration in config.yaml.
    - Recommendation: **prefer Option 2** (this is exactly the measured inprocess + build_mode flow of the current team, minimal change); use Option 1 with measured verification only if multiple pre-provisioned teammates must be statically registered.
  - Startup: after starting jiuwenswarm in cluster/team mode, the leader creates tasks (task board) and teammates claim them; members communicate via `send_message`; artifacts are written to the shared `.team/` directory.
  - ⚠️ to verify: If the demo needs a **separate demo team independent of this course team**, add a new team section in config.yaml and restart; confirm spawn_mode/transport = inprocess so a single-machine demo works (no multi-machine Docker needed).

### 1.5 Virtual Environment / Docker

- **What they are**:
  - Virtual environment: an isolated Python dependency set (venv / conda / uv).
  - Docker: containerized environment (image-level isolation, consistent across machines).
- **Why they are needed**: avoid polluting the system Python (PEP 668), keep the demo environment reproducible, and prevent version conflicts; Docker is only needed for multi-machine/cloud demos or environment migration.
- **How to obtain/configure**:
  - **Preferred: virtual environment (lightweight, sufficient)**: `uv venv --python 3.12 .venv && source .venv/bin/activate`.
  - Docker (optional): `python:3.12-slim` base image + `requirements.txt` (`pip freeze > requirements.txt` to pin versions). The demo is a single-machine inprocess cluster, so **Docker is not needed by default**.

### 1.6 Other Tools

| Tool | What it is | Why it is needed | How to obtain |
|---|---|---|---|
| Git | Version control | Track demo code evolution, easy rollback and review | `brew install git` / bundled |
| uv | Python package/environment manager (fast) | Create environments + install dependencies with one command, ~10× faster than pip | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (⚠️ to verify network); **fallback if the install fails** (review S-5): `python3 -m pip install --user uv`, or bootstrap via a temp venv `python3 -m venv /tmp/uv-bootstrap-venv && /tmp/uv-bootstrap-venv/bin/pip install uv`, or fall back to conda/venv (§1.5) — see `local-env-setup-uv.md` §1.2 |
| Streamlit (optional) | Web UI framework | Change parameters live during the demo (asset pool / risk-aversion coefficient) and watch the portfolio update | `pip install streamlit` |
| VS Code / Jupyter | Development & debugging | Write code, inspect data | Per personal preference |

---

## 2. Data Preparation

### 2.1 Asset Pool & Historical Price Data Acquisition

- **What it is**: Select **6 US-listed ETFs (Scheme A)** and fetch 3–5 years of daily close prices; keep the 6-stock baseline for comparison.
- **Why it is needed**: Mean-variance optimization requires "expected return per asset + covariance between assets", all derived from historical prices; Scheme A's cross-asset composition (equity/bond/commodity/international) yields a covariance structure with positive correlation (equity–equity), negative correlation (EEM-DBC measured at -0.12), and near-zero correlation (DBC vs. most others) — maximum teaching information.
- **How to obtain/configure**:

  ```python
  import yfinance as yf
  import pandas as pd

  # Scheme A (primary pool): cross-asset-class ETFs
  tickers_a = ["SPY", "IWM", "TLT", "GLD", "EEM", "DBC"]
  # Baseline (comparison pool): 6 individual stocks
  tickers_base = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "XOM"]

  # Dynamic end date (review S-6): use the most recent trading day before the demo, avoid hard-coded stale dates
  end = pd.Timestamp.today().strftime("%Y-%m-%d")
  start = (pd.Timestamp.today() - pd.DateOffset(years=5)).strftime("%Y-%m-%d")

  data = yf.download(tickers_a, start=start, end=end,
                     group_by="ticker", auto_adjust=True, threads=True)
  closes = data.loc[:, (slice(None), "Close")]   # multi-column → one column per ticker
  closes.columns = tickers_a
  ```

  - `auto_adjust=True`: use adjusted close prices (splits/dividends adjusted — ETF distributions included) to avoid price jumps.
  - Asset-class labels (for downstream aggregation by class): SPY/IWM=US equity, TLT=US long-term bonds, GLD=precious metals, EEM=emerging-market equity, DBC=broad commodities.
  - ⚠️ to verify (Scheme A specific): EEM (emerging markets) has a trading calendar different from the US (emerging-market holidays may fall on US trading days); after `dropna(how="any")` the window may shrink — measure the usable window (target ≥ 3 years, ~750 trading days).
  - ⚠️ to verify (return direction): **EEM / TLT / DBC may have near-zero or negative returns over the past 5 years** (emerging markets underperforming, rising rates, commodity roll/contango costs). Measure return directions during development and prepare the talking point: "the goal of portfolio optimization is risk-adjusted return, not positive return for every single asset".
  - ⚠️ to verify: network connectivity must be tested on first fetch; if it fails, fall back to local cache (see §2.4) or switch data sources.
  - The 6-stock baseline is fetched the same way (`tickers_base`) and is used only for the dual-frontier comparison, not in the main optimization flow.

### 2.2 Data Cleaning & Alignment (Trading Days, Missing Values, Returns)

- **What it is**:
  - **Alignment**: different assets have different listing dates/suspensions/holidays → date indices differ; they must be unified onto common trading days.
  - **Missing values**: individual trading days with no data (suspension, source gaps, cross-market holidays).
  - **Returns**: daily returns computed from price series, used for mean and covariance estimation.
- **Why it is needed**: The covariance matrix is meaningful only when all assets share the same time axis; missing values fed directly into computations can make the covariance matrix non-positive-definite (causing later optimization failures); returns are the direct input to optimization.
- **How to obtain/configure**:

  ```python
  # 1) Alignment: take trading days common to all assets (intersection), or forward-fill first then intersect
  #    Scheme A includes cross-market ETFs (EEM); measure the window length after ffill
  closes = closes.ffill().dropna(how="any")

  # 2) Returns: simple returns (recommended for the course demo, intuitive)
  returns = closes.pct_change().dropna()
  # Alternative: log returns  log_returns = np.log(closes / closes.shift(1)).dropna()
  #       (log returns have nicer mathematical properties when aggregating across periods,
  #        but the numerical difference is negligible for this demo)

  # 3) Annualized parameters
  ann_return = returns.mean() * 252
  ann_cov    = returns.cov() * 252
  ```

- **Common pitfalls**: ① different listing dates leave a very short window after `dropna` → use mature instruments listed before 2021 (all six Scheme A ETFs qualify); ② cross-market holidays (EEM) cause tail missingness → handle with `ffill()` first; ③ the baseline stocks also have suspensions/splits (handled by auto_adjust).
- ⚠️ to verify: the impact of `dropna(how="any")` vs. `ffill` on the final efficient-frontier shape; run both once during development, fix on one for the demo, and document it.

### 2.3 Risk-Free Rate & Market Benchmark

- **What they are**:
  - **Risk-free rate rf**: in optimization, "excess return = asset return − rf"; the maximum Sharpe portfolio depends on it.
  - **Market benchmark**: used to draw the CML (capital market line) and for comparison (e.g., the S&P 500 index); also used for beta or as the Black-Litterman prior (optional extension).
- **Why they are needed**: without rf the Sharpe ratio and tangency portfolio cannot be defined; without a benchmark the course's core conclusion "the portfolio beats/underperforms the market" cannot be shown.
- **How to obtain/configure** (US-market demo):
  - Risk-free rate: use the **3-month Treasury yield** (Yahoo ticker `^IRX`) or 13-week T-bills:
    ```python
    rf_series = yf.download("^IRX", start=start, end=end)["Close"].iloc[-1] / 100.0
    rf_annual = rf_series   # ^IRX returns a percentage value; divide by 100
    ```
    - For simplicity a constant rf ≈ 0.04–0.05 (recent two-year Treasury levels) may be used; document the basis.
  - Market benchmark: **SPY is recommended** (same instrument type as the pool assets — more intuitive and fair comparison); the S&P 500 index `^GSPC` is also acceptable:
    ```python
    spx = yf.download("SPY", start=start, end=end, auto_adjust=True)["Close"]
    spx_ret = spx.pct_change().dropna()
    ```
  - A-share alternative: risk-free rate from the 10-year government bond yield (akshare `ak.bond_zh_us_rate()`); benchmark = CSI 300 (code `000300.SH`).
  - ⚠️ to verify: the `^IRX` unit (percent vs. decimal) must be made explicit in the demo script with an assertion (`assert 0 < rf < 0.15`).

### 2.4 Data Caching (Key to Demo Robustness)

- **What it is**: persist fetched quotes to local CSV/Parquet.
- **Why it is needed**: ① the live demo does not depend on the network; ② multiple agents share one data copy (no duplicate fetches or inconsistent results); ③ reproducibility; ④ Scheme A and the baseline can coexist for comparison.
- **How to obtain/configure**:

  ```python
  # File names carry the pool identifier (review item A), so multiple pools can coexist for comparison
  closes.to_csv("data/closes_assetclass.csv")      # Scheme A: SPY/IWM/TLT/GLD/EEM/DBC
  returns.to_csv("data/returns_assetclass.csv")
  closes_base.to_csv("data/closes_stocks.csv")     # Baseline: 6 individual stocks
  returns_base.to_csv("data/returns_stocks.csv")
  ```

  - Convention: the data agent reads the cache first (`data/`), and only fetches from the network with `--refresh`.

---

## 3. Algorithm / Model Preparation

### 3.1 Markowitz Mean-Variance Optimization (Core, Mandatory)

- **What it is**: minimize portfolio variance for a given target return (or maximize return for a given risk), yielding the efficient frontier; two special solutions on the frontier are the **global minimum variance (GMV) portfolio** and the **maximum Sharpe (tangency) portfolio**.
- **Why it is needed**: This is the **main algorithm** of the course demo; all visualizations (efficient frontier, weight bar charts) revolve around it.
- **How to obtain/configure** (mathematical tools + dependencies):

  - **Inputs**: annualized expected return vector `mu` (`returns.mean()*252`), annualized covariance matrix `Sigma` (`returns.cov()*252`), risk-free rate `rf`.
  - **Mathematical form** (N assets):
    - Minimize `wᵀ Σ w` subject to `Σwᵢ = 1` (weights sum to 1), optionally `wᵢ ≥ 0` (no shorting) or allow shorting.
    - Maximum Sharpe: maximize `(wᵀμ − rf) / √(wᵀΣw)`, also subject to weights summing to 1.
  - **⚠️ Important: constraint-set difference between the analytical and numerical solutions (review I-2)**:
    - **The analytical solution (formulas below) implicitly assumes "shorting allowed, unbounded weights"** — derived without the `wᵢ ≥ 0` constraint, so the GMV/tangency weights may be negative;
    - **No-shorting (`wᵢ ≥ 0`) requires numerical optimization (scipy SLSQP)**, whose result **differs** from the analytical one (e.g., the analytical GMV may contain negative weights);
    - **The demo must use one consistent convention**: ① recommended: use **numerical optimization (no-shorting)** as the primary demo convention (closer to real investment constraints); or ② treat "unconstrained vs. no-shorting" as a **comparison highlight** (teaching point: showing how allowing shorting expands the frontier and raises the Sharpe ratio). Note in acceptance A2 that weight validation follows the chosen convention. **Do not show both results side by side without explaining the difference**, or students may think the results contradict.
  - **Implementation**:
    1. **Analytical solution (only for the "shorting allowed" case, as reference/teaching)**:
       - GMV: `w_gmv = Σ⁻¹·1 / (1ᵀ·Σ⁻¹·1)` (mind numerical stability; use `np.linalg.solve` rather than inversion);
       - Tangency: `w_tan = Σ⁻¹·(μ − rf·1) / (1ᵀ·Σ⁻¹·(μ − rf·1))`.
    2. **Numerical optimization (recommended primary convention: no-shorting, scipy)**:
       ```python
       from scipy.optimize import minimize
       def port_var(w): return w @ Sigma @ w
       cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]   # weights sum to 1
       bounds = [(0, 1)] * N                                   # no-shorting (primary demo convention)
       res = minimize(port_var, x0=np.ones(N)/N, method="SLSQP",
                      constraints=cons, bounds=bounds)
       ```
       - Efficient-frontier scan (review S-4: handle the feasible-region boundary): scan target returns over `[min(mu), max(mu)]` with a **5% margin at each end**; wrap each `minimize` in **try/except to skip infeasible points**, and use **warm start** (previous solution as initial guess) for a continuous curve:
         ```python
         lo, hi = mu.min() * 1.05, mu.max() * 0.95   # 5% margin at each end
         targets = np.linspace(lo, hi, 60)
         frontier = []
         w_prev = np.ones(N) / N
         for t in targets:
             try:
                 res = minimize(port_var, x0=w_prev, method="SLSQP",
                                constraints=cons + [{"type": "eq", "fun": lambda w, t=t: w @ mu - t}],
                                bounds=bounds)
                 if res.success:
                     frontier.append((np.sqrt(res.x @ Sigma @ res.x), res.x @ mu, res.x))
                     w_prev = res.x                      # warm start
             except Exception:
                 continue                                 # skip infeasible points
         ```
  - **Dependencies**: numpy (linear algebra) + scipy.optimize (SLSQP); scikit-learn for shrinkage fallback (§1.2 installed).

### 3.2 Efficient Frontier / GMV / Tangency / Drawdown (Computation & Presentation Points)

- **What it is**: four standard outputs — ① the efficient frontier curve (set of optimal portfolios in the return-risk plane); ② GMV weights; ③ maximum Sharpe portfolio weights and its Sharpe ratio; ④ portfolio drawdown series and maximum drawdown.
- **Why it is needed**: the course's core points "diversification reduces risk" and "no portfolio dominates the frontier" need to be shown visually; drawdown is an intuitive measure of the risk-control dimension.
- **How to obtain/configure**:
  - Plotting: matplotlib scatter plot, x-axis = annualized volatility `np.sqrt(wᵀΣw)`, y-axis = annualized return `wᵀμ`.
  - Overlays: ① Monte Carlo random portfolios (gray cloud, showing "random portfolios all lie to the right of the frontier"); ② the CML line (from `(0, rf)` through the tangency portfolio); ③ single-asset points labeled.
  - **Drawdown definition (review S-1)**, same convention for portfolio and benchmark:
    ```python
    nav   = (1 + r).cumprod()            # cumulative net asset value
    dd    = nav / nav.cummax() - 1       # drawdown series (≤ 0)
    max_dd = dd.min()                    # maximum drawdown (most negative)
    ```
  - Output metrics table: per portfolio `return / volatility / Sharpe / max drawdown / weight vector`, saved to CSV for the reporting agent.

### 3.3 Optional Extensions (Decide by Time Budget; at Least One Recommended)

| Extension | What it is | Math / dependencies | Demo value |
|---|---|---|---|
| **Risk Parity** | Each asset contributes equally to portfolio risk | Iterative solve: `RCᵢ = wᵢ(Σw)ᵢ/√(wᵀΣw)`, equalize all RCᵢ; numpy suffices | Contrast with mean-variance ("no return forecasting needed"); Scheme A's bonds/gold naturally have low risk contributions — intuitive |
| **Black-Litterman** | Bayesian posterior optimization combining "market-equilibrium prior + subjective views" | Inverse optimization for equilibrium returns `π = δ·Σ·w_mkt`; posterior μ formula; numpy suffices | Shows "how views change the portfolio", a course highlight; ETF priors are more sensible than single stocks |
| **Monte Carlo simulation** | Generate many random weight portfolios and observe the return-risk distribution | `np.random.dirichlet(alpha)` for weights; numpy suffices | Great visualization (gray cloud), simplest to implement |

- **Dependencies**: all numpy/pandas; no new libraries. ⚠️ to verify: risk-parity iteration convergence (cap at 1000 iterations + tolerance 1e-6).

---

## 4. Cluster-Mode Demo Design (jiuwenswarm Team Mode)

### 4.1 Why the Cluster Mode Fits This Demo

1. **The pipeline is naturally phased**: data → features → optimization → visualization → reporting; each step has a clear responsibility, making it a natural fit for splitting into agents.
2. **It demonstrates real collaboration**: task board + message channel (send_message) + shared `.team/` workspace — showing "multi-agent division of labor and message flow" is far more convincing from an engineering standpoint than a single-agent script.
3. **Parallelism**: data collection can be parallelized by asset group; feature computation and visualization partially overlap — showing the cluster's concurrency advantage.
4. **Course fit**: a Project Demo typically showcases "solving a real problem with a multi-agent framework", and portfolio optimization is the most intuitive numerical case.

### 4.2 Agent Role Breakdown (Recommended: 5 Roles)

| Agent role | Suggested member name | Responsibility | Outputs | Depends on |
|---|---|---|---|---|
| **Data collection agent** | data-collector | Fetch Scheme A quotes (yfinance), clean & align (incl. EEM cross-market calendar), write CSV cache; cache-first | `data/closes_assetclass.csv`, `data/returns_assetclass.csv` (+ baseline `closes_stocks.csv`) | None (runs first) |
| **Feature engineering agent** | feature-engineer | Compute annualized returns/covariance/risk-free rate/benchmark return; output params JSON (incl. asset-class labels) | `data/params.json` (incl. mu/Sigma/rf/benchmark/asset_class) | Data agent |
| **Optimization engine agent** | optimizer-engine | Run GMV / maximum Sharpe / efficient frontier (primary convention: no-shorting numerical optimization) / (optional extensions); output portfolios & metrics | `output/portfolios.csv`, `output/frontier.csv` | Feature agent |
| **Visualization agent** | viz-agent | Plot efficient frontier, weight bar chart (colored by class), drawdown curve, correlation heatmap, dual-frontier comparison | `output/*.png`, `output/dashboard.py` (optional Streamlit) | Optimization agent |
| **Reporting agent** | reporter | Aggregate metrics & charts into conclusions (beat/underperform benchmark, Sharpe comparison, risk attribution); **new: aggregate weights by asset class** (e.g., "bonds 25%, gold 15%…") and 60/40 benchmark Sharpe comparison | `output/report.md` | Optimization/visualization agent |

> Can be simplified to 3 roles (data, optimization, reporting) — but **5 roles are recommended** to fully showcase cluster collaboration; the leader is responsible for task decomposition, sequencing, and acceptance.
> Role registration/creation mechanism: see §1.4 (Option 2 — runtime creation by the leader — is the recommended path, ⚠️ to verify).

### 4.3 Message Flow & Collaboration

```
team-leader (task decomposition, acceptance)
   │ creates tasks on the task board (data → feature → optimizer → viz → report)
   ▼
data-collector ──send_message(data ready, path)──► feature-engineer
feature-engineer ──send_message(params.json ready)──► optimizer-engine
optimizer-engine ──send_message(results ready)──► viz-agent ──► reporter
                                                      └──► (optional) dashboard
```

- **Task dependencies**: use the task board's `blocked_by` to express sequential dependencies (optimization task blocked_by feature task); the leader only decomposes tasks, never writes code.
- **Shared files**: all intermediate artifacts are written under `data/` and `output/` in `.team/jiuwen_team_sess_19ffa2c098f_773d5c07c3b4/` (lock before writing, unlock after).
- **Message content**: send only "file path + one-line summary" (e.g., `data/params.json ready, contains mu/Sigma/rf`), never paste long data.

### 4.4 Demo Script (Suggested Live Flow)

1. Show the team board: 5 tasks + dependency graph.
2. The leader issues the "start" instruction; agents claim tasks one by one.
3. Show each agent's tool calls and output files in sequence (emphasizing send_message handoffs).
4. Aggregate the charts and the reporting agent's conclusions (incl. weights aggregated by asset class).
5. (Optional) Streamlit interaction: change the risk-aversion coefficient / asset pool and watch the portfolio update live.

---

## 5. Demo Assets

### 5.1 Required Visualizations (5 Charts)

| Chart | Content | Tool | Notes |
|---|---|---|---|
| ① Efficient frontier scatter | Frontier curve + Monte Carlo gray cloud + CML + GMV/tangency annotations | matplotlib | Demo centerpiece; must be the most polished |
| ② Weight bar chart | Weight allocations of the max-Sharpe / GMV / a target-return portfolio, **colored by asset class** (equity/bond/commodity/international) | matplotlib/barh | Shows diversification and class allocation |
| ③ Drawdown curve | Cumulative NAV and max drawdown of the portfolio vs. benchmark (**SPY**) | matplotlib/area | Shows risk control; benchmark and portfolio share the same instrument type (ETF) for a fairer comparison |
| ④ Correlation heatmap | Asset return correlation matrix — **promoted to the centerpiece chart**: Scheme A contains a negative correlation pair (**EEM-DBC measured at -0.12, emerging-market equities-commodities**) and a strong positive one (SPY-TLT measured at +0.68; stocks and bonds moved together over the past 5 years) — the single most information-dense chart | seaborn/heatmap | Explains the covariance input; the negative correlation (EEM-DBC) is the key differentiator of Scheme A vs. the stock pool |
| ⑤ Dual-frontier comparison | **Baseline 6 stocks vs. Scheme A** overlaid on two efficient frontiers | matplotlib | Shows the "asset-class vs. single-stock diversification" difference; teaching enhancement |

- **Chinese font**: ⚠️ to verify — on macOS use `plt.rcParams["font.sans-serif"] = ["PingFang SC"]` (or Arial Unicode MS) to avoid tofu boxes.
- In Scheme A, GLD (precious metals) and DBC (broad commodities: energy/industrial metals/agriculture) are both inflation hedges, **measured correlation -0.12 (negative, measured in P2b)**; they hedge different inflation sources — use this as a teaching point: negatively correlated commodity-gold adds extra diversification, so students should not think they are redundant.

### 5.2 Optional Interactive UI (Streamlit / Dash)

- **What it is**: a web app whose parameters can be adjusted live.
- **Why it is needed**: a demo plus-item showing "the model computed by the cluster can be interacted with by users in real time".
- **How to obtain/configure**:
  - **Streamlit** is recommended (simpler): `streamlit run output/dashboard.py`, widgets: `st.sidebar.selectbox` (asset pool: Scheme A / baseline), `st.slider` (risk-aversion coefficient), `st.checkbox` (no-shorting).
  - Reuse cluster outputs: the dashboard reads `data/params.json` and `output/frontier.csv` directly and **does not recompute**, embodying "data/model as a service".

### 5.3 Demo Script / PPT Outline (With Buffer)

```
1. Opening (2 min): problem statement — how to allocate capital for optimal return-risk? How do multiple agents collaborate?
2. Team board (2 min): show the 5 roles and dependencies; explain the cluster-mode design.
3. Data stage (3 min): data-collector pulls 5 years of quotes for 6 ETFs; show cleaning/alignment (incl. EEM cross-market calendar).
4. Optimization stage (5 min): feature engineering → optimization engine produces GMV / tangency portfolio / efficient frontier.
5. Visualization & conclusions (5 min): 5 charts + reporting agent conclusions (portfolio Sharpe vs. benchmark, class weights, 60/40 comparison).
6. Interaction (2 min, optional): Streamlit parameter demo; **skip if over time** (buffer strategy).
7. Summary (2 min): value of cluster mode + extension outlook (risk parity / Black-Litterman).
```
> **Buffer strategy (review S-3)**: the core segments total ~21 minutes; the interaction segment is marked "skip if over time", reserving 3–4 minutes of buffer for live delays so the total stays ≤ 25 min.

---

## 6. Acceptance & Milestones

### 6.1 Demo Acceptance Criteria

| # | Acceptance item | Pass criteria |
|---|---|---|
| A1 | Pipeline runs end-to-end | One command drives data-to-report fully automatically with no manual intervention |
| A2 | Correct results | Weights sum to 1 (±1e-6); GMV volatility ≤ volatility of any single asset (diversification works); frontier curve monotonic and convex; **new assertion: Scheme A correlation matrix contains at least one negative correlation (measured: EEM-DBC = -0.12)** (validates covariance-structure diversity); weight validation follows the chosen convention (primary: no-shorting) |
| A3 | Real data | Uses real historical quotes (not random numbers); cache reproducible offline |
| A4 | Cluster collaboration visible | The demo clearly shows ≥4 agents handing off via the task board and messages |
| A5 | Charts complete | 5 required charts + metrics table complete, no Chinese tofu boxes |
| A6 | Clear conclusions | Reporting agent outputs: portfolio Sharpe vs. benchmark Sharpe (SPY), max drawdown, optimal weights; **new: weights aggregated by asset class + Sharpe comparison vs. the 60/40 (equity/bond) benchmark portfolio** |
| A7 | Live robustness | Runs offline (local cache); total demo ≤ 25 min; passes once with no errors |

### 6.2 Phased Timeline (Recommended: 5 Phases, ~2 Weeks / 8–12 Working Days)

| Phase | Content | Outputs | Duration |
|---|---|---|---|
| P1 Environment setup | Create virtual environment, install dependencies (incl. scikit-learn), verify jiuwenswarm team config & 5-role registration mechanism, test yfinance connectivity | Environment readiness report | 1–2 days |
| P2 Data pipeline | Scheme A data collection/cleaning/alignment (incl. EEM cross-market calendar & return-direction check)/caching + parameter scripts | `data/`, `params.json` | 1–2 days |
| P3 Core algorithms | GMV/tangency/efficient frontier (no-shorting numerical primary + analytical reference), unit-test assertions; **new milestone check: measure frontier shape & correlation matrix with the §5 verification code, confirm Scheme A expectations (negative correlation EEM-DBC=-0.12, clear GMV/tangency separation)** | `output/portfolios.csv`, frontier.csv | 2–3 days |
| P4 Cluster orchestration | Split into 5 agents, define task dependencies & message flow, run the full chain | Cluster pipeline scripts | 2–3 days |
| P5 Visualization & rehearsal | 5 charts + Streamlit + reporting report (incl. class weights & 60/40 comparison) + 2 full rehearsals | Charts, dashboard, report.md | 2–3 days |

> Milestone checkpoints: end of P2 (data real & usable; EEM/TLT/DBC return directions verified) → end of P3 (optimization correct; frontier shape matches Scheme A expectations) → end of P4 (full cluster chain runs) → end of P5 (rehearsal passes; verified against A1–A7).

### 6.3 Common Pitfalls & Fallback Options

| # | Pitfall | Symptom | Fallback / mitigation |
|---|---|---|---|
| 1 | yfinance network unreachable/rate-limited | Fetch timeout, HTTP 429 | Local CSV cache first; switch to akshare; or pre-download before the demo |
| 2 | Covariance matrix singular/not positive definite | scipy optimization errors, exploding weights | Insufficient samples → lengthen the history window; use Ledoit-Wolf shrinkage (`sklearn.covariance.LedoitWolf`, scikit-learn installed) ⚠️ to verify |
| 3 | Weights-sum-to-1 constraint violated | Optimized weights don't sum to 1 | Add an explicit equality constraint + result assertion; numerical tolerance 1e-6 |
| 4 | Negative weights (shorting) | Large negative weights, abnormal portfolio volatility | Primary demo convention: `bounds=(0,1)` no-shorting; negative weights in the analytical solution are expected (shorting-allowed case) — explain per §3.1 convention, never show both confusingly |
| 5 | Date misalignment (incl. EEM cross-market holidays) | Covariance computed on the wrong window, distorted results | `ffill().dropna()` first; add a window-length assertion (target ≥ 750 trading days) |
| 6 | Frontier non-convex/sawtooth/no solution at ends | Too few scan points, SLSQP local optima, endpoint errors | Scan 50–100 points, 5% margin at each end, try/except to skip infeasible points, warm start (§3.1) |
| 7 | matplotlib Chinese tofu boxes | Chinese glyphs render as boxes | Set PingFang SC / Noto Sans CJK font |
| 8 | Reporting agent data inconsistency | Agents use different data versions | All agents read the shared `data/` cache read-only; lock before writing |
| 9 | Unstable model API at the demo | Agents stutter/timeout | Use deterministic scripts as the live fallback (pre-generate all outputs after the cluster run); keep a screen recording |
| 10 | EEM/TLT/DBC negative returns over the past 5 years (Scheme A specific) | Negative annualized returns for single assets, student confusion | Measure return directions during development and prepare the talking point: "the goal of portfolio optimization is risk-adjusted return"; emphasize the diversification value of configurations like 60/40 during the demo |

---

## 7. Appendix: Command Cheat Sheet

```bash
# Environment (see local-env-setup-uv.md)
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install numpy pandas scipy matplotlib seaborn yfinance akshare streamlit jupyter scikit-learn
uv pip freeze > requirements.txt

# Data (verify connectivity during development)
python -c "import yfinance as yf; d=yf.download('SPY',period='5d'); print(d.tail(2))"

# Run the cluster demo (illustrative; follow the actual jiuwenswarm team startup) ⚠️ to verify
jiuwenswarm team start --name jiuwen_team   # exact CLI per the installed version's help

# Charts & interaction
python scripts/viz.py
streamlit run output/dashboard.py
```

---

### Document Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1.0 | 2026-08-13 | Initial version: complete six-dimension preparation checklist | portfolio-planner |
| v1.1 | 2026-08-13 | ①Scheme A asset pool (SPY/IWM/TLT/GLD/EEM/DBC), baseline stocks kept for comparison; ②first-round review I-1 (5-role registration mechanism)/I-2 (analytical vs. numerical constraint conventions)/I-3 (scikit-learn in the install list); ③first-round review S-1 (drawdown definition)/S-2 (timeline unified to 8–12 working days)/S-3 (script buffer)/S-4 (frontier scan boundary)/S-5 (uv install fallback)/S-6 (dynamic end date); ④asset-pool review comments for Scheme A (EEM weak-return check into P2, GLD/DBC difference note, frontier-shape validation into the P3 milestone); charts upgraded to 5 (heatmap as centerpiece, class-colored weight chart, dual-frontier comparison, benchmark switched to SPY); acceptance A2/A6 enhanced | portfolio-planner |
| v1.2 | 2026-08-13 | Back-filled P2b/P3 measured correlations: GLD-DBC=-0.12 (negative, replacing the 0.3–0.4 estimate), SPY-TLT=+0.68 (positive, correcting the "negative correlation between stocks and bonds" assumption); §0 asset-pool description, §2.1 covariance-structure note, §5.1 chart ④ and GLD/DBC note, §6.1 A2 assertion and §6.2 P3 milestone wording updated accordingly | portfolio-planner |
