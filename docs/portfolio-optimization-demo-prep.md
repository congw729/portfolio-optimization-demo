# Portfolio Optimization 课程 Project Demo — 项目准备清单

> 目标：使用 **jiuwenswarm 集群模式（team 模式）** 制作投资组合优化（马科维茨均值-方差框架）课程 Project Demo。
> 本文档是一份**完整、可执行**的准备清单：覆盖环境与工具、数据准备、算法/模型准备、集群模式演示设计、演示素材、验收与里程碑六大维度。
> 每项准备内容均给出「是什么 + 为什么需要 + 怎么获得/配置」三要素；**不确定的环境依赖标注为「⚠️ 需验证」**。
>
> 文档版本：**v1.2**（2026-08-13）｜ 作者：portfolio-planner
> **v1.2 变更项**：回写方案 A 实测相关性数据（P2b/P3 实测）——**GLD-DBC 实测 -0.12（负相关，替代原预估值 0.3–0.4）**；**SPY-TLT 实测 +0.68（正相关，近 5 年股债同向，更正原「负相关出现在股债」的预判）**；同步更新 §5.1 图表④描述、GLD/DBC 说明与 §6 验收/里程碑表述；版本由 v1.1 升至 v1.2。变更明细见文末维护记录。

---

## 0. Demo 总览（先看这里）

| 项目 | 说明 |
|---|---|
| Demo 主题 | 用多 agent 集群协作完成「数据采集 → 特征计算 → 组合优化 → 可视化 → 汇报」的完整投资组合优化流水线 |
| 核心算法 | 马科维茨均值-方差优化：有效前沿、最小方差组合、最大夏普（切线）组合 |
| 可选扩展 | 风险平价、Black-Litterman、蒙特卡洛模拟（作为加分项） |
| 演示市场 | 美股 / 美股上市 ETF（yfinance 免费、无风险利率易取）；A 股可作备选（akshare） |
| 建议资产池 | **方案 A（推荐，已确认）**：SPY / IWM / TLT / GLD / EEM / DBC —— 跨资产类别组合（美股大盘 + 小盘 + 长债 + 黄金 + 新兴市场 + 广义商品），协方差结构含正相关（股-股）、负相关（**GLD-DBC 实测 -0.12**）与近零相关（DBC-多数），直接对应「资产配置」课程主线 |
| 对比组合（保留） | 基线 6 只个股（AAPL/MSFT/GOOGL/AMZN/JPM/XOM）保留作对比，演示「资产类别分散 vs 个股分散」双前沿差异 |
| 演示形态 | 集群模式跑通流水线 + 产出图表（有效前沿、权重条形图、回撤曲线、相关性热力图）+ 可选 Streamlit 交互页 |
| 总工期建议 | 5 个阶段，约 **2 周（8–12 个工作日）**（详见 §6.2） |

---

## 1. 环境与工具

### 1.1 Python 版本

- **是什么**：整个数据管道与优化算法全部基于 Python 实现，需要确定解释器版本。
- **为什么需要**：numpy/pandas/scipy/matplotlib 新版本对 Python 版本有要求；Python 3.9 过旧（本机实测为 3.9.6，见下），3.12+ 生态最稳。
- **怎么获得/配置**：
  - 推荐 **Python 3.10–3.12**（3.12 为当前主流，全部依赖均有预编译 wheel）。
  - 通过 `pyenv` / `uv` / `conda` 管理多版本：`uv python install 3.12` 或 `conda create -n po-demo python=3.12`。
  - ⚠️ 需验证：本机实测 `/usr/bin/python3` 为 **Python 3.9.6**，且系统自带解释器与 pip 安装可能受 PEP 668（externally-managed-environment）限制，**不要直接用系统 python3 装包**，必须建虚拟环境。
  - **实操指南**：完整安装步骤见配套文档 `local-env-setup-uv.md`（基于 uv 的 macOS 环境搭建指南，含每步验证命令与预期输出）。

### 1.2 核心 Python 依赖（numpy / pandas / scipy / matplotlib / scikit-learn）

- **是什么**：数值计算、表格数据处理、优化求解、绘图四件套 + 统计收缩估计库。
- **为什么需要**：
  - numpy：向量/矩阵运算（协方差矩阵、权重向量）；
  - pandas：历史行情 DataFrame、交易日对齐、收益率计算；
  - scipy.optimize：有效前沿与最大夏普组合的约束优化求解（SLSQP）；
  - matplotlib：有效前沿散点、权重条形图、回撤曲线；
  - **scikit-learn**：协方差矩阵不正定时的 **Ledoit-Wolf 收缩估计**兜底（`sklearn.covariance.LedoitWolf`），评审 I-3 要求纳入。
