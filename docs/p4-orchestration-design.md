# 集群编排设计方案（P4a）— 5-Agent Portfolio Optimization Demo

> 定位：P4 核心、demo 的灵魂展示——把已跑通的工程脚本（fetch_data / optimizer / viz）编排为 **5-agent 集群协作流水线**，在 jiuwenswarm team 模式（任务看板 + send_message + 共享 .team 工作空间）上现场演示「数据采集 → 特征计算 → 组合优化 → 可视化 → 汇报」全链路。
> 依据：准备清单 v1.2（§4 集群演示设计）、工程产物（scripts/fetch_data.py、scripts/optimizer.py、scripts/viz.py、data/params.json、output/frontier*.csv）。
> 文档版本：**v1.1**（2026-08-13）｜ 作者：portfolio-planner
> **v1.1 变更项**：①吸收评审意见 I-1（T1 补充基线个股拉取）/I-2（T3 输入补 features.json 并明确依赖语义）/S-1（§4.1 目录同步方案收敛为唯一方案）/S-2（params.json 与 params_assetclass.json 关系说明）/S-3（DAG 图 T5 双入边改清晰）/S-4（M4 措辞与 T5 依赖一致）；②落地检查清单更新（5 演示角色成员已 spawn，B-1 阻塞项由 Leader 决策解决）。变更明细见文末维护记录。

---

## 0. 设计总览（先看这里）

```
team-leader（拆任务、验收，不写代码）
   │ 创建 5 个任务（task board，blocked_by 表达依赖）
   ▼
┌─────────────┐   ┌─────────────────┐   ┌──────────────────┐   ┌─────────────┐   ┌──────────┐
│ data-collector│──►│ feature-engineer │──►│ optimizer-engine │──►│  viz-agent   │──►│ reporter │
│ 拉取+清洗+缓存 │   │ 算 mu/Sigma/rf  │   │ GMV+切线+前沿     │   │ 5 张图+dashboard│  │ 指标+结论 │
└─────────────┘   └─────────────────┘   └──────────────────┘   └─────────────┘   └──────────┘
   对接 fetch_data.py     消费 data/ 缓存       对接 optimizer.py       对接 viz.py         汇总 output/
```

**核心设计原则**：
1. **脚本即任务实现**：每个 agent 的任务 = 调用一个（或一组）已测脚本 + 产出约定文件；agent 负责「决策与衔接」（读什么、跑哪个命令、结果传给谁），不重写算法；
2. **产物即接口**：agent 间通过 `.team/` 下的 `data/` 与 `output/` 文件解耦，消息只传「路径 + 摘要」；
3. **缓存优先**：data-collector 默认读缓存（断网可演示），`--refresh` 才联网；
4. **写锁保护**：共享文件写入前 lock、写完 unlock，避免多 agent 互相覆盖。

---

## 1. 5 角色任务定义

> 每个角色给出：任务内容 / 输入文件 / 输出文件 / 对接的现成脚本与命令。

### 1.1 data-collector（数据采集）

| 项 | 内容 |
|---|---|
| 任务内容 | ①拉取方案 A 六只 ETF 近 5 年日线（SPY/IWM/TLT/GLD/EEM/DBC），清洗对齐（ffill + dropna），算收益率与年化参数，落盘缓存；**缓存优先，--refresh 才联网**；同时拉取 rf（^IRX）与基准（SPY）；②**同时拉取基线六只个股**（AAPL/MSFT/GOOGL/AMZN/JPM/XOM，复用 fetch_data.py `--name stocks`），产出基线缓存（评审 I-1） |
| 输入 | 无（联网或已有缓存）；ticker 列表由任务描述给定 |
| 输出 | 方案 A：`data/closes_assetclass.csv`、`data/returns_assetclass.csv`、`data/params_assetclass.json`、`data/params.json`（正式参数文件，含 rf/benchmark/asset_class）；**基线：`data/closes_stocks.csv`、`data/returns_stocks.csv`、`data/params_stocks.json`**（供 T3 基线运行与 T4 双前沿对比） |
| 对接脚本 | 方案 A：`python scripts/fetch_data.py --name assetclass --tickers SPY,IWM,TLT,GLD,EEM,DBC --years 5 --rf --benchmark SPY --params-out data/params.json`；**基线：`python scripts/fetch_data.py --name stocks --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5`**（评审 I-1） |
| 关键校验 | 数据质量报告全绿：closes_NaN=0、returns_NaN=0、交易日 ≥ 750、rf 断言 0<rf<0.15（脚本已内置断言，失败非零退出）；两套资产池均需校验通过 |

