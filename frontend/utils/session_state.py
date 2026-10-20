"""
Session State & Singleton Management
Centralized session defaults and cached singleton registry.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from config.settings import DEFAULT_CURRENCY

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────

SESSION_DEFAULTS: dict = {
    # Dataset
    "df":               None,
    "filename":         "",
    "raw":              None,
    # Analysis
    "profile":          None,
    "sem_map":          None,
    "contract":         None,
    "df_clean":         None,
    "df_eng":           None,
    "ml_result":        None,
    "ind_risks":        None,
    "dept_risks":       None,
    "org_risk":         None,
    "insight_report":   None,
    "biosignal_profile": None,
    "ts_result":        None,
    "analysis_done":    False,
    "explain_report":   None,
    "ethical_report":   None,
    "confidence_profile": None,
    "exec_report":      None,
    "telemetry":        None,
    # Enterprise governance
    "unified_confidence": None,
    "feature_trust":    None,
    "currency":         DEFAULT_CURRENCY,
    "demo_mode":        False,
    "mask_employee_ids": True,
}


def init_session() -> None:
    """Initialize all session state keys with defaults if not already set."""
    for k, v in SESSION_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_analysis_state() -> None:
    """Clear all analysis outputs while keeping dataset and settings."""
    keep = {"df", "filename", "raw", "profile", "sem_map", "contract",
            "currency", "demo_mode", "mask_employee_ids"}
    analysis_keys = [k for k in SESSION_DEFAULTS if k not in keep]
    for k in analysis_keys:
        st.session_state[k] = SESSION_DEFAULTS[k]


def get_contract():
    from backend.core.dataset_contract import DatasetContract
    return st.session_state.get("contract")


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def get_singletons() -> dict:
    """Cached singleton registry — loaded once per Streamlit process."""
    from backend.core.dataset_profiler import DatasetProfiler
    from backend.core.semantic_mapper import SemanticMapper
    from backend.core.adaptive_router import AdaptiveRouter
    from backend.core.feature_factory import FeatureFactory
    from backend.core.ml_router import MLRouter
    from backend.core.insight_generator import InsightGenerator
    from backend.core.biosignal_adapter import BiosignalAdapter
    from backend.core.timeseries_engine import TimeSeriesEngine
    from backend.core.explainability_engine import ExplainabilityEngine
    from backend.core.ethical_ai import EthicalAIEngine
    from backend.core.confidence_engine import ConfidenceEngine
    from backend.core.report_generator import ReportGenerator

    return {
        "profiler":    DatasetProfiler(),
        "mapper":      SemanticMapper(),
        "router":      AdaptiveRouter(),
        "factory":     FeatureFactory(),
        "ml_router":   MLRouter(),
        "insight_gen": InsightGenerator(),
        "biosignal":   BiosignalAdapter(),
        "ts_engine":   TimeSeriesEngine(),
        "explain_eng": ExplainabilityEngine(),
        "ethical_eng": EthicalAIEngine(),
        "conf_eng":    ConfidenceEngine(),
        "report_gen":  ReportGenerator(),
    }
