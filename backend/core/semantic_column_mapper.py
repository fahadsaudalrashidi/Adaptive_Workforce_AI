"""
Semantic Column Mapper
Schema-agnostic column semantic role detection.

Maps each column to a SemanticRole WITHOUT assuming any fixed schema.
Works on HR, biosignal, survey, financial, and completely unknown datasets.

Roles:
  TARGET             — likely prediction target (binary outcome, label)
  IDENTIFIER         — row ID (should not be used as feature)
  TEMPORAL           — date / time / sequence
  NUMERIC_METRIC     — continuous quantitative measurement
  CATEGORICAL_DIM    — grouping dimension (department, job type, etc.)
  BINARY_FLAG        — yes/no, 0/1 binary indicator
  ORDINAL_SCALE      — ordered discrete scale (Likert, rating)
  FREE_TEXT          — unstructured text content
  PROTECTED_ATTR     — potential protected attribute (gender, race, age, etc.)
  BIOSIGNAL_RAW      — raw physiological sensor reading
  EMPLOYEE_ATTR      — HR-specific employee property
  SURVEY_ITEM        — survey / questionnaire item
  FINANCIAL_METRIC   — currency / revenue / cost
  HIGH_CARDINALITY   — many unique values, possibly a name/code
  UNKNOWN            — cannot determine semantic role

Every column mapping carries:
  confidence   — 0–1
  evidence     — what signals drove the assignment
  caveats      — limitations
"""
from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ── Roles ─────────────────────────────────────────────────────────────────────

class SemanticRole(str, Enum):
    TARGET          = "target"
    IDENTIFIER      = "identifier"
    TEMPORAL        = "temporal"
    NUMERIC_METRIC  = "numeric_metric"
    CATEGORICAL_DIM = "categorical_dimension"
    BINARY_FLAG     = "binary_flag"
    ORDINAL_SCALE   = "ordinal_scale"
    FREE_TEXT       = "free_text"
    PROTECTED_ATTR  = "protected_attribute"
    BIOSIGNAL_RAW   = "biosignal_raw"
    EMPLOYEE_ATTR   = "employee_attribute"
    SURVEY_ITEM     = "survey_item"
    FINANCIAL_METRIC= "financial_metric"
    HIGH_CARDINALITY= "high_cardinality"
    UNKNOWN         = "unknown"


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class ColumnMapping:
    column_name: str
    role: SemanticRole
    confidence: float           # 0–1
    evidence: List[str]         # human-readable signals
    caveats: List[str]          # limitations / warnings
    is_usable_feature: bool     # False for ID, TARGET, PROTECTED_ATTR (use with care)
    inferred_dtype: str         # "numeric" / "categorical" / "datetime" / "text" / "binary"
    n_unique: int
    missing_rate: float


@dataclass
class SemanticMapping:
    """Full mapping of all columns in a dataset."""
    columns: Dict[str, ColumnMapping]
    target_candidates: List[str]     # columns that might be the target
    identifier_columns: List[str]
    temporal_columns: List[str]
    protected_attributes: List[str]
    biosignal_columns: List[str]
    hr_columns: List[str]
    survey_columns: List[str]
    financial_columns: List[str]
    feature_columns: List[str]       # usable ML features
    dominant_role: str               # most common role (plain string, not enum)
    schema_coherence: float          # 0–1 how internally consistent the schema is
    provenance: List[str]
    assumptions: List[str]
    caveats: List[str]
    validity_score: float

    @property
    def column_roles(self) -> Dict[str, ColumnMapping]:
        """Alias for .columns — backward-compatible name."""
        return self.columns


# ── Keyword tables ─────────────────────────────────────────────────────────────

