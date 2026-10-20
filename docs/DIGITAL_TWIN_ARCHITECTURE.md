# DIGITAL TWIN ARCHITECTURE
## Adaptive Workforce Intelligence — Phase D Workforce Digital Twin
**Classification:** Product Architecture — Proprietary  
**Author:** Chief AI Officer / Enterprise Architect  
**Date:** June 2026  
**Status:** Architecture Design — Ready for Engineering Sprints

---

## STRATEGIC RATIONALE

A "Workforce Digital Twin" is the highest-value capability in enterprise workforce analytics. It transforms AWI from a diagnostic tool into a prescriptive planning platform — the difference between a doctor telling you "you are unhealthy" versus "here is the exact intervention plan, calibrated to your biology, that will improve your health score by 15 points over 6 months."

The digital twin concept is already partially implemented in AWI through `workforce_simulation_engine.py`. This document architectures the full capability expansion.

**Market Context:**
- Deloitte's Workforce Insights charges $3M+ for bespoke digital twin implementations
- Workday's "Workday Predict" (strategic scenarios module) is priced at $500K+ per enterprise
- AWI can deliver this capability natively, grounded in theory, with governance

---

## ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                  WORKFORCE DIGITAL TWIN ENGINE                   │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  BASELINE    │   │ INTERVENTION │   │   OUTCOME PREDICTION │ │
│  │  SNAPSHOT    │ → │   LEVERS     │ → │   ENGINE             │ │
│  │  (Current)   │   │  (What-If)   │   │   (Impact Estimate)  │ │
│  └──────────────┘   └──────────────┘   └──────────────────────┘ │
│         ↓                  ↓                       ↓            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            FINANCIAL IMPACT LAYER                        │   │
│  │  Cost of Attrition | ROI of Intervention | Payback Time  │   │
│  └──────────────────────────────────────────────────────────┘   │
│         ↓                                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            TIMELINE PROJECTION LAYER                     │   │
│  │       30 days | 90 days | 180 days | 12 months           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## LAYER 1: BASELINE SNAPSHOT (Current State)

The baseline is the current-state representation of the workforce — the "digital twin at t=0."

### Baseline Data Structure

```python
@dataclass
class WorkforceBaselineSnapshot:
    # Core metrics
    total_employees:        int
    analysis_date:          str        # ISO timestamp
    avg_risk_score:         float      # 0-100
    avg_stability_score:    float      # 0-100
    
    # Band distribution
    stable_count:           int
    monitoring_count:       int
    strategic_concern_count: int
    priority_review_count:  int
    
    # Financial baseline (requires salary data or industry defaults)
    avg_annual_salary_sar:  float      # Input or industry estimate
    annual_attrition_rate:  float      # Computed or industry default
    annual_attrition_cost_sar: float   # Computed from ROI engine
    
    # Index baselines
    wsi:   float            # Workforce Stability Index
    rhi:   float            # Retention Health Index
    tfri:  float            # Talent Flight Risk Index
    hcri:  float            # Human Capital Risk Index
    
    # Risk drivers
    top_risk_drivers:       list[dict] # Top 5 org-level drivers
    top_protective_factors: list[dict]
    
    # Departmental profiles
    department_baselines:   list[DeptBaseline]
    
    # Confidence
    data_quality_score:     float      # 0-100
    confidence_level:       str        # high/medium/low
    governance_note:        str
```

---

## LAYER 2: INTERVENTION LEVERS

The following 12 intervention levers are available. Each lever has:
- A description (what the HR team does)
- Theory linkage (which organizational behavior theory explains the mechanism)
- Feature linkage (which dataset columns activate this lever)
- Conservative impact bounds (derived from meta-analyses, NOT causal claims)
- Cost model (what the intervention costs)

