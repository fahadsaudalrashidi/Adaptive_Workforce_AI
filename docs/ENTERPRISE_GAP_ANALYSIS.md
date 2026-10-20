# ENTERPRISE GAP ANALYSIS
## Adaptive Workforce Intelligence — Phase A Strategic Audit
**Classification:** Executive Confidential  
**Prepared by:** Office of the Chief AI Officer  
**Date:** June 2026  
**Version:** 1.0

---

## EXECUTIVE SUMMARY

AWI possesses a technically sophisticated, governance-hardened core that exceeds most academic HR-analytics platforms in rigor and explainability. However, the gap between current state and enterprise-grade commercial readiness is significant across six critical dimensions: monetization architecture, executive experience, boardroom reporting, market intelligence, integration readiness, and SaaS scalability.

This analysis maps 47 specific gaps across 11 capability domains, each rated by enterprise impact (1–5) and implementation effort (Low/Medium/High).

**Net Assessment:** AWI is a **Tier 2 Enterprise MVP** — production-ready as a proof-of-concept, but requiring 6–9 months of focused product work to reach Tier 4 commercial SaaS status suitable for enterprise contracting at SAR 500K+ per engagement.

---

## SECTION 1: CAPABILITY DOMAIN INVENTORY

### 1.1 Current Capability Heatmap

| Domain | Current Maturity | Required Maturity | Gap Score |
|--------|-----------------|-------------------|-----------|
| Data Governance | ████████░░ 8/10 | ████████░░ 9/10 | LOW |
| ML Engine | ███████░░░ 7/10 | ████████░░ 8/10 | LOW |
| Risk Scoring | ████████░░ 8/10 | █████████░ 9/10 | LOW |
| Executive Reporting | █████░░░░░ 5/10 | █████████░ 9/10 | **CRITICAL** |
| Simulation / Digital Twin | ████░░░░░░ 4/10 | ████████░░ 8/10 | **HIGH** |
| ROI Quantification | ██░░░░░░░░ 2/10 | ████████░░ 8/10 | **CRITICAL** |
| Strategic Indices | ███░░░░░░░ 3/10 | ████████░░ 8/10 | **HIGH** |
| Integration Layer | █░░░░░░░░░ 1/10 | ███████░░░ 7/10 | **CRITICAL** |
| Multi-Tenancy / SaaS | ██░░░░░░░░ 2/10 | █████████░ 9/10 | **CRITICAL** |
| Benchmarking | ░░░░░░░░░░ 0/10 | ███████░░░ 7/10 | **CRITICAL** |
| Mobile / Self-Service | ░░░░░░░░░░ 0/10 | ██████░░░░ 6/10 | HIGH |

---

## SECTION 2: CRITICAL GAPS (Impact 5/5)

### GAP-01: No Executive ROI Quantification
**Impact:** 5/5 — **Effort:** Medium  
**Description:** The platform diagnoses risk but cannot answer the CEO's first question: "What does this cost us?" There is no calculation of attrition cost, replacement cost, productivity loss, or training ROI. The `roi_estimation_engine.py` module exists but is not surfaced in any executive output.  
**Enterprise Consequence:** No C-suite buyer will authorize procurement of a risk platform without a financial justification engine. Every McKinsey/Deloitte HR analytics engagement leads with the "cost of attrition" model.  
**Required Deliverable:** ROI calculator surfaced on dashboard, PDF report financial impact section, CFO-readable cost model.

### GAP-02: No Industry Benchmarking
**Impact:** 5/5 — **Effort:** Medium  
**Description:** AWI tells an executive their risk score is 63/100 with no reference to whether this is excellent, average, or alarming relative to their industry or Saudi market peers. There is zero benchmarking capability.  
**Enterprise Consequence:** Without a benchmark, the score is meaningless to an executive. "Your attrition risk is 63" means nothing. "Your attrition risk is 63, which is 15 points above the Saudi banking sector average of 48" drives urgency and action.  
**Required Deliverable:** Saudi industry benchmark database (Banking, O&G, Telecom, Government, Retail), percentile positioning, sector comparison report.

