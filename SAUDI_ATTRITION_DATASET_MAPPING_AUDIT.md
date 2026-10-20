# Saudi Attrition Dataset Column Mapping Audit — Phase 10

**Date:** 2026-05-21  
**Dataset:** Original Dataset of Employee Attrition (1).xlsx  
**Rows:** 1,191 | **Columns (raw):** 35  
**Normaliser:** `backend/core/saudi_attrition_normalizer.py`

---

## 1. Purpose

This audit documents every column mapping applied to the real Saudi attrition dataset during normalisation. It serves as the authoritative record for:
- Audit trail of data transformations
- Scientific justification for proxy construct assignments
- Reproducibility of any analysis that uses this dataset

---

## 2. Column Mapping Table (35 columns)

| Raw Column Name | Issue | Canonical Name |
|----------------|-------|---------------|
| `ID` | Pass-through | `employee_row_id` |
| `Attrition` | Pass-through | `attrition` |
| `Gender ` | Trailing space | `gender` |
| `Age` | Pass-through | `age` |
| ` Maritalstatus` | Leading space, no underscore | `marital_status` |
| `\xa0Academic_degree ` | NBSP prefix + trailing space | `academic_degree` |
| `Academic_degree ` | Trailing space (fallback) | `academic_degree` |
| `Years_Experience` | Pass-through | `years_experience` |
| `Years_experience_lastorganization` | Long name | `years_in_current_org` |
| `Sector` | Pass-through | `sector` |
| `Department` | Pass-through | `department` |
| `JobTitle` | CamelCase | `job_title` |
| `MonthlySalary` | CamelCase, range text | `monthly_salary_range` |
| `Allowances` | Pass-through | `allowances` |
| `MedicalInsurance` | CamelCase | `medical_insurance` |
| `Bonus` | Pass-through | `bonus` |
| `OverTime` | CamelCase | `overtime` |
| `Payment_Overtime` | Pass-through | `payment_overtime` |
| `Rewards&Wages_Satisfaction` | Ampersand | `rewards_wages_satisfaction` |
| `Get_ Deserved_Promotion` | Internal space after underscore | `get_deserved_promotion` |
| `Training_programs_ During_last_three_years` | Internal space | `training_programs_during_last_three_years` |
| `Useful_Training_Programs` | Pass-through | `useful_training_programs` |
| `Business_Travel` | Pass-through | `business_travel` |
| `Job_Support` | Pass-through | `job_support` |
| `Recognition` | Pass-through | `recognition` |
| `Emotional_Commitment` | Pass-through | `emotional_commitment` |
| `Job_Engagement` | Pass-through | `job_engagement` |
| `Work_Live_Balance` | Typo: "Live" vs "Life" | `work_life_balance` |
| `Distance_to_work` | Pass-through | `distance_to_work` |
| `Physical_Stress` | Pass-through | `physical_stress` |
| `Psychological_Exhaustion` | Pass-through | `psychological_exhaustion` |
| `Job_Stability` | Pass-through | `job_stability` |
| `Health_Issues` | Pass-through | `health_issues` |
| `Environment_Satisfaction` | Pass-through | `environment_satisfaction` |
| `Job_Satisfaction` | Pass-through | `job_satisfaction` |
| `Job_Opportunities` | Pass-through | `job_opportunities` |

---

## 3. Attrition Target Normalisation

**Raw column:** `Attrition`  
**Values observed:** `" Yes"`, `" No"`, `"Yes"`, `"No"`  
**Normalisation method:** `.strip().lower()` → membership check

| Raw value | Stripped | Canonical | Binary |
|-----------|---------|-----------|--------|
| `" Yes"` | `"yes"` | Yes | 1 |
| `" No"` | `"no"` | No | 0 |
| `"Yes"` | `"yes"` | Yes | 1 |
| `"No"` | `"no"` | No | 0 |

**Unparseable values:** 0 (all 1,191 rows successfully mapped)

---

## 4. Salary Range Parsing

**Raw column:** `MonthlySalary` → canonical: `monthly_salary_range`  
**Pattern observed:** `"From X to Y S.R"` (SAR currency suffix)  
**Derived columns:** `monthly_salary_range_min`, `monthly_salary_range_max`, `monthly_salary_range_midpoint`

