# Leakage Forensics Report: HR Attrition Prediction Platform
## Forensic Data Leakage Audit — Saudi Company HR Datasets
**Classification:** Internal Governance Document — ML Forensics Division  
**Target Variable:** `Attrition` (binary: Yes / No) — Voluntary Employee Turnover  
**Audit Scope:** Beyond the 14 implemented LeakageDetector checks  
**Audience:** ML Governance Architect, Leakage Forensics Specialist  
**Date:** 2026-05-20

---

## Executive Summary

This report performs a deep forensic audit of data leakage patterns in an HR attrition prediction platform. Standard leakage detection (e.g., correlation thresholds, known column blacklists) fails to catch latent, multi-hop, and structurally embedded leakage. This audit identifies ten categories of leakage risk, classifies every column type by severity, and provides a forensic decision framework for evaluating new Saudi HR dataset columns. The central finding is that attrition prediction datasets are uniquely prone to **temporal leakage**, **administrative artifact leakage**, and **semantic proxy leakage** — all of which produce models that appear to generalize but are actually exploiting future-state information.

---

## 1. TARGET ADJACENCY LEAKAGE

Target adjacency leakage occurs when a feature either directly encodes the target or is derived from a process that required knowledge of the target value. This is the most severe class of leakage and the most common in HR datasets, where administrative systems backfill records after an employee exits.

### 1.1 CRITICAL: Derived Prediction Columns

These columns are outputs of a prior attrition scoring model or manual HR risk assessment. Their presence means the dataset contains a prediction of the target as a feature of the target — a perfect circular dependency.

| Column Name | Leakage Mechanism |
|---|---|
| `AttritionRisk` | Named risk score derived from prior model or HR scoring system |
| `RetentionRisk` | Inverse of attrition probability — encodes target directly |
| `ChurnScore` | "Churn" is the exact semantic equivalent of attrition |
| `ResignationScore` | A scored prediction of the resignation event itself |

**Why they survive naive correlation checks:** If these scores were computed with noise or on a slightly different definition of the target (e.g., voluntary + involuntary vs. voluntary only), Pearson correlation may be 0.75 rather than 1.0, falling below a naive 0.95 threshold. The model still trains on a noisy proxy of the exact outcome.

**Forensic rule:** Any column whose name contains the strings `risk`, `churn`, `resign`, `retain`, `turnover`, `attrition`, or `exit` as a prefix or suffix must be treated as CRITICAL until its computational lineage is traced to non-exit features measured before the decision period.

### 1.2 CRITICAL: Post-Exit Administrative Data

These columns are populated in HR systems only after an employee has resigned, been terminated, or completed an offboarding process. They are future-state records masquerading as employee attributes.

| Column Name | Leakage Mechanism |
|---|---|
| `ExitReason` | Populated during or after offboarding — requires knowing the exit occurred |
| `FinalStatus` | HR status code set at separation — terminal state indicator |
| `LastDayWorked` | An exit date — logically impossible to know before the exit |
| `OffboardingDate` | Process initiated only after resignation accepted |
| `VoluntaryExit` | A sub-classification of the attrition event itself |
| `InvoluntaryTermination` | Same as above, different branch |
| `SeparationReason` | Categorical encoding of why the employee left |

**Note for Saudi HR systems:** Saudi Ministry of Human Resources (MHRSD) mandates specific separation documentation in Qiwa platform records. Columns sourced from Qiwa exit notifications are definitionally post-exit and must be excluded entirely.

### 1.3 HIGH: Pre-Decision Proxy Columns

These columns may be collected before a formal resignation but reflect a psychological state that is essentially simultaneous with the exit decision. They are not predictors of the exit event — they are symptoms of a decision already made.

| Column Name | Leakage Mechanism |
|---|---|
| `IntentToLeave` | A survey question that directly asks about departure intent |
| `ResignationIntent` | A scored version of departure intent |
| `ThinkingOfLeaving` | Binary or Likert survey response — identical to asking the target |
| `ExternalJobOpportunities` | Reported job search activity — a behavioral proxy for imminent exit |
| `JobSearch` | Same as above |

**Temporal subtlety:** Even if these were measured 30 days before the official resignation date, the measurement is contemporaneous with the exit decision in any meaningful causal sense. A model trained on these features is not predicting attrition — it is reading a report of the employee's own prediction.

