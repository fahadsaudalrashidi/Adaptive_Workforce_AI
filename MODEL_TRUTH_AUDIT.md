# Model Truth Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Post-training scientific validity governance  
**Status:** IMPLEMENTED — ModelTruthAuditor runs after every training

---

## Purpose

The Model Truth Audit is a mandatory post-training check that goes beyond leakage detection.
It surfaces honesty problems that would otherwise produce scientifically misleading executive reports.

**Triggering condition:** Runs automatically after every `MLRouter.train()` call via `audit_model_truth()`.  
**Result stored in:** `TrainingResult.truth_audit_report` (type: `ModelTruthAuditReport`)

---

## Eight Truth Checks

| # | Check Name | Trigger Condition | Verdict Levels |
|---|-----------|------------------|----------------|
| 1 | AUC_BELIEVABILITY | AUC ≥ 0.97 → CRITICAL; AUC ≥ 0.92 on HR data → FLAG | PASS / FLAG / CRITICAL |
| 2 | LEAKAGE_SUMMARY | Critical flags from LeakageDetector | PASS / WARN / FLAG / CRITICAL |
| 3 | THRESHOLD_SAFETY | Threshold < 0.15 or >40% population flagged high-risk | PASS / WARN / FLAG |
| 4 | CALIBRATION_REQUIRED | AUC ≥ 0.85 → calibration mandatory | PASS / FLAG |
| 5 | HIGH_CARDINALITY_RISK | JobTitle/role feature > 30% importance | PASS / WARN / FLAG |
| 6 | DEPT_ONEHOT_DETECTED | Department_* one-hot group found | PASS / WARN / FLAG |
| 7 | CLASS_IMBALANCE_HONEST | Minority class < 10% | PASS / WARN |
| 8 | VERSION_CONSISTENCY | PLATFORM_VERSION startswith "2.3" | PASS / WARN |

---

## Verdict Hierarchy

```
PASS → WARN → FLAG → CRITICAL
```

Overall verdict = worst individual check verdict.

### Deployment Recommendations by Overall Verdict

| Verdict | Recommendation |
|---------|---------------|
| PASS | SUITABLE — All truth checks passed |
| WARN | SUITABLE WITH CAVEATS — Minor warnings present |
| FLAG | CONDITIONAL — Resolve FLAG-level issues before executive reporting |
| CRITICAL | NOT SUITABLE — Do not use for decisions |

---

## Calibration Governance Rule

When `AUC ≥ 0.85`:
- Calibration (Brier Score + ECE) is **mandatory** before issuing "Suitable" verdict
- If `CalibrationReport.brier_score is None` or `quality == "Poor"` → **FLAG**
- This prevents high-AUC models with inflated scores from appearing trustworthy

---

## Threshold Sanity Rule

When `optimal_threshold < 0.15` OR `>40% of OOF predictions ≥ threshold`:
- **WARN** or **FLAG** (depending on severity)
- Output uses "priority review segment" language, not "high-risk employees"
- Executive reports must disclose the flagged population percentage

---

## AUC Believability Thresholds

| Threshold | Action |
|-----------|--------|
| AUC ≥ 0.97 | CRITICAL — implausible for HR data |
| AUC ≥ 0.92 (HR datasets, no CRITICAL leakage) | FLAG — suspiciously high |
| Governed AUC < Original AUC | WARN — leakage governance applied |
| AUC < 0.92 | PASS (believability check) |

**Background:** Real-world attrition models on genuine HR data typically achieve 0.65–0.80 AUC.
Above 0.92 without a strong leakage explanation should be investigated.

---

## Current Platform State (v2.5.1)

- `ModelTruthAuditor` implemented in `backend/core/model_truth_audit.py`
- `audit_model_truth()` called from `ml_router._train_classification()` after validation
- `TrainingResult.truth_audit_report` stores result for downstream use
- Version check now reads 2.5.1 → VERSION_CONSISTENCY check passes
- Calibration mandate (AUC ≥ 0.85) wired but calibration runs in app layer — `calibration_report=None` on first run; app layer should pass CalibrationReport if available

---

## Known Gaps

| Gap | Severity | Resolution |
|-----|----------|-----------|
| Calibration report not passed to truth auditor in initial run | MEDIUM | App layer should update truth_audit_report post-calibration |
| Ablation tests not implemented | LOW | Would require 6 model variants; deferred to v3.0 |
| SHAP values not integrated | LOW | sklearn importances used; SHAP deferred |
