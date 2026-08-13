# 数据缓存说明（data/）

本目录存放**行情数据缓存**，由 `scripts/fetch_data.py` 自动生成，**不纳入 git 版本管理**（断网可兜底演示，现场用 `--refresh` 重新拉取）。

## 生成方式

```bash
# 在项目根目录、已激活 .venv 的环境中执行
python scripts/fetch_data.py --name spy --tickers SPY --years 5
```

- **缓存优先**：若 `data/closes_<name>.csv` 已存在则直接读取，不联网；
- **强制刷新**：加 `--refresh` 参数联网重新拉取；
- **日期动态化**：截止日 = `pd.Timestamp.today()`，窗口 = 近 N 年（S-6，不写死过期）。

## 文件命名约定

| 文件 | 内容 |
|---|---|
| `closes_<name>.csv` | 对齐后收盘价（Date 索引，每 ticker 一列，auto_adjust 复权价） |
| `returns_<name>.csv` | 日收益率（`pct_change().dropna()`） |
| `params_<name>.json` | 年化 mu（×252）、年化协方差 Sigma（×252）、起止日期、rf、benchmark、asset_class |
| `params.json` | **正式参数文件**（P3 优化直接消费，`--params-out data/params.json` 生成） |

`<name>` 为缓存标识：`spy`（P2a 单标的验证）、`assetclass`（方案 A 六只 ETF）、`stocks`（基线六只个股）。

## 当前缓存

| 文件 | 说明 | 生成日期 |
|---|---|---|
| `closes_spy.csv` | SPY 近 5 年日线收盘价（1254 个交易日） | 2026-08-13 |
| `returns_spy.csv` | SPY 日收益率 | 2026-08-13 |
| `params_spy.json` | SPY 年化 mu/Sigma | 2026-08-13 |
| `closes_assetclass.csv` | 方案 A 六只 ETF 对齐收盘价（1254×6） | 2026-08-13 |
| `returns_assetclass.csv` | 方案 A 日收益率 | 2026-08-13 |
| `params_assetclass.json` | 方案 A 年化参数 + rf/benchmark/asset_class | 2026-08-13 |
| `closes_stocks.csv` | 基线六只个股对齐收盘价（1254×6） | 2026-08-13 |
| `returns_stocks.csv` | 基线六只个股日收益率 | 2026-08-13 |
| `params_stocks.json` | 基线个股年化参数 | 2026-08-13 |
| `params.json` | 正式参数文件（方案 A，P3 使用） | 2026-08-13 |

## 生成命令（P2b）

```bash
# 方案 A（含 rf=^IRX、benchmark=SPY，输出正式 params.json）
python scripts/fetch_data.py --name assetclass --tickers SPY,IWM,TLT,GLD,EEM,DBC \
    --years 5 --rf --benchmark SPY --params-out data/params.json

# 基线个股
python scripts/fetch_data.py --name stocks --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5
```

## 验证记录（P2b）

- 窗口：方案 A / 基线均为 **1254 交易日**（2021-08-13 ~ 2026-08-12，目标 ≥ 750 ✓，EEM 跨市场日历无缩短）
- 无 NaN、日期连续（最大间隔 4 天）✓
- 年化收益：DBC **-7.19%**（负收益，商品展期损耗，备好解释话术）；其余资产均为正（+9.4% ~ +27.8%）
- rf = **3.707%**（^IRX，断言 0<rf<0.15 通过）；基准 SPY 最新收盘 772.49
- 相关矩阵特征：负相关 **DBC-EEM(-0.12)**、近零相关 DBC 与多数资产（|r|<0.15）、强正相关 SPY-EEM(0.85)/SPY-TLT(0.68)