### 1.4 CAUTION: Forward-Looking Intent Statements

| Column Name | Leakage Mechanism |
|---|---|
| `CareerGoals` | If free-text, NLP features may encode "looking for new challenges" language |
| `FiveYearPlan` | Subjective; if coded as "outside this company," encodes exit intent |

**Forensic guidance:** These columns require qualitative inspection of how they were encoded. A `FiveYearPlan` coded as a continuous score by an HR analyst with knowledge of actual outcomes is CRITICAL leakage. If coded from a survey administered uniformly across all employees at a fixed interval, it degrades to CAUTION.

---

## 2. RESIGNATION TIMING LEAKAGE

Resignation timing leakage arises in retrospective datasets where features are recorded or averaged over periods that overlap with the exit decision window. These features are not stable employee characteristics — they are symptomatic signals of withdrawal that are only observable as patterns in hindsight.

### 2.1 HIGH: Absence Rate Trending

`AbsenceRate` measured as a single snapshot in the final 6 months of employment captures behavioral withdrawal, not a stable predictor. Research in organizational psychology consistently shows absence rates increase 3–6 months before voluntary exit as employees disengage, use accrued leave, or pursue job search activities during work hours.

**Leakage mechanism:** In a cross-sectional dataset where `AbsenceRate` is the employee's value at the time of dataset construction, leavers will systematically show higher absence than stayers — not because absence causes leaving, but because the dataset snapshot captures the withdrawal phase.

**What a legitimate feature looks like:** `AbsenceRate_Year1`, `AbsenceRate_Year2` measured in fixed calendar windows, not trailing windows anchored to exit date.

### 2.2 HIGH: Performance Rating Decline

`PerformanceRating` in the final 1–2 review cycles before exit reflects two mechanisms, both leaky:

1. **Manager anticipation effect:** Managers aware that an employee has signaled departure (explicitly or implicitly) rate more critically or more leniently depending on retention incentive.
2. **Retrospective bias:** In some HR systems, final performance ratings are updated or re-entered during offboarding, incorporating knowledge of the exit.

**Detection method:** Compare the distribution of `PerformanceRating` for employees who left in the same review period as leavers vs. stayers. A statistically significant difference in the final rating that does not appear in ratings 2+ years prior suggests timing leakage.

### 2.3 HIGH: Training Hours Near Zero in Final Period

`TrainingHours` trending to zero in the final 6 months is an HR behavior, not an employee behavior. When HR systems are informed (formally or through manager communication) that an employee is leaving, training nominations and L&D investments are deprioritized. This is an **HR intervention signal**, not an independent predictor.

**Leakage type:** HR_Response_Leakage — the feature encodes HR's prior knowledge of exit risk, which correlates with actual exit.

### 2.4 CAUTION: Salary Hike Patterns

`SalaryHike = 0%` or below-cohort-average in the final review cycle is a retention failure signal. The mechanism: if HR and management attempted a retention conversation and the employee declined or the budget was insufficient, the salary review reflects that the employee was in the departure pathway. However, this is only leaky if the dataset captures the final salary review rather than a review from a neutral earlier period.

### 2.5 CAUTION: Tenure Stagnation Without Promotion

`YearsAtCurrentLevel` increasing without a corresponding promotion event is a legitimate predictor IF measured at a fixed point in time for all employees. It becomes leaky if measured as of last employment date (i.e., end of tenure for leavers), because leavers by definition have a longer `YearsAtCurrentLevel` at the point of departure than stayers measured at the same calendar date.

---

## 3. POST-RESIGNATION ARTIFACTS

These are administrative records entered into the HR system after the resignation event. They are routinely included in HR data exports without temporal annotation.

### 3.1 CRITICAL: Exit Interview Data as Features

Exit interview responses are collected after resignation acceptance. Any feature derived from exit interview data (reason for leaving, satisfaction with company, team dynamics assessment) is definitionally post-exit. No exit interview data field may appear in the feature set.

**Saudi context:** Companies using Taleo, SAP SuccessFactors, or Oracle HCM in Saudi Arabia commonly store exit interview data in the same employee record as pre-employment and employment data. A raw export of `employees.csv` from these systems will include both.

### 3.2 CRITICAL: Severance Classification Features

`SeveranceType` (voluntary vs. involuntary), `SeveranceAmount`, and `SeverancePaidDate` are all records created as part of the separation process. They encode the exit event by definition.