### LEVER 1: Increase Salary / Compensation
**Theory:** Adams Equity Theory — perceived compensation fairness drives commitment  
**Feature Keywords:** `monthly_allowance`, `salary`, `compensation`, `pay_grade`  
**Conservative Impact Bounds:**
- Risk reduction: 2–8% of avg risk score
- Stability gain: 3–10 points
- Implementation timeline: 90 days (budget cycle)
**Cost Model:**
- Input: Percentage salary increase (e.g., 10%)
- Cost: TotalPayroll × IncreasePercentage + AdministrativeCost(15% of increase)
- Breakeven: (AttritionCostAvoided - InterventionCost) / InterventionCost

### LEVER 2: Expand Training Access
**Theory:** Conservation of Resources (COR) — skill development = resource gain that buffers stress  
**Feature Keywords:** `training_access`, `training`, `learning`, `development`  
**Conservative Impact Bounds:**
- Risk reduction: 1–5% of avg risk score
- Stability gain: 2–6 points
- Implementation timeline: 60–120 days
**Cost Model:**
- Input: Training investment (SAR per employee per year)
- Typical range: SAR 3,000–15,000 per employee
- Breakeven: approximately 8–18 months based on attrition avoidance

### LEVER 3: Improve Promotion Rates / Fairness
**Theory:** Adams Equity Theory + Mobley's Withdrawal — perceived career growth drives commitment  
**Feature Keywords:** `promotion_fairness`, `promotion`, `career_growth`, `advancement`  
**Conservative Impact Bounds:**
- Risk reduction: 1–5% of avg risk score
- Stability gain: 2–7 points
- Implementation timeline: 180 days (promotion cycle alignment)
**Cost Model:**
- Input: Percentage of workforce promoted annually (increase from X% to Y%)
- Cost: ΔPromotion% × TotalEmployees × AvgPromotionIncrease × 12 months

### LEVER 4: Reduce Overtime / Workload
**Theory:** Job Demands-Resources (JD-R) — reducing demands decreases burnout and withdrawal  
**Feature Keywords:** `overtime`, `workload`, `hours`, `burnout`  
**Conservative Impact Bounds:**
- Risk reduction: 2–7% of avg risk score
- Stability gain: 3–8 points
- Implementation timeline: 30–60 days
**Cost Model:**
- Input: Overtime hours reduction target (%)
- Cost: Replacement capacity (contractors, new hires, or process efficiency)
- NOTE: Workload reduction often yields indirect savings (productivity + quality + safety)

### LEVER 5: Improve Manager Quality / Support
**Theory:** JD-R — social support (manager) = key resource that moderates demands  
**Feature Keywords:** `manager_support`, `leadership_quality`, `supervisor_satisfaction`  
**Conservative Impact Bounds:**
- Risk reduction: 2–6% of avg risk score
- Stability gain: 3–8 points
- Implementation timeline: 90–180 days (training cycles)
**Cost Model:**
- Input: Manager development investment (SAR per manager)
- Typical: SAR 10,000–50,000 per manager (coaching, training, 360 feedback)
- Breakeven: typically 12–24 months

### LEVER 6: Improve Work-Life Balance Policies
**Theory:** COR — recovery time = resource restoration preventing depletion  
**Feature Keywords:** `work_life_balance`, `flexibility`, `remote_work`  
**Conservative Impact Bounds:**
- Risk reduction: 1–4% of avg risk score
- Stability gain: 2–5 points
- Implementation timeline: 30–90 days (policy change)
**Cost Model:**
- Input: Policy cost (flexible work infrastructure, HR administration)
- Typically low marginal cost — primarily a policy and culture change

### LEVER 7: Increase Job Opportunities / Internal Mobility
**Theory:** Mobley's Withdrawal — internal alternatives reduce external job search  
**Feature Keywords:** `job_opportunities`, `internal_mobility`, `career_opportunities`  
**Conservative Impact Bounds:**
- Risk reduction: 3–8% of avg risk score (highest single lever)
- Stability gain: 4–10 points
- Implementation timeline: 90–180 days
**Cost Model:**
- Input: Internal mobility program investment
- Typical: SAR 200,000–2M for enterprise mobility platform

