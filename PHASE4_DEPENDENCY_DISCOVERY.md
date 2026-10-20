# Phase 4 — Dependency Discovery Report
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** All imports and usages of FeatureFactory, legacy Layer B constructs, and theory engine modules

---

## Pipeline Architecture (Current State)

```
Dataset Upload
    │
    ├─ DatasetProfiler.profile()
    ├─ SemanticMapper.map(df)                  → SemanticMap
    ├─ AdaptiveRouter.route()                  → RoutingDecision
    ├─ DataHealer.fit_transform(df, sem_map)   → df_clean
    │
    ├─ FeatureFactory.engineer(df_clean, ...)  ← PROBLEMATIC STEP
    │     ├─ Layer A: numeric interactions     (SAFE — no theory claims)
    │     ├─ Layer B: HR constructs            (UNSAFE — wrong formulas)
    │     ├─ Layer C: psychological survey     (UNSAFE — invented constructs)
    │     ├─ Layer D: temporal features        (SAFE — no theory claims)
    │     └─ Layer E: organizational stress    (CAUTION — some theory claims)
    │
    ├─ MLRouter.train(df_eng, features, target) → TrainingResult
    └─ Risk / Insights / Reports
```

**Theory engines (Phase 1-2) NOT yet wired into this pipeline:**
```
TheoryAwareColumnMapper.map(df)              → Dict[str, ConstructMapping]
TheoryGroundedConstructEngine.compute(df, mappings) → ConstructActivationReport
```

---

## Task Group 1: FeatureFactory Import Map

| File | Line | Usage | Safety | Proposed Action |
|------|------|-------|--------|-----------------|
| `backend/api/main.py` | 43 | `from backend.core.feature_factory import FeatureFactory` | UNSAFE | Keep import; gate Layer B in engineer() |
| `backend/api/main.py` | 62 | `_factory = FeatureFactory()` singleton | UNSAFE | Keep; behavior governed by SCIENTIFIC_FEATURE_MODE |
| `backend/api/main.py` | 208 | `_factory.engineer(df_clean, sem_map, ...)` | UNSAFE | Integrate theory engine BEFORE this call |
| `frontend/app.py` | 76 | `from backend.core.feature_factory import FeatureFactory` | UNSAFE | Keep import; gated by mode flag |
| `frontend/app.py` | 127 | `FeatureFactory()` singleton in session dict | UNSAFE | Keep; gated |
| `tests/test_e2e.py` | 29 | `from backend.core.feature_factory import FeatureFactory` | TEST | Update to use theory engine in theory_grounded mode |
| `_smoke_test.py` | 52 | Import + instantiation | TOOL | Keep for debug mode |
| `_trace_target.py` | 7 | Import + instantiation | TOOL | Keep for debug mode |
| `frontend/utils/session_state.py` | 90 | Import + singleton | UNSAFE | Keep; gated by mode flag |

**Risk if changed:** Breaking main.py would disable the entire analysis pipeline. Changes must be additive/gated, not substitutive.

---

## Task Group 2: Legacy Layer B Construct Usage Map

### Constructs Computed in feature_factory.py Layer B

| Construct | Line | Formula Used | Paper Formula | Scientific Status |
|-----------|------|-------------|---------------|-------------------|
| `BurnoutRiskComposite` | 147 | `_norm(OT)×0.40 + _norm(WL)×0.35 + (1-_norm(SAT))×0.25` | `OverTime_binary × (5 − WLB)` | **SCIENTIFICALLY INVALID** |
| `SatisfactionIndex` | 154 | `_norm(sat)×0.55 + _norm(eng)×0.45` | `(JS+ES+RS+WLB)/4` | **SCIENTIFICALLY INVALID** |
| `EngagementScore` | 160 | `_norm(eng)` single-source | `JobInvolvement × JobSatisfaction` | **SCIENTIFICALLY INVALID** |
| `RetentionRisk` | 172 | Weighted composite (5 inputs) | Not in paper | **INVENTED — NO PAPER ANCHOR** |
| `CareerProgressionScore` | 175 | `_norm(perf)×0.40 + _norm(prom)×0.35 + _norm(trn)×0.25` | `JobLevel / (YearsAtCompany+1)` | **SCIENTIFICALLY INVALID** |
| `CompensationEquity` | 182 | `_norm(sal) / (_norm(ten)+0.1)` | `MonthlyIncome / (JobLevel+1)` | **WRONG DENOMINATOR** |
| `WorkLifeBalanceRisk` | 187 | `_norm(OT)×0.50 + _norm(dist)×0.30 + _norm(WL)×0.20` | Not in paper | **INVENTED** |
| `ManagerialSupportIndex` | 194 | `_norm(mgr)` | Not in paper | **INVENTED** |
| `EmployeeStabilityRisk` | 198 | `(1-_norm(ten))×0.60 + (1-_norm(age))×0.40` | Not in paper | **INVENTED + TARGET-ADJACENT** |
| `AbsenteeismPressureIndex` | 204 | `_norm(abs_)` | Not in paper | **INVENTED** |