### 3.3 HIGH: Manager Final-Period Ratings

Manager assessments of employee quality, collaboration, and potential made in the employee's final quarter before exit are contaminated by the manager's knowledge of the impending departure. This creates two leakage vectors:

1. **Sympathy inflation:** Manager rates higher to provide a favorable reference.
2. **Resentment deflation:** Manager rates lower due to departure announcement friction.

Both produce a systematic difference between final-period manager ratings of leavers vs. stayers that has nothing to do with stable employee quality.

### 3.4 HIGH: Backward-Computed Date Features

If `LastWorkDay` is present in the dataset, any feature computed as `(LastWorkDay - SomeEvent)` is a backward-looking date arithmetic that embeds the exit date into a numeric feature. Examples include:

- `DaysSinceLastPromotion` (computed as of `LastWorkDay`)
- `TenureAtLastReview` (computed using `LastWorkDay` as reference point)
- `MonthsSinceHire` (if computed as total tenure including exit, not as of snapshot date)

**Detection query:** Any `DaysSince*` or `MonthsSince*` or `Years*` feature in the dataset must be validated that the reference date is a fixed snapshot date common to all employees, not an employee-specific terminal date.

---

## 4. HR INTERVENTION LEAKAGE

HR intervention leakage occurs when HR takes a specific action because they already believe an employee is at attrition risk. The action (feature) is therefore caused by the HR system's prior estimate of the target, creating a causal inversion.

### 4.1 HIGH: Counter-Offer and Retention Bonus Features

| Column | Mechanism |
|---|---|
| `CounterOfferMade` | HR extends counter-offer only when an employee has signaled intent to leave |
| `RetentionBonus` | Granted specifically to employees identified as flight risks |
| `RetentionBonusAmount` | Numeric encoding of retention urgency from HR perspective |

**Why this is leakage, not prediction:** These features do not predict attrition — they reflect that attrition was already predicted by a human decision-maker. The model trains on the HR system's prior knowledge, not independent employee features.

### 4.2 HIGH: Promotion Timing Correlated with Flight Risk

`PromotionInLastYear` is a legitimate predictor in isolation. However, if HR explicitly promotes employees to retain them when they signal departure intent, then promotion becomes a leaky feature — it is the HR response to perceived attrition risk, not an independent organizational decision.

**Detection:** If `PromotionInLastYear = True` has a higher attrition rate than `PromotionInLastYear = False` in the training data, this is a signal that promotions are being given to at-risk employees (HR intervention), and the promotion did not succeed, confirming the leakage pathway.

### 4.3 CAUTION: HR Meeting Frequency in Final Period

`HRMeetingCount_Last90Days` or `ManagerialConversation_Count` in the terminal employment period reflects HR's awareness of employee status. A spike in HR meetings before exit is caused by the exit pathway, not predictive of it.

---

## 5. DERIVED LEAKAGE CHAINS (Multi-Hop)

Multi-hop leakage occurs when no single feature is directly leaky, but a chain of causal relationships between features transmits leakage from an intermediate node. Standard correlation-based detection misses these because it evaluates features individually against the target.

### Chain 1: Absence → HR_Risk_Flag → Attrition

```
AbsenceRate (rising) → HR_Risk_Flag = 1 → Attrition = Yes
```

`AbsenceRate` alone may not be flagged as critically leaky. But if `HR_Risk_Flag` was computed by an HR analyst using absence as the primary input, and if `HR_Risk_Flag` was then recorded in the system, the model trained on `HR_Risk_Flag` is training on a human-computed intermediate attrition prediction.

**Detection:** If `HR_Risk_Flag` was computed at any point using outcome-aware information (post-hoc labeling, analyst knowledge of exits), it is CRITICAL leakage even if the source feature (`AbsenceRate`) is legitimate.

### Chain 2: SalaryHike → PromotionDecision → IntentToLeave → Attrition

```
SalaryHike = 0% → PromotionDecision = Rejected → IntentToLeave = High → Attrition = Yes
```

Each link in this chain is plausible and individually defensible. The leakage is structural: if `IntentToLeave` is measured after the compensation decision and encodes the employee's reaction to it, and if the training data captures these temporally close together, the chain compresses into a single leakage signal.

### Chain 3: PerformanceRating_Trend → ManagerialAction → Separation

