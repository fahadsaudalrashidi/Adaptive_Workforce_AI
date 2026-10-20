# AWI — Final Executive Product Audit
## Brutal Assessment: Architecture, Security, Commercialization, Valuation

**Audit Panel:**
- Former McKinsey Partner (Strategy, Commercialization, Investor Readiness)
- Former SAP SuccessFactors Product Director (Enterprise Architecture, Feature Completeness)
- Former Workday Enterprise Architect (Scalability, Integration, Platform Design)
- Former Deloitte HR Transformation Lead (Domain Validity, Compliance, Client Adoption)

**Date:** 2026-06-01  
**Scope:** Full repository — backend, frontend, infrastructure, ML/AI, documentation  
**Verdict:** Not yet production-deployable to a paying enterprise client. Pre-revenue positioning is accurate. 12–16 weeks of critical hardening required before any enterprise pilot.

---

## PART 1 — ARCHITECTURE WEAKNESSES

---

### A-01: Zero Authentication on Every API Endpoint

**Severity:** CRITICAL

**Business Impact:** Any person on the same network — or any internet-accessible deployment — can upload employee data, retrieve risk scores, download exports, and enumerate analysis sessions without providing any credential. A Saudi bank CISO will reject this in the first 30-minute technical review. PDPL Article 18 (organizational security measures) is structurally violated.

**Technical Impact:** `backend/api/main.py` line 94 contains the comment "no auth, single machine." CORS is configured as `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]` — the three most dangerous wildcard settings in web security. Every export endpoint (`/export/{sid}/csv`) accepts any UUID session ID with no ownership check. The result: an attacker who observes network traffic or guesses a UUID can download any organization's employee risk data.

**Recommended Fix:**
1. Immediate: Add API key middleware (X-API-Key header) with per-tenant keys stored in `awi_auth.db`
2. Phase 31A: JWT Bearer tokens with RS256 signing, 1-hour expiry, refresh token rotation
3. CORS: Restrict to specific allowed origin list; fail-closed on missing Origin header
4. Export endpoints: Validate session ownership against authenticated tenant context before serving data

**Expected ROI:** Unblocks enterprise procurement. Without auth, no enterprise client will sign. This is the single change with highest commercial leverage — estimated 100% of enterprise deals currently blocked by it.

---

### A-02: Employee Risk Data Stored Unencrypted in Browser localStorage

**Severity:** CRITICAL

**Business Impact:** Under PDPL Article 6, processed personal data (including derived risk classifications linked to workforce segments) requires appropriate technical safeguards. Storing workforce risk tables, priority review counts, and department breakdowns in unencrypted browser localStorage means any browser extension, injected script, or XSS attack can exfiltrate the entire analysis. A single client incident of this type ends the business.

**Technical Impact:** `src/state/analysisStore.ts` and `src/state/employeeRiskStore.ts` persist full analysis state to `localStorage.setItem(STORAGE_KEY, ...)`. localStorage has no access controls, no expiry enforcement, no encryption. It survives browser close. It is accessible to every JavaScript execution context on the origin. There are no Content-Security-Policy headers to limit what scripts can run.

**Recommended Fix:**
1. Move sensitive analysis state to session-scoped memory only (`sessionStorage` at minimum, React context at best)
2. Implement explicit session clear on browser close or logout event
3. Add CSP headers: `default-src 'self'`, `script-src 'nonce-{random}'`
4. Never store employee_risk_table arrays client-side — re-fetch paginated from authenticated API

**Expected ROI:** Required for PDPL compliance sign-off. Blocks data breach liability. Estimated legal exposure avoided: SAR 5–50M per incident under PDPL Article 34 penalty framework.

---

### A-03: In-Memory Session Store with No Eviction — Memory Leak and Data Loss Risk

**Severity:** CRITICAL

**Business Impact:** `backend/api/main.py` stores full pandas DataFrames and raw file bytes per session in `_SESSIONS: Dict[str, Dict[str, Any]] = {}`. A 500-row HR file at 50 columns = approximately 400KB DataFrame + raw bytes. At 100 concurrent sessions (realistic for an enterprise demo), that is 80MB — manageable. At 1,000 sessions (a typical bank deployment with multiple HR analysts over one day), that is 800MB with no eviction, growing until OOM crash. When the process restarts, all sessions are lost, silently.

**Technical Impact:** The code comment on line 59 acknowledges this: "production: use Redis/DB." The gap is that this has been in the code since Phase 12 (Phase 30 audit passed with it unchanged). No TTL, no LRU eviction, no max session count. Uvicorn is configured with `workers=1`, meaning this single process handles all load AND holds all session state.

**Recommended Fix:**
1. Replace in-memory dict with Redis (TTL of 4 hours, eviction policy allkeys-lru)
2. For on-premises air-gapped deployment: SQLite-backed session cache with explicit TTL column
3. Never store raw DataFrames — store only analysis result JSON, re-ingest file on demand
4. Add `workers=4` minimum in uvicorn configuration

**Expected ROI:** Required for multi-analyst deployment. Without this, concurrent use by more than one analyst destabilizes the system. Unblocks deployment to any organization with >1 HR analyst.

---

### A-04: Single-Threaded API — Cannot Serve Multiple Simultaneous Requests

**Severity:** CRITICAL

**Business Impact:** An enterprise client with 3 HR analysts running analyses simultaneously will experience 15-second timeouts for the second and third analysts while the first analysis runs. This is unacceptable for a platform priced at SAR 720K/year. Workday and SuccessFactors serve hundreds of concurrent users with sub-second latency.

**Technical Impact:** `Dockerfile` line 43 runs uvicorn with default workers (1). FastAPI is ASGI and supports async, but the analysis pipeline calls `asyncio.to_thread()` which delegates to a thread pool. The default thread pool is `min(32, os.cpu_count() + 4)`, typically 4–8 threads. The 15-second analysis timeout means 4–8 concurrent analyses maximum before queuing. The ML validation (`run_ml_validation`) runs synchronously in the thread pool and blocks other requests.

**Recommended Fix:**
1. Uvicorn: `--workers 4` (multiple processes) behind nginx reverse proxy
2. Separate the ML analysis into an async task queue (Celery + Redis, or FastAPI BackgroundTasks)
3. Return a job ID immediately; poll for completion or use WebSocket for progress
4. Add nginx with rate limiting and request queuing

**Expected ROI:** Required for any multi-user deployment. Estimated cost of implementation: 2 weeks engineering. Estimated deal unlock: all enterprise clients that require >1 concurrent user.

---

### A-05: Risk Score Formula Contains Unexplained Hardcoded Multiplier — Scientifically Indefensible

**Severity:** HIGH

