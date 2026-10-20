# AWI — Top 50 Improvements
## Ranked by Business Value (Revenue Unlock, Risk Elimination, Deal Velocity)

**Ranking Methodology:** Each improvement scored on:
- Revenue unlock (0–5): direct impact on ARR potential
- Risk elimination (0–5): PDPL/security/valuation risk removed
- Deal velocity (0–5): how much it accelerates sales cycle
- Implementation effort (1–5): weeks to complete (lower = easier)
- **Business value = (Revenue + Risk + Velocity) × (1 / Effort)**

Items marked 🔴 are procurement blockers — deals cannot close without them.  
Items marked 🟡 are investor blockers — institutional funding requires them.  
Items marked 🟢 are demo/conversion accelerators.

---

## TIER 1 — CRITICAL PATH (Must complete before first paying client)

---

### #1 — Implement JWT Authentication and Bearer Token Middleware 🔴

**Audit Ref:** A-01, S-01  
**Severity:** CRITICAL  
**Business Value Score:** 15/15  

**What:** Add JWT Bearer token authentication to all API endpoints. Issue tokens via a login endpoint. Validate tokens in FastAPI middleware before any route handler executes. Restrict CORS to specific allowed origins.

**Business Impact:** Unblocks every enterprise procurement approval. Without authentication, no Saudi bank, government ministry, or healthcare group will sign a contract. This is the single highest-leverage change in the entire backlog.

**Technical Steps:**
1. Add `python-jose[cryptography]` and `passlib` to requirements
2. Create `POST /api/v1/auth/token` endpoint (local username/password for Phase 30; SSO bridge in Phase 31)
3. Add `Depends(verify_token)` to all route handlers
4. Replace CORS `allow_origins=["*"]` with explicit origin list
5. Add Authorization header injection in frontend fetch calls

**Effort:** 1 week  
**Expected ARR Unlock:** 100% of pipeline (all deals require auth)

---

### #2 — Replace In-Memory Session Store with SQLite/Redis-Backed Sessions 🔴

**Audit Ref:** A-03  
**Severity:** CRITICAL  
**Business Value Score:** 14/15  

**What:** Move `_SESSIONS` dict in `main.py` to a persistent store with TTL, eviction, and crash recovery. Use Redis for multi-user deployments, SQLite for single-org air-gapped deployments.

**Business Impact:** Enables >1 concurrent user without memory crash. Required for any multi-analyst deployment. Prevents silent data loss on server restart (analyst loses 30 minutes of work).

**Technical Steps:**
1. Create `backend/core/session_store.py` with SQLite backend (WAL mode, 4-hour TTL)
2. Store analysis result JSON, not raw DataFrames
3. Add background task to clean expired sessions every 15 minutes
4. Optional: Redis adapter for cloud/SaaS deployment

**Effort:** 1 week  
**Expected ARR Unlock:** Enables multi-analyst enterprise deployments (all enterprise-tier clients)

---

### #3 — Enforce HTTPS / TLS with nginx Reverse Proxy 🔴

**Audit Ref:** S-02  
**Severity:** CRITICAL  
**Business Impact:** PDPL technical security measures, NCSA ECC compliance, banking security policy requirements. No enterprise client will deploy AWI on HTTP.

