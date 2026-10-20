# Governance Gaps Report
**Platform:** Adaptive Workforce Intelligence Engine v2.3.0  
**Audit Date:** 2026-05-19

---

## Governance Coverage Matrix

| Governance Requirement | Status | Gap Level |
|------------------------|--------|-----------|
| No contradictory confidence scores | FIXED | — |
| Model reliability != AUC-only | **PARTIAL** | HIGH |
| JobTitle flagged as high-cardinality | FIXED | — |
| BurnoutRisk shows N/A (not 0%) when insufficient evidence | FIXED | — |
| Department breakdown real or honestly unavailable | FIXED | — |
| SAR default everywhere | **PARTIAL** | MEDIUM — insight_generator still USD |
| Executive language safe | FIXED | — |
| Employee IDs masked in demo mode | FIXED | — |
| HTML report generated | FIXED | — |
| Human oversight disclaimer everywhere | FIXED | — |
| Leakage detector integrated | FIXED | — |
| Model validation integrated | FIXED | — |
| Adaptive routing regression protected | FIXED | — |
| No raw stack traces in UI | FIXED | — |
| Calibration quality assessed | **MISSING** | HIGH |
| Train/test gap monitored | **PARTIAL** — available in validation_report, not shown | MEDIUM |
| Brier score computed | **MISSING** | MEDIUM |
| Probability overconfidence detection | **MISSING** | MEDIUM |
| Feature dominance → retrain suggestion | **MISSING** | LOW |
| PDF export | **MISSING** | LOW |
| Arabic department column names (القسم) | **PARTIAL** | LOW |

---

## Critical Governance Gaps (must fix)

### GAP-01: Model Reliability = AUC-only
**Risk:** Platform claims scientific validity while model reliability is calculated as `mr_score = governed_auc`. This means a model with 0.85 AUC but poor calibration, fold instability, and high feature dominance risk still shows "High" model reliability.

**Required fix:** Multi-component weighted formula:
- 25% governed_auc
- 20% leakage cleanliness
- 15% calibration quality
- 15% fold stability  
- 10% feature trustworthiness
- 10% train/test generalization gap
- 5% data sufficiency

### GAP-02: No Calibration Assessment
**Risk:** Predicted probabilities (e.g., 0.87 attrition probability) are shown without any calibration check. If the model is overconfident, the displayed probabilities are misleading.

**Required fix:** CalibrationGovernor module with:
- Brier score (lower = better)
- Expected Calibration Error (ECE)
- Overconfidence detection
- Calibration quality label: Good / Moderate / Poor / Not Evaluated

### GAP-03: Financial Insights Still Show USD
**Risk:** insight_generator.py formats financial exposure as "USD" even when SAR is configured.

**Required fix:** Pass currency through InsightGenerator; use configured currency in all financial mentions.

---

## Governance Items Already Resolved

| Item | Resolution |
|------|-----------|
| Confidence contradictions | confidence_governance.py 5-dimension system |
| Fake zero burnout | Optional[float] + evidence modes in risk_intelligence.py |
| Fake department | Empty list returned; department_column_found=False on org |
| Hardcoded USD in UI | Currency selector + CURRENCY_SYMBOLS used in app.py |
| Causal language in features | Associative templates in feature_trustworthiness.py |
| Executive aggressive language | "Risk Signal" + human oversight disclaimer |
| Stack traces in UI | Global try/except in page dispatcher |
| Employee ID exposure | Employee #001 masking in demo mode |
| AUC governance | governed_auc ≤ raw AUC when leakage/validation fails |
| Leakage types | 12-type detection in leakage_detector.py |
| Model deployment gate | deployment_safe flag in model_validator.py |
