# ROI Estimation Governance
**Module:** `backend/core/roi_estimation_engine.py`
**Phase:** 6 — Enterprise Commercialization & Deployment Architecture
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose and Scope

The `ROIEstimationEngine` produces defensible, assumption-cited business value estimates for attrition risk intelligence. It is designed to answer one legitimate question for HR and Finance stakeholders:

> "If our high-risk employees leave, what would it cost to replace them?"

It is NOT designed to:
- Guarantee cost savings
- Project specific ROI percentages
- Replace actuarial or financial modeling
- Claim that interventions will produce specific outcomes

All estimates are presented as ranges with explicit uncertainty notes and cited assumption sources.

---

## 2. Assumption Citations

### 2.1 Replacement Cost Multipliers

**Source:** CIPD Middle East HR Benchmark Report (2023); SHRM "The True Cost of Turnover" (2022)

| Role Category | Multiplier Range | Basis |
|---|---|---|
| Standard roles (Job Level 1–3) | 1.5–2.5× monthly salary | CIPD Gulf HR survey median |
| Senior roles (Job Level ≥ 4) | 2.5–4.0× monthly salary | CIPD senior executive premium |

**Why these multipliers:** The 1.5–2.5× range for standard roles captures:
- Recruitment advertising and agency fees (SAR 5,000–15,000 per role)
- Interview and selection time (2–4 weeks manager time)
- Onboarding and productivity ramp (3–6 months to full productivity)
- Knowledge transfer and documentation costs
- Cover/overtime costs during vacancy

The senior premium reflects executive search costs, longer vacancy periods, and greater institutional knowledge loss.

**What is NOT included in these multipliers:**
- Nitaqat/Saudization compliance costs (can add 15–30% for Saudization-sensitive roles)
- HRDF training contribution requirements
- End-of-service gratuity (governed by Saudi Labour Law Art. 84 — calculated separately)
- Immigration costs for expatriate replacement
- Productivity loss during transition (difficult to quantify without company-specific data)

### 2.2 Intervention Effectiveness

**Source:** Hom, P.W., Lee, T.W., Shaw, J.D., & Hausknecht, J.P. (2017). "One hundred years of employee turnover theory and research." *Journal of Applied Psychology*, 102(3), 530–545.

**Conservative range:** 25–50% of at-risk employees retained through targeted intervention.

**Why conservative:** The literature range of 25–50% reflects:
- Studies with well-implemented, personalized retention programs (not blanket bonuses)
- Organizational contexts with manager quality and HR capacity to execute
- The upper end (50%) represents organizations with strong HR infrastructure

**What this range does NOT account for:**
- Push factors outside the employer's control (family relocation, better opportunity, personal circumstances)
- Employees whose decision to leave is already finalized
- Organizational capacity to execute interventions simultaneously on multiple employees
- Quality of the intervention (generic vs. personalized vs. manager-led)

### 2.3 Default Salary Assumption

When no salary column is provided: **SAR 8,000/month** (Saudi median estimate based on GOSI wage data, 2024).

This is clearly flagged in `BusinessValueReport.governance_warnings` when it is used.

---

## 3. Estimate Types and Governance

### 3.1 Annual Turnover Cost Exposure

**Definition:** The replacement cost if ALL high-risk employees leave in the next period.

**Formula:**
```
Exposure_low = n_high_risk × median_monthly_salary × 1.5
Exposure_high = n_high_risk × median_monthly_salary × 2.5
```

**Governance note:** This is a worst-case upper bound, not a prediction. In practice, not all high-risk employees will leave. The actual rate depends on base rates, macro-economic conditions, and intervention effectiveness.

**Required disclosure:** Every use of this estimate must be accompanied by the assumption list and uncertainty notes stored in `ROIEstimate.assumptions` and `ROIEstimate.uncertainty_notes`.

### 3.2 Senior Role Replacement Exposure

**Definition:** Additional cost exposure for senior employees (Job Level ≥ 4) in the high-risk band.

**Governance note:** Computed only when `job_level_col` is provided and the dataset contains senior employees in the high-risk band. When `n_senior_risk < 5`, confidence is set to `LOW` and the uncertainty note explicitly states the small sample limitation.

### 3.3 Retention Opportunity Estimate

**Definition:** The potential cost avoidance if targeted interventions retain 25–50% of high-risk employees.

**Formula:**
```
Retained_low = n_high_risk × 0.25
Retained_high = n_high_risk × 0.50
Opportunity_low = Retained_low × median_salary × 1.5
Opportunity_high = Retained_high × median_salary × 2.5
```

**Governance constraint:** This estimate carries `confidence = "LOW"` regardless of dataset size. The literature range has wide variance across organizational contexts, and the estimate must not be presented as a financial projection.

**Mandatory uncertainty note (stored in ROIEstimate.uncertainty_notes):**
> "Intervention effectiveness varies substantially across organizations, industries, and individual cases. This estimate must not be presented as a financial projection to stakeholders."

### 3.4 Department-Level Exposure

**Definition:** Per-department cost exposure for the top-3 highest-exposure departments.

**Governance constraint:** Department estimates with `n_risk < 10` carry `confidence = "LOW"`. The uncertainty note explicitly references the `CalibrationReliabilityAuditor` department reliability assessment.

