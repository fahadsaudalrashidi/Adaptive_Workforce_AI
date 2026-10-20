# Technical Debt Report
**Platform:** Adaptive Workforce Intelligence Engine v2.3.0  
**Audit Date:** 2026-05-19

---

## Debt Summary

| Category | Items | Priority |
|----------|-------|----------|
| Architecture | 1 | HIGH |
| Scientific | 2 | HIGH |
| Localization | 2 | MEDIUM |
| Testing | 3 | MEDIUM |
| Features | 2 | LOW |

---

## HIGH Priority

### TD-01: app.py monolith (3103 lines)
- **Problem:** Single file mixes sidebar, routing, session state management, 10 page renderers, 27 helper functions, governance panels, export functions, and analysis pipeline
- **Risk:** Any change risks breaking multiple unrelated pages. Testing requires loading entire 3103-line file. Hard to audit for safety/compliance.
- **Solution:** Extract to `frontend/components/`, `frontend/pages/`, `frontend/utils/`
- **Effort:** HIGH — but safe if done incrementally with regression testing after each step

### TD-02: Model reliability = governed_auc only
- **Problem:** `mr_score = _clamp(governed_auc)` in confidence_governance.py
- **Risk:** Scientific claim "model reliability" is essentially just AUC governance — no calibration, no fold stability, no feature trust integrated
- **Solution:** Multi-component weighted formula (see GOVERNANCE_GAPS.md GAP-01)
- **Effort:** MEDIUM

### TD-03: No calibration module
- **Problem:** Platform shows predicted probabilities (e.g., 87% attrition risk) without any calibration assessment
- **Risk:** Overconfident models show inflated probabilities as reliable
- **Solution:** `backend/core/calibration_engine.py` with Brier score, ECE, reliability diagram data
- **Effort:** MEDIUM

---

## MEDIUM Priority

### TD-04: insight_generator.py shows USD financial exposure
- **Problem:** L80 and L334 use `total_financial_exposure_usd` with "USD" format string
- **Risk:** Incorrect currency in executive insights even after SAR is selected
- **Solution:** Pass currency parameter through InsightGenerator; format with configured currency
- **Effort:** LOW

### TD-05: api/main.py not currency-aware
- **Problem:** REST API exports financial exposure as USD-only
- **Risk:** API consumers (external systems) always receive USD
- **Solution:** Accept `currency` query parameter; convert appropriately
- **Effort:** LOW

### TD-06: No test file for calibration
- **Problem:** CalibrationGovernor has no dedicated tests
- **Risk:** Regressions undetected
- **Solution:** `test_calibration.py` once CalibrationGovernor is built
- **Effort:** LOW

### TD-07: No test file for executive language safety (comprehensive)
- **Problem:** test_company_readiness.py covers basic language checks but not comprehensive
- **Solution:** `test_executive_language.py` with full forbidden word list
- **Effort:** LOW

### TD-08: No test file for routing regression
- **Problem:** test_routing.py covers routing logic but not full pipeline regression
- **Solution:** `test_routing_regression.py` covering all 8 routing scenarios
- **Effort:** LOW

---

## LOW Priority

### TD-09: No PDF export
- **Problem:** Only HTML + TXT reports supported
- **Solution:** Add `weasyprint` or `pdfkit` dependency for PDF generation
- **Effort:** MEDIUM (dependency management)

### TD-10: Arabic department column support incomplete
- **Problem:** DEPT_SYNONYMS includes Arabic terms but word-boundary regex may not handle Arabic properly
- **Solution:** Test with Arabic column names; ensure regex handles Unicode correctly
- **Effort:** LOW

---

## Resolved Debt (this session)

- confidence contradictions → resolved by confidence_governance.py
- fake burnout zero → resolved by Optional[float] in risk_intelligence.py
- fake dept groups → resolved by _detect_dept_column() + empty list return
- hardcoded USD in UI → resolved by currency selector + CURRENCY_SYMBOLS
- causal language → resolved by associative templates
- stack traces in UI → resolved by global try/except
- employee ID exposure → resolved by mask_employee_ids default=True
- AUC-only display → resolved by governed_auc propagation
- missing leakage integration → resolved by ml_router wiring
- missing model validation → resolved by ml_router wiring
