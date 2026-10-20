"""
Job Market Dataset Handler — Phase 10.

Handles three non-attrition dataset types from the real Saudi validation corpus:

  1. Jadarat_data12.csv       — Arabic Saudi job market postings (Hijri dates, benefits list)
  2. processed_dataset.csv   — Cleaned Saudi job market data (numeric salary, sensitive comp_name)
  3. Job Posting.csv         — Large global job postings stress-test (cp1256, 9919 rows)

Design rules:
  - NEVER trigger attrition modeling for these datasets
  - NEVER generate stability scores, flight-risk scores, or turnover predictions
  - comp_name / company identifiers are SENSITIVE — exclude from executive outputs
  - Produce honest market intelligence summaries only
  - Hijri dates are recognised but not converted (calendar ambiguity)
  - Benefits fields are parsed best-effort; failures are logged, not raised
  - All results include explicit analysis_mode = "market_intelligence"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Dataset sub-type ──────────────────────────────────────────────────────────

class JobMarketSubtype(str, Enum):
    JADARAT_SAUDI_POSTINGS  = "JADARAT_SAUDI_POSTINGS"
    PROCESSED_JOB_MARKET    = "PROCESSED_JOB_MARKET"
    GLOBAL_STRESS_TEST      = "GLOBAL_STRESS_TEST"
    GENERIC_JOB_MARKET      = "GENERIC_JOB_MARKET"


# ── Sensitive column registry ─────────────────────────────────────────────────
# These columns must NOT appear in executive-facing outputs.

_SENSITIVE_COLUMNS: set[str] = {
    "comp_name", "company_name", "employer_name",
    "comp_no", "company_number",
    "national_id", "iqama", "employee_id", "emp_id",
    "email", "phone", "mobile",
}


# ── Hijri date pattern ────────────────────────────────────────────────────────
# Jadarat job_date values look like '27/05/1444' — Hijri year range 1400–1460

_HIJRI_DATE_RE = re.compile(
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](1[34]\d{2})\b"
)


def _is_hijri_date(val: str) -> bool:
    """Return True if val looks like a Hijri date (year 1300–1600)."""
    if pd.isna(val):
        return False
    m = _HIJRI_DATE_RE.search(str(val))
    if m:
        year = int(m.group(3))
        return 1300 <= year <= 1600
    return False


def _detect_hijri_column(series: pd.Series) -> bool:
    """Return True if the majority of non-null values in the series are Hijri dates."""
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return False
    hijri_count = sum(1 for v in non_null if _is_hijri_date(v))
    return hijri_count / len(non_null) >= 0.5


# ── Jadarat benefits parser ───────────────────────────────────────────────────
# Benefits values look like: "['Salary', '5000.0']" or "['Housing', 'Transportation']"

_SALARY_FROM_BENEFITS_RE = re.compile(r"[\d,]+\.?\d*")


def _extract_salary_from_benefits(val) -> Optional[float]:
    """
    Pull the first numeric value from a Jadarat benefits string.
    Returns None if no numeric is found or the value is null.
    """
    if pd.isna(val):
        return None
    text = str(val)
    # Only try if 'Salary' or 'salary' appears nearby
    if "alary" not in text and "راتب" not in text:
        return None
    nums = _SALARY_FROM_BENEFITS_RE.findall(text)
    for n in nums:
        try:
            f = float(n.replace(",", ""))
            if f >= 100:   # plausible salary (SAR)
                return f
        except ValueError:
            continue
    return None


# ── Position slot parser ──────────────────────────────────────────────────────
# Jadarat positions values: "0 / 3" → filled=0, total=3

_POSITIONS_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def _parse_positions(val) -> tuple[Optional[int], Optional[int]]:
    """Return (filled, total) from '0 / 3' format. (None, None) if unparseable."""
    if pd.isna(val):
        return None, None
    m = _POSITIONS_RE.search(str(val))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


# ── Experience parser ─────────────────────────────────────────────────────────
# Jadarat exper: "0 Years", "3 Years", "5 Years"

_EXPER_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[Yy]ears?")


def _parse_experience_years(val) -> Optional[float]:
    """Return numeric years from '3 Years'. None if unparseable."""
    if pd.isna(val):
        return None
    m = _EXPER_RE.search(str(val))
    if m:
        return float(m.group(1))
    return None


# ── Subtype detector ──────────────────────────────────────────────────────────

def _detect_subtype(df: pd.DataFrame, filename: str = "") -> JobMarketSubtype:
    """Identify which job-market sub-type we are handling."""
    cols_lower = {str(c).lower().strip() for c in df.columns}

    # Jadarat: Arabic-centric Saudi postings with specific column set
    jadarat_cols = {"job_date", "comp_name", "comp_no", "comp_type", "comp_size",
                    "eco_activity", "qualif", "contract", "positions", "exper",
                    "region", "city", "benefits"}
    jadarat_hits = len(cols_lower & jadarat_cols)
    if jadarat_hits >= 5:
        return JobMarketSubtype.JADARAT_SAUDI_POSTINGS

    # Processed dataset: clean market data, numeric salary present
    processed_cols = {"job_title", "comp_name", "region", "city", "salary"}
    processed_hits = len(cols_lower & processed_cols)
    if processed_hits >= 3 and len(df) <= 3000:
        return JobMarketSubtype.PROCESSED_JOB_MARKET

    # Global stress test: large row count with global posting signals
    global_cols = {"job_opening_title", "first_seen_at", "last_seen_at",
                   "website_domain", "ticker", "onet_code", "seniority"}
    global_hits = len(cols_lower & global_cols)
    if global_hits >= 2 or len(df) > 5000:
        return JobMarketSubtype.GLOBAL_STRESS_TEST

    return JobMarketSubtype.GENERIC_JOB_MARKET


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class JobMarketHandlingResult:
    success: bool
    subtype: JobMarketSubtype
    analysis_mode: str                      # always "market_intelligence"
    attrition_blocked: bool                 # always True
    attrition_block_reason: str

    row_count: int
    column_count: int
    columns_present: list[str]
    sensitive_columns_detected: list[str]   # excluded from executive outputs

    # Jadarat-specific
    hijri_date_column: Optional[str]
    salary_extracted_count: int             # rows where salary was parsed from benefits
    position_slots_parsed: bool
    experience_parsed: bool

    # Market summary (safe for executive view — no sensitive columns)
    salary_stats: dict                      # {mean, median, min, max, parsed_count}
    region_distribution: dict              # {region: count}
    sector_distribution: dict             # {sector/eco_activity: count}
    top_job_titles: list[str]
    open_position_slots: Optional[int]     # total positions available (Jadarat only)
    avg_experience_required: Optional[float]

    # Governance
    transformations: list[str]
    warnings: list[str]
    error: Optional[str] = None


# ── Handler ───────────────────────────────────────────────────────────────────

class JobMarketDatasetHandler:
    """
    Processes job-market datasets for market-intelligence analysis only.

    Usage:
        handler = JobMarketDatasetHandler()
        result = handler.handle(df, filename="Jadarat_data12.csv")
    """

    _ATTRITION_BLOCK_REASON = (
        "This dataset is classified as a job market posting dataset. "
        "It contains vacancy/posting records, not employee-level HR behavioral data. "
        "Attrition modeling, flight-risk scoring, and workforce stability predictions "
        "are not permitted for this dataset type. "
        "Only market intelligence analysis (salary ranges, sector distribution, "
        "vacancy volumes, experience requirements) is allowed."
    )

    def handle(self, df: pd.DataFrame, filename: str = "") -> JobMarketHandlingResult:
        transformations: list[str] = []
        warnings: list[str] = []

        subtype = _detect_subtype(df, filename)
        logger.info("JobMarketDatasetHandler: subtype=%s rows=%d", subtype, len(df))

        cols_present = list(df.columns)
        cols_lower_map = {str(c).lower().replace("\xa0", "").strip(): c for c in df.columns}

        # ── Sensitive column detection ────────────────────────────────────────
        sensitive_found: list[str] = []
        for c_lower, c_orig in cols_lower_map.items():
            if c_lower in _SENSITIVE_COLUMNS:
                sensitive_found.append(c_orig)
        if sensitive_found:
            warnings.append(
                f"Sensitive columns detected (excluded from executive outputs): {sensitive_found}"
            )

        # ── Route to sub-handler ──────────────────────────────────────────────
        if subtype == JobMarketSubtype.JADARAT_SAUDI_POSTINGS:
            return self._handle_jadarat(
                df, cols_lower_map, sensitive_found, transformations, warnings
            )
        elif subtype == JobMarketSubtype.PROCESSED_JOB_MARKET:
            return self._handle_processed(
                df, cols_lower_map, sensitive_found, transformations, warnings
            )
        else:
            return self._handle_generic(
                df, subtype, cols_lower_map, sensitive_found, transformations, warnings
            )

    # ── Jadarat handler ───────────────────────────────────────────────────────

    def _handle_jadarat(
        self,
        df: pd.DataFrame,
        cols_lower_map: dict,
        sensitive_found: list[str],
        transformations: list[str],
        warnings: list[str],
    ) -> JobMarketHandlingResult:

        # Hijri date detection
        hijri_col = None
        date_col_orig = cols_lower_map.get("job_date")
        if date_col_orig is not None and date_col_orig in df.columns:
            if _detect_hijri_column(df[date_col_orig]):
                hijri_col = date_col_orig
                warnings.append(
                    f"Column '{date_col_orig}' contains Hijri dates. "
                    "Dates are recognised but not converted to Gregorian — "
                    "Hijri→Gregorian conversion requires calendar variant confirmation."
                )
                transformations.append(f"Hijri date column detected: '{date_col_orig}'")

        # Salary extraction from benefits
        benefits_col = cols_lower_map.get("benefits")
        salary_extracted = 0
        salary_vals: list[float] = []
        if benefits_col is not None and benefits_col in df.columns:
            extracted = df[benefits_col].apply(_extract_salary_from_benefits)
            salary_extracted = int(extracted.notna().sum())
            salary_vals = extracted.dropna().tolist()
            if salary_extracted > 0:
                df = df.copy()
                df["salary_extracted_sar"] = extracted
                transformations.append(
                    f"Salary extracted from benefits column for {salary_extracted} rows "
                    f"→ 'salary_extracted_sar'"
                )
            else:
                warnings.append(
                    "Benefits column present but no salary amounts could be extracted. "
                    "Benefits may not include Salary entries."
                )

        # Position slots
        positions_col = cols_lower_map.get("positions")
        open_slots: Optional[int] = None
        positions_parsed = False
        if positions_col is not None and positions_col in df.columns:
            parsed = df[positions_col].apply(_parse_positions)
            filled_list = [p[0] for p in parsed if p[0] is not None]
            total_list  = [p[1] for p in parsed if p[1] is not None]
            if total_list:
                positions_parsed = True
                open_slots = sum(
                    t - f for f, t in zip(filled_list, total_list)
                    if t is not None and f is not None and t >= f
                )
                transformations.append(
                    f"Position slots parsed from '{positions_col}': "
                    f"total={sum(total_list)}, open={open_slots}"
                )

        # Experience
        exper_col = cols_lower_map.get("exper")
        avg_exp: Optional[float] = None
        exp_parsed = False
        if exper_col is not None and exper_col in df.columns:
            exp_vals = df[exper_col].apply(_parse_experience_years).dropna()
            if len(exp_vals) > 0:
                exp_parsed = True
                avg_exp = float(exp_vals.mean())
                transformations.append(
                    f"Experience parsed from '{exper_col}': mean={avg_exp:.1f} years"
                )

        # Region distribution
        region_dist = self._value_counts_safe(df, cols_lower_map, "region", top_n=15)

        # Sector (eco_activity)
        sector_dist = self._value_counts_safe(df, cols_lower_map, "eco_activity", top_n=15)

        # Top job titles
        top_titles = self._top_values_safe(df, cols_lower_map, "job_title", n=10)

        # Salary stats
        salary_stats = self._compute_salary_stats(salary_vals)

        return JobMarketHandlingResult(
            success=True,
            subtype=JobMarketSubtype.JADARAT_SAUDI_POSTINGS,
            analysis_mode="market_intelligence",
            attrition_blocked=True,
            attrition_block_reason=self._ATTRITION_BLOCK_REASON,
            row_count=len(df),
            column_count=len(df.columns),
            columns_present=list(df.columns),
            sensitive_columns_detected=sensitive_found,
            hijri_date_column=hijri_col,
            salary_extracted_count=salary_extracted,
            position_slots_parsed=positions_parsed,
            experience_parsed=exp_parsed,
            salary_stats=salary_stats,
            region_distribution=region_dist,
            sector_distribution=sector_dist,
            top_job_titles=top_titles,
            open_position_slots=open_slots,
            avg_experience_required=avg_exp,
            transformations=transformations,
            warnings=warnings,
        )

    # ── Processed dataset handler ─────────────────────────────────────────────

    def _handle_processed(
        self,
        df: pd.DataFrame,
        cols_lower_map: dict,
        sensitive_found: list[str],
        transformations: list[str],
        warnings: list[str],
    ) -> JobMarketHandlingResult:

        # Salary column (numeric)
        salary_vals: list[float] = []
        salary_col = cols_lower_map.get("salary")
        if salary_col is not None and salary_col in df.columns:
            numeric_salary = pd.to_numeric(df[salary_col], errors="coerce")
            salary_vals = numeric_salary.dropna().tolist()
            if salary_vals:
                transformations.append(
                    f"Numeric salary column '{salary_col}' read: "
                    f"{len(salary_vals)} non-null values"
                )
            else:
                warnings.append(f"Salary column '{salary_col}' present but no numeric values parsed.")

        # comp_name is sensitive — warn explicitly
        comp_col = cols_lower_map.get("comp_name")
        if comp_col and comp_col not in sensitive_found:
            sensitive_found.append(comp_col)
            warnings.append(
                f"'{comp_col}' column detected — company names are sensitive "
                "and excluded from executive outputs."
            )

        region_dist  = self._value_counts_safe(df, cols_lower_map, "region", top_n=15)
        sector_dist  = self._value_counts_safe(df, cols_lower_map, "eco_activity", top_n=10)
        top_titles   = self._top_values_safe(df, cols_lower_map, "job_title", n=10)
        salary_stats = self._compute_salary_stats(salary_vals)

        return JobMarketHandlingResult(
            success=True,
            subtype=JobMarketSubtype.PROCESSED_JOB_MARKET,
            analysis_mode="market_intelligence",
            attrition_blocked=True,
            attrition_block_reason=self._ATTRITION_BLOCK_REASON,
            row_count=len(df),
            column_count=len(df.columns),
            columns_present=list(df.columns),
            sensitive_columns_detected=sensitive_found,
            hijri_date_column=None,
            salary_extracted_count=len(salary_vals),
            position_slots_parsed=False,
            experience_parsed=False,
            salary_stats=salary_stats,
            region_distribution=region_dist,
            sector_distribution=sector_dist,
            top_job_titles=top_titles,
            open_position_slots=None,
            avg_experience_required=None,
            transformations=transformations,
            warnings=warnings,
        )

    # ── Generic / global stress-test handler ─────────────────────────────────

    def _handle_generic(
        self,
        df: pd.DataFrame,
        subtype: JobMarketSubtype,
        cols_lower_map: dict,
        sensitive_found: list[str],
        transformations: list[str],
        warnings: list[str],
    ) -> JobMarketHandlingResult:

        if subtype == JobMarketSubtype.GLOBAL_STRESS_TEST:
            warnings.append(
                "STRESS TEST MODE: This dataset is a large global job posting file. "
                "It is used for ingestion robustness testing only. "
                "No Saudi workforce conclusions should be drawn from this data."
            )

        # Best-effort salary extraction (many salary fields may be null or JSON-like)
        salary_vals: list[float] = []
        for key in ("salary", "salary_data", "salary_range", "salary_min"):
            sal_col = cols_lower_map.get(key)
            if sal_col and sal_col in df.columns:
                parsed = pd.to_numeric(df[sal_col], errors="coerce").dropna()
                if len(parsed) > 0:
                    salary_vals = parsed.tolist()
                    null_rate = df[sal_col].isna().mean()
                    transformations.append(
                        f"Salary parsed from '{sal_col}': "
                        f"{len(salary_vals)} values, {null_rate:.1%} null rate"
                    )
                    if null_rate > 0.8:
                        warnings.append(
                            f"Salary column '{sal_col}' has {null_rate:.1%} null rate — "
                            "salary statistics are unreliable."
                        )
                    break

        region_dist  = self._value_counts_safe(df, cols_lower_map, "region", top_n=10)
        sector_dist  = self._value_counts_safe(df, cols_lower_map, "category", top_n=10)
        top_titles   = self._top_values_safe(df, cols_lower_map, "job_title", n=10)
        salary_stats = self._compute_salary_stats(salary_vals)

        if not salary_vals:
            warnings.append(
                "No salary data could be extracted from this dataset. "
                "Salary statistics are unavailable."
            )

        return JobMarketHandlingResult(
            success=True,
            subtype=subtype,
            analysis_mode="market_intelligence",
            attrition_blocked=True,
            attrition_block_reason=self._ATTRITION_BLOCK_REASON,
            row_count=len(df),
            column_count=len(df.columns),
            columns_present=list(df.columns),
            sensitive_columns_detected=sensitive_found,
            hijri_date_column=None,
            salary_extracted_count=len(salary_vals),
            position_slots_parsed=False,
            experience_parsed=False,
            salary_stats=salary_stats,
            region_distribution=region_dist,
            sector_distribution=sector_dist,
            top_job_titles=top_titles,
            open_position_slots=None,
            avg_experience_required=None,
            transformations=transformations,
            warnings=warnings,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _value_counts_safe(
        self,
        df: pd.DataFrame,
        cols_lower_map: dict,
        key: str,
        top_n: int = 10,
    ) -> dict:
        col = cols_lower_map.get(key)
        if col is None or col not in df.columns:
            return {}
        try:
            counts = df[col].value_counts().head(top_n)
            return {str(k): int(v) for k, v in counts.items()}
        except Exception:
            return {}

    def _top_values_safe(
        self,
        df: pd.DataFrame,
        cols_lower_map: dict,
        key: str,
        n: int = 10,
    ) -> list[str]:
        col = cols_lower_map.get(key)
        if col is None or col not in df.columns:
            return []
        try:
            return df[col].value_counts().head(n).index.tolist()
        except Exception:
            return []

    def _compute_salary_stats(self, salary_vals: list[float]) -> dict:
        if not salary_vals:
            return {
                "mean": None, "median": None,
                "min": None, "max": None, "parsed_count": 0,
            }
        arr = np.array(salary_vals, dtype=float)
        return {
            "mean":   round(float(np.mean(arr)), 2),
            "median": round(float(np.median(arr)), 2),
            "min":    round(float(np.min(arr)), 2),
            "max":    round(float(np.max(arr)), 2),
            "parsed_count": len(salary_vals),
        }