**Technical Steps:**
1. Add nginx service to `docker-compose.yml`
2. Configure SSL termination (Let's Encrypt for SaaS, self-signed + docs for on-prem)
3. Add HSTS header: `max-age=63072000; includeSubDomains`
4. Redirect HTTP → HTTPS
5. Provide on-premises deployment guide with certificate setup

**Effort:** 3 days  
**Expected ARR Unlock:** Required for banking and government pilot deployment

---

### #4 — Remove Employee Risk Data from localStorage — Move to Session-Scoped Memory 🔴

**Audit Ref:** A-02  
**Severity:** CRITICAL  
**Business Impact:** Prevents XSS-based employee data exfiltration. PDPL Article 18 (technical safeguards) compliance. One data breach from localStorage exposure ends the business.

**Technical Steps:**
1. Replace `localStorage.setItem` with in-component React state for sensitive analysis data
2. Use `sessionStorage` only for non-sensitive UI state (active page, language preference)
3. Add `Content-Security-Policy` header in nginx: `default-src 'self'`
4. Add `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
5. Clear session state on explicit logout event

**Effort:** 3 days  
**Expected Risk Elimination:** Eliminates primary PDPL technical breach vector

---

### #5 — Implement Azure AD OIDC Single Sign-On 🔴

**Audit Ref:** E-01  
**Severity:** CRITICAL  
**Business Impact:** Every Saudi bank (SNB, Al Rajhi, Riyad Bank, SABB) has mandatory Azure AD for all internal tools. Without SSO, the banking segment is entirely inaccessible — no exceptions, no workarounds.

**Technical Steps:**
1. Add `msal` (Microsoft Authentication Library) to requirements
2. Create `POST /api/v1/auth/sso/azure` endpoint for OIDC authorization code flow
3. Add `GET /api/v1/auth/sso/azure/callback` for token exchange
4. Frontend: Add MSAL.js and replace login form with Azure AD redirect
5. Map Azure AD group membership to AWI roles (CHRO group → AWIRole.CHRO)

**Effort:** 2 weeks  
**Expected ARR Unlock:** Entire banking segment (Priority 1 clients, SAR 360–720K each)

---

### #6 — Make Risk Scores Deterministic (Remove Stochastic Jitter) 🔴

**Audit Ref:** A-05, R-01  
**Severity:** HIGH  
**Business Impact:** Reproducible scores are a prerequisite for HR audit trails, PDPL Article 14 (accuracy), and client trust. A single incident of "we ran the analysis twice and got different Priority Review lists" destroys confidence.

**Technical Steps:**
1. Remove `rng.uniform(-3.0, 3.0)` jitter from `employee_risk_scoring.py`
2. If score variance is scientifically needed, compute it as explicit `risk_score_low` / `risk_score_high` confidence interval
3. Add test: `assert score_run_1 == score_run_2` for identical input
4. Document in governance disclaimer: "Scores are deterministic given the same input data"

**Effort:** 1 day  
**Expected ARR Unlock:** Required for regulated-industry clients (banking, government)

---

### #7 — Implement RBAC Enforcement Middleware 🔴

**Audit Ref:** A-01 (Part 2)  
**Severity:** CRITICAL  
**Business Impact:** Enterprise procurement requires documented access control. CHRO should not be able to access tenant management. HR Analysts should not access raw PII exports. Role-based access is a standard checkbox in enterprise security questionnaires.

**Technical Steps:**
1. Add `require_role(AWIRole.CHRO, AWIRole.HR_MANAGER)` dependency injection to export endpoints
2. Add `require_role(AWIRole.SYSTEM_ADMIN)` to tenant management endpoints
3. Return HTTP 403 with structured error on role violation (log the attempt)
4. Frontend: Hide UI elements the current role cannot access (use role from JWT claim)

**Effort:** 1 week  
**Expected ARR Unlock:** Passes enterprise security questionnaire — required for procurement approval

---

### #8 — Add nginx Rate Limiting on Analysis Endpoints

**Audit Ref:** S-03  
**Severity:** HIGH  
**Business Impact:** Prevents DoS. Required for SaaS architecture. Prevents bill shock from accidental integration loops.

**Technical Steps:**
1. nginx `limit_req_zone $binary_remote_addr zone=analysis:10m rate=10r/m`
2. FastAPI `slowapi` middleware: 10 req/min per IP for analysis, 60 req/min for read endpoints
3. Return `429 Too Many Requests` with `Retry-After` header
4. Whitelist tenant API keys from global rate limits (they have per-tenant limits)

**Effort:** 2 days  
**Expected Risk Elimination:** Eliminates DoS vulnerability. Required for production hardening.

---

### #9 — Add Alembic Database Migrations

**Audit Ref:** A-06  
**Severity:** HIGH  
**Business Impact:** Phase 31 will require schema changes (adding `sso_subject` column, `rbac_role` columns, etc.). Without migrations, either data is lost or deployment is blocked. Client sites cannot be updated safely.

**Technical Steps:**
1. `pip install alembic`, initialize in `/backend/migrations/`
2. Create initial migrations for all 5 databases (or consolidate to 2)
3. Add `alembic upgrade head` to Docker startup script
4. Add CI check: migration applies cleanly on empty database
5. Add rollback migrations for every forward migration

**Effort:** 1 week  
**Expected Risk Elimination:** Prevents catastrophic data loss at client sites during updates

---

### #10 — Publish OpenAPI Documentation and Commit API Spec

**Audit Ref:** E-04  
**Severity:** MEDIUM  
**Business Impact:** Consulting resellers (KPMG, Deloitte) cannot scope integration engagements without API documentation. Resellers are the primary scale mechanism in COMMERCIALIZATION_PACKAGE.md Phase 2.

**Technical Steps:**
1. Add comprehensive docstrings with `summary`, `description`, `response_description` to all route handlers
2. Add request/response Pydantic models with field examples
3. Export: `python -m scripts/export_openapi.py > api-spec-v1.yaml`
4. Host at `/api/docs` (FastAPI built-in) and commit `api-spec-v1.yaml` to repository

**Effort:** 3 days  
**Expected ARR Unlock:** Enables consulting channel partnerships (Phase 2 GTM)

---

## TIER 2 — PRE-PILOT HARDENING (Complete before first client data enters the system)

---

### #11 — Add Multi-Stage Docker Build (Remove Build Tools from Production Image)

**Audit Ref:** D-01  
**Severity:** HIGH  
**Business Impact:** Enterprise Docker image security scans (Trivy, Clair) will flag `gcc`, `make`, `g++` as high-severity vulnerabilities in a production image.

**Technical Steps:**
1. Split Dockerfile into builder stage (with `build-essential`) and runtime stage (clean)
2. `COPY --from=builder /root/.local /root/.local` to transfer installed packages
3. Runtime image has zero build tools
4. Add `docker scan` or `trivy` to CI pipeline

**Effort:** 1 day  
**Expected Risk Elimination:** Passes enterprise Docker security audit

---

### #12 — Implement Audit Log API Endpoint

**Audit Ref:** E-03  
**Severity:** HIGH  
**Business Impact:** Banking internal audit and government ministry compliance teams will require audit trail exports before approving production deployment.

**Technical Steps:**
1. Add `GET /api/v1/audit/log?tenant_id=X&from=Y&to=Z&limit=100` route
2. Add `GET /api/v1/audit/export/csv` for compliance exports
3. Require `AWIRole.AUDITOR` or `AWIRole.CHRO` role
4. Paginate with cursor-based pagination for large logs

**Effort:** 2 days  
**Expected ARR Unlock:** Required for government and banking procurement sign-off

---

### #13 — Implement API Versioning (/api/v1/ prefix)

**Audit Ref:** A-09  
**Severity:** HIGH  
**Business Impact:** Integration partners and clients cannot maintain stable integrations without versioned APIs.

**Technical Steps:**
1. Introduce `/api/v1/` prefix on all routes
2. Keep `/api/local/` as deprecated alias with `Deprecation` response header
3. Add version negotiation in request headers: `AWI-API-Version: 1.0`
4. Document breaking change policy: 12-month deprecation period

**Effort:** 2 days  
**Expected ARR Unlock:** Required for consulting channel API integrations

---

### #14 — Add Error Message Sanitization (No Internal Paths in Responses)

**Audit Ref:** S-04  
**Severity:** HIGH  
**Business Impact:** Information disclosure vulnerability. Internal paths in error messages assist attackers and fail OWASP ASVS requirements.

**Technical Steps:**
1. Create `_safe_error_response(ref_code, client_message)` utility function
2. Replace all `detail=str(e)` with `detail=f"Analysis failed. Reference: {ref_code}"`
3. Log full exception with correlation ID server-side
4. Add correlation ID to response headers for support tracing

**Effort:** 1 day  
**Expected Risk Elimination:** Closes OWASP A05:2021 information exposure

---

### #15 — Implement Result Caching by Dataset Hash

**Audit Ref:** SC-03  
**Severity:** MEDIUM  
**Business Impact:** Demo experience improvement (instant results for previously-analyzed dataset). Reduces server load by 60–80% for repeat analyses (common in POC phase where same dataset is uploaded multiple times).

**Technical Steps:**
1. After computing analysis result, store in SQLite keyed by `dataset_hash`
2. On new upload: check cache before running pipeline; return cached result if found
3. TTL: 24 hours configurable per tenant
4. Add "Force Re-Analysis" button in UI
5. Include `cache_hit: true/false` and `cached_at` in response

**Effort:** 2 days  
**Expected ROI:** 60–80% reduction in server compute for repeat analyses. Transforms demo experience.

---

### #16 — Wire PlatformWalkthrough.tsx into App Router and Sidebar

**Audit Ref:** A-10  
**Severity:** MEDIUM  
**Business Impact:** The enterprise-branded walkthrough is a dead component. Every demo starts without showing it.

**Technical Steps:**
1. Add `'platform-walkthrough'` to `activePage` type in App.tsx
2. Add route case to render `<PlatformWalkthrough />`
3. Add "Platform Walkthrough" entry in Sidebar under "Getting Started" section
4. Set as default landing page for new sessions (before any data is uploaded)

**Effort:** 2 hours  
**Expected ROI:** First impression improvement for all demos. The enterprise framing should be the first thing a prospect sees.

---

### #17 — Add HMAC-SHA256 with Salt for Employee ID Masking

**Audit Ref:** A-08  
**Severity:** HIGH  
**Business Impact:** Closes PDPL technical risk. Required for NCSA ECC compliance review.

**Technical Steps:**
1. Replace `hashlib.sha256(str(emp_id).encode()).hexdigest()[:6]` with HMAC-SHA256
2. Key: per-tenant secret derived from `HMAC(tenant_id, deployment_secret)`
3. Output: 12 hex characters minimum (48 bits)
4. Add salt: `HMAC(key, f"{session_id}:{emp_id}")`
5. IDs are now session-scoped — cross-session correlation impossible

**Effort:** 2 hours  
**Expected Risk Elimination:** PDPL Article 18 technical safeguard compliance

---

### #18 — Implement CI/CD Pipeline (GitHub Actions)

**Audit Ref:** D-03  
**Severity:** HIGH  
**Business Impact:** Prevents broken deployments at client sites. Required for ISO 27001 and SOC2 certification. Enables safe rapid iteration.

**Technical Steps:**
1. `.github/workflows/test.yml`: on every PR — `pytest`, `npm run build`, `mypy backend/`
2. `.github/workflows/deploy.yml`: on merge to main — build Docker image, push to registry
3. Branch protection: require passing CI before merge
4. Add `pip-audit` to CI for dependency vulnerability scanning

**Effort:** 2 days  
**Expected Risk Elimination:** Prevents client-facing deployment failures. Required for certification.

---

### #19 — Separate ML Validation into Async Background Task

**Audit Ref:** SC-02  
**Severity:** HIGH  
**Business Impact:** Transforms user experience from 15-second blocking spinner to instant results with async ML loading.

**Technical Steps:**
1. Return analysis result immediately after governance + scoring (3–5 seconds)
2. Submit ML validation as FastAPI `BackgroundTask`
3. Store ML result in session (keyed by `session_id`) when complete
4. Frontend: poll `GET /api/v1/sessions/{session_id}/ml-validation` for ML result
5. Show "ML Validation: Computing..." badge that updates to results when ready

**Effort:** 1 week  
**Expected ROI:** Dramatically improves demo conversion rate — prospects see results in 3 seconds vs 15 seconds.

---

### #20 — Add PDPL-Compliant Data Deletion Endpoint

**Audit Ref:** S-05 (partial), compliance gap  
**Severity:** HIGH  
**Business Impact:** PDPL Article 12 (right to erasure). Government procurement will require data deletion capability.

**Technical Steps:**
1. `DELETE /api/v1/sessions/{session_id}` (exists but only deletes from local_intelligence.db)
2. Cascade deletion to `awi_history.db`, `awi_tenants.db` audit log entries
3. Add tenant-level deletion: `DELETE /api/v1/tenants/{tenant_id}/data` — removes all snapshots and analysis history
4. Return deletion receipt with timestamp (required for PDPL compliance evidence)

**Effort:** 2 days  
**Expected ARR Unlock:** Required for government client data agreements

---

## TIER 3 — QUALITY AND ENTERPRISE POLISH

---

### #21 — Add Fairness Audit Module to Governance Panel

**Audit Ref:** M-03  
**Severity:** HIGH  
**Business Impact:** Proactive bias auditing is a competitive differentiator and regulatory requirement for government deployment.

**Technical Steps:**
1. Compute risk score distributions by department and demographic proxies (nationality_flag if present, gender_flag if present)
2. Flag systematic score differences >10 points between groups
3. Add "Fairness Audit" section to Governance Panel
4. Documentation: "AWI detects potential score disparities by group — HR judgment required before acting on any risk classification"

**Effort:** 1 week

---

### #22 — Document and Justify the 0.6 Protective Factor Multiplier

**Audit Ref:** A-05  
**Severity:** HIGH  
**Business Impact:** Scientific defensibility. Any data science reviewer will challenge unexplained multipliers.

**Technical Steps:**
1. Conduct internal calibration analysis: what multiplier value minimizes prediction error on validation set?
2. Document result in `SCORING_METHODOLOGY.md`
3. Either: validate 0.6 is correct, or update to empirically-derived value
4. Add cite in code comment with reference to methodology document

**Effort:** 3 days

---

### #23 — Implement Model Drift Detection

**Audit Ref:** M-02  
**Severity:** HIGH  
**Business Impact:** Maintains long-term prediction quality. Required for enterprise SLA.

**Technical Steps:**
1. On first analysis: save feature distribution statistics to `awi_history.db`
2. On subsequent analyses: compute Population Stability Index (PSI) vs. baseline
3. PSI > 0.2: add governance warning "Workforce composition has changed significantly — model re-validation recommended"
4. Surface warning in Governance Panel

**Effort:** 1 week

---

### #24 — Implement Request-Level Correlation IDs and Structured Logging

**Audit Ref:** D-03 (monitoring aspect)  
**Severity:** MEDIUM  
**Business Impact:** Required for enterprise support SLA. When a client reports "analysis failed at 14:32," support needs to find the log entry.

**Technical Steps:**
1. Add `X-Correlation-ID` header injection in nginx (generate UUID per request)
2. Python: pass correlation ID to all log statements in the request context
3. Change logger to JSON format: `{"timestamp": "...", "level": "INFO", "correlation_id": "...", "message": "..."}`
4. Frontend: include `X-Correlation-ID` in all API requests

**Effort:** 2 days

---

### #25 — White-Label Report Branding Configuration

**Audit Ref:** R-04  
**Severity:** MEDIUM  
**Business Impact:** Unlocks consulting channel. KPMG/Deloitte resellers require branded outputs.

**Technical Steps:**
1. Add branding configuration model: `{ company_name, logo_base64, primary_color, footer_text }`
2. Inject into all PDF report and PPTX generation functions
3. UI: add "Report Branding" settings page
4. Default: AWI branding. Consulting mode: reseller branding + "Powered by AWI" footer

**Effort:** 1 week

---

### #26 — Validate Arabic PDF Export (RTL Text Rendering)

**Audit Ref:** R-05  
**Severity:** MEDIUM  
**Business Impact:** Bilingual is a stated core differentiator. It must work in exported format.

**Technical Steps:**
1. Add Arabic font (Noto Naskh Arabic or Amiri) to WeasyPrint/PDF dependencies
2. Explicit `direction: rtl; unicode-bidi: embed` CSS for Arabic text blocks
3. Add integration test: generate PDF with Arabic content, verify Arabic characters in binary output
4. Manual QA: print a sample Arabic board report and verify on-screen

**Effort:** 3 days

---

### #27 — Add Virtual Scrolling for Employee Risk Table (>2,000 rows)

**Audit Ref:** R-03  
**Severity:** MEDIUM  
**Business Impact:** Required for enterprise clients with >2,000 employees (banks, government ministries).

**Technical Steps:**
1. Replace current employee table render with `@tanstack/react-virtual` or `react-window`
2. Implement server-side pagination: only fetch current page from API
3. Add column sorting via URL query parameters (persisted on page navigation)
4. Load indicator for page changes

**Effort:** 1 week

---

### #28 — Create Legal DPA Template

**Audit Ref:** C-02  
**Severity:** HIGH  
**Business Impact:** No enterprise client in Saudi Arabia will sign a contract without a Data Processing Agreement.

**Technical Steps:**
1. Engage Saudi data protection lawyer for PDPL-compliant DPA template (1–2 weeks legal work)
2. Create `/legal/DPA_TEMPLATE.docx` in repository
3. Create sub-processor list (empty for on-premises; populated for SaaS)
4. Add SDAIA reference architecture alignment statement

**Effort:** 2 weeks (legal, not engineering)

---

### #29 — Build SAP SuccessFactors Connector (Data Ingestion)

**Audit Ref:** A-07  
**Severity:** HIGH  
**Business Impact:** Most Saudi enterprises use SAP SuccessFactors. Removes #1 operational adoption barrier.

**Technical Steps:**
1. Research SAP SuccessFactors OData API v2 (Employee Central module)
2. Build `backend/core/connectors/sap_successfactors.py` with OAuth 2.0 authentication
3. Map SF Employee Central fields to AWI column schema
4. Add scheduled sync: pull delta changes nightly
5. UI: add "Connect SAP SuccessFactors" button in Data Intake page

**Effort:** 4 weeks

---

### #30 — Add PostgreSQL Support for Multi-Tenant SaaS

**Audit Ref:** SC-01  
**Severity:** HIGH  
**Business Impact:** Required for Phase 32 SaaS architecture and any multi-server deployment.

**Technical Steps:**
1. Create database abstraction layer with SQLite and PostgreSQL adapters
2. Uncomment PostgreSQL service in `docker-compose.yml`
3. Migrate schema to PostgreSQL-compatible syntax (no SQLite-specific pragmas)
4. Add `DATABASE_URL` environment variable; auto-detect SQLite vs PostgreSQL
5. Update Alembic to work with both backends

**Effort:** 2 weeks

---

### #31 — Implement Pilot Agreement and Proof-of-Value Framework

**Audit Ref:** C-04  
**Severity:** MEDIUM  
**Business Impact:** Accelerates pilot-to-contract conversion.

**Technical Steps:**
1. Write 3-page Pilot Agreement template (legal review required)
2. Define 5 standard success criteria (see FINAL_EXECUTIVE_PRODUCT_AUDIT.md)
3. Create Pilot Playbook document: week-by-week HR analyst onboarding guide
4. Add "Pilot Mode" configuration in TenantManager (limited analyses, 90-day TTL)

**Effort:** 1 week (plus legal review)

---

### #32 — Add "Data as of" Timestamp Banner on All Dashboard Pages

**Audit Ref:** R-02  
**Severity:** MEDIUM  
**Business Impact:** Prevents presenting stale data in board presentations.

**Technical Steps:**
1. Extract `analysis_timestamp` from stored analysis result
2. Display "Workforce Analysis as of [Date/Time]" banner on ExecutiveDashboard, CEODashboard, EmployeeRiskDashboard
3. If analysis >24 hours old: highlight banner in amber with "Consider re-analyzing"
4. Add `analysis_age_hours` to API response

**Effort:** 1 day

---

### #33 — Consolidate Five SQLite Files into Two

**Audit Ref:** A-06 (partial)  
**Severity:** MEDIUM  
**Business Impact:** Simplifies backup, reduces migration complexity, fewer file handle issues.

**Technical Steps:**
1. `awi_operational.db`: tenants, sessions, auth, audit log, analysis results, history
2. `awi_benchmarks.db`: benchmark data, contributions (separate because air-gapped clients may not want benchmark sharing)
3. Migrate all existing data
4. Update all module `_DB_PATH` variables
5. Single Alembic migration runner for operational DB

**Effort:** 1 week

---

### #34 — Implement SAML 2.0 SSO (for ADFS/on-premises AD customers)

**Audit Ref:** E-01 (extension)  
**Severity:** HIGH  
**Business Impact:** Some Saudi government clients and older banks use ADFS (on-premises Active Directory) rather than Azure AD cloud. SAML 2.0 is the protocol they require.

**Technical Steps:**
1. Add `python3-saml` to requirements
2. Implement SAML SP-initiated login flow
3. Map SAML attributes to AWI user profile and role
4. Test with ADFS and Okta (for non-MSFT customers)

**Effort:** 2 weeks

---

### #35 — Add iPad / Tablet Responsive Layout for CEO Dashboard and Board Reports

**Audit Ref:** E-02  
**Severity:** MEDIUM  
**Business Impact:** CHROs who approve purchase decisions predominantly view on iPad.

**Technical Steps:**
1. Audit CEO Dashboard and Executive Reports at 768px and 1024px viewports
2. Convert dense multi-column layouts to single-column stacked layout on tablet
3. Increase tap target sizes to minimum 44×44px
4. Test font rendering at tablet DPI
5. Add PWA manifest for "Add to Home Screen"

**Effort:** 1 week

---

### #36 — Pin All Dependencies to Exact Versions (requirements.txt lockfile)

**Audit Ref:** Supply chain  
**Severity:** MEDIUM  
**Business Impact:** Prevents silent breakage from upstream version changes. Required for reproducible builds.

**Technical Steps:**
1. Run `pip freeze > requirements-lock.txt` from known-good environment
2. Use `requirements-lock.txt` in Dockerfile for production builds
3. Keep `requirements.txt` as human-readable specification with minimum versions
4. Add `pip-audit` to CI for vulnerability scanning of pinned dependencies

**Effort:** 1 day

---

### #37 — Add Real-Time Analysis Progress via WebSocket or SSE

**Audit Ref:** SC-02 (UX aspect)  
**Severity:** MEDIUM  
**Business Impact:** Users currently stare at a spinner with no feedback during 10–15 second analysis. Progress indication transforms the experience.

**Technical Steps:**
1. Add `GET /api/v1/analysis/stream/{job_id}` Server-Sent Events endpoint
2. Backend: emit progress events at each pipeline stage (Governance Scan → Scoring → ML → Storytelling)
3. Frontend: subscribe to SSE stream; update progress bar with stage names
4. Fallback to polling if SSE not supported

**Effort:** 1 week

---

### #38 — Implement Data Retention Policies and Auto-Cleanup

**Audit Ref:** Compliance gap  
**Severity:** MEDIUM  
**Business Impact:** PDPL Article 12 (data minimization). Prevents indefinite accumulation of employee risk data.

**Technical Steps:**
1. Add `retention_days` field to TenantProfile (default: 365 days)
2. Background job: daily cleanup of sessions and analysis results older than `retention_days`
3. UI: show data retention policy in Governance Panel
4. Add client notification before data deletion (30-day warning email if email configured)

**Effort:** 3 days

---

### #39 — File a Provisional Patent on the Conservative ML Validation Methodology

**Audit Ref:** I-03  
**Severity:** MEDIUM (Investor concern)  
**Business Impact:** Strengthens investor due diligence, creates defensible IP moat.

**Action:** Engage Saudi IP law firm for provisional patent application on:
1. Proxy-free cross-validation methodology for HR attrition prediction
2. 6-theory construct scoring system with PDPL-compliant aggregation
3. Conservative vs. Full feature comparison framework

**Effort:** 4 weeks (legal, not engineering)  
**Expected Cost:** SAR 15–30K  
**Expected ROI:** IP certification strengthens Series A valuation by estimated 20–30%

---

### #40 — Add Workforce Comparison Across Subsidiaries (Multi-Entity Analysis)

**Audit Ref:** Enterprise feature gap  
**Severity:** MEDIUM  
**Business Impact:** Saudi conglomerates (SABIC, STC, Almarai) have 5–20 subsidiaries. A consolidated view across all entities is a premium capability no competitor offers in the Saudi market.

**Technical Steps:**
1. Add "Multi-Entity Analysis" mode: upload multiple datasets (one per subsidiary)
2. Compute consolidated risk index across entities
3. Show entity-vs-entity comparison in Executive Dashboard
4. Generate consolidated board report covering all subsidiaries

**Effort:** 2 weeks  
**Expected ARR Unlock:** +SAR 120K/year per client (Multi-subsidiary Admin Panel upsell)

---

### #41 — Document the Scoring Methodology and Construct Validity in a Technical Annex

**Audit Ref:** M-01, A-05  
**Severity:** MEDIUM  
**Business Impact:** Enterprise clients' in-house HR analytics teams will challenge the methodology. Having a published Technical Annex prevents "black box" objections and supports regulatory review.

**Action:**
1. Create `TECHNICAL_METHODOLOGY.md` documenting: construct definitions, weight derivation, calibration study, proxy detection logic, validation approach
2. For each of 18+ constructs: cite academic source, explain Saudi labor market adaptation
3. Publish as a downloadable PDF from the AWI platform

**Effort:** 1 week  
**Expected ROI:** Overcomes "show me the methodology" sales objection, which blocks 30–40% of enterprise deals

---

### #42 — Add Benchmark Comparison to Executive Reports (PDF/PPTX Export)

**Audit Ref:** Feature gap  
**Severity:** MEDIUM  
**Business Impact:** The BenchmarkEngine produces comparison results but they are not included in the PDF board report or PPTX slide deck. This is a missed opportunity — the benchmark comparison is a high-value output for board presentations.

**Technical Steps:**
1. Add "Sector Benchmarking" slide to PPTX export (Slide 5 in the 11-slide deck)
2. Include benchmark comparison table in PDF board report Section 3
3. Add `benchmark_result` to the slide exporter input schema

**Effort:** 3 days

---

### #43 — Implement Oracle HCM Cloud Connector

**Audit Ref:** A-07  
**Severity:** MEDIUM  
**Business Impact:** Saudi healthcare groups and some government entities use Oracle HCM. A second connector expands the integration footprint.

**Technical Steps:**
1. Oracle HCM Cloud REST API authentication (OAuth 2.0)
2. Map Oracle HCM Person and Employment objects to AWI schema
3. Bundle with SAP connector in "Integration Hub" module

**Effort:** 3 weeks

---

### #44 — Add "Board Mode" — Large-Font High-Contrast Presentation Layout

**Audit Ref:** E-02 (extension)  
**Severity:** LOW  
**Business Impact:** CHROs presenting to board members on large screens need a decluttered, high-contrast layout. Currently the UI is optimized for analyst use (dense information).

**Technical Steps:**
1. Add "Board Mode" toggle in TopBar
2. Switch to 24px+ font, high-contrast color scheme, hide secondary metrics
3. CEO Dashboard becomes full-screen with simplified KPI cards
4. Keyboard shortcut: `B` key toggles Board Mode during presentation

**Effort:** 3 days

---

### #45 — Implement Conduct 10 Customer Discovery Interviews Before Raising Capital

**Audit Ref:** I-02  
**Severity:** MEDIUM (Investor concern)  
**Business Impact:** Investor-facing validation. Reduces Series A close risk by 40%.

**Action:**
1. Schedule 10× 45-minute calls with CHROs at target companies
2. Script: current HR analytics tools, pain points, willingness to pay, procurement process
3. Document findings in `CUSTOMER_DISCOVERY_REPORT.md`
4. Use findings to validate or revise pricing tiers

**Effort:** 4 weeks (business development, not engineering)

---

### #46 — Add Stale Data Notification and Re-Analysis Prompt

**Audit Ref:** R-02  
**Severity:** LOW  
**Business Impact:** Prevents presenting outdated analysis in board meetings.

**Technical Steps:**
1. `localStorage` stores analysis timestamp alongside results
2. On page load: if analysis >24 hours old, show banner: "Analysis is X hours old. Re-analyze for current results."
3. Add "Run New Analysis" CTA button in banner
4. On CEO Dashboard: show "Last analyzed: [date/time]" in subtitle

**Effort:** 2 hours

---

### #47 — Add Workday REST API Connector

**Audit Ref:** A-07 (extension)  
**Severity:** MEDIUM  
**Business Impact:** Workday is growing in the Saudi market, especially at international companies with local operations (ARAMCO subsidiaries, STC).

**Technical Steps:**
1. Workday Reports-as-a-Service (RaaS) API for Employee data export
2. Authenticate via Workday ISU (Integration System User) credential
3. Map Workday Worker and Employment Position objects to AWI schema
4. Schedule nightly sync

**Effort:** 3 weeks

---

### #48 — Add Support for Arabic-Language Data Input (Column Headers in Arabic)

**Audit Ref:** Feature gap  
**Severity:** MEDIUM  
**Business Impact:** Government clients with Arabic HR systems upload files with Arabic column names. The current normalization map handles a few Arabic cases but is incomplete.

**Technical Steps:**
1. Expand `_SAUDI_HR_COLUMN_RENAMES` with comprehensive Arabic→English column mappings
2. Add Arabic column detection to `SemanticColumnMapper`
3. Test with sample Arabic-column dataset
4. Governance scan should recognize Arabic column names without blocking

**Effort:** 1 week

---

### #49 — Generate and Publish a Software Bill of Materials (SBOM)

**Audit Ref:** Supply chain  
**Severity:** LOW  
**Business Impact:** Enterprise security teams increasingly require SBOM as part of vendor security questionnaires. NCSA ECC Tier 1 requirement for government technology vendors.

**Technical Steps:**
1. Add `cyclonedx-bom` to CI pipeline
2. Generate `sbom.json` on every release
3. Publish as a release artifact in GitHub Releases
4. Document SBOM availability in security response policy

**Effort:** 1 day

---

### #50 — Revise Internal Valuation Methodology Before Investor Conversations

**Audit Ref:** C-01, I-02  
**Severity:** HIGH (Investor concern)  
**Business Impact:** SAR 75M self-assessed valuation will damage credibility with informed investors. Revising to milestone-based valuation thesis is the professional approach.

**Action:**
1. Remove explicit valuation claim from AWI_PRODUCT_MATURITY_REPORT.md
2. Replace with: "Investment Thesis: First 5 paying clients at average SAR 480K = SAR 2.4M ARR. Series A at 8–10× ARR = SAR 19–24M valuation at this milestone"
3. Add "Comparable Transactions" section citing MENA HR tech exits at verifiable multiples
4. Engage a MENA-focused tech investment bank for pre-raise valuation advisory

**Effort:** 1 week (business strategy, not engineering)

---

## RANKED SUMMARY TABLE

| Rank | Improvement | Category | Effort | Business Value |
|------|-------------|----------|--------|----------------|
| 1 | JWT Authentication Middleware | Architecture | 1 week | 🔴 All deals blocked |
| 2 | Replace In-Memory Sessions | Architecture | 1 week | 🔴 Multi-user blocked |
| 3 | Enforce HTTPS/TLS | Security | 3 days | 🔴 Enterprise deployment blocked |
| 4 | Remove localStorage Employee Data | Security | 3 days | 🔴 PDPL breach risk |
| 5 | Azure AD SSO | Auth | 2 weeks | 🔴 Banking segment blocked |
| 6 | Deterministic Risk Scores | ML | 1 day | 🔴 Audit trail blocked |
| 7 | RBAC Enforcement Middleware | Auth | 1 week | 🔴 Security questionnaire |
| 8 | nginx Rate Limiting | Security | 2 days | DoS vulnerability |
| 9 | Alembic Database Migrations | Architecture | 1 week | Schema drift / data loss |
| 10 | OpenAPI Documentation | Product | 3 days | Consulting channel unlock |
| 11 | Multi-Stage Docker Build | DevOps | 1 day | Security scan approval |
| 12 | Audit Log API Endpoint | Compliance | 2 days | 🔴 Gov/banking procurement |
| 13 | API Versioning (/v1/) | Architecture | 2 days | Integration stability |
| 14 | Error Message Sanitization | Security | 1 day | Information disclosure |
| 15 | Analysis Result Caching | Performance | 2 days | Demo experience |
| 16 | Wire PlatformWalkthrough to Router | Frontend | 2 hours | Demo quality |
| 17 | HMAC-SHA256 Employee ID Masking | Security | 2 hours | PDPL compliance |
| 18 | CI/CD Pipeline (GitHub Actions) | DevOps | 2 days | Deployment safety |
| 19 | Async ML Validation Background | Performance | 1 week | UX: 15s→3s |
| 20 | PDPL Data Deletion Endpoint | Compliance | 2 days | 🔴 Gov data agreements |
| 21 | Fairness Audit Module | ML/AI | 1 week | Regulatory + differentiator |
| 22 | Justify 0.6 Protective Multiplier | ML/AI | 3 days | Scientific credibility |
| 23 | Model Drift Detection | ML/AI | 1 week | Long-term quality |
| 24 | Structured Logging + Correlation IDs | Operations | 2 days | Support SLA |
| 25 | White-Label Report Branding | Product | 1 week | Consulting channel |
| 26 | Validate Arabic PDF RTL Export | Product | 3 days | Core differentiator |
| 27 | Virtual Scrolling for Risk Table | Frontend | 1 week | Large org usability |
| 28 | Legal DPA Template | Legal | 2 weeks | 🔴 Contract prerequisite |
| 29 | SAP SuccessFactors Connector | Integration | 4 weeks | #1 adoption barrier |
| 30 | PostgreSQL Support | Architecture | 2 weeks | SaaS architecture |
| 31 | Pilot Agreement Framework | Business | 1 week | Deal velocity |
| 32 | "Data as of" Timestamp Banner | Frontend | 1 day | Board presentation safety |
| 33 | Consolidate 5 SQLite → 2 | Architecture | 1 week | Backup/maintenance |
| 34 | SAML 2.0 SSO (ADFS) | Auth | 2 weeks | Government SSO |
| 35 | iPad / Tablet Responsive Layout | Frontend | 1 week | CHRO experience |
| 36 | Pin Dependencies (lockfile) | DevOps | 1 day | Build reproducibility |
| 37 | Analysis Progress via SSE | Frontend | 1 week | UX improvement |
| 38 | Data Retention Auto-Cleanup | Compliance | 3 days | PDPL minimization |
| 39 | Provisional Patent Application | Legal/IP | 4 weeks | Investor credibility |
| 40 | Multi-Entity Analysis (Subsidiaries) | Product | 2 weeks | Conglomerate segment |
| 41 | Scoring Methodology Technical Annex | Documentation | 1 week | Sales objection removal |
| 42 | Benchmark in PDF/PPTX Export | Product | 3 days | Report value increase |
| 43 | Oracle HCM Connector | Integration | 3 weeks | Healthcare segment |
| 44 | Board Mode Presentation Layout | Frontend | 3 days | CHRO demo experience |
| 45 | Customer Discovery (10 interviews) | Business | 4 weeks | Investor validation |
| 46 | Stale Data Notification | Frontend | 2 hours | Board safety |
| 47 | Workday Connector | Integration | 3 weeks | International company segment |
| 48 | Arabic Column Header Support | Data | 1 week | Government usability |
| 49 | Software Bill of Materials (SBOM) | Security | 1 day | Enterprise security questionnaire |
| 50 | Revise Valuation Methodology | Business | 1 week | Investor credibility |

---

## IMPLEMENTATION ROADMAP

### Sprint 1 (Weeks 1–2): Security Foundation
Items #1, #3, #4, #6, #11, #16, #17 — Minimum viable security for demo to enterprise client

### Sprint 2 (Weeks 3–4): Auth and Access Control
Items #2, #7, #13, #14 — Session management, RBAC, API versioning

### Sprint 3 (Weeks 5–6): Enterprise Procurement Requirements
Items #5, #8, #12, #18, #28 — SSO, rate limiting, audit API, CI/CD, DPA legal

### Sprint 4 (Weeks 7–8): Performance and UX
Items #9, #15, #19, #20, #32, #36 — Migrations, caching, async ML, data retention

### Sprint 5 (Weeks 9–12): Product Excellence
Items #21, #22, #23, #24, #25, #26, #27, #29 — Fairness, methodology, drift, connectors

### Sprint 6 (Weeks 13–16): Commercial Readiness
Items #30, #31, #33, #34, #35, #37, #39, #41, #50 — PostgreSQL, pilot framework, patent, valuation

---

*TOP_50_IMPROVEMENTS.md | AWI Product Improvement Backlog | 2026-06-01*  
*Ranked by business value: revenue unlock + risk elimination + deal velocity*  
*Classification: Internal — Confidential*
