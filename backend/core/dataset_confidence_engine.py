"""
Dataset Confidence Engine
Multi-signal confidence scoring for routing decisions.

Aggregates evidence from:
  - ModalityClassifier output
  - Semantic column mapping
  - Value distribution analysis
  - Statistical structural features
  - Filename signals
  - Cross-signal consistency

Every score carries:
  confidence, provenance, assumptions, caveats, validity_score

The engine NEVER fabricates confidence. When evidence is weak,
it lowers the score rather than defaulting to a plausible-sounding value.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from .modality_classifier import ModalityResult, Modality


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ConfidenceSignal:
    """One piece of evidence contributing to the routing confidence."""
    source: str          # "modality_classifier" / "column_keywords" / "value_dist" / "cross_signal"
    description: str
    value: float         # raw signal value (e.g. keyword score)
    weight: float        # importance weight
    contribution: float  # value × weight, used in final sum
    trust: float         # how reliable is this source (0–1)


@dataclass
class RoutingConfidence:
    """
    Complete confidence assessment for a routing decision.
    The final arbiter before any analysis is allowed.
    """
    dataset_type: str
    overall_confidence: float           # 0–1 final governed score
    raw_confidence: float               # before governance penalties
    confidence_band: str                # "Very High" / "High" / "Moderate" / "Low" / "Unreliable"
    signals: List[ConfidenceSignal]
    provenance: List[str]
    assumptions: List[str]
    caveats: List[str]
    validity_score: float               # 0–1 quality of the confidence estimate itself
    requires_human_confirmation: bool   # True if confidence < threshold
    suppressed_analyses: List[str]      # analyses blocked due to low confidence
    routing_locked: bool                # True if routing is certain (filename hard-rule)

    # Per-modality scores used for tie-breaking
    modality_scores: Dict[str, float] = field(default_factory=dict)


# ── Analysis-level confidence thresholds ─────────────────────────────────────

# Minimum overall routing confidence to allow each analysis type
_ANALYSIS_THRESHOLDS: Dict[str, float] = {
    "attrition_prediction":       0.65,  # needs high HR confidence
    "burnout_intelligence":       0.55,
    "psychological_constructs":   0.55,
    "biosignal_stress_analysis":  0.70,  # needs high biosignal confidence
    "timeseries_forecast":        0.50,
    "fairness_audit":             0.60,
    "department_stability":       0.60,
    "retention_roi":              0.65,
    "pdf_report":                 0.40,
    "data_profiling":             0.00,  # always allowed
    "schema_mapping":             0.00,  # always allowed
    "compatibility_matrix":       0.00,  # always allowed
    "supervised_ml":              0.65,
    "unsupervised_clustering":    0.30,
}

# Governance penalty multipliers
_PENALTY_SMALL_DATASET   = 0.80   # < 50 rows
_PENALTY_TINY_DATASET    = 0.55   # < 20 rows
_PENALTY_FEW_COLS        = 0.75   # < 3 columns
_PENALTY_LOW_MODALITY    = 0.70   # modality_classifier confidence < 0.50
_PENALTY_AMBIGUOUS       = 0.80   # runner-up within 20% of winner
_PENALTY_NO_FILENAME     = 0.90   # no informative filename
_PENALTY_HIGH_MISSING    = 0.85   # >30% missing values overall


# ── Engine ───────────────────────────────────────────────────────────────────

class DatasetConfidenceEngine:
    """
    Aggregates all available signals to produce a governed routing confidence score.
    Designed to fail conservatively — doubts low confidence, never inflates it.
    """

    def score(
        self,
        modality_result: ModalityResult,
        df: pd.DataFrame,
        filename: str = "",
        missing_rate_overall: float = 0.0,
        semantic_col_scores: Optional[Dict[str, float]] = None,
    ) -> RoutingConfidence:
        """
        Compute routing confidence from all available evidence.

        Args:
            modality_result: output of ModalityClassifier.classify()
            df: the DataFrame
            filename: original filename
            missing_rate_overall: fraction of missing values across full dataset
            semantic_col_scores: per-semantic-role coverage scores from SemanticColumnMapper
        """
        signals: List[ConfidenceSignal] = []
        assumptions: List[str] = []
        caveats: List[str] = []
        modality_scores: Dict[str, float] = {}

        # ── Signal 1: ModalityClassifier base confidence ──────────────────────
        mc_conf = modality_result.confidence
        mc_signal = ConfidenceSignal(
            source="modality_classifier",
            description=f"Modality classifier: {modality_result.modality.value} at {mc_conf:.0%}",
            value=mc_conf,
            weight=4.0,
            contribution=mc_conf * 4.0,
            trust=modality_result.validity_score,
        )
        signals.append(mc_signal)
        modality_scores[modality_result.modality.value] = mc_conf
        if modality_result.runner_up:
            modality_scores[modality_result.runner_up.value] = modality_result.runner_up_confidence

        # ── Signal 2: Filename hard-rule bonus ────────────────────────────────
        routing_locked = False
        filename_lower = filename.lower()
        stem = filename_lower.rsplit(".", 1)[0] if "." in filename_lower else filename_lower

        _HARD_RULE_STEMS = {"hr", "eda", "bvp", "temp", "acc", "ibi", "ecg", "eeg", "ppg", "emg"}
        if stem in _HARD_RULE_STEMS:
            routing_locked = True
            signals.append(ConfidenceSignal(
                source="filename_hard_rule",
                description=f"Filename '{filename}' matches hard-rule stem → routing locked",
                value=1.0,
                weight=5.0,
                contribution=5.0,
                trust=1.0,
            ))
        elif not filename or filename in ("", "unnamed", "data.csv", "upload.csv"):
            # No useful filename — apply penalty
            signals.append(ConfidenceSignal(
                source="filename",
                description="Non-informative filename — cannot use as routing signal",
                value=0.0,
                weight=1.0,
                contribution=0.0,
                trust=0.5,
            ))
            caveats.append("Filename provides no routing signal — classification relies on content only.")

        # ── Signal 3: Semantic column coverage ────────────────────────────────
        if semantic_col_scores:
            dominant = max(semantic_col_scores, key=semantic_col_scores.get)
            dom_score = semantic_col_scores[dominant]
            if dom_score > 0.0:
                signals.append(ConfidenceSignal(
                    source="semantic_columns",
                    description=f"Dominant semantic role: '{dominant}' ({dom_score:.0%} coverage)",
                    value=dom_score,
                    weight=3.0,
                    contribution=dom_score * 3.0,
                    trust=0.85,
                ))
                # Alignment bonus: semantic dominant role matches modality
                if _semantic_matches_modality(dominant, modality_result.modality):
                    signals.append(ConfidenceSignal(
                        source="cross_signal",
                        description="Semantic role aligns with modality classification — cross-signal agreement",
                        value=0.20,
                        weight=2.0,
                        contribution=0.20 * 2.0,
                        trust=0.90,
                    ))
                else:
                    caveats.append(f"Semantic role '{dominant}' does not fully align with modality '{modality_result.modality.value}'.")
            assumptions.append("SemanticColumnMapper roles are correct for this dataset schema.")

        # ── Signal 4: Evidence signal count bonus ─────────────────────────────
        strong_evidence = [e for e in modality_result.evidence if e.weight >= 2.0]
        if len(strong_evidence) >= 3:
            signals.append(ConfidenceSignal(
                source="evidence_count",
                description=f"{len(strong_evidence)} strong evidence signals agree — high confidence",
                value=0.15,
                weight=2.0,
                contribution=0.15 * 2.0,
                trust=0.80,
            ))
        elif len(strong_evidence) == 0:
            caveats.append("No strong evidence signals — classification is speculative.")

        # ── Compute raw confidence ────────────────────────────────────────────
        total_contribution = sum(s.contribution for s in signals)
        total_weight       = sum(s.weight for s in signals)
        raw_conf = total_contribution / max(total_weight, 1e-9)
        raw_conf = min(1.0, max(0.0, raw_conf))

        # ── Governance penalties ──────────────────────────────────────────────
        governed = raw_conf

        if routing_locked:
            # Hard-rule → always return near-max confidence
            governed = max(governed, 0.95)
        else:
            n_rows, n_cols = df.shape

            if n_rows < 20:
                governed *= _PENALTY_TINY_DATASET
                caveats.append(f"Very small dataset ({n_rows} rows) — confidence penalised.")
            elif n_rows < 50:
                governed *= _PENALTY_SMALL_DATASET
                caveats.append(f"Small dataset ({n_rows} rows) — routing less certain.")

            if n_cols < 3:
                governed *= _PENALTY_FEW_COLS
                caveats.append(f"Only {n_cols} column(s) — limited routing signal.")

            if mc_conf < 0.50:
                governed *= _PENALTY_LOW_MODALITY
                caveats.append(f"Modality classifier low confidence ({mc_conf:.0%}) — penalty applied.")

            # Ambiguity penalty: if runner-up is close
            ruc = modality_result.runner_up_confidence
            if mc_conf > 0 and ruc / max(mc_conf, 1e-9) > 0.70:
                governed *= _PENALTY_AMBIGUOUS
                caveats.append(
                    f"Runner-up modality '{modality_result.runner_up.value if modality_result.runner_up else '?'}' "
                    f"({ruc:.0%}) is close to winner ({mc_conf:.0%}) — routing ambiguous."
                )

            if missing_rate_overall > 0.30:
                governed *= _PENALTY_HIGH_MISSING
                caveats.append(f"High missing data ({missing_rate_overall:.0%}) limits classification reliability.")

        governed = round(min(1.0, max(0.0, governed)), 4)

        # ── Confidence band ───────────────────────────────────────────────────
        band = _band(governed)

        # ── Suppressed analyses ───────────────────────────────────────────────
        suppressed = _compute_suppressed(governed, modality_result.modality)

        # ── Validity score ────────────────────────────────────────────────────
        validity = _confidence_validity(signals, governed, modality_result.validity_score)

        # ── Provenance ────────────────────────────────────────────────────────
        provenance = [
            f"Dataset: {modality_result.modality.value} | confidence: {governed:.0%} [{band}]",
            f"Raw confidence before penalties: {raw_conf:.0%}",
            f"Routing locked by hard rule: {routing_locked}",
            f"Evidence signals used: {len(signals)}",
        ]
        for s in sorted(signals, key=lambda x: x.contribution, reverse=True)[:5]:
            provenance.append(f"  [{s.source}] {s.description} → contribution: {s.contribution:.3f}")
        if caveats:
            provenance.append(f"Caveats: {'; '.join(caveats[:3])}")

        requires_confirmation = governed < 0.55 and not routing_locked

        if not assumptions:
            assumptions.append("Dataset content is representative of the full population.")

        return RoutingConfidence(
            dataset_type=modality_result.modality.value,
            overall_confidence=governed,
            raw_confidence=round(raw_conf, 4),
            confidence_band=band,
            signals=signals,
            provenance=provenance,
            assumptions=assumptions,
            caveats=caveats,
            validity_score=validity,
            requires_human_confirmation=requires_confirmation,
            suppressed_analyses=suppressed,
            routing_locked=routing_locked,
            modality_scores=modality_scores,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _band(score: float) -> str:
    if score >= 0.90: return "Very High"
    if score >= 0.75: return "High"
    if score >= 0.55: return "Moderate"
    if score >= 0.40: return "Low"
    return "Unreliable"


def _semantic_matches_modality(semantic_role: str, modality: Modality) -> bool:
    mapping = {
        "employee_attribute":  [Modality.TABULAR_HR],
        "hr_outcome":          [Modality.TABULAR_HR],
        "biosignal_raw":       [Modality.BIOSIGNAL],
        "survey_item":         [Modality.TABULAR_SURVEY],
        "temporal":            [Modality.GENERIC_TIMESERIES, Modality.BIOSIGNAL],
        "financial_metric":    [Modality.TABULAR_FINANCIAL],
    }
    return modality in mapping.get(semantic_role, [])


def _compute_suppressed(confidence: float, modality: Modality) -> List[str]:
    """Return list of analyses that should be suppressed due to low confidence."""
    suppressed = []
    for analysis, threshold in _ANALYSIS_THRESHOLDS.items():
        if threshold == 0.0:
            continue
        if confidence < threshold:
            suppressed.append(analysis)
    # Always suppress HR analyses for non-HR modalities
    if modality != Modality.TABULAR_HR:
        for analysis in ["attrition_prediction", "department_stability", "retention_roi", "fairness_audit"]:
            if analysis not in suppressed:
                suppressed.append(analysis)
    # Always suppress biosignal for non-biosignal
    if modality != Modality.BIOSIGNAL:
        if "biosignal_stress_analysis" not in suppressed:
            suppressed.append("biosignal_stress_analysis")
    return list(set(suppressed))


def _confidence_validity(
    signals: List[ConfidenceSignal],
    governed: float,
    mc_validity: float,
) -> float:
    score = mc_validity
    if len(signals) < 2:
        score *= 0.70
    # Check trust levels of signals
    avg_trust = np.mean([s.trust for s in signals]) if signals else 0.5
    score *= avg_trust
    if governed < 0.40:
        score *= 0.80  # low confidence estimate itself is less reliable
    return round(min(1.0, max(0.0, score)), 4)
