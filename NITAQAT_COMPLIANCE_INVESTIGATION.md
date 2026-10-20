# Nitaqat / Saudization Compliance — Investigation Report

Date: 2026-08-06
Scope: discovery only, same discipline as `ETHICAL_AI_ENGINE_INVESTIGATION.md`. No feature code written. Every code claim was verified by opening the cited file and line; the threshold claims in §3 were verified via live web search (not memory), per instruction.

---

## 1. Does any Nitaqat/Saudization-specific business logic exist? — No compliance logic; column-detection and one uncited financial constant only

Repo-wide search for `Nitaqat`/`Saudization`/`Qiwa`/`Muqeem`/`GOSI` (case-insensitive) returned 75 files, the overwhelming majority self-authored `.md` reports (treated as leads, not evidence, per this session's established discipline). Every **code** match, classified:

| File:line | What it actually does | Classification |
|---|---|---|
| `saudi_schema_intelligence.py:169-178` (`_QIWA_TO_STANDARD`) | Renames raw Qiwa export column headers (`nitaqat_band`, `saudization_pct`, etc.) to standardized internal names. **No threshold, no band, no compliance status anywhere in the function.** Applied at `:578-580` inside `_normalize_column()`, purely a string lookup. | (a) column-detection/naming only |
| `saudi_schema_intelligence.py:538-545` (`qiwa_hits`) | Counts how many column headers match Qiwa-signature patterns, to guess "this file came from the Qiwa platform" for ERP-source detection. No compliance computation. | (a) column-detection only |
| `dataset_type_classifier.py:104-108` (`_GOVERNMENT_SIGNALS`) | Keyword set (`nitaqat`, `saudization_percentage`, `qiwa_sector_code`, ...) used only to classify a dataset as "looks like government/official labor statistics" — a dataset-*type* label, not a per-employer compliance verdict. | (a) column-detection only |
| `excel_ingestion_engine.py:427-428` | If headers contain `qiwa`/`saudization`, labels the detected ERP source as `"Qiwa (Saudi Labour)"` — same dataset-source-fingerprinting purpose as above. | (a) column-detection only |
| `demo_company_generator.py:39,57,81,104,127,149,240` | `saudization_pct` is a **hardcoded field on 5 fictional demo companies** (e.g. `62.4`, `45.1`, `71.3`, `38.7`, `94.5`), used only to probabilistically assign a fake `is_saudi` flag when generating synthetic demo employee rows (`:240`). Illustrative demo data, not compliance logic applied to a real upload. | (c) synthetic demo-data generator, not real logic |
| `financial_intelligence_engine.py:154-156` (`NITAQAT_PREMIUM_LOW/HIGH = 0.18/0.35`) | A financial multiplier applied inside `executive_roi_engine.py` (`:314-315`) to inflate replacement-cost estimates by 18-35%, labeled "Nitaqat compliance premium." **No citation of any kind** — not in the comment above it, not in the module's own `ASSUMPTION_SOURCES` list (`:58-65`, which cites Cascio & Boudreau, CIPD, SHRM, Saudi Labour Law Art. 84, Hom et al., Gulf HR Consortium — none of which plausibly published a specific "Nitaqat premium" figure). See flag below. | (b)-shaped but **uncited, likely fabricated** — see §3 |
| `roi_estimation_engine.py:246` | The *same claimed concept*, phrased as **"15-30%"** — a different, also-uncited range, in a different file. This module is already documented as dead relative to the live path (`PHASE_4_MODULES_REPORT.md:37`: "confirmed test-only/dead in the live path"). | (b)-shaped, uncited, **internally inconsistent with the 18-35% figure above** — two different guessed numbers for the same "fact" |
| `enterprise_language_guard.py:252-258` | A regex rule that flags/blocks generated report *prose* if it links Saudization terms to attrition/risk language (a legal-exposure guard on narrative text) — not a compliance computation. | (c) narrative-safety governance, unrelated to computing compliance |
| `saudi_data_governance.py:17` | Module docstring **claims** "Nationalization data exposure (Saudization percentages as features)" is governed — but no `saudization`/`nitaqat` pattern actually appears anywhere in `_LEAKAGE_COLUMN_PATTERNS` or `_PII_COLUMN_PATTERNS` (`:105-155`, checked in full). **The docstring's claim is aspirational; the code does not implement it.** | (c) documentation overstates the code — no logic exists |
| `export_safety.py`, `executive_reporting_layer.py` | Import `enterprise_language_guard` (the narrative-safety rule above) — no independent Nitaqat logic. | (c) same governance rule, re-imported |

**Conclusion: no Nitaqat/Saudization band, threshold, or compliance-status computation exists anywhere in this codebase.** The closest thing to "business logic" is a single uncited financial multiplier (§1 table, row 6) that is itself internally inconsistent with a second, differently-valued uncited guess elsewhere (row 7) — both bearing the same fabricated-precision character this session already found and partially fixed for the old flat-`$120,000` attrition-cost formula in Phase 0.

---

## 2. Is any of it wired into the live request path?

Same tracing method as every prior investigation this session: grep the entire `backend/api/` directory, confirm against `main.py`'s actual mounted routers.

| Module | Verdict | Evidence |
|---|---|---|
| `saudi_schema_intelligence.py` (Qiwa column mapping) | **CONFIRMED DEAD** | Only referenced by `enterprise_routes.py:399` — and `enterprise_routes.py` itself is already established dead in this session's original `AUDIT_REPORT.md` §1: "never mounted in `main.py`... only reference in the entire repo is `tests/test_phase7_tenant_isolation.py`." |
| `saudi_data_governance.py` | **CONFIRMED DEAD** | Same reason — only referenced by `enterprise_routes.py`. |
| `saudi_attrition_normalizer.py` | **CONFIRMED DEAD** | Zero references anywhere under `backend/api/` (grepped). Not even reachable via the dead `enterprise_routes.py`. |
| `dataset_type_classifier.py` (`_GOVERNMENT_SIGNALS` keyword set) | **CONFIRMED LIVE** | `local_analysis_routes.py:60-61,143` — instantiated and called in the real live pipeline. But per §1, this only classifies dataset *type*, never computes a compliance verdict. |
| `financial_intelligence_engine.py`'s `NITAQAT_PREMIUM_LOW/HIGH` (via `executive_roi_engine.py`) | **PARTIALLY WIRED** | `compute_executive_roi()` is called live inside the main risk-scoring endpoint (`local_analysis_routes.py:1065`, confirmed inside `local_upload_analyze_with_employees`, the endpoint `executive-ui`'s `DataUpload.tsx` actually calls). Its dict output — **including** `nitaqat_premium_low_sar`/`nitaqat_premium_high_sar` — is included in the JSON response at **three separate response-shape branches** (`local_analysis_routes.py:1096,1114,1161`). The TypeScript type is aware of both fields (`executive-ui/src/state/employeeRiskStore.ts:419-420`). **But grepping the entire `executive-ui/src` tree for any JSX/component usage of `nitaqat_premium_low_sar`/`nitaqat_premium_high_sar` returns zero matches** — the numbers are computed, sent over the wire, and never rendered anywhere. This is the exact "computed and discarded" pattern the original `AUDIT_REPORT.md` flagged elsewhere in this codebase. |
| `ExecutiveReports.tsx:872-909` ("Nitaqat Compliance" panel) | **CONFIRMED LIVE but decorative** | This IS rendered — a "Strategic Alignment" card titled "Nitaqat Compliance" — but it displays only generic templated prose (*"Workforce stability analysis supports Nitaqat tier maintenance. {stabilityPct}% of the workforce is in the stable band..."*) built from `stabilityPct` (overall risk-band stability, unrelated to Saudization). It does **not** reference `nitaqat_premium_low_sar/_high_sar`, does not compute or display an actual Saudization percentage, band, or compliance status — confirmed by reading the full component (`:856-920`). |
| `enterprise_language_guard.py` (Nitaqat-linked-language rule) | **CONFIRMED DEAD** | Neither `export_safety.py` nor `executive_reporting_layer.py` (its only importers) is referenced anywhere under `backend/api/` (grepped). |

