# Cross-Company Validation Report
**Scope:** Multi-ERP schema adaptation, schema portability, and feature consistency across Saudi enterprise deployments
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Executive Summary

The Adaptive Workforce AI pipeline was designed against IBM HR Benchmark data (1,470 employees, 35 columns). Saudi enterprise deployments introduce 7 additional HR system architectures with different column naming conventions, bilingual schemas, and regulatory-specific fields. This report documents how the pipeline handles schema variability across these systems and what guarantees hold regardless of ERP source.

**Key finding:** All 7 theory constructs compute correctly across all recognized ERP schemas when column mapping succeeds. Calibration guarantees hold dataset-wide; department-level reliability degrades predictably for small units.

---

## 2. Schema Variability Matrix

| ERP System | Column Naming | Language | Theory Construct Coverage |
|---|---|---|---|
| IBM HR Benchmark | camelCase (JobSatisfaction) | English | 7/7 (reference dataset) |
| SAP SuccessFactors | PascalCase with prefixes (SF_EmployeeID) | English | 7/7 after normalization |
| Oracle HRMS / Fusion | snake_case (person_id, pay_annualized_salary) | English | 7/7 after normalization |
| Mudad (Government) | Arabic snake_case (رقم_الموظف) | Arabic | 5/7 (limited job satisfaction data) |
| Qiwa (Labor Market) | Mixed English/Arabic | Bilingual | 4/7 (contract focus, limited satisfaction) |
| Generic Saudi HR | Varies | Arabic/English | 3–7 (schema-dependent) |
| Generic Bilingual | Varies | Mixed | 3–7 (schema-dependent) |
| Generic English HR | Varies | English | 3–7 (schema-dependent) |

**Interpretation:** Mudad and Qiwa schemas focus on payroll and compliance data rather than attitudinal measures (satisfaction, engagement). This is expected — these platforms are government payroll/labor systems, not talent management systems. Organizations using Mudad/Qiwa as their only HR data source will have 4–5 constructs blocked. This is a governance feature, not a failure — the system correctly reports what it cannot compute.

---

## 3. Column Normalization Consistency

### 3.1 Salary Column Handling

Salary column detection across ERPs:

| ERP | Raw Column | Normalized To | Salary Scale |
|---|---|---|---|
| IBM | `MonthlyIncome` | `MonthlyIncome` | SAR 5,000–25,000/month |
| SAP SF | `base_pay` | `MonthlyIncome` | SAR 5,000–25,000/month |
| Oracle | `pay_annualized_salary` | `MonthlyIncome` | SAR 60,000–240,000/year |
| Mudad | `الراتب_الأساسي` | `MonthlyIncome` | SAR 4,000–50,000/month |

**Oracle annual vs. monthly detection:** Oracle's `pay_annualized_salary` consistently exceeds the `_SAR_LIKELY_ANNUAL_THRESHOLD` (60,000 SAR). The governance engine detects this and flags that the salary column appears to represent annual rather than monthly income. The `IncomePerLevel` construct uses the salary value as-is; the `SaudiDataGovernanceEngine` records the scale detection in `salary_currency_suspected`.

### 3.2 Employee ID Handling