### 1.2 feature-engineer（特征计算）

| 项 | 内容 |
|---|---|
| 任务内容 | 校验 params.json 完整性（mu/Sigma/rf/benchmark/asset_class 齐全），补充派生特征：相关系数矩阵、按资产类别的收益/波动汇总、60/40 基准组合参数（用于汇报 agent 对比），产出特征摘要 JSON |
| 输入 | `data/params.json`（data-collector 产出）、`data/returns_assetclass.csv` |
| 输出 | `data/features.json`（派生特征：corr、asset_class_summary、benchmark_6040 等） |
| 对接脚本 | 无独立脚本；复用 `fetch_data.py` 已产出的 params + 一段派生特征计算（可沉淀为 `scripts/features.py`，P2b 后补充，⚠️ 需验证） |
| 关键校验 | 相关矩阵含至少一个负相关系数（验收 A2 断言）；asset_class 标签齐全 |

> 说明：P2b 的 fetch_data.py 已把 rf/benchmark/asset_class 全部写入 params.json，feature-engineer 的增量价值是**派生特征**（相关性、类别汇总、60/40 基准）——这部分建议沉淀为 `scripts/features.py`（小脚本，由 dev-engineer 在 P2b 收尾时补上，⚠️ 需验证）。

### 1.3 optimizer-engine（优化引擎）

| 项 | 内容 |
|---|---|
| 任务内容 | 运行马科维茨优化：GMV（数值禁做空主口径 + 解析对照）、切线组合（同口径）、有效前沿扫描 60 点（5% 余量/warm start/try-except），输出组合指标表与前沿 CSV；对方案 A 与基线分别运行 |
| 输入 | `data/params.json`（方案 A）、`data/params_stocks.json`（基线）、`data/returns_assetclass.csv`、`data/returns_stocks.csv`、**`data/features.json`（供优化前相关矩阵校验与 60/40 基准对比参数，评审 I-2）** |
| 输出 | `output/portfolios.csv`（方案 A 主输出）、`output/portfolios_stocks.csv`、`output/frontier.csv`、`output/frontier_stocks.csv` |
| 对接脚本 | `python scripts/optimizer.py --params data/params.json --returns data/returns_assetclass.csv --tag assetclass` 及 `--tag stocks` 对应命令 |
| 关键校验 | 权重和=1（±1e-6）、GMV 波动率 ≤ 任一单资产、前沿凸性/弯曲验证（脚本已打印 P3 里程碑摘要）；优化前先读 features.json 校验相关矩阵含负相关（GLD-DBC 实测 -0.12）；主口径为数值禁做空，解析解仅对照（评审 I-2 口径） |

### 1.4 viz-agent（可视化）

| 项 | 内容 |
|---|---|
| 任务内容 | 消费 output/ 与 data/ 产物，输出 5 张必备图 + 可选 Streamlit dashboard：① 有效前沿散点（+蒙特卡洛云+CML+GMV/切线标注）；② 按资产类别着色的权重条形图；③ 回撤曲线（组合 vs SPY 基准）；④ 相关性热力图（主图，含负相关）；⑤ 双前沿对比（基线个股 vs 方案 A） |
| 输入 | `output/frontier.csv`、`output/frontier_stocks.csv`、`output/portfolios.csv`、`data/params.json`、`data/returns_*.csv` |
| 输出 | `output/frontier.png`、`output/weights.png`、`output/drawdown.png`、`output/corr_heatmap.png`、`output/frontier_compare.png`、`output/dashboard.py`（可选） |
| 对接脚本 | `python scripts/viz.py`（P5 dev-engineer 产出，⚠️ 需验证：图表文件命名与 dashboard 入口以实际实现为准） |
| 关键校验 | 5 张图全部生成且无中文乱码（PingFang SC）；热力图含负相关可见 |

### 1.5 reporter（汇报）

| 项 | 内容 |
|---|---|
| 任务内容 | 汇总全部产物，生成最终结论报告：组合夏普 vs 基准（SPY）夏普、最大回撤、最优权重、**按资产类别的权重汇总**、**60/40（股/债）基准组合夏普对比**、风险归因结论 |
| 输入 | `output/portfolios.csv`、`output/frontier*.csv`、`data/params.json`、`data/features.json`、`output/*.png` |
| 输出 | `output/report.md`（最终演示报告，供现场展示） |
| 对接脚本 | 无独立脚本；reporter 读取 CSV/JSON 汇总成 Markdown（可沉淀为 `scripts/report.py`，⚠️ 需验证） |
| 关键校验 | 结论完整覆盖 A6 验收项（夏普对比、最大回撤、类别权重、60/40 对比） |