### Constructs in Layer E (Organizational Stress)

| Construct | Line | Scientific Status |
|-----------|------|-------------------|
| `WorkloadPerHeadcount` | 315 | CAUTION — no theory anchor |
| `CompensationEfficiencyGap` | 323 | CAUTION — _norm() applied |
| `PresenteeismSignal` | 333 | **HIGH RISK — absence × overtime; temporal leakage** |
| `ManagerialStrainIndex` | 341 | CAUTION — no theory anchor |

### Constructs in Layer C (Psychological Survey)

| Construct | Line | Scientific Status |
|-----------|------|-------------------|
| `PsychologicalWellbeingScore` | 232 | CAUTION — mean of unvalidated columns |
| `PsychologicalVariabilityIndex` | 236 | CAUTION — intra-individual std |
| `PositiveAffectIndex` | 243 | INVALID — splits columns by position (no theory) |
| `NegativeAffectIndex` | 244 | INVALID — column-position split |

---

## Task Group 3: Downstream Construct References

| File | Line | Construct Referenced | Risk |
|------|------|---------------------|------|
| `tests/test_construct_evidence.py` | 73 | `BurnoutRiskComposite` in test fixture | MEDIUM — test uses old construct name |
| `frontend/pages/psychological_page.py` | 22-26 | List of psych construct names for display | LOW — display only, no formula |
| `frontend/app.py` | 1775-1778 | Construct names list for visualization | LOW — display only |
| `backend/core/risk_intelligence.py` | 203 | `feature_factory` column reference | LOW — references column presence, not formula |

---

## Task Group 4: Theory Engine — Current Status

| Module | Location | Status |
|--------|----------|--------|
| `TheoryAwareColumnMapper` | `backend/core/theory_aware_column_mapper.py` | IMPLEMENTED — not wired to pipeline |
| `TheoryGroundedConstructEngine` | `backend/core/theory_grounded_construct_engine.py` | IMPLEMENTED — not wired to pipeline |
| `map_columns()` convenience fn | `theory_aware_column_mapper.py` | AVAILABLE |
| `compute_constructs()` convenience fn | `theory_grounded_construct_engine.py` | AVAILABLE |

**Both engines are fully tested (67 + 61 tests pass) and ready for pipeline integration.**

---

## Task Group 5: Semantic Mapper (Legacy Path)

| Module | Usage |
|--------|-------|
| `SemanticMapper` | Maps columns to 28 semantic categories (salary, overtime, engagement, etc.) |
| `SemanticMap` | Output: `sem_map.get(category)` returns column list |
| Used by: | `FeatureFactory._get_col()` — pulls columns by category to build Layer B constructs |

**The SemanticMapper is a different system from TheoryAwareColumnMapper:**
- `SemanticMapper` → 28 broad categories → used by FeatureFactory
- `TheoryAwareColumnMapper` → 25 specific psychological constructs with evidence quality → used by ConstructEngine

Both can run in parallel. The theory engine does NOT depend on SemanticMapper.

---

## Integration Point Summary

**Where to inject theory engine (lowest risk):**

```
backend/api/main.py — line 206–211 (BEFORE factory.engineer call):

df_clean, heal_report = healer.fit_transform(df, sem_map, target)

# ← INSERT HERE: theory mapping + construct computation
column_mappings = TheoryAwareColumnMapper().map(df_clean)
activation_report = compute_constructs(df_clean, column_mappings)
df_theory = activation_report.constructed_df  # has valid constructs added

df_eng, manifest = _factory.engineer(
    df_theory,    # ← use theory-enriched df (was: df_clean)
    sem_map, decision.dataset_type, target,
)
```

**Where to gate legacy Layer B (lowest risk):**

```
feature_factory.py — engineer() method:

# Gate: skip Layer B when in theory_grounded mode
if SCIENTIFIC_FEATURE_MODE != "theory_grounded":
    df = _layer_b_hr_constructs(df, sem_map, manifest)
    df = _layer_e_organizational(df, sem_map, manifest)
else:
    manifest.warnings = ["LEGACY_LAYER_B_DISABLED: theory_grounded mode active"]
```

---

## Risk Assessment by Change

| Change | Risk Level | Rationale |
|--------|------------|-----------|
| Add config flag to settings.py | NONE | Additive only |
| Gate Layer B in feature_factory.py | LOW | Gated by flag; existing behavior preserved in debug mode |
| Integrate theory engine in main.py | LOW | Additive; theory engine is exception-safe |
| Create model_input_contract.py | NONE | New file, no existing dependencies |
| Create temporal_validation_guard.py | NONE | New file, no existing dependencies |
| Remove Layer B constructs from feature set | MEDIUM | Downstream features (RetentionRisk) may affect display |

**VERDICT:** All changes are safe and additive. Physical file removal deferred to Phase 5.