### GAP-03: No SaaS / Multi-Tenant Architecture
**Impact:** 5/5 — **Effort:** High  
**Description:** The platform runs on a single SQLite file with no authentication, no tenant isolation at the application layer (only code-level guards), no billing, no user management, no API key provisioning.  
**Enterprise Consequence:** Cannot be sold as a SaaS product. Every enterprise client will ask: "Where is my data?" and "Can other clients see my data?" The current answer is architecturally concerning.  
**Required Deliverable:** PostgreSQL backend, JWT authentication, tenant schema isolation, API key management, usage metering, billing hooks.

### GAP-04: No System Integration Layer
**Impact:** 5/5 — **Effort:** High  
**Description:** AWI is a closed silo. It has no connectors to SAP SuccessFactors, Workday, Oracle HCM, MUDAD (Saudi payroll), Qiwa (Saudi labor platform), GOSI (social insurance), or any HRIS. All data enters via manual file upload.  
**Enterprise Consequence:** Saudi enterprise clients — Aramco, STC, Riyad Bank — all have SAP or Oracle HCM. Manual file upload is a non-starter for enterprise procurement. Integration is the #1 procurement requirement in enterprise HR analytics.  
**Required Deliverable:** REST API connector framework, SAP OData adapter, Workday Prism API adapter, SFTP auto-ingestion, webhook notification system.

### GAP-05: No Saudization (Nitaqat) Compliance Module
**Impact:** 5/5 — **Effort:** Medium  
**Description:** Vision 2030 mandates Saudization quotas across all sectors. Saudi clients must demonstrate Nitaqat compliance (Green/Platinum zone). AWI has no awareness of nationality workforce composition, Saudization rates, or compliance risk.  
**Enterprise Consequence:** This is a regulatory compliance requirement, not an analytics feature. Ministry of HR clients and any company subject to Nitaqat will not purchase an HR analytics platform that ignores their primary compliance obligation.  
**Required Deliverable:** Saudization rate calculator, Nitaqat zone classifier, compliance risk forecasting, Ministry of HR report format.

### GAP-06: No Organizational Network Analysis (ONA)
**Impact:** 5/5 — **Effort:** High  
**Description:** AWI scores individual employees and departments in isolation. It has no understanding of organizational connectivity, key connector identification, knowledge network mapping, or influence topology.  
**Enterprise Consequence:** The most dangerous attrition is often not the highest-risk employee, but the central connector whose departure severs knowledge networks. ONA is a $50M+ market segment (Cognitive Talent Solutions, Humanyze, Worklytics) that AWI is completely absent from.  
**Required Deliverable:** Basic ONA from org hierarchy, key person risk identification, network fragility score, knowledge loss simulation.

---

## SECTION 3: HIGH-SEVERITY GAPS (Impact 4/5)

### GAP-07: No Real-Time Monitoring / Pulse Surveys
**Impact:** 4/5 — **Effort:** High  
**Description:** AWI is a batch-analysis tool. It analyzes historical HR snapshots but cannot monitor workforce sentiment in real-time. Enterprise clients expect continuous monitoring, not quarterly reports.  
**Required Deliverable:** Scheduled re-analysis API, pulse survey integration, trend alerting, momentum scoring.

### GAP-08: No Manager / Department-Head Self-Service Portal
**Impact:** 4/5 — **Effort:** Medium  
**Description:** The current UI is designed for HR executives and C-suite. Individual department managers — who are responsible for retention of their teams — have no self-service access to their team's risk profile.  
**Required Deliverable:** Role-based access control, manager dashboard (team view only), coaching recommendation cards for managers, mobile-responsive design.

### GAP-09: No Succession Planning Intelligence
**Impact:** 4/5 — **Effort:** Medium  
**Description:** AWI identifies flight-risk employees but provides no succession depth analysis. Who replaces a Priority Review employee if they leave? What is the bench strength for critical roles?  
**Required Deliverable:** Role criticality mapping, succession depth score, key person dependency risk, single-point-of-failure identification.

### GAP-10: Board Reporting Quality is Insufficient
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Current PDF reports are technically accurate but aesthetically and structurally below the standard expected at board level. McKinsey-quality reports have executive summary on page 1, visual hierarchy, strategic framing, and explicit financial impact quantification.  
**Required Deliverable:** Redesigned board report (see BOARD_REPORT_SPECIFICATION.md), heat maps, trend charts, financial impact tables, governance certification page.

