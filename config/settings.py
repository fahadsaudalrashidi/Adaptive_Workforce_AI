"""
Adaptive Workforce AI — Global Configuration & Settings
Enterprise-grade universal workforce intelligence engine.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Any

# ── Phase 44: load .env into the process environment ───────────────────────
# python-dotenv was already an installed dependency (transitively) but no
# call to load_dotenv() existed ANYWHERE in this codebase before Phase 44 —
# every existing os.environ.get(...) below only ever worked if the variable
# happened to already be set in the shell. This is the single, centralized
# place it now happens: config/settings.py is imported before any other
# backend module that reads an env var at import time (e.g.
# local_enterprise_runtime.py's _DEFAULT_BASE_DIR), so loading here — before
# any os.environ.get() call in this file or any module imported after it —
# is the correct place, not a per-module ad hoc call.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# PLATFORM IDENTITY  (single authoritative source — used by UI + all reports)
#
# Phase 39 rebrand: the platform's real, live scope is no longer "workforce
# attrition prediction" (that engine — theory-construct generation, ML
# validation, the V1 ML/theory pipeline — was removed this phase). What
# remains and is actually reachable from the frontend: ~18 non-predictive HR
# modules (labor law/GOSI/Zakat calculators, letters, compliance trackers,
# workforce risk/cost analytics), 6 Business Intelligence domains (Financial,
# Accounting, Inventory, Procurement, Logistics, Operations), and the AI
# Business Analyst. The identity below reflects that — see
# PHASE_39_PREDICTION_REMOVAL_AND_ENTERPRISE_REBRAND_REPORT.md.
# ─────────────────────────────────────────────────────────────────────────────
PLATFORM_NAME    = "AWI Enterprise Intelligence Platform"
PLATFORM_VERSION = "3.0.0"
REPORT_VERSION   = "3.0"
MODEL_VERSION    = "3.0.0"
PLATFORM_TAGLINE = "Enterprise Intelligence — HR Operations, Business Intelligence & AI Analysis"
PLATFORM_AUTHOR  = "Enterprise AI Research Division"

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
DATA_DIR      = BASE_DIR / "data"
UPLOADS_DIR   = DATA_DIR / "uploads"
OUTPUTS_DIR   = DATA_DIR / "outputs"
MODELS_DIR    = BASE_DIR / "saved_models"
FRONTEND_DIR  = BASE_DIR / "frontend"

for _p in (UPLOADS_DIR, OUTPUTS_DIR, MODELS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# SUPPORTED FILE FORMATS
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS: List[str] = [".csv", ".xlsx", ".xls", ".json", ".parquet", ".pkl", ".feather"]
MAX_UPLOAD_MB: int = 500
MAX_ROWS_PROFILE: int = 500_000   # profile up to 500k rows; sample above

# ─────────────────────────────────────────────────────────────────────────────
# DATASET TYPE TAXONOMY
# ─────────────────────────────────────────────────────────────────────────────
DATASET_TYPES: List[str] = [
    "hr_attrition",           # employee turnover / attrition prediction
    "hr_engagement",          # engagement / satisfaction surveys
    "hr_performance",         # performance reviews & KPIs
    "hr_recruitment",         # talent acquisition & hiring funnel
    "burnout_survey",         # burnout / MBI-style instruments
    "psychological_survey",   # general psychometric / Likert surveys
    "org_network",            # organizational network / collaboration graph
    "time_series_hr",         # longitudinal HR metrics over time
    "biosignal",              # wearable / physiological sensor data
    "productivity",           # task / output / OKR tracking
    "compensation",           # salary, benefits, equity analysis
    "learning_development",   # training, certifications, skill acquisition
    "workforce_planning",     # headcount, capacity, FTE forecasting
    "mixed",                  # multi-domain combined dataset
    "unknown",                # could not determine type
]

# ─────────────────────────────────────────────────────────────────────────────
# COLUMN SEMANTIC CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
SEMANTIC_CATEGORIES: List[str] = [
    "target",                 # attrition/outcome label
    "employee_id",            # unique employee identifier
    "timestamp",              # date/time
    "age",                    # age in years
    "tenure",                 # time at company / in role
    "department",             # organizational unit
    "job_level",              # seniority / grade
    "gender",                 # gender identity
    "education",              # education level/field
    "salary",                 # compensation amount
    "performance",            # performance rating/score
    "satisfaction",           # job/life satisfaction
    "engagement",             # engagement score
    "burnout",                # burnout indicator
    "overtime",               # overtime hours/flag
    "workload",               # work volume/pressure
    "manager_quality",        # manager support/rating
    "team_size",              # direct reports / team members
    "distance",               # commute / distance from office
    "promotion",              # promotion history/recency
    "training",               # training hours/count
    "absence",                # absence days/rate
    "role_change",            # job change / role transitions
    "psychological_score",    # generic psych construct score
    "text_free",              # open-text / NLP field
    "binary_flag",            # yes/no indicator
    "numeric_kpi",            # generic numeric KPI
    "categorical_other",      # other categorical
    "unknown",
]

# ─────────────────────────────────────────────────────────────────────────────
# MACHINE LEARNING
# ─────────────────────────────────────────────────────────────────────────────
ML_TASK_TYPES: List[str] = ["binary_classification", "multiclass_classification",
                             "regression", "time_series_forecast", "clustering",
                             "survival_analysis", "anomaly_detection"]

# Model registry — which model IDs are available
TABULAR_MODELS: List[str] = ["lr", "rf", "xgb", "lgb", "catboost", "ensemble"]
TIMESERIES_MODELS: List[str] = ["prophet", "lstm", "arima", "exp_smoothing"]
BIOSIGNAL_MODELS: List[str] = ["cnn_lstm", "transformer", "random_forest_ts"]

DEFAULT_TEST_SIZE: float  = 0.20
DEFAULT_CV_FOLDS: int     = 5
DEFAULT_RANDOM_STATE: int = 42
MAX_OPTUNA_TRIALS: int    = 60
OPTUNA_TIMEOUT_SECS: int  = 300
MIN_CLASS_SAMPLES: int    = 30     # minimum per-class samples for classification

# Imbalance handling
IMBALANCE_RATIO_THRESHOLD: float = 1.5  # minority/majority < this → apply imbalance handling
SMOTE_STRATEGY: str = "auto"            # SMOTE sampling_strategy inside CV only

# ─────────────────────────────────────────────────────────────────────────────
# RISK INTELLIGENCE THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
RISK_LEVELS: Dict[str, Any] = {
    "critical":  {"min": 0.75, "color": "#dc2626", "label": "Critical"},
    "high":      {"min": 0.55, "color": "#ea580c", "label": "High"},
    "moderate":  {"min": 0.35, "color": "#d97706", "label": "Moderate"},
    "low":       {"min": 0.00, "color": "#16a34a", "label": "Low"},
}

BURNOUT_THRESHOLDS: Dict[str, float] = {"critical": 0.80, "high": 0.65, "moderate": 0.45}
ENGAGEMENT_THRESHOLDS: Dict[str, float] = {"critical": 0.30, "low": 0.45, "moderate": 0.65}

# ─────────────────────────────────────────────────────────────────────────────
# CURRENCY & FINANCIAL DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CURRENCY: str         = "SAR"          # Saudi Riyal — change per deployment
CURRENCY_OPTIONS: List[str]   = ["SAR", "USD", "AED", "EUR"]
CURRENCY_SYMBOLS: Dict[str, str] = {
    "SAR": "SAR",
    "USD": "$",
    "AED": "AED",
    "EUR": "€",
}
# Approximate exchange rates from USD (update per deployment)
CURRENCY_FROM_USD: Dict[str, float] = {
    "SAR": 3.75,    # 1 USD ≈ 3.75 SAR
    "USD": 1.00,
    "AED": 3.67,
    "EUR": 0.92,
}
DEFAULT_ANNUAL_SALARY_LOCAL: float = 120_000.0    # fallback salary in DEFAULT_CURRENCY (SAR)
ATTRITION_REPLACEMENT_COST_FACTOR: float = 0.50   # 50% of annual salary

# Legacy alias kept for backward compat
DEFAULT_ANNUAL_SALARY_USD: float = DEFAULT_ANNUAL_SALARY_LOCAL / CURRENCY_FROM_USD.get(DEFAULT_CURRENCY, 1.0)

# ─────────────────────────────────────────────────────────────────────────────
# ENTERPRISE GOVERNANCE LANGUAGE
# ─────────────────────────────────────────────────────────────────────────────
HUMAN_OVERSIGHT_DISCLAIMER: str = (
    "This system is a decision-support tool. It must not be used as the sole basis "
    "for employment, promotion, compensation, disciplinary, or termination decisions. "
    "All predictions require human validation before any personnel action is taken."
)

# Words / phrases forbidden from appearing in executive-facing AI output
FORBIDDEN_EXECUTIVE_PHRASES: List[str] = [
    "terminate", "terminated", "termination",
    "fire ", "fires ", "fired",
    "dismiss", "dismissed", "dismissal",
    "layoff", "lay off", "lay-off",
    "redundant", "made redundant",
    "will leave", "will resign", "will quit",
    "certain to leave", "guaranteed to leave",
    "must be removed", "should be removed",
    "eliminate this employee",
]

ATTRITION_LANGUAGE_SAFE: Dict[str, str] = {
    "require immediate action":     "flagged for HR review",
    "must intervene":               "recommended for human validation",
    "employees will leave":         "employees with elevated predicted risk",
    "critical employees":           "employees in priority review segment",
    "take action against":          "conduct structured review for",
    "will attrit":                  "show elevated predicted risk",
    "certain to leave":             "show the highest predicted risk",
    "increases risk":               "associated with elevated predicted risk",
    "decreases risk":               "associated with lower predicted risk",
    "high-risk employees":          "employees in the priority review segment",
    "require immediate retention":  "flagged for structured retention review",
}

# ─────────────────────────────────────────────────────────────────────────────
# SCIENTIFIC VALIDITY GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────

# AUC threshold above which mandatory calibration is required before "Suitable" verdict
MODEL_TRUTH_HIGH_AUC_THRESHOLD: float  = 0.85

# If AUC exceeds this on typical HR data, flag as suspicious without strong leakage evidence
MODEL_TRUTH_SUSPICIOUS_AUC_HR: float   = 0.92

# If more than this fraction of employees are classified high-risk, issue threshold warning
THRESHOLD_HIGH_RISK_PCT_WARN: float    = 0.40

# Proxy leakage keywords — feature names matching any of these are flagged
PROXY_LEAKAGE_KEYWORDS: List[str] = [
    "attrition", "exit", "resigned", "resignation", "turnover", "left",
    "terminated", "termination", "churn", "quit", "separated", "separation",
    "leave", "voluntary", "involuntary", "last_day", "final_day",
    "reason_for", "job_opportunities", "no_longer", "departure",
    "status_change", "end_date", "offboard",
]

# One-hot department column prefixes — triggers reconstruction advisory
DEPT_ONEHOT_PREFIXES: List[str] = [
    "department_", "dept_", "division_", "unit_", "group_", "team_",
]

# ─────────────────────────────────────────────────────────────────────────────
# HIGH-CARDINALITY GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────
HC_DOMINANCE_WARN_THRESHOLD: float  = 0.40   # single-feature importance > 40% → warn
HC_DOMINANCE_FLAG_THRESHOLD: float  = 0.60   # single-feature importance > 60% → flag
HC_UNIQUE_RATIO_RISK: float         = 0.30   # unique ratio > 30% → cardinality risk
MIN_DEPT_GROUP_SIZE: int            = 5      # below this → "small sample" warning

# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY / PROFILING
# ─────────────────────────────────────────────────────────────────────────────
MISSING_WARN_THRESHOLD: float  = 0.20   # warn if >20% missing
MISSING_DROP_THRESHOLD: float  = 0.60   # drop column if >60% missing
CARDINALITY_HIGH: int          = 50     # categorical with >50 unique → high-cardinality
CARDINALITY_ID_LIKE: float     = 0.95   # if unique ratio > 95% → likely ID col
NUMERIC_SKEW_THRESHOLD: float  = 2.0    # abs skew > 2 → log-transform candidate
OUTLIER_IQR_FACTOR: float      = 3.0    # IQR multiplier for outlier detection
MIN_ROWS_FOR_ML: int           = 50     # refuse ML if fewer rows

# ─────────────────────────────────────────────────────────────────────────────
# SEMANTIC MAPPING — confidence thresholds
# ─────────────────────────────────────────────────────────────────────────────
SEMANTIC_EXACT_SCORE: float    = 1.00
SEMANTIC_HIGH_SCORE: float     = 0.85
SEMANTIC_MEDIUM_SCORE: float   = 0.65
SEMANTIC_LOW_SCORE: float      = 0.40
SEMANTIC_REJECT_SCORE: float   = 0.30   # below this → "unknown"
FUZZY_MATCH_CUTOFF: float      = 0.70   # rapidfuzz token_set_ratio / 100

# ─────────────────────────────────────────────────────────────────────────────
# TIME SERIES
# ─────────────────────────────────────────────────────────────────────────────
TS_MIN_PERIODS: int          = 8        # minimum periods to fit a trend
TS_FORECAST_HORIZONS: List[int] = [3, 6, 12]   # months ahead
TS_BOOTSTRAP_N: int          = 200
TS_ANOMALY_ZSCORE: float     = 1.8
TS_SEASONAL_PERIODS: int     = 12       # monthly seasonality

# ─────────────────────────────────────────────────────────────────────────────
# INSIGHT GENERATION
# ─────────────────────────────────────────────────────────────────────────────
MAX_INSIGHTS: int         = 12
INSIGHT_TOP_N_FEATURES: int = 10
INSIGHT_MIN_EFFECT_SIZE: float = 0.05   # skip trivially small effects

# ─────────────────────────────────────────────────────────────────────────────
# API (FastAPI)
# ─────────────────────────────────────────────────────────────────────────────
API_HOST: str  = "0.0.0.0"
API_PORT: int  = 8000
API_VERSION: str = "v1"
API_PREFIX: str = f"/api/{API_VERSION}"

# ─────────────────────────────────────────────────────────────────────────────
# FRONTEND (Streamlit)
# ─────────────────────────────────────────────────────────────────────────────
STREAMLIT_PORT: int  = 8510
STREAMLIT_THEME: str = "dark"

# ─────────────────────────────────────────────────────────────────────────────
# SCIENTIFIC FEATURE MODE — Phase 4 Integration Gate
# ─────────────────────────────────────────────────────────────────────────────
# Controls which construct computation path is active in the ML pipeline.
#
# "theory_grounded"   (DEFAULT) — Phase 2 engine computes constructs from exact
#                                 paper formulas; legacy Layer B is disabled.
# "legacy_for_debug_only"       — Old feature_factory Layer B runs with warning;
#                                 for debugging only, never for reports or output.
# "legacy_disabled"             — Alias for theory_grounded; legacy constructs
#                                 are explicitly quarantined and logged.
#
# NEVER set to "legacy_for_debug_only" in production deployments.
SCIENTIFIC_FEATURE_MODE: str = "theory_grounded"

# Constructs produced by feature_factory.py Layer B that are LOGICALLY DISABLED
# in theory_grounded mode. Listed explicitly so audits can reference them.
LEGACY_DISABLED_CONSTRUCTS: List[str] = [
    "BurnoutRiskComposite",       # wrong formula: additive instead of multiplicative gate
    "SatisfactionIndex",          # wrong formula: 2-input _norm() instead of 4-input average
    "EngagementScore",            # wrong formula: single-source _norm() instead of JI × JS
    "RetentionRisk",              # invented composite: no paper anchor
    "CareerProgressionScore",     # wrong inputs: uses performance/training, not JobLevel/YearsAtCompany
    "CompensationEquity",         # wrong denominator: tenure instead of JobLevel
    "WorkLifeBalanceRisk",        # invented composite: no paper anchor
    "ManagerialSupportIndex",     # invented: no paper anchor
    "EmployeeStabilityRisk",      # invented + target-adjacent: semantically adjacent to attrition
    "AbsenteeismPressureIndex",   # invented: no paper anchor
    "PresenteeismSignal",         # high leakage risk: absence × overtime in retrospective datasets
    "PsychologicalWellbeingScore",# invented: mean of unvalidated columns
    "PsychologicalVariabilityIndex", # invented: intra-individual std
    "PositiveAffectIndex",        # invalid: column-position split with no theory
    "NegativeAffectIndex",        # invalid: column-position split with no theory
]

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
LOG_LEVEL: str  = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# ─────────────────────────────────────────────────────────────────────────────
# AGENTIC AI — CLOUD MODE (Phase 44)
# ─────────────────────────────────────────────────────────────────────────────
# EXPLICIT, USER-CONFIRMED, SCOPED EXCEPTION to this platform's offline-first
# design (see backend/core/offline_mode_guard.py — that guard is completely
# unaffected by this setting and continues blocking every other module's
# network access). When set, the AI Business Analyst's agentic tool-use path
# (backend/core/cloud_llm_client.py) sends the user's question, uploaded-file
# structure, and real Evidence Pack figures to Anthropic's API. This is NEVER
# read by any other module — no other feature in this platform becomes
# network-capable because this key is present. Read once here via the same
# os.environ.get(...) convention as LOG_LEVEL above; never hardcoded, never
# logged. The masked-display convention (first 8 + last 4 characters) used
# throughout this phase's code/reports is defined once in
# backend/core/cloud_llm_client.py's mask_api_key().
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