---

## 4. Prohibited Uses

The `BusinessValueReport` and its estimates must NEVER be used to:

1. **Claim guaranteed savings** — "This system will save you SAR X" is prohibited. The estimates are ranges with cited uncertainty.
2. **Present as financial projections** — in investor materials, financial statements, or board-level financial planning without actuary review.
3. **Remove uncertainty disclosures** — all displayed estimates must show the low-high range, not a point estimate.
4. **Omit assumption citations** — any presentation of a cost figure must include its source (CIPD/SHRM citation).
5. **Compare across tenants** — a different organization's estimate is not a benchmark for a given client.
6. **Attribute to specific employees** — cost estimates are population-level; individual attribution is prohibited.

---

## 5. `BusinessValueReport` Fields and Governance

| Field | Type | Governance Note |
|---|---|---|
| `n_employees_total` | int | Total workforce assessed |
| `n_high_risk` | int | Count above `high_risk_threshold` (default 0.60) |
| `high_risk_fraction` | float | Fraction of workforce in high-risk band |
| `estimates` | list[ROIEstimate] | All estimates with ranges and assumptions |
| `assumptions` | CostAssumptions | Full assumption record with source citations |
| `governance_warnings` | list[str] | Warnings about data quality or missing inputs |
| `governance_notes` | list[str] | Mandatory disclosures about estimate limitations |
| `summary` | str | One-line summary (includes range, not point estimate) |

### 5.1 `CostAssumptions` Fields

| Field | Stored Value |
|---|---|
| `replacement_multiplier_low` | 1.5 |
| `replacement_multiplier_high` | 2.5 |
| `monthly_salary_sar` | Actual median or default |
| `intervention_effectiveness_low` | 0.25 |
| `intervention_effectiveness_high` | 0.50 |
| `salary_source` | Data provenance string |
| `multiplier_source` | "CIPD Middle East HR Benchmark 2023; SHRM 2022" |
| `effectiveness_source` | "Hom et al. (2017), Journal of Management" |

---

## 6. Confidence Levels

| Level | Meaning |
|---|---|
| `LOW` | Estimate has high uncertainty — data quality, sample size, or assumption validity is limited |
| `MEDIUM` | Estimate is reasonable given the data — n ≥ 50 and salary data available |
| `HIGH` | Not currently assigned — no estimate in this system currently qualifies for HIGH confidence |

**Design choice:** HIGH confidence is intentionally not assigned to any estimate. All attrition cost estimates involve inherent uncertainty (labor market conditions, individual circumstances, intervention capacity). Presenting any estimate as HIGH confidence would misrepresent the epistemic state.

---

## 7. Saudi-Specific Cost Adjustments (Not Yet Implemented)

The following Saudi-specific costs are recognized but not yet included in the base estimates. They should be noted in client communications:

1. **End-of-service gratuity (EOSB):** Required under Saudi Labour Law Art. 84. Formula: 0.5 month salary × years (first 5 years) + 1 month salary × years (after 5 years). This is a significant cost for long-tenured employees and can exceed the replacement cost multiplier for senior employees.

2. **Saudization compliance cost:** Replacing a Saudi national with another requires recruiting against Nitaqat quotas. Saudization-sensitive roles may have 15–30% higher effective replacement costs due to limited candidate pools.

3. **HRDF levy:** Saudi employers pay 2.5% of Saudized employees' salaries to HRDF. If a departing Saudi employee is replaced by an expatriate (reducing Saudization ratio), the levy calculation changes.

4. **Iqama renewal and visa costs:** For expatriate replacements, visa processing and Iqama costs (SAR 2,400–4,800/year) add to replacement costs.

These adjustments will be added in a future version once standardized Gulf HR cost data is available.

---

## 8. Test Coverage

`tests/test_phase6_enterprise_deployment.py::TestROIEstimationEngine` — 13 tests:

| Test | Assertion |
|---|---|
| `test_returns_business_value_report` | Correct return type |
| `test_estimates_present_when_high_risk_exists` | Estimates populated |
| `test_cost_range_is_valid` | low ≤ high for all estimates |
| `test_assumptions_always_populated` | Assumptions list non-empty for all estimates |
| `test_uncertainty_note_always_present` | uncertainty_notes present for all estimates |
| `test_governance_notes_populated` | Governance notes non-empty |
| `test_no_predictions_produces_warning` | Warning when y_prob=None |
| `test_n_high_risk_count_correct` | Correct count at threshold |
| `test_salary_col_used_when_provided` | No crash with/without salary col |
| `test_department_estimates_generated` | Department estimates present |
| `test_retention_opportunity_is_subset_of_exposure` | Opportunity ≤ Exposure |
| `test_zero_high_risk_produces_no_cost_estimate` | No estimates when no high-risk |
| `test_assumptions_cite_sources` | multiplier_source contains "SHRM" or "CIPD" |

All 13 pass. No regressions in the 352-test suite.

---

*Governance document produced as part of Phase 6 — Enterprise Commercialization & Deployment Architecture. Financial estimates cite CIPD Middle East HR Benchmark 2023, SHRM 2022, and Hom et al. (2017). Not financial advice. Must be reviewed by HR and Finance professionals before use in business planning.*
