# EXECUTIVE INDEX FRAMEWORK
## Adaptive Workforce Intelligence — Phase C Strategic Intelligence Indices
**Classification:** Product Design — Proprietary Methodology  
**Author:** Chief AI Officer / Chief Product Officer  
**Date:** June 2026  
**Status:** Approved for Implementation

---

## STRATEGIC RATIONALE

Executives do not process raw ML scores. They process indices — bounded, branded, comparable, intuitive measures that synthesize complexity into decision-ready signals. This framework defines six proprietary executive indices that transform AWI from a "prediction system" into an "Executive Workforce Decision Platform."

Each index is:
- Bounded 0–100 for comparability
- Computed from real data (no fake inputs)
- Explainable (driver decomposition available)
- Graded (letter grade A–F with narrative interpretation)
- Benchmarkable (industry positioning once benchmark database is built)
- Bilingual (EN/AR labels and narratives)

---

## INDEX 1: WORKFORCE STABILITY INDEX (WSI)

### Definition
**WSI** measures the organization's current workforce stability — the degree to which the workforce is operating from a position of strength, engagement, and commitment rather than withdrawal, disengagement, or active job-seeking.

**Scale:** 0 (Complete Instability) → 100 (Complete Stability)  
**Target Grade:** A (80+)  
**Alert Level:** D/F (<60)

### Computation Methodology

```
WSI = w1 × StableRatio + w2 × InverseRiskScore + w3 × ConstructHealthScore + w4 × ModelConfidenceBonus

Where:
  StableRatio        = (Stable + Monitoring employees) / TotalEmployees × 100
  InverseRiskScore   = 100 - AverageRiskScore_0_100
  ConstructHealthScore = MatchedConstructCount / 25 × 100   (25 = max expected constructs)
  ModelConfidenceBonus = if ROC_AUC > 0.75 then min((ROC_AUC - 0.50) / 0.50 × 100, 100) else 0

  w1 = 0.40  (composition of workforce by band — most direct)
  w2 = 0.35  (inverted average risk — individual-level signal)
  w3 = 0.15  (data quality / construct coverage — confidence weight)
  w4 = 0.10  (ML validation confidence bonus)
```

### Grade Thresholds
| Grade | Range | Interpretation |
|-------|-------|----------------|
| A | 80–100 | Excellent stability. Workforce in strong position. |
| B | 70–79 | Good stability. Minor monitoring required. |
| C | 60–69 | Moderate risk. Targeted interventions needed. |
| D | 50–59 | Elevated instability. Leadership attention required. |
| F | 0–49 | Critical instability. Executive action required immediately. |

### Executive Narrative Template
> "The Workforce Stability Index stands at **{WSI}/100** (Grade **{Grade}**), indicating **{interpretation}**. The primary stability enablers are **{top protective factors}**. The primary stability threats are **{top risk drivers}**."

### Arabic Label
مؤشر استقرار القوى العاملة (WSI)

---

## INDEX 2: RETENTION HEALTH INDEX (RHI)

### Definition
**RHI** measures the organization's ability to retain its workforce — specifically its capacity to sustain employee commitment, satisfaction, and organizational attachment over the next 12-month horizon.

**Scale:** 0 (Severely Unhealthy Retention Environment) → 100 (Optimal Retention Health)  
**Target Grade:** B+ (75+)  
**Alert Level:** D (<60)

### Computation Methodology

```
RHI = w1 × InverseFlightRiskConcentration + w2 × EquityScore + w3 × EngagementProxy + w4 × DeptVarianceScore

Where:
  InverseFlightRiskConcentration = 100 - (PriorityReview% + StrategicConcern% × 0.5) × 100
  EquityScore = if EquityTheoryConstructAvailable:
                  100 - (equity_driver_employee_count / TotalEmployees × 200)
                else: 50  (neutral when data unavailable)
  EngagementProxy = (CommitmentConstructScore + JobSatisfactionConstructScore) / 2
                    where each = 100 × (1 - scaled_negative_loading)
  DeptVarianceScore = 100 - (StdDev(DeptAvgRiskScores) × 2)  — penalizes high variance
                      clamped to [0, 100]

  w1 = 0.40  (flight risk composition — most direct retention metric)
  w2 = 0.25  (equity perception — theoretical retention driver)
  w3 = 0.20  (engagement proxies — available from theory constructs)
  w4 = 0.15  (departmental variance — identifies systemic vs. isolated risk)
```

