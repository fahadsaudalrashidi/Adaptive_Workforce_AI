# Executive Reporting Governance
**Module:** `backend/core/executive_reporting_layer.py`
**Phase:** 6 — Enterprise Commercialization & Deployment Architecture
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

The `ExecutiveReportingLayer` transforms model predictions into governance-safe, language-audited intelligence briefings for HR leadership. It is designed for two audiences:
- **CHRO / HR Director** — workforce-level volatility indicators, intervention priorities, confidence reliability
- **C-Suite / Board** — high-risk concentration alerts, cost exposure context, organizational stability signals

All output text is routed through `EnterpriseLanguageGuard` before being returned. No individual employee data appears in executive reports. No deterministic predictions. No causal language.

---

## 2. What Executive Reports Contain

### 2.1 Organization Risk Summary

| Metric | Description |
|---|---|
| `n_employees_total` | Total workforce assessed |
| `fraction_low_risk` | Employees with predicted probability < 0.30 |
| `fraction_medium_risk` | Employees with predicted probability 0.30–0.59 |
| `fraction_high_risk` | Employees with predicted probability ≥ 0.60 |
| `mean_risk_score` | Mean predicted probability (0–1 scale) |
| `workforce_volatility_indicator` | LOW / ELEVATED / HIGH / CRITICAL |
| `high_risk_concentration_flag` | True when >40% of workforce in high-risk band |

### 2.2 Workforce Volatility Indicator

| Level | High-Risk Fraction | Meaning |
|---|---|---|
| LOW | < 15% | Workforce risk indicators within expected range |
| ELEVATED | 15–29% | Some organizational units show elevated risk patterns |
| HIGH | 30–44% | Substantial proportion of workforce shows elevated risk patterns — HR review recommended |
| CRITICAL | ≥ 45% | Critical proportion — immediate HR leadership review required |

**Governance note:** Volatility levels are derived from population-level statistics. They describe patterns in the data, not predictions about individual employees.

### 2.3 Department Risk Summaries

Per-department aggregates:
- `mean_risk_score` — department-level average predicted probability
- `risk_band` — LOW / MEDIUM / HIGH based on mean score
- `fraction_high_risk` — fraction of department in high-risk band
- `is_reliable` — True when department has ≥10 employees
- `reliability_note` — human-readable reliability caveat
- `recommended_action_category` — governance-safe intervention category

Departments are sorted by `mean_risk_score` (highest first) to highlight priority areas.

### 2.4 Intervention Recommendation Categories

Recommendations are expressed as intervention categories, not specific actions or directives:

| Volatility | Recommendation Category |
|---|---|
| LOW | "Routine monitoring — low risk indicator profile" |
| ELEVATED | "Targeted department review — focus retention programs on highest-risk departments" |
| HIGH / CRITICAL | "Workforce-wide engagement review — elevated risk indicators suggest systemic pattern" |

All recommendation text passes `EnterpriseLanguageGuard.audit()` before being stored in the report. Any text that fails the language audit is replaced with the safe alternative.

---

## 3. What Executive Reports Do NOT Contain

This is enforced by architecture, not policy:

| Excluded Data | Why |
|---|---|
| Individual employee risk scores | PDPL individual profiling restrictions; `ExecutiveReport` dataclass has no field for individual scores |
| Employee names or IDs | EmployeeNumber column values never written to report text |
| Deterministic predictions ("will leave") | EnterpriseLanguageGuard blocks all deterministic language |
| Causal claims ("because of low satisfaction") | EnterpriseLanguageGuard blocks causal language |
| Medical/clinical language | EnterpriseLanguageGuard blocks medical terminology |
| Individual department with <5 employees | Department summaries exclude depts below minimum size |
| Model feature weights | Feature importance is not surfaced to executive reports |
| Training data statistics | Raw data characteristics not included in executive reports |

---

## 4. Language Guard Integration

Every piece of generated text goes through this sequence:

```
Generate text string
    ↓
EnterpriseLanguageGuard.audit(text)
    ↓
audit.is_compliant?
    YES → use text as-is
    NO  → use audit.safe_text (auto-remediated)
         + increment language_violations_detected
         + append governance note
```

`ExecutiveReport.language_compliant` is `True` only when `language_violations_detected == 0`. A report with `language_compliant == False` has been auto-remediated but must be reviewed by a qualified HR professional before distribution.

