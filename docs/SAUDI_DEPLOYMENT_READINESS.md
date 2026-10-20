# Saudi Deployment Readiness Assessment
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** CONDITIONALLY READY
**Date:** 2026-05-20

---

## 1. Readiness Summary

| Area | Status | Blocker |
|---|---|---|
| Core ML Pipeline | READY | — |
| Theory Construct Engine | READY | — |
| Model Input Contract | READY | — |
| Temporal Validation | READY | — |
| Saudi Schema Intelligence | READY | — |
| Saudi Data Governance | READY | — |
| Enterprise Language Guard | READY | — |
| Calibration Reliability Audit | READY | — |
| Arabic Language Support | PARTIAL | No Arabic UI translations yet |
| PDPL Compliance | PARTIAL | Legal review required for data processing agreement |
| Nitaqat Integration | NOT STARTED | Out of current scope |
| HR Dashboard | NOT AUDITED | UI testing not part of this phase |
| Production Infrastructure | NOT AUDITED | DevOps/infra outside this scope |

**Overall readiness: CONDITIONALLY READY** — the ML and governance pipeline is production-quality. PDPL legal review and Arabic UI are the remaining pre-deployment blockers.

---

## 2. What Is Production Ready

### 2.1 ML Pipeline

All core machine learning components have passed 302 tests with zero failures:
- Feature engineering pipeline (Phase 1–3)
- Theory construct computation (Phase 4)
- Model input contract validation (Phase 4)
- Temporal leakage prevention (Phase 4)
- Saudi schema normalization (Phase 5)
- Saudi data governance checks (Phase 5)
- Enterprise language guard (Phase 5)
- Calibration reliability auditor (Phase 5)

### 2.2 Scientific Validity

The 7 theory constructs remain mathematically faithful to their published sources:
- COR Theory (Hobfoll 1989) → SatisfactionIndex
- JD-R Model (Bakker & Demerouti 2007) → BurnoutRisk, EngagementScore
- Mobley Turnover Process (1977) → TenureRatio, CareerProgression
- Adams Equity Theory (1963) → IncomePerLevel, SalaryGrowth

No synthetic constructs, no benchmark gaming, no artificial metric inflation detected in Phase 1–5 audit.

### 2.3 Governance Layers (All Active)

| Layer | Module | Status |
|---|---|---|
| Target leakage prevention | `model_input_contract.py` | ACTIVE |
| Proxy leakage prevention | `model_input_contract.py` | ACTIVE |
| Temporal leakage prevention | `temporal_validation_guard.py` | ACTIVE |
| PII detection | `saudi_schema_intelligence.py` + `saudi_data_governance.py` | ACTIVE |
| Legacy construct quarantine | `model_input_contract.py` | ACTIVE |
| Theory construct pre-approval | `model_input_contract.py` | ACTIVE |
| Language risk guard | `enterprise_language_guard.py` | ACTIVE |
| Calibration reliability | `calibration_reliability_audit.py` | ACTIVE |
| Saudi salary validation | `saudi_data_governance.py` | ACTIVE |
| Age/tenure plausibility | `saudi_data_governance.py` | ACTIVE |
| Attrition rate plausibility | `saudi_data_governance.py` | ACTIVE |
| ERP fingerprinting | `saudi_schema_intelligence.py` | ACTIVE |

---

## 3. Remaining Blockers

### 3.1 PDPL Legal Review (MANDATORY BEFORE DEPLOYMENT)

The Saudi Personal Data Protection Law (PDPL, Royal Decree No. M/19, 2021) requires:

1. **Data processing agreement** — a signed DPA between the deploying organization and Anthropic/the system operator must be in place before employee data is processed.
2. **Data subject rights** — employees must be informed that their HR data is used in automated risk assessment. The pipeline does not implement the notification workflow.
3. **Automated decision making** — PDPL Art. 25 restricts automated decisions that significantly affect individuals. The system must be positioned as a "decision support tool" (human in the loop required) in all legal documentation.
4. **Cross-border transfer** — if the model or data is processed outside Saudi Arabia, additional PDPL consent requirements apply. Cloud deployment region must be documented.
5. **Data minimization** — the system must only receive columns needed for prediction. The `SaudiSchemaIntelligenceEngine` identifies PII columns, but their removal from the data pipeline is a process control, not an automated action.

**Action required:** Legal review of data processing workflow with PDPL counsel before go-live.

### 3.2 Arabic UI (BLOCKING FOR ARABIC-FIRST CLIENTS)

The ML pipeline handles Arabic column names (Mudad, Qiwa schemas). The dashboard and report narratives are English-only. Saudi government entities and many private sector clients require Arabic interfaces.

**Scope not yet built:**
- Arabic translations of risk level labels
- Arabic-language report narratives
- RTL layout support in dashboard
- Arabic safe vocabulary reference (`SAFE_ATTRITION_VOCABULARY` has no Arabic equivalents)

**Action required:** UI localization sprint before deploying to Arabic-first clients.

### 3.3 Qiwa API Integration (OPTIONAL, HIGH VALUE)

Qiwa provides real-time Saudization compliance data via API. Manual data exports create data freshness risk — an employee's Nitaqat status may change between export and prediction. A direct API integration would:
- Eliminate the manual export step
- Reduce data staleness from weeks to hours
- Enable real-time governance flag updates

This integration is not in scope for Phase 5 but is recommended before enterprise-scale deployment.

---

## 4. Mandatory Pre-Deployment Checklist

Before serving predictions to any Saudi enterprise client:

