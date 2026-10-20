# Psychometric Scale Audit
## Adaptive Workforce AI — HR Attrition Prediction Platform
### Saudi Company HR Dataset Compatibility Review

**Document Version:** 1.0  
**Audit Date:** 2026-05-20  
**Audience:** Psychometrics Engineer, HR Analytics Governance Board  
**Scope:** 7-construct paper formula pipeline, IBM HR baseline scales, Saudi HR adaptation risks

---

## 1. Executive Summary

This audit evaluates the psychometric integrity of the 12 IBM HR baseline scale variables used as inputs to the platform's 7-construct formula pipeline. The platform maps incoming Saudi HR dataset columns to these constructs through a 4-stage pipeline (IBM exact match → English synonym → Arabic exact match → keyword fallback). Each stage introduces measurement risk if the incoming scale does not conform to the IBM HR baseline specification.

Three critical violations are present in the current `feature_factory.py` implementation that must be resolved before Phase 3 deployment. Additionally, five scale-level psychometric risks exist in the formula definitions themselves that require governance-board awareness regardless of implementation correctness.

---

## 2. Scale Inventory — IBM HR Baseline Specification

The following table defines the authoritative measurement scale for each of the 12 required columns. Deviations from these specifications in incoming Saudi HR data constitute measurement error that propagates into all downstream construct scores.

| Column | Scale Type | Range | Anchors | Unit | Formula Role |
|---|---|---|---|---|---|
| `JobSatisfaction` | Likert | 1–4 | 1=Low, 4=High | Ordinal | SatisfactionIndex, EngagementScore |
| `EnvironmentSatisfaction` | Likert | 1–4 | 1=Low, 4=High | Ordinal | SatisfactionIndex |
| `RelationshipSatisfaction` | Likert | 1–4 | 1=Low, 4=High | Ordinal | SatisfactionIndex |
| `WorkLifeBalance` | Likert | 1–4 | 1=Bad, 4=Best | Ordinal | BurnoutRisk |
| `OverTime` | Binary | 0–1 | Yes=1, No=0 | Nominal | BurnoutRisk |
| `JobInvolvement` | Likert | 1–4 | 1=Low, 4=High | Ordinal | EngagementScore |
| `YearsAtCompany` | Continuous | 0–40+ | — | Years (integer) | TenureRatio |
| `TotalWorkingYears` | Continuous | 0–40+ | — | Years (integer) | TenureRatio |
| `MonthlyIncome` | Continuous | 5,000–30,000 | — | SAR | IncomePerLevel |
| `JobLevel` | Ordinal | 1–5 | 1=Entry, 5=Executive | Ordinal (rank) | IncomePerLevel |
| `PercentSalaryHike` | Continuous | 10–25 | — | Percentage (%) | SalaryGrowth |
| `PerformanceRating` | Ordinal | 3–4 (nominal 1–4) | 3=Excellent, 4=Outstanding | Ordinal | SalaryGrowth |

**Note on PerformanceRating:** Although the IBM HR schema defines the column as ranging 1–4, the actual dataset contains only values 3 and 4. Values 1 and 2 do not appear. This is a data-level floor effect, not a schema error, but it has severe psychometric consequences documented in Section 4.3.

---

## 3. Saudi HR Scale Drift Risk Table

Saudi HR datasets commonly diverge from IBM HR baseline specifications in the following ways. Each divergence type, its detection method, its impact on construct validity, and the required mitigation are enumerated below.