### GAP-11: No Competitive Benchmarking Module
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Clients cannot compare themselves to competitors. "What is the attrition rate at Saudi banks comparable to ours?" is the most common executive question in HR analytics.  
**Required Deliverable:** Anonymized industry comparison database, peer group positioning, industry quartile reporting.

### GAP-12: Simulation Lacks Temporal Dimension
**Impact:** 4/5 — **Effort:** Medium  
**Description:** The simulation engine produces "estimated risk reduction" as a single number but has no timeline. "If we implement training programs, when will we see results — Q2 or Q4?"  
**Required Deliverable:** Time-phased simulation (30/60/90/180-day windows), cumulative impact projections, investment timeline alignment.

### GAP-13: No Pay Equity Analysis
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Gender pay gap, nationality-based pay disparity, and role-level pay inequity are major retention drivers and regulatory concerns in Saudi Arabia (Vision 2030 gender inclusion mandate).  
**Required Deliverable:** Pay equity index, gender compensation analysis, grade-level pay distribution, equity-adjusted risk scoring.

### GAP-14: No Candidate / External Talent Intelligence
**Impact:** 4/5 — **Effort:** High  
**Description:** AWI only analyses the internal workforce. It provides no intelligence on external talent availability, market salary benchmarks, or recruitment difficulty for at-risk roles.  
**Required Deliverable:** External talent market integration (LinkedIn APIs, Glassdoor), replacement difficulty scoring per role, market salary gap analysis.

### GAP-15: No Contract / Workflow Management Integration
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Recommendations generated by AWI exist only in PDF. There is no action tracking — no way to assign "HR Manager will implement training program for Operations" and track whether it was done.  
**Required Deliverable:** Action tracking module, recommendation assignment, completion tracking, impact measurement loop.

---

## SECTION 4: MEDIUM-SEVERITY GAPS (Impact 3/5)

### GAP-16: Arabic Language Support is Partial
**Impact:** 3/5 — **Effort:** Low  
**Description:** UI has bilingual support but PDF reports are English-primary with Arabic sections. Full Arabic reports are expected by Ministry of HR and government clients.  
**Required Deliverable:** Fully Arabic PDF report mode, RTL-optimized layout, Arabic typography optimization.

### GAP-17: No API Documentation / Developer Portal
**Impact:** 3/5 — **Effort:** Low  
**Description:** There is no Swagger/OpenAPI documentation, no developer portal, no SDK, no webhook documentation. Enterprise IT teams will demand API documentation before procurement.  
**Required Deliverable:** Auto-generated Swagger docs, API reference documentation, integration guide, sample code library.

### GAP-18: No Audit Evidence Package for Regulators
**Impact:** 3/5 — **Effort:** Low  
**Description:** An `audit_package_builder.py` exists but is not surfaced in the UI. Regulatory clients (Ministry of HR, banking regulators) need a one-click audit export.  
**Required Deliverable:** Audit package download button in UI, structured audit evidence PDF, compliance certification format.

### GAP-19: Employee Risk Table Is Not Exportable to HRIS Format
**Impact:** 3/5 — **Effort:** Low  
**Description:** CSV export exists but is not formatted for HRIS import (SAP format, Workday format, Oracle HCM format). Data has to be re-mapped before it can be actioned in any HRIS.  
**Required Deliverable:** HRIS-format export templates (SAP, Workday, Oracle), field mapping configuration.

### GAP-20: No White-Labeling / Brand Configuration
**Impact:** 3/5 — **Effort:** Low  
**Description:** All reports display "Adaptive Workforce Intelligence" branding. Enterprise clients want reports branded with their own logo and colors. Consulting firms (Big 4) reselling AWI need client-branded output.  
**Required Deliverable:** Logo upload, color scheme configuration, report header/footer customization, partner branding mode.

### GAP-21: No Multilingual Support Beyond EN/AR
**Impact:** 3/5 — **Effort:** Medium  
**Description:** GCC clients include UAE, Kuwait, Bahrain, Qatar with different Arabic dialects and some English/French preferences. PIF portfolio companies may include multinational workforces.  
**Required Deliverable:** Modular translation framework, French support for North Africa, dialect-aware Arabic.