Employee ID columns are detected and quarantined by `ModelInputContract` (check #5 — ID memorization patterns) regardless of column naming:

| ERP | Raw Column | ModelInputContract Action |
|---|---|---|
| IBM | `EmployeeNumber` | Blocked (ID memorization) |
| SAP SF | `EmployeeID` | Blocked |
| Oracle | `person_id` | Blocked |
| Mudad | `رقم_الموظف` | Blocked |
| Qiwa | `employee_id` | Blocked |

The block fires on pattern matching, not column name lookup. Any column containing "id", "number", "code" in an employee identifier context is quarantined.

### 3.3 Leakage Column Portability

Leakage detection (`_SAUDI_ERP_LEAKAGE_COLUMNS` + `_LEAKAGE_COLUMN_PATTERNS`) operates on both the raw column name and the normalized name. This ensures:
- `termination_reason` (Oracle) is flagged
- `سبب_الإنهاء` (Mudad Arabic form) is flagged
- `reason_for_leaving` (generic) is flagged

The same leakage event is caught regardless of ERP source.

---

## 4. Feature Completeness by ERP

Feature completeness is the fraction of IBM reference columns that are present (or have a normalized equivalent) in the deployed schema:

| ERP | Completeness Score | Constructs Active | Constructs Blocked |
|---|---|---|---|
| IBM HR Benchmark | 1.00 | 7 | 0 |
| SAP SuccessFactors | 0.75–0.90 | 6–7 | 0–1 |
| Oracle HRMS | 0.70–0.85 | 6–7 | 0–1 |
| Mudad | 0.35–0.55 | 4–5 | 2–3 |
| Qiwa | 0.25–0.40 | 3–4 | 3–4 |
| Generic Saudi HR | 0.30–0.70 | 3–6 | 1–4 |

A completeness score below 0.5 triggers a governance note in `SchemaIntelligenceReport` recommending feature subset analysis before model training. Models trained on fewer than 4 active constructs should be evaluated with extra care — the theoretical grounding is weaker with fewer inputs.

---

## 5. Cross-Company Theory Construct Stability

### 5.1 SatisfactionIndex

Formula: `(JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction) / 3`

- **IBM:** All three columns present. SatisfactionIndex computed on all 1,470 rows.
- **SAP SF:** `job_satisfaction_score` → `JobSatisfaction` (normalized); `environment_satisfaction` → `EnvironmentSatisfaction`. Construct active.
- **Oracle:** `job_satisfaction` → `JobSatisfaction`; `work_environment_score` → `EnvironmentSatisfaction`. Construct active.
- **Mudad:** `رضا_الموظف` (employee satisfaction) provides one dimension only. Construct BLOCKED — single-dimension SatisfactionIndex would misrepresent the COR resource bundle construct.
- **Qiwa:** No satisfaction columns. Construct BLOCKED.

### 5.2 BurnoutRisk

Formula: `OverTime_binary × (1 / WorkLifeBalance) × (1 / JobInvolvement)`

- **IBM:** All three present. BurnoutRisk computed.
- **Oracle:** `overtime_flag` → `OverTime`; `work_life_balance_score` → `WorkLifeBalance`. Construct active.
- **Mudad:** Overtime hours available (`ساعات_العمل_الإضافية`) but `WorkLifeBalance` absent. Construct BLOCKED.
- **Qiwa:** No attitudinal columns. Construct BLOCKED.

### 5.3 TenureRatio

Formula: `YearsAtCompany / (TotalWorkingYears + ε)`

This construct is most portable across ERPs because tenure data appears in virtually all payroll systems:

- **IBM, SAP SF, Oracle, Mudad, Qiwa:** Tenure data available (under various column names). TenureRatio is the most consistently activating construct across all ERPs.

### 5.4 IncomePerLevel

Formula: `MonthlyIncome / (JobLevel + 1)`

- Requires both salary and job grade/level. Available in IBM, SAP SF, Oracle (with normalization). Not available in Mudad/Qiwa (which have salary but not job level in the Nitaqat/Saudization sense that maps to IBM's JobLevel 1–5 scale).

---

## 6. Calibration Portability

### 6.1 What Transfers Across Companies

- The calibration methodology (Platt scaling + reliability diagrams) is model-agnostic and transfers regardless of ERP.
- The concentration and FP rate thresholds (40%/60% concentration, 30%/50% FP) are grounded in operational capacity constraints, not dataset-specific statistics, and are valid across Saudi enterprises.

### 6.2 What Does Not Transfer

- **Decision threshold:** The 0.5 default threshold is appropriate for balanced datasets. Saudi enterprise datasets with 8–15% natural attrition rates require threshold adjustment for acceptable precision-recall trade-offs.
- **Department reliability thresholds:** The 10/5 employee thresholds are calibrated for organizations with ≥100 employees and ≥5 departments. Very small organizations (20–50 employees) should not use department-level predictions at all.
- **Fold AUC std thresholds:** The 0.08/0.12 thresholds assume 5-fold CV with ≥300 training examples. For smaller datasets, expected variance is higher.

### 6.3 Cross-Company Calibration Transfer Prohibition

A model calibrated on IBM HR Benchmark data cannot be directly deployed to a Saudi enterprise without retraining and recalibration. The IBM dataset:
- Reflects a U.S. labor market with different attrition base rates
- Has different salary distributions (USD, not SAR)
- Has different overtime patterns (U.S. Fair Labor Standards Act context)
- Lacks Saudization compliance pressure

**This pipeline enforces this through `SaudiDataGovernanceEngine`**, which detects when the salary distribution, age distribution, and attrition rate are inconsistent with Saudi labor market norms and flags the dataset as potentially non-Saudi.

---

## 7. Cross-Company Test Evidence

`tests/test_phase5_saudi_validation.py::TestCrossCompanySchemaAdaptation` — 5 tests:

| Test | Schema | Assertion |
|---|---|---|
| `test_ibm_to_oracle_normalization` | Oracle HRMS | Oracle columns normalize correctly |
| `test_ibm_to_qiwa_partial_constructs` | Qiwa | Fewer constructs active; no crash |
| `test_arabic_schema_handled` | Mudad | Arabic columns processed; governance notes populated |
| `test_salary_scale_detection` | Oracle annual | Annual salary flag set; warning issued |
| `test_leakage_detected_cross_schema` | Oracle with `termination_reason` | Leakage flag regardless of ERP source |

All 5 pass. No regressions in the full 302-test suite.

---

## 8. Recommendation Matrix

| Deployment Scenario | Recommendation |
|---|---|
| IBM HR data (research replication) | Full pipeline, all 7 constructs expected |
| SAP SF data | Full pipeline with normalization; verify construct activation report |
| Oracle HRMS | Full pipeline; check annual vs. monthly salary flag |
| Mudad-only data | Deploy with TenureRatio + SalaryGrowth only; alert HR that satisfaction constructs unavailable |
| Qiwa-only data | Not recommended for attrition prediction — insufficient attitudinal data |
| Mudad + SAP SF combined | Full pipeline after schema merge; verify join keys don't introduce duplicates |
| Generic Arabic HR | Run `SaudiSchemaIntelligenceEngine.analyse()` first; review completeness score before proceeding |

---

## 9. Schema Governance Commitment

The pipeline will not:
- Substitute a missing required column with a correlated proxy
- Compute a partial construct (e.g., SatisfactionIndex from 2 of 3 dimensions)
- Silently skip governance checks on unrecognized schemas
- Apply IBM-trained thresholds to non-IBM data without flagging the mismatch

These commitments preserve the scientific validity of construct measurements across deployment contexts.

---

*Report produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