| Risk ID | Column(s) Affected | Drift Type | Detection Signal | Construct Impact | Confidence Penalty | Mitigation |
|---|---|---|---|---|---|---|
| SD-01 | All Likert columns | 1–5 scale instead of 1–4 | `max(col) == 5` | All constructs inflated | 10% | Rescale: `x_4 = 1 + (x_5 − 1) × 0.75` |
| SD-02 | `WorkLifeBalance` | Directional reversal (1=Best) | Negative WLB-burnout correlation | BurnoutRisk inverted | 20% | Reverse-score: `wlb_corrected = 5 − wlb_raw` |
| SD-03 | `WorkLifeBalance` | 0–100 continuous score | `max(col) > 10` | BurnoutRisk formula breaks | 15% | Rescale: `wlb_4 = 1 + wlb_100 × 0.03` |
| SD-04 | `JobInvolvement` | Replaced by composite EmployeeEngagement (0–100) | Column name mismatch + range > 4 | EngagementScore theoretically invalid | 25% | Flag for manual review; do not merge constructs |
| SD-05 | `PerformanceRating` | Full 1–4 range used (not compressed to 3–4) | `min(col) < 3` | SalaryGrowth range doubles; comparability lost | 15% | Document; do not rescale — retain dataset-native range |
| SD-06 | `YearsAtCompany` / `TotalWorkingYears` | Stored in months | Values > 60 with plausible tenure | TenureRatio inflated by 12× | 20% | Detect: `median(col) > 30`; divide by 12 |
| SD-07 | `PercentSalaryHike` | Stored as absolute SAR amount | Values > 100 | SalaryGrowth astronomically inflated | BLOCKED | Reject column; require human remapping |
| SD-08 | `OverTime` | Continuous hours (e.g., 45.5 hours/week) | `dtype == float` or `max(col) > 1` | BurnoutRisk loses binary semantics | 10% (binarized) | Binarize: `OT = 1 if hours > 0 else 0` |
| SD-09 | `MonthlyIncome` | Stored in USD or EUR (not SAR) | Values < 2,000 (implausible for Saudi market) | IncomePerLevel ratio distorted | 10% | Flag; apply currency conversion if rate known |
| SD-10 | `JobLevel` | Non-standard ordinal (e.g., 0-indexed or 6-level) | `min(col) == 0` or `max(col) == 6` | IncomePerLevel denominator shift | 10% | Remap to 1–5 before computation |

---

## 4. Detailed Psychometric Issue Analysis

### 4.1 Likert Scale Consistency Risks

#### 4.1.1 Scale Range Drift (1–4 vs. 1–5)

Saudi organizational surveys frequently adopt 5-point Likert formats aligned with international HR instruments (e.g., Gallup Q12, Utrecht UWES). When a Saudi dataset reports `JobSatisfaction` on a 1–5 scale, treating it as a 1–4 scale without rescaling causes systematic upward bias in the `SatisfactionIndex`.

**Quantitative effect:** A respondent scoring 5 on the Saudi 5-point scale (maximum satisfaction) would map to a raw value of 5 in the IBM 1–4 formula, exceeding the defined maximum. The `SatisfactionIndex` would report 1.25 instead of 1.00, violating the construct's theoretical ceiling.

**Rescaling formula (1–5 to 1–4):**

```
x_4 = 1 + (x_5 − 1) × 0.75
```

This linearly maps: 1→1, 2→1.75, 3→2.5, 4→3.25, 5→4.00

**Confidence penalty:** 10% applied to all constructs using the rescaled column, reflecting information loss from unit transformation.

#### 4.1.2 WorkLifeBalance 0–100 Continuous Scale

Some Saudi HR platforms (particularly those integrated with ERP systems such as SAP SuccessFactors or Oracle HCM) store `WorkLifeBalance` as a composite index from 0 to 100. This scale is not ordinal Likert data; it is a derived continuous score.

**Rescaling formula (0–100 to 1–4):**

```
wlb_4 = 1 + wlb_100 × 0.03
```

This maps: 0→1, 50→2.5, 100→4.0

**Confidence penalty:** 15%, reflecting that the conversion is an approximation across fundamentally different measurement models (composite index vs. single-item Likert).

---

### 4.2 WorkLifeBalance Directional Assumption — Critical Risk

This is the highest-severity single-variable risk in the entire pipeline.

#### 4.2.1 IBM HR Baseline Direction

