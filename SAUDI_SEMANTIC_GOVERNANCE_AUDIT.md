# Saudi HR Semantic Governance Audit
## Attrition Prediction Platform — Column Mapping Governance Document

**Document Type:** Semantic Governance Audit  
**Platform:** Adaptive Workforce AI — Attrition Prediction Pipeline  
**Audience:** Saudi HR Analytics Specialist, Organizational Psychology Researcher  
**Date:** 2026-05-20  
**Scope:** Arabic and English Saudi HR column name mapping to organizational psychology constructs

---

## Overview

This audit governs the semantic mapping of Saudi HR dataset column names — in both English and Arabic — to the organizational psychology constructs used in the attrition prediction platform. Incorrect mappings introduce construct validity failures, model contamination, or circular leakage into the prediction pipeline. Each mapping is assigned an evidence tier and confidence score derived from the platform's 4-stage resolution pipeline.

### Pipeline Evidence Tiers

| Stage | Method | Evidence Level | Confidence |
|-------|--------|---------------|------------|
| Stage 1 | IBM HR exact match | DIRECT | 0.95 |
| Stage 2 | English synonym exact match | STRONG_PROXY | 0.85 |
| Stage 3 | Arabic exact match | STRONG_PROXY | 0.85 |
| Stage 4 | Keyword substring match | WEAK_PROXY | 0.38–0.65 |

A mapping that does not resolve through Stages 1–3 must be treated with elevated scrutiny. WEAK_PROXY mappings (Stage 4) are never sufficient as sole evidence for construct assignment in model-critical features.

### Construct Categories

| Category | Required Constructs |
|----------|-------------------|
| SATISFACTION_HYGIENE | JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance |
| JOB_DEMANDS | OverTime |
| JOB_RESOURCES | WorkLifeBalance, ManagerialSupport, TrainingHours |
| ENGAGEMENT_INVOLVEMENT | JobInvolvement, EmployeeEngagement |
| EQUITY_FAIRNESS | PromotionFairness, SalaryFairness |
| COMMITMENT_ATTACHMENT | OrganizationalCommitment |
| RETENTION_WITHDRAWAL | IntentToLeave (moderated), ExternalJobOpportunities (moderated) |
| STRUCTURAL_HR_BASELINE | YearsAtCompany, TotalWorkingYears, MonthlyIncome, JobLevel, PercentSalaryHike, PerformanceRating, Age, Department, Absence |

---

## Section 1: Valid Saudi-to-IBM Mappings

The following mappings have been verified as semantically valid through Stage 2 (English synonym) or Stage 3 (Arabic exact match) of the resolution pipeline. Each entry documents the English column, its Arabic equivalent, the target IBM HR construct, evidence level, confidence score, and semantic justification.

---

### 1.1 monthly_salary → MonthlyIncome

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `monthly_salary` |
| Arabic Equivalent | `الراتب الشهري` |
| IBM Construct | `MonthlyIncome` |
| Construct Category | STRUCTURAL_HR_BASELINE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** "Monthly salary" is the standard Saudi private-sector payroll term for base monthly compensation, directly equivalent to the IBM HR `MonthlyIncome` field. The Arabic `الراتب الشهري` (al-ratib al-shahri) is the formal Modern Standard Arabic HR term used in Saudi Labor Law documentation and GOSI filings. The mapping is semantically stable across public and private sector Saudi HR systems. `MonthlyIncome` in the IBM construct serves as an objective economic indicator in the Siegrist Effort-Reward Imbalance model and is classified as STRUCTURAL_HR_BASELINE — not a subjective survey item. Analysts must verify whether the field represents gross or net salary, as Saudi payroll often records both separately.

---

### 1.2 service_years → YearsAtCompany

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `service_years` |
| Arabic Equivalent | `مدة الخدمة` |
| IBM Construct | `YearsAtCompany` |
| Construct Category | STRUCTURAL_HR_BASELINE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `مدة الخدمة` (muddat al-khidma, "duration of service") is the canonical Saudi government and private sector HR term for organizational tenure. It maps directly to `YearsAtCompany` when measured in years. The construct is a critical baseline variable in tenure-based attrition models and contributes to the embeddedness component of Mitchell's job embeddedness theory. Analysts must confirm the unit of measurement — Saudi HR systems, particularly those inherited from legacy government ERP platforms, occasionally record `مدة الخدمة` in Hijri calendar months rather than Gregorian years. A conversion factor of approximately 0.9709 applies when converting Hijri years to Gregorian years.

---

### 1.3 job_grade → JobLevel

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `job_grade` |
| Arabic Equivalent | `المستوى الوظيفي` |
| IBM Construct | `JobLevel` |
| Construct Category | STRUCTURAL_HR_BASELINE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `job_grade` and `المستوى الوظيفي` (al-mustawa al-wazifi, "job level/grade") refer to hierarchical position within the organizational structure. This aligns with `JobLevel` (1–5 ordinal scale in IBM HR) which operationalizes Hackman and Oldham's task significance and autonomy dimensions as a function of organizational rank. The Saudi Civil Service Commission uses a 15-grade system (الدرجات الوظيفية), while private sector entities frequently use a compressed 5–8 grade system. The analyst must normalize the source scale to the IBM 1–5 ordinal range before model ingestion to avoid cardinality artifacts.

---

