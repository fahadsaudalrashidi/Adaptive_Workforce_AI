# System Health Report
**Platform:** Adaptive Workforce Intelligence Engine v2.3.0  
**Audit Date:** 2026-05-19  
**Auditor:** Automated system audit (Phase 0)

---

## 1. Python Syntax

| Check | Result |
|-------|--------|
| Total Python files | 41 |
| Syntax errors | **0** |
| All files parseable | YES |

---

## 2. Module Imports

| Check | Result |
|-------|--------|
| Backend modules checked | 27 |
| Import failures | **0** |
| All modules importable | YES |

---

## 3. Streamlit Boot

| Check | Result |
|-------|--------|
| app.py syntax OK | YES |
| HTTP 200 on port 8510 | **YES** |
| Boot without crash | YES |

---

## 4. File Structure

| File | Lines | Status |
|------|-------|--------|
| frontend/app.py | 3,103 | OVERSIZED — refactor needed |
| backend/core/leakage_detector.py | 1,160 | OK |
| backend/core/confidence_governance.py | 331 | OK |
| backend/core/feature_trustworthiness.py | 277 | OK |
| backend/core/risk_intelligence.py | 523 | OK |
| backend/core/report_generator.py | 761 | OK |
| config/settings.py | 238 | OK |

---

## 5. Module Orphan Status

| Module | Status | Note |
|--------|--------|------|
| adaptive_router.py | USED | Core routing — called in app.py |
| adaptive_visualization_engine.py | ORPHAN in app.py | Used via adaptive_router internally |
| automl_engine.py | ORPHAN in app.py | Used via ml_router internally |
| confidence_engine.py | USED | Legacy confidence — also used |
| confidence_governance.py | USED | New 5-dimension governance |
| dataset_confidence_engine.py | ORPHAN in app.py | Used via adaptive_router chain |
| fail_safe_guardrails.py | ORPHAN in app.py | Used via adaptive_router chain |
| leakage_detector.py | ORPHAN in app.py | Used via ml_router — WIRED |
| modality_classifier.py | ORPHAN in app.py | Used via adaptive_router chain |
| model_validator.py | ORPHAN in app.py | Used via ml_router — WIRED |
| semantic_column_mapper.py | ORPHAN in app.py | Used via adaptive_router chain |

Note: "Orphan" means not directly imported in app.py but used indirectly through router chains.

---

## 6. Session State Keys

All 15 required session_state keys present:
analysis_done, biosignal_profile, confidence_profile, contract, currency, demo_mode, df, exec_report, explain_report, filename, insight_report, mask_employee_ids, profile, sem_map, ts_result

Missing from audit: unified_confidence, feature_trust, ind_risks, dept_risks, org_risk, ml_result, df_eng, df_clean, raw, ethical_report — PRESENT in code but not captured by regex (accessed differently).

---

## 7. Governance Coverage

| Governance Feature | Status |
|-------------------|--------|
| ConfidenceGovernor imported | OK |
| FeatureTrustworthinessAssessor imported | OK |
| HUMAN_OVERSIGHT_DISCLAIMER imported | OK |
| DEFAULT_CURRENCY imported | OK |
| unified_confidence in session_state | OK |
| feature_trust in session_state | OK |
| mask_employee_ids in session_state | OK |
| demo_mode in session_state | OK |
| _render_unified_confidence_panel defined | OK |
| _render_feature_trust_panel defined | OK |

---

## 8. Test Results

| Test Suite | Passed | Failed |
|-----------|--------|--------|
| test_routing.py | 41 | 0 |
| test_biosignal.py | 36 | 0 |
| test_e2e.py | 62 | 0 |
| test_frontend_guards.py | 78 | 0 |
| test_integration_v3.py | 50 | 0 |
| test_stress.py | 49 | 0 |
| test_company_readiness.py | 92 | 0 |
| **TOTAL** | **408** | **0** |

---

## 9. HTTP Check

- Port 8510: **HTTP 200** ✅

---

## 10. Overall Health

| Dimension | Score | Notes |
|-----------|-------|-------|
| Syntax | 100/100 | 0 errors in 41 files |
| Imports | 100/100 | 27/27 modules import clean |
| Tests | 100/100 | 408/408 passing |
| HTTP | 100/100 | 200 on port 8510 |
| Architecture | 60/100 | app.py 3103 lines — needs refactor |
| Governance | 85/100 | Multi-component reliability pending |
| Localization | 75/100 | USD refs remain in insight_generator + api |
| **Overall** | **88/100** | |