- [ ] **PDPL DPA signed** — legal counsel approval
- [ ] **HR human-in-the-loop policy documented** — model is advisory, not autonomous
- [ ] **PII columns excluded from pipeline** — verify `SaudiSchemaIntelligenceEngine.pii_columns` are not in feature matrix
- [ ] **Leakage columns excluded from pipeline** — verify `SaudiDataGovernanceEngine.leakage_columns` are not in feature matrix
- [ ] **CalibrationReliabilityReport.overall_reliability != "CRITICAL"** — run after every model training
- [ ] **EnterpriseLanguageGuard.audit()` applied to all report narratives** — verify before rendering
- [ ] **SaudiDataGovernanceReport.is_clean == True** — or all findings reviewed and accepted
- [ ] **TemporalValidationReport.has_temporal_risk == False** — or CRITICAL findings resolved
- [ ] **Attrition rate plausibility check passed** — `governance_report.attrition_rate_observed < 0.5`
- [ ] **Salary scale confirmed** — monthly vs. annual detection reviewed in governance report
- [ ] **Department reliability noted** — CRITICAL-reliability departments flagged in dashboard
- [ ] **Model retraining policy documented** — when and how the model will be retrained as workforce changes

---

## 5. Not Included in This System (Governance Boundaries)

The following capabilities are explicitly out of scope and must not be added without a formal scientific review:

| Capability | Why Not Included |
|---|---|
| Individual employee risk scores in public-facing reports | PDPL + individual targeting risk |
| Automated termination recommendations | Legal risk + Saudi Labour Law |
| Salary benchmarking vs. market | Would require external market data not validated in this paper |
| Performance prediction | Out of scope; different theoretical framework required |
| Recruitment scoring | Different domain; COR/JD-R not validated for recruitment |
| Psychometric profiling | Clinical tools require clinical validation, not HR data |
| Real-time attrition alerts | Operational infrastructure not built |
| GenAI narrative generation | No validated framework for LLM-generated HR reports |

These boundaries are enforced through the governance modules (language guard, model input contract) rather than policy alone.

---

## 6. Known Scientific Limitations (Deployment Communication)

These limitations must be communicated to client organizations before deployment:

1. **The model was developed on IBM HR Benchmark data.** Client data will differ in base rates, salary ranges, and cultural context. Model performance on client data must be validated through internal cross-validation before deployment decisions are made.

2. **Attrition prediction is probabilistic.** A score of 0.7 does not mean "this employee will leave." It means employees with similar profiles leave at approximately 70% rates. Individual prediction error is high.

3. **The model captures correlation, not causation.** If the model associates low JobSatisfaction with attrition, that does not mean improving satisfaction will reduce attrition. The causal mechanism requires separate investigation.

4. **The model is not aware of macro-economic conditions.** A Saudi-wide recession, regulatory changes, or sector-specific disruptions will shift attrition rates outside the model's training distribution. The model must be retrained when base rates shift significantly.

5. **Small departments are unreliable.** Predictions for departments with fewer than 10 employees should be treated as indicative only.

6. **The model requires periodic retraining.** Workforce composition, market conditions, and organizational culture change. A model trained on 2023 data may not be valid in 2026.

---

## 7. Post-Deployment Monitoring Requirements

Once deployed, the following must be monitored continuously:

| Metric | Frequency | Alert Threshold |
|---|---|---|
| Model AUC on new labeled data | Monthly | Drop >0.05 from baseline |
| Calibration gap (Brier score) | Monthly | >0.03 degradation |
| High-risk concentration | Weekly | >40% triggers review |
| Attrition rate vs. predicted | Quarterly | >15 percentage point deviation |
| PII column presence in new data | Every upload | Any detection = immediate block |
| Leakage column presence | Every upload | Any detection = immediate block |
| Department size changes | Monthly | Any dept dropping below 10 flagged |

---

## 8. Test Suite Certification

| Test Suite | Tests | Status |
|---|---|---|
| Phase 1–3 baseline | 127 | 127/127 passed |
| Phase 4 theory integration | 36 | 36/36 passed |
| Phase 5 Saudi validation | 59 | 59/59 passed |
| Routing regression | 11 | 11/11 passed |
| Column mapper | 69 | 69/69 passed |
| **TOTAL** | **302** | **302/302 passed** |

Zero test failures. Zero regressions introduced in Phase 5.

---

## 9. Governance Document Index

| Document | Purpose |
|---|---|
| `SAUDI_SCHEMA_INTELLIGENCE_AUDIT.md` | ERP fingerprinting, normalization, PII detection |
| `THEORY_ACTIVATION_GOVERNANCE.md` | Construct activation criteria, Layer B quarantine |
| `ENTERPRISE_RISK_LANGUAGE_AUDIT.md` | Language guard rules, safe vocabulary, PDPL language |
| `CALIBRATION_RELIABILITY_AUDIT.md` | Calibration thresholds, FP governance, dept reliability |
| `CROSS_COMPANY_VALIDATION_REPORT.md` | Multi-ERP schema portability, construct coverage by ERP |
| `SAUDI_DEPLOYMENT_READINESS.md` | This document — deployment checklist and blockers |
| `PHASE4_INTEGRATION_SUMMARY.md` | Phase 4 integration details |
| `MODEL_INPUT_CONTRACT_AUDIT.md` | Feature gating rules |
| `TEMPORAL_VALIDATION_GOVERNANCE.md` | Temporal leakage prevention |
| `SCIENTIFIC_TRACEABILITY_AUDIT.md` | Theory-formula-to-code traceability |
| `LEGACY_LOGICAL_QUARANTINE_REPORT.md` | Layer B/C quarantine details |

---

*Assessment produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
