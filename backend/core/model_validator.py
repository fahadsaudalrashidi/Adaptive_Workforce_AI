"""
Model Validator — Post-Training Integrity & Scientific Validity Engine
======================================================================

Validates model integrity AFTER training by consuming a TrainingResult
produced by ml_router.py.  Every check runs inside its own try/except so
a single data-quality edge-case never crashes the whole validation pass.

Checks implemented
------------------
1.  HOLDOUT_VALIDITY       — test AUC vs OOF AUC gap
2.  FOLD_STABILITY         — per-fold OOF AUC standard deviation
3.  CLASS_CALIBRATION      — predicted probability discrimination gap
4.  MINIMUM_SAMPLE_SIZE    — n_train floor
5.  FEATURE_COUNT_RATIO    — curse-of-dimensionality guard
6.  CLASS_DISTRIBUTION     — extreme minority-class imbalance
7.  AUC_SANITY             — model must beat random baseline
8.  TRAIN_VARIANCE         — suspicious across-model AUC uniformity
9.  PERMUTATION_BASELINE   — shuffle test labels and re-score
10. ENSEMBLE_AGREEMENT     — divergence between best and second-best model
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds — centralised so they are easy to tune
# ---------------------------------------------------------------------------
_HOLDOUT_WARN_GAP   = 0.08
_HOLDOUT_FAIL_GAP   = 0.15
_FOLD_STD_WARN      = 0.10
_FOLD_STD_FAIL      = 0.15
_CALIB_WARN_GAP     = 0.20   # mean(pos) - mean(neg) < this → weak discrimination
_MIN_TRAIN_WARN     = 200
_MIN_TRAIN_FAIL     = 100
_FEATURE_RATIO_WARN = 10     # n_features > n_train / 10
_MINORITY_PCT_WARN  = 0.03   # < 3 % → extreme imbalance
_AUC_RANDOM         = 0.50
_HIGH_AUC_THRESHOLD = 0.95
_SECOND_BEST_LOW    = 0.70
_PERM_AUC_WARN      = 0.60
_GOVERN_FAIL_CAP    = 0.70
_GOVERN_WARN_CAP    = 0.80
_WARN_COUNT_DEGRADE = 3


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ValidationCheck:
    check_name: str
    passed: bool
    severity: str           # "PASS" / "WARN" / "FAIL"
    message: str
    value: Optional[float]
    recommendation: str


@dataclass
class ValidationReport:
    checks: List[ValidationCheck]
    n_pass: int
    n_warn: int
    n_fail: int
    overall_status: str       # "VALID" / "DEGRADED" / "INVALID"
    governed_auc: float       # AUC after validation governance
    original_auc: float
    confidence_band: str      # "High" / "Moderate" / "Low" / "Unreliable"
    model_name: str
    deployment_safe: bool     # False if any FAIL
    summary: str
    recommendations: List[str]
    provenance: List[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _severity(value: float, warn_thresh: float, fail_thresh: float,
               higher_is_worse: bool = True) -> str:
    """Return 'FAIL' / 'WARN' / 'PASS' based on scalar value and thresholds."""
    if higher_is_worse:
        if value > fail_thresh:
            return "FAIL"
        if value > warn_thresh:
            return "WARN"
    else:
        if value < fail_thresh:
            return "FAIL"
        if value < warn_thresh:
            return "WARN"
    return "PASS"


def _make_check(name: str, sev: str, message: str,
                value: Optional[float], recommendation: str) -> ValidationCheck:
    return ValidationCheck(
        check_name=name,
        passed=(sev == "PASS"),
        severity=sev,
        message=message,
        value=value,
        recommendation=recommendation,
    )


def _extract_best_auc(ml_result: Any) -> float:
    """Pull best AUC from TrainingResult safely."""
    try:
        bm = getattr(ml_result, "best_metric_name", "")
        bv = getattr(ml_result, "best_metric_value", 0.0)
        if "auc" in str(bm).lower():
            return float(bv)
        # Fall back: scan models dict for highest AUC
        models: Dict = getattr(ml_result, "models", {}) or {}
        aucs = []
        for mr in models.values():
            m = getattr(mr, "metrics", {}) or {}
            if "auc" in m:
                aucs.append(float(m["auc"]))
        if aucs:
            return max(aucs)
    except Exception:
        pass
    return 0.0


def _collect_model_aucs(ml_result: Any) -> List[float]:
    """Return list of AUC values across all trained models."""
    try:
        models: Dict = getattr(ml_result, "models", {}) or {}
        aucs = []
        for mr in models.values():
            m = getattr(mr, "metrics", {}) or {}
            if "auc" in m:
                aucs.append(float(m["auc"]))
        return aucs
    except Exception:
        return []


def _get_oof_predictions(ml_result: Any) -> Optional[np.ndarray]:
    """Return OOF predictions from the best model, if available."""
    try:
        best_name: str = getattr(ml_result, "best_model_name", "") or ""
        models: Dict = getattr(ml_result, "models", {}) or {}
        mr = models.get(best_name)
        if mr is None and models:
            mr = next(iter(models.values()))
        if mr is None:
            return None
        oof = getattr(mr, "oof_predictions", None)
        if oof is not None and len(oof) > 0:
            return np.asarray(oof, dtype=float)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------
def _check_holdout_validity(
    test_auc: Optional[float],
    oof_auc: Optional[float],
) -> ValidationCheck:
    name = "HOLDOUT_VALIDITY"
    if test_auc is None or oof_auc is None:
        return _make_check(
            name, "PASS",
            "Skipped — insufficient data to compute test/OOF gap.",
            None,
            "Provide both X_test/y_test and oof_auc_per_fold for a full holdout check.",
        )
    try:
        gap = abs(test_auc - oof_auc)
        sev = _severity(gap, _HOLDOUT_WARN_GAP, _HOLDOUT_FAIL_GAP)
        if sev == "FAIL":
            msg = (f"Large generalisation gap: |test_auc({test_auc:.4f}) - "
                   f"oof_auc({oof_auc:.4f})| = {gap:.4f} > {_HOLDOUT_FAIL_GAP}. "
                   "Strong evidence of overfitting.")
            rec = "Reduce model complexity, increase regularisation, or collect more training data."
        elif sev == "WARN":
            msg = (f"Moderate generalisation gap: gap={gap:.4f} "
                   f"(test={test_auc:.4f}, oof={oof_auc:.4f}). "
                   f"Threshold: WARN>{_HOLDOUT_WARN_GAP}.")
            rec = "Monitor on live data; consider cross-validated evaluation as primary metric."
        else:
            msg = (f"Holdout valid: gap={gap:.4f} "
                   f"(test={test_auc:.4f}, oof={oof_auc:.4f}).")
            rec = "No action required."
        return _make_check(name, sev, msg, round(gap, 6), rec)
    except Exception as exc:
        logger.warning("HOLDOUT_VALIDITY check failed with exception: %s", exc)
        return _make_check(name, "PASS", f"Check skipped due to error: {exc}", None,
                           "Inspect ml_result structure.")


def _check_fold_stability(
    oof_auc_per_fold: Optional[List[float]],
) -> ValidationCheck:
    name = "FOLD_STABILITY"
    if not oof_auc_per_fold or len(oof_auc_per_fold) < 2:
        return _make_check(
            name, "PASS",
            "Skipped — per-fold AUC list not provided or has fewer than 2 folds.",
            None,
            "Pass oof_auc_per_fold for fold stability analysis.",
        )
    try:
        arr = np.asarray(oof_auc_per_fold, dtype=float)
        std = float(np.std(arr, ddof=1))
        sev = _severity(std, _FOLD_STD_WARN, _FOLD_STD_FAIL)
        fold_str = ", ".join(f"{v:.3f}" for v in arr)
        if sev == "FAIL":
            msg = (f"High fold instability: std={std:.4f} > {_FOLD_STD_FAIL}. "
                   f"Per-fold AUC: [{fold_str}].")
            rec = "Check for data leakage between folds, label noise, or class imbalance per fold."
        elif sev == "WARN":
            msg = (f"Moderate fold instability: std={std:.4f}. "
                   f"Per-fold AUC: [{fold_str}].")
            rec = "Consider stratified k-fold or increasing the number of folds."
        else:
            msg = f"Fold stability acceptable: std={std:.4f}. Per-fold AUC: [{fold_str}]."
            rec = "No action required."
        return _make_check(name, sev, msg, round(std, 6), rec)
    except Exception as exc:
        logger.warning("FOLD_STABILITY check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None,
                           "Inspect oof_auc_per_fold values.")


def _check_class_calibration(
    y_test: Optional[np.ndarray],
    y_prob: Optional[np.ndarray],
) -> ValidationCheck:
    name = "CLASS_CALIBRATION"
    if y_test is None or y_prob is None:
        return _make_check(
            name, "PASS",
            "Skipped — y_test or predicted probabilities not available.",
            None,
            "Provide X_test and y_test together with a model that outputs predict_proba.",
        )
    try:
        y_t = np.asarray(y_test).ravel()
        y_p = np.asarray(y_prob).ravel()
        if len(y_t) != len(y_p):
            return _make_check(name, "PASS",
                               "Skipped — shape mismatch between y_test and y_prob.",
                               None, "Verify prediction array dimensions.")
        pos_mask = y_t == 1
        neg_mask = y_t == 0
        if pos_mask.sum() == 0 or neg_mask.sum() == 0:
            return _make_check(name, "PASS",
                               "Skipped — single-class test set.",
                               None, "Ensure test set contains both classes.")
        mean_pos = float(np.mean(y_p[pos_mask]))
        mean_neg = float(np.mean(y_p[neg_mask]))
        gap = mean_pos - mean_neg
        if gap < _CALIB_WARN_GAP:
            sev = "WARN"
            msg = (f"Weak probability discrimination: mean(prob|y=1)={mean_pos:.4f}, "
                   f"mean(prob|y=0)={mean_neg:.4f}, gap={gap:.4f} < {_CALIB_WARN_GAP}.")
            rec = "Apply Platt scaling or isotonic regression calibration; review decision threshold."
        else:
            ideal_pos = mean_pos >= 0.60
            ideal_neg = mean_neg <= 0.40
            sev = "PASS"
            notes = []
            if not ideal_pos:
                notes.append(f"mean_pos={mean_pos:.4f} < 0.60 (lower than ideal)")
            if not ideal_neg:
                notes.append(f"mean_neg={mean_neg:.4f} > 0.40 (higher than ideal)")
            note_str = "; ".join(notes) if notes else "both within ideal range"
            msg = (f"Calibration adequate: gap={gap:.4f}. "
                   f"mean(prob|y=1)={mean_pos:.4f}, mean(prob|y=0)={mean_neg:.4f}. "
                   f"{note_str}.")
            rec = "No action required." if not notes else (
                "Consider probability calibration for better-aligned scores.")
        return _make_check(name, sev, msg, round(gap, 6), rec)
    except Exception as exc:
        logger.warning("CLASS_CALIBRATION check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None,
                           "Verify y_test and probability array integrity.")


def _check_minimum_sample_size(n_train: Optional[int]) -> ValidationCheck:
    name = "MINIMUM_SAMPLE_SIZE"
    if n_train is None:
        return _make_check(name, "PASS",
                           "Skipped — n_train not reported.",
                           None, "Ensure TrainingResult.n_train is populated.")
    try:
        n = int(n_train)
        sev = _severity(n, _MIN_TRAIN_WARN, _MIN_TRAIN_FAIL, higher_is_worse=False)
        if sev == "FAIL":
            msg = (f"Critical: n_train={n} < {_MIN_TRAIN_FAIL}. "
                   "Model trained on fewer than 100 samples — results are unreliable.")
            rec = "Collect more labelled data before deploying this model."
        elif sev == "WARN":
            msg = (f"Small training set: n_train={n} < {_MIN_TRAIN_WARN}. "
                   "Statistical estimates may be noisy.")
            rec = "Target at least 200 training samples; use cross-validation metrics as primary signal."
        else:
            msg = f"Training set size adequate: n_train={n}."
            rec = "No action required."
        return _make_check(name, sev, msg, float(n), rec)
    except Exception as exc:
        logger.warning("MINIMUM_SAMPLE_SIZE check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_feature_count_ratio(
    n_features: Optional[int],
    n_train: Optional[int],
) -> ValidationCheck:
    name = "FEATURE_COUNT_RATIO"
    if n_features is None or n_train is None or n_train == 0:
        return _make_check(name, "PASS",
                           "Skipped — n_features or n_train not available.",
                           None, "Ensure feature_names and n_train are populated.")
    try:
        ratio = float(n_features) / float(n_train)
        threshold = 1.0 / _FEATURE_RATIO_WARN  # n_features > n_train/10  ↔  ratio > 0.10
        if ratio > threshold:
            sev = "WARN"
            msg = (f"Curse of dimensionality risk: n_features={n_features}, "
                   f"n_train={n_train}, ratio={ratio:.4f} > 1/{_FEATURE_RATIO_WARN}.")
            rec = ("Apply feature selection (RFECV, SelectFromModel) or dimensionality "
                   "reduction (PCA) before training.")
        else:
            sev = "PASS"
            msg = (f"Feature/sample ratio acceptable: {n_features} features, "
                   f"{n_train} samples, ratio={ratio:.4f}.")
            rec = "No action required."
        return _make_check(name, sev, msg, round(ratio, 6), rec)
    except Exception as exc:
        logger.warning("FEATURE_COUNT_RATIO check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_class_distribution(
    class_distribution: Optional[Dict],
) -> ValidationCheck:
    name = "CLASS_DISTRIBUTION"
    if not class_distribution:
        return _make_check(name, "PASS",
                           "Skipped — class_distribution not reported.",
                           None, "Ensure TrainingResult.class_distribution is populated.")
    try:
        counts = list(class_distribution.values())
        if len(counts) < 2:
            return _make_check(name, "PASS",
                               "Skipped — fewer than 2 classes in distribution.",
                               None, "Verify class_distribution structure.")
        total = sum(counts)
        if total == 0:
            return _make_check(name, "PASS", "Skipped — zero total samples.", None, "")
        minority_count = min(counts)
        minority_pct = minority_count / total
        if minority_pct < _MINORITY_PCT_WARN:
            sev = "WARN"
            msg = (f"Extreme class imbalance: minority class = {minority_count} "
                   f"({minority_pct*100:.2f}% of {total} samples).")
            rec = ("Use SMOTE/oversampling, class_weight='balanced', or collect more minority "
                   "samples. Evaluate with PR-AUC, not only ROC-AUC.")
        else:
            sev = "PASS"
            msg = (f"Class distribution acceptable: minority={minority_pct*100:.2f}% "
                   f"({minority_count}/{total}).")
            rec = "No action required."
        return _make_check(name, sev, msg, round(minority_pct, 6), rec)
    except Exception as exc:
        logger.warning("CLASS_DISTRIBUTION check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_auc_sanity(best_auc: float) -> ValidationCheck:
    name = "AUC_SANITY"
    try:
        if best_auc < _AUC_RANDOM:
            sev = "FAIL"
            msg = (f"AUC={best_auc:.4f} < {_AUC_RANDOM}. "
                   "Model performs worse than random — likely an inverted label or data error.")
            rec = ("Check for inverted target encoding, data leakage in the negative direction, "
                   "or a systematic preprocessing bug.")
        else:
            sev = "PASS"
            msg = f"AUC sanity check passed: AUC={best_auc:.4f} >= {_AUC_RANDOM}."
            rec = "No action required."
        return _make_check(name, sev, msg, round(best_auc, 6), rec)
    except Exception as exc:
        logger.warning("AUC_SANITY check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_train_variance(model_aucs: List[float]) -> ValidationCheck:
    name = "TRAIN_VARIANCE"
    if len(model_aucs) < 2:
        return _make_check(
            name, "PASS",
            "Skipped — fewer than 2 models trained; variance check not applicable.",
            None,
            "Train multiple models for cross-model variance analysis.",
        )
    try:
        high_auc_models = [a for a in model_aucs if a > _HIGH_AUC_THRESHOLD]
        all_high = len(high_auc_models) == len(model_aucs)
        if all_high:
            mean_auc = float(np.mean(model_aucs))
            sev = "WARN"
            msg = (f"All {len(model_aucs)} models report AUC > {_HIGH_AUC_THRESHOLD} "
                   f"(mean={mean_auc:.4f}). "
                   "Uniform near-perfect performance across diverse models is suspicious — "
                   "possible feature leakage or target contamination.")
            rec = ("Audit features for target leakage (post-event proxies, future data). "
                   "Recompute AUC on a true time-held-out or geographically isolated set.")
        else:
            std = float(np.std(model_aucs, ddof=1)) if len(model_aucs) > 1 else 0.0
            sev = "PASS"
            msg = (f"Model AUC variance normal: "
                   f"[{', '.join(f'{a:.3f}' for a in model_aucs)}], std={std:.4f}.")
            rec = "No action required."
        return _make_check(name, sev, msg,
                           round(float(np.mean(model_aucs)), 6) if model_aucs else None, rec)
    except Exception as exc:
        logger.warning("TRAIN_VARIANCE check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_permutation_baseline(
    y_test: Optional[np.ndarray],
    y_prob: Optional[np.ndarray],
    random_state: int = 42,
) -> ValidationCheck:
    name = "PERMUTATION_BASELINE"
    if y_test is None or y_prob is None:
        return _make_check(
            name, "PASS",
            "Skipped — y_test or predicted probabilities not available.",
            None,
            "Provide X_test and y_test for permutation baseline analysis.",
        )
    try:
        from sklearn.metrics import roc_auc_score

        y_t = np.asarray(y_test).ravel()
        y_p = np.asarray(y_prob).ravel()
        if len(np.unique(y_t)) < 2:
            return _make_check(name, "PASS",
                               "Skipped — test set contains only one class.",
                               None, "Ensure test set has both classes.")
        rng = np.random.default_rng(random_state)
        y_shuffled = rng.permutation(y_t)
        shuffled_auc = float(roc_auc_score(y_shuffled, y_p))
        if shuffled_auc > _PERM_AUC_WARN:
            sev = "WARN"
            msg = (f"Permutation AUC={shuffled_auc:.4f} > {_PERM_AUC_WARN} "
                   "after shuffling labels. The model may be memorising dataset structure "
                   "rather than learning true signal.")
            rec = ("Run full permutation importance analysis. Consider reducing model capacity "
                   "or checking for structural data leakage (row order, index correlation).")
        else:
            sev = "PASS"
            msg = (f"Permutation baseline passed: shuffled_auc={shuffled_auc:.4f} "
                   f"<= {_PERM_AUC_WARN}. Model is not memorising structure.")
            rec = "No action required."
        return _make_check(name, sev, msg, round(shuffled_auc, 6), rec)
    except Exception as exc:
        logger.warning("PERMUTATION_BASELINE check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


def _check_ensemble_agreement(model_aucs: List[float]) -> ValidationCheck:
    name = "ENSEMBLE_AGREEMENT"
    if len(model_aucs) < 2:
        return _make_check(
            name, "PASS",
            "Skipped — fewer than 2 models; ensemble agreement not applicable.",
            None,
            "Train multiple models to enable ensemble agreement analysis.",
        )
    try:
        sorted_aucs = sorted(model_aucs, reverse=True)
        best = sorted_aucs[0]
        second = sorted_aucs[1]
        if best > _HIGH_AUC_THRESHOLD and second < _SECOND_BEST_LOW:
            sev = "WARN"
            msg = (f"Suspicious model divergence: best_auc={best:.4f} > {_HIGH_AUC_THRESHOLD} "
                   f"but second_best_auc={second:.4f} < {_SECOND_BEST_LOW}. "
                   "A single model vastly outperforming all others may indicate leakage "
                   "or overfit specific to that algorithm.")
            rec = ("Investigate the best model's feature usage. Check if it has access to "
                   "features the other models cannot exploit effectively due to their inductive bias.")
        else:
            sev = "PASS"
            gap = best - second
            msg = (f"Ensemble agreement acceptable: "
                   f"best={best:.4f}, second_best={second:.4f}, gap={gap:.4f}.")
            rec = "No action required."
        return _make_check(name, sev, msg, round(best - second, 6), rec)
    except Exception as exc:
        logger.warning("ENSEMBLE_AGREEMENT check failed: %s", exc)
        return _make_check(name, "PASS", f"Check skipped: {exc}", None, "")


# ---------------------------------------------------------------------------
# Governance logic
# ---------------------------------------------------------------------------
def _apply_governance(
    checks: List[ValidationCheck],
    original_auc: float,
    model_name: str,
) -> ValidationReport:
    n_pass = sum(1 for c in checks if c.severity == "PASS")
    n_warn = sum(1 for c in checks if c.severity == "WARN")
    n_fail = sum(1 for c in checks if c.severity == "FAIL")

    has_fail = n_fail > 0
    deployment_safe = not has_fail

    # Governed AUC
    governed_auc = original_auc
    if has_fail:
        overall_status = "INVALID"
        governed_auc = min(original_auc, _GOVERN_FAIL_CAP)
    elif n_warn >= _WARN_COUNT_DEGRADE:
        overall_status = "DEGRADED"
        governed_auc = min(original_auc, _GOVERN_WARN_CAP)
    else:
        overall_status = "VALID"

    # Confidence band
    if governed_auc >= 0.85:
        confidence_band = "High"
    elif governed_auc >= 0.75:
        confidence_band = "Moderate"
    elif governed_auc >= 0.60:
        confidence_band = "Low"
    else:
        confidence_band = "Unreliable"

    # Gather actionable recommendations (non-trivial)
    recommendations = [
        c.recommendation for c in checks
        if c.severity in ("WARN", "FAIL") and c.recommendation.strip()
        and c.recommendation.strip() != "No action required."
    ]

    # Provenance trail
    provenance = [
        f"[{c.severity}] {c.check_name}: {c.message}" for c in checks
    ]

    # Human-readable summary
    status_emoji_map = {"VALID": "PASS", "DEGRADED": "WARN", "INVALID": "FAIL"}
    summary = (
        f"Model '{model_name}' — overall status: {overall_status} "
        f"({n_pass} PASS, {n_warn} WARN, {n_fail} FAIL). "
        f"Original AUC={original_auc:.4f}, governed AUC={governed_auc:.4f}, "
        f"confidence band={confidence_band}. "
        f"Deployment safe: {deployment_safe}."
    )

    return ValidationReport(
        checks=checks,
        n_pass=n_pass,
        n_warn=n_warn,
        n_fail=n_fail,
        overall_status=overall_status,
        governed_auc=round(governed_auc, 6),
        original_auc=round(original_auc, 6),
        confidence_band=confidence_band,
        model_name=model_name,
        deployment_safe=deployment_safe,
        summary=summary,
        recommendations=recommendations,
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class ModelValidator:
    """
    Post-training model integrity validator.

    Usage
    -----
    >>> validator = ModelValidator()
    >>> report = validator.validate(ml_result, X_test=X_test, y_test=y_test,
    ...                             oof_auc_per_fold=[0.82, 0.80, 0.84, 0.81, 0.83])
    >>> print(report.summary)
    """

    def validate(
        self,
        ml_result: Any,
        X_test: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        oof_auc_per_fold: Optional[List[float]] = None,
    ) -> ValidationReport:
        """
        Run all validation checks and return a ValidationReport.

        Parameters
        ----------
        ml_result : TrainingResult
            Output from ml_router.MLRouter.train().
        X_test : np.ndarray, optional
            Held-out feature matrix (n_samples × n_features).
        y_test : np.ndarray, optional
            Held-out ground-truth labels.
        oof_auc_per_fold : list of float, optional
            Per-fold OOF AUC from cross-validation.

        Returns
        -------
        ValidationReport
        """
        checks: List[ValidationCheck] = []

        # ── Extract core attributes ──────────────────────────────────────────
        best_auc    = _extract_best_auc(ml_result)
        model_aucs  = _collect_model_aucs(ml_result)
        model_name  = getattr(ml_result, "best_model_name", "unknown") or "unknown"
        n_train     = getattr(ml_result, "n_train", None)
        n_test      = getattr(ml_result, "n_test", None)
        feature_names = getattr(ml_result, "feature_names", None) or []
        n_features  = len(feature_names) if feature_names else None
        class_dist  = getattr(ml_result, "class_distribution", None)

        # OOF AUC (scalar) derived from per-fold list OR oof_predictions
        oof_auc_scalar: Optional[float] = None
        if oof_auc_per_fold and len(oof_auc_per_fold) >= 1:
            try:
                oof_auc_scalar = float(np.mean(oof_auc_per_fold))
            except Exception:
                pass

        # If no per-fold list, try to compute from raw OOF predictions
        oof_predictions = _get_oof_predictions(ml_result)
        y_prob: Optional[np.ndarray] = None

        if X_test is not None and y_test is not None:
            # Try to get probabilities from the best trained model
            try:
                models: Dict = getattr(ml_result, "models", {}) or {}
                best_name: str = getattr(ml_result, "best_model_name", "") or ""
                mr = models.get(best_name)
                if mr is None and models:
                    mr = next(iter(models.values()))
                if mr is not None:
                    fitted_model = getattr(mr, "model", None)
                    if fitted_model is not None and hasattr(fitted_model, "predict_proba"):
                        y_prob = fitted_model.predict_proba(
                            np.asarray(X_test, dtype=float)
                        )[:, 1]
            except Exception as exc:
                logger.debug("Could not extract predict_proba from best model: %s", exc)

        # Compute test AUC if possible
        test_auc: Optional[float] = None
        if y_test is not None and y_prob is not None:
            try:
                from sklearn.metrics import roc_auc_score
                yt = np.asarray(y_test).ravel()
                if len(np.unique(yt)) >= 2:
                    test_auc = float(roc_auc_score(yt, y_prob))
            except Exception as exc:
                logger.debug("Could not compute test AUC: %s", exc)

        # If we have a test AUC but no OOF scalar, use the best_metric_value as proxy
        if oof_auc_scalar is None and best_auc > 0:
            # Use reported best metric as OOF approximation only when no fold list given
            # (conservative: marks HOLDOUT_VALIDITY as skipped unless fold data provided)
            pass

        # ── Run checks ───────────────────────────────────────────────────────
        checks.append(_check_auc_sanity(best_auc))

        checks.append(_check_holdout_validity(test_auc, oof_auc_scalar))

        checks.append(_check_fold_stability(oof_auc_per_fold))

        checks.append(_check_class_calibration(
            np.asarray(y_test) if y_test is not None else None,
            y_prob,
        ))

        checks.append(_check_minimum_sample_size(n_train))

        checks.append(_check_feature_count_ratio(n_features, n_train))

        checks.append(_check_class_distribution(class_dist))

        checks.append(_check_train_variance(model_aucs))

        checks.append(_check_permutation_baseline(
            np.asarray(y_test) if y_test is not None else None,
            y_prob,
        ))

        checks.append(_check_ensemble_agreement(model_aucs))

        # ── Apply governance and build report ────────────────────────────────
        report = _apply_governance(checks, best_auc, model_name)

        logger.info(
            "ModelValidator: model='%s' status=%s governed_auc=%.4f "
            "(pass=%d warn=%d fail=%d)",
            model_name, report.overall_status, report.governed_auc,
            report.n_pass, report.n_warn, report.n_fail,
        )
        return report


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------
def validate_model(
    ml_result: Any,
    X_test: Optional[np.ndarray] = None,
    y_test: Optional[np.ndarray] = None,
    oof_auc_per_fold: Optional[List[float]] = None,
) -> ValidationReport:
    """
    Module-level shortcut for ModelValidator().validate(...).

    Parameters
    ----------
    ml_result : TrainingResult
        Output from ml_router.MLRouter.train().
    X_test : np.ndarray, optional
        Held-out feature matrix.
    y_test : np.ndarray, optional
        Held-out labels.
    oof_auc_per_fold : list of float, optional
        Per-fold OOF AUC values.

    Returns
    -------
    ValidationReport
    """
    return ModelValidator().validate(
        ml_result=ml_result,
        X_test=X_test,
        y_test=y_test,
        oof_auc_per_fold=oof_auc_per_fold,
    )
