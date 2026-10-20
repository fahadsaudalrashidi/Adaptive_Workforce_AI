# Enterprise Onboarding Workflow
**Module:** `backend/core/enterprise_onboarding_pipeline.py`
**Phase:** 6 — Enterprise Commercialization & Deployment Architecture
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

The `EnterpriseOnboardingPipeline` is the entry gate for every new tenant dataset. No dataset proceeds to model training without passing through this pipeline. A blocked dataset cannot reach the science pipeline — the blocking is enforced by the `overall_status` field, not by a configuration flag that could be overridden.

The pipeline produces an `OnboardingReport` that serves as the audit record of what was checked, what was found, and what decision was made.

---

## 2. Pipeline Stages

The pipeline runs 7 stages in sequence. Each stage produces an `OnboardingStageResult` with:
- `stage_name` — human-readable name
- `status` — PASS / WARN / FAIL / SKIP
- `score` — float 0.0–1.0 contribution to the readiness score
- `findings` — list of human-readable observations (warnings and notes)
- `blocking_issues` — list of issues that cause the overall status to become BLOCKED

A `FAIL` status on any stage triggers BLOCKED overall status regardless of the aggregate score.

### Stage 1: Dataset Upload Validation

**Purpose:** Verify the dataset is minimally viable for processing.

| Check | Threshold | Result |
|---|---|---|
| Row count | < 100 → BLOCKED | Ensures minimum training viability |
| Column count | < 3 → BLOCKED | Prevents degenerate inputs |
| Row count warning | < 300 | WARN — high variance expected |
| Null fraction per column | > 30% → WARNING | High-null columns flagged |

**Score:** 1.0 (no warnings), 0.7 (warnings), 0.0 (fail)

### Stage 2: Schema Fingerprinting

**Purpose:** Identify the source ERP, normalize column names, detect PII and leakage columns.

Uses `SaudiSchemaIntelligenceEngine.analyse()` from Phase 5.

| Check | Result |
|---|---|
| PII columns detected | BLOCKED — must be removed before training |
| Leakage columns detected | BLOCKED — must be removed before training |
| ERP confidence LOW/NONE | WARN — manual column mapping review recommended |
| Schema completeness < 0.5 | WARN — limited theory construct coverage expected |

**Score:** 1.0 (no warnings, no PII/leakage), proportional to schema_completeness_score (with warnings)

### Stage 3: Governance Validation

**Purpose:** Saudi-specific data quality validation — salary plausibility, age/tenure bounds, attrition rate sanity, duplicate detection.

Uses `SaudiDataGovernanceEngine.validate()` from Phase 5.

| Severity | Action |
|---|---|
| CRITICAL finding | BLOCKED |
| HIGH finding | WARN; score reduced by 0.15 per finding |
| MEDIUM finding | WARN; score = 0.8 |
| CRITICAL PII detected | BLOCKED (secondary to Stage 2) |

**Score:** 1.0 (no violations) → 0.0 (CRITICAL) via linear penalty

### Stage 4: Temporal Leakage Scan

**Purpose:** Detect exit dates, hire dates, snapshot columns, and other temporal leakage patterns. Check that random split is safe.

Uses `TemporalValidationGuard.validate()` from Phase 4.

| Finding | Result |
|---|---|
| CRITICAL temporal finding | BLOCKED |
| HIGH temporal finding | WARN |
| Random split unsafe | WARN — recommended strategy noted |

**Score:** 1.0 (no warnings), 0.6 (warnings), 0.0 (fail)

### Stage 5: Theory Compatibility Scan

**Purpose:** Check which of the 7 theory constructs can be computed from the available columns.

Uses `TheoryAwareColumnMapper.map()` from Phase 4.

| Compatible Constructs | Score | Status |
|---|---|---|
| 5–7 | 1.0 | PASS |
| 3–4 | 0.7 | WARN |
| 1–2 | 0.4 | WARN |
| 0 | 0.1 | WARN (model proceeds on raw features only) |

**Note:** Zero compatible constructs is a WARN, not a FAIL. The model can still train on raw features. However, a governance note is generated explaining that the theoretical grounding is absent and results should be treated with extra caution.

### Stage 6: Unsupported Construct Rejection

**Purpose:** Block any column in the dataset that matches a quarantined legacy construct name.

Compares `df.columns` against `LEGACY_DISABLED_CONSTRUCTS` from `model_input_contract.py`.

| Finding | Result |
|---|---|
| Any quarantined column found | BLOCKED |
| No quarantined columns | PASS |

**Score:** Binary gate — 1.0 (PASS) or 0.0 (FAIL)

**Why this matters:** If a tenant's HR system exports a column named `BurnoutRiskComposite` or `RetentionRisk`, these are recognized as quarantined Layer B constructs that would contaminate the model. They must be renamed or removed before onboarding.

### Stage 7: Calibration Readiness

**Purpose:** Verify that the target column has sufficient positive cases for reliable model calibration.

| Check | Threshold | Result |
|---|---|---|
| Positive cases (attrition events) | < 20 → BLOCKED | Calibration unreliable |
| Attrition rate > 50% | WARNING | Suspicious — possible biased sample |
| Attrition rate < 5% | WARNING | Class imbalance handling required |
| Fewer than 50 positive cases | WARNING | Department-level analysis will be unreliable |
| No target column provided | SKIP (score = 0.7) | Cannot assess calibration |

