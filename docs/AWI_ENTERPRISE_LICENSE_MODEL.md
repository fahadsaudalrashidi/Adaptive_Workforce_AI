# AWI Enterprise License Model
## Commercial Terms, Deployment Rights, and Usage Boundaries
**Version:** v2.0.1-enterprise | **Effective Date:** 2026

---

## License Type: Enterprise On-Premises Perpetual License

AWI is sold as an **Enterprise On-Premises Perpetual License** with optional annual maintenance. The customer receives the right to deploy and operate AWI software on their own infrastructure, in perpetuity, with no recurring SaaS fees.

---

## Core License Principles

### 1. One License = One Organisation
Each license covers one legal entity and its wholly-owned subsidiaries.
- Aramco license → all Aramco business units within the Kingdom
- STC license → all STC subsidiaries (STC Pay, STC Solutions, etc.)
- Riyad Bank license → Riyad Bank and wholly-owned domestic subsidiaries

### 2. One Deployment = One Environment
Each license includes the right to deploy on one production server cluster. A separate development/staging environment is included at no additional cost.

### 3. No Per-Seat Fees
Users are unlimited within the licensed organisation. The license is priced by organisation tier (headcount × industry multiplier), not per user.

### 4. No Usage-Based Billing
There are no API call fees, storage fees, or analysis volume fees. The license covers unlimited analyses within the licensed organisation.

### 5. No External Data Transfer
AWI must not transmit workforce data to any external service. The customer's data stays on the customer's infrastructure. This is a contractual requirement, not a technical limitation.

---

## Pricing Tiers

| Tier | Organisation Size | Industry | Annual Price (SAR) | Notes |
|------|-------------------|----------|--------------------|-------|
| Tier 1 — Growth | < 1,000 employees | Any | 450,000 | Includes 1 year maintenance |
| Tier 2 — Enterprise | 1,000 – 10,000 employees | Standard | 900,000 | Includes 1 year maintenance |
| Tier 2+ — Enterprise | 1,000 – 10,000 employees | Financial / Energy | 1,200,000 | SAMA / NCA compliance modules |
| Tier 3 — Large Enterprise | 10,000 – 50,000 employees | Standard | 1,800,000 | Includes 1 year maintenance |
| Tier 3+ — Large Enterprise | 10,000 – 50,000 employees | Government / SOE | 2,400,000 | CITC / HRSD compliance modules |
| Tier 4 — Strategic | > 50,000 employees | Any | Custom | Multi-deployment rights included |

*All prices exclude VAT (15%). Payment: 50% on contract signature, 50% on delivery.*

---

## What Is Included

### License (Perpetual)
- Full AWI source code for the licensed version
- Deployment rights on customer infrastructure (unlimited nodes within one cluster)
- Documentation package (deployment guide, user manual, API reference)
- 30-day implementation support

### Annual Maintenance (Optional — billed annually)
| Maintenance Tier | Price (% of license) | Includes |
|-----------------|---------------------|---------|
| Standard | 18% per year | Software updates, bug fixes, security patches |
| Premium | 24% per year | Standard + priority support (48h SLA) + minor version upgrades |
| Strategic | 30% per year | Premium + quarterly strategic roadmap sessions + custom report templates |

### Professional Services (Billed Separately)
| Service | Rate (SAR) |
|---------|-----------|
| Remote implementation (4 days) | 120,000 |
| On-site implementation (4 days, KSA) | 160,000 |
| Custom integration (SSO/LDAP/HRMS) | 80,000/sprint |
| Training (half-day, up to 20 users) | 40,000 |
| Custom dashboard development | 60,000/module |

---

## License Restrictions

The customer may NOT:
1. Resell, sublicense, or redistribute AWI software
2. Use AWI to process data belonging to a third-party organisation
3. Reverse-engineer the ML models or scoring algorithms
4. Remove or alter copyright notices or watermarks in generated reports
5. Deploy AWI in a multi-tenant configuration serving multiple unrelated organisations
6. Use AWI as a bureau service (processing other companies' data for a fee)

---

## Intellectual Property

- AWI software, ML models, scoring indices (WSI, RHI, TFRI, etc.), report templates, and UI design remain the property of AWI (the vendor).
- Customer-specific configurations, data, and analysis outputs belong to the customer.
- Customer-provided data used to train or fine-tune any AWI model remains the property of the customer and must not be used for any other purpose.

---

## Support and Warranty

### Warranty (12 months from delivery)
AWI warrants that the software will perform substantially as described in the documentation. If a defect is found, AWI will provide a fix or workaround within the SLA below.

### Defect SLA
| Severity | Definition | Response | Resolution |
|----------|-----------|----------|-----------|
| Critical | System down, data loss | 4 hours | 24 hours |
| High | Core feature broken | 24 hours | 5 business days |
| Medium | Feature degraded | 48 hours | 15 business days |
| Low | Cosmetic / minor | 5 business days | Next release |

### Out-of-Scope Support
The following are not covered under standard maintenance:
- Customer infrastructure (OS, networking, TLS certificates)
- Custom integrations not delivered by AWI
- Data quality issues in customer-provided datasets
- Third-party library vulnerabilities (we provide patches in maintenance releases)

---

## Technology Escrow

For Tier 3+ and Tier 4 customers, AWI offers source code escrow with a third-party escrow agent. If AWI (the vendor) ceases operations, the escrowed source code is released to the customer, granting them the right to maintain the software internally.

Escrow is available as an optional add-on: SAR 80,000 setup + SAR 40,000 annually.

---

## Compliance and Certifications

| Certificate / Standard | Status |
|----------------------|--------|
| SAMA Cybersecurity Framework | In progress (Phase 31) |
| NCA ECC-1:2018 | In progress (Phase 31) |
| Saudi PDPL compliance | Compliant — data stays on-premises |
| ISO 27001 (vendor) | Roadmap (2026 Q4) |
| HRSD integration readiness | Available |

---

## Competitive Positioning vs. SaaS Alternatives

| Factor | AWI (On-Premises) | SAP SuccessFactors | Oracle HCM | Qureos.ai |
|--------|------------------|--------------------|-----------|-----------|
| Data leaves org? | Never | Yes (cloud) | Yes (cloud) | Yes (cloud) |
| Annual cost (5,000 emp) | SAR 900K (one-time + maint) | SAR 2.5M+/year | SAR 3M+/year | SAR 800K+/year |
| Air-gap compatible | Yes | No | No | No |
| Custom ML models | Yes | Limited | No | No |
| HRSD/PDPL native | Yes | Partial | Partial | Unknown |
| Time-to-value | 4–8 weeks | 6–18 months | 9–24 months | 3–6 months |

---

## Renewals and Upgrades

- **Maintenance renewal:** Annual, invoiced 60 days before expiry
- **Major version upgrade** (e.g., v2 → v3): Licensed separately (50% of original license fee for maintenance customers)
- **Additional deployment rights:** 30% of original license fee per additional production cluster

---

*AWI Enterprise Workforce Intelligence Platform | Commercial and Confidential*
*All prices subject to change. Final terms per signed contract.*
