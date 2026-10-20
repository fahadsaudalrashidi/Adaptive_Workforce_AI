# Theory-Grounded Construct Activation Engine — Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Phase 2 — Theory-Grounded Construct Activation for Saudi HR Datasets  
**Module:** `backend/core/theory_grounded_construct_engine.py`

---

## Purpose

This engine computes the 7 psychological constructs defined in the paper's Table IV
using Phase 1 ConstructMapping objects as input evidence.

It does NOT:
- Retrain models or modify `ml_router.py`
- Change any UI or dashboard output
- Invent constructs beyond the 7 paper-defined ones
- Normalise inputs before formula application
- Silently substitute weak or invalid columns

---

## Architecture

```
Phase 1 output (Dict[str, ConstructMapping])
    │
    ├─ _resolve_column(target_construct)
    │     ├─ evidence_strength ∈ {DIRECT, STRONG_PROXY}     required
    │     ├─ semantic_confidence ≥ 0.70                      required
    │     ├─ scale_confidence ≥ 0.70                         required
    │     ├─ leakage_flag == False                           required
    │     └─ Priority: DIRECT > STRONG_PROXY > sem_conf
    │
    ├─ _determine_mode(resolved)
    │     ├─ All DIRECT → DIRECT_PAPER_REPLICATION
    │     └─ Any STRONG_PROXY → THEORY_COMPATIBLE_PROXY
    │
    ├─ Formula computation (no normalisation)
    │     ├─ OverTime binarised transparently when continuous (+0.10 penalty)
    │     └─ WorkLifeBalance rescaled when not 1–4 (+0.10 or +0.15 penalty)
    │
    └─ _compute_base_confidence(input_mappings, mode, extra_penalty)
          ├─ DIRECT base: 0.95
          ├─ PROXY base:  0.80
          ├─ Per STRONG_PROXY input: −0.08
          ├─ Per binarisation: −0.10
          └─ Per WLB rescale: −0.10 (1-5) or −0.15 (0-100)
```

---

## The Seven Paper Constructs

### Formula 1: SatisfactionIndex
**Theory:** COR (caravan of resources) + FFM (inverse Neuroticism)  
**Formula:** `(JobSatisfaction + EnvironmentSatisfaction + RelationshipSatisfaction + WorkLifeBalance) / 4`  
**Required inputs:** All four satisfaction dimensions — no partial computation  
**Range:** 1.0 – 4.0 on IBM HR Likert scales  
**DIRECT requires:** JobSatisfaction, EnvironmentSatisfaction, RelationshipSatisfaction, WorkLifeBalance (exact IBM names)

### Formula 2: BurnoutRisk
**Theory:** JD-R (health-impairment pathway) + COR (energy resource depletion)  
**Formula:** `OverTime_binary × (5 − WorkLifeBalance)`  
**Required inputs:** OverTime (binary gate) AND WorkLifeBalance (1–4 scale)  
**Range:** 0 (no overtime OR perfect WLB) to 4 (OT=1 and WLB=1)  
**Critical governance:**
- WorkPressure CANNOT substitute OverTime — theoretically distinct constructs
- Absence CANNOT substitute WorkLifeBalance — different behavioural mechanism
- WLB scale direction assumed: 1=Poor, 4=Excellent

### Formula 3: EngagementScore
**Theory:** JD-R (motivational pathway) + FFM (Conscientiousness) + Kahn 1990  
**Formula:** `JobInvolvement × JobSatisfaction`  
**Required inputs:** Both simultaneously — multiplicative form is non-negotiable  
**Critical governance:**
- Generic EmployeeEngagement scores CANNOT substitute either input
- Kahn simultaneity: zero involvement OR zero satisfaction → zero engagement

### Formula 4: TenureRatio
**Theory:** COR (condition resource) + Mobley 1977 (Stage 1 evaluation anchor)  
**Formula:** `YearsAtCompany / (TotalWorkingYears + 1)`  
**Required inputs:** Both YearsAtCompany and TotalWorkingYears  
**+1:** Paper-specified to prevent division by zero for fresh graduates  
**Signal:** High value (~0.85) = career loyalist; Low value (~0.10) = frequent mover

### Formula 5: IncomePerLevel
**Theory:** COR (object resource) + Adams Equity Theory 1963  
**Formula:** `MonthlyIncome / (JobLevel + 1)`  
**Required inputs:** MonthlyIncome AND JobLevel  
**+1:** Prevents division by zero at JobLevel = 0  
**Signal:** Rank-relative compensation fairness, NOT absolute underpayment  
**Saudi context:** MonthlyIncome in SAR (5,000–30,000 range) — values not scaled