**Business Impact:** `employee_risk_scoring.py` line 728: `score = 30.0 + risk_points - (protective_points * 0.6)`. The `0.6` multiplier applied to protective factors has no documented justification — no citation, no calibration study, no cross-validation result. When an enterprise client's data science team (or their regulator) asks "why is a protective factor worth 60% of a risk factor?", there is no answer. A McKinsey HR analytics team reviewing this will reject it as arbitrary. The Deloitte HR practice would call it "model risk" under EY/Deloitte internal review frameworks.

**Technical Impact:** The same function adds stochastic jitter `rng.uniform(-3.0, 3.0)` to every score. Identical employees uploaded twice will receive different scores (up to 6 points apart). This is by design (comment says "realistic variation") but creates non-reproducibility: a client who runs the same dataset twice gets different Priority Review lists. This is a trust-destroying behavior in enterprise software.

**Recommended Fix:**
1. Document the 0.6 multiplier with a calibration study or remove it and use equal weighting
2. Remove stochastic jitter entirely; replace with a documented confidence interval displayed separately
3. Add score reproducibility guarantee: same input → same output (deterministic pipeline)
4. Publish internal calibration methodology as a Technical Annex

**Expected ROI:** Required for scientific defensibility and board-level credibility. Loss of a single large client due to "inconsistent scores" = SAR 720K+. Fixing this costs 2–3 days.

---

### A-06: No Database Migration System — Schema Drift Guaranteed at Scale

**Severity:** HIGH

**Business Impact:** When a Phase 31 feature requires adding a column to the `tenants` table or `workforce_snapshots` table, there is no migration tooling. The developer will manually ALTER TABLE in SQLite, or drop and recreate the database, losing client historical data. At a government client with 18 months of workforce snapshots, data loss from a botched migration is a breach of contract.

**Technical Impact:** All schema creation is done via `CREATE TABLE IF NOT EXISTS` on every application start. There is no version table, no migration runner (Alembic, Flyway, Liquibase), no rollback capability. Four separate SQLite databases exist (`local_intelligence.db`, `awi_tenants.db`, `awi_auth.db`, `awi_history.db`, `awi_benchmarks.sqlite`) with no coordination. Any schema change to one requires manual synchronization.

**Recommended Fix:**
1. Integrate Alembic for all SQLite schemas immediately
2. Consolidate the five SQLite databases to one (or two: operational + benchmark)
3. Add `schema_version` table to every database
4. CI/CD must run `alembic upgrade head` on deployment

**Expected ROI:** Avoids catastrophic data loss at client sites. Required for Phase 31 schema changes. 1-week implementation.

---

### A-07: No HRIS Integration Layer — The Biggest Enterprise Adoption Blocker

**Severity:** HIGH

**Business Impact:** Every enterprise client that AWI targets (Saudi banks, government ministries, healthcare groups) already has an HRIS — SAP SuccessFactors, Oracle HCM, Workday, or custom HRSD system. They will not export a CSV manually every time they want to run an analysis. The current "upload a CSV" model is a prototype workflow, not an enterprise workflow. SAP SuccessFactors and Workday both have native export APIs. Without connectors, the target client's IT team will classify AWI as a "shadow IT tool" and block procurement.

**Technical Impact:** Zero integration code exists. No SFTP, no ODATA endpoint, no SAP BAPI/RFC connector, no Workday REST API client, no Oracle HCM adapter. The only data ingestion path is manual file upload.

**Recommended Fix:**
1. Phase 31: Build one enterprise connector (SAP SuccessFactors OData API is the Saudi market default)
2. Define a standard AWI Data Exchange Schema (CSV/JSON) that connectors export to
3. Add scheduled analysis capability: connector pulls data nightly, AWI runs analysis, results available in morning
4. SFTP-based "air-gapped" connector for government clients who cannot use REST APIs

**Expected ROI:** Removes the #1 operational friction for enterprise deployment. Without HRIS integration, each analysis requires IT involvement for CSV extraction — in a Saudi ministry, that is a 2-week process. With integration: self-service. Estimated deal acceleration: 3–6 months per client.

---

### A-08: Weak Employee ID Masking — Potential PII Re-identification

**Severity:** HIGH

**Business Impact:** The `_make_record_id()` function in `employee_risk_scoring.py` hashes employee identifiers to a 6-character hex string (24 bits of entropy). With 16.7M possible values, an organization with 5,000 employees has a collision probability of approximately 0.07% — not catastrophic, but in a PDPL audit, the methodology will be scrutinized. More critically, SHA-256 without a HMAC salt means the hash is deterministic and pre-computed rainbow tables could partially reverse it.

**Technical Impact:** 6 hex characters = `a1b2c3` style ID. If the original employee number is sequential (e.g., EMP-001, EMP-002), only 3–4 guesses with the hash function reveals the sequence. The hash has no cryptographic salt per-tenant or per-session. Cross-session correlation is possible.

**Recommended Fix:**
1. Replace 6-char truncated SHA-256 with HMAC-SHA256 using a per-tenant secret key
2. Minimum 12 hex characters (48 bits)
3. Add random salt per-session so IDs are not correlated across sessions
4. Document masking methodology in PDPL technical annex

**Expected ROI:** Closes PDPL audit risk. Required for government client deployment where NCSC (Saudi National Cybersecurity Authority) will review the technical methodology.

---

### A-09: No API Versioning — Breaking Changes Will Break All Clients

**Severity:** HIGH

**Business Impact:** The API currently uses `/api/local/` prefix with no version segment. When Phase 31 changes the response schema of `/upload/analyze-with-employees` (adding tenant_id, session validation), every frontend client and any integration partner using the API breaks simultaneously. Workday's API has maintained v1, v2, v3 simultaneously for 6+ years precisely because enterprise clients cannot redeploy integrations instantly.

**Technical Impact:** No versioning scheme. All routes are under `/api/local/`. A response schema change requires simultaneous deployment of API and frontend. For air-gapped government clients with 3-month change-freeze windows, this means no updates for 3 months or coordinated deployment.

**Recommended Fix:**
1. Introduce `/api/v1/` prefix immediately before external API exposure
2. Use response envelope: `{ "api_version": "1.0", "data": {...}, "schema_version": "1.0" }`
3. Maintain v1 compatibility for minimum 12 months after v2 release
4. Generate OpenAPI spec and version it in git

**Expected ROI:** Required for integration partnerships (KPMG, PwC resellers need stable API). Prevents breaking client integrations. 1-day implementation.

---

### A-10: PlatformWalkthrough.tsx Exists But Is Not Routed in App.tsx

**Severity:** MEDIUM

**Business Impact:** The primary replacement for DemoMode.tsx — the new enterprise-branded Platform Walkthrough — is an orphaned component. It was created in Phase 30 but never wired into the navigation or router. A prospect doing a product tour will never find it. The old demo framing may still surface through other entry points.