### GAP-22: Dashboard Has No Time-Series View
**Impact:** 3/5 — **Effort:** Medium  
**Description:** The dashboard shows a single point-in-time analysis. There is no longitudinal view showing how risk has evolved over multiple analysis periods.  
**Required Deliverable:** Trend dashboard (risk over time), analysis-to-analysis comparison, momentum indicators.

### GAP-23: No Mobile Application
**Impact:** 3/5 — **Effort:** High  
**Description:** Executive dashboards must be mobile-accessible. A CEO reviewing workforce risk before a board meeting expects to do it on an iPad, not a desktop.  
**Required Deliverable:** Mobile-responsive PWA, executive summary mobile view, push notifications for critical risk alerts.

### GAP-24: No API Rate Limiting or Usage Analytics
**Impact:** 3/5 — **Effort:** Low  
**Description:** No metering of API usage, no rate limiting, no usage analytics. Cannot support commercial licensing based on usage volume.  
**Required Deliverable:** Request metering, rate limiting middleware, usage dashboard, billing event hooks.

### GAP-25: Simulation Has No Financial Impact Dimension
**Impact:** 3/5 — **Effort:** Medium  
**Description:** Simulation shows "risk reduction %" but not financial impact. "If we increase training access, we reduce risk by 4.6%" is less compelling than "...saving SAR 3.2M in attrition replacement costs."  
**Required Deliverable:** Financial impact overlay on simulation scenarios, ROI per intervention, payback period calculator.

---

## SECTION 5: INFRASTRUCTURE GAPS

### GAP-26: Single-Machine SQLite Is Not Production-Scale
**Impact:** 5/5 — **Effort:** High  
**Description:** SQLite works for single-machine demos but fails at enterprise scale (concurrent users, 10K+ employee datasets, multi-client deployments).  
**Required Deliverable:** PostgreSQL migration path, connection pooling, read replicas for reporting, cloud-native storage option.

### GAP-27: No CI/CD Pipeline
**Impact:** 3/5 — **Effort:** Medium  
**Description:** No automated deployment pipeline, no staging environment, no automated testing on commit, no deployment rollback capability.  
**Required Deliverable:** GitHub Actions pipeline, staging environment, automated test gate, container registry, deployment runbook.

### GAP-28: No Observability / Monitoring
**Impact:** 4/5 — **Effort:** Medium  
**Description:** No application performance monitoring, no error tracking, no uptime monitoring, no SLA measurement. Enterprise contracts require 99.9% SLA with monitoring proof.  
**Required Deliverable:** APM integration (Datadog/Grafana), error tracking (Sentry), health dashboards, SLA reporting.

### GAP-29: No Disaster Recovery / Backup
**Impact:** 4/5 — **Effort:** Medium  
**Description:** SQLite database has no automated backup, no point-in-time recovery, no geographic redundancy. Loss of the local database means loss of all analysis history.  
**Required Deliverable:** Automated backup (S3/Azure Blob), point-in-time recovery, cross-region replication option.

### GAP-30: No Data Residency Controls
**Impact:** 5/5 — **Effort:** Medium  
**Description:** Saudi clients (banking, government) require data to remain in-Kingdom (Saudi data residency requirements). No data residency certification or configuration exists.  
**Required Deliverable:** Data residency configuration (KSA region), data flow documentation, residency certification, cloud provider region selection.

---

## SECTION 6: COMMERCIAL READINESS GAPS

### GAP-31: No Pricing Model / Licensing Engine
**Impact:** 5/5 — **Effort:** Low  
**Description:** No pricing tiers, no per-seat licensing, no usage-based billing, no enterprise contract templates exist.  
**Required Deliverable:** 3-tier pricing model (Starter/Professional/Enterprise), licensing terms, contract templates.

### GAP-32: No Sales Demo / Sandbox Environment
**Impact:** 4/5 — **Effort:** Low  
**Description:** Demo mode exists with hardcoded Saudi data, but there is no curated sales demo flow, no "wow moment" scenario, no competitive battle card.  
**Required Deliverable:** Curated 5-minute demo flow, industry-specific demo datasets (Banking, O&G, Telecom), battle card vs. Workday/SAP.

### GAP-33: No Customer Success / Onboarding Module
**Impact:** 4/5 — **Effort:** Medium  
**Description:** No guided onboarding wizard, no "getting started" templates, no quick-win report presets, no implementation methodology documentation.  
**Required Deliverable:** Onboarding wizard, quick-start guide (Arabic + English), implementation playbook.

