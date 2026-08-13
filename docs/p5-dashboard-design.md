# 交互式展示网页设计方案（P5b）— Portfolio Optimization Demo 核心可视化交付物

> 定位：把第二层可视化从「静态 PNG + 基础 Streamlit dashboard」**升级为可交互展示网页**，作为 demo 的核心可视化交付物（用户已确认方向）。
> 依据：准备清单 v1.2（§5 演示素材）、编排方案 v1.1（viz-agent 产出 dashboard）、现有产物（output/dashboard.py 单页版、data/features.json、output/extensions_summary.csv、output/mc_points.csv、output/frontier*.csv、output/portfolios*.csv）。
> 文档版本：v1.0（2026-08-13）｜ 作者：portfolio-planner

---

## 0. 设计总览（先看这里）

| 项 | 决策 |
|---|---|
| 技术选型 | **Streamlit 多页面应用（`app/` 目录 + 侧边栏导航）+ plotly 交互图表**（升级现有 output/dashboard.py 单页版） |
| 页面数量 | 6 页：① 总览 ② 有效前沿（交互）③ 权重分布 ④ 净值与回撤 ⑤ 相关性热力图 ⑥ 扩展算法对比 |
| 数据策略 | **复用 P2/P3/P3x 产物（data/params.json、features.json、output/*.csv），不重算**；仅有效前沿页按 γ 轻量实时求解（复用 dashboard.py 已实现的 solve_utility） |
| 静态图 | **保留**（5 张 PNG 供 report.md/PPT 引用）；网页为交互主交付物，两者并存 |
| 对现有 dashboard.py | **替换**：将单页升级为多页应用，`output/dashboard.py` 退役，新入口 `app/Home.py`（或保留作单页精简版，见 §4.4） |

---

## 1. 定位与形态

### 1.1 网页在 demo 中的角色

- **现场演示第二层展示**：第一层 = 集群流水线跑通（5 agent 协作出产物）；第二层 = 进入网页交互浏览（总览指标 → 前沿调参 → 权重 → 回撤 → 热力图 → 扩展对比），把「算好的模型」变成「可玩的演示」；
- **课后可自行浏览/部署**：学生课后 `streamlit run app/Home.py` 本地打开，或部署到分享平台（§4.3）；
- **课程叙事闭环**：网页把散落的 CSV/PNG 组装成「一个产品的视角」，体现「数据/模型即服务」的工程理念（编排方案 §1.4 教学点）。

### 1.2 技术选型与理由（推荐 Streamlit 多页 + plotly）

| 备选 | 理由 | 结论 |
|---|---|---|
| **Streamlit 多页 + plotly（推荐）** | ① Python 原生，与现有 scripts/ 无缝衔接；② 已有单页 dashboard.py 基础（solve_utility 等可复用）；③ 课程演示一键 `streamlit run`，无需前端工程链；④ plotly 提供悬停/缩放/框选交互，图表质感远超 matplotlib | ✅ 主选 |
| Dash（plotly 官方） | 交互能力同 plotly，但回调模型（@callback）比 Streamlit 的脚本重跑模型复杂，学习曲线陡 | 备选，不推荐 |
| Vue/React + FastAPI | 需要前端工程链与打包，超出课程 demo 范畴 | 不采用 |
| Panel（HoloViz） | 可作 Streamlit 平替，但生态与教程不如 Streamlit 普及 | 不采用 |

> 若用户后续有**公网部署**需求：Streamlit Community Cloud / Hugging Face Spaces 免费托管，或自有服务器 `streamlit run` + Nginx 反代；文档 §4.3 给出两种方式（⚠️ 需验证：分享平台对免费额度与 Python 版本限制）。

### 1.3 静态 5 张图是否保留

- **保留**：① report.md 与 PPT 引用静态图最稳妥（评审/存档用）；② 断网/网页故障时静态图是兜底展示；③ 集群演示第一层「viz-agent 出图」本身就要展示 PNG 产物。
- **关系**：静态图为「产出物存档 + 文档引用」，网页为「交互主交付物」；两者数据同源（output/ 与 data/），内容一致不冲突。

---

## 2. 页面结构（信息架构）— 6 页

```
app/
├── Home.py                    # 入口：项目简介 + 页面导航 + 数据版本说明
└── pages/
    ├── 1_总览.py              # 关键指标卡片（组合 vs 基准）
    ├── 2_有效前沿.py          # 交互前沿（γ 滑块 / 方案切换）
    ├── 3_权重分布.py          # 组合权重条形图（按类别着色）
    ├── 4_净值与回撤.py        # 净值曲线 + 回撤曲线（时间范围选择）
    ├── 5_相关性热力图.py      # plotly 热力图（悬停数值 + 负相关标注）
    └── 6_扩展算法对比.py      # 风险平价 / BL / 蒙特卡洛 vs 均值-方差
```

> Streamlit 多页约定：`pages/` 目录下文件名数字前缀控制侧边栏导航顺序；`Home.py` 为默认入口。每页顶部统一 `st.set_page_config(layout="wide")` 与中文标题。

---

## 3. 交互设计（每页控件 / 联动 / 数据来源）

### ① 总览（关键指标卡片）

| 项 | 内容 |
|---|---|
| 控件 | 无（或资产池 selectbox：方案 A / 基线，默认方案 A） |
| 展示 | 指标卡片行（st.metric）：GMV / 切线组合 / 基准 SPY / 60-40 基准 的 收益、波动、夏普、最大回撤（4 列 × 若干行）；底部加「结论摘要」引用 report.md 关键行（如「切线夏普 0.999 > 基准 SPY 0.592」） |
| 数据来源 | `output/portfolios.csv`（GMV/切线指标）、`output/report.md`（结论）、`data/features.json`（benchmark_6040：ret/vol/sharpe）、`data/params.json`（rf） |
| 联动 | 切换资产池 → 卡片数据整体切换（portfolios.csv ↔ portfolios_stocks.csv） |

### ② 有效前沿（核心交互页）

| 项 | 内容 |
|---|---|
| 控件 | ① 资产池 selectbox（方案 A / 基线）；② 风险厌恶系数 γ slider（0.5–20，步长 0.5，默认 5）；③ 禁做空 checkbox（默认 True）；④（可选）目标收益 slider 替代 γ（二选一模式切换） |
| 展示 | plotly 散点图：有效前沿线（from frontier.csv）+ 蒙特卡洛灰点云（from mc_points.csv）+ CML 线（rf 起）+ 当前 γ 组合星标 + 单资产菱形点；图下方三个指标卡（当前组合 ret/vol/sharpe） |
| 数据来源 | `output/frontier.csv` / `frontier_stocks.csv`（前沿）、`output/mc_points.csv`（蒙特卡洛云，方案 A 6000 样本）、`data/params.json` / `params_stocks.json`（mu/Sigma/rf）、`data/features.json`（asset_class 供着色） |
| 联动 | γ / 禁做空 / 资产池任一变化 → **实时求解** `max wᵀμ − 0.5γ·wᵀΣw`（复用 dashboard.py 的 solve_utility，scipy SLSQP，轻量 <0.1s）→ 星标位置、指标卡、CML 斜率同步更新 |
| 教学点 | 拖动 γ 看组合沿前沿移动：γ 小→右上方高收益高风险，γ 大→左下方保守；对比「允许做空」时前沿扩展 |

### ③ 权重分布

| 项 | 内容 |
|---|---|
| 控件 | ① 组合 selectbox（GMV 数值 / 切线数值 / 自定义 γ（联动②页当前 γ））；② 资产池 selectbox；③ 展示模式 toggle（明细条形图 / 按类别汇总条形图） |
| 展示 | plotly 横向条形图：每资产权重（按 asset_class 着色，图例=类别）；下方按类别汇总（equity-us/bond/gold/equity-em/commodity 堆叠） |
| 数据来源 | `output/portfolios.csv`（GMV/切线权重列 w_*）、②页 γ 实时解（自定义）、`data/features.json`（asset_class 映射） |
| 联动 | 组合选择 → 权重向量切换；类别着色由 asset_class 映射驱动；自定义 γ 与②页共享 session_state（跨页联动） |

### ④ 净值与回撤

| 项 | 内容 |
|---|---|
| 控件 | ① 时间范围 date_input（默认 2021-08-13 ~ 2026-08-12，即数据窗口）；② 组合 selectbox（GMV / 切线 / 基准 SPY / 60-40）；③ 展示模式 toggle（净值 / 回撤 / 双图） |
| 展示 | plotly 双轴或双子图：累计净值 `nav=(1+r).cumprod()`（组合 vs SPY vs 60-40 三条线）+ 回撤 `dd=nav/nav.cummax()-1` 填充区域 |
| 数据来源 | `data/returns_assetclass.csv`（日收益率，组合权重 → 组合日收益 `returns @ w`）、`data/returns_stocks.csv`（基线）、`data/params.json`（SPY 基准列）与 `features.json`（benchmark_6040 权重构造 60-40 净值） |
| 联动 | 时间范围 → 三线同步裁剪；组合选择 → 组合线切换；回撤最大值自动标注（plotly annotation） |
| 教学点 | 直观对比：切线组合 vs SPY 的回撤深度与恢复速度；60-40 的平滑性 |

### ⑤ 相关性热力图

| 项 | 内容 |
|---|---|
| 控件 | 资产池 selectbox（方案 A / 基线）；(可选) 排序 toggle（原始顺序 / 层次聚类顺序） |
| 展示 | plotly heatmap（或 imshow）：6×6 相关系数矩阵，**悬停显示数值**；**负相关对（EEM-DBC = -0.12）红框/星标标注**，并加 caption「负相关 = 分散化增量来源」 |
| 数据来源 | `data/features.json` → `corr`（方案 A 已算好）；基线用 `params_stocks.json` 的 sigma 现场推导 corr（轻量，pandas corr） |
| 联动 | 资产池切换 → 矩阵整体切换；悬停数值、负相关标注自动更新 |
| 教学点 | 强调「方案 A 含负相关（EEM-DBC），SPY-TLT 实测 +0.68 正相关（近 5 年股债同向）」——v1.2 实测口径，作为全场信息量最大单图 |

### ⑥ 扩展算法对比

| 项 | 内容 |
|---|---|
| 控件 | ① 对比维度 selectbox（指标表 / 收益-风险散点 / 风险贡献条形图）；②（散点模式）是否叠加蒙特卡洛云 checkbox |
| 展示 | ① 指标表：均值-方差（GMV/切线）vs 风险平价 / BL 先验 / BL 后验 / 蒙特卡洛（ret/vol/sharpe/max_dd，from extensions_summary.csv）；② 散点：各算法在收益-风险平面上的位置 + 蒙特卡洛云；③ 风险贡献条形图：风险平价组合各资产 RC（rc_* 列，六资产等高） |
| 数据来源 | `output/extensions_summary.csv`（pool/combo/note/ret/vol/sharpe/max_dd/w_*/rc_*）、`output/mc_points.csv`（蒙特卡洛样本）、`output/portfolios.csv`（均值-方差对照） |
| 联动 | 维度切换 → 图表类型切换；散点模式叠加云点 |
| 教学点 | 对比「均值-方差（依赖收益预测）」vs「风险平价（不依赖预测）」vs「BL（观点驱动）」的权重与指标差异 |

