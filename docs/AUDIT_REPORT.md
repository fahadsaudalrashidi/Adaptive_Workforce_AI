# Adaptive Workforce AI — Full Codebase Audit

Scope: `c:\Users\PvP-Pc\Desktop\Adaptive_Workforce_AI` (not a git repo — no commit history available). Every claim below was verified by opening the cited file and line, not inferred from filenames or the ~150 self-authored `*.md` "audit"/"report" documents already sitting in the repo root. Those documents were treated as leads to check, never as evidence — several of their claims are contradicted by what's actually in the code (noted inline).

---

## 1. Entry Point & Live Execution Path

**Backend entry point:** `backend/api/main.py`, function `create_app()` (line 79). It mounts exactly two routers:

```python
app.include_router(auth_router)                          # main.py:107 → backend/api/auth_routes.py
app.include_router(create_local_analysis_router())        # main.py:110 → backend/api/local_analysis_routes.py
```

It also defines two endpoints **inline**, directly in `create_app()`: `POST /api/v1/upload` (main.py:132) and `POST /api/v1/analyse` (main.py:175).

**Route files in `backend/api/`: LIVE vs DEAD**

| File | Verdict | Evidence |
|---|---|---|
| `main.py` | CONFIRMED LIVE | entry point itself |
| `auth_routes.py` | CONFIRMED LIVE (mounted) but see §7 — not called by the shipped frontend | `main.py:107` |
| `local_analysis_routes.py` | CONFIRMED LIVE — this is the real workhorse | `main.py:110`; confirmed as the actual fetch target from `executive-ui/src/pages/DataUpload.tsx:672` |
| `upload_routes.py` | CONFIRMED DEAD | Zero references anywhere in the repo outside its own file — not imported by `main.py`, not imported by any test |
| `report_routes.py` | CONFIRMED DEAD | Zero references anywhere outside its own file |
| `enterprise_routes.py` | CONFIRMED DEAD | Only reference in the entire repo is `tests/test_phase7_tenant_isolation.py` (imports `router`, `GovernanceStatus`, `TenantCreateResponse`, `OnboardingResponse`, `ExecutiveReportResponse`) — never mounted in `main.py` |

**A second, more important finding: `main.py`'s own inline `/api/v1/upload` + `/api/v1/analyse` endpoints are themselves not what the shipped frontend calls.** `executive-ui/src/pages/DataUpload.tsx:672` and `:708` POST to `/api/local/upload/analyze` and `/api/local/upload/analyze-with-employees` — both served by `local_analysis_routes.py`, confirmed by its `APIRouter(prefix="/api/local", ...)` declaration (`local_analysis_routes.py:441`) and matching route decorators at lines 443 and 701. `executive-ui/src/state/sessionStore.ts` (`API_BASE = '/api/local'`) confirms the same. **Nothing in `executive-ui/src` calls `/api/v1/upload` or `/api/v1/analyse` at all** (grepped, zero matches). Those two inline endpoints are technically mounted and reachable (e.g. via curl or the `/api/v1/docs` Swagger page) but are not part of the product's actual user flow — PARTIALLY WIRED at best.

**Two Docker/deployment bugs found while tracing this, not mentioned anywhere in the ~150 root `.md` docs:**
1. `Dockerfile`'s `CMD` is `uvicorn backend.api.main:app …`, which requires a module-level `app` object. But `main.py` only ever assigns `app = create_app()` **inside** `if __name__ == "__main__":` (line 414) — a block that does not execute when uvicorn imports the module. Running the documented Docker command would raise `AttributeError: module 'backend.api.main' has no attribute 'app'`. UNVERIFIED whether this has actually been run (I did not execute Docker), but the code is unambiguous.
2. `Dockerfile`/`docker-compose.yml` `HEALTHCHECK` hits `http://localhost:8000/health` — no such route exists anywhere in the app. The only health-style endpoint is `GET /api/v1/status` (`main.py:123`, prefix confirmed as `/api/v1` via `config/settings.py:270-271`). The healthcheck would 404 forever.

**Frontend: executive-ui (React) vs frontend/ (Streamlit) — both are real, but they are two separate, parallel applications, not a live/dead pair.**
- `executive-ui` (React + Vite, `executive-ui/package.json` scripts: `dev`/`build`/`preview`) talks to the FastAPI backend over HTTP, exclusively via `/api/local/*` routes in `local_analysis_routes.py`.
- `frontend/app.py` (Streamlit, `frontend/app.py:1-23` docstring: "Port 8510. Run: py -3 -m streamlit run frontend/app.py") does **not** call the FastAPI backend over HTTP at all. It directly imports and calls `backend.core.*` modules in-process (`DatasetProfiler`, `SemanticMapper`, `AdaptiveRouter`, `DataHealer`, `FeatureFactory`, `MLRouter`, `risk_intelligence` — `frontend/app.py:68-80`), i.e. it is a second, independent reimplementation of the orchestration logic that also lives inline in `main.py`'s `/api/v1/analyse`.
- `docker-compose.yml` comments the Streamlit service out entirely ("Disabled by default. Enable only for demo/development purposes.") — so in the one deployment artifact the repo ships, only the React app is live by default.
- Net effect: **React is the product's live frontend. Streamlit is a real, functioning, but separate and non-default alternate frontend that duplicates orchestration logic rather than consuming the same API.**

---

## 2. Machine Learning Path — Which One Actually Runs

Both `ml_router.py` and `ml_validation_engine.py` are real, working code. They are not duplicates of each other in the trivial sense — they are wired into **different, non-overlapping live paths**, and only one of those paths is what the shipped product actually uses.

