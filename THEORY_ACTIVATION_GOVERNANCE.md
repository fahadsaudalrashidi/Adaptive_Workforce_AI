# Theory Activation Governance
**Module:** `backend/core/theory_grounded_construct_engine.py`, `backend/core/model_input_contract.py`
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

The theory engine computes exactly 7 constructs grounded in five peer-reviewed organizational theories. This document governs which constructs activate, under what evidence conditions, what happens when evidence is insufficient, and how the Model Input Contract enforces that only theory-grounded constructs enter the predictive model.

---

## 2. The 7 Authorized Theory Constructs

These are the only constructs whose names appear in `_VALID_THEORY_CONSTRUCTS`. No other construct names are permitted.

| Construct | Theoretical Basis | Required Columns |
|---|---|---|
| `SatisfactionIndex` | COR Theory (Hobfoll 1989) + JD-R Model (Bakker & Demerouti 2007) | JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction |
| `BurnoutRisk` | JD-R Model — demands-resources imbalance | OverTime, WorkLifeBalance, JobInvolvement |
| `EngagementScore` | JD-R Model — resource activation | JobInvolvement, WorkLifeBalance, JobSatisfaction |
| `TenureRatio` | Mobley Turnover Process (1977) — job embeddedness | YearsAtCompany, TotalWorkingYears |
| `IncomePerLevel` | Adams Equity Theory (1963) — comparison standard | MonthlyIncome, JobLevel |
| `CareerProgression` | Mobley Turnover Process — advancement perception | YearsInCurrentRole, YearsAtCompany, JobLevel |
| `SalaryGrowth` | Adams Equity Theory — reward proportionality | PercentSalaryHike, YearsAtCompany |

**LOCK REQUIREMENT:** These names, their theoretical citations, and their column dependencies are frozen to the research paper. Any modification requires explicit paper citation of the changed formula.

---

## 3. Construct Activation Criteria

### 3.1 Evidence Threshold

A construct activates only when all required columns are present in the dataset AND contain sufficient non-null values to produce a statistically meaningful result. The engine checks:

1. **Column presence** — all required columns must exist (case-insensitive match via `TheoryAwareColumnMapper`)
2. **Non-null ratio** — at least 80% non-null values per required column
3. **Variance** — the column must not be constant (zero variance blocked constructs produce NaN ratios)

When any check fails, the construct is added to `ConstructActivationReport.blocked_constructs` with a reason string, not silently dropped.

### 3.2 Activation Report

`ConstructActivationReport` fields:
- `construct_results` — dict mapping construct name → computed Series (or None if blocked)
- `blocked_constructs` — dict mapping construct name → reason string
- `constructed_df` — input DataFrame with activated constructs appended as new columns
- `activation_notes` — list of human-readable audit notes

**No `activated_constructs` attribute exists.** Code that reads `report.activated_constructs` will raise `AttributeError`. The correct access pattern is `report.construct_results.keys()`.

### 3.3 What Triggers Blocking (Not Rejection)

Blocking is governance-neutral — it means the data does not support computing the construct, not that the construct is invalid:

| Blocking Reason | Example |
|---|---|
| Missing required column | `TenureRatio` blocked when `TotalWorkingYears` absent |
| All-null column | Column exists but 100% NaN |
| Constant column | `WorkLifeBalance` always = 3 (no variance to differentiate employees) |
| Divide-by-zero guard | `TenureRatio` when `TotalWorkingYears == 0` for all rows |

Blocked constructs do NOT propagate to `constructed_df`. The Model Input Contract handles the downstream consequence.

---

## 4. The Layer B / Layer C Quarantine

### 4.1 LEGACY_DISABLED_CONSTRUCTS (15 constructs)

These 15 construct names are blocked from entering the model under all circumstances:

```
BurnoutRiskComposite, SatisfactionIndex (Layer B), EngagementScore (Layer B),
RetentionRisk, CareerProgressionScore, CompensationEquity, WorkLifeBalanceRisk,
ManagerialSupportIndex, EmployeeStabilityRisk, AbsenteeismPressureIndex,
PresenteeismSignal, PsychologicalWellbeingScore, PsychologicalVariabilityIndex,
PositiveAffectIndex, NegativeAffectIndex
```

**Why these were quarantined:** These constructs were engineered in earlier pipeline versions using statistical aggregation and domain intuition rather than published theory formulas. Several (`BurnoutRiskComposite`, `RetentionRisk`) are obvious target-adjacent proxies. Others (`PsychologicalWellbeingScore`, `PresenteeismSignal`) synthesize psychological states from HR metrics in ways that have no published empirical basis and introduce unquantifiable construct validity threats.