### Retention Risk Bands
| Band | RHI Range | Projected 12mo Attrition Range |
|------|-----------|-------------------------------|
| Optimal | 80–100 | 0–8% voluntary attrition |
| Healthy | 65–79 | 8–15% |
| At-Risk | 50–64 | 15–25% |
| Distressed | 35–49 | 25–40% |
| Critical | 0–34 | 40%+ |

### Arabic Label
مؤشر صحة الاستبقاء (RHI)

---

## INDEX 3: TALENT FLIGHT RISK INDEX (TFRI)

### Definition
**TFRI** is an inversion of retention health — it quantifies the organization's exposure to unwanted voluntary turnover of its most critical talent segments in the near term (30–90 days horizon).

Unlike WSI (which is stable and strategic), TFRI is **tactical and urgent** — it tells leadership "what is happening right now" with flight-risk concentration.

**Scale:** 0 (No material flight risk) → 100 (Critical mass of workforce at immediate risk)  
**Target Grade:** A (<20 — low risk is desirable)  
**Alert Level:** D/F (>50)

### Computation Methodology

```
TFRI = w1 × PriorityReviewConcentration + w2 × RiskAcceleration + w3 × CriticalRoleExposure + w4 × DeptConcentration

Where:
  PriorityReviewConcentration = (PriorityReview / Total) × 100 × 3.0  (3x weight — most urgent band)
  StrategicConcernContribution = (StrategicConcern / Total) × 100 × 1.5
  RawFlight = PriorityReviewConcentration + StrategicConcernContribution
  NormalizedFlight = min(RawFlight, 100)

  RiskAcceleration = if MultipleAnalysesAvailable:
                       max(0, CurrentAvgRisk - PreviousAvgRisk) × 5
                     else: 0  (no acceleration signal without historical data)

  CriticalRoleExposure = HighRiskDeptCount / TotalDeptCount × 100
                         where HighRiskDept = dept with avg_risk > 60

  DeptConcentration = if any single dept has > 30% PriorityReview: +15 concentration bonus

  w1 = 0.50, w2 = 0.20, w3 = 0.20, w4 = 0.10
  Final TFRI clamped to [0, 100]
```

### TFRI Action Protocol
| TFRI | Color | Executive Action Required |
|------|-------|--------------------------|
| 0–20 | Green | Monitor quarterly |
| 21–35 | Blue | HR Manager review, department check-ins |
| 36–50 | Amber | CHRO escalation, targeted retention packages |
| 51–65 | Orange | CEO attention, emergency retention budget |
| 66–100 | Red | Board-level crisis response |

### Arabic Label
مؤشر مخاطر هروب المواهب (TFRI)

---

## INDEX 4: LEADERSHIP STABILITY INDEX (LSI)

### Definition
**LSI** measures the stability and strength of leadership-level talent specifically — the degree to which director, senior manager, and leadership positions are occupied by stable, engaged employees rather than flight-risk individuals.

Leadership attrition is 3–5× more costly than frontline attrition and carries organizational knowledge loss, culture disruption, and external signaling risk that are disproportionate to headcount.

**Scale:** 0 (Leadership bench severely at risk) → 100 (Leadership deeply stable)  
**Target Grade:** A (80+)  
**Alert Level:** C (<65)

### Computation Methodology