- **怎么获得/配置**（在虚拟环境中一次性安装）：

  ```bash
  uv pip install --python 3.12 \
    numpy pandas scipy matplotlib seaborn \
    yfinance akshare streamlit jupyter scikit-learn
  ```

  - 建议同时装 `seaborn`（图表更美观）与 `jupyter`（开发调试）。
  - 安装完成后立即固化版本：`uv pip freeze > requirements.txt`（详见 `local-env-setup-uv.md` §3.2）。
  - ⚠️ 需验证（本机实测，系统 python3.9 环境）：numpy 2.0.2 / pandas 2.3.3 / scipy 1.13.1 / matplotlib 3.9.4 已就绪；**yfinance 与 scikit-learn 未安装，需补装**。建议在 demo 专用虚拟环境中重新验证整套版本组合。

### 1.3 数据获取库：yfinance / akshare

- **是什么**：
  - `yfinance`：免费拉取 Yahoo Finance 行情（美股/ETF/指数/国债收益率，无需 API key）。
  - `akshare`：免费拉取 A 股/港股/中国债券数据（A 股备选方案）。
- **为什么需要**：Demo 的「数据采集 agent」必须能从真实数据源拿到历史价格；两库均免费、纯 Python、无需注册，适合课程演示。
- **怎么获得/配置**：`pip install yfinance akshare`（与上一条合并）。
  - ⚠️ 需验证：yfinance 依赖网络访问 Yahoo Finance，**国内网络环境可能不稳定/被墙**，演示前必须实测一次下载；建议提前把数据缓存为本地 CSV（见 §2.4），现场断网也能演示。

### 1.4 jiuwenswarm 集群模式（team 模式）安装与启动配置

- **是什么**：jiuwenswarm 的**集群模式 = team 模式**：一个 leader agent + 多个 teammate agent，通过任务看板（task board）+ 消息通道（send_message）协作，共享 `.team/` 工作空间。
- **为什么需要**：这是本 Demo 的**核心展示载体**——把投资组合优化流水线拆成多个 agent 角色协作完成（详见 §4），展示多 agent 编排能力。
- **怎么获得/配置**：
  - 安装：`pip install jiuwenswarm`（若已有环境则跳过）。
  - 团队配置位于 `~/.jiuwenswarm/config/config.yaml` 的 `modes.team.<team_name>` 段。当前本项目团队（实测配置）：
    ```yaml
    modes:
      team:
        jiuwen_team:
          team_name: jiuwen_team
          lifecycle: persistent          # 团队生命周期
          teammate_mode: build_mode      # teammate 自主执行模式
          spawn_mode: inprocess          # 进程内生成 agent
          enable_swarmflow: false
          worktree: { enabled: true }    # 成员 worktree 隔离（写代码用）
          transport: { type: inprocess }
          storage: { type: sqlite }
          leader: { member_name: team-leader, display_name: 团队领导, persona: "..." }
          agents: { leader: $agent_leader }
          workspace: { enabled: true }
    ```
  - **5 个 teammate 角色的注册/创建机制（评审 I-1 补充）**，两种方式任选：
    - **方式 1：config.yaml `agents` 段静态注册**——在 `modes.team.<team_name>.agents` 下逐个声明角色（引用 `$agent_teammate` 模板并覆盖 member_name / persona）：
      ```yaml
      agents:
        leader: $agent_leader
        data-collector:    # 数据采集 agent
          <<: *agent_teammate    # 继承 agent_teammate 模板（YAML anchor 写法，按实际配置语法调整）
          member_name: data-collector
          display_name: 数据采集
          persona: "负责拉取行情并清洗对齐"
        feature-engineer:  { member_name: feature-engineer, persona: "..." }
        optimizer-engine:  { member_name: optimizer-engine, persona: "..." }
        viz-agent:         { member_name: viz-agent, persona: "..." }
        reporter:          { member_name: reporter, persona: "..." }
      ```
      ⚠️ 需验证：`agents` 段的 teammate 声明语法与模板继承写法需以安装版本 `jiuwenswarm` 的实际 schema 为准（示例为示意，未实测）。
    - **方式 2：leader 运行时创建（推荐，当前团队即此机制）**——leader 在任务看板（task board）创建任务并指派 member_name，teammate 以 `build_mode` 自主认领执行；角色即「任务认领者 + 职责分工」，无需在 config.yaml 预注册。
    - 建议：**优先方式 2**（本团队实测的 inprocess + build_mode 流程即如此，改动最小）；若需静态注册多个预置 teammate，再走方式 1 并实测验证。
  - 启动：以集群/团队模式启动 jiuwenswarm 后，leader 创建任务（task board），teammate 自主认领执行；成员间通过 `send_message` 通信，产物落 `.team/` 共享目录。
  - ⚠️ 需验证：Demo 现场若需**独立于本课程团队**新建演示团队，需在 config.yaml 增加新 team 段并重启；确认 spawn_mode/transport 采用 inprocess 即可单机演示（无需 Docker 多机）。

### 1.5 虚拟环境 / Docker

- **是什么**：
  - 虚拟环境：隔离的 Python 依赖集合（venv / conda / uv）。
  - Docker：容器化环境（镜像级隔离，跨机器一致）。
