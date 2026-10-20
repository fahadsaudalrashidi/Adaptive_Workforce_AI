"""
Secure File Ingestion — Phase 9.

Wraps ExcelIngestionEngine with a governance layer:
  - Tenant isolation check before any parsing
  - PII column detection (blocks personally-identifiable fields)
  - Leakage column detection (blocks future-state / post-event columns)
  - Target column identification
  - Data quality scoring
  - Returns a FileIngestionReport with readiness level: READY / CONDITIONAL / BLOCKED

Design rules:
  - Never returns raw employee rows in the report
  - All blocking decisions are logged with reasons
  - Arabic column names are treated identically to English equivalents
  - A BLOCKED result must include at least one blocking_reason
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

from .excel_ingestion_engine import ExcelIngestionEngine, IngestionResult

logger = logging.getLogger(__name__)

# ── PII patterns ──────────────────────────────────────────────────────────────

_PII_PATTERNS_EN = {
    "national_id", "nationalid", "id_number", "iqama", "iqama_number",
    "passport", "passport_number", "passport_no",
    "iban", "bank_account", "account_number",
    "phone", "mobile", "telephone", "phone_number", "mobile_number",
    "email", "email_address",
    "full_name", "employee_name", "name", "first_name", "last_name", "surname",
    "address", "home_address", "residence",
    "date_of_birth", "birth_date", "dob",
    "salary",  # salary is PII at individual level; aggregate is permitted
    "photo", "biometric",
}

_PII_PATTERNS_AR = {
    "الهوية_الوطنية", "رقم_الهوية", "الإقامة", "رقم_الإقامة",
    "جواز_السفر", "رقم_جواز_السفر",
    "الآيبان", "رقم_الحساب", "الحساب_البنكي",
    "الجوال", "الهاتف", "رقم_الجوال", "رقم_الهاتف",
    "البريد_الإلكتروني",
    "الاسم", "الاسم_الكامل", "اسم_الموظف",
    "العنوان", "تاريخ_الميلاد",
}

# Regex patterns for PII detection even with suffix/prefix noise
_PII_REGEX_PATTERNS = [
    re.compile(r"\b(national.?id|id.?number|iqama)\b", re.I),
    re.compile(r"\b(passport|iban|bank.?acc)\b", re.I),
    re.compile(r"\b(phone|mobile|telephone)\b", re.I),
    re.compile(r"\b(email|e.mail)\b", re.I),
    re.compile(r"\b(full.?name|first.?name|last.?name|surname)\b", re.I),
    re.compile(r"\b(date.?of.?birth|birth.?date|dob)\b", re.I),
    re.compile(r"\b(biometric|photo|face)\b", re.I),
]

# ── Leakage column patterns ───────────────────────────────────────────────────

_LEAKAGE_PATTERNS_EN = {
    "resignation_date", "termination_date", "last_day", "exit_date",
    "left_company", "has_resigned", "resigned", "terminated",
    "future_salary", "promotion_date", "next_review_date",
    "attrition", "attrited", "churned", "is_churned",
}

_LEAKAGE_PATTERNS_AR = {
    "تاريخ_الاستقالة", "تاريخ_الإنهاء", "آخر_يوم",
    "استقال", "أنهي_عقده", "الاستنزاف",
}

_LEAKAGE_REGEX_PATTERNS = [
    re.compile(r"\b(resignat|terminat|exit.?date|last.?day|left.?comp)\b", re.I),
    re.compile(r"\b(attrited|churned|has.?resigned)\b", re.I),
    re.compile(r"\b(future|next.?(salary|review|promot))\b", re.I),
]

# ── Target column candidates ──────────────────────────────────────────────────

_TARGET_CANDIDATES_EN = [
    "flight_risk", "risk_score", "stability_score", "attrition_risk",
    "turnover_risk", "retention_score", "leaving_probability",
    "resignation_risk", "churn_risk", "workforce_stability",
]

_TARGET_CANDIDATES_AR = [
    "مخاطر_المغادرة", "درجة_الاستقرار", "مخاطر_الاستنزاف",
]

# ── Record-ID column detection (for confident duplicate-row matching) ─────────
# Covers both HR-employee datasets and recruitment/candidate datasets
# (Phase 5 recruitment_pipeline_engine.py) — any dataset with a per-record
# identifier column benefits from ID-based dedup instead of the full-row-
# match fallback.

_ID_COLUMN_PATTERNS = re.compile(
    r"\b(employee[_\s]?id|employee[_\s]?number|emp[_\s]?id|emp[_\s]?no|"
    r"empno|staff[_\s]?id|record[_\s]?id|candidate[_\s]?id|applicant[_\s]?id|"
    r"candidate[_\s]?number|applicant[_\s]?number)\b",
    re.I,
)

# ── Period/date column detection (for longitudinal-data-aware dedup) ──────────
# Deliberately the SAME pattern as payroll_movement_tracker.py's
# _PERIOD_PATTERNS (kept in sync intentionally, not centralised — this
# codebase's established convention is per-module-local column-detection
# regexes, e.g. each engine keeps its own _find_column()/pattern set). This
# copy exists because pipeline-level dedup needs to know about longitudinal
# data BEFORE any engine ever sees the dataframe, so it can't simply import
# the payroll engine's pattern without creating a dedup-module -> analysis-
# engine dependency that doesn't exist anywhere else in this codebase.
_PERIOD_COLUMN_PATTERNS = re.compile(
    r"\b(period|snapshot[_\s]?date|as[_\s]?of[_\s]?date|report[_\s]?date|month|quarter|year|date)\b",
    re.I,
)

# ── HR feature signals ────────────────────────────────────────────────────────

_FEATURE_SIGNALS_EN = {
    "age", "gender", "tenure", "years_at_company", "years_in_role",
    "department", "job_level", "job_grade", "performance_rating",
    "last_promotion_date", "training_hours", "overtime_hours",
    "satisfaction_score", "engagement_score", "burnout_score",
    "salary_band", "salary_grade", "manager_id", "team_size",
    "work_from_home", "saudization_percentage", "nationality",
}


# ── Report types ──────────────────────────────────────────────────────────────

class ReadinessLevel(str, Enum):
    READY = "READY"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"


@dataclass
class ColumnClassification:
    name: str
    classification: str          # 'pii' | 'leakage' | 'target' | 'feature' | 'unknown'
    reason: str
    blocked: bool = False


@dataclass
class DataQualityMetrics:
    total_rows: int
    total_columns: int
    duplicate_rows: int
    missing_value_pct: float     # 0–100
    empty_columns: list[str] = field(default_factory=list)
    high_null_columns: list[str] = field(default_factory=list)  # >50% null
    suspicious_salary_flag: bool = False


@dataclass
class FileIngestionReport:
    tenant_id: str
    filename: str
    readiness_level: ReadinessLevel
    ingestion_result: IngestionResult          # raw ingestion from ExcelIngestionEngine
    column_classifications: list[ColumnClassification]
    data_quality: DataQualityMetrics
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    identified_target_column: Optional[str] = None
    pii_columns_detected: list[str] = field(default_factory=list)
    leakage_columns_detected: list[str] = field(default_factory=list)
    feature_columns: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    governance_scan_passed: bool = False


# ── Engine ────────────────────────────────────────────────────────────────────

class SecureFileIngestion:
    """
    Wraps ExcelIngestionEngine with full governance scanning.

    Usage:
        engine = SecureFileIngestion()
        report = engine.scan(raw_bytes, filename, tenant_id)
    """

    def __init__(self) -> None:
        self._ingestion_engine = ExcelIngestionEngine()

    def scan(
        self,
        raw_bytes: bytes,
        filename: str,
        tenant_id: str,
    ) -> FileIngestionReport:
        """
        Full governance scan of an uploaded file.

        Returns a FileIngestionReport with readiness_level:
          READY       — safe to proceed to theory activation
          CONDITIONAL — warnings present, user should review, can proceed with caution
          BLOCKED     — hard stop, file cannot be used
        """
        blocking_reasons: list[str] = []
        warnings: list[str] = []

        # ── Tenant validation ─────────────────────────────────────────────────
        if not tenant_id or not isinstance(tenant_id, str) or not tenant_id.strip():
            return self._blocked_report(
                tenant_id=tenant_id or "UNKNOWN",
                filename=filename,
                reason="tenant_id is missing or invalid. File cannot be processed without tenant context.",
            )

        tenant_id = tenant_id.strip()

        # ── Ingest ────────────────────────────────────────────────────────────
        result = self._ingestion_engine.ingest(raw_bytes, filename)

        if not result.success:
            return self._blocked_report(
                tenant_id=tenant_id,
                filename=filename,
                reason=f"File could not be parsed: {result.error}",
                ingestion_result=result,
            )

        df = result.df

        # ── Deduplication (pipeline-level: runs once, before any module reads
        #    this dataframe, so a single record is never double-counted by
        #    risk scoring, overtime cost, or payroll movement analysis) ───────
        df, dedup_notes = self._deduplicate(df)
        if dedup_notes:
            warnings.extend(dedup_notes)
        result.df = df
        result.row_count = len(df)

        # ── Column classification ─────────────────────────────────────────────
        classifications: list[ColumnClassification] = []
        pii_columns: list[str] = []
        leakage_columns: list[str] = []
        target_column: Optional[str] = None
        feature_columns: list[str] = []

        for col in df.columns:
            cls = self._classify_column(col)
            classifications.append(cls)
            if cls.classification == "pii":
                pii_columns.append(col)
                blocking_reasons.append(
                    f"PII column detected: '{col}' ({cls.reason}). "
                    "Remove this column before upload per PDPL Article 6."
                )
            elif cls.classification == "leakage":
                leakage_columns.append(col)
                blocking_reasons.append(
                    f"Leakage column detected: '{col}' ({cls.reason}). "
                    "This column contains post-event information that would invalidate model training."
                )
            elif cls.classification == "target":
                if target_column is None:
                    target_column = col
                else:
                    warnings.append(
                        f"Multiple target-like columns found: '{target_column}' and '{col}'. "
                        "Only one target column is supported."
                    )
            elif cls.classification == "feature":
                feature_columns.append(col)

        # ── Data quality ──────────────────────────────────────────────────────
        # (computed on the already-deduplicated df — see _deduplicate() above,
        # which already disclosed any duplicate rows found/removed via `warnings`)
        dq = self._compute_data_quality(df)

        if dq.missing_value_pct > 30:
            warnings.append(
                f"High missing value rate: {dq.missing_value_pct:.1f}% of cells are null. "
                "Model quality may be impacted."
            )

        if dq.empty_columns:
            warnings.append(
                f"Completely empty columns will be dropped: {dq.empty_columns}"
            )

        if dq.high_null_columns:
            warnings.append(
                f"Columns with >50% null values: {dq.high_null_columns}. "
                "Consider removing or imputing."
            )

        if dq.suspicious_salary_flag:
            warnings.append(
                "Salary distribution appears anomalous (possible formatting errors or outliers). "
                "Review salary column before proceeding."
            )

        if dq.total_rows < 50:
            blocking_reasons.append(
                f"Insufficient data: only {dq.total_rows} rows. "
                "Minimum 50 rows required for meaningful organizational analysis."
            )

        # ── Target column check ───────────────────────────────────────────────
        if target_column is None:
            warnings.append(
                "No target column identified. Platform will operate in exploration mode "
                "(stability scoring without supervised labels). "
                "Add a column like 'flight_risk' or 'stability_score' for supervised training."
            )

        # ── Feature adequacy ──────────────────────────────────────────────────
        if len(feature_columns) < 3:
            blocking_reasons.append(
                f"Insufficient feature columns: {len(feature_columns)} HR-relevant columns found "
                "(minimum 3 required). Ensure dataset includes columns such as department, tenure, "
                "job_level, performance_rating."
            )

        # ── Recommended actions ───────────────────────────────────────────────
        recommended_actions = self._build_recommendations(
            pii_columns=pii_columns,
            leakage_columns=leakage_columns,
            target_column=target_column,
            feature_columns=feature_columns,
            dq=dq,
            warnings=warnings,
        )

        # ── Readiness level ───────────────────────────────────────────────────
        if blocking_reasons:
            readiness = ReadinessLevel.BLOCKED
            governance_passed = False
        elif warnings:
            readiness = ReadinessLevel.CONDITIONAL
            governance_passed = True
        else:
            readiness = ReadinessLevel.READY
            governance_passed = True

        logger.info(
            "Secure scan complete tenant=%s file=%s readiness=%s pii=%d leakage=%d",
            tenant_id, filename, readiness.value, len(pii_columns), len(leakage_columns),
        )

        return FileIngestionReport(
            tenant_id=tenant_id,
            filename=filename,
            readiness_level=readiness,
            ingestion_result=result,
            column_classifications=classifications,
            data_quality=dq,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            identified_target_column=target_column,
            pii_columns_detected=pii_columns,
            leakage_columns_detected=leakage_columns,
            feature_columns=feature_columns,
            recommended_actions=recommended_actions,
            governance_scan_passed=governance_passed,
        )

    # ── Column classification ─────────────────────────────────────────────────

    def _classify_column(self, col: str) -> ColumnClassification:
        col_lower = col.lower().strip()
        col_normalized = re.sub(r"[\s\-./]", "_", col_lower)

        # PII check — exact set membership first
        if col_normalized in _PII_PATTERNS_EN or col_normalized in _PII_PATTERNS_AR:
            return ColumnClassification(
                name=col, classification="pii",
                reason="exact match to known PII field name",
                blocked=True,
            )

        # PII regex patterns
        for pattern in _PII_REGEX_PATTERNS:
            if pattern.search(col_normalized):
                return ColumnClassification(
                    name=col, classification="pii",
                    reason=f"matches PII pattern: {pattern.pattern}",
                    blocked=True,
                )

        # Leakage check — exact set membership first
        if col_normalized in _LEAKAGE_PATTERNS_EN or col_normalized in _LEAKAGE_PATTERNS_AR:
            return ColumnClassification(
                name=col, classification="leakage",
                reason="exact match to known leakage field name",
                blocked=True,
            )

        # Leakage regex patterns
        for pattern in _LEAKAGE_REGEX_PATTERNS:
            if pattern.search(col_normalized):
                return ColumnClassification(
                    name=col, classification="leakage",
                    reason=f"matches leakage pattern: {pattern.pattern}",
                    blocked=True,
                )

        # Target column check
        if col_normalized in _TARGET_CANDIDATES_EN or col_normalized in _TARGET_CANDIDATES_AR:
            return ColumnClassification(
                name=col, classification="target",
                reason="matches known target column name",
            )

        # HR feature signal check
        if col_normalized in _FEATURE_SIGNALS_EN:
            return ColumnClassification(
                name=col, classification="feature",
                reason="recognized HR feature column",
            )

        # Partial feature signal
        for signal in _FEATURE_SIGNALS_EN:
            if signal in col_normalized:
                return ColumnClassification(
                    name=col, classification="feature",
                    reason=f"contains HR feature signal '{signal}'",
                )

        return ColumnClassification(
            name=col, classification="unknown",
            reason="not matched to any known category",
        )

    # ── Deduplication ────────────────────────────────────────────────────────

    def _deduplicate(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """
        Remove duplicate rows before any downstream module reads this
        dataframe, so a single uploaded record is never double-counted
        (e.g. inflating an at-risk percentage). Never silent — always
        returns a disclosure note when rows are removed.

        Strategy:
          - If a confident employee-ID column exists AND a recognisable
            period/date column also exists (see _PERIOD_COLUMN_PATTERNS —
            kept in sync with payroll_movement_tracker.py's own period
            detection), dedupe on the COMPOSITE (id, period) key: the same
            employee legitimately repeats across multiple periods in
            longitudinal data (e.g. one row per employee per month), so the
            ID alone is not a safe duplicate signal there. Two rows are only
            duplicates when both the ID and the period match.
          - If a confident employee-ID column exists and no period column is
            present, dedupe on that ID column alone (keep first occurrence):
            two rows sharing the same employee ID are the same person
            regardless of what else differs between them.
          - Otherwise, dedupe on exact full-row match only — a partial
            overlap between two rows is never assumed to be the same record.
        """
        if df is None or df.empty:
            return df, []

        id_col: Optional[str] = None
        for col in df.columns:
            if _ID_COLUMN_PATTERNS.search(str(col).strip().lower()):
                id_col = col
                break

        if id_col is not None and df[id_col].notna().any():
            period_col: Optional[str] = None
            for col in df.columns:
                if col != id_col and _PERIOD_COLUMN_PATTERNS.search(str(col).strip().lower()):
                    period_col = col
                    break

            if period_col is not None:
                # Longitudinal data: the same employee ID legitimately
                # repeats across multiple periods. Matching on the ID alone
                # would strip every period after the first, destroying real
                # history (confirmed live: a 60-employee x 18-period payroll
                # upload was wrongly reduced from 1080 rows to 60). Only an
                # (id, period) pair repeating is a genuine duplicate.
                dup_mask = df[id_col].notna() & df.duplicated(subset=[id_col, period_col], keep="first")
                n_dupes = int(dup_mask.sum())
                if n_dupes == 0:
                    return df, []
                deduped = df[~dup_mask].reset_index(drop=True)
                return deduped, [
                    f"{n_dupes} duplicate (employee, period) row(s) removed before "
                    f"analysis (matched by '{id_col}' + '{period_col}' together — "
                    f"the same employee AND the same period both appeared more than "
                    f"once; the same employee across different periods is legitimate "
                    f"longitudinal data and was kept). "
                    f"{len(df)} row(s) in the original upload, {len(deduped)} remain."
                ]

            dup_mask = df[id_col].notna() & df.duplicated(subset=[id_col], keep="first")
            n_dupes = int(dup_mask.sum())
            if n_dupes == 0:
                return df, []
            deduped = df[~dup_mask].reset_index(drop=True)
            return deduped, [
                f"{n_dupes} duplicate row(s) removed before analysis (matched by "
                f"'{id_col}' — the same ID appeared more than once). "
                f"{len(df)} row(s) in the original upload, {len(deduped)} remain."
            ]

        full_dup_mask = df.duplicated(keep="first")
        n_dupes = int(full_dup_mask.sum())
        if n_dupes == 0:
            return df, []
        deduped = df[~full_dup_mask].reset_index(drop=True)
        return deduped, [
            f"{n_dupes} exact duplicate row(s) removed before analysis (no employee-ID "
            f"column was found, so rows were compared across all columns). "
            f"{len(df)} row(s) in the original upload, {len(deduped)} remain."
        ]

    # ── Data quality ──────────────────────────────────────────────────────────

    def _compute_data_quality(self, df: pd.DataFrame) -> DataQualityMetrics:
        total_rows = len(df)
        total_cols = len(df.columns)

        duplicate_rows = int(df.duplicated().sum())

        total_cells = total_rows * total_cols if total_cols > 0 else 1
        missing_cells = int(df.isnull().sum().sum())
        missing_pct = (missing_cells / total_cells) * 100 if total_cells > 0 else 0.0

        empty_cols = [c for c in df.columns if df[c].isnull().all()]

        high_null_cols = [
            c for c in df.columns
            if df[c].isnull().mean() > 0.5 and c not in empty_cols
        ]

        # Suspicious salary distribution: any salary column with stddev/mean > 10
        suspicious_salary = False
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ("salary", "راتب", "income", "pay")):
                numeric_col = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(numeric_col) > 10:
                    mean_val = numeric_col.mean()
                    std_val = numeric_col.std()
                    if mean_val > 0 and (std_val / mean_val) > 10:
                        suspicious_salary = True

        return DataQualityMetrics(
            total_rows=total_rows,
            total_columns=total_cols,
            duplicate_rows=duplicate_rows,
            missing_value_pct=round(missing_pct, 2),
            empty_columns=empty_cols,
            high_null_columns=high_null_cols,
            suspicious_salary_flag=suspicious_salary,
        )

    # ── Recommendations ───────────────────────────────────────────────────────

    def _build_recommendations(
        self,
        pii_columns: list[str],
        leakage_columns: list[str],
        target_column: Optional[str],
        feature_columns: list[str],
        dq: DataQualityMetrics,
        warnings: list[str],
    ) -> list[str]:
        recs: list[str] = []

        if pii_columns:
            recs.append(
                f"Remove PII columns before re-uploading: {', '.join(pii_columns)}. "
                "These cannot be processed under PDPL data minimization requirements."
            )

        if leakage_columns:
            recs.append(
                f"Remove leakage columns: {', '.join(leakage_columns)}. "
                "These contain post-event information that would create temporal leakage."
            )

        if not target_column:
            recs.append(
                "Add a target column (e.g. 'flight_risk', 'stability_score') with values 0/1 or 0.0–1.0 "
                "to enable supervised model training."
            )

        if len(feature_columns) < 5:
            recs.append(
                "Add more HR feature columns: department, job_level, tenure, performance_rating, "
                "training_hours, satisfaction_score are recommended for optimal construct coverage."
            )

        if dq.high_null_columns:
            recs.append(
                f"Impute or remove columns with high null rates: {', '.join(dq.high_null_columns)}."
            )

        return recs

    # ── Helper: blocked report ────────────────────────────────────────────────

    def _blocked_report(
        self,
        tenant_id: str,
        filename: str,
        reason: str,
        ingestion_result: Optional[IngestionResult] = None,
    ) -> FileIngestionReport:
        if ingestion_result is None:
            from .excel_ingestion_engine import IngestionResult as IR
            ingestion_result = IR(
                success=False, df=None, row_count=0, column_count=0,
                original_headers=[], normalized_headers=[],
                detected_language="unknown", detected_erp_style=None,
                encoding_used="none", sheet_used=None,
                error=reason,
            )
        return FileIngestionReport(
            tenant_id=tenant_id,
            filename=filename,
            readiness_level=ReadinessLevel.BLOCKED,
            ingestion_result=ingestion_result,
            column_classifications=[],
            data_quality=DataQualityMetrics(
                total_rows=0, total_columns=0,
                duplicate_rows=0, missing_value_pct=0.0,
            ),
            blocking_reasons=[reason],
            warnings=[],
            governance_scan_passed=False,
        )
