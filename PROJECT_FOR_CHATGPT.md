# PROJECT SUMMARY

**Project Name:** Adaptive Workforce Intelligence Engine (internal codename "AWI" / "Adaptive_Workforce_AI"), version 2.5.1.

**Purpose:** An HR-analytics platform that ingests an organization's employee dataset (CSV/Excel/JSON/Parquet), automatically classifies what kind of dataset it is, runs governance checks (PII/data-leakage detection), computes employee attrition-risk scores via classical machine learning, generates psychology-theory-grounded workforce constructs, and produces executive-facing dashboards, forecasts, ROI estimates, and board-ready reports (PDF/PPTX/HTML) — all positioned for the Saudi Arabian market with PDPL (Personal Data Protection Law) compliance framing.

**Business Problem:** Employee attrition is expensive and hard to predict early. The product's pitch is "upload your HR data, get statistically grounded attrition risk, department-level stability scores, financial exposure estimates, and board-ready reports — without a data science team," with extra emphasis on Arabic-language support, Saudi HR schema recognition, and regulatory-safe language (no deterministic "this employee will quit" claims).

**Target Users:** HR executives / C-suite (CHRO, CEO) at mid-to-large organizations, primarily framed for the Saudi/GCC market; secondary audience is HR analysts who upload and review data quality.

**Current Status:** Advanced-prototype / pre-commercial. The codebase is large and functionally rich (81 backend modules, 16 React pages, ~1150 passing tests), but a full independent audit (performed in this same session, see `AUDIT_REPORT.md` in the repo root) found: **no client/tenant has ever used the system** (all account/tenant databases are empty), **the shipped frontend has zero authentication** despite a fully-built auth system existing, and several "advertised" capabilities (XGBoost/LightGBM/CatBoost ensemble ML, 3 named governance modules) are not actually reachable from the product a user opens. See `AUDIT_REPORT.md` for full detail — this document is deliberately more neutral/descriptive; the audit report is the critical companion read.

**Estimated Completion %:** ~65-70% toward a genuine commercial MVP. Core data pipeline, ML scoring, dashboards, and report exports work end-to-end. Missing/broken for production readiness: authentication wired into the live product, a single consistent ML path, CI/CD, a real multi-tenant/client onboarding flow, and resolution of the duplicate-implementation problem (see Known Issues).

**Key Features:**
- Adaptive dataset ingestion — auto-detects dataset type (HR attrition, job-market postings, government workforce tables, biosignal/wearable data, etc.) and routes to the appropriate analysis mode.
- Governance-first upload — PII and data-leakage column detection before any modeling; blocks or conditionally allows analysis.
- Employee-level and department-level attrition risk scoring (0-100 scale) with band classification (stable / monitoring / strategic concern / priority review).
- "Theory-grounded" psychological construct engine — computes ~25 named constructs intended to map to published organizational-psychology formulas (burnout, engagement, etc.).
- Executive dashboards: CEO dashboard, risk segmentation, department heatmaps, workforce stability index, financial-exposure treemaps, benchmark comparison against sector data.
- Board-ready report generation in 3 formats (PDF, PPTX, printable HTML slide deck), bilingual English/Arabic.
- Workforce simulation ("what-if" scenario modeling) and forecasting.
- Local, single-machine, no-cloud-dependency deployment story ("fully offline", SQLite-based).
- A separate, secondary Streamlit-based frontend/analysis app exists in parallel to the primary React app (see Architecture).