### GAP-34: No Partner / Reseller Program
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Big 4 consulting firms (Deloitte, KPMG, EY, PwC Saudi) could resell AWI embedded in their HR transformation engagements. No partner program, white-labeling, or commission structure exists.  
**Required Deliverable:** Partner portal, white-label mode, reseller margin structure, co-branded report templates.

### GAP-35: No Trust Center / Security Documentation
**Impact:** 4/5 — **Effort:** Low  
**Description:** Enterprise procurement teams require a Trust Center — SOC 2 certification or equivalent, penetration test reports, data flow diagrams, DPIA documentation.  
**Required Deliverable:** Security documentation package, PDPL compliance certificate, data flow diagram, penetration test (or bug bounty program).

---

## SECTION 7: AI GOVERNANCE GAPS

### GAP-36: No Model Fairness / Bias Audit
**Impact:** 4/5 — **Effort:** Medium  
**Description:** AWI scores employees for risk, but has no demographic fairness audit. Does the model systematically score expatriate workers higher risk than Saudi nationals? Does it disadvantage women? This is a regulatory and reputational risk.  
**Required Deliverable:** Demographic parity analysis, equalized odds testing, fairness report, bias mitigation options.

### GAP-37: No Model Drift Monitoring in Production
**Impact:** 4/5 — **Effort:** Medium  
**Description:** `drift_monitor.py` exists but is not wired into any production alerting. If client data distribution shifts, model performance degrades silently.  
**Required Deliverable:** Automated drift detection alerts, performance degradation notifications, model re-training triggers.

### GAP-38: No Human-in-the-Loop Workflow
**Impact:** 3/5 — **Effort:** Medium  
**Description:** Recommendations are generated but there is no workflow for HR professionals to review, accept, reject, or override AI recommendations. Regulators increasingly require human oversight of AI decisions affecting employment.  
**Required Deliverable:** Recommendation review workflow, override logging, human decision audit trail, explainability on demand.

### GAP-39: No Model Card / AI Disclosure Documentation
**Impact:** 3/5 — **Effort:** Low  
**Description:** No standardized model card (as per Google/Hugging Face standards) exists. Enterprise clients and regulators increasingly require model transparency documentation.  
**Required Deliverable:** Model card (intended use, limitations, fairness metrics, training data characteristics), published in platform UI.

---

## SECTION 8: REPORTING GAPS

### GAP-40: No Longitudinal Cohort Analysis
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Cannot compare attrition cohorts across hire dates, promotion cohorts, or tenure bands. "Do employees who received promotions in Year 1 have lower 3-year attrition?" is unanswerable.  
**Required Deliverable:** Cohort analysis module, survival analysis (Kaplan-Meier), tenure-based risk curves.

### GAP-41: No Department-Level Action Plans
**Impact:** 4/5 — **Effort:** Low  
**Description:** Reports identify high-risk departments but do not generate department-specific action plans. An Operations Director needs a plan for Operations, not a company-wide recommendation.  
**Required Deliverable:** Department-specific action plans, tailored to that department's top risk drivers, automated from existing intelligence.

### GAP-42: No Trend Narrative Between Analyses
**Impact:** 3/5 — **Effort:** Low  
**Description:** When a second analysis is run, there is no narrative comparing it to the first. "Risk has increased by 5 points in Finance since January" is high-value insight.  
**Required Deliverable:** Delta analysis narrative, trend commentary, improvement/deterioration flags.

### GAP-43: No NPS / Engagement Score Integration
**Impact:** 3/5 — **Effort:** Medium  
**Description:** eNPS, ENPS, and engagement survey scores are the most commonly available HR data points. AWI does not accept or process engagement survey data as primary input.  
**Required Deliverable:** Engagement survey template, NPS → risk correlation model, hybrid risk score (behavioral + survey).

---

## SECTION 9: SECTOR-SPECIFIC GAPS

### GAP-44: No Vision 2030 Alignment Reporting
**Impact:** 5/5 — **Effort:** Medium  
**Description:** Every Saudi client's board presentation references Vision 2030. AWI produces no output that frames workforce intelligence in terms of Vision 2030 KPIs (Saudization, women's participation, private sector employment).  
**Required Deliverable:** Vision 2030 workforce compliance dashboard, Saudization trajectory, women workforce participation index.

