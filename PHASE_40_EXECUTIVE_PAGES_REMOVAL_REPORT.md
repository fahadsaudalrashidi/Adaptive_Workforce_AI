# Phase 40 — Complete Removal: `employee_risk_scoring.py` + All Dependent Executive Pages

**Supersedes:** Phase 39's "contained removal" decision. The user reviewed the live site and confirmed the entire prediction/"theory" page cluster should be deleted, not kept.

---

## Step 1 — Confirmed Scope (real import tracing, not name-matching)

Each of the 7 pages the user named was traced via real `useEmployeeRisk` / `EmployeeRiskContext` / risk-store usage and real backend route dependencies — not docstrings, comments, or name similarity.

| # | User's Arabic name | English | File | Verdict |
|---|---|---|---|---|
| 1 | استيعاب بيانات المؤسسة | Enterprise Data Ingestion | `DataUpload.tsx` | **Confirmed dependent** — see DataUpload finding below |
| 2 | موجز الرئيس التنفيذي | Executive Brief | `ExecutiveReports.tsx` / `ExecutiveReportPreview.tsx` / `ExecutiveReportPrint.tsx` | **Confirmed dependent** — consumed `EmployeeRiskContext` scored data and the deleted narrative/exporter engines |
| 3 | الذكاء التنفيذي للقوى العاملة | Workforce Executive Intelligence | `ExecutiveDashboard.tsx` / `CEODashboard.tsx` | **Confirmed dependent** — hero metrics sourced from `employee_risk_scoring.py` output |
| 4 | ذكاء مخاطر القوى العاملة | Workforce Risk Intelligence | `EmployeeRiskDashboard.tsx` | **Confirmed dependent** — direct 1:1 UI over risk-scorer output |
| 5 | مركز القرار | Decision Center | `DecisionCenter.tsx` | **Confirmed dependent** — consumed `executive_decision_intelligence.py`, which itself only ever ran on risk-scorer output |
| 6 | مركز تسليم الذكاء لمجلس الإدارة | Board Intelligence Delivery Center | `ExecutiveReports.tsx` (board-report path) | **Confirmed dependent** — same file family as #2, board narrative/export path |
| 7 | الحوكمة المؤسسية السعودية | Saudi Corporate Governance | `GovernancePanel.tsx` | **Confirmed dependent** — governance scoring pulled from risk-scorer confidence/PII fields |

All 7 named items are genuine dependents. **No false alarm this round** — unlike Phase 39's "Theory Drivers," every page the user named for removal really did trace back to `employee_risk_scoring.py` or its exclusive downstream engines.

### DataUpload.tsx finding (flagged as requested)

Confirmed via exhaustive grep of every surviving BI/HR module's `<input type="file">` and `fetch()` calls: **`DataUpload.tsx` is NOT the platform's shared upload mechanism.** Every surviving module (the 6 BI domains, all 11 HR analytics pages, the 4 Saudi calculators) has its own independent file-upload widget and its own dedicated backend endpoint. `DataUpload.tsx` only ever populated `AnalysisContext`/`EmployeeRiskContext`, which — after this phase — nothing else reads. It was safe to delete outright; nothing else breaks.

### Additional dependents found (not named by the user, but confirmed real)

Import-tracing surfaced 5 more genuine dependents the user didn't explicitly name:

- `RiskSegmentation.tsx` — direct `EmployeeRiskContext` consumer
- `SimulationPanel.tsx` — consumed `workforce_simulation_engine.py`, which only ever ran on risk-scored data
- `TheoryExplainability.tsx` — direct risk-model explainability UI
- `AnalysisHistory.tsx` — history view over `AnalysisContext`/sessions, both now-orphaned
- `ExecutiveReportPreview.tsx` / `ExecutiveReportPrint.tsx` — sub-family of item #2/#6 above

**Correctly excluded:** `TrustPanel.tsx` (zero risk-context usage — genuinely independent, kept as "AI Integrity"), and the "Workforce Risk Analysis" label Phase 39 applied inside `DataUpload.tsx` — moot, since the whole file is now deleted, not a separate surviving feature.

---