### Formula 6: CareerProgression
**Theory:** COR (resource gain velocity) + JD-R (growth resource adequacy)  
**Formula:** `JobLevel / (YearsAtCompany + 1)`  
**Required inputs:** JobLevel AND YearsAtCompany  
**Signal:** High = fast advancement; Low = stagnation (known attrition antecedent)

### Formula 7: SalaryGrowth
**Theory:** JD-R + FFM + Siegrist Effort-Reward Imbalance 1996  
**Formula:** `PercentSalaryHike × PerformanceRating`  
**Required inputs:** PercentSalaryHike AND PerformanceRating  
**Multiplicative form mandatory:** Reward must match performance (ERI logic)  
**Signal:** High hike + low performance → misaligned; Low hike + high performance → imbalance

---

## Activation Modes

| Mode | Trigger | Confidence Ceiling |
|------|---------|--------------------|
| `DIRECT_PAPER_REPLICATION` | All inputs are DIRECT evidence | 0.95 |
| `THEORY_COMPATIBLE_PROXY` | Any input is STRONG_PROXY | 0.80 |
| `BLOCKED_INSUFFICIENT_EVIDENCE` | Required input missing or below threshold | — |
| `BLOCKED_WEAK_PROXY` | Only WEAK_PROXY columns available | — |
| `BLOCKED_LEAKAGE_RISK` | Required column has leakage_flag=True | — |
| `BLOCKED_SCALE_INVALID` | OverTime or WLB cannot be safely converted | — |

---

## Evidence Quality Thresholds

Both thresholds must be met for a column to be accepted:

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| `semantic_confidence` | ≥ 0.70 | Minimum theory compatibility |
| `scale_confidence` | ≥ 0.70 | Minimum measurement validity |

Columns failing either threshold are treated as missing — the construct is blocked.

---

## Confidence Calculation

```
base = 0.95 (DIRECT) or 0.80 (PROXY)

penalties:
  − 0.08  per STRONG_PROXY input
  − 0.10  OverTime binarization (continuous → binary)
  − 0.10  WorkLifeBalance 1-5 rescaled to 1-4
  − 0.15  WorkLifeBalance 0-100 rescaled to 1-4

final = max(0.30, base − total_penalties)
```

Confidence is never 1.00. DIRECT ceiling is 0.95. PROXY ceiling is 0.80.

---

## OverTime Binarisation Rules

| Detected Form | Conversion | Penalty |
|---------------|------------|---------|
| Yes/No/Y/N strings | Map to 1/0 | 0.00 |
| Numeric {0, 1} | Unchanged | 0.00 |
| Continuous hours (max > 1) | >0 → 1, =0 → 0 | 0.10 |
| Unrecognisable values | Blocked | — |

---

## WorkLifeBalance Scale Adjustment Rules

| Detected Scale | Rescaling Formula | Penalty |
|----------------|-------------------|---------|
| 1–4 (expected) | No change | 0.00 |
| 1–5 Likert | `wlb_4 = 1 + (wlb_5 − 1) × 0.75` | 0.10 |
| 0–100 percentage | `wlb_4 = 1 + wlb_100 × 0.03` | 0.15 |
| Other | Blocked | — |

---

## Governance Rules

| Rule | Detail |
|------|--------|
| No WorkPressure → OverTime | Theoretically distinct; WorkPressure maps to JD-R demand, not binary gate |
| No Absence → BurnoutRisk | Absence is STRUCTURAL_HR_BASELINE behavioural indicator only |
| No EmployeeEngagement → JobInvolvement | Composite scores miss Kahn simultaneity requirement |
| No normalisation before formula | Interaction semantics destroyed by z-score/min-max |
| No partial SatisfactionIndex | All 4 satisfaction dimensions required by COR caravan principle |
| No leakage inputs | AttritionRisk, RetentionRisk, ExitReason always blocked |
| No WEAK_PROXY inputs | Confidence below threshold; construct blocked, not approximated |
| No silent substitution | Missing inputs explicitly reported in BlockedConstruct.missing_inputs |

---

## Saudi HR Context Adaptations

### Payroll-Only Datasets
- TenureRatio, IncomePerLevel, CareerProgression may be computable
- SatisfactionIndex, BurnoutRisk, EngagementScore, SalaryGrowth typically blocked
- Construct engine reports which are blocked and why

### Survey-Based Datasets
- All 7 constructs potentially computable as THEORY_COMPATIBLE_PROXY
- Saudi Likert synonyms (Arabic or English) accepted at STRONG_PROXY level
- Scale validation critical: survey instruments may use 5-point instead of 4-point

### HRIS Mixed Exports
- Primary target: camelCase/PascalCase column names handled by Phase 1 normalisation
- Phase 2 receives ConstructMapping objects — language normalisation already done

