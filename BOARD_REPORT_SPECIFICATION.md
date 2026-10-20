# BOARD REPORT SPECIFICATION
## Adaptive Workforce Intelligence — Phase F Boardroom Reporting Standard
**Classification:** Product Design — Reporting Framework  
**Quality Standard:** McKinsey / Deloitte / PwC Human Capital Practice  
**Date:** June 2026

---

## DESIGN PHILOSOPHY

Board reports are not data reports. They are **strategic decision documents**. Every page must answer the question a board member silently asks: "What does this mean for our organization, what should we do about it, and what does it cost us if we don't?"

The current AWI reporting style is technically correct but fails the board-level test. This specification defines the reporting standard for all board-level outputs.

**Design Principles:**
1. **Executive Summary First** — Board members read page 1, scan page 2, skip the rest unless alarmed
2. **Financial Impact on Every Page** — Translate every metric to SAR
3. **Red/Amber/Green on Every Section** — Visual hierarchy enables 30-second scanning
4. **Arabic and English** — Dual-language every section (Arabic on left, English on right in landscape)
5. **One Recommendation per Section** — Not findings dumps, but single prioritized actions
6. **Source Transparency** — Every number cites its source (N= sample, methodology, confidence)

---

## REPORT STRUCTURE

### COVER PAGE
```
[ORGANIZATION LOGO]

WORKFORCE INTELLIGENCE BRIEF
For the Board of Directors

[Organization Name]
Prepared by: Adaptive Workforce Intelligence Platform
Date: [Month Year]
Classification: CONFIDENTIAL — BOARD ONLY

Key Headline: [One sentence — e.g., "Workforce stability is HIGH with targeted risk in 
Operations requiring board-level attention by Q3."]
```

---

### SECTION 1: EXECUTIVE SUMMARY (Page 1 — MANDATORY READ)

**One-page synthesis. No more. No less.**

```
┌──────────────────────────────────────────────────────────────────────┐
│  EXECUTIVE SUMMARY                         الملخص التنفيذي           │
│──────────────────────────────────────────────────────────────────────│
│                                                                       │
│  WORKFORCE STATUS:  ● CONDITIONAL ATTENTION                          │
│  حالة القوى العاملة:  ● تتطلب انتباهاً مشروطاً                        │
│                                                                       │
│  Human Capital Risk Index (HCRI)    38/100    Grade: A              │
│  مؤشر مخاطر رأس المال البشري                                        │
│  ▼ Below sector average (46) — Favorable positioning                 │
│                                                                       │
│  KEY FACTS:                                                           │
│  • 1,191 employees analyzed across [X] departments                   │
│  • 148 employees (12.4%) require strategic attention                  │
│  • 7 employees (0.6%) classified Priority Review — immediate action  │
│  • Estimated annual attrition cost: SAR 7.9M                        │
│  • Recommended intervention: Job Opportunities + Training (ROI 330%) │
│                                                                       │
│  BOARD DECISION REQUIRED BY: Q3 2026                                 │
│  FINANCIAL COMMITMENT NEEDED: SAR 1.3M (intervention budget)        │
│  EXPECTED RETURN: SAR 2.1M annual cost avoidance                    │
│                                                                       │
│  CONFIDENCE: High — ML validation AUC 0.82, 1,191 employee records  │
└──────────────────────────────────────────────────────────────────────┘
```

**Executive Narrative** (3 paragraphs maximum):
- Paragraph 1: Current state (numbers + interpretation)
- Paragraph 2: Primary risk (specific, actionable)
- Paragraph 3: Recommended action (specific, with financial consequence of inaction)

---

### SECTION 2: WORKFORCE STABILITY OVERVIEW (Page 2)

**Purpose:** Give the board a simple, visual understanding of workforce health.

#### 2.1 Index Dashboard

```
WORKFORCE STABILITY DASHBOARD

Workforce Stability Index (WSI)    72/100    [B]    ▲3 vs. Last Period
Retention Health Index (RHI)       68/100    [C]    ▼2 vs. Last Period  ⚠
Talent Flight Risk Index (TFRI)    24/100    [A]    ▼1 (Improving)
Leadership Stability Index (LSI)   80/100    [A]    Stable
Organizational Resilience (ORI)    65/100    [B]    ▲1 vs. Last Period
─────────────────────────────────────────────────────────────────────
HUMAN CAPITAL RISK INDEX (HCRI)    38/100    [A]    Favorable
```