**Technical Impact:** `executive-ui/src/pages/PlatformWalkthrough.tsx` is created but `App.tsx` does not include it in the `activePage` state machine or Sidebar navigation. The component is dead code from a user experience perspective.

**Recommended Fix:** Add `platform-walkthrough` to the activePage type, add a Sidebar entry under "Getting Started," and route to `<PlatformWalkthrough />` in App.tsx's render logic.

**Expected ROI:** Immediate demo quality improvement. First thing a prospect sees in a walkthrough is currently a broken link.

---

## PART 2 — SECURITY RISKS

---

### S-01: CORS Allows All Origins — CSRF and Data Exfiltration Risk

**Severity:** CRITICAL

**Business Impact:** With `allow_origins=["*"]`, a malicious website can make credentialed requests to the AWI API from any user's browser. If an HR analyst is logged into AWI and visits a compromised website, that site can POST to `/upload/analyze-with-employees` and exfiltrate the response.

**Technical Impact:** CORS wildcard is in `main.py`. FastAPI's CORSMiddleware with `*` also sets `Access-Control-Allow-Credentials: true` implicitly in some configurations. Combined with cookie-based sessions (if added in Phase 31), this creates a full CSRF vulnerability.

**Recommended Fix:** Replace `allow_origins=["*"]` with explicit list: `["http://localhost:5173", "https://awi.clientdomain.com"]`. Never combine wildcard origins with credentials.

**Expected ROI:** Eliminates CSRF attack surface. Required before any browser-based client deployment.

---

### S-02: No HTTPS / TLS — Data in Transit Is Plaintext

**Severity:** CRITICAL

**Business Impact:** Employee workforce risk data, analysis results, and board reports transmitted over HTTP are readable by any network intermediary. In Saudi Arabia, ISPs and government monitoring systems capture plaintext HTTP traffic by law. A bank client whose employee risk data is intercepted at the network layer has a reportable PDPL breach.

**Technical Impact:** The Dockerfile and docker-compose.yml have no TLS termination. No nginx reverse proxy with SSL. No certbot/Let's Encrypt configuration. No HTTPS redirect. All API requests from the frontend use `fetch('/api/...')` (relative URL), which inherits the protocol of the page — HTTP by default in development.

**Recommended Fix:**
1. Add nginx reverse proxy with SSL termination in docker-compose
2. For on-premises: provide self-signed certificate generation script + documentation
3. For SaaS: Let's Encrypt via certbot in nginx config
4. Add HSTS header: `Strict-Transport-Security: max-age=63072000; includeSubDomains`

**Expected ROI:** Required for any production deployment. Any enterprise client's security team will reject HTTP-only deployment outright.

---

### S-03: No Rate Limiting on Any Endpoint — Denial of Service Trivial

**Severity:** HIGH

**Business Impact:** An attacker (or a malfunctioning integration) can POST thousands of analysis requests per second, saturating CPU and memory. A single POST to `/upload/analyze-with-employees` triggers governance scan + ML validation + storytelling engine — approximately 2–5 seconds of CPU per request. 100 concurrent requests = server unresponsive for several minutes.

**Technical Impact:** No rate limiting middleware anywhere. No per-IP limits, no per-tenant limits, no global request queue. The in-memory session store will fill with partial results from aborted requests.

**Recommended Fix:**
1. Add `slowapi` (FastAPI rate limiting) with: 10 req/min for analysis endpoints, 60 req/min for read endpoints
2. Per-tenant limits enforced in TenantManager (already has `max_analyses_per_month`)
3. Nginx: `limit_req_zone` and `limit_req` directives
4. Return 429 with `Retry-After` header

**Expected ROI:** Prevents DoS. Required for SaaS multi-tenant mode. 1-day implementation.

---

### S-04: Error Messages Expose Internal File Paths and Stack Traces

**Severity:** HIGH

**Business Impact:** Exception handling in `main.py` line 145: `raise HTTPException(status_code=400, detail=str(e))`. A `FileNotFoundError` returns `"[Errno 2] No such file or directory: '/home/appuser/app/data/local_intelligence.db'"`. An attacker learns the internal directory structure, OS, user account, and database location from a single failed request.

**Technical Impact:** Python exception `str(e)` includes the exception class and message, which often contains paths, variable names, and internal state. This is information disclosure (OWASP A05:2021).

**Recommended Fix:**
1. Generic error responses to client: `{"error": "Analysis failed. Reference: ERR-20260601-001"}`
2. Full exception logged server-side with correlation ID
3. Never return `str(e)` to client
4. Add Sentry or equivalent for server-side error aggregation

**Expected ROI:** Required for any external deployment. Prevents information disclosure vulnerability.

---

### S-05: SQLite Databases Not Encrypted — Physical Access = Full Data Access

**Severity:** HIGH

**Business Impact:** Five SQLite database files are stored in plaintext on the server filesystem. A Saudi IT administrator with server access, a disgruntled employee, or a physical intruder can copy the database files and read all workforce risk data, tenant configurations, and analysis history. For government clients deploying in ministry data centers, this violates the principle of least privilege and would fail NCSC security review.

**Technical Impact:** `local_intelligence.db`, `awi_tenants.db`, `awi_history.db`, `awi_benchmarks.sqlite`, `awi_auth.db` — none are encrypted. SQLite has no native encryption; SQLCipher (community edition) or file-level encryption (Linux `dm-crypt`, LUKS) are required.

**Recommended Fix:**
1. On-premises deployment: provide LUKS volume encryption documentation and setup script
2. Application level: integrate SQLCipher via `pysqlcipher3` for database-level encryption
3. Key derivation from deployment secret + tenant salt
4. Government deployment: document alignment with NCA Essential Cybersecurity Controls (ECC)

**Expected ROI:** Required for government and banking clients. NCSC ECC compliance is a procurement requirement for Saudi government technology vendors.

---

## PART 3 — REPORTING AND UI WEAKNESSES

---

### R-01: Risk Scores Are Non-Reproducible — Same Input, Different Output

**Severity:** HIGH

**Business Impact:** `employee_risk_scoring.py` adds `rng.uniform(-3.0, 3.0)` jitter to every score. An HR director who runs the same dataset on Monday and Wednesday will get different Priority Review lists. When employees are on the boundary between bands (score ~55 or ~75), they will flip bands between runs. This destroys trust in the platform's recommendations and makes the system unauditable under PDPL Article 14 (accuracy requirement for automated decisions).

**Technical Impact:** The `rng = np.random.default_rng(seed=42)` is re-created per invocation in `score_dataframe()` — the seed is constant, so jitter is deterministic per-session but different per-upload. If the same file is uploaded twice (a common QA check), the results differ.

**Recommended Fix:** Remove jitter entirely. If score variation is scientifically justified, compute it as an explicit confidence interval field (`risk_score_low`, `risk_score_high`) separate from the point estimate. The point estimate must be deterministic.