### LEVER 8: Strengthen Job Security / Stability Assurances
**Theory:** COR — security = fundamental resource; insecurity = severe depletion  
**Feature Keywords:** `job_stability`, `job_security`, `employment_stability`  
**Conservative Impact Bounds:**
- Risk reduction: 2–6% of avg risk score
- Stability gain: 3–7 points
- Implementation timeline: 30–60 days (communication strategy)
**Cost Model:**
- Input: Communication program cost (town halls, leadership statements)
- Low direct cost; high cultural impact

### LEVER 9: Increase Engagement Programs
**Theory:** Multiple — engagement activates multiple protective constructs simultaneously  
**Feature Keywords:** `engagement`, `emotional_commitment`, `organizational_commitment`  
**Conservative Impact Bounds:**
- Risk reduction: 1–5% of avg risk score
- Stability gain: 2–6 points
- Implementation timeline: 90 days
**Cost Model:**
- Input: Engagement program budget (SAR per employee)
- Typical: SAR 1,000–5,000 per employee per year

### LEVER 10: Saudization / Nationalization Initiatives
**Theory:** Equity Theory — perceived fairness between national and expat treatment  
**Feature Keywords:** `nationality`, `saudization`, `nitaqat`, `nationalization`  
**Conservative Impact Bounds:**
- Saudization rate improvement: defined by intervention intensity
- Risk reduction for Saudi nationals: 1–4%
- Implementation timeline: 180–365 days (structural workforce change)
**Cost Model:**
- Input: Nationalization investment (training, premium salaries, development programs)
- Regulatory context: Nitaqat compliance may reduce government fees (Levy savings)

### LEVER 11: Reduce Burnout / Psychological Safety
**Theory:** JD-R + COR — burnout is the highest-risk depletion state  
**Feature Keywords:** `burnout`, `emotional_exhaustion`, `psychological_safety`  
**Conservative Impact Bounds:**
- Risk reduction: 3–9% of avg risk score (high impact when burnout is primary driver)
- Stability gain: 4–10 points
- Implementation timeline: 60–180 days

### LEVER 12: Combined Strategy
Up to 3 levers can be combined. Combined impact is capped at 22% risk reduction and 15 stability points — conservative bounds preventing false precision.

---

## LAYER 3: OUTCOME PREDICTION ENGINE

### Prediction Methodology

The digital twin does NOT claim to predict the future with certainty. It produces **statistically-grounded scenario estimates** with explicit confidence bounds and governance disclaimers.

```python
@dataclass
class TwinOutcomePrediction:
    # Input
    lever_applied:          str
    lever_intensity:        float         # 0-1 (e.g., 0.5 = moderate implementation)
    implementation_timeline_days: int     # 30, 60, 90, 180, 365
    
    # Predicted Metrics (with confidence intervals)
    predicted_avg_risk:     float         # Point estimate
    predicted_risk_ci_lower: float        # 80% CI lower bound
    predicted_risk_ci_upper: float        # 80% CI upper bound
    
    predicted_stability:    float
    predicted_stable_count: int           # Estimated employees moving to Stable band
    predicted_priority_review_reduction: int
    
    predicted_wsi:          float         # Predicted WSI after intervention
    predicted_hcri:         float         # Predicted HCRI after intervention
    
    # Financial impact
    estimated_attrition_reduction: float  # Percentage point reduction
    estimated_cost_avoided_sar:    float  # SAR value of attrition avoided
    intervention_cost_sar:         float  # Cost of implementing intervention
    net_roi_sar:                   float  # cost_avoided - intervention_cost
    roi_percentage:                float  # net_roi / intervention_cost × 100
    payback_months:                float  # intervention_cost / (cost_avoided/12)
    
    # Confidence
    confidence_level:      str            # high/medium/low
    confidence_basis:      str            # ml_driven / driver_driven / theoretical
    
    # Governance
    governance_disclaimer: str            # Mandatory statistical disclaimer
    causal_language_guard: bool           # Confirmed: no causal certainty in output
```