#### 2.2 Workforce Composition Chart

```
                    WORKFORCE BY RISK BAND
    
    Stable          ████████████████████████████░░  46.8% (557)
    Monitoring      ████████████████████████░░░░░░  40.8% (486)
    Strategic Concern  ██████░░░░░░░░░░░░░░░░░░░░  11.8% (141)
    Priority Review  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.6%   (7)
    
    87.6% of workforce is Stable or Monitoring — Healthy composition
    12.4% requires active HR attention — 148 employees
```

#### 2.3 Year-on-Year Comparison (if prior analyses available)

```
TREND ANALYSIS                           CHANGE VS. PRIOR PERIOD
Avg Risk Score:    33.5    (Prior: 36.1)    ▼ Improving    ✓
Strategic Concern: 141     (Prior: 167)     ▼ Improving    ✓
Priority Review:     7     (Prior: 12)      ▼ Improving    ✓
Stable:            557     (Prior: 489)     ▲ Improving    ✓
```

---

### SECTION 3: RISK LANDSCAPE (Page 3)

**Purpose:** Show where risk is concentrated and why.

#### 3.1 Top Risk Drivers (Organization-Level)

```
PRIMARY WORKFORCE RISK DRIVERS

#1  Limited Internal Job Opportunities         Affects 412 employees (34.6%)
    محدودية فرص العمل الداخلية
    Theory: Mobley's Withdrawal Model
    Action Required: Internal mobility program — SAR 800K investment
    Board Decision: Q2 2026

#2  Training Access Below Benchmark           Affects 287 employees (24.1%)
    محدودية الوصول إلى التدريب
    Theory: Conservation of Resources (COR)
    Action Required: L&D budget increase — SAR 475K additional annual
    Board Decision: Annual budget cycle — September 2026

#3  Promotion Fairness Perception             Affects 198 employees (16.6%)
    إدراك عدالة الترقية
    Theory: Adams Equity Theory
    Action Required: Transparent promotion criteria review — Minimal cost
    Board Decision: CHRO mandate — 30-day implementation

PROTECTIVE STRENGTHS:
✓  Job Stability Assurances                  Protecting 78.2% of workforce
✓  Adequate Compensation Framework           Protecting 71.3% of workforce
```

#### 3.2 Risk Driver Distribution Chart

Visual heatmap: X-axis = risk driver, Y-axis = affected employees.

#### 3.3 Governance Status

```
DATA GOVERNANCE                             COMPLIANCE STATUS
────────────────────────────────────────────────────────────
PII Columns Detected:        0              ✓ CLEAR
Leakage Columns Detected:    1 (removed)    ✓ HANDLED
Dataset Readiness:           BLOCKED→SCORED  ⚠ NOTE BELOW
ML Validation:               READY           ✓ AUC 0.82
Export Safety:               CERTIFIED       ✓ CERTIFIED
PDPL Compliance:             COMPLIANT       ✓ VERIFIED

⚠ NOTE: The Attrition column was detected and removed per governance 
protocol before ML training. This prevents data leakage and ensures 
statistical integrity. Employee scoring uses theory constructs only.
```

---

### SECTION 4: DEPARTMENT RANKINGS (Page 4)

**Purpose:** Force the board to see which departments need attention.

#### 4.1 Department Risk Ranking Table

```
DEPARTMENT RISK RANKING                               BOARD ATTENTION
──────────────────────────────────────────────────────────────────────
                         Avg    % Priority  % Strategic    Status
Department               Risk   Review      Concern
──────────────────────────────────────────────────────────────────────
1. Operations            52.1    2.8%        28.5%         🔴 HIGH RISK
2. Finance               41.3    0.9%        18.2%         🟡 MONITOR
3. Human Resources       38.7    0.5%        14.8%         🟡 MONITOR
4. Information Technology 31.2   0.2%         8.4%         🟢 STABLE
5. Sales                 28.9    0.0%         6.1%         🟢 STABLE
──────────────────────────────────────────────────────────────────────
ORGANIZATION TOTAL       33.5    0.6%        11.8%         🟡 CONDITIONAL
```

#### 4.2 Department Action Briefs