## Step 2 — CEO Dashboard / Landing Replacement: `EnterpriseOverview.tsx`

**Design chosen:** an honest navigation hub — one card per surviving module, grouped into "AI & Business Intelligence" (7), "HR Analytics" (11), and "Saudi Compliance & Calculators" (4) — over a fabricated cross-module metrics dashboard.

**Why not a cross-domain summary metric:** every surviving module now runs on its *own* independently-uploaded dataset (confirmed by the DataUpload finding above — there is no shared analyzed dataset anymore, since `AnalysisContext`/`EmployeeRiskContext` are both gone). A "pull one headline number from each domain" dashboard would require either (a) inventing numbers with no data behind them, or (b) silently re-introducing a shared-dataset assumption the rest of Phase 40 just removed. Both violate this project's governance standard of never presenting a number without real data behind it. A navigation hub makes zero unbacked claims and gets every user to the module they need in one click — the explicit design goal stated in the page's own header comment.

---

## Step 3 — Everything Removed

**Frontend pages (13):** `DataUpload.tsx`, `CEODashboard.tsx`, `ExecutiveDashboard.tsx`, `EmployeeRiskDashboard.tsx`, `DecisionCenter.tsx`, `ExecutiveReports.tsx`, `ExecutiveReportPreview.tsx`, `ExecutiveReportPrint.tsx`, `GovernancePanel.tsx`, `RiskSegmentation.tsx`, `SimulationPanel.tsx`, `TheoryExplainability.tsx`, `AnalysisHistory.tsx`

**Frontend shared state (6):** `EmployeeRiskContext.tsx`, `employeeRiskStore.ts`, `AnalysisContext.tsx`, `analysisStore.ts`, `dataConsistencyValidator.ts`, `sessionStore.ts`

**Frontend orphaned visualizations (3):** `FinancialImpactTreemap.tsx`, `RiskRadarChart.tsx`, `WorkforceCompositionRiver.tsx` — not in the original scope, found dead via `tsc --noEmit` after the page deletions

**Backend engines/exporters (17):** `employee_risk_scoring.py`, `employee_risk_exporter.py`, `workforce_simulation_engine.py`, `executive_decision_intelligence.py`, `executive_index_engine.py`, `executive_roi_engine.py`, `executive_storytelling_engine.py`, `executive_readiness_engine.py`, `workforce_forecasting_engine.py`, `executive_narrative_engine.py`, `executive_pptx_exporter.py`, `executive_pdf_exporter.py`, `executive_slide_exporter.py`, `local_database.py`, `hr_recommendation_engine.py`, `employee_explainability_engine.py`, `historical_intelligence_engine.py` — plus `backend/core/html_to_pdf.mjs`

**Backend routes removed from `local_analysis_routes.py`:** `/upload/analyze`, `/upload/analyze-with-employees` (818 lines), `/sessions/latest`, `/sessions`, `/sessions/{id}` (GET+DELETE), `/export-audit`, `/upload/export-employee-csv`, `/export/slides`, `/export/pptx`, `/export/pdf` (248 lines). Router: 31 routes remain.

**Kept routes patched (non-fatal fallback preserved, not invented):** `/overtime-cost-intelligence`, `/payroll-movements`, `/fairness-audit` — each had an embedded risk-scorer cross-reference call replaced with the same empty/default value the route already used whenever that call failed non-fatally. Downstream engine logic in all three routes is untouched.

**New file:** `executive-ui/src/pages/EnterpriseOverview.tsx` (Step 2 replacement, sole landing page).

**Navigation:** `Sidebar.tsx` rewritten around `NAV_GROUPS` (Overview / AI & Business Intelligence / HR Analytics / Saudi Compliance & Calculators / Advanced); footer changed from dynamic "LIVE ANALYSIS"/"NO DATASET" to static "LOCAL & OFFLINE — Each module uploads its own data," matching the now-per-module upload model. `NavPage` type in `types/index.ts` reduced from ~35 to 24 members. `App.tsx` rewritten — no more `AnalysisProvider`/`EmployeeRiskProvider`, no more `lazy()` imports.