```
LSI = w1 × LeadershipStableRatio + w2 × TenureWeightedScore + w3 × InverseLeadershipRisk

Where:
  LeadershipStableRatio:
    If job_level / seniority columns present in dataset:
      = (Leaders in Stable band / Total Leaders) × 100
    Else (fallback, most datasets):
      = Top-20%-tenure employees' Stable rate × 100
      where "Top 20% tenure" approximates leadership cohort

  TenureWeightedScore = Avg(RiskScore of employees with YearsAtCompany > median) 
                        converted: (100 - AvgRisk) for high-tenure cohort
                        Falls back to InverseRiskScore if tenure not available

  InverseLeadershipRisk = if DeptSummary available:
                            100 - (count(depts where avg_risk > 55) / TotalDepts × 100)
                          else: 75 (conservative neutral default)

  w1 = 0.45, w2 = 0.35, w3 = 0.20
```

### Arabic Label
مؤشر استقرار القيادة (LSI)

---

## INDEX 5: ORGANIZATIONAL RESILIENCE INDEX (ORI)

### Definition
**ORI** measures the organization's capacity to withstand, adapt to, and recover from workforce disruptions — talent loss, department crises, knowledge drain, and structural shocks.

A highly resilient organization has distributed risk (no single department catastrophically exposed), broad talent depth, strong succession indicators, and moderate risk variance across functions.

**Scale:** 0 (Structurally fragile) → 100 (Highly resilient)  
**Target Grade:** B+ (75+)  
**Alert Level:** D (<55)

### Computation Methodology

```
ORI = w1 × RiskDistributionScore + w2 × DepartmentDiversityScore + w3 × ConstructCoverageScore + w4 × GovernanceBonus

Where:
  RiskDistributionScore:
    Gini = Gini coefficient of per-department average risk scores
    RiskDistributionScore = (1 - Gini) × 100
    — High Gini (concentrated risk in one dept) = low resilience
    — Low Gini (risk spread evenly) = high resilience

  DepartmentDiversityScore:
    = (DeptCount / max(DeptCount, 10)) × 100  (normalized dept count)
    — More departments = more resilient (redundancy)
    Clamped to [20, 100] — single-dept orgs get 20, not 0

  ConstructCoverageScore:
    = (MatchedConstructCount / 25) × 100
    — Better theory coverage = more reliable resilience measurement

  GovernanceBonus:
    = if ReadinessLevel == 'READY': +10
      elif ReadinessLevel == 'CONDITIONAL': +5
      else: 0

  w1 = 0.45, w2 = 0.25, w3 = 0.20, w4 = 0.10
  Final ORI clamped to [0, 100]
```

### Arabic Label
مؤشر المرونة التنظيمية (ORI)

---

## INDEX 6: HUMAN CAPITAL RISK INDEX (HCRI)

### Definition
**HCRI** is the composite, board-level headline index — the single number that encapsulates the organization's overall workforce risk exposure. It is the "credit rating" of the workforce, designed for board reporting, executive dashboards, and benchmarking.

HCRI synthesizes all five prior indices into one executive-level signal.

**Scale:** 0 (No material human capital risk) → 100 (Extreme human capital risk exposure)  
**Target Grade:** A (<25 risk is desirable for this inverse index)  
**Alert Level:** D/F (>50)

### Computation Methodology

```
HCRI = w1 × InverseWSI + w2 × InverseRHI + w3 × TFRI + w4 × InverseLSI + w5 × InverseORI

Where:
  InverseWSI  = 100 - WSI    (stability becoming risk)
  InverseRHI  = 100 - RHI    (retention health becoming retention risk)
  TFRI        = TFRI          (already expressed as risk, no inversion needed)
  InverseLSI  = 100 - LSI    (leadership stability becoming leadership risk)
  InverseORI  = 100 - ORI    (resilience becoming fragility)

  w1 = 0.20 (WSI contribution — strategic stability)
  w2 = 0.25 (RHI contribution — retention is most directly controllable)
  w3 = 0.25 (TFRI contribution — most urgent signal)
  w4 = 0.20 (LSI contribution — leadership risk is highest impact)
  w5 = 0.10 (ORI contribution — resilience is a longer-term structural factor)
```