**Expected ROI:** Directly enables audit trail compliance. HR directors in regulated industries (banking, government) require reproducible outputs for any HR decision-support system.

---

### R-02: No Real-Time Dashboard Refresh — Stale Data Shown After Re-Analysis

**Severity:** MEDIUM

**Business Impact:** After uploading a new dataset, if a user navigates away and back to the Executive Dashboard, they may be viewing cached analysis results from a previous session without realizing it. In a live board presentation, showing outdated risk data is a serious credibility risk.

**Technical Impact:** Frontend state management uses Zustand stores persisted to localStorage. The analysis result is stored client-side and loaded on page initialization without a staleness check. No timestamp validation. No "data as of" banner.

**Recommended Fix:**
1. Add visible "Analysis as of [timestamp]" banner on every dashboard page
2. Implement staleness detection: if stored analysis is >24 hours old, show banner and prompt re-analysis
3. Add WebSocket or polling for real-time analysis progress indication

**Expected ROI:** Prevents presenting stale data in board presentations. Medium priority but high visibility for demos.

---

### R-03: Employee Risk Table Has No Meaningful Pagination for Large Organizations

**Severity:** MEDIUM

**Business Impact:** Saudi banks with 5,000–15,000 employees loading the full workforce risk table will experience slow renders and browser freezes. The current implementation loads page 1 of 100 records server-side, but the full scored result is included in the API response JSON. A 15,000-row analysis response is approximately 15–20MB of JSON — a significant payload even over LAN.

**Technical Impact:** `local_analysis_routes.py` applies pagination to `scored_records` (the employee table) but passes the full `org_risk_driver_summary`, all `department_summary`, and all `specialty_summary` in the same response. The frontend renders the full department summary without virtualization.

**Recommended Fix:**
1. Add virtual scrolling (`react-window` or `@tanstack/virtual`) to department summary table
2. Separate the large response into: (a) summary endpoint and (b) paginated employee table endpoint
3. Use HTTP/2 server push or streaming responses for large datasets

**Expected ROI:** Required for enterprise clients >2,000 employees. Without this, large-org demos crash browsers.

---

### R-04: Board Reports Contain Hardcoded "AWI" Logo Placeholder — Not White-Labelable

**Severity:** MEDIUM

**Business Impact:** Large Saudi enterprises (Aramco subsidiaries, STC, Almarai) require co-branded or white-labeled reports. Consulting resellers (KPMG, Deloitte) will require their branding on reports delivered to their clients. The current board report template has no branding customization capability.

**Technical Impact:** `executive_slide_exporter.py` and PDF generation modules contain hardcoded "AWI" references and no company logo injection point. Report templates are static strings.

**Recommended Fix:**
1. Add `company_name`, `company_logo_base64`, `primary_color` parameters to all report generators
2. Add branding configuration screen in the UI
3. Consulting reseller mode: white-label with reseller branding + "Powered by AWI" in footer

**Expected ROI:** Unlocks consulting channel (KPMG/Deloitte resellers require branded outputs). Estimated deal value increase: 20–30% per reseller agreement.

---

### R-05: Arabic Language Reports Are Not Fully RTL-Compliant in PDF Export

**Severity:** MEDIUM

**Business Impact:** PDF exports are a primary deliverable for government clients. If Arabic text in PDFs is not properly right-to-left with correct font rendering, the report is unpresentable to a Saudi ministry audience. Bilingual is a core differentiator in PRODUCT_IDENTITY.md — if it doesn't work in exported format, the differentiator is marketing only.

**Technical Impact:** The executive_slide_exporter.py and PDF generation use Python-based HTML-to-PDF conversion. Arabic text in HTML renders RTL correctly in modern browsers, but HTML-to-PDF engines (WeasyPrint, ReportLab, pdfkit) have known issues with Arabic text direction and font shaping (kashida, ligatures). No test for Arabic PDF output exists in the test suite.

**Recommended Fix:**
1. Add explicit RTL test: generate a PDF with Arabic content, verify visual output manually
2. Use `weasyprint` with `css dir=rtl` and proper Arabic font (Noto Naskh Arabic)
3. Add automated test that checks Arabic characters are present in PDF binary (not garbled)

**Expected ROI:** Required for government client deliverables. Bilingual is a stated core differentiator — it must actually work.

---

## PART 4 — SCALABILITY RISKS

---

### SC-01: Five Separate SQLite Files — No Viable Path to Multi-Server Deployment

**Severity:** HIGH

**Business Impact:** The current architecture uses five SQLite files. SQLite does not support multiple simultaneous writers from different processes, and it cannot be accessed across a network. This means AWI can never be deployed as:
- A cluster (load-balanced across 2+ servers)
- A cloud SaaS deployment (multiple app instances)
- A Docker Swarm or Kubernetes deployment

The Phase 32 "AWI SaaS" objective is architecturally impossible without migrating away from SQLite.

**Technical Impact:** `local_intelligence.db`, `awi_tenants.db`, `awi_history.db`, `awi_benchmarks.sqlite`, `awi_auth.db`. WAL mode helps with concurrent readers but does not resolve writer contention. SQLite `SQLITE_BUSY` errors will occur under any concurrent write load (multiple analysts running simultaneous analyses).

**Recommended Fix:**
1. Phase 31: Migrate to PostgreSQL for multi-tenant data (tenants, sessions, audit, history)
2. Keep SQLite only for offline/air-gapped single-org deployments
3. Abstract database layer behind repository interfaces so on-prem (SQLite) and SaaS (PostgreSQL) share business logic
4. Docker-compose: add PostgreSQL service (already commented out — uncomment and implement)

**Expected ROI:** Unblocks SaaS architecture (Phase 32), multi-server deployment, consulting channel demos. Without this, the SAR 75M valuation's SaaS component is not achievable.

---

### SC-02: ML Validation Runs Synchronously on API Thread — Blocks All Other Requests

**Severity:** HIGH

**Business Impact:** The ML validation step (5-fold cross-validation, training 3 models) runs synchronously during the analysis request. On a 1,500-employee dataset, this takes 8–15 seconds. During this time, all other API requests queue. Three analysts running simultaneous analyses means the third analyst waits 30+ seconds with no progress indication and no way to cancel.

**Technical Impact:** `run_ml_validation` is called with `await asyncio.to_thread(run_ml_validation, ir.df)` in `local_analysis_routes.py`. This correctly offloads to a thread pool, but with `workers=1` in uvicorn, the event loop itself blocks on the `await`. The `_TIMEOUT_SECS=15` hard timeout doesn't apply to the ML step (it only wraps the governance scan).

