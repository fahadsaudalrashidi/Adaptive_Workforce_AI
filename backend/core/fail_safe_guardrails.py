"""
Fail-Safe Guardrails
Hard analytical integrity guards for the Adaptive Workforce Intelligence Engine.

NEVER renders HR analytics for non-HR datasets.
NEVER fabricates employee metrics.
NEVER forces supervised learning without a valid target.
NEVER assumes classification problems.
NEVER allows fake confidence.
ALWAYS degrades gracefully rather than crashing or hallucinating.

Architecture:
  - GuardRule: a single check with severity and blocking behaviour
  - GuardResult: outcome of all rules applied to a request
  - SandboxValidator: pre-render validation gateway — every page goes through this

Severity levels:
  BLOCK  — analysis must not proceed under any circumstances
  WARN   — analysis may proceed with prominent user warning
  LOG    — analysis may proceed; log for audit purposes
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pandas as pd

warnings.filterwarnings("ignore")

from .modality_classifier import Modality, ModalityResult
from .dataset_confidence_engine import RoutingConfidence


# ── Severity ──────────────────────────────────────────────────────────────────

class Severity(str, Enum):
    BLOCK = "BLOCK"
    WARN  = "WARN"
    LOG   = "LOG"


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class GuardViolation:
    rule_name: str
    severity: Severity
    message: str
    analysis_blocked: str      # which analysis this blocks
    recommendation: str        # what the user should do instead


@dataclass
class GuardResult:
    """
    Complete result of a sandbox validation run.
    An analysis may only proceed if allowed=True.
    """
    analysis_requested: str
    allowed: bool
    violations: List[GuardViolation]          # BLOCK-level violations
    warnings: List[GuardViolation]            # WARN-level violations
    logs: List[GuardViolation]                # LOG-level notes
    allowed_alternatives: List[str]           # what analyses ARE valid for this data
    suppression_reason: str                   # human-readable reason if blocked
    confidence_score: float                   # routing confidence
    validity_score: float                     # overall data validity
    provenance: List[str]
    degraded_mode: bool                       # True if analysis allowed but degraded


@dataclass
class SandboxReport:
    """Full pre-render sandbox validation for all analyses."""
    modality: str
    routing_confidence: float
    validated_analyses: Dict[str, GuardResult]   # key = analysis name
    globally_blocked: List[str]                  # blocked regardless of analysis
    globally_available: List[str]                # safe to render
    dataset_health_score: float                  # 0–1 overall data integrity
    critical_failures: List[str]                 # must-fix issues before any rendering
    advisory_notes: List[str]
    provenance: List[str]


# ── Guard rule registry ───────────────────────────────────────────────────────

# Each rule: (name, description, check_fn, severity, blocked_analysis, recommendation)
# check_fn signature: (modality_result, routing_conf, df, analysis_key, extra_ctx) -> bool (True = violation)

_GuardRuleDef = Tuple[str, str, Callable, Severity, str, str]


def _is_biosignal(m: ModalityResult, *_) -> bool:
    return m.modality == Modality.BIOSIGNAL


def _is_not_hr(m: ModalityResult, *_) -> bool:
    return m.modality not in {Modality.TABULAR_HR}


def _is_not_biosignal(m: ModalityResult, *_) -> bool:
    return m.modality != Modality.BIOSIGNAL


def _no_target(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    return not ctx.get("target_available", False)


def _tiny_dataset(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    return len(df) < 20


def _low_confidence(m: ModalityResult, rc: RoutingConfidence, *_) -> bool:
    return rc.overall_confidence < 0.40


def _very_low_confidence(m: ModalityResult, rc: RoutingConfidence, *_) -> bool:
    return rc.overall_confidence < 0.25


def _too_few_features(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    feature_cols = ctx.get("feature_columns", [])
    return len(feature_cols) < 2


def _highly_missing(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    missing_rate = ctx.get("missing_rate_overall", 0.0)
    return missing_rate > 0.70


def _mixed_biosignal_hr(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    sem = ctx.get("semantic_mapping")
    if sem is None:
        return False
    return bool(sem.biosignal_columns) and bool(sem.hr_columns)


def _too_small_for_ml(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    return len(df) < 50


def _single_class_target(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    target = ctx.get("target_column")
    if target is None or target not in df.columns:
        return False
    return int(df[target].nunique()) <= 1


def _extreme_imbalance(m: ModalityResult, rc: RoutingConfidence, df: pd.DataFrame, analysis_key: str, ctx: Dict) -> bool:
    target = ctx.get("target_column")
    if target is None or target not in df.columns:
        return False
    vc = df[target].value_counts(normalize=True)
    if len(vc) < 2:
        return True
    return float(vc.iloc[0]) > 0.98  # >98% one class


# ── All rules ─────────────────────────────────────────────────────────────────

_GUARD_RULES: Dict[str, List[_GuardRuleDef]] = {

    # ── Attrition prediction ──────────────────────────────────────────────────
    "attrition_prediction": [
        (
            "biosignal_blocks_attrition",
            "Biosignal data CANNOT produce attrition predictions — these are sensor samples, not employees.",
            lambda m, rc, df, k, ctx: m.modality == Modality.BIOSIGNAL,
            Severity.BLOCK,
            "attrition_prediction",
            "Navigate to Biosignal Intelligence for physiological signal analysis.",
        ),
        (
            "non_hr_blocks_attrition",
            "Attrition prediction requires an HR employee dataset.",
            _is_not_hr,
            Severity.BLOCK,
            "attrition_prediction",
            "Upload an HR employee dataset with an attrition/turnover column.",
        ),
        (
            "no_target_blocks_attrition",
            "No attrition target column detected — supervised attrition prediction is not possible.",
            _no_target,
            Severity.BLOCK,
            "attrition_prediction",
            "Ensure dataset contains a column named 'Attrition', 'Turnover', or similar.",
        ),
        (
            "too_small_for_attrition_ml",
            "Dataset too small (<50 rows) for reliable attrition model training.",
            _too_small_for_ml,
            Severity.BLOCK,
            "attrition_prediction",
            "Collect at least 200+ employee records for reliable attrition modelling.",
        ),
        (
            "single_class_blocks_attrition",
            "Target column has only one class — cannot train a classifier.",
            _single_class_target,
            Severity.BLOCK,
            "attrition_prediction",
            "Ensure target column contains both positive (attrition) and negative (retained) examples.",
        ),
        (
            "extreme_imbalance_warns_attrition",
            "Target class imbalance >98% detected — predictions will be severely biased.",
            _extreme_imbalance,
            Severity.WARN,
            "attrition_prediction",
            "Consider collecting more examples of the minority class or using cost-sensitive learning.",
        ),
        (
            "low_confidence_warns_attrition",
            "Low routing confidence — dataset type uncertain.",
            _low_confidence,
            Severity.WARN,
            "attrition_prediction",
            "Verify that this is an employee dataset before using attrition predictions.",
        ),
    ],

    # ── Biosignal stress analysis ─────────────────────────────────────────────
    "biosignal_stress_analysis": [
        (
            "non_biosignal_blocks_stress",
            "Biosignal stress analysis requires physiological sensor data.",
            _is_not_biosignal,
            Severity.BLOCK,
            "biosignal_stress_analysis",
            "Upload HR.csv, EDA.csv, BVP.csv, TEMP.csv, ACC.csv, or IBI.csv.",
        ),
        (
            "tiny_biosignal_warns",
            "Very few signal samples (<500) — stress analysis may not be reliable.",
            lambda m, rc, df, k, ctx: len(df) < 500,
            Severity.WARN,
            "biosignal_stress_analysis",
            "Ensure signal contains at least 30 seconds of data at the expected sampling rate.",
        ),
    ],

    # ── Department stability ──────────────────────────────────────────────────
    "department_stability": [
        (
            "biosignal_blocks_department",
            "Biosignal data has no department structure.",
            _is_biosignal,
            Severity.BLOCK,
            "department_stability",
            "Navigate to Biosignal Intelligence for signal-based analysis.",
        ),
        (
            "no_dept_column_blocks",
            "No department/division column detected.",
            lambda m, rc, df, k, ctx: not ctx.get("has_department_column", False),
            Severity.BLOCK,
            "department_stability",
            "Ensure dataset contains a 'Department' or 'Division' column.",
        ),
        (
            "non_hr_blocks_department",
            "Department stability analysis requires HR employee data.",
            _is_not_hr,
            Severity.BLOCK,
            "department_stability",
            "Upload an HR dataset with department information.",
        ),
    ],

    # ── Fairness audit ────────────────────────────────────────────────────────
    "fairness_audit": [
        (
            "biosignal_blocks_fairness",
            "Fairness audit requires employee records, not sensor data.",
            _is_biosignal,
            Severity.BLOCK,
            "fairness_audit",
            "Fairness audit applies to HR employee datasets only.",
        ),
        (
            "no_target_blocks_fairness",
            "Fairness audit requires a target outcome column.",
            _no_target,
            Severity.WARN,
            "fairness_audit",
            "Add a target column (e.g. Attrition) to enable fairness metrics.",
        ),
    ],

    # ── Retention ROI ─────────────────────────────────────────────────────────
    "retention_roi": [
        (
            "biosignal_blocks_roi",
            "Biosignal data contains no salary or compensation information.",
            _is_biosignal,
            Severity.BLOCK,
            "retention_roi",
            "Retention ROI applies to HR employee datasets with salary data.",
        ),
        (
            "non_hr_blocks_roi",
            "Retention ROI requires HR employee data with compensation columns.",
            _is_not_hr,
            Severity.BLOCK,
            "retention_roi",
            "Upload an HR dataset including monthly income or salary information.",
        ),
    ],

    # ── Supervised ML (generic) ───────────────────────────────────────────────
    "supervised_ml": [
        (
            "no_target_blocks_supervised",
            "No target column detected — supervised learning cannot proceed.",
            _no_target,
            Severity.BLOCK,
            "supervised_ml",
            "Add a labelled outcome column to enable supervised machine learning.",
        ),
        (
            "too_small_for_supervised",
            "Dataset too small (<50 rows) for reliable supervised modelling.",
            _too_small_for_ml,
            Severity.BLOCK,
            "supervised_ml",
            "Collect at least 100+ labelled records for supervised learning.",
        ),
        (
            "too_few_features_blocks_supervised",
            "Fewer than 2 usable feature columns detected.",
            _too_few_features,
            Severity.BLOCK,
            "supervised_ml",
            "Ensure dataset has multiple informative feature columns.",
        ),
        (
            "single_class_blocks_supervised",
            "Target has only one class — no classifier can be trained.",
            _single_class_target,
            Severity.BLOCK,
            "supervised_ml",
            "Ensure target column contains multiple classes.",
        ),
        (
            "highly_missing_warns_supervised",
            ">70% overall missing data — model will be unreliable.",
            _highly_missing,
            Severity.WARN,
            "supervised_ml",
            "Address missing data before training a supervised model.",
        ),
    ],

    # ── Mixed modality detection ──────────────────────────────────────────────
    "any_analysis": [
        (
            "mixed_biosignal_hr_blocks_all",
            "Dataset contains BOTH biosignal AND HR columns — scientifically invalid mix. "
            "Cannot safely route to either biosignal or HR pipeline.",
            _mixed_biosignal_hr,
            Severity.BLOCK,
            "any_analysis",
            "Split dataset into separate HR and biosignal files before uploading.",
        ),
        (
            "very_low_confidence_blocks_prediction",
            "Routing confidence below 25% — cannot safely determine dataset type.",
            _very_low_confidence,
            Severity.BLOCK,
            "any_analysis",
            "Ensure uploaded file is a recognised dataset type (HR, survey, biosignal, or time-series).",
        ),
    ],

    # ── Burnout/psychological ─────────────────────────────────────────────────
    "burnout_intelligence": [
        (
            "biosignal_blocks_burnout",
            "Biosignal data does not contain survey-based burnout constructs.",
            _is_biosignal,
            Severity.BLOCK,
            "burnout_intelligence",
            "Upload a psychological survey dataset for burnout analysis.",
        ),
        (
            "non_survey_warns_burnout",
            "Dataset does not appear to be a psychological survey.",
            lambda m, rc, df, k, ctx: m.modality not in {Modality.TABULAR_SURVEY, Modality.TABULAR_HR},
            Severity.WARN,
            "burnout_intelligence",
            "Burnout analysis is most reliable with Likert-scale survey data.",
        ),
    ],

    # ── Time-series ───────────────────────────────────────────────────────────
    "timeseries_forecast": [
        (
            "no_temporal_warns_ts",
            "No datetime or sequence column detected — time-series forecasting may not be meaningful.",
            lambda m, rc, df, k, ctx: not ctx.get("has_temporal_column", False),
            Severity.WARN,
            "timeseries_forecast",
            "Add a timestamp or date column to enable proper time-series analysis.",
        ),
    ],
}

# Analyses always allowed regardless of dataset type
_ALWAYS_ALLOWED: Set[str] = {"data_profiling", "schema_mapping", "compatibility_matrix"}


# ── SandboxValidator ──────────────────────────────────────────────────────────

class SandboxValidator:
    """
    Pre-render sandbox validator.
    Call validate_all() before rendering ANY dashboard.
    """

    def validate_all(
        self,
        modality_result: ModalityResult,
        routing_conf: RoutingConfidence,
        df: pd.DataFrame,
        ctx: Dict[str, Any],
        analyses_requested: Optional[List[str]] = None,
    ) -> SandboxReport:
        """
        Run all guards for all requested analyses.

        ctx keys:
          target_available (bool)
          target_column (str|None)
          feature_columns (List[str])
          missing_rate_overall (float)
          has_department_column (bool)
          has_temporal_column (bool)
          semantic_mapping (SemanticMapping|None)
        """
        if analyses_requested is None:
            from .dataset_contract import ANALYSIS_KEYS
            analyses_requested = list(ANALYSIS_KEYS)

        validated: Dict[str, GuardResult] = {}
        global_block_rules = _GUARD_RULES.get("any_analysis", [])

        # Global blocks first
        global_violations: List[GuardViolation] = []
        for rule_name, desc, check_fn, severity, blocked, rec in global_block_rules:
            try:
                fired = check_fn(modality_result, routing_conf, df, "any_analysis", ctx)
            except Exception:
                fired = False
            if fired and severity == Severity.BLOCK:
                global_violations.append(GuardViolation(
                    rule_name=rule_name,
                    severity=severity,
                    message=desc,
                    analysis_blocked="all",
                    recommendation=rec,
                ))

        critical_failures = [v.message for v in global_violations]

        # Per-analysis guards
        globally_blocked: List[str] = []
        globally_available: List[str] = []

        for analysis in analyses_requested:
            if analysis in _ALWAYS_ALLOWED:
                result = GuardResult(
                    analysis_requested=analysis,
                    allowed=True,
                    violations=[],
                    warnings=[],
                    logs=[],
                    allowed_alternatives=[analysis],
                    suppression_reason="",
                    confidence_score=routing_conf.overall_confidence,
                    validity_score=modality_result.validity_score,
                    provenance=[f"{analysis} is always allowed"],
                    degraded_mode=False,
                )
                validated[analysis] = result
                globally_available.append(analysis)
                continue

            # If global block fires, all prediction analyses are blocked
            if global_violations:
                result = GuardResult(
                    analysis_requested=analysis,
                    allowed=False,
                    violations=global_violations,
                    warnings=[],
                    logs=[],
                    allowed_alternatives=list(_ALWAYS_ALLOWED),
                    suppression_reason=global_violations[0].message,
                    confidence_score=routing_conf.overall_confidence,
                    validity_score=modality_result.validity_score,
                    provenance=["Blocked by global guard violation"],
                    degraded_mode=False,
                )
                validated[analysis] = result
                globally_blocked.append(analysis)
                continue

            result = self.validate_one(modality_result, routing_conf, df, analysis, ctx)
            validated[analysis] = result
            if result.allowed:
                globally_available.append(analysis)
            else:
                globally_blocked.append(analysis)

        # Dataset health score
        health = self._dataset_health(modality_result, routing_conf, df, ctx)

        # Advisory notes
        advisory: List[str] = []
        if routing_conf.overall_confidence < 0.60:
            advisory.append(f"Low routing confidence ({routing_conf.overall_confidence:.0%}) — review dataset type.")
        if ctx.get("missing_rate_overall", 0) > 0.30:
            advisory.append(f"High missing data ({ctx.get('missing_rate_overall'):.0%}) — address before modelling.")
        sem = ctx.get("semantic_mapping")
        if sem and sem.protected_attributes:
            advisory.append(f"Protected attributes detected: {sem.protected_attributes}. Run fairness audit.")
        if not ctx.get("target_available") and modality_result.modality == Modality.TABULAR_HR:
            advisory.append("No target column detected — only unsupervised analytics available.")

        provenance = [
            f"Modality: {modality_result.modality.value} ({routing_conf.overall_confidence:.0%} confidence)",
            f"Global violations: {len(global_violations)}",
            f"Analyses available: {len(globally_available)} / {len(analyses_requested)}",
            f"Dataset health: {health:.0%}",
        ]

        return SandboxReport(
            modality=modality_result.modality.value,
            routing_confidence=routing_conf.overall_confidence,
            validated_analyses=validated,
            globally_blocked=globally_blocked,
            globally_available=globally_available,
            dataset_health_score=health,
            critical_failures=critical_failures,
            advisory_notes=advisory,
            provenance=provenance,
        )

    def validate_one(
        self,
        modality_result: ModalityResult,
        routing_conf: RoutingConfidence,
        df: pd.DataFrame,
        analysis_key: str,
        ctx: Dict[str, Any],
    ) -> GuardResult:
        """Validate a single analysis against all applicable rules."""
        rules = _GUARD_RULES.get(analysis_key, [])
        violations: List[GuardViolation] = []
        warnings_list: List[GuardViolation] = []
        logs: List[GuardViolation] = []

        for rule_name, desc, check_fn, severity, blocked, rec in rules:
            try:
                fired = check_fn(modality_result, routing_conf, df, analysis_key, ctx)
            except Exception:
                fired = False
            if not fired:
                continue
            v = GuardViolation(
                rule_name=rule_name,
                severity=severity,
                message=desc,
                analysis_blocked=blocked,
                recommendation=rec,
            )
            if severity == Severity.BLOCK:
                violations.append(v)
            elif severity == Severity.WARN:
                warnings_list.append(v)
            else:
                logs.append(v)

        allowed = len(violations) == 0
        degraded = allowed and len(warnings_list) > 0

        alternatives = self._alternatives(analysis_key, modality_result.modality)
        suppression_reason = violations[0].message if violations else ""

        provenance = [
            f"Rules checked: {len(rules)}",
            f"Violations: {len(violations)}, Warnings: {len(warnings_list)}",
            f"Decision: {'ALLOWED' + (' (degraded)' if degraded else '') if allowed else 'BLOCKED'}",
        ]
        if violations:
            provenance.append(f"Blocking rule: {violations[0].rule_name}")

        return GuardResult(
            analysis_requested=analysis_key,
            allowed=allowed,
            violations=violations,
            warnings=warnings_list,
            logs=logs,
            allowed_alternatives=alternatives,
            suppression_reason=suppression_reason,
            confidence_score=routing_conf.overall_confidence,
            validity_score=modality_result.validity_score,
            provenance=provenance,
            degraded_mode=degraded,
        )

    def _alternatives(self, analysis_key: str, modality: Modality) -> List[str]:
        """Suggest valid alternatives when an analysis is blocked."""
        always = list(_ALWAYS_ALLOWED)
        if modality == Modality.BIOSIGNAL:
            return always + ["biosignal_stress_analysis"]
        if modality in {Modality.TABULAR_HR}:
            return always + ["attrition_prediction", "burnout_intelligence", "department_stability",
                             "retention_roi", "fairness_audit"]
        if modality == Modality.TABULAR_SURVEY:
            return always + ["burnout_intelligence", "psychological_constructs"]
        return always

    def _dataset_health(
        self,
        modality_result: ModalityResult,
        routing_conf: RoutingConfidence,
        df: pd.DataFrame,
        ctx: Dict,
    ) -> float:
        score = 1.0
        score *= routing_conf.overall_confidence
        score *= modality_result.validity_score
        missing = ctx.get("missing_rate_overall", 0.0)
        if missing > 0.50:
            score *= 0.60
        elif missing > 0.30:
            score *= 0.80
        n = len(df)
        if n < 20:
            score *= 0.40
        elif n < 100:
            score *= 0.70
        return round(min(1.0, max(0.0, score)), 4)