**Competitive Advantages (as positioned by the product's own documentation):** Saudi/Arabic-market specialization (column-name normalization for local HR/ERP exports, Arabic report localization, SAR currency default), a bespoke "theory-grounded" academic-formula construct engine differentiating it from generic AutoML attrition tools, and an emphasis on "governance-safe" executive language (a hardcoded list of forbidden deterministic phrases like "will leave"/"terminate" is filtered from AI-generated text). Whether these are fully realized in the live, user-facing product varies — see `AUDIT_REPORT.md`.

---

# REPOSITORY STRUCTURE

```
Adaptive_Workforce_AI/
├── backend/
│   ├── api/            # FastAPI route definitions (6 files; only 3 are mounted live)
│   ├── core/            # 81 business-logic/ML/governance modules — the bulk of the backend
│   └── models/           # Empty package (only __init__.py) — unused
├── config/
│   └── settings.py       # Single source of truth for platform constants, thresholds, taxonomies
├── data/
│   ├── uploads/, outputs/  # Runtime scratch dirs (empty in repo)
│   └── *.db, *.sqlite     # Runtime SQLite databases (local_intelligence, awi_benchmarks)
├── datasets/
│   └── saudi/             # Empty — intended location for reference Saudi datasets, unused
├── docs/                  # 6 business/pitch markdown docs (sales deck, demo script) — not technical docs
├── executive-ui/          # PRIMARY live frontend: React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── pages/          # 16 top-level views (dashboards, upload, reports, etc.)
│   │   ├── components/     # dashboard/, governance/, shared/, theory/, visualizations/ subfolders
│   │   ├── context/         # React Context providers (Analysis, EmployeeRisk, Language, Theme)
│   │   ├── state/            # localStorage-backed state stores + API client wrappers
│   │   ├── data/              # Hardcoded demo-company datasets (used only by orphaned demo pages)
│   │   ├── layout/             # App shell (Sidebar, TopBar, AppLayout)
│   │   └── types/               # Shared TS types
│   └── dist/                     # Committed build output (stale artifact, should not be in VCS)
├── frontend/               # SECONDARY, parallel Streamlit application (off by default)
│   ├── app.py                # Streamlit entry point, ~3000+ lines, duplicates orchestration logic
│   ├── pages/                 # 9 Streamlit page modules
│   ├── components/             # governance_panel.py, safe_tables.py, metric_cards.py
│   └── utils/                    # demo_mode.py, session_state.py, formatting.py, session_helpers.py
├── frontendcomponents/, frontendpages/, frontendutils/   # Empty stray directories — repo debris, not used by anything
├── scripts/                # 4 standalone Python scripts (ML search, release checks) — no CI wiring
├── tests/                  # 37 pytest test files (the only directory pytest.ini collects)
├── *.md (root, ~150 files) # Historical, self-authored "phase completion" and "audit" narrative docs
├── *.py (root, "_"-prefixed) # 4 standalone debug scripts (_smoke_test.py, _audit_scan.py, etc.)
├── test_*.py (root, 7 files) # Real tests, but NOT collected by pytest.ini — orphaned from CI
├── *.mjs (root, ~9 files)   # Playwright screenshot/verification scripts, run manually only
├── Dockerfile, docker-compose.yml   # Container definitions (CMD has a confirmed bug — see Known Issues)
├── requirements.txt, pytest.ini, .env.example
└── awi_history.db, awi_tenants.db  # Root-level runtime SQLite databases
```

**Per-folder responsibility summary:**

| Folder | Purpose | Responsibility | Main files |
|---|---|---|---|
| `backend/api/` | HTTP boundary | Defines FastAPI routers; only `auth_routes.py` and `local_analysis_routes.py` are mounted into the running app | `main.py` (entry point), `local_analysis_routes.py` (the real workhorse, ~1560 lines) |
| `backend/core/` | Business/ML logic | Everything from file ingestion to ML training to report rendering lives here as standalone, mostly-independent modules | `ml_router.py`, `ml_validation_engine.py`, `feature_factory.py`, `risk_intelligence.py`, the 5 report exporters |
| `config/` | Global constants | Single authoritative source for taxonomies, thresholds, currency, forbidden-language lists | `settings.py` |
| `executive-ui/` | Live product UI | The React SPA a real user interacts with | `App.tsx` (client-side page switch, not react-router despite it being a dependency), `pages/DataUpload.tsx` (true entry point) |
| `frontend/` | Alternate UI | A separate Streamlit app that reimplements the pipeline in-process rather than calling the FastAPI backend | `app.py` |
| `tests/` | Automated verification | The only test directory pytest actually runs by default | 37 files, ~1150 passing tests |
| `scripts/` | Manual ML/ops tooling | One-off scripts for model search and release checks, run by hand | `phase29_5_model_search.py` (source of the repo's headline 0.8471 AUC figure) |

---

# TECHNOLOGY STACK

**Frontend (primary, live):** React 18.3, TypeScript 5.4 (strict mode), Vite 5.2 (dev server + bundler), Tailwind CSS 3.4, Framer Motion 11 (animation), Recharts 2.12 (charts), Lucide React (icons). `react-router-dom` 6.23 is a declared dependency but **not actually used** — routing is a hand-rolled `useState` switch in `App.tsx`. Playwright 1.60 is present as a devDependency for manual verification scripts, not CI.

**Frontend (secondary, alternate):** Streamlit ≥1.28, Plotly ≥5.17 for charts, run as a standalone Python process, off by default.

**Backend:** Python (3.9+ syntax features observed; no `.python-version` pinned), FastAPI ≥0.103, Uvicorn ≥0.23 (ASGI server), no ORM — raw `sqlite3` standard-library module throughout.

**Database:** SQLite only, multiple separate `.db`/`.sqlite` files (no PostgreSQL/MySQL despite `.env.example` referencing optional Postgres config for "production audit persistence" — never actually implemented). No formal migration tool; schema is created idempotently via `CREATE TABLE IF NOT EXISTS` in each module's `_ensure_schema()`-style function.

**AI / ML Frameworks:** scikit-learn ≥1.3 (the actual live-path models: LogisticRegression, RandomForest, GradientBoosting), XGBoost ≥1.7, LightGBM ≥4.0, CatBoost ≥1.2, imbalanced-learn ≥0.11 (SMOTE — only used in the non-live `ml_router.py` path), Optuna ≥3.3 (hyperparameter search, used in `automl_engine.py` which is dead code with zero references), SHAP (declared nowhere in `requirements.txt` but installed in the global Python env and used only by the Streamlit app's explainability page).

**No LLM / generative AI, no vector database, no embeddings anywhere in the codebase** — confirmed by direct search (see AI System section). All "AI" is classical statistical ML plus deterministic rule/template-based natural-language generation.

**Other notable libraries:** rapidfuzz (fuzzy column-name matching — has a confirmed live bug, `AttributeError: rapidfuzz.fuzz has no attribute 'token_set_ratio'`), Prophet + statsmodels (time-series forecasting, declared but largely unreferenced), openpyxl + pyarrow (Excel/Parquet I/O), fpdf2 (PDF generation for one dead exporter), python-pptx (PowerPoint generation, live), passlib[bcrypt] + python-jose[cryptography] (JWT auth system — real but disconnected from the live UI).

**Authentication:** Custom-built local auth system (bcrypt password hashing, JWT access/refresh tokens, account lockout, RBAC) — fully implemented but never invoked by the shipped frontend (see Security Review).

**Hosting / Cloud Services:** None integrated. The `.env.example` mentions AWS Secrets Manager / Azure Key Vault / HashiCorp Vault as recommendations for production secret management, but no actual cloud SDK or integration exists anywhere in the code. This is a fully local/on-premises-oriented deployment.

**Deployment:** Docker + docker-compose provided (API service only, by default). The documented Docker `CMD` has a confirmed bug (references a module-level `app` object that doesn't exist). No CI/CD pipeline of any kind exists in the repository.

**Dev Tools:** pytest (test runner, not declared in requirements.txt), Playwright (manual E2E screenshot scripts), ESLint/Prettier not detected, TypeScript strict mode enabled for the frontend.

**Languages:** Python (backend, ~81+ core modules plus API/scripts/tests), TypeScript/TSX (executive-ui), a small amount of vanilla JS (`.mjs` Playwright scripts), Markdown (extensive — ~150 root-level narrative documents), SQL (inline, no separate `.sql` files).

---

# HIGH LEVEL ARCHITECTURE

**Frontend:** Two independent frontends exist. (1) `executive-ui` — a React 18 + TypeScript SPA served by Vite in dev, built to static assets for production. It is the live/primary product surface. Client-side "routing" is a hand-rolled `useState` switch in `App.tsx`, not `react-router-dom` (declared but unused). It talks to the backend exclusively over `fetch()` calls to `/api/local/*`. (2) `frontend/app.py` — a Streamlit application that does NOT call the backend over HTTP at all; it imports `backend/core/*` modules directly and runs the pipeline in-process, in its own Python runtime, off by default in the shipped Docker Compose setup.

**Backend:** A single FastAPI process (`backend/api/main.py`, `create_app()`) mounts two routers — `auth_routes.py` (`/api/auth/*`, JWT-based) and `local_analysis_routes.py` (`/api/local/*`, the real workhorse, no auth). Three additional, fully-implemented routers (`upload_routes.py`, `report_routes.py`, `enterprise_routes.py`) exist but are never mounted — dead weight representing an earlier, more elaborate multi-tenant SaaS design that was superseded by the simpler local-analysis approach without being deleted. `backend/core/` (81 modules) is the shared business-logic substrate consumed unevenly by these different entry points.

**Database:** SQLite only, 7 separate `.db`/`.sqlite` files, no ORM, no formal migrations (see DATABASE section). No shared connection pool or central data-access layer — each module manages its own connection lifecycle.

**Authentication:** A real, well-built JWT/bcrypt local auth system exists (`local_auth.py` + `auth_routes.py`) but is architecturally isolated — it protects only the `/api/auth/*` router, and nothing in `local_analysis_routes.py` (the router the live frontend actually calls) references it. Architecturally, this is a bolt-on auth layer that was never actually integrated into the main request path.

**AI Layer:** No LLM, no embeddings, no vector store (verified by dependency and code-string audit, with a runtime-enforced block on OpenAI API calls). The "AI layer" is: (1) a deterministic data-profiling/routing/cleaning pipeline, (2) a psychology-theory-grounded feature-construction engine with real, cited formulas, (3) classical supervised ML (two competing implementations — see below), and (4) template-based natural-language generation for all "insights"/"narratives"/"recommendations."

**Prediction Layer:** Two independent, non-overlapping ML training implementations exist. `ml_router.py` (XGBoost/LightGBM/CatBoost/LR/RF/GB with SMOTE applied only inside cross-validation folds) is reachable only via the dead-to-the-live-frontend `/api/v1/analyse` endpoint and the Streamlit app. `ml_validation_engine.py` (LogisticRegression/RandomForest/GradientBoosting only, class-weight balancing instead of SMOTE, StratifiedKFold(5) with per-fold-refit preprocessing) is the one actually invoked by the live `/api/local/upload/analyze-with-employees` endpoint the React frontend calls.

**Business Logic:** A 12-module "executive intelligence" layer (indices, ROI, forecasting, simulation, narratives, decision intelligence — see BUSINESS LOGIC section) sits between raw risk scores and the API response, mostly live-wired into the same `/upload/analyze-with-employees` call chain.

**External APIs:** None. This is architected as a fully offline, on-premises system — `offline_mode_guard.py` actively blocks outbound network calls at the socket level. No third-party API integrations (payment, email, cloud storage, identity provider, LLM) exist anywhere in the codebase.

**Background Workers:** None. No job queue (Redis is mentioned in `.env.example` but never implemented), no Celery/RQ/task-runner of any kind. Long-running work (ML training, report generation) happens synchronously within the HTTP request lifecycle, offloaded to a thread pool via `asyncio.to_thread` so it doesn't block the event loop, but still tying up the client's open connection for the full duration.

**File Storage:** Local filesystem only (`data/uploads/`, `data/outputs/`, `saved_models/`) — uploaded file bytes are generally NOT persisted to disk in the live `/api/local/*` path (in-memory scan only, per `SecureFileIngestion`'s own design-rules docstring); only derived, aggregated, PII-scrubbed results are written to SQLite.

**Caching:** None identified anywhere in the codebase.

---

# APPLICATION FLOW

**1. A user opens the application.** They navigate to `http://localhost:5173` (Vite dev server) or a built static bundle. `App.tsx` mounts `ThemeProvider → LanguageProvider → AnalysisProvider → EmployeeRiskProvider → AppContent`. `AnalysisProvider`/`EmployeeRiskProvider` immediately attempt to load any prior session from `localStorage` (`awi-real-analysis-v1` key, versioned schema). If none exists, the app lands on the `DataUpload` page by default (`activePage` initial state = `'upload'`). No login screen appears at any point — the app is immediately usable.

**2. "Logs in."** This step does not actually occur in the shipped product — there is no login page in the React app's 16 pages, and no code path calls `/api/auth/login`. (If a developer or integrator wanted to exercise the real auth system directly via API calls, they would `POST /api/auth/bootstrap` with a chosen password to create the first admin, then `POST /api/auth/login` to get a JWT — but nothing in the live UI does this.)

**3. Uses the primary feature — data upload.** User drags/selects a file on `DataUpload.tsx`. The component immediately `fetch('/api/local/upload/analyze', {method:'POST', body: FormData})`. The backend: reads the file bytes → applies Saudi HR column normalization (e.g. `Attrition`→`flight_risk` so it isn't flagged as leakage) → runs `SecureFileIngestion.scan()` (PII/leakage detection, data-quality metrics, 15-second hard timeout) → runs `DatasetTypeClassifier.classify()` → computes a 0-100 health score → returns readiness level (READY/CONDITIONAL/BLOCKED), governance findings, and workforce-capability indicators. The frontend renders this immediately (`ScanResultPanel`) and, if `row_count > 0`, **concurrently** fires a second request.

**4. Requests an AI prediction (fires automatically, not user-initiated as a separate step).** The second request, `POST /api/local/upload/analyze-with-employees`, re-uploads the same file and triggers the full pipeline: per-employee risk/stability scoring (`EmployeeRiskScorer`) → department/specialty summaries → org narrative generation → workforce forecast → **ML validation** (`run_ml_validation` — trains LogisticRegression/RandomForest/GradientBoosting via 5-fold CV, this is the actual "AI prediction" step) → workforce simulation (8 intervention scenarios) → executive decision intelligence → 4 executive-index/ROI/storytelling/readiness computations → a snapshot write to `awi_history.db`. Every sub-step is wrapped in try/except with a non-fatal fallback, so a failure in e.g. the simulation engine doesn't take down the whole response.

**5. Receives a response.** The frontend receives a large JSON payload (paginated employee risk table, department summaries, executive indices, ROI figures, narrative text, simulation scenarios, decision-intelligence output). `buildAnalysisFromApiResponse()` and `buildEmployeeRiskFromApiResponse()` normalize this into typed state, persisted to `localStorage` and pushed into React Context (`AnalysisContext`, `EmployeeRiskContext`) so every other page can read it without re-fetching.

**6. Saves data.** Persistence already happened server-side during step 4 — `local_analysis_routes.py` writes the session, results, ML metrics, and governance audit trail to `data/local_intelligence.db` automatically as part of handling the request (no separate "save" action exists client-side). The client additionally mirrors the response into `localStorage` purely for instant page-refresh continuity.

**7. Loads reports.** Navigating to `ExecutiveReports.tsx`, the user can trigger `POST /api/local/export/slides` (returns HTML deck content, rendered client-side or printed), `POST /api/local/export/pptx` (returns a binary `.pptx` download, built with python-pptx), or `POST /api/local/export/pdf` (attempts a headless-Chromium/Playwright subprocess render of "Board Report V3," falling back to a JSON/HTML payload if that's unavailable). All three independently recompute the same financial-exposure figures from the request payload rather than reusing a shared computation (see BUSINESS LOGIC).

**8. Uses other major features:** `EmployeeRiskDashboard` paginates/filters/sorts the per-employee table already in context (no new fetch, unless the user explicitly re-uploads). `AnalysisHistory` calls `GET /api/local/sessions` to list prior runs and `GET /api/local/sessions/{id}` to reload one. `GovernancePanel`, `TheoryExplainability`, `TrustPanel`, `RiskSegmentation`, `SimulationPanel`, `DecisionCenter` all read from the already-populated Context/localStorage state rather than making their own network calls (with the caveat that several of them fall back to a client-side statistical estimate, `estimateRiskSegments()`, when the employee-level scoring response hasn't arrived yet — see the audit's frontend deep-dive for the exact pages affected).

---

# MAJOR MODULES

**Ingestion & Governance** (`secure_file_ingestion.py`, `excel_ingestion_engine.py`, `dataset_type_classifier.py`) — Purpose: safely parse arbitrary uploaded files and gate what can proceed. Responsibilities: format detection, PII/leakage column detection (self-contained keyword logic, not delegated to the separate `leakage_detector.py`), dataset-type classification into 4 top-level modes (HR attrition / job market / government workforce / stress-test). Dependencies: pandas/openpyxl for parsing. Important classes: `SecureFileIngestion`, `DatasetTypeClassifier`.

**Adaptive Pipeline Core** (`dataset_profiler.py`, `semantic_mapper.py`, `adaptive_router.py`, `data_healer.py`, `feature_factory.py`) — Purpose: transform a raw, arbitrary dataframe into a model-ready feature matrix. Responsibilities: statistical profiling, column-to-semantic-category mapping, dataset-type/modality routing, 9-step deterministic cleaning, layered feature engineering (gated by the `SCIENTIFIC_FEATURE_MODE` flag). Dependencies: numpy/pandas/scipy/rapidfuzz/scikit-learn. Important classes: `DatasetProfiler`, `SemanticMapper`, `AdaptiveRouter`, `DataHealer`, `FeatureFactory`.

**Theory-Grounded Construct Engine** (`theory_aware_column_mapper.py`, `theory_grounded_construct_engine.py`) — Purpose: the platform's scientific differentiator — maps columns to 27 organizational-psychology constructs and computes 7 of them via literature-cited formulas. Dependencies: pandas, the `feature_factory.py` pipeline stage that calls it. Important classes: `TheoryAwareColumnMapper`, construct-computation functions in `compute_constructs()`.

**ML Training (two competing implementations)** (`ml_router.py`, `ml_validation_engine.py`) — Purpose: train and evaluate classification models on the (governance-cleared) feature matrix. `ml_router.py`: multi-strategy (classification/regression/clustering/survival), XGBoost/LightGBM/CatBoost/ensemble, SMOTE-in-CV-folds, integrates 3 governance modules (leakage detector, model validator, truth auditor) — reachable only via the non-live `/api/v1/analyse` endpoint and Streamlit. `ml_validation_engine.py`: simpler 3-model sklearn-only path, class-weight balancing, no SMOTE — the one the live frontend actually reaches. Important classes: `MLRouter`, function `run_ml_validation`.

**Risk Scoring** (`risk_intelligence.py`, `employee_risk_scoring.py`, `employee_explainability_engine.py`) — Purpose: turn model probabilities into individual/department/organization risk scores, financial-exposure estimates, and human-readable driver explanations. Dependencies: the trained model's output probabilities, `config/settings.py`'s risk-level thresholds. Important classes: `EmployeeRiskScorer`, functions `score_individuals`/`score_departments`/`score_organization`.

**Executive Intelligence Layer** (12 modules — see BUSINESS LOGIC section for the full list) — Purpose: convert risk scores into board-facing indices, financial ROI, narratives, forecasts, simulations, and strategic priorities. This is the largest single functional cluster by module count and is where the most significant cross-module duplication (financial formulas, risk labeling, grading) was found.

**Report/Export Generation** (`executive_pdf_exporter.py`, `executive_pptx_exporter.py`, `executive_slide_exporter.py`, plus the dead `executive_report_exporter.py` and Streamlit-only `report_generator.py`) — Purpose: render the analysis payload into board-consumable artifacts. Dependencies: python-pptx, fpdf2 (unused in the live PDF path, which shells out to headless Chromium instead), Jinja-adjacent HTML templating. These three live exporters are the most duplicated code in the repository.

**Authentication & Security** (`local_auth.py`, `auth_routes.py`, `security_middleware.py`, `auth_session.py` [dormant]) — Purpose: local user management, JWT issuance/validation, RBAC, lockout, audit logging. Fully functional but architecturally isolated from the live data path (see SECURITY REVIEW).

**Tenant/Multi-Tenancy Scaffold** (`tenant_manager.py`, `tenant_isolation.py`, `enterprise_onboarding_pipeline.py`) — Purpose: an earlier, more ambitious multi-tenant SaaS design. Mostly dead code today — `tenant_manager.py` is live (used for a single "default" local tenant in the current single-machine design) but the broader tenant-isolation/onboarding machinery is reachable only from the unmounted `enterprise_routes.py` and tests.

**Persistence** (`local_database.py`, `historical_intelligence_engine.py`, `benchmark_engine.py`) — Purpose: SQLite-backed session storage, historical snapshotting/trend analysis, and sector benchmarking. All three are genuinely live and used by the main analysis flow (benchmarking via separate endpoints).

---

# IMPORTANT FILES

| File | Purpose | Why it matters |
|---|---|---|
| `backend/api/main.py` | FastAPI app factory; defines the original inline analysis endpoints | Entry point of the whole backend; also where the (currently unreachable-from-frontend) `ml_router.py` path lives, and where the confirmed Docker `CMD` bug originates (no module-level `app`) |
| `backend/api/local_analysis_routes.py` | The actual live analysis pipeline the product uses | Largest, most-imported-from file in `backend/api`; 14 of the app's most important endpoints live here |
| `backend/core/ml_router.py` | Multi-model ML training with SMOTE-in-folds and 3 governance-module integration | The more "advertised" ML implementation — but not the one actually reachable from the shipped UI |
| `backend/core/ml_validation_engine.py` | Simpler, actually-live ML training path | This is the real predictive engine behind the product's headline attrition-risk feature |
| `backend/core/theory_grounded_construct_engine.py` | Computes the 7 literature-cited psychological constructs | The platform's most scientifically distinctive, differentiating code |
| `backend/core/executive_pdf_exporter.py` | Largest `backend/core` file (2,509 lines); generates the "Board Report V3" PDF | Best single example of the report-duplication problem; also the file with the "Universal financial formula" comment |
| `frontend/app.py` | Streamlit alternate frontend, largest file in the repo (3,209 lines) | Fully independent reimplementation of pipeline orchestration; explains why two ML paths and two report-generation stacks both exist |
| `config/settings.py` | Single source of truth for platform constants | Every threshold, taxonomy, currency default, and forbidden-language rule referenced throughout the codebase originates here |
| `executive-ui/src/pages/DataUpload.tsx` | The true entry point of the live user flow | Where the two critical `fetch()` calls to the backend actually happen |
| `executive-ui/src/App.tsx` | Client-side page routing (hand-rolled, not react-router) | Determines which of the 16 pages are actually reachable — 3 pages are confirmed orphaned here |
| `Dockerfile` / `docker-compose.yml` | Container packaging and default deployment topology | Contains 2 confirmed bugs (broken `CMD`, broken healthcheck) and defines that Streamlit is off by default |
| `backend/api/enterprise_routes.py` | 18-endpoint aspirational multi-tenant SaaS API | Largest single block of dead-but-fully-implemented code in the repo; represents the "road not taken" architecturally |
| `backend/core/local_auth.py` | Complete bcrypt/JWT auth implementation | Well-built but disconnected — central to the Security Review's most severe finding |
| `pytest.ini` | Scopes pytest collection to `tests/` only | Explains why 7 real, substantive test files (root-level `test_*.py`) are invisible to CI-equivalent runs |
| `AUDIT_REPORT.md` (repo root) | Companion forensic audit produced in this same working session | The authoritative, file:line-cited source for every "live vs. dead" claim summarized in this document |

---

# API DOCUMENTATION

Six router files define the full HTTP surface: **57 endpoints total**. Only two files are wired into the live app — `backend/api/main.py`'s `create_app()` calls `app.include_router(auth_router)` and `app.include_router(create_local_analysis_router())` (main.py:107,110). `upload_routes.py`, `report_routes.py`, and `enterprise_routes.py` (25 of the 57 endpoints, 44%) define fully-implemented routers that **no code ever imports or mounts** — real, working handlers that are structurally unreachable in the running app.

## 1. `backend/api/main.py` — Core Analysis Pipeline (LIVE, mounted inline, no prefix router — routes defined directly in `create_app()`)

In-memory `_SESSIONS` dict (volatile, lost on restart). No auth on any route.

| Method | Path | Purpose | Auth | Key Output |
|---|---|---|---|---|
| GET | `/api/v1/status` | Health check | No | `status`, `platform`, `version` |
| POST | `/api/v1/upload` | Profile file, semantic-map columns, routing decision | No | `session_id`, `profile`, `routing`, `sem_map_coverage`, `target_col` |
| POST | `/api/v1/analyse` | Full adaptive pipeline (data healing → theory constructs → feature engineering → ML train/predict → risk scoring → insights); branches biosignal vs HR/survey | No | `model_metrics`, `best_auc`, `organisational_risk`, `departments[]`, `insights[]`, `executive_summary`, `actions_30/60/90d` |
| GET | `/api/v1/session/{sid}` | Retrieve stored analysis result | No | Full analysis dict |
| POST | `/api/v1/export/{sid}/csv` | Export per-employee predictions as CSV | No | CSV streaming download |

*Not called by the shipped React frontend at all (see AI System / Architecture sections) — reachable only via direct API calls or the disabled-by-default Streamlit app.*

## 2. `backend/api/auth_routes.py` — Authentication & User Admin (LIVE, prefix `/api/auth`)

JWT-based local auth backed by SQLite (`backend/core/local_auth.py`). 13 endpoints: `POST /login`, `POST /logout` (Bearer JWT), `POST /refresh`, `GET /me` (Bearer JWT), `POST /change-password` (Bearer JWT), `GET /users` (role SYSTEM_ADMIN/CHRO), `POST /users` (SYSTEM_ADMIN), `PATCH /users/{id}/role` (SYSTEM_ADMIN), `DELETE /users/{id}` (SYSTEM_ADMIN), `POST /users/{id}/reset-password` (SYSTEM_ADMIN), `POST /users/{username}/unlock` (SYSTEM_ADMIN), `GET /audit-log` (role AUDITOR/CHRO/SYSTEM_ADMIN), `POST /bootstrap` (no auth — first-boot admin creation, self-documented as "disable in production"). **Genuinely functional, but never called by the live executive-ui frontend** (zero references, confirmed by repo-wide grep).

## 3. `backend/api/local_analysis_routes.py` — Local Analysis, Sessions & Exports (LIVE, prefix `/api/local`, ~1660 lines, the real workhorse)

Fully offline, no auth, single-machine design. 14 endpoints. Persists results to SQLite (`local_database.py`), unlike main.py's volatile in-memory sessions.

| Method | Path | Purpose | Key Output |
|---|---|---|---|
| POST | `/upload/analyze` | Governance scan + classification only (fast path, 15s timeout, Saudi HR column auto-normalization first) | `readiness_level`, `dataset_type`, PII/leakage lists, `health_score`, `workforce_indicators[]`, `executive_recommendations[]` |
| POST | `/upload/analyze-with-employees` | **Full pipeline**: everything above + per-employee risk/stability scoring, dept summaries, narrative, forecast, ML validation, simulation, decision intelligence, executive indices/ROI/storytelling/readiness; auto-persists session | `employee_risk_table[]` (paginated), `department_summary[]`, `executive_indices`, `executive_roi`, `storytelling`, `simulation_result`, `decision_intelligence` |
| GET | `/sessions/latest` | Most recent saved session | Session dict or 404 |
| GET | `/sessions` | List saved sessions | `{sessions[], count}` |
| GET | `/sessions/{id}` | Full session detail | Session detail or 404 |
| DELETE | `/sessions/{id}` | Delete session (cascades) | `{deleted, session_id}` |
| POST | `/export-audit` | Log an export event | `{logged, export_id}` |
| GET | `/upload/export-employee-csv` | **Non-functional stub** — always returns 400, tells client to re-upload | 400 error |
| POST | `/export/slides` | Generate 11-slide printable HTML deck | `{html_content, slide_count}` |
| POST | `/export/pptx` | Generate real `.pptx` (python-pptx, 11 slides) | Binary download |
| POST | `/export/pdf` | Generate Board Report V3 as binary PDF via headless-Chromium subprocess, JSON/HTML fallback if unavailable | Binary PDF or JSON fallback |
| GET | `/benchmarks/sectors` | List sectors available for comparison (k≥5 contributors, DP noise) | `{sectors[]}` |
| POST | `/benchmarks/compare` | Compare org indices vs. sector benchmark | Gap-analysis dict |
| POST | `/benchmarks/submit` | Submit anonymised org data to improve benchmarks (k-anonymity enforced) | Engine result dict |

This is the ONLY router the shipped React frontend actually calls (`DataUpload.tsx` → `/upload/analyze` then `/upload/analyze-with-employees`).

## 4-6. Dead Routers (44% of the API surface, fully implemented but never mounted)

- **`upload_routes.py`** (prefix `/v1/tenants`, 3 endpoints) — "Phase 9" tenant-scoped governance scan precursor to `local_analysis_routes.py`. Structural-only tenant checks (comment admits "JWT pending").
- **`report_routes.py`** (prefix `/v1/tenants`, 4 endpoints) — "Phase 9" 4-type bilingual report generator + governance audit-package ZIP export, using hardcoded demo data merged with request data.
- **`enterprise_routes.py`** (prefix `/v1`, 18 endpoints) — "Phase 7" the most elaborate/aspirational router: full tenant lifecycle, dataset onboarding pipeline scaffold, analysis jobs, executive reports, audit/compliance/PDPL endpoints. Most handlers return placeholder/scaffold data (job status always `NOT_FOUND`, calibration always `NOT_EVALUATED`) rather than real computed results — designed API-first with backend wiring never completed. Only consumer anywhere in the repo is `tests/test_phase7_tenant_isolation.py`.

**Cross-cutting notes:** No endpoint in the entire codebase enforces true multi-tenant isolation at the HTTP layer. Two competing, unreconciled session models exist (`main.py`'s volatile in-memory dict vs. `local_analysis_routes.py`'s persistent SQLite store).

---

# DATABASE

**Database type:** SQLite only (no PostgreSQL/MySQL despite `.env.example` referencing an optional Postgres config that's never implemented). Raw `sqlite3` standard-library module throughout — **no ORM**. WAL mode enabled on every connection. Hand-written `CREATE TABLE IF NOT EXISTS` statements per module. **7 physical `.db`/`.sqlite` files**, owned by 6 distinct schema modules.

## 1. `data/awi_auth.db` — Local Authentication (source: `local_auth.py`)
5 tables, all empty (0 rows — never used): `awi_local_users` (PK `user_id`, bcrypt `password_hash`, `must_change_pw` flag), `awi_login_attempts`, `awi_account_locks`, `awi_active_tokens` (JWT jti tracking for revocation), `awi_security_audit`. Indexed on username/attempted_at, user_id/revoked, event_type/occurred_at.

**Notable finding:** a *second*, unrelated schema (`awi_users`, `awi_sessions`, `awi_auth_audit`) is defined in `backend/core/auth_session.py` pointing at the **same file**, but none of those three tables actually exist on disk — this is dormant/scaffold "Phase 30D" code that has never been invoked in this deployment, coexisting unused alongside the real, active `local_auth.py` system.

## 2. `data/local_intelligence.db` — Analysis Session Persistence (source: `local_database.py`)
The most actively-used database (2.1 MB, 4 real session rows). 5 tables: `analysis_sessions` (PK `id`), `analysis_results`, `ml_validation_results`, `governance_audit` (all 3 with real `FOREIGN KEY → analysis_sessions.id ON DELETE CASCADE`, enforced via `PRAGMA foreign_keys=ON`), `export_audit` (nullable, unenforced session link). No PII ever stored — a `_scrub_pii` blocklist is enforced at write time; nested data stored as JSON TEXT columns.

## 3. `awi_tenants.db` — Tenant Registry (source: `tenant_manager.py`, "Phase 30C")
3 tables: `tenants` (PK `tenant_id`, org name, subscription tier, country, deployment mode), `tenant_sessions`, `tenant_audit_log`. All empty in every copy. **Bug: the class defaults to a bare relative filename** (`"awi_tenants.db"`) instead of a repo-root-anchored path, so the file gets created in whatever directory the process's CWD happens to be — confirmed **two physical copies exist** (repo root and `backend/`), both empty but structurally divergent by location.

## 4. `awi_history.db` — Workforce Snapshots (source: `historical_intelligence_engine.py`, "Phase 30E")
1 table, `workforce_snapshots` (period, stability index, ML metrics, top risk drivers as JSON, soft cross-database references to `local_intelligence.db` and `awi_tenants.db` — unenforceable, SQLite can't FK across files). **Same relative-path bug as #3** — two copies exist (7 rows at repo root, 3 rows under `backend/`), and this time the row *counts differ*, confirming genuinely separate write histories, not just duplicate empty shells.

## 5. `data/awi_benchmarks.sqlite` — Sector Benchmarking (source: `benchmark_engine.py`, "Phase 29F")
2 tables: `sector_benchmarks` (k-anonymity ≥5, differential-privacy noise ε=0.5, pre-seeded with 8 synthetic Saudi-sector rows), `benchmark_contributions` (SHA-256 one-way org hash, DP-noised metrics JSON). Correctly path-anchored (no duplicate-file bug). 3 live contributions recorded.

## 6. `telemetry.db` — Optional Event Telemetry (source: `telemetry_engine.py`)
Defined but **opt-in and never actually enabled** in this deployment — no `telemetry.db` file exists anywhere on disk. Normally events live purely in an in-memory list, exportable as JSON.

**Relationships:** Real, enforced foreign keys exist only within `local_intelligence.db` (CASCADE delete from `analysis_sessions`). `awi_tenants.db`'s `tenant_sessions → tenants` FK is declared but not enforced (PRAGMA foreign_keys not explicitly set on those connections). Every other relationship — including all cross-database links between `awi_history.db`, `awi_tenants.db`, and `local_intelligence.db` — is a convention-only soft reference with no DB-level enforcement.

**Views / Triggers:** None found anywhere in the codebase.

**ORM Models:** None — this project does not use SQLAlchemy, Django ORM, Peewee, or any ORM. All access is raw parameterized SQL via `sqlite3`.

**Migration status:** No formal migration system exists (no Alembic, no `migrations/` folder, no migration runner — confirmed by full-repo search). Schema evolution happens by directly editing each module's `CREATE TABLE IF NOT EXISTS` string, which means existing columns can never be altered on a database that already has the table — only new tables/databases get the new shape. On-disk schemas currently match their owning code byte-for-byte (no column-level drift observed), but the relative-path bugs in `tenant_manager.py` and `historical_intelligence_engine.py` mean **which physical file** gets written to is nondeterministic across process launches.

---

# AI SYSTEM

**Overall characterization: a classical ML + deterministic rule-engine hybrid — NOT an LLM-based product.** A repo-wide dependency and code-string audit (grep for `openai|anthropic|langchain|chromadb|pinecone|faiss|embedding|vector_db`) found **zero LLM SDK, embedding library, or vector-database usage anywhere**. The one relevant hit is `tests/test_phase10_real_saudi_datasets.py:309-321`, a governance test proving `offline_mode_guard.py` actively **blocks** any outbound call to `api.openai.com` by patching `socket.getaddrinfo`, raising `OfflinePolicyViolation` — the platform doesn't just omit LLM calls, it runtime-enforces their absence. `requirements.txt` lists zero LLM/embedding/vector-DB packages.

**1. Dataset Profiler (`dataset_profiler.py`).** Statistical profiling per column: dtype inference (numeric/categorical/datetime/text/binary/id — object columns classified "text" if avg string length >60), missing rate, cardinality, mean/std/skew/kurtosis, IQR-based outlier counts. Quality score starts at 100, subtracts up to 30 points for insufficient rows (<50), up to 15 for duplicate rows, 1-3 per problematic column, clipped to [0,100]. Dataset-type inference scores 13 candidate types by column-name keyword overlap.

**2. Semantic Mapper (`semantic_mapper.py`).** Four-stage cascade per column: (1) exact alias match → confidence 1.00; (2) keyword-substring scoring → up to 0.85; (3) `rapidfuzz.fuzz.token_set_ratio` fuzzy match, accepted only if ratio ≥0.70; (4) value-distribution heuristics (binary attrition-named columns → "target"; 1-7 integer range → "psychological_score"; large positive floats → "salary"). Falls to "unknown" below confidence 0.30.

**3. Adaptive Router (`adaptive_router.py`).** Four-stage dataset-type classifier: filename hard rules (files literally named `hr.csv`/`bvp.csv` force biosignal routing at 0.99 confidence), weighted column-keyword scoring with word-boundary regex (avoids false positives like "month" matching inside "monthlyincome"), value heuristics (a single long, high-uniqueness numeric column signals biosignal), and conflict resolution where biosignal routing wins whenever its score is at least half the HR score — a documented "critical invariant" ensuring wearable data never gets accidentally treated as HR data. A Phase-3 overlay can hard-override routing if an independent modality classifier detects biosignal at ≥80% confidence.

**4. Data Healer (`data_healer.py`).** Deterministic 9-step cleaning pipeline, fully replayable on new data for train/inference consistency: drop junk columns → parse timestamps → encode target → coerce currency-stripped numerics → median/mode imputation → IQR×3 outlier capping → log1p transform for skewed features → ordinal/one-hot/label categorical encoding → RobustScaler/StandardScaler. Every step is logged to an audit-trail report object.

**5. Feature Factory (`feature_factory.py`).** Five feature layers gated by the `SCIENTIFIC_FEATURE_MODE` flag (default `"theory_grounded"`). Layer A (universal ratios) and Layer D (tenure/career-progression features) always run. **Layer B and Layer C — the 15 constructs listed in `config/settings.py`'s `LEGACY_DISABLED_CONSTRUCTS`** (BurnoutRiskComposite, SatisfactionIndex, RetentionRisk, etc.) — are disabled by default and only execute under an explicit debug-only mode; they remain present in the codebase as dead branches, stripped from output by a defense-in-depth cleanup pass even if accidentally triggered. **Gap found:** Layer E ("organizational stress" composites — WorkloadPerHeadcount, CompensationEfficiencyGap, ManagerialStrainIndex) is NOT gated by the same flag and runs unconditionally for HR datasets even in the "safe" theory_grounded mode — these are invented, non-paper-anchored ratios that escaped the legacy quarantine.

**6. Theory-Grounded Construct Engine (`theory_aware_column_mapper.py` + `theory_grounded_construct_engine.py`) — the platform's signature differentiator.** Citing a named 2026 paper on theory-grounded hybrid attrition prediction. Phase 1 maintains a registry of **27** construct definitions (not the 25 referenced in some doc comments) across 9 organizational-psychology categories (Job Demands, Job Resources, Satisfaction/Hygiene, Engagement, Equity/Fairness, Commitment, Retention/Withdrawal, Structural HR Baseline, and a hard-blocked Target-Adjacent-Leakage category). Each construct has direct-evidence column names plus Saudi English/Arabic synonym lists. Phase 2 computes 7 composite constructs from validated inputs (requiring ≥0.70 semantic AND scale confidence per input, or the construct is skipped entirely — never approximated), with real, literature-cited formulas found in the code: `SatisfactionIndex = mean(4 satisfaction dimensions)`; `BurnoutRisk = OverTime_binary × (5 − WorkLifeBalance)` (multiplicative JD-R gate — zero overtime forces zero risk, by design); `EngagementScore = JobInvolvement × JobSatisfaction` (Kahn 1990's simultaneity requirement); `TenureRatio`, `IncomePerLevel` (Adams' Equity Theory), `CareerProgression`, `SalaryGrowth` (Siegrist's Effort-Reward Imbalance). This is a genuinely well-evidenced, academically-grounded feature-engineering layer distinguishing this from a generic AutoML attrition tool.

**7. Risk Intelligence (`risk_intelligence.py`).** `financial_exposure = salary × 0.50 × attrition_probability`. Risk labels: critical ≥0.75, high ≥0.55, moderate ≥0.35, else low. Department scoring returns an **empty list** (not a fabricated bucket) if no department column is detected — a deliberate honesty choice. Organization sustainability score is a weighted blend of risk/burnout/engagement; early-warning level (Critical/Elevated/Watchlist/Stable) is threshold-driven off org risk and high-risk percentage.

**8. Insight Generator (`insight_generator.py`).** Explicitly documented in its own file header: "No LLM dependency — pure rule-based and threshold-driven generation." Every "insight" and "executive summary" sentence is an f-string template selected by numeric threshold (e.g. risk≥65% → "Critical Organisational Attrition Signal" template) with live numbers substituted in — confirmed zero API calls, zero prompt construction anywhere in this file.

**9. Employee Risk Scoring & Explainability (`employee_risk_scoring.py`, `employee_explainability_engine.py`).** PII is regex-stripped bilingually before any scoring occurs. ~20 named constructs are regex-matched to compute per-employee risk (bands: Stable 0-30, Monitoring 30-55, Strategic Concern 55-75, Priority Review 75-100). Explainability is **template-based, not SHAP** in the live path — per-employee driver sentences are generated by substituting values into fixed templates, explicitly documented "No random values. No fake drivers... Fully offline." **A separate module, `explainability_engine.py`, does implement real SHAP** (TreeExplainer with graceful fallback) — but it is only imported by the Streamlit frontend, and `shap` isn't even declared in `requirements.txt`. SHAP is not part of the live FastAPI/React path.

**10. Biosignal Adapter (`biosignal_adapter.py`).** Handles 10 wearable signal types (HR/EDA/BVP/TEMP/ACC/IBI/ECG/EEG/EMG/PPG) via sliding-window statistical feature extraction — mean/std/skew/kurtosis/slope/peak-count plus signal-specific stress proxies (e.g. HR stress = clip((mean−60)/50, 0, 1); EDA stress = weighted spike-activation + sympathetic-arousal proxy). **No ML model is trained here** — pure numpy/scipy signal processing, despite `config/settings.py` listing aspirational deep-learning model names (cnn_lstm, transformer) that are never actually implemented. Every output carries a fixed non-clinical disclaimer.

**11. Calibration & Confidence Governance (`calibration_engine.py`, `confidence_governance.py`).** Real statistical calibration: Brier score, 10-bin population-weighted Expected Calibration Error, quality tiers (Good/Moderate/Poor) by fixed thresholds. `ConfidenceGovernor` produces a 5-dimension confidence report with explicit cross-dimension caps (e.g. any CRITICAL leakage flag caps model reliability at ≤0.40 regardless of other scores) — a genuinely thoughtful governance design, though (per the AUDIT_REPORT.md companion doc) not the live path's primary consumer of leakage detection.

**AI System bottom line:** this is an enterprise classical-ML decision-support system with a rule-based/statistical expert-system layer on top — scientifically grounded (the theory-construct engine cites real organizational-psychology literature with exact formulas), fully deterministic and reproducible, explicitly engineered to avoid both LLM dependency and the platform's own earlier "invented" (non-paper-anchored) metrics. The predictive core is XGBoost/LightGBM/CatBoost/LR/RF/GB (see companion `AUDIT_REPORT.md` §2 for which of these two competing training modules is actually reachable from the live product).

---

# BUSINESS LOGIC

Twelve `backend/core/` modules make up the "executive intelligence" layer sitting on top of raw risk scores. Live-chain status verified against `local_analysis_routes.py`'s `/upload/analyze-with-employees` handler.

**1. `executive_index_engine.py` — Six board-level indices (LIVE).** Computes WSI (Workforce Stability), RHI (Retention Health), TFRI (Talent Flight Risk, lower=better), LSI (Leadership Stability), ORI (Organizational Resilience), and HCRI (Human Capital Risk, composite of the other five) — all 0-100, each a weighted linear blend of risk-band ratios, department-risk Gini coefficient, construct coverage, and ML AUC bonus. Example: `WSI = 0.40·stable_ratio + 0.35·(100−avg_risk) + 0.15·construct_coverage + 0.10·ml_bonus`. Letter grades A(≥80) through F(<50), inverted for TFRI/HCRI. Zero records → hardcoded all-F fallback.

**2. `executive_roi_engine.py` — 9-component Cascio-Boudreau cost model (LIVE, NOT the source of the 120K/35%/28% formula).** Separation, replacement, recruitment, lost productivity, onboarding, training, vacancy, manager time, knowledge loss — each component = department-inferred monthly salary (SAR 6,500-18,000 base × 1.0-4.5× seniority multiplier, both guessed from department-name keywords, no real salary/seniority columns used) × a cost-matrix multiplier by component and tier. Adds Nitaqat compliance premium (18-35%) and Saudi End-of-Service Gratuity per Labour Law Art. 84. Three ROI scenarios assume 20-55% retention effectiveness (cited to Hom et al. 2017). **This module never produces or references the "120,000 SAR / 35% recovery / 28% retained" figure used by the three report exporters** (§3 of the audit) — that flat formula lives only in `executive_pdf_exporter.py`/`pptx`/`slide` exporters, sourced to "SHRM Human Capital Benchmarking," a completely separate and much simpler assumption set that bypasses this more sophisticated engine entirely.

**3. `executive_readiness_engine.py` — Platform/commercial readiness self-score (LIVE).** Not an HR metric — scores the *product itself* across 5 dimensions (Executive, Product, Enterprise, Commercial, Investment readiness) for sales/investor purposes, using a mix of pipeline-output presence checks and hardcoded marketing evidence text (e.g. "Offline Architecture" is a fixed 100.0 score). Overall = weighted average, letter-graded A-F. This is effectively a baked-in marketing scorecard riding inside the analysis pipeline's output.

**4. `executive_storytelling_engine.py` — Board narrative generation (LIVE).** Four audience-specific narratives (CEO/CHRO/Board/Government), purely threshold-based template selection — WSI maps to 5 stability labels, at-risk% maps to 5 risk labels via fixed cutoffs, sentence fragments interpolated with live numbers. The `board_narrative` object (consumed by all three live report exporters) leads with a WSI/HCRI headline, cites the ROI exposure range, and closes with 3 fixed board-resolution action items.

**5. `executive_narrative_engine.py` — Org-level narrative (LIVE).** Department highlights (top-3 by risk), protective strengths and emerging risks pulled from the driver-summary data (generic fallback text if none detected), overall risk level bucketed at 4 fixed thresholds, HR priorities conditionally appended based on band counts.

**6. `executive_decision_intelligence.py` — Strategic priorities & decision readiness (LIVE).** Executive Priority Score starts at avg_risk_score, adds penalties for high Priority-Review%/governance-warning count, discounted if ML AUC<0.60. Decision Readiness Level: "high" only if AUC≥0.65 AND simulation available. Strategic priorities come from the top-4 simulation scenarios by estimated risk reduction (if available) or top-4 risk drivers otherwise, each urgency-tagged.

**7. `workforce_forecasting_engine.py` — Single-snapshot scenario projection, explicitly NOT time-series forecasting (LIVE).** The module's own docstring states confidence is always low because there's no historical data — it projects Moderate/Significant drift scenarios as a linear function of the *current* risk-score standard deviation, not a regression over time. 30/60/90-day horizons. Output is explicitly labeled "Statistical Projection — Not a Prediction" per its governance note.

**8. `workforce_simulation_engine.py` — 8-lever "what-if" intervention planner (LIVE).** Fixed intervention list (internal mobility, training access, promotion fairness, job stability, work-life balance, engagement, compensation, overtime reduction). Impact = ML feature importance for matching keywords × a fixed scale constant (32.0), capped per-lever at 7-10 percentage points, combined-strategy cap 22pp. **Uses a THIRD independent financial constant** — a flat SAR 18,000-per-departure floor — distinct from both the ROI engine's 9-component model and the exporters' SAR 120,000 figure. Recommended strategy = top-3 scenarios by confidence-weighted impact, combined with diminishing-returns weights.

**9. `hr_recommendation_engine.py` — Per-employee/per-department HR actions (LIVE, reached via `employee_risk_scoring.py`).** Explicitly never recommends firing/replacing. Urgency from risk band; category chosen from the highest-contribution risk driver via a fixed 21-construct → 9-category map. Each category × urgency combination has a canned bilingual action/rationale/timeframe pulled from a ~240-line static template dictionary — this is templated text generation, not a generative model.

**10. `roi_estimation_engine.py` — earlier, simpler ROI engine (DEAD/test-only).** Confirmed the only reference anywhere in the repo is `tests/test_phase6_enterprise_deployment.py`. Real formula content nonetheless: flat SAR 8,000/month base salary, 1.5-4.0× multiplier by seniority tier, 25-50% intervention effectiveness. A fourth, independent financial-assumption set that was apparently superseded by `executive_roi_engine.py` but never deleted.

**11. `benchmark_engine.py` — Sector benchmark comparison (LIVE, but only via the separate `/benchmarks/*` endpoints, NOT part of the main analysis pipeline).** SQLite-backed, seeded with 8 static records across Saudi sectors (banking, oil & gas, telecom, government, retail/FMCG, healthcare) — explicitly disclosed in the code as "seeded estimates" from public reports, not real client contributions. Applies differential-privacy Gaussian noise (ε=0.5) to every returned value; enforces k≥5 anonymity before publishing a contributed benchmark row.

**12. `historical_intelligence_engine.py` — Snapshot history & trend detection (LIVE — this module is called inside `/upload/analyze-with-employees` too, via `create_snapshot_from_analysis`, though it's easy to miss since it's not one of the more obviously-named "executive_*" modules).** Append-only aggregate snapshots per period; trend classification (improving/declining/stable, ±3.0-point threshold) requires ≥2 snapshots; forecast is a naive linear extrapolation from the last 3 snapshots, confidence tied to snapshot count (<6 low, <12 medium, ≥12 high).

**Business-logic-wide observation:** at least **four different, independently-maintained financial-exposure formulas** coexist in this codebase (the 3 live report exporters' flat SAR 120,000/35%/28%; `executive_roi_engine.py`'s 9-component Cascio-Boudreau model; `workforce_simulation_engine.py`'s flat SAR 18,000/departure; and the dead `roi_estimation_engine.py`'s flat SAR 8,000/month model) with no single canonical source — a materially more severe version of the duplication problem already documented for report generation and PII detection.

---

# IMPORTANT CLASSES

| Class | File | Purpose | Main Methods |
|---|---|---|---|
| `SecureFileIngestion` | `secure_file_ingestion.py` | Governance scan on upload (PII/leakage/quality) | `scan()` |
| `DatasetTypeClassifier` | `dataset_type_classifier.py` | Classifies dataset into 4 dashboard modes | `classify()` |
| `DatasetProfiler` | `dataset_profiler.py` | Statistical profiling of an uploaded dataframe | `profile()`, `profile_to_dict()` |
| `SemanticMapper` | `semantic_mapper.py` | 4-stage column → semantic-category mapping | `map()` |
| `AdaptiveRouter` | `adaptive_router.py` | 4-stage dataset-type/modality routing | `route()` |
| `DataHealer` | `data_healer.py` | 9-step deterministic cleaning, replayable | `fit_transform()`, `transform_new()` |
| `FeatureFactory` | `feature_factory.py` | Layered feature engineering | `engineer()` |
| `TheoryAwareColumnMapper` | `theory_aware_column_mapper.py` | Maps columns to 27 psychology constructs | `map()` |
| `MLRouter` | `ml_router.py` | Multi-strategy ML training/orchestration (non-live path) | `train()`, `predict_proba()` |
| `EmployeeRiskScorer` | `employee_risk_scoring.py` | Per-employee/department risk + stability scoring | `score_dataframe()` |
| `LocalAuthManager` | `local_auth.py` | Full local user/auth lifecycle | `login()`, `create_user()`, `bootstrap_admin()`, `change_password()` |
| `TenantManager` | `tenant_manager.py` | Tenant registry CRUD | `provision_default_tenant()`, tenant lookup methods |
| `HistoricalIntelligenceEngine` | `historical_intelligence_engine.py` | Append-only snapshot store + trend analysis | `create_snapshot_from_analysis()`, `analyze_trends()` |
| `CalibrationEngine` | `calibration_engine.py` | Brier score / ECE model calibration evaluation | `evaluate()` |
| `ConfidenceGovernor` | `confidence_governance.py` | Cross-dimension confidence-score capping | `build()` |
| `BiosignalAdapter` | `biosignal_adapter.py` | Wearable-signal windowed feature extraction | `analyse()` |
| `LeakageDetector` | `leakage_detector.py` | Statistical leakage/proxy detection (non-live-path only) | `detect()` |
| `ModelValidator` | `model_validator.py` | Model-quality validation (non-live-path only) | `validate()` |
| `ExecutivePDFExporter` | `executive_pdf_exporter.py` | Board Report V3 PDF generation | `generate()` |

---

# IMPORTANT FUNCTIONS

| Function | Purpose | Input | Output | File |
|---|---|---|---|---|
| `create_app()` | Builds and configures the FastAPI application | — | `FastAPI` app instance | `backend/api/main.py` |
| `create_local_analysis_router()` | Builds the live `/api/local/*` router with all its endpoint closures | — | `APIRouter` | `backend/api/local_analysis_routes.py` |
| `run_ml_validation(df)` | The actual live-path ML training/evaluation entry point | pandas DataFrame | Structured dict: models, metrics, best model, governance warnings | `backend/core/ml_validation_engine.py` |
| `score_individuals(df, probs, sem_map)` | Per-employee risk scoring | dataframe, model probabilities, semantic map | List of individual risk records incl. financial exposure | `backend/core/risk_intelligence.py` |
| `score_departments(...)` | Department-level aggregation | individual risk records | List of department risk summaries (or empty list if no dept column) | `backend/core/risk_intelligence.py` |
| `score_organization(...)` | Org-wide risk rollup | department risk summaries | `OrganizationalRisk` object (sustainability score, early-warning level) | `backend/core/risk_intelligence.py` |
| `compute_constructs(df, column_mappings)` | Computes the 7 theory-grounded psychological constructs | dataframe + column mapping | Enriched dataframe + activation report | `backend/core/theory_grounded_construct_engine.py` |
| `generate_org_narrative(...)` | Produces department-highlight/protective/emerging-risk narrative text | scored-result aggregates | `OrgNarrative` object (bilingual) | `backend/core/executive_narrative_engine.py` |
| `compute_executive_indices(...)` | Computes the 6 board-level indices (WSI/RHI/TFRI/LSI/ORI/HCRI) | scored-result aggregates | Index scores + letter grades + drivers | `backend/core/executive_index_engine.py` |
| `compute_executive_roi(...)` | 9-component Cascio-Boudreau financial exposure model | scored-result aggregates, tenure | ROI scenarios (Conservative/Targeted/Comprehensive) | `backend/core/executive_roi_engine.py` |
| `run_workforce_simulation(...)` | 8-lever what-if intervention scenario generation | scored-result aggregates + ML validation output | Scenario list + recommended combined strategy | `backend/core/workforce_simulation_engine.py` |
| `run_executive_decision_intelligence(...)` | Strategic-priority synthesis from all upstream engine outputs | ML validation + simulation + forecast + driver data | Priority score, readiness level, strategic priorities, decision questions | `backend/core/executive_decision_intelligence.py` |
| `generate_slide_deck(data, company_name)` | Renders the printable HTML board deck | analysis-result payload | HTML string | `backend/core/executive_slide_exporter.py` |
| `generate_pptx(data, company_name)` | Renders the binary PPTX board deck | analysis-result payload | bytes | `backend/core/executive_pptx_exporter.py` |
| `bootstrap_admin(initial_password)` | First-boot admin account creation | password string | `LocalUser` | `backend/core/local_auth.py` |
| `login(username, password, ...)` | Authenticate and issue JWT pair | credentials | `LoginResult` (tokens, must_change_pw flag) | `backend/core/local_auth.py` |

---

# CONFIGURATION

**`config/settings.py`** — the single authoritative source for platform constants: dataset-type taxonomy, semantic column categories, ML task types/model registry, risk-level thresholds (critical≥0.75/high≥0.55/moderate≥0.35), currency defaults (SAR base, exchange-rate table), the forbidden-executive-language list, scientific-validity thresholds (AUC suspicion cutoffs, proxy-leakage keywords), data-quality thresholds (missing/cardinality/outlier), semantic-matching confidence cutoffs, time-series parameters, and API/Streamlit port constants. A second file, `config/production_settings.py`, exists in parallel with its own hardcoded `ENVIRONMENT="production"` and artifact/audit/model store paths — but **nothing in the codebase ever imports or switches to it based on an env var**; it's only consumed by one module (`audit_package_builder.py`) for a governance-lock snapshot, not as an active runtime config.

**`package.json`** (executive-ui) — 3 scripts (`dev`, `build`, `preview`), 6 runtime deps (React 18, react-router-dom [unused], framer-motion, lucide-react, recharts), 10 devDeps (TypeScript, Vite, Tailwind, Playwright, PostCSS/Autoprefixer).

**`requirements.txt`** — ~24 pinned-minimum packages across ML (numpy/pandas/scipy/scikit-learn/imbalanced-learn/xgboost/lightgbm/catboost/optuna), NLP (rapidfuzz), time-series (prophet/statsmodels), API (fastapi/uvicorn/python-multipart), the Streamlit frontend (streamlit/plotly/jinja2), file I/O (openpyxl/pyarrow), reporting (fpdf2), and security (passlib[bcrypt]/python-jose[cryptography]/cryptography). Notably `pytest` itself is not listed (see AUDIT_REPORT.md §8).

**Docker / Docker Compose** — `Dockerfile` builds a `python:3.11-slim` image, non-root user, installs `requirements.txt`, exposes port 8000, and its `CMD` (`uvicorn backend.api.main:app ...`) is confirmed broken (no module-level `app` object exists — see Known Issues). `docker-compose.yml` runs only the API service by default; a Streamlit service block exists but is fully commented out, and its port mapping (`8501`) doesn't match the Streamlit app's own documented port (`8510`) — a second, independent confirmation of the port mismatch found in Environment Variables below.

**Config files loading order:** there is no `.env` loader (no `python-dotenv` import found) — environment variables must be set in the actual process environment (shell, Docker Compose `environment:` block, or CI), not picked up automatically from a `.env` file at runtime. `.env.example` is a template for manual copying, not an auto-loaded file.

---

# ENVIRONMENT VARIABLES

Full-codebase grep found **only 9 environment variables actually read by application code** — the remainder of `.env.example`'s entries (JWT_SECRET_KEY, POSTGRES_*, REDIS_URL, SAUDI_COMPLIANCE_MODE, PDPL_WARNING_ENABLED) are aspirational/documentation-only and have no corresponding `os.environ.get(...)` call anywhere in the repo. **No frontend TypeScript file references `import.meta.env` or `process.env` at all** — executive-ui has zero build-time or runtime env-var dependencies; it talks to the backend purely via relative paths proxied by Vite.

| Variable | Default | Read in | Purpose |
|---|---|---|---|
| `AWI_AUTH_ENFORCED` | `"true"` (anything but literal `"false"` keeps auth on) | `security_middleware.py:24` | Master auth toggle. When `false`, `get_current_user()` skips JWT validation entirely and returns a synthetic `SYSTEM_ADMIN` user for every request — dev/test only, dangerous if left off in production. |
| `AWI_CORS_ORIGINS` | `""` → hardcoded fallback list (localhost:3000/8501, 127.0.0.1:3000/8501) | `main.py:92` | Comma-separated CORS allow-list. **The default list does not include Vite's actual dev port 5173** — generally masked because Vite proxies API calls server-side, so the browser never makes a genuinely cross-origin request in the default dev flow. |
| `AWI_ADMIN_BOOTSTRAP_PASSWORD` | `""` (empty → no auto-bootstrap) | `main.py:116` | If set, auto-creates the first SYSTEM_ADMIN account at server startup. |
| `AWI_AUTH_DB` | `""` → module default sqlite path | `local_auth.py:152` | Overrides the auth SQLite file path — used by the test suite to isolate test runs. |
| `AWI_DATA_DIR` | `"data/enterprise"` | `local_enterprise_runtime.py:45` | Base directory for per-tenant enterprise runtime storage (reports/exports/audit_logs/cache/uploads subdirs). |
| `LOG_LEVEL` | `"INFO"` | `config/settings.py:317` | Logging verbosity — but note `config/production_settings.py` hardcodes `"INFO"` and ignores this env var entirely, an inconsistency between the two settings modules. |
| `ARTIFACT_STORE_PATH` | `BASE_DIR/data/artifacts` | `config/production_settings.py:115` | Report/export artifact storage path override (production profile only, which is never actually activated — see Configuration). |
| `AUDIT_LOG_PATH` | `BASE_DIR/data/audit_logs` | `config/production_settings.py:116` | Audit log storage path override (same caveat). |
| `MODEL_STORE_PATH` | `BASE_DIR/saved_models` | `config/production_settings.py:117` | Trained-model artifact storage path override (same caveat). |

**Additional findings:** `ENVIRONMENT`, `API_HOST`, and `API_PORT` are listed in `.env.example` but **never actually read from the environment anywhere** — `API_HOST`/`API_PORT` are hardcoded Python constants in `config/settings.py` consumed directly by `uvicorn.run()`, so setting them in `.env` has zero effect. No secrets (JWT keys, DB passwords, API keys) are read from the environment anywhere — the auth system is entirely local-SQLite-based. `offline_mode_guard.py` (which patches `socket.getaddrinfo` to block all non-loopback network calls, enforcing the "fully offline" design claim) has no env-var toggle at all — it's installed unconditionally wherever called. `fail_safe_guardrails.py`'s rule thresholds are hardcoded, not env-configurable.

**Additional config files:** `executive-ui/tailwind.config.js` extends the default Tailwind theme with a `brand` blue scale, a semantic `risk` palette (stable/monitor/concern/priority), Inter + Cairo (Arabic) font families, and custom fade/slide/pulse animations — no plugins registered. `postcss.config.js` is minimal (just tailwindcss + autoprefixer). `.vscode/settings.json` hardcodes a local absolute Python interpreter path and pytest args — developer-machine-specific, not portable.

---

# SECURITY REVIEW

*(See `AUDIT_REPORT.md` §7 in the repo root for the full forensic trace with file:line citations — this section is a compressed summary for cross-project review.)*

**Authentication:** A genuinely well-built local auth system exists (`local_auth.py`/`auth_routes.py`): bcrypt password hashing (cost 12), JWT access/refresh tokens (HS256), account lockout (5 attempts/15 min), password-strength policy, full security audit log. **But it is completely disconnected from the live product** — the shipped React frontend never calls `/api/auth/login` (zero references anywhere in `executive-ui/src`), and the actual data-analysis endpoints (`local_analysis_routes.py`, self-documented as "no-auth, no-tenant") have zero authentication checks regardless of the `AWI_AUTH_ENFORCED` flag's state. A dormant second auth-schema scaffold (`auth_session.py`) coexists unused in the same database file.

**Authorization:** RBAC exists (`AWIRole` enum, `require_role`/`require_permission` decorators) but only protects the `/api/auth/*` admin endpoints — never applied to any data-bearing route.

**Input Validation:** Pydantic models validate most POST bodies in `auth_routes.py`. File uploads are size-capped (500MB) and format-restricted. The `/api/auth/bootstrap` endpoint takes `initial_password` as a bare, unvalidated-by-Pydantic parameter (though `validate_password_strength()` is called explicitly inside the handler).

**SQL Injection:** No ORM; all SQL is raw `sqlite3` with parameterized `?` placeholders throughout every module reviewed — no string-formatted SQL queries were found. Low risk on this specific vector.

**XSS:** The React frontend uses standard JSX escaping (no widespread `dangerouslySetInnerHTML` usage identified in the modules reviewed). Report exporters generate HTML server-side from structured data, not raw user text, reducing (but not eliminating, since department/dataset names come from user-uploaded file content) injection surface into generated reports.

**CSRF:** No CSRF token mechanism found — mitigated somewhat by the JWT-bearer-token auth model (no ambient cookie-based session to forge against) for the one router that does use auth, but irrelevant to the unauthenticated data routes since there's no session state to protect there either.

**Secrets:** JWT signing secret is generated on first run and persisted to `data/awi_secret.key` (256-bit, `secrets.token_hex(32)`) — not hardcoded, reasonable approach for a local/offline deployment. No API keys or cloud credentials exist anywhere in the codebase (no LLM API calls, no cloud SDKs).

**Rate Limiting:** None found on any endpoint (login lockout is the only throttling mechanism, and it's username-scoped, not IP-scoped).

**Encryption:** Passwords bcrypt-hashed at rest. No field-level encryption of employee data in the SQLite databases (mitigated in principle by the "no PII ever stored" design rule in `local_database.py`, enforced via a scrub-list rather than encryption).

**JWT:** HS256, 8-hour access token TTL, 30-day refresh token TTL, revocation tracked via a `jti` table (real, working design) — but only exercised by a router the live frontend never calls.

**Cookies/Sessions:** No cookie-based sessions — pure bearer-token JWT design (again, for the one router that uses it).

**CORS:** Configurable via `AWI_CORS_ORIGINS`, defaults to a localhost-only allow-list that (notably) omits the actual Vite dev port.

**File Upload Security:** `SecureFileIngestion` performs PII/leakage column detection, has a 500MB hard cap and a 15-second processing timeout on the primary upload endpoint, and never persists raw uploaded bytes to disk in the local-analysis path (in-memory scan only, per its own design-rules docstring).

**Bottom line:** the individual security *components* (hashing, JWT, lockout, parameterized SQL, secret generation) are competently implemented in isolation. The system-level failure is integration: the product a user actually opens has none of these protections active on any endpoint that touches data.

---

# PERFORMANCE REVIEW

**Slow APIs:** `/api/local/upload/analyze-with-employees` is the heaviest endpoint — it chains governance scan, classification, per-employee risk scoring, narrative generation, forecasting, ML validation (5-fold CV × 3 models), simulation, decision intelligence, 4 executive-index/ROI/storytelling/readiness engines, and a snapshot write, all in one request. Each ML-adjacent sub-step is individually wrapped in try/except-with-non-fatal-fallback and run via `asyncio.to_thread` (so it doesn't block the event loop), but the end-to-end latency for a large file is necessarily high — there's no background job queue (`REDIS_URL` is mentioned in `.env.example` but never implemented) so the client's HTTP request stays open for the full duration.

**Heavy Queries:** No complex joins anywhere (schema is intentionally flat, mostly single-table lookups by primary key or simple WHERE filters) — SQLite query performance is not a likely bottleneck given the data volumes involved (single-digit session counts observed in practice).

**Memory Usage:** File ingestion loads the entire uploaded file into memory (`await file.read()`) with no streaming/chunking — combined with the 500MB upload cap, a large file could cause significant memory pressure, especially since the same bytes get re-parsed multiple times across the governance scan, classification, and employee-scoring steps rather than reusing one parsed DataFrame throughout.

**Caching:** No caching layer identified anywhere (no Redis, no in-process LRU caching of expensive computations like the benchmark DP-noise calculations or ML training).

**Concurrency:** FastAPI/Uvicorn's async model is used correctly for I/O (file read is `await`ed, CPU-bound work is offloaded via `asyncio.to_thread`), but the Dockerfile runs a single worker (`--workers 1`), so true parallel request handling under load is limited to Python's GIL-bound thread pool behavior for the offloaded synchronous work.

**Large Files:** The 500MB cap combined with `MAX_ROWS_PROFILE=500_000` (profile-then-sample logic) suggests some awareness of scale limits, but the full in-memory, non-streaming ingestion path caps practical usability well below the stated 500MB limit for typical hardware.

**Potential Bottlenecks (ranked):** (1) the monolithic `/upload/analyze-with-employees` endpoint doing 10+ sequential engine calls per request with no job queue or progress streaming beyond the client-side simulated progress bar in `DataUpload.tsx`; (2) full-file in-memory loading with re-parsing across pipeline stages; (3) single-worker Uvicorn process; (4) the 15-second hard timeout on the governance scan (`_TIMEOUT_SECS`) — reasonable as a safety valve, but will hard-fail large/complex files rather than gracefully degrading.

---

# CODE QUALITY

**Architecture:** A layered-in-theory, monolithic-in-practice structure — `backend/core/` holds ~81 largely independent modules with minimal cross-imports, each implementing one pipeline stage or "engine." This makes individual modules easy to read in isolation but has produced the duplication problems documented throughout this doc (3 report exporters, 3-4 PII-detection implementations, 4 financial-formula implementations) because there's no shared "compute once, render many times" layer enforcing a single source of truth.

**Maintainability:** Mixed. Individual files are generally well-organized with clear docstrings and section-comment banners (`# ── Section Name ──`). But the sheer number of near-duplicate modules (two ML training paths, two report-generation stacks, two frontend applications, two auth-schema definitions sharing one DB file) means a change to core business logic (e.g. the financial-exposure formula) must be made correctly in 3-4 places by hand, and the audit already found evidence of those copies drifting apart.

**Readability:** Generally high at the individual-function level — descriptive names, type hints used consistently (Python 3.10+ `X | None` syntax throughout), docstrings present on most public functions/classes.

**Design Patterns:** Module-level singletons are the dominant pattern for stateful services (`_scanner = SecureFileIngestion()`, `_ml_router = MLRouter()`, etc.) — simple but means no dependency injection, making unit testing require monkeypatching module globals in places. `@dataclass` used extensively for result/report objects. Factory functions (`create_local_analysis_router()`, `create_app()`) wrap router/app construction. Guarded-import (`try/except ImportError` → `_HAS_X` flag) is used pervasively (15+ files) for optional heavy dependencies (xgboost/lightgbm/catboost/shap/prophet/optuna) — a genuinely good pattern, consistently applied.

**SOLID:** Single Responsibility is respected at the module level (each engine does one thing) but violated at the system level — three separate modules each independently reimplement "compute financial exposure," meaning that responsibility isn't actually singular across the codebase. Open/Closed is reasonably served by the guarded-import pattern (new optional model backends can be added without touching call sites). Dependency Inversion is weak — concrete singletons are imported and used directly rather than injected, coupling call sites to implementations.

**Technical Debt:** Significant and well-documented **by the codebase's own history** — ~150 root-level markdown files chronicle "Phase N" rewrites and audits, several of which (per file content, e.g. `LEGACY_LOGICAL_QUARANTINE_REPORT.md`, `config/settings.py`'s `LEGACY_DISABLED_CONSTRUCTS` list) explicitly acknowledge and quarantine earlier, now-known-incorrect formulas rather than deleting the code — meaning old, wrong implementations remain present (behind a feature flag) alongside their replacements.

**Duplicated Code:** The most severe quality issue in the codebase. Confirmed, non-trivial duplication in: (1) report content generation (PDF/PPTX/slide exporters each recompute the same board-report content independently), (2) PII/leakage column detection (reimplemented independently in `SecureFileIngestion`, `ml_validation_engine.py`, and the orphaned `leakage_detector.py`), (3) financial-exposure formulas (4 independent implementations, see Business Logic), (4) two entirely separate frontend applications (React + Streamlit) that both reimplement pipeline orchestration rather than one calling the other's API.

**Unused/Dead Code:** Extensive — 25 of 57 API endpoints (44%), roughly 32 of 81 `backend/core/` modules (not reachable from any live entry point), an entire orphaned auth-schema scaffold (`auth_session.py`), 3 orphaned frontend pages (`DemoMode.tsx`, `PlatformWalkthrough.tsx`, `ExecutiveReportPrint.tsx`), 3 empty stray root directories (`frontendcomponents/`, `frontendpages/`, `frontendutils/`), and a stale committed `executive-ui/dist/` build artifact.

**Precise duplication instances found by direct cross-file function-name scan (beyond the already-documented report-exporter and PII-detection triplication):** `_expected_calibration_error` independently reimplemented in `calibration_engine.py` and `ml_validation_engine.py`; `_risk_label` independently reimplemented 3 times with different thresholds (`executive_decision_intelligence.py`, `executive_storytelling_engine.py`, `risk_intelligence.py`); `_grade` duplicated (`executive_index_engine.py`, `executive_readiness_engine.py`); `_clamp` reimplemented 3 times with slightly different signatures; 4-10 near-duplicate string/column-name normalization helpers scattered across half a dozen files. **Root cause: `backend/core/` has no shared `utils`/`helpers` module** for small cross-cutting numeric/string operations — each of the ~81 files tends to write its own private copy rather than importing a common one. Minor benign case: `risk_intelligence.py` defines an identical `total_financial_exposure_usd` property twice in the same file, on two different dataclasses.

**Design pattern census (precise counts):** `@dataclass` used 148 times across 69 of 81 `backend/core/` files (85% of the directory). Module-level singleton instantiation appears 14 times total (2 in `backend/core`, 12 in `backend/api` route modules wiring up shared engines at import time). Guarded `try/except ImportError` appears 21 times across 11 files. Router-factory functions (`create_X_router()`) appear 3 times, all in `backend/api`.

**Style consistency:** 100% snake_case Python filenames (zero camelCase files found across `backend/`, `frontend/`, `tests/`, `scripts/`). Return-type annotation density in `backend/core/` is ~97% (932 function definitions vs. 900 lines containing `->`). Docstring coverage is bimodal: an AST-based check of 15 representative files found governance/validation-engine files (`leakage_detector.py`, `theory_grounded_construct_engine.py`, `audit_logger.py`) at 80-100% top-level docstring coverage, while report/scoring-exporter files (`executive_pdf_exporter.py`, `risk_intelligence.py`, `employee_risk_scoring.py`) sit at only 17-33% — the more business-critical/scientific modules are documented noticeably better than the presentation-layer ones. Overall top-level docstring coverage across the sample: 62.7%.

**TODO/FIXME density:** Essentially zero in actual code — a full-repo case-insensitive search found exactly **one** match, and it's a test fixture string (a list of placeholder-detection markers), not a real outstanding TODO. No `FIXME`/`XXX`/`HACK` exists anywhere in `backend/`, `frontend/`, `executive-ui/src/`, `tests/`, or `scripts/`. The phrase "not implemented" appears 20 times, but **exclusively in the root-level `.md` audit-doc corpus**, never in code (e.g. `PRODUCTION_API_SURFACE.md`: "Rate Limiting — Not Implemented — Required for Production"). This confirms the pattern already noted: known gaps are tracked as prose in ~150 narrative documents, not as inline code markers — meaning a reviewer who only greps code for TODOs would significantly undercount the project's actual known-incomplete surface.

---

# KNOWN ISSUES

**Confirmed bugs (verified by direct code inspection, not speculation):**
1. **`Dockerfile`'s `CMD` cannot start the app.** `uvicorn backend.api.main:app` requires a module-level `app` object that only exists inside `if __name__ == "__main__":` — importing the module (as uvicorn does) never executes that block. The working invocation is `python backend/api/main.py`, which also means `--reload` and CLI host/port flags are unavailable via the documented Docker entrypoint.
2. **Docker `HEALTHCHECK` targets a route that doesn't exist** (`/health`; the only health-style endpoint is `/api/v1/status`) — the healthcheck would 404 indefinitely if the container otherwise started successfully.
3. **`rapidfuzz.fuzz.token_set_ratio` AttributeError** in `semantic_mapper.py:265`, reproducible via the excluded `test_e2e.py` — a real, currently-broken code path in the fuzzy column-matching stage, invisible to CI because the file that exercises it isn't collected by `pytest.ini`.
4. **`tenant_manager.py` and `historical_intelligence_engine.py` both default to bare relative SQLite filenames**, producing duplicate, diverging physical `.db` files depending on process working directory at instantiation time.
5. **Streamlit port mismatch**: the app itself (and `config/settings.py`) say port 8510; `docker-compose.yml`'s commented-out service maps port 8501.
6. **`/api/local/upload/export-employee-csv` is a non-functional stub** — always returns HTTP 400 telling the caller to re-upload, rather than actually exporting anything.
7. **44% of the API surface (25 endpoints) is fully implemented but structurally unreachable** — `upload_routes.py`, `report_routes.py`, `enterprise_routes.py` are never mounted by `main.py`.
8. **`config/production_settings.py` is dead configuration** — hardcodes `ENVIRONMENT="production"` but nothing ever switches to it based on an actual environment variable.

**Broken/incomplete logic:**
- `enterprise_routes.py`'s job-status and calibration endpoints are permanent scaffolds — `GET /v1/jobs/{job_id}/status` always returns `NOT_FOUND`, calibration always returns `NOT_EVALUATED`, regardless of input. This was built API-first with the backend wiring never completed.
- Two unreconciled session models (`main.py`'s volatile in-memory dict vs. `local_analysis_routes.py`'s persistent SQLite store) with no migration path between them.
- A dormant, unused second auth-schema (`auth_session.py`) shares a database file with the active `local_auth.py` system but has never written to it.

**TODOs/FIXMEs:** See Repository Statistics section for the full grep results; the codebase's preferred mechanism for flagging known-incomplete work is markdown "audit" documents (~150 of them) rather than inline TODO comments, so inline-comment density is lower than the actual amount of known incompleteness would suggest — the real backlog lives in prose, not code comments.

**Incomplete features:** Multi-tenant isolation (schema exists, enforcement doesn't), production Postgres/Redis support (mentioned in `.env.example`, never implemented), CI/CD (entirely absent), the entire `enterprise_routes.py` SaaS surface (built but never wired in).

---

# IMPROVEMENT SUGGESTIONS (ranked by impact)

1. **Wire authentication into the live product**, or explicitly and honestly reposition the product as single-user/local-only (in which case, remove the unused auth system entirely rather than leaving it half-connected — it currently creates false confidence that access control exists).
2. **Consolidate the financial-exposure formula** into one function that `executive_roi_engine.py`, the 3 report exporters, and `workforce_simulation_engine.py` all call — eliminates the 4-way drift risk identified in Business Logic.
3. **Fix the Dockerfile `CMD`** (add a module-level `app = create_app()` outside the `__main__` guard, or change the CMD to `python backend/api/main.py`) and fix the healthcheck route — the deployment path is currently non-functional as documented.
4. **Consolidate PII/leakage detection** into a single shared function called by `SecureFileIngestion`, `ml_validation_engine.py`, and `leakage_detector.py` (or delete the redundant copies) — same drift risk as #2, applied to governance/compliance logic specifically.
5. **Decide between the two frontends.** Either delete `frontend/` (Streamlit) or make it a genuine thin client of the same FastAPI backend the React app uses, instead of a second independent in-process reimplementation of the pipeline.
6. **Add CI** — even a minimal GitHub Actions workflow running `pytest` and `npm run build` on push would have caught the `rapidfuzz` bug and would prevent the Docker `CMD` regression from recurring.
7. **Remove or wire up the 44% dead API surface** — `upload_routes.py`/`report_routes.py`/`enterprise_routes.py` represent significant, functioning engineering effort that currently provides zero value and meaningfully inflates the codebase's apparent scope.
8. **Fix `pytest.ini` to collect the 7 excluded root-level test files** (after converting them from `sys.exit()`-based scripts to proper pytest test functions) — they contain real, substantive checks currently invisible to CI.
9. **Delete stray empty directories** (`frontendcomponents/`, `frontendpages/`, `frontendutils/`) and stop committing `executive-ui/dist/`.
10. **Move the ~150 root-level narrative `.md` files into a `docs/history/` subfolder** — they're valuable historical record but currently dominate the repo root and make it hard to find the handful of files (README-equivalent, `AUDIT_REPORT.md`) that actually matter for onboarding.

---

# DEPENDENCY GRAPH

**High-level module dependency flow (live path only):**

```
executive-ui (React, browser)
      │  fetch() — relative paths, proxied by Vite in dev
      ▼
backend/api/local_analysis_routes.py  ──imports──▶  backend/core/{secure_file_ingestion, dataset_type_classifier,
      │                                               excel_ingestion_engine, employee_risk_scoring,
      │                                               employee_risk_exporter, executive_narrative_engine,
      │                                               workforce_forecasting_engine, ml_validation_engine,
      │                                               workforce_simulation_engine, executive_decision_intelligence,
      │                                               executive_index_engine, executive_roi_engine,
      │                                               executive_storytelling_engine, executive_readiness_engine,
      │                                               local_database, tenant_manager, historical_intelligence_engine,
      │                                               executive_pdf_exporter, executive_pptx_exporter,
      │                                               executive_slide_exporter, benchmark_engine}
      │
      ▼ (employee_risk_scoring.py also imports)
backend/core/{employee_explainability_engine, hr_recommendation_engine}
      │
      ▼ (ml_validation_engine.py is self-contained sklearn code, no further backend.core imports)

backend/api/auth_routes.py  ──imports──▶  backend/core/{local_auth, auth_session (types only), security_middleware}

backend/api/main.py  ──imports──▶  backend/core/{dataset_profiler, semantic_mapper, adaptive_router, data_healer,
                                     feature_factory, ml_router, risk_intelligence, insight_generator,
                                     biosignal_adapter, theory_aware_column_mapper, theory_grounded_construct_engine,
                                     model_input_contract, temporal_validation_guard}
                                     — this whole subtree is reachable only via /api/v1/* routes, which
                                       executive-ui never calls (see Architecture / Known Issues)
```

**Parallel, disconnected subtree:**
```
frontend/app.py (Streamlit, separate process)  ──imports──▶  backend/core/{dataset_profiler, semantic_mapper,
      adaptive_router, data_healer, feature_factory, ml_router, risk_intelligence, report_generator,
      confidence_governance, calibration_engine, feature_trustworthiness, ethical_ai, explainability_engine,
      timeseries_engine, confidence_engine}
      — this subtree overlaps with main.py's imports but is a fully independent call graph
        (no shared code path with local_analysis_routes.py beyond backend/core module reuse)
```

**Dead subtree (imported only by unmounted routers / tests):**
```
backend/api/{upload_routes, report_routes, enterprise_routes}.py  ──imports──▶  backend/core/{
      artifact_registry, audit_logger, audit_package_builder, executive_report_exporter, export_safety,
      report_localization, demo_company_generator, enterprise_language_guard (transitively), tenant_isolation}
```

**Key insight:** `backend/core/` modules are the shared substrate, but three different "top-level" call graphs consume overlapping-but-not-identical subsets of them (executive-ui → local_analysis_routes.py; direct-API-caller/Streamlit → main.py's inline endpoints or app.py directly; nothing → the three dead routers). No single module in `backend/core/` is imported by all three graphs.

---

# EXECUTION GUIDE

**Prerequisites:** Python 3.12/3.13 (inferred from bytecode cache tags and `X | None` union-type syntax used throughout `backend/core/`; no version is formally pinned via `.python-version` or `pyproject.toml`), Node.js/npm for the frontend.

1. `pip install -r requirements.txt` from the repo root.
2. **Start the backend using `python backend/api/main.py`** — not `uvicorn backend.api.main:app`, which fails (see Known Issues #1). Listens on `0.0.0.0:8000`.
3. In a second terminal: `cd executive-ui && npm install && npm run dev` — Vite dev server on `http://localhost:5173`, proxying `/api` and `/v1` to `localhost:8000`.
4. **Both processes must run simultaneously** — neither the frontend nor backend alone provides a working end-to-end experience.
5. **No auth setup is required** to use the core product — `/api/local/upload/analyze` and every other data-analysis endpoint have zero authentication checks. To exercise the separate auth/RBAC system specifically: call `POST /api/auth/bootstrap` with a chosen `initial_password`, or set `AWI_ADMIN_BOOTSTRAP_PASSWORD` before starting the server, or set `AWI_AUTH_ENFORCED=false` to bypass JWT checks entirely (dev/test only).
6. **Optional alternate frontend:** `streamlit run frontend/app.py --server.port 8510` — note the app's own docstring specifies port 8510, which does not match `docker-compose.yml`'s commented-out `8501` default; this frontend talks directly to `backend/core/` in-process and does not require the FastAPI server to be running at all.

---

# BUILD PROCESS

**Frontend production build:** `cd executive-ui && npm run build`, which runs `tsc && vite build` — TypeScript type-checks the entire project (failing the build on type errors, not just transpiling) before Vite bundles to `executive-ui/dist/`. **Note:** `executive-ui/dist/` already exists in the working tree as a checked-in-looking build artifact — since this isn't a git repository, "committed" can't be verified via git history, but its presence alongside source is the same anti-pattern as committing build output normally is: it will silently drift out of sync with `src/` and should be excluded from version control once this project is placed under one.

**Backend build:** None — interpreted Python, no compilation step. `Dockerfile` packages it into a `python:3.11-slim` container image (non-root user, exposes port 8000) — but see Known Issues #1 and #2 for the two confirmed bugs in that packaging (broken `CMD`, broken healthcheck route).

**Deployment:** `docker-compose.yml` runs only the API container by default (the Streamlit service block is present but fully commented out). **No CI/CD pipeline exists anywhere in the repository** — no `.github/workflows/`, no other CI config of any kind — so building, testing, and deploying are entirely manual today.

---

# REPOSITORY STATISTICS

**Total files in scope (excluding node_modules/.venv/venv/.git/dist/build/coverage/cache/__pycache__/logs/saved_models/SCREENSHOTS/tmp/bin/obj/catboost_info): 403.**

| Extension | Count |
|---|---|
| `.py` | 172 |
| `.md` | 133 (127 at repo root, 6 in `docs/`) |
| `.tsx` | 40 |
| `.mjs` | 9 |
| `.ts` | 8 |
| `.json` | 8 |
| `.db` / `.sqlite` | 7 |
| `.html` | 4 |
| `.csv` / `.xlsx` | 3 |
| `.css` | 1 |
| Other (`.env.example`, `.yml`, `Dockerfile`, config `.js`, `.pptx`, `.pdf`, `.ini`, etc.) | 18 |

**Lines of code by area:**

| Area | Files | LOC |
|---|---|---|
| `backend/core/*.py` | 81 | 45,130 |
| `backend/api/*.py` | 6 | 3,879 |
| `executive-ui/src/**/*.{ts,tsx}` | 48 | 18,488 |
| `frontend/**/*.py` | — | 6,358 |
| `tests/*.py` + root `test_*.py` | — | 17,873 |
| `scripts/*.py` | 4 | 2,220 |
| Root-level `*.md` docs (all 127 combined) | 127 | 32,154 |

`backend/core/` alone (45,130 LOC across 81 files) is larger than `backend/api`, `frontend`, `executive-ui/src`, `tests`, and `scripts` **combined** (48,818 LOC) — the large majority of the system's actual logic sits in one flat 81-file directory with no sub-package structure.

**15 largest individual source files:** `frontend/app.py` (3,209 lines — the Streamlit app is the single largest file in the repo), `executive_pdf_exporter.py` (2,509), `ExecutiveDashboard.tsx` (2,117), `EmployeeRiskDashboard.tsx` (2,054), `ExecutiveReports.tsx` (1,810), `local_analysis_routes.py` (1,657), `theory_aware_column_mapper.py` (1,340), `scripts/phase29_5_model_search.py` (1,326), `leakage_detector.py` (1,279 — notably large for a module confirmed only partially wired into the live path), `executive_pptx_exporter.py` (1,264), `ExecutiveReportPreview.tsx` (1,210), `employee_risk_scoring.py` (1,081), `theory_grounded_construct_engine.py` (1,064), `DataUpload.tsx` (1,061), `executive_slide_exporter.py` (1,000).

**On-disk size:** `backend/` 2.4MB · `executive-ui/` (excl. node_modules/dist) 1.2MB · `frontend/` 734KB · root-level `.md` docs combined 1.9MB · `data/` + root `.db` files combined ~2.16MB.

**Documentation debris:** 127 markdown files sit at the repo root — 63 with "report"/"audit" in the filename, 26 "PHASE*" progress logs. These total 32,154 lines / 1.9MB — roughly 70% of all markdown volume in the repo, and larger by line count than the entire `backend/api` + `executive-ui/src` codebase combined. These are historical, AI-generated project-narrative documents accumulated phase-by-phase during development, not reference documentation.

---

# PROJECT MATURITY

| Dimension | Score /10 | Why |
|---|---|---|
| **Architecture** | 5 | Reasonable per-module separation of concerns, but two unreconciled frontends, two unreconciled ML training paths, three unmounted "aspirational" API routers, and no shared utils layer add up to a system that's architecturally larger and more fragmented than its actual live surface requires. |
| **Code Quality** | 6 | Individual files are well-typed (~97% return-annotation density), consistently snake_case, and reasonably documented in the modules that matter most scientifically. Undermined by extensive, confirmed cross-file duplication (financial formulas, PII detection, calibration metrics, risk labeling, grading — at least 8 distinct duplicated-logic instances found) with no shared helpers module. |
| **Security** | 3 | Individual security primitives (bcrypt, JWT, parameterized SQL, generated secrets) are competently built, but completely disconnected from the live product — every data-bearing endpoint a real user hits has zero authentication, regardless of the auth-enforcement flag's state. This is a severe, not cosmetic, gap for anything beyond single-developer local use. |
| **Performance** | 6 | Sensible async/await usage and CPU-work offloading for a single-process deployment; no caching layer, no job queue, full in-memory file loading with re-parsing across pipeline stages, and a single Uvicorn worker cap headroom for anything beyond light, single-user load. |
| **Maintainability** | 5 | The ~150-document narrative-audit-doc habit is a double-edged sign: it shows the team actively tracks its own debt (good), but the debt itself (2 ML paths, 2 frontends, 4 financial formulas, 44% dead API surface) is real and would slow any new contributor's onboarding significantly, especially with zero automated tests protecting the auth path. |
| **Scalability** | 4 | SQLite-only persistence (no Postgres despite being mentioned in `.env.example`), no message queue, no horizontal-scaling story, single-worker container — appropriate for the stated "single-machine, offline" design goal, but that goal is in tension with the parallel "enterprise multi-tenant SaaS" ambitions expressed in the dead `enterprise_routes.py` and ~150 pitch/audit documents. |
| **AI Quality** | 7 | The theory-grounded construct engine is a genuine, well-evidenced differentiator with real formulas cited to real organizational-psychology literature, and the platform's explicit avoidance/runtime-blocking of LLM calls is a defensible, honest design choice rather than a limitation to apologize for. Held back from a higher score by the live product using the simpler of its two ML training paths, and by real governance modules (leakage detector, model validator, truth auditor) being genuinely invoked but only in the unused training path, with their output silently discarded even there. |
| **Overall Score** | **38/100** | Calculated as a security-and-liveness-weighted composite, not a simple average of the above (which would suggest ~5.1/10 → 51/100). The overall score is pulled down hard by two facts that dominate any technical-buyer risk assessment: **(1)** no client or tenant has ever used this system (every account/tenant database is empty), and **(2)** the live product a user would actually open today has no authentication and does not run the ML pipeline described in most of the project's own documentation. This is a well-engineered set of *components* that has not yet been assembled into a coherent, secure, single product — closer to an advanced, feature-rich prototype than to a deployable commercial MVP. |

---

# CHATGPT CONTEXT

**What this project is, in one paragraph:** A Python/FastAPI backend + React/TypeScript frontend HR-analytics application that ingests employee CSV/Excel files, runs them through a deterministic governance-and-cleaning pipeline, computes psychology-theory-grounded features, trains a classical ML classifier (LogisticRegression/RandomForest/GradientBoosting) to predict attrition risk, and produces executive dashboards plus board-ready PDF/PPTX/HTML reports — positioned for the Saudi/GCC market with Arabic localization and PDPL-compliance framing. There is no LLM, embedding model, or vector database anywhere in the system (verified, and actively runtime-blocked at the socket level) — every "AI" output is either classical supervised ML or deterministic rule/template-based text generation.

**The single most important structural fact:** two parallel implementations exist for almost every major subsystem, and only one half of each pair is what the shipped React product actually uses. (1) ML training: `ml_router.py` (XGBoost/LightGBM/CatBoost, SMOTE-in-folds, 3 governance-module integration) is NOT reachable from the live frontend; `ml_validation_engine.py` (simpler sklearn-only, no SMOTE) IS what runs. (2) Frontend: React `executive-ui` is live; Streamlit `frontend/app.py` is a separate, off-by-default, in-process reimplementation. (3) API surface: `local_analysis_routes.py` + `auth_routes.py` are mounted and live; `upload_routes.py`/`report_routes.py`/`enterprise_routes.py` (44% of all endpoints, 25 of 57) are fully built but never mounted into the running app. Any review of this codebase must first establish which half of a given pair is actually being asked about.

**The second most important structural fact:** a fully-functional, well-built local authentication system (bcrypt + JWT + lockout + RBAC + audit log) exists but is never called by the shipped frontend, and the actual data-analysis endpoints have zero auth checks by design (self-documented in `local_analysis_routes.py`'s own docstring as "no-auth, single machine"). Anyone reviewing this for security purposes should treat the live product as **currently unauthenticated**, full stop — the auth code's quality is irrelevant to that fact since it's not in the request path that matters.

**The third most important structural fact:** no client or tenant has ever used this system in any commercial sense. Every tenant/user account database (`awi_tenants.db`, `data/awi_auth.db`) has zero rows. The only substantive dataset ever processed through the pipeline is a single external Excel file (1191 rows × 35 columns) that lives outside the repository on the developer's personal filesystem, processed repeatedly by one `default` local tenant over about 7 weeks — evidence of solo development/testing, not client engagements. Whether that one file represents real Saudi HR data or a downloaded practice dataset cannot be determined from the repository alone; treat any specific "real client data" claim in the project's own ~150 narrative markdown documents as unverified marketing language, not established fact.

**Financial/business-logic fragmentation:** at least 4 independent, differently-calibrated financial-exposure formulas coexist (flat SAR 120,000/35%/28% in the 3 live report exporters; a 9-component Cascio-Boudreau model in `executive_roi_engine.py`; a flat SAR 18,000/departure floor in `workforce_simulation_engine.py`; a flat SAR 8,000/month model in the dead `roi_estimation_engine.py`). Similar fragmentation exists for PII/leakage detection (3 independent implementations) and several smaller statistical helpers (calibration error, risk labeling, grading). There is no shared `utils` module in `backend/core/` — this is a systemic pattern, not a one-off oversight, and is the single highest-leverage refactoring opportunity in the codebase.

**Governance modules — a nuanced case worth understanding precisely:** `leakage_detector.py`, `model_validator.py`, and `model_truth_audit.py` are genuinely invoked with real logic — but only inside `ml_router.py`'s training path (the one the live frontend doesn't use), and even there their computed output (leakage report, validation report, truth-audit verdict) is silently discarded before the API response is built — never returned to any caller except the Streamlit app. `saudi_data_governance.py` and `enterprise_language_guard.py` are fully orphaned — no live-reachable import path exists at all. The governance behavior a real user of the live product experiences (PII/leakage blocking, feature exclusion) comes from separate, self-contained logic duplicated into `SecureFileIngestion` and `ml_validation_engine.py` rather than these named modules.

**What's genuinely good here:** the theory-grounded psychological construct engine (27 mapped constructs, 7 computed via real formulas cited to named organizational-psychology literature — JD-R model, Kahn's engagement theory, Adams' Equity Theory, Siegrist's Effort-Reward Imbalance) is a legitimate scientific/product differentiator, not marketing fluff — the formulas are real and traceable in code. The deterministic, LLM-free design is a defensible and honestly-executed choice, not a gap. Code style (typing, naming, docstrings on the most important modules) is consistently good. The team's own extensive self-audit habit (~150 markdown documents) shows real awareness of the system's limitations, even though that awareness hasn't yet translated into fixing the two-implementations and dead-auth problems.

**What would most change a technical reviewer's verdict:** (1) confirming whether the "live" `ml_validation_engine.py` path or the "advertised" `ml_router.py` path is the one the business actually wants to ship, and consolidating to one; (2) wiring auth into the live request path or explicitly repositioning as single-user local software; (3) consolidating the 4 financial formulas and 3 PII-detection implementations into single sources of truth; (4) either deleting or actually mounting the 44% dead API surface; (5) getting the excluded root-level tests (`test_e2e.py` etc., which currently hide at least one real bug — a `rapidfuzz` `AttributeError` in `semantic_mapper.py`) back into the CI-equivalent test run. None of these are large individual efforts; the fact that none have been done yet, despite ~150 documents describing very similar findings across many "phases," is itself informative about this project's development pattern — thorough self-diagnosis, incomplete follow-through on remediation.