**Test verification:** `test_narrative_is_language_compliant` and `test_recommendations_language_compliant` verify that all generated text is compliant after language guard processing.

---

## 5. High-Risk Concentration Alert

When `fraction_high_risk > 0.40`, the report includes a `high_risk_concentration_alert` — a governance-safe notice to HR leadership that the model's discrimination is limited. This alert:

1. Describes the concentration as a data characteristic, not a crisis declaration
2. Recommends calibration review before planning interventions
3. Is itself audited by `EnterpriseLanguageGuard`
4. Contains no individual employee data

When concentration exceeds 60%, the `CalibrationReliabilityAuditor` independently flags this as CRITICAL (see `CALIBRATION_RELIABILITY_AUDIT.md`). The two flags are independent: the executive report flag is a reporting tool; the calibration auditor flag is a deployment blocker.

---

## 6. Reliability Communication

`ExecutiveReport.confidence_reliability` reflects the `CalibrationReliabilityAuditor` assessment:

| Value | Executive Communication |
|---|---|
| `RELIABLE` | "The model's predictions are considered statistically reliable for this dataset." |
| `UNRELIABLE` | "Model reliability is below acceptable thresholds. Treat all risk indicators as preliminary." |
| `CRITICAL` | "IMPORTANT: Model reliability is critically low. This report must not inform HR decisions until model issues are resolved." |
| `NOT_EVALUATED` | "Model reliability has not been evaluated. Treat all risk indicators with appropriate caution." |

A `CRITICAL` reliability rating adds a governance note explicitly stating that the report must not be used for HR decisions. This is the only case where the executive report itself recommends against its own use.

---

## 7. Department Reliability Communication

Departments with fewer than 10 employees receive `is_reliable = False` and a reliability note:
> "Team size ([n]) is below the minimum threshold for reliable statistical predictions. Use qualitative HR assessment for this team."

Their `recommended_action_category` is:
> "Qualitative HR Assessment Recommended — insufficient data for statistical analysis"

This prevents executives from drawing conclusions about small teams based on statistically unreliable aggregates.

---

## 8. Cross-Fold Stability Integration

When `fold_auc_std` is provided:
- If `> 0.08`: a governance note flags moderate stability concerns
- If `> 0.12`: a governance note flags critical stability (model is inconsistent across data subsets)

This information is surfaced to executives as a confidence qualifier, not a technical metric. The note uses plain language: "model performance is inconsistent across data subsets."

---

## 9. Test Coverage

`tests/test_phase6_enterprise_deployment.py::TestExecutiveReportingLayer` — 16 tests:

| Test | Assertion |
|---|---|
| `test_returns_executive_report` | Correct return type |
| `test_narrative_is_language_compliant` | `language_compliant == True` |
| `test_no_deterministic_claims_in_narrative` | Zero `CAT_DETERMINISTIC_CLAIM` violations |
| `test_department_summaries_generated` | Summaries present when `department_col` provided |
| `test_department_summaries_sorted_by_risk` | Descending order by mean_risk_score |
| `test_high_concentration_flag_set` | Flag set when >40% high-risk |
| `test_concentration_alert_is_language_compliant` | Alert text passes guard |
| `test_critical_reliability_adds_governance_note` | CRITICAL note present |
| `test_org_summary_fractions_sum_to_one` | fractions sum within 0.01 of 1.0 |
| `test_intervention_recommendations_not_empty` | Recommendations present |
| `test_recommendations_language_compliant` | Each recommendation passes guard |
| `test_no_individual_employee_data_in_report` | No EmployeeNumber pattern in narrative |
| `test_volatility_indicator_valid_value` | One of four valid labels |
| `test_governance_notes_populated` | Notes list non-empty |
| `test_unreliable_small_dept_flagged` | Small dept marked not reliable |
| `test_fold_auc_std_instability_noted` | Instability note present |

All 16 pass. No regressions in the 352-test suite.

---

## 10. Distribution Policy

Executive reports may be distributed to:
- HR Director / CHRO — full report including department summaries
- CEO / Board — organization summary and volatility indicator only (no department detail)
- Finance (for cost planning) — `BusinessValueReport` only (no risk scores)

Executive reports must NOT be distributed to:
- Line managers (department-level detail might enable individual identification in small teams)
- Individual employees
- External parties without explicit PDPL data sharing agreement

---

*Governance document produced as part of Phase 6 — Enterprise Commercialization & Deployment Architecture. Scientific traceability governed by the research paper PDF as primary source of truth.*