- **为什么需要**：避免污染系统 Python（PEP 668）、保证演示环境可复现、防止版本冲突；Docker 仅在需要多机/云端演示或环境迁移时才有必要。
- **怎么获得/配置**：
  - **首选虚拟环境（轻量、够用）**：`uv venv --python 3.12 .venv && source .venv/bin/activate`。
  - Docker 可选：`python:3.12-slim` 基础镜像 + `requirements.txt`（`pip freeze > requirements.txt` 固化版本）。Demo 是单机 inprocess 集群，**默认不需要 Docker**。

### 1.6 其他工具

| 工具 | 是什么 | 为什么需要 | 怎么获得 |
|---|---|---|---|
| Git | 版本控制 | 记录 demo 代码演进、方便回滚与评审 | `brew install git` / 自带 |
| uv | Python 包/环境管理（快） | 一条命令建环境+装依赖，比 pip 快 10 倍 | `curl -LsSf https://astral.sh/uv/install.sh \| sh`（⚠️ 需验证网络）；**失败兜底**（评审 S-5）：`python3 -m pip install --user uv` 或临时 venv 引导 `python3 -m venv /tmp/uv-bootstrap-venv && /tmp/uv-bootstrap-venv/bin/pip install uv`，或退回 conda/venv 方案（§1.5）——详见 `local-env-setup-uv.md` §1.2 |
| Streamlit（可选） | Web 交互界面框架 | 演示时现场改参数（资产池/风险厌恶系数）看组合变化 | `pip install streamlit` |
| VS Code / Jupyter | 开发与调试 | 写代码、看数据 | 按个人习惯 |

---

## 2. 数据准备

### 2.1 资产池与历史价格数据获取

- **是什么**：选定 **6 只美股上市 ETF（方案 A）**，拉取近 3–5 年日线收盘价；同时保留基线 6 只个股作对比。
- **为什么需要**：均值-方差优化需要「每只资产的期望收益 + 资产间协方差」，全部由历史价格计算得出；方案 A 的跨类别构成（股/债/商品/国际）使协方差结构含正相关（股-股）、负相关（GLD-DBC 实测 -0.12）与近零相关（DBC-多数），教学信息量最大。
- **怎么获得/配置**：

  ```python
  import yfinance as yf
  import pandas as pd

  # 方案 A（主资产池）：跨资产类别 ETF
  tickers_a = ["SPY", "IWM", "TLT", "GLD", "EEM", "DBC"]
  # 基线（对比资产池）：6 只个股
  tickers_base = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "XOM"]

  # 截止日动态化（评审 S-6）：按演示前最近交易日取数，避免写死过期
  end = pd.Timestamp.today().strftime("%Y-%m-%d")
  start = (pd.Timestamp.today() - pd.DateOffset(years=5)).strftime("%Y-%m-%d")

  data = yf.download(tickers_a, start=start, end=end,
                     group_by="ticker", auto_adjust=True, threads=True)
  closes = data.loc[:, (slice(None), "Close")]   # 多列 → 每 ticker 一列
  closes.columns = tickers_a
  ```

  - `auto_adjust=True`：自动用复权价（已调整拆股/分红——ETF 分红已含在内），避免价格跳变。
  - 资产类别标注（供下游按类别聚合）：SPY/IWM=美股权益、TLT=美国长债、GLD=贵金属、EEM=新兴市场权益、DBC=广义商品。
  - ⚠️ 需验证（方案 A 特有）：EEM（新兴市场）与美股交易日历存在差异（新兴市场休市日美股可能交易），`dropna(how="any")` 后时间窗可能略缩短，需实测可用窗口长度（目标 ≥ 3 年、约 750 个交易日）。
  - ⚠️ 需验证（收益方向）：**EEM / TLT / DBC 近 5 年可能接近零或为负收益**（新兴市场跑输、利率上行、商品展期损耗），须在开发期实测收益方向并备好解释话术：「组合优化的目标是风险调整后收益，而非单资产正收益」。
  - ⚠️ 需验证：首次拉取必须实测网络连通性；若失败，改用本地缓存（见 §2.4）或换数据源。
  - 基线 6 只个股拉取方式相同（`tickers_base`），仅用于双前沿对比，不进入主流程优化。

### 2.2 数据清洗与对齐（交易日、缺失值、收益率）

- **是什么**：
  - **对齐**：不同资产上市日期/停牌日/休市日不同 → 日期索引不一致，需统一到共同交易日。
  - **缺失值**：个别交易日无数据（停牌、数据源缺漏、跨市场休市）。
  - **收益率**：由价格序列计算日收益率，用于均值与协方差估计。