In the IBM HR dataset, `WorkLifeBalance` is coded as:

- 1 = Bad
- 2 = Good
- 3 = Better
- 4 = Best

Higher scores indicate better work-life balance. The `BurnoutRisk` formula exploits this directionality:

```
BurnoutRisk = OverTime × (5 − WorkLifeBalance)
```

When `WLB = 4` (Best balance), the term `(5 − 4) = 1` — minimum burnout contribution.  
When `WLB = 1` (Bad balance), the term `(5 − 1) = 4` — maximum burnout contribution.

This is psychometrically coherent: poor work-life balance amplifies the burnout effect of overtime.

#### 4.2.2 Saudi Dataset Reversal Risk

Saudi HR instruments sometimes invert this scale, coding 1 as the most favorable outcome (consistent with some Arabic-language survey conventions where right-to-left reading influences scale anchoring). If a Saudi dataset uses:

- 1 = Best
- 4 = Bad

And the platform applies the formula without reversal correction, the `BurnoutRisk` formula inverts entirely:

- High-WLB employees (1=Best) generate maximum burnout scores: `OT × (5−1) = OT × 4`
- Low-WLB employees (4=Bad) generate minimum burnout scores: `OT × (5−4) = OT × 1`

**This is a complete semantic inversion of the construct.** The platform would identify the most balanced employees as highest burnout risk and the most overloaded employees as lowest burnout risk.

#### 4.2.3 Detection Test Cases

The following test cases are designed to reveal directional violations in production data:

**Test WLB-DIR-01 — Correlation Sign Check**

```
Expectation: corr(WorkLifeBalance, Attrition_numeric) < 0
             (better WLB predicts lower attrition probability)
Violation signal: corr(WorkLifeBalance, Attrition_numeric) > +0.10
Action: Flag dataset for directional audit; apply reverse-score correction
```

**Test WLB-DIR-02 — BurnoutRisk Monotonicity Check**

```
For employees with OverTime = 1:
  Expectation: mean(BurnoutRisk | WLB=1) > mean(BurnoutRisk | WLB=4)
  Violation signal: mean(BurnoutRisk | WLB=1) < mean(BurnoutRisk | WLB=4)
  Action: Reverse-score WorkLifeBalance before formula application
```

**Test WLB-DIR-03 — Anchor Label Verification**

```
If dataset metadata or data dictionary is available:
  Check: WLB label for value=1 contains "best" | "ممتاز" | "مثالي"
  If TRUE: Apply reverse-score transformation: wlb_corrected = 5 − wlb_raw
  Confidence penalty: 20%
```

---

### 4.3 PerformanceRating Scale Compression

#### 4.3.1 Observed Distribution in IBM HR Data

The IBM HR dataset exhibits a severe floor effect in `PerformanceRating`:

- Value 1 (Low): 0% of employees
- Value 2 (Good): 0% of employees
- Value 3 (Excellent): ~84% of employees
- Value 4 (Outstanding): ~16% of employees

This is not a coding error; it reflects a real-world leniency bias common in corporate performance management systems. However, it has critical consequences for psychometric validity.

#### 4.3.2 Impact on SalaryGrowth Formula

The `SalaryGrowth` formula is:

```
SalaryGrowth = PercentSalaryHike × PerformanceRating
```

With `PerformanceRating` limited to {3, 4}, this formula behaves as a weak binary multiplier:

- PR=3 employees: `SalaryGrowth = PercentSalaryHike × 3`
- PR=4 employees: `SalaryGrowth = PercentSalaryHike × 4`

The ratio between the two groups is always exactly 4:3 regardless of the magnitude of `PercentSalaryHike`. This means `PerformanceRating` contributes a ~33% scalar difference rather than the 4× range implied by a full 1–4 scale.

**Variance compression consequence:** The standard deviation of `SalaryGrowth` is driven almost entirely by `PercentSalaryHike` variance. `PerformanceRating` functions as a weak categorical modifier, not a continuous performance dimension.

