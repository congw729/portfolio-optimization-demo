# Dashboard Case Studies

> Seven real bugs found and fixed while building this demo. Each case follows the structure **Symptom → Root cause → Why the tests missed it → Lesson → Fix**, and is meant as teaching material on "building web apps with collaborating agents".
>
> Scope: `app/` (Streamlit frontend), `scripts/` (tests), `output/` (shared artifacts).

## Background: why these bugs cluster together

The demo's architecture is **"scripts produce shared files (CSV/JSON) → the frontend consumes them read-only"**. This "artifacts-as-interface" design decouples components, but when the **interface contract does not explicitly declare which fields are optional vs. required, or global vs. per-pool**, downstream consumers break on their own assumptions. CS-1, CS-4, CS-6 and CS-7 are all of this kind; CS-2, CS-3 and CS-5 expose separate blind spots around caching, UI branches, and cross-page state.

---

## CS-1 Missing shared-artifact field → Baseline crashes with `KeyError: 'mc'`

- **Symptom**: switching Asset Pool to "Baseline (6 Stocks)" on Overview / Efficient Frontier / Weights / Correlation / NAV & Drawdown all raise `KeyError: 'mc'`.
- **Root cause**: in `app/utils.py`, the `"Baseline (6 Stocks)"` entry in `POOLS` has no `"mc"` key (Monte Carlo only applies to Portfolio A), but `load_pool()` accesses it unconditionally:
  ```python
  mc = pd.read_csv(p["mc"]) if p["mc"].exists() else pd.DataFrame()
  ```
- **Why the tests missed it**: `test_dashboard.py` only calls `at.run()` once against the default pool (Portfolio A, listed first); it never exercised the "switch the selectbox" branch.
- **Lesson**: shared artifacts must **declare optional fields explicitly**; consumers should use `.get()` for optional fields instead of hard `p["key"]` access.
- **Fix**: `p["mc"]` → `p.get("mc")`, plus a new `test_baseline_pool()` regression test that switches to Baseline.

## CS-2 `st.cache_data` does not invalidate when the underlying file changes

- **Symptom**: after regenerating `output/*.csv`, pages still read stale data (e.g. Weights reports "Weights not found" because the cache still holds old Chinese combo names while the code now looks up English names).
- **Root cause**: `load_pool` / `load_features` / `load_report_lines` use `@st.cache_data`, whose cache key depends only on function arguments — it does **not** watch the mtime of the underlying CSV/JSON files.
- **Lesson**: after regenerating data artifacts you must **Clear cache / restart Streamlit**; caching is an optimization, not a data source.
- **Fix**: recorded as a gotcha (documentation) rather than a hard bug; to auto-invalidate, include file mtime in the cache key.

## CS-3 Wrong color mapping → `ValueError`

- **Symptom**: on the Extensions page, choosing "Risk Contribution Bars" raises `ValueError: Invalid element(s) received for the 'color' property ... ['equity-us', 'equity-us', 'bond', ...]`.
- **Root cause**: `app/pages/6_Extensions.py` passes asset-class strings directly as colors:
  ```python
  marker=dict(color=[asset_class.get(t, "#999999") for t in rc_tickers])
  ```
  `asset_class.get(t)` returns a class label like `"equity-us"`, not a color; it needs one more `CLASS_COLORS` mapping layer, and the file was missing `import CLASS_COLORS`.
- **Why the tests missed it**: the D2 test only ran the default "Metrics table" dimension, never "Risk Contribution Bars".
- **Lesson**: (1) test every dropdown/dimension branch; (2) respect value levels — `ticker → asset_class → color` is three layers, don't skip one.
- **Fix**: add `from utils import CLASS_COLORS` and use `CLASS_COLORS.get(asset_class.get(t, "equity-us"), "#999999")`.

## CS-4 Baseline shows the wrong 60/40 benchmark