### Impact Computation Algorithm

```python
def compute_twin_outcome(
    baseline: WorkforceBaselineSnapshot,
    lever: InterventionLever,
    intensity: float,        # 0.0 (minimal) to 1.0 (maximum)
    ml_validation: dict,     # For feature-importance-based estimates
    timeline_days: int,
) -> TwinOutcomePrediction:
    
    # Step 1: Determine base impact estimate
    # If ML feature importance available and lever matches a feature:
    if lever.feature_importance_score is not None:
        base_reduction = lever.feature_importance_score × intensity × 12.0
        confidence = 'high'
        basis = 'ml_driven'
    # Else if org risk driver matches lever:
    elif lever.driver_keyword_match:
        base_reduction = lever.driver_weight × intensity × 8.0
        confidence = 'medium'
        basis = 'driver_driven'
    # Else theoretical bounds:
    else:
        base_reduction = lever.theoretical_min_impact × intensity
        confidence = 'low'
        basis = 'theoretical'
    
    # Step 2: Apply timeline discount
    # Interventions take time — discount based on timeline
    timeline_factor = {30: 0.3, 60: 0.5, 90: 0.7, 180: 0.9, 365: 1.0}
    effective_reduction = base_reduction × timeline_factor.get(timeline_days, 0.7)
    
    # Step 3: Apply conservative cap
    effective_reduction = min(effective_reduction, lever.max_impact_cap)
    
    # Step 4: Apply intensity calibration (diminishing returns)
    intensity_multiplier = 1 - (0.3 × max(0, intensity - 0.7))
    effective_reduction × = intensity_multiplier
    
    # Step 5: Compute confidence interval (80% CI)
    ci_half_width = effective_reduction × (0.4 if confidence == 'low' else 0.25 if confidence == 'medium' else 0.15)
    
    # Step 6: Compute financial impact
    outcome = compute_financial_impact(baseline, effective_reduction)
    
    return TwinOutcomePrediction(...)
```

---

## LAYER 4: FINANCIAL IMPACT LAYER

### Connection to ROI Engine

The digital twin integrates directly with the ROI engine (see EXECUTIVE_ROI_ENGINE.md) to translate predicted risk reductions into SAR values.

```
Financial Impact Calculation:
──────────────────────────────────────────────────────────────────
Predicted Attrition Reduction:   3.5%  (from risk reduction estimate)
Current Annual Attrition:        18%   (observed or industry default)
New Annual Attrition:            14.5% (18% - 3.5%)
Attrition Reduction Count:       43 employees (3.5% × 1,191 employees)

Replacement Cost Per Employee:   SAR 45,000 (1.5× avg monthly salary × 3)
Total Cost Avoided:              SAR 1,935,000 per year
Intervention Cost (Training):    SAR 450,000 (1,191 × SAR 3,780)
Net ROI:                         SAR 1,485,000
ROI Percentage:                  330%
Payback Period:                  2.8 months
──────────────────────────────────────────────────────────────────
```

---

## LAYER 5: TIMELINE PROJECTION LAYER

### Phased Outcome Model

For each intervention, the twin projects outcomes across 5 time horizons:

| Horizon | Expected Realization | What's Visible |
|---------|---------------------|----------------|
| T+30 days | 30% of max impact | Communication, awareness, initial engagement |
| T+60 days | 50% | Program launch, early participants |
| T+90 days | 70% | Behavioral changes beginning, survey improvement |
| T+180 days | 90% | Full implementation, measurable retention change |
| T+365 days | 100% | Full realization, longitudinal confirmation available |

---

## USER INTERFACE: SIMULATION CONTROL PANEL

