# Broken Pipelines Report
**Platform:** Adaptive Workforce Intelligence Engine v2.3.0  
**Audit Date:** 2026-05-19

---

## Pipeline Status Summary

| Pipeline | Status | Severity |
|----------|--------|----------|
| Saudi HR → Attrition routing | OK | — |
| IBM HR → Attrition routing | OK | — |
| WESAD BVP.csv → Biosignal | OK | — |
| WESAD HR.csv → Biosignal | OK | — |
| EDA.csv → Biosignal | OK | — |
| Unknown CSV → Profiling only | OK | — |
| Generic time-series → Time-series | OK | — |
| Biosignal → no employee metrics | OK | — |
| HR → no biosignal dashboard | OK | — |
| Leakage detection pipeline | OK | — |
| Model validation pipeline | OK | — |
| Currency conversion pipeline | OK | — |
| Department detection pipeline | OK | — |

---

## Active Bugs / Technical Debt

### BUG-01: insight_generator.py hardcodes USD (MEDIUM)
- **File:** `backend/core/insight_generator.py` L80, L334
- **Issue:** Uses `org_risk.total_financial_exposure_usd` and formats with "USD"
- **Impact:** Financial insights show USD instead of configured currency
- **Fix:** Use `org_risk.total_financial_exposure` with currency parameter

### BUG-02: api/main.py hardcodes USD (LOW — API not used in UI)
- **File:** `backend/api/main.py` L263, L316
- **Issue:** Uses `financial_exposure_usd` in API response and CSV export
- **Impact:** API consumers receive USD-only values
- **Fix:** Accept currency parameter; use `financial_exposure` with currency

### BUG-03: confidence_governance.py model_reliability = AUC-only (HIGH)
- **File:** `backend/core/confidence_governance.py` L190
- **Issue:** `mr_score = _clamp(governed_auc)` — model reliability is purely AUC
- **Impact:** Scientifically weak; model reliability should incorporate calibration, stability, feature trust
- **Fix:** Implement multi-component weighted formula (Phase 3)

### BUG-04: app.py is 3103 lines (MEDIUM — maintainability)
- **File:** `frontend/app.py`
- **Issue:** Monolithic file mixes routing, UI rendering, business logic
- **Impact:** Hard to maintain, test, and audit; risk of regressions
- **Fix:** Refactor into components/pages/utils (Phase 2)

### BUG-05: No calibration assessment (HIGH — scientific validity)
- **Issue:** Predictions shown as probabilities without calibration check
- **Impact:** Overconfident or underconfident predictions appear as reliable
- **Fix:** Implement CalibrationGovernor with Brier score, ECE, reliability diagram

### BUG-06: No PDF export (LOW — nice-to-have)
- **Issue:** HTML and TXT reports exist, PDF not implemented
- **Impact:** Some enterprises expect PDF output
- **Fix:** Use weasyprint or pdfkit in report export

---

## No Breaking Bugs Found

All routing pipelines, biosignal isolation, and safety guardrails are functioning.
All 408 tests pass.
