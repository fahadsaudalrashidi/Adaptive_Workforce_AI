# Scientific Reproducibility Report
**Platform:** Adaptive Workforce Intelligence Engine v2.4.0  
**Updated:** 2026-05-19  
**Purpose:** Ensure every important result can be independently reproduced and verified.

---

## Reproducibility Philosophy

> "A result that cannot be reproduced is not a result — it is a coincidence."

The platform must produce identical outcomes when given identical inputs. Every deviation must be explained by intentional randomness (cross-validation folds, train/test splits) or documented environment differences.

---

## Reproducibility Tracking Components

### 1. Dataset Fingerprinting
**Module:** `backend/core/drift_monitor.py` → `DriftMonitor.set_baseline()`  
**Method:** SHA-256 hash of column names + shape + first 5 rows  
**Usage:** Compare `dataset_hash` across runs to verify same input data

```python
from backend.core.drift_monitor import get_drift_monitor
monitor = get_drift_monitor()
baseline = monitor.set_baseline(df, dataset_type="hr_attrition")
print(baseline.dataset_hash)  # e.g., "a3f2c9d1e8b7..."
```

**Limitation:** Hash is not deterministic for floating-point columns with different precision. A full MD5/SHA of the serialized CSV is more robust for production.

---

### 2. Random Seed Governance

**Current state:** Partial.

| Component | Random State | Fixed? |
|-----------|-------------|--------|
| `MLRouter.train()` | `random_state=42` in `RandomizedSearchCV` | YES |
| `StratifiedKFold` | `random_state=42` | YES |
| `train_test_split` | `random_state=42` | YES (check in ml_router.py) |
| `SMOTE` | `random_state=42` | YES |
| `numpy.random` | Not globally fixed | NO — risk |
| `random` module | Not globally fixed | NO — risk |
| Python hash randomization | OS-dependent | NO — risk |

**Action needed for full reproducibility:**
```python
import random, numpy as np
random.seed(42)
np.random.seed(42)
# For Python hash seed: set PYTHONHASHSEED=42 in environment
```

---

### 3. Preprocessing Version Tracking

**Current version string:** `v2.4.0-preprocessing`  
**Tracked in:** `backend/core/feature_factory.py` → `FeatureFactory.manifest`

The `FeatureEngineeringManifest` records:
- `features_added`: list of engineered features
- `transformations_applied`: list of transforms (imputation, encoding, etc.)
- `dropped_features`: columns dropped during healing
- `dataset_type`: routing-determined type

**Gap:** No version hash of the preprocessing code itself. A code change to `feature_factory.py` would produce different features without changing the version string.

**Recommended:** Hash the source of `feature_factory.py` at startup and store in the manifest.

---

### 4. Model Version Tracking

| Component | Version Tracked | Method |
|-----------|----------------|--------|
| Best model type | YES | `MLResult.best_model_name` |
| Hyperparameters | YES | `MLResult.models[name].hyperparams` |
| Training AUC | YES | `MLResult.best_metric_value` |
| OOF predictions | YES (if available) | `ModelResult.oof_predictions` |
| Feature names | YES | `MLResult` feature_names |
| Governance version | NO | Not stored in MLResult |

**Recommended addition to `MLResult`:**
```python
governance_version: str = "v2.4.0"
preprocessing_hash: Optional[str] = None
dataset_hash: Optional[str] = None
```

---

### 5. Governance Version Tracking

**Current governance version:** `v2.4.0`  
**Tracked by:** `ConfidenceGovernor` formula weights  
**Stored:** NOT currently persisted in analysis results

**Gap:** If governance formula weights change between v2.3.0 and v2.4.0, a re-analysis of the same dataset will produce a different `model_reliability_score`. This is correct behavior but must be documented.

**Recommended:** Store `governance_version: "v2.4.0"` in `UnifiedConfidenceReport`.

---

### 6. Calibration Version Tracking

**Current calibration version:** `v2.4.0`  
**Method:** Brier score + ECE from OOF predictions  
**Thresholds:** `BRIER_GOOD=0.10`, `BRIER_MODERATE=0.18`, `ECE_GOOD=0.05`, `ECE_MODERATE=0.10`

If thresholds change, the same analysis will produce a different `CalibrationQuality` label. Track threshold version in `CalibrationReport`.

---

## Known Non-Determinism Sources

### Acceptable Non-Determinism
| Source | Why Acceptable |
|--------|---------------|
| Cross-validation fold order | `random_state=42` fixed — deterministic |
| RandomizedSearchCV | `random_state=42` fixed — deterministic |
| SMOTE synthetic samples | `random_state=42` fixed — deterministic |

### Uncontrolled Non-Determinism (Action Needed)
| Source | Impact | Fix |
|--------|--------|-----|
| `numpy.random` global state | Minor — affects some estimators | Add `np.random.seed(42)` at session start |
| Python hash randomization | Minor — dict/set ordering | Set `PYTHONHASHSEED=42` |
| LightGBM/XGBoost thread parallelism | Minor — float rounding | Add `n_jobs=1` for reproducibility or accept minor differences |

---

## Reproducibility Audit Protocol

Run this checklist before claiming a result is reproducible:

```
1. Record dataset hash:    DriftMonitor.set_baseline(df) → baseline.dataset_hash
2. Record random seed:     numpy.random.seed(42); random.seed(42)
3. Record preprocessing:   manifest.features_added, manifest.transformations_applied
4. Record model:           ml_res.best_model_name, ml_res.best_metric_value
5. Record governance:      ucr.model_reliability.score, governance_version="v2.4.0"
6. Record calibration:     cal_rep.quality, cal_rep.brier_score
7. Log the run:            GovernanceLogger.log_reproducibility(...)
```

The `GovernanceLogger.log_reproducibility()` method captures all 6 components in a single structured event to `logs/governance.jsonl`.

---

## Reproducibility Gap Register

| Gap ID | Description | Severity | Fix ETA |
|--------|-------------|----------|---------|
| RP-01 | Global numpy/random seeds not fixed | MEDIUM | Pre-production |
| RP-02 | No feature_factory source hash | MEDIUM | v2.5 |
| RP-03 | governance_version not stored in UnifiedConfidenceReport | LOW | v2.5 |
| RP-04 | MLResult does not store dataset_hash | MEDIUM | v2.5 |
| RP-05 | PYTHONHASHSEED not documented in deployment guide | LOW | Docker setup |

---

## How to Reproduce a Previous Run

Given a `logs/governance.jsonl` entry:
```json
{
  "event_type": "REPRODUCIBILITY",
  "details": {
    "dataset_hash": "a3f2c9d1e8b7...",
    "random_seed": 42,
    "preprocessing_version": "v2.4.0-preprocessing",
    "model_version": "v2.4.0",
    "governance_version": "v2.4.0"
  }
}
```

Steps to reproduce:
1. Upload the same dataset (verify hash matches)
2. Run: `py -3 -m streamlit run frontend/app.py --server.port 8510`
3. Ensure platform version is v2.4.0 (check PLATFORM_VERSION in settings.py)
4. Run analysis — results should be identical within floating-point precision

---

## Reproducibility Statement for Executive Reports

All HR reports generated by this platform include the following statement in the Scientific Validity section:
> "Model trained on uploaded dataset only. Results are specific to the provided data and should not be generalized beyond this organization without revalidation."

This is the correct scientific scope claim. Never claim results generalize to future data or other organizations without revalidation.
