# Calibration Reliability Audit
**Module:** `backend/core/calibration_reliability_audit.py`
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

A well-calibrated model is a prerequisite for any risk-based HR intervention. If the model says "30% attrition probability," 30% of employees with that score should actually leave within the prediction window. Miscalibration means HR teams waste resources on interventions that target the wrong employees, or fail to act on employees who are genuinely at risk.

This module extends the base `CalibrationEngine` with three additional governance layers specific to enterprise HR deployment:

1. **High-risk concentration governance** — prevents the model from labeling an implausibly large fraction of the workforce as "high risk," which destroys operational utility and signals a calibration failure.
2. **Department-level reliability** — detects organizational units too small for reliable prediction and flags them for human review.
3. **Cross-fold stability** — measures variance in AUC across validation folds to catch models that perform well on average but catastrophically on subsets of the data.

---

## 2. High-Risk Concentration Governance

### 2.1 Thresholds

| Level | Threshold | Response |
|---|---|---|
| WARNING | >40% of employees scored "high risk" | Log warning; flag in report |
| CRITICAL | >60% of employees scored "high risk" | Block deployment; require calibration review |

### 2.2 Rationale

If 60% of a 1,000-person company scores as high attrition risk, the model has failed to discriminate — it is either miscalibrated, trained on a biased sample, or the decision threshold has been set incorrectly. The 40%/60% thresholds are based on:

- **Practical utility:** HR teams cannot meaningfully intervene on more than ~20–30% of the workforce simultaneously.
- **Calibration signal:** Attrition rates in stable organizations are typically 10–25%. A model flagging 60% as high-risk is inconsistent with this base rate unless the organization is in acute crisis.
- **Saudi context:** Saudi enterprise HR budgets for retention interventions are capacity-constrained. A high-concentration flag prevents budget misallocation.

### 2.3 Calculation

```
high_risk_fraction = (y_prob >= decision_threshold).mean()
```

The `decision_threshold` defaults to 0.5 but can be overridden. In Saudi enterprise deployments, lower thresholds (0.3–0.4) are sometimes used to improve recall. The concentration check uses the same threshold that is passed to downstream decision logic.

---

## 3. False Positive Rate Governance

### 3.1 Thresholds

| Level | FP Rate | Response |
|---|---|---|
| WARNING | >30% | Log warning |
| FLAG | >50% | Include in report; require HR sign-off before deployment |

### 3.2 Calculation

```
fp_rate = FP / (FP + TN)
       = sum((y_pred == 1) & (y_true == 0)) / sum(y_true == 0)
```

where `y_pred = (y_prob >= decision_threshold).astype(int)`.

### 3.3 Business Consequence

A 50% FP rate means that for every two employees flagged as "high risk," one will not leave. At scale:
- 500 employees flagged → 250 are false positives
- Each retention intervention costs time and signals to the employee that management has concerns
- False positives can paradoxically trigger the attrition they were meant to prevent

The 30% warning threshold is calibrated to trigger early review before business harm occurs.

---

## 4. Department-Level Reliability

### 4.1 Thresholds

| Level | Department N | Reliability Label |
|---|---|---|
| RELIABLE | ≥10 employees | `RELIABLE` |
| UNRELIABLE | 5–9 employees | `UNRELIABLE` |
| CRITICAL | <5 employees | `CRITICAL` |

### 4.2 `DepartmentReliabilityRecord` Fields

| Field | Type | Purpose |
|---|---|---|
| `department` | str | Department identifier |
| `n_employees` | int | Headcount in this department |
| `mean_predicted_prob` | float | Average risk score |
| `is_reliable` | bool | True when `n >= 10` |
| `reliability_level` | str | RELIABLE / UNRELIABLE / CRITICAL |
| `governance_note` | str | Human-readable caveat |

### 4.3 Governance Note Content

CRITICAL departments receive the note:
> "Department has <5 employees — individual predictions are not statistically reliable. HR decisions for this unit must rely on qualitative assessment."

UNRELIABLE departments receive:
> "Department has <10 employees — predictions are indicative only. Use alongside manager judgment."

### 4.4 Saudi Context

Saudi organizations often have small departments due to Saudization requirements creating specialized roles. A 3-person Saudi national specialist unit must be treated differently from a 200-person shared services department. The department reliability audit makes this distinction explicit and auditable.

---

## 5. Cross-Fold Stability

### 5.1 Thresholds

| Level | AUC Standard Deviation | Response |
|---|---|---|
| WARNING | std > 0.08 | Flag potential overfitting |
| CRITICAL | std > 0.12 | Block deployment; model is unstable |

### 5.2 Rationale

A model with fold AUC values of [0.85, 0.84, 0.86, 0.85, 0.84] (std ≈ 0.007) is stable. A model with fold AUC values of [0.90, 0.70, 0.85, 0.65, 0.88] (std ≈ 0.10) has learned different patterns in different data subsets — it is not generalizable.

