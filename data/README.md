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
| `params_<name>.json` | 年化 mu（×252）、年化协方差 Sigma（×252）、起止日期 |

`<name>` 为缓存标识：`spy`（P2a 单标的验证）、`assetclass`（方案 A 六只 ETF）、`stocks`（基线六只个股）。

## 当前缓存

| 文件 | 说明 | 生成日期 |
|---|---|---|
| `closes_spy.csv` | SPY 近 5 年日线收盘价（1254 个交易日） | 2026-08-13 |
| `returns_spy.csv` | SPY 日收益率 | 2026-08-13 |
| `params_spy.json` | SPY 年化 mu/Sigma | 2026-08-13 |

## 验证记录（P2a）

- 交易日数：**1254**（预期 ≥ 1200 ✓）
- 无 NaN（closes/returns 均为 0）✓
- 日期连续：最大相邻间隔 4 天（节假日，≤ 7 天判定 OK）✓
- 年化收益：**+13.89%**（为正 ✓）
- 年化波动率：**17.22%**（15–25% 量级 ✓）
