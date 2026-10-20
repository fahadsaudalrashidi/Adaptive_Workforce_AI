# CUSTOMER ADOPTION BARRIERS
## Adaptive Workforce Intelligence — Phase B Customer Perspective Audit
**Classification:** Sales & Commercial Strategy  
**Perspective:** Fortune 500 Chief Procurement Officer / HR Leadership  
**Simulated Clients:** Aramco, STC, SABIC, Riyad Bank, Saudi National Bank, Ministry of Human Resources, PIF Portfolio Companies  
**Date:** June 2026

---

## EXECUTIVE FRAMING

This document answers the question: **"Would I pay SAR 500,000 for AWI?"** from the perspective of a CPO or CHRO at a major Saudi enterprise. It maps every barrier between AWI's current state and a signed enterprise contract.

The answer today is: **"Not yet — but closer than any domestic competitor."**

The answer in 6 months, with targeted improvements: **"Yes, conditionally."**

---

## CLIENT SIMULATION 1: SAUDI ARAMCO

**Profile:** 70,000+ employees, global workforce, highly Saudized, complex grade structure, SAP SuccessFactors primary HRIS, world-class internal analytics team.

### Would They Buy?
**Probability: 15%** (Current State) → **65%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER A1 — SAP Integration Requirement (BLOCKING)**
> "We're a SAP house. Everything integrates with SuccessFactors. If you can't connect to our HRIS, we'd have to manually export data for every analysis. That's not enterprise-grade — that's a consultancy project."

AWI requires manual file upload. Aramco runs daily automated HR data feeds. No SAP OData connector = no enterprise deployment.

**BARRIER A2 — Data Residency and Security Clearance (BLOCKING)**
> "We operate under ARAMCO security protocols and Saudi national security regulations. Any platform handling our workforce data needs a data residency guarantee, security audit clearance, and approval from our Information Security directorate. Your SQLite-based local deployment is interesting but undocumented."

Current state: no formal security certification, no penetration test report, no data residency documentation.

**BARRIER A3 — Scale Limitation**
> "We have 70,000 employees across 60 countries. Your analysis pipeline processes 1,191 employees in 0.2 seconds. Can it handle 70,000? What about 500,000 contractor records? What are the SLAs?"

No benchmarking data for large datasets. No multi-node deployment documentation.

**BARRIER A4 — Internal Analytics Credibility**
> "We have 25 data scientists who built our own attrition models. What do you add beyond what we already have? Our models use 3 years of longitudinal data. You use one snapshot."

AWI needs a clear differentiation story vs. internal capabilities: governance, explainability, executive-layer synthesis, time-to-insight vs. months of engineering.

**BARRIER A5 — No Integration with Aramco Performance Framework**
> "Our performance management framework, IDP system, and training records are all in SuccessFactors. Your risk scores don't incorporate performance data, IDP completion, or training history."

---

## CLIENT SIMULATION 2: STC (Saudi Telecom Company)

**Profile:** 20,000+ employees, technology-forward, already investing in AI, active digital transformation program, Oracle HCM primary HRIS.

### Would They Buy?
**Probability: 30%** (Current State) → **75%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER S1 — Price Justification (BLOCKING)**
> "We've been quoted SAR 2M for Workday People Analytics. Why should we pay anything for a tool that lacks the benchmarking, real-time monitoring, and integration that Workday offers? What's the ROI calculation on buying AWI?"

No ROI calculator, no business case template, no case studies with quantified savings.

**BARRIER S2 — Bilingual Board Reporting**
> "Our board presentations are in Arabic. Our CEO and most board members prefer Arabic. Your English-first reports with Arabic sections don't work for board-level presentations."

Current: English primary with Arabic sections. Required: full Arabic report mode.

**BARRIER S3 — Oracle Integration**
> "We're Oracle-first. SuccessFactors, Workday, Oracle — we use Oracle HCM. You need to connect to Oracle's REST APIs."

