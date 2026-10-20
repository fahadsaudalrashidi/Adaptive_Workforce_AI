# Adaptive Workforce AI — Final System Overview

Version: v1.0.0-enterprise-local | Date: 2026-05-23 | Status: Production-Ready (Local)

---

## Purpose

Adaptive Workforce AI is a fully local, offline workforce intelligence platform. It analyses employee data to surface attrition risk patterns, explains them through established organisational theories, and presents board-ready intelligence — all without sending any data to external services.

The system is designed to **inform** HR and executive decision-making, not to replace human judgement. Every output is governed by statistical-association-only disclaimers and ethical use constraints.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Executive UI (React 18 + TypeScript + Vite)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐│
│  │ Data Upload  │  │ Executive    │  │ Decision Center (Phase 23) ││
│  │ & History    │  │ Dashboard    │  │ Board Intelligence UI      ││
│  └──────────────┘  └──────────────┘  └───────────────────────────┘│
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐│
│  │ Risk         │  │ Employee     │  │ Simulation Panel           ││
│  │ Segmentation │  │ Risk Table   │  │ Scenario Planner           ││
│  └──────────────┘  └──────────────┘  └───────────────────────────┘│
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐│
│  │ Theory       │  │ Governance   │  │ Executive Reports          ││
│  │ Explainability│  │ Panel        │  │ + CSV Exports              ││
│  └──────────────┘  └──────────────┘  └───────────────────────────┘│
└────────────────────────────────────────────────────────────────────┘
          │  HTTP (localhost only)
┌────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ local_analysis_routes.py  (main orchestration)               │ │
│  └──────────────────────────────────────────────────────────────┘ │
│  Core Engines:                                                      │
│  ├── risk_scoring_engine.py         (employee attrition scoring)   │
│  ├── ml_validation_engine.py        (conservative CV, proxy-free)  │
│  ├── workforce_simulation_engine.py  (scenario planning engine)    │
│  ├── executive_decision_intelligence.py  (board-level AI)          │
│  ├── workforce_forecast.py          (trend forecasting)            │
│  ├── theory_explainability.py       (COR/SDT/JD-R/OCT/SET/SIT)    │
│  └── export_safety.py               (PII/governance gate)          │
│  Storage:                                                           │
│  └── SQLite (WAL mode) — local only, auto-cleared between sessions │
└────────────────────────────────────────────────────────────────────┘
```

---

## Key Engines

### 1. Risk Scoring Engine (`risk_scoring_engine.py`)
- Scores each employee 0–100 for attrition risk and 0–100 for stability
- Drivers mapped to six theories: COR, SDT, JD-R, OCT, SET, SIT
- Top risk drivers and protective factors computed per employee and per group
- Output: per-employee risk table + org-level driver summary

### 2. ML Validation Engine (`ml_validation_engine.py`)
- Conservative design: proxy features (job level, tenure, salary) removed before training
- PII and identifier columns excluded automatically
- StratifiedKFold cross-validation (5-fold)
- Reports: ROC-AUC, MCC, F1, Precision, Recall, Brier Score, Calibration Error
- Feature importance (top 10) for interpretability
- Best model: VotingEnsemble_top3 (CatBoost+RF+GB, soft voting — Phase 29.5, Saudi workforce dataset: AUC = 0.8471, MCC = 0.4942, ECE = 0.0379)

### 3. Workforce Simulation Engine (`workforce_simulation.py`)
- 9 built-in intervention scenarios (internal mobility, training, leadership, compensation, etc.)
- Baseline established from current risk band distribution
- Estimated risk reduction % per scenario, affected departments, confidence level
- Recommended strategy: highest-impact scenario combination

### 4. Executive Decision Intelligence (`executive_decision_intelligence.py`)
- **Executive Priority Score** (0–100): risk base + Priority Review concentration + governance discount
- **Decision Readiness Level**: high / medium / low (based on ML quality + simulation availability)
- **Board Summary**: 5-sentence bilingual narrative (EN + AR)
- **Strategic Priorities**: top 3, sorted by estimated impact, with urgency and confidence
- **Decision Questions**: 5 evidence-backed Q&A pairs for executive briefings
- **Department Briefs**: per-department action recommendation with expected impact
- **Evidence Pack**: ML summary, top features, top risk drivers, simulation, forecast, governance

---

## Data Flow

```
User uploads CSV
      │
      ▼
