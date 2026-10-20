# Scientific Traceability Audit

**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Phase:** 4 — Scientific Governance Integration  
**Document type:** Full-Chain Scientific Traceability Audit  
**Scope:** All 7 theory-grounded psychological constructs  
**Audit date:** 2026-05-20  
**Status:** Enforced in production via `SCIENTIFIC_FEATURE_MODE = "theory_grounded"`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What Full Scientific Traceability Means for HR ML](#2-what-full-scientific-traceability-means-for-hr-ml)
3. [Traceability Matrix: All 7 Constructs](#3-traceability-matrix-all-7-constructs)
4. [Paper-to-Code Mapping](#4-paper-to-code-mapping)
5. [Layer B Violation Registry](#5-layer-b-violation-registry)
6. [Pipeline Chain](#6-pipeline-chain)
7. [Governance Checkpoints by Pipeline Step](#7-governance-checkpoints-by-pipeline-step)
8. [Confidence Reporting Chain](#8-confidence-reporting-chain)
9. [Audit Trail Fields in FeatureManifest](#9-audit-trail-fields-in-featuremanifest)
10. [Missing Traceability Gaps](#10-missing-traceability-gaps)
11. [Appendix: Construct Theory References](#11-appendix-construct-theory-references)

---

## 1. Executive Summary

This audit documents the complete scientific chain for the seven theory-grounded psychological constructs used in the Adaptive Workforce Intelligence Engine v2.5.1. For each construct, the chain traces:

**Theoretical paper → Psychological construct definition → Mathematical formula → Required dataset inputs → Implementation in code → Evidence quality rating → Confidence score → Model input contract validation**

The audit was triggered by the discovery that the pre-Phase 4 feature factory (`feature_factory.py`, Layer B) computed all seven constructs using formulas that deviated from the published theoretical literature in ways that materially affected interpretation:

- Three constructs used an additive `_norm()` combination instead of the mandatory multiplicative form (BurnoutRisk, EngagementScore, SalaryGrowth).
- Two constructs used wrong denominator columns (IncomePerLevel used tenure; CareerProgression used performance and training).
- One construct was computed from 2 inputs instead of 4 (SatisfactionIndex).
- One construct had no equivalent in Layer B at all (SalaryGrowth).

Phase 4 resolved these violations by implementing the `TheoryGroundedConstructEngine` (`backend/core/theory_grounded_construct_engine.py`), which computes all seven constructs from exact paper formulas. Layer B is disabled in production (`SCIENTIFIC_FEATURE_MODE = "theory_grounded"`). The `ModelInputContract` enforces this gate at the feature set level, blocking any legacy-disabled construct from entering the model.

This document serves as the authoritative record of theoretical provenance, formula correctness, and implementation fidelity for audit, peer review, and regulatory compliance purposes.

---

## 2. What Full Scientific Traceability Means for HR ML

HR machine learning systems make predictions that can influence employment decisions — retention interventions, compensation reviews, promotion prioritization, and workforce planning. The scientific basis of the features that drive these predictions therefore carries ethical and legal weight beyond what is typical in commercial ML.

Full scientific traceability means:

1. **Every feature that represents a psychological construct has a named theoretical source** (a peer-reviewed framework or paper, identified by author and year) that explains why the construct predicts attrition.

2. **The formula used to compute the construct matches the formula in the source paper**, not a convenience approximation. If the paper specifies a multiplicative interaction, the code must use multiplication, not a weighted sum.

3. **The inputs required by the formula are traced to dataset columns** with documented evidence quality (DIRECT if the column is an exact IBM HR match; STRONG_PROXY if it is a validated synonym; WEAK_PROXY or lower if the match is tenuous).

4. **The confidence of the construct is reported quantitatively**, reflecting the evidence quality of its inputs and any transformations applied (binarization, rescaling).

5. **Deviations from the paper formula are documented** as violations with a severity rating, not silently incorporated.

6. **Every construct result carries a governance note** that an HR professional can read to understand the limitations of the signal before using it in a workforce decision.

The alternative — computing features without theoretical anchoring, using approximations without documentation, and reporting AUC metrics without confidence bounds — produces systems that appear scientifically grounded but cannot withstand independent audit.

---

## 3. Traceability Matrix: All 7 Constructs

### 3.1 SatisfactionIndex

| Field | Value |
|---|---|
| **Theoretical framework** | COR (Conservation of Resources, Hobfoll 1989) + FFM (Five-Factor Model — inverse Neuroticism proxy) |
| **Mechanism** | COR caravan principle: satisfaction resources travel together. Low scores on all four dimensions simultaneously signals resource depletion cascade. Neuroticism (FFM) amplifies perceived resource loss. |
| **Paper formula** | `(JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction + WorkLifeBalance) / 4` |
| **Output range** | 1.0 – 4.0 (IBM HR Likert scales, each 1–4) |
| **Required inputs** | JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance |
| **Evidence quality** | DIRECT when IBM HR exact columns present; THEORY_COMPATIBLE_PROXY for Saudi-equivalent columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_satisfaction_index()` |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py (61 tests) |
| **Layer B violation** | Layer B used a 2-input `_norm(sat) * 0.55 + _norm(eng) * 0.45` formula — wrong inputs (engagement is not part of SatisfactionIndex), wrong computation (_norm before averaging changes the result when columns have different ranges), wrong dimensionality (2 inputs vs. 4 required) |

### 3.2 BurnoutRisk

| Field | Value |
|---|---|
| **Theoretical framework** | JD-R (Job Demands-Resources, Bakker & Demerouti 2007/2017) + COR (energy resource depletion pathway) |
| **Mechanism** | JD-R health-impairment pathway: job demands (overtime) deplete energy resources. The gate structure (multiplicative) reflects that overtime is a necessary condition for burnout-driven attrition; low work-life balance amplifies the damage but only when overtime exists. |
| **Paper formula** | `OverTime_binary × (5 − WorkLifeBalance)` |
| **Output range** | 0 – 4 (0 when no overtime; 1–4 when overtime present, scaled by WLB score) |
| **Required inputs** | OverTime (binary gate), WorkLifeBalance (1–4 Likert) |
| **Evidence quality** | DIRECT for IBM HR (OverTime Yes/No, WLB 1–4); PROXY for Saudi equivalents |
| **Implementation status** | Active. OverTime binarized transparently with documented penalty (0.10 for continuous input). WLB rescaled if 1–5 (penalty 0.10) or 0–100 (penalty 0.15). |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py |
| **Layer B violation** | Layer B computed `BurnoutRiskComposite` using `_norm(ot)*0.40 + _norm(wl)*0.35 + (1−_norm(sat))*0.25`. This is additive, uses a third input (workload) not in the paper formula, uses _norm() which destroys the binary gate logic (a normalized OT of 0.3 would still contribute), and has no paper anchor. The multiplicative gate is theoretically mandatory. |

### 3.3 EngagementScore

| Field | Value |
|---|---|
| **Theoretical framework** | JD-R (motivational pathway) + FFM (Conscientiousness) + Kahn (1990) Engagement Theory |
| **Mechanism** | Kahn (1990) simultaneity principle: true engagement requires simultaneous psychological availability (satisfaction signal = JobSatisfaction) and psychological presence (involvement signal = JobInvolvement). Zero on either dimension → zero engagement. This mandates the multiplicative form. |
| **Paper formula** | `JobInvolvement × JobSatisfaction` |
| **Output range** | 1 – 16 (both inputs are 1–4 Likert scales) |
| **Required inputs** | JobInvolvement (Conscientiousness-FFM proxy), JobSatisfaction (resource signal) |
| **Evidence quality** | DIRECT for IBM HR exact columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_engagement_score()` |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py |
| **Layer B violation** | Layer B computed `EngagementScore` as `_norm(eng)` — a single-source normalization of whatever column the semantic mapper identified as "engagement." This produces a value in [0,1] rather than the theoretically meaningful [1,16] product. It does not implement Kahn simultaneity at all. |

### 3.4 TenureRatio

| Field | Value |
|---|---|
| **Theoretical framework** | COR (condition resource — organizational embeddedness) + Mobley (1977) Turnover Process Model Stage 1 |
| **Mechanism** | Mobley Stage 1: employee evaluates current job relative to alternatives. High tenure ratio (time at company / total career) signals high switching costs and organizational embeddedness — a condition resource (COR). The +1 denominator prevents division-by-zero for fresh graduates (0 total working years). |
| **Paper formula** | `YearsAtCompany / (TotalWorkingYears + 1)` |
| **Output range** | 0.0 – 1.0 (bounded by definition: YearsAtCompany cannot exceed TotalWorkingYears) |
| **Required inputs** | YearsAtCompany (numerator), TotalWorkingYears (denominator) |
| **Evidence quality** | DIRECT for IBM HR exact columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_tenure_ratio()` |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py |
| **Layer B violation** | Layer B had a `CareerProgressionScore` that used performance rating, promotion recency, and training hours — none of which match the TenureRatio formula. There was no equivalent of TenureRatio in Layer B. |

### 3.5 IncomePerLevel

| Field | Value |
|---|---|
| **Theoretical framework** | COR (object resource — financial security) + Adams Equity Theory (1963) |
| **Mechanism** | Adams: perceived equity is a ratio of one's own outcome/input to a referent's outcome/input. `MonthlyIncome / (JobLevel + 1)` is a within-dataset equity signal: a high-level employee earning a low-level salary experiences acute inequity (low IncomePerLevel). The +1 prevents division-by-zero at JobLevel=0. Saudi context: MonthlyIncome in SAR (typical range 5,000–30,000). |
| **Paper formula** | `MonthlyIncome / (JobLevel + 1)` |
| **Output range** | SAR 1,250 – 7,500 for typical Saudi HR data (level-adjusted salary signal) |
| **Required inputs** | MonthlyIncome (object resource), JobLevel (ordinal rank reference) |
| **Evidence quality** | DIRECT for IBM HR exact columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_income_per_level()` |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py |
| **Layer B violation** | Layer B computed `CompensationEquity` as `_norm(sal) / (_norm(ten) + 0.1)` — salary divided by tenure, not by job level. Tenure is not the referent in Adams Equity Theory. A senior employee who has been at the company for 15 years and earns a mid-level salary would appear to have high CompensationEquity (low tenure → high ratio) when the equity signal should actually be low. |

### 3.6 CareerProgression

| Field | Value |
|---|---|
| **Theoretical framework** | COR (resource gain velocity) + JD-R (growth resource adequacy) |
| **Mechanism** | Resource gain velocity (COR): employees who accumulate resources (job level advancement) faster than average are resource-gaining; those who stagnate are resource-losing. JD-R growth resources: lack of advancement is a chronic demand that depletes engagement. High CareerProgression = fast advancement; low = stagnation. Allen, Bryant & Vardaman (2010) identify stagnation as a direct antecedent of voluntary exit. |
| **Paper formula** | `JobLevel / (YearsAtCompany + 1)` |
| **Output range** | 0.0 – 5.0 for typical data (JobLevel 1–5, YearsAtCompany 0–20+) |
| **Required inputs** | JobLevel (numerator — career rank achieved), YearsAtCompany (denominator — time invested) |
| **Evidence quality** | DIRECT for IBM HR exact columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_career_progression()` |
| **Test coverage** | Covered by test_theory_grounded_construct_engine.py |
| **Layer B violation** | Layer B computed `CareerProgressionScore` using `_norm(perf)*0.40 + (1−_norm(prom))*0.35 + _norm(trn)*0.25` — a composite of performance rating, promotion recency (inverted), and training hours. None of these are the JobLevel/YearsAtCompany ratio. The Layer B formula captures performance-training dynamics, not career velocity in the COR sense. |

### 3.7 SalaryGrowth

| Field | Value |
|---|---|
| **Theoretical framework** | JD-R (effort-reward alignment) + FFM (Conscientiousness sensitivity to unfairness) + Siegrist Effort-Reward Imbalance (ERI, 1996) |
| **Mechanism** | Siegrist ERI: attrition risk increases when effort (performance rating) is not matched by reward (salary hike). The multiplicative form is mandatory: a high hike with low performance signals misaligned reward; a low hike with high performance is the canonical ERI imbalance. Conscientious employees (FFM) are particularly sensitive to this mismatch. |
| **Paper formula** | `PercentSalaryHike × PerformanceRating` |
| **Output range** | 10–100 for typical IBM HR data (hike 10–25%, rating 1–4) |
| **Required inputs** | PercentSalaryHike (reward signal), PerformanceRating (effort/merit signal) |
| **Evidence quality** | DIRECT for IBM HR exact columns |
| **Implementation status** | Active in `TheoryGroundedConstructEngine._try_salary_growth()` |
| **Layer B violation** | No equivalent existed in Layer B. SalaryGrowth was entirely absent from the pre-Phase 4 feature set. |

---

## 4. Paper-to-Code Mapping

This section shows the exact formula expression in the paper and the corresponding Python expression in `theory_grounded_construct_engine.py`.

### SatisfactionIndex

**Paper formula:**
```
SI = (JS + ES + RS + WLB) / 4
```
where JS = JobSatisfaction, ES = EnvironmentSatisfaction, RS = RelationshipSatisfaction, WLB = WorkLifeBalance.

**Code (engine lines 477–481):**
```python
values = (
    series_dict["JobSatisfaction"]
    + series_dict["EnvironmentSatisfaction"]
    + series_dict["RelationshipSatisfaction"]
    + series_dict["WorkLifeBalance"]
) / 4.0
```

Equivalence: exact. No normalization applied before formula. Division by 4.0 is literal.

---

### BurnoutRisk

**Paper formula:**
```
BR = OT_binary × (5 − WLB)
```
where OT_binary is OverTime binarized (0/1), WLB is WorkLifeBalance (1–4).

**Code (engine line 573):**
```python
values = ot_binary * (5.0 - wlb_adj)
```

Note: `wlb_adj` is WorkLifeBalance after scale validation (rescaled from 1–5 or 0–100 if necessary, with documented confidence penalty). The `5.0` constant is literal from the paper.

---

### EngagementScore

**Paper formula:**
```
ES = JI × JS
```
where JI = JobInvolvement, JS = JobSatisfaction.

**Code (engine line 660):**
```python
values = ji_series * js_series
```

Equivalence: exact multiplicative product. No normalization before computation.

---

### TenureRatio

**Paper formula:**
```
TR = YAC / (TWY + 1)
```
where YAC = YearsAtCompany, TWY = TotalWorkingYears.

**Code (engine line 739):**
```python
values = yac / (twy + 1.0)
```

Equivalence: exact. The +1 is paper-specified for fresh graduates.

---

### IncomePerLevel

**Paper formula:**
```
IPL = Income / (Level + 1)
```

**Code (engine line 815):**
```python
values = income / (level + 1.0)
```

Equivalence: exact. The +1 prevents division-by-zero at Level=0.

---

### CareerProgression

**Paper formula:**
```
CP = Level / (YAC + 1)
```

**Code (engine line 893):**
```python
values = level / (tenure + 1.0)
```

Equivalence: exact. The +1 is paper-specified for employees with 0 years at company.

---

### SalaryGrowth

**Paper formula:**
```
SG = Hike% × PerformanceRating
```
Multiplicative form is theoretically mandatory per Siegrist ERI.

**Code (engine line 965):**
```python
values = hike * perf
```

Equivalence: exact multiplicative product. No normalization before computation.

---

## 5. Layer B Violation Registry

This section documents the specific formula violations present in `feature_factory.py` Layer B that were identified during the Phase 4 governance review. All of these constructs are now listed in `LEGACY_DISABLED_CONSTRUCTS` in `config/settings.py` and are blocked from entering the model in `theory_grounded` mode.

| Legacy Construct | Layer B Formula | Paper-Specified Formula | Violation Type | Severity |
|---|---|---|---|---|
| `SatisfactionIndex` | `_norm(sat)*0.55 + _norm(eng)*0.45` | `(JS + ES + RS + WLB) / 4` | Wrong inputs (uses `engagement` instead of 3 satisfaction sub-scales + WLB); _norm destroys scale; 2 inputs vs. 4 required | CRITICAL |
| `BurnoutRiskComposite` | `_norm(ot)*0.40 + _norm(wl)*0.35 + (1−_norm(sat))*0.25` | `OT_binary × (5 − WLB)` | Additive instead of multiplicative gate; introduces workload (not in paper formula); _norm destroys binary gate | CRITICAL |
| `EngagementScore` | `_norm(eng)` (single-source) | `JobInvolvement × JobSatisfaction` | Single input; does not implement Kahn simultaneity; no multiplicative interaction | CRITICAL |
| `CareerProgressionScore` | `_norm(perf)*0.40 + (1−_norm(prom))*0.35 + _norm(trn)*0.25` | `JobLevel / (YearsAtCompany + 1)` | Completely wrong inputs (performance, promotion, training vs. level/tenure); additive vs. ratio | CRITICAL |
| `CompensationEquity` | `_norm(sal) / (_norm(ten) + 0.1)` | `MonthlyIncome / (JobLevel + 1)` | Wrong denominator (tenure instead of job level); _norm before division changes semantics | CRITICAL |
| `RetentionRisk` | Composite of burnout, satisfaction, promotion, overtime, manager quality | No paper anchor | Invented composite; target-adjacent semantics; no theoretical provenance | HIGH |
| `WorkLifeBalanceRisk` | Overtime + distance composite | No paper anchor | Invented composite; partially duplicates BurnoutRisk; no theoretical provenance | HIGH |
| `ManagerialSupportIndex` | Manager quality normalization | No paper anchor | Invented; single-factor normalization with no construct theory | MEDIUM |
| `EmployeeStabilityRisk` | Multi-signal composite | No paper anchor + target-adjacent | Invented; semantically adjacent to attrition target; memorization risk | CRITICAL |
| `AbsenteeismPressureIndex` | Absence + overtime composite | No paper anchor | Invented composite | MEDIUM |
| `PresenteeismSignal` | Absence × overtime | No paper anchor | High leakage risk in retrospective datasets; constructed from absence data that may be absent-because-leaving | HIGH |
| `PsychologicalWellbeingScore` | Mean of unvalidated columns | No paper anchor | Invented; inputs are not validated psychometric instruments | MEDIUM |
| `PsychologicalVariabilityIndex` | Intra-individual standard deviation | No paper anchor | Invented; assumes repeated-measures data which IBM HR does not provide | HIGH |
| `PositiveAffectIndex` | Column-position split | No paper anchor | Invalid; splits columns by position with no theoretical basis | HIGH |
| `NegativeAffectIndex` | Column-position split | No paper anchor | Invalid; same column-position split | HIGH |

**Total: 15 legacy-disabled constructs.** All are blocked in `theory_grounded` mode via `ModelInputContract`.

---

## 6. Pipeline Chain

The 7-step chain from settings configuration to ML Router input:

```
Step 1: config/settings.py
        SCIENTIFIC_FEATURE_MODE = "theory_grounded"
        LEGACY_DISABLED_CONSTRUCTS = [15 construct names]
           |
           | Governance mode propagated to all downstream components
           v

Step 2: config/settings.py
        LEGACY_DISABLED_CONSTRUCTS (15 constructs explicitly quarantined)
           |
           | Names used as blocklist by ModelInputContract and FeatureFactory
           v

Step 3: backend/core/theory_aware_column_mapper.py
        TheoryAwareColumnMapper.map(df)
        → Returns Dict[str, ConstructMapping] for all recognized columns
        → Each ConstructMapping carries:
             mapped_construct (e.g., "JobSatisfaction")
             evidence_strength (DIRECT / STRONG_PROXY / WEAK_PROXY / ...)
             semantic_confidence (0.0 – 1.0)
             scale_confidence (0.0 – 1.0)
             leakage_flag (bool)
           |
           | 67 tests in test_theory_aware_column_mapper.py
           v

Step 4: backend/core/theory_grounded_construct_engine.py
        TheoryGroundedConstructEngine.compute(df, column_mappings)
        → Computes 7 constructs from exact paper formulas
        → Returns ConstructActivationReport with:
             constructed_df (enriched DataFrame)
             construct_results: Dict[str, ConstructResult]
             blocked_constructs: Dict[str, BlockedConstruct]
             warnings: List[str]
             audit_summary: str
        → Each ConstructResult carries construct_confidence (0.30 – 0.95)
           |
           | 61 tests in test_theory_grounded_construct_engine.py
           v

Step 5: backend/core/feature_factory.py
        FeatureFactory.engineer(df, sem_map, dataset_type, target)
        → Layer B GATED: if SCIENTIFIC_FEATURE_MODE == "theory_grounded":
              skip _layer_b_hr_constructs()
              manifest.legacy_constructs_disabled = LEGACY_DISABLED_CONSTRUCTS
        → Layer A (universal interactions) and Layer D (temporal features) still run
        → Returns (engineered_df, FeatureManifest)
           |
           | Layer B bypass is tested in test_phase4_integration.py
           v

Step 6: backend/core/model_input_contract.py
        ModelInputContract.validate(feature_names, df, target_col, column_mappings)
        → Checks each feature against:
             LEGACY_DISABLED_CONSTRUCTS (CRITICAL if matched)
             PROXY_LEAKAGE_KEYWORDS (CRITICAL if matched)
             _TARGET_ADJACENT_KEYWORDS (CRITICAL if matched)
             _ID_COLUMN_KEYWORDS (HIGH if matched)
             _PREPROCESSING_KEYWORDS (MEDIUM if matched)
             column_mappings leakage_flag (CRITICAL if True)
        → Theory-grounded constructs pre-approved (bypass all pattern checks)
        → Returns ContractValidationResult with approved_features list
           |
           | 9 tests in test_phase4_integration.py (ModelInputContract class)
           v

Step 7: backend/core/ml_router.py
        MLRouter.train(df_eng, approved_features, target, dataset_type)
        → Receives ONLY approved_features from Step 6
        → Trains ensemble of LR, RF, XGBoost, LightGBM, CatBoost
        → Returns MLResult with best model, metrics, optimal threshold
```

**Total test coverage across chain:** 243 tests, all passing.

---

## 7. Governance Checkpoints by Pipeline Step

| Step | Component | Governance Rule Enforced |
|---|---|---|
| Step 1 | `config/settings.py` | `SCIENTIFIC_FEATURE_MODE` must equal `"theory_grounded"`. Tested: `test_scientific_feature_mode_is_theory_grounded`. Any value other than `"theory_grounded"` or `"legacy_disabled"` is flagged as non-production configuration. |
| Step 2 | `config/settings.py` | `LEGACY_DISABLED_CONSTRUCTS` must be non-empty and must contain known violations (`BurnoutRiskComposite`, `SatisfactionIndex`, `EngagementScore`, `EmployeeStabilityRisk`, `PresenteeismSignal`). Tested: `test_legacy_disabled_constructs_non_empty`, `test_burnout_risk_composite_is_disabled`, etc. |
| Step 3 | `TheoryAwareColumnMapper` | Evidence quality gate: columns with `WEAK_PROXY`, `UNSUPPORTED`, or `TARGET_ADJACENT` evidence are excluded from construct computation. Leakage-flagged columns are marked and never accepted by the engine. |
| Step 4 | `TheoryGroundedConstructEngine` | Formula exactness: each construct is computed using the paper formula, not an approximation. If required inputs are missing, the construct is blocked (not approximated). Minimum confidence thresholds: semantic_confidence ≥ 0.70, scale_confidence ≥ 0.70 per input. |
| Step 5 | `FeatureFactory` | Layer B bypass gate: `if not _LEGACY_MODE_ACTIVE: skip _layer_b_hr_constructs()`. `_LEGACY_MODE_ACTIVE` is False when `SCIENTIFIC_FEATURE_MODE != "legacy_for_debug_only"`. The bypass is logged and recorded in `FeatureManifest.legacy_constructs_disabled`. |
| Step 6 | `ModelInputContract` | Seven governance rules enforced in order: target-in-features, legacy-disabled, proxy-leakage, target-adjacent, ID-memorization, preprocessing-leakage, Phase-1-leakage-flag. Theory-grounded constructs are pre-approved before any rule check. |
| Step 7 | `MLRouter` | Receives only `approved_features` from Step 6. Has no internal awareness of which constructs are legacy or theory-grounded — enforcement is fully upstream. |

---

## 8. Confidence Reporting Chain

Each theory-grounded construct carries a `construct_confidence` score that propagates through the pipeline. This section documents how that score is computed and how it flows.

### 8.1 Phase 1: TheoryAwareColumnMapper

Each `ConstructMapping` produced by Phase 1 carries two confidence scores:

- **`semantic_confidence`** (0.0 – 1.0): How confidently the column name maps to the target construct. IBM HR exact name → 1.00. Saudi English synonym → 0.70 – 0.95. Arabic synonym → 0.70 – 0.90 (with scale check).

- **`scale_confidence`** (0.0 – 1.0): How well the column's value distribution matches the expected scale. A JobSatisfaction column with values {1, 2, 3, 4} on a 1–4 Likert → 0.95. The same column with values {0, 1, 2, 3, 4} → 0.85 (scale boundary mismatch). Values suggesting 0–100 percentage → 0.70.

### 8.2 Phase 2: TheoryGroundedConstructEngine

The engine computes `construct_confidence` for each activated construct:

```python
# Base confidence ceiling:
_MAX_CONF_DIRECT = 0.95   # DIRECT_PAPER_REPLICATION
_MAX_CONF_PROXY  = 0.80   # THEORY_COMPATIBLE_PROXY

# Per-input penalties:
_PENALTY_PROXY_INPUT    = 0.08   # each STRONG_PROXY input
_PENALTY_OT_BINARIZE    = 0.10   # OverTime continuous → binarized
_PENALTY_WLB_RESCALE_SM = 0.10   # WLB 1-5 rescaled to 1-4
_PENALTY_WLB_RESCALE_LG = 0.15   # WLB 0-100 rescaled to 1-4

construct_confidence = max(0.30, base − Σ(penalties))
```

**Example: BurnoutRisk with IBM HR data (all DIRECT inputs)**
```
base           = 0.95  (DIRECT_PAPER_REPLICATION)
penalty        = 0.00  (OverTime is Yes/No → no binarization penalty)
                 0.00  (WLB is 1–4 → no rescaling penalty)
confidence     = 0.95
```

**Example: BurnoutRisk with Saudi HR data (STRONG_PROXY inputs, continuous OT)**
```
base           = 0.80  (THEORY_COMPATIBLE_PROXY)
penalty        = 0.08  (OverTime proxy → STRONG_PROXY penalty)
               + 0.08  (WorkLifeBalance proxy → STRONG_PROXY penalty)
               + 0.10  (OverTime continuous → binarization penalty)
confidence     = max(0.30, 0.80 − 0.26) = 0.54
```

### 8.3 Phase 4: ModelInputContract

The `ContractValidationResult` records the `scientific_feature_mode`. When theory-grounded constructs are present in `approved_features`, a governance note is added:

```
"Theory-grounded constructs in feature set: [SatisfactionIndex, BurnoutRisk, ...]"
```

The individual `construct_confidence` values from Phase 2 are not re-evaluated by the contract. The contract trusts Phase 2 evidence and focuses on blocking violations, not re-scoring confidence.

### 8.4 Confidence in ConstructActivationReport

The `ConstructActivationReport.audit_summary` field includes the confidence and penalty for each computed construct:

```
Theory-Grounded Construct Activation — Audit Summary
======================================================
Computed: 7 / 7 constructs
Blocked : 0 / 7 constructs

COMPUTED CONSTRUCTS:
  ✓ SatisfactionIndex    [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ BurnoutRisk          [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ EngagementScore      [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ TenureRatio          [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ IncomePerLevel       [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ CareerProgression    [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000
  ✓ SalaryGrowth         [DIRECT_PAPER_REPLICATION]  confidence=0.950 penalty=0.000

Legend: ✓=DIRECT_PAPER_REPLICATION  ~=THEORY_COMPATIBLE_PROXY  ✗=BLOCKED
```

---

## 9. Audit Trail Fields in FeatureManifest

The `FeatureManifest` dataclass (defined in `backend/core/feature_factory.py`) carries two fields that provide the scientific governance audit trail:

```python
@dataclass
class FeatureManifest:
    features_added: List[str]              # all features that were added
    features_failed: List[str]             # features that failed computation
    specs_applied: List[FeatureSpec]       # specification for each feature
    n_original: int                        # original column count
    n_final: int                           # final column count after engineering
    legacy_constructs_disabled: List[str]  # AUDIT FIELD: which Layer B constructs were blocked
    scientific_feature_mode: str           # AUDIT FIELD: current governance mode
```

**`legacy_constructs_disabled`:** Populated from `LEGACY_DISABLED_CONSTRUCTS` when the factory runs in `theory_grounded` mode. In production, this list always contains all 15 disabled construct names. An auditor can inspect this field to confirm that no legacy construct entered the engineering phase. The Phase 4 integration test `test_manifest_records_disabled_constructs` verifies that the manifest records at least some disabled constructs when running in theory_grounded mode.

**`scientific_feature_mode`:** Set at class definition time from `settings.SCIENTIFIC_FEATURE_MODE`. This field is captured at pipeline start and included in the manifest, so the audit trail records the governance mode that was active when features were engineered — not the current mode at inspection time.

**Test:** `test_scientific_feature_mode_recorded_in_manifest` (in `tests/test_phase4_integration.py`) verifies that the manifest's `scientific_feature_mode` field equals `"theory_grounded"`.

---

## 10. Missing Traceability Gaps

This section documents what is **not yet fully traced** in the current implementation. These are known gaps, not defects.

### 10.1 Layer E has no paper anchor

`feature_factory.py` Layer E computes organizational features (workload pressure, managerial span, organizational network centrality proxies). None of these features have a cited paper anchor in the current implementation. They are computed as reasonable engineering heuristics but are not part of the theory-grounded framework.

**Risk:** Layer E features may contain signals that correlate with attrition for reasons unrelated to the seven theoretical constructs. If they are highly predictive, the model's behavior in production may diverge from theoretical expectations.

**Recommendation:** Assign each Layer E feature a COR, JD-R, or other theoretical anchor, or disable Layer E features in theory_grounded mode. Currently, Layer E runs in all modes.

### 10.2 Layer A interactions lack multiplicity justification

Layer A computes five interaction features: `pay_performance_ratio`, `career_start_age_proxy`, `pay_load_efficiency`, `engagement_burnout_gap`, `satisfaction_load_ratio`. While each ratio is individually defensible, no paper specifies these exact interaction forms.

**Current status:** These are labeled as "engineering heuristics" in the Layer A docstring, not theory-grounded constructs.

**Risk:** Low. These features do not claim theoretical provenance and are not named to suggest it. They can be disabled without affecting the seven theory-grounded constructs.

### 10.3 Construct confidence is not propagated to model feature importance

The `construct_confidence` score computed in Phase 2 is recorded in `ConstructResult` but is not passed to the ML Router. SHAP feature importance values for theory-grounded constructs are not weighted by their confidence.

**Implication:** A construct computed at confidence 0.54 (proxy inputs with penalties) contributes the same to model feature importance as a construct computed at confidence 0.95 (direct IBM HR inputs). An auditor cannot distinguish these cases from the SHAP output alone.

**Recommendation:** Pass `construct_confidence` to the explainability engine and display confidence-weighted SHAP values in the governance panel.

### 10.4 Arabic column mapping traceability is incomplete

`TheoryAwareColumnMapper` supports Arabic column names via Unicode pattern matching. The confidence scores for Arabic column matches are documented in the mapper, but the audit trail does not currently record whether a column was matched via English or Arabic synonym, making it harder to verify Arabic-language HR export provenance in an audit.

### 10.5 No paper anchor for target variable derivation

The `Attrition` binary target variable is treated as a ground truth label throughout the pipeline. The paper the constructs are drawn from defines attrition as voluntary departure — but HR export files frequently combine voluntary and involuntary attrition. No governance component currently verifies that the target variable is restricted to voluntary departures before training.

**Risk:** A model trained on combined voluntary + involuntary attrition may generalize poorly compared to the theoretical predictions, which are exclusively modeled for voluntary departure.

### 10.6 Layer D temporal features not fully anchored

Layer D generates tenure bucket features, career velocity bins, and period-in-role indicators. These are consistent with COR and Mobley theory but are not mapped to specific paper formulas. They are computed from raw IBM HR columns (`YearsAtCompany`, `YearsInCurrentRole`, `YearsSinceLastPromotion`) and are not currently blocked in theory_grounded mode.

---

## 11. Appendix: Construct Theory References

| Theory | Full Citation | Constructs |
|---|---|---|
| **COR** | Hobfoll, S. E. (1989). Conservation of resources: A new attempt at conceptualizing stress. *American Psychologist, 44*(3), 513–524. | SatisfactionIndex (caravan principle), TenureRatio (condition resource), IncomePerLevel (object resource), CareerProgression (resource gain velocity) |
| **JD-R** | Bakker, A. B., & Demerouti, E. (2007). The job demands-resources model: State of the art. *Journal of Managerial Psychology, 22*(3), 309–328. | BurnoutRisk (health-impairment pathway), EngagementScore (motivational pathway), CareerProgression (growth resource adequacy), SalaryGrowth (effort-reward alignment) |
| **FFM** | Costa, P. T., & McCrae, R. R. (1992). *Revised NEO Personality Inventory (NEO-PI-R) and NEO Five-Factor Inventory (NEO-FFI) professional manual.* Odessa, FL: Psychological Assessment Resources. | SatisfactionIndex (inverse Neuroticism proxy), EngagementScore (Conscientiousness), SalaryGrowth (Conscientiousness sensitivity to ERI) |
| **Mobley** | Mobley, W. H. (1977). Intermediate linkages in the relationship between job satisfaction and employee turnover. *Journal of Applied Psychology, 62*(2), 237–240. | TenureRatio (Stage 1 evaluation anchor) |
| **Adams** | Adams, J. S. (1963). Towards an understanding of inequity. *Journal of Abnormal and Social Psychology, 67*(5), 422–436. | IncomePerLevel (rank-relative compensation equity) |
| **Siegrist** | Siegrist, J. (1996). Adverse health effects of high-effort/low-reward conditions. *Journal of Occupational Health Psychology, 1*(1), 27–41. | SalaryGrowth (effort-reward imbalance, multiplicative form) |
| **Kahn** | Kahn, W. A. (1990). Psychological conditions of personal engagement and disengagement at work. *Academy of Management Journal, 33*(4), 692–724. | EngagementScore (simultaneity principle — multiplicative mandatory) |
| **Allen, Bryant & Vardaman** | Allen, D. G., Bryant, P. C., & Vardaman, J. M. (2010). Retaining talent: Replacing misconceptions with evidence-based strategies. *Academy of Management Perspectives, 24*(2), 48–64. | CareerProgression (stagnation as voluntary exit antecedent) |

**Source paper for this implementation:**

> "Integrating Psychological Precursors into Machine Learning for Enhanced Employee Attrition Prediction: A Theory-Grounded Hybrid Framework" (2026). The construct formulas, input specifications, and output ranges documented in this audit were drawn from this paper's methodology section. This document serves as the implementation traceability record for that methodology.

---

*This document is part of the Phase 4 Scientific Governance Audit for the Adaptive Workforce Intelligence Engine v2.5.1. For temporal leakage governance, see `TEMPORAL_VALIDATION_GOVERNANCE.md`.*