**BARRIER S4 — Governance Approval**
> "Our data governance team needs to approve any new platform that touches employee data. They'll want a Data Protection Impact Assessment (DPIA), a data flow diagram, and evidence of PDPL compliance with a legal opinion."

`SAUDI_PDPL_READINESS.md` exists but is not a client-ready DPIA. No legal opinion documentation.

**BARRIER S5 — No Change Management / Training Package**
> "Who trains our HR team? Who supports us when something breaks? What's the SLA? Do you have a customer success team?"

No SLA definition, no support tier documentation, no training materials.

---

## CLIENT SIMULATION 3: SABIC (Saudi Basic Industries Corporation)

**Profile:** 32,000+ employees, highly international workforce, science/engineering-heavy, complex talent pipeline, BASF parent company influence.

### Would They Buy?
**Probability: 20%** (Current State) → **60%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER B1 — Global Workforce Complexity**
> "We have employees in 50 countries. Our Saudi workforce is 40% of our total. Your platform seems built only for Saudi context. How does it handle German engineers, American chemists, Indian IT specialists?"

AWI is Saudi-optimized. Global multilingual support is limited. Column normalization assumes Saudi HR terminology.

**BARRIER B2 — Scientific Validity with Parent Company**
> "BASF's analytics team will review your methodology. They'll want peer-reviewed validation of your theory constructs and a comparison with their in-house models."

The extensive governance documents (THEORY_CONSTRUCT_VALIDITY_AUDIT.md, SCIENTIFIC_TRACEABILITY_AUDIT.md) address this — but they're not presented as a client-readable scientific brief. Need a 2-page methodology executive summary.

**BARRIER B3 — No Manufacturing/Operations Workforce Module**
> "Our highest attrition is in plant operations. Your model doesn't seem to account for shift work, physical working conditions, or safety incident correlation with attrition."

AWI is HR-data agnostic but has no manufacturing-specific construct mapping.

**BARRIER B4 — Procurement Threshold**
> "Anything above SAR 1M goes to a full RFP process. You need to be in our Approved Vendor List, which requires ISO 27001 certification or equivalent."

No ISO 27001, no approved vendor status.

---

## CLIENT SIMULATION 4: RIYAD BANK

**Profile:** 7,000+ employees, financial services, regulatory-heavy (SAMA oversight), workforce Saudization focus, Oracle HRMS.

### Would They Buy?
**Probability: 40%** (Current State) → **80%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER R1 — SAMA Compliance**
> "We're regulated by SAMA. Any system touching employee data must comply with SAMA cybersecurity framework and PDPL. Can you provide SAMA-compliant deployment documentation?"

PDPL documentation exists; SAMA-specific cybersecurity framework documentation is absent.

**BARRIER R2 — Saudization Focus**
> "Our #1 workforce priority is Nitaqat compliance and Saudization trajectory. Your platform doesn't track Saudization rates, nationalization targets, or compliance risk at all."

No Saudization module (GAP-05 from enterprise gap analysis).

**BARRIER R3 — Small Dataset Concern**
> "We have 7,000 employees. Your ML model seems optimized for larger datasets. What's the minimum dataset size for reliable predictions?"

No minimum dataset documentation, no accuracy degradation curves for small datasets.

**BARRIER R4 — Compensation Sensitivity**
> "In banking, salary is the #1 retention driver. Your model needs to incorporate our salary-to-market ratio data. Can it accept compensation benchmarking data as an input?"

AWI accepts whatever columns are in the dataset, but there's no compensation benchmarking integration.

**BARRIER R5 — Most Likely to Purchase**
> Riyad Bank is the most likely early customer. Smaller IT footprint, Saudization urgency, board-level awareness of HR risk. Primary barrier is Saudization module and Arabic board reporting.

---

## CLIENT SIMULATION 5: SAUDI NATIONAL BANK (SNB)

