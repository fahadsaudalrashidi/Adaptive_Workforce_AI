# EXECUTIVE ROI ENGINE
## Adaptive Workforce Intelligence — Phase E Financial Impact Quantification
**Classification:** Commercial Product Design  
**Author:** Chief AI Officer / CFO Advisory  
**Date:** June 2026  
**Status:** Ready for Implementation

---

## STRATEGIC RATIONALE

Executives buy platforms when the financial return is clear. "Your attrition risk is 63/100" is interesting. "Your attrition costs you SAR 12.4 million per year, and we can reduce that by SAR 4.1 million within 6 months" is a purchase decision.

This document specifies a complete ROI quantification engine, grounded in established HR finance methodology (SHRM, Deloitte, McKinsey Human Capital), adapted for the Saudi market.

**Critical Design Principle:** All financial estimates are:
- Clearly labeled as **estimates based on industry models**
- Shown with **ranges, not point estimates only**
- Allow HR teams to **input their own cost data** to override defaults
- NEVER presented as guaranteed financial outcomes

---

## MODULE 1: COST OF ATTRITION ESTIMATOR

### Methodology

The cost of attrition model follows the Cascio-Boudreau framework (2011) with Saudi market calibration.

### Cost Components

```
Total Attrition Cost = Separation Cost + Recruitment Cost + Onboarding Cost + Productivity Loss
```

#### 1.1 Separation Cost
```
Separation Cost per Departure = 
    Exit Interview Admin:           SAR 500 – 1,500
  + HR Administrative Processing:  SAR 800 – 2,000
  + Final Settlement (GOSI, EOSB): 3.33% × AnnualSalary × YearsOfService
  + Remaining Leave Encashment:    (UnusedDays / 260) × AnnualSalary

Saudi Default (if EOSB data unavailable):
  SeparationCost = 0.15 × AnnualSalary per departing employee
```

#### 1.2 Recruitment Cost
```
Recruitment Cost per Hire =
    Job Posting / Headhunter:    8-20% of AnnualSalary (Saudi market: 12-18%)
  + Recruitment Platform Fees:  SAR 3,000 – 15,000 per hire
  + HR Recruiter Time:          40-80 hours × (HRSalary / 2080)
  + Interview Panels:           6-12 hours × (InterviewerAvgSalary / 2080) × 3 interviewers
  + Visa / Iqama (for expats):  SAR 8,000 – 25,000 per expatriate hire
  + Relocation (if applicable): SAR 15,000 – 80,000

Saudi Default:
  RecruitmentCost = 0.25 × AnnualSalary for Saudi nationals
  RecruitmentCost = 0.40 × AnnualSalary for expatriate professionals
```

#### 1.3 Onboarding / Integration Cost
```
OnboardingCost =
    Orientation Programs:        SAR 2,000 – 8,000
  + IT Setup / Equipment:       SAR 5,000 – 25,000
  + Training (role-specific):   10-15% of AnnualSalary
  + Mentor Time:                40-80 hours × MentorSalary / 2080
  + Productivity Ramp Time:     see productivity loss model below

Saudi Default:
  OnboardingCost = 0.12 × AnnualSalary
```

#### 1.4 Productivity Loss Cost
```
ProductivityLoss =
    Vacancy Period Productivity Gap:
      VacancyDays × (AnnualSalary / 260) × ProductivityGapFactor(0.70)
      [70% of salary lost in productivity while position vacant]
      Average Saudi vacancy period: 45-90 days

    New Hire Ramp Period:
      RampDays × (AnnualSalary / 260) × RampFactor
      RampFactor by role level:
        - Frontline:  60 days at 60% productivity
        - Mid-level:  90 days at 40% productivity
        - Senior:     180 days at 30% productivity
        - Leadership: 365 days at 20% productivity
```

### Total Cost Multiplier (by Role Level)

Based on SHRM and adapted Cascio-Boudreau for Saudi context:

| Role Level | Annual Salary Range (SAR) | Cost Multiplier | Typical Total Cost |
|------------|--------------------------|-----------------|-------------------|
| Frontline / Operational | 40,000–80,000 | 0.75×–1.25× | SAR 30K–100K |
| Professional / Specialist | 80,000–200,000 | 1.5×–2.0× | SAR 120K–400K |
| Senior / Manager | 200,000–500,000 | 2.0×–3.0× | SAR 400K–1.5M |
| Director / Executive | 500,000+ | 3.0×–5.0× | SAR 1.5M–5M+ |