**Overall verdict for Q2: no real Nitaqat compliance data reaches a user today.** The one live, user-visible "Nitaqat" surface (`ExecutiveReports.tsx`'s panel) is decorative narrative copy with no underlying computation; the one place a real number IS computed and transmitted (the uncited 18-35% premium) is never displayed.

---

## 3. Real official Nitaqat band thresholds — live web search results

**Band names/tiers — confirmed from multiple sources:** Platinum, High Green, Mid Green, Low Green, Red. The Yellow band was **eliminated in 2025**; establishments previously classified Yellow were reclassified to Red (immediate exposure to blocked visa processing and work-permit renewals).

**No single, simple, universally-citable percentage table exists** — and this is a structural fact about the real program, not a gap in my search. Every source checked, including a direct extraction attempt on a Mercans.com glossary summary, explicitly states there is no flat percentage-per-band table:

> "The existing Saudization formula remains in place, but 'c' values (used to set the Saudization rate by sector) are being increased for most economic activities over the next three years." — [Mercans](https://mercans.com/glossary/saudization-nitaqat/)

The real calculation (the **"Nitaqat Mutawar"** program) is a **logarithmic formula per economic sub-activity**: `Required % = MAX(0, m × ln(headcount) + c)`, where `m` and `c` are sector-specific coefficients set by HRSD — not a fixed lookup table. On top of that, individual *occupations* within a sector often carry their own separate localization quotas layered on top of the band system, e.g. (per [Middle East Briefing](https://www.middleeastbriefing.com/news/saudi-arabias-nitaqat-2026-update-latest-quotas-by-sector-and-what-foreign-employers-need-to-comply-now/), published 2026-05-15):
- Hospital pharmacy activities: 65%
- Medical laboratories: 70%
- Physiotherapy: 80%
- Engineering (establishments with ≥5 workers): 30%
- Accounting: 40% from October 2025, rising 10 percentage points/year
- Marketing (establishments with ≥3 workers): 60%
- 69 additional administrative roles: 100% localization

Additional structural facts confirmed (via [Jisr HRMS](https://www.jisr.net/en/hr-tools/nitaqat-calculator) / [Token Talent](https://tokentalent.co/free-tools/nitaqat-calculator-ksa) summaries):
- Small establishments (≤5 employees, "Entity Size A") use a simplified **two-tier** system (Green/Red only) — must employ at least 1 Saudi to stay Green.
- Point-weighting is not 1-employee-1-point: a full-time Saudi earning ≥ SAR 4,000/month = 1 point, part-time = 0.5, an employee with disability = 2 points. The SAR 4,000 minimum-wage-to-count threshold rose from SAR 3,000 recently.
- As of 15 April 2026, **only Saudis with Qiwa-documented contracts count toward Saudization** — an eligibility rule with no percentage attached.

**Primary source attempt:** the official HRSD procedural guideline PDF (`hrsd.gov.sa/sites/default/files/2023-06/E20210523.pdf`, "Nitaqat Mutawar Program Version 2.0") returned **HTTP 403 Forbidden** when fetched directly — could not be retrieved. Qiwa's own "what is Nitaqat and how it's calculated" page (`qiwa.sa/en/business-owners/manage-establishment/what-nitaqat-and-how-it-calculated`) is a JavaScript SPA that returns no static content to a non-browser fetch.

**Honest conclusion, per instruction:** the band *names* are confirmed from multiple consistent secondary sources. The exact numeric `m`/`c` coefficients per economic sub-activity that would be needed to *compute* a band from a headcount + nationality mix are **not available from any source I could actually retrieve** (the one primary-source PDF is blocked; Qiwa's calculator is interactive/JS-only, not a published static table). Any band-threshold table hardcoded into this codebase today would necessarily be either (a) sourced from a secondary/consultancy summary with only a handful of illustrative sector examples, not the full coefficient set, or (b) fabricated — exactly the failure mode already found in `NITAQAT_PREMIUM_LOW/HIGH` (§1). I am not proposing either.

---

## 4. Does the real test data have the needed columns? — No

| Fixture | Columns | Nationality/Saudi-vs-non-Saudi signal? |
|---|---|---|
| `test_employee_data.csv` (200 rows, the platform's primary live-testing fixture) | `EmployeeID, Department, Age, Gender, JobRole, Attrition, MonthlyIncome, OverTime, JobSatisfaction, PerformanceRating, YearsAtCompany` | **None.** No `Nationality`, `Country`, `IsSaudi`, or equivalent column. |
| `messy_test_data.csv` (Phase 35.5 correction fixture) | `EmployeeID, Department, OverTime, MonthlyIncome, tenure_years, job_level, performance_rating, PercentSalaryHike` | **None.** |
| `messy_recruitment_data.csv` (Phase 5 fixture) | `CandidateID, Stage, Department, Source, ApplicationDate, HireDate, RejectionReason, RecruitmentCost` | **None.** |
| Any other CSV in the repo | `MODEL_SEARCH_RESULTS_PHASE29_5.csv` — unrelated (ML hyperparameter-search results, no HR columns at all) | N/A |

**This is the same "not applicable to current test data" situation flagged for Recruitment Pipeline Tracker before it was built**, and it's a genuine constraint here too: none of this session's real, repeatedly-used test fixtures contain a column that could seed a Saudization percentage. The only place `Nationality`-style data exists in this repo at all is the fully synthetic demo-company generator (`demo_company_generator.py`), which fabricates fictional companies with hardcoded `saudization_pct` values for demo purposes — not a real dataset to validate real logic against.

---

## 5. Adjacent/overlapping modules — no competing implementation exists

- **`saudi_data_governance.py`**: checked in full (§1) — its docstring claims Saudization-exposure governance, but the actual `_LEAKAGE_COLUMN_PATTERNS`/`_PII_COLUMN_PATTERNS` lists contain zero `saudization`/`nitaqat` entries. Nothing to reuse or conflict with; the intended feature was apparently never implemented.
- **`saudi_attrition_normalizer.py`**: checked in full (§1) — entirely about mapping Saudi HR column names to psychological-theory constructs (COR/JD-R/FFM/Mobley/Adams proxy mapping). Zero nationality-related content of any kind (grepped for `nationality`/`Nationality`/`saudi`/`Saudi`, only module-name-level mentions in comments, no logic).

**Conclusion: nothing would need to be replaced or reconciled.** A new Nitaqat/Saudization feature would not compete with any existing implementation — there isn't one.

---

## Recommendation

**(b) — missing pieces, and more of them than initially framed. Not ready to build today.**

Specifically missing:

1. **No real compliance-band logic exists anywhere to extend** — only column-name mapping (dead code) and one uncited, internally-inconsistent financial constant (§1). This is a green-field build, not an extension of existing infrastructure — closer to Recruitment Pipeline Tracker's situation than to the Ethical AI fix.
2. **No real test data** — none of this session's three working fixtures have a nationality/Saudi-vs-non-Saudi column (§4). Building this today would mean either fabricating a synthetic test fixture from scratch (no real dataset to validate against, unlike the Ethical AI fix which had `Age`/`Gender` sitting right there in `test_employee_data.csv`) or shipping a feature with zero real live-browser verification possible against existing data.
3. **The official threshold structure is genuinely more complex than a lookup table** (§3) — a simple "Saudization % ≥ X → Green" implementation would itself be a simplification bordering on fabrication, since the real system is a per-sector logarithmic formula with coefficients I could not retrieve from an accessible primary source. Anything built now would need to either (a) implement a deliberately-labeled "illustrative, non-official" band heuristic (explicitly not claiming to replicate the real HRSD calculation — similar in spirit to `SECTOR_BENCHMARK_CONFIDENCE`'s "uncalibrated_generic_estimate" honesty pattern already established in this codebase), or (b) integrate the official Qiwa API/calculator directly (out of scope for an offline-only platform — this codebase's `offline_mode_guard.py` convention explicitly forbids network calls).
4. **A pre-existing, unrelated bug worth flagging regardless of whether this feature is prioritized**: `NITAQAT_PREMIUM_LOW/HIGH = 0.18/0.35` (`financial_intelligence_engine.py:155-156`) is live, uncited, and inconsistent with a second uncited guess (`roi_estimation_engine.py:246`, "15-30%", dead code but still evidence of the same fabrication). This already reaches the live product today (§2) via `executive_roi_engine.py`, even though nothing currently displays it. This is a smaller, independent fix (remove or honestly re-label, matching the `SECTOR_BENCHMARK_CONFIDENCE` pattern) that doesn't require solving 1-3 above, and is arguably higher-priority than building the full feature, since it's a live inaccuracy already flowing through the system today.

If this is prioritized later, the realistic scope is: (a) fix the uncited premium constant first (small, independent), (b) build an explicitly-labeled illustrative Saudization/Nitaqat-band indicator (not a claim of official HRSD accuracy) driven by a synthetic test fixture built specifically for this feature, since no real one exists, and (c) surface it honestly with the same "not detected in this dataset" pattern used by Recruitment Pipeline / Fairness Audit when no nationality column is present — which, against every fixture actually used in this project today, would be every time.

Not recommending implementation. Awaiting confirmation, per instruction.
