# 基于 uv 的本地环境搭建操作指南（macOS）

> 适用对象：Portfolio Optimization 课程 Demo 项目前置环境准备
> 目标机器：macOS 本机（darwin 23.5.0）
> 项目目录：`/Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo`
> 关联文档：`portfolio-optimization-demo-prep.md` §1（环境与工具）
> 评审修订依据：`portfolio-optimization-demo-review.md` **I-3**（scikit-learn 纳入安装清单）、**S-5**（uv 安装失败兜底）
> 文档版本：v1.0（2026-08-13）｜ 作者：portfolio-planner

---

## 0. 背景与本机现状（先读）

**为什么用 uv？** uv 是 Python 包/环境管理工具，一条命令即可「建虚拟环境 + 装依赖」，比 `pip` 快一个数量级；内置 Python 版本管理，可自动下载并管理 Python 3.12，规避系统 Python 的 PEP 668 限制。

**本机实测基线（2026-08-13，作为对比参照）**：

| 项 | 现状 | 说明 |
|---|---|---|
| 系统 Python | `/usr/bin/python3` = **3.9.6** | 过旧，且受 **PEP 668**（externally-managed-environment）限制，**不可直接 pip 安装** |
| numpy / pandas | 2.0.2 / 2.3.3 | 已装在系统环境，但 **demo 不要复用系统环境** |
| scipy / matplotlib | 1.13.1 / 3.9.4 | 同上 |
| yfinance / akshare | **均未安装** | 数据采集必需，必须在本指南搭建的虚拟环境中安装 |

> ⚠️ 需验证：系统环境中已装的包版本与 uv 虚拟环境无关联；以下所有操作**都在 uv 创建的虚拟环境中进行**，不触碰系统 Python。

---

## 1. 安装 uv

### 1.1 官方脚本安装（首选）

**是什么**：uv 官方提供的安装脚本，将 uv 二进制安装到用户目录（不污染系统）。
**为什么需要**：官方脚本安装的 uv 自带 Python 版本管理能力，后续 `uv venv --python 3.12` 可自动下载 Python 3.12。

**完整命令**：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**验证命令**：

```bash
uv --version
```

**预期输出**（版本号随发布更新）：

```
uv 0.7.x (Homebrew 或 ~/.local/bin 安装)   # 以实际版本为准
```

### 1.2 失败兜底：`pip install uv`（S-5 修订项）

**是什么**：若官方脚本因网络不可达/被墙/证书问题失败，改用 pip 安装 uv。
**为什么需要**：评审 S-5 指出原文档只给了脚本路径、缺兜底；pip 安装走 PyPI（国内常配镜像，可用性更高）。

**完整命令**：

```bash
# 兜底路径 1：pip 安装 uv（装到 ~/.local/bin 或当前 Python 的 bin 目录）
python3 -m pip install --user uv

# 兜底路径 2：若 pip 也受 PEP 668 限制（本机实测系统 python3 大概率触发），
# 先建一个最小的临时 venv 再装 uv：
python3 -m venv /tmp/uv-bootstrap-venv
/tmp/uv-bootstrap-venv/bin/pip install uv
/tmp/uv-bootstrap-venv/bin/uv --version   # 确认可用

# 兜底路径 3：Homebrew（若已装 brew）
brew install uv
```

**验证命令**（任选一种安装方式后执行）：

```bash
uv --version
```

**预期输出**：

```
uv 0.7.x
```

**判定**：输出版本号 = 安装成功；`command not found: uv` = 未安装或 PATH 未配置（见 1.3）。

### 1.3 macOS 路径说明与 PATH 配置

**是什么**：uv 安装后的二进制所在目录，需加入 shell PATH 才能直接调用 `uv`。
**为什么需要**：不同安装方式的落盘路径不同；PATH 未配置会导致「装好了却敲不了 `uv`」。

**各安装方式的默认路径**：

| 安装方式 | 二进制路径 | 说明 |
|---|---|---|
| 官方脚本 | `~/.local/bin/uv` | 常见默认，脚本会自动配置 shell（zsh 写入 `~/.zshrc`）⚠️ 需验证自动配置是否生效 |
| pip `--user` | `~/Library/Python/3.x/bin/uv`（macOS） | 随 pip 版本路径不同 |
| 临时 venv | `/tmp/uv-bootstrap-venv/bin/uv` | 仅用于引导，不建议长期依赖 |
| Homebrew | `/opt/homebrew/bin/uv`（Apple Silicon）或 `/usr/local/bin/uv`（Intel） | brew 自动加入 PATH |

