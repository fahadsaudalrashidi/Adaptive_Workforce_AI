# Dependency Risk Report
**Platform:** Adaptive Workforce Intelligence Engine v2.4.0  
**Generated:** 2026-05-19  
**Risk Assessment:** Enterprise deployment dependency audit

---

## Risk Summary

| Risk ID | Package | Risk | Severity | Status |
|---------|---------|------|----------|--------|
| DR-01 | pandas 3.x | ArrowDtype .values crash | HIGH | FIXED (ml_router) |
| DR-02 | numpy 2.x | Removed type aliases | MEDIUM | CLEAR |
| DR-03 | streamlit 1.x | No multi-user session isolation | HIGH | OPEN (auth blocker) |
| DR-04 | shap 0.51 | TreeExplainer API changes | MEDIUM | OPEN (G1 backlog) |
| DR-05 | lightgbm 4.6 | C++ backend optional | LOW | CLEAR |
| DR-06 | xgboost 3.2 | GPU build separate | LOW | CLEAR |
| DR-07 | fastapi 0.136 | Pydantic v2 required | MEDIUM | OPEN |
| DR-08 | No lock file | Non-reproducible installs | HIGH | OPEN |

---

## Detailed Risk Analysis

### DR-01 — pandas 3.x ArrowDtype (FIXED)

**Impact:** sklearn pipelines crash when receiving PyArrow-backed arrays.  
**Root cause:** `pd.rng.choice(["Yes", "No"], n)` creates `StringDtype(storage="pyarrow")` by default in pandas 3.x. `.values` returns `ArrowExtensionArray` instead of `numpy.ndarray`.  
**Fix applied:** `ml_router.py` uses `.to_numpy(dtype=object, na_value=None)`.  
**Remaining exposure:** 57 `.values` calls in other files — most are numeric (safe), but `leakage_detector.py` (10 uses) should be reviewed before processing string-heavy datasets.

**Test coverage:** `tests/test_routing_regression.py` covers this end-to-end.

---

### DR-02 — numpy 2.x Removed Aliases (CLEAR)

**Impact:** `AttributeError` at runtime if deprecated aliases used.  
**Removed:** `np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str`.  
**Status:** Audit found zero instances in backend code. Clean.  
**Prevention:** Add pre-commit or CI lint rule: `grep -rn "np\.(bool|int|float)\b"`.

---

### DR-03 — Streamlit 1.x Session Isolation (OPEN — Auth Blocker)

**Impact:** Multiple simultaneous users share session_state in single-process Streamlit.  
**Risk:** User A's analysis overwrites User B's session during concurrent uploads.  
**Severity:** CRITICAL for multi-user production.  
**Current mitigation:** Acceptable for single-user demo/pilot.  
**Resolution path:** Add authentication (P1) + Redis/DB session store.

---

### DR-04 — SHAP 0.51 API Changes (OPEN — G1 Backlog)

**Impact:** `ExplainabilityEngine` has SHAP hooks but uses sklearn feature importances as fallback.  
**Risk:** SHAP 0.51 changed `TreeExplainer` return type for multi-class models.  
**Status:** SHAP not yet fully wired. G1 backlog item (SHAP integration).  
**Action needed:** Test `TreeExplainer(model).shap_values(X)` with xgboost 3.2 before enabling.

---

### DR-05 — LightGBM 4.6 C++ Backend (CLEAR)

**Impact:** LightGBM requires native C++ libraries.  
**Status:** Installed and functional. No issues detected.  
**Windows note:** Requires Visual C++ Redistributable 2019+. Ensure in Docker image.

---

### DR-06 — XGBoost 3.2 (CLEAR)

**Impact:** XGBoost 3.x changed GPU build separation.  
**Status:** CPU-only build installed. No GPU dependency. Clean.

---

### DR-07 — FastAPI 0.136 + Pydantic v2 (OPEN)

**Impact:** FastAPI 0.136 requires Pydantic v2. Pydantic v2 changed `.dict()` → `.model_dump()`, `.json()` → `.model_json()`.  
**Status:** `api/main.py` uses simple dicts (no Pydantic models yet). Risk is latent.  
**Action needed:** When adding Pydantic request/response models to the API, use Pydantic v2 API.

---

### DR-08 — No Dependency Lock File (OPEN — HIGH)

**Impact:** Different developers/environments may install incompatible package versions.  
**Risk:** A pandas 4.x or numpy 3.x release could silently break the platform on fresh install.  
**Resolution:**
```
pip freeze > requirements-lock.txt
```
Then create `requirements.txt` with bounded version pins (see ENVIRONMENT_HEALTH.md).

---

## Import Graph Risk

### Known Circular Import Risks
No circular imports detected in current codebase. Key import order:
```
config.settings                   (no internal deps)
  ↓
backend.core.dataset_contract     (imports settings)
  ↓
backend.core.adaptive_router      (imports contract)
  ↓
backend.core.ml_router            (imports router)
  ↓
frontend.app                      (imports everything)
```

### Potential Hidden Coupling
- `frontend/pages/biosignal_page.py` duplicates `_contract()` and `_build_csv_export()` from `app.py` — acceptable for module isolation but creates maintenance divergence if app.py logic changes.
- `frontend/pages/explainability_page.py` duplicates `_require_analysis()` from `app.py`.
- **Action:** Create `frontend/utils/session_helpers.py` with `get_contract()`, `require_analysis()` as shared utilities.

---

## Anti-Entropy Findings

### Duplicated Internal Helpers

| Helper | Files | Risk | Action |
|--------|-------|------|--------|
| `_clamp()` | `confidence_governance.py`, `feature_factory.py` | Low — independent use | Document, no change needed |
| `_band()` | `confidence_governance.py`, `dataset_confidence_engine.py` | Medium — may diverge | Move to shared `backend/core/score_utils.py` in v2.5 |
| `_contract()` | `app.py`, `biosignal_page.py` | Low — module isolation | Move to `frontend/utils/session_helpers.py` |
| `_build_csv_export()` | `app.py`, `biosignal_page.py` | Low — biosignal variant only uses biosignal branch | Acceptable |
| `_require_analysis()` | `app.py`, `explainability_page.py` | Low — simple wrapper | Move to `frontend/utils/session_helpers.py` |

### Stale Session State Keys
All 45 session_state keys are accounted for. Keys set via `st.session_state.update()` in the upload and analysis pipelines, and consumed in page modules. No orphaned keys found.

---

## Recommended Immediate Actions (P1-P3)

1. **Create `requirements.txt`** — pin all deps to working versions (30 minutes)
2. **Fix `_band()` duplication** — merge into shared utility module (2 hours)
3. **Create `frontend/utils/session_helpers.py`** — consolidate `_contract()`, `_require_analysis()` (1 hour)
4. **Test `leakage_detector.py` .values calls** with pandas 3.x string columns (1 hour)
5. **Add pytest-env and dependency checks** to CI when CI is set up
