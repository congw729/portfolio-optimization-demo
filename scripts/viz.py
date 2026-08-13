#!/usr/bin/env python3
"""P5 可视化：5 张必备图（对照准备清单 v1.1 §5.1）

输出（output/*.png，dpi=150）：
  1. frontier_scatter.png    ① 有效前沿散点图（+蒙特卡洛灰点云 + CML + GMV/切线标注）Demo 主图
  2. weights_bar.png         ② 权重条形图（GMV/切线/中目标收益，按资产类别着色）
  3. drawdown_curve.png      ③ 回撤曲线（切线组合 vs SPY 基准，nav/dd/max_dd，S-1 口径）
  4. correlation_heatmap.png ④ 相关性热力图（升级主图，标注负相关/强正相关）
  5. frontier_compare.png    ⑤ 双前沿对比图（方案 A vs 基线个股）

用法：
    python scripts/viz.py            # 生成全部 5 张图
    python scripts/viz.py --only 1   # 只生成第 1 张

依赖：matplotlib / seaborn / numpy / pandas（P1 已装）
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"
DATA = ROOT / "data"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 全局样式（中文字体 + 统一美观配置）
# ---------------------------------------------------------------------------
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS", "Heiti TC", "Hiragino Sans GB"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False

# 资产类别 → 颜色（图② 按类别着色）
CLASS_COLORS = {
    "equity-us": "#4C72B0",   # 蓝：美股权益
    "bond": "#DD8452",        # 橙：债券
    "gold": "#C44E52",        # 红：黄金
    "equity-em": "#55A868",   # 绿：新兴市场
    "commodity": "#8172B2",   # 紫：商品
}


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------


def load_params(path: Path = DATA / "params.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_portfolios(path: Path = OUT / "portfolios.csv") -> pd.DataFrame:
    return pd.read_csv(path)


def load_frontier(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_returns(path: Path = DATA / "returns_assetclass.csv") -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, parse_dates=True)


def get_combo_weights(portfolios: pd.DataFrame, combo: str) -> np.ndarray:
    row = portfolios[portfolios["combo"] == combo].iloc[0]
    w_cols = [c for c in portfolios.columns if c.startswith("w_")]
    return row[w_cols].to_numpy(dtype=float)


def get_combo_metric(portfolios: pd.DataFrame, combo: str, col: str) -> float:
    row = portfolios[portfolios["combo"] == combo].iloc[0]
    return float(row[col])


# ---------------------------------------------------------------------------
# 图① 有效前沿散点图（Demo 主图）
# ---------------------------------------------------------------------------


def fig_frontier_scatter(params: dict, frontier: pd.DataFrame,
                         portfolios: pd.DataFrame, path: Path) -> None:
    tickers = params["tickers"]
    mu = np.array([params["mu"][t] for t in tickers])
    sigma = np.array([params["sigma"][t] for t in tickers])
    rf = params.get("rf", 0.0)

    # 蒙特卡洛随机组合（灰点云）：dirichlet 生成权重
    rng = np.random.default_rng(42)
    n_sim = 3000
    W = rng.dirichlet(np.ones(len(tickers)), size=n_sim)
    sim_ret = W @ mu
    sim_vol = np.sqrt(np.einsum("ij,jk,ik->i", W, sigma, W))

    fig, ax = plt.subplots(figsize=(10, 7))
    # 灰点云
    ax.scatter(sim_vol, sim_ret, c="0.75", s=6, alpha=0.6,
               label="蒙特卡洛随机组合 (3000)")
    # 有效前沿
    ax.plot(frontier["vol"], frontier["ret"], color="#4C72B0", lw=2.5,
            label="有效前沿（方案 A）")
    ax.scatter(frontier["vol"], frontier["ret"], color="#4C72B0", s=14, zorder=3)

    # GMV / 切线组合（数值禁做空主口径）
    gmv_vol = get_combo_metric(portfolios, "GMV_数值(禁做空)", "vol")
    gmv_ret = get_combo_metric(portfolios, "GMV_数值(禁做空)", "ret")
    tan_vol = get_combo_metric(portfolios, "切线_数值(禁做空)", "vol")
    tan_ret = get_combo_metric(portfolios, "切线_数值(禁做空)", "ret")
    ax.scatter([gmv_vol], [gmv_ret], marker="*", s=260, color="#55A868", zorder=5,
               edgecolor="white", linewidth=1.2, label="最小方差组合 GMV")
    ax.scatter([tan_vol], [tan_ret], marker="*", s=260, color="#C44E52", zorder=5,
               edgecolor="white", linewidth=1.2, label="最大夏普（切线）组合")
    ax.annotate(f"GMV\n({gmv_vol:.1%}, {gmv_ret:.1%})", (gmv_vol, gmv_ret),
                textcoords="offset points", xytext=(12, -14), fontsize=9,
                color="#2d7d3b")
    ax.annotate(f"切线\n({tan_vol:.1%}, {tan_ret:.1%})", (tan_vol, tan_ret),
                textcoords="offset points", xytext=(12, 10), fontsize=9,
                color="#a03336")

    # CML 资本市场线：从 (0, rf) 过切线组合并延长
    if tan_vol > 1e-9:
        slope = (tan_ret - rf) / tan_vol
        x_cml = np.linspace(0, tan_vol * 1.6, 50)
        y_cml = rf + slope * x_cml
        ax.plot(x_cml, y_cml, "--", color="#DD8452", lw=1.8,
                label=f"CML（rf={rf:.2%}）")
    ax.scatter([0], [rf], marker="o", s=40, color="#DD8452", zorder=4)
    ax.annotate(f"rf={rf:.2%}", (0, rf), textcoords="offset points",
                xytext=(8, -2), fontsize=9, color="#a5672f")

    # 单资产点
    single_vol = np.sqrt(np.diag(sigma))
    ax.scatter(single_vol, mu, marker="D", s=60, color="#333333", zorder=4,
               label="单资产")
    for t, v, r in zip(tickers, single_vol, mu):
        ax.annotate(t, (v, r), textcoords="offset points", xytext=(6, 4),
                    fontsize=8.5, color="#333333")

    ax.set_xlabel("年化波动率（标准差）")
    ax.set_ylabel("年化收益")
    ax.set_title("马科维茨有效前沿 — 方案 A（SPY/IWM/TLT/GLD/EEM/DBC）")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[图①] {path}")


# ---------------------------------------------------------------------------
# 图② 权重条形图（按资产类别着色）
# ---------------------------------------------------------------------------


def fig_weights_bar(params: dict, portfolios: pd.DataFrame,
                    frontier: pd.DataFrame, path: Path) -> None:
    tickers = params["tickers"]
    asset_class = params["asset_class"]
    colors = [CLASS_COLORS.get(asset_class.get(t, "equity-us"), "#999999")
              for t in tickers]

    # 三个组合：GMV / 切线 / 中目标收益组合
    combos = [
        ("GMV_数值(禁做空)", "最小方差组合 GMV"),
        ("切线_数值(禁做空)", "最大夏普（切线）"),
    ]
    # 中目标收益组合：取前沿中间点
    mid = frontier.iloc[len(frontier) // 2]
    mid_w = [mid[f"w_{t}"] for t in tickers]
    combos.append((None, f"中目标收益组合（ret={mid['ret']:.1%}）"))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharey=True)
    for ax, (combo, title) in zip(axes, combos):
        if combo:
            w = get_combo_weights(portfolios, combo)
        else:
            w = np.array(mid_w)
        y = np.arange(len(tickers))[::-1]
        bars = ax.barh(y, w, color=colors, edgecolor="white", height=0.62)
        ax.set_yticks(y, tickers, fontsize=9)
        ax.set_xlim(0, 1)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("权重")
        for yi, wi in zip(y, w):
            if wi > 0.02:
                ax.text(wi + 0.015, yi, f"{wi:.1%}", va="center", fontsize=8.5)
    # 类别图例
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in
               list(dict.fromkeys(colors))]
    labels = [f"{t}（{asset_class.get(t)}）" for t in tickers]
    # 按 ticker 顺序的类别色块（去重但保留顺序）
    seen = {}
    for t in tickers:
        c = colors[tickers.index(t)]
        seen.setdefault(c, f"{t}:{asset_class.get(t)}")
    fig.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in seen],
               list(seen.values()), loc="lower center", ncol=len(seen),
               fontsize=8.5, frameon=False)
    fig.suptitle("组合权重对比（按资产类别着色）— 方案 A", y=1.02, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[图②] {path}")


# ---------------------------------------------------------------------------
# 图③ 回撤曲线（切线组合 vs 基准 SPY）
# ---------------------------------------------------------------------------


def fig_drawdown(params: dict, portfolios: pd.DataFrame,
                 returns_df: pd.DataFrame, path: Path) -> None:
    tickers = params["tickers"]
    rf = params.get("rf", 0.0)
    # 切线组合（数值禁做空主口径）
    w = get_combo_weights(portfolios, "切线_数值(禁做空)")
    r_port = returns_df[tickers] @ w
    r_bench = returns_df["SPY"]  # 基准 SPY（与组合同口径，同为方案 A 成员）

    def nav_dd(r: pd.Series):
        nav = (1.0 + r).cumprod()
        dd = nav / nav.cummax() - 1.0
        return nav, dd

    nav_p, dd_p = nav_dd(r_port)
    nav_b, dd_b = nav_dd(r_bench)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})
    ax1.plot(nav_p.index, nav_p.values, color="#C44E52", lw=1.8,
             label=f"切线组合（max_dd={dd_p.min():.1%}）")
    ax1.plot(nav_b.index, nav_b.values, color="#4C72B0", lw=1.5, alpha=0.85,
             label=f"基准 SPY（max_dd={dd_b.min():.1%}）")
    ax1.axhline(1.0, color="gray", lw=0.8, ls=":")
    ax1.set_ylabel("累计净值 nav")
    ax1.set_title("组合 vs 基准（SPY）— 累计净值与回撤（近 5 年日频）")
    ax1.legend(loc="upper left", fontsize=9)

    ax2.fill_between(dd_p.index, dd_p.values, 0, color="#C44E52", alpha=0.45,
                     label=f"切线组合回撤（max {dd_p.min():.1%}）")
    ax2.fill_between(dd_b.index, dd_b.values, 0, color="#4C72B0", alpha=0.35,
                     label=f"SPY 回撤（max {dd_b.min():.1%}）")
    ax2.set_ylabel("回撤 dd")
    ax2.set_xlabel("日期")
    ax2.legend(loc="lower left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[图③] {path}")


# ---------------------------------------------------------------------------
# 图④ 相关性热力图（升级主图）
# ---------------------------------------------------------------------------


def fig_corr_heatmap(returns_df: pd.DataFrame, path: Path) -> None:
    corr = returns_df.corr()
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                vmin=-1, vmax=1, square=True, linewidths=0.6,
                cbar_kws={"shrink": 0.8, "label": "相关系数"}, ax=ax)
    ax.set_title("方案 A 资产收益率相关矩阵 — 负相关与强正相关并存", fontsize=13)

    # 标注关键相关性：负相关（GLD-DBC）与强正相关（SPY-EEM/SPY-TLT）
    n = len(corr)
    annots = []
    pairs = [("GLD", "DBC", "负相关"), ("SPY", "EEM", "强正相关"),
             ("SPY", "TLT", "强正相关")]
    for a, b, tag in pairs:
        if a in corr.index and b in corr.columns:
            v = corr.loc[a, b]
            annots.append((a, b, v, tag))
    # 用方框圈出关键元素
    for a, b, v, tag in annots:
        i, j = corr.index.get_loc(a), corr.columns.get_loc(b)
        color = "#1f7a33" if v < 0 else "#a03336"
        ax.add_patch(plt.Rectangle((j, i), 1, 1, fill=False, edgecolor=color,
                                   lw=2.6))
        ax.text(j + 0.5, i + 0.5, f"{v:.2f}\n{tag}", ha="center", va="center",
                fontsize=8, color=color, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[图④] {path}")


# ---------------------------------------------------------------------------
# 图⑤ 双前沿对比图（方案 A vs 基线个股）
# ---------------------------------------------------------------------------


def fig_frontier_compare(frontier_a: pd.DataFrame,
                         frontier_s: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.plot(frontier_a["vol"], frontier_a["ret"], color="#4C72B0", lw=2.8,
            label="方案 A（跨资产类别 ETF）")
    ax.scatter(frontier_a["vol"], frontier_a["ret"], color="#4C72B0", s=12)
    ax.plot(frontier_s["vol"], frontier_s["ret"], color="#C44E52", lw=2.2,
            ls="--", label="基线（6 只个股）")
    ax.scatter(frontier_s["vol"], frontier_s["ret"], color="#C44E52", s=12)

    # 标注各自 GMV 位置（波动率最低点）
    for fdf, label, color in ((frontier_a, "方案A GMV", "#2d7d3b"),
                              (frontier_s, "基线 GMV", "#a03336")):
        i = int(fdf["vol"].idxmin())
        ax.scatter([fdf.loc[i, "vol"]], [fdf.loc[i, "ret"]], marker="*",
                   s=220, color=color, edgecolor="white", zorder=5)
        ax.annotate(label, (fdf.loc[i, "vol"], fdf.loc[i, "ret"]),
                    textcoords="offset points", xytext=(10, 8), fontsize=9,
                    color=color)

    ax.set_xlabel("年化波动率（标准差）")
    ax.set_ylabel("年化收益")
    ax.set_title("双前沿对比：跨资产类别 ETF vs 个股（资产类别分散 vs 个股分散）")
    ax.legend(loc="upper left", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[图⑤] {path}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="P5 可视化：5 张必备图")
    p.add_argument("--only", type=int, default=0, help="只生成指定图（1-5）")
    args = p.parse_args(argv)

    params = load_params()
    portfolios = load_portfolios()
    frontier_a = load_frontier(OUT / "frontier.csv")
    frontier_s = load_frontier(OUT / "frontier_stocks.csv")
    returns_a = load_returns()

    tasks = {
        1: ("frontier_scatter.png",
            lambda: fig_frontier_scatter(params, frontier_a, portfolios,
                                         OUT / "frontier_scatter.png")),
        2: ("weights_bar.png",
            lambda: fig_weights_bar(params, portfolios, frontier_a,
                                    OUT / "weights_bar.png")),
        3: ("drawdown_curve.png",
            lambda: fig_drawdown(params, portfolios, returns_a,
                                 OUT / "drawdown_curve.png")),
        4: ("correlation_heatmap.png",
            lambda: fig_corr_heatmap(returns_a,
                                     OUT / "correlation_heatmap.png")),
        5: ("frontier_compare.png",
            lambda: fig_frontier_compare(frontier_a, frontier_s,
                                         OUT / "frontier_compare.png")),
    }

    if args.only:
        name, fn = tasks[args.only]
        print(f"== 生成 {name} ==")
        fn()
    else:
        for name, fn in tasks.values():
            fn()
    print("\n[OK] 5 张图全部生成完毕")
    return 0


if __name__ == "__main__":
    sys.exit(main())