### Saudi Benchmark Defaults (When Dataset Lacks Salary Data)

If the client dataset does not contain salary columns, AWI uses industry defaults:

| Sector | Avg Annual Salary (SAR) | Replacement Cost per Departure |
|--------|------------------------|-------------------------------|
| Banking (Saudi national) | 120,000 | SAR 180,000–240,000 |
| O&G / Petrochemicals | 180,000 | SAR 270,000–540,000 |
| Telecom / Technology | 150,000 | SAR 225,000–300,000 |
| Government / Semi-gov | 90,000 | SAR 90,000–180,000 |
| Retail / Services | 45,000 | SAR 33,750–56,250 |
| Healthcare | 130,000 | SAR 195,000–390,000 |

---

## MODULE 2: ANNUAL ATTRITION COST CALCULATOR

### Computation

```python
def compute_annual_attrition_cost(
    total_employees: int,
    priority_review_count: int,
    strategic_concern_count: int,
    avg_annual_salary_sar: float,
    sector: str,
    salary_data_available: bool,
) -> AttritionCostEstimate:
    
    # Estimate attrition rate from risk bands
    # Priority Review → ~60% probability of departure in 12 months (conservative estimate)
    # Strategic Concern → ~25% probability of departure in 12 months
    # Monitoring → ~8% probability
    # Stable → ~3% probability
    
    expected_departures = (
        priority_review_count × 0.55 +     # conservative: not 60%
        strategic_concern_count × 0.22 +   # conservative: not 25%
        monitoring_count × 0.07 +          # conservative
        stable_count × 0.02               # baseline turnover
    )
    
    # Apply replacement cost model
    replacement_cost_per_person = get_replacement_cost(avg_annual_salary_sar, sector)
    
    total_annual_cost = expected_departures × replacement_cost_per_person
    
    return AttritionCostEstimate(
        expected_departures_low  = expected_departures × 0.7,
        expected_departures_mid  = expected_departures,
        expected_departures_high = expected_departures × 1.4,
        cost_low_sar   = total_annual_cost × 0.7,
        cost_mid_sar   = total_annual_cost,
        cost_high_sar  = total_annual_cost × 1.4,
        cost_per_departure_sar = replacement_cost_per_person,
        methodology_note = "Based on Conservative Cascio-Boudreau model...",
        disclaimer = "These are statistical estimates...",
    )
```

---

## MODULE 3: RETENTION INTERVENTION ROI CALCULATOR

### ROI Framework

For each simulation scenario, the ROI engine computes:

```
Net ROI = Attrition Cost Avoided - Intervention Cost
ROI%    = Net ROI / Intervention Cost × 100
Payback = Intervention Cost / (Monthly Cost Avoided)
```

### Intervention Cost Database

| Intervention | Cost Estimate | Basis |
|-------------|---------------|-------|
| Salary increase 5% | 5% × payroll | Direct payroll cost |
| Salary increase 10% | 10% × payroll | Direct payroll cost |
| Training program (light) | SAR 3,000/employee/year | SHRM benchmark |
| Training program (intensive) | SAR 12,000/employee/year | Executive education rates |
| Manager coaching program | SAR 25,000/manager/year | ICF coaching rates |
| Internal mobility platform | SAR 500K–2M one-time | Vendor benchmarks |
| Engagement program | SAR 2,000/employee/year | Industry average |
| Work-life balance policies | SAR 1,500/employee/year | Administrative + infrastructure |
| Burnout reduction program | SAR 5,000/employee/year | EAP + wellness costs |
| Promotion acceleration | Role-salary-dependent | Individual basis |

### Example ROI Output (Saudi Dataset)

```
═══════════════════════════════════════════════════════════════
        RETENTION ROI ANALYSIS — SAUDI WORKFORCE DATASET
═══════════════════════════════════════════════════════════════
Dataset:          Saudi HR Dataset (1,191 employees)
Avg Salary:       SAR 120,000 (industry default: Saudi mixed sector)
Sector:           Mixed / Corporate

CURRENT STATE
─────────────
  Total Employees:         1,191
  Priority Review:            7  (0.6%)
  Strategic Concern:        141  (11.8%)
  Expected Annual Departures: ~40 (conservative estimate)
  Estimated Annual Cost:    SAR 6.1M – 9.8M
  Mid-Point Estimate:       SAR 7.9M per year

RECOMMENDED SCENARIO: Improve Job Opportunities + Training
─────────────────────────────────────────────────────────
  Estimated Risk Reduction:  6.5% (combined)
  Expected Departure Reduction: ~11 fewer departures per year
  Cost Avoided (Mid):        SAR 2.1M per year
  
  Intervention Cost:
    Internal Mobility Program:  SAR 800,000 (one-time)
    Training Access Enhancement:SAR 475,000 per year
    Total Year 1 Investment:    SAR 1,275,000

  Net ROI (Year 1):           SAR 825,000
  Net ROI (Year 2+):          SAR 1,625,000 per year
  ROI Percentage:             65% (Year 1) → 342% (Year 2+)
  Payback Period:             7.3 months

CONFIDENCE: Medium — Based on feature-importance-driven estimate
DISCLAIMER: Statistical associations. Individual outcomes will vary.
═══════════════════════════════════════════════════════════════
```

