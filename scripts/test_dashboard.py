#!/usr/bin/env python3
"""P5b 交互式展示网页验证脚本（纯 assert 实现，无 pytest 依赖）

覆盖设计方案 §5 验收要点：
  D1 数据正确性快检：网页消费文件存在且关键值符合预期
     - portfolios.csv 含 GMV/切线行（方案 A 与基线）
     - features.json 有 corr 与 benchmark_6040
     - extensions_summary.csv 含风险平价/BL/蒙特卡洛行
     - mc_points.csv 行数 ≥ 5000
  D2 页面可运行性：AppTest 加载 app/Home.py 与 6 个页面均无异常
     （模拟 streamlit 脚本执行，捕获 exception）

用法：
    python scripts/test_dashboard.py

退出码：0 = 全部通过；1 = 存在失败断言。
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"

PASSED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        raise AssertionError(f"[FAIL] {name} {detail}")
    PASSED.append(name)
    print(f"  [PASS] {name}")


# ---------------------------------------------------------------------------
# D1 数据正确性快检
# ---------------------------------------------------------------------------


def test_data_snapshot() -> None:
    print("== D1 数据正确性快检 ==")
    data, out = ROOT / "data", ROOT / "output"

    # portfolios.csv 含 GMV/切线行（方案 A）
    pf_a = pd.read_csv(out / "portfolios.csv")
    check("portfolios.csv 含 GMV 行", "GMV (no short)" in pf_a["combo"].values)
    check("portfolios.csv 含切线行", "Tangency (no short)" in pf_a["combo"].values)

    # portfolios_stocks.csv（基线）
    pf_s = pd.read_csv(out / "portfolios_stocks.csv")
    check("portfolios_stocks.csv 含 GMV/切线行",
          "GMV (no short)" in pf_s["combo"].values
          and "Tangency (no short)" in pf_s["combo"].values)

    # features.json 有 corr 与 benchmark_6040
    feats = json.load(open(data / "features.json", encoding="utf-8"))
    check("features.json 含 corr", "corr" in feats)
    check("features.json 含 benchmark_6040", "benchmark_6040" in feats)
    check("features.json corr 含 EEM-DBC 负相关",
          feats["corr"]["EEM"]["DBC"] < 0, f"ρ={feats['corr']['EEM']['DBC']:.3f}")

    # extensions_summary.csv 含风险平价/BL/蒙特卡洛行
    ext = pd.read_csv(out / "extensions_summary.csv")
    combos = set(ext["combo"].tolist())
    check("extensions_summary.csv 含风险平价",
          any("Risk Parity" in c for c in combos))
    check("extensions_summary.csv 含 BL", any("BL" in c for c in combos))
    check("extensions_summary.csv 含蒙特卡洛",
          any("Monte Carlo" in c for c in combos))

    # mc_points.csv 行数 ≥ 5000
    mc = pd.read_csv(out / "mc_points.csv")
    check("mc_points.csv 行数 ≥ 5000", len(mc) >= 5000, f"n={len(mc)}")

    # 关键数值抽查（W3：①页卡片与 portfolios.csv 一致）
    gmv = pf_a[pf_a["combo"] == "GMV (no short)"].iloc[0]
    tan = pf_a[pf_a["combo"] == "Tangency (no short)"].iloc[0]
    check("GMV ret ≈ 6.07%", abs(gmv["ret"] - 0.0607) < 0.001, f"ret={gmv['ret']:.4f}")
    check("切线 ret ≈ 16.82%", abs(tan["ret"] - 0.1682) < 0.001, f"ret={tan['ret']:.4f}")
    check("切线 sharpe ≈ 0.999", abs(tan["sharpe"] - 0.999) < 0.01, f"sharpe={tan['sharpe']:.4f}")


# ---------------------------------------------------------------------------
# D2 页面可运行性（AppTest 加载）
# ---------------------------------------------------------------------------


def test_pages_run() -> None:
    print("== D2 页面可运行性（AppTest）==")
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError as e:  # pragma: no cover
        print(f"  [SKIP] streamlit.testing 不可用: {e}")
        return

    pages = [
        APP / "Home.py",
        APP / "pages" / "1_Overview.py",
        APP / "pages" / "2_Efficient_Frontier.py",
        APP / "pages" / "3_Weights.py",
        APP / "pages" / "4_Nav_Drawdown.py",
        APP / "pages" / "5_Correlation.py",
        APP / "pages" / "6_Extensions.py",
        APP / "pages" / "7_Agent_Workflow.py",
    ]
    for p in pages:
        at = AppTest.from_file(str(p), default_timeout=30)
        at.run()
        # AppTest 将异常记录在 at.exception 中
        if at.exception:
            msg = str(at.exception[0]) if at.exception else "unknown"
            check(f"{p.name} 无异常", False, msg)
        else:
            check(f"{p.name} 无异常", True)
            # 输出页面标题/卡片数等概要信息
            n_metric = len(at.metric)
            n_plotly = len(at.get("plotly_chart"))
            print(f"      页面元素: metric×{n_metric}, plotly_chart×{n_plotly}")


def main() -> int:
    test_data_snapshot()
    print()
    test_pages_run()
    print()
    print(f"=== 全部通过：{len(PASSED)} 项断言 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
