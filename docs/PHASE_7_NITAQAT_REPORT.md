# Phase 7 Report — Nitaqat/Saudization Premium Fix + Full Compliance Module

Date: 2026-08-06
Scope: two parts, per `NITAQAT_COMPLIANCE_INVESTIGATION.md`'s findings. Part A fixes a live, uncited, internally-inconsistent financial constant. Part B builds a genuinely new, honestly-labeled illustrative Saudization/Nitaqat estimate module — the sixth new live module built this session, and the first to carry an explicit "not an official determination" framing throughout, since compliance-adjacent claims carry real legal/reputational risk if presented as more authoritative than they are.

**Verification method:** direct code inspection (file:line citations), real computed-value tests (25 new tests across both parts), a full regression run before and after, and a live Playwright browser session against the actual running backend + Vite dev server for both required scenarios, screenshots taken, console errors checked, plus direct API-response inspection for Part A (not just code reading, per instruction).

---

## Part A — Uncited Nitaqat premium constant: fixed, not removed

### Root cause (confirmed via live web search before fixing, not fabricated)

`financial_intelligence_engine.py:171-172` (pre-fix): `NITAQAT_PREMIUM_LOW/HIGH = 0.18/0.35`, applied inside `executive_roi_engine.py:314-315` and reaching the live product via `local_analysis_routes.py:1065` → three response-shape branches (`:1096,1114,1161`) — confirmed transmitted in the JSON payload but never rendered by any `executive-ui` component. **No citation existed anywhere** for this figure. A second, different, also-uncited guess ("15-30%") existed independently in `roi_estimation_engine.py:246` for the identical claimed concept.

