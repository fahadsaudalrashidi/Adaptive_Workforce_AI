# -*- coding: utf-8 -*-
"""
Saudi Schema Intelligence Engine
==================================

Enterprise-grade schema understanding for Saudi HR datasets from heterogeneous
sources: Arabic HR systems, bilingual datasets, SAP SuccessFactors exports,
Oracle HRMS exports, Mudad/Qiwa government platform exports, and custom
Saudi HR spreadsheets.

Responsibilities:
  - Fingerprint the likely ERP/source system from column naming patterns
  - Normalize ERP-specific column names to platform-standard names
  - Detect bilingual (Arabic/English) column structures
  - Assess schema completeness against required construct inputs
  - Return schema-level metadata that downstream mapping uses

Does NOT:
  - Compute any psychological constructs
  - Train or modify models
  - Make governance decisions (that is ModelInputContract's role)
  - Modify the DataFrame
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# ERP SYSTEM FINGERPRINTS
# ─────────────────────────────────────────────────────────────────────────────

ERP_UNKNOWN             = "UNKNOWN"
ERP_IBM_HR              = "IBM_HR_BENCHMARK"       # IBM HR Analytics dataset
ERP_SAP_SF              = "SAP_SUCCESSFACTORS"
ERP_ORACLE_HRMS         = "ORACLE_HRMS"
ERP_MUDAD               = "MUDAD_PLATFORM"         # Saudi payroll platform
ERP_QIWA                = "QIWA_PLATFORM"          # Saudi labor market platform
ERP_GENERIC_SAUDI       = "GENERIC_SAUDI_HR"       # Generic Arabic-dominant spreadsheet
ERP_GENERIC_BILINGUAL   = "GENERIC_BILINGUAL_HR"   # Mixed Arabic-English spreadsheet
ERP_GENERIC_ENGLISH     = "GENERIC_ENGLISH_HR"     # English-only non-IBM spreadsheet


# ─────────────────────────────────────────────────────────────────────────────
# ERP COLUMN SIGNATURE PATTERNS
# ─────────────────────────────────────────────────────────────────────────────

# Columns that are diagnostic of specific ERP systems
_IBM_SIGNATURE_COLUMNS: Set[str] = {
    "attrition", "businesstravel", "dailyrate", "department",
    "distancefromhome", "education", "educationfield", "employeecount",
    "employeenumber", "environmentsatisfaction", "gender", "hourlyrate",
    "jobinvolvement", "joblevel", "jobrole", "jobsatisfaction",
    "maritalstatus", "monthlyincome", "monthlyrate", "numcompaniesworked",
    "over18", "overtime", "percentsalaryhike", "performancerating",
    "relationshipsatisfaction", "standardhours", "stockoptionlevel",
    "totalworkingyears", "trainingtimeslastyear", "worklifebalance",
    "yearsatcompany", "yearsincurrentrole", "yearssincelastpromotion",
    "yearswithcurrmanager",
}

_SAP_SF_SIGNATURE_PATTERNS: List[str] = [
    "empjob", "empemployment", "emppaycompensation",
    "empjobrelationship", "empglobalassignment",
    "cust_", "custom_", "ext_", "hris_",
    "position_id", "position_title", "personnel_number",
    "cost_center", "business_unit_id",
    "hire_date_sf", "termination_date_sf",
]

_ORACLE_SIGNATURE_PATTERNS: List[str] = [
    "employee_number", "assignment_status", "organization_id",
    "grade_id", "step_id", "payroll_id", "pay_basis",
    "person_id", "assignment_id", "element_type",
    "effective_start_date", "effective_end_date",
    "action_type", "action_reason",
    "location_code", "job_code", "position_code",
]

_MUDAD_SIGNATURE_PATTERNS: List[str] = [
    "iqama_number", "iqama_no", "iqama",
    "national_id", "national_address",
    "mudad_id", "payroll_month", "payment_date",
    "basic_salary_sar", "housing_allowance", "transport_allowance",
    "gosi_contribution", "gosi_number",
    "establishment_number", "cr_number",
    "nationality_code", "nationality_name",
    "visa_status", "visa_expiry",
    "رقم الإقامة", "رقم الهوية", "الراتب الأساسي",
    "بدل سكن", "بدل مواصلات", "الجنسية",
]

_QIWA_SIGNATURE_PATTERNS: List[str] = [
    "qiwa_id", "nitaqat", "nitaqat_band", "saudization_pct",
    "labor_office_number", "mol_number", "mol_id",
    "contract_type", "contract_end_date",
    "work_permit", "work_permit_expiry",
    "replacement_percentage", "saudis_count", "expats_count",
    "activity_type", "economic_activity",
    "نطاقات", "تأشيرة العمل", "رقم مكتب العمل",
    "نسبة السعودة", "نوع العقد",
]


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZATION DICTIONARIES (ERP → platform-standard name)
# ─────────────────────────────────────────────────────────────────────────────

# SAP SuccessFactors → standard
_SAP_TO_STANDARD: Dict[str, str] = {
    "empjoblevels":              "JobLevel",
    "empjob_level":              "JobLevel",
    "emppaycompensation_salary": "MonthlyIncome",
    "annual_salary":             "MonthlyIncome",      # note: will need /12 flag
    "emp_hiredate":              "HireDate",
    "position_title":            "JobTitle",
    "cost_center_name":          "Department",
    "business_unit":             "Department",
    "performance_form_rating":   "PerformanceRating",
    "last_performance_rating":   "PerformanceRating",
    "custom_overtime":           "OverTime",
    "ext_overtime":              "OverTime",
    "hris_yearsatcompany":       "YearsAtCompany",
    "time_with_company":         "YearsAtCompany",
    "emp_tenure_years":          "YearsAtCompany",
}

# Oracle HRMS → standard
_ORACLE_TO_STANDARD: Dict[str, str] = {
    "employee_number":           "EmployeeID",
    "assignment_status_type":    "EmploymentStatus",
    "grade_name":                "JobLevel",
    "job_name":                  "JobTitle",
    "organization_name":         "Department",
    "location_name":             "Location",
    "action_type":               "EmploymentAction",      # leakage risk if =TERMINATION
    "action_reason":             "TerminationReason",     # ALWAYS leakage risk
    "effective_start_date":      "EffectiveStartDate",
    "effective_end_date":        "EffectiveEndDate",      # leakage risk
    "pay_annualized_salary":     "AnnualSalary",
    "element_value":             "SalaryElement",
    "step_name":                 "SalaryStep",
}

# Mudad → standard
_MUDAD_TO_STANDARD: Dict[str, str] = {
    "basic_salary_sar":          "MonthlyIncome",
    "الراتب الأساسي":           "MonthlyIncome",
    "بدل سكن":                  "HousingAllowance",
    "بدل مواصلات":              "TransportAllowance",
    "إجمالي الراتب":            "TotalSalary",
    "الجنسية":                  "Nationality",
    "رقم الهوية":               "NationalID",             # PII — never a model feature
    "رقم الإقامة":              "IqamaNumber",            # PII
    "تاريخ الالتحاق":           "HireDate",
    "تاريخ انتهاء العقد":       "ContractEndDate",        # potential leakage
    "سبب الخروج":               "ExitReason",             # ALWAYS leakage
    "حالة الموظف":              "EmploymentStatus",
}

# Qiwa → standard
_QIWA_TO_STANDARD: Dict[str, str] = {
    "nitaqat_band":              "NitaqatBand",
    "saudization_pct":           "SaudizationPercentage",
    "contract_type":             "ContractType",
    "contract_end_date":         "ContractEndDate",       # potential leakage
    "work_permit_expiry":        "WorkPermitExpiry",
    "نسبة السعودة":              "SaudizationPercentage",
    "نوع العقد":                 "ContractType",
    "تاريخ انتهاء العقد":       "ContractEndDate",
}


# ─────────────────────────────────────────────────────────────────────────────
# COLUMNS WITH INHERENT LEAKAGE RISK IN SAUDI ERP EXPORTS
# ─────────────────────────────────────────────────────────────────────────────

# These columns, when found in any ERP export, are ALWAYS leakage risks
_SAUDI_ERP_LEAKAGE_COLUMNS: Dict[str, str] = {
    "action_type":               "Oracle HRMS action (TERMINATION = post-outcome)",
    "action_reason":             "Post-outcome termination reason",
    "effective_end_date":        "Assignment end date — post-outcome",
    "contract_end_date":         "Contract end date — post-outcome if terminated",
    "تاريخ انتهاء العقد":       "Contract end date in Arabic — post-outcome",
    "exit_reason":               "Exit reason — post-outcome",
    "sbb_reason":                "Separation reason (Saudi Business Bureau style)",
    "separation_reason":         "Post-outcome separation reason",
    "termination_date":          "Post-outcome termination date",
    "تاريخ الخروج":              "Exit date in Arabic",
    "سبب الخروج":               "Exit reason in Arabic",
    "last_working_day":          "Last day — post-outcome",
    "آخر يوم عمل":              "Last working day in Arabic",
    "resignation_date":          "Resignation date — post-outcome",
    "employment_end_date":       "Employment end date",
    "attrition_flag":            "Derived target-adjacent flag",
    "attrition_label":           "Encoded target column",
    "churn_label":               "Encoded target column",
    "استقالة":                   "Resignation indicator in Arabic",
    "إنهاء خدمة":               "Service termination in Arabic",
}

# Columns that are PII and must never be model features
_PII_COLUMNS: Dict[str, str] = {
    "national_id":               "Saudi National ID (NIN) — PII",
    "iqama_number":              "Iqama/Residency number — PII",
    "رقم الهوية":               "Saudi National ID in Arabic — PII",
    "رقم الإقامة":              "Iqama in Arabic — PII",
    "iqama_no":                  "Iqama number variant — PII",
    "passport_number":           "Passport number — PII",
    "رقم الجواز":               "Passport number in Arabic — PII",
    "mobile_number":             "Mobile phone number — PII",
    "email":                     "Email address — PII",
    "email_address":             "Email address — PII",
    "البريد الإلكتروني":        "Email in Arabic — PII",
    "bank_account":              "Bank account number — PII",
    "iban":                      "IBAN — PII",
    "رقم الحساب":               "Bank account in Arabic — PII",
    "home_address":              "Home address — PII",
    "العنوان الوطني":           "National address — PII",
    "gosi_number":               "GOSI subscription number — PII",
}


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColumnSchemaRecord:
    """Schema metadata for one column."""
    original_name: str
    normalized_name: Optional[str]          # ERP-normalized platform-standard name
    language: str                           # english / arabic / mixed / unknown
    erp_source: str                         # which ERP system likely produced this
    is_leakage_risk: bool
    is_pii: bool
    leakage_reason: Optional[str]
    pii_reason: Optional[str]
    normalization_applied: bool
    governance_notes: List[str] = field(default_factory=list)


@dataclass
class SchemaIntelligenceReport:
    """Full schema intelligence output for a dataset."""
    erp_system_detected: str
    erp_confidence: str                     # HIGH / MEDIUM / LOW / NONE
    n_columns: int
    n_arabic: int
    n_english: int
    n_mixed: int
    n_leakage_risk: int
    n_pii: int
    n_normalized: int
    language_profile: str                   # arabic_dominant / english_dominant / bilingual / unknown
    column_records: List[ColumnSchemaRecord]
    leakage_columns: List[str]
    pii_columns: List[str]
    normalized_column_map: Dict[str, str]   # original → standard name
    missing_required_constructs: List[str]  # which IBM HR constructs are absent
    schema_completeness_score: float        # 0.0–1.0 (fraction of IBM constructs present)
    governance_notes: List[str]
    summary: str


# ─────────────────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────────────────

# IBM HR columns required for the 7 theory constructs
_REQUIRED_IBM_CONSTRUCTS: Dict[str, List[str]] = {
    "SatisfactionIndex": [
        "JobSatisfaction", "EnvironmentSatisfaction",
        "RelationshipSatisfaction", "WorkLifeBalance",
    ],
    "BurnoutRisk":        ["OverTime", "WorkLifeBalance"],
    "EngagementScore":    ["JobInvolvement", "JobSatisfaction"],
    "TenureRatio":        ["YearsAtCompany", "TotalWorkingYears"],
    "IncomePerLevel":     ["MonthlyIncome", "JobLevel"],
    "CareerProgression":  ["JobLevel", "YearsAtCompany"],
    "SalaryGrowth":       ["PercentSalaryHike", "PerformanceRating"],
}

_ALL_IBM_REQUIRED: Set[str] = {
    col for cols in _REQUIRED_IBM_CONSTRUCTS.values() for col in cols
}


class SaudiSchemaIntelligenceEngine:
    """
    Fingerprints Saudi HR dataset schema, normalizes ERP column names,
    flags leakage and PII risks, and assesses theory construct completeness.

    Usage
    -----
    engine = SaudiSchemaIntelligenceEngine()
    report = engine.analyse(df)
    """

    def analyse(
        self,
        df: pd.DataFrame,
    ) -> SchemaIntelligenceReport:
        """
        Analyse the schema of a DataFrame.

        Parameters
        ----------
        df : The DataFrame whose columns will be analysed.

        Returns
        -------
        SchemaIntelligenceReport with full schema metadata.
        """
        columns = list(df.columns)
        col_lower_map = {c: c.lower().strip() for c in columns}

        # ── Step 1: language profile ──────────────────────────────────────
        n_arabic = sum(1 for c in columns if _has_arabic(c))
        n_english = sum(1 for c in columns if _is_latin_dominant(c))
        n_mixed = sum(1 for c in columns if _has_arabic(c) and _is_latin_dominant(c))

        if n_arabic > 0 and n_english > 0:
            lang_profile = "bilingual"
        elif n_arabic > len(columns) * 0.5:
            lang_profile = "arabic_dominant"
        elif n_english > len(columns) * 0.5:
            lang_profile = "english_dominant"
        else:
            lang_profile = "unknown"

        # ── Step 2: ERP fingerprint ───────────────────────────────────────
        erp, erp_confidence = self._fingerprint_erp(columns, col_lower_map, df)

        # ── Step 3: column-level analysis ────────────────────────────────
        records: List[ColumnSchemaRecord] = []
        norm_map: Dict[str, str] = {}
        leakage_cols: List[str] = []
        pii_cols: List[str] = []

        for col in columns:
            col_l = col.lower().strip()

            # Leakage check
            is_leakage = False
            leakage_reason: Optional[str] = None
            for pattern, reason in _SAUDI_ERP_LEAKAGE_COLUMNS.items():
                if pattern.lower() in col_l or col == pattern:
                    is_leakage = True
                    leakage_reason = reason
                    break

            # PII check
            is_pii = False
            pii_reason: Optional[str] = None
            for pattern, reason in _PII_COLUMNS.items():
                if pattern.lower() in col_l or col == pattern:
                    is_pii = True
                    pii_reason = reason
                    break

            # Normalization
            normalized = self._normalize_column(col, col_l, erp)
            norm_applied = normalized is not None and normalized != col
            if norm_applied:
                norm_map[col] = normalized

            # Language
            lang = _detect_column_language(col)

            # Governance notes
            gov_notes: List[str] = []
            if is_leakage:
                gov_notes.append(f"LEAKAGE RISK: {leakage_reason}")
            if is_pii:
                gov_notes.append(f"PII: {pii_reason} — never use as model feature")
            if norm_applied:
                gov_notes.append(f"NORMALIZED: '{col}' → '{normalized}'")

            records.append(ColumnSchemaRecord(
                original_name=col,
                normalized_name=normalized,
                language=lang,
                erp_source=erp,
                is_leakage_risk=is_leakage,
                is_pii=is_pii,
                leakage_reason=leakage_reason,
                pii_reason=pii_reason,
                normalization_applied=norm_applied,
                governance_notes=gov_notes,
            ))

            if is_leakage:
                leakage_cols.append(col)
            if is_pii:
                pii_cols.append(col)

        # ── Step 4: schema completeness against IBM required constructs ───
        # Compare case-insensitively (camelCase IBM names vs any casing in dataset)
        present_cols_lower = {c.lower() for c in columns}
        # Also include any normalized (standard) names from ERP mapping
        present_cols_lower |= {v.lower() for v in norm_map.values()}
        missing_required: List[str] = []
        for ibm_col in _ALL_IBM_REQUIRED:
            if ibm_col.lower() not in present_cols_lower:
                missing_required.append(ibm_col)

        completeness = 1.0 - (len(missing_required) / max(len(_ALL_IBM_REQUIRED), 1))

        # ── Step 5: construct availability check ─────────────────────────
        gov_notes: List[str] = []
        if leakage_cols:
            gov_notes.append(
                f"LEAKAGE: {len(leakage_cols)} column(s) identified as post-outcome "
                f"or target-adjacent: {leakage_cols[:5]}"
            )
        if pii_cols:
            gov_notes.append(
                f"PII: {len(pii_cols)} personally-identifiable column(s) detected. "
                "These must never be model features."
            )
        if missing_required:
            gov_notes.append(
                f"SCHEMA INCOMPLETE: {len(missing_required)} IBM construct column(s) absent. "
                f"Missing: {missing_required[:6]}. "
                "Some theory constructs cannot be computed."
            )
        if lang_profile == "arabic_dominant":
            gov_notes.append(
                "ARABIC DOMINANT: Most columns are in Arabic. "
                "Theory-aware column mapper will attempt Arabic synonym matching."
            )
        if erp == ERP_ORACLE_HRMS:
            gov_notes.append(
                "ORACLE HRMS: action_type and action_reason columns are critical leakage "
                "risks — they encode termination events post-outcome."
            )
        if erp == ERP_MUDAD:
            gov_notes.append(
                "MUDAD EXPORT: Payroll-focused schema. Satisfaction and engagement "
                "constructs unlikely to be computable. Structural constructs (TenureRatio, "
                "IncomePerLevel, CareerProgression) may be available."
            )
        if erp == ERP_QIWA:
            gov_notes.append(
                "QIWA EXPORT: Contains Saudization/Nitaqat fields which are "
                "organizational metadata, not individual psychological predictors. "
                "Construct activation will be limited."
            )

        summary = (
            f"Schema: {erp} ({erp_confidence} confidence). "
            f"Language: {lang_profile}. "
            f"{len(columns)} columns: {len(leakage_cols)} leakage, "
            f"{len(pii_cols)} PII, {len(norm_map)} normalized. "
            f"Completeness: {completeness:.0%} of IBM constructs."
        )

        logger.info("SaudiSchemaIntelligence: %s", summary)

        return SchemaIntelligenceReport(
            erp_system_detected=erp,
            erp_confidence=erp_confidence,
            n_columns=len(columns),
            n_arabic=n_arabic,
            n_english=n_english,
            n_mixed=n_mixed,
            n_leakage_risk=len(leakage_cols),
            n_pii=len(pii_cols),
            n_normalized=len(norm_map),
            language_profile=lang_profile,
            column_records=records,
            leakage_columns=leakage_cols,
            pii_columns=pii_cols,
            normalized_column_map=norm_map,
            missing_required_constructs=missing_required,
            schema_completeness_score=round(completeness, 3),
            governance_notes=gov_notes,
            summary=summary,
        )

    # ── Private helpers ────────────────────────────────────────────────────

    def _fingerprint_erp(
        self,
        columns: List[str],
        col_lower_map: Dict[str, str],
        df: pd.DataFrame,
    ) -> Tuple[str, str]:
        """Detect which ERP system produced this dataset."""
        lowers = set(col_lower_map.values())

        # IBM HR: high-confidence exact column set match
        ibm_hits = len(lowers & {c.lower() for c in _IBM_SIGNATURE_COLUMNS})
        if ibm_hits >= 10:
            return ERP_IBM_HR, "HIGH"
        if ibm_hits >= 5:
            return ERP_IBM_HR, "MEDIUM"

        # SAP SuccessFactors
        sap_hits = sum(
            1 for c in lowers
            if any(pat in c for pat in _SAP_SF_SIGNATURE_PATTERNS)
        )
        if sap_hits >= 4:
            return ERP_SAP_SF, "HIGH"
        if sap_hits >= 2:
            return ERP_SAP_SF, "MEDIUM"

        # Oracle HRMS
        oracle_hits = sum(
            1 for c in lowers
            if any(pat in c for pat in _ORACLE_SIGNATURE_PATTERNS)
        )
        if oracle_hits >= 4:
            return ERP_ORACLE_HRMS, "HIGH"
        if oracle_hits >= 2:
            return ERP_ORACLE_HRMS, "MEDIUM"

        # Mudad
        mudad_hits = sum(
            1 for c in list(lowers) + columns  # check originals for Arabic
            if any(pat.lower() in c.lower() for pat in _MUDAD_SIGNATURE_PATTERNS)
        )
        if mudad_hits >= 3:
            return ERP_MUDAD, "HIGH"
        if mudad_hits >= 1:
            return ERP_MUDAD, "LOW"

        # Qiwa
        qiwa_hits = sum(
            1 for c in list(lowers) + columns
            if any(pat.lower() in c.lower() for pat in _QIWA_SIGNATURE_PATTERNS)
        )
        if qiwa_hits >= 3:
            return ERP_QIWA, "HIGH"
        if qiwa_hits >= 1:
            return ERP_QIWA, "LOW"

        # Language-based fallback
        n_arabic = sum(1 for c in columns if _has_arabic(c))
        n_latin = sum(1 for c in columns if _is_latin_dominant(c))

        if n_arabic > 0 and n_latin > 0:
            return ERP_GENERIC_BILINGUAL, "NONE"
        if n_arabic > n_latin:
            return ERP_GENERIC_SAUDI, "NONE"
        return ERP_GENERIC_ENGLISH, "NONE"

    def _normalize_column(
        self,
        col: str,
        col_lower: str,
        erp: str,
    ) -> Optional[str]:
        """Return platform-standard name for known ERP columns, or None."""
        # Check ERP-specific dictionaries
        if erp == ERP_SAP_SF:
            for pat, std in _SAP_TO_STANDARD.items():
                if pat in col_lower:
                    return std
        elif erp == ERP_ORACLE_HRMS:
            for pat, std in _ORACLE_TO_STANDARD.items():
                if pat == col_lower or pat in col_lower:
                    return std
        elif erp == ERP_MUDAD:
            for pat, std in _MUDAD_TO_STANDARD.items():
                if pat.lower() == col_lower or pat == col:
                    return std
        elif erp == ERP_QIWA:
            for pat, std in _QIWA_TO_STANDARD.items():
                if pat.lower() == col_lower or pat == col:
                    return std

        # IBM HR: identity (already standard)
        if erp == ERP_IBM_HR:
            return col  # IBM columns ARE the standard

        return None


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _has_arabic(text: str) -> bool:
    return any("؀" <= c <= "ۿ" for c in text)


def _is_latin_dominant(text: str) -> bool:
    return sum(1 for c in text if c.isascii() and c.isalpha()) > 0


def _detect_column_language(col: str) -> str:
    has_ar = _has_arabic(col)
    has_lat = _is_latin_dominant(col)
    if has_ar and has_lat:
        return "mixed"
    if has_ar:
        return "arabic"
    if has_lat:
        return "english"
    return "unknown"


def _normalise_col(name: str) -> str:
    """Lowercase + split camelCase + collapse separators."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    return re.sub(r"[\s\-./]+", "_", s.lower().strip()).strip("_")


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def analyse_schema(df: pd.DataFrame) -> SchemaIntelligenceReport:
    """One-call convenience wrapper around SaudiSchemaIntelligenceEngine.analyse()."""
    return SaudiSchemaIntelligenceEngine().analyse(df)