### GAP-45: No GOSI Integration
**Impact:** 4/5 — **Effort:** High  
**Description:** Saudi General Organization for Social Insurance (GOSI) data is the most reliable source of actual attrition in Saudi Arabia (subscription changes = employment changes). GOSI integration would provide ground truth for model validation.  
**Required Deliverable:** GOSI data ingestion adapter, GOSI-validated attrition metric, regulatory reporting alignment.

### GAP-46: No Seasonal / Ramadan Adjustment
**Impact:** 3/5 — **Effort:** Low  
**Description:** Saudi workforce patterns are heavily influenced by Ramadan, Eid, Hajj season, and national holidays. Attrition risk models should account for these seasonal factors.  
**Required Deliverable:** Saudi seasonal calendar integration, Hijri calendar support, seasonal adjustment factors in risk scoring.

### GAP-47: No Public Sector / Government Workforce Module
**Impact:** 4/5 — **Effort:** Medium  
**Description:** Government clients (Ministry of HR, HRDF, PIF portfolio companies) have fundamentally different workforce structures (Civil Service grades, pension schemes, secondment). AWI treats all workforces identically.  
**Required Deliverable:** Government workforce module, Civil Service grade mapping, pension-adjusted retention model, public sector benchmark.

---

## SECTION 10: PRIORITIZED GAP REMEDIATION ROADMAP

### Sprint 1 (Weeks 1–4): Quick Wins, Maximum Impact
| Priority | Gap | Effort | Business Impact |
|----------|-----|--------|-----------------|
| 1 | GAP-01: ROI Engine Surface | Low | Immediate C-suite value |
| 2 | GAP-10: Board Report Redesign | Medium | Sales enablement |
| 3 | GAP-17: API Documentation | Low | Enterprise IT procurement |
| 4 | GAP-20: White-labeling | Low | Partner/consulting sales |
| 5 | GAP-41: Dept Action Plans | Low | User adoption |

### Sprint 2 (Weeks 5–10): Market Differentiators
| Priority | Gap | Effort | Business Impact |
|----------|-----|--------|-----------------|
| 6 | GAP-02: Industry Benchmarking | Medium | Competitive differentiation |
| 7 | GAP-05: Saudization Module | Medium | Regulatory compliance market |
| 8 | GAP-25: Financial Simulation | Medium | CFO-level engagement |
| 9 | GAP-44: Vision 2030 Reporting | Medium | Government clients |
| 10 | GAP-36: Fairness Audit | Medium | Regulatory risk mitigation |

### Sprint 3 (Weeks 11–20): Enterprise Infrastructure
| Priority | Gap | Effort | Business Impact |
|----------|-----|--------|-----------------|
| 11 | GAP-03: SaaS Architecture | High | Scale monetization |
| 12 | GAP-04: HRIS Integration | High | Enterprise procurement |
| 13 | GAP-26: PostgreSQL Migration | High | Production-grade scaling |
| 14 | GAP-28: Observability | Medium | SLA credibility |
| 15 | GAP-06: ONA Module | High | Premium tier differentiation |

---

## SECTION 11: ENTERPRISE VALUE ASSESSMENT

### Current Enterprise Value Score: 52/100

| Dimension | Score | Weight | Weighted Score |
|-----------|-------|--------|----------------|
| Technical Rigor | 82/100 | 15% | 12.3 |
| Executive Experience | 48/100 | 20% | 9.6 |
| Commercial Readiness | 25/100 | 20% | 5.0 |
| Integration Capability | 15/100 | 15% | 2.3 |
| Governance/Compliance | 75/100 | 15% | 11.3 |
| Market Differentiation | 60/100 | 15% | 9.0 |
| **TOTAL** | | | **49.5/100** |

### Target Enterprise Value Score (Post-Remediation): 82/100

Achieving an 82/100 enterprise value score requires completing all Sprint 1 and Sprint 2 items and at least 50% of Sprint 3. This positions AWI for commercial SaaS launch at SAR 200K–800K per enterprise contract.

---

*This document is an internal strategic planning artifact. All capability assessments are based on observed platform state as of June 2026.*