**若 `uv` 命令找不到，手动配置 PATH（zsh）**：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**验证命令**：

```bash
which uv
```

**预期输出**（示例）：

```
/Users/congwang/.local/bin/uv
```

**判定**：输出为有效路径 = PATH 配置成功；`uv not found` = 继续排查（见 §6）。

---

## 2. 在项目目录创建 Python 3.12 虚拟环境

### 2.1 创建虚拟环境（uv venv）

**是什么**：在项目目录下创建 `.venv` 虚拟环境，隔离 demo 的全部依赖。
**为什么需要**：① 规避系统 Python 3.9 + PEP 668；② 依赖版本不污染全局；③ 可复现、可删除重建。

**完整命令**（在项目目录下执行）：

```bash
cd /Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo
uv venv --python 3.12 .venv
```

**预期输出**（首次运行可能自动下载 Python 3.12）：

```
Using CPython 3.12.x
Creating virtual environment at: .venv
```

> ⚠️ 需验证：若本机已有 Python 3.12 则直接复用；否则 uv 会自动下载 CPython 3.12（需网络，见 §6.2 网络不可达的处理）。

### 2.2 激活虚拟环境并验证

**完整命令**：

```bash
source .venv/bin/activate
which python
python --version
```

**预期输出**：

```
/Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo/.venv/bin/python
Python 3.12.x
```

**判定**：
- `which python` 指向项目内 `.venv/bin/python` = 激活成功；
- `python --version` 显示 3.12.x = 版本正确；
- 若 `python` 仍指向 `/usr/bin/python3` = 未激活或激活失败（见 §6）。

> 提示：uv 支持免激活用法 `uv run python ...`（自动使用 .venv），演示脚本也可用该方式，不强制 source。

---

## 3. 安装完整依赖清单

### 3.1 一键安装（含 scikit-learn，I-3 修订项）

**是什么**：demo 全链路依赖（数值计算 / 数据获取 / 绘图 / 交互 / 优化兜底）。
**为什么需要**：
- numpy/pandas/scipy/matplotlib/seaborn：核心计算与绘图；
- yfinance/akshare：行情数据获取；
- streamlit：可选交互界面；
- jupyter：开发调试；
- **scikit-learn**：评审 I-3 要求纳入——协方差矩阵不正定时的 **Ledoit-Wolf 收缩估计**兜底（`sklearn.covariance.LedoitWolf`）依赖它，现场缺库会导致兜底方案无法落地。

**完整命令**（确保已激活 .venv）：

```bash
uv pip install numpy pandas scipy matplotlib seaborn \
    yfinance akshare streamlit jupyter scikit-learn
```

**预期输出**（uv 输出较长，结尾关键行）：

```
Resolved X packages in ...ms
Installed X packages in ...ms
```

> ⚠️ 需验证：akshare 依赖较多、安装包体积大，首次安装耗时较长；若装 akshare 失败可先跳过（`uv pip install akshare` 单独重试），其余包不阻塞。

### 3.2 版本固化与 requirements.txt 导出

**是什么**：把当前虚拟环境里实际安装的精确版本固化为 `requirements.txt`。
**为什么需要**：评审 I-3 明确要求「提前固化版本」——保证现场/他人环境与开发环境**逐字节一致**，避免版本漂移导致结果差异；也是 §3.1 安装失败的恢复依据（离线可重建）。

**完整命令**：

```bash
# 导出当前环境全部包及精确版本
uv pip freeze > requirements.txt

# 查看文件内容确认（预期每行格式：包名==精确版本）
cat requirements.txt
```

**预期输出**（示例片段）：

```
numpy==2.2.1
pandas==2.2.3
scipy==1.15.1
matplotlib==3.10.0
seaborn==0.13.2
yfinance==0.2.54
akshare==1.16.x
streamlit==1.41.x
jupyter==1.1.x
scikit-learn==1.6.x
```

**验证命令**：

```bash
head -5 requirements.txt
```

**判定**：每行均为 `包名==版本号` = 固化成功；出现 `@ file://` 或缺失 = 环境存在非 PyPI 源，需排查（一般不会出现）。

**版本回滚/重建（可选，现场快速恢复）**：

