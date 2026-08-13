# Cluster Orchestration Design (P4a) — 5-Agent Portfolio Optimization Demo

> Positioning: The heart of P4 and the soul of the demo — orchestrate the already-working engineering scripts (fetch_data / optimizer / viz) into a **5-agent cluster collaboration pipeline**, and live-demonstrate the full chain — "data collection → feature engineering → portfolio optimization → visualization → reporting" — on the jiuwenswarm team mode (task board + send_message + shared `.team/` workspace).
> Basis: Preparation checklist v1.2 (§4 Cluster-Mode Demo Design), engineering artifacts (scripts/fetch_data.py, scripts/optimizer.py, scripts/viz.py, data/params.json, output/frontier*.csv).
> Document version: **v1.1** (2026-08-13) ｜ Author: portfolio-planner
> **This is the English version of the Chinese v1.1 document** (`p4-orchestration-design.md`); structure, tables, commands, message examples (M1–M6), and demo-flow steps are kept identical.
> **v1.1 changes**: ①Incorporated review items I-1 (T1 also fetches the baseline stock pool) / I-2 (T3 inputs include features.json, dependency semantics clarified) / S-1 (§4.1 directory-sync approach consolidated to a single option) / S-2 (relation between params.json and params_assetclass.json explained) / S-3 (DAG diagram T5 dual-inbound edges clarified) / S-4 (M4 wording aligned with T5 dependency); ②deployment checklist updated (5 demo-role members spawned; blocker B-1 resolved by Leader decision). See the change log at the end of this document.

---

## 0. Design Overview (Read This First)

```
team-leader (task decomposition, acceptance; writes no code)
   │ creates 5 tasks (task board, dependencies expressed via blocked_by)
   ▼
┌─────────────┐   ┌─────────────────┐   ┌──────────────────┐   ┌─────────────┐   ┌──────────┐
│ data-collector│──►│ feature-engineer │──►│ optimizer-engine │──►│  viz-agent   │──►│ reporter │
│ fetch+clean+  │   │ compute mu/       │   │ GMV+tangency+    │   │ 5 charts +   │  │ metrics+ │
│ cache         │   │ Sigma/rf         │   │ frontier         │   │ dashboard    │  │ conclusions│
└─────────────┘   └─────────────────┘   └──────────────────┘   └─────────────┘   └──────────┘
   runs fetch_data.py    consumes data/ cache      runs optimizer.py       runs viz.py         aggregates output/
```

**Core design principles**:
1. **Script = task implementation**: each agent's task is to run one (or a group of) tested script(s) and produce the agreed files; the agent handles "decisions & handoffs" (what to read, which command to run, where to send results) without rewriting algorithms;
2. **Artifact = interface**: agents decouple through `data/` and `output/` files under `.team/`; messages carry only "path + summary";
3. **Cache first**: data-collector reads the cache by default (offline-capable demo); `--refresh` is the only trigger for network access;
4. **Write-lock protection**: lock before writing shared files, unlock after writing, to prevent agents from overwriting each other.

---

## 1. The 5 Role Definitions

> Each role specifies: task content / input files / output files / the existing scripts and commands it runs.

### 1.1 data-collector (Data Collection)

| Item | Content |
|---|---|
| Task content | ①Fetch 5 years of daily data for the six Scheme A ETFs (SPY/IWM/TLT/GLD/EEM/DBC), clean & align (ffill + dropna), compute returns and annualized parameters, write to cache; **cache first, `--refresh` only for network**; also fetch rf (^IRX) and the benchmark (SPY); ②**also fetch the six baseline stocks** (AAPL/MSFT/GOOGL/AMZN/JPM/XOM, reusing fetch_data.py `--name stocks`) and produce the baseline cache (review I-1) |
| Input | None (network or existing cache); the ticker list is given in the task description |
| Output | Scheme A: `data/closes_assetclass.csv`, `data/returns_assetclass.csv`, `data/params_assetclass.json`, `data/params.json` (official parameter file, incl. rf/benchmark/asset_class); **Baseline: `data/closes_stocks.csv`, `data/returns_stocks.csv`, `data/params_stocks.json`** (for the T3 baseline run and the T4 dual-frontier comparison) |
| Scripts | Scheme A: `python scripts/fetch_data.py --name assetclass --tickers SPY,IWM,TLT,GLD,EEM,DBC --years 5 --rf --benchmark SPY --params-out data/params.json`; **Baseline: `python scripts/fetch_data.py --name stocks --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5`** (review I-1) |
| Key checks | Data quality report fully green: closes_NaN=0, returns_NaN=0, trading days ≥ 750, rf assertion 0<rf<0.15 (assertions are built into the script; failure exits non-zero); both pools must pass |

