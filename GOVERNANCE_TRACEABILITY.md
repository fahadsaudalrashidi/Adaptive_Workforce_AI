# AI Governance Traceability
**Platform:** Adaptive Workforce Intelligence Engine v2.4.0  
**Updated:** 2026-05-19  
**Purpose:** Every executive conclusion must be traceable to source data, transformations, confidence adjustments, and applied warnings.

---

## Traceability Philosophy

The platform operates on the principle of **traceable AI governance**:

> "If we cannot explain how we arrived at a conclusion, we should not present it as a conclusion."

Every risk score, insight, recommendation, and executive summary must have:
1. A source feature chain
2. A confidence score with derivation
3. All governance adjustments applied
4. Evidence level classification
5. Warnings that were triggered

---

## Insight Traceability Chain

### For Every HR Risk Score

```
Raw Data Upload
    ↓ [DatasetProfiler] → quality_score, missing_pct, n_rows
    ↓ [SemanticMapper] → column semantic roles, target_col
    ↓ [AdaptiveRouter] → dataset_type, routing_confidence
    ↓ [DatasetContract] → allowed/blocked analyses
    ↓ [DataHealer] → imputation log, rows_healed
    ↓ [FeatureFactory] → engineered_features, manifest
    ↓ [MLRouter] → model_type, AUC, OOF predictions
    ↓ [LeakageDetector] → leakage_risk_score, n_critical, governed_AUC
    ↓ [ModelValidator] → validation_status, deployment_safe
    ↓ [CalibrationEngine] → brier_score, ECE, calibration_quality
    ↓ [FeatureTrustworthinessAssessor] → feature_trust, dominance_flag
    ↓ [ConfidenceGovernor] → 9-component reliability, exec_readiness
    ↓ [RiskIntelligence] → individual_risk, department_risk, org_risk
    ↓ [InsightGenerator] → executive_summary, recommended_actions
    ↓ [ReportGenerator] → scientific_validity_section, deployment_verdict
    ↓ Executive Dashboard
```

### For Every Biosignal Profile

```
Raw Biosignal Upload
    ↓ [DatasetProfiler] → signal_type detection (HR/EDA/BVP/TEMP/ACC/IBI)
    ↓ [BiosignalAdapter] → window_features, composite_scores
    ↓ NON-CLINICAL DISCLAIMER always attached
    ↓ No attrition predictions, no employee labels, no HR pipeline
    ↓ BiosignalProfile → stress_proxy, quality_score, disclaimer
    ↓ [InsightGenerator] → biosignal_context only
    ↓ Biosignal Intelligence Page
```

---

## Confidence Score Traceability

### 9-Component Model Reliability Formula (as of v2.4.0)

| Component | Weight | Source | Fallback |
|-----------|--------|--------|---------|
| AUC quality | 22% | MLRouter.best_metric_value | 0.60 |
| Leakage cleanliness | 20% | LeakageDetector.leakage_risk_score | 0.60 |
| Calibration quality | 15% | CalibrationEngine.brier_score / ECE | 0.60 |
| CV fold stability | 13% | ValidationReport.FOLD_STABILITY check | 0.60 |
| Feature trustworthiness | 10% | FeatureTrustworthinessAssessor.overall_trust | 0.70 |
| Train/test generalization | 10% | ValidationReport.HOLDOUT_VALIDITY check | 0.65 |
| Data sufficiency | 5% | n_rows | computed |
| Class balance | 2% | minority_class_pct | 0.65 |
| Deployment safety | 3% | ValidationReport.deployment_safe | 0.65 |

**Hard governance caps applied after formula:**
- `validation_overall_status == INVALID` → score ≤ 0.45
- `validation_overall_status == DEGRADED` → score ≤ 0.72
- `validation_n_fail > 0` → score × (1 - 0.08 × n_fail)
- `routing_confidence < 0.50` → analysis_confidence ≤ 0.70
- `data_quality < 0.55` → analysis_confidence ≤ 0.65
- `CRITICAL leakage` → analysis_confidence ≤ 0.50

All governance adjustments are recorded in `UnifiedConfidenceReport.caveats`.

---

## Evidence Level Classification

Every insight is classified by evidence level:

| Level | Criteria | Language Used |
|-------|----------|---------------|
| **Strong** | AUC > 0.75, Brier < 0.10, no leakage, n > 1000 | "Data suggests...", "Analysis indicates..." |
| **Moderate** | AUC 0.65–0.75, Brier 0.10–0.18, low leakage, n 200–1000 | "There are indications that...", "Patterns suggest..." |
| **Weak** | AUC 0.55–0.65, or moderate leakage, or n < 200 | "Insufficient evidence to conclude...", "Uncertain — requires validation" |
| **Not Evaluated** | No model, unsupervised, or biosignal | "Not evaluated", "No predictive model trained" |

**Anti-hallucination rule:** Never upgrade evidence level to make a conclusion sound stronger. Always degrade conservatively.

---

## Construct Traceability