```
PerformanceRating declining → Manager initiates PIP → Separation
```

If `ManagerialAction` (e.g., a Performance Improvement Plan flag) is included as a feature, it encodes that the manager had already identified the employee as at-risk, making it intermediate leakage.

### Chain 4: OvertimeHours_Spike → BurnoutDiagnosis → LeaveRequest → Attrition

```
OvertimeHours spike → BurnoutDiagnosis (EAP referral) → MedicalLeaveRequest → Attrition
```

`BurnoutDiagnosis` or `EAP_Referral` columns, if present, carry clinical or HR-system flags that are generated concurrently with the withdrawal process. They are not stable, pre-decision predictors.

---

## 6. PROXY LEAKAGE (Semantic)

Semantic proxy leakage occurs when column names reveal that a feature was deliberately constructed to predict attrition (and therefore encodes attrition-correlated information in its construction), or when the feature is a renamed version of the target.

### 6.1 CRITICAL: Direct Proxy Names

| Pattern | Example Columns | Risk Level |
|---|---|---|
| `*_risk` | `flight_risk`, `turnover_risk`, `attrition_risk` | CRITICAL |
| `*_probability` | `retention_probability`, `churn_probability` | CRITICAL |
| `*_score` (exit-adjacent) | `stability_score`, `resignation_score` | CRITICAL |

### 6.2 HIGH: Soft Proxy Names

| Pattern | Example Columns | Risk Level |
|---|---|---|
| `loyalty_*` | `loyalty_index`, `loyalty_score` | HIGH |
| `commitment_*` | `commitment_score`, `commitment_level` | HIGH |
| `stay_*` | `stay_probability`, `stay_likelihood` | HIGH |
| `predicted_*` | `predicted_tenure`, `predicted_exit_date` | CRITICAL |

### 6.3 CAUTION: Wellness-Adjacent Proxies

`employee_health_risk` may be a legitimate wellness metric or may be correlated with exit in the HR system if health events are disproportionately documented for at-risk employees. Requires provenance trace.

**Forensic rule for semantic detection:** Apply a term list scan against all column names using the vocabulary: {attrition, churn, resign, turnover, exit, flight, retain, retention, leave, departure, quit, separate, termination, loyalty, commit, stable, stability, stay, predict, score, risk, probability, index, likelihood}. Any column name matching two or more terms from this list is HIGH risk minimum.

---

## 7. RECONSTRUCTION LEAKAGE

Reconstruction leakage occurs when a combination of features, none of which are individually leaky, can be combined to uniquely identify which employees left — effectively reconstructing the target from structural artifacts.

### 7.1 HIGH: Identity Reconstruction via Rare Combinations

In a department with 8 employees where 2 left in a given year:

```
Department = "Legal" + JobLevel = "Senior" + YearsAtCompany = 7 + ExitYear = 2024
```

This combination may uniquely identify those 2 employees in the dataset. A model trained on these features in a small dataset learns to associate this combination with `Attrition = Yes` — not because the features are predictive in general, but because they are identity-reconstructing in this specific dataset.

**Saudi context:** Saudi companies with nationalization (Saudization) requirements often have small Saudi employee cohorts in specific roles. Combinations of `Nationality = Saudi` + `Department` + `JobLevel` may create uniquely identifying feature sets in small teams.

### 7.2 HIGH: Salary + Department Combinations

Salary bands in specific departments may be unique to one or two employees. If a leaver has a unique salary band in a small department, the model memorizes the combination as an attrition indicator.

### 7.3 CAUTION: Sequential Employee ID Patterns

`EmployeeID` ranges or patterns (e.g., IDs 10000–10500 were hired in a batch that had 80% attrition) encode hiring cohort membership. If the model is allowed to use `EmployeeID` as a feature (or any feature derived from ID ranges), it may learn batch-level attrition rates rather than individual predictors.

---

## 8. DEPARTMENT DOMINANCE LEAKAGE

Department-level attrition concentration creates a specific class of leakage where the model learns to predict department membership rather than individual risk.

### 8.1 HIGH: Extreme Department Attrition Rates

If the `Sales` department has 78% historical attrition and is one-hot encoded as `Dept_Sales`, then `Dept_Sales = 1` becomes an approximate proxy for `Attrition = 1`. The model achieves high accuracy by learning department membership, not individual behavioral patterns.

