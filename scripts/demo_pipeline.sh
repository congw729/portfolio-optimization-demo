#!/bin/bash
# ============================================================================
# P4b 兜底演示脚本（编排方案「方式 3：确定性编排脚本」）
#
# 顺序执行完整流水线：fetch_data（缓存优先）→ features → optimizer（方案A+基线）
#                    → viz → report
# 每步检查退出码与产物存在性，失败即停并提示；支持 --data-dir/--output-dir 透传。
#
# 用法：
#   bash scripts/demo_pipeline.sh                       # 默认 data/ output/
#   bash scripts/demo_pipeline.sh --data-dir DIR --output-dir DIR
#   bash scripts/demo_pipeline.sh --refresh             # 强制联网刷新数据
#
# 退出码：0 = 全链路成功；非 0 = 某步失败（见提示）。
# ============================================================================

set -u

DATA_DIR="data"
OUTPUT_DIR="output"
REFRESH=""

# ---- 参数解析 ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --data-dir)   DATA_DIR="$2";   shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --refresh)    REFRESH="--refresh"; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "❌ 未知参数: $1（可用 --data-dir / --output-dir / --refresh）"; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"

fail() { echo "❌ [FAIL] $1"; exit 1; }
ok()   { echo "✅ [OK]   $1"; }

step() { echo ""; echo "════════════════════════════════════════════"; echo "  $1"; echo "════════════════════════════════════════════"; }

# ---- 0. 环境检查 ----
step "0/5 环境检查"
[[ -x "$PY" ]] || fail "虚拟环境缺失（$PY），请先完成 P1 环境搭建"
"$PY" -c "import numpy, pandas, scipy, matplotlib, yfinance" 2>/dev/null \
  || fail "依赖缺失，请执行 uv pip install -r requirements.txt"
ok "虚拟环境与依赖就绪（$("$PY" --version)）"

# ---- 1. 数据采集（缓存优先）----
step "1/5 数据采集（scripts/fetch_data.py，缓存优先${REFRESH:+，--refresh 联网}）"
"$PY" scripts/fetch_data.py --name assetclass \
      --tickers SPY,IWM,TLT,GLD,EEM,DBC --years 5 \
      --rf --benchmark SPY \
      --params-out "$DATA_DIR/params.json" \
      --data-dir "$DATA_DIR" $REFRESH \
  || fail "fetch_data assetclass 失败"
# 基线 stocks 同样带 --rf（无风险利率与资产池无关，保证双前沿对比口径一致）
"$PY" scripts/fetch_data.py --name stocks \
      --tickers AAPL,MSFT,GOOGL,AMZN,JPM,XOM --years 5 \
      --rf \
      --data-dir "$DATA_DIR" $REFRESH \
  || fail "fetch_data stocks 失败"
[[ -f "$DATA_DIR/params.json" ]]      || fail "产物缺失: $DATA_DIR/params.json"
[[ -f "$DATA_DIR/params_stocks.json" ]] || fail "产物缺失: $DATA_DIR/params_stocks.json"
ok "数据与参数就绪（1254 交易日，rf 断言内置）"

# ---- 2. 特征计算 ----
step "2/5 特征计算（scripts/features.py）"
"$PY" scripts/features.py --data-dir "$DATA_DIR" --output-dir "$OUTPUT_DIR" \
  || fail "features 失败"
[[ -f "$DATA_DIR/features.json" ]] || fail "产物缺失: $DATA_DIR/features.json"
ok "派生特征就绪（corr/类别汇总/60-40 基准，A2 负相关校验通过）"

# ---- 3. 组合优化（方案 A + 基线）----
step "3/5 组合优化（scripts/optimizer.py，方案 A + 基线）"
"$PY" scripts/optimizer.py --params "$DATA_DIR/params.json" \
      --returns "$DATA_DIR/returns_assetclass.csv" \
      --tag assetclass --output-dir "$OUTPUT_DIR" \
  || fail "optimizer assetclass 失败"
"$PY" scripts/optimizer.py --params "$DATA_DIR/params_stocks.json" \
      --returns "$DATA_DIR/returns_stocks.csv" \
      --tag stocks --output-dir "$OUTPUT_DIR" \
  || fail "optimizer stocks 失败"
for f in "$OUTPUT_DIR/frontier.csv" "$OUTPUT_DIR/frontier_stocks.csv" \
         "$OUTPUT_DIR/portfolios.csv" "$OUTPUT_DIR/portfolios_stocks.csv"; do
  [[ -f "$f" ]] || fail "产物缺失: $f"
done
ok "组合与前沿就绪（GMV/切线/60 点前沿）"

# ---- 4. 可视化 ----
step "4/5 可视化（scripts/viz.py，5 张图）"
"$PY" scripts/viz.py --data-dir "$DATA_DIR" --output-dir "$OUTPUT_DIR" \
  || fail "viz 失败"
for f in frontier_scatter weights_bar drawdown_curve \
         correlation_heatmap frontier_compare; do
  [[ -f "$OUTPUT_DIR/$f.png" ]] || fail "图缺失: $OUTPUT_DIR/$f.png"
done
ok "5 张图就绪（中文字体 PingFang SC）"

# ---- 5. 汇报 ----
step "5/5 汇报（scripts/report.py）"
"$PY" scripts/report.py --data-dir "$DATA_DIR" --output-dir "$OUTPUT_DIR" \
  || fail "report 失败"
[[ -f "$OUTPUT_DIR/report.md" ]] || fail "产物缺失: $OUTPUT_DIR/report.md"
ok "最终报告就绪（夏普对比/最大回撤/类别权重/60-40 对比）"

# ---- 完成 ----
echo ""
echo "🎉 全链路完成！产物清单："
echo "  data/   : $(ls "$DATA_DIR"/*.csv "$DATA_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ') 个文件"
echo "  output/ : $(ls "$OUTPUT_DIR"/*.csv "$OUTPUT_DIR"/*.png "$OUTPUT_DIR"/report.md 2>/dev/null | wc -l | tr -d ' ') 个文件"
echo "  最终报告: $OUTPUT_DIR/report.md"
exit 0
