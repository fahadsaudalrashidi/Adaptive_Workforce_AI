# Environment Health Report
**Platform:** Adaptive Workforce Intelligence Engine v2.4.0  
**Generated:** 2026-05-19  
**Python:** 3.13.13 (Windows 11, AMD64)

---

## Runtime Environment

| Component | Version | Status |
|-----------|---------|--------|
| Python | 3.13.13 | OK |
| pandas | 3.0.2 | WARN — see compatibility notes |
| numpy | 2.4.4 | WARN — see compatibility notes |
| scikit-learn | 1.8.0 | OK |
| streamlit | 1.57.0 | OK |
| plotly | 6.7.0 | OK |
| fastapi | 0.136.1 | OK |
| uvicorn | 0.46.0 | OK |
| scipy | 1.17.1 | OK |
| shap | 0.51.0 | OK |
| pyarrow | 24.0.0 | OK |
| xgboost | 3.2.0 | OK |
| lightgbm | 4.6.0 | OK |

---

## Active Compatibility Risks

### RISK-01 — pandas 3.x StringDtype / ArrowDtype
**Severity:** HIGH  
**Description:** pandas 3.x uses `StringDtype` backed by PyArrow for string columns by default. Calling `.values` on such columns returns an `ArrowExtensionArray`, not a plain `numpy.ndarray`. This causes crashes in sklearn's `train_test_split` and other estimators that expect numpy arrays.

**Status:** FIXED in `backend/core/ml_router.py` — `.to_numpy(dtype=object, na_value=None)` used instead of `.values`.

**Remaining risk:** 57 `.values` calls across 10 backend files. Most are on numeric columns (safe), but any that access string columns on pandas 3.x data may silently return ArrowExtensionArrays.

**Files to monitor:** `leakage_detector.py` (10), `biosignal_adapter.py` (5), `data_healer.py` (4), `adaptive_router.py` (4).

**Mitigation:** When accessing columns that may be string-typed in pandas 3.x, always use `.to_numpy(dtype=object, na_value=None)` or `.to_list()`.

---

### RISK-02 — numpy 2.x Removed Type Aliases
**Severity:** MEDIUM  
**Description:** NumPy 2.0 removed `np.bool`, `np.int`, `np.float`, `np.complex`, `np.object`, `np.str` (all without trailing underscore). Any code using these will raise `AttributeError` at runtime.

**Status:** No instances found in backend code. All clear.

**Ongoing check:** Run `grep -rn "np\.(bool|int|float|complex|object|str)\b" backend/` before any numpy upgrade.

---

### RISK-03 — scikit-learn 1.5+ Behavioral Changes
**Severity:** LOW  
**Description:** scikit-learn 1.5+ changed verbose output format for `RandomizedSearchCV`. `check_is_fitted` now raises `NotFittedError` with more context. These are cosmetic/logging changes and do not affect model results.

**Status:** No action needed. Monitor release notes for 1.6+.

---

### RISK-04 — Streamlit Session State and Multi-Page Architecture
**Severity:** MEDIUM  
**Description:** Streamlit 1.x session_state is not thread-safe for multi-user deployments. All 45+ session_state keys are set from a single `app.py` analysis pipeline. If two users upload simultaneously, state can collide.

**Status:** Known limitation of Streamlit's single-process architecture. Acceptable for demo/pilot. Production requires authentication layer (P1 blocker) + Redis session store.

---

### RISK-05 — PyArrow 24.0 + pandas 3.0 Integration
**Severity:** LOW  
**Description:** PyArrow 24.0 is the backend for pandas 3.x StringDtype. The version combination is tested and stable. However, cross-platform CSV export of ArrowDtype columns may behave differently on Linux vs Windows.

**Status:** Monitor. No issues detected in current test suite.

---

## Dependency Lock Strategy

### Current State
No `requirements.txt` version pins. Dependencies resolved from environment at install time.

### Recommended Lock Process
```
# 1. Export current working environment
pip freeze > requirements-lock.txt

# 2. Pin in requirements.txt (minimum viable pins)
pandas>=3.0.2,<4.0
numpy>=2.4.4,<3.0
scikit-learn>=1.8.0,<2.0
streamlit>=1.57.0,<2.0
plotly>=6.0.0,<7.0
fastapi>=0.136.0,<1.0
pyarrow>=24.0.0,<25.0
xgboost>=3.0.0,<4.0
lightgbm>=4.0.0,<5.0
shap>=0.50.0,<1.0
scipy>=1.17.0,<2.0
uvicorn>=0.46.0,<1.0
```

### Known Dangerous Upgrades
| Package | Safe Range | Breaking Change Risk |
|---------|-----------|---------------------|
| pandas | 3.x only | 4.x expected to remove more legacy behavior |
| numpy | 2.x only | 3.x will remove further aliases |
| streamlit | 1.x | 2.x may break session_state API |
| scikit-learn | 1.5–1.9 | 2.0 expected to break pipeline API |
| xgboost | 3.x | 4.x may change booster API |

---

## Reproducibility Notes

### Random Seed Governance
- Random seed is NOT currently fixed globally. sklearn's RandomizedSearchCV uses `random_state=42` (hardcoded in `ml_router.py`).
- To ensure full reproducibility: add `numpy.random.seed(42)` and `random.seed(42)` at session start.

### Dataset Fingerprinting
- `DriftMonitor.set_baseline()` computes a SHA-256 hash of dataset shape + sample. Use this to verify the same dataset was used across runs.

### Environment Capture
```python
# Capture current environment for a run
import json, platform, sys
env_snapshot = {
    "python": sys.version,
    "platform": platform.platform(),
    "packages": {p: v for p, v in [("pandas", pd.__version__), ("numpy", np.__version__)]},
}
```

---

## Required Pre-Production Actions

1. **Create `requirements.txt`** with pinned versions (see above)
2. **Create `requirements-dev.txt`** for test dependencies
3. **Add CI/CD step** to validate `pip install -r requirements.txt` on clean environment
4. **Fix `.values` calls** in `leakage_detector.py` (10 occurrences) — highest risk file
5. **Add Docker** for reproducible deployment environment

---

## Next Environment Health Audit
Schedule: Before every production release and after any major package upgrade.