---

## MODULE 4: TALENT LOSS COST MODEL

### Beyond Replacement: The Real Cost of Talent Loss

Standard models count replacement costs. The talent loss model adds the invisible costs:

#### 4.1 Knowledge Loss Cost
```
KnowledgeLossCost = 
    TenureYears × LearningRate × AnnualSalary × AccumulationFactor

Where:
  LearningRate = 0.15 (15% of salary in knowledge value per year — Davenport et al.)
  AccumulationFactor = 1 - (1/(1 + 0.1×TenureYears))  (diminishing returns)

For a 10-year employee on SAR 150,000:
  KnowledgeLoss = 10 × 0.15 × 150,000 × 0.63 = SAR 141,750
```

#### 4.2 Network Disruption Cost
```
NetworkDisruptionCost = 
  If DepartingEmployee is a "connector" (high-centrality in org chart):
    DirectionalImpact × AffectedTeamSize × AverageProductivityDip × 90 days
  Else:
    0.05 × AnnualSalary (minor network disruption)
```

#### 4.3 Client Relationship Cost
```
ClientRelationshipCost (for client-facing roles):
  Estimated as 1.5× – 3× annual salary for senior client-facing departures
  Applied to: Sales, Account Management, Key Account Directors
```

#### 4.4 Cultural / Morale Contagion Cost
```
MoraleContagionCost = 
  VisibleDepartures × AffectedTeamSize × AvgSalary × 0.05 × ContagionDuration_months / 12
  
  Where VisibleDepartures are Priority Review employees who are visible to peers
  ContagionDuration: 2-4 months typically
```

---

## MODULE 5: TRAINING ROI MODEL

### Training Investment vs. Retention ROI

```
TrainingROI =
    Direct Benefit:     (AttritionReductionFromTraining × ReplacementCost)
  + Productivity Gain:  (SkillGainFactor × AffectedEmployees × AvgSalary × 0.08)
  + Safety Improvement: (If applicable — SAR 50,000 per incident avoided)
  - Training Cost:      (ProgramCost + LostProductivity during training)

TrainingROI% = (TotalBenefit - TrainingCost) / TrainingCost × 100
```

### Typical Training ROI Ranges (Saudi Market)
| Training Type | Cost per Employee | ROI Range | Payback |
|--------------|-------------------|-----------|---------|
| E-learning / Self-paced | SAR 1,500/year | 200–400% | 3-6 months |
| Classroom / Instructor-led | SAR 8,000/year | 150–300% | 6-12 months |
| Leadership development | SAR 30,000/year | 100–250% | 12-24 months |
| Executive coaching | SAR 80,000/year | 80–200% | 18-36 months |
| Technical certification | SAR 5,000/year | 300–600% | 2-4 months |

---

## MODULE 6: PRODUCTIVITY LOSS MODEL

### Vacancy and Ramp Productivity Gap

```
ProductivityGapCost = VacancyCost + RampCost

VacancyCost:
  = VacancyDays × DailyProductivityValue × ProductivityGapFactor
  DailyProductivityValue = AnnualSalary / 260
  ProductivityGapFactor = 0.70  (70% of salary value lost while vacant)
  AvgVacancyDays by sector:
    Technology: 68 days
    Banking: 45 days
    O&G: 52 days
    Healthcare: 75 days
    Government: 30 days (faster internal transfers)

RampCost:
  = RampDays × DailyProductivityValue × (1 - FullProductivityFactor)
  FullProductivityFactor by level:
    Frontline: 0.70 at 60 days
    Professional: 0.50 at 90 days
    Manager: 0.35 at 150 days
    Director: 0.25 at 240 days
    Executive: 0.15 at 365 days
```

---

## FRONTEND IMPLEMENTATION: ROI DASHBOARD