#### 4.3.3 Cross-Dataset Comparability Risk

Saudi HR datasets may use the full 1–4 range of `PerformanceRating`. In this case:

- PR=1 employees: `SalaryGrowth = PercentSalaryHike × 1`
- PR=4 employees: `SalaryGrowth = PercentSalaryHike × 4`

The range of `SalaryGrowth` doubles relative to the IBM HR computation, making cross-company comparisons of this construct invalid without normalization. **Do not rescale PerformanceRating to force the {3,4} IBM distribution onto Saudi data** — this would discard legitimate performance variance.

Document the dataset's `PerformanceRating` range in all model outputs and apply appropriate confidence penalties (15%) when the distribution departs from IBM HR norms.

---

### 4.4 JobInvolvement vs. EmployeeEngagement Construct Confusion

#### 4.4.1 Theoretical Distinction

These are distinct psychological constructs and must not be merged or substituted:

**JobInvolvement (Lodahl & Kejner, 1965; IBM HR scale 1–4):**  
The degree to which an employee identifies psychologically with their job. A behavioral correlate of the Conscientiousness factor in the Five-Factor Model (FFM). Measured as a unidimensional 1–4 Likert item in IBM HR data. This is a stable, trait-like disposition.

**EmployeeEngagement (Kahn, 1990; composite 0–100):**  
A state construct defined as the simultaneous expression of cognitive, emotional, and behavioral investment in work. Kahn's framework explicitly requires BOTH job involvement AND job satisfaction as separate inputs — they are antecedents to engagement, not components of the same construct.

#### 4.4.2 Platform Formula Dependency

The `EngagementScore` construct uses:

```
EngagementScore = JobInvolvement × JobSatisfaction
```

This formula captures Kahn's simultaneity requirement: both involvement and satisfaction must be high for engagement to be high. This is theoretically correct and requires `JobInvolvement` as a 1–4 Likert item.

#### 4.4.3 Violation Scenario

If a Saudi HR dataset provides an `EmployeeEngagement` composite score (0–100) mapped to the `JobInvolvement` column (because the column name appears to match), the formula becomes:

```
EngagementScore = EngagementComposite(0–100) × JobSatisfaction(1–4)
```

The resulting range would be 0–400 instead of 1–16, and the multiplicative structure would amplify already-aggregated engagement data with an independent satisfaction measure, creating a double-counting artifact.

**Detection:** `max(JobInvolvement) > 4` — flag column for human review; do not allow automatic mapping from composite engagement instruments to `JobInvolvement`.

---

### 4.5 IncomePerLevel Ordinal Misuse

#### 4.5.1 Formula Structure

```
IncomePerLevel = MonthlyIncome / (JobLevel + 1)
```

The `+1` offset prevents division by zero if `JobLevel = 0` (non-standard encoding). The intent is to normalize income relative to career level — a level-adjusted compensation ratio.

#### 4.5.2 Ordinal vs. Interval Measurement Error

`JobLevel` is an ordinal variable (ranking), not an interval variable (equal spacing). The formula assumes that the income-per-level ratio is directly comparable across the scale — i.e., that a Level 2 employee earns twice the "level-adjusted" value of a Level 1 employee.

This assumption fails if the actual income distribution does not scale proportionally with job level. In Saudi organizations, the salary jump from Level 1 (entry) to Level 2 (associate) may differ substantially from the jump from Level 4 (senior) to Level 5 (executive), due to:

- Executive compensation packages including equity and benefits not captured in `MonthlyIncome`
- Non-linear pay scales typical of Gulf-region organizations
- Grade compression at lower levels in high-headcount companies

**Psychometric classification:** This is a level-of-measurement violation — arithmetic operations (division) applied to ordinal data produce results that are not psychometrically interpretable as ratio-scale quantities.