| Module | Where it's called from | Reachable from the shipped React frontend? |
|---|---|---|
| `backend/core/ml_router.py` (`MLRouter`, class `XGBClassifier`/`LGBMClassifier`/`CatBoostClassifier`/LR/RF/GB, `ml_router.py:8-11,26-62`) | `main.py:70` (`_ml_router = MLRouter()`), invoked at `main.py:293` inside the inline `/api/v1/analyse` endpoint. Also imported directly by `frontend/app.py:77` (Streamlit). | **No.** `/api/v1/analyse` is not called anywhere in `executive-ui/src` (verified, zero matches). Streamlit is disabled by default (see §1). |
| `backend/core/ml_validation_engine.py` (`run_ml_validation`, LogisticRegression/RandomForest/GradientBoosting only, `ml_validation_engine.py:28-29`) | `local_analysis_routes.py:80` imports it, called at `local_analysis_routes.py:932`: `_ml_validation = await asyncio.to_thread(run_ml_validation, ir.df)`, inside `POST /upload/analyze-with-employees`. | **Yes.** This is the exact endpoint `DataUpload.tsx:708` fires after the initial governance scan. |

**Conclusion: for the product a user actually opens (executive-ui), the live ML path is `ml_validation_engine.py`, not `ml_router.py`.** `ml_router.py` is real and does get exercised — but only via the Streamlit app (off by default) or by calling the orphaned `/api/v1/analyse` endpoint directly. This directly contradicts a simple "ml_router.py is the real engine" reading of the codebase; the opposite is true for the shipped UI.

**SMOTE / preprocessing-in-CV-folds — checked against the actual live path (`ml_validation_engine.py`), not the unused one:**
- `ml_validation_engine.py` contains **zero references to SMOTE or imbalanced-learn** anywhere in the file (grepped, confirmed). Class imbalance is handled via `class_weight='balanced'` on all three sklearn models (`ml_validation_engine.py:658-668`), not resampling.
- Preprocessing genuinely happens inside CV folds: `_run_conservative_analysis` (`ml_validation_engine.py:605`) builds a fresh `Pipeline([('prep', clone(preprocessor_template)), ('clf', clone(clf_template))])` **inside** the `for train_idx, val_idx in kf.split(...)` loop (lines 689-697) and calls `pipe_fold.fit(X_tr, y_tr)` on the training fold only, predicting on the held-out fold — `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)` (line 671). This is methodologically correct: imputation/scaling/one-hot-encoding are refit per fold, no leakage from validation rows into preprocessing statistics.
- `ml_router.py`'s docstring (lines 13-14) makes the same "SMOTE only inside folds" claim for **its own** pipeline (`ml_router.py:137-139`, SMOTE inserted as the first Pipeline step, only fires on `.fit()` which happens per-fold under `cross_val_predict`) — this claim also checks out on inspection — but again, this is the path the shipped frontend never reaches.

**So: the specific claim "SMOTE only happens inside CV folds" is true of `ml_router.py`, and irrelevant to what end users experience, because SMOTE doesn't run at all in the path they actually hit — that path avoids the imbalance problem differently (class weighting), correctly, inside properly-scoped CV folds.**

---

## 3. Report Generation — Real Duplication Check

Five named generators plus two more discovered while tracing live call sites (`executive_narrative_engine.py`, `executive_storytelling_engine.py`).

| File | Verdict | Evidence |
|---|---|---|
| `executive_report_exporter.py` | **CONFIRMED DEAD** | Only importers: `backend/api/report_routes.py` (already confirmed unmounted, §1) and a test file. Zero references from `local_analysis_routes.py`. |
| `executive_pdf_exporter.py` | **CONFIRMED LIVE** (one of 7 internal branches actually exercised) | `local_analysis_routes.py:1455-1521` (`POST /export/pdf`) imports and calls it; the executive-ui always sends `report_type: 'BOARD_REPORT_V3'` (`ExecutiveReports.tsx:591-593`), so only the `_body_board_report_v3` branch (line 1662) runs in practice — the other six body-builders are dead weight reachable only by hand-crafting a different request body. |
| `executive_pptx_exporter.py` | **CONFIRMED LIVE** | `local_analysis_routes.py:1381-1405` (`POST /export/pptx`) imports `generate_pptx` and calls it directly; `ExecutiveReports.tsx` "download-pptx-btn" → `fetch('/api/local/export/pptx', …)` (line 571). |
| `executive_slide_exporter.py` | **CONFIRMED LIVE** | `local_analysis_routes.py:1352-1377` (`POST /export/slides`) imports `generate_slide_deck` and calls it; `ExecutiveReports.tsx` "McKinsey Slide Deck" button → `fetch('/api/local/export/slides', …)` (line 555). |
| `report_generator.py` | **PARTIALLY WIRED** — live, but in the *other* app | Never imported anywhere under `backend/api/`. Actively imported and used by `frontend/app.py` (the separate Streamlit app, §1) and `frontend/utils/session_state.py`. Live for Streamlit users only; dead relative to the React/FastAPI stack. |
| `executive_narrative_engine.py` (not in the original 5, found while tracing) | CONFIRMED LIVE, different content domain | Imported `local_analysis_routes.py:72-75`, called at lines 899-909, output stored under the `"org_narrative"` response key — qualitative department-highlight prose, not financial figures. |

**Genuine duplication among the three LIVE exporters (pdf/pptx/slides) — this is real, not a naming coincidence.** All three independently hard-code the identical financial formula:
- `executive_pptx_exporter.py:57-60`: `exposure = at_risk * 120_000` (SAR per at-risk employee), re-derived separately in ~9 slide functions.
- `executive_slide_exporter.py:287-290`: `exposure = at_risk * 120_000; savings = int(exposure * 0.35); retained = int(at_risk * 0.28); monthly = int(exposure / 12)`.
- `executive_pdf_exporter.py:1721-1725`, literally commented `# ── Universal financial formula ──`: the same four lines again.