### Enhanced SimulationPanel.tsx Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  WORKFORCE DIGITAL TWIN SIMULATOR                    [Saudi Workforce] │
│                                                                        │
│  BASELINE (Current)          │  SCENARIO BUILDER                      │
│  ─────────────────           │  ─────────────────                     │
│  Total Employees: 1,191      │  Lever 1: [Salary Increase ▼] [10% ▼] │
│  Avg Risk Score:  33.5       │  Lever 2: [Training Access ▼] [High ▼] │
│  HCRI:           38/100 [A]  │  Lever 3: [— Add Lever —]              │
│  Ann. Attrition: ~18%        │                                         │
│  Attrition Cost: SAR 8.5M   │  Timeline: [90 days ▼]                  │
│                              │                                         │
│                              │  [▶ RUN SIMULATION]                     │
│──────────────────────────────│────────────────────────────────────────│
│  PREDICTED OUTCOME (90-day)  │  FINANCIAL IMPACT                       │
│  ─────────────────           │  ─────────────────                     │
│  Avg Risk Score:  29.1 ▼4.4  │  Cost Avoided:     SAR 1.94M/year      │
│  HCRI:            31/100 ▼7  │  Intervention Cost: SAR 0.45M           │
│  Stable (▲):      +52 people │  Net ROI:           SAR 1.49M           │
│  Priority Review (▼): -5     │  ROI %:             330%               │
│                              │  Payback:           2.8 months          │
│  Confidence: ■■■□□ Medium    │                                         │
│──────────────────────────────┴────────────────────────────────────────│
│  GOVERNANCE: These are statistically-grounded estimates based on       │
│  organizational associations. They do not predict individual           │
│  behavior or guarantee specific outcomes. Human judgment required.     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## BACKEND MODULE SPECIFICATION

### New Module: `backend/core/workforce_digital_twin.py`

```python
"""
Workforce Digital Twin Engine — Phase D.

Extends workforce_simulation_engine.py with:
- Multi-lever scenario composition
- Timeline-phased projections
- Financial impact integration
- Confidence intervals
- Baseline snapshot management
"""

class WorkforceDigitalTwin:
    def __init__(
        self,
        baseline: WorkforceBaselineSnapshot,
        roi_engine: RetentionROIEngine,
        index_engine: ExecutiveIndexEngine,
    ): ...
    
    def apply_lever(
        self,
        lever_id: str,
        intensity: float = 0.7,
        timeline_days: int = 90,
    ) -> TwinOutcomePrediction: ...
    
    def apply_combined_strategy(
        self,
        levers: list[tuple[str, float]],  # [(lever_id, intensity), ...]
        timeline_days: int = 180,
    ) -> TwinOutcomePrediction: ...
    
    def compare_scenarios(
        self,
        scenarios: list[TwinOutcomePrediction],
    ) -> ScenarioComparison: ...
    
    def generate_optimal_strategy(
        self,
        budget_sar: float,
        timeline_days: int = 180,
        priority: str = 'roi',  # 'roi' | 'risk_reduction' | 'speed'
    ) -> RecommendedStrategy: ...
```

---

## GOVERNANCE REQUIREMENTS FOR DIGITAL TWIN

1. **No causal language:** "may be associated with" not "will reduce"
2. **Confidence intervals required:** All predictions must show uncertainty ranges
3. **Mechanism transparency:** Every prediction must cite which theory and feature drives it
4. **Human review required:** Digital twin recommendations require HR professional review before action
5. **Audit logging:** All simulations logged with parameters, outputs, and reviewing user
6. **Recalibration trigger:** If actual attrition deviates >5% from prediction, model recalibration is triggered
7. **Disclaimer on all outputs:** Mandatory 3-sentence governance disclaimer on every simulation report

---

*Architecture based on established workforce analytics frameworks including JD-R theory, COR theory, and conservation of attrition cost methodology from SHRM/McKinsey meta-analyses. All impact estimates are conservative bounds derived from published academic literature.*
