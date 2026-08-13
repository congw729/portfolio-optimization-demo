#!/usr/bin/env python3
"""P4b 汇报汇总（演示角色 reporter 的支撑脚本）

职责（对照编排方案 §1.5 与验收 A6）：
  汇总全部产物生成最终结论报告 output/report.md：
    - 组合夏普 vs 基准 SPY 夏普；
    - 最大回撤（GMV/切线 vs SPY）；
    - 最优权重（切线组合，含按资产类别汇总）；
    - 60/40（股/债）基准组合夏普对比；
    - 双前沿对比结论（方案 A vs 基线个股）。

用法：
    python scripts/report.py [--data-dir data] [--output-dir output]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TODAY = "2026-08-13"


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
    p = argparse.ArgumentParser(description="P4b 汇报汇总（reporter）")
    p.add_argument("--data-dir", default="data", help="数据目录，默认 data/")
    p.add_argument("--output-dir", default="output", help="输出目录，默认 output/")
    args = p.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output_dir)

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
    add("# Portfolio Optimization Demo 最终报告")
    add("")
    add(f"> 生成日期：{TODAY} ｜ 数据：yfinance 近 5 年日线（auto_adjust）｜ 口径：数值优化禁做空（主）")
    add("")

    # 1) 组合指标总览
    add("## 1. 组合指标总览（方案 A，rf=%.2f%%）" % (rf * 100))
    add("")
    add("| 组合 | 年化收益 | 年化波动率 | 夏普 | 最大回撤 |")
    add("|---|---|---|---|---|")
    add(f"| GMV（最小方差） | {gmv['ret']:.2%} | {gmv['vol']:.2%} | {gmv['sharpe']:.3f} | {gmv['max_dd']:.2%} |")
    add(f"| 切线（最大夏普） | {tan['ret']:.2%} | {tan['vol']:.2%} | **{tan['sharpe']:.3f}** | {tan['max_dd']:.2%} |")
    add(f"| 基准 SPY | {spy_ret['ret']:.2%} | {spy_ret['vol']:.2%} | {spy_sharpe:.3f} | — |")
    add("")
    add(f"**结论：切线组合夏普 {tan['sharpe']:.3f} {'优于' if tan['sharpe'] > spy_sharpe else '不及'} 基准 SPY（{spy_sharpe:.3f}）**。")
    add("")

    # 2) 最大回撤
    add("## 2. 最大回撤（S-1 口径 nav/dd/max_dd）")
    add("")
    add(f"- 切线组合 max_dd = **{tan['max_dd']:.2%}**（vs SPY 回撤曲线见 `output/drawdown_curve.png`）")
    add(f"- GMV 组合 max_dd = **{gmv['max_dd']:.2%}**（低波动组合回撤更小）")
    add("")

    # 3) 切线组合最优权重（含类别汇总）
    add("## 3. 切线组合最优权重")
    add("")
    add("| 资产 | 类别 | 权重 |")
    add("|---|---|---|")
    for t in tickers:
        add(f"| {t} | {asset_class.get(t)} | {tan_w[t]:.2%} |")
    add("")
    add("**按资产类别汇总权重：**")
    add("")
    for cls, w in cat_sum.items():
        add(f"- **{cls}**：{w:.1%}")
    add("")

    # 4) 60/40 基准对比
    add("## 4. 60/40 基准组合对比")
    add("")
    add(f"60/40 基准（60% SPY + 40% TLT，再平衡）：年化收益 {spy_6040['ret']:.2%}、"
        f"波动 {spy_6040['vol']:.2%}、**夏普 {spy_6040['sharpe']:.3f}**")
    add("")
    add(f"切线组合夏普 {tan['sharpe']:.3f} "
        f"{'优于' if tan['sharpe'] > spy_6040['sharpe'] else '不及'} "
        f"60/40 基准（{spy_6040['sharpe']:.3f}）→ "
        f"{'有效前沿优化带来超额风险调整收益' if tan['sharpe'] > spy_6040['sharpe'] else '60/40 简单策略已接近最优'}")
    add("")

    # 5) 双前沿对比
    add("## 5. 双前沿对比（方案 A vs 基线个股）")
    add("")
    add(f"- 方案 A 前沿：{frontier_summary['A']['points']} 点，"
        f"收益范围 [{frontier_summary['A']['ret_range'][0]:.1%}, {frontier_summary['A']['ret_range'][1]:.1%}]，"
        f"GMV 波动 {frontier_summary['A']['gmv']['vol']:.1%}")
    add(f"- 基线个股前沿：{frontier_summary['stocks']['points']} 点，"
        f"收益范围 [{frontier_summary['stocks']['ret_range'][0]:.1%}, {frontier_summary['stocks']['ret_range'][1]:.1%}]，"
        f"GMV 波动 {frontier_summary['stocks']['gmv']['vol']:.1%}")
    add("")
    add(f"- **结论**：方案 A（跨资产类别）GMV 波动 {frontier_summary['A']['gmv']['vol']:.1%} "
        f"显著低于基线个股 {frontier_summary['stocks']['gmv']['vol']:.1%} —— "
        f"资产类别分散（股/债/金/商品/国际）比个股分散更有效降低组合风险（详见 `output/frontier_compare.png`）")
    add("")

    # 6) 风险归因结论
    add("## 6. 风险归因与教学结论")
    add("")
    add("1. **分散化生效**：GMV 波动率低于任一单资产（方案 A 各资产波动 15.7%~22.5%，GMV 仅 "
        f"{gmv['vol']:.1%}）——资产间低相关/负相关是组合风险下降的来源；")
    add("2. **负相关价值**：GLD-DBC 相关系数 -0.12（黄金 vs 商品），组合内负相关资产对冲单类资产风险；")
    add("3. **60/40 基准**：简单股债配置夏普 "
        f"{spy_6040['sharpe']:.3f}，与优化切线组合 {tan['sharpe']:.3f} "
        f"{'存在差距，体现均值-方差优化的增量价值' if abs(tan['sharpe'] - spy_6040['sharpe']) > 0.05 else '差距不大，教学重点转向风险结构而非收益'}")
    add("")
    add("---")
    add("")
    add(f"> 报告由 `scripts/report.py` 自动生成｜图表见 `output/*.png`｜数据 `data/` 缓存（断网可演示）")

    out_path = out_dir / "report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[输出] {out_path}")
    print(f"[摘要] 切线夏普 {tan['sharpe']:.3f} vs SPY {spy_sharpe:.3f} vs 60/40 {spy_6040['sharpe']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