**Threshold for concern:** Any department with attrition rate > 2× the overall dataset mean warrants investigation. At > 70% attrition rate in a department, the one-hot column is functionally equivalent to the target for that department's employees.

### 8.2 CAUTION: Small Team Identifiability

| Team Size | Leavers | Attrition Rate | Risk |
|---|---|---|---|
| 3 | 1 | 33.3% | HIGH — model memorizes team |
| 5 | 1 | 20.0% | CAUTION |
| 10 | 1 | 10.0% | LOW |
| 20+ | varies | varies | LOW unless extreme |

For a 3-person team with 1 leaver, `TeamID` or any feature unique to that team (manager ID, sub-department code) is a reconstruction vector. The model learns that belonging to Team_X is equivalent to attrition risk.

**Forensic rule:** Any grouping variable (team, manager, sub-department) where the smallest group has fewer than 10 members must be reviewed for rate extremity and identifiability.

---

## 9. SYNTHETIC LEAKAGE AMPLIFICATION

Synthetic oversampling techniques (SMOTE, ADASYN, BorderlineSMOTE) applied incorrectly interact with existing leakage signals to amplify them.

### 9.1 CAUTION: Oversampling Before Train/Test Split

**Incorrect pipeline (leaky):**
```
Full Dataset → SMOTE Oversampling → Train/Test Split → Model Training
```

**Correct pipeline (clean):**
```
Full Dataset → Train/Test Split → SMOTE on Train Only → Model Training
```

When SMOTE is applied before splitting, synthetic minority samples (generated from actual leaver feature vectors) appear in both train and test sets. If the original leavers have leaky features (e.g., slightly elevated `AbsenceRate`), the synthetic copies inherit those features. The model then tests on synthetic samples that share the same leakage signal as training samples — inflating test AUC by 5–15 percentage points in typical HR datasets.

### 9.2 CAUTION: Feature Engineering on Full Dataset

**Incorrect pipeline (leaky):**
```
Full Dataset → Compute RetentionRisk (using global _norm()) → Split → Train/Model
```

**Correct pipeline (clean):**
```
Full Dataset → Split → Compute RetentionRisk on train only → Apply transform to test
```

The `_norm()` function applied globally uses the mean and standard deviation of the full dataset, including test set records, to normalize features. This leaks test-set statistics into training features — a form of distribution leakage. For small datasets (< 5,000 records), this can shift feature values by 0.03–0.08 standard deviations, which is sufficient to inflate recall on the minority class.

---

## 10. FEATURE FACTORY SPECIFIC LEAKAGE RISKS

### 10.1 RetentionRisk Composite

The `RetentionRisk` feature in `feature_factory.py` is a weighted composite:

```
RetentionRisk = w1*burnout + w2*(1-satisfaction) + w3*(1-promotion) + w4*overtime + w5*(1-manager_quality)
```

**Risk assessment:** CAUTION to HIGH depending on input provenance.

- If `burnout` is a retrospective HR assessment (filed after exit), it is HIGH leakage.
- If `satisfaction` is from a survey administered after resignation announcement, it is CRITICAL.
- If `manager_quality` reflects the manager's own knowledge of impending departure, it is HIGH.
- The composite name (`RetentionRisk`) itself is a semantic proxy for the target — even if inputs are clean, the named output must not be used as a feature in a model predicting the same target.

### 10.2 BurnoutRiskComposite

```
BurnoutRiskComposite = _norm(overtime) * w1 + _norm(workload) * w2 + (1 - _norm(satisfaction)) * w3
```

**Risk assessment:** HIGH if `workload` is sourced from retrospective HR assessment.

`_norm()` applied globally (before split) introduces distribution leakage. If `workload` is manager-assessed and reflects the manager's knowledge of employee exit trajectory, the burnout composite inherits that signal.

### 10.3 PresenteeismSignal

```
PresenteeismSignal = _norm(absence) * 0.50 + _norm(overtime) * 0.50
```

**Risk assessment:** HIGH.

Presenteeism metrics combining absence and overtime are meaningful as stable workforce health indicators when measured at fixed intervals. In retrospective exit datasets, absence near exit is behavioral withdrawal (leaky), and overtime near exit may reflect project wrap-up or covering departing colleagues (also temporally contaminated). This feature requires measurement-date validation before use.