### SAR Currency
- IncomePerLevel uses SAR values directly (5,000–30,000 range)
- No currency conversion or scaling applied
- MonthlyIncome scale validation: `mean ≥ 1000` threshold satisfied

---

## Output Contract

### ConstructResult (computed constructs)
| Field | Type | Description |
|-------|------|-------------|
| `construct_name` | str | One of the 7 paper constructs |
| `formula_used` | str | Exact formula with actual column names |
| `source_columns` | List[str] | Original column names from dataset |
| `source_constructs` | List[str] | Mapped construct names used |
| `theory_anchor` | str | Theoretical framework reference |
| `activation_mode` | str | DIRECT or PROXY |
| `evidence_strength` | str | Worst among all inputs |
| `semantic_confidence` | float | Minimum among all inputs |
| `scale_confidence` | float | Minimum among all inputs |
| `construct_confidence` | float | Final after all penalties |
| `proxy_penalty` | float | Total penalties applied |
| `leakage_status` | str | Always "CLEAN" for computed constructs |
| `governance_notes` | List[str] | Scientific cautions and warnings |
| `limitations` | List[str] | Known approximation limitations |
| `values` | pd.Series | Computed column values |

### BlockedConstruct (failed activations)
| Field | Type | Description |
|-------|------|-------------|
| `construct_name` | str | Name of blocked construct |
| `activation_mode` | str | BLOCKED_* variant |
| `blocking_reason` | str | Human-readable explanation |
| `missing_inputs` | List[str] | Which required construct names absent |
| `governance_notes` | List[str] | Scientific rationale for blocking |

---

## Test Results

| Test Scenario | Tests | Status |
|---------------|-------|--------|
| Scenario 1: IBM exact dataset — all 7 formulas | 12 | ✅ PASS |
| Scenario 2: Saudi proxy dataset — PROXY mode | 5 | ✅ PASS |
| Scenario 3: Weak-proxy columns blocked | 3 | ✅ PASS |
| Scenario 4: Leakage-flagged columns blocked | 3 | ✅ PASS |
| Scenario 5: Missing required inputs block constructs | 9 | ✅ PASS |
| Scenario 6: BurnoutRisk governance (no WorkPressure) | 4 | ✅ PASS |
| Scenario 7: Absence governance (never burnout evidence) | 3 | ✅ PASS |
| Scenario 8: No normalisation applied before formula | 5 | ✅ PASS |
| Scenario 9: Confidence downgraded for proxy constructs | 7 | ✅ PASS |
| Scenario 10: Construct metadata produced correctly | 10 | ✅ PASS |
| **Phase 2 Total** | **61** | **✅ 61/61 PASS** |

Phase 1 test suite: **67/67 PASS** (no regressions)  
Pre-existing test suite: **79/79 PASS** (no regressions)  
**Full suite: 207/207 PASS**

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| WLB scale direction not verified | If dataset uses 1=Good, 4=Poor, BurnoutRisk inverts | Governance note warns; HR review required |
| OverTime continuous binarisation loses granularity | 1 overtime hour = same as 40 | Confidence penalised 0.10; warn in governance_notes |
| Multiplicative EngagementScore inflated by scale choice | JI×JS on Likert 1-4 = range 1-16, not a normed score | No normalisation applied — use relative comparisons only |
| CareerProgression and IncomePerLevel share JobLevel | If JobLevel column is missing, both are blocked together | Report both in blocked_constructs.missing_inputs |
| No imputation for NaN values | Missing rows produce NaN in output | Formula computation proceeds; NaN propagation is correct behaviour |
| Saudi survey proxy mappings not validated psychometrically | Scale equivalence between Arabic survey and IBM Likert unverified | THEORY_COMPATIBLE_PROXY label; human construct validity review recommended |

---

## Do NOT Proceed Until

**Phase 3 (model integration) must NOT begin until:**
- All Phase 2 acceptance criteria confirmed (61 tests pass ✅)
- Column mapping for target dataset reviewed by HR analyst
- Governance decisions made for any proxy activations
- Theory-grounded construct outputs inspected for distribution validity
- BurnoutRisk WLB scale direction verified against dataset documentation

---

## Next Recommended Phase

**Phase 3 — Feature Factory Reconstruction**

Given Phase 2 construct values:
1. Replace `feature_factory.py` computations with exact paper formulas
2. Wire `TheoryAwareColumnMapper` + `TheoryGroundedConstructEngine` into the training pipeline
3. Ablation tests: 6 model variants (paper Table VI) — ONLY after Phase 2 audit sign-off
4. Truth auditor receives construct confidence metadata
5. Log which constructs were DIRECT vs PROXY in every training run

**Do NOT begin Phase 3 until:**
- Phase 2 audit reviewed and signed off
- Target dataset column mapping completed
- BurnoutRisk governance decisions finalised