**Profile:** 11,000+ employees (post AlAhli merger), complex integration workforce, Saudization pressure, SAP S/4HANA shop.

### Would They Buy?
**Probability: 25%** (Current State) → **70%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER N1 — Post-Merger Workforce Complexity**
> "We completed the merger of NCB and Samba. Our workforce is in integration mode. We need to identify flight risk across two previously separate organizations with different cultures. Can your system handle cross-entity analysis?"

No multi-entity / multi-subsidiary support.

**BARRIER N2 — SAP Integration (as with Aramco)**
Same as A1 — SAP shop requires native integration.

**BARRIER N3 — Credit Risk Analogy Expectation**
> "We're a bank. We think in risk ratings, loss-given-default, probability of departure. Can you give us workforce risk ratings comparable to our credit risk framework? Grade 1-10, not just high/medium/low."

Current risk bands (4 categories) are too coarse for banking professionals accustomed to 10-point rating scales.

---

## CLIENT SIMULATION 6: MINISTRY OF HUMAN RESOURCES (MOHRSD)

**Profile:** Government ministry, national policy mandate, oversees all Saudi private sector employment, Vision 2030 delivery authority, Qiwa platform owner.

### Would They Buy?
**Probability: 10%** (Current State) → **55%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER G1 — National Platform vs. Point Solution**
> "We already own Qiwa — the national labor platform. We need a national workforce intelligence layer, not a single-company tool. Can AWI operate at population scale — 12 million workers?"

AWI is a company-level tool. It has no concept of cross-company, sector-level, or national workforce analysis.

**BARRIER G2 — Government Procurement Process**
> "Any government procurement above SAR 100K requires full tender (منافسة), vendor qualification, and ministry approval. Your timeline would be 18 months minimum."

Government sales cycle is fundamentally longer. Need a pilot program strategy.

**BARRIER G3 — Arabic-First Requirement**
> "All government platforms must be Arabic-first. Your UI must be natively Arabic with English as an option, not the reverse."

Current: English-first with Arabic language toggle.

**BARRIER G4 — Open Source / Government Cloud Requirement**
> "Government systems in Saudi Arabia must be hosted on government-approved cloud infrastructure (Saudi Government Cloud or Hyperscaler with KSA data center). No offshore data storage."

Deployment architecture documentation for government cloud does not exist.

**BARRIER G5 — Highest Value Client, Longest Sales Cycle**
> Ministry partnership would establish AWI as the de facto national workforce intelligence standard. However, the path requires a different product (national scale, Arabic-first, government procurement strategy).

---

## CLIENT SIMULATION 7: PIF PORTFOLIO COMPANY (e.g., NEOM, Diriyah Gate Authority, Qiddiya)

**Profile:** New economy entities, significant hiring mandates, Saudization targets, global talent competition, modern HR stacks (often Workday or SAP), executive-driven.

### Would They Buy?
**Probability: 45%** (Current State) → **80%** (Post-Remediation)

### Barriers to Purchase:

**BARRIER P1 — Talent Competition Context**
> "We're competing for global talent — Saudi nationals with international options, expat specialists who can go anywhere. Our workforce risk isn't about attrition from a legacy company; it's about failing to attract and keep the talent needed to build a new city / entertainment destination."

AWI scores retention risk but doesn't quantify external market competition or replacement difficulty for specialized roles.

**BARRIER P2 — Greenfield HR Data**
> "We started 5 years ago. We don't have 5 years of attrition history. Your model — does it work on 3 years of data? 2 years?"

No minimum data requirements documentation.

**BARRIER P3 — Most Commercially Accessible**
> PIF entities are modern, Workday/SAP compatible, executive-driven, and budget-authorized. They're the best near-term commercial target. Primary need: Saudization tracking, ROI reporting, executive dashboards.

---

## UNIVERSAL ADOPTION BARRIERS (All Clients)