### 10.4 EmployeeStabilityRisk

```
EmployeeStabilityRisk = (1 - tenure_norm) * 0.60 + (1 - age_norm) * 0.40
```

**Risk assessment:** CAUTION.

`tenure` and `age` are legitimate demographic features. The risk here is semantic: naming a composite `StabilityRisk` creates a column that is semantically adjacent to the target. If this feature is audited post-deployment and found to have high feature importance, the explanation "stability risk predicted attrition" is circular. Additionally, `tenure_norm` applied globally leaks test statistics as noted in section 9.2.

### 10.5 AbsenteeismPressureIndex

**Risk assessment:** HIGH if absence is measured in the final 6 months before exit.

A single-source absence feature is high-risk when absence measurement windows are anchored to exit date rather than a fixed calendar window. This is the canonical behavioral withdrawal signal in attrition research.

---

## Column Risk Classification Table

| Column Type | Risk Level | Justification |
|---|---|---|
| `AttritionRisk`, `ChurnScore`, `ResignationScore` | CRITICAL | Derived prediction of target |
| `ExitReason`, `SeparationReason`, `FinalStatus` | CRITICAL | Post-exit administrative record |
| `LastDayWorked`, `OffboardingDate` | CRITICAL | Exit date fields — impossible pre-exit |
| `VoluntaryExit`, `InvoluntaryTermination` | CRITICAL | Sub-classification of target event |
| Exit interview fields (any) | CRITICAL | Collected post-resignation |
| `SeveranceType`, `SeveranceAmount` | CRITICAL | Separation process records |
| `IntentToLeave`, `ResignationIntent` | HIGH | Direct intent proxy — contemporaneous with decision |
| `ExternalJobOpportunities`, `JobSearch` | HIGH | Behavioral signal of imminent exit |
| `CounterOfferMade`, `RetentionBonus` | HIGH | HR response to known flight risk |
| `AbsenceRate` (terminal period) | HIGH | Behavioral withdrawal signal |
| `PerformanceRating` (final cycle) | HIGH | Manager anticipation or retrospective bias |
| `TrainingHours` (final 6 months) | HIGH | HR disinvestment in known leaver |
| `HR_Risk_Flag` (any) | HIGH | Intermediate computed leakage |
| `BurnoutDiagnosis`, `EAP_Referral` | HIGH | Clinical flags concurrent with exit pathway |
| `PresenteeismSignal` (feature_factory) | HIGH | Absence + overtime near exit |
| `AbsenteeismPressureIndex` (feature_factory) | HIGH | Terminal absence signal |
| `flight_risk`, `turnover_risk` column names | CRITICAL | Semantic direct proxy |
| `stability_score`, `retention_probability` | CRITICAL | Semantic direct proxy |
| `loyalty_index`, `commitment_score` | HIGH | Exit-correlated composite |
| `predicted_tenure`, `stay_probability` | CRITICAL | Model output used as feature |
| `RetentionRisk` (feature_factory) | HIGH | Named composite — semantic adjacency + input risk |
| `BurnoutRiskComposite` (feature_factory) | HIGH | Workload input may be retrospective |
| `EmployeeStabilityRisk` (feature_factory) | CAUTION | Semantic adjacency; inputs are demographic |
| `PromotionInLastYear` (if HR intervention) | HIGH | HR response to known risk, not independent event |
| `HRMeetingCount_Last90Days` | CAUTION | May reflect HR awareness of exit trajectory |
| `SalaryHike` (final review only) | CAUTION | Retention failure signal if final-period only |
| `YearsAtCurrentLevel` (as of exit date) | CAUTION | Stagnation signal; leaky if exit-anchored |
| `Department` (one-hot, if >70% attrition rate) | HIGH | Department = target in extreme cases |
| `TeamID` or `ManagerID` (small teams) | CAUTION | Reconstruction vector in small cohorts |
| `EmployeeID`, `EmployeeID` ranges | CAUTION | Batch-level attrition encoding |
| `CareerGoals`, `FiveYearPlan` (coded by analyst) | CAUTION | May encode analyst's knowledge of outcome |
| `Age`, `Gender`, `Education` | SAFE | Stable demographic, not exit-derived |
| `MaritalStatus`, `NumChildren` | SAFE | Pre-employment demographic |
| `Department`, `JobRole` (balanced attrition) | SAFE | Organizational attribute (with rate monitoring) |
| `DistanceFromHome`, `CommuteTime` | SAFE | Geographic, stable |
| `YearsAtCompany` (snapshot date, not exit date) | SAFE | Tenure at fixed reference date |
| `JobLevel`, `EducationField` | SAFE | Structural attribute |
| `TrainingHours` (Year 1–3, not final period) | SAFE | L&D investment in stable period |
| `AbsenceRate` (Year 1–3, not final period) | SAFE | Stable period absence pattern |