- **为什么需要**：协方差矩阵要求所有资产在同一时间轴上才有意义；缺失值直接进计算会导致协方差矩阵不正定（后续优化失败）；收益率是优化的直接输入。
- **怎么获得/配置**：

  ```python
  # 1) 对齐：取所有资产都有的交易日（交集），或先前向填充再按交集对齐
  #    方案 A 含跨市场 ETF（EEM），务必实测 ffill 后窗口长度
  closes = closes.ffill().dropna(how="any")

  # 2) 收益率：简单收益率（课程演示推荐，直观）
  returns = closes.pct_change().dropna()
  # 备选：对数收益率 log_returns = np.log(closes / closes.shift(1)).dropna()
  #       （对数收益率在跨期加总时数学性质更好，但数值差异对演示结果影响很小）

  # 3) 年化参数
  ann_return = returns.mean() * 252
  ann_cov    = returns.cov() * 252
  ```

- **常见坑**：① 不同资产上市日期不同导致 `dropna` 后只剩很短时间窗 → 统一用「全部在 2021 年前上市」的成熟标的（方案 A 六只 ETF 均满足）；② 跨市场休市（EEM）导致尾部缺失 → `ffill()` 先行处理；③ 基线个股同样存在停牌/拆股（auto_adjust 已处理）。
- ⚠️ 需验证：`dropna(how="any")` 与 `ffill` 两种策略对最终有效前沿形状的影响，建议在开发阶段各跑一次对比，演示时固定用一种并写进文档。

### 2.3 无风险利率与市场基准

- **是什么**：
  - **无风险利率 rf**：优化中「超额收益 = 资产收益 − rf」，最大夏普组合依赖它。
  - **市场基准**：用于画 CML（资本市场线）与对比（如 S&P 500 指数），也用于计算 beta 或作为 Black-Litterman 先验（可选扩展）。
- **为什么需要**：没有 rf 就无法定义夏普比率与切线组合；没有基准就无法展示「组合跑赢/跑输大盘」这一课程核心结论。
- **怎么获得/配置**（美股演示）：
  - 无风险利率：用 **3 个月期美债收益率**（Yahoo Ticker `^IRX`）或 **13 周国债**：
    ```python
    rf_series = yf.download("^IRX", start=start, end=end)["Close"].iloc[-1] / 100.0
    rf_annual = rf_series   # ^IRX 返回的是百分数数值，需除以 100
    ```
    - 简单起见也可用常数 rf ≈ 0.04–0.05（近两年美债水平），并在文档中注明取值依据。
  - 市场基准：**推荐 SPY**（与组合内资产同口径、同为 ETF，对比更直观、口径更公平）；也可用 S&P 500 指数 `^GSPC`：
    ```python
    spx = yf.download("SPY", start=start, end=end, auto_adjust=True)["Close"]
    spx_ret = spx.pct_change().dropna()
    ```
  - A 股备选：无风险利率用 10 年期国债收益率（akshare `ak.bond_zh_us_rate()`）；基准用沪深 300（代码 `000300.SH`）。
  - ⚠️ 需验证：`^IRX` 数值单位（百分数 vs 小数）在演示脚本里必须写清楚并加断言（`assert 0 < rf < 0.15`）。

### 2.4 数据缓存（演示稳健性关键）

- **是什么**：把拉取到的行情落盘为本地 CSV/Parquet。
- **为什么需要**：① 现场演示不依赖网络；② 多 agent 共享同一份数据（避免重复拉取、结果不一致）；③ 可复现；④ 方案 A 与基线可并存对比。
- **怎么获得/配置**：

  ```python
  # 文件名加方案标识（评审 A 项要求），便于多资产池并存对比
  closes.to_csv("data/closes_assetclass.csv")      # 方案 A：SPY/IWM/TLT/GLD/EEM/DBC
  returns.to_csv("data/returns_assetclass.csv")
  closes_base.to_csv("data/closes_stocks.csv")     # 基线：6 只个股
  returns_base.to_csv("data/returns_stocks.csv")
  ```

  - 约定：数据 agent 优先读缓存（`data/` 目录），缓存缺失或带 `--refresh` 参数时才联网拉取。

---

## 3. 算法 / 模型准备

### 3.1 马科维茨均值-方差优化（核心必做）