FastAPI /analyze endpoint
      │
      ├── Risk Scoring Engine          → per-employee scores, risk bands
      ├── Theory Explainability        → driver labels + theory links
      ├── ML Validation (conservative) → AUC, MCC, feature importance
      ├── Workforce Simulation         → scenarios + recommended strategy
      ├── Workforce Forecast           → trend projection
      ├── Department Summary           → aggregated group analytics
      ├── Org Risk Driver Summary      → organisation-wide patterns
      └── Executive Decision Intelligence → board intelligence pack
            │
            ▼
      SQLite persistence (result_json)
            │
            ▼
      React UI renders all pages from stored result
```

---

## Navigation Pages

| Page | Route Key | Purpose |
|---|---|---|
| Data Upload | `upload` | CSV upload, analysis trigger |
| Executive Dashboard | `dashboard` | KPIs, ML metrics, DI card |
| Employee Risk Table | `employees` | Per-employee drill-down |
| Risk Segmentation | `segmentation` | Breakdown by dept/role/tenure |
| Theory Explainability | `theory` | Driver → theory mapping |
| Strategy Simulator | `simulation` | Scenario what-if planning |
| Decision Center | `decision` | Board intelligence full view |
| Governance Panel | `governance` | Ethical constraints, disclaimers |
| Executive Reports | `reports` | Full reports + CSV exports |
| Analysis History | `history` | Past sessions + audit trail |
| Trust Panel | `trust` | ML quality + governance notes |

---

## Governance Constraints (Non-Negotiable)

1. All outputs are **statistical associations** — never causal claims
2. System must **never** be the sole basis for employment decisions (hiring, firing, promotion)
3. Governance disclaimers appear on every output-bearing page
4. Conservative ML: proxy features removed, calibration tracked, leakage prevented
5. No data leaves the user's machine — fully local/offline
6. Export audit trail logged per session

---

## Test Coverage

| Phase | Tests |
|---|---|
| Phase 1–14 Core | 562 |
| Phase 22 Simulation | 10 |
| Phase 23 Decision Intelligence | 10 |
| Phase 24 Release Hardening | 10 |
| **Total** | **≥ 712** |

Run all tests: `py -m pytest tests/ -q`

---

## Running Locally

```bash
# Backend
cd c:\Users\PvP-Pc\Desktop\Adaptive_Workforce_AI
uvicorn backend.api.main:app --reload

# Frontend (separate terminal)
cd executive-ui
npm install
npm run dev

# Validate ML on Saudi dataset
py scripts/run_saudi_ml_validation.py

# Final release check
py scripts/final_release_check.py
```

---

## File Structure (Key Files)

```
Adaptive_Workforce_AI/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   └── local_analysis_routes.py        # Main orchestration
│   └── core/
│       ├── risk_scoring_engine.py
│       ├── ml_validation_engine.py
│       ├── workforce_simulation.py
│       ├── executive_decision_intelligence.py
│       ├── workforce_forecast.py
│       ├── theory_explainability.py
│       └── export_safety_validator.py
├── executive-ui/
│   └── src/
│       ├── App.tsx                          # Route + lazy loading + error boundary
│       ├── pages/
│       │   ├── ExecutiveDashboard.tsx
│       │   ├── DecisionCenter.tsx           # Phase 23 board intelligence
│       │   ├── SimulationPanel.tsx          # Phase 22 simulation
│       │   ├── ExecutiveReports.tsx
│       │   ├── EmployeeRiskDashboard.tsx
│       │   └── ...
│       └── components/shared/
│           ├── PageErrorBoundary.tsx        # Phase 24 error handling
│           ├── GovernanceDisclaimer.tsx
│           ├── UploadRequiredState.tsx
│           └── ...
├── tests/
│   ├── test_phase22_workforce_simulation.py
│   ├── test_phase23_decision_intelligence.py
│   └── test_phase24_release_hardening.py
├── scripts/
│   ├── run_saudi_ml_validation.py
│   └── final_release_check.py
├── RELEASE_NOTES.md
└── docs/
    └── FINAL_SYSTEM_OVERVIEW.md
```