### BARRIER U1 — No Business Case Template
**Severity: CRITICAL**
Every enterprise client needs a business case document to justify procurement internally. There is no "AWI Business Case Template" — a document that a junior HR analyst can complete with their data to present to their CFO.

**Required:** Business case template with ROI model, comparable case studies (anonymized), payback period calculator.

### BARRIER U2 — No Reference Customers
**Severity: CRITICAL**
"Who else uses this? What results did they achieve?" is the first question from any procurement team. Without reference customers, every sale is a leap of faith.

**Required:** Pilot program strategy to generate 3 reference customers before commercial launch. Target: 2 Saudi banks + 1 government entity.

### BARRIER U3 — No Support / SLA Model
**Severity: HIGH**
Enterprise clients buy support, not software. Without defined SLAs, support tiers (Gold/Silver/Bronze), and escalation paths, AWI cannot be seriously considered for enterprise procurement.

**Required:** Support tiers document, SLA definition (99.9% uptime), incident response times, designated CSM model.

### BARRIER U4 — Price Anchoring Problem
**Severity: HIGH**
There is no pricing. When enterprise procurement asks "how much?", the answer must be immediate and confidence-inspiring. Ad-hoc pricing signals immaturity.

**Required:** Pricing sheet (per-seat, per-analysis-run, enterprise flat-fee options), discount authorization matrix.

### BARRIER U5 — No Pilot / POC Framework
**Severity: HIGH**
Enterprise clients in Saudi Arabia do not buy software without a proof-of-concept (POC) on their own data. There is no defined 30-day POC framework.

**Required:** POC framework (30-day, structured deliverables, success criteria, commercialization pathway).

### BARRIER U6 — No Arabic Procurement Documentation
**Severity: MEDIUM**
RFP responses, data processing agreements, service level agreements — all need Arabic versions for Saudi public sector and many private sector clients.

**Required:** Arabic versions of key commercial documents.

### BARRIER U7 — The "AI Risk" Concern
**Severity: MEDIUM**
> "If your AI flags one of my employees as high-risk and I take action — and they sue — am I liable? Does your platform create legal risk for us?"

No employment law guidance, no liability documentation, no recommended usage policies.

**Required:** Usage policy guide, limitation-of-liability documentation, recommended HR governance workflow (human-in-the-loop requirement).

---

## ADOPTION PROBABILITY MATRIX

| Client | Now | 6mo | 12mo | Key Unlock |
|--------|-----|-----|------|------------|
| Aramco | 15% | 40% | 65% | SAP integration, Security cert |
| STC | 30% | 65% | 80% | Arabic reports, Oracle connector |
| SABIC | 20% | 50% | 70% | Global support, Scientific brief |
| Riyad Bank | 40% | 75% | 85% | Saudization module, SAMA docs |
| SNB | 25% | 60% | 75% | SAP integration, Arabic reports |
| MOHRSD | 10% | 30% | 55% | National scale, Arabic-first |
| PIF Entity | 45% | 80% | 90% | ROI model, Saudization, Workday |

**Prioritized Target Sequence:** PIF Entity → Riyad Bank → STC → SNB → Aramco → SABIC → MOHRSD

---

## RECOMMENDATION: IMMEDIATE ACTIONS

1. **Build the Business Case Template** (Week 1) — single highest-leverage commercial document
2. **Initiate Riyad Bank Pilot Discussion** (Week 2) — highest probability, clearest value case
3. **Complete Saudization Module** (Week 4) — unlocks 3 of 7 target clients
4. **Publish Arabic Board Report** (Week 4) — unlocks 4 of 7 target clients
5. **Draft PDPL + SAMA Compliance Package** (Week 6) — required for financial sector
6. **Design 30-Day POC Framework** (Week 2) — needed before any client conversation

---

*Customer simulations are based on publicly known organizational profiles and standard enterprise software procurement patterns in the Saudi market.*
