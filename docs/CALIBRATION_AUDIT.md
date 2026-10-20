# Calibration Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Calibration governance, mandatory calibration rules, Brier/ECE tracking

---

## Summary

| Item | Status |
|------|--------|
| CalibrationEngine implemented | ✅ Yes (`backend/core/calibration_engine.py`) |
| Brier Score computed | ✅ When OOF predictions available |
| ECE (Expected Calibration Error) computed | ✅ When OOF predictions available |
| Reliability diagram values computed | ✅ |
| Overconfidence detection | ✅ |
| Mandatory calibration for AUC ≥ 0.85 | ✅ Governed in `ModelTruthAuditor` (v2.5.1) |
| "Suitable" verdict blocked when not calibrated at high AUC | ✅ FLAG returned |
| Calibration shown in UI panel | ✅ `governance_panel.py` → `render_calibration_panel()` |

---

## Calibration Mandate (v2.5.1 Rule)

**Rule:** When model AUC ≥ 0.85, calibration evaluation is **mandatory** before a "Suitable" deployment verdict can be issued.

```
IF auc >= 0.85 AND (brier_score is None OR quality == "Poor"):
    → ModelTruthAuditReport.overall_verdict = FLAG or worse
    → deployment_recommendation = "CAUTION — Calibration mandatory but not satisfied"
```

**Rationale:** High AUC models on HR data carry elevated leakage risk. Even when no CRITICAL
leakage flags are found, a well-performing model that is poorly calibrated produces risk scores
that cannot be interpreted as literal probability values. This misleads HR decision-makers
who may over-rely on the numeric outputs.

---

## Calibration Metrics

### Brier Score
- Range: 0 (perfect) to 1 (worst) — random classifier scores ~0.25 on 50/50 data
- Target: < 0.20 for "Good" calibration on typical HR data
- Computed on OOF predictions (never on training set)

### Expected Calibration Error (ECE)
- Measures mean deviation between predicted probabilities and actual outcome rates
- Computed across 10 equal-width probability bins
- Target: < 0.10 for acceptable calibration

### Overconfidence Detection
- Flags when mean predicted probability exceeds actual positive rate by > 0.15
- Generates `CalibrationQuality.Poor` when overconfidence is severe

### Reliability Diagram
- Stored as list of (mean_predicted, actual_fraction) tuples per bin
- Rendered in the UI Calibration Panel
- Perfect calibration lies on the diagonal

---

## When Calibration Cannot Be Computed

Calibration requires OOF (out-of-fold) predictions from cross-validation. It is NOT computed when:

1. **Dataset too small** — < 30 samples per class → OOF predictions may be empty or unreliable
2. **All-negative labels** — if the positive class has 0 occurrences in training data
3. **OOF not generated** — models that fail during cross_val_predict leave oof_predictions=None

In these cases: `CalibrationReport.brier_score = None`, quality shows "Not Evaluated".

**Governance position:** "Not Evaluated" calibration is treated as potentially problematic
in deployment verdicts — the report discloses it but does not block deployment unless AUC ≥ 0.85.

---

## Calibration Quality Labels

| Label | Brier Score | ECE | Meaning |
|-------|------------|-----|---------|
| Excellent | < 0.10 | < 0.05 | Probabilities are highly reliable |
| Good | 0.10–0.15 | 0.05–0.08 | Probabilities are reliable for decision support |
| Fair | 0.15–0.20 | 0.08–0.12 | Use with caution; disclose uncertainty |
| Poor | > 0.20 or overconfident | > 0.12 | Do not use probabilities as literal values |
| Not Evaluated | N/A | N/A | OOF unavailable — calibration not assessed |

---

## Platform Configuration

```python
# backend/core/calibration_engine.py
class CalibrationEngine:
    def evaluate(self, y_true, y_prob) -> CalibrationReport:
        ...
```

Called in:
1. **`_smoke_test.py`** — validates on synthetic HR data
2. **`tests/test_calibration.py`** — 17 calibration unit tests
3. **`frontend/pages/hr_attrition_page.py`** — renders calibration panel in UI
4. **`frontend/components/governance_panel.py`** — `render_calibration_panel()`

---

## Known Gap

The `ModelTruthAuditor` currently receives `calibration_report=None` on the first training run
because calibration is computed in the app layer after training. To fully enforce the mandatory
calibration rule, the app layer should call:

```python
from backend.core.model_truth_audit import ModelTruthAuditor
auditor = ModelTruthAuditor()
# After calibration is computed:
result.truth_audit_report = auditor.audit(
    ml_result=result,
    leakage_report=result.leakage_report,
    calibration_report=cal_report,  # pass actual report
    dataset_type=contract.dataset_type,
)
```

This is deferred to v3.0 app-layer integration.
