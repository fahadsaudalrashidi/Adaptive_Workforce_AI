# Theory Construct Validity Audit
## HR Attrition Prediction Platform — Psychological Construct Integrity Review

**Document type:** Scientific audit — construct validity, psychometric defensibility, governance compliance  
**Target audience:** I/O psychology researchers; HR analytics governance boards; model validation committees  
**Platform:** Adaptive Workforce AI — Saudi HR Attrition Prediction System  
**Audit scope:** Phase 1 column mapping (`theory_aware_column_mapper.py`) + Phase 2 activation (`theory_grounded_construct_engine.py`) + known violations in legacy `feature_factory.py`  
**Theoretical framework:** COR (Hobfoll 1989), JD-R (Bakker & Demerouti 2007/2017), FFM (Costa & McCrae 1992), Mobley (1977), Adams (1963), Siegrist (1996), Kahn (1990)  
**Audit date:** 2026-05-20  
**Status:** Active — production pipeline in use

---

## Table of Contents

1. [Audit Purpose and Scope](#1-audit-purpose-and-scope)
2. [Construct 1 — SatisfactionIndex](#2-construct-1--satisfactionindex)
3. [Construct 2 — BurnoutRisk](#3-construct-2--burnoutrisk)
4. [Construct 3 — EngagementScore](#4-construct-3--engagementscore)
5. [Construct 4 — TenureRatio](#5-construct-4--tenureratio)
6. [Construct 5 — IncomePerLevel](#6-construct-5--incomeperlevel)
7. [Construct 6 — CareerProgression](#7-construct-6--careerprogression)
8. [Construct 7 — SalaryGrowth](#8-construct-7--salarygrowth)
9. [Cross-Construct Dependency Table](#9-cross-construct-dependency-table)
10. [Formula Integrity Matrix](#10-formula-integrity-matrix)
11. [Known Violations in feature_factory.py](#11-known-violations-in-feature_factorypy)
12. [Governance Summary and Recommendations](#12-governance-summary-and-recommendations)

---

## 1. Audit Purpose and Scope

This document provides a scientific construct validity audit of the seven psychological constructs computed by the platform's Phase 2 Theory-Grounded Construct Activation Engine. Each construct is derived from published organizational psychology theory. The audit evaluates:

- Whether the formula faithfully implements the paper-specified operationalization
- Whether the column mappings are construct-valid for Saudi HR datasets
- Which substitutions are scientifically impermissible and why
- What psychometric and interpretive risks attach to each construct
- What governance constraints must be enforced at the model and reporting layers
- How construct confidence should be downgraded when exact inputs are unavailable

### Terminological Conventions Used in This Audit

| Term | Meaning |
|------|---------|
| DIRECT_PAPER_REPLICATION | All inputs map exactly to IBM HR column definitions; formula is exact paper transcription |
| THEORY_COMPATIBLE_PROXY | One or more inputs are Saudi-equivalent columns with confirmed construct alignment |
| BLOCKED_INSUFFICIENT_EVIDENCE | Required input has no column meeting minimum confidence thresholds |
| BLOCKED_WEAK_PROXY | Candidate column exists but evidence quality is below STRONG_PROXY |
| BLOCKED_LEAKAGE_RISK | Column is target-adjacent and cannot be used as predictor |
| BLOCKED_SCALE_INVALID | Column exists but its measurement scale cannot be safely mapped to the formula's expected range |

### Minimum Activation Thresholds

Both conditions must hold for any column to be accepted as a formula input:

- Semantic confidence ≥ 0.70 (construct-level match quality)
- Scale confidence ≥ 0.70 (measurement scale match quality)
- Evidence strength: DIRECT or STRONG_PROXY only; WEAK_PROXY, UNSUPPORTED, and TARGET_ADJACENT are always blocked

---

## 2. Construct 1 — SatisfactionIndex

### 2.1 Construct Purpose

SatisfactionIndex aggregates four orthogonal satisfaction facets into a unidimensional well-being composite. It operationalizes the individual's subjective resource appraisal across work domains. In the attrition prediction model, a low SatisfactionIndex is theorized to reduce the psychological cost of leaving (Hobfoll's resource caravan collapse), increasing voluntary exit probability.

### 2.2 Theoretical Mechanism

**Primary theory:** COR — Conservation of Resources (Hobfoll 1989)  
**Secondary theory:** FFM — Five-Factor Model (Costa & McCrae 1992)

COR posits that individuals strive to acquire, retain, protect, and foster resources. When multiple resource categories (job content, physical environment, social relationships, temporal sovereignty) degrade simultaneously, the individual experiences a "caravan" loss — a compounding effect more threatening than single-resource loss. This construct operationalizes that caravan by aggregating four distinct resource satisfaction facets.

The FFM connection operates through inverse Neuroticism: individuals high in Neuroticism (emotional instability) systematically underrate satisfaction on all four facets. The simple mean therefore carries a latent Neuroticism signal; governance constraints must prevent this from being misattributed to organizational conditions alone.

**JD-R pathway:** Not the primary mechanism, but JD-R's resources branch overlaps with the environmental and relational satisfaction facets.

### 2.3 Exact Paper Formula

```
SatisfactionIndex = (JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction + WorkLifeBalance) / 4
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Direction |
|----------|--------------|-------|-----------|
| JobSatisfaction | `JobSatisfaction` | 1–4 Likert | 1=Low, 4=High |
| EnvironmentSatisfaction | `EnvironmentSatisfaction` | 1–4 Likert | 1=Low, 4=High |
| RelationshipSatisfaction | `RelationshipSatisfaction` | 1–4 Likert | 1=Low, 4=High |
| WorkLifeBalance | `WorkLifeBalance` | 1–4 Likert | 1=Poor, 4=Excellent |

**Output range:** 1.0–4.0 (arithmetic mean of four 1–4 Likert items)  
**Aggregation operator:** Simple unweighted mean — no differential weighting is paper-specified

### 2.4 Saudi-Compatible Column Mappings

**English mappings (DIRECT or STRONG_PROXY):**

| Formula Variable | Saudi English Synonym | Evidence Level |
|------------------|-----------------------|----------------|
| JobSatisfaction | `job_satisfaction`, `work_satisfaction`, `role_satisfaction` | STRONG_PROXY |
| EnvironmentSatisfaction | `workplace_satisfaction`, `environment_rating`, `office_satisfaction` | STRONG_PROXY |
| RelationshipSatisfaction | `colleague_satisfaction`, `team_satisfaction`, `peer_relationship` | STRONG_PROXY |
| WorkLifeBalance | `work_life_balance`, `wlb_rating`, `balance_score` | STRONG_PROXY |

**Arabic mappings (STRONG_PROXY with scale verification):**

| Formula Variable | Arabic Column Name | Notes |
|------------------|--------------------|-------|
| JobSatisfaction | `الرضا الوظيفي` | Verify 1–4 Likert; 1–5 requires rescaling with confidence penalty |
| EnvironmentSatisfaction | `الرضا عن بيئة العمل` | Same scale verification required |
| RelationshipSatisfaction | `الرضا عن العلاقات` | Same scale verification required |
| WorkLifeBalance | `التوازن بين العمل والحياة` | Critical: verify direction (1=Poor or 1=Excellent varies by instrument) |

### 2.5 Unsafe Substitutions — What Cannot Replace These Inputs

The following columns **cannot** substitute any of the four required inputs, regardless of column naming:

| Blocked Substitute | Reason |
|--------------------|--------|
| `EmployeeEngagement` (generic composite) | Conflates satisfaction with involvement; destroys the four-facet independence required by COR caravan logic |
| `PerformanceRating` | Performance outcome ≠ satisfaction perception; direction of causality is reversed |
| `JobInvolvement` | Behavioral investment construct (FFM/Kahn), not a satisfaction facet |
| `WorkLifeBalance` alone (as full SatisfactionIndex) | Single-facet cannot represent caravan; collapses three construct dimensions |
| `Absence` or `AbsenteeismRate` | Behavioral outcome, not attitudinal resource appraisal |
| `MonthlyIncome` | Objective resource ≠ subjective satisfaction appraisal |
| Any normalized `[0,1]` composite | Normalization destroys the scale anchoring required by the mean formula |

### 2.6 Blocked Substitutions with Scientific Reasons

**Why a weighted composite is not acceptable:**  
The paper formula specifies equal weighting. COR does not rank-order the four resource caravan facets. Differential weighting would impose a researcher-specific theory not present in the source paper, violating the DIRECT_PAPER_REPLICATION criterion.

**Why pre-normalized inputs are not acceptable:**  
Min-max normalization to [0,1] collapses the Likert scale anchor points. After normalization, a dataset where all employees score 3–4 on JobSatisfaction and one that has full 1–4 variance will produce the same normalized mean, eliminating the construct's sensitivity to population-level satisfaction deficits. This is the central violation in `feature_factory.py` (see Section 11).

**Why engagement composite scores cannot replace satisfaction items:**  
Engagement instruments (e.g., Gallup Q12, UWES) measure energy, dedication, and absorption — not hedonic resource appraisal. Substituting engagement for satisfaction conflates the JD-R motivational pathway (engagement) with the COR resource conservation pathway (satisfaction).

### 2.7 Psychometric Limitations

1. **Acquiescence bias:** All four items share a common unidirectional Likert direction. High-acquiescence respondents inflate SatisfactionIndex independent of true resource states. No correction mechanism is applied.
2. **Positivity bias in Saudi cultural contexts:** Research on Middle Eastern organizational surveys (Elsaid & Elsaid 2012) documents systematically elevated satisfaction ratings relative to Western norms, compressing the effective range toward the upper tail.
3. **Single-item measurement:** Each facet is measured by a single Likert item in the IBM HR dataset. Single-item reliability is lower than multi-item subscale reliability; Cronbach's alpha cannot be computed for this construct.
4. **Cross-sectional snapshot limitation:** The construct captures momentary resource appraisal; longitudinal degradation trajectories (which are more predictive of exit) are not captured.
5. **Common method variance:** JobSatisfaction and EnvironmentSatisfaction are collected in the same survey, introducing common method bias that inflates their apparent correlation.

### 2.8 Known Interpretation Risks

- **Directional assumption:** Higher SatisfactionIndex = lower attrition risk. This assumes the attrition model uses SatisfactionIndex as a negative predictor. If included as a raw feature, the model learns this direction from data — but if the data contains survivorship bias (highly dissatisfied employees already left), the remaining distribution may not support this direction.
- **Scale ambiguity risk:** WorkLifeBalance in some Saudi HR systems is coded 1=Excellent, 4=Poor (reversed). If imported without direction verification, SatisfactionIndex will be inverted for this facet. The construct engine checks scale direction via value distribution, but Arabic-language datasets may not have documented direction metadata.
- **Caravan vs. compensation:** COR caravan theory assumes losses compound non-linearly. The arithmetic mean imposes linear additivity, which is a simplification. Researchers using SatisfactionIndex should not interpret it as a pure COR caravan operationalization.

### 2.9 Governance Constraints

- SatisfactionIndex must not be reported as an absolute score to employees or managers without contextualization against department-level baselines.
- When activation mode is THEORY_COMPATIBLE_PROXY, confidence ceiling is 0.80 (not 0.95).
- Each STRONG_PROXY input incurs a 0.08 confidence penalty. With four proxy inputs, maximum reachable confidence is 0.95 − (4 × 0.08) = 0.63.
- SatisfactionIndex values must never be presented as direct measures of organizational culture quality without longitudinal reference data.

### 2.10 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| All four inputs are DIRECT (IBM HR exact columns) | 0.00 | 0.95 |
| One STRONG_PROXY input | −0.08 | 0.87 |
| Two STRONG_PROXY inputs | −0.16 | 0.79 |
| Three STRONG_PROXY inputs | −0.24 | 0.71 |
| Four STRONG_PROXY inputs | −0.32 | 0.63 |
| Any input below 0.70 semantic or scale confidence | Blocked | N/A |
| Any input is WEAK_PROXY | Blocked | N/A |

---

## 3. Construct 2 — BurnoutRisk

### 3.1 Construct Purpose

BurnoutRisk operationalizes the individual-level depletion of energy resources through a demand-gate mechanism. It is not a clinical burnout measure but a structural risk indicator: it is zero for all employees not working overtime, regardless of their work-life balance rating. This binary gate structure is theoretically essential and distinguishes it from all additive composites.

### 3.2 Theoretical Mechanism

**Primary theory:** JD-R — Job Demands-Resources Model, health-impairment pathway (Bakker & Demerouti 2017)  
**Secondary theory:** COR — energy resource depletion gate (Hobfoll 1989)

The JD-R health-impairment pathway specifies that excessive job demands (here: overtime as an operationalization of sustained high demand) deplete energy resources, leading to exhaustion, cynicism, and ultimately burnout. The health-impairment pathway is distinct from the JD-R motivational pathway (which drives engagement, not burnout).

COR provides the energy framing: overtime depletes the core energy resource (vitality). WorkLifeBalance operationalizes the rate of energy recovery — poor balance (score=1) means energy is not restored outside work hours. The multiplicative gate in the formula captures COR's threshold concept: if no overtime occurs, the depletion mechanism is not activated regardless of recovery capacity.

**Gate logic (theoretically mandatory):** When `OverTime = 0`, `BurnoutRisk = 0` for all values of WorkLifeBalance. This eliminates false positives for employees with poor work-life balance who nevertheless do not work overtime.

### 3.3 Exact Paper Formula

```
BurnoutRisk = OverTime_binary × (5 − WorkLifeBalance)
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Notes |
|----------|--------------|-------|-------|
| OverTime_binary | `OverTime` | {0, 1} | Yes=1, No=0; binarization documented when continuous |
| WorkLifeBalance | `WorkLifeBalance` | 1–4 Likert | 1=Poor, 4=Excellent; (5−WLB) inverts so 4=highest risk factor |

**Derivation of (5 − WorkLifeBalance):**  
WorkLifeBalance range 1–4 is inverted by subtracting from 5, producing a "deprivation factor" in range 1–4:
- WLB=4 (Excellent) → factor=1 (minimal amplification)
- WLB=3 → factor=2
- WLB=2 → factor=3
- WLB=1 (Poor) → factor=4 (maximum amplification)

**Output range:** 0–4  
- 0: Employee not working overtime (gate closed)  
- 1: Overtime + excellent work-life balance  
- 4: Overtime + poorest work-life balance (maximum risk)

### 3.4 Saudi-Compatible Column Mappings

**OverTime (binary gate):**

| Saudi English Synonym | Arabic | Notes |
|-----------------------|--------|-------|
| `overtime`, `over_time`, `extra_hours_flag` | `العمل الإضافي` | Must be Yes/No or 0/1; continuous hours binarized with 0.10 penalty |
| `is_overtime`, `overtime_indicator` | `مؤشر الوقت الإضافي` | Preferred binary form |

**WorkLifeBalance:**

| Saudi English Synonym | Arabic | Notes |
|-----------------------|--------|-------|
| `work_life_balance`, `wlb_score`, `balance_rating` | `التوازن بين العمل والحياة` | Must confirm 1=Poor direction; 1–5 scale rescaled with 0.10 penalty |

### 3.5 Unsafe Substitutions

| Blocked Substitute for OverTime | Scientific Reason |
|---------------------------------|------------------|
| `WorkHours`, `TotalHours`, `HoursPerWeek` | Continuous hours measure different construct; no validated threshold for binary depletion gate |
| `WorkloadRating` (Likert) | Subjective demand perception ≠ objective overtime indicator; different theoretical pathway |
| `Absence` | Behavioral consequence, not demand input; reverses causal direction |
| `StressLevel` | Mediator or outcome variable; cannot serve as demand input without circularity |

| Blocked Substitute for WorkLifeBalance | Scientific Reason |
|----------------------------------------|------------------|
| `Absence`, `SickLeave` | Behavioral expression of imbalance, not its rating; collapses cause and effect |
| `JobSatisfaction` | Different construct dimension; satisfaction ≠ balance |
| `CommutingTime` / `DistanceFromHome` | Antecedent of imbalance, not its appraisal |
| `FamilyStatus` (Married/Single) | Demographic moderator, not a balance rating |

### 3.6 Binarization Protocol

When OverTime is not native binary, the following documented rules apply in order:

1. **Yes/No strings:** Map `"Yes"→1`, `"No"→0`. No penalty. Full confidence preserved.
2. **Numeric 0/1:** Accept as-is. No penalty.
3. **Continuous hours (e.g., 0–80):** Binarize as `(hours > 0) → 1`. Apply 0.10 confidence penalty. Log warning with original range.
4. **Unresolvable values:** Block BurnoutRisk. Do not approximate.

When WorkLifeBalance is not 1–4:

1. **1–4:** Accept as-is. No penalty.
2. **1–5:** Rescale via `wlb_4 = 1 + (wlb_5 − 1) × 0.75`. Apply 0.10 confidence penalty.
3. **0–100:** Rescale via `wlb_4 = 1 + wlb_100 × 0.03`. Apply 0.15 confidence penalty.
4. **Other:** Block BurnoutRisk.

### 3.7 Psychometric Limitations

1. **Binary demand oversimplification:** OverTime as a binary variable loses intensity information. An employee working 60 hours/week and one working 41 hours/week are treated identically. This reduces the construct's sensitivity at high-demand extremes.
2. **WLB self-report bias:** Work-life balance satisfaction is a hedonic appraisal, subject to adaptation effects (employees adapt to chronic imbalance and rate it as normal over time).
3. **No separation of burnout dimensions:** The formula operationalizes the energy depletion dimension of burnout (Maslach 1981) but does not separately capture depersonalization or reduced accomplishment. The construct name BurnoutRisk should be understood as exhaustion-pathway risk, not clinical burnout probability.
4. **Gate eliminates partial overtime cases:** Employees working occasional unplanned overtime (which may be coded No in surveys) are classified as zero risk even if their WLB is severely degraded.

### 3.8 Known Interpretation Risks

- **Zero inflation:** All non-overtime employees receive BurnoutRisk=0 regardless of WLB. In datasets where 60–70% of employees do not work overtime (typical in Saudi professional services), the construct will have a strongly zero-inflated distribution. Machine learning models treating this as a continuous feature may be misled.
- **Scale direction criticality:** If WorkLifeBalance is coded 1=Excellent rather than 1=Poor, the formula produces an inverted signal — employees with the best balance receive the highest BurnoutRisk scores. This is a data quality failure that produces systematically wrong model features. The construct engine's scale validation attempts to detect this but cannot guarantee it for undocumented datasets.
- **Confounding with volition:** Some employees work overtime voluntarily (high autonomy, high Conscientiousness) and report high WLB. The formula assigns them the same BurnoutRisk as involuntary overtime workers with identical WLB scores. The construct cannot distinguish motivated from pressured overtime.

### 3.9 Governance Constraints

- BurnoutRisk must be disclosed to HR professionals as a structural risk indicator, not a clinical burnout diagnosis.
- When OverTime is binarized from continuous hours, reports must note: "OverTime column binarized from continuous hours measure — confidence penalized by 10%."
- BurnoutRisk scores must not be used as input to any employee wellness intervention without clinical review by an occupational psychologist.
- Saudi labor law context: OverTime norms differ by sector (government vs. private, Vision 2030 entities vs. SMEs). BurnoutRisk scores are not comparable across sectors without sector-stratified baseline calibration.

### 3.10 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| Both inputs DIRECT, OverTime native binary, WLB 1–4 | 0.00 | 0.95 |
| OverTime binarized from continuous | −0.10 | 0.85 |
| WLB rescaled from 1–5 | −0.10 | 0.85 |
| WLB rescaled from 0–100 | −0.15 | 0.80 |
| One STRONG_PROXY input | −0.08 | 0.87 |
| OT binarized + WLB rescaled 1-5 + proxy inputs | cumulative | floor 0.30 |

---

## 4. Construct 3 — EngagementScore

### 4.1 Construct Purpose

EngagementScore captures the simultaneous co-presence of cognitive investment (involvement) and affective resource availability (satisfaction). It operationalizes Kahn's (1990) foundational definition of engagement as the harnessing of organization members' selves to their work roles — requiring both psychological presence (involvement) and psychological safety/meaningfulness (satisfaction).

### 4.2 Theoretical Mechanism

**Primary theory:** JD-R motivational pathway — resources fuel engagement (Bakker & Demerouti 2017)  
**Secondary theory:** FFM Conscientiousness — behavioral disposition toward involvement and effort  
**Foundation:** Kahn (1990) — engagement as simultaneous cognitive-affective investment

Kahn (1990) explicitly specified that engagement requires simultaneous presence of psychological meaningfulness, psychological safety, and psychological availability. The multiplicative formula enforces the "simultaneity condition": an employee with maximum involvement but zero satisfaction — indicating a meaningful job in a hostile or unsustaining environment — cannot be meaningfully engaged. The product of zero satisfaction is zero engagement, regardless of involvement.

The FFM connection operates through Conscientiousness: high-Conscientiousness individuals display systematically higher JobInvolvement scores (Matthews & Deary 1998), making JobInvolvement a behavioral proxy for the trait dimension.

### 4.3 Exact Paper Formula

```
EngagementScore = JobInvolvement × JobSatisfaction
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Notes |
|----------|--------------|-------|-------|
| JobInvolvement | `JobInvolvement` | 1–4 ordinal | 1=Low, 4=High; Conscientiousness behavioral correlate |
| JobSatisfaction | `JobSatisfaction` | 1–4 Likert | 1=Low, 4=High; resource availability signal |

**Output range:** 1–16 (IBM HR scales: 1×1=1 minimum; 4×4=16 maximum)  
**Aggregation operator:** Multiplication — not addition, not weighted mean  
**Zero handling:** If either input is zero (only possible if data is corrupted, as IBM HR uses 1–4), output is zero. Dataset documentation must confirm minimum value is 1, not 0.

### 4.4 Saudi-Compatible Column Mappings

| Formula Variable | Saudi English Synonym | Arabic | Evidence |
|------------------|-----------------------|--------|----------|
| JobInvolvement | `job_involvement`, `work_involvement`, `role_involvement` | `الانخراط الوظيفي` | STRONG_PROXY |
| JobSatisfaction | `job_satisfaction`, `work_satisfaction` | `الرضا الوظيفي` | STRONG_PROXY |

### 4.5 Unsafe Substitutions

| Blocked Substitute for JobInvolvement | Scientific Reason |
|---------------------------------------|------------------|
| `EmployeeEngagement` (composite score) | Contains satisfaction component; produces circular formula (satisfaction × satisfaction-composite) |
| `PerformanceRating` | Performance outcome ≠ cognitive investment; eliminates Kahn's psychological presence dimension |
| `TrainingHours` | Learning investment ≠ role involvement; different construct domain |
| `YearsAtCompany` | Tenure is a structural variable, not a psychological investment measure |

| Blocked Substitute for JobSatisfaction | Scientific Reason |
|----------------------------------------|------------------|
| `EnvironmentSatisfaction` alone | Sub-facet only; misses affective job content evaluation |
| `WorkLifeBalance` alone | Resource appraisal facet, not job content satisfaction |
| `JobInvolvement` itself | Would produce JobInvolvement², losing the resource dimension entirely |

### 4.6 Psychometric Limitations

1. **Scale non-additivity assumption:** The multiplicative formula assumes that the psychological meaning of `JobInvolvement=4, JobSatisfaction=1` (highly involved, deeply dissatisfied — a theoretically distressed profile) is equivalent to `JobInvolvement=2, JobSatisfaction=2` (moderately both). Both produce a score of 4. This is a known psychometric limitation of multiplicative composites.
2. **Ordinal multiplication validity:** Multiplying two ordinal-level variables is technically inappropriate without interval-level justification. The formula treats the 1–4 scale as interval, which is defensible for IBM HR Likert scales under weak measurement assumptions but cannot be confirmed without factor analysis.
3. **Range restriction:** In organizational samples with positive selection (voluntary survey participation), both JobInvolvement and JobSatisfaction tend to be right-skewed, compressing EngagementScore into the upper portion of the 1–16 range.
4. **Simultaneity assumption:** Kahn's simultaneity requirement is only partially captured. The formula does not include psychological safety (which would require a manager quality or psychological safety item not included in the formula specification).

### 4.7 Known Interpretation Risks

- **Score non-uniqueness:** Multiple (JobInvolvement, JobSatisfaction) pairs produce the same EngagementScore. A score of 8 is produced by (2,4), (4,2), and (8/3, 3) [if not integer-constrained]. Reporting EngagementScore without decomposition loses meaningful profile information.
- **Conflation with SatisfactionIndex:** JobSatisfaction feeds both SatisfactionIndex (Construct 1) and EngagementScore (Construct 3). When both constructs are included as model features, multicollinearity is introduced through this shared input. Regularization or variance inflation factor monitoring is required.
- **Scale minimum assumption:** If any Saudi HR dataset codes JobInvolvement or JobSatisfaction with a minimum of 0 (rather than 1), zero scores become possible and the construct loses its 1–16 range guarantee.

### 4.8 Governance Constraints

- EngagementScore must not be conflated with validated engagement instruments (UWES, Gallup Q12). It is a theory-grounded formula, not a psychometrically validated scale.
- The multiplicative structure must be preserved in all transformations. EngagementScore must not be post-hoc normalized before entering the model (normalization applies to the output, not the inputs).
- When both SatisfactionIndex and EngagementScore are used as model features, the shared JobSatisfaction input must be disclosed in the model card and VIF must be monitored.

### 4.9 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| Both DIRECT (IBM HR columns) | 0.00 | 0.95 |
| JobInvolvement is STRONG_PROXY | −0.08 | 0.87 |
| JobSatisfaction is STRONG_PROXY | −0.08 | 0.87 |
| Both STRONG_PROXY | −0.16 | 0.79 |

---

## 5. Construct 4 — TenureRatio

### 5.1 Construct Purpose

TenureRatio operationalizes the proportion of an individual's total career spent at the current organization. A high ratio (approaching 1.0) signals a career-loyal employee with high accumulated switching costs (lost pension rights, social capital, seniority benefits). A low ratio signals a mobile employee whose total career demonstrates willingness to change employers.

### 5.2 Theoretical Mechanism

**Primary theory:** COR — condition resource (organizational membership as accumulated condition resource; Hobfoll 1989)  
**Secondary theory:** Mobley (1977), Stage 1 — evaluation of the current job

Mobley's 1977 process model specifies that voluntary turnover begins with evaluation of the current job relative to alternatives. TenureRatio captures the structural component of this evaluation: an employee who has committed the majority of their career to one employer has implicitly demonstrated (or been trapped by) high switching costs. COR frames organizational tenure as a condition resource — a stable status that provides security and identity.

**+1 denominator:** The paper-specified `+1` in the denominator prevents division by zero for fresh graduates (`TotalWorkingYears = 0`). It is not an arbitrary constant; it is documented as a protection for career entrants and is part of the formula specification.

### 5.3 Exact Paper Formula

```
TenureRatio = YearsAtCompany / (TotalWorkingYears + 1)
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Notes |
|----------|--------------|-------|-------|
| YearsAtCompany | `YearsAtCompany` | Continuous positive integer (years) | Numerator: current employer tenure |
| TotalWorkingYears | `TotalWorkingYears` | Continuous positive integer (years) | Denominator: career span including prior employers |

**Output range:** 0 to ~1  
- 0.0: Fresh joiners with long prior career (`YearsAtCompany=0`)  
- ~1.0: Career loyalists (`YearsAtCompany ≈ TotalWorkingYears`)  
- >1.0: Theoretically impossible but may occur when `YearsAtCompany > TotalWorkingYears` due to data entry errors; must be flagged

**Data quality check:** Any row where `YearsAtCompany > TotalWorkingYears` indicates a data integrity failure. Such rows must produce a NaN output with a governance warning.

### 5.4 Saudi-Compatible Column Mappings

| Formula Variable | Saudi English Synonym | Arabic | Evidence |
|------------------|-----------------------|--------|----------|
| YearsAtCompany | `years_at_company`, `tenure_years`, `company_tenure`, `years_with_employer` | `سنوات في الشركة`, `مدة الخدمة` | STRONG_PROXY |
| TotalWorkingYears | `total_experience`, `career_years`, `total_tenure`, `work_experience_years` | `إجمالي سنوات الخبرة`, `مجموع سنوات العمل` | STRONG_PROXY |

### 5.5 Unsafe Substitutions

| Blocked Substitute | Target Variable | Scientific Reason |
|--------------------|----------------|------------------|
| `Age` | TotalWorkingYears | Age ≠ total career span; ignores education years, career breaks, late entrants |
| `JobLevel` | YearsAtCompany | Structural rank ≠ tenure at current employer |
| `YearsInCurrentRole` | YearsAtCompany | Role tenure is shorter than employer tenure by definition; different construct |
| `YearsSinceLastPromotion` | Either | Promotion lag ≠ career span; captures different phenomenon |
| `NumCompaniesWorked` | TotalWorkingYears | Count of employers ≠ years of total experience; ignores duration per employer |

### 5.6 Psychometric Limitations

1. **Non-linear switching cost assumption:** COR assumes switching costs accumulate non-linearly with tenure (pension cliffs, social network density, skill specificity). The formula uses a linear ratio, which understates the effect at high tenure values.
2. **Voluntary vs. involuntary tenure conflation:** Long tenure may reflect career commitment (intended) or labor market constraints (trapped). The formula cannot distinguish these mechanisms.
3. **Cohort effects:** In Saudi Vision 2030 context, TotalWorkingYears for young Saudized workforce entrants may be systematically shorter than their international counterparts. Ratios near 1.0 in this cohort do not carry the same switching-cost interpretation.
4. **Unit consistency requirement:** If `YearsAtCompany` is in years and `TotalWorkingYears` is in months (occasionally found in Arabic HR exports), the ratio will be numerically wrong by a factor of 12. The construct engine validates scale type but cannot detect unit mismatch within the same scale category.

### 5.7 Known Interpretation Risks

- **TenureRatio > 1.0 signals data error** (impossible: cannot be at company longer than total career). Any such cases must produce a NaN and a data quality warning rather than a computed value.
- **Direction of attrition prediction is not universal:** High TenureRatio could predict either low attrition (loyal employee) or moderate attrition (employee who realizes all career progress has been at one company and decides to diversify). The model will learn the direction from data, but interpretation without theoretical qualification is inappropriate.

### 5.8 Governance Constraints

- Rows with `YearsAtCompany > TotalWorkingYears` must return `NaN` for TenureRatio. They must not receive the closest valid value or a median imputation without flagging.
- TenureRatio must not be presented to employees as a loyalty score. It is an organizational mobility signal, not an evaluation of employee commitment.
- Saudi Saudization (nationalization) programs may create systematic differences in TenureRatio distributions between Saudi and non-Saudi employees. Cross-group comparisons require demographic stratification.

### 5.9 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| Both inputs DIRECT | 0.00 | 0.95 |
| YearsAtCompany is STRONG_PROXY | −0.08 | 0.87 |
| TotalWorkingYears is STRONG_PROXY | −0.08 | 0.87 |
| Both STRONG_PROXY | −0.16 | 0.79 |
| Unit inconsistency detected | Blocked | N/A |

---

## 6. Construct 5 — IncomePerLevel

### 6.1 Construct Purpose

IncomePerLevel captures whether an employee's monetary compensation is commensurate with their organizational rank. It is a rank-relative equity signal: a senior manager (JobLevel=4) earning a salary equivalent to an analyst-level role is experiencing acute equity deprivation, whereas a junior employee (JobLevel=1) earning the same absolute salary is in a positive equity position. The construct does not measure absolute poverty or underpayment — it measures position-income alignment.

### 6.2 Theoretical Mechanism

**Primary theory:** COR — object resource (monetary resources as protection against environmental and psychological threat; Hobfoll 1989)  
**Secondary theory:** Adams Equity Theory (1963) — perception of fair input-outcome ratio relative to comparison others

Adams (1963) specifies that employees compare their input-to-outcome ratio against a referent (other employees at similar levels). When the ratio is unfavorable — high job level (high input) with low income (low outcome) — the individual experiences inequity tension. This tension motivates either behavior change (demand raise, reduce effort) or withdrawal (exit). IncomePerLevel operationalizes this relative inequity signal using job level as the organizational input proxy.

The `+1` denominator prevents division by zero at `JobLevel = 0` (a data quality edge case not present in IBM HR, which uses levels 1–5, but possible in Saudi HR datasets using zero-indexed grades).

### 6.3 Exact Paper Formula

```
IncomePerLevel = MonthlyIncome / (JobLevel + 1)
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Saudi Range |
|----------|--------------|-------|-------------|
| MonthlyIncome | `MonthlyIncome` | Continuous positive (USD or local currency) | 5,000–30,000 SAR monthly |
| JobLevel | `JobLevel` | Ordinal 1–5 | 1=Entry, 5=Executive; zero-indexed variants use 0–4 |

**Output:** Income units per (level+1) — dimensionally has currency/level units  
**Saudi SAR context:** With SAR range 5,000–30,000 and JobLevel 1–5, IncomePerLevel ranges approximately 2,500–15,000 SAR per level unit at median scenarios.

### 6.4 Saudi-Compatible Column Mappings

| Formula Variable | Saudi English Synonym | Arabic | Evidence |
|------------------|-----------------------|--------|----------|
| MonthlyIncome | `monthly_salary`, `base_salary`, `gross_salary`, `monthly_wage` | `الراتب الشهري`, `الدخل الشهري` | STRONG_PROXY |
| JobLevel | `job_level`, `grade`, `job_grade`, `position_level`, `career_level` | `المستوى الوظيفي`, `الدرجة الوظيفية` | STRONG_PROXY |

### 6.5 Unsafe Substitutions

| Blocked Substitute for MonthlyIncome | Scientific Reason |
|--------------------------------------|------------------|
| `AnnualSalary / 12` (when not explicitly stated) | Permissible only if conversion is documented; undocumented conversion introduces currency-period errors |
| `TotalCompensation` (including bonuses) | Bonus components are variable outcomes; base salary is the stable resource signal Adams (1963) specifies |
| `SalaryHike` (percentage) | Rate of change ≠ current level; different construct (feeds SalaryGrowth, Construct 7) |
| `SalaryBand` (categorical) | Categorical band midpoints introduce approximation error and lose within-band variance |

| Blocked Substitute for JobLevel | Scientific Reason |
|---------------------------------|------------------|
| `YearsAtCompany` | Tenure ≠ rank; seniority-based organizations may equate these but it destroys generalizability |
| `PerformanceRating` | Performance outcome ≠ structural job grade; eliminates equity comparison referent |
| `JobRole` (categorical) | Nominal role label without ordinal structure cannot serve as a rank input |
| `Age` | Demographics cannot substitute organizational hierarchy position |

### 6.6 Psychometric Limitations

1. **Currency heterogeneity:** Saudi datasets may mix SAR, USD, and "thousands" units within the same column (a common HR export artifact). The formula produces nonsensical values if income units are not homogeneous.
2. **Non-linear level transitions:** The difference between JobLevel 1 and 2 (junior to mid-level) does not carry the same organizational weight as the difference between 4 and 5 (director to executive). The formula treats level differences as linear, which misrepresents the equity gap at executive transitions.
3. **Internal vs. market equity:** The formula captures internal equity (within-organization rank-income alignment) but does not address external equity (alignment with market rates). An employee at a well-paying company may have a higher IncomePerLevel than a competitor's equivalent employee without experiencing equity satisfaction.
4. **Bonus exclusion:** Saudi HR compensation frequently includes significant non-base components (housing allowance, transportation allowance, performance bonuses). Excluding these from MonthlyIncome underestimates total compensation for senior levels where allowances are a larger share.

### 6.7 Known Interpretation Risks

- **Low IncomePerLevel does not mean exploitation:** A senior executive (JobLevel=5) earning the median organizational salary will have a low IncomePerLevel, but this reflects rank expectations, not underpayment relative to external markets.
- **Cross-sector comparability:** Saudi government employees have different salary structures than private sector employees. IncomePerLevel comparisons across sectors are not valid without sector stratification.
- **Currency normalization warning:** If MonthlyIncome is reported in thousands (common in Arabic HR exports where "15" means 15,000 SAR), IncomePerLevel values will differ from those in a dataset with full values by a factor of 1,000. The construct carries no intrinsic unit; interpretation requires documented units.

### 6.8 Governance Constraints

- IncomePerLevel must be labeled as an equity signal, not an underpayment indicator, in all HR analytics reports.
- IncomePerLevel must not be reported at the individual employee level to managers without HR governance approval, as it reveals individual salary information in ratio form.
- Currency unit must be documented in model metadata. If unit cannot be confirmed, a governance warning must be appended to all IncomePerLevel outputs.

### 6.9 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| Both inputs DIRECT | 0.00 | 0.95 |
| MonthlyIncome STRONG_PROXY | −0.08 | 0.87 |
| JobLevel STRONG_PROXY | −0.08 | 0.87 |
| Both STRONG_PROXY | −0.16 | 0.79 |
| Currency unit undocumented | Governance warning appended | confidence unchanged but report flagged |

---

## 7. Construct 6 — CareerProgression

### 7.1 Construct Purpose

CareerProgression measures the rate of organizational advancement per unit of tenure. It is a career velocity metric: employees who reach senior levels quickly demonstrate high advancement velocity; those who remain at entry levels after many years experience stagnation. Career stagnation is a documented antecedent of voluntary turnover independent of salary dissatisfaction (Allen, Bryant & Vardaman 2010).

### 7.2 Theoretical Mechanism

**Primary theory:** COR — resource gain velocity (the rate at which condition and status resources are acquired; Hobfoll 1989)  
**Secondary theory:** JD-R — growth resource adequacy (whether the job provides sufficient opportunities for development; Bakker & Demerouti 2007)

COR specifies that resource gain (acquiring higher job level = condition resource) is motivationally salient. When gain velocity is low relative to career expectations, the individual anticipates future resource loss (career ceiling), triggering withdrawal cognition. JD-R frames promotions and advancement opportunities as growth resources; their absence (low CareerProgression) constitutes a resource deficit on the growth dimension.

### 7.3 Exact Paper Formula

```
CareerProgression = JobLevel / (YearsAtCompany + 1)
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Notes |
|----------|--------------|-------|-------|
| JobLevel | `JobLevel` | Ordinal 1–5 | Current organizational rank |
| YearsAtCompany | `YearsAtCompany` | Continuous positive integer | Current employer tenure |

**+1 denominator:** Prevents division by zero for new joiners (`YearsAtCompany = 0`); also applies a temporal smoothing that reflects the zero-experience baseline.  
**Output interpretation:** High value = rapid advancement; low value = stagnation  
**Typical ranges:** A JobLevel=3 employee with 3 years: 3/4=0.75 (fast). A JobLevel=3 employee with 20 years: 3/21=0.14 (slow). A JobLevel=5 employee with 10 years: 5/11=0.45 (very fast).

### 7.4 Saudi-Compatible Column Mappings

Same as IncomePerLevel mappings for JobLevel (see Section 6.4) and TenureRatio mappings for YearsAtCompany (see Section 5.4). See the Cross-Construct Dependency Table in Section 9.

### 7.5 Unsafe Substitutions

| Blocked Substitute for JobLevel | Scientific Reason |
|---------------------------------|------------------|
| `PromotionFairness` (Likert) | Perceptual fairness rating ≠ actual organizational rank; measures a different construct (justice perception) |
| `PerformanceRating` | Performance appraisal outcome ≠ hierarchical position; high performers at low levels may be stagnating |
| `JobRole` (nominal) | Nominal role cannot serve as ordinal velocity numerator |
| `NumCompaniesWorked` | Career breadth measure ≠ organizational depth measure |

| Blocked Substitute for YearsAtCompany | Scientific Reason |
|---------------------------------------|------------------|
| `TotalWorkingYears` | Total career span ≠ current employer tenure; the formula specifically requires within-employer advancement velocity |
| `Age` | Age and tenure diverge systematically for late-career changers |
| `YearsInCurrentRole` | Role tenure is a sub-interval of employer tenure; produces a different (role stagnation) signal |

### 7.6 Psychometric Limitations

1. **Level ceiling for senior employees:** Executives at JobLevel=5 cannot advance further; their CareerProgression score declines with each additional year of tenure, conflating tenure loyalty with stagnation. Long-serving senior leaders will be misclassified as stagnating.
2. **Organization-specific level definitions:** JobLevel=3 in a large organization (middle management) differs from JobLevel=3 in a startup (senior contributor). The formula produces non-comparable signals across organizations of different size and structure.
3. **Promotion timing artifacts:** Employees promoted just before the survey will have higher CareerProgression than equivalent employees promoted just after. The formula is cross-sectionally biased by promotion timing.
4. **Saudi organizational hierarchy conventions:** Some Saudi organizations use different grade numbering conventions (grade bands 1–15, where 1=highest) requiring direction inversion before application.

### 7.7 Known Interpretation Risks

- **Senior employee misclassification:** Long-tenured senior employees (JobLevel=5, YearsAtCompany=25) receive `5/26 = 0.19` — a "low progression" score despite having reached the top of the hierarchy. This is a known formula artifact; governance controls must prevent automatic assignment of high attrition risk to long-serving senior leaders on this construct alone.
- **Direction reversal check:** If JobLevel is coded highest=1 (as in some Saudi systems), CareerProgression must be inverted before use. Scale validation in Phase 1 detects ordinal direction but may not catch all Saudi-specific inversions.

### 7.8 Governance Constraints

- CareerProgression must not be used as a sole signal for attrition risk for employees at the maximum job level.
- Grade direction must be documented in Phase 1 metadata before activation. Undocumented grade direction triggers a governance warning.
- Cross-organization comparisons of CareerProgression are not valid without normalization to organization-specific level structures.

### 7.9 Confidence Downgrade Logic

Same structure as IncomePerLevel (Section 6.9), since the same input columns are used for JobLevel and YearsAtCompany.

---

## 8. Construct 7 — SalaryGrowth

### 8.1 Construct Purpose

SalaryGrowth operationalizes the alignment between merit-based reward (salary hike percentage) and demonstrated performance. It captures the degree to which the organization's reward system is coupled to performance — a critical signal in the Effort-Reward Imbalance framework. When rewards are decoupled from performance (high performance, low hike or vice versa), the organization's psychological contract with the employee is violated.

### 8.2 Theoretical Mechanism

**Primary theory:** Siegrist Effort-Reward Imbalance (ERI) model (1996) — chronic imbalance between effort expended and reward received is a primary occupational stressor  
**Secondary theory:** JD-R — compensation as a tangible job resource  
**Tertiary theory:** FFM — Conscientious employees are particularly sensitive to effort-reward misalignment because they invest high effort and expect commensurate reward

Siegrist (1996) demonstrated that effort-reward imbalance predicts cardiovascular disease, depression, and work-related mental ill-health. In the attrition context, the ERI pathway operates through perceived injustice: high-performance employees receiving low salary hikes experience acute inequity (overlapping with Adams 1963) and reward inadequacy, which motivates exit cognition.

The multiplicative structure captures the "match" requirement: a high salary hike for a low performer represents organizational misalignment (rewarding non-performance) rather than a motivating signal. A low salary hike for a high performer operationalizes the classic ERI imbalance case.

### 8.3 Exact Paper Formula

```
SalaryGrowth = PercentSalaryHike × PerformanceRating
```

**Variable definitions:**

| Variable | IBM HR Column | Scale | Notes |
|----------|--------------|-------|-------|
| PercentSalaryHike | `PercentSalaryHike` | Continuous 11–25% (IBM HR range) | Annual percentage increase in base salary |
| PerformanceRating | `PerformanceRating` | Ordinal 1–4 (IBM HR: 3=Excellent, 4=Outstanding) | Annual performance appraisal |

**Output range:** IBM HR: 11×1=11 (minimum) to 25×4=100 (maximum)  
**Interpretation:** High score = high reward commensurate with high performance (well-aligned); Low score = either low performer, low hike, or both; Misalignment is not directly captured by the score magnitude alone.

**Note on misalignment detection:** The formula as specified does not directly flag misalignment cases (high hike + low performance or low hike + high performance). Misalignment detection requires residual analysis against the expected hike-performance relationship and is beyond the formula's direct scope.

### 8.4 Saudi-Compatible Column Mappings

| Formula Variable | Saudi English Synonym | Arabic | Evidence |
|------------------|-----------------------|--------|----------|
| PercentSalaryHike | `salary_hike_pct`, `annual_raise_pct`, `salary_increase_pct`, `raise_percentage` | `نسبة زيادة الراتب`, `نسبة الرفع` | STRONG_PROXY |
| PerformanceRating | `performance_rating`, `annual_rating`, `performance_score`, `appraisal_rating` | `تقييم الأداء`, `درجة الأداء` | STRONG_PROXY |

### 8.5 Unsafe Substitutions

| Blocked Substitute for PercentSalaryHike | Scientific Reason |
|------------------------------------------|------------------|
| `MonthlyIncome` (absolute) | Current salary level ≠ growth rate; eliminates the dynamic reward signal |
| `IncomePerLevel` (Construct 5) | Derived construct; circular if used as input to another construct |
| `PromotionFairness` (Likert) | Perception of fairness ≠ actual monetary reward received |
| `NumStockOptionLevel` | Equity compensation ≠ salary hike; different reward type, different ERI pathway |

| Blocked Substitute for PerformanceRating | Scientific Reason |
|------------------------------------------|------------------|
| `JobInvolvement` | Behavioral investment ≠ performance appraisal outcome; different construct entirely |
| `TrainingTimesLastYear` | Training participation ≠ performance output |
| `PercentSalaryHike` itself | Self-substitution; produces `(PercentSalaryHike)²`, a non-theoretical construct |

### 8.6 Psychometric Limitations

1. **Manager bias in PerformanceRating:** Performance ratings are subject to halo effects, leniency bias, recency bias, and in Saudi organizational contexts, wasta (social network influence) effects. The formula treats PerformanceRating as an objective performance signal; it is more accurately described as a "rated performance" signal subject to systematic distortion.
2. **Salary hike range compression:** If the organization has narrow hike bands (e.g., all employees receive 10–12% regardless of performance), SalaryGrowth loses discriminant validity because the hike component has near-zero variance.
3. **Scale compatibility across organizations:** IBM HR PerformanceRating uses a 1–4 scale where 3 and 4 are "above expectations" categories (most employees score 3–4). Saudi performance management systems may use 1–5 with a different central tendency. If PerformanceRating proxy uses a 1–5 scale without rescaling, SalaryGrowth maximum inflates to 125 instead of 100, changing model interpretation.
4. **Retrospective signal:** PercentSalaryHike reflects a past decision; PerformanceRating may refer to a different evaluation period. The formula assumes temporal alignment between the two variables.

### 8.7 Known Interpretation Risks

- **Misalignment is not captured by magnitude alone:** A SalaryGrowth score of 48 could result from (12% hike × 4 rating) or (24% hike × 2 rating). The first represents reasonable alignment; the second represents potential inequity. The score magnitude alone does not diagnose misalignment.
- **Cultural context of performance ratings:** In some Saudi organizational cultures, rating inflation is common (supervisors avoid giving low ratings to preserve relationships). This systematically elevates PerformanceRating, compressing SalaryGrowth toward the upper range and reducing its predictive variance.
- **Overperformers receiving capped hikes:** In organizations with salary band caps, high performers may receive lower hike percentages than their performance warrants (because they are already at the band ceiling). This creates artificial ERI misalignment signals for high-tenure senior employees.

### 8.8 Governance Constraints

- SalaryGrowth must not be interpreted as evidence of salary discrimination without controlling for performance rating distribution, job level, and tenure.
- When PerformanceRating proxy uses a different scale than 1–4, scale conversion must be documented and a confidence penalty applied.
- SalaryGrowth must not be included in employee-facing dashboards where employees can compare their score against colleagues, as this reveals relative salary and performance information.

### 8.9 Confidence Downgrade Logic

| Condition | Penalty | Result |
|-----------|---------|--------|
| Both inputs DIRECT | 0.00 | 0.95 |
| PercentSalaryHike STRONG_PROXY | −0.08 | 0.87 |
| PerformanceRating STRONG_PROXY | −0.08 | 0.87 |
| Both STRONG_PROXY | −0.16 | 0.79 |
| PerformanceRating on different scale (undocumented) | Governance warning + −0.05 additional | 0.74 |

---

## 9. Cross-Construct Dependency Table

This table documents which source columns are shared across multiple constructs. Shared inputs create construct correlation and model multicollinearity. When constructs are used as simultaneous model features, shared-input pairs require VIF monitoring and may require one construct to be excluded or orthogonalized.

### 9.1 Shared Input Matrix

| Source Column | Construct 1 SatisfactionIndex | Construct 2 BurnoutRisk | Construct 3 EngagementScore | Construct 4 TenureRatio | Construct 5 IncomePerLevel | Construct 6 CareerProgression | Construct 7 SalaryGrowth |
|---------------|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|:-----:|
| JobSatisfaction | YES | — | YES | — | — | — | — |
| EnvironmentSatisfaction | YES | — | — | — | — | — | — |
| RelationshipSatisfaction | YES | — | — | — | — | — | — |
| WorkLifeBalance | YES | YES | — | — | — | — | — |
| OverTime | — | YES | — | — | — | — | — |
| JobInvolvement | — | — | YES | — | — | — | — |
| YearsAtCompany | — | — | — | YES | — | YES | — |
| TotalWorkingYears | — | — | — | YES | — | — | — |
| MonthlyIncome | — | — | — | — | YES | — | — |
| JobLevel | — | — | — | — | YES | YES | — |
| PercentSalaryHike | — | — | — | — | — | — | YES |
| PerformanceRating | — | — | — | — | — | — | YES |

### 9.2 Critical Shared-Input Dependency Pairs

**JobSatisfaction → SatisfactionIndex AND EngagementScore**  
This is the most consequential shared input. Both constructs include JobSatisfaction as a direct formula input. When both constructs are present as model features:
- Expected correlation: r ≈ 0.40–0.65 (varies by dataset)
- VIF monitoring threshold: VIF > 5 warrants investigation; VIF > 10 requires exclusion of one construct
- Mitigation option: Report SatisfactionIndex and EngagementScore as separate dimensions with explicit note of shared input; do not combine them into a single composite

**WorkLifeBalance → SatisfactionIndex AND BurnoutRisk**  
WorkLifeBalance appears in both formulas but with different roles:
- In SatisfactionIndex: it is an additive positive resource term (higher=better)
- In BurnoutRisk: it is an inverted multiplicative amplifier `(5−WLB)` (lower=worse outcome)
- Correlation direction: SatisfactionIndex increases with WLB; BurnoutRisk decreases with WLB. This negative correlation is theoretically expected and not a collinearity problem — the two constructs are measuring different constructs despite sharing one input.

**YearsAtCompany → TenureRatio AND CareerProgression**  
YearsAtCompany appears in both formulas as the time denominator:
- In TenureRatio: it is the numerator (company loyalty signal)
- In CareerProgression: it is the denominator (advancement velocity signal)
- These produce constructs that are partially negatively correlated: longer tenure increases TenureRatio but decreases CareerProgression velocity. This is theoretically coherent (loyalty vs. advancement rate are distinct constructs) but creates complex model interactions.

**JobLevel → IncomePerLevel AND CareerProgression**  
JobLevel feeds both constructs. As JobLevel increases:
- IncomePerLevel may increase or decrease depending on whether income grows proportionally
- CareerProgression decreases with tenure (advancement velocity slows for senior employees)
- This shared input creates moderate positive correlation between the two constructs in early-career employees and potentially negative correlation in senior employees.

---

## 10. Formula Integrity Matrix

Each formula is evaluated across five dimensions of scientific defensibility.

| Construct | Scale Integrity | Denominator Safety | Monotonic Validity | Ordinal vs. Continuous | Psychometric Defensibility |
|-----------|:--------------:|:-----------------:|:-----------------:|:----------------------:|:-------------------------:|
| SatisfactionIndex | PASS — all inputs on same 1–4 scale; mean is scale-consistent | PASS — no denominator | PASS — higher = more resources | CONCERN — Likert treated as interval; defensible under weak measurement | PARTIAL — single-item facets; no Cronbach's alpha |
| BurnoutRisk | CRITICAL — WLB scale direction must be confirmed; (5−WLB) inversion is scale-sensitive | PASS — no denominator | CONDITIONAL — monotonic only when gate is open (OT=1) | CONCERN — ordinal WLB used in continuous arithmetic | PARTIAL — binary OT oversimplifies demand intensity |
| EngagementScore | PASS — both inputs on same 1–4 scale | PASS — no denominator; minimum is 1×1=1 | PASS — both increase together under Kahn simultaneity | CONCERN — ordinal × ordinal; non-uniqueness of product values | PARTIAL — validated construct names; not a validated psychometric scale |
| TenureRatio | PASS — years-to-years ratio is dimensionally consistent | PASS — +1 prevents zero; paper-specified | CONDITIONAL — non-monotonic for senior employees (see Section 7.7) | PASS — both continuous positive integers | PASS — ratio of two continuous, same-unit variables |
| IncomePerLevel | WARNING — currency unit must be verified; SAR vs. USD vs. thousands | PASS — +1 prevents zero at JobLevel=0 | CONDITIONAL — non-linear level transitions not captured | CONCERN — ordinal JobLevel treated as divisor in ratio arithmetic | PARTIAL — Adams 1963 is theoretically grounded; formula is a simplification |
| CareerProgression | PASS — level/years ratio consistent | PASS — +1 prevents zero | FAIL for maximum-level employees — score decreases with tenure for JobLevel=5 | CONCERN — ordinal JobLevel as numerator | PARTIAL — theoretically grounded but floor/ceiling artifacts exist |
| SalaryGrowth | WARNING — PerformanceRating scale must be confirmed (1–4 vs. 1–5) | PASS — no denominator | CONDITIONAL — misalignment cases not distinguishable by magnitude | CONCERN — ordinal PerformanceRating multiplied by continuous hike percentage | PARTIAL — multiplicative structure is theoretically required (Siegrist 1996) |

### 10.1 Summary Flags

- **CRITICAL:** BurnoutRisk scale direction for WorkLifeBalance must be validated in every dataset before activation.
- **WARNING:** IncomePerLevel requires currency unit documentation; SalaryGrowth requires PerformanceRating scale documentation.
- **CONCERN (shared):** Five of seven constructs use ordinal Likert inputs in arithmetic operations. This is a known measurement-level violation that is standard practice in organizational psychology (Carifio & Perla 2008 defend this under weak measurement theory) but must be disclosed in all publications and model cards.
- **FAIL:** CareerProgression monotonicity fails for maximum job-level employees. Governance controls must prevent this construct from being used as the primary attrition signal for JobLevel=5 employees.

---

## 11. Known Violations in feature_factory.py

The legacy `feature_factory.py` module (`backend/core/feature_factory.py`) was written prior to the theory-grounded pipeline and contains systematic violations of the seven construct specifications. These violations are documented here for the governance record. The module remains in production for non-HR dataset types and for feature engineering layers that do not claim theoretical grounding (Layers A, D, E). The violations pertain specifically to Layer B (`_layer_b_hr_constructs`) and Layer C (`_layer_c_psychological`).

### 11.1 Violation 1 — Universal Pre-Normalization Destroys Formula Semantics

**Location:** `_layer_b_hr_constructs`, line 122: `df[name] = _clamp(_norm(result.fillna(result.median())))`

The `_add()` helper function wraps every construct computation with `_norm()` (min-max normalization to [0,1]) before storing the result. This is applied to **every** construct in Layer B, including SatisfactionIndex and EngagementScore.

**Scientific violation:**
- SatisfactionIndex is specified as `(JS + ES + RS + WLB) / 4`, producing a 1.0–4.0 output. Normalizing this to [0,1] collapses the Likert anchor points, making the output non-interpretable in terms of paper units.
- BurnoutRisk is specified with a multiplicative gate producing 0–4. Normalizing this eliminates the zero-preservation property of the gate: if the dataset's minimum BurnoutRisk is 0, normalization shifts all values from 0 upward, creating false non-zero BurnoutRisk values for non-overtime employees.
- EngagementScore normalization eliminates the 1–16 Kahn simultaneity range, making the product's theoretical meaning inaccessible.
- TenureRatio normalization destroys the [0,1] natural interpretation where the raw score itself is a proportion.

**Severity:** CRITICAL — all Layer B constructs that share names with the seven paper constructs are computing non-paper quantities after normalization.

### 11.2 Violation 2 — SatisfactionIndex Computed from Wrong Inputs

**Location:** `_layer_b_hr_constructs`, lines 154–156

```python
_add("SatisfactionIndex", lambda: (
    _norm(sat.fillna(0)) * 0.55 + _norm(eng.fillna(0)) * 0.45
) if sat is not None and eng is not None else None)
```

**Scientific violation:** The paper formula requires four inputs (JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance) with equal weights (1/4 each). The feature_factory implementation uses only two inputs (a generic `satisfaction` semantic category and a generic `engagement` semantic category) with differential weights (0.55 and 0.45). This is:
1. Wrong number of inputs (2 vs. 4)
2. Wrong theoretical constructs (engagement ≠ satisfaction facets)
3. Wrong aggregation weights (0.55/0.45 vs. 0.25/0.25/0.25/0.25)
4. Wrong formula type (weighted additive of normalized single-category proxies vs. unweighted mean of four distinct facets)

This means the value stored as `SatisfactionIndex` in the feature_factory output is not SatisfactionIndex as defined by the paper. It is an unlabeled composite that has been given a misleading name.

### 11.3 Violation 3 — BurnoutRiskComposite Invents a Non-Paper Construct

**Location:** `_layer_b_hr_constructs`, lines 147–151

```python
_add("BurnoutRiskComposite", lambda: (
    _norm(ot.fillna(0)) * 0.40
    + _norm(wl.fillna(0)) * 0.35
    + (1 - _norm(sat.fillna(sat.median()))) * 0.25
) if ot is not None and wl is not None and sat is not None else None)
```

**Scientific violation:** This construct does not exist in any paper in the theoretical framework. It is an invented composite that:
1. Uses additive aggregation where the paper requires multiplicative gating
2. Includes a workload term that is not in the BurnoutRisk paper formula
3. Includes an inverse satisfaction term that conflates JD-R demands with COR resource appraisal
4. Has no theoretical provenance
5. Is named `BurnoutRiskComposite` — a name that could be confused with the paper-defined `BurnoutRisk` construct by consumers of the feature output

The multiplicative gate (`OverTime_binary × (5−WLB)`) is not present. This means employees who are not working overtime can receive nonzero BurnoutRiskComposite values, which violates the JD-R health-impairment pathway's demand-activation requirement.

### 11.4 Violation 4 — RetentionRisk Is a Non-Paper Construct with Unvalidated Weights

**Location:** `_layer_b_hr_constructs`, lines 163–172

```python
if bur is not None:  parts.append(_norm(bur.fillna(0)));  weights.append(0.25)
if sat is not None:  parts.append(1-_norm(sat.fillna(0))); weights.append(0.20)
if prom is not None: parts.append(_norm(prom.fillna(0)));  weights.append(0.20)
if ot is not None:   parts.append(_norm(ot.fillna(0)));    weights.append(0.15)
if mgr is not None:  parts.append(1-_norm(mgr.fillna(0))); weights.append(0.20)
```

**Scientific violation:** `RetentionRisk` is not defined in COR, JD-R, FFM, or Mobley (1977). The weights (0.25, 0.20, 0.20, 0.15, 0.20) have no published theoretical basis. The variable inclusion logic is conditional on column availability, meaning the effective weights change depending on which columns exist in the dataset — a different `RetentionRisk` is computed for every dataset configuration. This violates reproducibility requirements for scientific constructs.

Additionally, `bur` in this context refers to a generic `burnout` semantic category, not the paper-defined `BurnoutRisk` construct. The construct is therefore a composite of composites with floating weights.

### 11.5 Violation 5 — PresenteeismSignal Uses Clinical Terminology Without Clinical Grounding

**Location:** `_layer_e_organizational`, lines 333–338

```python
df["PresenteeismSignal"] = _clamp(_norm(
    _norm(abs_) * 0.50 + _norm(ot) * 0.50
))
```

**Scientific violation:** Presenteeism is a clinically defined construct (Johns 2010) referring to being physically present at work while productively impaired due to health conditions. It requires self-reported measures of productivity loss while attending work. The feature_factory operationalization uses absence rate and overtime — which are antecedents or correlates of presenteeism, not measures of it. Naming this column `PresenteeismSignal` in any output that reaches HR professionals or executives will create systematic misinterpretation of a clinical construct.

Furthermore, high absence + high overtime can occur for reasons unrelated to presenteeism (e.g., project crunch periods followed by sick leave), making the composite both theoretically ungrounded and empirically noisy.

### 11.6 Violation 6 — CareerProgressionScore Is Not CareerProgression

**Location:** `_layer_b_hr_constructs`, lines 175–179

```python
_add("CareerProgressionScore", lambda: (
    _norm(perf.fillna(0)) * 0.40
    + (1 - _norm(prom.fillna(0))) * 0.35
    + _norm(trn.fillna(0)) * 0.25
) if perf is not None and prom is not None else None)
```

**Scientific violation:** The paper-defined `CareerProgression = JobLevel / (YearsAtCompany + 1)`. The feature_factory version uses performance rating, promotion recency (inverted), and training hours — none of which appear in the paper formula. This is a different construct entirely, given the same approximate name. If both Layer B's `CareerProgressionScore` and Phase 2's `CareerProgression` appear in a feature set, the naming confusion will cause model interpretation errors.

### 11.7 Summary of feature_factory.py Violations

| Violation | Layer | Severity | Type |
|-----------|-------|----------|------|
| Universal `_norm()` applied before all construct storage | B, C | CRITICAL | Destroys formula semantics for all 7 constructs |
| SatisfactionIndex uses wrong inputs and wrong weights | B | HIGH | Name collision with paper construct |
| BurnoutRiskComposite uses additive formula without gate | B | HIGH | Non-paper construct with misleading name |
| RetentionRisk has no theoretical provenance or stable weights | B | MODERATE | Invented construct |
| PresenteeismSignal misappropriates clinical terminology | E | MODERATE | Clinical misrepresentation |
| CareerProgressionScore ≠ paper CareerProgression | B | HIGH | Name collision with paper construct |
| EngagementScore computed from single normalized column | B | HIGH | Missing Kahn simultaneity requirement |

**Remediation status:** Feature_factory.py Layer B constructs sharing names with the 7 paper constructs must be either (a) renamed to clearly non-paper identifiers (e.g., `BurnoutProxy_Additive`, `SatisfactionProxy_TwoInput`) or (b) replaced by output from `theory_grounded_construct_engine.py` for datasets where Phase 2 activation is available. The renaming is required for governance audit compliance.

---

## 12. Governance Summary and Recommendations

### 12.1 Constructs Ready for Production Use

The following constructs, when activated by `theory_grounded_construct_engine.py` with DIRECT evidence quality, meet the scientific standards for use in attrition prediction models and HR analytics dashboards:

| Construct | Condition for Production Use | Max Confidence |
|-----------|------------------------------|----------------|
| SatisfactionIndex | All 4 inputs at DIRECT evidence | 0.95 |
| BurnoutRisk | Both inputs at DIRECT, OverTime native binary, WLB 1–4 confirmed | 0.95 |
| EngagementScore | Both inputs at DIRECT evidence | 0.95 |
| TenureRatio | Both inputs at DIRECT evidence, YAC ≤ TotalWorkingYears verified | 0.95 |
| IncomePerLevel | Both inputs at DIRECT, currency unit documented | 0.95 |
| CareerProgression | Both inputs at DIRECT, grade direction confirmed ascending | 0.95 |
| SalaryGrowth | Both inputs at DIRECT, PerformanceRating scale confirmed as 1–4 | 0.95 |

### 12.2 Mandatory Disclosures for All Constructs

Every construct computed by the platform must carry the following disclosures in model cards and HR analytics reports:

1. **Activation mode:** DIRECT_PAPER_REPLICATION or THEORY_COMPATIBLE_PROXY
2. **Confidence score:** Numerical value from 0.30 to 0.95
3. **Proxy penalties applied:** List each penalty and its cause
4. **Measurement level limitation:** "Five of seven constructs apply arithmetic operations to ordinal Likert items, following standard practice in organizational psychology under weak measurement assumptions (Carifio & Perla 2008)."
5. **Shared input notice:** When SatisfactionIndex and EngagementScore are both active, disclose shared JobSatisfaction input and report VIF.

### 12.3 Blocking Conditions — Constructs Must Not Activate Under These Conditions

- Any required input has evidence strength WEAK_PROXY or lower
- Any required input has semantic confidence < 0.70
- Any required input has scale confidence < 0.70
- Any required input carries a leakage flag (TARGET_ADJACENT)
- BurnoutRisk: OverTime cannot be safely binarized
- BurnoutRisk: WorkLifeBalance scale cannot be mapped to 1–4
- TenureRatio: YearsAtCompany > TotalWorkingYears in any row (data integrity failure — flag rows, do not impute)
- CareerProgression: JobLevel scale direction is not confirmed ascending

### 12.4 Immediate Remediation Actions Required

1. **Rename or retire feature_factory.py Layer B constructs** that share names with the 7 paper constructs. The naming collision between `SatisfactionIndex` (feature_factory) and `SatisfactionIndex` (theory_grounded_construct_engine) is a governance audit failure.
2. **Remove `_norm()` wrapping from all paper-named constructs** in feature_factory.py or route HR attrition datasets exclusively through theory_grounded_construct_engine.py.
3. **Rename `PresenteeismSignal`** to a non-clinical name such as `AbsenceOvertimeOverlap` or `WorkingPatternStrain`.
4. **Add VIF monitoring** to the model pipeline for all datasets where both SatisfactionIndex and EngagementScore are activated (shared JobSatisfaction input).
5. **Document currency units** for all Saudi HR datasets in Phase 1 metadata to enable IncomePerLevel governance compliance.
6. **Add grade direction validation** for JobLevel columns from Saudi HR systems where descending-coded hierarchies may be present.

### 12.5 Theoretical Citation Requirements

All models and reports using these constructs must cite the following foundational works:

- Hobfoll, S. E. (1989). Conservation of resources: A new attempt at conceptualizing stress. *American Psychologist, 44*(3), 513–524.
- Bakker, A. B., & Demerouti, E. (2017). Job demands-resources theory: Taking stock and looking forward. *Journal of Occupational Health Psychology, 22*(3), 273–285.
- Costa, P. T., & McCrae, R. R. (1992). *Revised NEO Personality Inventory (NEO PI-R) and NEO Five-Factor Inventory (NEO-FFI) professional manual.* Psychological Assessment Resources.
- Mobley, W. H. (1977). Intermediate linkages in the relationship between job satisfaction and employee turnover. *Journal of Applied Psychology, 62*(2), 237–240.
- Adams, J. S. (1963). Towards an understanding of inequity. *Journal of Abnormal and Social Psychology, 67*(5), 422–436.
- Siegrist, J. (1996). Adverse health effects of high-effort/low-reward conditions. *Journal of Occupational Health Psychology, 1*(1), 27–41.
- Kahn, W. A. (1990). Psychological conditions of personal engagement and disengagement at work. *Academy of Management Journal, 33*(4), 692–724.

---

*End of Theory Construct Validity Audit — Adaptive Workforce AI Platform*  
*Document version: 1.0 — 2026-05-20*  
*Audit scope: 7 paper-defined constructs, Phase 1 + Phase 2 pipeline, feature_factory.py violation registry*
