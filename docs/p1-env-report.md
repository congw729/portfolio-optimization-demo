# P1 环境搭建报告（p1-env-report）

> 执行者：dev-engineer ｜ 日期：2026-08-13
> 项目目录：`/Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo`
> 依据：`local-env-setup-uv.md`（v1.0）与任务 p1-env-setup
> 结论：**✅ 环境搭建完成，14/14 项自检全部通过**

---

## 1. 执行摘要

| 步骤 | 结果 | 说明 |
|---|---|---|
| Git 仓库初始化 | ✅ | `git init -b main`，首次提交 `68c7728`（.gitignore） |
| uv 安装 | ✅ | 官方脚本失败（astral.sh SSL 不可达）→ §1.2 兜底路径 1 pip 安装成功：**uv 0.12.3** |
| Python 3.12 虚拟环境 | ✅ | **CPython 3.12.13**（uv 自动下载，macos-aarch64） |
| 依赖安装 | ✅ | 143 个包全部安装成功（含 akshare、scikit-learn） |
| 版本固化 | ✅ | `requirements.txt` 143 行，全部 `包名==精确版本` |
| yfinance 连通性 | ✅ | SPY 5 日行情拉取成功（5 行 OHLC+Volume） |
| 环境自检 | ✅ | **14/14 通过** |

---

## 2. 环境基线

| 项 | 实测值 |
|---|---|
| 机器架构 | macOS Darwin 23.5.0，Apple Silicon (arm64) |
| 系统 Python | `/usr/bin/python3` = 3.9.6（未触碰，仅用于引导 uv） |
| 安装方式 | uv 官方脚本失败 → pip `--user` 兜底（PyPI 可达，10.2 MB/s） |
| uv 二进制 | `/Users/congwang/Library/Python/3.9/bin/uv`（已写入 `~/.zshrc` PATH） |
| 虚拟环境 | `/Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo/.venv` |

---

## 3. 各步骤执行详情

### 3.1 Git 仓库初始化
- `git init -b main`：成功，默认分支 main
- `.gitignore`：已创建（忽略 `.venv/`、`__pycache__/`、`*.pyc`、`.DS_Store`、`data/` 缓存、`*.csv`、日志等）
- 首次提交：`68c7728 chore: 初始化项目仓库并添加 .gitignore`

### 3.2 uv 安装（含兜底记录）
- **首选路径失败**：`curl -LsSf https://astral.sh/uv/install.sh | sh` 报 `curl: (35) LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to astral.sh:443`（astral.sh 网络不可达）
- **兜底路径 1 成功**：`python3 -m pip install --user uv` → `uv 0.12.3`（wheel 18.4MB，走 PyPI 正常）
- PATH 配置：二进制位于 `~/Library/Python/3.9/bin/`，已写入 `~/.zshrc`
- 验证：`uv --version` → `uv 0.12.3 (507230998 2026-08-07 aarch64-apple-darwin)`

### 3.3 Python 3.12 虚拟环境
- `uv venv --python 3.12 .venv` → 自动下载 CPython 3.12.13（23.8 MiB）并创建成功
- 解释器：`.venv/bin/python -> ~/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12`

### 3.4 依赖安装与固化
- `uv pip install numpy pandas scipy matplotlib seaborn yfinance akshare streamlit jupyter scikit-learn` → 143 包全部安装成功，无失败项
- `uv pip freeze > requirements.txt` → 143 行，全部为 `包名==精确版本`

---

## 4. §5 环境自检清单（14/14 通过）

| # | 检查项 | 实测结果 | 判定 |
|---|---|---|---|
| 1 | uv 可用 | `uv 0.12.3` | ✅ 通过 |
| 2 | Python 版本 | `Python 3.12.13` | ✅ 通过 |
| 3 | 解释器路径 | `.venv/bin/python`（uv 管理的 cpython-3.12） | ✅ 通过 |
| 4 | numpy | `2.5.2` | ✅ 通过 |
| 5 | pandas | `3.0.5` | ✅ 通过 |
| 6 | scipy | `1.18.0` | ✅ 通过 |
| 7 | matplotlib | `3.11.1` | ✅ 通过 |
| 8 | seaborn | `0.13.2` | ✅ 通过 |
| 9 | yfinance | `1.5.2` | ✅ 通过 |
| 10 | akshare | `1.18.86` | ✅ 通过 |
| 11 | streamlit | `1.61.1` | ✅ 通过 |
| 12 | scikit-learn + LedoitWolf | `1.9.0` + `LedoitWolf OK` | ✅ 通过 |
| 13 | 数据连通性 | SPY 5 日行情，`rows: 5` | ✅ 通过 |
| 14 | 版本固化 | `requirements.txt` 存在且非空（143 行） | ✅ 通过 |

### 13 项连通性验证原始输出（SPY，period='5d', auto_adjust=True）

```
Price            Close        High         Low        Open    Volume
Ticker             SPY         SPY         SPY         SPY       SPY
Date
2026-08-06  768.559998  771.820007  767.460022  770.210022  38416900
2026-08-07  773.260010  773.919983  769.609985  771.020020  43586300
2026-08-10  773.030029  775.049988  771.619995  772.599976  39249500
2026-08-11  770.559998  774.609985  769.200012  774.530029  36740600
2026-08-12  772.489990  774.900024  771.280029  774.710022  33095100
rows: 5
```

---

## 5. 关键实测版本清单

| 包 | 版本 |
|---|---|
| uv | 0.12.3 |
| Python | 3.12.13 |
| numpy | 2.5.2 |
| pandas | 3.0.5 |
| scipy | 1.18.0 |
| matplotlib | 3.11.1 |
| seaborn | 0.13.2 |
| yfinance | 1.5.2 |
| akshare | 1.18.86 |
| streamlit | 1.61.1 |
| jupyter / notebook | 1.1.1 / 7.6.2 |
| scikit-learn | 1.9.0 |

---

## 6. 异常与兜底记录

| # | 异常 | 处理 | 结果 |
|---|---|---|---|
| 1 | uv 官方安装脚本失败：`astral.sh:443 SSL_ERROR_SYSCALL` | §1.2 兜底路径 1：`python3 -m pip install --user uv`（走 PyPI） | ✅ uv 0.12.3 |
| 2 | uv 安装后 `command not found`（PATH 未含 `~/Library/Python/3.9/bin`） | §1.3：写入 `~/.zshrc` PATH | ✅ `which uv` 有效 |

---

## 7. 后续建议（供 P2 数据管道参考）

1. 按准备清单 §2.4 建议，在 P2 阶段将 SPY 等标的行情缓存为 `data/closes.csv`，现场断网可兜底演示；
2. 本环境基于 `requirements.txt` 可完整重建（`uv venv --python 3.12 .venv && uv pip install -r requirements.txt`）；
3. 若需更换 PyPI 源可配置 `UV_DEFAULT_INDEX`（指南 §6.2）。