### ROI Panel in ExecutiveDashboard.tsx

```
┌────────────────────────────────────────────────────────────────┐
│  FINANCIAL IMPACT INTELLIGENCE                                  │
│                                                                 │
│  CURRENT ANNUAL ATTRITION COST          INTERVENTION SAVINGS   │
│  SAR 7.9M / year (estimated)            SAR 2.1M / year         │
│  Range: SAR 6.1M – 9.8M                 with recommended plan   │
│                                                                  │
│  ──────────────────────────────────────────────────────────── │
│  BREAKDOWN PER DEPARTURE          COST BY DEPARTURE TYPE        │
│  Replacement:    SAR 120,000      Priority Review:  SAR 840K    │
│  Productivity:   SAR  58,000      Strategic Concern: SAR 7.1M   │
│  Knowledge Loss: SAR  42,000      Normal Turnover:  Included    │
│  Total:          SAR 220,000                                    │
│                                                                  │
│  ──────────────────────────────────────────────────────────── │
│  TOP ROI SCENARIOS                                              │
│  1. Improve Job Opportunities: ROI 330%, Payback 2.8mo          │
│  2. Expand Training Access:    ROI 215%, Payback 5.6mo          │
│  3. Promote Fairly:            ROI 180%, Payback 7.2mo          │
│                                                                  │
│  [View Full ROI Report]  [Customize Assumptions]                │
│                                                                  │
│  DISCLAIMER: Financial estimates based on industry models.      │
│  Input your actual cost data for precise calculations.          │
└────────────────────────────────────────────────────────────────┘
```

---

## BACKEND MODULE SPECIFICATION

### New Module: `backend/core/retention_roi_engine.py`

```python
"""
Retention ROI Engine — Phase E.
Computes financial impact of attrition and interventions.
All estimates are clearly labeled as statistical estimates with ranges.
No guarantee of financial outcomes — human financial judgment required.
"""

@dataclass
class AttritionCostEstimate:
    expected_departures_low:   float
    expected_departures_mid:   float
    expected_departures_high:  float
    cost_low_sar:              float
    cost_mid_sar:              float
    cost_high_sar:             float
    cost_per_departure_sar:    float
    annual_cost_breakdown:     dict   # separation, recruitment, onboarding, productivity
    sector_benchmark_used:     str
    salary_data_source:        str    # 'provided' or 'industry_default'
    methodology:               str
    disclaimer:                str    # Mandatory

@dataclass
class InterventionROI:
    intervention_name:         str
    intervention_cost_sar:     float
    cost_avoided_per_year_sar: float
    net_roi_year1_sar:         float
    net_roi_year2_sar:         float
    roi_percentage_year1:      float
    roi_percentage_year2:      float
    payback_months:            float
    confidence_level:          str
    assumptions:               list[str]
    disclaimer:                str

class RetentionROIEngine:
    def estimate_attrition_cost(
        self,
        scored_result: EmployeeRiskResult,
        avg_salary_sar: float | None = None,
        sector: str = 'mixed',
    ) -> AttritionCostEstimate: ...
    
    def compute_intervention_roi(
        self,
        attrition_estimate: AttritionCostEstimate,
        intervention: InterventionLever,
        predicted_reduction_pct: float,
        intervention_cost_sar: float,
    ) -> InterventionROI: ...
    
    def generate_roi_report(
        self,
        scored_result: EmployeeRiskResult,
        scenarios: list[WorkforceSimulationScenario],
    ) -> ROIReport: ...
```

---

## PRICING TOOL FOR AWI SALES

### AWI's Own ROI Justification

The ROI engine should be used to justify AWI's own purchase price:

```
AWI PURCHASE JUSTIFICATION (for a 1,000-employee client):

  Estimated Current Attrition Cost:        SAR 8.0M/year
  Expected Improvement with AWI:           15–25% reduction in high-risk attrition
  Expected Annual Savings:                 SAR 1.2M – 2.0M/year
  AWI Enterprise License:                  SAR 350,000/year
  
  Net Benefit:                             SAR 850K – 1.65M/year
  ROI on AWI License:                      240% – 470%
  Payback Period:                          2.1 – 3.5 months
```

This becomes the first page of every sales conversation.

---

*Financial models based on: SHRM 2023 Employee Benefits Survey, Deloitte Global Human Capital Trends 2024, Cascio & Boudreau (2011) "Investing in People," McKinsey "The War for Talent 2022," and Saudi GOSI workforce statistics 2023.*