**Governance recommendation:** Treat `IncomePerLevel` as a relative ordering variable only. Do not interpret differences in `IncomePerLevel` as proportional differences in actual compensation fairness.

---

### 4.6 TenureRatio Ratio Scale Assumptions

#### 4.6.1 Formula Structure

```
TenureRatio = YearsAtCompany / (TotalWorkingYears + 1)
```

The `+1` denominator offset correctly handles the fresh graduate edge case:

- Fresh graduate (both = 0): `TenureRatio = 0 / 1 = 0` — valid, no division error
- 5 years at company, 5 total: `TenureRatio = 5 / 6 = 0.833` — high tenure concentration
- 5 years at company, 20 total: `TenureRatio = 5 / 21 = 0.238` — distributed career

#### 4.6.2 Unit Consistency Requirement

The ratio is valid only if both variables share the same unit. If `YearsAtCompany` is stored in years and `TotalWorkingYears` is stored in months (a realistic Saudi HR database inconsistency), the ratio becomes dimensionally incoherent:

```
TenureRatio = 5 (years) / (120 (months) + 1) = 0.041
```

Instead of the correct `5 / 21 = 0.238`. This is a 5.8× underestimation of tenure concentration.

**Detection test:**

```
Test TENURE-01 — Unit Consistency Check
  If median(TotalWorkingYears) > 30 AND median(YearsAtCompany) < 10:
    Suspect months encoding in TotalWorkingYears
    Flag: divide TotalWorkingYears by 12 before formula application
    Confidence penalty: 20%

Test TENURE-02 — Logical Bound Check
  Assertion: YearsAtCompany <= TotalWorkingYears (always true if units match)
  Violation: YearsAtCompany > TotalWorkingYears in any row
  Action: BLOCK computation; require data cleaning
```

---

### 4.7 Salary Percentage vs. Absolute Value Confusion

#### 4.7.1 Formula Requirement

```
SalaryGrowth = PercentSalaryHike × PerformanceRating
```

`PercentSalaryHike` must be a percentage point value (e.g., `13` representing 13%). The IBM HR dataset range is approximately 10–25.

#### 4.7.2 Absolute SAR Amount Misuse

If a Saudi HR system stores salary increase amounts in SAR rather than percentage points (e.g., `3,500` meaning a SAR 3,500 raise), the formula produces:

```
SalaryGrowth = 3500 × 3 = 10,500
```

This value is dimensionally meaningless as a "growth" construct and would make `SalaryGrowth` orders of magnitude larger than any other construct in the composite scoring system.

**Detection:** `max(PercentSalaryHike) > 100` — BLOCK the column; require human remapping. Do not apply automatic rescaling because the conversion factor (percentage of what salary base?) cannot be inferred from the column data alone.

---

### 4.8 Binary Conversion Safety for OverTime

| Input Form | Values | Conversion | Psychometric Safety | Confidence Penalty |
|---|---|---|---|---|
| String Yes/No | `"Yes"`, `"No"` | `Yes → 1, No → 0` | Safe — unambiguous nominal coding | None |
| Numeric binary | `1`, `0` | Pass through | Safe — already correct encoding | None |
| Numeric binary (float) | `1.0`, `0.0` | Cast to integer | Safe — representation only | None |
| Continuous hours | `0.0–80.0` (hours/week) | `> 0 → 1, = 0 → 0` | Lossy — loses magnitude information | 10% |
| Categorical level | `"Never"`, `"Sometimes"`, `"Always"` | Requires manual mapping | Ambiguous — "Sometimes" OT threshold undefined | BLOCKED |
| Missing / NaN | NaN | Cannot impute safely | Undefined binary state | BLOCKED |

**Governance note:** The 10% penalty for continuous-hours binarization reflects the loss of overtime intensity information. An employee working 41 hours/week and one working 80 hours/week are treated identically in the `BurnoutRisk` formula after binarization. This is a known formula limitation, not a data processing error.

---

### 4.9 Ceiling and Floor Effects in Derived Constructs

