# Adaptive Workforce AI — Release Notes

## v1.0.0-enterprise-local — 2026-05-23

### Summary
First stable enterprise-local release. All analysis runs entirely offline on user-uploaded data. No external APIs, no cloud dependencies, no persistent employee records.

### ML Validation (Saudi Workforce Dataset — Conservative Proxy-Controlled CV)
| Metric | Value |
|---|---|
| ROC-AUC | **0.8471** (±0.0234) |
| MCC (Matthews Correlation Coefficient) | **0.4942** (±0.0692) |
| F1 Score | **0.7073** (±0.0420) |
| Accuracy | **75.23%** |
| Precision | **0.7240** |
| Recall | **0.6932** |
| ECE (calibration error) | **0.0379** |
| Best Model | VotingEnsemble (CatBoost+RF+GB, soft voting) |

**Phase 29.5 improvement vs Phase 29 baseline:** AUC +0.0266, MCC +0.0194, F1 +0.0100. All acceptance gates passed. Zero leakage flags. Proxy exclusion enforced programmatically.

**Phase 29 baseline (locked):** ROC-AUC 0.8205, MCC 0.4748, F1 0.6973 — preserved in `BASELINE_CONSERVATIVE_ML_RESULTS.json`.

All proxy features (job level, tenure, salary) removed before training. Identifier and PII columns excluded automatically.

### Phases Delivered

**Phase 1–14 — Core Engine & Governance**
- Attrition risk scoring with weighted theory-driven drivers (COR, SDT, JD-R, OCT, SET, SIT)
- Conservative ML validation with proxy removal and calibration
- Governance disclaimers and ethical constraint enforcement throughout
- Bilingual (EN/AR) output for all user-facing content
- SQLite-backed analysis persistence with WAL mode

**Phase 15 — Production Mode**
- Demo data eliminated; all analysis requires real uploaded CSV
- EmployeeRiskContext and UploadRequiredState guard all pages
- 562 tests passing at phase completion

**Phase 16–20 — Employee Risk Dashboard & Segmentation**
- Individual employee risk table with drill-down
- Risk segmentation by department, role, tenure band
- Theory explainability per employee
- Export to CSV from all major views

**Phase 21 — Analysis Persistence & History**
- Analysis History page with full audit trail
- SQLite WAL mode + CASCADE deletes
- Result summary stored per analysis session

**Phase 22 — Workforce Simulation**
- Scenario simulation engine (workforce_simulation.py)
- 9 built-in intervention scenarios mapped to theory drivers
- Baseline/scenario comparison with estimated risk reduction
- Simulation results in Executive Reports + CSV export

**Phase 23 — Executive Decision Intelligence**
- Board-level AI intelligence engine (executive_decision_intelligence.py)
- Executive Priority Score (0–100) and Decision Readiness Level (low/medium/high)
- Strategic priorities derived from simulation + org driver alignment
- 5 decision Q&A pairs with evidence and confidence reasoning
- Department decision briefs with action recommendations
- Evidence pack: ML summary, top features, top risk drivers, simulation summary
- Decision Center page with full bilingual board intelligence UI
- DecisionIntelligenceCard in Executive Dashboard

**Phase 24 — Final Enterprise Hardening**
- PageErrorBoundary wrapping all pages (no blank screens on runtime errors)
- React.lazy code splitting for EmployeeRiskDashboard, ExecutiveReports, SimulationPanel, DecisionCenter
- Backend try/except non-fatal blocks for simulation and decision intelligence
- Governance language audit: no causal certainty, no employment decision claims
- Final release check script (scripts/final_release_check.py)
- 712+ tests across all phases

### Architecture
- Backend: FastAPI + Python 3.11, SQLite (local), scikit-learn, pandas
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS
- No external network calls during analysis
- All data stays on the user's machine

### Governance & Ethics
- All outputs are **statistical associations only** — not causal claims
- System must **never** be used as the sole basis for employment decisions
- Governance disclaimers present on every output page
- Conservative ML design: proxy features removed, calibration error tracked
- Bilingual governance notes in EN and AR throughout

### Known Limitations
- Simulation estimates assume consistent HR programme delivery
- ML confidence depends on data quality and class balance in uploaded CSV
- Decision intelligence confidence downgrades automatically with many governance warnings
- Forecast (workforce trend) section requires sufficient historical data