```bash
# 删除旧环境重新安装（全部依赖按 requirements.txt 精确还原）
rm -rf .venv
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

---

## 4. 连通性验证（yfinance 拉取 AAPL）

**是什么**：验证数据链路可用——yfinance 能真实拉到 Yahoo Finance 的行情数据。
**为什么需要**：演示数据源是第一风险点（评审坑 #1：网络不可达/限流）；必须在开发期提前验证，并确认预期输出形态，避免现场才发现拉不到数据。

**完整命令**（已激活 .venv）：

```python
python -c "
import yfinance as yf
d = yf.download('AAPL', start='2026-08-06', end='2026-08-13', auto_adjust=True)
print(d.tail(3))
"
```

**预期输出**（价格数字随行情变化，重点是**结构**：四列 OHLC + Volume + 多级列名）：

```
[*********************100%%**********************]  1 of 1 completed
                 Open        High         Low       Close    Volume
Date
2026-08-10  227.220001  229.509995  226.550003  227.440002  43740000
2026-08-11  228.190002  231.699997  227.449997  231.649994  40160000
2026-08-12  231.000000  233.300003  229.649994  232.190002  41580000
```

**判定**：
- 输出含 `Date` 索引 + OHLC/Volume 列，行数 ≥ 1 = **通过**（数据链路可用）；
- 报错 `No data found` / 超时 / HTTP 4xx = 网络问题（见 §6.2）；
- 输出为空 DataFrame = 参数范围无交易日或数据源问题，换 `period='5d'` 重试：

  ```bash
  python -c "import yfinance as yf; print(yf.download('AAPL', period='5d', auto_adjust=True).tail())"
  ```

> 提示：验证通过后，按准备清单 §2.4 立即把数据缓存为 CSV（`data/closes.csv`），现场断网也能演示。

---

## 5. 环境自检清单（每项含通过/失败判定）

**是什么**：一张可勾选的核对表，确认环境完全就绪后才进入数据/算法开发。
**为什么需要**：把「环境是否 OK」从模糊感觉变成可判定清单，任何一项失败都应在开发前解决，避免 Demo 现场炸在环境上。

**运行方式**：在项目目录、已激活 .venv 的终端中逐项执行。

| # | 检查项 | 命令 | 通过判定 | 失败判定/处理 |
|---|---|---|---|---|
| 1 | uv 可用 | `uv --version` | 输出版本号 `uv 0.7.x` | `command not found` → 见 §1.3 PATH / §6.4 |
| 2 | Python 版本 | `python --version` | `Python 3.12.x` | 3.9 或其他 → 环境未激活或创建版本错误，见 §2.2 / §6 |
| 3 | 解释器路径 | `which python` | 指向 `.../project-demo/.venv/bin/python` | 指向 `/usr/bin` → 未激活 |
| 4 | numpy | `python -c "import numpy; print(numpy.__version__)"` | 输出版本号（如 2.2.x） | ImportError → 缺装或环境串了，`uv pip install -r requirements.txt` |
| 5 | pandas | `python -c "import pandas; print(pandas.__version__)"` | 输出版本号（如 2.2.x） | 同上 |
| 6 | scipy | `python -c "import scipy; print(scipy.__version__)"` | 输出版本号（如 1.15.x） | 同上 |
| 7 | matplotlib | `python -c "import matplotlib; print(matplotlib.__version__)"` | 输出版本号（如 3.10.x） | 同上 |
| 8 | seaborn | `python -c "import seaborn; print(seaborn.__version__)"` | 输出版本号（如 0.13.x） | 同上 |
| 9 | yfinance | `python -c "import yfinance; print(yfinance.__version__)"` | 输出版本号（如 0.2.5x） | 同上 |
| 10 | akshare | `python -c "import akshare; print(akshare.__version__)"` | 输出版本号（如 1.16.x） | 同上（若已跳过安装则标「未装，A 股备选」） |
| 11 | streamlit | `python -c "import streamlit; print(streamlit.__version__)"` | 输出版本号（如 1.41.x） | 同上 |
| 12 | scikit-learn（I-3） | `python -c "import sklearn; print(sklearn.__version__); from sklearn.covariance import LedoitWolf; print('LedoitWolf OK')"` | 输出版本号 + `LedoitWolf OK` | ImportError → 未装 scikit-learn，见 §3.1 |
| 13 | 数据连通性 | 见 §4 命令 | 拉到 AAPL 行情行数 ≥ 1 | 见 §4 判定 / §6.2 |
| 14 | 版本固化 | `ls -la requirements.txt` | 文件存在且非空 | 未导出 → 执行 §3.2 |

**一键自检脚本（可复制为 `scripts/env_check.sh` 使用）**：

```bash
#!/bin/bash
set -e
echo "== uv =="; uv --version
echo "== python =="; python --version; which python
echo "== 关键包 =="
for pkg in numpy pandas scipy matplotlib seaborn yfinance streamlit sklearn; do
  python -c "import $pkg; print('$pkg', $pkg.__version__)" 2>/dev/null || echo "$pkg 缺失"