---

## 4. 实现建议

### 4.1 目录结构（app/ 多页应用）

```
project-demo/
├── app/
│   ├── Home.py                # 入口：标题 + 简介 + 数据版本 + 导航提示
│   ├── utils.py               # 共享：load_params/load_frontier/load_returns/solve_utility/指标计算
│   └── pages/
│       ├── 1_总览.py
│       ├── 2_有效前沿.py
│       ├── 3_权重分布.py
│       ├── 4_净值与回撤.py
│       ├── 5_相关性热力图.py
│       └── 6_扩展算法对比.py
├── data/                      # 已有（只读消费）
├── output/                    # 已有（只读消费 + dashboard.py 退役）
└── scripts/                   # 已有（viz.py 等）
```

- `app/utils.py` 从现有 `output/dashboard.py` 抽取：`load()`（读 params/frontier）、`solve_utility()`（γ 实时求解）、`compute_nav/drawdown()`（净值回撤口径，对齐 S-1）——**接口与 P2/P3 产物解耦，全部只读**；
- 路径解析复用 dashboard.py 的 `ROOT = Path(__file__).resolve().parent.parent` 约定，兼容 `streamlit run app/Home.py` 任意 cwd 启动。

### 4.2 与现有 scripts 的接口

| 消费产物 | 文件 | 用途页 |
|---|---|---|
| `data/params.json` / `params_stocks.json` | mu/Sigma/rf/tickers/asset_class | ②③④⑤ |
| `data/features.json` | corr / asset_class_summary / benchmark_6040 / checks | ①⑤④ |
| `data/returns_assetclass.csv` / `returns_stocks.csv` | 日收益率 → 净值/回撤/组合收益 | ④ |
| `output/frontier.csv` / `frontier_stocks.csv` | 有效前沿点 | ② |
| `output/portfolios.csv` / `portfolios_stocks.csv` | GMV/切线指标与权重 | ①③⑥ |
| `output/extensions_summary.csv` | 扩展算法指标与 RC | ⑥ |
| `output/mc_points.csv` | 蒙特卡洛样本 | ②⑥ |
| `output/report.md` | 结论摘要（①页引用关键行） | ① |

