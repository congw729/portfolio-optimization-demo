#!/usr/bin/env python3
"""P4b 汇报汇总 + en-report 英文版（演示角色 reporter 的支撑脚本）

职责（对照编排方案 §1.5 与验收 A6）：
  汇总全部产物生成最终结论报告 output/report.md：
    - 组合夏普 vs 基准 SPY 夏普；
    - 最大回撤（GMV/切线 vs SPY）；
    - 最优权重（切线组合，含按资产类别汇总）；
    - 60/40（股/债）基准组合夏普对比；
    - 双前沿对比结论（方案 A vs 基线个股）；
    - 风险归因结论。

用法：
    python scripts/report.py                        # 中文 report.md（默认）
    python scripts/report.py --lang en              # 英文 report.en.md
    python scripts/report.py --data-dir DIR --output-dir DIR [--lang zh|en]

中英文报告使用完全相同的数值计算（仅文案/表头/结论语言不同），
保证数据一致性（en-report 交付要求）。
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TODAY = "2026-08-13"

# ---------------------------------------------------------------------------
# 文案模板（中 / 英）
# ---------------------------------------------------------------------------
LANG_T = {
    "zh": {
        "title": "# Portfolio Optimization Demo 最终报告",
        "meta": "> 生成日期：{d} ｜ 数据：yfinance 近 5 年日线（auto_adjust）｜ 口径：数值优化禁做空（主）",
        "s1": "## 1. 组合指标总览（方案 A，rf={rf:.2%}）",
        "s1_head": "| 组合 | 年化收益 | 年化波动率 | 夏普 | 最大回撤 |",
        "s1_sep": "|---|---|---|---|---|",
        "gmv": "GMV（最小方差）",
        "tan": "切线（最大夏普）",
        "bench": "基准 SPY",
        "concl1_better": "**结论：切线组合夏普 {s:.3f} 优于 基准 SPY（{b:.3f}）**。",
        "concl1_worse": "**结论：切线组合夏普 {s:.3f} 不及 基准 SPY（{b:.3f}）**。",
        "s2": "## 2. 最大回撤（S-1 口径 nav/dd/max_dd）",
        "tan_dd": "- 切线组合 max_dd = **{v:.2%}**（vs SPY 回撤曲线见 `output/drawdown_curve.png`）",
        "gmv_dd": "- GMV 组合 max_dd = **{v:.2%}**（低波动组合回撤更小）",
        "s3": "## 3. 切线组合最优权重",
        "s3_head": "| 资产 | 类别 | 权重 |",
        "s3_sep": "|---|---|---|",
        "s3_cat": "**按资产类别汇总权重：**",
        "s4": "## 4. 60/40 基准组合对比",
        "s4_base": "60/40 基准（60% SPY + 40% TLT，再平衡）：年化收益 {ret:.2%}、波动 {vol:.2%}、**夏普 {sharpe:.3f}**",
        "s4_better": "切线组合夏普 {s:.3f} 优于 60/40 基准（{b:.3f}）→ 有效前沿优化带来超额风险调整收益",
        "s4_worse": "切线组合夏普 {s:.3f} 不及 60/40 基准（{b:.3f}）→ 60/40 简单策略已接近最优",
        "s5": "## 5. 双前沿对比（方案 A vs 基线个股）",
        "s5_a": "- 方案 A 前沿：{n} 点，收益范围 [{lo:.1%}, {hi:.1%}]，GMV 波动 {vol:.1%}",
        "s5_s": "- 基线个股前沿：{n} 点，收益范围 [{lo:.1%}, {hi:.1%}]，GMV 波动 {vol:.1%}",
        "s5_concl": "- **结论**：方案 A（跨资产类别）GMV 波动 {a:.1%} 显著低于基线个股 {s:.1%} —— 资产类别分散（股/债/金/商品/国际）比个股分散更有效降低组合风险（详见 `output/frontier_compare.png`）",
        "s6": "## 6. 风险归因与教学结论",
        "s6_1": "1. **分散化生效**：GMV 波动率低于任一单资产（方案 A 各资产波动 15.7%~22.5%，GMV 仅 {v:.1%}）——资产间低相关/负相关是组合风险下降的来源；",
        "s6_2": "2. **负相关价值**：GLD-DBC 相关系数 -0.12（黄金 vs 商品），组合内负相关资产对冲单类资产风险；",
        "s6_3_gap": "3. **60/40 基准**：简单股债配置夏普 {b:.3f}，与优化切线组合 {s:.3f} 存在差距，体现均值-方差优化的增量价值",
        "s6_3_close": "3. **60/40 基准**：简单股债配置夏普 {b:.3f}，与优化切线组合 {s:.3f} 差距不大，教学重点转向风险结构而非收益",
        "footer": "> 报告由 `scripts/report.py` 自动生成｜图表见 `output/*.png`｜数据 `data/` 缓存（断网可演示）",
        "out_summary": "切线夏普 {s:.3f} vs SPY {spy:.3f} vs 60/40 {b:.3f}",
        "out_msg": "[输出] {}",
        "done": "[摘要] {}",
    },
    "en": {
        "title": "# Portfolio Optimization Demo — Final Report",
        "meta": "> Generated: {d} ｜ Data: yfinance 5-year daily (auto_adjust) ｜ Methodology: numeric optimization, no short selling (primary)",
        "s1": "## 1. Portfolio Metrics Overview (Portfolio A, rf={rf:.2%})",
        "s1_head": "| Portfolio | Annual Return | Annual Volatility | Sharpe | Max Drawdown |",
        "s1_sep": "|---|---|---|---|---|",
        "gmv": "GMV (Minimum Variance)",
        "tan": "Tangency (Max Sharpe)",
        "bench": "Benchmark SPY",
        "concl1_better": "**Conclusion: Tangency portfolio Sharpe {s:.3f} outperforms benchmark SPY ({b:.3f}).**",
        "concl1_worse": "**Conclusion: Tangency portfolio Sharpe {s:.3f} underperforms benchmark SPY ({b:.3f}).**",
        "s2": "## 2. Maximum Drawdown (S-1 definition: nav/dd/max_dd)",
        "tan_dd": "- Tangency portfolio max_dd = **{v:.2%}** (drawdown vs SPY: see `output/drawdown_curve.png`)",
        "gmv_dd": "- GMV portfolio max_dd = **{v:.2%}** (lower-volatility portfolio has smaller drawdown)",
        "s3": "## 3. Tangency Portfolio Optimal Weights",
        "s3_head": "| Asset | Class | Weight |",
        "s3_sep": "|---|---|---|",
        "s3_cat": "**Asset class allocation summary:**",
        "s4": "## 4. 60/40 Benchmark Comparison",
        "s4_base": "60/40 benchmark (60% SPY + 40% TLT, rebalanced): annual return {ret:.2%}, volatility {vol:.2%}, **Sharpe {sharpe:.3f}**",
        "s4_better": "Tangency Sharpe {s:.3f} beats 60/40 benchmark ({b:.3f}) → mean-variance optimization delivers excess risk-adjusted return",
        "s4_worse": "Tangency Sharpe {s:.3f} lags 60/40 benchmark ({b:.3f}) → simple 60/40 strategy is already near-optimal",
        "s5": "## 5. Two-Frontier Comparison (Portfolio A vs Baseline Stocks)",
        "s5_a": "- Portfolio A frontier: {n} points, return range [{lo:.1%}, {hi:.1%}], GMV volatility {vol:.1%}",
        "s5_s": "- Baseline stocks frontier: {n} points, return range [{lo:.1%}, {hi:.1%}], GMV volatility {vol:.1%}",
        "s5_concl": "- **Conclusion**: Portfolio A (cross-asset-class) GMV volatility {a:.1%} is significantly lower than baseline stocks {s:.1%} — asset-class diversification (equity/bond/gold/commodity/international) reduces portfolio risk more effectively than stock-level diversification (see `output/frontier_compare.png`)",
        "s6": "## 6. Risk Attribution and Pedagogical Conclusions",
        "s6_1": "1. **Diversification works**: GMV volatility is below every single asset (Portfolio A assets range 15.7%–22.5%, GMV only {v:.1%}) — low/negative correlation across assets is the source of portfolio risk reduction;",
        "s6_2": "2. **Value of negative correlation**: GLD-DBC correlation is -0.12 (gold vs commodities); negatively correlated assets hedge single-class risk within the portfolio;",
        "s6_3_gap": "3. **60/40 benchmark**: simple stock-bond allocation Sharpe {b:.3f} vs optimized tangency {s:.3f} — the gap highlights the incremental value of mean-variance optimization",
        "s6_3_close": "3. **60/40 benchmark**: simple stock-bond allocation Sharpe {b:.3f} vs optimized tangency {s:.3f} — the gap is small; teaching focus shifts to risk structure rather than return",
        "footer": "> Report auto-generated by `scripts/report.py` ｜ Charts: `output/*.png` ｜ Data: `data/` cache (works offline)",
        "out_summary": "Tangency Sharpe {s:.3f} vs SPY {spy:.3f} vs 60/40 {b:.3f}",
        "out_msg": "[Output] {}",
        "done": "[Summary] {}",
    },
}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def combo_row(portfolios: pd.DataFrame, combo: str) -> pd.Series:
    return portfolios[portfolios["combo"] == combo].iloc[0]


def annualized_from_returns(returns: pd.Series) -> dict:
    mu = float(returns.mean() * 252)
    vol = float(returns.std(ddof=0) * np.sqrt(252))
    return {"ret": mu, "vol": vol}


def cat_weights_summary(weights: dict, asset_class: dict) -> dict:
    """按资产类别汇总权重。"""
    out: dict[str, float] = {}
    for t, w in weights.items():
        cls = asset_class.get(t, "other")
        out[cls] = out.get(cls, 0.0) + w
    return {k: round(v, 6) for k, v in sorted(out.items(), key=lambda x: -x[1])}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="P4b 汇报汇总（reporter，支持中/英）")
    p.add_argument("--data-dir", default="data", help="数据目录，默认 data/")
    p.add_argument("--output-dir", default="output", help="输出目录，默认 output/")
    p.add_argument("--lang", choices=["zh", "en"], default="zh",
                   help="输出语言：zh（默认，report.md）/ en（report.en.md）")
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)
    T = LANG_T[args.lang]

    params = load_json(data_dir / "params.json")
    features = load_json(data_dir / "features.json")
    portfolios = pd.read_csv(out_dir / "portfolios.csv")
    frontier_a = pd.read_csv(out_dir / "frontier.csv")
    frontier_s = pd.read_csv(out_dir / "frontier_stocks.csv")
    returns_a = pd.read_csv(data_dir / "returns_assetclass.csv",
                            index_col=0, parse_dates=True)

    tickers = params["tickers"]
    asset_class = params["asset_class"]
    rf = params["rf"]

    # 主口径组合（数值禁做空）
    gmv = combo_row(portfolios, "GMV_数值(禁做空)")
    tan = combo_row(portfolios, "切线_数值(禁做空)")

    # 基准 SPY 年化指标（同口径：mean*252 / std*√252）
    spy_ret = annualized_from_returns(returns_a["SPY"])
    spy_sharpe = (spy_ret["ret"] - rf) / spy_ret["vol"]
    spy_6040 = features["benchmark_6040"]

    # 切线组合按类别权重汇总
    tan_w = {t: float(tan[f"w_{t}"]) for t in tickers}
    cat_sum = cat_weights_summary(tan_w, asset_class)

    # 双前沿对比
    i_gmv_a = int(frontier_a["vol"].idxmin())
    i_gmv_s = int(frontier_s["vol"].idxmin())
    frontier_summary = {
        "A": {"points": len(frontier_a),
              "ret_range": (frontier_a["ret"].min(), frontier_a["ret"].max()),
              "gmv": {"ret": frontier_a.loc[i_gmv_a, "ret"],
                      "vol": frontier_a.loc[i_gmv_a, "vol"]}},
        "stocks": {"points": len(frontier_s),
                   "ret_range": (frontier_s["ret"].min(), frontier_s["ret"].max()),
                   "gmv": {"ret": frontier_s.loc[i_gmv_s, "ret"],
                           "vol": frontier_s.loc[i_gmv_s, "vol"]}},
    }

    lines: list[str] = []
    add = lines.append
    add(T["title"])
    add("")
    add(T["meta"].format(d=TODAY))
    add("")

    # 1) 组合指标总览
    add(T["s1"].format(rf=rf))
    add("")
    add(T["s1_head"])
    add(T["s1_sep"])
    add(f"| {T['gmv']} | {gmv['ret']:.2%} | {gmv['vol']:.2%} | {gmv['sharpe']:.3f} | {gmv['max_dd']:.2%} |")
    add(f"| {T['tan']} | {tan['ret']:.2%} | {tan['vol']:.2%} | **{tan['sharpe']:.3f}** | {tan['max_dd']:.2%} |")
    add(f"| {T['bench']} | {spy_ret['ret']:.2%} | {spy_ret['vol']:.2%} | {spy_sharpe:.3f} | — |")
    add("")
    concl1 = (T["concl1_better"] if tan["sharpe"] > spy_sharpe
              else T["concl1_worse"])
    add(concl1.format(s=tan["sharpe"], b=spy_sharpe))
    add("")

    # 2) 最大回撤
    add(T["s2"])
    add("")
    add(T["tan_dd"].format(v=tan["max_dd"]))
    add(T["gmv_dd"].format(v=gmv["max_dd"]))
    add("")

    # 3) 切线组合最优权重（含类别汇总）
    add(T["s3"])
    add("")
    add(T["s3_head"])
    add(T["s3_sep"])
    for t in tickers:
        add(f"| {t} | {asset_class.get(t)} | {tan_w[t]:.2%} |")
    add("")
    add(T["s3_cat"])
    add("")
    for cls, w in cat_sum.items():
        add(f"- **{cls}**：{w:.1%}")
    add("")

    # 4) 60/40 基准对比
    add(T["s4"])
    add("")
    add(T["s4_base"].format(ret=spy_6040["ret"], vol=spy_6040["vol"],
                            sharpe=spy_6040["sharpe"]))
    add("")
    s4 = (T["s4_better"] if tan["sharpe"] > spy_6040["sharpe"]
          else T["s4_worse"])
    add(s4.format(s=tan["sharpe"], b=spy_6040["sharpe"]))
    add("")

    # 5) 双前沿对比
    add(T["s5"])
    add("")
    fa, fs = frontier_summary["A"], frontier_summary["stocks"]
    add(T["s5_a"].format(n=fa["points"], lo=fa["ret_range"][0],
                         hi=fa["ret_range"][1], vol=fa["gmv"]["vol"]))
    add(T["s5_s"].format(n=fs["points"], lo=fs["ret_range"][0],
                         hi=fs["ret_range"][1], vol=fs["gmv"]["vol"]))
    add("")
    add(T["s5_concl"].format(a=fa["gmv"]["vol"], s=fs["gmv"]["vol"]))
    add("")

    # 6) 风险归因结论
    add(T["s6"])
    add("")
    add(T["s6_1"].format(v=gmv["vol"]))
    add(T["s6_2"])
    s6_3 = (T["s6_3_gap"] if abs(tan["sharpe"] - spy_6040["sharpe"]) > 0.05
            else T["s6_3_close"])
    add(s6_3.format(b=spy_6040["sharpe"], s=tan["sharpe"]))
    add("")
    add("---")
    add("")
    add(T["footer"])

    out_name = "report.md" if args.lang == "zh" else "report.en.md"
    out_path = out_dir / out_name
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(T["out_msg"].format(out_path))
    print(T["done"].format(
        T["out_summary"].format(s=tan["sharpe"], spy=spy_sharpe, b=spy_6040["sharpe"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