Two independent live web searches (query 1: "Saudization Nitaqat compliance cost premium percentage recruitment replacement cost study report"; query 2: `"cost of Saudization" OR "Nitaqat compliance cost" academic study percentage HRDF report`) both concluded explicitly: **"there is no universal Saudization cost or universal timeframe"** — Saudization cost varies by sector/role scarcity/company size, and HRDF wage subsidies (30-75% of a new Saudi hire's salary) often make the true net cost *lower* than commonly assumed, undermining the very premise of a flat "premium." No citable source was reused, per instruction.

### Fix

- **`financial_intelligence_engine.py:154-176`**: `NITAQAT_PREMIUM_LOW/HIGH` retained as an internal illustrative heuristic (removing the number entirely would have been more disruptive to `executive_roi_engine.py`'s existing cost-range output than honestly labeling it), but now paired with two new constants: `NITAQAT_PREMIUM_CONFIDENCE = "uncalibrated_generic_estimate"` (`:173`) — reusing the exact string already established for `SECTOR_BENCHMARK_CONFIDENCE`, per instruction — and `NITAQAT_PREMIUM_DISCLAIMER` (`:174-181`), a full-sentence honesty note documenting the search finding.
- **`executive_roi_engine.py`**: new `nitaqat_premium_confidence: str` field on `ExecutiveROIResult` (`:142`), always set to the confidence constant (`:407`), serialized in `executive_roi_to_dict()` (`:428`). The governance-note text itself (`:372`, what a report reader actually sees) now reads *"an ILLUSTRATIVE, uncalibrated Nitaqat compliance premium estimate... not sourced to a specific published study"* rather than presenting the number as plain fact.
- **`roi_estimation_engine.py:244-254`** (already-dead module, per `PHASE_4_MODULES_REPORT.md:37`): the inconsistent "15-30%" text was **corrected to match the single canonical uncalibrated estimate** rather than silently left wrong — chosen over a bare "this is dead" comment because leaving two different fabricated numbers in the codebase (one live, one dead-but-discoverable) is worse than fixing both, and the edit cost was identical either way.

### Tests

Appended to `tests/test_phase28_enterprise_transformation.py` — 3 new tests: `test_nitaqat_premium_always_carries_confidence_label` (asserts both the dataclass field and the serialized dict always carry `"uncalibrated_generic_estimate"`), `test_nitaqat_premium_governance_note_says_illustrative_not_sourced` (asserts the actual report text, not just a hidden field, calls it illustrative), `test_nitaqat_premium_disclaimer_constant_exists_and_is_honest`. **52/52 passed** in that file after the change.

### Live verification (API response, not just code reading)

```
POST /api/local/upload/analyze-with-employees  (test_employee_data.csv)
executive_roi.nitaqat_premium_low_sar:    113098.0
executive_roi.nitaqat_premium_high_sar:   431256.0
executive_roi.nitaqat_premium_confidence: "uncalibrated_generic_estimate"
```
Confirmed via live `curl` against the running backend — the confidence label now travels with the figure in the real, live JSON response every time.

---

## Part B — New module: Nitaqat / Saudization Compliance (illustrative)

### Non-negotiable framing — verified present in every layer

Every `available=True` result carries `is_official_calculation: False` (`nitaqat_compliance_engine.py:410`) and a full bilingual disclaimer (`:174-190`, `NITAQAT_ILLUSTRATIVE_DISCLAIMER_EN/AR`). The frontend renders this disclaimer **twice** — a persistent, unconditional amber banner at the very top of the page (`NitaqatComplianceTracker.tsx`, rendered outside any results-conditional block) and again, in full, alongside the results table with the exact band thresholds used spelled out (so the heuristic is never a black box). Confirmed live in the screenshot (§4).

### Band-threshold heuristic chosen, and why

**What is real (confirmed via live web search, not memory):**
- Band names: Platinum, High Green, Mid Green, Low Green, Red — Yellow eliminated 2025. Sources: [Mercans](https://mercans.com/glossary/saudization-nitaqat/), [Middle East Briefing](https://www.middleeastbriefing.com/news/saudi-arabias-nitaqat-2026-update-latest-quotas-by-sector-and-what-foreign-employers-need-to-comply-now/) (published 2026-05-15) — both cited in `nitaqat_compliance_engine.py:36-42` and returned in every result's `sources` list.
- Small-establishment (≤5 employees) simplified two-tier Green/Red rule (`SMALL_ESTABLISHMENT_MAX_HEADCOUNT = 5`, `:152`) — a genuine structural program rule, confirmed via the same investigation, not illustrative.

**What is this module's own construction (explicitly labeled as such, everywhere):** the percentage cut points `ILLUSTRATIVE_BAND_THRESHOLDS` (`:142-149`) — Platinum ≥40%, High Green ≥30%, Mid Green ≥20%, Low Green ≥10%, Red <10% — simple, round numbers chosen specifically because the real HRSD per-sector logarithmic formula's coefficients are not publicly retrievable (confirmed: the primary-source PDF returned HTTP 403 during investigation). This is stated in the module docstring (`:1-46`), in every result's `governance_note`, and in the `sources` list itself (`:432-436`), not just in a code comment.

### Engine — `backend/core/nitaqat_compliance_engine.py` (463 lines)

- Column detection (`_NATIONALITY_PATTERNS`, `_SECTOR_OR_DEPARTMENT_PATTERNS`, `:82-91`) follows the same local-regex, English+Arabic-combined convention as every other Phase 4-6 module — `theory_aware_column_mapper.py` and `saudi_schema_intelligence.py` were both reviewed and rejected as fits (the latter confirmed dead relative to the live product in the investigation).
- Saudi/non-Saudi value classification (`_classify_saudi_status`, `:117-124`) handles both boolean-style columns (`IsSaudi`: Yes/No/1/0) and free-text `Nationality` columns (Saudi/سعودي/India/Egypt/...) with one token check — missing values excluded from the denominator, never guessed.
- Department/sector grouping reuses `department_normalizer.py` **verbatim** (`:9`, called at `:322`) — the same fix already applied to HR department data and recruitment pipeline data.
- Deduplication is not reimplemented — `SecureFileIngestion.scan()`'s existing pipeline-level dedup runs before this module ever sees the data (confirmed live, §4).

### Test fixture — `nitaqat_test_data.csv` (61 rows, one exact duplicate)

Built specifically for this feature since no real fixture in the repo has a nationality column (confirmed in the investigation). Reuses this session's established messiness patterns: mixed Arabic/English Saudi tokens (`Saudi`/`سعودي`/`saudi`/`KSA`/`Saudi Arabia`/`السعودية`), explicit non-Saudi tokens (`Non-Saudi`/`غير سعودي`) alongside real country names, 5 missing values, mixed department casing/language (`Sales`/`مبيعات`, `Finance`/`finance`, `Operations`/`Operations `), and one exact duplicate `EmployeeID` row.

### Tests — `tests/test_nitaqat_compliance_engine.py` (22 tests)

| Test | Asserts |
|---|---|
| `test_real_employee_fixture_...is_unavailable` / `test_messy_test_data_fixture_also_has_no_nationality_column` | Both real existing fixtures correctly return `available=False`, no fabrication |
| `test_band_assignment_matches_hand_computation` (parametrized ×6) | Hand-computed exact percentages/bands across all 5 bands, including the `39%` just-below-Platinum boundary |
| `test_small_establishment_green_with_at_least_one_saudi` / `_red_with_zero_saudi` | The confirmed real ≤5-employee two-tier rule |
| `test_missing_nationality_values_excluded_not_guessed` | 2 missing excluded from an 8-row set → 6-row denominator, exact percentage |
| `test_bilingual_saudi_tokens_recognised` | EN/AR token parity |
| `test_messy_fixture_department_names_reuse_department_normalizer` | Merges disclosed, no raw `مبيعات`/`finance`/`"Operations "` leaking into output |
| `test_messy_fixture_saudization_pct_matches_independent_classification` | Independently reclassifies every raw value (not calling the engine's own function) — exact match |
| `test_duplicate_row_removed_by_pipeline_level_dedup` | Full `SecureFileIngestion.scan()` integration — duplicate genuinely removed upstream |
| `test_available_result_always_carries_illustrative_disclaimer` / `test_unavailable_result_also_carries_disclaimer_fields` | The mandatory honesty framing is never omittable, in either code path |
| `test_to_dict_is_json_safe_and_includes_honesty_fields` | Serializer completeness |

**All 22 pass.**

### Live route + live frontend page

```
POST /api/local/nitaqat-compliance
```
(`local_analysis_routes.py:1810`, confirmed mounted via direct route-table inspection). Pipeline identical to the five prior modules: Saudi HR column normalization → governance scan (dedup/PII/leakage) → `analyze_nitaqat_compliance()`.

New page: "Nitaqat / Saudization" (`executive-ui/src/pages/NitaqatComplianceTracker.tsx`, 403 lines) in the sidebar's Analysis nav group, `App.tsx`'s `case 'nitaqat'`. Bilingual EN/AR throughout.

---

## What happened to the decorative `ExecutiveReports.tsx` panel

**Relabeled, not wired to the new engine.** The panel (`ExecutiveReports.tsx:869-879`) is part of the executive-report *preview* flow, built from `EmployeeRiskData` session state — a different data shape than a fresh nationality-column upload, and genuinely wiring it would require re-running Nitaqat analysis against the originally-ingested dataframe at report-generation time, which isn't currently plumbed through that flow at all. Per the instruction's explicit fallback ("if that panel is out of scope/lower priority — relabel"), the card was renamed from **"Nitaqat Compliance"** (which claimed to "support Nitaqat tier maintenance" and stated retention "directly impacts Nitaqat classification" — an assessment claim with nothing behind it but overall risk-band stability) to **"Workforce Retention Stability"**, with copy that describes what the data genuinely is and points the reader to the real, honestly-labeled Nitaqat page for an actual estimate. This is a smaller, correct fix rather than a deferred TODO.

---

## Full-Suite Regression Trail

| Checkpoint | Result |
|---|---|
| Before this phase (end of Phase 6) | 39 failed, 1288 passed, 1 skipped |
| After this phase | 39 failed, **1313 passed**, 1 skipped *(+25: 22 Nitaqat-engine tests + 3 Part A premium-honesty tests)* |

Same 39 pre-existing, unrelated `passlib`/bcrypt failures throughout. **Net: zero regressions, +25 new tests, all passing.**

---

## Live browser verification — both required scenarios

### (a) Real Nitaqat fixture — `09_nitaqat_estimate.png`

- `nitaqat_test_data.csv · 60 rows` (61→60: duplicate removed, disclosed)
- **Total Classified: 55** (5 excluded, missing) · **Saudi Nationals: 22** (33 non-Saudi) · **Saudization %: 40.0%** · **Illustrative Band: Platinum**
- Department table: Engineering 16.7% (Low Green), Finance 29.4% (Mid Green), Operations 42.9% (Platinum), Sales 63.6% (Platinum) — all department names correctly merged (مبيعات→Sales, finance→Finance, "Operations "→Operations)
- Illustrative-estimate banner visible at the top **and** repeated in full alongside results, with exact thresholds shown
- Sources list cites the real web-search findings
- **Zero console errors**

### (b) No nationality column — `10_nitaqat_not_applicable.png`

- `test_employee_data.csv · 200 rows`
- "Nationality data not detected in this upload" panel, listing both activating columns (only `department_or_sector` present, correctly checked)
- **Zero console errors**

---

## Summary Table

| Requirement | Status |
|---|---|
| Part A: citable source search, live, not memory | ✅ two independent searches, both confirm no universal figure exists |
| Part A: honest relabel (not fabricated citation) | ✅ `NITAQAT_PREMIUM_CONFIDENCE`, `financial_intelligence_engine.py:173` |
| Part A: dead-module inconsistency resolved | ✅ `roi_estimation_engine.py:244-254` |
| Part A: regression test + live API verification | ✅ 3 tests, `curl`-confirmed live |
| Part B: `is_official_calculation` + disclaimer never omittable | ✅ verified in engine, route, and UI (banner shown twice) |
| Part B: real band names, illustrative thresholds clearly separated | ✅ documented in code, UI, and sources list |
| Part B: synthetic fixture (none existed) | ✅ `nitaqat_test_data.csv`, same messiness patterns as prior phases |
| Part B: 22 tests, hand-verified | ✅ all passing |
| Part B: live route + live page | ✅ `POST /api/local/nitaqat-compliance`, "Nitaqat / Saudization" nav item |
| Decorative panel fixed | ✅ relabeled to "Workforce Retention Stability", points to real tool |
| Full regression | ✅ 1288 → 1313 passed, same 39 pre-existing unrelated failures |