- **Symptom**: on Baseline, the Overview "60/40 Benchmark (SPY+TLT)" card still shows Portfolio A's numbers (ret≈13.9%, Sharpe≈0.62), even though Baseline is 6 stocks with no SPY/TLT.
- **Root cause**: `b6040_metrics()` unconditionally reads the global `features.json` `benchmark_6040` (Portfolio A's SPY+TLT), without checking whether the current pool even contains SPY/TLT.
- **Lesson**: **global artifacts ≠ applicable to every pool**; judge applicability per pool and return NaN when not applicable.
- **Fix**: call `benchmark_6040_returns()` first — it returns `None` for pools without SPY/TLT — and return all-NaN in that case.

## CS-5 Cross-page `session_state` contract break

- **Symptom**: Weights' "Custom γ (linked to Page 2)" always uses the default γ=5.0 / no_short=True, never the γ dragged on Page 2.
- **Root cause**: Page 2's `gamma` slider and `no_short` checkbox have **no `key=`**, while Page 3 reads `st.session_state.get("gamma")` / `["no_short"]`. Without an explicit `key`, a widget's state is not stored under `session_state["gamma"]`.
- **Lesson**: when sharing state across pages, widgets must set an explicit `key=`, and both sides must use the same name — this is also a "cross-component contract".
- **Fix**: add `key="gamma"` / `key="no_short"` to the Page 2 widgets.

## CS-6 Copy vs. data drift

- **Symptom**: the Correlation page says "SPY-TLT +0.68", but `data/features.json` measures SPY-TLT=0.166; and `pos_pairs` marks SPY-EEM / SPY-TLT (≈0.17) as "strong positive", while the real strong pair is SPY-IWM=0.85.
- **Root cause**: correlation values changed after re-fetching data, but the copy and hard-coded annotations were not updated.
- **Lesson**: **after re-running data, grep every place that quotes the number**; numbers hard-coded in prose drift the most.
- **Fix**: update docstring/caption to `SPY-IWM +0.85`, `pos_pairs` to `("SPY", "IWM")`, and "stocks and bonds" → "equities".

## CS-7 `sigma` structure index error (only hit on the Baseline branch)

- **Symptom**: Correlation on Baseline raises `TypeError: list indices must be integers or slices, not str`.
- **Root cause**: `params["sigma"]` is `{ticker: one-dimensional row vector}` (produced by `{k: list(v) for k, v in sigma.items()}` in `fetch_data.py`), but the sigma derivation wrote:
  ```python
  s = np.array([[params["sigma"][a][b] for b in tickers] for a in tickers])
  ```
  `params["sigma"][a][b]` indexes a 1-D list with a ticker string.
- **Why the tests missed it**: Portfolio A reads corr directly from `features.json`, so this branch never ran; only Baseline (or a missing `features.json`) reaches it — again, an uncovered alternate branch.
- **Lesson**: **cover branch code**; before reading someone else's data structure, confirm whether it is 1-D or 2-D.
- **Fix**: `s = np.array([params["sigma"][a] for a in tickers])` (stack each row into an n×n matrix).

---

## Common lessons

1. **Test parameter switches / alternate branches, not just the default path** — CS-1, CS-3, CS-7 all slipped through for this reason.
2. **Shared artifacts and cross-component state need explicit contracts** — declare optional fields, use explicit widget `key`s — CS-1, CS-4, CS-5.
3. **Don't hard-code numbers in prose; re-check references after regenerating data** — CS-2, CS-6.
4. **Confirm data-structure dimensionality before reading; use `.get()` on the consumer side** — CS-1, CS-7.

---

## Proposed solution: add a `tester` role

All seven cases share one meta-cause: **no one systematically owns quality**. The `leader` was supposed to "verify", but in practice verification meant eyeballing artifacts rather than running tests — so untested branches (Baseline, alternate dimensions, cross-page state) silently rotted.

The recommended fix is to split acceptance out of the leader and give it to a dedicated **tester** role.

| Item | Design |
|---|---|
| Role | `tester` |
| Duty | Own acceptance: define criteria → write/run tests → **accept or reject** each artifact → produce a test report |
| Scripts | `scripts/test_optimizer.py` / `test_extensions.py` / `test_dashboard.py` |
| Output | test report + reject feedback (rejected artifacts go back to the responsible agent) |
| Gate position | after T3 (optimizer) and T5 (reporter); a failure rejects back to that agent |
| Knowledge source | this `case-studies/` folder — each case becomes a regression test |

The role closes a learning loop:

```
tester distills acceptance criteria from case-studies
   → encodes them into scripts/test_*.py
   → runs them as a gate
   → new bugs get documented back into case-studies
```

This turns quality from an afterthought into a first-class agent responsibility — and is itself a teachable point on "shift-left testing" and "learning from incidents" inside a multi-agent workflow.

---

> Regression test: `scripts/test_dashboard.py` D3 `test_baseline_pool()` (switches to Baseline across 5 pages). All 7 cases are fixed and tests pass.
