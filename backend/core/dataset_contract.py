"""
DatasetContract — Formal Dataset Classification Contract

Every uploaded file produces exactly one DatasetContract before ANY dashboard
or analytics pipeline runs. The contract is the single source of truth that
governs which analyses are allowed and which are explicitly blocked.

Hard invariants enforced here (never in the UI layer):
  - Biosignal datasets: row_unit = "signal_samples", never "employees"
  - Biosignal datasets: all HR employee metrics blocked
  - No target_available → supervised attrition prediction blocked
  - Unknown datasets → prediction entirely blocked

Nothing in the UI should check dataset_type directly; it should read
contract.compatible_analyses / contract.blocked_analyses and
contract.row_unit to decide what to render.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# ALLOWED LITERAL TYPES
# ─────────────────────────────────────────────────────────────────────────────

DATASET_TYPES = [
    "hr_attrition",
    "hr_workforce",
    "psychological_survey",
    "burnout_survey",
    "biosignal_timeseries",
    "generic_timeseries",
    "productivity_logs",
    "compensation_dataset",
    "mixed_enterprise",
    "unknown",
]

ROW_UNITS = [
    "employees",
    "survey_responses",
    "signal_samples",
    "time_windows",
    "events",
    "records",
    "unknown",
]

# Canonical analysis names used throughout the app
ANALYSIS_KEYS = [
    "attrition_prediction",
    "burnout_intelligence",
    "psychological_constructs",
    "biosignal_stress_analysis",
    "timeseries_forecast",
    "fairness_audit",
    "department_stability",
    "retention_roi",
    "pdf_report",
    "data_profiling",
    "schema_mapping",
    "compatibility_matrix",
]

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS DISPLAY LABELS  (shown in the compatibility matrix)
# ─────────────────────────────────────────────────────────────────────────────

ANALYSIS_LABELS: Dict[str, str] = {
    "attrition_prediction":      "Attrition Prediction",
    "burnout_intelligence":      "Burnout Intelligence",
    "psychological_constructs":  "Psychological Constructs",
    "biosignal_stress_analysis": "Biosignal Stress Analysis",
    "timeseries_forecast":       "Time-Series Forecast",
    "fairness_audit":            "Fairness Audit",
    "department_stability":      "Department Stability",
    "retention_roi":             "Retention ROI",
    "pdf_report":                "PDF Report",
    "data_profiling":            "Data Profiling",
    "schema_mapping":            "Schema Mapping",
    "compatibility_matrix":      "Compatibility Matrix",
}


# ─────────────────────────────────────────────────────────────────────────────
# DATASET CONTRACT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CompatibilityEntry:
    analysis_key: str
    label: str
    available: bool
    reason: str


@dataclass
class DatasetContract:
    # ── Core classification ───────────────────────────────────────────────────
    dataset_type: str               # one of DATASET_TYPES
    dataset_subtype: str            # e.g. "wesad_hr", "ibm_attrition", etc.
    confidence: float               # 0–1

    # ── Row semantics ─────────────────────────────────────────────────────────
    row_unit: str                   # one of ROW_UNITS — controls all display labels

    # ── Target & structure ───────────────────────────────────────────────────
    target_available: bool
    target_column: Optional[str]
    subject_id_column: Optional[str]
    time_column: Optional[str]

    # ── Detected column groups ────────────────────────────────────────────────
    signal_columns: List[str]       # biosignal: HR, EDA, BVP etc.
    employee_columns: List[str]     # HR: age, dept, tenure, salary etc.

    # ── Routing ──────────────────────────────────────────────────────────────
    recommended_pipeline: str
    reason: str

    # ── Analysis permission table ─────────────────────────────────────────────
    compatible_analyses: List[str]          # keys from ANALYSIS_KEYS
    blocked_analyses: List[str]             # keys from ANALYSIS_KEYS
    compatibility_matrix: List[CompatibilityEntry] = field(default_factory=list)

    # ── Human-readable messages ───────────────────────────────────────────────
    warning_messages: List[str] = field(default_factory=list)

    # ── Derived convenience flags ─────────────────────────────────────────────
    is_biosignal: bool = False
    is_hr: bool = False
    is_survey: bool = False
    is_timeseries: bool = False
    is_unknown: bool = False

    # ── Biosignal extras ─────────────────────────────────────────────────────
    detected_signal_type: Optional[str] = None   # "HR" / "EDA" / "BVP" etc.
    n_signal_columns: int = 0

    # ── Quality summary ──────────────────────────────────────────────────────
    quality_score: float = 0.0
    quality_issues: List[str] = field(default_factory=list)

    # ── Phase 3: Universal architecture results (attached by AdaptiveRouter) ─
    modality_result:    Optional[Any] = None  # ModalityResult
    routing_confidence: Optional[Any] = None  # RoutingConfidence
    semantic_map_v2:    Optional[Any] = None  # SemanticMapping
    sandbox_report:     Optional[Any] = None  # SandboxReport

    # ─────────────────────────────────────────────────────────────────────────
    # GUARD METHODS — call these in every dashboard section
    # ─────────────────────────────────────────────────────────────────────────

    def allows(self, analysis_key: str) -> bool:
        return analysis_key in self.compatible_analyses

    def blocks(self, analysis_key: str) -> bool:
        return analysis_key in self.blocked_analyses

    def row_label(self, plural: bool = True) -> str:
        """Return the correct noun for a row — NEVER "employee" for biosignal."""
        labels = {
            "employees":        ("employee", "employees"),
            "survey_responses": ("survey response", "survey responses"),
            "signal_samples":   ("signal sample", "signal samples"),
            "time_windows":     ("time window", "time windows"),
            "events":           ("event", "events"),
            "records":          ("record", "records"),
            "unknown":          ("record", "records"),
        }
        pair = labels.get(self.row_unit, ("record", "records"))
        return pair[1] if plural else pair[0]

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items()
             if k != "compatibility_matrix"}
        d["compatibility_matrix"] = [
            {"analysis": e.analysis_key, "label": e.label,
             "available": e.available, "reason": e.reason}
            for e in self.compatibility_matrix
        ]
        return d


# ─────────────────────────────────────────────────────────────────────────────
# CONTRACT BUILDER  (internal — called by DatasetClassifier)
# ─────────────────────────────────────────────────────────────────────────────

# Maps dataset_type → default allowed analyses
_DEFAULT_COMPATIBLE: Dict[str, List[str]] = {
    "hr_attrition": [
        "attrition_prediction", "burnout_intelligence", "psychological_constructs",
        "timeseries_forecast", "fairness_audit", "department_stability",
        "retention_roi", "pdf_report", "data_profiling", "schema_mapping",
        "compatibility_matrix",
    ],
    "hr_workforce": [
        "burnout_intelligence", "psychological_constructs",
        "timeseries_forecast", "department_stability",
        "data_profiling", "schema_mapping", "compatibility_matrix",
    ],
    "psychological_survey": [
        "burnout_intelligence", "psychological_constructs",
        "timeseries_forecast", "data_profiling", "schema_mapping",
        "compatibility_matrix",
    ],
    "burnout_survey": [
        "burnout_intelligence", "psychological_constructs",
        "data_profiling", "schema_mapping", "compatibility_matrix",
    ],
    "biosignal_timeseries": [
        "biosignal_stress_analysis", "timeseries_forecast",
        "data_profiling", "schema_mapping", "compatibility_matrix",
    ],
    "generic_timeseries": [
        "timeseries_forecast", "data_profiling",
        "schema_mapping", "compatibility_matrix",
    ],
    "productivity_logs": [
        "timeseries_forecast", "data_profiling",
        "schema_mapping", "compatibility_matrix",
    ],
    "compensation_dataset": [
        "data_profiling", "schema_mapping", "compatibility_matrix",
    ],
    "mixed_enterprise": [
        "burnout_intelligence", "psychological_constructs",
        "timeseries_forecast", "data_profiling", "schema_mapping",
        "compatibility_matrix",
    ],
    "unknown": [
        "data_profiling", "schema_mapping", "compatibility_matrix",
    ],
}

# Maps dataset_type → always-blocked analyses (regardless of data)
_HARD_BLOCKED: Dict[str, List[str]] = {
    "biosignal_timeseries": [
        "attrition_prediction", "burnout_intelligence",
        "psychological_constructs", "fairness_audit",
        "department_stability", "retention_roi", "pdf_report",
    ],
    "generic_timeseries": [
        "attrition_prediction", "fairness_audit",
        "department_stability", "retention_roi",
    ],
    "unknown": [
        "attrition_prediction", "burnout_intelligence",
        "psychological_constructs", "biosignal_stress_analysis",
        "fairness_audit", "department_stability", "retention_roi",
        "pdf_report",
    ],
    "compensation_dataset": [
        "attrition_prediction", "biosignal_stress_analysis",
        "fairness_audit",
    ],
    "productivity_logs": [
        "attrition_prediction", "biosignal_stress_analysis",
        "fairness_audit",
    ],
}

# Reasons for blocking
_BLOCK_REASONS: Dict[str, str] = {
    "attrition_prediction":      "No attrition/outcome target column detected",
    "burnout_intelligence":      "No HR survey or psychological construct columns",
    "psychological_constructs":  "No Likert/survey columns for construct estimation",
    "biosignal_stress_analysis": "Dataset does not contain physiological signal data",
    "timeseries_forecast":       "No temporal/sequential structure detected",
    "fairness_audit":            "Requires demographic + outcome columns",
    "department_stability":      "No department column detected",
    "retention_roi":             "Requires salary and attrition target",
    "pdf_report":                "HR dataset required for workforce PDF report",
}

# Biosignal-specific block reasons
_BIOSIGNAL_BLOCK_REASONS: Dict[str, str] = {
    "attrition_prediction":     "Biosignal: rows are signal samples, not employees. No attrition target exists.",
    "burnout_intelligence":     "Biosignal: burnout constructs require employee survey columns, not sensor data.",
    "psychological_constructs": "Biosignal: psychological construct estimation requires Likert survey responses.",
    "fairness_audit":           "Biosignal: no demographic employee data present.",
    "department_stability":     "Biosignal: no department/organisational structure detected.",
    "retention_roi":            "Biosignal: no salary or employee turnover data.",
    "pdf_report":               "Biosignal: HR workforce report not applicable. Use Biosignal Stress Report.",
}

# Row units per dataset type
_ROW_UNIT_MAP: Dict[str, str] = {
    "hr_attrition":         "employees",
    "hr_workforce":         "employees",
    "psychological_survey": "survey_responses",
    "burnout_survey":       "survey_responses",
    "biosignal_timeseries": "signal_samples",
    "generic_timeseries":   "records",
    "productivity_logs":    "events",
    "compensation_dataset": "employees",
    "mixed_enterprise":     "records",
    "unknown":              "unknown",
}


def _build_compatibility_matrix(
    dataset_type: str,
    compatible: List[str],
    blocked: List[str],
) -> List[CompatibilityEntry]:
    entries: List[CompatibilityEntry] = []
    for key in ANALYSIS_KEYS:
        label = ANALYSIS_LABELS.get(key, key)
        if key in compatible:
            entries.append(CompatibilityEntry(key, label, True, "Supported for this dataset type"))
        else:
            if dataset_type == "biosignal_timeseries" and key in _BIOSIGNAL_BLOCK_REASONS:
                reason = _BIOSIGNAL_BLOCK_REASONS[key]
            else:
                reason = _BLOCK_REASONS.get(key, "Not applicable for this dataset type")
            entries.append(CompatibilityEntry(key, label, False, reason))
    return entries


def build_contract(
    dataset_type: str,
    dataset_subtype: str,
    confidence: float,
    target_available: bool,
    target_column: Optional[str],
    subject_id_column: Optional[str],
    time_column: Optional[str],
    signal_columns: List[str],
    employee_columns: List[str],
    recommended_pipeline: str,
    reason: str,
    warning_messages: Optional[List[str]] = None,
    detected_signal_type: Optional[str] = None,
    quality_score: float = 0.0,
    quality_issues: Optional[List[str]] = None,
) -> DatasetContract:
    """
    Build a DatasetContract from classification outputs.
    Enforces hard blocking rules — no caller can override these.
    """
    warning_messages = warning_messages or []
    quality_issues   = quality_issues or []

    # Base permissions from type
    compatible = list(_DEFAULT_COMPATIBLE.get(dataset_type, ["data_profiling", "schema_mapping", "compatibility_matrix"]))

    # Remove attrition_prediction if no target
    if not target_available and "attrition_prediction" in compatible:
        compatible.remove("attrition_prediction")
        warning_messages.append(
            "No attrition/outcome target detected — supervised prediction disabled. "
            "Running unsupervised risk scoring instead."
        )

    # Remove dept_stability if no dept/employee cols
    dept_like = any(kw in " ".join(employee_columns).lower()
                    for kw in ["dept", "department", "division", "team"])
    if not dept_like and "department_stability" in compatible:
        compatible.remove("department_stability")

    # Remove retention_roi if no salary
    salary_like = any(kw in " ".join(employee_columns).lower()
                      for kw in ["salary", "income", "wage", "pay", "comp"])
    if not salary_like and "retention_roi" in compatible:
        compatible.remove("retention_roi")

    # Hard-block rules (cannot be overridden)
    hard_blocked = list(_HARD_BLOCKED.get(dataset_type, []))

    # Final blocked = everything not in compatible
    blocked = [k for k in ANALYSIS_KEYS if k not in compatible]

    # Biosignal: hard-add all employee metric analyses to blocked
    if dataset_type == "biosignal_timeseries":
        for key in ["attrition_prediction", "burnout_intelligence", "psychological_constructs",
                    "fairness_audit", "department_stability", "retention_roi", "pdf_report"]:
            if key not in blocked:
                blocked.append(key)
            if key in compatible:
                compatible.remove(key)
        warning_messages.append(
            "BIOSIGNAL DATASET: Rows represent physiological signal samples — NOT employees. "
            "Employee count, attrition probability, HR risk levels, and replacement cost "
            "are NOT applicable and will not be displayed."
        )

    row_unit = _ROW_UNIT_MAP.get(dataset_type, "unknown")
    n_sig    = len(signal_columns)

    matrix = _build_compatibility_matrix(dataset_type, compatible, blocked)

    return DatasetContract(
        dataset_type         = dataset_type,
        dataset_subtype      = dataset_subtype,
        confidence           = round(confidence, 3),
        row_unit             = row_unit,
        target_available     = target_available,
        target_column        = target_column,
        subject_id_column    = subject_id_column,
        time_column          = time_column,
        signal_columns       = signal_columns,
        employee_columns     = employee_columns,
        recommended_pipeline = recommended_pipeline,
        reason               = reason,
        compatible_analyses  = compatible,
        blocked_analyses     = blocked,
        compatibility_matrix = matrix,
        warning_messages     = warning_messages,
        is_biosignal         = (dataset_type == "biosignal_timeseries"),
        is_hr                = dataset_type in ("hr_attrition", "hr_workforce"),
        is_survey            = dataset_type in ("psychological_survey", "burnout_survey"),
        is_timeseries        = dataset_type in ("biosignal_timeseries", "generic_timeseries"),
        is_unknown           = (dataset_type == "unknown"),
        detected_signal_type = detected_signal_type,
        n_signal_columns     = n_sig,
        quality_score        = quality_score,
        quality_issues       = quality_issues,
    )