---

## 2. 任务 DAG 与依赖

### 2.1 依赖关系（blocked_by）

| 任务 | blocked_by（前置） | 说明 |
|---|---|---|
| T1 data-collector | 无 | 最先执行（联网或读缓存） |
| T2 feature-engineer | T1 | 需要 params.json / returns 就绪 |
| T3 optimizer-engine | T2（严格） | **依赖 T2 且消费 `data/features.json`**（优化前校验相关矩阵含负相关、读取 60/40 基准参数供对比），保证派生特征一致（评审 I-2）；同时需要 T1 产出的 params/returns |
| T4 viz-agent | T3 | 需要 frontier/portfolios 就绪 |
| T5 reporter | T3 + T4 | 需要优化结果与图表就绪（reporter 读 CSV 为主，图表用于报告引用） |

```
T1 ──► T2 ──► T3 ──► T4 ──┐
                          ├──► T5   （T5 blocked_by T3 + T4，T4 完成后才开工）
                          └──►（T3 完成后 T5 可开始读取 portfolios.csv 作预汇总）
```
> DAG 说明（评审 S-3）：T5 依赖 T3 与 T4 两个前置；实际执行中 T5 在 T3 完成后即可开始读取优化结果做预汇总，但**正式产出 report.md 须等 T4 图表就绪后**（M5 为开工触发点，见 §3）。

### 2.2 与 jiuwenswarm 任务看板对应

- leader 在任务看板创建 T1–T5 五个任务，每个任务 `blocked_by` 按上表设置（如 T3 blocked_by T2）；
- 指派策略：**先指派 T1**，T2–T5 保持 pending；T1 完成后其下游自动解锁（框架在依赖解除后通知对应成员）；
- 认领模式：teammate 以 `build_mode` 自主认领（与当前团队实测流程一致）；
- 演示效果：看板上的「blocked_by 链条」本身就是一张可视化 DAG，现场可展示任务如何逐级解锁、接力推进。

---

## 3. 消息流设计（send_message 衔接）

> 约定：所有 agent 间消息只传「**产物路径 + 一句话摘要**」，不贴数据正文（硬约束：≤2000 字符）；接收方通过 read_file 读取具体内容。

| 衔接点 | 发送方 → 接收方 | 消息内容（示意） |
|---|---|---|
| M1 | data-collector → feature-engineer | `data/params.json 已就绪（SPY/IWM/TLT/GLD/EEM/DBC，1254 交易日，rf=3.71%，含 asset_class），请开始特征计算` |
| M2 | feature-engineer → optimizer-engine | `data/features.json 已就绪（含 corr/类别汇总/60-40 基准），params 为 data/params.json，请开始优化` |
| M3 | optimizer-engine → viz-agent | `output/frontier.csv + portfolios.csv 已就绪（方案 A 59 点前沿，切线夏普 0.999），请出图` |
| M4 | optimizer-engine → reporter | `output/portfolios.csv 已就绪（GMV/切线指标），frontier_stocks.csv 为基线；产出已就绪（待 T4 完成后正式汇总，评审 S-4）` |
| M5 | viz-agent → reporter | `output/*.png 五张图已生成（含双前沿对比），dashboard.py 可选；报告可引用图表，可开始正式汇总（M5 为 T5 开工触发点）` |
| M6 | reporter → team-leader | `output/report.md 已就绪（夏普对比/最大回撤/类别权重/60-40 结论），demo 可交付` |

**教学点**：每个衔接点演示「agent 只传路径+摘要、不搬运数据」——体现集群模式下上下文解耦与文件共享协作的工程价值。

---

## 4. 共享产物约定

### 4.1 目录布局（.team/ 下）

```
.team/jiuwen_team_sess_19ffa2c098f_773d5c07c3b4/
├── p4-orchestration-design.md      # 本文档
├── data/                           # 数据缓存（只读为主，写入需 lock）
│   ├── closes_assetclass.csv / returns_assetclass.csv / params.json
│   ├── closes_stocks.csv / returns_stocks.csv / params_stocks.json
│   └── features.json               # feature-engineer 产出
└── output/                         # 优化与可视化产物（写入需 lock）
    ├── portfolios.csv / frontier.csv / frontier_stocks.csv
    ├── frontier.png / weights.png / drawdown.png / corr_heatmap.png / frontier_compare.png
    ├── dashboard.py（可选）
    └── report.md
```