---

## Forensic Decision Tree for New Saudi HR Columns

Use this tree to classify any new column encountered in a Saudi HR dataset extract.

```
NEW COLUMN ENCOUNTERED
│
├─ Does the column name contain: exit, resign, separate, final, offboard,
│  severance, last_day, churn, turnover, retention, flight, attrition?
│  ├─ YES → FLAG: CRITICAL — trace computational lineage before any use
│  └─ NO → continue
│
├─ Was this column populated AFTER the employee's resignation date?
│  ├─ YES → FLAG: CRITICAL — post-exit administrative artifact
│  └─ NO / UNKNOWN → continue
│
├─ Does this column reflect an HR or manager action taken in response to
│  perceived attrition risk (counter-offer, retention bonus, PIP, HR meeting)?
│  ├─ YES → FLAG: HIGH — HR intervention leakage
│  └─ NO → continue
│
├─ Does this column measure employee behavior in the last 6 months of employment?
│  (absence, overtime, performance rating, training hours)
│  ├─ YES → FLAG: HIGH — behavioral withdrawal or timing leakage
│  │         Require: measurement window validation against snapshot date
│  └─ NO → continue
│
├─ Is this column a composite score or index computed from other features?
│  ├─ YES → Recursively apply this tree to all input features
│  │         If any input is HIGH or CRITICAL → inherit that classification
│  │         If composite name is semantically adjacent to target → CAUTION minimum
│  └─ NO → continue
│
├─ Can this column, combined with 2–3 other columns, uniquely identify
│  an individual employee in a group of < 10 people?
│  ├─ YES → FLAG: CAUTION for reconstruction leakage; review group sizes
│  └─ NO → continue
│
├─ Does this column encode an intent, desire, or plan expressed by the employee?
│  ├─ YES → FLAG: HIGH (if near exit decision) or CAUTION (if from annual survey)
│  └─ NO → continue
│
└─ Column passes all checks → SAFE
   Document: column name, source system, measurement date, measurement window
```

---

## Temporal Validation Recommendations

### Why Random Train/Test Split Fails for Attrition Data

Random splitting violates the temporal ordering of HR events. An employee who resigned in January 2023 may appear in the test set, while data about their behavioral patterns from November 2022 appears in the training set (for another employee whose exit is used as a training example). This cross-contamination is impossible to detect without explicit temporal validation.

More critically: in a random split, a model can learn to identify leavers by the pattern of their terminal features (absence spike, performance decline) because both the feature pattern and the label appear in training data for other employees at similar career stages. The model is not learning to predict who will leave — it is learning to identify the signature of employees who have already decided to leave.

### Recommended Temporal Validation Protocol

**Step 1: Define the prediction horizon.**  
Choose a fixed window (e.g., 6 months) as the prediction horizon. The model should predict "will this employee leave in the next 6 months?" using only data available at the snapshot date.

**Step 2: Establish a snapshot date.**  
For each employee, define a single reference date. All features must be measured as of this date. No feature may incorporate information from after this date.

**Step 3: Time-based split.**

```
|------ Training period ------| Gap | Test period --|
   Jan 2020 — Jun 2023           3mo   Oct 2023 — Mar 2024
```

The gap window (90 days recommended) prevents the training and test periods from sharing employees who are simultaneously in their pre-exit behavioral phase and in the training label set.

**Step 4: Employee-level exclusion zone.**  
Any employee whose snapshot date in the training set falls within 6 months of their actual exit date must be flagged and reviewed. Their terminal behavioral features may contaminate the training signal.

**Step 5: Walk-forward validation.**  
For model evaluation, use rolling time windows rather than a single split:

```
Fold 1: Train Jan 2020–Dec 2021, Test Jan 2022–Jun 2022
Fold 2: Train Jan 2020–Jun 2022, Test Jul 2022–Dec 2022
Fold 3: Train Jan 2020–Dec 2022, Test Jan 2023–Jun 2023
```

