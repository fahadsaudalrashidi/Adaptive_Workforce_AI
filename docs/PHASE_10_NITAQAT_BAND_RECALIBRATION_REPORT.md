# Nitaqat Band Threshold Recalibration — Flat "Platinum" Fix

Status: **Fixed, researched, tested, live-verified. Zero regressions.**
Not a correctness bug — a resolution/usefulness fix to this module's own
illustrative construction, done with the same citation discipline as the
original Phase 7 work.

---

## 1. New thresholds and reasoning

`backend/core/nitaqat_compliance_engine.py:165-177`:

```python
ILLUSTRATIVE_BAND_THRESHOLDS: dict[str, float] = {
    "Platinum":    75.0,   # was 40.0
    "High Green":  60.0,   # was 30.0
    "Mid Green":   40.0,   # was 20.0
    "Low Green":   20.0,   # was 10.0
    "Red":          0.0,   # unchanged
}
```

**Reproduced the bug first.** Built a 220-employee/9-department fixture
(`nitaqat_realistic_multidept_test_data.csv`) matching the reported shape
— department range 46.7%-75.0%, overall 61.4% (very close to the reported
61.8%). Against the *original* thresholds, every one of the 9 departments
came back `Platinum`, confirming the report exactly.

**Research performed before changing anything** (live web search,
2026-08-07, same discipline as the original Phase 7 investigation):
searched specifically for any newly-published real Saudization
distribution or cut-point data. Checked Saudizationmeter's own Nitaqat
compliance guide and Mercans directly — both confirm the real per-sector
`Required % = m·ln(headcount) + c` cut-points remain unpublished (same
conclusion the Phase 7 investigation already reached; nothing new to cite
here). What the search *did* surface, and is now cited in the module
sources list, is real sector-level Saudization **requirement** data:
engineering 30%, retail 50-70%, healthcare 50-60%, manufacturing 30-50%,
construction 20-40%, procurement 70%, marketing/sales 60%, accounting
40→70% (phased) — via Envoy Global, Motaded, and Middle East Briefing.
This confirms realistic percentages commonly cluster in the 20-70%+ range,
which is exactly why the original 40/30/20/10 spacing (topping out at 40%)
was too coarse.

**Judgment call, disclosed as such:** since no official cut-point table
exists to cite, the specific new numbers (75/60/40/20) are this module's
own construction — chosen as even 20-point spacing across the 20-75% zone
where the cited real data clusters, with Platinum deliberately narrowed to
a genuinely top-tier ≥75% band rather than "anything above 40%" (matching
how the real program treats its highest tier as a minority of
establishments, not a plurality). Band count (5) and the real, cited band
*names* (Platinum/High Green/Mid Green/Low Green/Red) are unchanged.

Module docstring (`nitaqat_compliance_engine.py:33-52`) and the `sources`
list returned in every API response (`nitaqat_compliance_engine.py:408-425`)
both document this reasoning and cite the new sources — same "constructed
heuristic vs. cited fact" discipline as every other honesty-framed figure
this session.

---

## 2. Disclosure text/table

The frontend's "Illustrative band thresholds used" table
(`executive-ui/src/pages/NitaqatComplianceTracker.tsx:373-378`) already
renders dynamically from the API's `band_thresholds_used` field — no
hardcoded percentages exist anywhere in the frontend (confirmed via grep).
**No frontend code change was needed**; the backend constant change alone
updates what's displayed. Confirmed live: the table now reads
`"Platinum ≥ 75% · High Green ≥ 60% · Mid Green ≥ 40% · Low Green ≥ 20% ·
Red ≥ 0%"`.

---

## 3. Tests

`tests/test_nitaqat_compliance_engine.py`:

- **Updated** `test_band_assignment_matches_hand_computation` (6
  parametrized cases) and `test_band_thresholds_are_the_documented_illustrative_values`
  to the new threshold values — these are deliberate, disclosed changes to
  match the new (also deliberate, disclosed) behavior, not regressions.
- **New**: `test_realistic_multidept_fixture_is_not_flat_platinum` —
  asserts the 9-department fixture (46.7%-75.0% range) produces **at least
  3 distinct bands**, directly regression-testing the reported bug.
- **New**: `test_realistic_multidept_fixture_band_assignments_match_new_thresholds`
  — independently recomputes the expected band for every department's
  exact percentage (not calling the engine's own `_band_for_pct()`) and
  asserts an exact match, plus hand-verified spot checks: Procurement
  (46.7%) → Mid Green, Sales (70.0%) → High Green, Operations (75.0%) →
  Platinum.

```
py -m pytest tests/test_nitaqat_compliance_engine.py -v
30 passed   (28 pre-existing/updated + 2 new, zero failures)
```

---

## 4. Full regression suite

```
Before this fix: 39 failed, 1352 passed, 1 skipped
After this fix:  39 failed, 1354 passed, 1 skipped   (+2 new tests)
```

The 39 failures are the same pre-existing, unrelated `passlib`/bcrypt
`MissingBackendError` in `test_phase30_1_security.py`, unchanged in count
since Phase 5. Zero regressions: no other module's tests reference the
changed threshold constants, and none were affected.

---

## 5. Live browser verification

Backend restarted (plain `python backend/api/main.py`, no `--reload` —
confirmed via a direct `curl` to `/api/local/nitaqat-compliance` before
opening the browser, returning `band_thresholds_used: {"Platinum": 75.0,
"High Green": 60.0, "Mid Green": 40.0, "Low Green": 20.0, "Red": 0.0}`).

Uploaded `nitaqat_realistic_multidept_test_data.csv` (220 rows, 9
departments) to the Nitaqat / Saudization page. Playwright, console errors:
**`[]`**.

- Overall: `61.4%` → **`High Green`** (was `Platinum`)
- Department table, now visibly differentiated instead of flat:

| Department | Saudization % | Band (before) | Band (after) |
|---|---|---|---|
| Procurement | 46.7% | Platinum | **Mid Green** |
| Engineering | 50.0% | Platinum | **Mid Green** |
| Marketing | 55.0% | Platinum | **Mid Green** |
| Legal | 56.7% | Platinum | **Mid Green** |
| Human Resources | 59.1% | Platinum | **Mid Green** |
| Finance | 64.3% | Platinum | **High Green** |
| Information Technology | 68.0% | Platinum | **High Green** |
| Sales | 70.0% | Platinum | **High Green** |
| Operations | 75.0% | Platinum | **Platinum** |

3 distinct bands now appear across the realistic range, exactly the goal.
The "illustrative band thresholds used" disclosure box correctly shows the
new numbers, and the sources list shows both new citations (the "no new
cut-point data found" confirmation and the sector-requirement clustering
data). Screenshot: `nitaqat_bands_differentiated.png`.

---

## 6. Files changed

| File | Change |
|---|---|
| `backend/core/nitaqat_compliance_engine.py` | `ILLUSTRATIVE_BAND_THRESHOLDS` recalibrated (`:165-177`); module docstring recalibration note (`:33-52`); `sources` list updated with 2 new citations (`:408-425`). |
| `tests/test_nitaqat_compliance_engine.py` | Updated 2 existing tests to new thresholds; +2 new differentiation tests against the realistic fixture. |
| `nitaqat_realistic_multidept_test_data.csv` | **New** fixture (220 employees, 9 departments, 46.7%-75.0% range). |

No frontend files changed — the disclosure table was already
threshold-agnostic by design.