> 说明（评审 S-1 收敛为唯一方案）：演示阶段以 `.team/.../data/`、`.team/.../output/` 为**唯一共享真相源**，三个脚本（fetch_data/optimizer/viz）均通过 `--data-dir` / `--output-dir` 参数直接指向该目录（fetch_data.py 与 optimizer.py 已支持，viz.py 需同步支持，⚠️ 需验证）；不再采用符号链接方案（列为可选备选）。项目 git 仓库内的 `data/`、`output/` 与 `.team/` 共享目录二选一作为工作目录，避免双份数据不一致；建议统一以 `.team/` 共享目录为现场工作目录，git 仓库内保留脚本与文档。
>
> **params 双文件关系（评审 S-2）**：`data/params_assetclass.json` 为带方案标识（`--name assetclass`）的**原始输出副本**；`data/params.json` 为**统一正式参数文件**（由 `--params-out data/params.json` 生成，内容与方案 A 副本一致）——**P3 优化器消费的是 `params.json`（主文件）**，`params_assetclass.json` 用于按方案标识追溯与基线（`params_stocks.json`）对比；演示与验收均以 `params.json` 为准。

### 4.2 写锁约定

- **写前 lock**：任何 agent 要写入 `data/` 或 `output/` 下文件，先 `workspace_meta(action="lock", path=...)`；
- **写完 unlock**：写入完成后立即 `unlock`（默认 300s 超时自动释放）；
- **只读不锁**：纯读取（read_file / 读 CSV）无需 lock；
- **冲突规避**：各 agent 写入不同文件为主（data-collector 写 data/、optimizer 写 output/），同文件并发写仅发生在「data-collector 刷新缓存 vs 下游读取」——约定 **T1 完成前下游不启动**（blocked_by 已保证），无需额外协调。

### 4.3 只读缓存约定

- data-collector **默认读缓存**：`closes_assetclass.csv` 存在即用，`--refresh` 才联网——现场断网可演示（准备清单坑 #1）；
- 下游 agent（feature/optimizer/viz/reporter）**只读** `data/` 与 `output/`，不修改上游产物；
- 若需重新生成（数据更新），由 data-collector 以 `--refresh` 重跑并**串行**通知下游重跑（不并行覆盖）。

---

## 5. 落地方式建议与推荐

三种方式对比：

| 维度 | 方式 1：当前团队 spawn 演示角色 | 方式 2：独立演示团队配置 | 方式 3：确定性编排脚本 |
|---|---|---|---|
| 做法 | 在当前团队任务看板创建 T1–T5，teammate 认领执行；角色=任务认领者+职责 | 在 config.yaml 新建 `modes.team.<demo_team>` 段，预注册 5 角色（member_name/persona），重启后独立团队演示 | 一个 `scripts/demo_pipeline.sh` 顺序调用 fetch→optimize→viz→report，串起全链路 |
| 成本 | **低**（零新增配置，复用现有 inprocess+build_mode 流程） | **中高**（需写配置、重启、实测 schema，⚠️ 需验证） | **最低**（一个脚本） |
| 演示效果 | **好**：真实多 agent 看板 + 消息流 + 文件接力，展示集群协作本质 | **最好**：独立团队、角色名即 5 角色、看板干净无干扰 | **差**：只是脚本流水线，没有 agent 协作画面（最多打印步骤） |
| 现场风险 | **低**（机制已实测；风险=看板混有其他任务，可提前清理/聚焦演示任务） | **中**（新团队配置未实测、重启可能影响当前会话） | **最低**（确定性，无 LLM 不确定性；但失去「集群」卖点） |
| 教学契合 | 展示「leader 拆任务、teammate 认领、依赖解锁」真实协作 | 展示「独立团队从零配置」的完整形态 | 仅作兜底 |

**推荐：方式 1 为主 + 方式 3 兜底**。

理由：
1. **方式 1 成本最低、风险最低、演示效果达标**：团队已 spawn 5 个演示角色成员（data-collector / feature-engineer / optimizer-engine / viz-agent / reporter，评审 B-1 阻塞项已由 Leader 决策解决——扩员），每个角色即一个 teammate，可在任务看板认领 T1–T5，M1–M6 消息流为真实成员间协作，满足验收 A4（≥4 agent 协作可见）；
2. **方式 3 作为现场兜底**：若现场 LLM API 不稳/网络异常（准备清单坑 #9），用预生成产物 + `demo_pipeline.sh` 确定性重跑，保证 demo 不翻车；产物预生成后断网也能演示；
3. **方式 2 列为可选进阶**：若课程要求「独立演示团队」形态，可后续补做——但需提前验证 config.yaml `agents` 段 teammate 注册 schema（评审 I-1 的 ⚠️ 项），不阻塞主路径。

