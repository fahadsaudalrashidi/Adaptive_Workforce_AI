"""
Ethical AI Governance Module
Fairness audits, bias detection, protected attribute analysis,
confidence governance, and ethical disclaimers for all predictions.

Phase 6 correction: fixed a confirmed bug (ETHICAL_AI_ENGINE_INVESTIGATION.md
§5b) where a continuous attribute (e.g. Age, 34 distinct values across 200
rows) was grouped by raw unique value, and a handful of resulting 5-10-person
groups happened to have zero positive events, producing a fabricated
428,600,000x "CRITICAL" disparity ratio via division by the near-zero floor.
Two independent guards now sit in front of every disparity computation:
  1. Granularity gating (_bucket_or_skip_for_disparity) — a protected
     attribute with more than _MAX_DISTINCT_VALUES_FOR_RAW_GROUPING distinct
     values, OR one already flagged `representation_warning=True` at
     detection time, is never compared on its raw values. Numeric attributes
     are bucketed into quantile bands first (pandas.qcut — chosen over fixed
     decade bins specifically because it guarantees balanced group sizes by
     construction regardless of the underlying distribution's shape, which
     is what the bug actually needed); non-numeric high-cardinality
     attributes are skipped entirely with an explicit governance note,
     never silently computed or silently dropped.
  2. A minimum-group-size floor (_MIN_GROUP_SIZE_FOR_DISPARITY) applied to
     every individual group (bucketed or raw) before it may enter a
     disparity computation — groups below the floor are excluded with a
     note, never included with a possibly-zero rate.
A lightweight two-proportion z-test (scipy, optional import guarded like
every other optional dependency in this codebase) is also computed between
the highest- and lowest-rate surviving groups, surfacing statistical
significance as an additional transparency field — it does not override the
existing ratio-based risk_level classification, only adds context to it.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import stats as _scipy_stats
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

warnings.filterwarnings("ignore")

# ── Protected attribute keywords ────────────────────────────────────────────
_PROTECTED_KEYWORDS: Dict[str, List[str]] = {
    "gender":      ["gender", "sex", "male", "female"],
    "age":         ["age", "birth", "dob", "birthdate"],
    "race":        ["race", "ethnicity", "nationality", "origin"],
    "religion":    ["religion", "faith", "belief"],
    "disability":  ["disability", "disabled", "handicap", "impairment"],
    "marital":     ["marital", "married", "single", "divorced", "spouse"],
    "nationality": ["country", "nationality", "citizen", "region"],
}

_RISK_LEVEL_THRESHOLDS = {
    "critical": 0.20,
    "high":     0.10,
    "medium":   0.05,
    "low":      0.02,
}

# ── Granularity / small-sample guards (Phase 6 fix) ─────────────────────────

# A protected attribute with more distinct raw values than this is never
# compared on its raw values. 8 is generous enough to still allow direct
# comparison of genuinely categorical attributes with a handful of options
# (e.g. up to 8 nationality categories) while catching anything more
# granular — the bug fixture (Age) had 34 distinct values, far above any
# reasonable "few discrete categories" cutoff.
_MAX_DISTINCT_VALUES_FOR_RAW_GROUPING = 8

# Number of quantile bands a numeric high-cardinality attribute is bucketed
# into. pandas.qcut (equal-*count* bins) is used rather than fixed bands
# (e.g. decade-of-age bins) because it guarantees balanced group sizes by
# construction regardless of how the real data is distributed — a narrow or
# skewed real age distribution could still leave a fixed decade bin with a
# handful of members, reproducing the exact bug this fix closes.
_N_QUANTILE_BUCKETS = 5

# Deliberately stricter than config.settings.MIN_DEPT_GROUP_SIZE (5): that
# threshold flags a department ROW as "small" for display purposes, but a
# DISPARITY RATIO divides two rates, which amplifies small-sample noise
# multiplicatively rather than merely being imprecise — at n=5, a single
# chance-zero event reproduces exactly the fabricated-ratio bug this fix
# closes. At n=20 with a typical ~15-20% HR attrition base rate, the chance
# a truly-representative group shows zero positive events by chance drops to
# roughly (0.80)**20 ≈ 1.2% — a much safer margin than at n=5 (≈44%).
_MIN_GROUP_SIZE_FOR_DISPARITY = 20

_SIGNIFICANCE_ALPHA = 0.05


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class ProtectedAttribute:
    column_name: str
    attribute_type: str          # gender / age / race / etc.
    detection_confidence: float  # 0–1
    unique_values: List[str]
    value_counts: Dict[str, int]
    representation_warning: bool  # True if any group < 10% of total


@dataclass
class FairnessMetric:
    metric_name: str
    attribute_column: str
    score: float                 # 0–1; higher = more fair
    disparity_ratio: float       # max_group_rate / min_group_rate; 1.0 = perfect parity
    risk_level: str              # "critical" / "high" / "medium" / "low" / "acceptable"
    group_rates: Dict[str, float]
    interpretation: str
    recommendation: str
    was_bucketed: bool = False              # True if raw values were too granular and were bucketed first
    n_groups_excluded_small_sample: int = 0  # groups dropped for having < _MIN_GROUP_SIZE_FOR_DISPARITY members
    p_value: Optional[float] = None          # two-proportion z-test between highest/lowest surviving groups
    statistically_significant: Optional[bool] = None  # None if p_value could not be computed


@dataclass
class BiasAuditResult:
    protected_attributes: List[ProtectedAttribute]
    fairness_metrics: List[FairnessMetric]
    overall_risk_level: str      # worst-case across all metrics
    bias_detected: bool
    audit_summary: str
    recommendations: List[str]
    ethical_disclaimer: str
    audit_passed: bool           # True if no critical/high risk metrics
    # Phase 6: bucketing/skip/exclusion notes — never silent. Explains any
    # attribute that was bucketed before comparison, skipped as too granular
    # to bucket sensibly, or had individual groups excluded for having fewer
    # than _MIN_GROUP_SIZE_FOR_DISPARITY members.
    granularity_notes: List[str] = field(default_factory=list)


@dataclass
class ConfidenceGovernance:
    """Governs whether a prediction meets the confidence bar for display."""
    prediction_type: str         # "attrition" / "burnout" / "signal_stress" / etc.
    raw_confidence: float        # 0–1 from model
    governed_confidence: float   # after penalty adjustments
    display_allowed: bool        # False = suppress prediction
    suppression_reason: str      # why suppressed, if applicable
    confidence_band: str         # "High" / "Moderate" / "Low" / "Unreliable"
    caveats: List[str]
    requires_human_review: bool


@dataclass
class EthicalReport:
    bias_audit: BiasAuditResult
    governance: List[ConfidenceGovernance]
    overall_ethical_status: str  # "Pass" / "Conditional" / "Fail"
    blocking_issues: List[str]
    advisory_warnings: List[str]
    ethical_clearance_text: str
    requires_expert_review: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _detect_protected_attributes(df: pd.DataFrame) -> List[ProtectedAttribute]:
    attrs: List[ProtectedAttribute] = []
    total_rows = len(df)
    if total_rows == 0:
        return attrs

    for col in df.columns:
        col_lower = col.lower().strip()
        matched_type: Optional[str] = None
        best_score = 0.0

        for attr_type, keywords in _PROTECTED_KEYWORDS.items():
            for kw in keywords:
                if kw in col_lower:
                    score = len(kw) / len(col_lower)
                    if score > best_score:
                        best_score = score
                        matched_type = attr_type

        if matched_type and best_score >= 0.25:
            series = df[col].dropna()
            if series.empty:
                continue
            unique_vals = [str(v) for v in series.unique()[:20]]
            vc = series.value_counts().to_dict()
            vc_str = {str(k): int(v) for k, v in vc.items()}
            min_group = min(vc.values()) if vc else 0
            representation_warn = (min_group / total_rows) < 0.10

            attrs.append(ProtectedAttribute(
                column_name=col,
                attribute_type=matched_type,
                detection_confidence=round(best_score, 3),
                unique_values=unique_vals,
                value_counts=vc_str,
                representation_warning=representation_warn,
            ))
    return attrs


def _compute_disparity_ratio(rates: Dict[str, float]) -> float:
    vals = [v for v in rates.values() if v is not None]
    if len(vals) < 2:
        return 1.0
    return round(max(vals) / max(min(vals), 1e-9), 4)


def _rate_risk(disparity: float) -> str:
    gap = disparity - 1.0
    if gap >= _RISK_LEVEL_THRESHOLDS["critical"]:
        return "critical"
    if gap >= _RISK_LEVEL_THRESHOLDS["high"]:
        return "high"
    if gap >= _RISK_LEVEL_THRESHOLDS["medium"]:
        return "medium"
    if gap >= _RISK_LEVEL_THRESHOLDS["low"]:
        return "low"
    return "acceptable"


def _compute_selection_rate(
    df: pd.DataFrame, group_values: pd.Series, target_col: str, positive_label: Any,
    min_group_size: int = _MIN_GROUP_SIZE_FOR_DISPARITY,
) -> Tuple[Dict[str, float], Dict[str, int], List[str]]:
    """
    Compute a selection rate per group, using *group_values* (a Series
    aligned to *df*'s index — either the raw column or an already-bucketed
    version of it, see _bucket_or_skip_for_disparity) rather than a column
    name, so a bucketed Series can be passed in without writing it back to
    the dataframe first.

    Any group with fewer than *min_group_size* members is EXCLUDED from the
    returned rates — never included with a small, unstable rate — and its
    label is returned in the third tuple element so the caller can disclose
    the exclusion rather than silently dropping it. Group sizes for the
    surviving groups are returned alongside the rates (needed for the
    significance test).
    """
    rates: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    excluded: List[str] = []
    work = pd.DataFrame({"_group": group_values, "_target": df[target_col].values})
    for group_val, grp in work.groupby("_group", observed=True):
        n = len(grp)
        if n == 0:
            continue
        if n < min_group_size:
            excluded.append(f"{group_val} (n={n})")
            continue
        positive = (grp["_target"] == positive_label).sum()
        rates[str(group_val)] = round(float(positive) / n, 4)
        counts[str(group_val)] = n
    return rates, counts, excluded


def _bucket_or_skip_for_disparity(
    df: pd.DataFrame, attr: ProtectedAttribute,
) -> Tuple[Optional[pd.Series], Optional[str]]:
    """
    Decide how (or whether) *attr*'s column may be grouped for a disparity
    comparison. Never returns raw high-cardinality values for direct
    comparison — this is the fix for the confirmed 428,600,000x fabricated-
    disparity bug (ETHICAL_AI_ENGINE_INVESTIGATION.md §5b).

    Both existing granularity signals gate the decision, per the fix
    instructions: the distinct-value count computed here, AND the
    representation_warning already computed at detection time (True when
    some raw group is under 10% of the dataset).

    A genuinely FEW-category attribute (e.g. Gender: Male/Female/Other) is
    never skipped outright just because one of its groups is small —
    representation_warning is consulted downstream instead, where it
    actually matters: _compute_selection_rate's minimum-group-size floor
    excludes that one small group from the comparison while still comparing
    the groups that ARE large enough, rather than discarding the whole
    attribute. representation_warning only escalates a HIGH-CARDINALITY
    attribute (already over the distinct-value threshold) straight to
    bucketing/skip — for a low-cardinality attribute it is not, by itself,
    a reason to bucket or skip, only a signal that a group-level exclusion
    is likely.

    Returns (group_values, note):
      - (raw column values, None)      — few distinct values: safe to compare directly (small groups excluded downstream)
      - (bucketed values, note)        — numeric and high-cardinality: bucketed into quantile bands
      - (None, note)                   — not numeric and high-cardinality: skipped, not comparable
    """
    series = df[attr.column_name]
    n_distinct = series.dropna().nunique()

    if n_distinct <= _MAX_DISTINCT_VALUES_FOR_RAW_GROUPING:
        return series, None

    numeric = pd.to_numeric(series, errors="coerce")
    frac_numeric = numeric.notna().sum() / max(len(series), 1)
    if frac_numeric >= 0.90:
        try:
            n_buckets = max(2, min(_N_QUANTILE_BUCKETS, n_distinct))
            bucketed = pd.qcut(numeric, q=n_buckets, duplicates="drop")
            n_actual_buckets = bucketed.cat.categories.size
            if n_actual_buckets < 2:
                return None, (
                    f"'{attr.column_name}' has {n_distinct} distinct values and could not "
                    "be bucketed into more than one usable band (values too concentrated) — "
                    "skipped rather than comparing raw individual values."
                )
            labels = bucketed.astype(str)
            return labels, (
                f"'{attr.column_name}' has {n_distinct} distinct values — too granular for "
                f"a reliable per-value disparity comparison. Bucketed into {n_actual_buckets} "
                "quantile-based bands (balanced group sizes) before computing group rates, "
                "rather than comparing raw individual values."
            )
        except (ValueError, TypeError):
            pass

    return None, (
        f"'{attr.column_name}' has {n_distinct} distinct values and is not reliably numeric — "
        "too granular to audit without a bucketing strategy. Skipped rather than computing a "
        "misleading per-value disparity ratio."
    )


def _two_proportion_z_test(
    rate_a: float, n_a: int, rate_b: float, n_b: int,
) -> Optional[float]:
    """
    Two-proportion z-test p-value between the highest- and lowest-rate
    surviving groups behind a disparity ratio — additional transparency
    context, not a replacement for the ratio-based risk_level. Returns None
    (never a fabricated p-value) if scipy is unavailable or inputs are
    degenerate.
    """
    if not _SCIPY_AVAILABLE or n_a <= 0 or n_b <= 0:
        return None
    x_a, x_b = rate_a * n_a, rate_b * n_b
    pooled = (x_a + x_b) / (n_a + n_b)
    se = (pooled * (1 - pooled) * (1.0 / n_a + 1.0 / n_b)) ** 0.5
    if se == 0:
        return None
    z = (rate_a - rate_b) / se
    p_value = float(2 * _scipy_stats.norm.sf(abs(z)))
    return round(p_value, 4)


# ── Main engine ──────────────────────────────────────────────────────────────

class EthicalAIEngine:
    """
    Fairness auditing, bias detection, and confidence governance.
    Designed to be stateless — all methods take explicit inputs.
    """

    # ── Bias audit ────────────────────────────────────────────────────────

    def audit_bias(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        positive_label: Any = "Yes",
        predictions: Optional[np.ndarray] = None,
        prediction_col: str = "predicted",
    ) -> BiasAuditResult:
        """
        Full bias audit. Works on ground truth or model predictions.
        If target_col is None, only attribute detection is run.
        """
        protected = _detect_protected_attributes(df)
        metrics: List[FairnessMetric] = []
        granularity_notes: List[str] = []

        if target_col and target_col in df.columns:
            work_df = df.copy()
            if predictions is not None and len(predictions) == len(df):
                work_df[prediction_col] = predictions
                analysis_col = prediction_col
                analysis_label = 1 if predictions.dtype in [np.int32, np.int64, np.float32, np.float64] else positive_label
            else:
                analysis_col = target_col
                analysis_label = positive_label

            for attr in protected:
                try:
                    # Phase 6 fix: never compare raw high-cardinality/under-
                    # represented values directly — bucket or skip first.
                    group_values, bucket_note = _bucket_or_skip_for_disparity(work_df, attr)
                    if bucket_note:
                        granularity_notes.append(bucket_note)
                    if group_values is None:
                        continue  # too granular to bucket sensibly — skipped, not silently guessed at

                    rates, counts, excluded = _compute_selection_rate(
                        work_df, group_values, analysis_col, analysis_label,
                    )
                    if excluded:
                        granularity_notes.append(
                            f"'{attr.column_name}': excluded group(s) with fewer than "
                            f"{_MIN_GROUP_SIZE_FOR_DISPARITY} members from comparison "
                            f"(too small for a reliable rate): {', '.join(excluded)}."
                        )
                    if len(rates) < 2:
                        granularity_notes.append(
                            f"'{attr.column_name}': fewer than 2 groups had enough members "
                            f"(≥{_MIN_GROUP_SIZE_FOR_DISPARITY}) for a disparity comparison — "
                            "no fairness metric computed for this attribute."
                        )
                        continue

                    disparity = _compute_disparity_ratio(rates)
                    risk = _rate_risk(disparity)
                    score = round(1.0 / max(disparity, 1.0), 4)
                    interp = self._interpret_fairness(attr.attribute_type, risk, disparity, rates)
                    rec = self._recommend(attr.attribute_type, risk)

                    high_group = max(rates, key=rates.get)
                    low_group = min(rates, key=rates.get)
                    p_value = _two_proportion_z_test(
                        rates[high_group], counts[high_group],
                        rates[low_group], counts[low_group],
                    )
                    significant = (p_value < _SIGNIFICANCE_ALPHA) if p_value is not None else None
                    if p_value is not None and not significant:
                        interp += (
                            f" NOTE: this gap is NOT statistically significant at the "
                            f"conventional p<0.05 threshold (p={p_value:.3f}) — plausibly "
                            "sampling noise rather than a real disparity."
                        )

                    metrics.append(FairnessMetric(
                        metric_name="statistical_parity",
                        attribute_column=attr.column_name,
                        score=score,
                        disparity_ratio=disparity,
                        risk_level=risk,
                        group_rates=rates,
                        interpretation=interp,
                        recommendation=rec,
                        was_bucketed=bucket_note is not None,
                        n_groups_excluded_small_sample=len(excluded),
                        p_value=p_value,
                        statistically_significant=significant,
                    ))
                except Exception:
                    continue

        # Overall risk = worst single metric
        risk_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "acceptable": 0}
        overall_risk = "acceptable"
        for m in metrics:
            if risk_order.get(m.risk_level, 0) > risk_order.get(overall_risk, 0):
                overall_risk = m.risk_level

        bias_detected = overall_risk in {"critical", "high", "medium"}
        audit_passed  = overall_risk not in {"critical", "high"}

        summary = self._build_summary(protected, metrics, overall_risk, target_col, granularity_notes)
        recs = list({m.recommendation for m in metrics if m.recommendation})
        if not recs:
            recs = ["No significant bias concerns detected. Continue monitoring."]

        disclaimer = (
            "ETHICAL DISCLAIMER: This bias audit is statistical and does not constitute "
            "a legal determination of discrimination. Results should be reviewed by HR, "
            "legal, and ethics professionals before informing personnel decisions. "
            "Protected attribute detection is automated and may be incomplete."
        )

        return BiasAuditResult(
            protected_attributes=protected,
            fairness_metrics=metrics,
            overall_risk_level=overall_risk,
            bias_detected=bias_detected,
            audit_summary=summary,
            recommendations=recs,
            ethical_disclaimer=disclaimer,
            audit_passed=audit_passed,
            granularity_notes=granularity_notes,
        )

    # ── Confidence governance ─────────────────────────────────────────────

    def govern_prediction(
        self,
        prediction_type: str,
        raw_confidence: float,
        n_samples: int,
        data_quality_score: float,
        auc_score: float,
        class_imbalance_ratio: float = 1.0,
        protected_bias_risk: str = "acceptable",
    ) -> ConfidenceGovernance:
        """
        Apply governance penalties and determine if a prediction can be displayed.
        """
        governed = raw_confidence

        # Sample size penalty
        if n_samples < 50:
            governed *= 0.50
        elif n_samples < 200:
            governed *= 0.75
        elif n_samples < 500:
            governed *= 0.90

        # Data quality penalty
        if data_quality_score < 0.4:
            governed *= 0.60
        elif data_quality_score < 0.6:
            governed *= 0.80
        elif data_quality_score < 0.75:
            governed *= 0.92

        # AUC penalty
        if auc_score < 0.60:
            governed *= 0.55
        elif auc_score < 0.65:
            governed *= 0.70
        elif auc_score < 0.70:
            governed *= 0.85

        # Imbalance penalty
        if class_imbalance_ratio > 10:
            governed *= 0.70
        elif class_imbalance_ratio > 5:
            governed *= 0.85

        # Bias penalty
        if protected_bias_risk == "critical":
            governed *= 0.50
        elif protected_bias_risk == "high":
            governed *= 0.70

        governed = round(min(1.0, max(0.0, governed)), 4)

        # Band assignment
        if governed >= 0.80:
            band = "High"
        elif governed >= 0.65:
            band = "Moderate"
        elif governed >= 0.50:
            band = "Low"
        else:
            band = "Unreliable"

        # Display allowed above minimum threshold
        display_allowed = governed >= 0.45

        # Suppression reason
        suppression_reason = ""
        if not display_allowed:
            if auc_score < 0.60:
                suppression_reason = "Model discrimination (AUC < 0.60) insufficient for reliable prediction."
            elif n_samples < 50:
                suppression_reason = "Sample size too small for reliable prediction."
            elif data_quality_score < 0.40:
                suppression_reason = "Data quality too low to support reliable prediction."
            else:
                suppression_reason = "Governed confidence below minimum display threshold (0.45)."

        # Caveats
        caveats: List[str] = []
        if n_samples < 200:
            caveats.append(f"Small sample size ({n_samples} records) limits reliability.")
        if data_quality_score < 0.70:
            caveats.append(f"Data quality score {data_quality_score:.0%} may affect accuracy.")
        if auc_score < 0.75:
            caveats.append(f"Model AUC {auc_score:.3f} — predictions carry uncertainty.")
        if class_imbalance_ratio > 5:
            caveats.append(f"Class imbalance ratio {class_imbalance_ratio:.1f}:1 detected.")
        if protected_bias_risk in {"medium", "high", "critical"}:
            caveats.append(f"Fairness concern ({protected_bias_risk} risk) — review before use.")

        requires_review = (
            protected_bias_risk in {"critical", "high"} or
            not display_allowed or
            band == "Low"
        )

        return ConfidenceGovernance(
            prediction_type=prediction_type,
            raw_confidence=round(raw_confidence, 4),
            governed_confidence=governed,
            display_allowed=display_allowed,
            suppression_reason=suppression_reason,
            confidence_band=band,
            caveats=caveats,
            requires_human_review=requires_review,
        )

    # ── Full ethical report ───────────────────────────────────────────────

    def generate_ethical_report(
        self,
        bias_audit: BiasAuditResult,
        governance_results: List[ConfidenceGovernance],
    ) -> EthicalReport:
        blocking: List[str] = []
        advisory: List[str] = []

        # Phase 6: the ratio-based risk_level classification is intentionally
        # left unchanged by the significance test (see module docstring) —
        # but the TEXT a user actually reads must never claim unqualified
        # certainty when every metric at that risk level failed to reach
        # significance. If none of the metrics driving this risk level are
        # statistically significant, say so explicitly in the same message
        # rather than only exposing it as a separate field the caller might
        # not render.
        at_risk_metrics = [m for m in bias_audit.fairness_metrics if m.risk_level == bias_audit.overall_risk_level]
        any_significant = any(m.statistically_significant for m in at_risk_metrics)
        any_tested = any(m.statistically_significant is not None for m in at_risk_metrics)
        significance_caveat = ""
        if at_risk_metrics and any_tested and not any_significant:
            significance_caveat = (
                " CAVEAT: the underlying gap(s) driving this risk level did NOT reach "
                "conventional statistical significance (p<0.05) — plausibly sampling "
                "noise rather than a confirmed disparity; treat as a signal to monitor, "
                "not a confirmed finding."
            )

        if bias_audit.overall_risk_level == "critical":
            blocking.append(
                "CRITICAL BIAS RISK: Statistical parity disparity exceeds 20% threshold. "
                "Predictions must not be used for personnel decisions without expert review."
                + significance_caveat
            )
        elif bias_audit.overall_risk_level == "high":
            advisory.append(
                "HIGH BIAS RISK: Statistical disparity detected. Recommend fairness-aware "
                "model retraining before production deployment."
                + significance_caveat
            )
        elif bias_audit.overall_risk_level == "medium":
            advisory.append(
                "MEDIUM BIAS RISK: Moderate disparity across protected groups. "
                "Monitor outcomes and review periodically."
                + significance_caveat
            )

        suppressed = [g for g in governance_results if not g.display_allowed]
        if suppressed:
            for g in suppressed:
                blocking.append(
                    f"SUPPRESSED — {g.prediction_type}: {g.suppression_reason}"
                )

        low_conf = [g for g in governance_results if g.confidence_band in {"Low", "Unreliable"}]
        for g in low_conf:
            advisory.append(
                f"LOW CONFIDENCE — {g.prediction_type}: {g.governed_confidence:.0%} governed confidence. "
                + (g.caveats[0] if g.caveats else "Use with caution.")
            )

        if not blocking and not advisory:
            overall_status = "Pass"
        elif blocking:
            overall_status = "Fail"
        else:
            overall_status = "Conditional"

        requires_expert = (
            bias_audit.overall_risk_level in {"critical", "high"} or
            overall_status == "Fail"
        )

        if overall_status == "Pass":
            clearance_text = (
                "Ethical clearance: PASSED. No critical bias risks or confidence failures detected. "
                "Predictions may be presented with standard caveats."
            )
        elif overall_status == "Conditional":
            clearance_text = (
                "Ethical clearance: CONDITIONAL. Advisory warnings present. "
                "Review caveats before using predictions in personnel decisions."
            )
        else:
            clearance_text = (
                "Ethical clearance: FAILED. Critical issues block safe prediction display. "
                "Do NOT use these predictions for personnel decisions without expert review."
            )

        return EthicalReport(
            bias_audit=bias_audit,
            governance=governance_results,
            overall_ethical_status=overall_status,
            blocking_issues=blocking,
            advisory_warnings=advisory,
            ethical_clearance_text=clearance_text,
            requires_expert_review=requires_expert,
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _interpret_fairness(
        self, attr_type: str, risk: str, disparity: float, rates: Dict[str, float]
    ) -> str:
        sorted_groups = sorted(rates.items(), key=lambda x: x[1])
        if len(sorted_groups) < 2:
            return "Insufficient group data for interpretation."
        low_group, low_rate  = sorted_groups[0]
        high_group, high_rate = sorted_groups[-1]
        pct_diff = round((high_rate - low_rate) * 100, 1)
        return (
            f"Statistical parity disparity ratio: {disparity:.2f}x. "
            f"Highest rate: {high_group} ({high_rate:.1%}), "
            f"Lowest rate: {low_group} ({low_rate:.1%}). "
            f"Gap: {pct_diff:.1f} percentage points. "
            f"Risk level: {risk.upper()}."
        )

    def _recommend(self, attr_type: str, risk: str) -> str:
        base = {
            "critical": "Immediately pause predictions for personnel decisions. Engage ethics review board.",
            "high": "Conduct fairness-aware retraining. Apply algorithmic debiasing techniques.",
            "medium": "Monitor regularly. Consider stratified evaluation and calibration per group.",
            "low": "Document disparity. Apply continuous monitoring with quarterly audits.",
            "acceptable": "No action required. Continue monitoring.",
        }
        return base.get(risk, "Review bias metrics before deployment.")

    def _build_summary(
        self,
        protected: List[ProtectedAttribute],
        metrics: List[FairnessMetric],
        overall_risk: str,
        target_col: Optional[str] = None,
        granularity_notes: Optional[List[str]] = None,
    ) -> str:
        n_attrs = len(protected)
        n_metrics = len(metrics)
        if n_attrs == 0:
            return (
                "No protected attributes detected in the dataset. "
                "Bias audit not applicable. Standard data quality review recommended."
            )
        attr_names = ", ".join(a.attribute_type for a in protected)
        if n_metrics == 0:
            if not target_col:
                return (
                    f"Protected attributes detected: {attr_names}. "
                    "No target column available for fairness metric computation. "
                    "Attribute-level representation checks completed."
                )
            # A target column WAS available — metrics are zero because every
            # detected attribute was bucketed-then-still-too-small, skipped
            # as too granular, or had all groups excluded, not because no
            # target existed. Say so honestly rather than reusing the
            # no-target message.
            return (
                f"Protected attributes detected: {attr_names}. A target column was "
                "available, but no fairness metric could be reliably computed for any "
                f"of them ({len(granularity_notes or [])} granularity/sample-size note(s) — "
                "see granularity_notes for detail). Attribute-level representation "
                "checks completed."
            )
        critical_count = sum(1 for m in metrics if m.risk_level == "critical")
        high_count = sum(1 for m in metrics if m.risk_level == "high")
        return (
            f"Bias audit complete. {n_attrs} protected attribute(s) detected: {attr_names}. "
            f"{n_metrics} fairness metric(s) computed. "
            f"Critical risks: {critical_count}, High risks: {high_count}. "
            f"Overall risk level: {overall_risk.upper()}."
        )


# ── Module-level convenience function ────────────────────────────────────────

def build_ethical_report(
    df: pd.DataFrame,
    target_col: Optional[str] = None,
    positive_label: Any = "Yes",
    prediction_type: str = "attrition",
    raw_confidence: float = 0.75,
    n_samples: int = 200,
    data_quality_score: float = 0.80,
    auc_score: float = 0.75,
    class_imbalance_ratio: float = 1.0,
    predictions: Optional[np.ndarray] = None,
) -> EthicalReport:
    engine = EthicalAIEngine()
    audit = engine.audit_bias(
        df=df,
        target_col=target_col,
        positive_label=positive_label,
        predictions=predictions,
    )
    gov = engine.govern_prediction(
        prediction_type=prediction_type,
        raw_confidence=raw_confidence,
        n_samples=n_samples,
        data_quality_score=data_quality_score,
        auc_score=auc_score,
        class_imbalance_ratio=class_imbalance_ratio,
        protected_bias_risk=audit.overall_risk_level,
    )
    return engine.generate_ethical_report(audit, [gov])


# ── Serialization (Phase 6 — needed to wire this into the live JSON API) ────

def bias_audit_to_dict(r: BiasAuditResult) -> Dict[str, Any]:
    """Serialize BiasAuditResult to a JSON-safe dict."""
    return {
        "protected_attributes": [
            {
                "column_name": a.column_name,
                "attribute_type": a.attribute_type,
                "detection_confidence": a.detection_confidence,
                "unique_values": a.unique_values,
                "value_counts": a.value_counts,
                "representation_warning": a.representation_warning,
            }
            for a in r.protected_attributes
        ],
        "fairness_metrics": [
            {
                "metric_name": m.metric_name,
                "attribute_column": m.attribute_column,
                "score": m.score,
                "disparity_ratio": m.disparity_ratio,
                "risk_level": m.risk_level,
                "group_rates": m.group_rates,
                "interpretation": m.interpretation,
                "recommendation": m.recommendation,
                "was_bucketed": m.was_bucketed,
                "n_groups_excluded_small_sample": m.n_groups_excluded_small_sample,
                "p_value": m.p_value,
                "statistically_significant": m.statistically_significant,
            }
            for m in r.fairness_metrics
        ],
        "overall_risk_level": r.overall_risk_level,
        "bias_detected": r.bias_detected,
        "audit_summary": r.audit_summary,
        "recommendations": r.recommendations,
        "ethical_disclaimer": r.ethical_disclaimer,
        "audit_passed": r.audit_passed,
        "granularity_notes": r.granularity_notes,
    }


def ethical_report_to_dict(r: EthicalReport) -> Dict[str, Any]:
    """Serialize EthicalReport to a JSON-safe dict."""
    return {
        "bias_audit": bias_audit_to_dict(r.bias_audit),
        "governance": [
            {
                "prediction_type": g.prediction_type,
                "raw_confidence": g.raw_confidence,
                "governed_confidence": g.governed_confidence,
                "display_allowed": g.display_allowed,
                "suppression_reason": g.suppression_reason,
                "confidence_band": g.confidence_band,
                "caveats": g.caveats,
                "requires_human_review": g.requires_human_review,
            }
            for g in r.governance
        ],
        "overall_ethical_status": r.overall_ethical_status,
        "blocking_issues": r.blocking_issues,
        "advisory_warnings": r.advisory_warnings,
        "ethical_clearance_text": r.ethical_clearance_text,
        "requires_expert_review": r.requires_expert_review,
    }


def unavailable_bias_audit_result(reason: str) -> BiasAuditResult:
    """Public constructor for a no-protected-attributes / not-applicable
    result — matches the `available=False`-equivalent honesty pattern
    already used by payroll_movement_tracker.py / recruitment_pipeline_engine.py.
    ethical_ai.py's BiasAuditResult has no `available` field of its own, so
    this fills every field with an explicit, non-fabricated empty state and
    puts the reason in `audit_summary`."""
    return BiasAuditResult(
        protected_attributes=[],
        fairness_metrics=[],
        overall_risk_level="acceptable",
        bias_detected=False,
        audit_summary=reason,
        recommendations=[],
        ethical_disclaimer=(
            "ETHICAL DISCLAIMER: This bias audit is statistical and does not constitute "
            "a legal determination of discrimination. Results should be reviewed by HR, "
            "legal, and ethics professionals before informing personnel decisions. "
            "Protected attribute detection is automated and may be incomplete."
        ),
        audit_passed=True,
        granularity_notes=[],
    )


# ── Target-column detection (Phase 6 — for live wiring) ─────────────────────

_ATTRITION_TARGET_CANDIDATES = [
    "flight_risk", "attrition", "Attrition", "turnover",
    "label", "target", "resigned", "left_company",
]
# Mirrors employee_risk_scoring.py's private EmployeeRiskScorer._detect_target_column
# candidate list exactly, for consistency with the rest of the platform's
# attrition-target detection. Kept as an explicit local list here rather
# than importing a private method across modules.

_POSITIVE_TOKENS = {"yes", "1", "1.0", "true"}
_NEGATIVE_TOKENS = {"no", "0", "0.0", "false"}


def detect_attrition_target_column(df: pd.DataFrame) -> Tuple[Optional[str], Any]:
    """
    Find a recognisable binary attrition/flight-risk target column and the
    RAW value in it that represents the positive (left/at-risk) outcome, for
    use with audit_bias(). Returns (None, None) — never a guess — if no
    candidate column with a clean binary encoding and at least 50 non-null
    rows is found.
    """
    for col in _ATTRITION_TARGET_CANDIDATES:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if len(series) < 50:
            continue
        norm_to_raw: Dict[str, Any] = {}
        for raw in series.unique():
            norm_to_raw[str(raw).strip().lower()] = raw
        keys = set(norm_to_raw.keys())
        if keys <= (_POSITIVE_TOKENS | _NEGATIVE_TOKENS) and keys & _POSITIVE_TOKENS:
            positive_key = next(iter(keys & _POSITIVE_TOKENS))
            return col, norm_to_raw[positive_key]
    return None, None
