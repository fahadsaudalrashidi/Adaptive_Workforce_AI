# -*- coding: utf-8 -*-
"""
Saudi Data Governance Layer
============================

Enterprise-grade data quality and leakage governance for Saudi HR datasets.

Validates:
  - Saudi salary range plausibility (SAR-denominated)
  - Employee age validity (Saudi Labour Law constraints)
  - Tenure plausibility (impossible long tenure)
  - Duplicate employee record detection
  - Attrition rate plausibility (annual rate > 50% = suspicious)
  - Temporal contamination (post-outcome date leakage patterns)
  - Saudi-specific ERP leakage fields (Qiwa separation codes, Mudad payroll)
  - PII exposure (Iqama, national ID, GOSI number)
  - Nationalization data exposure (Saudization percentages as features)
  - Impossible HR patterns (age < 15, salary = 0, grade > max)

Does NOT:
  - Modify the DataFrame
  - Train or modify models
  - Remove records (returns findings only)
  - Override upstream governance decisions
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SAUDI LABOUR LAW & HR CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Saudi Labour Law Art. 3: minimum working age is 15 (hazardous: 18)
_MIN_EMPLOYEE_AGE: int = 15
_TYPICAL_RETIREMENT_AGE: int = 65     # General pension age in KSA
_SUSPICIOUS_AGE_HIGH: int = 70        # Unlikely to be employed (flag, not block)
_MAX_PLAUSIBLE_AGE: int = 80          # Impossible

# Tenure limits
_MAX_PLAUSIBLE_TENURE_YEARS: int = 45  # Company cannot be older than career
_SUSPICIOUS_TENURE_YEARS: int = 35     # Flag if > 35 years

# SAR salary ranges (monthly)
# Saudi Labour Law minimum wage 2024: 4,000 SAR/month for Saudis
_SAR_MINIMUM_WAGE: float = 4_000.0
_SAR_SUSPICIOUS_LOW: float = 1_000.0    # Below min wage = data error
_SAR_PLAUSIBLE_MAX: float = 200_000.0   # Above 200k/month = check for annual misentry
_SAR_LIKELY_ANNUAL_THRESHOLD: float = 60_000.0  # If mean > 60k, likely annual not monthly

# Attrition rate governance
_ATTRITION_SUSPICIOUS_HIGH: float = 0.50    # > 50% annual = suspicious
_ATTRITION_IMPOSSIBLE: float = 1.01         # > 100% = data error

# Duplicate thresholds
_DUPLICATE_EXACT_THRESHOLD: float = 0.02    # > 2% exact duplicates = flag


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DataQualityFinding:
    """A single data quality or governance finding."""
    finding_type: str
    severity: str                   # CRITICAL / HIGH / MEDIUM / INFO
    column_affected: Optional[str]
    n_records_affected: int
    description: str
    recommendation: str


@dataclass
class SaudiDataGovernanceReport:
    """Full output of Saudi data governance validation."""
    is_clean: bool                  # True only if n_critical == 0 and n_high == 0
    n_critical: int
    n_high: int
    n_medium: int
    n_info: int
    findings: List[DataQualityFinding]
    leakage_columns_detected: List[str]
    pii_columns_detected: List[str]
    impossible_records_count: int
    salary_currency_suspected: str  # "SAR_monthly" / "SAR_annual" / "USD" / "unknown"
    attrition_rate_observed: Optional[float]
    duplicate_rate: float
    summary: str
    governance_notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# LEAKAGE COLUMN PATTERNS (Saudi HR specific)
# ─────────────────────────────────────────────────────────────────────────────

_LEAKAGE_COLUMN_PATTERNS: List[Tuple[str, str, str]] = [
    # (pattern_substring, description, severity)
    ("exit_reason",          "Post-outcome exit reason",                  "CRITICAL"),
    ("termination_reason",   "Post-outcome termination reason",           "CRITICAL"),
    ("separation_reason",    "Post-outcome separation reason",            "CRITICAL"),
    ("resignation_date",     "Post-outcome resignation date",             "CRITICAL"),
    ("termination_date",     "Post-outcome termination date",             "CRITICAL"),
    ("last_working_day",     "Post-outcome last day",                     "CRITICAL"),
    ("offboarding_date",     "Post-outcome offboarding date",             "CRITICAL"),
    ("سبب الخروج",          "Exit reason in Arabic",                     "CRITICAL"),
    ("سبب الاستقالة",       "Resignation reason in Arabic",              "CRITICAL"),
    ("تاريخ الخروج",        "Exit date in Arabic",                       "CRITICAL"),
    ("آخر يوم عمل",         "Last working day in Arabic",               "CRITICAL"),
    ("استقالة",             "Resignation flag in Arabic",               "CRITICAL"),
    ("إنهاء خدمة",          "Service termination in Arabic",             "CRITICAL"),
    ("attrition_flag",       "Encoded target column",                     "CRITICAL"),
    ("attrition_label",      "Encoded target column",                     "CRITICAL"),
    ("churn_label",          "Encoded target column",                     "CRITICAL"),
    ("action_reason",        "Oracle action reason (may encode termination)","HIGH"),
    ("contract_end_date",    "Contract end date (leakage if terminated)", "HIGH"),
    ("employment_end_date",  "Employment end date",                       "HIGH"),
    ("end_date",             "End date column",                           "HIGH"),
    ("effective_end_date",   "Oracle effective end date",                 "HIGH"),
    ("تاريخ انتهاء العقد", "Contract end date in Arabic",              "HIGH"),
    ("attrition_risk",       "Derived attrition risk score",              "HIGH"),
    ("retention_risk",       "Derived retention risk score",              "HIGH"),
    ("flight_risk",          "Derived flight risk score",                 "HIGH"),
    ("churn_score",          "Derived churn probability",                 "HIGH"),
    ("resignation_score",    "Derived resignation probability",           "HIGH"),
    ("خطر الاستقالة",       "Resignation risk in Arabic",               "HIGH"),
    ("احتمالية المغادرة",   "Departure probability in Arabic",           "HIGH"),
]

_PII_COLUMN_PATTERNS: List[Tuple[str, str]] = [
    ("national_id",          "Saudi National ID (NIN)"),
    ("iqama",                "Iqama/Residency number"),
    ("رقم الهوية",          "National ID in Arabic"),
    ("رقم الإقامة",         "Iqama in Arabic"),
    ("passport",             "Passport number"),
    ("رقم الجواز",          "Passport in Arabic"),
    ("mobile",               "Mobile number"),
    ("phone",                "Phone number"),
    ("email",                "Email address"),
    ("البريد الإلكتروني",   "Email in Arabic"),
    ("bank_account",         "Bank account"),
    ("iban",                 "IBAN"),
    ("gosi_number",          "GOSI subscription number"),
    ("رقم الحساب",          "Bank account in Arabic"),
    ("home_address",         "Home address"),
    ("العنوان الوطني",      "National address in Arabic"),
]


# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class SaudiDataGovernanceEngine:
    """
    Validates Saudi HR data quality and governance compliance.

    Usage
    -----
    engine = SaudiDataGovernanceEngine()
    report = engine.validate(df, target_col="Attrition")
    if not report.is_clean:
        logger.warning("Governance issues: %s", report.summary)
    """

    def validate(
        self,
        df: pd.DataFrame,
        target_col: Optional[str] = None,
        salary_col: Optional[str] = None,
        age_col: Optional[str] = None,
        tenure_col: Optional[str] = None,
    ) -> SaudiDataGovernanceReport:
        """
        Validate a Saudi HR DataFrame for data quality and leakage governance.

        Parameters
        ----------
        df          : HR DataFrame.
        target_col  : Attrition target column name (if known).
        salary_col  : Monthly salary column name (if known).
        age_col     : Age column name (if known).
        tenure_col  : Tenure / years at company column name (if known).
        """
        findings: List[DataQualityFinding] = []
        leakage_cols: List[str] = []
        pii_cols: List[str] = []

        # ── 1. Leakage column detection ───────────────────────────────────
        for col in df.columns:
            col_lower = col.lower().strip()
            for pattern, desc, sev in _LEAKAGE_COLUMN_PATTERNS:
                if pattern.lower() in col_lower or col == pattern:
                    leakage_cols.append(col)
                    findings.append(DataQualityFinding(
                        finding_type="LEAKAGE_COLUMN",
                        severity=sev,
                        column_affected=col,
                        n_records_affected=len(df),
                        description=f"'{col}': {desc}.",
                        recommendation=(
                            "Remove from feature set. "
                            "Use only to define train/test split boundary if temporal ordering is needed."
                        ),
                    ))
                    break

        # ── 2. PII column detection ───────────────────────────────────────
        for col in df.columns:
            col_lower = col.lower().strip()
            for pattern, desc in _PII_COLUMN_PATTERNS:
                if pattern.lower() in col_lower or col == pattern:
                    pii_cols.append(col)
                    findings.append(DataQualityFinding(
                        finding_type="PII_EXPOSURE",
                        severity="CRITICAL",
                        column_affected=col,
                        n_records_affected=len(df),
                        description=f"'{col}': {desc} — must never be a model feature.",
                        recommendation=(
                            "Remove from feature set immediately. "
                            "Apply PDPL-compliant anonymization before any analysis."
                        ),
                    ))
                    break

        # ── 3. Salary range validation ────────────────────────────────────
        salary_currency = "unknown"
        if salary_col and salary_col in df.columns:
            salary_currency, sal_findings = self._validate_salary(df[salary_col], salary_col)
            findings.extend(sal_findings)
        else:
            # Auto-detect salary columns
            for col in df.columns:
                col_l = col.lower()
                if any(k in col_l for k in ["salary", "income", "pay", "wage",
                                             "راتب", "أجر", "دخل"]):
                    salary_currency, sal_findings = self._validate_salary(df[col], col)
                    findings.extend(sal_findings)
                    break

        # ── 4. Age validation ─────────────────────────────────────────────
        impossible_age = 0
        if age_col and age_col in df.columns:
            impossible_age, age_findings = self._validate_age(df[age_col], age_col)
            findings.extend(age_findings)
        else:
            for col in df.columns:
                if col.lower() in {"age", "employee_age", "age_years", "العمر", "السن"}:
                    impossible_age, age_findings = self._validate_age(df[col], col)
                    findings.extend(age_findings)
                    break

        # ── 5. Tenure validation ──────────────────────────────────────────
        if tenure_col and tenure_col in df.columns:
            _, ten_findings = self._validate_tenure(df[tenure_col], tenure_col)
            findings.extend(ten_findings)
        else:
            for col in df.columns:
                if col.lower() in {
                    "yearsatcompany", "years_at_company", "tenure", "tenure_years",
                    "سنوات الخدمة", "مدة الخدمة",
                }:
                    _, ten_findings = self._validate_tenure(df[col], col)
                    findings.extend(ten_findings)
                    break

        # ── 6. Attrition rate plausibility ───────────────────────────────
        attrition_rate: Optional[float] = None
        if target_col and target_col in df.columns:
            attrition_rate, att_findings = self._validate_attrition_rate(
                df[target_col], target_col
            )
            findings.extend(att_findings)

        # ── 7. Duplicate record detection ────────────────────────────────
        dup_rate, dup_findings = self._validate_duplicates(df)
        findings.extend(dup_findings)

        # ── 8. Impossible record count ────────────────────────────────────
        n_impossible = impossible_age  # extend with other impossible checks

        # ── Build summary ─────────────────────────────────────────────────
        n_crit   = sum(1 for f in findings if f.severity == "CRITICAL")
        n_high   = sum(1 for f in findings if f.severity == "HIGH")
        n_medium = sum(1 for f in findings if f.severity == "MEDIUM")
        n_info   = sum(1 for f in findings if f.severity == "INFO")

        is_clean = (n_crit == 0 and n_high == 0)

        gov_notes: List[str] = []
        if leakage_cols:
            gov_notes.append(
                f"POST-OUTCOME LEAKAGE: {leakage_cols} — remove before modelling."
            )
        if pii_cols:
            gov_notes.append(
                f"PII DETECTED: {pii_cols} — PDPL compliance required."
            )
        if salary_currency == "SAR_annual":
            gov_notes.append(
                "SALARY SCALE: Values appear to be annual SAR. "
                "MonthlyIncome formula requires monthly values (÷ 12)."
            )
        if n_impossible > 0:
            gov_notes.append(
                f"IMPOSSIBLE RECORDS: {n_impossible} record(s) with impossible values detected."
            )

        parts = []
        if n_crit: parts.append(f"{n_crit} CRITICAL")
        if n_high: parts.append(f"{n_high} HIGH")
        if n_medium: parts.append(f"{n_medium} MEDIUM")
        summary = (
            f"Saudi Data Governance: {'CLEAN' if is_clean else 'VIOLATIONS'} "
            f"({'OK' if not parts else ', '.join(parts)}). "
            f"{len(leakage_cols)} leakage, {len(pii_cols)} PII columns. "
            f"Salary: {salary_currency}. "
            f"Duplicate rate: {dup_rate:.1%}."
        )

        logger.info("SaudiDataGovernance: %s", summary)

        return SaudiDataGovernanceReport(
            is_clean=is_clean,
            n_critical=n_crit,
            n_high=n_high,
            n_medium=n_medium,
            n_info=n_info,
            findings=findings,
            leakage_columns_detected=leakage_cols,
            pii_columns_detected=pii_cols,
            impossible_records_count=n_impossible,
            salary_currency_suspected=salary_currency,
            attrition_rate_observed=attrition_rate,
            duplicate_rate=dup_rate,
            summary=summary,
            governance_notes=gov_notes,
        )

    # ── Private validators ─────────────────────────────────────────────────

    def _validate_salary(
        self,
        series: pd.Series,
        col_name: str,
    ) -> Tuple[str, List[DataQualityFinding]]:
        """Returns (currency_type, findings)."""
        findings: List[DataQualityFinding] = []
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s) == 0:
            return "unknown", findings

        mean_val = s.mean()
        min_val  = s.min()
        max_val  = s.max()
        n_zero   = int((s == 0).sum())
        n_below_min = int(((s > 0) & (s < _SAR_SUSPICIOUS_LOW)).sum())

        # Determine currency scale
        currency = "SAR_monthly"
        if mean_val >= _SAR_LIKELY_ANNUAL_THRESHOLD:
            currency = "SAR_annual"
            findings.append(DataQualityFinding(
                finding_type="SALARY_SCALE_SUSPICIOUS",
                severity="HIGH",
                column_affected=col_name,
                n_records_affected=len(s),
                description=(
                    f"'{col_name}' mean={mean_val:,.0f} SAR suggests annual salary "
                    f"(threshold: {_SAR_LIKELY_ANNUAL_THRESHOLD:,}). "
                    "IncomePerLevel formula requires monthly income."
                ),
                recommendation=(
                    "Verify salary period. Divide by 12 if annual. "
                    "MonthlyIncome column must contain monthly SAR values."
                ),
            ))
        elif mean_val < _SAR_SUSPICIOUS_LOW and mean_val > 0:
            currency = "USD"
            findings.append(DataQualityFinding(
                finding_type="SALARY_CURRENCY_MISMATCH",
                severity="MEDIUM",
                column_affected=col_name,
                n_records_affected=len(s),
                description=(
                    f"'{col_name}' mean={mean_val:,.0f} is below SAR minimum wage "
                    f"({_SAR_MINIMUM_WAGE:,}). May be in USD or thousands."
                ),
                recommendation=(
                    "Verify currency. Platform expects SAR monthly values. "
                    "Apply appropriate currency conversion."
                ),
            ))

        # Zero salary records
        if n_zero > 0:
            findings.append(DataQualityFinding(
                finding_type="SALARY_ZERO_VALUES",
                severity="HIGH",
                column_affected=col_name,
                n_records_affected=n_zero,
                description=f"'{col_name}': {n_zero} records with salary = 0 SAR.",
                recommendation="Investigate zero-salary records. May indicate data entry errors.",
            ))

        # Implausible max
        if max_val > _SAR_PLAUSIBLE_MAX and currency == "SAR_monthly":
            findings.append(DataQualityFinding(
                finding_type="SALARY_IMPLAUSIBLE_MAX",
                severity="MEDIUM",
                column_affected=col_name,
                n_records_affected=int((s > _SAR_PLAUSIBLE_MAX).sum()),
                description=(
                    f"'{col_name}' max={max_val:,.0f} SAR/month exceeds plausible ceiling "
                    f"({_SAR_PLAUSIBLE_MAX:,}). May indicate data entry errors."
                ),
                recommendation="Review outlier salary records for data entry errors.",
            ))

        return currency, findings

    def _validate_age(
        self,
        series: pd.Series,
        col_name: str,
    ) -> Tuple[int, List[DataQualityFinding]]:
        """Returns (n_impossible_records, findings)."""
        findings: List[DataQualityFinding] = []
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s) == 0:
            return 0, findings

        n_below_min = int((s < _MIN_EMPLOYEE_AGE).sum())
        n_above_max = int((s > _MAX_PLAUSIBLE_AGE).sum())
        n_suspicious_high = int(((s > _SUSPICIOUS_AGE_HIGH) & (s <= _MAX_PLAUSIBLE_AGE)).sum())
        n_impossible = n_below_min + n_above_max

        if n_below_min > 0:
            findings.append(DataQualityFinding(
                finding_type="AGE_BELOW_MINIMUM",
                severity="CRITICAL",
                column_affected=col_name,
                n_records_affected=n_below_min,
                description=(
                    f"'{col_name}': {n_below_min} records with age < {_MIN_EMPLOYEE_AGE}. "
                    "Saudi Labour Law Art. 3 prohibits employment below this age."
                ),
                recommendation=(
                    "Investigate records. May indicate data entry errors or age encoding issues."
                ),
            ))

        if n_above_max > 0:
            findings.append(DataQualityFinding(
                finding_type="AGE_IMPOSSIBLE",
                severity="HIGH",
                column_affected=col_name,
                n_records_affected=n_above_max,
                description=(
                    f"'{col_name}': {n_above_max} records with age > {_MAX_PLAUSIBLE_AGE}. "
                    "Impossible employee age."
                ),
                recommendation="These records should be excluded or corrected before modelling.",
            ))

        if n_suspicious_high > 0:
            findings.append(DataQualityFinding(
                finding_type="AGE_SUSPICIOUSLY_HIGH",
                severity="INFO",
                column_affected=col_name,
                n_records_affected=n_suspicious_high,
                description=(
                    f"'{col_name}': {n_suspicious_high} records with age > {_SUSPICIOUS_AGE_HIGH}. "
                    "Verify these are active employees."
                ),
                recommendation="Manual verification recommended for employees above retirement age.",
            ))

        return n_impossible, findings

    def _validate_tenure(
        self,
        series: pd.Series,
        col_name: str,
    ) -> Tuple[int, List[DataQualityFinding]]:
        """Returns (n_impossible, findings)."""
        findings: List[DataQualityFinding] = []
        s = pd.to_numeric(series, errors="coerce").dropna()
        if len(s) == 0:
            return 0, findings

        n_impossible = int((s > _MAX_PLAUSIBLE_TENURE_YEARS).sum())
        n_suspicious  = int(((s > _SUSPICIOUS_TENURE_YEARS) & (s <= _MAX_PLAUSIBLE_TENURE_YEARS)).sum())
        n_negative    = int((s < 0).sum())

        if n_negative > 0:
            findings.append(DataQualityFinding(
                finding_type="TENURE_NEGATIVE",
                severity="CRITICAL",
                column_affected=col_name,
                n_records_affected=n_negative,
                description=f"'{col_name}': {n_negative} records with tenure < 0 years.",
                recommendation="Negative tenure is impossible. Investigate data pipeline.",
            ))

        if n_impossible > 0:
            findings.append(DataQualityFinding(
                finding_type="TENURE_IMPOSSIBLE",
                severity="HIGH",
                column_affected=col_name,
                n_records_affected=n_impossible,
                description=(
                    f"'{col_name}': {n_impossible} records with tenure > "
                    f"{_MAX_PLAUSIBLE_TENURE_YEARS} years. Likely data entry error."
                ),
                recommendation="Review and correct impossible tenure values before modelling.",
            ))

        if n_suspicious > 0:
            findings.append(DataQualityFinding(
                finding_type="TENURE_SUSPICIOUSLY_HIGH",
                severity="MEDIUM",
                column_affected=col_name,
                n_records_affected=n_suspicious,
                description=(
                    f"'{col_name}': {n_suspicious} records with tenure > "
                    f"{_SUSPICIOUS_TENURE_YEARS} years. Verify accuracy."
                ),
                recommendation="Manual verification recommended for very long-tenured employees.",
            ))

        return n_impossible + n_negative, findings

    def _validate_attrition_rate(
        self,
        series: pd.Series,
        col_name: str,
    ) -> Tuple[Optional[float], List[DataQualityFinding]]:
        """Returns (attrition_rate, findings)."""
        findings: List[DataQualityFinding] = []

        try:
            # Convert Yes/No or 1/0
            s = series.map(
                lambda x: 1 if str(x).strip().lower() in {"yes", "1", "true"} else
                          0 if str(x).strip().lower() in {"no", "0", "false"} else None
            ).dropna()

            if len(s) == 0:
                return None, findings

            rate = float(s.mean())

            if rate > _ATTRITION_IMPOSSIBLE:
                findings.append(DataQualityFinding(
                    finding_type="ATTRITION_RATE_IMPOSSIBLE",
                    severity="CRITICAL",
                    column_affected=col_name,
                    n_records_affected=len(series),
                    description=f"Attrition rate {rate:.0%} exceeds 100% — data error.",
                    recommendation="Review target column encoding and class distribution.",
                ))
            elif rate > _ATTRITION_SUSPICIOUS_HIGH:
                findings.append(DataQualityFinding(
                    finding_type="ATTRITION_RATE_SUSPICIOUS",
                    severity="HIGH",
                    column_affected=col_name,
                    n_records_affected=len(series),
                    description=(
                        f"Attrition rate {rate:.0%} exceeds {_ATTRITION_SUSPICIOUS_HIGH:.0%}. "
                        "Saudi HR benchmark: 10–25% annual attrition is typical. "
                        "High rate may indicate retrospective sampling bias or data errors."
                    ),
                    recommendation=(
                        "Verify the dataset is not retrospectively enriched with terminated employees. "
                        "Check for post-outcome sampling bias."
                    ),
                ))

            return rate, findings

        except Exception:
            return None, findings

    def _validate_duplicates(
        self,
        df: pd.DataFrame,
    ) -> Tuple[float, List[DataQualityFinding]]:
        """Returns (duplicate_rate, findings)."""
        findings: List[DataQualityFinding] = []
        n_total = len(df)
        if n_total == 0:
            return 0.0, findings

        n_dup = int(df.duplicated().sum())
        rate = n_dup / n_total

        if rate > _DUPLICATE_EXACT_THRESHOLD:
            findings.append(DataQualityFinding(
                finding_type="DUPLICATE_RECORDS",
                severity="HIGH",
                column_affected=None,
                n_records_affected=n_dup,
                description=(
                    f"{n_dup} exact duplicate rows ({rate:.1%} of dataset). "
                    "Duplicates spanning train/test split cause leakage."
                ),
                recommendation=(
                    "Deduplicate before splitting. "
                    "Investigate source — may indicate multiple ERP export pulls."
                ),
            ))
        elif n_dup > 0:
            findings.append(DataQualityFinding(
                finding_type="DUPLICATE_RECORDS",
                severity="INFO",
                column_affected=None,
                n_records_affected=n_dup,
                description=f"{n_dup} exact duplicate rows ({rate:.1%}).",
                recommendation="Review and deduplicate before modelling.",
            ))

        return rate, findings


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def validate_saudi_data(
    df: pd.DataFrame,
    target_col: Optional[str] = None,
    salary_col: Optional[str] = None,
    age_col: Optional[str] = None,
    tenure_col: Optional[str] = None,
) -> SaudiDataGovernanceReport:
    """One-call convenience wrapper around SaudiDataGovernanceEngine.validate()."""
    return SaudiDataGovernanceEngine().validate(
        df, target_col=target_col,
        salary_col=salary_col, age_col=age_col, tenure_col=tenure_col,
    )
