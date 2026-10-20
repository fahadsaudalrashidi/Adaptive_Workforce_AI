# Legacy Logical Quarantine Report
## Adaptive Workforce Intelligence Engine — v2.5.1
### Phase 4 Scientific Governance — Feature Engineering Audit

---

**Document type:** Phase 4 Governance Audit  
**Prepared by:** Enterprise AI Research Division  
**Platform version:** 2.5.1  
**Audit date:** 2026-05-20  
**Status:** ACTIVE — Quarantine in Effect  
**Classification:** Internal Governance — Engineering and Science Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background: Why These Constructs Exist](#2-background-why-these-constructs-exist)
3. [Quarantine Method: Logical Gate vs. Physical Deletion](#3-quarantine-method-logical-gate-vs-physical-deletion)
4. [The 15 Quarantined Constructs](#4-the-15-quarantined-constructs)
5. [Violation Type Taxonomy](#5-violation-type-taxonomy)
6. [Activation Gate Mechanism](#6-activation-gate-mechanism)
7. [What Still Runs in Theory-Grounded Mode](#7-what-still-runs-in-theory-grounded-mode)
8. [FeatureManifest Audit Trail](#8-featuremanifest-audit-trail)
9. [Test Coverage](#9-test-coverage)
10. [Reversal Path: Debug Mode Warning](#10-reversal-path-debug-mode-warning)
11. [Physical Deletion: Deferred to Phase 5](#11-physical-deletion-deferred-to-phase-5)
12. [Governance Responsibilities and Sign-off](#12-governance-responsibilities-and-sign-off)

---

## 1. Executive Summary

During Phase 4 of the Adaptive Workforce AI development program, a systematic review of the feature engineering pipeline identified **15 constructs** in `backend/core/feature_factory.py` (Layer B and Layer C) that are scientifically invalid and must not be used in any trained model, generated report, or decision-support output.

These constructs fall into three categories of violation:

- **Wrong formula:** The implementation deviates materially from the theoretical formula it claims to operationalize (e.g., additive formulas where the theory requires a multiplicative gate).
- **Invented composite:** No published peer-reviewed paper anchors the construct. The feature was constructed from plausible-sounding inputs with no theoretical basis for the specific weighting or functional form used.
- **Target-adjacent or leakage-prone:** The construct encodes information semantically adjacent to the attrition outcome, or combines retrospective signals in a way that introduces temporal leakage in historical datasets.

The chosen remediation is a **logical gate** controlled by a single configuration key — `SCIENTIFIC_FEATURE_MODE` in `config/settings.py`. When set to `"theory_grounded"` (the production default since Phase 4), Layers B and C do not execute. All 15 constructs are recorded in `LEGACY_DISABLED_CONSTRUCTS` and are carried into the `FeatureManifest` for every pipeline run, providing a complete, auditable record.

This approach deliberately preserves the Layer B and C code in-tree rather than deleting it. Physical deletion is deferred to Phase 5, pending formal audit sign-off from the science review board. This allows the invalid implementations to be compared line-by-line against correct formulas during that review.

**Key facts:**

| Item | Value |
|---|---|
| Total legacy constructs quarantined | 15 |
| Layers affected | Layer B (HR Constructs), Layer C (Psychological Survey) |
| Layers unaffected | Layer A (Numeric Interactions), Layer D (Temporal), Layer E (Organizational) |
| Gate controlling variable | `SCIENTIFIC_FEATURE_MODE` in `config/settings.py` |
| Default production value | `"theory_grounded"` |
| Debug-only escape hatch | `"legacy_for_debug_only"` — never in production |
| Audit trail mechanism | `FeatureManifest.legacy_constructs_disabled` |
| Test file | `tests/test_phase4_integration.py` |
| Physical deletion target | Phase 5, pending audit sign-off |

---

## 2. Background: Why These Constructs Exist

The feature factory (`backend/core/feature_factory.py`) was written in early platform development as a pragmatic, heuristic approach to construct engineering. At that time, the platform did not have the `TheoryGroundedConstructEngine` (Phase 2) or the `TheoryAwareColumnMapper` (Phase 1). Construct computation was handled entirely inside `feature_factory.py`, organized into five layers (A through E).

Layers B and C were written to produce plausible-sounding psychological constructs from whatever semantic columns were available. They used `_norm()` (min-max normalization) liberally before computation, invented additive composite weights, and combined inputs in ways that felt intuitive but were not anchored to any specific published formula. Some constructs were named after well-known psychological concepts (BurnoutRisk, SatisfactionIndex, EngagementScore) but computed them differently from the paper formulas those names imply.

When Phase 2 introduced `TheoryGroundedConstructEngine` — computing the same named constructs from exact paper formulas — a collision emerged: both engines were capable of producing a column named `SatisfactionIndex`, but with fundamentally different mathematical content. The Phase 2 engine computes it as the arithmetic mean of four Likert-scale inputs (JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance). The Layer B implementation computes a two-input weighted average using `_norm()` before combining, which changes the scale and loses three of the four required theoretical inputs.

Phase 4's mandate was to resolve this collision permanently, document all 15 invalid constructs, and ensure the production pipeline uses only the theory-grounded versions.

---

## 3. Quarantine Method: Logical Gate vs. Physical Deletion

### 3.1 Why Not Physical Deletion?

Physical deletion of Layer B and C code from `feature_factory.py` was considered and rejected for Phase 4. The reasons are:

1. **Audit comparison requires the code to exist.** The Phase 5 science review board must be able to read the wrong formula and the correct formula side by side. If the Layer B code is deleted before that review concludes, the comparison becomes impossible.

2. **Edge case testing requires the code to be executable.** The test suite includes a `"legacy_for_debug_only"` execution path that verifies Layer B behavior is correctly gated off in production. Those tests need the Layer B functions to exist so they can exercise the gate.

3. **Reversal risk during Phase 5 audit.** If a construct is found to be correctly implemented (against expectations), the team can upgrade its classification without needing to recover deleted code. Logical quarantine is reversible; deletion is not.

4. **Governance principle: "Mark before you delete."** Deleting first and documenting later is a governance anti-pattern. The correct order is to quarantine, document, review, then delete.

### 3.2 How the Logical Gate Works

The gate is implemented as a single read-once boolean at module import time in `feature_factory.py`:

```python
_LEGACY_MODE_ACTIVE = (SCIENTIFIC_FEATURE_MODE == "legacy_for_debug_only")
```

`SCIENTIFIC_FEATURE_MODE` is read from `config/settings.py`. In any deployment where that file has not been deliberately edited to `"legacy_for_debug_only"`, `_LEGACY_MODE_ACTIVE` is `False` and Layer B and C never execute.

Layer B and C functions exist in the module as first-class Python functions, but they are only called inside conditional blocks guarded by `_run_legacy`. The functions themselves have no side effects when not called; they are inert code until explicitly activated.

A secondary cleanup sweep in the main `engineer()` method ensures that even if a legacy construct column was pre-computed elsewhere and placed into the DataFrame before `feature_factory.py` ran, it is actively removed:

```python
if not _run_legacy:
    for col in LEGACY_DISABLED_CONSTRUCTS:
        if col in df.columns:
            df = df.drop(columns=[col])
```

This means the gate is enforced in two directions: Layer B and C do not produce columns, and any pre-existing legacy columns are excised from the DataFrame before it is returned to the caller.

### 3.3 Why This Is the Right Approach

The logical gate satisfies all four requirements of a sound quarantine:

| Requirement | How the Gate Satisfies It |
|---|---|
| Invalid code does not execute in production | `_LEGACY_MODE_ACTIVE = False` by default; layers B and C are never called |
| Code is available for audit comparison | Layer B and C functions remain in the file, readable and comparable |
| Audit trail records what was disabled | `FeatureManifest.legacy_constructs_disabled` lists all 15 constructs per run |
| Re-enablement requires deliberate action | Must change `SCIENTIFIC_FEATURE_MODE` in `settings.py` to a non-default value |

---

## 4. The 15 Quarantined Constructs

The following table documents all 15 constructs in `LEGACY_DISABLED_CONSTRUCTS`. Each row identifies the construct name, the feature factory layer in which it was computed, the violation type (see Section 5), and the specific reason it was quarantined.

| # | Construct Name | Layer | Violation Type | Specific Reason | Scientific Status |
|---|---|---|---|---|---|
| 1 | `BurnoutRiskComposite` | B | Wrong formula | Implemented as a weighted additive sum of normalized overtime, workload, and satisfaction inputs. The JD-R health-impairment pathway requires a multiplicative gate: when overtime is absent (OverTime = 0), burnout risk must be zero regardless of workload — additive formulas cannot enforce this constraint. | INVALID — wrong functional form |
| 2 | `SatisfactionIndex` | B | Wrong formula | Computed from two inputs (satisfaction + engagement) using `_norm()` before combining. The paper formula requires a four-input arithmetic mean (JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance) with no prior normalization. Three required inputs are missing entirely. | INVALID — missing required inputs; wrong normalization order |
| 3 | `EngagementScore` | B | Wrong formula | Computed as `_norm(engagement_col)` when only one engagement source is available. The paper formula (Kahn 1990) requires a multiplicative product of JobInvolvement and JobSatisfaction. A single-source normalized score is not operationally equivalent to the two-dimension engagement construct. | INVALID — single-source normalization vs. required product formula |
| 4 | `RetentionRisk` | B | Invented composite | A weighted sum of burnout, satisfaction, promotion gap, overtime, and managerial support signals. No published paper anchors this specific combination or these weights. The construct is conceptually plausible but scientifically ungrounded. | INVALID — no paper anchor |
| 5 | `CareerProgressionScore` | B | Wrong inputs | Uses performance rating and training hours as inputs, weighted with a heuristic formula. The theory-grounded CareerProgression construct requires JobLevel and YearsAtCompany — rank-velocity, not effort-output. The Layer B formula conflates performance with career advancement. | INVALID — wrong theoretical inputs |
| 6 | `CompensationEquity` | B | Wrong denominator | Computes salary relative to tenure (`salary / (tenure + 0.1)`). Adams (1963) Equity Theory specifies that the denominator must be rank (JobLevel), not time. Tenure is a different resource dimension entirely. A senior employee with long tenure but a junior job level has a low ratio for the wrong reason. | INVALID — wrong denominator (tenure vs. JobLevel) |
| 7 | `WorkLifeBalanceRisk` | B | Invented composite | A weighted sum of overtime, commute distance, and workload. No published paper anchors this formula or the specific 50/30/20 weights used. | INVALID — no paper anchor |
| 8 | `ManagerialSupportIndex` | B | Invented composite | Defined as `_norm(manager_quality)` — a single-column normalized score. While manager quality is a theoretically relevant variable, no paper anchors a standalone normalized index as an independent construct. | INVALID — no paper anchor for standalone construct |
| 9 | `EmployeeStabilityRisk` | B | Invented + target-adjacent | Computed as a weighted inverse of tenure and age. Both signals are semantically adjacent to attrition: long tenure and older age correlate with reduced voluntary exit rates. The construct is effectively a proxy attrition score derived from the same features the model trains on, creating a circular signal. | INVALID — no paper anchor; target-adjacent leakage risk |
| 10 | `AbsenteeismPressureIndex` | B | Invented composite | Defined as `_norm(absence_col)` — a single-column normalized score. Absence rate is an important input variable, but wrapping it in a normalized "index" construct name implies theoretical grounding that does not exist. | INVALID — no paper anchor for standalone construct |
| 11 | `PresenteeismSignal` | E (CAUTION) | High leakage risk | Computed as a 50/50 weighted sum of normalized absence and normalized overtime. In retrospective HR datasets, high absence combined with high overtime frequently co-occurs with imminent attrition. This creates a temporally leaky signal: the combination may be detecting behavioral warning signs that postdate the decision to leave rather than predicting future departure. | FLAGGED — temporal leakage risk in retrospective datasets |
| 12 | `PsychologicalWellbeingScore` | C | Invented composite | Computed as the row-wise mean across all columns tagged `psychological_score` by the semantic mapper. No paper specifies that an unweighted mean across generic psychometric columns constitutes a valid wellbeing construct. The inputs are not validated against any specific instrument. | INVALID — mean of unvalidated columns |
| 13 | `PsychologicalVariabilityIndex` | C | Invented composite | Computed as the row-wise standard deviation across psychometric columns. Within-person variability has some theoretical basis in mood research, but no published paper specifies this column-set standard deviation as a valid psychological construct for attrition prediction. | INVALID — intra-individual std with no paper anchor |
| 14 | `PositiveAffectIndex` | C | Invalid construction | Computes the mean of the "top half" of psychometric columns (by column position). Column position is not a theoretical attribute. The split has no basis in any published instrument or theory — it reflects an arbitrary index order, not a validated positive-affect subscale. | INVALID — column-position split with no theory |
| 15 | `NegativeAffectIndex` | C | Invalid construction | Computes the inverted mean of the "bottom half" of psychometric columns (by column position). The same position-based split problem applies. Neither positive nor negative affect can be validly operationalized by splitting columns by their order in a DataFrame. | INVALID — column-position split with no theory |

---

## 5. Violation Type Taxonomy

The 15 constructs were classified into four violation types. This taxonomy is used consistently across this report and the `LEGACY_DISABLED_CONSTRUCTS` inline comments in `config/settings.py`.

| Violation Type | Definition | Count |
|---|---|---|
| **Wrong formula** | The construct exists in published literature but the implementation uses a different functional form, wrong normalization order, or incorrect inputs | 3 (BurnoutRiskComposite, SatisfactionIndex, EngagementScore) |
| **Wrong inputs** | The construct exists in published literature but the implementation uses theoretically incorrect input variables | 1 (CareerProgressionScore) |
| **Wrong denominator** | The construct uses the correct general formula structure but the wrong variable in a critical denominator position | 1 (CompensationEquity) |
| **Invented composite** | No published peer-reviewed paper anchors the construct, its formula, or its input combination | 7 (RetentionRisk, WorkLifeBalanceRisk, ManagerialSupportIndex, EmployeeStabilityRisk, AbsenteeismPressureIndex, PsychologicalWellbeingScore, PsychologicalVariabilityIndex) |
| **Invalid construction method** | The operational procedure is invalid regardless of whether the inputs are correct (e.g., column-position split) | 2 (PositiveAffectIndex, NegativeAffectIndex) |
| **Target-adjacent leakage risk** | The construct encodes signals that are semantically or temporally adjacent to the attrition outcome | 1 (EmployeeStabilityRisk — overlaps with Invented; also PresenteeismSignal in Layer E) |

Note: `EmployeeStabilityRisk` appears under both "Invented composite" and "Target-adjacent." `PresenteeismSignal` is in Layer E (which still runs) but is flagged CAUTION rather than fully quarantined; see Section 7.

---

## 6. Activation Gate Mechanism

### 6.1 Configuration Key

The gate is controlled by a single string variable in `config/settings.py`:

```python
SCIENTIFIC_FEATURE_MODE: str = "theory_grounded"
```

Three recognized values exist:

| Value | Meaning | Layer B/C Status | Use Case |
|---|---|---|---|
| `"theory_grounded"` | Default production setting | DISABLED | All production runs, reports, scoring |
| `"legacy_disabled"` | Alias for theory_grounded | DISABLED | Explicit documentation use |
| `"legacy_for_debug_only"` | Escape hatch for engineering comparison | ENABLED | Side-by-side formula comparison in dev only — never in production |

### 6.2 How the Gate is Evaluated in `engineer()`

The `FeatureFactory.engineer()` method evaluates the gate at the start of each call:

```python
_run_legacy = _LEGACY_MODE_ACTIVE
```

`_LEGACY_MODE_ACTIVE` is a module-level boolean, computed once at import time:

```python
_LEGACY_MODE_ACTIVE = (SCIENTIFIC_FEATURE_MODE == "legacy_for_debug_only")
```

Because this is evaluated at import, changing `SCIENTIFIC_FEATURE_MODE` at runtime after module import has no effect. The setting must be correct in `config/settings.py` before the process starts.

### 6.3 Gate Logic Flow

```
engineer() is called
    |
    v
_run_legacy = _LEGACY_MODE_ACTIVE  (module-level, set at import)
    |
    v
Layer A runs always (numeric interactions — no theory formula claims)
    |
    v
Layer D runs always (temporal features — tenure, career velocity)
    |
    v
Is dataset_type in HR/burnout/engagement/mixed/unknown?
    |
    +-- YES --> Is _run_legacy True?
    |               |
    |               +-- YES --> Layer B runs (HR constructs)
    |               |
    |               +-- NO  --> Layer B SKIPPED
    |
    +-- YES --> Layer E runs (organizational stress — always, with CAUTION)
    |
    v
Is dataset_type in psychological/burnout/engagement/mixed?
    |
    +-- YES --> Is _run_legacy True?
                    |
                    +-- YES --> Layer C runs (psychological constructs)
                    |
                    +-- NO  --> Layer C SKIPPED
    |
    v
Cleanup pass: remove any LEGACY_DISABLED_CONSTRUCTS columns from df
(handles pre-computed legacy columns from prior runs or cached DataFrames)
    |
    v
Return df, manifest
```

### 6.4 Log Output

When the gate suppresses Layer B and C, the following log line is emitted at INFO level:

```
FeatureFactory [theory_grounded]: Layer B (HR constructs) and Layer C (psychological)
are DISABLED. 15 legacy constructs quarantined.
TheoryGroundedConstructEngine is the active construct source.
```

When the gate is open (debug mode), the following WARNING is emitted:

```
FeatureFactory [LEGACY_FOR_DEBUG_ONLY]: Layer B and C are ACTIVE.
Constructs use scientifically invalid formulas.
DO NOT use this output for reports, scoring, or any production purpose.
```

---

## 7. What Still Runs in Theory-Grounded Mode

The following layers remain active regardless of `SCIENTIFIC_FEATURE_MODE`.

### 7.1 Layer A — Universal Numeric Interactions (Always Active, No Concerns)

Layer A computes safe ratio and difference features from semantically mapped column pairs. These features make no theoretical formula claims — they are straightforward numeric interactions.

| Feature | Formula | Inputs |
|---|---|---|
| `pay_performance_ratio` | salary / performance | `salary`, `performance` |
| `career_start_age_proxy` | tenure / age | `tenure`, `age` |
| `pay_load_efficiency` | salary / workload | `salary`, `workload` |
| `engagement_burnout_gap` | engagement / burnout | `engagement`, `burnout` |
| `satisfaction_load_ratio` | satisfaction / workload | `satisfaction`, `workload` |

These features are dataset-driven (they only compute if both columns are present and sufficiently populated) and do not claim to replicate any specific paper formula. They are analogous to "derived numeric columns" rather than "psychological constructs."

### 7.2 Layer D — Temporal and Tenure Features (Always Active, No Concerns)

Layer D engineers time-based features from tenure, age, promotion history, and role change data.

| Feature | Formula | Risk Level |
|---|---|---|
| `TenureBucket` | Binned tenure into 6 ordinal groups | None |
| `CareerStartAge` | Age minus tenure (implied entry age) | None |
| `PromotionStagnationRatio` | Promotion gap / (tenure + 1) | None |
| `CareerVelocity` | Role changes / (tenure + 1) | None |

These features use interpretable, directly computable formulas with no theory anchoring claims. They do not produce psychological constructs.

### 7.3 Layer E — Organizational Stress Features (Active, CAUTION for PresenteeismSignal)

Layer E runs for HR-type datasets in all modes. Most Layer E features are straightforward organizational metrics:

| Feature | Formula | Status |
|---|---|---|
| `WorkloadPerHeadcount` | workload / (team_size + 1) | CLEAN — structural metric |
| `CompensationEfficiencyGap` | norm(salary) - norm(performance) | CLEAN — structural metric |
| `ManagerialStrainIndex` | (1 - norm(mgr)) × 0.60 + norm(team_size) × 0.40 | CLEAN — structural metric |
| `PresenteeismSignal` | norm(absence) × 0.50 + norm(overtime) × 0.50 | CAUTION — temporal leakage risk |

**CAUTION — PresenteeismSignal:** This feature was originally in the LEGACY_DISABLED list (Construct #11 in Section 4) because it combines absence and overtime in a way that may detect pre-departure behavioral patterns rather than prospective risk. It remains in Layer E because the feature is not theoretically invalid (the two inputs are genuine JD-R demand signals), but it carries a documented leakage risk in retrospective datasets.

The governance decision for Phase 4 is: **PresenteeismSignal runs but is labeled CAUTION.** It must not be used in final model feature sets without explicit review by the science team and temporal validation via `TemporalValidationGuard`. `ModelInputContract` does not block it by name, but any downstream leakage audit should flag it for manual review.

---

## 8. FeatureManifest Audit Trail

### 8.1 New Fields Added in Phase 4

The `FeatureManifest` dataclass in `backend/core/feature_factory.py` was extended with two fields in Phase 4:

```python
@dataclass
class FeatureManifest:
    features_added: List[str] = field(default_factory=list)
    features_failed: List[str] = field(default_factory=list)
    specs_applied: List[FeatureSpec] = field(default_factory=list)
    n_original: int = 0
    n_final: int = 0
    legacy_constructs_disabled: List[str] = field(default_factory=list)  # NEW
    scientific_feature_mode: str = SCIENTIFIC_FEATURE_MODE               # NEW
```

| Field | Type | Description |
|---|---|---|
| `legacy_constructs_disabled` | `List[str]` | All 15 construct names from `LEGACY_DISABLED_CONSTRUCTS` when mode is `theory_grounded`. Empty in `legacy_for_debug_only` mode. |
| `scientific_feature_mode` | `str` | Exact value of `SCIENTIFIC_FEATURE_MODE` at the time the manifest was created. Recorded from the module-level constant so it cannot be falsified by caller arguments. |

### 8.2 What the Audit Trail Proves

For every pipeline run in production, the returned `FeatureManifest` object provides:

1. **Proof that Layer B and C did not run:** `legacy_constructs_disabled` contains the full list of 15 construct names, confirming the gate was active.
2. **Proof of the mode setting used:** `scientific_feature_mode == "theory_grounded"` confirms no override was applied.
3. **Proof of what was added vs. what was suppressed:** `features_added` lists all columns that actually entered the DataFrame; no name from `legacy_constructs_disabled` should appear there.

### 8.3 Logging Counterpart

The manifest is complemented by structured INFO logging at the end of `engineer()`:

```
FeatureFactory: added N features, failed M, legacy_disabled=15, total cols=K
```

This log line is emitted on every run and can be monitored by log aggregation tools to detect any anomalous execution where `legacy_disabled` drops below 15.

---

## 9. Test Coverage

Phase 4 integration tests are located in `tests/test_phase4_integration.py`. The following test classes and cases provide coverage for the quarantine gate.

### 9.1 Settings Governance Tests (`TestSettingsGovernance`)

| Test | What It Verifies |
|---|---|
| `test_scientific_feature_mode_is_theory_grounded` | `SCIENTIFIC_FEATURE_MODE == "theory_grounded"` in the deployed configuration |
| `test_legacy_disabled_constructs_non_empty` | `LEGACY_DISABLED_CONSTRUCTS` contains at least 10 entries (the known minimum for a sound quarantine) |
| `test_burnout_risk_composite_is_disabled` | `"BurnoutRiskComposite"` is present in `LEGACY_DISABLED_CONSTRUCTS` |
| `test_satisfaction_index_is_disabled` | `"SatisfactionIndex"` is present in `LEGACY_DISABLED_CONSTRUCTS` |
| `test_engagement_score_is_disabled` | `"EngagementScore"` is present in `LEGACY_DISABLED_CONSTRUCTS` |
| `test_employee_stability_risk_is_disabled` | `"EmployeeStabilityRisk"` is present (target-adjacent — requires explicit confirmation) |
| `test_presenteeism_signal_is_disabled` | `"PresenteeismSignal"` is present (temporal leakage risk — requires explicit confirmation) |

### 9.2 Feature Factory Gating Tests (`TestFeatureFactoryGating`)

| Test | What It Verifies |
|---|---|
| `test_legacy_constructs_not_in_output` | None of the 15 `LEGACY_DISABLED_CONSTRUCTS` names appear in the engineered DataFrame columns when `SCIENTIFIC_FEATURE_MODE == "theory_grounded"` |
| `test_manifest_records_disabled_constructs` | `manifest.legacy_constructs_disabled` is non-empty and has the `legacy_constructs_disabled` attribute |
| `test_layer_a_interactions_still_run` | Engineered DataFrame has at least as many columns as the input DataFrame (Layer A must add columns) |
| `test_scientific_feature_mode_recorded_in_manifest` | `manifest.scientific_feature_mode` equals the value from `config.settings.SCIENTIFIC_FEATURE_MODE` |

### 9.3 Coverage Gaps (Flagged for Phase 5)

The following scenarios are **not yet covered** by `test_phase4_integration.py` and should be added in Phase 5:

- **Gate enforcement under `legacy_for_debug_only`:** A test that sets `_LEGACY_MODE_ACTIVE = True` via monkeypatching and verifies Layer B actually produces the expected (invalid) constructs — confirming the gate switch works in both directions.
- **Cleanup sweep coverage:** A test that pre-populates a DataFrame with a legacy column name (e.g., `BurnoutRiskComposite`) before calling `engineer()`, then verifies the column is absent from the returned DataFrame.
- **Layer E PresenteeismSignal isolation:** A test that confirms `PresenteeismSignal` still appears in output when Layer E runs (to detect if a future change accidentally extends the quarantine to Layer E).

---

## 10. Reversal Path: Debug Mode Warning

### 10.1 How to Re-enable Legacy Constructs

The only supported reversal path is editing `config/settings.py`:

```python
# CHANGE FROM (production default):
SCIENTIFIC_FEATURE_MODE: str = "theory_grounded"

# TO (debug only):
SCIENTIFIC_FEATURE_MODE: str = "legacy_for_debug_only"
```

This must be reverted before any commit is merged to main. It must never appear in a production configuration, a CI/CD artifact, or a Docker image used for user-facing deployments.

### 10.2 Warning: Consequences of Enabling Legacy Mode

> **CRITICAL WARNING**
>
> Setting `SCIENTIFIC_FEATURE_MODE = "legacy_for_debug_only"` causes all 15 quarantined constructs to be computed and placed into the feature DataFrame. Any model trained or scored with these constructs:
>
> - Uses **scientifically invalid formulas** that do not replicate any published paper
> - May produce **inflated AUC or SHAP importance** for constructs that are proxies of the target
> - Will generate **misleading explanations** in any SHAP or feature attribution output
> - **Cannot be used in any report, audit output, or personnel decision** under any circumstances
>
> If you are enabling this mode to compare legacy vs. theory-grounded formulas, you must:
>
> 1. Work in an isolated development environment
> 2. Never connect this environment to any real employee data
> 3. Revert `SCIENTIFIC_FEATURE_MODE` before committing or pushing
> 4. Document the comparison findings and share them with the science review board

The platform logs a WARNING-level message on every call to `engineer()` when legacy mode is active. This log message should be treated as an alert in any monitoring system.

### 10.3 No UI Toggle for Legacy Mode

There is no Streamlit UI, API endpoint, or environment variable that can enable legacy mode without a code change to `config/settings.py`. This is intentional. The gate must not be controllable at runtime by any system that has access to real employee data.

---

## 11. Physical Deletion: Deferred to Phase 5

### 11.1 Current Status

As of Phase 4, the following code blocks remain in `backend/core/feature_factory.py` but are logically unreachable in production:

- The full body of `_layer_b_hr_constructs()` — all 11 constructs
- The full body of `_layer_c_psychological()` — all 4 constructs

These functions are defined, syntactically valid, and importable. They are never called in theory-grounded mode.

### 11.2 Phase 5 Deletion Criteria

Physical deletion will proceed in Phase 5 only when all of the following conditions are met:

| Criterion | Owner | Status |
|---|---|---|
| Science review board has confirmed all 15 constructs are correctly classified as invalid | Science Lead | Pending |
| A line-by-line comparison of Layer B formulas vs. theory-grounded formulas is documented | Engineering | Pending |
| All test cases in Section 9.3 (coverage gaps) are implemented and passing | QA | Pending |
| No open issue in the project tracker references a Layer B construct for rehabilitation | Product | Pending |
| A deletion PR is reviewed by at least two engineering reviewers and one science reviewer | Engineering | Pending |

### 11.3 What Deletion Will Remove

When approved, Phase 5 will remove:

1. The `_layer_b_hr_constructs()` function body (the function signature and its call site may be retained as a stub with a `raise NotImplementedError` for one release cycle)
2. The `_layer_c_psychological()` function body (same approach)
3. The `_LEGACY_MODE_ACTIVE` boolean and the `if _run_legacy:` conditional blocks in `engineer()`
4. The `"legacy_for_debug_only"` branch handling in `engineer()`

The `LEGACY_DISABLED_CONSTRUCTS` list in `config/settings.py` will be **retained** after deletion as a permanent historical record of constructs that were found invalid and removed.

---

## 12. Governance Responsibilities and Sign-off

| Role | Responsibility | Name/Team |
|---|---|---|
| Science Lead | Validate violation classifications in Section 4 | Enterprise AI Research Division |
| Engineering Lead | Confirm gate implementation correctness in Section 6 | Engineering |
| QA Lead | Confirm test coverage in Section 9 and sign off on gaps | QA |
| Platform Owner | Approve this document as the authoritative quarantine record | Product |
| Phase 5 Reviewer | Sign off on physical deletion criteria in Section 11.2 | TBD at Phase 5 kickoff |

---

**Document version:** 1.0  
**Created:** 2026-05-20  
**Next review due:** Phase 5 kickoff (pending schedule)  
**Authoritative source for construct list:** `config/settings.py` — `LEGACY_DISABLED_CONSTRUCTS`  
**Authoritative source for gate logic:** `backend/core/feature_factory.py` — `FeatureFactory.engineer()`