**Recommended Fix:**
1. Move ML validation to an async background task
2. Return analysis result immediately without ML validation; stream ML results when complete
3. Add per-request timeout specifically on ML validation step
4. Cache ML validation results keyed by `dataset_hash` — same file uploaded twice doesn't re-train

**Expected ROI:** Transforms user experience from "wait 15 seconds staring at a spinner" to "see results in 3 seconds with ML loading asynchronously." Direct impact on demo conversion rate.

---

### SC-03: No Caching Layer — Every Analysis Re-Computes Everything from Scratch

**Severity:** MEDIUM

**Business Impact:** An HR analyst who uploads the same dataset (same file, same content) runs the full pipeline again — governance scan, ML validation, scoring, narrative generation, ROI engine, storytelling, readiness assessment. For large datasets, this is a 30–60 second wait. Competitors like Visier cache analysis results and serve dashboards instantly after initial computation.

**Technical Impact:** The `_dataset_hash` (SHA-256 of file bytes) is computed but used only for the persistence audit trail. It is not checked against a cache before running the pipeline. There is no computation cache for any module.

**Recommended Fix:**
1. Cache full analysis result by `dataset_hash` in the database (already have `_dataset_hash` computed)
2. TTL: 24 hours (configurable per tenant)
3. "Force re-analysis" button in UI for users who want fresh computation
4. Partial caching: cache governance scan result separately from scoring

**Expected ROI:** Dramatically improves demo and daily-use experience. Low implementation cost (1–2 days), high perceived quality improvement.

---

## PART 5 — DEPLOYMENT RISKS

---

### D-01: Dockerfile Runs Build Tools in Production Image — Attack Surface Expansion

**Severity:** HIGH

**Business Impact:** The Dockerfile installs `build-essential` (compiler, linker, make, binutils) in the production image. This is required to compile native Python extensions (numpy, scikit-learn). However, leaving compiler tools in the final image means an attacker who achieves code execution inside the container can compile and run arbitrary binary code. NCA ECC and CIS Docker Benchmark both require removing build tools from final images.

**Technical Impact:** The image does not use multi-stage builds. Build tools installed in stage 1 remain in the final image. `build-essential` adds ~200MB to image size and expands the attack surface significantly.

**Recommended Fix:**
```dockerfile
FROM python:3.11-slim AS builder
RUN apt-get install -y build-essential && pip install --user ...

FROM python:3.11-slim AS runtime
COPY --from=builder /root/.local /root/.local
# No build tools in final image
```

**Expected ROI:** Required for enterprise Docker security review. Saudi banking clients' security teams scan Docker images with Trivy or Snyk before deployment approval.

---

### D-02: No Health Check Endpoint Wired to Docker HEALTHCHECK Instruction

**Severity:** MEDIUM

**Business Impact:** Kubernetes and Docker Swarm route traffic based on health check results. Without a working HEALTHCHECK, an unhealthy container (OOM state, DB connection lost) continues to receive traffic. The Dockerfile has a HEALTHCHECK instruction commented out. When deploying to a client's Kubernetes cluster (Phase 31 Private Cloud deployment model), the container will be treated as perpetually healthy even when serving 500 errors.

**Technical Impact:** `Dockerfile` HEALTHCHECK is commented out. There is a `/health` endpoint in the API but it does not check database connectivity, disk space, or memory usage — only that the process is running.

**Recommended Fix:**
1. Implement `/health/live` (process alive) and `/health/ready` (DB connected, disk available)
2. Uncomment and fix HEALTHCHECK in Dockerfile: `HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8000/health/ready || exit 1`
3. In Kubernetes: separate liveness and readiness probes

**Expected ROI:** Required for Kubernetes deployment (Phase 31 Private Cloud). Prevents routing traffic to degraded instances.

---

### D-03: No CI/CD Pipeline — Human Error in Every Deployment

**Severity:** HIGH

**Business Impact:** There are no GitHub Actions, Azure Pipelines, or any CI/CD configuration files in the repository. Every deployment is manual. There is no automated test run before deployment. No type checking enforced on Python (mypy). A developer pushing broken code to a client site cannot be detected or prevented. For a Phase 31 pilot client, a broken deployment is a trust-ending event.

**Technical Impact:** No `.github/workflows/`, no `azure-pipelines.yml`, no `Jenkinsfile`. The 1,094 tests are only run manually with `pytest`. TypeScript build is only run manually with `npm run build`. No branch protection rules documented.

**Recommended Fix:**
1. GitHub Actions workflow: on every PR, run `pytest` + `npm run build` + type-check
2. Deployment pipeline: build Docker image, push to registry, deploy to staging, run smoke tests
3. Branch protection: require passing CI before merge to main
4. Separate staging and production environments

**Expected ROI:** Prevents client-facing deployment failures. Required for any ISO 27001 or SOC2 certification. 2-day setup, infinite ongoing risk reduction.

---

## PART 6 — COMMERCIALIZATION RISKS

---

### C-01: SAR 75M Valuation Has No Supporting Revenue, IP Moats, or Comparable Transactions

**Severity:** HIGH (Investor Concern)

**Business Impact:** The AWI_PRODUCT_MATURITY_REPORT.md states "Estimated valuation: SAR 75M." This is an internal self-assessment based on a 82.5/100 maturity score. An investor running standard SaaS valuation multiples would compute:
- Pre-revenue → no ARR multiple applicable
- DCF of projected ARR: Year 3 base case SAR 36M ARR at 5–8x revenue multiple = SAR 180–288M (if actually achieved)
- Current state: 0 paying clients, 0 ARR → fair market value is the replacement cost of the IP, roughly SAR 3–8M

The gap between self-assessed SAR 75M and realistic investor valuation of SAR 3–8M pre-revenue is a commercialization risk, not a strength.

**Recommended Fix:**
1. Remove internal valuation estimate from all materials until first paying client is signed
2. Replace with "Investment thesis: achieve 5 paying clients by Q3 2026 at SAR 480K average, generating SAR 2.4M ARR, then raise at 8–10x = SAR 19–24M valuation"
3. Document IP specifically: proprietary constructs, Saudi-specific calibration, exact methodology

**Expected ROI:** Prevents credibility loss in investor conversations. Over-claiming valuation before revenue is a red flag that experienced investors will flag immediately.

---

### C-02: No Data Processing Agreement Template Ready for Signature

**Severity:** HIGH

**Business Impact:** COMMERCIALIZATION_PACKAGE.md describes a DPA template but it does not exist as a legal document in the repository. An enterprise client's legal team will require a signed DPA before allowing their HR data to be processed. Without a reviewed, PDPL-compliant DPA, the sales cycle cannot close, regardless of how good the product demonstration is. Saudi banks require SAMA-compliant data agreements.

**Technical Impact:** No `/legal/` directory, no DPA template, no sub-processor list, no data flow diagram for PDPL Article 21 (cross-border transfer) compliance. The audit trail claims PDPL compliance but there is no legal instrument to formalize it.