**落地检查清单（方式 1，v1.1 更新）**：
- [x] **5 个演示角色成员已 spawn 就绪**（data-collector / feature-engineer / optimizer-engine / viz-agent / reporter，2026-08-13 团队名册确认）；
- [ ] leader 创建 T1–T5 任务并设置 blocked_by（T3 blocked_by T2 且消费 features.json，T5 blocked_by T3+T4）；
- [ ] 确认 5 个任务在同一团队看板可见、命名含角色前缀（如 `demo:data-collector`）便于现场聚焦；
- [ ] 预生成全部产物（output/report.md 等）作为兜底副本；
- [ ] 三个脚本（fetch_data/optimizer/viz）均确认支持 `--data-dir`/`--output-dir` 指向 .team 共享目录（S-1，viz.py ⚠️ 需验证）；
- [ ] 现场演示前 1 次全链路彩排（对照 §6 脚本）。

---

## 6. 现场演示流程（含教学点）

> 总时长建议 ≤ 20 min（核心 15 min + 缓冲 5 min，对照准备清单 S-3）。

| 步骤 | 时长 | 动作 | 教学点 |
|---|---|---|---|
| 1. 开场 | 1 min | 展示团队看板：5 任务 + blocked_by 依赖链 | 「流水线天然分阶段，适合多 agent 编排」 |
| 2. 拆任务 | 1 min | leader 讲解任务划分逻辑（数据/特征/优化/可视化/汇报） | 「leader 只拆任务不写代码，分工即架构」 |
| 3. T1 data-collector | 3 min | 认领任务，运行 fetch_data.py（读缓存或 --refresh），展示数据质量报告 | 「缓存优先、断网可演示」「数据清洗对齐（EEM 跨市场日历）」 |
| 4. M1 衔接 | 0.5 min | 展示 send_message 消息（路径+摘要） | 「agent 间只传路径不搬数据」 |
| 5. T2 feature-engineer | 1.5 min | 生成 features.json，展示相关矩阵含负相关（DBC-GLD -0.12） | 「协方差结构多样性是方案 A 的核心」 |
| 6. T3 optimizer-engine | 2.5 min | 运行 optimizer.py，展示 GMV/切线/前沿，P3 里程碑摘要 | 「禁做空主口径 vs 解析对照（I-2）」「分散化降风险」 |
| 7. M3/M4 衔接 | 0.5 min | 展示消息流转 | 「依赖解锁、接力推进」 |
| 8. T4 viz-agent | 2 min | 运行 viz.py，展示 5 张图（重点热力图 + 双前沿对比） | 「资产类别分散 vs 个股分散」「负相关资产价值」 |
| 9. T5 reporter | 2 min | 展示 report.md：夏普对比、最大回撤、类别权重、60/40 对比 | 「结论闭环：组合是否跑赢基准、风险收益权衡」 |
| 10. 总结 | 1 min | 回顾 5 角色接力全链路 + 可选扩展展望（风险平价/BL） | 「多 agent 集群 = 工程化交付的组合优化」 |
| 11. 缓冲 | ≤5 min | 交互演示（dashboard 调参）/答疑 | 超时则跳过（S-3） |

**现场风险预案**：
- LLM 卡顿 → 切方式 3 确定性脚本重跑（产物已预生成）；
- 网络断 → data-collector 读缓存，全程离线可跑；
- 某 agent 任务失败 → leader 在看板重派/由备用成员认领（角色职责与脚本绑定，换人不换逻辑）。

---

### 文档维护记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-13 | 初版：5 角色任务定义 / DAG / 消息流 / 共享产物约定 / 落地方式推荐 / 现场演示流程 | portfolio-planner |
| v1.1 | 2026-08-13 | ①吸收评审 I-1（T1 补充基线个股拉取）/I-2（T3 输入补 features.json、依赖语义明确）/S-1（§4.1 目录方案收敛为 --data-dir/--output-dir 唯一方案）/S-2（params.json 与 params_assetclass.json 关系说明）/S-3（DAG 图 T5 双入边改清晰）/S-4（M4 措辞与 T5 依赖一致）；②落地检查清单更新（5 演示角色成员已 spawn，B-1 阻塞项由 Leader 决策解决） | portfolio-planner |