**Operations — Priority Department:**
```
OPERATIONS DEPARTMENT BRIEF
 Employees:         342  |  Avg Risk: 52.1  |  Status: 🔴 HIGH RISK

 Top Risk Drivers:
  • Limited job opportunities — 31% of Operations staff
  • High workload / overtime — 24% of Operations staff

 Financial Exposure:    SAR 2.8M in annual attrition risk
 Recommended Action:   Internal transfer pathways + workload review
 Timeline:             90 days
 Investment Required:  SAR 220,000
 Expected Saving:      SAR 840,000/year
```

---

### SECTION 5: TALENT RETENTION OUTLOOK (Page 5)

**Purpose:** Forward-looking — not just what is, but what is likely.

#### 5.1 12-Month Attrition Projection

```
TALENT RETENTION OUTLOOK — NEXT 12 MONTHS

SCENARIO A: No Action (Status Quo)
  Expected Voluntary Departures:  36–52 employees
  Estimated Cost:                 SAR 6.5M – 10.8M
  HCRI in 12 months:              Likely deteriorates to 45–52/100

SCENARIO B: Recommended Interventions Implemented
  Expected Voluntary Departures:  23–38 employees  (▼ 35% reduction)
  Estimated Cost:                 SAR 4.0M – 7.5M
  HCRI in 12 months:              Likely improves to 29–34/100
  Investment Required:            SAR 1.3M

SCENARIO C: Full Retention Program
  Expected Voluntary Departures:  15–26 employees  (▼ 55% reduction)
  Estimated Cost:                 SAR 2.5M – 5.0M
  HCRI in 12 months:              Likely improves to 22–28/100
  Investment Required:            SAR 3.2M

RECOMMENDATION: Scenario B — Best risk-adjusted ROI (330% in Year 1)
CONFIDENCE: Medium — Based on ML feature importance and theory constructs
```

#### 5.2 At-Risk Segment Summary

```
CRITICAL TALENT SEGMENTS REQUIRING BOARD ATTENTION

Segment 1: Priority Review (7 employees)
  Recommended Action: Individual retention conversations within 30 days
  HR Owner: [CHRO / VP HR]
  Financial Exposure: SAR 1.5M (if all depart)
  Urgency: IMMEDIATE

Segment 2: Operations Department at Strategic Concern Level (97 employees)
  Recommended Action: Department head briefing + workload assessment
  HR Owner: [Operations CHRO Partner]
  Financial Exposure: SAR 4.2M
  Urgency: Q2 2026

Segment 3: Finance Department Monitoring (68 employees)
  Recommended Action: Engagement check-in, career development review
  HR Owner: [Finance HRBP]
  Financial Exposure: SAR 2.8M
  Urgency: Q3 2026
```

---

### SECTION 6: KEY RISK DRIVERS (Page 6)

**Purpose:** Deep-dive on the top 3 risk drivers — behavioral theory explains WHY.

#### Format for each driver:

```
RISK DRIVER #1: LIMITED INTERNAL JOB OPPORTUNITIES
مؤشر الخطر الأول: محدودية فرص العمل الداخلية

THEORY BASIS:      Mobley's Withdrawal Model (1977)
                   Employees who perceive limited internal opportunities 
                   are statistically more likely to engage in external 
                   job search behavior.

AFFECTED EMPLOYEES: 412 (34.6% of workforce)
RISK CONCENTRATION: Highest in Operations (31%), Finance (22%)

OBSERVABLE SIGNALS:
• Employees score low on "Job Opportunities" construct (top driver)
• Cross-correlated with high "External Alternatives" construct scores
• ML feature importance: 0.18 (highest single feature)

WHAT THE ORGANIZATION CAN DO:
□ Launch internal job board with transparent posting process
□ Establish cross-departmental project participation program
□ Create formal internal transfer policy with manager accountability
□ Introduce quarterly "career conversations" with line managers

FINANCIAL IMPLICATION OF INACTION:
  412 at-risk employees × 15% departure probability = ~62 at-risk events
  × SAR 180,000 replacement cost = SAR 11.2M exposure
  HCRI impact if unaddressed: +8 points (deterioration)

RECOMMENDED BOARD ACTION:
  Authorize CHRO to implement Internal Mobility Program by Q2 2026
  Budget: SAR 800,000 one-time
  Expected ROI: 330% | Payback: 2.8 months
```

---