### HCRI Board Interpretation
| HCRI | Rating | Board Action |
|------|--------|-------------|
| 0–20 | AAA | No action required. Monitor annually. |
| 21–30 | AA | Healthy. Quarterly HR reporting sufficient. |
| 31–40 | A | Moderate. CHRO presents to board semi-annually. |
| 41–50 | BBB | Elevated. Board HR Committee review recommended. |
| 51–60 | BB | Significant. Board agenda item — strategic retention plan required. |
| 61–75 | B | High. Emergency retention fund. Executive attention. |
| 76–100 | CCC/D | Critical. Organizational crisis response. Chairman escalation. |

### Arabic Label
مؤشر مخاطر رأس المال البشري (HCRI)

---

## IMPLEMENTATION SPECIFICATION

### Computation Location
All six indices must be computed in `backend/core/executive_index_engine.py` — a new module that accepts the output of `EmployeeRiskScorer.score_dataframe()` and returns `ExecutiveIndexResult`.

### Integration Points

```python
@dataclass
class ExecutiveIndexResult:
    wsi:   float          # Workforce Stability Index 0-100
    rhi:   float          # Retention Health Index 0-100
    tfri:  float          # Talent Flight Risk Index 0-100
    lsi:   float          # Leadership Stability Index 0-100
    ori:   float          # Organizational Resilience Index 0-100
    hcri:  float          # Human Capital Risk Index 0-100

    wsi_grade:  str       # A/B/C/D/F
    rhi_grade:  str
    tfri_grade: str       # Note: lower TFRI is better (A = low risk)
    lsi_grade:  str
    ori_grade:  str
    hcri_grade: str       # Note: lower HCRI is better

    wsi_narrative_en:  str
    wsi_narrative_ar:  str
    hcri_narrative_en: str
    hcri_narrative_ar: str

    drivers: dict          # Top 3 drivers for each index
    computed_at: str       # ISO timestamp
    governance_note: str   # Mandatory statistical disclaimer
```

### API Surface
- Returned as part of `/api/local/upload/analyze-with-employees` response
- Added to `result_json` in SQLite database
- Exposed in `EmployeeRiskData.executiveIndices` TypeScript interface
- Displayed on Executive Dashboard (KPI cards)
- Included in Board Report Section 2

### Dashboard KPI Card Layout
```
┌──────────────────────────────────────────────────────┐
│  HUMAN CAPITAL RISK INDEX         HCRI   38/100  [A] │
│  ──────────────────────────────────────────────────  │
│  WSI  72  [B]   RHI  68  [C]   TFRI  24  [A]        │
│  LSI  80  [A]   ORI  65  [B]                         │
│                                                      │
│  Primary Risk: Retention Health — Operations Dept    │
│  Primary Strength: Leadership Stability — C-Suite    │
└──────────────────────────────────────────────────────┘
```

### Governance Requirements
1. Every index display MUST include: "Statistical associations from organizational data. Not predictive of individual employee behavior."
2. Grade thresholds MUST be disclosed in all reports.
3. Index computation methodology MUST be available on demand (one-click methodology PDF).
4. Indices MUST NOT be used as the sole basis for employment decisions.
5. All six indices MUST appear together — cherry-picking individual indices is prohibited in reporting.

---

## BENCHMARKING ROADMAP

Once a dataset of 10+ client analyses is accumulated, benchmark the indices:

### Saudi Sector Benchmarks (Target Year 1)
| Sector | Expected WSI Range | Expected HCRI Range |
|--------|-------------------|---------------------|
| Saudi Banking | 65–75 | 30–45 |
| Saudi O&G | 70–80 | 25–40 |
| Saudi Telecom | 60–72 | 35–50 |
| Saudi Retail | 50–65 | 40–60 |
| Saudi Government | 72–85 | 20–35 |
| Saudi Technology | 55–70 | 35–55 |

Benchmark positioning language: "Your HCRI of 38 places you in the **top quartile** of Saudi financial services organizations in our index. The sector median is 46."

---

*Methodologies are based on established organizational behavior theories (COR, JD-R, Mobley) and validated against the Saudi attrition dataset (ROC-AUC 0.82, N=1,191). Index weights are validated through sensitivity analysis. All indices require re-validation with each new client dataset.*