### 1.2 feature-engineer (Feature Engineering)

| Item | Content |
|---|---|
| Task content | Validate params.json completeness (mu/Sigma/rf/benchmark/asset_class all present), add derived features: correlation matrix, per-asset-class return/volatility summary, 60/40 benchmark portfolio parameters (for the reporter's comparison), and produce a feature-summary JSON |
| Input | `data/params.json` (produced by data-collector), `data/returns_assetclass.csv` |
| Output | `data/features.json` (derived features: corr, asset_class_summary, benchmark_6040, etc.) |
| Scripts | No standalone script; reuses the params produced by `fetch_data.py` plus a derived-feature computation (can be consolidated into `scripts/features.py`, added after P2b, ⚠️ to verify) |
| Key checks | Correlation matrix contains at least one negative correlation (acceptance A2 assertion); asset_class labels complete |

> Note: P2b's fetch_data.py already writes rf/benchmark/asset_class into params.json; feature-engineer's incremental value is the **derived features** (correlation, class summary, 60/40 benchmark) — recommended to consolidate into `scripts/features.py` (a small script, added by dev-engineer at the end of P2b, ⚠️ to verify).

### 1.3 optimizer-engine (Optimization Engine)

| Item | Content |
|---|---|
| Task content | Run Markowitz optimization: GMV (numerical no-shorting primary + analytical reference), tangency portfolio (same convention), efficient-frontier scan of 60 points (5% margin / warm start / try-except); output the portfolio metrics table and frontier CSVs; run for both Scheme A and the baseline |
| Input | `data/params.json` (Scheme A), `data/params_stocks.json` (baseline), `data/returns_assetclass.csv`, `data/returns_stocks.csv`, **`data/features.json` (for pre-optimization correlation-matrix check and 60/40 benchmark comparison parameters, review I-2)** |
| Output | `output/portfolios.csv` (Scheme A primary output), `output/portfolios_stocks.csv`, `output/frontier.csv`, `output/frontier_stocks.csv` |
| Scripts | `python scripts/optimizer.py --params data/params.json --returns data/returns_assetclass.csv --tag assetclass` and the corresponding `--tag stocks` command |
| Key checks | Weights sum to 1 (±1e-6); GMV volatility ≤ any single asset; frontier convexity/curvature check (the script prints the P3 milestone summary); read features.json before optimizing to verify the correlation matrix contains a negative correlation (EEM-DBC measured at -0.12); primary convention is numerical no-shorting, analytical solution is reference only (review I-2 convention) |

### 1.4 viz-agent (Visualization)

| Item | Content |
|---|---|
| Task content | Consume output/ and data/ artifacts and produce the 5 required charts + optional Streamlit dashboard: ① efficient-frontier scatter (with Monte Carlo cloud + CML + GMV/tangency annotations); ② weight bar chart colored by asset class; ③ drawdown curve (portfolio vs. SPY benchmark); ④ correlation heatmap (centerpiece, contains negative correlation); ⑤ dual-frontier comparison (baseline stocks vs. Scheme A) |
| Input | `output/frontier.csv`, `output/frontier_stocks.csv`, `output/portfolios.csv`, `data/params.json`, `data/returns_*.csv` |
| Output | `output/frontier.png`, `output/weights.png`, `output/drawdown.png`, `output/corr_heatmap.png`, `output/frontier_compare.png`, `output/dashboard.py` (optional) |
| Scripts | `python scripts/viz.py` (produced by dev-engineer in P5, ⚠️ to verify: chart file naming and dashboard entry per the actual implementation) |
| Key checks | All 5 charts generated with no Chinese tofu boxes (PingFang SC); negative correlation visible in the heatmap |

### 1.5 reporter (Reporting)

| Item | Content |
|---|---|
| Task content | Aggregate all artifacts into the final conclusions report: portfolio Sharpe vs. benchmark (SPY) Sharpe, max drawdown, optimal weights, **weights aggregated by asset class**, **60/40 (equity/bond) benchmark portfolio Sharpe comparison**, risk-attribution conclusions |
| Input | `output/portfolios.csv`, `output/frontier*.csv`, `data/params.json`, `data/features.json`, `output/*.png` |
| Output | `output/report.md` (final demo report for live display) |
| Scripts | No standalone script; the reporter aggregates CSV/JSON into Markdown (can be consolidated into `scripts/report.py`, ⚠️ to verify) |
| Key checks | Conclusions fully cover acceptance item A6 (Sharpe comparison, max drawdown, class weights, 60/40 comparison) |

---

## 2. Task DAG & Dependencies

### 2.1 Dependencies (blocked_by)

| Task | blocked_by (predecessors) | Description |
|---|---|---|
| T1 data-collector | None | Runs first (network or cache) |
| T2 feature-engineer | T1 | Needs params.json / returns ready |
| T3 optimizer-engine | T2 (strict) | **Depends on T2 and consumes `data/features.json`** (pre-optimization correlation-matrix check; reads 60/40 benchmark parameters for comparison), ensuring derived features are consistent (review I-2); also needs T1's params/returns |
| T4 viz-agent | T3 | Needs frontier/portfolios ready |
| T5 reporter | T3 + T4 | Needs optimization results and charts ready (the reporter mainly reads CSVs; charts are referenced in the report) |

```
T1 ──► T2 ──► T3 ──► T4 ──┐
                          ├──► T5   (T5 blocked_by T3 + T4; formally starts after T4 completes)
                          └──► (after T3 completes, T5 may begin reading portfolios.csv for pre-aggregation)
```
> DAG note (review S-3): T5 depends on both T3 and T4; in practice T5 may start reading optimization results for pre-aggregation once T3 completes, but the **formal report.md must wait until T4's charts are ready** (M5 is the start trigger; see §3).

### 2.2 Mapping to the jiuwenswarm Task Board

- The leader creates tasks T1–T5 on the task board, each with `blocked_by` set per the table above (e.g., T3 blocked_by T2);
- Assignment strategy: **assign T1 first**; T2–T5 remain pending; once T1 completes its downstream tasks unlock automatically (the framework notifies the corresponding members when dependencies are released);
- Claiming mode: teammates claim tasks autonomously in `build_mode` (consistent with the measured flow of the current team);
- Demo effect: the "blocked_by chain" on the board is itself a visual DAG — the live demo can show tasks unlocking and advancing step by step.

---

## 3. Message Flow Design (send_message Handoffs)

> Convention: messages between agents carry only "**artifact path + one-line summary**", never the data body (hard constraint: ≤ 2000 characters); the receiver reads details via read_file.

| Handoff | Sender → Receiver | Message content (illustrative) |
|---|---|---|
| M1 | data-collector → feature-engineer | `data/params.json ready (SPY/IWM/TLT/GLD/EEM/DBC, 1254 trading days, rf=3.71%, incl. asset_class); please start feature engineering` |
| M2 | feature-engineer → optimizer-engine | `data/features.json ready (incl. corr/class summary/60-40 benchmark); params at data/params.json; please start optimization` |
| M3 | optimizer-engine → viz-agent | `output/frontier.csv + portfolios.csv ready (Scheme A, 59-point frontier, tangency Sharpe 0.999); please generate charts` |
| M4 | optimizer-engine → reporter | `output/portfolios.csv ready (GMV/tangency metrics); frontier_stocks.csv is the baseline; outputs ready (formal aggregation starts after T4, review S-4)` |
| M5 | viz-agent → reporter | `output/*.png — all five charts generated (incl. dual-frontier comparison); dashboard.py optional; charts can be cited in the report; formal aggregation may start (M5 is the T5 start trigger)` |
| M6 | reporter → team-leader | `output/report.md ready (Sharpe comparison / max drawdown / class weights / 60-40 conclusions); demo deliverable` |

**Teaching point**: every handoff demonstrates "agents pass only paths + summaries, never move data" — illustrating the engineering value of context decoupling and file-based collaboration in cluster mode.

---

## 4. Shared Artifact Conventions

### 4.1 Directory Layout (under .team/)

```
.team/jiuwen_team_sess_19ffa2c098f_773d5c07c3b4/
├── p4-orchestration-design.md      # this document
├── data/                           # data cache (read-mostly; lock before writing)
│   ├── closes_assetclass.csv / returns_assetclass.csv / params.json
│   ├── closes_stocks.csv / returns_stocks.csv / params_stocks.json
│   └── features.json               # produced by feature-engineer
└── output/                         # optimization & visualization artifacts (lock before writing)
    ├── portfolios.csv / frontier.csv / frontier_stocks.csv
    ├── frontier.png / weights.png / drawdown.png / corr_heatmap.png / frontier_compare.png
    ├── dashboard.py (optional)
    └── report.md
```

> Note (review S-1, consolidated to a single option): during the demo phase, `.team/.../data/` and `.team/.../output/` are the **single source of truth**; all three scripts (fetch_data/optimizer/viz) point to these directories directly via the `--data-dir` / `--output-dir` arguments (fetch_data.py and optimizer.py already support them; viz.py must be aligned, ⚠️ to verify). The symbolic-link approach is dropped (listed only as an optional alternative). Between the git repo's `data/`/`output/` and the `.team/` shared directories, choose one as the working directory to avoid two divergent data copies; it is recommended to use the `.team/` shared directory as the live working directory, keeping only scripts and documents in the git repo.
>
> **params dual-file relation (review S-2)**: `data/params_assetclass.json` is the **raw output copy** carrying the pool identifier (`--name assetclass`); `data/params.json` is the **unified official parameter file** (generated via `--params-out data/params.json`; content identical to the Scheme A copy) — **the P3 optimizer consumes `params.json` (the primary file)**; `params_assetclass.json` is used for pool-identifier traceability and comparison against the baseline (`params_stocks.json`); both the demo and acceptance use `params.json` as authoritative.

### 4.2 Write-Lock Conventions

- **Lock before writing**: any agent writing a file under `data/` or `output/` first calls `workspace_meta(action="lock", path=...)`;
- **Unlock after writing**: unlock immediately after the write completes (default 300 s auto-expiry);
- **Read-only, no lock**: pure reads (read_file / reading CSVs) need no lock;
- **Conflict avoidance**: agents mostly write different files (data-collector writes data/, optimizer writes output/); concurrent writes to the same file only occur between "data-collector refreshing the cache vs. downstream reads" — the convention is that **downstream does not start before T1 completes** (guaranteed by blocked_by), so no extra coordination is needed.

### 4.3 Read-Only Cache Conventions

- data-collector **reads the cache by default**: if `closes_assetclass.csv` exists, use it; `--refresh` only for network — the live demo can run offline (checklist pitfall #1);
- Downstream agents (feature/optimizer/viz/reporter) **read** `data/` and `output/` only, never modifying upstream artifacts;
- If regeneration is needed (data update), data-collector re-runs with `--refresh` and **serially** notifies downstream to re-run (no parallel overwrites).

---

## 5. Deployment Approach: Options & Recommendation

Comparing the three options:

| Dimension | Option 1: spawn demo roles in the current team | Option 2: dedicated demo-team configuration | Option 3: deterministic orchestration script |
|---|---|---|---|
| Approach | Create T1–T5 on the current team's task board; teammates claim and execute; role = task claimer + responsibility | Create a new `modes.team.<demo_team>` section in config.yaml, pre-register 5 roles (member_name/persona), restart, and demo in a standalone team | One `scripts/demo_pipeline.sh` sequentially calls fetch→optimize→viz→report, chaining the full pipeline |
| Cost | **Low** (zero new config; reuses the existing inprocess + build_mode flow) | **Medium-high** (config writing, restart, schema verification, ⚠️ to verify) | **Lowest** (one script) |
| Demo effect | **Good**: real multi-agent board + message flow + file handoffs, showing the essence of cluster collaboration | **Best**: standalone team, role names ARE the 5 roles, clean board with no interference | **Poor**: just a script pipeline, no agent-collaboration visuals (at most prints steps) |
| Live risk | **Low** (mechanism already measured; risk = other tasks on the board, can be cleaned up/focused beforehand) | **Medium** (new team config unmeasured; restart may affect the current session) | **Lowest** (deterministic, no LLM uncertainty; but loses the "cluster" selling point) |
| Teaching fit | Shows real collaboration: "leader decomposes, teammates claim, dependencies unlock" | Shows the full form of "building a standalone team from scratch" | Fallback only |

**Recommendation: Option 1 as primary + Option 3 as fallback.**

Rationale:
1. **Option 1 has the lowest cost and risk with adequate demo effect**: the team has already spawned the 5 demo-role members (data-collector / feature-engineer / optimizer-engine / viz-agent / reporter; blocker B-1 resolved by Leader decision — team expansion), each role is a teammate who can claim T1–T5 on the task board, and the M1–M6 message flow is genuine inter-member collaboration, satisfying acceptance A4 (≥4 agents collaborating visibly);
2. **Option 3 as the live fallback**: if the live LLM API is unstable / network is abnormal (checklist pitfall #9), deterministically re-run with pre-generated artifacts + `demo_pipeline.sh` so the demo cannot fail; pre-generated artifacts also allow offline demoing;
3. **Option 2 as an optional enhancement**: if the course requires a "standalone demo team" form, it can be added later — but the config.yaml `agents` section teammate-registration schema must be verified in advance (review I-1 ⚠️ item); it does not block the primary path.

**Deployment checklist (Option 1, v1.1 updated)**:
- [x] **5 demo-role members spawned and ready** (data-collector / feature-engineer / optimizer-engine / viz-agent / reporter; confirmed in the roster on 2026-08-13);
- [ ] Leader creates tasks T1–T5 with blocked_by set (T3 blocked_by T2 and consumes features.json; T5 blocked_by T3+T4);
- [ ] Confirm all 5 tasks are visible on the same team board, named with a role prefix (e.g., `demo:data-collector`) for live focus;
- [ ] Pre-generate all artifacts (output/report.md, etc.) as fallback copies;
- [ ] Confirm all three scripts (fetch_data/optimizer/viz) support `--data-dir`/`--output-dir` pointing at the .team shared directory (S-1; viz.py ⚠️ to verify);
- [ ] One full-chain rehearsal before the live demo (per the §6 script).

---

## 6. Live Demo Flow (with Teaching Points)

> Recommended total ≤ 20 min (core 15 min + 5 min buffer, per checklist S-3).

| Step | Duration | Action | Teaching point |
|---|---|---|---|
| 1. Opening | 1 min | Show the team board: 5 tasks + blocked_by dependency chain | "The pipeline is naturally phased, ideal for multi-agent orchestration" |
| 2. Task decomposition | 1 min | Leader explains the division of labor (data/features/optimization/visualization/reporting) | "The leader only decomposes tasks, never writes code — division of labor IS the architecture" |
| 3. T1 data-collector | 3 min | Claim the task, run fetch_data.py (cache or --refresh), show the data quality report | "Cache first, offline-capable demo" / "Data cleaning & alignment (EEM cross-market calendar)" |
| 4. M1 handoff | 0.5 min | Show the send_message (path + summary) | "Agents pass only paths, never move data" |
| 5. T2 feature-engineer | 1.5 min | Generate features.json; show the correlation matrix contains a negative correlation (DBC-EEM -0.12) | "Covariance-structure diversity is the core of Scheme A" |
| 6. T3 optimizer-engine | 2.5 min | Run optimizer.py; show GMV/tangency/frontier and the P3 milestone summary | "No-shorting primary vs. analytical reference (I-2)" / "Diversification reduces risk" |
| 7. M3/M4 handoffs | 0.5 min | Show message flow | "Dependencies unlock; relay progression" |
| 8. T4 viz-agent | 2 min | Run viz.py; show the 5 charts (heatmap + dual-frontier comparison highlighted) | "Asset-class diversification vs. single-stock diversification" / "Value of negatively correlated assets" |
| 9. T5 reporter | 2 min | Show report.md: Sharpe comparison, max drawdown, class weights, 60/40 comparison | "Conclusion closure: does the portfolio beat the benchmark; return-risk tradeoff" |
| 10. Summary | 1 min | Review the 5-role relay across the full chain + optional extensions outlook (risk parity / BL) | "Multi-agent cluster = engineered delivery of portfolio optimization" |
| 11. Buffer | ≤5 min | Interactive demo (dashboard parameter tuning) / Q&A | Skip if over time (S-3) |

**Live risk playbook**:
- LLM stutters → switch to Option 3 deterministic script re-run (artifacts pre-generated);
- Network down → data-collector reads the cache; the whole flow runs offline;
- An agent task fails → the leader reassigns on the board / a standby member claims it (role responsibility is bound to the script; swap the person, keep the logic).

---

### Document Change Log

| Version | Date | Changes | Author |
|---|---|---|---|
| v1.0 | 2026-08-13 | Initial version: 5-role task definitions / DAG / message flow / shared-artifact conventions / deployment recommendation / live demo flow | portfolio-planner |
| v1.1 | 2026-08-13 | ①Incorporated review I-1 (T1 also fetches baseline stocks) / I-2 (T3 inputs add features.json, dependency semantics clarified) / S-1 (§4.1 directory approach consolidated to --data-dir/--output-dir as the single option) / S-2 (params.json vs. params_assetclass.json relation explained) / S-3 (DAG diagram T5 dual-inbound edges clarified) / S-4 (M4 wording aligned with T5 dependency); ②deployment checklist updated (5 demo-role members spawned; blocker B-1 resolved by Leader decision) | portfolio-planner |