The 0.08/0.12 thresholds are calibrated for 5-fold cross-validation on HR datasets with 500–5,000 employees (typical Saudi enterprise scale). For larger datasets, expected std is lower; for smaller datasets, higher std is expected and thresholds may need adjustment.

### 5.3 What Causes High Fold Instability

- **Temporal structure not respected** — random splits that leak future information cause some folds to appear much better than others
- **Class imbalance by fold** — if attrition events cluster in time (e.g., post-merger resignation wave), some folds have much higher base rates
- **Small dataset** — with <300 employees, a single fold's attrition cluster dominates
- **Feature leakage in specific folds** — a leakage column present in training but not validation of some folds

---

## 6. Risk Band Reliability (`RiskBandReliability`)

The auditor segments the predicted probability distribution into risk bands and checks calibration within each band:

| Band | Probability Range | Expected Outcome Rate |
|---|---|---|
| Low Risk | [0.0, 0.3) | ~10–20% actual attrition |
| Medium Risk | [0.3, 0.6) | ~30–50% actual attrition |
| High Risk | [0.6, 1.0] | ~60–80% actual attrition |

### 6.1 `RiskBandReliability` Fields

| Field | Type | Purpose |
|---|---|---|
| `band_name` | str | Low / Medium / High Risk |
| `thresholds` | tuple[float, float] | Probability range |
| `n_employees` | int | Employees in this band |
| `fraction_actually_positive` | float | Observed attrition rate |
| `mean_predicted_prob` | float | Average predicted probability |
| `calibration_gap` | float | abs(predicted - observed) |
| `is_well_calibrated` | bool | gap < 0.15 |
| `reliability_note` | str | Human-readable calibration note |

A calibration gap >0.15 within a risk band means the model's risk communication to HR is systematically misleading in that band.

---

## 7. `CalibrationReliabilityReport` — Overall Reliability

The `overall_reliability` field summarizes the audit outcome:

| Value | Condition |
|---|---|
| `RELIABLE` | All checks pass |
| `UNRELIABLE` | One or more WARNING-level issues |
| `CRITICAL` | Any CRITICAL-level issue (concentration >60%, fold std >0.12, or base calibration failure) |
| `NOT_EVALUATED` | Insufficient data to assess (e.g., no department series provided) |

A `CRITICAL` overall reliability is a mandatory deployment blocker.

---

## 8. Integration with Base Calibration Engine

`CalibrationReliabilityAuditor` calls `CalibrationEngine.calibrate()` from `backend/core/calibration_engine.py` and wraps its `CalibrationReport` as `base_calibration` in the output. This preserves the existing calibration audit trail while adding the five new governance dimensions.

```python
auditor = CalibrationReliabilityAuditor()
report = auditor.audit(
    y_true=labels,
    y_prob=predictions,
    department_series=df["Department"],
    fold_aucs=[0.82, 0.83, 0.81, 0.84, 0.82],
    decision_threshold=0.5
)
```

---

## 9. Test Coverage

`tests/test_phase5_saudi_validation.py::TestCalibrationReliabilityAudit` — 11 tests:

| Test | Assertion |
|---|---|
| `test_high_risk_concentration_warning` | >40% high-risk → warning flag set |
| `test_high_risk_concentration_critical` | >60% high-risk → CRITICAL overall |
| `test_fp_rate_warning` | FP rate >30% → fp_governance_flag set |
| `test_department_reliable` | Large dept → `RELIABLE` |
| `test_department_unreliable_small` | <5 employees → `CRITICAL` |
| `test_fold_instability_warning` | std >0.08 → warning |
| `test_fold_instability_critical` | std >0.12 → CRITICAL |
| `test_overall_reliable` | Clean data → `RELIABLE` |
| `test_risk_band_calibration_gap` | Miscalibrated band → `is_well_calibrated == False` |
| `test_convenience_function` | `audit_calibration_reliability()` returns correct type |
| `test_no_department_series` | None department_series → graceful handling |

All 11 pass. No regressions in the full 302-test suite.

---

## 10. Saudi Enterprise Deployment Guidance

For Saudi enterprises deploying this system:

1. Run `CalibrationReliabilityAuditor.audit()` after every model retraining cycle.
2. Store `CalibrationReliabilityReport` as part of the model artifact alongside the model weights.
3. Any `overall_reliability == "CRITICAL"` result must be reviewed by a qualified data scientist before the model serves predictions.
4. Department records with `reliability_level == "CRITICAL"` must trigger a note in the HR dashboard: "Predictions for this team are not statistically reliable. Please use additional context."
5. Cross-fold std > 0.08 should trigger review of the temporal split strategy (see `TemporalValidationGuard`).

---

*Audit produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