- **是什么**：在「给定目标收益」下最小化组合方差，或在「给定风险」下最大化收益，得到有效前沿（efficient frontier）；前沿上有两个特解：**最小方差组合（GMV）** 与 **最大夏普组合（tangency portfolio）**。
- **为什么需要**：这是课程 Demo 的**主算法**，全部可视化（有效前沿、权重条形图）围绕它展开。
- **怎么获得/配置**（数学工具 + 依赖）：

  - **输入**：年化期望收益向量 `mu`（`returns.mean()*252`）、年化协方差矩阵 `Sigma`（`returns.cov()*252`）、无风险利率 `rf`。
  - **数学形式**（N 资产）：
    - 最小化 `wᵀ Σ w`，约束 `Σwᵢ = 1`（权重和=1），可选 `wᵢ ≥ 0`（禁做空）或允许做空。
    - 最大夏普：最大化 `(wᵀμ − rf) / √(wᵀΣw)`，同样约束权重和为 1。
  - **⚠️ 重要：解析解与数值解的约束口径差异（评审 I-2）**：
    - **解析解（下述公式）隐含「允许做空、无界权重」**——在无 `wᵢ ≥ 0` 约束下推导，GMV/切线组合可能出现负权重；
    - **禁做空（`wᵢ ≥ 0`）只能用数值优化（scipy SLSQP）**，其结果与解析解**不同**（如解析 GMV 可能含负权重）；
    - **演示口径必须统一**：① 推荐全部用**数值优化（禁做空）**作为主演示口径（更贴近真实投资约束）；或 ② 把「无约束 vs 禁做空」作为**对比展示点**（教学亮点：展示允许做空如何扩展有效前沿、提高夏普），并在验收 A2 中注明权重校验按所选口径执行。**不要并列展示两套结果而不说明差异**，避免学员误以为结果矛盾。
  - **实现方式**：
    1. **解析解（仅用于「允许做空」情形对照/教学）**：
       - GMV：`w_gmv = Σ⁻¹·1 / (1ᵀ·Σ⁻¹·1)`（注意数值稳定性，用 `np.linalg.solve` 而非求逆）；
       - 切线组合：`w_tan = Σ⁻¹·(μ − rf·1) / (1ᵀ·Σ⁻¹·(μ − rf·1))`。
    2. **数值优化（推荐主口径：禁做空，scipy）**：
       ```python
       from scipy.optimize import minimize
       def port_var(w): return w @ Sigma @ w
       cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]   # 权重和=1
       bounds = [(0, 1)] * N                                   # 禁做空（主演示口径）
       res = minimize(port_var, x0=np.ones(N)/N, method="SLSQP",
                      constraints=cons, bounds=bounds)
       ```
       - 有效前沿扫描（评审 S-4：处理可行域边界）：目标收益扫描范围在 `[min(mu), max(mu)]` 两端各留 **5% 余量**；对每次 `minimize` 用 **try/except 跳过无可行解点**，并配合 **warm start**（用前一解作初值）保证曲线连续：
         ```python
         lo, hi = mu.min() * 1.05, mu.max() * 0.95   # 两端各留 5% 余量
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
                 continue                                 # 跳过不可行点
         ```
  - **依赖**：numpy（线性代数）+ scipy.optimize（SLSQP）；收缩估计兜底用 scikit-learn（§1.2 已装）。

### 3.2 有效前沿 / 最小方差 / 最大夏普 / 回撤（计算与展示要点）

- **是什么**：四样标准输出——① 有效前沿曲线（收益-风险平面上最优组合集合）；② GMV 权重；③ 最大夏普组合权重及对应夏普比率；④ 组合回撤序列与最大回撤。
- **为什么需要**：课程核心知识点「分散化降低风险」「不存在优于前沿的组合」需要用图直观展示；回撤是「风险控制」维度的直观度量。
- **怎么获得/配置**：
  - 绘制：matplotlib 散点图，x 轴 = 年化波动率 `np.sqrt(wᵀΣw)`，y 轴 = 年化收益 `wᵀμ`。
  - 叠加：① 蒙特卡洛随机组合（灰点云，展示「随机组合都在前沿右侧」）；② CML 线（从 `(0, rf)` 出发、过切线组合的直线）；③ 单资产点标注。
  - **回撤计算定义（评审 S-1 补充）**，组合与基准用同一口径：
    ```python
    nav   = (1 + r).cumprod()            # 累计净值
    dd    = nav / nav.cummax() - 1       # 回撤序列（≤ 0）
    max_dd = dd.min()                    # 最大回撤（最负值）
    ```
  - 输出指标表：每组合的 `收益 / 波动 / 夏普 / 最大回撤 / 权重向量`，存 CSV 供汇报 agent 引用。

### 3.3 可选扩展（按时间余量决定，建议至少做一个）

| 扩展 | 是什么 | 数学/依赖 | 演示价值 |
|---|---|---|---|
| **风险平价（Risk Parity）** | 每资产对组合风险贡献相等 | 迭代求解：`RCᵢ = wᵢ(Σw)ᵢ/√(wᵀΣw)`，令所有 RCᵢ 相等；numpy 即可 | 与均值-方差对比「不依赖收益预测」，好讲；方案 A 含债/金天然低风险贡献，效果直观 |
| **Black-Litterman** | 在「市场均衡先验 + 主观观点」下做贝叶斯后验优化 | 逆优化求均衡收益 `π = δ·Σ·w_mkt`，后验 μ 公式；numpy 即可 | 展示「观点如何影响组合」，课程亮点；ETF 先验比个股更合理 |
| **蒙特卡洛模拟** | 随机生成大量权重组合，观察收益-风险分布 | `np.random.dirichlet(alpha)` 生成权重；numpy 即可 | 可视化效果好（灰点云），实现最简单 |

- **依赖**：均为 numpy/pandas，无需新库。⚠️ 需验证：风险平价的迭代收敛（建议上限 1000 次 + 容差 1e-6）。

---

## 4. 集群模式演示设计（jiuwenswarm team 模式）