### BurnoutRisk
- **Source features:** Overwork_Index, CommitmentScore, FatigueProxy, WorklifeBalance_Score, Overtime_Hours
- **Computation:** Composite from available columns; `None` (not 0.0) when no evidence columns found
- **Governed by:** `risk_intelligence.py:_compute_burnout_risk()` — explicit evidence check
- **Traceable**: YES — `IndividualRisk.burnout_mode` records the evidence source

### EngagementRisk
- **Source features:** EngagementScore, JobSatisfactionRating, ManagerRating, PerformanceRating
- **Computation:** 1.0 - mean(available columns); `None` when no evidence columns found
- **Governed by:** `risk_intelligence.py:_compute_engagement_risk()` — explicit evidence check

### AttritionProbability
- **Source:** Supervised ML model trained on uploaded dataset
- **Not available when:** No target column, or dataset routed to unsupervised path
- **Fallback:** Unsupervised risk score from `unsupervised_risk_scores()` — clearly labeled as "statistical pattern score, not attrition probability"

### DepartmentRisk
- **Source:** Aggregation of individual risks within detected department groups
- **Governed by:** Minimum 5 employees for reliability; `reliability_flag` set for small groups
- **Fallback:** `"Department column not detected"` when no department-like column found

---

## Executive Language Governance

### Forbidden Phrases (FORBIDDEN_EXECUTIVE_PHRASES in settings.py)
The system will never generate the following language in executive outputs:
- terminate, fire, dismiss, layoff
- will leave, will resign, will quit
- certain to leave, guaranteed to leave
- must be removed, should be removed
- eliminate this employee

### Mandatory Associative Language
All insights use statistical association, not causal claims:
- "associated with" (not "causes")
- "correlated with" (not "predicts with certainty")
- "suggests" (not "proves")
- "indicates a pattern" (not "confirms")

### Mandatory Disclaimers
- `HUMAN_OVERSIGHT_DISCLAIMER` shown on every sensitive page
- Non-clinical disclaimer shown first on every biosignal page
- "Statistical indicator only. Human validation required." on every risk signal header
- Deployment verdict (NOT SAFE / CAUTION / LIMITED / SUITABLE) in every HR report

---

## Governance Adjustment Log

Every governance adjustment is recorded in `UnifiedConfidenceReport.caveats` and in `GovernanceLogger` (logs/governance.jsonl).

### Example trace for a governed analysis:
```
Dataset: IBM_HR_Attrition.csv (1,470 rows)
Routing: hr_attrition (confidence=0.92, locked=True)
Model: XGBoost (original_AUC=0.82)
LeakageDetector: CLEAN (risk=0.03, critical=0)
Calibration: GOOD (Brier=0.087, ECE=0.032)
FeatureTrust: Reliable (no dominance)
ValidationReport: VALID (deployment_safe=True)
ConfidenceGovernor: model_reliability=0.81
  - AUC 82% × 0.22 = 0.180
  - Leakage 97% × 0.20 = 0.194
  - Calibration 65% × 0.15 = 0.098   (Brier-derived)
  - Fold stability 60% × 0.13 = 0.078 (not evaluated)
  - Feature trust 90% × 0.10 = 0.090
  - Train/test gap 65% × 0.10 = 0.065 (not evaluated)
  - Data sufficiency 100% × 0.05 = 0.050
  - Class balance 65% × 0.02 = 0.013  (not evaluated)
  - Deployment safety 100% × 0.03 = 0.030
  Total: 0.798 → rounded to 0.80
ExecReadiness: READY
Caveats: ["CV fold stability not evaluated", "Train/test gap not evaluated"]
```

---

## Audit Trail Storage

### Current Implementation
- `GovernanceLogger` writes to `logs/governance.jsonl` (JSONL, append-only)
- Every analysis run emits structured events for: routing, leakage, calibration, model training
- `DriftMonitor.set_baseline()` writes `logs/drift_baseline.json`

### Production Requirements (not yet implemented)
- Append-only audit log with cryptographic signatures
- Per-user analysis trail with anonymized employee IDs
- GDPR-compliant data retention and deletion
- SOC2 audit export format

---

## GOVERNANCE_TRACEABILITY Checklist

Before any executive presentation of results, verify:

- [ ] Routing decision was logged with confidence score
- [ ] Leakage report shows CLEAN or MODERATE with no critical flags
- [ ] Calibration quality is GOOD or MODERATE (not POOR or NOT_EVALUATED for deployment)
- [ ] Model reliability score ≥ 0.65 for presentation-grade output
- [ ] No FORBIDDEN_EXECUTIVE_PHRASES in any output
- [ ] HUMAN_OVERSIGHT_DISCLAIMER present on every page
- [ ] BurnoutRisk is None or has explicit evidence source (not fabricated from 0.0)
- [ ] Department list is empty (not fake) when no department column detected
- [ ] All financial figures use configured currency (SAR default), not hardcoded USD
- [ ] Scientific Validity section present in every exported HR report