done
echo "== 数据连通性 =="
python -c "import yfinance as yf; d=yf.download('AAPL', period='5d', auto_adjust=True, progress=False); print('rows:', len(d))"
echo "== 全部就绪 =="
```

---

## 6. 常见失败与解决

### 6.1 PEP 668（externally-managed-environment）

**现象**：系统 Python 下执行 `pip install xxx` 报：

```
error: externally-managed-environment
This environment is externally managed ...
```

**原因**：macOS 新版系统 Python 禁止 pip 直接写系统目录（本机实测 `/usr/bin/python3` 即如此）。
**解决**：**不要**在系统 Python 下装包；全部改用 uv 虚拟环境（本指南 §2–§3）。若必须用系统 python 装，加 `--break-system-packages`（**不推荐**，会污染系统环境）。

### 6.2 网络不可达 / yfinance 拉取失败

**现象**：
- uv 下载 Python 或安装包超时；
- yfinance 报 `HTTP Error 429`、超时、`No data found`、`Failed to download`。

**原因**：Yahoo Finance / PyPI 在国内网络环境可能不稳定或被限流。
**解决**（按优先级）：
1. **本地缓存兜底**（准备清单 §2.4）：开发期拉取成功后立即 `closes.to_csv("data/closes.csv")`，现场断网用缓存数据；
2. 重试：yfinance 拉取加 `period='5d'` 短窗口测试；重跑 1–2 次；
3. 换数据源：akshare（A 股）或已配置的镜像源；
4. uv 装包网络问题：配置 PyPI 镜像（如阿里云）：

   ```bash
   export UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple"
   uv pip install -r requirements.txt
   ```

### 6.3 版本冲突（numpy 2.x 与旧依赖）

**现象**：安装或 import 时报 `numpy.core.multiarray failed to import`、`A module that was compiled using NumPy 1.x cannot run in NumPy 2.x` 等。
**原因**：某些包编译时绑定旧 numpy ABI，与 numpy 2.x 不兼容。
**解决**：
1. 一律从 `requirements.txt`（§3.2 固化的精确版本）安装，不要混合手动装包；
2. 若冲突，`uv pip install --upgrade <冲突包>` 或删除 `.venv` 后按 requirements.txt 重建（§3.2 回滚命令）；
3. 检查依赖树：`uv pip tree | grep -i numpy` 定位谁依赖旧 numpy。

### 6.4 uv 安装脚本失败

**现象**：`curl -LsSf https://astral.sh/uv/install.sh | sh` 无输出/报错/超时。
**原因**：脚本下载不可达（网络/代理/证书）。
**解决**：按 §1.2 兜底路径——`python3 -m pip install --user uv` → 仍受 PEP 668 则临时 venv 装 → 或 `brew install uv`；装好后按 §1.3 配置 PATH。

### 6.5 激活失败 / `python` 仍指向系统

**现象**：`source .venv/bin/activate` 后 `which python` 仍为 `/usr/bin/python3`。
**原因**：shell 缓存或 PATH 顺序；或用了子 shell。
**解决**：
```bash
hash -r          # 清除 shell 命令缓存
which python     # 重新检查
# 或直接用 uv 免激活：uv run python --version（自动使用 .venv）
```

### 6.6 磁盘 / 权限问题

**现象**：`Permission denied` 或 `No space left on device`。
**解决**：uv 缓存目录 `~/.cache/uv` 可清（`uv cache clean`）；确认对项目目录有写权限（`chmod -R u+rwX .` 视情况）。

---

## 附录 A：快速开始（最小命令序列）

```bash
# 1. 安装 uv（官方脚本；失败则见 §1.2 兜底）
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 2. 建环境 + 装依赖
cd /Users/congwang/.jiuwenswarm/agent/workspace/work/project-demo
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install numpy pandas scipy matplotlib seaborn yfinance akshare streamlit jupyter scikit-learn

# 3. 验证 + 固化
uv pip freeze > requirements.txt
python -c "import yfinance as yf; print(yf.download('AAPL', period='5d', auto_adjust=True).tail())"
```

## 附录 B：清理与重建

```bash
deactivate 2>/dev/null; rm -rf .venv   # 删除虚拟环境（不影响项目文件）
uv cache clean                          # 清理 uv 下载缓存（可选）
# 重建：回到附录 A 第 2 步
```

---

### 文档维护记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v1.0 | 2026-08-13 | 初版：基于 uv 的 macOS 环境搭建指南（含 I-3 scikit-learn、S-5 uv 兜底修订） | portfolio-planner |