### 4.1 为什么适合用集群模式演示

1. **流水线天然分阶段**：数据 → 特征 → 优化 → 可视化 → 汇报，每一步职责清晰，天然适合拆 agent。
2. **展示真实协作**：任务看板（task board）+ 消息通信（send_message）+ 共享 `.team/` 工作空间，演示「多 agent 分工与消息流」比单 agent 脚本更有工程说服力。
3. **可并行**：数据采集可按资产分组并行、特征计算与可视化可部分重叠，能体现集群的并发优势。
4. **课程契合**：Project Demo 通常要展示「用多 agent 框架解决实际问题」，portfolio optimization 是最直观的数值型案例。

### 4.2 Agent 角色拆分（建议 5 角色）

| Agent 角色 | 成员名建议 | 分工 | 产出物 | 依赖 |
|---|---|---|---|---|
| **数据采集 agent** | data-collector | 拉取方案 A 行情（yfinance），清洗对齐（含 EEM 跨市场日历），落盘 CSV；缓存优先 | `data/closes_assetclass.csv`、`data/returns_assetclass.csv`（+ 基线 `closes_stocks.csv`） | 无（最先执行） |
| **特征计算 agent** | feature-engineer | 计算年化收益/协方差/无风险利率/基准收益，产出参数 JSON（含资产类别标签） | `data/params.json`（含 mu/Sigma/rf/benchmark/asset_class） | 数据 agent |
| **优化引擎 agent** | optimizer-engine | 跑 GMV / 最大夏普 / 有效前沿（主口径禁做空数值优化）/（可选扩展），产出组合与指标 | `output/portfolios.csv`、`output/frontier.csv` | 特征 agent |
| **可视化 agent** | viz-agent | 画有效前沿、权重条形图（按类别着色）、回撤曲线、相关热力图、双前沿对比图 | `output/*.png`、`output/dashboard.py`（可选 Streamlit） | 优化 agent |
| **汇报 agent** | reporter | 汇总指标与图表，生成结论（跑赢/跑输基准、夏普对比、风险归因）；**新增：按资产类别汇总权重**（如「债券 25%、黄金 15%…」）与 60/40 基准夏普对比 | `output/report.md` | 优化/可视化 agent |

> 也可精简为 3 角色（数据、优化、汇报）——**推荐 5 角色**以充分展示集群协作；leader 负责拆任务、排序、验收。
> 角色注册/创建机制见 §1.4（方式 2 leader 运行时创建为推荐路径，⚠️ 需验证）。

### 4.3 消息流与协作方式

```
team-leader（拆任务、验收）
   │ 创建任务 task-board（data → feature → optimizer → viz → report）
   ▼
data-collector ──send_message(数据就绪, 路径)──► feature-engineer
feature-engineer ──send_message(params.json 就绪)──► optimizer-engine
optimizer-engine ──send_message(组合结果就绪)──► viz-agent ──► reporter
                                                      └──►（可选）dashboard
```

- **任务依赖**：用任务看板的 `blocked_by` 表达前后依赖（优化任务 blocked_by 特征任务），leader 只拆任务不写代码。
- **共享文件**：所有中间产物写 `.team/jiuwen_team_sess_19ffa2c098f_773d5c07c3b4/` 下的 `data/` 与 `output/` 子目录（写前 lock，写完 unlock）。
- **消息内容**：只传「文件路径 + 一句摘要」（如 `data/params.json 已就绪，含 mu/Sigma/rf`），不贴长数据。

### 4.4 演示脚本（现场流程建议）

1. 展示团队看板：5 个任务 + 依赖关系。
2. leader 发出「开始」指令，逐个 agent 认领任务。
3. 依次展示每个 agent 执行时的工具调用与产出文件（强调 send_message 衔接）。
4. 汇总展示图表与汇报 agent 的结论（含按资产类别的权重汇总）。
5. （可选）Streamlit 交互：改风险厌恶系数/资产池，看组合实时变化。

---

## 5. 演示素材

### 5.1 必备可视化图表（5 张）

| 图表 | 内容 | 工具 | 备注 |
|---|---|---|---|
| ① 有效前沿散点图 | 前沿曲线 + 蒙特卡洛灰点云 + CML + GMV/切线组合标注 | matplotlib | Demo 主图，必须最精美 |
| ② 权重条形图 | 最大夏普组合 / GMV / 某目标收益组合的权重分配，**按资产类别着色**（权益/债券/商品/国际） | matplotlib/barh | 展示分散化与类别配置 |
| ③ 回撤曲线 | 组合 vs 基准（**SPY**）的累计净值与最大回撤 | matplotlib/area | 展示风险控制；基准与组合同口径（ETF）对比更公平 |
| ④ 相关性热力图 | 资产收益率相关系数矩阵——**升级为主图**：方案 A 含负相关元素（**GLD-DBC 实测 -0.12，商品-黄金**）与强正相关（SPY-TLT 实测 +0.68，近 5 年股债同向），是全场信息量最大的单张图 | seaborn/heatmap | 解释协方差输入；负相关（GLD-DBC）是方案 A 区别于个股池的核心亮点 |
| ⑤ 双前沿对比图 | **基线 6 只个股 vs 方案 A** 两条有效前沿叠加 | matplotlib | 展示「资产类别分散 vs 个股分散」差异，教学增强项 |