And the fallback narrative strings have visibly drifted apart from a common original, which only happens with copy-paste, not shared code:
- `executive_slide_exporter.py:292-295` vs `executive_pdf_exporter.py:1732-1735`: the same "Workforce intelligence analysis identified {at_risk} employees in elevated risk bands…" sentence, `_sar` renamed to `sar_str` in one copy.
- `executive_slide_exporter.py:382-383` and `executive_pptx_exporter.py:367-368` both hard-code the identical, oddly specific fallback claim "Engineering and Operations departments" as the top-risk explanation when the real narrative object is absent.

**Verdict:** `executive_pdf_exporter.py`'s v3 branch, `executive_pptx_exporter.py`, and `executive_slide_exporter.py` are three independent reimplementations of the same "board report" — same section outline, same risk-band extraction, same financial constants recomputed from scratch in each file. A correctly layered version would compute board content once and hand it to three format-specific renderers; instead the content computation itself is copy-pasted three times, and the copies have already started to diverge. `executive_report_exporter.py` and `report_generator.py`, by contrast, are wasted code (dead / parallel-app-only) but not part of this specific duplication — they do different jobs (PDPL/governance-audit HTML, and generic ML-pipeline confidence reporting) and contain no SAR financial-exposure math.

---

## 4. Test Suite Reality Check

**`pytest.ini` scopes collection to `testpaths = tests` only.** The seven root-level `test_*.py` files (`test_biosignal.py`, `test_company_readiness.py`, `test_e2e.py`, `test_frontend_guards.py`, `test_integration_v3.py`, `test_routing.py`, `test_stress.py`) are invisible to a plain `python -m pytest` run — and they aren't even pytest-compatible (each ends with a module-level `sys.exit(...)`; forcing pytest to collect one crashes with `INTERNALERROR> SystemExit`). They only work invoked directly as `python <file>.py`.

**Actual pytest run** (`python -m pytest --tb=short -q`, `tests/` only): **39 failed, 1113 passed, 1 skipped, 200 warnings in 55.61s.** All 39 failures are confined to one file, `tests/test_phase30_1_security.py`, and are environment breakage rather than code bugs — `passlib.exc.MissingBackendError: bcrypt: no backends available` and a `TestClient(app=app)` signature mismatch against the installed `starlette`/`httpx` version. The practical consequence: **authentication, JWT, RBAC, and audit-log regressions are currently invisible to anyone running `pytest`** in this environment, even though the test file itself is well-designed (real bcrypt-format assertions, e.g. `h.startswith("$2")`).

**The engine tests are genuinely strong where they're strong.** Roughly 30 of the 37 files in `tests/` verify real numeric formulas to `1e-9` precision (`test_theory_grounded_construct_engine.py:748-749`), real range/invariant checks, real PII/leakage governance blocking, cross-tenant isolation, and forbidden-language audits — computed against actual business logic, not mocks. Representative example: `test_phase14_employee_risk_dashboard.py:270`, `assert ids_p1.isdisjoint(ids_p2)` — a genuine pagination-correctness check.

**But roughly 8 of the Phase 27–29 files are UI/documentation theater, not tests.** They grep literal strings out of `.tsx`/`.md` source files rather than exercising any runtime behavior — e.g. `test_phase29_executive_experience.py:388`: `assert "ceo" in content`. This would not catch a broken component, a renamed prop, or a UI rendering the wrong data. The single weakest individual assertion in the whole suite is a straightforward tautology: `test_phase16_model_metrics.py:105`, `assert result.model_metrics is not None or True` — always passes regardless of what's on the left.