**不重算原则**：除 ②页 γ 实时求解（必须实时）与 ④页净值构造（`returns @ w` 轻量）外，全部读 CSV/JSON；页面加载用 `@st.cache_data` 缓存文件读取（文件不变不重复解析，500ms → 20ms）。

### 4.3 部署方式

| 方式 | 命令/步骤 | 适用 |
|---|---|---|
| 本地运行（主） | `cd project-demo && streamlit run app/Home.py`（需 .venv 已激活，streamlit 已装） | 现场演示、课后自用 |
| 局域网分享（可选） | `streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501` | 教室同网段浏览器访问（⚠️ 需验证：网络环境允许端口访问） |
| 公网部署（可选） | Streamlit Community Cloud / HF Spaces 上传仓库，选 `app/Home.py` 入口 | 课后长期访问（⚠️ 需验证：平台 Python 3.12 与依赖版本支持，akshare 依赖较重建议精简） |

### 4.4 对现有 dashboard.py 的取舍

- **推荐：替换（升级为多页）**——`app/` 成为唯一交互入口，`output/dashboard.py` 退役（其逻辑抽入 `app/utils.py`），避免两套入口数据口径漂移；
- 备选：保留 `output/dashboard.py` 作为「单页精简版」（仅总览+前沿），适合快速演示；但会增加维护成本，**不推荐并存**；
- 文档/脚本引用同步更新：viz-agent 职责描述（编排方案 §1.4）改为「输出 5 张静态图 + app/ 多页交互网页」。