### SECTION 7: STRATEGIC RECOMMENDATIONS (Page 7)

**Purpose:** Clear decision framework — not options, but a prioritized action plan.

#### 7.1 Priority Action Matrix

```
STRATEGIC HR PRIORITIES FOR BOARD APPROVAL

PRIORITY 1 — INTERNAL MOBILITY PROGRAM                     [APPROVE NOW]
  Investment:   SAR 800,000 one-time
  Timeline:     90 days to launch
  Expected ROI: 330% | SAR 2.1M cost avoided in Year 1
  Risk if Delayed: HCRI deterioration to 46+ by Q4

PRIORITY 2 — TRAINING ACCESS ENHANCEMENT                   [BUDGET CYCLE]
  Investment:   SAR 475,000/year additional
  Timeline:     Q3 2026 implementation
  Expected ROI: 215% | SAR 1.02M cost avoided/year
  Risk if Delayed: Secondary risk driver remains unaddressed

PRIORITY 3 — PROMOTION TRANSPARENCY INITIATIVE             [CHRO MANDATE]
  Investment:   SAR 45,000 (process redesign, no new headcount)
  Timeline:     30-day CHRO mandate
  Expected ROI: 180% | SAR 81,000 cost avoided/year
  Risk if Delayed: Equity perception deteriorates in Finance

─────────────────────────────────────────────────────────────────────
TOTAL RECOMMENDED INVESTMENT:    SAR 1,320,000
TOTAL EXPECTED ANNUAL SAVINGS:   SAR 3,201,000
PORTFOLIO ROI:                   242%
COMBINED PAYBACK:                4.9 months
─────────────────────────────────────────────────────────────────────
```

---

### SECTION 8: FINANCIAL IMPACT (Page 8)

**Purpose:** The CFO's section — everything in SAR.

#### 8.1 Financial Summary Table

```
HUMAN CAPITAL FINANCIAL IMPACT STATEMENT
For Board and CFO Review

CURRENT ANNUAL ATTRITION COST
  Method: Conservative Cascio-Boudreau Model
  Expected Departures (Mid):          40 employees
  Replacement Cost per Departure:    SAR 197,500
  ─────────────────────────────────────────────
  Total Annual Attrition Cost (Mid):  SAR 7,900,000
  Range:                              SAR 6.1M – 9.8M

COST BY COMPONENT
  Recruitment & Selection:            SAR 2,370,000  (30%)
  Productivity Loss / Vacancy:        SAR 1,975,000  (25%)
  Onboarding & Integration:           SAR 1,185,000  (15%)
  Knowledge & Network Loss:           SAR 1,580,000  (20%)
  Administrative / Separation:        SAR   790,000  (10%)

RECOMMENDED INTERVENTION FINANCIAL CASE
  Investment (Year 1):                SAR 1,320,000
  Cost Avoided (Year 1):              SAR 3,201,000
  Net Benefit (Year 1):               SAR 1,881,000
  Cost Avoided (Year 2+):             SAR 3,201,000 (recurring)
  Investment (Year 2+):               SAR   475,000 (recurring)
  Net Benefit (Year 2+):              SAR 2,726,000/year

  3-YEAR NPV (12% discount rate):     SAR 7,432,000
  3-YEAR TOTAL INVESTMENT:            SAR 2,270,000
  3-YEAR NET VALUE:                   SAR 5,162,000

DATA DISCLAIMER: Estimates based on industry models (SHRM/Deloitte).
Actual figures require cost data input by HR/Finance team.
```

---

### SECTION 9: GOVERNANCE STATUS (Page 9)

**Purpose:** Give the board confidence that this analysis is trustworthy.