### 1.4 performance_score → PerformanceRating

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `performance_score` |
| Arabic Equivalent | `تقييم الأداء` |
| IBM Construct | `PerformanceRating` |
| Construct Category | STRUCTURAL_HR_BASELINE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `تقييم الأداء` (taqyim al-ada', "performance appraisal/evaluation") is the standard Saudi HR term for annual or semi-annual performance review scores. It maps to IBM `PerformanceRating`, which in the original dataset uses a 3–4 scale (Excellent/Outstanding). The semantic match is strong under the assumption that the source score reflects supervisor-rated performance rather than a 360-degree or peer-rated composite. See Section 6.4 for cultural interpretation caveats regarding wasta influence on performance ratings in certain Saudi organizational contexts.

---

### 1.5 employee_satisfaction → JobSatisfaction

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `employee_satisfaction` |
| Arabic Equivalent | `الرضا الوظيفي` |
| IBM Construct | `JobSatisfaction` |
| Construct Category | SATISFACTION_HYGIENE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `الرضا الوظيفي` (al-rida al-wazifi, "job satisfaction") is the textbook Arabic translation of Locke's job satisfaction construct and is used in Saudi academic HR literature as well as commercial employee survey instruments. The mapping to IBM `JobSatisfaction` is semantically valid under the assumption that the source column represents a Likert-type self-reported job satisfaction measure. Analysts must be aware that survey administration context in Saudi organizations can introduce social desirability suppression — see Section 6.2 for detailed caveats.

---

### 1.6 work_environment → EnvironmentSatisfaction

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `work_environment` |
| Arabic Equivalent | `الرضا عن بيئة العمل` |
| IBM Construct | `EnvironmentSatisfaction` |
| Construct Category | SATISFACTION_HYGIENE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `الرضا عن بيئة العمل` (al-rida 'an bi'at al-'amal, "satisfaction with the work environment") explicitly operationalizes the physical and social work environment dimension of Herzberg's hygiene factors. This maps cleanly to IBM `EnvironmentSatisfaction`. The Arabic phrase is notably more specific than the English `work_environment`, which could refer to the physical environment score or a composite index — the analyst must confirm the source survey item wording. If `work_environment` is a composite of physical, social, and safety dimensions, disaggregation may be required before mapping.

---

### 1.7 work_life_score → WorkLifeBalance

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `work_life_score` |
| Arabic Equivalent | `التوازن بين العمل والحياة` |
| IBM Construct | `WorkLifeBalance` |
| Construct Category | SATISFACTION_HYGIENE / JOB_RESOURCES |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `التوازن بين العمل والحياة` (al-tawazun bayn al-'amal wal-hayah, "work-life balance") is a direct semantic translation of the work-life balance construct and maps to IBM `WorkLifeBalance`. This construct appears in both SATISFACTION_HYGIENE and JOB_RESOURCES categories in the platform's framework, reflecting its dual role as a hygiene factor (Herzberg) and a personal resource in the JD-R model (Bakker and Demerouti). Scale direction must be verified — see Section 2.2 for conditional validity discussion.

---

### 1.8 overtime_hours → OverTime

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `overtime_hours` |
| Arabic Equivalent | `ساعات إضافية` |
| IBM Construct | `OverTime` |
| Construct Category | JOB_DEMANDS |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `ساعات إضافية` (sa'at idafiyya, "additional/overtime hours") refers to logged hours beyond the standard workday and maps semantically to IBM `OverTime`. However, a critical structural mismatch exists: IBM `OverTime` is a binary categorical variable (Yes/No), whereas `overtime_hours` is a continuous count variable. This mapping is semantically valid but requires mandatory binarization before model ingestion (e.g., threshold at >0 hours = Yes, or at a domain-appropriate cut-off such as >10 hours/month). The continuous form cannot be substituted directly as the binary gate in JOB_DEMANDS. See Section 3.1 for the related blocked mapping of `stress_level`.

---

### 1.9 salary_increase → PercentSalaryHike

| Attribute | Value |
|-----------|-------|
| Saudi English Column | `salary_increase` |
| Arabic Equivalent | `نسبة الزيادة` |
| IBM Construct | `PercentSalaryHike` |
| Construct Category | STRUCTURAL_HR_BASELINE |
| Evidence Level (EN) | STRONG_PROXY |
| Confidence (EN) | 0.85 |
| Evidence Level (AR) | STRONG_PROXY |
| Confidence (AR) | 0.85 |

**Semantic Justification:** `نسبة الزيادة` (nisbat al-ziyadah, "increase percentage/ratio") refers to the annualized percentage change in base salary, directly equivalent to IBM `PercentSalaryHike`. This is a Siegrist Effort-Reward Imbalance indicator representing the reward arm of the ERI ratio. The mapping is semantically clean provided the source column records the hike as a percentage (e.g., 12.5) rather than an absolute monetary value. Analysts must confirm scale type before ingestion. Critically, this construct is distinct from equity perception — see the blocked mapping in Section 3.5 for the `promotion_fairness → PercentSalaryHike` violation.

---

## Section 2: Conditionally Valid Mappings

The following mappings are semantically plausible but require explicit human confirmation before activation in the pipeline. Each entry describes the condition that must be verified and the risk of proceeding without verification.

---

### 2.1 engagement_level → JobInvolvement

**Proposed Mapping:** `engagement_level` → `JobInvolvement` (ENGAGEMENT_INVOLVEMENT)  
**Conditional Status:** Requires construct disambiguation

**Condition for Validity:** This mapping is conditionally valid only if `engagement_level` operationalizes behavioral job involvement (Kanungo, 1982) — the degree to which an employee's self-image is defined by their job role. It is NOT valid if `engagement_level` represents an engagement composite score combining vigor, dedication, and absorption dimensions (Schaufeli and Bakker, 2003), which would more accurately map to `EmployeeEngagement`.

**Risk of Incorrect Assignment:** Treating an engagement composite as `JobInvolvement` understates the construct's motivational complexity and may confound the ENGAGEMENT_INVOLVEMENT category. Engagement composites typically have higher predictive validity for performance outcomes, while job involvement is more strongly associated with job-specific turnover intentions.

**Required Action:** Obtain survey instrument documentation or data dictionary confirming which psychological construct the source measure operationalizes.

---

### 2.2 work_life_score → WorkLifeBalance (Scale Direction)

**Proposed Mapping:** `work_life_score` → `WorkLifeBalance` (SATISFACTION_HYGIENE / JOB_RESOURCES)  
**Conditional Status:** Requires scale direction verification

**Condition for Validity:** IBM `WorkLifeBalance` uses a 1–4 scale where 1 = Bad and 4 = Best. If the source `work_life_score` uses an inverted scale (1 = Best, 4 = Bad), all downstream model coefficients will be sign-reversed, producing a model that predicts lower attrition risk for employees with the worst work-life balance.

**Risk of Incorrect Assignment:** Scale inversion is a silent validity failure — it does not produce a pipeline error, only a semantically inverted model. This type of error is among the most difficult to detect post-deployment.

**Required Action:** Compare the mean `work_life_score` for voluntarily separated employees vs. active employees. If separated employees show higher mean scores than retained employees, scale inversion is indicated and reversal transformation must be applied before ingestion.

---

### 2.3 promotion_satisfaction → PromotionFairness

**Proposed Mapping:** `promotion_satisfaction` → `PromotionFairness` (EQUITY_FAIRNESS)  
**Conditional Status:** Valid for equity construct only — NOT for PercentSalaryHike

**Condition for Validity:** This mapping is valid if and only if `promotion_satisfaction` is interpreted under the EQUITY_FAIRNESS category, operationalizing Adams' equity theory perception of whether promotions are allocated fairly. It must not be cross-mapped to `PercentSalaryHike` (Siegrist ERI reward indicator), which is an objective salary data field in STRUCTURAL_HR_BASELINE.

**Risk of Incorrect Assignment:** Using a subjective promotion satisfaction perception score as a proxy for the objective `PercentSalaryHike` conflates two theoretically distinct constructs from different theoretical frameworks (Adams equity theory vs. Siegrist ERI). This produces a category error that invalidates both the EQUITY_FAIRNESS and STRUCTURAL_HR_BASELINE construct measurements simultaneously.

**Required Action:** Confirm the analyst's intended construct assignment and document whether the field will be used as a STRUCTURAL_HR_BASELINE feature or an EQUITY_FAIRNESS perceptual indicator, never both.

---

### 2.4 total_experience → TotalWorkingYears

**Proposed Mapping:** `total_experience` → `TotalWorkingYears` (STRUCTURAL_HR_BASELINE)  
**Conditional Status:** Requires unit verification

**Condition for Validity:** IBM `TotalWorkingYears` is recorded in years (integer). This mapping is valid only if `total_experience` is also measured in years. Saudi HR systems — particularly legacy SAP implementations used in government-linked enterprises — occasionally record experience in months or as a formatted string (e.g., "3Y 4M").

**Risk of Incorrect Assignment:** If the source is in months and mapped directly, a 36-month career history is treated as a 36-year career, producing extreme outliers that distort experience-based tenure segments in the model.

**Required Action:** Verify the unit by examining the distribution — median values exceeding 40 in what is labeled as years indicates a months-based encoding. Apply integer division by 12 if months encoding is confirmed.

---

### 2.5 training_hours / ساعات التدريب → TrainingHours

**Proposed Mapping:** `training_hours` / `ساعات التدريب` → `TrainingHours` (JOB_RESOURCES)  
**Conditional Status:** Valid as JD-R resource indicator only

**Condition for Validity:** `ساعات التدريب` (sa'at al-tadrib, "training hours") is a valid JOB_RESOURCES indicator under the Job Demands-Resources model, representing organizational investment in employee development. The mapping is valid for this purpose.

**Restriction:** This field must NOT be used as a formula input for any derived construct calculation (e.g., computing a skill-development index or ERI effort score). Training hours as a raw count does not carry the psychometric properties required for formula-based composite construction without validated weighting coefficients.

**Required Action:** Confirm the field is used only as a standalone JOB_RESOURCES feature and is excluded from any composite score formulas in the feature engineering pipeline.

---

## Section 3: BLOCKED Mappings

The following mappings are permanently blocked from the pipeline. Each represents a category error, theoretical violation, or data contamination risk that cannot be resolved by human confirmation. Blocking is non-negotiable.

---

### 3.1 stress_level → OverTime: BLOCKED

**Reason:** Psychological stress is a subjective self-reported psychophysiological state (operationalized in instruments such as the Perceived Stress Scale, Cohen et al., 1983). `OverTime` in the IBM HR construct is a binary behavioral indicator of whether the employee works beyond standard hours. These are theoretically and operationally distinct constructs from different levels of analysis (subjective phenomenological vs. objective behavioral).

**Critical Structural Issue:** `OverTime` functions as a binary gate in the JOB_DEMANDS category. Substituting a continuous psychological stress score for this binary gate — even after binarization — introduces construct substitution: the model would be predicting attrition from perceived stress rather than from measurable overtime behavior. These constructs have different antecedents, different distributions, and different policy intervention implications.

**Permissible Use:** `stress_level` may be considered for inclusion as a standalone feature under a separate PSYCHOLOGICAL_DEMANDS or WELLBEING category if theoretically justified, but it cannot substitute for `OverTime`.

---

### 3.2 absence_days / الغياب → BurnoutRisk: BLOCKED

**Reason:** `الغياب` (al-ghiyab, "absence") and `absence_days` are administrative attendance records classifiable under STRUCTURAL_HR_BASELINE as `Absence`. Mapping absence records to a `BurnoutRisk` construct constitutes a theoretical category error: absence behavior is a withdrawal behavior outcome variable in Hanisch and Hulin's (1991) withdrawal cognitions model, not a burnout measurement. Burnout is a psychometric construct requiring validated self-report instruments (e.g., Maslach Burnout Inventory).

**Additional Risk:** Treating `Absence` as a demand-side burnout indicator would double-count the withdrawal signal — `Absence` already contributes to the STRUCTURAL_HR_BASELINE feature set that predicts attrition. Reclassifying it as a psychological construct creates multicollinearity between the baseline and the demand categories.

**Permissible Use:** `absence_days` / `الغياب` must remain in STRUCTURAL_HR_BASELINE as `Absence`.

---

### 3.3 resignation_intent / نية ترك العمل → Any Construct: BLOCKED — TARGET_ADJACENT_LEAKAGE

**Reason:** `نية ترك العمل` (niyyat tark al-'amal, "intention to leave work") and `resignation_intent` are direct behavioral intention measures that are target-adjacent to the attrition outcome variable. Including any such measure as a predictor feature in an attrition model constitutes temporal leakage: intent to leave is a proximal antecedent of actual resignation in Ajzen's Theory of Planned Behavior and in Mobley's (1977) turnover process model. The predictor would effectively encode the outcome.

**Nuance:** The RETENTION_WITHDRAWAL category does include `IntentToLeave` and `ExternalJobOpportunities` as moderated constructs. However, these are retained only under specific moderation conditions with explicit theoretical guards. A raw `resignation_intent` column from an HR dataset carries no such moderation structure and must be blocked from direct feature ingestion.

**Required Action:** If `resignation_intent` data exists, it must be isolated from the feature matrix and evaluated for use only as a validation signal against model predictions, never as a predictor.

---

### 3.4 exit_risk / خطر الاستقالة → Any Construct: BLOCKED — Derived Score Circular Leakage

**Reason:** `خطر الاستقالة` (khatar al-istiqalah, "resignation risk") and `exit_risk` are derived risk scores — typically produced by a previous predictive model or statistical scoring engine. Using a derived attrition risk score as a feature in a new attrition model creates circular leakage: the new model trains on the predictions of a prior model, absorbing that model's biases, errors, and training data artifacts.

**Severity:** This is a data contamination error that invalidates model evaluation metrics — the new model will appear to perform well because it has learned to reproduce the prior model's output rather than to learn genuine relationships between HR constructs and attrition.

---

### 3.5 promotion_fairness / عدالة الترقية → PercentSalaryHike: BLOCKED

**Reason:** `عدالة الترقية` (adalah al-tarqiya, "promotion justice/fairness") and `promotion_fairness` are Adams equity theory perceptual constructs measuring the subjective fairness of promotion decisions. `PercentSalaryHike` is an objective, administratively recorded salary increment percentage from the Siegrist Effort-Reward Imbalance framework. These constructs belong to different theoretical traditions, different data types (subjective Likert vs. objective administrative), and different measurement levels.

**Specific Harm:** Substituting a fairness perception for an objective salary metric in the ERI reward calculation corrupts the Effort-Reward Imbalance ratio. The ERI ratio requires objective reward data; injecting a perception score inflates the reward term for employees who are satisfied with unfair promotions, paradoxically reducing their predicted ERI imbalance.

**Permissible Mapping:** `promotion_fairness` / `عدالة الترقية` is valid exclusively for the EQUITY_FAIRNESS → `PromotionFairness` construct.

---

### 3.6 managerial_score → JobLevel: BLOCKED

**Reason:** `managerial_score` measures managerial competence, leadership quality, or 360-degree managerial effectiveness — a behavioral and relational construct. `JobLevel` is an organizational rank indicator reflecting hierarchical position in the authority structure. Managerial quality and organizational rank are empirically uncorrelated constructs; highly ranked individuals may score poorly on managerial effectiveness, and highly effective managers may hold mid-level ranks.

**Additional Risk:** Substituting `managerial_score` for `JobLevel` in STRUCTURAL_HR_BASELINE would corrupt the rank-based compensation and career progression features that underpin the attrition model's hierarchical embeddedness signals.

---

### 3.7 attrition_risk / خطر التسرب → Any Construct: BLOCKED — CRITICAL Leakage

**Reason:** `خطر التسرب` (khatar al-tasarrub, "attrition/turnover risk") and `attrition_risk` are direct operationalizations of the prediction target. Including the attrition risk score as any form of predictor feature — regardless of the construct it is mapped to — constitutes the most severe form of target leakage possible. Model performance metrics become meaningless, the model cannot generalize to future employees, and any deployed predictions are circularly self-reinforcing.

**Severity Level:** CRITICAL. Pipeline must enforce hard rejection of any column matching attrition risk naming patterns, in both English and Arabic, regardless of proposed construct assignment.

---

### 3.8 churn_score → Any Construct: BLOCKED — CRITICAL Leakage

**Reason:** `churn_score` is an alternative label for a derived attrition prediction score, equivalent in structure and risk to `attrition_risk`. The use of "churn" (a term adopted from customer analytics into HR analytics) does not change the fundamental nature of the variable as a model output being recycled as a model input. CRITICAL leakage classification applies.

---

### 3.9 loyalty_score → MonthlyIncome: BLOCKED

**Reason:** `loyalty_score` measures affective or behavioral loyalty — typically a composite of perceived organizational commitment, identification, and intention to remain. `MonthlyIncome` is an objective administrative payroll record. These constructs are not semantically related. The proposed mapping likely arises from a heuristic assumption that loyal employees earn higher salaries; this is an empirically unstable correlation that varies by organization and sector, and cannot justify construct substitution.

**Permissible Use:** `loyalty_score` may be evaluated for mapping to `OrganizationalCommitment` (COMMITMENT_ATTACHMENT) under construct validation review, but must not approach any STRUCTURAL_HR_BASELINE field.

---

## Section 4: Arabic Synonym Risks

Arabic HR column names introduce a set of linguistic and computational risks that are absent from English-only pipelines. These risks operate at the character encoding, morphological, dialectal, and semantic levels.

---

### 4.1 Diacritics Stripping

The platform's Stage 3 Arabic matching normalizes column names by stripping diacritical marks (harakat: fatha, kasra, damma, shadda, sukun, and their variants). This means that `رضا الموظف` and `رَضا الموظَّف` (the diacritically marked version) are treated as equivalent after normalization.

**Risk:** While this normalization is generally correct for HR column matching, it creates ambiguity in cases where the undiacritized form is a homograph — the same character sequence representing different words depending on vocalization. For example, `مُدير` (mudir, manager) and `مَدار` (madar, orbit/scope) share overlapping undiacritized sequences in some romanization contexts. Analysts must validate that the normalization does not collapse semantically distinct terms.

---

### 4.2 Homonyms and Polysemy

`الراتب` (al-ratib) is the most significant HR homonym in the platform's mapping vocabulary. It can mean:

- **Salary** (in employment contexts): الراتب الشهري = monthly salary
- **Stipend or allowance** (in scholarship or governmental grant contexts)
- **Repetitive/routine** (adjectival use, from the root ر-ت-ب)

In Saudi HR exports from systems that include both base salary and living allowance (بدل السكن, badal al-sakan) and transportation allowance (بدل المواصلات, badal al-muwasalat), `الراتب` may refer only to base salary or to the total compensation package depending on organizational convention. This directly affects the semantic validity of the `monthly_salary → MonthlyIncome` mapping.

**Required Action:** Confirm with the data owner whether `الراتب` in the source system refers to base salary, gross salary, or total compensation before accepting the mapping.

---

### 4.3 Dialectal and Register Variation

The platform's Arabic matching is calibrated for Modern Standard Arabic (MSA, الفصحى) HR vocabulary. Saudi organizational HR practice spans three registers:

1. **MSA formal**: Used in official documentation, labor contracts, Ministry of Human Resources correspondence.
2. **Saudi Arabic dialect (Najdi/Hijazi)**: May appear in informal HRIS column labels or custom-built internal systems.
3. **Gulf Arabic variants**: Used in multinational companies operating across GCC member states.

Dialectal variants that may not resolve through Stage 3 include:
- `وظيفة` (wazifa, MSA for "job/position") vs. informal uses of `شغل` (shughl, "work/employment")
- `إجازة` (ijaza, MSA for "leave/vacation") vs. `عطلة` (utla, colloquial for "holiday")
- `موظف` (muwazzaf, MSA for "employee") vs. `عامل` (amil, "worker" — more common in blue-collar contexts)

**Risk:** Dialectal column names will fail Stage 3 matching and fall through to Stage 4 WEAK_PROXY keyword matching, producing confidence scores of 0.38–0.65 that may be below the platform's acceptance threshold. These cases require manual mapping review.

---

### 4.4 Mixed Arabic-English Column Names

Saudi HRIS exports from SAP SuccessFactors, Oracle HCM, and Workday frequently produce bilingual column headers that combine English prefixes or suffixes with Arabic content. Examples include:

- `HR_الأداء` (HR_performance)
- `KPI_الرضا` (KPI_satisfaction)
- `EMP_مدة_الخدمة` (EMP_service_duration)

The platform's pipeline handles these as mixed-language columns: the English component is attempted first (Stage 1–2), then the Arabic component is extracted and matched (Stage 3). However, if the English prefix is an organizational code (e.g., `HR_`, `EMP_`, `KPI_`) rather than a semantic term, Stage 1–2 will fail, and the Arabic substring will be matched in Stage 3 with standard STRONG_PROXY confidence.

**Risk:** The English prefix may carry semantic meaning that modifies the Arabic term's interpretation. `KPI_الرضا` may refer to a KPI-normalized satisfaction score rather than a raw survey response, which would require different preprocessing. The pipeline does not currently parse such semantic modifiers from mixed-script prefixes.

---

### 4.5 False Friends: مشاركة vs. اندماج

`مشاركة` (musharaka) and `اندماج` (indimaj) are both plausible Arabic translations for the English term "engagement" but operationalize entirely different psychological constructs:

- `مشاركة` derives from the root ش-ر-ك (sharing, participation, partnership). In HR contexts it typically refers to employee participation in decision-making processes, organizational events, or collaborative activities. This is closer to the participation dimension of organizational citizenship behavior.
- `اندماج` derives from the root د-م-ج (merging, integration, fusion). In HR and organizational psychology contexts it operationalizes psychological engagement — the state of vigor, dedication, and absorption described by Schaufeli and Bakker's UWES instrument.

**Critical Risk:** A column labeled `مشاركة_الموظف` (employee participation) would falsely match to `EmployeeEngagement` through keyword substring matching in Stage 4. The resulting WEAK_PROXY mapping carries confidence 0.38–0.65, but the semantic error is categorical — participation and engagement are not interchangeable in attrition modeling. Participation measures are more strongly linked to voice behavior and OCB, while engagement measures are more strongly linked to burnout prevention and discretionary effort.

**Required Action:** Any Arabic column containing `مشاركة` must be reviewed by an organizational psychology specialist to determine whether it operationalizes participation or engagement before any construct assignment is accepted.

---

## Section 5: Saudi HR Naming Drift Patterns

Saudi HR datasets exhibit systematic naming drift patterns that arise from the intersection of organizational evolution, Vision 2030 reform vocabulary, and multilingual HRIS platform diversity.

---

### 5.1 Government Sector Job Classification Terminology

Saudi government entities governed by the Civil Service Commission use `مسمى وظيفي` (musamman wazifi, "job title/designation") as the primary job classification field rather than `job_grade` or `المستوى الوظيفي`. The `مسمى وظيفي` field is typically a text string (e.g., "محلل مالي أول" — Senior Financial Analyst) rather than an ordinal grade.

**Impact on Mapping:** `مسمى وظيفي` cannot be directly mapped to `JobLevel` (ordinal 1–5) without a translation lookup table from job title to grade. Government datasets frequently lack a numeric grade column entirely. In such cases, `JobLevel` cannot be constructed without external reference data from the Civil Service Commission's job classification tables.

---

### 5.2 Vision 2030 HR Vocabulary Evolution

Since 2016, Saudi Vision 2030 has introduced a new organizational development lexicon into Saudi HR practice. Terms that have emerged and may appear in modern Saudi HRIS exports include:

- `التحول المهني` (professional transformation/career transition)
- `مؤشرات الإنتاجية` (productivity indicators — may be used as a proxy for performance metrics)
- `الكفاءة الوظيفية` (job competency — distinct from performance rating)
- `الاستدامة الوظيفية` (job sustainability — an emerging retention-adjacent concept)

These terms do not appear in the platform's Stage 1–3 matching dictionaries and will fall through to Stage 4 WEAK_PROXY matching at reduced confidence, or may fail to match entirely.

**Required Action:** The Arabic matching dictionary should be periodically updated with Vision 2030 vocabulary as it standardizes in Saudi HR practice. Terms should be reviewed against existing construct definitions before addition.

---

### 5.3 Bilingual HRIS Export Patterns

SAP S/4HANA, Oracle Fusion HCM, and Workday — the three dominant HRIS platforms in Saudi large enterprises and Vision 2030 giga-projects — produce multilingual exports with characteristic structural patterns:

- **SAP**: Produces German-English-Arabic trilingual field labels in some configurations; the Arabic label may appear in parentheses after the English technical field name.
- **Oracle HCM**: Uses camelCase English technical names with a separate Arabic display label column; the column header exported to CSV may be the Arabic display label.
- **Workday**: Exports English camelCase by default; Arabic labels require custom report template configuration and may not appear in standard data extracts.

**Impact:** Datasets from different HRIS platforms representing the same organization may use entirely different column naming conventions for the same underlying data field. Cross-system dataset merges require mapping reconciliation before any automated pipeline processing.

---

### 5.4 Payroll-Only Dataset Limitations

Saudi payroll systems (e.g., METIQ, Bayanati, legacy HRMS installations) frequently produce datasets that are limited to compensation and administrative fields. A payroll-only export can be expected to contain:

**Present:** MonthlyIncome, PercentSalaryHike, JobLevel, YearsAtCompany, Department, Age, Absence  
**Absent:** JobSatisfaction, EnvironmentSatisfaction, WorkLifeBalance, JobInvolvement, OverTime, PerformanceRating, OrganizationalCommitment

**Critical Implication:** A payroll-only dataset cannot support a full attrition prediction model using the platform's construct framework. The SATISFACTION_HYGIENE, JOB_DEMANDS (OverTime), ENGAGEMENT_INVOLVEMENT, and COMMITMENT_ATTACHMENT categories will be entirely unmapped. Any attrition model trained on payroll-only data must be explicitly scoped as a structural baseline model with known construct coverage limitations documented in the model card.

---

### 5.5 Ministry of Human Resources Survey Vocabulary

The Saudi Ministry of Human Resources and Social Development (MHRSD, وزارة الموارد البشرية والتنمية الاجتماعية) conducts periodic national workforce satisfaction surveys using survey instruments with standardized Arabic vocabulary that differs from private sector HR practice. Notable divergences include:

- MHRSD uses `الأمان الوظيفي` (job security) as a primary satisfaction dimension — not mapped in the platform's IBM-derived construct set
- MHRSD `بيئة العمل` items measure safety and physical conditions more heavily than interpersonal climate
- MHRSD `الاستقرار المهني` (professional stability) is a compound construct combining tenure security, career development prospects, and income predictability — it cannot be mapped to a single IBM construct

Datasets originating from MHRSD surveys should be treated as requiring full construct remapping review before ingestion into the platform's pipeline.

---

## Section 6: Cultural Interpretation Caveats

The organizational psychology constructs operationalized in the IBM HR dataset were developed and validated primarily in North American and Western European organizational contexts. Their application to Saudi Arabian HR data requires acknowledgment of systematic cultural interpretation differences.

---

### 6.1 WorkLifeBalance in the Saudi Context

The `WorkLifeBalance` construct in IBM HR operationalizes the extent to which work demands interfere with personal life. In the Saudi context, this construct carries additional dimensions that are not captured by standard Western Likert-item instruments:

- **Religious observance time:** Saudi employees are entitled to prayer breaks (خمس صلوات, five daily prayers) during the workday. The impact of workplace prayer accommodation on work-life balance perception is significant and culturally specific.
- **Family obligation norms:** Extended family obligations, particularly during Ramadan, Eid holidays, and family events, generate leave demand patterns that differ structurally from Western family-work conflict patterns.
- **Gender segregation legacy:** While mixed-gender workplaces are now permitted and increasing under Vision 2030, legacy workplace arrangements continue to influence commute times, facility availability, and schedule flexibility in ways that affect work-life balance scores differentially by gender.

**Implication:** The `WorkLifeBalance` score distribution in Saudi datasets may not be comparable to IBM HR dataset distributions. Normalization benchmarks derived from the IBM HR dataset should not be applied directly to Saudi survey data.

---

### 6.2 Social Desirability Bias in Job Satisfaction Measures

Survey-based job satisfaction measures in Saudi organizational contexts are subject to elevated social desirability bias relative to Western contexts, due to:

- **Hierarchical deference norms:** Saudi organizational culture is characterized by high power distance (Hofstede, 1980). Employees may report higher satisfaction than experienced to avoid appearing disloyal to management.
- **Collective face-saving:** Expressing dissatisfaction may be perceived as reflecting poorly on the team or department, creating social pressure toward positive response distortion.
- **Survey anonymity skepticism:** In smaller organizations, employees may doubt the anonymity of digitally administered surveys, further suppressing honest negative responses.

**Implication:** Mean `JobSatisfaction` and `EnvironmentSatisfaction` scores from Saudi HR surveys may be systematically inflated relative to their true construct values. This inflation can attenuate the correlations between satisfaction constructs and attrition outcomes, leading to underestimation of the satisfaction-attrition relationship in model training.

---

### 6.3 Organizational Commitment and Dual Commitment Structures

Meyer and Allen's (1991) three-component model of organizational commitment (affective, continuance, normative) underlies the `OrganizationalCommitment` construct. In Saudi organizational contexts, the normative commitment component — staying because one feels obligated — is amplified by:

- **Kafala (كفالة) system legacy:** Expatriate workers under the kafala sponsorship system have historically had their mobility restricted, inflating continuance commitment measures that reflect constraint rather than genuine attachment.
- **National workforce loyalty narratives:** Vision 2030 Saudization (نطاقات, Nitaqat) initiatives have introduced explicit national loyalty framing into organizational culture communications, potentially inflating normative commitment reports among Saudi national employees.
- **Affective vs. normative confound:** In high-context collectivist cultural settings, affective and normative commitment are empirically less distinguishable than in individualist Western settings (Wasti, 2003). Single-item `OrganizationalCommitment` measures cannot reliably distinguish between these components.

**Implication:** `OrganizationalCommitment` scores in Saudi HR datasets should not be interpreted using Western normative benchmarks without cross-cultural measurement invariance testing.

---

### 6.4 Performance Ratings and Wasta

`PerformanceRating` in the IBM HR construct is assumed to reflect supervisor-assessed job performance based on work-related criteria. In some Saudi organizational contexts, performance ratings may be influenced by `wasta` (واسطة) — the use of personal connections, family relationships, or social network influence to obtain favorable treatment.

**Empirical Implication:** If wasta influence is present in performance ratings, the `PerformanceRating` construct in the Saudi dataset will have lower criterion validity as a measure of actual job performance, and its relationship to attrition will be partially mediated by social capital rather than task performance. This does not necessarily invalidate the mapping, but it does mean that the construct's theoretical meaning in the Saudi context is partially different from its IBM HR operationalization.

**Recommended Action:** Where possible, supplement `PerformanceRating` with objective performance indicators (sales quotas met, project completion rates, customer satisfaction scores) to assess the extent of wasta-related rating inflation.

---

## Section 7: Bilingual Mapping Limitations

The platform's bilingual mapping pipeline has specific technical limitations that analysts must understand to correctly interpret mapping confidence scores and pipeline outputs.

---

### 7.1 Arabic Normalization Scope

The Stage 3 Arabic matching normalizes input column names by stripping diacritical marks (tashkeel) only. It does NOT handle:

- **Letter variant normalization:** The letters `ة` (ta marbuta) and `ه` (ha) are distinct Unicode code points that are sometimes used interchangeably at word endings in informal writing. For example, `سنه` and `سنة` (both meaning "year") are not treated as equivalent by the current normalization. Column names using the informal variant will fail Stage 3 matching.
- **Alif variants:** `أ`, `إ`, `آ`, and `ا` are distinct code points. `أداء` (ada', performance) and `اداء` (without hamza) are treated as different strings. Informal HRIS exports frequently omit hamza diacritics on alif characters.
- **Ye variants:** `ي` and `ى` (ya vs. alif maqsura) are sometimes used interchangeably. `مبنى` and `مبني` would not be treated as equivalent.

**Impact:** Saudi HR columns with informal spelling variants will fall through to Stage 4 WEAK_PROXY matching or fail entirely. The analyst should manually inspect all failed Arabic matches before concluding that a construct is unmapped.

---

### 7.2 Mixed-Script Column Processing Order

When a column name contains both Arabic and Latin characters, the pipeline attempts matching in the following order:

1. The full string is attempted as English (Stage 1–2)
2. The Arabic substring (extracted by Unicode range detection) is matched in Stage 3
3. If neither resolves, Stage 4 keyword matching is applied to both components

This order can produce incorrect results when the English component is a non-semantic organizational code and the Arabic component is the semantically meaningful term. For example, `EMP_رضا` would first attempt to match "EMP_رضا" as an English term (Stage 1–2 fail), then extract `رضا` for Arabic matching. `رضا` (rida, satisfaction) would resolve in Stage 3, but without the context of the full column name the pipeline cannot determine whether it is `JobSatisfaction`, `EnvironmentSatisfaction`, or another satisfaction construct.

---

### 7.3 Transliteration Not Caught by Arabic Stage

Saudi HR professionals working in English-medium organizations or using English-language HRIS interfaces sometimes label Arabic-concept columns using Arabic-to-English transliteration (romanization of Arabic sounds). Examples include:

- `Radaa` or `Rida` for `رضا` (satisfaction)
- `Wadheefa` for `وظيفة` (job/position)
- `Khibra` for `خبرة` (experience)
- `Ijaza` for `إجازة` (leave/absence)

These transliterated column names will not be caught by Stage 3 Arabic matching (which requires Arabic Unicode characters) and may not resolve through Stage 2 English synonym matching (which requires recognized English HR terms). They will typically fall through to Stage 4 WEAK_PROXY matching at reduced confidence, or fail entirely.

**Required Action:** The platform's Stage 2 English synonym dictionary should be extended to include common Arabic HR term transliterations specific to Saudi organizational practice. This extension requires collaboration with Saudi HR domain experts to ensure coverage of the most prevalent transliteration conventions used in the target organization's HRIS.

---

## Appendix: Construct Mapping Summary Table

| Saudi EN Column | Arabic Equivalent | IBM Construct | Category | Evidence | Confidence | Status |
|----------------|-------------------|---------------|----------|----------|------------|--------|
| monthly_salary | الراتب الشهري | MonthlyIncome | STRUCTURAL_HR_BASELINE | STRONG_PROXY | 0.85 | VALID |
| service_years | مدة الخدمة | YearsAtCompany | STRUCTURAL_HR_BASELINE | STRONG_PROXY | 0.85 | VALID |
| job_grade | المستوى الوظيفي | JobLevel | STRUCTURAL_HR_BASELINE | STRONG_PROXY | 0.85 | VALID |
| performance_score | تقييم الأداء | PerformanceRating | STRUCTURAL_HR_BASELINE | STRONG_PROXY | 0.85 | VALID |
| employee_satisfaction | الرضا الوظيفي | JobSatisfaction | SATISFACTION_HYGIENE | STRONG_PROXY | 0.85 | VALID |
| work_environment | الرضا عن بيئة العمل | EnvironmentSatisfaction | SATISFACTION_HYGIENE | STRONG_PROXY | 0.85 | VALID |
| work_life_score | التوازن بين العمل والحياة | WorkLifeBalance | SATISFACTION_HYGIENE / JOB_RESOURCES | STRONG_PROXY | 0.85 | VALID (scale direction check required) |
| overtime_hours | ساعات إضافية | OverTime | JOB_DEMANDS | STRONG_PROXY | 0.85 | VALID (binarization required) |
| salary_increase | نسبة الزيادة | PercentSalaryHike | STRUCTURAL_HR_BASELINE | STRONG_PROXY | 0.85 | VALID |
| engagement_level | — | JobInvolvement | ENGAGEMENT_INVOLVEMENT | — | — | CONDITIONAL |
| promotion_satisfaction | — | PromotionFairness | EQUITY_FAIRNESS | — | — | CONDITIONAL |
| total_experience | — | TotalWorkingYears | STRUCTURAL_HR_BASELINE | — | — | CONDITIONAL (unit check) |
| training_hours | ساعات التدريب | TrainingHours | JOB_RESOURCES | STRONG_PROXY | 0.85 | CONDITIONAL (no formula use) |
| stress_level | — | OverTime | JOB_DEMANDS | — | — | BLOCKED |
| absence_days | الغياب | BurnoutRisk | — | — | — | BLOCKED |
| resignation_intent | نية ترك العمل | Any | — | — | — | BLOCKED — TARGET_ADJACENT_LEAKAGE |
| exit_risk | خطر الاستقالة | Any | — | — | — | BLOCKED — Circular Leakage |
| promotion_fairness | عدالة الترقية | PercentSalaryHike | — | — | — | BLOCKED |
| managerial_score | — | JobLevel | — | — | — | BLOCKED |
| attrition_risk | خطر التسرب | Any | — | — | — | BLOCKED — CRITICAL Leakage |
| churn_score | — | Any | — | — | — | BLOCKED — CRITICAL Leakage |
| loyalty_score | — | MonthlyIncome | — | — | — | BLOCKED |

---

*This document should be reviewed and updated each time the platform's construct dictionary is extended, when new Saudi HRIS data sources are onboarded, or when the organizational psychology framework underlying the attrition model is revised. All mapping decisions documented here represent the governance baseline for the Saudi deployment configuration of the Adaptive Workforce AI platform.*