**No `@pytest.mark.xfail` exists anywhere.** Only one skip actually fired in this run (`test_phase16_model_metrics.py:193`, "Real Saudi dataset not present") — caused by a path inconsistency (it checks the repo root rather than the `C:\Users\PvP-Pc\Desktop\datasetssaudi\` path used everywhere else in the codebase, per §10).

**The seven excluded root-level scripts are, when run standalone, mostly real and mostly passing** — test_biosignal.py 36/36, test_company_readiness.py 91/91, test_frontend_guards.py 78/78, test_integration_v3.py 50/50, test_routing.py 41/41, test_stress.py 49/49 — genuine edge-case and stress checks (empty dataframes, 99:1 class imbalance, 200-column inputs). **One of them is silently broken and nobody would know:** `test_e2e.py` crashes even standalone with `AttributeError: module 'rapidfuzz.fuzz' has no attribute 'token_set_ratio'`, tracing to a real, reproducible bug at `backend/core/semantic_mapper.py:265` in the fuzzy-column-matching stage — invisible precisely because this file is excluded from `pytest.ini` and nobody runs it by hand.

**Bottom line: this test suite would catch a real regression in the core scoring/governance/construct-mapping engine. It would not catch an auth regression (currently failing wholesale), a broken UI component (many "tests" just grep source text), or the semantic-mapper bug that's already broken and shipping silently.**

---

## 5. Governance Modules — Actually Wired or Decorative?

Traced by reading the actual `/upload/analyze` and `/upload/analyze-with-employees` handler bodies in `local_analysis_routes.py` line-by-line, then grepping every import site of each named module across the whole repo.

**First finding: none of the 6 named governance modules are called anywhere in the live React-frontend path (`local_analysis_routes.py`).** That file's "governance scan" is implemented by `SecureFileIngestion.scan()` (`local_analysis_routes.py:114`, `_scanner = SecureFileIngestion()`) — a self-contained module with **zero internal `backend.core` imports** (grepped `secure_file_ingestion.py`, confirmed empty) — i.e. it does its own PII/leakage keyword matching rather than delegating to `leakage_detector.py` or `saudi_data_governance.py`. Separately, `ml_validation_engine.py` **also** reimplements its own column-exclusion logic with independent `_PII_KEYWORDS`, `_IDENTIFIER_KEYWORDS`, `_PROXY_KEYWORDS` lists (`ml_validation_engine.py:53-85`) rather than calling `leakage_detector.py`. That's three separate, non-shared implementations of "detect problematic columns" across the codebase (`SecureFileIngestion`, `ml_validation_engine.py`, and `leakage_detector.py` itself) — redundancy in the same family as §3's report-generator duplication.

| Module | Verdict | Evidence |
|---|---|---|
| `leakage_detector.py` | **PARTIALLY WIRED** | Imported only by `ml_router.py:70` (try/except-guarded) and `test_stress.py`. Actually invoked (not just imported) at `ml_router.py:448`: `result.leakage_report = _LeakageDetector().detect(...)`. But `ml_router.py` is only reachable via the orphaned `/api/v1/analyse` endpoint and the disabled-by-default Streamlit app (§1, §2) — never from the endpoint the shipped frontend calls. |
| `model_truth_audit.py` | **PARTIALLY WIRED**, same caveat | Imported/invoked only inside `ml_router.py` (`ml_router.py:82`, called at line 486: `result.truth_audit_report = _audit_model_truth(...)`). Same reachability problem as above. |
| `model_validator.py` | **PARTIALLY WIRED**, weakest of the three | Imported only by `ml_router.py:76` (try/except-guarded) and `test_stress.py:34`. Invoked at `ml_router.py:474`: `result.validation_report = _ModelValidator().validate(...)`. Same reachability problem. |
| `saudi_data_governance.py` | **CONFIRMED DEAD** | Only non-test importer is `enterprise_onboarding_pipeline.py:22` — which is itself only imported by `tests/test_phase6_enterprise_deployment.py:23`. No path from either live entry point (`main.py`, `local_analysis_routes.py`) reaches it. |
| `enterprise_language_guard.py` | **CONFIRMED DEAD** | Two known importers, both dead: `export_safety.py:24` (itself only imported by the dead `enterprise_routes.py:59` and three test files) and `executive_reporting_layer.py:26` (itself only imported by `tests/test_phase6_enterprise_deployment.py:39`). No live-reachable path. |

**Even where a module IS wired in (leakage_detector, model_truth_audit, model_validator via `ml_router.py`), its output is computed and then silently discarded, not surfaced to any UI a real user sees:**
- `ml_router.py`'s `TrainingResult` dataclass carries `leakage_report`, `validation_report`, `truth_audit_report` fields (`ml_router.py:120-122`), genuinely populated at lines 448/474/486.
- `main.py`'s `/api/v1/analyse` endpoint — the only FastAPI route that calls `MLRouter.train()` — builds its JSON response at `main.py:326-358` and **never reads any of those three fields**. Computed, logged (`main.py` only logs a truth-audit verdict summary at `ml_router.py:492-496` via the logger, server-side), then dropped before the HTTP response is built.
- The **one** place these reports do reach a human is the Streamlit app: `frontend/app.py:779-780,830-831,2982-2983` and `frontend/pages/explainability_page.py:345-346` all do `getattr(ml_res, "leakage_report", None)` / `"validation_report"` and render them. But Streamlit is off by default (§1).

**Net picture for Section 5:** the specific named governance modules are either fully orphaned (`saudi_data_governance.py`, `enterprise_language_guard.py`) or real-and-invoked-but-stranded behind a disabled frontend and a mounted-but-unused API endpoint, with their output actively discarded even in the one live route that computes it (`/api/v1/analyse`). The governance behavior a React-frontend user actually experiences (PII/leakage blocking on upload, feature exclusion before ML training) comes from *different*, self-contained code (`SecureFileIngestion`, `ml_validation_engine.py`'s own keyword lists) that duplicates — rather than reuses — the logic in the named modules.

---

## 6. Frontend (executive-ui) Deep Dive

**Correction to earlier scope estimate:** `executive-ui/src/pages/` contains **16 files**, not 20. All 16 were read in full.

### Page-by-page data source audit

| Page | Data Source | Reachable from nav? |
|---|---|---|
| AnalysisHistory.tsx | CONFIRMED LIVE — `fetchSessionHistory`/`fetchSessionDetail` from sessionStore (`:16-18`, `:301`) | Yes |
| CEODashboard.tsx | CONFIRMED LIVE — `useEmployeeRisk`/`useAnalysis` context, no demo import | Yes |
| DataUpload.tsx | CONFIRMED LIVE — the true entry point; `fetch('/api/local/upload/analyze', …)` (`:672`) and `.../analyze-with-employees` (`:708`) | Yes |
| DecisionCenter.tsx | CONFIRMED LIVE — `useEmployeeRisk` context (`:239`) | Yes |
| **DemoMode.tsx** | Demo data (`DEMO_COMPANIES` from `data/demoCompanies.ts`, hardcoded band counts 1847/892/384/124, hardcoded 0.847 AUC) | **No — CONFIRMED DEAD**, unreachable from any nav path |
| EmployeeRiskDashboard.tsx | CONFIRMED LIVE — `useEmployeeRisk` context, no demo import anywhere in file | Yes |
| ExecutiveDashboard.tsx | PARTIALLY WIRED — real context, but falls back to `estimateRiskSegments(analysis.rowCount, analysis.healthScore)` (`:1997`) whenever employee-level `riskData` hasn't populated yet | Yes |
| ExecutiveReportPreview.tsx | PARTIALLY WIRED — same `estimateRiskSegments` fallback pattern (`:210-213`) | Yes (special-cased) |
| **ExecutiveReportPrint.tsx** | Built to take real data as props, but never wired to anything | **No — CONFIRMED DEAD.** Its own file header (`:4`) claims it's "rendered inline at bottom of ExecutiveReports page" — verified false; `ExecutiveReports.tsx`'s full import list contains no such import. Fully-built component contradicted by its own comment. |
| ExecutiveReports.tsx | PARTIALLY WIRED — same `estimateRiskSegments` fallback (`:1044`) | Yes |
| GovernancePanel.tsx | CONFIRMED LIVE — real context | Yes |
| **PlatformWalkthrough.tsx** | Fully hardcoded — zero `useAnalysis`/`useEmployeeRisk` imports at all; static band counts (`1847/892/384/124`, `72.4` stability index) identical to DemoMode's numbers | **No — CONFIRMED DEAD** |
| RiskSegmentation.tsx | PARTIALLY WIRED — real bands when `riskData` present, `estimateRiskSegments` fallback otherwise (`:39` vs `:199`) | Yes |
| SimulationPanel.tsx | CONFIRMED LIVE — `useEmployeeRisk` + `fetchLatestSession`, no fallback | Yes |
| TheoryExplainability.tsx | CONFIRMED LIVE for the data; static (but genuine) academic citation list (Hobfoll 1989, Bakker & Demerouti 2007, etc.), explicitly commented "Real academic citations — not demo data" | Yes |
| **TrustPanel.tsx** | Fully hardcoded — no `useAnalysis`/`useEmployeeRisk` import at all; a fixed "100/100 AI Integrity Score" that never changes regardless of what's uploaded | Yes — but content never reflects the current session |

### State management wiring quality
`state/employeeRiskStore.ts` is genuinely real-data-only (its own header: *"Data is always from real uploaded datasets — no demo employee rows"*), both builder functions map every field from an external API payload, and storage is versioned with stale-schema eviction — solid engineering. `state/dataConsistencyValidator.ts` is **not dead code** — it's wired live into `App.tsx:46`'s `useEffect`, and contains explicit `DEMO_SENTINEL_POPULATIONS`/`DEMO_SENTINEL_STRINGS` checks designed to catch demo-data leakage into the real UI — but a failed check only does `console.error(...)`; there is no user-facing block or warning banner if it ever fires.

### Is "Demo Mode" explicit, or silently baked in?
**There is no user-reachable Demo Mode toggle.** The two components that would constitute one — `DemoMode.tsx` and `PlatformWalkthrough.tsx` — are both orphaned (zero references anywhere outside their own files, confirmed not present in `App.tsx`'s page switch). Instead, two narrower and more consequential issues exist in the pages that *are* reachable: (1) the `estimateRiskSegments()` fallback — a real statistical projection, not demo data, but one that silently substitutes for true per-employee scoring in four different pages whenever employee-level scoring hasn't finished, distinguished from real data only by a small italic caption; and (2) `TrustPanel.tsx`, reachable from the main nav, presents as a live governance dashboard but is entirely static — its "100/100 integrity score" never reflects the uploaded dataset at all, which could mislead a reviewer into thinking it's session-derived.

---

## 7. Security & Auth Reality

**`AWI_AUTH_ENFORCED` default:** `backend/core/security_middleware.py:24`: `return os.environ.get("AWI_AUTH_ENFORCED", "true").lower() != "false"` — defaults to **enforced** when the env var is unset. That part of the code is a secure default.

**But this enforcement is never applied to the endpoints that actually do anything.** `security_middleware.py`'s `get_current_user`/`require_role`/`optional_auth` are imported and used only inside `backend/api/auth_routes.py` (`auth_routes.py:23-27`) — i.e. they protect the `/api/auth/*` endpoints themselves (user management, audit log, etc.). They are **never imported or referenced anywhere in `local_analysis_routes.py`** (grepped, confirmed) — the file whose own docstring says outright (`local_analysis_routes.py:4`): *"Single-machine, no-auth, no-tenant endpoint for real local analysis."* Every endpoint a real user's browser calls — upload, analyze, employee scoring, exports, benchmarks, session history — has zero authentication checks in its handler code, regardless of `AWI_AUTH_ENFORCED`.

**The shipped React frontend never authenticates at all.** Grepped `executive-ui/src` for any reference to `/auth/`, `/login`, or an auth-related fetch call — **zero matches**. There is no login page among the 16 pages in `executive-ui/src/pages/`. A user opens the app and has immediate, unauthenticated access to upload data and every dashboard. The entire `local_auth.py` + `auth_routes.py` system — which is genuinely well-built (bcrypt cost-12 hashing, JWT with revocation tracking, 5-attempts/15-minute lockout, password-strength policy, full security audit log table — `local_auth.py:1-798`) — is a real, working backend capability that the product's own UI never calls.

**Admin bootstrap password:**
- `local_auth.py:706`: `bootstrap_admin(self, initial_password: str = "AWI@Admin2026!")` — a hardcoded default password exists in the function signature.
- But `main.py:112-120` only calls `bootstrap_admin()` when the `AWI_ADMIN_BOOTSTRAP_PASSWORD` env var is explicitly set and non-empty. **On a genuinely fresh, default deployment with no env vars configured, no admin account is created at all** — the hardcoded default password is never actually applied automatically. (This contradicts a naive "there's a hardcoded default password that's silently active" reading — the real issue is closer to the opposite: an unconfigured deployment has no way in until someone sets an env var or calls the endpoint below.)
- `auth_routes.py:403-424` exposes `POST /api/auth/bootstrap`, taking `initial_password` as a plain, **unauthenticated** parameter. It's idempotent (if an admin already exists it just returns that user's public info, not the password), but on a fresh install, whoever calls this endpoint first gets to set the admin password — a real first-caller-wins race if the API is network-reachable before an operator locks it down. The docstring self-acknowledges this ("Disable this endpoint in production after initial setup") but nothing in the code enforces that disablement.
- `must_change_pw` is tracked correctly server-side (`local_auth.py:109,542,610`) and returned to callers of `/api/auth/login`, but since the shipped frontend never calls `/api/auth/login` (see above), this control is never exercised by an actual product user.

---

## 8. Dependency & Environment Reality

**No virtual environment lives inside this repo** (no `venv/`, `.venv/`, or lockfile — just `requirements.txt`). Critically, `python` on this machine's PATH resolves to **a different project's virtualenv entirely** (`Enterprise_AI_Analyst\.venv`), while `py -3` resolves to a separate global install. This isn't a minor detail — it directly determines which of the §2 findings actually hold on this machine (see verification table below).

**Unused declared dependencies:** `statsmodels>=0.14.0` — zero real imports anywhere in the codebase; only referenced as a name in test files that pre-fake it as an empty module. `pyarrow`, `jinja2`, `python-multipart`, `cryptography` are declared but never imported *by name* — they're required transitively (Parquet I/O, pandas styling, FastAPI file uploads) so not truly dead, just indirectly used.

**Used but undeclared:** `pydantic` (imported directly in 3 backend/api files — low risk since fastapi pulls it in transitively anyway), and more importantly **`pytest` itself is never declared in `requirements.txt`** — a clean `pip install -r requirements.txt` gives no test runner at all. `httpx` (required by `fastapi.testclient.TestClient`, used in `tests/test_phase30_1_security.py`) is also undeclared — confirmed to raise `ModuleNotFoundError` if genuinely absent.

**Guarded optional imports — the pattern is used extensively and consistently** (main.py, local_analysis_routes.py, ml_router.py, automl_engine.py, biosignal_adapter.py, semantic_mapper.py, timeseries_engine.py, explainability_engine.py, executive_pptx_exporter.py, executive_report_exporter.py, local_auth.py, feature_trustworthiness.py, employee_risk_scoring.py, ml_validation_engine.py, and `frontend/app.py`'s own local-module fallback). One code-smell flagged: `explainability_engine.py`'s SHAP guard catches a broad `except (ImportError, Exception)` — functionally just `except Exception`, silently swallowing unrelated bugs as "SHAP unavailable."

**The single most consequential finding of this section, directly relevant to §2's ML-path tracing:** actual installed-package verification (both interpreters on this machine were queried directly with `pip list`/`pip show`) shows:

| Package | `python` → Enterprise_AI_Analyst venv | `py -3` → global Python 3.13 |
|---|---|---|
| xgboost | **Not installed** | Installed |
| lightgbm | **Not installed** | Installed |
| catboost | **Not installed** | Installed |
| imbalanced-learn (SMOTE) | **Not installed** | Installed |
| shap | **Not installed** | Installed |
| fastapi / uvicorn / streamlit / python-pptx / openpyxl | Installed (all) | Installed (all) |

**In the environment that `python` resolves to, `ml_router.py`'s entire premise — XGBoost/LightGBM/CatBoost ensemble with SMOTE-in-CV-folds — silently degrades to whatever plain-sklearn + no-oversampling fallback its guards provide, with no error and no visible warning.** Combined with §2's finding that `ml_router.py` isn't even reached by the shipped frontend, this means the "sophisticated" ML story described across the repo's `.md` documentation depends on a specific interpreter (`py -3`, the global install) that happens to have every optional package present — not something the codebase itself guarantees or checks for at deploy time. Collection sanity check: `python -m pytest --collect-only -q` succeeded from the `Enterprise_AI_Analyst` venv (1153 tests collected, no crash) — confirming the `_HAS_*` guard pattern does work as designed to prevent hard failures, it just silently changes what the system actually does.

---

## 9. Dead Code & Redundancy Inventory

`backend/core/` contains **81 `.py` files** (80 modules + `__init__.py` — corrects an earlier estimate of 89). Full reachability was computed by BFS over the internal import graph starting from the three live entry files: `main.py`, `local_analysis_routes.py`, `auth_routes.py`. Result: **49 modules LIVE, 32 not reachable** (dead-in-production or test-only).

**Confirms §1: `backend/api/enterprise_routes.py`, `report_routes.py`, and `upload_routes.py` are all real, unmounted, orphaned router files** — and they drag a cluster of otherwise-working `backend/core/` modules down with them: `artifact_registry.py`, `audit_logger.py`, `audit_package_builder.py`, `executive_report_exporter.py`, `export_safety.py`, `report_localization.py`, `demo_company_generator.py` (partially — also referenced from test-only code).

**A second, distinct dead cluster belongs only to the Streamlit app** (`frontend/app.py` / `frontend/utils/session_state.py`), not the FastAPI stack: `calibration_engine.py`, `confidence_engine.py`, `confidence_governance.py`, `ethical_ai.py`, `explainability_engine.py` (a *different* module from the live `employee_explainability_engine.py` — easy to confuse), `feature_trustworthiness.py`, `report_generator.py` (§3), `timeseries_engine.py`. These are real, working, and exercised — just not by the React product.

**A third cluster is genuinely unreferenced by any application code, live or otherwise** — only by standalone debug scripts or nothing at all: `automl_engine.py` (zero references anywhere), `drift_monitor.py` and `governance_logger.py` (referenced only by `_smoke_test.py`).

**Governance module verdicts — a more granular read than §5's, consistent with it:** this section traces reachability from the *mounted API surface* (is the code path live at all), while §5 additionally traced whether the *shipped React frontend* ever exercises that path. Both are true simultaneously and worth holding together:
- `leakage_detector.py`, `model_validator.py`, `model_truth_audit.py`: **LIVE by reachability** — genuinely imported and invoked inside `ml_router.py`'s training path, which `main.py`'s mounted `/api/v1/analyse` endpoint calls. **But per §2/§5, `/api/v1/analyse` is never called by executive-ui** — so "live" here means "real, working, and running if that endpoint is hit," not "exercised by a user of the shipped product."
- `saudi_data_governance.py`, `enterprise_language_guard.py`: dead by both measures — no path from any live entry file reaches either one, only test files and other already-dead modules.

### Root-level utility scripts

| Script | What it actually does | CI/CD wiring |
|---|---|---|
| `_smoke_test.py` | Imports a list of modules (several already confirmed dead, e.g. `confidence_governance`, `calibration_engine`, `drift_monitor`) and runs an ad hoc pipeline simulation, printing PASS/FAIL to stdout | None |
| `_trace_target.py` | One-off debug script tracing a dtype bug through the routing pipeline | None |
| `_audit_scan.py` | Greps the repo for forbidden literal strings (hardcoded USD figures, causal language, stack-trace leaks) | None |
| `_validate_routing.py` | Builds synthetic dataframes and asserts `AdaptiveRouter.route()` classifies them correctly | None |
| `generate_proof.py` | Generates a PPTX/HTML board report from **hardcoded mock data**, then self-asserts required text/branding is present as a "proof" artifact | None |
| `debug_nav.mjs`, `take_html_screenshots.mjs`, `take_pdf_screenshot.mjs`, `take_phase33_1_screenshots.mjs`, `take_screenshots.mjs`, `verify_phase33_2*.mjs` (×3) | Playwright scripts that screenshot saved HTML files or drive the dev server manually | None |

**No CI/CD wiring exists for any of these, or for anything else in the repo.** No `.github/workflows/`, no `azure-pipelines.yml`, `.gitlab-ci.yml`, or `Jenkinsfile` anywhere. `pytest.ini` scopes collection to `tests/` only — explicitly excluding every root-level `_*.py` and `test_*.py` script. `executive-ui/package.json`'s scripts are just `dev`/`build`/`preview` — none of the `.mjs` verification scripts are referenced from anywhere. These are all standalone, manually-run developer scripts, not an automated pipeline of any kind — despite several of them being named `verify_*` in a way that could suggest otherwise.

---

## 10. Data Reality

### Precision metrics found — provenance trace

| Metric | Location | Traced to computation? | Input dataset |
|---|---|---|---|
| ROC-AUC 0.8205 (baseline) | `BASELINE_CONSERVATIVE_ML_RESULTS.json:15`, referenced in `scripts/phase29_5_model_search.py:131` | UNVERIFIED — the script that would have *generated* this baseline JSON is not in the repo, only code that reads/compares against it. Its structure matches the real CV harness format, so it's plausibly genuine, but unconfirmable. | Claimed: "Original Dataset of Employee Attrition (Saudi), n=1191" |
| ROC-AUC **0.8471**, MCC 0.4942, F1 0.7073 (VotingEnsemble, "best model") | `BEST_MODEL_PHASE29_5.json:9`, `MODEL_SEARCH_RESULTS_PHASE29_5.csv` row 14 | **CONFIRMED TRACED.** Full source present: `scripts/phase29_5_model_search.py`. CV in `run_cv_eval()` (lines 441-493), ensemble at 1157-1178, written at line 922. | Loaded via `find_dataset()` (script lines 194-202) — first candidate path is `C:\Users\PvP-Pc\Desktop\datasetssaudi\Original Dataset of Employee Attrition (1).xlsx`, a file **outside the repo entirely**, on the developer's own Desktop. |
| Other 13 model rows in the CSV | `MODEL_SEARCH_RESULTS_PHASE29_5.csv` | CONFIRMED TRACED — same script, same run | Same external file |
| `n=1191` cited throughout | Multiple docs/tests | CONFIRMED — matches the actual row count of the external xlsx (verified directly) | Same external file |

### Data file inventory
- **`datasets/`, `datasets/saudi/`, `data/uploads/`, `data/outputs/` — all empty.** The repo's own "official" data directories contain nothing.
- **`test_employee_data.csv`** (200×11, synthetic-looking sequential IDs) — zero references anywhere in the code. An orphaned, unused fixture.
- **The actual training data lives outside the repository**, at `C:\Users\PvP-Pc\Desktop\datasetssaudi\Original Dataset of Employee Attrition (1).xlsx` — verified directly: 1191 rows × 35 columns, messy real-world-looking column names (trailing/leading spaces, an NBSP character) that byte-for-byte match the artifacts hardcoded in `backend/core/saudi_attrition_normalizer.py:38-75`. It is **not** the public Kaggle IBM HR dataset (different columns, different filename) and **not** output from the repo's own synthetic generator (`demo_company_generator.py`, confirmed fully synthetic via `np.random.default_rng` and an explicit `DEMO_MODE=True` attribute). But it sits in a personal folder alongside other clearly-practice/scraped datasets — including the actual public Kaggle IBM HR file under its canonical filename (`WA_Fn-UseC_-HR-Employee-Attrition.csv`), one directory up. No source attribution, client name, or business-relationship record exists anywhere for this file.

### SQLite database inspection
- **`awi_tenants.db`: 0 rows in every table.** No tenant/client account has ever been created in this system.
- **`data/awi_auth.db`: 0 rows in every table.** No user has ever logged in — consistent with §7's finding that the shipped frontend never calls the auth system.
- **`data/local_intelligence.db`: 9 session rows, all referencing the exact same file** (`"Original Dataset of Employee Attrition (1).xlsx"`, identical `dataset_hash='9a44efec36c46706'` every time), spanning roughly seven weeks. No other filename or client name appears anywhere.
- **`awi_history.db`: 7 snapshot rows, all with identical derived stats** (`workforce_stability_index=66.5`, `avg_risk_score=33.5` every row) and, oddly, `ml_auc=1.0/mcc=1.0/f1=1.0` in every row — placeholder-looking perfect scores inconsistent with the real 0.8471 AUC found above, a data-quality red flag isolated to this specific table.

### Verdict: has real, non-synthetic, non-public client data ever been processed?
**CONFIRMED NO for a "client"** in any commercial sense — `awi_tenants.db` and `data/awi_auth.db` are completely empty, so there is no mechanism by which any external party could have used this system. The only substantive dataset ever run through the pipeline is one static Excel file, processed nine times by a single `default` tenant over seven weeks — a developer repeatedly re-testing one file, not multiple client engagements.

**The origin of that one file itself is UNVERIFIED.** It's structurally real-looking (dirty headers, free-text salary ranges, binned ages) and isn't the public IBM dataset or the repo's own synthetic generator — but it carries zero source attribution anywhere in code, docs, or database records, and sits on a personal Desktop next to other obviously-practice datasets including the actual public Kaggle file. `REAL_SAUDI_DATASET_VALIDATION_REPORT.md`'s structural claims about this file (row/column counts, dirty headers, salary-range format) check out against the real file. Its claim that this is data from "a Saudi HR organisation" is **unverifiable from the repository alone** — nothing in the code or databases confirms or refutes that provenance claim.

---

## Top 5 Engineering Risks (for a technical buyer or investor)

**1. There is no authentication on the product a user actually runs, despite a fully-built auth system existing in the codebase.** `local_auth.py`/`auth_routes.py` implement real bcrypt hashing, JWT with revocation, lockout, and audit logging — but the shipped React frontend never calls `/api/auth/login` (zero references, confirmed by grep), and the actual data endpoints (`local_analysis_routes.py`, explicitly documented in its own source as "no-auth, no-tenant") have no auth check regardless of the `AWI_AUTH_ENFORCED` flag. Anyone who can reach the app can upload data and generate reports with zero login. This is the single most severe finding for any deployment beyond a developer's own laptop.

**2. The ML sophistication described in the repo's own documentation depends on which frontend and which Python environment you happen to be running.** The shipped React app's live ML path (`ml_validation_engine.py`) uses only LogisticRegression/RandomForest/GradientBoosting with no SMOTE — methodologically sound, but far simpler than `ml_router.py`'s XGBoost/LightGBM/CatBoost/SMOTE-in-CV-folds pipeline, which is only reachable via a disabled-by-default Streamlit app or an API endpoint the frontend never calls. Worse, on this machine's own default `python` environment, xgboost/lightgbm/catboost/imbalanced-learn/shap are **not even installed** — so even someone who found and hit that endpoint would silently get degraded sklearn fallbacks, not the advertised ensemble.

**3. Of six named governance/compliance modules, two are completely dead code and three more never reach the product a user sees.** `saudi_data_governance.py` and `enterprise_language_guard.py` are unreachable from any live entry point — real code, but disconnected. `leakage_detector.py`, `model_validator.py`, and `model_truth_audit.py` are genuinely invoked, but only inside the ML path from finding #2 that the shipped frontend doesn't use — and even there, their computed verdicts are silently discarded before the API response is built (`main.py`'s `/api/v1/analyse` never reads `ml_res.leakage_report`/`validation_report`/`truth_audit_report`). The governance behavior end users actually experience comes from separate, duplicated, ad hoc keyword-matching logic written independently in at least three different files.

**4. The provenance of the one real dataset this system has ever processed cannot be verified from the repository, and no client/tenant has ever used the product.** `awi_tenants.db` and the auth database are completely empty — zero accounts ever created. The only substantive data ever run through the pipeline is a single external Excel file (1191×35, hash-identical across all nine recorded sessions) that lives outside the repo on the developer's personal Desktop, next to other clearly-practice datasets including the actual public Kaggle IBM HR file. The commercial and provenance claims made throughout the ~150 root `.md` documents about this data are not independently verifiable one way or the other — the structural claims check out, but "real Saudi client data" as a business claim does not have supporting evidence in the code or databases.

**5. Widespread, genuine content duplication across the report-generation and governance-detection layers signals a codebase that grew by copy-paste extension rather than refactoring — a maintenance/drift risk, not just a tidiness one.** Three live report exporters (PDF board-report branch, PPTX, HTML slides) independently hard-code the identical financial formula and contain fallback narrative sentences that have visibly drifted apart from a shared original. The same pattern repeats in governance: PII/leakage detection is implemented three separate times (`SecureFileIngestion`, `ml_validation_engine.py`'s own keyword lists, and the orphaned `leakage_detector.py`). Every future change to a business rule (the financial formula, an exclusion keyword) has to be made correctly in multiple places by hand, and the drift already visible between the copies shows that isn't happening reliably today.
