# Final Evidence Pack
## Adaptive Workforce AI — v1.0.0-enterprise-local

**Date:** 2026-05-23
**Status:** Release Freeze Complete

---

## Test Results

| Metric | Value |
|---|---|
| Total tests | 713 (712 passed, 1 skipped, 0 failed) |
| Test framework | pytest 9.0.3 |
| Python version | 3.13.13 |
| Platform | Windows 11 Pro |
| Runtime | ~33 seconds |

### Test Coverage by Phase

| Phase | File | Tests |
|---|---|---|
| Phase 1–11 | Core pipeline, upload, routing, ingestion | ~562 |
| Phase 12 | Local analysis endpoint (Saudi dataset) | ~15 |
| Phase 13 | Performance benchmarks | ~10 |
| Phase 14 | Employee risk dashboard | ~22 |
| Phase 15 | Production mode | included above |
| Phase 16 | Model metrics | ~10 |
| Phase 18 | Explainability | ~12 |
| Phase 22 | Workforce simulation | 10 |
| Phase 23 | Executive decision intelligence | 10 |
| Phase 24 | Release hardening | 10 |
| **Total** | | **712** |

### Non-Blocking Warnings (174 total)

| Warning Type | Source | Action Required |
|---|---|---|
| `Pandas4Warning: select_dtypes object` | excel_ingestion_engine, adaptive_router | None — future pandas version |
| `DeprecationWarning: datetime.utcnow()` | employee_risk_scoring, executive_decision_intelligence, enterprise_onboarding_pipeline, executive_reporting_layer | None — Python 3.13, no removal date |
| `UserWarning: date format inference` | adaptive_router, modality_classifier, semantic_column_mapper | None — dateutil fallback correct |

---

## Build Status

| Check | Status |
|---|---|
| Vite production build | PASS |
| Build time | 3.76 seconds |
| Modules transformed | 2,682 |
| TypeScript errors | 0 |
| Build errors | 0 |

### Bundle Chunks (Code-Split)

| Chunk | Raw Size | Gzip Size |
|---|---|---|
| `index.js` (core) | 439.59 kB | 129.15 kB |
| `EmployeeRiskDashboard.js` | 416.91 kB | 114.94 kB |
| `ExecutiveReports.js` | 41.05 kB | 9.56 kB |
| `DecisionCenter.js` | 13.73 kB | 3.39 kB |
| `SimulationPanel.js` | 12.30 kB | 4.15 kB |
| `index.css` | 51.96 kB | 8.78 kB |
| `download.js` | 0.43 kB | 0.32 kB |

Note: `EmployeeRiskDashboard` is large because it renders the full interactive employee table. It is lazy-loaded and does not affect initial page load.

---

## Final Release Check — `scripts/final_release_check.py`

| Check | Result |
|---|---|
| Core modules import cleanly | PASS |
| SQLite initialises with WAL mode | PASS |
| Risk scoring engine runs on synthetic data | PASS |
| Workforce simulation engine runs and returns scenarios | PASS |
| Decision intelligence engine runs and returns dict | PASS |
| No causal certainty language in DI output | PASS |
| Governance: zero records -> available=False with reason | PASS |
| **Total** | **7/7 PASS** |

---

## Saudi ML Validation Results

### Dataset

| Attribute | Value |
|---|---|
| File | Original Dataset of Employee Attrition (1).xlsx |
| Rows | 1,191 |
| Columns | 35 |
| Target | Attrition (binary) |
| Positive class | 515 (43.2%) |
| Negative class | 676 (56.8%) |

### Section A — Full Features (WITH proxy leakage)

| Model | AUC | MCC | F1 | Acc |
|---|---|---|---|---|
| GradientBoosting | 1.0000 | 1.0000 | 1.0000 | 100% |
| LogisticRegression | 1.0000 | 0.9729 | 0.9843 | 98.7% |
| RandomForest | 0.9974 | 0.9662 | 0.9802 | 98.3% |

**Warning:** Top feature `Years_Experience` accounts for >85% of importance. Metrics are inflated by proxy leakage. Not suitable for academic reporting.

### Section B — Conservative Proxy-Free (RECOMMENDED)

| Metric | Mean | Std |
|---|---|---|
| ROC-AUC | **0.8471** | ±0.0234 |
| MCC | **0.4942** | ±0.0692 |
| F1 Score | **0.7073** | ±0.0420 |
| Accuracy | **75.23%** | ±3.39% |
| Precision | **0.7240** | ±0.0454 |
| Recall | **0.6932** | ±0.0516 |
| ECE (calibration error) | **0.0379** | — |

**Best model:** VotingEnsemble_top3 — CatBoost + RandomForest + GradientBoosting, soft voting (5-fold StratifiedKFold CV)

**Per-fold AUCs:** 0.8267 | 0.8306 | 0.8882 | 0.8315 | 0.8585

**OOF Confusion Matrix (threshold=0.50):**

|  | Predicted Positive | Predicted Negative |
|---|---|---|
| **Actual Positive** | TP: 357 | FN: 158 |
| **Actual Negative** | FP: 137 | TN: 539 |

**Phase 29.5 improvement vs Phase 29 baseline (locked):**