#### 4.9.1 SatisfactionIndex

```
SatisfactionIndex = (JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction) / (3 × 4)
```

- Theoretical range: `3/12 = 0.25` to `12/12 = 1.00`
- Minimum floor: 0.25 (not 0.0) — occurs when all three items = 1
- Maximum ceiling: 1.00 — occurs when all three items = 4
- IBM HR observed range: approximately 0.42–1.00 (left-skewed distribution)

**Implication:** `SatisfactionIndex` cannot reach its theoretical minimum (0.0) by formula construction. Governance reports referencing this index should note the effective floor of 0.25.

#### 4.9.2 BurnoutRisk

```
BurnoutRisk = OverTime × (5 − WorkLifeBalance)
```

- When `OverTime = 0`: `BurnoutRisk = 0` for all employees regardless of WLB
- When `OverTime = 1` and `WLB = 4`: `BurnoutRisk = 1` (minimum non-zero)
- When `OverTime = 1` and `WLB = 1`: `BurnoutRisk = 4` (maximum)

**Structural issue:** Approximately 71% of IBM HR employees have `OverTime = No`, making `BurnoutRisk = 0` for the majority. The construct provides no differentiation within the non-overtime population despite the fact that poor work-life balance may still contribute to attrition risk for salaried employees not formally classified as overtime.

#### 4.9.3 EngagementScore

```
EngagementScore = JobInvolvement × JobSatisfaction
```

- Theoretical range: 1 (both = 1) to 16 (both = 4)
- IBM HR observed clustering: 9–12 (both items near midpoint)
- Low-engagement tail (1–4): rare; captures employees with both low involvement AND low satisfaction
- High-engagement peak (16): uncommon; requires both items at ceiling

**Implication:** The multiplicative structure creates a non-linear distribution — employees near the midpoint of each item (2 or 3) cluster at values 4–9, while extreme scores require coordination across both items. This is theoretically desirable (Kahn simultaneity) but creates a right-compressed distribution in practice.

---

## 5. Current feature_factory.py Implementation Violations

The following violations are present in the current `feature_factory.py` and must be corrected before Phase 3 deployment. These are implementation errors, not formula design issues.

### Violation 1 — Universal _norm() Application Destroys Likert Semantics

**Current behavior:** The `_norm()` function applies min-max normalization to all input columns before compute formulae are evaluated.

**Psychometric consequence:** Likert values lose their absolute scale meaning. A dataset where `JobSatisfaction` ranges 2–4 maps to 0.0–1.0. A dataset where it ranges 1–4 also maps to 0.0–1.0. After normalization, both datasets produce identical `SatisfactionIndex` values despite having fundamentally different satisfaction distributions.

**Severity:** Critical. Min-max normalization is scale-relative; it cannot be applied to Likert data before formula computation without destroying between-dataset comparability.

**Required fix:** Apply scale validation and rescaling (Section 4.1) before formula computation. Remove `_norm()` from Likert inputs. Reserve normalization for final construct scores if cross-construct comparison is needed.

### Violation 2 — _norm(OverTime) Converts Binary to Continuous

**Current behavior:** `_norm()` applied to `OverTime` transforms `{0, 1}` to `{0.0, 1.0}` only in the single-dataset case. If a future dataset has all employees with `OverTime = 1`, normalization maps this to `0.0` — the opposite of the intended encoding.

**Psychometric consequence:** In edge-case datasets (all OT or no OT), `_norm(OverTime)` collapses to a constant (0.0), eliminating `BurnoutRisk` entirely for all employees.

**Required fix:** `OverTime` must be passed through as a binary integer {0, 1} without normalization. Normalize only after formula computation if required for output scaling.

### Violation 3 — BurnoutRisk Formula Includes Satisfaction as Third Term

**Current behavior:** The implemented `BurnoutRisk` formula includes a weighted satisfaction term not present in the paper formula:

```python
# Current (incorrect):
BurnoutRisk = alpha * OT * (5 - WLB) + beta * (1 - SatisfactionIndex)

# Paper formula (correct):
BurnoutRisk = OT * (5 - WLB)
```

**Psychometric consequence:** The satisfaction term introduces collinearity between `BurnoutRisk` and `SatisfactionIndex`, which are intended to be orthogonal constructs in the 7-construct system. Adding satisfaction to burnout conflates two theoretically distinct pathways to attrition.

**Required fix:** Remove the satisfaction term from `BurnoutRisk`. If a composite burnout-satisfaction index is desired for downstream modeling, construct it as a separate eighth variable, not by modifying a paper construct.

### Violation 4 — SatisfactionIndex Uses Only 2 Columns

**Current behavior:** The implemented `SatisfactionIndex` averages `JobSatisfaction` and a mapped engagement variable, dividing by 2×4 = 8.

**Paper formula (correct):**

```
SatisfactionIndex = (JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction) / 12
```

**Psychometric consequence:** Using 2 of 3 required items reduces internal consistency. If `EnvironmentSatisfaction` or `RelationshipSatisfaction` is the primary driver of attrition in a given Saudi organization, the truncated formula misses this signal entirely.

**Required fix:** Require all three satisfaction columns. If one is missing, apply a 15% confidence penalty and impute with the dataset mean of the available satisfaction items (not a fixed constant).

### Violation 5 — No Scale Validation Applied Before Computation

**Current behavior:** The pipeline proceeds to formula computation regardless of detected scale anomalies.

**Required fix:** Implement a pre-computation validation gate with the following checks executed in order:

1. `max(col) <= expected_max` for all Likert columns — fail fast if exceeded without rescaling
2. WLB direction check via correlation test (Test WLB-DIR-01)
3. PercentSalaryHike range check — BLOCK if `max > 100`
4. TenureRatio logical bound check (Test TENURE-02)
5. OverTime binary validity check before formula application

---

## 6. Test Cases for Scale Direction and Validity Verification

The following test battery should be executed against any new Saudi HR dataset before construct computation. Each test includes the expected outcome, the violation signal, and the required action.

### Test Battery: Pre-Computation Validation

| Test ID | Variable | Test Description | Expected | Violation Signal | Action |
|---|---|---|---|---|---|
| VAL-01 | All Likert | `max(col) in {4, 5}` | 4 | 5 | Rescale 1–5 → 1–4; 10% penalty |
| VAL-02 | All Likert | `min(col) >= 1` | True | False (0 present) | Check 0-indexed encoding; remap |
| VAL-03 | `WorkLifeBalance` | `corr(WLB, Attrition) < 0` | Negative | Positive (>+0.10) | Reverse-score WLB; 20% penalty |
| VAL-04 | `WorkLifeBalance` | `max(WLB) <= 5` | True | `max > 10` | Apply 0–100 rescaling; 15% penalty |
| VAL-05 | `OverTime` | `set(OverTime) subset of {0,1}` | True | Other values present | Apply binarization rules from Section 4.8 |
| VAL-06 | `JobInvolvement` | `max(col) <= 4` | True | `max > 4` | BLOCK; flag composite engagement confusion |
| VAL-07 | `PercentSalaryHike` | `max(col) <= 100` | True | `max > 100` | BLOCK; require human remapping |
| VAL-08 | `TenureRatio` | `YearsAtCompany <= TotalWorkingYears` (all rows) | True | Any violation | BLOCK; require data cleaning |
| VAL-09 | `PerformanceRating` | `max(col) <= 4` | True | `max > 4` | Flag for documentation; do not rescale |
| VAL-10 | `MonthlyIncome` | `min(col) >= 2000` (SAR plausibility) | True | `min < 2000` | Flag possible currency mismatch |
| VAL-11 | `JobLevel` | `min(col) >= 1 AND max(col) <= 5` | True | 0-indexed or 6-level | Remap to 1–5 encoding |
| VAL-12 | Tenure units | `median(TotalWorkingYears) < 30` | True | `median > 30` | Suspect months encoding; divide by 12 |