**Score:** 1.0 (healthy), 0.7 (warnings), 0.0 (fail)

---

## 3. Deployment Readiness Score

The score is computed as a weighted average of stage scores:

| Stage | Weight |
|---|---|
| Dataset Upload Validation | 0.20 |
| Schema Fingerprinting | 0.20 |
| Governance Validation | 0.30 |
| Temporal Leakage Scan | 0.20 |
| Theory Compatibility Scan | 0.20 |
| Unsupported Construct Rejection | 0.00 (binary gate, handled via blocking_issues) |
| Calibration Readiness | 0.10 |

Note: weights sum to 1.20 before normalization because Schema and Upload each get 0.20. The `_compute_readiness_score` method divides by the total weight of non-skipped stages.

### Score → Status Mapping

| Score | Status (when no blocking issues) |
|---|---|
| ≥ 0.80 | READY — proceed to model training |
| 0.50–0.79 | CONDITIONAL — proceed with documented caveats |
| < 0.50 | BLOCKED — do not proceed |

**Any blocking issue overrides the score** — a dataset with a perfect score of 1.0 that has a PII column detected is still BLOCKED.

---

## 4. Onboarding Report Fields

| Field | Type | Purpose |
|---|---|---|
| `company_id` | str | Tenant identifier |
| `assessed_at` | str | ISO 8601 UTC timestamp |
| `n_rows` | int | Dataset row count |
| `n_columns` | int | Dataset column count |
| `overall_status` | str | READY / CONDITIONAL / BLOCKED |
| `deployment_readiness_score` | float | 0.0–1.0 aggregate score |
| `stages` | list[OnboardingStageResult] | Per-stage results |
| `erp_system_detected` | str | ERP fingerprint result |
| `erp_confidence` | str | HIGH / MEDIUM / LOW / NONE |
| `schema_completeness_score` | float | IBM column coverage fraction |
| `theory_compatible_constructs` | list[str] | Constructs that can be computed |
| `blocked_constructs` | list[str] | Constructs blocked due to missing columns |
| `unsupported_mappings` | list[str] | Quarantined columns found in dataset |
| `pii_columns_detected` | list[str] | PII columns from both scanners |
| `leakage_columns_detected` | list[str] | Leakage columns from both scanners |
| `governance_warnings` | list[str] | Non-blocking governance concerns |
| `blocking_issues` | list[str] | Issues causing BLOCKED status |
| `summary` | str | One-line human-readable summary |
| `governance_notes` | list[str] | Full governance note trail |

---

## 5. Schema Drift Detection

When a tenant re-uploads a dataset after the initial onboarding, the pipeline runs again from scratch. Schema drift is detected naturally:
- Columns added: new constructs may activate
- Columns removed: constructs that previously activated may be blocked
- Column types changed: null fraction checks may flag newly problematic columns

The governance note trail in `OnboardingReport.governance_notes` provides a complete record of what was found in each run. Comparing two sequential `OnboardingReport` objects from the same tenant reveals schema drift.

---

## 6. Arabic Schema Handling

The pipeline passes Arabic column names through all stages without modification:
- `SaudiSchemaIntelligenceEngine` recognizes Arabic column names for Mudad/Qiwa schemas
- `SaudiDataGovernanceEngine` matches Arabic PII and leakage patterns
- `TheoryAwareColumnMapper` handles Arabic column names via its bilingual mapping logic
- `TemporalValidationGuard` pattern matching works on lowercase versions of column names (Arabic patterns included)

Arabic datasets that pass onboarding are fully supported. The theory construct compatibility score may be lower (3–5 constructs vs. 6–7 for IBM-style schemas) due to the different column structure of government platforms.

---

## 7. Usage Example

```python
from backend.core.enterprise_onboarding_pipeline import run_enterprise_onboarding
import pandas as pd

# Load tenant data
df = pd.read_csv("client_hr_data.csv")

# Run onboarding
report = run_enterprise_onboarding(
    df=df,
    company_id="acme_corp_001",
    target_col="Attrition",
    salary_col="MonthlyIncome",
    age_col="Age",
    tenure_col="YearsAtCompany",
)

# Decision gate
if report.overall_status == "BLOCKED":
    print(f"Onboarding blocked: {report.blocking_issues}")
    raise ValueError("Dataset cannot proceed to model training.")

print(f"Onboarding {report.overall_status}: score={report.deployment_readiness_score:.2f}")
print(f"ERP: {report.erp_system_detected} ({report.erp_confidence} confidence)")
print(f"Theory constructs available: {report.theory_compatible_constructs}")
```

---

## 8. Test Coverage

`tests/test_phase6_enterprise_deployment.py::TestEnterpriseOnboardingPipeline` — 17 tests covering all stages and edge cases.

All 17 pass. No regressions in the 352-test suite.

---

*Workflow documentation produced as part of Phase 6 — Enterprise Commercialization & Deployment Architecture. Scientific traceability governed by the research paper PDF as primary source of truth.*
