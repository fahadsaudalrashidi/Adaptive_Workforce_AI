"""
Dataset Type Classifier — Phase 10.

Classifies an uploaded dataset as one of four types before any analysis
decision is made. This classification gates which analytical modes are
permitted — only EMPLOYEE_ATTRITION_DATASET may trigger attrition modeling.

Classification is column-signal-based (not filename-based) to prevent
misclassification from renamed files.

Design rules:
  - Never trigger attrition prediction for JOB_MARKET_POSTING_DATASET
  - Never trigger attrition prediction for UNKNOWN_OR_UNSUPPORTED
  - Classification is deterministic given the same column set
  - Confidence score reflects signal strength (not model probability)
  - All decisions are auditable via the classification_evidence dict
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ── Dataset type enum ─────────────────────────────────────────────────────────

class DatasetType(str, Enum):
    EMPLOYEE_ATTRITION_DATASET = "EMPLOYEE_ATTRITION_DATASET"
    JOB_MARKET_POSTING_DATASET = "JOB_MARKET_POSTING_DATASET"
    GOVERNMENT_WORKFORCE_TABLE  = "GOVERNMENT_WORKFORCE_TABLE"
    GLOBAL_JOB_POSTING_STRESS_TEST = "GLOBAL_JOB_POSTING_STRESS_TEST"
    UNKNOWN_OR_UNSUPPORTED      = "UNKNOWN_OR_UNSUPPORTED"


# ── Analysis permissions by type ──────────────────────────────────────────────

ATTRITION_MODELING_ALLOWED: set[DatasetType] = {
    DatasetType.EMPLOYEE_ATTRITION_DATASET,
}

THEORY_ACTIVATION_ALLOWED: set[DatasetType] = {
    DatasetType.EMPLOYEE_ATTRITION_DATASET,
}

MARKET_INTELLIGENCE_ALLOWED: set[DatasetType] = {
    DatasetType.JOB_MARKET_POSTING_DATASET,
    DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST,
    DatasetType.GOVERNMENT_WORKFORCE_TABLE,
}

DASHBOARD_MODE: dict[DatasetType, str] = {
    DatasetType.EMPLOYEE_ATTRITION_DATASET:    "workforce_stability",
    DatasetType.JOB_MARKET_POSTING_DATASET:    "market_intelligence",
    DatasetType.GOVERNMENT_WORKFORCE_TABLE:     "government_workforce",
    DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST: "ingestion_stress_test",
    DatasetType.UNKNOWN_OR_UNSUPPORTED:         "blocked",
}


# ── Signal column sets ────────────────────────────────────────────────────────

# Strong employee-level HR signals
_ATTRITION_TARGET_SIGNALS = {
    "attrition", "turnover", "left", "resigned", "terminated", "churn",
    "الاستنزاف", "دوران_العمل", "استقال",
}

_EMPLOYEE_BEHAVIORAL_SIGNALS = {
    "job_satisfaction", "job_engagement", "emotional_commitment", "burnout",
    "psychological_exhaustion", "physical_stress", "work_life_balance",
    "work_live_balance", "environment_satisfaction", "job_stability",
    "recognition", "job_support", "useful_training_programs",
    "get_deserved_promotion", "job_opportunities", "health_issues",
    "overtime", "business_travel", "monthly_salary", "monthlysalary",
    "allowances", "medicalinsurance", "bonus", "payment_overtime",
    "rewards&wages_satisfaction", "distance_to_work",
}

_EMPLOYEE_DEMOGRAPHICS = {
    "age", "gender", "maritalstatus", "marital_status", "academic_degree",
    "years_experience", "department", "jobtitle", "job_title",
    "sector", "employee_id", "emp_id",
}

# Strong job posting signals
_JOB_POSTING_SIGNALS = {
    "job_title", "job_date", "job_desc", "job_tasks", "job_post_id",
    "comp_name", "comp_no", "comp_type", "comp_size", "eco_activity",
    "qualif", "contract", "positions", "exper", "region", "city",
    "benefits", "job_opening_title", "job_opening_url",
    "first_seen_at", "last_seen_at", "website_domain", "ticker",
    "location_data", "salary_data", "job_status", "job_language",
    "onet_code", "seniority", "category", "keywords", "description",
}

# Government/official signals
_GOVERNMENT_SIGNALS = {
    "gastat", "ministry", "nitaqat", "saudization_percentage",
    "employment_rate", "labor_force", "population_category",
    "qiwa_sector_code",
}


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    dataset_type: DatasetType
    confidence: float           # 0.0–1.0
    attrition_modeling_allowed: bool
    theory_activation_allowed: bool
    dashboard_mode: str
    detected_target_column: Optional[str]
    attrition_block_reason: Optional[str]
    classification_evidence: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_employee_dataset(self) -> bool:
        return self.dataset_type == DatasetType.EMPLOYEE_ATTRITION_DATASET

    @property
    def is_job_market_dataset(self) -> bool:
        return self.dataset_type in (
            DatasetType.JOB_MARKET_POSTING_DATASET,
            DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST,
        )


# ── Classifier ────────────────────────────────────────────────────────────────

class DatasetTypeClassifier:
    """
    Classifies a DataFrame's column set to determine which analysis modes
    are permitted. Does not read row data — classification is column-name-only.

    Usage:
        clf = DatasetTypeClassifier()
        result = clf.classify(df, filename="hr_data.xlsx")
    """

    def classify(
        self,
        df: pd.DataFrame,
        filename: str = "",
        row_count: Optional[int] = None,
    ) -> ClassificationResult:
        cols_raw = list(df.columns)
        cols_normalized = self._normalize_cols(cols_raw)
        n_rows = row_count if row_count is not None else len(df)

        # Score each type
        attrition_score  = self._score_attrition(cols_normalized, cols_raw)
        job_posting_score = self._score_job_posting(cols_normalized, n_rows)
        government_score  = self._score_government(cols_normalized)

        # Detect target column
        target_col = self._find_target_column(cols_normalized, cols_raw)

        # Classification logic
        dataset_type, confidence, evidence = self._decide(
            attrition_score=attrition_score,
            job_posting_score=job_posting_score,
            government_score=government_score,
            target_col=target_col,
            cols_normalized=cols_normalized,
            n_rows=n_rows,
            filename=filename,
        )

        attrition_allowed = dataset_type in ATTRITION_MODELING_ALLOWED
        theory_allowed    = dataset_type in THEORY_ACTIVATION_ALLOWED
        dash_mode         = DASHBOARD_MODE[dataset_type]

        block_reason: Optional[str] = None
        warnings: list[str] = []

        if not attrition_allowed:
            block_reason = self._build_block_reason(dataset_type, target_col)

        if dataset_type == DatasetType.EMPLOYEE_ATTRITION_DATASET and target_col is None:
            warnings.append(
                "No attrition target column detected. Attrition modeling will be blocked. "
                "Add a column named 'Attrition', 'flight_risk', or 'stability_score'."
            )
            attrition_allowed = False
            block_reason = "No attrition target column found in dataset."

        logger.info(
            "Dataset classified: type=%s confidence=%.2f target=%s file=%s",
            dataset_type.value, confidence, target_col, filename,
        )

        return ClassificationResult(
            dataset_type=dataset_type,
            confidence=confidence,
            attrition_modeling_allowed=attrition_allowed,
            theory_activation_allowed=theory_allowed,
            dashboard_mode=dash_mode,
            detected_target_column=target_col,
            attrition_block_reason=block_reason,
            classification_evidence=evidence,
            warnings=warnings,
        )

    # ── Scoring methods ────────────────────────────────────────────────────────

    def _score_attrition(self, cols_norm: list[str], cols_raw: list[str]) -> dict:
        cols_set = set(cols_norm)
        target_hits = [c for c in cols_norm if c in _ATTRITION_TARGET_SIGNALS]
        behavioral_hits = [c for c in cols_norm if c in _EMPLOYEE_BEHAVIORAL_SIGNALS]
        demographic_hits = [c for c in cols_norm if c in _EMPLOYEE_DEMOGRAPHICS]

        score = (
            len(target_hits) * 5 +
            len(behavioral_hits) * 2 +
            len(demographic_hits) * 1
        )
        return {
            "score": score,
            "target_hits": target_hits,
            "behavioral_hits": behavioral_hits,
            "demographic_hits": demographic_hits,
        }

    def _score_job_posting(self, cols_norm: list[str], n_rows: int) -> dict:
        cols_set = set(cols_norm)
        posting_hits = [c for c in cols_norm if c in _JOB_POSTING_SIGNALS]
        score = len(posting_hits) * 2
        # Large row count with posting columns → likely global stress-test
        is_large = n_rows > 5000
        if is_large and score > 6:
            score += 5
        return {
            "score": score,
            "posting_hits": posting_hits,
            "is_large_dataset": is_large,
        }

    def _score_government(self, cols_norm: list[str]) -> dict:
        gov_hits = [c for c in cols_norm if c in _GOVERNMENT_SIGNALS]
        score = len(gov_hits) * 3
        return {"score": score, "gov_hits": gov_hits}

    # ── Decision logic ─────────────────────────────────────────────────────────

    def _decide(
        self,
        attrition_score: dict,
        job_posting_score: dict,
        government_score: dict,
        target_col: Optional[str],
        cols_normalized: list[str],
        n_rows: int,
        filename: str,
    ) -> tuple[DatasetType, float, dict]:
        asc = attrition_score["score"]
        jsc = job_posting_score["score"]
        gsc = government_score["score"]
        is_large = job_posting_score["is_large_dataset"]

        evidence = {
            "attrition_score": asc,
            "job_posting_score": jsc,
            "government_score": gsc,
            "target_column": target_col,
            "column_count": len(cols_normalized),
            "row_count": n_rows,
            "behavioral_columns_found": attrition_score["behavioral_hits"],
            "posting_columns_found": job_posting_score["posting_hits"],
        }

        # Government table — highest specificity signals take precedence
        if gsc >= 6:
            return DatasetType.GOVERNMENT_WORKFORCE_TABLE, min(gsc / 15, 1.0), evidence

        # Employee attrition: strong behavioral signal OR explicit target present
        # (even without an explicit target, strong behavioral signal → attrition type)
        if asc >= 8 and asc > jsc:
            confidence = min(asc / 30, 1.0)
            return DatasetType.EMPLOYEE_ATTRITION_DATASET, confidence, evidence

        # Job posting: posting signals dominate, large dataset → stress test
        if jsc > asc:
            if is_large and jsc >= 10:
                return DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST, min(jsc / 25, 1.0), evidence
            if jsc >= 4:
                return DatasetType.JOB_MARKET_POSTING_DATASET, min(jsc / 20, 1.0), evidence

        # Weak signals on both sides
        if asc >= 4:
            return DatasetType.EMPLOYEE_ATTRITION_DATASET, min(asc / 30, 0.6), evidence

        return DatasetType.UNKNOWN_OR_UNSUPPORTED, 0.1, evidence

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _normalize_cols(self, cols: list[str]) -> list[str]:
        """Lowercase, strip whitespace, replace spaces with underscores."""
        result = []
        for c in cols:
            normalized = str(c)
            # Strip non-breaking space and regular whitespace
            normalized = normalized.replace("\xa0", "").strip()
            # Lowercase
            normalized = normalized.lower()
            # Replace inner spaces/underscores sequences
            normalized = re.sub(r"[\s_]+", "_", normalized)
            # Remove trailing underscores
            normalized = normalized.strip("_")
            result.append(normalized)
        return result

    def _find_target_column(
        self, cols_norm: list[str], cols_raw: list[str]
    ) -> Optional[str]:
        """Find the original column name that matches known target signals."""
        for norm, raw in zip(cols_norm, cols_raw):
            if norm in _ATTRITION_TARGET_SIGNALS:
                return raw
            # Partial match for composite names
            if any(sig in norm for sig in ("attrition", "turnover", "churn", "flight_risk")):
                return raw
        return None

    def _build_block_reason(
        self, dataset_type: DatasetType, target_col: Optional[str]
    ) -> str:
        if dataset_type == DatasetType.JOB_MARKET_POSTING_DATASET:
            return (
                "Dataset classified as JOB_MARKET_POSTING_DATASET. "
                "This dataset contains job posting records, not employee-level HR data. "
                "Attrition modeling requires employee behavioral and satisfaction data with "
                "an attrition target column."
            )
        if dataset_type == DatasetType.GLOBAL_JOB_POSTING_STRESS_TEST:
            return (
                "Dataset classified as GLOBAL_JOB_POSTING_STRESS_TEST. "
                "Large global job posting data. Not suitable for Saudi workforce attrition analysis. "
                "Use for ingestion and stress-testing only."
            )
        if dataset_type == DatasetType.GOVERNMENT_WORKFORCE_TABLE:
            return (
                "Dataset classified as GOVERNMENT_WORKFORCE_TABLE. "
                "Aggregate government statistics do not support individual attrition modeling."
            )
        return (
            "Dataset type is UNKNOWN_OR_UNSUPPORTED. "
            "Cannot identify sufficient HR-relevant columns for attrition analysis."
        )