---

## 7. Recommendations for Phase 3 Deployment

### 7.1 Pre-Deployment Requirements (Mandatory)

1. **Resolve all 5 feature_factory.py violations** documented in Section 5 before any Saudi HR dataset is processed through the production pipeline. Violations 1 and 2 (universal normalization) are the highest priority as they affect all 7 constructs simultaneously.

2. **Implement the 12-test validation battery** (Section 6) as a blocking gate in the pipeline. Failed tests must halt computation and route the dataset to human review, not silently proceed with degraded data.

3. **Separate OverTime normalization pathway** — `OverTime` must be validated as binary before any formula uses it. Create a dedicated binary-validation function distinct from `_norm()`.

4. **Restore three-item SatisfactionIndex** — add `EnvironmentSatisfaction` and `RelationshipSatisfaction` to the formula. Confirm column mapping covers Arabic equivalents (رضا بيئة العمل، رضا العلاقات).

### 7.2 Phase 3 Governance Recommendations

5. **Document PerformanceRating distribution per dataset** — report whether the dataset uses the full 1–4 range or the IBM-compressed {3,4} range. Include this metadata in all model output reports so downstream analysts interpret `SalaryGrowth` correctly.

6. **Establish WLB direction verification as mandatory** for all Saudi datasets — do not rely on keyword matching to infer scale direction. Require either (a) data dictionary confirmation or (b) correlation test VAL-03 with `p < 0.05` before proceeding.

7. **Create construct confidence score output** — each derived construct should carry a confidence multiplier (product of all applicable penalties) visible in the output. Example: a dataset with WLB rescaled from 1–5 (10% penalty) and BurnoutRisk flagged for direction (20% penalty) produces `BurnoutRisk_confidence = 0.90 × 0.80 = 0.72`.

8. **Do not allow composite EmployeeEngagement scores to substitute for JobInvolvement** — enforce this in the Arabic synonym mapping stage. Column names containing "مشاركة الموظفين" (employee engagement) must not be auto-mapped to `JobInvolvement`; they require a separate validation step confirming the column contains a 1–4 Likert item, not a composite index.

9. **Treat IncomePerLevel as ordinal output only** — do not use this construct in regression models as a continuous predictor without first verifying monotonic salary scaling across job levels in the specific organization's data.

10. **Archive the IBM HR baseline distribution statistics** (means, standard deviations, percentile distributions) for each of the 12 variables as the reference standard. Any Saudi dataset whose variable distributions exceed 1.5 standard deviations from these baselines on more than 3 variables should trigger a full psychometric review before model training proceeds.

---

## 8. References and Theoretical Basis

- Kahn, W. A. (1990). Psychological conditions of personal engagement and disengagement at work. *Academy of Management Journal, 33*(4), 692–724. — Basis for `EngagementScore` simultaneity requirement.
- Lodahl, T. M., & Kejner, M. (1965). The definition and measurement of job involvement. *Journal of Applied Psychology, 49*(1), 24–33. — Basis for `JobInvolvement` as distinct from engagement composites.
- IBM HR Analytics Employee Attrition & Performance Dataset (Kaggle). — Source specification for all 12 baseline scale definitions.
- Stevens, S. S. (1946). On the theory of scales of measurement. *Science, 103*(2684), 677–680. — Theoretical basis for ordinal vs. interval distinction in `JobLevel` and `PerformanceRating` analysis.
- Nunnally, J. C., & Bernstein, I. H. (1994). *Psychometric Theory* (3rd ed.). McGraw-Hill. — Internal consistency and scale reliability standards referenced in Sections 4.1 and 4.4.

---

*End of Psychometric Scale Audit — Version 1.0*  
*Next scheduled review: Prior to Phase 3 deployment or upon addition of any new Saudi HR dataset source.*
