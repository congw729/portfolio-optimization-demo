# 优化输出说明（output/）

本目录存放 **P3 优化器 + P3x 扩展算法 + P5 可视化产物**（组合指标、有效前沿 CSV 与 5 张图表 PNG），由 `scripts/optimizer.py` / `scripts/extensions.py` / `scripts/viz.py` 生成。
CSV/PNG 数据文件**不纳入 git 版本管理**（可随时用脚本重新生成），本说明文件入库。

## 生成方式

```bash
# 方案 A（主输出：portfolios.csv + frontier.csv）
python scripts/optimizer.py --params data/params.json \
    --returns data/returns_assetclass.csv --tag assetclass

# 基线个股（frontier_stocks.csv，供 P5 双前沿对比）
python scripts/optimizer.py --params data/params_stocks.json \
    --returns data/returns_stocks.csv --tag stocks

# P3x 可选扩展（风险平价 / Black-Litterman / 蒙特卡洛）
python scripts/extensions.py

# P5 可视化（5 张 PNG）
python scripts/viz.py

# 可选：Streamlit 交互页（不重算，读产物）
streamlit run output/dashboard.py
```

## 文件说明

| 文件 | 内容 |
|---|---|
| `portfolios.csv` | 方案 A 组合指标表：GMV/切线（数值禁做空主口径 + 解析允许做空对照），含 ret/vol/sharpe/max_dd/权重 |
| `portfolios_stocks.csv` | 基线个股组合指标表（口径同方案 A，rf 一致） |
| `extensions_summary.csv` | **P3x 扩展汇总表**：风险平价（权重+RC 分布）、BL 先验/后验切线、蒙特卡洛统计，含与均值-方差主结果的对照行 |
| `mc_points.csv` | 蒙特卡洛 6000 随机组合的收益/波动样本点（dirichlet，供与有效前沿叠加） |
| `frontier.csv` | 方案 A 有效前沿（59/60 可行点，含 target_ret/ret/vol/权重） |
| `frontier_assetclass.csv` | 同上（tag 副本） |
| `frontier_stocks.csv` | 基线个股有效前沿（60/60 可行点） |
| `frontier_scatter.png` | **图① 有效前沿散点图**（+蒙特卡洛 3000 灰点云 + CML + GMV/切线标注 + 单资产点），Demo 主图 |
| `weights_bar.png` | **图② 权重条形图**（GMV/切线/中目标收益组合，按资产类别着色 equity-us/bond/gold/equity-em/commodity） |
| `drawdown_curve.png` | **图③ 回撤曲线**（切线组合 vs 基准 SPY：nav/dd/max_dd，S-1 口径） |
| `correlation_heatmap.png` | **图④ 相关性热力图**（升级主图，方框标注负相关 GLD-DBC / 强正相关 SPY-EEM、SPY-TLT） |
| `frontier_compare.png` | **图⑤ 双前沿对比图**（方案 A vs 基线个股，含各自 GMV 标注） |
| `dashboard.py` | 可选 Streamlit 交互页：资产池选择/风险厌恶 γ slider/禁做空 checkbox，读产物不重算 |

## 口径说明（评审 I-2）

- **主口径**：数值优化（SLSQP，禁做空 bounds=(0,1)，权重和=1）——GMV 与切线组合均以此为准；
- **对照**：解析解（允许做空、无界权重）仅作教学对照（如切线解析解含大额负权重），演示不并列混淆；
- rf 统一 = 0.03707（^IRX 3 个月美债，方案 A 与基线同口径，保证夏普可比）；
- 最大回撤按 S-1 口径：nav=(1+r).cumprod()；dd=nav/nav.cummax()-1；max_dd=dd.min()。

## 关键结论（P3 里程碑）

- 方案 A：GMV 年化收益 +6.07%、波动 10.13%；切线组合年化收益 +16.82%、波动 13.13%、**夏普 0.999**；前沿 59 点弯曲明显，GMV 与切线分离清晰（Δvol=+0.03, Δret=+0.106）；
- 基线个股：GMV 年化收益 +22.40%、波动 17.74%；切线组合年化收益 +25.18%、波动 18.98%、**夏普 1.131**；前沿 60 点（rf 口径统一后计算）。

## 关键结论（P3x 扩展，准备清单 §3.3）

- **风险平价**：迭代 18 次收敛（RC 相对差异 5.3e-7，容差 1e-6）。权重 SPY 14.9% / IWM 16.2% / TLT 12.7% / GLD 19.0% / EEM 11.3% / DBC 25.8%，各资产风险贡献 RC 完全相等（1.84%）；组合 ret=+8.38%、vol=11.03%、sharpe=0.424。与 GMV 对比：**不依赖收益预测**，牺牲少量收益（Δret − 与 GMV +2.3pp）换取风险贡献均衡，债/金等低波动资产被赋予更高权重（vs GMV 中 DBC 39.9%）；
- **Black-Litterman**：δ=2.5、w_mkt 等权近似（注明假设）；逆优化均衡收益 π = δΣw_mkt（SPY 4.1%…EEM 5.5%）。叠加观点①看好美股（SPY/IWM 平均年化 8%）、②黄金低配（GLD 1%）后，后验收益显著变化（SPY 4.1%→6.1%、GLD 2.7%→2.4%），后验切线权重 IWM 0%→21.5%、TLT 7.5%→23.3%、EEM 92.5%→55.1%，**展示观点如何重塑组合**；
- **蒙特卡洛**：dirichlet 生成 6000 个随机组合（≥5000），样本点存 `mc_points.csv` 供与有效前沿叠加；**100% 样本落在有效前沿右侧（低效区）**，直观展示『随机组合不可战胜优化』的教学叙事；
- 教学叙事：风险平价（无收益预测）/ BL（观点融入）/ 蒙特卡洛（随机 vs 优化的直观对比）三者与均值-方差主结果形成完整扩展链条。