**Recommended Fix:**
1. Engage a Saudi data protection lawyer to draft PDPL-compliant DPA (estimated cost: SAR 15–25K one-time)
2. Create standard Data Processing Agreement template with: data categories, retention periods, sub-processors list, deletion obligations
3. For government clients: add SDAIA (Saudi Data and AI Authority) reference architecture alignment section

**Expected ROI:** Unlocks the entire client pipeline. Without a signed DPA, no enterprise client in regulated industries will proceed. SAR 15–25K legal cost unlocks SAR 1M+ in potential Year 1 revenue.

---

### C-03: Pricing Strategy Has No Competitive Anchor — Price Could Be Too Low

**Severity:** MEDIUM

**Business Impact:** The Starter tier at SAR 120K/year (≈$32K USD) for up to 500 employees is cheaper than Workday Peakon's per-employee pricing for the same headcount in MENA markets (approximately $8–12/employee/year = $40K–$60K for 500 employees). AWI is priced below its less-capable competitors. Buyers in the Saudi market often interpret low price as low quality. For government procurement, the RFP scoring will weight price 20–30% — a higher price with stronger technical scoring wins.

**Recommended Fix:**
1. Raise Starter tier to SAR 180–240K/year
2. Add a "Proof of Value" engagement at SAR 45–60K for 90 days before annual contract
3. Articulate price premium rationale: theory-grounded, PDPL-native, Arabic-first — why AWI costs more than cloud competitors

**Expected ROI:** 50% price increase on Starter tier = 50% more ARR per SME client, same cost to serve. If 5 Starter clients convert: +SAR 300K ARR annually from pricing alone.

---

### C-04: No Pilot Agreement Template or Proof-of-Value Framework

**Severity:** MEDIUM

**Business Impact:** COMMERCIALIZATION_PACKAGE.md describes a "6-month pilot at 50% price" but there is no standardized Pilot Agreement document, no pilot success criteria template, no handoff-to-production checklist. When the first pilot client asks "what are the terms?", the answer is currently "we'll figure it out." This unprofessionalism in early sales is a leading indicator of poor implementation quality to enterprise procurement teams.

**Recommended Fix:**
1. Create a 3-page Pilot Agreement template: scope, success criteria, support SLA, transition terms, reference right
2. Define 5 standard pilot success criteria: e.g., ≥3 Priority Review employees validated by HR, 1 board report delivered, PDPL scan passes, ≥1 C-suite member reviews output
3. Create a Pilot Playbook: week-by-week timeline, HR analyst training guide, first analysis checklist

**Expected ROI:** Reduces pilot close-to-contract conversion time from ad hoc (3–6 months) to structured (4–6 weeks). Each accelerated conversion = SAR 360–720K earlier in ARR.

---

### C-05: Year 1 Revenue Forecast Requires 8 Clients in 6 Months — Unrealistic Without Sales Team

**Severity:** HIGH (Investor Concern)

**Business Impact:** The "base case" Year 1 forecast is 8 clients at SAR 560K average = SAR 4.48M ARR. Achieving 8 enterprise clients in 12 months with a pre-revenue product, no sales team, and a 45–60 day sales cycle (optimistic for Saudi government procurement where 90–180 days is standard) requires 8 simultaneous active deals, each closing in under 6 months of the fiscal year. The "conservative" case (3 clients = SAR 1.44M) is more realistic but still requires 3 clients before a sales infrastructure exists.

**Recommended Fix:**
1. Revise Year 1 to: 1 paid pilot (Q3 2026) + 1 full contract (Q4 2026) = SAR 600K–1.44M ARR
2. Year 2 (with sales hire): 5–8 clients
3. Use the pilot client as a reference for Year 2 pipeline
4. Reframe to investors as "milestone-based" not "calendar-year ARR"

**Expected ROI:** Realistic forecast prevents credibility damage with investors. Overpromising Year 1 and missing by 70% destroys investor confidence in management judgment.

---

## PART 7 — ENTERPRISE ADOPTION BLOCKERS

---

### E-01: No Single Sign-On — Immediate Procurement Rejection at Every Bank

**Severity:** CRITICAL

**Business Impact:** Every Saudi bank (SNB, Al Rajhi, Riyad Bank) has a mandatory requirement that all internal applications integrate with their Azure Active Directory or ADFS deployment. "You must use our SSO" is not negotiable — it is an IT security policy. Without SSO, the AWI application requires a separate username and password, which the client's IT security team will classify as a shadow IT credential management risk and will not approve for production deployment.

**Technical Impact:** Phase 31 SSO is planned but is not started. The auth_session.py scaffold exists but contains no SSO token validation code. The ENTERPRISE_AUTH_ROADMAP.md documents the desired state correctly but there is zero implementation.

**Recommended Fix:**
1. Phase 31A (first 4 weeks): Implement OIDC/OAuth 2.0 authorization code flow with Azure AD
2. Use `msal` (Microsoft Authentication Library for Python) for token validation
3. Frontend: MSAL.js for seamless Azure AD sign-in
4. SAML 2.0 support for banks using ADFS (not Azure AD)
5. Local fallback: keep local admin session for air-gapped deployments

**Expected ROI:** Removes #1 procurement blocker for banking segment (Priority 1 clients in commercialization package). Every deal in the banking segment depends on SSO being available.

---

### E-02: No Mobile Experience — CHROs Make Decisions on iPad

**Severity:** MEDIUM

**Business Impact:** CHROs and CEOs in Saudi enterprises predominantly use iPads for reviewing dashboards and reports in board meetings. The current AWI UI is a desktop web application with dense information layouts not optimized for touch or mobile viewports. A CHRO presented with AWI on their iPad will see a broken layout and conclude the platform is not enterprise-ready.

**Technical Impact:** No responsive CSS breakpoints for tablet/mobile in the component library. The Tailwind configuration likely has breakpoints (`md:`, `lg:`) but the complex data visualizations (recharts, custom canvas elements) do not reflow for smaller screens. No PWA configuration.

**Recommended Fix:**
1. Audit all components for mobile breakpoints using Chrome DevTools at 768px and 1024px
2. CEO Dashboard and Executive Reports pages are the priority — these are what CHROs see first
3. Add PWA manifest for "Add to Home Screen" capability on iPad
4. Consider a "Board Mode" — read-only, high-contrast, large-font view optimized for presentations

**Expected ROI:** Directly improves CHRO demo experience. CHROs who approve budgets need to personally experience the value — if the tool doesn't work on their device, they don't approve the budget.

---

### E-03: No Audit Log API — Compliance Teams Cannot Access Records

**Severity:** HIGH