| Metric | Phase 29 Baseline | Phase 29.5 | Delta |
|---|---|---|---|
| ROC-AUC | 0.8205 | **0.8471** | +0.0266 |
| MCC | 0.4748 | **0.4942** | +0.0194 |
| F1 | 0.6973 | **0.7073** | +0.0100 |

All 4 acceptance gates passed (ROC-AUC +0.0266 ≥ +0.01, MCC +0.0194 ≥ −0.01, F1 +0.0100 ≥ −0.01, leakage flags = 0).

---

## Governance Exclusions

### ML Training Exclusions

| Column Type | Columns Removed | Reason |
|---|---|---|
| PII | `Business_Travel` | PDPL Article 6 — personal identifier |
| Identifier | `ID` | Row identifier — must not enter model |
| Proxy features | `Years_Experience` (all variants), `Years_experience_lastorganization` (all variants) | Structural correlate — would inflate metrics |

### Governance Warnings Emitted (3 — correct by design)

1. PII columns excluded from ML features: Business_Travel. PDPL Article 6 compliance.
2. Identifier-like columns removed from ML features: ID.
3. ML validation uses real uploaded data. Results are statistical model metrics only. They do not constitute employment decisions, causal claims, or predictions.

---

## Top Clean Features (Conservative, Proxy-Free)

| Rank | Feature | Importance | Theory |
|---|---|---|---|
| 1 | Job_Opportunities_Yes | 0.194 | COR |
| 2 | Job_Opportunities_No | 0.068 | COR |
| 3 | Training_programs (7+ programs) | 0.067 | JD-R / SDT |
| 4 | Get_Deserved_Promotion_Yes | 0.048 | SET |
| 5 | Department_Patient Affairs | 0.041 | SIT |
| 6 | JobTitle_Teacher | 0.041 | SIT |
| 7 | Job_Stability_No | 0.041 | COR |
| 8 | Get_Deserved_Promotion_No | 0.034 | SET |
| 9 | Emotional_Commitment_High | 0.030 | OCT |
| 10 | Job_Engagement_Difficult | 0.028 | JD-R |

---

## Screenshots Checklist

See: `docs/SCREENSHOT_CHECKLIST.md`

---

## Demo Checklist

Before a live demo or recording:

- [ ] Backend running: `uvicorn backend.api.main:app --reload`
- [ ] Frontend running: `cd executive-ui && npm run dev`
- [ ] Saudi dataset uploaded and analysis completed
- [ ] Executive Dashboard showing results (not Upload page)
- [ ] Decision Center loaded and visible
- [ ] Strategy Simulator loaded and visible
- [ ] Governance Panel accessible
- [ ] Language toggle tested (EN ↔ AR)
- [ ] Dark/light mode tested
- [ ] CSV export tested (at least one export)
- [ ] Analysis History showing at least one saved session

---

## Acceptance Checklist

### Functionality

- [x] CSV/Excel upload with automatic column mapping
- [x] Employee risk scoring (0–100 risk + stability)
- [x] Risk band classification (Stable / Monitoring / Strategic Concern / Priority Review)
- [x] Department-level aggregation and comparison
- [x] Theory-attributed driver explanation (6 theories, EN + AR)
- [x] Conservative ML validation (proxy removal + StratifiedKFold CV)
- [x] ML feature importance (top 15, proxy-free)
- [x] Workforce scenario simulation (9 intervention scenarios)
- [x] Executive decision intelligence (Priority Score + Decision Readiness)
- [x] Board-level summary (EN + AR)
- [x] Strategic priorities with urgency + confidence
- [x] Decision Q&A (5 pairs with evidence)
- [x] Department decision briefs
- [x] Evidence pack (6 sections)
- [x] Workforce forecast
- [x] Analysis history (SQLite persistence with WAL mode)
- [x] CSV export (risk table, ML validation, simulation, decision intelligence)
- [x] Export audit trail

### Governance

- [x] No causal certainty language in any output
- [x] Employment decision prohibition on every page
- [x] Governance disclaimers bilingual (EN + AR)
- [x] PII exclusion from ML training
- [x] Proxy feature removal documented
- [x] Zero records → available=False enforced
- [x] Conservative ML metrics reported (Section B, not Section A)

### Technical

- [x] All 712 tests passing
- [x] Vite production build succeeds (0 errors)
- [x] Final release check 7/7 PASS
- [x] Saudi ML validation available=True
- [x] React.lazy code splitting (4 heavy pages)
- [x] PageErrorBoundary (no blank screens on error)
- [x] No external API calls
- [x] No cloud dependencies
- [x] SQLite WAL mode + CASCADE deletes
- [x] Bilingual toggle (EN/AR) functional

### Documentation

- [x] `RELEASE_NOTES.md`
- [x] `docs/FINAL_SYSTEM_OVERVIEW.md`
- [x] `docs/ACADEMIC_RESEARCH_PACKAGE.md`
- [x] `docs/EXECUTIVE_DEMO_SCRIPT.md`
- [x] `docs/ENTERPRISE_PITCH.md`
- [x] `docs/FINAL_EVIDENCE_PACK.md`
- [x] `docs/SCREENSHOT_CHECKLIST.md`
- [x] `scripts/final_release_check.py`