| Pattern | Example | Min | Max | Midpoint logic |
|---------|---------|-----|-----|----------------|
| `From X to Y` | `"From 5000 to 10000 S.R"` | 5,000 | 10,000 | `(lo + hi) / 2` |
| `Less than X` | `"Less than 5000 SAR"` | 0 | 5,000 | `hi * 0.75` |
| `More than X` | `"More than 15000"` | 15,000 | 22,500 | `lo * 1.25` |
| Standalone | `"7500"` | 7,500 | 7,500 | exact value |

**Scientific note:** Midpoint imputation for bounded ranges introduces measurement error. Analyses using `monthly_salary_range_midpoint` should report this limitation explicitly.

---

## 5. Proxy Construct Assignments

All constructs are **PROXY** — derived from available Saudi HR columns, not validated psychometric scales.

### COR (Conservation of Resources Theory — Hobfoll, 1989)

**BurnoutRisk_Proxy**
- Columns: `physical_stress`, `psychological_exhaustion`, `health_issues`
- Direction: Higher = more burnout risk
- Justification: COR theory predicts resource depletion (physical/psychological) leads to burnout and turnover intention. These columns are the closest available proxies in the Saudi dataset.
- Limitation: None of these columns are validated burnout scales (e.g., MBI, Oldenburg). They are ordinal satisfaction ratings repurposed as depletion signals.

**SatisfactionIndex_Proxy**
- Columns: `job_satisfaction`, `environment_satisfaction`, `rewards_wages_satisfaction`, `work_life_balance`
- Direction: Higher = more satisfied (resource-rich state)
- Limitation: Four columns of unequal psychometric weight; no validated factor structure.

**EngagementScore_Proxy**
- Columns: `job_engagement`, `emotional_commitment`
- Direction: Higher = more engaged
- Limitation: No validated engagement scale (e.g., UWES) is available. These are single-item proxies.

### JD-R (Job Demands-Resources Model — Bakker & Demerouti, 2007)

**CareerProgression_Proxy**
- Columns: `get_deserved_promotion`, `training_programs_during_last_three_years`, `useful_training_programs`
- Direction: Higher = better career progression (resource axis)

**SalaryGrowth_Proxy**
- Columns: `monthly_salary_range`, `allowances`, `bonus`, `medical_insurance`
- Direction: Higher = better compensation (economic resource axis)
- Note: `monthly_salary_range` uses midpoint values; see Section 4.

**TenureRatio_Proxy**
- Columns: `years_experience`, `years_in_current_org`
- Direction: Ratio of org tenure to total experience (job embeddedness proxy)

### Mobley (Turnover Decision Process — Mobley, 1977)

**WithdrawalPressure_Proxy**
- Columns: `job_opportunities`, `job_stability`, `distance_to_work`
- Direction: Higher `job_opportunities` = higher pull toward leaving; higher `job_stability` = lower withdrawal pressure
- Note: Scale direction conflict exists — `job_opportunities` and `job_stability` push in opposite directions. Composite use requires explicit direction weighting.

### Adams (Equity Theory — Adams, 1965)

**PerceivedEquity_Proxy**
- Columns: `get_deserved_promotion`, `payment_overtime`, `rewards_wages_satisfaction`
- Direction: Higher = more equitable perception

---

## 6. Scientific Limitations

1. **No validated Western instruments**: None of the 8 proxy constructs use validated psychometric scales (MBI, UWES, JES, etc.). They are best-available proxies only.
2. **Saudi cultural context**: Response bias in self-reported satisfaction scales may differ from the Western samples on which COR/JD-R/Mobley/Adams theories were originally validated.
3. **Ordinal data treated as quasi-continuous**: Satisfaction ratings (e.g., "Satisfied"/"Not satisfied") are converted to numeric values for construct computation. This assumes equal intervals, which may not hold.
4. **Cross-sectional data**: The dataset captures a single time point. Causal claims about attrition drivers cannot be supported.

---

## 7. Audit Certification

| Property | Value |
|---------|-------|
| Normaliser module | `backend/core/saudi_attrition_normalizer.py` |
| Column map version | Phase 10, 2026-05-21 |
| Proxy construct map | `PROXY_CONSTRUCT_MAP` dict (8 entries) |
| All constructs labelled proxy | YES |
| Unparseable attrition values | 0 |
| Salary parsing failure rate | 0% (all range formats covered) |

*Audit produced by automated normalisation pipeline with manual review of column alias map.*