- **中文字体**：⚠️ 需验证 macOS 用 `plt.rcParams["font.sans-serif"] = ["PingFang SC"]`（或 Arial Unicode MS），避免中文乱码。
- 方案 A 中 GLD（贵金属）与 DBC（广义商品：能源/工业金属/农产品）同属通胀对冲，**实测相关性 -0.12（负相关，P2b 实测）**，分别对冲不同通胀来源——可作教学点说明：负相关商品-黄金提供额外分散，避免学员误以为重复配置。

### 5.2 可选交互界面（Streamlit / Dash）

- **是什么**：网页应用，现场可调参数。
- **为什么需要**：Demo 加分项，展示「集群算好的模型可被用户实时交互」。
- **怎么获得/配置**：
  - 推荐 **Streamlit**（更简单）：`streamlit run output/dashboard.py`，控件：`st.sidebar.selectbox`（资产池：方案 A / 基线）、`st.slider`（风险厌恶系数）、`st.checkbox`（禁做空）。
  - 复用集群产物：dashboard 直接读 `data/params.json` 与 `output/frontier.csv`，**不重新计算**，体现「数据/模型即服务」。

### 5.3 演示剧本 / PPT 大纲（预留缓冲）

```
1. 开场（2 min）：问题引入 —— 如何分配资金实现「收益-风险」最优？多 agent 如何协作？
2. 团队看板（2 min）：展示 5 角色与依赖，说明集群模式设计。
3. 数据环节（3 min）：data-collector 拉取 6 只 ETF 5 年行情，展示清洗对齐（含 EEM 跨市场日历）。
4. 优化环节（5 min）：特征计算 → 优化引擎产出 GMV / 切线组合 / 有效前沿。
5. 可视化与结论（5 min）：5 张图 + 汇报 agent 结论（组合夏普 vs 基准、类别权重、60/40 对比）。
6. 交互（2 min，可选）：Streamlit 调参演示；**超时则跳过**（缓冲策略）。
7. 总结（2 min）：集群模式价值 + 扩展展望（风险平价 / Black-Litterman）。
```
> **缓冲策略（评审 S-3）**：剧本核心段合计约 21 分钟，交互段标注「超时则跳过」，为现场延迟预留 3–4 分钟缓冲，确保总时长稳定 ≤ 25 min。

---

## 6. 验收与里程碑

### 6.1 Demo 成功验收标准

| # | 验收项 | 判定标准 |
|---|---|---|
| A1 | 流水线跑通 | 一条指令从数据到报告全自动完成，无人工干预 |
| A2 | 结果正确 | 权重和=1（±1e-6）；GMV 波动率 ≤ 任一单资产波动率（分散化生效）；前沿曲线单调凸；**新增断言：方案 A 相关矩阵含至少一个负相关系数（实测负相关来自 GLD-DBC=-0.12）**（验证协方差结构多样性）；权重校验按所选口径（主口径禁做空）执行 |
| A3 | 数据真实 | 使用真实历史行情（非随机数），缓存可离线复现 |
| A4 | 集群协作可见 | 演示中能清楚看到 ≥4 个 agent 通过任务看板与消息衔接 |
| A5 | 图表齐全 | 5 张必备图 + 指标表完整、无中文乱码 |
| A6 | 结论清晰 | 汇报 agent 输出：组合夏普 vs 基准夏普（SPY）、最大回撤、最优权重；**新增：按资产类别的权重汇总 + 与 60/40（股/债）基准组合的夏普对比** |
| A7 | 现场稳健 | 断网可跑（本地缓存）；总演示时长 ≤ 25 min；一次通过无报错 |

### 6.2 分阶段时间规划（建议 5 阶段，约 2 周 / 8–12 个工作日）

| 阶段 | 内容 | 产出 | 时长 |
|---|---|---|---|
| P1 环境搭建 | 建虚拟环境、装依赖（含 scikit-learn）、jiuwenswarm team 配置与 5 角色注册机制验证、yfinance 连通性实测 | 环境可用性报告 | 1–2 天 |
| P2 数据管道 | 方案 A 数据采集/清洗/对齐（含 EEM 跨市场日历与收益方向核验）/缓存 + 参数计算脚本 | `data/`、`params.json` | 1–2 天 |
| P3 核心算法 | GMV/切线组合/有效前沿（禁做空数值优化主口径 + 解析解对照），加单测断言；**新增里程碑检查：用 §5 验证代码实测前沿形状与相关矩阵，核对方案 A 预期（负相关存在 GLD-DBC=-0.12、GMV/切线分离清晰）** | `output/portfolios.csv`、frontier.csv | 2–3 天 |
| P4 集群编排 | 拆 5 个 agent、定义任务依赖与消息流、跑通全链路 | 集群流水线脚本 | 2–3 天 |
| P5 可视化与彩排 | 5 张图 + Streamlit + 汇报报告（含类别权重与 60/40 对比）+ 全流程彩排 2 次 | 图表、dashboard、report.md | 2–3 天 |

