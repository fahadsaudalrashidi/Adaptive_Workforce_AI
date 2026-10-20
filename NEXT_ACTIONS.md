# Next Actions — Adaptive Workforce Intelligence Engine
**Updated:** 2026-05-20  
**Status:** v2.5.0-rc1 FROZEN — 171 tests passing (92 readiness + 79 governance), HTTP 200  
**Enterprise Readiness Score:** 87/100 — PILOT READY  
**Target:** 90/100 (Production Ready — post-pilot)

---

## FREEZE STATUS
**This release (v2.5.0-rc1) is FROZEN for pilot deployment.**  
No architecture changes, new modules, or governance expansions until pilot feedback is collected.

---

## Phase 20 Complete (2026-05-20)
- `frontend/pages/adaptive_page.py` — NEW: full Adaptive Dataset Intelligence page extracted
  - 5-tab layout: Compatibility Matrix, Column Mapping, Sandbox, Run Analysis, Export
  - `run_analysis_fn` injected from `app.py` (avoids circular import, preserves `_run_analysis` as shared infra)
  - All blocks wrapped in `safe_error_boundary()`
  - Export section: HR report, biosignal report, survey report, profiling report
- `frontend/app.py` — UPDATED: all 10 pages now dispatch to modular modules
  - `adaptive_page.py` added to import block + dispatch
  - `hr_attrition`, `department`, `insights` dispatch updated to use `_mod.render` when `_MODULAR`
- `_validate_routing.py` — NEW: final validation script, 21 checks (all pass)
- `.vscode/settings.json` — NEW: Python 3.13 interpreter path persisted for VS Code

---

## Production Blockers (Deferred to v3.0.0)

### P1 — Authentication Layer
- Add SSO/OAuth2 to Streamlit app (streamlit-authenticator or separate auth proxy)
- Required before any external client access
- Est: 2-3 days

### P2 — PDF Report Export
- Add PDF export to every HR report (fpdf2 or weasyprint)
- Cover page with client logo, report date, HUMAN_OVERSIGHT_DISCLAIMER
- Est: 1 day

### P3 — Docker Containerization
- Dockerfile for Streamlit app
- docker-compose.yml for app + API
- Est: 0.5 days

### P4 — /health Endpoint in FastAPI
- Add GET /health and GET /ping to api/main.py
- Est: 2 hours

---

## Governance Improvements (Post-Pilot — Score 87 → 92)

### G2 — model_reliability_score in Report
- Move exec_report_obj generation to AFTER unified_conf so `model_reliability_score` is populated
- Currently `model_reliability_score=None` due to ordering in `_run_analysis()`

### G3 — Bootstrap Calibration Fallback
- When OOF predictions not available, use Platt scaling on train proba
- Ensures calibration_rep is always computed

### G4 — Arabic / RTL Support
- Arabic locale formatting for Saudi enterprise clients
- Hijri date support in reports

### G5 — Wire GovernanceLogger into app.py pipeline
- GovernanceLogger exists but not yet wired for log_routing(), log_leakage(), log_calibration()
- Wire after: adaptive_router(), leakage_detector(), calibration_engine() calls

### G6 — Wire DriftMonitor.set_baseline() in app.py
- DriftMonitor exists but baseline not set after successful analysis runs

---

## Test Suite Gaps (Post-Pilot)

### T1 — API Layer Tests
- test_api_endpoints.py — test /analyze, /report, /health payloads

### T2 — Report Export Tests
- test_report_exports.py — HTML/PDF outputs; no USD; correct currency

### T3 — Demo Mode Tests
- test_demo_mode.py — page gating, ID masking, company name

---

## Known Warnings (Non-Blocking)
These produce warnings but NOT errors. Safe to defer until Pandas 4.0 migration:

| ID | Warning | File | Impact |
|----|---------|------|--------|
| W-01 | `select_dtypes(include=["object"])` Pandas4Warning | adaptive_router.py:143 | NONE — backward compat |
| W-02 | `Could not infer format` date parsing | modality_classifier.py:276 | NONE — falls back to dateutil |
| W-03 | `Could not infer format` date parsing | semantic_column_mapper.py:348 | NONE — falls back to dateutil |

---

## Safety Invariants — Must Never Break
1. Biosignal → never HR pipeline (test_routing_regression: 12 tests)
2. BurnoutRisk = None when no evidence (test_construct_evidence: 8 tests)
3. Model reliability = 9-component formula, not AUC-only (test_calibration: 17 tests)
4. SAR default everywhere (test_currency_localization: 11 tests)
5. No forbidden executive phrases in AI output (test_executive_language: 21 tests)
6. No stack traces in UI (test_no_stack_traces: 9 tests)
7. SMOTE inside CV folds only (test_routing_regression)
8. GovernanceLogger audit events NEVER exposed to executive UI
9. Unknown datasets enter sandbox-safe mode — no crash, graceful degradation