Performance metrics should be reported as the mean and standard deviation across folds, not a single held-out result.

---

## Holdout Strategy for Preventing Timing Leakage

### The Temporal Holdout Problem

A standard holdout set (e.g., 20% of records) selected randomly will contain employees whose exit events occurred earlier than some employees in the training set. The model sees future-exit employees during training, defeating the purpose of held-out evaluation.

### Recommended Holdout Protocol

**1. Hard temporal cutoff holdout.**  
Reserve the most recent 6–12 months of attrition events as the holdout set. These events occurred after the training window ends and cannot have been used — even indirectly — during training.

**2. Department-stratified temporal holdout.**  
Within each department, maintain temporal ordering. This prevents a model from achieving high holdout performance by exploiting department-level attrition cycles that happen to fall in the holdout period.

**3. Feature freeze at snapshot date.**  
For all holdout employees, verify that every feature value reflects the state of that feature at the snapshot date (the prediction point), not at any later date. Apply a systematic audit:

```
FOR each feature IN holdout_records:
    IF feature.measurement_date > employee.snapshot_date:
        FLAG as post-snapshot contamination
        EXCLUDE or impute from pre-snapshot data only
```

**4. Prohibition on feedback loop features in holdout.**  
Features that could have been updated in response to model predictions (e.g., if the model is already deployed and HR uses scores to trigger interventions) must be excluded from both training and holdout evaluation sets.

**5. Saudi-specific consideration: Ramadan and fiscal year boundaries.**  
Saudi HR datasets often show attrition spikes at Hijri year boundaries and post-Ramadan. A holdout set that straddles a Ramadan period without controlling for it will show artificially different attrition rates. Holdout periods should be seasonally matched to the training period, or seasonal effects should be explicitly modeled and removed before evaluation.

---

## Appendix: Leakage Severity Definitions

| Level | Definition | Action Required |
|---|---|---|
| CRITICAL | Feature directly encodes, derives from, or is computationally equivalent to the target variable | Exclude immediately; no conditional use |
| HIGH | Feature systematically encodes information that is only available after the target event occurs, or reflects a human decision based on prior knowledge of the target | Exclude unless temporal provenance is fully validated; document exception |
| CAUTION | Feature may carry partial leakage depending on measurement window, encoding method, or dataset construction process | Validate measurement date and encoding method; include with documented justification |
| SAFE | Feature is a stable pre-decision attribute with no plausible causal pathway from the target back to the feature | Include with standard preprocessing; document source |

---

## Appendix: Quick Reference — Leakage Detection Beyond the 14 Checks

The existing LeakageDetector implements 14 checks primarily covering direct correlation, known column blacklisting, and basic temporal ordering. The following additional checks are recommended:

1. **Measurement window audit:** For every behavioral feature (absence, performance, overtime), validate that the measurement window does not overlap with the exit decision period for any employee.
2. **HR intervention flag audit:** Identify any feature that could only be triggered by an HR decision taken in response to perceived exit risk.
3. **Composite input lineage trace:** For every engineered feature, recursively audit all inputs using the forensic decision tree above.
4. **Small group identifiability check:** For any grouping variable, compute the minimum group size. Flag all groups with < 10 members.
5. **Department attrition rate check:** Flag any department with attrition rate > 2× dataset mean.
6. **Global normalization audit:** Verify that all `_norm()` or `StandardScaler` operations are applied only to training data, with test data transformed using training-derived parameters.
7. **Oversampling pipeline audit:** Verify that SMOTE or any synthetic oversampling is applied exclusively within the training fold, after cross-validation split.
8. **Semantic name scan:** Apply the vocabulary scan from Section 6 to all column names in the raw dataset before any preprocessing.
9. **Date arithmetic audit:** Identify all features computed as date differences and verify that the reference date is a fixed snapshot date, not an employee-specific terminal date.
10. **Post-split feature engineering audit:** Verify that all feature engineering transformations (binning, encoding, scaling, composite construction) are fitted on training data only.

---

*This report is produced as part of the Adaptive Workforce AI platform forensic governance process. Findings should be reviewed by a data governance officer before any model is promoted to production. All column classifications are conditional on dataset provenance documentation — classifications may change if source system metadata reveals different measurement windows or encoding processes.*