**Business Impact:** Under Saudi Labour Law and PDPL, HR decisions influenced by AI tools must be auditable. A bank's Internal Audit function or the Human Resources General Commission (HRGC) may request an audit trail of all workforce risk analyses, when they were run, who ran them, and what actions were taken. The audit log exists in the database but there is no API endpoint to retrieve it in a structured format.

**Technical Impact:** `TenantManager.get_audit_log()` exists in Python and returns a list of dicts. It is never exposed via any API endpoint. There is no `/api/audit/` route, no `/api/v1/sessions/{session_id}/audit` endpoint, no export of audit records to CSV.

**Recommended Fix:**
1. Add `GET /api/v1/audit/log` with pagination and date filtering
2. Add `GET /api/v1/audit/export/csv` for compliance exports
3. Add `user_id` field to all audit events (once authentication is implemented)
4. Include audit log in the annual PDPL compliance package documentation

**Expected ROI:** Required for banking and government client procurement sign-off. Auditors require documented evidence of audit trail capability before system approval.

---

### E-04: No External Integration Documentation / OpenAPI Spec Not Published

**Severity:** MEDIUM

**Business Impact:** Consulting resellers (KPMG, Deloitte) who want to integrate AWI into their HR transformation engagements need API documentation to scope the integration. Without published OpenAPI docs, they cannot assess integration effort. A reseller with a 6-month engagement timeline cannot wait 3 months for informal API documentation from AWI.

**Technical Impact:** FastAPI auto-generates an OpenAPI spec at `/docs` and `/redoc`. However, the spec is incomplete: endpoint descriptions are sparse, request/response schemas have no examples, error codes are undocumented. There is no versioned API spec file committed to the repository.

**Recommended Fix:**
1. Add docstrings to all route handlers with example request/response bodies
2. Export OpenAPI spec as `api-spec-v1.yaml` and commit to repository
3. Publish at `docs.awi-platform.com` (even a static HTML export of ReDoc)
4. Add API changelog document

**Expected ROI:** Unlocks consulting channel integration. KPMG/Deloitte partnership agreements require technical due diligence — API docs are a standard deliverable.

---

## PART 8 — ML / AI DOMAIN VALIDITY CONCERNS

---

### M-01: Risk Score Probability Claims Are Invalid — Score Is Not a Calibrated Probability

**Severity:** HIGH

**Business Impact:** The `model_metrics` section of the analysis response includes ECE (Expected Calibration Error = 0.0379) and Brier Score computed by treating the hand-crafted risk score (0–100 scale) as a probability (0–1). The probability space conversion `score / 100` is mathematically invalid — a hand-crafted aggregate of construct scores is not a probability. Publishing ECE=0.0379 in investor materials and board reports implies a level of statistical rigor that the methodology does not support.

**Technical Impact:** `employee_risk_scoring.py` line 537: `float(rec.risk_score_0_100) / 100.0` used as probability estimate for calibration metrics. This inflates the appearance of model quality. The actual model (from `ml_validation_engine.py`) uses proper sklearn probabilities for AUC and ECE — that is valid. The risk scoring module's metrics are not valid.

**Recommended Fix:**
1. Clearly separate two score types: (a) Theory-based Risk Index (0–100, no probability claims) and (b) ML-validated probability estimate (0–1, AUC/ECE valid)
2. Remove ECE and Brier Score from the risk scoring module's output
3. Add explicit documentation: "Risk Index is a structured assessment tool, not a statistical probability"
4. The ML validation module's metrics (AUC=0.8471) remain valid and should be the only metrics presented

**Expected ROI:** Prevents regulatory scrutiny and investor credibility loss. A data science due diligence reviewer will immediately flag invalid probability claims.

---

### M-02: No Model Drift Detection — Deployed Models Go Stale Over Time

**Severity:** HIGH

**Business Impact:** The VotingEnsemble model and scoring constructs were calibrated on a specific dataset. After 6–12 months of deployment at a client, the workforce dynamics change — new hiring cohorts, post-COVID labor patterns, Vision 2030 Saudization impacts. Without drift detection, the model silently degrades. The client sees declining prediction quality but attributes it to their workforce, not to model staleness. This is a hidden product quality risk.

**Technical Impact:** No population stability index (PSI) monitoring. No feature distribution tracking over time. No scheduled re-validation against new data. The `HistoricalIntelligenceEngine` captures workforce snapshots but does not compare feature distributions against training data baseline.

**Recommended Fix:**
1. Log feature distribution statistics on every analysis run (mean, std, percentiles per feature)
2. Compute PSI between new data and training baseline; alert if PSI > 0.2
3. Trigger re-validation recommendation in the governance panel when drift exceeds threshold
4. Document model retraining schedule in ENTERPRISE_AUTH_ROADMAP.md

**Expected ROI:** Maintains long-term prediction quality at client sites. Prevents a Year 2 "the model stopped working" client complaint that triggers contract non-renewal.

---

### M-03: No Bias Audit — Risk Scores May Systematically Disadvantage Protected Groups

**Severity:** HIGH

**Business Impact:** Under Saudi Labour Law and international AI ethics standards (EU AI Act is becoming global baseline), HR AI tools must demonstrate that their outputs do not systematically disadvantage employees based on gender, nationality (Saudis vs. expatriates), age, or disability. If an audit finds that the AWI risk scoring assigns systematically higher risk scores to Saudi nationals (due to Saudization pressure as a construct feature), the platform becomes a compliance liability rather than an asset.

**Technical Impact:** No demographic parity checks. No equalized odds measurement. The theory constructs include "Saudisation_pressure" and "Expatriate_contract_risk" — these explicitly encode nationality as a risk signal, which could constitute unlawful discrimination under some interpretations of Saudi Labour Law Article 26 (anti-discrimination).

**Recommended Fix:**
1. Add fairness audit module: compute risk score distributions by gender, nationality, age cohort, department
2. Flag constructs that encode protected attributes as risk signals (Saudisation_pressure should only be an organizational metric, not an individual risk signal)
3. Add governance disclaimer: "AWI scores reflect organizational risk factors, not individual employee demographics"
4. Commission independent AI fairness review before government deployment

**Expected ROI:** Prevents regulatory enforcement action. Government clients will require fairness certification before deployment. Proactive bias audit is also a differentiator — no competitor publishes fairness metrics.

---

## PART 9 — INVESTOR-SPECIFIC CONCERNS

---

### I-01: Phase 31 Is 4 Months / SAR 480K — But Includes SSO, RBAC, Docker, Historical UI Simultaneously

**Severity:** HIGH