**The naming collision problem:** `SatisfactionIndex` and `EngagementScore` appear in BOTH `LEGACY_DISABLED_CONSTRUCTS` (their Layer B invalid versions) AND `_VALID_THEORY_CONSTRUCTS` (their correct theory engine output). The resolution is priority-based:

- Layer B versions: computed by arbitrary aggregation, quarantined.
- Theory engine versions: computed by exact paper formulas, pre-approved.

### 4.2 Model Input Contract — Check #0

`ModelInputContract.validate()` processes features in this order:

```python
# 0. Theory-grounded constructs are pre-approved — skip all pattern checks.
if feat in _VALID_THEORY_CONSTRUCTS:
    continue  # → approved_features

# 1–6. All other checks (leakage, ID memorization, etc.)
```

Check #0 fires before any pattern-matching check. This ensures:
- `SatisfactionIndex` (theory engine output) is never blocked by the "index" substring match in check #5 (ID memorization patterns)
- `EngagementScore` (theory engine output) is never blocked by the legacy disabled check
- No valid theory construct is accidentally quarantined by substring pattern collisions

### 4.3 SCIENTIFIC_FEATURE_MODE

| Mode | Behavior |
|---|---|
| `"theory_grounded"` (default) | Theory engine runs; legacy constructs blocked |
| `"legacy_for_debug_only"` | Theory engine runs; legacy constructs allowed with warning |
| `"legacy_disabled"` | Theory engine skipped; legacy constructs blocked (emergency mode) |

The mode is read from settings at startup and cannot be changed mid-request.

---

## 5. `FeatureManifest` Extensions (Phase 5)

The `FeatureManifest` returned by `_factory.engineer()` now includes:

| Field | Type | Purpose |
|---|---|---|
| `legacy_constructs_disabled` | bool | True when quarantine is active |
| `scientific_feature_mode` | str | Current SCIENTIFIC_FEATURE_MODE value |

These fields are logged with every training run and stored in model artifacts to ensure reproducibility.

---

## 6. Governance Invariants

1. **Theory constructs cannot be renamed** — renaming `SatisfactionIndex` to `satisfaction_score` would break the theoretical citation chain. Column mapper uses case-insensitive matching; the construct name in the output DataFrame must be the exact string from `_VALID_THEORY_CONSTRUCTS`.

2. **Theory constructs cannot be silently repaired** — if `SatisfactionIndex` cannot be computed because `RelationshipSatisfaction` is absent, it is blocked and logged, not approximated using available columns.

3. **Theory construct formulas cannot be simplified** — `TenureRatio = YearsAtCompany / (TotalWorkingYears + ε)` cannot be replaced with `YearsAtCompany` alone, even if the two are highly correlated.

4. **Unsupported constructs cannot activate** — a construct not in `_VALID_THEORY_CONSTRUCTS` cannot enter `constructed_df` regardless of how it is named in upstream code.

5. **The contract validates before training** — `ModelInputContract.validate()` runs before any model sees the feature matrix. This is enforced in `backend/api/main.py` by architectural position (contract runs after engineering, before model call).

---

## 7. Mandatory Stop Conditions

STOP IMMEDIATELY and halt the training pipeline if:

| Condition | Detection Method |
|---|---|
| A theory formula has been altered | Compare `_FORMULA_CHECKSUMS` (in engine module) against stored hashes |
| An unsupported construct appears in `constructed_df` | Any column not in `_VALID_THEORY_CONSTRUCTS ∪ original_columns` |
| Leakage bypass attempted | Target column present in `approved_features` |
| Temporal contamination detected | `TemporalValidationReport.has_temporal_risk == True` with CRITICAL severity |
| Governance disabled | `SCIENTIFIC_FEATURE_MODE` changed to non-standard value at runtime |
| Calibration unreliable | `CalibrationReliabilityReport.overall_reliability == "CRITICAL"` |
| Scientific traceability breaks | Any construct in output lacks `theoretical_basis` citation |

---

## 8. Test Coverage

`tests/test_phase4_integration.py::TestModelInputContractBlocking` (6 tests) and `TestModelInputContractApproval` (3 tests) cover:

- Legacy constructs are blocked
- Theory constructs pass check #0 and are approved
- `SatisfactionIndex` is not blocked by "index" substring match
- `EngagementScore` is not blocked by legacy disabled check
- Target column is blocked regardless of theory status
- Proxy leakage columns are blocked

All 302 tests pass. No theory-construct activation regressions detected.

---

## 9. Future Governance

If the research paper is updated to add an 8th construct:
1. Add construct name to `_VALID_THEORY_CONSTRUCTS`
2. Implement computation in `theory_grounded_construct_engine.py` with paper citation
3. Add required columns to `TheoryAwareColumnMapper`
4. Add tests in `test_phase4_integration.py`
5. Update this document with the new row in Section 2

Adding a construct without paper citation is not permitted.

---

*Audit produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