# (pattern, role, confidence)
_COLUMN_ROLE_RULES: List[Tuple[str, SemanticRole, float]] = [
    # ── Target / outcome ──────────────────────────────────────────────────────
    (r"^attrition$",            SemanticRole.TARGET,         1.00),
    (r"^turnover$",             SemanticRole.TARGET,         0.95),
    (r"attrition",              SemanticRole.TARGET,         0.90),
    (r"^churn$",                SemanticRole.TARGET,         0.95),
    (r"^resigned$",             SemanticRole.TARGET,         0.90),
    (r"^left$",                 SemanticRole.TARGET,         0.85),
    (r"^outcome$",              SemanticRole.TARGET,         0.80),
    (r"^label$",                SemanticRole.TARGET,         0.80),
    (r"^target$",               SemanticRole.TARGET,         0.80),
    (r"^y$",                    SemanticRole.TARGET,         0.75),  # exact match only
    (r"^class$",                SemanticRole.TARGET,         0.75),
    (r"terminated|separated",   SemanticRole.TARGET,         0.85),
    (r"exit_flag|exited",       SemanticRole.TARGET,         0.85),

    # ── Identifiers ───────────────────────────────────────────────────────────
    (r"^id$",                   SemanticRole.IDENTIFIER,     0.95),
    (r"employee.*id|emp.*id",   SemanticRole.IDENTIFIER,     0.95),
    (r".*_id$",                 SemanticRole.IDENTIFIER,     0.80),
    (r"^uuid$|^guid$",          SemanticRole.IDENTIFIER,     0.95),
    (r"^index$",                SemanticRole.IDENTIFIER,     0.75),
    (r"^row_num|^row_id",       SemanticRole.IDENTIFIER,     0.85),
    (r"^customer.*id",          SemanticRole.IDENTIFIER,     0.90),
    (r"^user.*id|^account.*id", SemanticRole.IDENTIFIER,     0.90),

    # ── Temporal ──────────────────────────────────────────────────────────────
    (r"date|datetime|timestamp", SemanticRole.TEMPORAL,      0.90),
    (r"^time$|^time_",           SemanticRole.TEMPORAL,      0.85),
    (r"created_at|updated_at",   SemanticRole.TEMPORAL,      0.90),
    (r"hired.*date|start.*date", SemanticRole.TEMPORAL,      0.85),
    (r"birth.*date|dob",         SemanticRole.TEMPORAL,      0.85),
    (r"year.*joined|join.*year", SemanticRole.TEMPORAL,      0.80),

    # ── Protected attributes ──────────────────────────────────────────────────
    (r"^gender$|^sex$",          SemanticRole.PROTECTED_ATTR, 0.95),
    (r"^race$|^ethnicity$",      SemanticRole.PROTECTED_ATTR, 0.95),
    (r"^nationality$",           SemanticRole.PROTECTED_ATTR, 0.90),
    (r"^religion$",              SemanticRole.PROTECTED_ATTR, 0.90),
    (r"^disability",             SemanticRole.PROTECTED_ATTR, 0.90),
    (r"^marital",                SemanticRole.PROTECTED_ATTR, 0.85),
    (r"^age$",                   SemanticRole.PROTECTED_ATTR, 0.80),
    (r"^dob$|^birthdate$",       SemanticRole.PROTECTED_ATTR, 0.85),

    # ── Biosignal raw ─────────────────────────────────────────────────────────
    (r"^eda$|^gsr$",             SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"^bvp$",                   SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"^ibi$",                   SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"^hrv$",                   SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"^ecg$|^eeg$|^emg$",       SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"^ppg$",                   SemanticRole.BIOSIGNAL_RAW,  0.99),
    (r"skin_conductance",        SemanticRole.BIOSIGNAL_RAW,  0.95),
    (r"blood_volume|inter_beat", SemanticRole.BIOSIGNAL_RAW,  0.95),
    (r"rr_interval|nn_interval", SemanticRole.BIOSIGNAL_RAW,  0.95),
    (r"heart_rate|heartrate",    SemanticRole.BIOSIGNAL_RAW,  0.85),
    (r"galvanic|accelerometer",  SemanticRole.BIOSIGNAL_RAW,  0.85),

    # ── HR-specific employee attributes ───────────────────────────────────────
    (r"department|division",     SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"jobrole|job_role",        SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"joblevel|job_level",      SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"yearsatcompany|tenure",   SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"monthlyincome|salary",    SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"overtime|over_time",      SemanticRole.EMPLOYEE_ATTR,  0.80),
    (r"businesstravel",          SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"education.*field",        SemanticRole.EMPLOYEE_ATTR,  0.80),
    (r"performancerating",       SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"numcompaniesworked",      SemanticRole.EMPLOYEE_ATTR,  0.85),
    (r"stockoption|stock_opt",   SemanticRole.EMPLOYEE_ATTR,  0.80),
    (r"trainingtime",            SemanticRole.EMPLOYEE_ATTR,  0.80),
    (r"worklifebalance",         SemanticRole.EMPLOYEE_ATTR,  0.80),
    (r"headcount|workforce",     SemanticRole.EMPLOYEE_ATTR,  0.75),

    # ── Survey items ──────────────────────────────────────────────────────────
    (r"burnout|exhaustion",      SemanticRole.SURVEY_ITEM,    0.90),
    (r"cynicism|engagement",     SemanticRole.SURVEY_ITEM,    0.85),
    (r"wellbeing|wellness",      SemanticRole.SURVEY_ITEM,    0.80),
    (r"mbi_|^q[0-9]+_",         SemanticRole.SURVEY_ITEM,    0.85),
    (r"^item_[0-9]+",            SemanticRole.SURVEY_ITEM,    0.80),
    (r"questionnaire|survey",    SemanticRole.SURVEY_ITEM,    0.85),
    (r"self_report|likert",      SemanticRole.SURVEY_ITEM,    0.90),

    # ── Financial metrics ─────────────────────────────────────────────────────
    (r"revenue|profit|loss",     SemanticRole.FINANCIAL_METRIC, 0.90),
    (r"transaction|invoice",     SemanticRole.FINANCIAL_METRIC, 0.90),
    (r"debit|credit|balance",    SemanticRole.FINANCIAL_METRIC, 0.90),
    (r"amount|payment|price",    SemanticRole.FINANCIAL_METRIC, 0.75),
    (r"budget|expense|cost",     SemanticRole.FINANCIAL_METRIC, 0.75),
    (r"fiscal|quarter.*rev",     SemanticRole.FINANCIAL_METRIC, 0.85),
]