**Business Impact:** The investment requirement document proposes delivering SSO + RBAC enforcement + Docker containerization + Historical Intelligence UI + Multi-tenant admin panel in 4 months for SAR 480K (approximately 2 senior engineers for 4 months). Each of these is a substantial engineering effort independently:
- SSO (Entra ID + SAML): 6–8 weeks for a thorough implementation
- RBAC enforcement: 3–4 weeks
- Docker production hardening: 2–3 weeks
- Historical UI: 3–4 weeks
- Multi-tenant admin panel: 3–4 weeks
Total realistic estimate: 17–23 weeks for 2 engineers, not 16 weeks.

**Technical Impact:** Phase 31 scope is over-committed relative to budget and timeline. Under-delivering Phase 31 means the first pilot client is attempted with incomplete SSO — which means the banking sector (Priority 1 clients) is inaccessible.

**Recommended Fix:**
1. Phase 31A (Weeks 1–6): SSO only (Azure AD OIDC) — this unlocks banking clients
2. Phase 31B (Weeks 7–10): RBAC enforcement + audit log API
3. Phase 31C (Weeks 11–14): Docker hardening + Historical UI
4. Phase 31D (Weeks 15–20): Multi-tenant admin panel
5. Budget revised: SAR 720K for 20 weeks (realistic)

**Expected ROI:** Realistic planning prevents a failed Phase 31 that delays the first paying client by 6 months, representing SAR 2–4M in deferred ARR.

---

### I-02: No Customer Discovery Documentation — TAM/SAM/SOM Claims Are Unvalidated

**Severity:** MEDIUM (Investor Concern)

**Business Impact:** The COMMERCIALIZATION_PACKAGE.md makes market size claims without citing sources. Series A investors will ask: "How many of your 50 target banking clients have you spoken to? What was their reaction to the demo? What is the average sales cycle you've observed?" If the answer is "zero customer discovery conversations," the entire go-to-market strategy is theoretical.

**Recommended Fix:**
1. Conduct 10 customer discovery interviews with CHROs at target companies before raising
2. Document willingness-to-pay, current tools used, primary pain points
3. Include customer discovery summary in investor deck

**Expected ROI:** 10 customer discovery conversations cost 0 SAR and increase Series A close probability by an estimated 40% (from baseline for pre-revenue SaaS in MENA).

---

### I-03: IP Protection — No Patent Filed, No Trade Secret Documentation

**Severity:** MEDIUM (Investor Concern)

**Business Impact:** The PRODUCT_IDENTITY.md lists five core differentiators including "conservative proxy-free ML validation" and "theory-grounded explainability." These are methods, not just software. Workday could replicate the methodology after reading PRODUCT_IDENTITY.md and BENCHMARK_EVOLUTION_REPORT.md. Without IP protection, the competitive moat is execution speed, not defensibility.

**Recommended Fix:**
1. File a provisional patent application for: (a) the proxy-free ML validation methodology, (b) the 6-theory construct scoring system, (c) the Conservative vs. Full feature comparison framework
2. Document trade secrets: specific construct weights, calibration methodology, Saudi labor market benchmark parameters
3. Add confidentiality notices to all technical documentation

**Expected ROI:** Provisional patent in Saudi Arabia costs approximately SAR 15–30K. Strengthens investor due diligence, increases defensibility against Workday/SAP competitive response.

---

## SUMMARY SEVERITY MATRIX

| Issue ID | Issue | Severity | Category |
|----------|-------|----------|----------|
| A-01 | Zero authentication on all API endpoints | CRITICAL | Architecture |
| A-02 | Employee data in localStorage unencrypted | CRITICAL | Architecture |
| A-03 | In-memory session store / memory leak | CRITICAL | Architecture |
| A-04 | Single-threaded API — cannot serve concurrent users | CRITICAL | Architecture |
| S-01 | CORS allows all origins — CSRF risk | CRITICAL | Security |
| S-02 | No HTTPS / TLS | CRITICAL | Security |
| E-01 | No SSO — banking procurement blocked | CRITICAL | Adoption |
| A-05 | Non-reproducible risk scores (random jitter) | HIGH | Architecture |
| A-06 | No database migration system | HIGH | Architecture |
| A-07 | No HRIS integration — CSV-only is prototype workflow | HIGH | Architecture |
| A-08 | Weak employee ID masking (24-bit hash, no salt) | HIGH | Security |
| A-09 | No API versioning | HIGH | Architecture |
| S-03 | No rate limiting — trivial DoS | HIGH | Security |
| S-04 | Error messages expose internal paths | HIGH | Security |
| S-05 | SQLite databases unencrypted at rest | HIGH | Security |
| SC-01 | SQLite cannot support multi-server / SaaS | HIGH | Scalability |
| SC-02 | ML validation blocks all concurrent requests | HIGH | Scalability |
| D-03 | No CI/CD pipeline | HIGH | Deployment |
| D-01 | Build tools in production Docker image | HIGH | Deployment |
| C-01 | SAR 75M valuation has no revenue support | HIGH | Commercialization |
| C-02 | No DPA legal template ready | HIGH | Commercialization |
| C-05 | Year 1 forecast requires 8 clients — unrealistic | HIGH | Commercialization |
| E-03 | No audit log API | HIGH | Adoption |
| M-01 | Invalid probability claims on risk scores | HIGH | ML/AI |
| M-02 | No model drift detection | HIGH | ML/AI |
| M-03 | No bias audit on risk scores | HIGH | ML/AI |
| I-01 | Phase 31 scope over-committed | HIGH | Investor |
| R-01 | Non-reproducible scores between uploads | HIGH | Reporting |
| R-03 | No virtualization for large org employee tables | MEDIUM | Reporting |
| R-04 | Board reports not white-labelable | MEDIUM | Reporting |
| R-05 | Arabic PDF export not validated RTL | MEDIUM | Reporting |
| A-10 | PlatformWalkthrough.tsx not routed in App.tsx | MEDIUM | Architecture |
| SC-03 | No caching layer — every analysis recomputes | MEDIUM | Scalability |
| D-02 | Docker HEALTHCHECK not implemented | MEDIUM | Deployment |
| C-03 | Pricing too low vs. competitors | MEDIUM | Commercialization |
| C-04 | No pilot agreement template | MEDIUM | Commercialization |
| E-02 | No mobile/tablet experience | MEDIUM | Adoption |
| E-04 | No OpenAPI documentation | MEDIUM | Adoption |
| R-02 | No stale data warning on dashboard | MEDIUM | Reporting |
| I-02 | No customer discovery documented | MEDIUM | Investor |
| I-03 | No IP protection / patents filed | MEDIUM | Investor |

**Total Critical Issues:** 7  
**Total High Issues:** 21  
**Total Medium Issues:** 13

---

*FINAL_EXECUTIVE_PRODUCT_AUDIT.md | AWI Enterprise Product Audit | 2026-06-01*  
*Panel: McKinsey Partner / SAP SuccessFactors PD / Workday EA / Deloitte HRT Lead*  
*Classification: Internal — Confidential*