```
GOVERNANCE CERTIFICATION

DATA PROTECTION
  Personal Identifiable Information:   NOT INCLUDED in analysis ✓
  Employee Identifiers:                Masked (record_id_safe) ✓
  Saudi PDPL Compliance:               Verified ✓
  Data Stored:                         Aggregated metrics only ✓

ML GOVERNANCE
  Model Type:                          Gradient Boosting (XGBoost)
  Cross-Validation:                    5-fold stratified ✓
  Proxy Feature Removal:               Attrition column removed ✓
  Calibration:                         Isotonic regression ✓
  Conservative Reporting:              Proxy-removed metrics used ✓

ANALYSIS INTEGRITY
  Leakage Prevention:                  Active ✓
  Data Quality Score:                  87/100 ✓
  Missing Value Rate:                  2.4% (acceptable) ✓
  Dataset Readiness:                   CONDITIONAL — Notes below ✓

STATISTICAL DISCLAIMER
  This analysis uses machine learning associations, not causal models.
  Risk scores indicate statistical patterns, not predictions of 
  individual employee decisions. All workforce actions must involve 
  qualified HR professionals and comply with applicable labor law.
  Saudi Labor Law Article [x] governs employment decisions.

PLATFORM CERTIFICATION
  Platform:          Adaptive Workforce Intelligence (AWI)
  Analysis Date:     [Date]
  Data Version:      #[Hash]
  Report Certified:  [AWI Platform Seal]
```

---

### SECTION 10: CONFIDENCE & LIMITATIONS (Page 10)

**Purpose:** Epistemic honesty — builds trust with sophisticated board members.

```
CONFIDENCE AND LIMITATIONS

MODEL PERFORMANCE
  Metric                Value    Interpretation
  ─────────────────────────────────────────────────────────
  ROC-AUC (conserv.)   0.8471   Strong discriminative ability
  MCC Score            0.4942   Moderate-strong balanced accuracy
  F1 Score (Class 1)   0.7073   Good minority class detection
  Brier Score          0.1602   Well-calibrated probabilities
  Calibration Error    0.0379   Predictions are reliable (ECE)

  WHAT THIS MEANS: The model reliably distinguishes between stable and 
  at-risk employees 84.7% of the time. In practical terms: out of 10 employees 
  flagged as Priority Review, approximately 7–8 are likely exhibiting 
  genuine early-departure indicators.

WHAT AWI CAN TELL YOU
  ✓ Which departments have elevated collective risk patterns
  ✓ Which organizational factors are most associated with risk
  ✓ What interventions have the strongest evidence base
  ✓ Financial impact of attrition under reasonable assumptions
  ✓ How your workforce compares to industry benchmarks [when available]

WHAT AWI CANNOT TELL YOU
  ✗ Which specific individual employee will leave
  ✗ The exact financial impact (estimates require your cost data)
  ✗ Causal mechanisms (correlation, not causation)
  ✗ Future events not reflected in historical data
  ✗ Individual employee intent, attitude, or personal circumstances

DATA LIMITATIONS FOR THIS ANALYSIS
  • Single-point-in-time analysis (no longitudinal trend data)
  • [X] columns not mapped to behavioral constructs
  • Salary data: [present/estimated from sector defaults]
  • No external market benchmark comparison available yet

RECOMMENDED NEXT STEPS FOR ENHANCED CONFIDENCE
  1. Re-run analysis quarterly (trend data improves prediction quality)
  2. Input actual replacement cost data for precise financial estimates
  3. Connect HRIS data feed for continuous monitoring
```

---

### SECTION 11: APPENDICES (Pages 11+)

**Appendix A:** Methodology — Theory Construct Mapping  
**Appendix B:** Department-Level Detail Tables  
**Appendix C:** ML Validation Technical Summary  
**Appendix D:** Intervention Evidence Base (academic references)  
**Appendix E:** Data Dictionary — What each score means  
**Appendix F:** Governance Audit Trail  
**Appendix G:** Glossary (EN/AR)

---

## PRODUCTION IMPLEMENTATION NOTES

### PDF Technical Requirements
- A4 and Letter format support
- Arabic RTL layout for Arabic sections
- Print-ready (300 DPI equivalent)
- Embedded fonts (no font substitution)
- Digital watermark on CONFIDENTIAL pages
- Page numbers: "Page X of Y — Board Confidential"
- Header: Organization name + report date on every page
- Footer: AWI platform branding + mandatory disclaimer

### Report Generation Trigger
- Automatic generation after every analysis completion
- Available via: Executive Dashboard → "Generate Board Report" button
- Delivery: PDF download, encrypted email option (future)
- Languages: English, Arabic, Bilingual (default)

### Quality Gate Before Generation
- Minimum 100 employees (below this, report quality insufficient for board)
- Minimum dataset readiness: CONDITIONAL or READY
- ML validation must be available (AUC required for confidence section)
- Governance audit must be complete

---

*This specification supersedes all prior reporting formats. All client-facing reports generated by AWI must conform to this standard from the date of implementation.*