> 里程碑检查点：P2 结束（数据真实可用、EEM/TLT/DBC 收益方向核验完成）→ P3 结束（优化结果正确、前沿形状与方案 A 预期核对通过）→ P4 结束（集群全链路跑通）→ P5 结束（彩排通过，对照 A1–A7）。

### 6.3 常见坑与备选方案

| # | 坑 | 现象 | 备选/规避方案 |
|---|---|---|---|
| 1 | yfinance 网络不可达/限流 | 拉取超时、报 429 | 本地 CSV 缓存为主；换 akshare；或演示前预下载 |
| 2 | 协方差矩阵奇异/不正定 | scipy 优化报错、权重爆炸 | 样本数不足→加长历史窗口；用 Ledoit-Wolf 收缩估计（`sklearn.covariance.LedoitWolf`，scikit-learn 已装）⚠️ 需验证 |
| 3 | 权重和为 1 约束被破坏 | 优化结果权重和 ≠ 1 | 显式加 equality 约束 + 结果断言；数值容差 1e-6 |
| 4 | 负权重（做空） | 出现大额负权重、组合波动异常 | 主演示口径默认 `bounds=(0,1)` 禁做空；解析解出现负权重属正常（允许做空情形），按 §3.1 口径说明，不并列混淆 |
| 5 | 日期不对齐（含 EEM 跨市场休市） | 协方差矩阵用错时间窗、结果失真 | 先 `ffill().dropna()` 再算；脚本加时间窗断言（目标 ≥ 750 交易日） |
| 6 | 有效前沿非凸/锯齿/两端无解 | 扫描点太少、SLSQP 局部最优、端点报错 | 扫描 50–100 点、两端留 5% 余量、try/except 跳过不可行点、warm start（§3.1） |
| 7 | matplotlib 中文乱码 | 图上中文变方框 | 指定 PingFang SC / Noto Sans CJK 字体 |
| 8 | 汇报 agent 数据不一致 | 不同 agent 用了不同版本数据 | 所有 agent 只读共享 `data/` 缓存；写文件前 lock |
| 9 | 演示现场模型 API 不稳 | agent 卡顿、超时 | 现场演示用确定性脚本兜底（集群跑通后预生成全部产物）；备一份录屏 |
| 10 | EEM/TLT/DBC 近 5 年负收益（方案 A 特有） | 单资产年化收益为负、学员困惑 | 开发期实测收益方向并备好话术：「组合优化目标是风险调整后收益」；必要时演示时强调 60/40 等配置的分散价值 |

---

## 7. 附录：命令速查

```bash
# 环境（详见 local-env-setup-uv.md）
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install numpy pandas scipy matplotlib seaborn yfinance akshare streamlit jupyter scikit-learn
uv pip freeze > requirements.txt

# 数据（开发期验证连通性）
python -c "import yfinance as yf; d=yf.download('SPY',period='5d'); print(d.tail(2))"

# 运行集群 demo（示意；实际以 jiuwenswarm 团队启动方式为准）⚠️ 需验证
jiuwenswarm team start --name jiuwen_team   # 具体 CLI 以安装版本 help 为准

# 图表与交互
python scripts/viz.py
streamlit run output/dashboard.py
```

---

### 文档维护记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-13 | 初版：六大维度完整准备清单 | portfolio-planner |
| v1.1 | 2026-08-13 | ①资产池切换方案 A（SPY/IWM/TLT/GLD/EEM/DBC），基线个股保留对比；②首轮评审 I-1（5 角色注册机制）/I-2（解析解与数值解约束口径）/I-3（scikit-learn 入清单）；③首轮评审 S-1（回撤定义）/S-2（工期统一 8–12 工作日）/S-3（剧本缓冲）/S-4（前沿扫描边界）/S-5（uv 安装兜底）/S-6（截止日动态化）；④吸收资产池评审针对方案 A 的意见（EEM 弱收益核验入 P2、GLD/DBC 差异说明、前沿形状验证入 P3 里程碑）；图表升级至 5 张（热力图主图、类别着色权重图、双前沿对比图、基准改 SPY）；验收 A2/A6 增强 | portfolio-planner |
| v1.2 | 2026-08-13 | 回写 P2b/P3 实测相关性：GLD-DBC=-0.12（负相关，替代预估值 0.3–0.4）、SPY-TLT=+0.68（正相关，更正「负相关出现在股债」预判）；同步更新 §0 资产池描述、§2.1 协方差结构说明、§5.1 图表④与 GLD/DBC 说明、§6.1 A2 断言与 §6.2 P3 里程碑表述 | portfolio-planner |
