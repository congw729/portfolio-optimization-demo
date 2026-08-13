# Portfolio Optimization Course Demo — jiuwenswarm Cluster Mode

A complete course project demo for **Modern Portfolio Theory (Markowitz Mean-Variance Optimization)**, built as a **multi-agent cluster pipeline** running on the [jiuwenswarm](https://github.com/) team mode. The demo covers the full pipeline: **data collection → feature engineering → portfolio optimization → visualization → reporting**, executed by 5 collaborating agents, plus an interactive web dashboard.

> 中文简介：基于 jiuwenswarm 集群模式（team 模式）制作的投资组合优化（马科维茨均值-方差框架）课程 Project Demo。5 个 agent 角色协作完成「数据采集 → 特征计算 → 组合优化 → 可视化 → 汇报」全链路，配套可交互展示网页。

## Highlights

- **Cross-asset portfolio (Portfolio A)**: SPY / IWM / TLT / GLD / EEM / DBC — equity, long-duration bonds, gold, emerging markets, and commodities; correlation structure contains negative (EEM-DBC) and near-zero pairs, ideal for teaching diversification.
- **Baseline for comparison**: 6 mega-cap stocks (AAPL / MSFT / GOOGL / AMZN / JPM / XOM) for a two-frontier comparison (asset-class diversification vs stock-level diversification).
- **Core algorithms**: GMV (minimum variance), tangency (max Sharpe) portfolio, and a 60-point efficient frontier scan — numeric optimization (no short selling, primary) with analytic closed-form solutions as teaching contrast.
- **Optional extensions**: Risk Parity, Black-Litterman, and Monte Carlo simulation.
- **5-agent cluster orchestration**: leader breaks down tasks, teammates claim tasks on the shared board, hand off via `send_message`, and share artifacts through a common workspace (`.team/`).

## 5-Agent 协同架构（Cluster Orchestration）

demo 的核心是「**5 个 agent + 1 个 leader**」的集群协作流水线，运行在 jiuwenswarm team 模式（任务看板 + `send_message` + 共享 `.team/` 工作空间）上，完成「数据采集 → 特征计算 → 组合优化 → 可视化 → 汇报」全链路。leader 只负责拆任务与验收、**不写代码**；五个 teammate 认领任务、按 `blocked_by` 依赖接力，agent 之间只传「**产物路径 + 一句话摘要**」，不搬运数据正文。

### 角色职责表

| 角色 | 任务 | 职责 | 输入 → 输出 | 对接脚本 |
|---|---|---|---|---|
| leader | — | 拆任务、验收（不写代码） | 设计 → 5 个任务 + 验收结论 | 无（仅编排） |
| data-collector | T1 | 拉取 + 清洗 + 缓存（缓存优先，`--refresh` 才联网） | 联网/缓存 → `data/params.json`、`data/returns_*.csv` | `scripts/fetch_data.py` |
| feature-engineer | T2 | 派生特征（corr / 类别汇总 / 60-40 基准） | `data/params.json` + returns → `data/features.json` | `scripts/features.py` |
| optimizer-engine | T3 | GMV / 切线 / 有效前沿（禁做空主口径 + 解析对照） | params + returns + features → `output/portfolios.csv`、`frontier.csv` | `scripts/optimizer.py` |
| viz-agent | T4 | 5 张图 + dashboard | frontier/portfolios → `output/*.png` | `scripts/viz.py` |
| reporter | T5 | 汇总指标与结论 | 全部产物 → `output/report.md` | `scripts/report.py` |

### 依赖链（DAG）

```
leader（拆任务、验收，不写代码）
   │ 创建 T1–T5 任务（blocked_by 表达依赖）
   ▼
data-collector ──► feature-engineer ──► optimizer-engine ──► viz-agent ──► reporter
                                                  └───────────────────────────►
                              （reporter 还依赖 optimizer-engine，即 T3 → T5）
```

| 任务 | blocked_by | 说明 |
|---|---|---|
| T1 data-collector | 无 | 最先执行（联网或读缓存） |
| T2 feature-engineer | T1 | 需要 params.json / returns 就绪 |
| T3 optimizer-engine | T2（严格） | 消费 `data/features.json`（优化前校验负相关、读 60/40 基准参数） |
| T4 viz-agent | T3 | 需要 frontier / portfolios 就绪 |
| T5 reporter | T3 + T4 | 需要优化结果与图表就绪 |

### 消息流（agent 只传「路径 + 摘要」）

| 衔接 | 发送方 → 接收方 | 消息示意 |
|---|---|---|
| M1 | data-collector → feature-engineer | `data/params.json 已就绪（含 asset_class），请开始特征计算` |
| M2 | feature-engineer → optimizer-engine | `data/features.json 已就绪（含 corr/60-40 基准），请开始优化` |
| M3 | optimizer-engine → viz-agent | `output/frontier.csv + portfolios.csv 已就绪，请出图` |
| M4 | optimizer-engine → reporter | `output/portfolios.csv 已就绪（GMV/切线），frontier_stocks.csv 为基线` |
| M5 | viz-agent → reporter | `output/*.png 五张图已生成（含双前沿对比），可开始正式汇总` |
| M6 | reporter → team-leader | `output/report.md 已就绪（夏普/回撤/类别权重/60-40），demo 可交付` |

> 教学点：每个衔接点都体现「agent 只传路径 + 摘要、不搬数据」——集群模式下上下文解耦与文件共享协作的工程价值。

> 详细设计见 `docs/p4-orchestration-design.md`（§1 角色定义、§2 DAG、§3 消息流）。

## Directory Structure

```
.
├── README.md                 # This file
├── scripts/                  # Pipeline scripts (each maps to an agent role)
│   ├── fetch_data.py         #   data-collector: fetch → clean → returns → cache
│   ├── features.py           #   feature-engineer: derived features → data/features.json
│   ├── optimizer.py          #   optimizer-engine: GMV / tangency / efficient frontier
│   ├── viz.py                #   viz-agent: 5 charts (PNG) with Chinese font support
│   ├── report.py             #   reporter: final report.md / report.en.md (--lang)
│   ├── extensions.py         #   optional: risk parity / Black-Litterman / Monte Carlo
│   ├── test_optimizer.py     #   unit tests for optimizer (assert-based, no pytest)
│   ├── test_extensions.py    #   unit tests for extensions
│   └── demo_pipeline.sh      #   deterministic one-shot pipeline (fallback mode)
├── data/                     # Cached market data + params (not committed to git)
│   ├── closes_*.csv          #   aligned close prices (auto-adjust)
│   ├── returns_*.csv         #   daily returns
│   ├── params.json           #   mu / Sigma / rf / benchmark / asset_class
│   ├── params_stocks.json    #   baseline parameters
│   └── features.json         #   derived features (corr, class summary, 60/40)
├── output/                   # Optimization & visualization outputs (CSV/PNG not committed)
│   ├── portfolios*.csv       #   portfolio metrics (GMV / tangency / analytic contrast)
│   ├── frontier*.csv         #   efficient frontier points (A + baseline)
│   ├── extensions_summary.csv#   extension algorithm results
│   ├── *.png                 #   5 charts (frontier, weights, drawdown, heatmap, compare)
│   ├── report.md / report.en.md  # final report (Chinese / English)
│   └── dashboard.py          #   Streamlit interactive page
├── app/                      # Multi-page interactive web app (Streamlit + plotly)
├── docs/                     # Design & review documents (for GitHub backup)
│   ├── portfolio-optimization-demo-prep.md / .en.md   # preparation checklist v1.2
│   ├── p4-orchestration-design.md / .en.md            # 5-agent orchestration design v1.1
│   ├── local-env-setup-uv.md                          # uv environment setup guide
│   ├── p1-env-report.md / p2-data-report.md           # environment & data reports
│   ├── asset-pool-options.md / p5-dashboard-design.md # design documents
│   ├── *-review.md                                    # independent review reports
│   └── report.md / report.en.md                       # final demo reports
└── .venv/                    # Python 3.12 virtual environment (not committed)
```

## Environment Setup

Requirements: macOS (tested on Darwin 23.5.0, arm64), network for first data fetch.

```bash
# 1. Install uv (fallback: pip install --user uv if astral.sh unreachable)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. Create Python 3.12 venv and install dependencies
cd project-demo
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install numpy pandas scipy matplotlib seaborn yfinance akshare streamlit jupyter scikit-learn
uv pip freeze > requirements.txt
```

> Full step-by-step guide (with fallbacks and troubleshooting): `docs/local-env-setup-uv.md`.

## Quick Start (One-Shot Pipeline)

```bash
# Deterministic full pipeline: fetch (cache-first) → features → optimizer → viz → report
bash scripts/demo_pipeline.sh

# Interactive web app (Streamlit + plotly multi-page)
streamlit run app/Home.py          # or: streamlit run output/dashboard.py (single page)
```

## Running the 5-Agent Cluster Demo

1. Leader creates 5 tasks on the team board with `blocked_by` dependencies:
   `data-collector → feature-engineer → optimizer-engine → viz-agent → reporter`.
2. Teammates claim tasks (build_mode), execute the mapped scripts, and hand off via `send_message` (path + one-line summary only).
3. Shared artifacts live in the common workspace; write access is guarded by file locks.
4. Fallback: `scripts/demo_pipeline.sh` re-runs the whole chain deterministically (works offline with cached data).

## Key Results (as of 2026-08-13, 5-year daily data)

| Metric | Portfolio A | Baseline Stocks |
|---|---|---|
| GMV volatility | 10.1% | 17.7% |
| Tangency Sharpe | 0.999 | 1.131 |
| Benchmark SPY Sharpe | 0.592 | — |
| 60/40 benchmark Sharpe | 0.500 | — |

- Asset-class diversification lowers GMV volatility far below any single asset (15.7%–22.5% range), demonstrating the value of low/negative correlation.
- Tangency (max Sharpe) portfolio beats both benchmark SPY (0.592) and the 60/40 benchmark (0.500).

## License & Attribution

Course project demo. Data from Yahoo Finance via `yfinance` (free, no API key). This repository is a backup of the team workspace deliverables.

---
*Generated by the Portfolio Optimization course demo team (jiuwenswarm cluster mode).*
