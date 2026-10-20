"""
Adaptive Visualization Engine
Schema-aware chart recommendation for any dataset type.

Produces VizConfig objects that describe the MOST APPROPRIATE chart
for a given DataFrame and semantic mapping — without assuming HR schema.

Principles:
  - Never recommend HR-specific charts (attrition funnel, replacement cost)
    unless the contract explicitly allows it.
  - Chart type is inferred from column semantics, not column names.
  - Confidence and rationale are always attached.
  - Returns empty list if no valid visualization can be determined.
  - Charts are ranked by analytical value, not visual novelty.

Output is a spec (VizConfig) — rendering is done by the frontend.
This engine does NOT import Streamlit or Plotly.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from .modality_classifier import Modality, ModalityResult
from .semantic_column_mapper import SemanticMapping, SemanticRole


# ── Chart types ────────────────────────────────────────────────────────────────

class ChartType(str, Enum):
    HISTOGRAM         = "histogram"
    BOX               = "box"
    VIOLIN            = "violin"
    BAR               = "bar"
    GROUPED_BAR       = "grouped_bar"
    HEATMAP           = "heatmap"
    SCATTER           = "scatter"
    LINE              = "line"
    AREA              = "area"
    PIE               = "pie"
    CORRELATION_MATRIX= "correlation_matrix"
    DISTRIBUTION_GRID = "distribution_grid"
    TIME_SERIES       = "time_series"
    MISSING_HEATMAP   = "missing_heatmap"
    RADAR             = "radar"
    SANKEY            = "sankey"
    KDE               = "kde"


# ── VizConfig ─────────────────────────────────────────────────────────────────

@dataclass
class VizConfig:
    """
    Specification for a single visualization.
    Frontend renders this spec; it does not contain rendered objects.
    """
    chart_id:          str
    chart_type:        ChartType
    title:             str
    x_col:            Optional[str]
    y_col:            Optional[str]
    color_col:        Optional[str]
    facet_col:        Optional[str]
    agg_fn:           str              # "none" / "mean" / "count" / "sum"
    x_label:          str
    y_label:          str
    confidence:       float            # 0–1 how appropriate is this chart
    rationale:        str              # why this chart was chosen
    caveats:          List[str]
    priority:         int              # 1=highest, larger=lower
    requires_contract_key: str        # "" = always show; otherwise show only if contract allows
    additional_cols:  List[str] = field(default_factory=list)


# ── Engine ────────────────────────────────────────────────────────────────────

class AdaptiveVisualizationEngine:
    """
    Recommends visualizations appropriate for the detected dataset modality
    and semantic column mapping.
    """

    def recommend(
        self,
        df: pd.DataFrame,
        modality_result: ModalityResult,
        semantic_mapping: SemanticMapping,
        max_charts: int = 12,
        contract_keys_allowed: Optional[List[str]] = None,
    ) -> List[VizConfig]:
        """
        Produce ranked list of VizConfig recommendations.
        Only includes charts where contract_keys_allowed covers the required key
        (or requires_contract_key == "").
        """
        if contract_keys_allowed is None:
            contract_keys_allowed = ["data_profiling", "schema_mapping"]

        modality = modality_result.modality
        configs: List[VizConfig] = []

        # ── Universal charts (always safe) ────────────────────────────────────
        configs.extend(self._universal_charts(df, semantic_mapping))

        # ── Modality-specific charts ──────────────────────────────────────────
        if modality == Modality.BIOSIGNAL:
            configs.extend(self._biosignal_charts(df, semantic_mapping))
        elif modality == Modality.TABULAR_HR:
            configs.extend(self._hr_charts(df, semantic_mapping))
        elif modality == Modality.TABULAR_SURVEY:
            configs.extend(self._survey_charts(df, semantic_mapping))
        elif modality == Modality.TABULAR_FINANCIAL:
            configs.extend(self._financial_charts(df, semantic_mapping))
        elif modality == Modality.GENERIC_TIMESERIES:
            configs.extend(self._timeseries_charts(df, semantic_mapping))
        elif modality == Modality.NLP_TEXT:
            configs.extend(self._text_charts(df, semantic_mapping))
        else:
            configs.extend(self._generic_tabular_charts(df, semantic_mapping))

        # Filter by contract
        filtered = [
            c for c in configs
            if not c.requires_contract_key or c.requires_contract_key in contract_keys_allowed
        ]

        # Sort by priority then confidence
        filtered.sort(key=lambda c: (c.priority, -c.confidence))

        return filtered[:max_charts]

    # ── Universal charts ──────────────────────────────────────────────────────

    def _universal_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []

        # Missing data heatmap — always valuable
        missing_cols = [c for c in df.columns if df[c].isna().any()]
        if missing_cols:
            configs.append(VizConfig(
                chart_id="missing_heatmap",
                chart_type=ChartType.MISSING_HEATMAP,
                title="Missing Data Overview",
                x_col=None, y_col=None, color_col=None, facet_col=None,
                agg_fn="none",
                x_label="Column", y_label="Row",
                confidence=0.95,
                rationale=f"{len(missing_cols)} columns have missing values — visualise pattern.",
                caveats=["Missing pattern may indicate systematic data collection issues."],
                priority=1,
                requires_contract_key="",
            ))

        # Numeric distribution grid
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(num_cols) >= 2:
            configs.append(VizConfig(
                chart_id="distribution_grid",
                chart_type=ChartType.DISTRIBUTION_GRID,
                title="Numeric Column Distributions",
                x_col=None, y_col=None, color_col=None, facet_col=None,
                agg_fn="none",
                x_label="Value", y_label="Frequency",
                confidence=0.90,
                rationale=f"{len(num_cols)} numeric columns — distribution overview.",
                caveats=["Distributions may be skewed; check for outliers before modelling."],
                priority=2,
                requires_contract_key="",
                additional_cols=num_cols[:10],
            ))

        # Correlation matrix (if enough numeric columns)
        if len(num_cols) >= 3:
            configs.append(VizConfig(
                chart_id="correlation_matrix",
                chart_type=ChartType.CORRELATION_MATRIX,
                title="Feature Correlation Matrix",
                x_col=None, y_col=None, color_col=None, facet_col=None,
                agg_fn="none",
                x_label="Feature", y_label="Feature",
                confidence=0.85,
                rationale="Correlation matrix reveals multicollinearity and feature relationships.",
                caveats=["Pearson correlation only; non-linear relationships not captured."],
                priority=3,
                requires_contract_key="schema_mapping",
                additional_cols=num_cols[:20],
            ))

        return configs

    # ── Biosignal charts ──────────────────────────────────────────────────────

    def _biosignal_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []
        sig_cols = sem.biosignal_columns or df.select_dtypes(include=[np.number]).columns.tolist()

        if not sig_cols:
            return configs

        primary = sig_cols[0]

        # Raw signal time-series
        configs.append(VizConfig(
            chart_id="biosignal_timeseries",
            chart_type=ChartType.TIME_SERIES,
            title=f"Raw Signal — {primary}",
            x_col=None,   # index as x
            y_col=primary,
            color_col=None, facet_col=None,
            agg_fn="none",
            x_label="Sample Index",
            y_label=f"{primary} Amplitude",
            confidence=0.95,
            rationale="Raw physiological signal visualisation.",
            caveats=[
                "Non-clinical tool — not a diagnostic device.",
                "Signal amplitude units depend on sensor calibration.",
            ],
            priority=1,
            requires_contract_key="biosignal_stress_analysis",
        ))

        # Amplitude distribution
        configs.append(VizConfig(
            chart_id="biosignal_amplitude_dist",
            chart_type=ChartType.HISTOGRAM,
            title=f"Signal Amplitude Distribution — {primary}",
            x_col=primary,
            y_col=None, color_col=None, facet_col=None,
            agg_fn="none",
            x_label="Amplitude",
            y_label="Frequency",
            confidence=0.85,
            rationale="Distribution of signal amplitude values.",
            caveats=["Non-clinical. Consult a healthcare professional for clinical interpretation."],
            priority=2,
            requires_contract_key="biosignal_stress_analysis",
        ))

        return configs

    # ── HR charts ─────────────────────────────────────────────────────────────

    def _hr_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []

        # Target distribution (attrition rate)
        target_cols = sem.target_candidates
        if target_cols:
            target = target_cols[0]
            configs.append(VizConfig(
                chart_id="hr_target_dist",
                chart_type=ChartType.BAR,
                title=f"Target Distribution — {target}",
                x_col=target, y_col=None, color_col=None, facet_col=None,
                agg_fn="count",
                x_label=target, y_label="Count",
                confidence=0.90,
                rationale="Distribution of the prediction target across classes.",
                caveats=["Class imbalance affects model performance."],
                priority=1,
                requires_contract_key="attrition_prediction",
            ))

        # Department breakdown
        dept_cols = [c for c in sem.hr_columns if "department" in c.lower() or "division" in c.lower()]
        if dept_cols and target_cols:
            configs.append(VizConfig(
                chart_id="hr_dept_breakdown",
                chart_type=ChartType.GROUPED_BAR,
                title="Outcome by Department",
                x_col=dept_cols[0], y_col=target_cols[0], color_col=target_cols[0], facet_col=None,
                agg_fn="count",
                x_label="Department", y_label="Count",
                confidence=0.85,
                rationale="Department-level breakdown of target outcome.",
                caveats=["Small departments may have unreliable rates."],
                priority=2,
                requires_contract_key="department_stability",
            ))

        # Numeric feature distributions by target
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        hr_num = [c for c in num_cols if c in sem.hr_columns or c in sem.feature_columns][:5]
        if hr_num and target_cols:
            for col in hr_num[:3]:
                configs.append(VizConfig(
                    chart_id=f"hr_box_{col}",
                    chart_type=ChartType.BOX,
                    title=f"{col} by {target_cols[0]}",
                    x_col=target_cols[0], y_col=col, color_col=target_cols[0], facet_col=None,
                    agg_fn="none",
                    x_label=target_cols[0], y_label=col,
                    confidence=0.80,
                    rationale=f"Distribution of {col} split by target outcome.",
                    caveats=[],
                    priority=3,
                    requires_contract_key="attrition_prediction",
                ))

        # Protected attribute distribution
        for prot in sem.protected_attributes[:2]:
            configs.append(VizConfig(
                chart_id=f"prot_dist_{prot}",
                chart_type=ChartType.BAR,
                title=f"Distribution of {prot}",
                x_col=prot, y_col=None, color_col=None, facet_col=None,
                agg_fn="count",
                x_label=prot, y_label="Count",
                confidence=0.75,
                rationale=f"Protected attribute distribution — required for fairness audit.",
                caveats=["This attribute requires fairness review before use in modelling."],
                priority=4,
                requires_contract_key="fairness_audit",
            ))

        return configs

    # ── Survey charts ─────────────────────────────────────────────────────────

    def _survey_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []
        survey_cols = sem.survey_columns
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        likert_cols = [c for c in num_cols if 1 <= (df[c].dropna().max() if len(df[c].dropna()) else 0) <= 7][:10]

        if likert_cols:
            configs.append(VizConfig(
                chart_id="survey_likert_means",
                chart_type=ChartType.BAR,
                title="Mean Survey Item Scores",
                x_col=None, y_col=None, color_col=None, facet_col=None,
                agg_fn="mean",
                x_label="Survey Item", y_label="Mean Score",
                confidence=0.85,
                rationale="Mean Likert scores across all survey items.",
                caveats=["Mean may mask bimodal distributions — check histograms."],
                priority=1,
                requires_contract_key="burnout_intelligence",
                additional_cols=likert_cols,
            ))

            if len(likert_cols) >= 3:
                configs.append(VizConfig(
                    chart_id="survey_correlation",
                    chart_type=ChartType.CORRELATION_MATRIX,
                    title="Survey Item Correlation",
                    x_col=None, y_col=None, color_col=None, facet_col=None,
                    agg_fn="none",
                    x_label="Item", y_label="Item",
                    confidence=0.80,
                    rationale="Inter-item correlations for construct validity check.",
                    caveats=["High inter-item correlation may indicate redundancy."],
                    priority=2,
                    requires_contract_key="burnout_intelligence",
                    additional_cols=likert_cols,
                ))

        return configs

    # ── Financial charts ──────────────────────────────────────────────────────

    def _financial_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []
        fin_cols = sem.financial_columns
        temp_cols = sem.temporal_columns

        if fin_cols:
            primary = fin_cols[0]
            if temp_cols:
                configs.append(VizConfig(
                    chart_id="financial_timeseries",
                    chart_type=ChartType.LINE,
                    title=f"{primary} Over Time",
                    x_col=temp_cols[0], y_col=primary, color_col=None, facet_col=None,
                    agg_fn="sum",
                    x_label="Date", y_label=primary,
                    confidence=0.85,
                    rationale="Financial metric trend over time.",
                    caveats=["Seasonal effects not automatically controlled."],
                    priority=1,
                    requires_contract_key="timeseries_forecast",
                ))

            configs.append(VizConfig(
                chart_id="financial_dist",
                chart_type=ChartType.HISTOGRAM,
                title=f"Distribution of {primary}",
                x_col=primary, y_col=None, color_col=None, facet_col=None,
                agg_fn="none",
                x_label=primary, y_label="Frequency",
                confidence=0.80,
                rationale="Distribution of primary financial metric.",
                caveats=["Outliers may represent anomalous transactions."],
                priority=2,
                requires_contract_key="",
            ))

        return configs

    # ── Time-series charts ────────────────────────────────────────────────────

    def _timeseries_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []
        temp_cols = sem.temporal_columns
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if num_cols:
            primary = num_cols[0]
            x = temp_cols[0] if temp_cols else None
            configs.append(VizConfig(
                chart_id="ts_primary",
                chart_type=ChartType.LINE,
                title=f"{primary} Time Series",
                x_col=x, y_col=primary, color_col=None, facet_col=None,
                agg_fn="none",
                x_label=x or "Index", y_label=primary,
                confidence=0.85,
                rationale="Primary numeric metric over time.",
                caveats=["Trend may be driven by external factors not in this dataset."],
                priority=1,
                requires_contract_key="timeseries_forecast",
            ))

        return configs

    # ── NLP/text charts ───────────────────────────────────────────────────────

    def _text_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not num_cols:
            return []
        return [VizConfig(
            chart_id="text_length_dist",
            chart_type=ChartType.HISTOGRAM,
            title="Text Length Distribution",
            x_col=None, y_col=None, color_col=None, facet_col=None,
            agg_fn="none",
            x_label="Character Count", y_label="Frequency",
            confidence=0.70,
            rationale="Distribution of text field lengths.",
            caveats=["Text length is a proxy — full NLP analysis not performed here."],
            priority=1,
            requires_contract_key="",
        )]

    # ── Generic tabular ───────────────────────────────────────────────────────

    def _generic_tabular_charts(self, df: pd.DataFrame, sem: SemanticMapping) -> List[VizConfig]:
        configs: List[VizConfig] = []
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        if num_cols:
            configs.append(VizConfig(
                chart_id="generic_num_dist",
                chart_type=ChartType.BOX,
                title="Numeric Column Distributions (Box Plots)",
                x_col=None, y_col=None, color_col=None, facet_col=None,
                agg_fn="none",
                x_label="Column", y_label="Value",
                confidence=0.75,
                rationale="Box plots for all numeric columns — outlier and spread overview.",
                caveats=["Dataset type unknown — interpret with caution."],
                priority=1,
                requires_contract_key="",
                additional_cols=num_cols[:10],
            ))

        if cat_cols:
            primary_cat = min(cat_cols, key=lambda c: int(df[c].nunique()))
            configs.append(VizConfig(
                chart_id="generic_cat_dist",
                chart_type=ChartType.BAR,
                title=f"Value Counts — {primary_cat}",
                x_col=primary_cat, y_col=None, color_col=None, facet_col=None,
                agg_fn="count",
                x_label=primary_cat, y_label="Count",
                confidence=0.70,
                rationale="Frequency distribution of most categorical column.",
                caveats=["Dataset type undetermined — verify before interpretation."],
                priority=2,
                requires_contract_key="",
            ))

        return configs


# ── Convenience function ──────────────────────────────────────────────────────

def recommend_charts(
    df: pd.DataFrame,
    modality_result: ModalityResult,
    semantic_mapping: SemanticMapping,
    contract_keys_allowed: Optional[List[str]] = None,
    max_charts: int = 10,
) -> List[VizConfig]:
    engine = AdaptiveVisualizationEngine()
    return engine.recommend(
        df=df,
        modality_result=modality_result,
        semantic_mapping=semantic_mapping,
        max_charts=max_charts,
        contract_keys_allowed=contract_keys_allowed,
    )