# ── Main mapper ───────────────────────────────────────────────────────────────

class SemanticColumnMapper:
    """
    Maps every column in a DataFrame to a semantic role without schema assumptions.
    Works on any dataset type.
    """

    def map(self, df: pd.DataFrame) -> SemanticMapping:
        columns: Dict[str, ColumnMapping] = {}

        for col in df.columns:
            columns[col] = self._map_column(col, df[col])

        # Aggregate role groups
        target_candidates  = [c for c, m in columns.items() if m.role == SemanticRole.TARGET]
        identifier_columns = [c for c, m in columns.items() if m.role == SemanticRole.IDENTIFIER]
        temporal_columns   = [c for c, m in columns.items() if m.role == SemanticRole.TEMPORAL]
        protected_attrs    = [c for c, m in columns.items() if m.role == SemanticRole.PROTECTED_ATTR]
        biosignal_columns  = [c for c, m in columns.items() if m.role == SemanticRole.BIOSIGNAL_RAW]
        hr_columns         = [c for c, m in columns.items() if m.role == SemanticRole.EMPLOYEE_ATTR]
        survey_columns     = [c for c, m in columns.items() if m.role == SemanticRole.SURVEY_ITEM]
        financial_columns  = [c for c, m in columns.items() if m.role == SemanticRole.FINANCIAL_METRIC]

        # Usable ML features: not ID, not raw target, not pure text
        feature_columns = [
            c for c, m in columns.items()
            if m.is_usable_feature and m.role not in {
                SemanticRole.IDENTIFIER, SemanticRole.FREE_TEXT, SemanticRole.HIGH_CARDINALITY
            }
        ]

        # Dominant role
        role_counts: Dict[str, int] = {}
        for m in columns.values():
            role_counts[m.role.value] = role_counts.get(m.role.value, 0) + 1
        dominant_role = max(role_counts, key=role_counts.get) if role_counts else "unknown"

        # Schema coherence: are roles internally consistent?
        coherence = self._schema_coherence(columns, biosignal_columns, hr_columns, survey_columns)

        # Provenance
        provenance = [
            f"Mapped {len(df.columns)} columns",
            f"Target candidates: {target_candidates}",
            f"Identifier columns: {identifier_columns}",
            f"Protected attributes: {protected_attrs}",
            f"Biosignal columns: {biosignal_columns}",
            f"Feature columns available: {len(feature_columns)}",
            f"Schema coherence: {coherence:.0%}",
        ]
        assumptions = [
            "Column names reflect their content.",
            "Missing values are random (not systematically absent).",
        ]
        caveats: List[str] = []
        if not target_candidates:
            caveats.append("No target column detected — supervised learning not available.")
        if len(identifier_columns) > 3:
            caveats.append("Many identifier-like columns detected — check for data leakage.")
        if len(protected_attrs) > 0:
            caveats.append(f"Protected attributes detected: {protected_attrs}. Fairness audit recommended.")
        if biosignal_columns and hr_columns:
            caveats.append("MIXED: biosignal AND HR columns detected — dataset may be multimodal or mislabelled.")

        validity = coherence * 0.8 + (0.2 if bool(target_candidates or feature_columns) else 0.0)

        # Per-role coverage scores (used by DatasetConfidenceEngine)
        role_coverage: Dict[str, float] = {}
        total_cols = max(len(df.columns), 1)
        for role_name, count in role_counts.items():
            role_coverage[role_name] = round(count / total_cols, 4)

        return SemanticMapping(
            columns=columns,
            target_candidates=target_candidates,
            identifier_columns=identifier_columns,
            temporal_columns=temporal_columns,
            protected_attributes=protected_attrs,
            biosignal_columns=biosignal_columns,
            hr_columns=hr_columns,
            survey_columns=survey_columns,
            financial_columns=financial_columns,
            feature_columns=feature_columns,
            dominant_role=dominant_role,
            schema_coherence=coherence,
            provenance=provenance,
            assumptions=assumptions,
            caveats=caveats,
            validity_score=round(min(1.0, max(0.0, validity)), 4),
        )

    # ── Per-column mapping ────────────────────────────────────────────────────

    def _map_column(self, col: str, series: pd.Series) -> ColumnMapping:
        cl = col.lower().strip().replace(" ", "_").replace("-", "_")
        n_total = len(series)
        n_missing = int(series.isna().sum())
        missing_rate = n_missing / max(n_total, 1)
        s_clean = series.dropna()
        n_unique = int(s_clean.nunique()) if len(s_clean) > 0 else 0
        is_numeric = pd.api.types.is_numeric_dtype(series)

        evidence: List[str] = []
        caveats: List[str] = []

        # ── Rule-based role assignment ────────────────────────────────────────
        best_role: SemanticRole = SemanticRole.UNKNOWN
        best_conf: float = 0.0

        for pattern, role, conf in _COLUMN_ROLE_RULES:
            if re.search(pattern, cl):
                if conf > best_conf:
                    best_role = role
                    best_conf = conf
                    evidence.append(f"Pattern '{pattern}' matched column name '{col}'")

        # ── Value-distribution fallback (when name-matching fails) ─────────────
        if best_conf < 0.50 and len(s_clean) > 0:
            role_v, conf_v, ev_v = self._value_role(cl, series, s_clean, is_numeric, n_unique)
            if conf_v > best_conf:
                best_role = role_v
                best_conf = conf_v
                evidence.extend(ev_v)

        # ── Identifier check (high cardinality numeric or string) ─────────────
        if best_role == SemanticRole.UNKNOWN or best_conf < 0.50:
            if n_unique > 0.95 * n_total and n_total > 20:
                best_role = SemanticRole.HIGH_CARDINALITY
                best_conf = 0.70
                evidence.append(f"Unique ratio {n_unique/max(n_total,1):.0%} — likely identifier or free text")

        # ── Missing rate caveats ──────────────────────────────────────────────
        if missing_rate > 0.50:
            caveats.append(f"High missing rate ({missing_rate:.0%}) — use with caution.")
        if missing_rate > 0.90:
            caveats.append("Nearly fully missing — consider dropping this column.")

        # ── Inferred dtype ────────────────────────────────────────────────────
        if is_numeric:
            if n_unique <= 2:
                inferred_dtype = "binary"
            elif n_unique <= 7:
                inferred_dtype = "ordinal"
            else:
                inferred_dtype = "numeric"
        else:
            try:
                pd.to_datetime(s_clean.head(10), errors="raise")
                inferred_dtype = "datetime"
            except Exception:
                max_len = int(s_clean.astype(str).str.len().max()) if len(s_clean) > 0 else 0
                inferred_dtype = "text" if max_len > 50 else "categorical"

        # Usable feature: not ID, not raw target in isolation
        is_usable = best_role not in {
            SemanticRole.IDENTIFIER,
            SemanticRole.FREE_TEXT,
            SemanticRole.HIGH_CARDINALITY,
        }

        if best_role == SemanticRole.PROTECTED_ATTR:
            caveats.append("Protected attribute — handle with care; fairness audit required before use as feature.")
            is_usable = True  # can be used but must be audited

        return ColumnMapping(
            column_name=col,
            role=best_role,
            confidence=round(min(1.0, max(0.0, best_conf)), 4),
            evidence=evidence[:5],
            caveats=caveats,
            is_usable_feature=is_usable,
            inferred_dtype=inferred_dtype,
            n_unique=n_unique,
            missing_rate=round(missing_rate, 4),
        )

    def _value_role(
        self,
        cl: str,
        series: pd.Series,
        s_clean: pd.Series,
        is_numeric: bool,
        n_unique: int,
    ) -> Tuple[SemanticRole, float, List[str]]:
        ev: List[str] = []

        if not is_numeric:
            # Datetime detection
            try:
                pd.to_datetime(s_clean.head(20), errors="raise")
                ev.append("Values parse as datetime")
                return SemanticRole.TEMPORAL, 0.80, ev
            except Exception:
                pass

            # Categorical
            if n_unique <= 20:
                ev.append(f"Low-cardinality categorical: {n_unique} unique values")
                return SemanticRole.CATEGORICAL_DIM, 0.55, ev

            # Free text
            max_len = int(s_clean.astype(str).str.len().max())
            if max_len > 80:
                ev.append(f"Long text values (max len {max_len})")
                return SemanticRole.FREE_TEXT, 0.70, ev

            return SemanticRole.CATEGORICAL_DIM, 0.40, ev

        # Numeric
        vals = s_clean.astype(float)
        mn, mx = float(vals.min()), float(vals.max())

        # Binary
        if n_unique == 2 and set(vals.unique()).issubset({0, 1, 0.0, 1.0}):
            ev.append("Exactly binary (0/1)")
            return SemanticRole.BINARY_FLAG, 0.90, ev

        # Binary text-encoded
        if n_unique == 2:
            ev.append("Only 2 unique values — binary")
            return SemanticRole.BINARY_FLAG, 0.75, ev

        # Likert scale
        if n_unique <= 7 and mn >= 1 and mx <= 7:
            try:
                if (vals == vals.round()).all():
                    ev.append(f"Integer values in [{mn:.0f}, {mx:.0f}] — Likert scale")
                    return SemanticRole.ORDINAL_SCALE, 0.80, ev
            except Exception:
                pass

        # Large positive integers with high cardinality — likely financial or sensor
        if mn >= 0 and float(vals.std()) / max(abs(float(vals.mean())), 1e-9) > 0.5:
            ev.append("High variability positive numeric — likely continuous metric")
            return SemanticRole.NUMERIC_METRIC, 0.55, ev

        return SemanticRole.NUMERIC_METRIC, 0.45, ["Numeric column, no specific pattern matched"]

    def _schema_coherence(
        self,
        columns: Dict[str, ColumnMapping],
        biosignal: List[str],
        hr: List[str],
        survey: List[str],
    ) -> float:
        n = len(columns)
        if n == 0:
            return 0.0

        # Penalty for mixed biosignal + HR (scientifically invalid mix)
        mixed_penalty = 0.0
        if biosignal and hr:
            mixed_penalty = min(0.40, (len(biosignal) + len(hr)) / n)

        # Reward for confident assignments
        high_conf = sum(1 for m in columns.values() if m.confidence >= 0.70)
        conf_ratio = high_conf / n

        score = conf_ratio * (1.0 - mixed_penalty)
        return round(min(1.0, max(0.0, score)), 4)