---

## 5. 验收标准

| # | 验收项 | 判定标准 |
|---|---|---|
| W1 | 可运行性 | `streamlit run app/Home.py` 启动无报错；侧边栏 6 页均可访问，无 Traceback |
| W2 | 交互响应 | γ 滑块 / 资产池 / 禁做空 / 时间范围任一操作后，图表与指标 **<1s** 内更新（实时求解 SLSQP 轻量 + cache_data） |
| W3 | 数据正确性 | ①页卡片与 `output/portfolios.csv` 数值一致（GMV ret=6.07%、切线 ret=16.82%、夏普 0.999）；②页前沿线与 `frontier.csv` 完全重合；④页回撤与 `max_dd` 列一致（切线 -17.05%） |
| W4 | 交互正确性 | γ 增大 → 组合点沿前沿向低波动方向移动；禁做空关闭 → 允许负权重（如 EEM 负权重出现）；方案切换 → 数据整体切换 |
| W5 | 中文显示 | 全站中文标题/标签/图例无乱码（plotly 默认处理中文，macOS 需确认系统字体，⚠️ 需验证） |
| W6 | 断网可用 | 所有页面读本地 data/、output/ 产物，**全程不联网**（yfinance 不被调用）；断网后网页功能完整 |
| W7 | 复用产物 | 消费文件清单与 §4.2 一致，无「网页内重新拉数据/重新跑优化」逻辑（仅 ②页 γ 实时求解、④页净值构造属允许的轻量计算） |

**一键自检**（可选，dev-engineer-2 实现时附带 `scripts/test_dashboard.py`）：
```python
# 校验网页消费文件存在且关键值符合预期（数据正确性快检）
# 断言：portfolios.csv 含 GMV/切线行；features.json 有 corr 与 benchmark_6040；
#       extensions_summary.csv 含风险平价/BL/蒙特卡洛行；mc_points.csv 行数 ≥ 5000
```

---

## 6. 实施顺序建议（衔接 P5b-dashboard-impl）

1. **P5b-1**：建 `app/` 结构 + `utils.py`（抽取 dashboard.py 的 load/solve_utility，新增 compute_nav/drawdown）；
2. **P5b-2**：实现 ①②③ 页（总览 / 有效前沿 / 权重）——核心交互，先跑通 γ 联动；
3. **P5b-3**：实现 ④⑤⑥ 页（净值回撤 / 热力图 / 扩展对比）；
4. **P5b-4**：对照 W1–W7 验收 + 中文字体实测 + 断网演练 + git 提交；
5. **P5b-5**：编排方案 viz-agent 职责文案同步（dashboard 入口改为 app/Home.py）。

---

### 文档维护记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-13 | 初版：6 页交互网页设计方案（定位/选型/页面结构/交互设计/实现/验收） | portfolio-planner |