**Copy cleanup:** `PageErrorBoundary.tsx` — "Return to Upload" → "Return to Overview"; help text updated to per-module upload language.

**Tests — deleted entirely (13 files):** `test_phase14_employee_risk_dashboard.py`, `test_phase16_model_metrics.py`, `test_phase18_explainability.py`, `test_phase19_enterprise_intelligence.py`, `test_phase21_persistence.py`, `test_phase22_workforce_simulation.py`, `test_phase23_decision_intelligence.py`, `test_phase27_simulation.py`, `test_phase27b_simulation_activation.py`, `test_phase26_ui_polish.py`, plus 3 more identified as fully obsolete after this round.

**Tests — surgically trimmed (12 files):** `test_department_normalization_phase35_5.py`, `test_phase11_productization.py`, `test_phase24_release_hardening.py`, `test_financial_intelligence_engine.py`, `test_phase12_local_analysis_endpoint.py`, `test_duplicate_row_deduplication_phase35_5.py`, `test_sector_benchmarking_phase4.py`, `test_phase30_enterprise_productization.py`, `test_phase29_integration.py`, `test_phase28_enterprise_transformation.py`, `test_phase29_executive_experience.py`, `test_phase29_extended.py`, `test_phase29_final_closure.py` — 159 individually-named doomed tests removed from the last 4 files alone via AST-precise line-range deletion, verified against the real failure output (FileNotFoundError / ModuleNotFoundError / AssertionError against deleted files and modules) before removal, not assumed from names.

Genuinely independent tests were preserved in every trimmed file — e.g. `TestBenchmarkGapPanelComponent`/`TestBenchmarkAPIFunctional` (real `/benchmarks/*` routes, unrelated to risk scoring), `TestBenchmarkRoadmap`/`TestVisualisationComponents`/`TestNavigationGroups` (Phase 29), `TestRiskMatrixComponent` (Phase 29 Extended — a generic display component, unrelated by more than name), and the full `TestBenchmarkEngine*` + `TestAPIEndpointWiring` suite (Phase 29 Final Closure).

---

## Test Counts

| | Passed | Failed | Skipped |
|---|---|---|---|
| End of Phase 39 | 1,631 | 9 (pre-existing, unrelated auth) | — |
| End of Phase 40 | 1,232 | 9 (same pre-existing auth failures) | 1 |

**Drop: 399 passing tests**, entirely accounted for by the deleted pages/engines/routes and their now-obsolete test coverage. The 9 remaining failures are the same pre-existing `test_phase30_1_security.py` auth-wiring failures present before Phase 40 began — confirmed unrelated by inspection (they fail on an unrelated `_IncludedRouter` attribute issue in the auth test harness, not on anything touched this phase). Zero new regressions.

One test, `test_health_wheel_imported`, no longer exists in the suite at all — it was inside one of the now-fully-empty classes removed from `test_phase29_extended.py` during this round's cleanup, since it asserted content of `CEODashboard.tsx`, which this phase deleted outright.

---

## Live Verification

Backend started via `python backend/api/main.py`, frontend via `npm run dev` (port 5174). Verified with Playwright (Chromium):

- **Landing page** (`EnterpriseOverview.tsx`): loads with 0 console/page errors, renders all 22 module cards across 3 grouped sections, disclaimer text ("no shared platform-wide dataset") visible.
- **Full nav click-through**: all 24 sidebar entries clicked in sequence — 0 console errors, 0 page errors across every page.
- **Real data end-to-end**: uploaded `test_employee_data.csv` to **Overtime Cost Intelligence** — real KPIs rendered (33% prevalence, SAR 112K/month, SAR 1.3M annual exposure, per-department breakdown). Uploaded the same file to **Payroll Movements** — correctly reported "Not available for this dataset" (no salary-hike/period columns present), confirming the non-fatal fallback patched into that route in Step 3 behaves identically to its pre-existing honest-failure state.

Screenshots saved to `pw_shots/` (repo root): `01_overview_landing.png` (landing page), `09_Overtime_Cost_Intelligence_*.png` through `24_AI_Integrity_*.png` (full nav walk), `upload_01_overtime_result.png` / `upload_02_payroll_result.png` (live data verification).
