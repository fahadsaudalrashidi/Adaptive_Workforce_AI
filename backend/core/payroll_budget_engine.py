"""
Payroll Budget — Planned vs. Actual — Phase 37.

Extends this session's Overtime Cost Intelligence concept (real overtime
spend vs. risk) to full payroll: real actual headcount and payroll cost per
department, computed from the SAME uploaded employee data used throughout
this session, compared against a user-supplied PLANNED/budgeted figure per
department.

**Input design decision — manual entry per department, not a second
uploaded planning file.** The brief left this as an explicit "your call."
A second uploaded file (Department + PlannedHeadcount + PlannedAvgSalary
columns) would force this module to fuzzy-match planning-file department
names against this module's own normalized department names from the
ACTUAL data — the exact kind of silent-wrong-join risk `contract_expiry_engine.py`'s
and `nitaqat_compliance_engine.py`'s cross-link functions explicitly refuse
to take (see their `get_expiry_signals_by_record_id()` / `get_saudi_status_by_record_id()`
docstrings: "rather than risk a silent wrong join... return None"). A
company's department list is also low-cardinality (typically 5-20
departments) — small enough that a manual per-department entry form is
genuinely more usable than preparing and uploading a second file, AND it
sidesteps the join problem entirely: the frontend fetches the REAL
normalized department list from THIS module first, then collects planned
figures keyed by those exact names, so there is never a name-matching step
to get wrong. This is the same reasoning the brief itself used to justify
Zakat's manual-entry design, applied here to a different but structurally
similar problem (low-cardinality, user-known figures that don't belong in
an employee-level CSV).

**Real actual salary — never a benchmark fallback.** Unlike
`financial_intelligence_engine.py`'s `estimate_monthly_salary()` (which
falls back to a sector/seniority benchmark, appropriate for illustrative
exposure sizing elsewhere on this platform), the ACTUAL side of a
planned-vs-actual variance must never be silently replaced by a benchmark
— that would corrupt the very comparison this module exists to make. This
module instead reuses the exact strict "clean number or excluded, never
approximated" rule Phase 21's `labor_law_calculators.py` established,
reproduced locally per this codebase's per-module convention (see e.g.
`gosi_calculator_engine.py`'s identical citation). `department_normalizer.py`
IS genuinely reused directly (real reuse, not local reimplementation) —
the same real actual-vs-planned join-key concern above is exactly why: the
planned figures the frontend collects must be keyed by the SAME normalized
labels this module produces from the actual data, not a second guess at
normalization.

**Missing planned/actual data is disclosed, never assumed zero.** A
department present in the actual data with no planned entry submitted is
flagged `planned_submitted: false` (not a fabricated zero budget); a
planned entry for a department name with zero actual headcount is flagged
`actual_present: false` rather than silently dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series

# ── Column detection (local-regex convention, see module docstring) ────────

# Reused verbatim from labor_law_calculators.py's / gosi_calculator_engine.py's _SALARY_PATTERNS.
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|annual[_\s]?salary|salary|wage|"
    r"compensation|basic[_\s]?pay|gross[_\s]?pay|"
    r"الراتب|الأجر|التعويض)\b", re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b", re.I,
)

_now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _is_missing_value(raw: object) -> bool:
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _extract_strict_numeric_salary(df: pd.DataFrame, salary_col: Optional[str]) -> tuple[dict[Any, float], int, Optional[str]]:
    """Same strict "clean number or excluded, never approximated" rule as
    labor_law_calculators._extract_strict_numeric_salary() — see module
    docstring for why this module never falls back to a benchmark."""
    if salary_col is None:
        return {}, 0, None
    raw_series = df[salary_col]
    numeric = pd.to_numeric(raw_series, errors="coerce")
    valid: dict[Any, float] = {}
    n_excluded = 0
    example_excluded: Optional[str] = None
    for idx in df.index:
        val = numeric.loc[idx]
        if pd.notna(val) and float(val) > 0:
            valid[idx] = float(val)
        else:
            raw_val = raw_series.loc[idx]
            if not _is_missing_value(raw_val):
                n_excluded += 1
                if example_excluded is None:
                    example_excluded = str(raw_val).strip()
    return valid, n_excluded, example_excluded


PAYROLL_BUDGET_SOURCES = [
    "This module compares REAL actual headcount/payroll cost (computed from your uploaded "
    "employee data, using the exact same strict numeric-salary rule Phase 21's Saudi Labor "
    "Law Calculators use) against a PLANNED/budgeted figure you enter manually per "
    "department. Neither side is a benchmark or industry estimate.",
]
PAYROLL_BUDGET_DISCLAIMER_EN = (
    "Actual figures are computed from your real uploaded employee data; planned figures are "
    "exactly what you entered — this module never fabricates, estimates, or benchmarks "
    "either side. Variance is a planning/monitoring aid, not an official budget reconciliation "
    "or finance-system-of-record figure; confirm against your actual payroll system before "
    "using these numbers for financial reporting or board-level decisions."
)
PAYROLL_BUDGET_DISCLAIMER_AR = (
    "تُحتسب الأرقام الفعلية من بيانات موظفيك الحقيقية المُحمّلة؛ والأرقام المخططة هي بالضبط "
    "ما أدخلته يدوياً — لا تختلق هذه الوحدة أو تقدّر أو تُقارن بمعيار أي من الجانبين. الفروقات "
    "أداة تخطيط ومراقبة، وليست تسوية ميزانية رسمية أو رقماً من نظام مالي معتمد؛ يرجى التحقق "
    "من نظام الرواتب الفعلي قبل استخدام هذه الأرقام في التقارير المالية أو قرارات مجلس الإدارة."
)


@dataclass(frozen=True)
class PlannedDepartmentBudget:
    planned_headcount: int
    planned_avg_salary_sar: float


@dataclass(frozen=True)
class DepartmentBudgetVariance:
    department: str
    actual_present: bool
    planned_submitted: bool
    actual_headcount: int
    actual_avg_salary_sar: Optional[float]
    actual_total_payroll_sar: Optional[float]
    n_excluded_invalid_salary: int
    planned_headcount: Optional[int]
    planned_avg_salary_sar: Optional[float]
    planned_total_payroll_sar: Optional[float]
    headcount_variance: Optional[int]
    headcount_variance_pct: Optional[float]
    payroll_cost_variance_sar: Optional[float]
    payroll_cost_variance_pct: Optional[float]


@dataclass(frozen=True)
class PayrollBudgetResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    salary_column: Optional[str]
    department_column: Optional[str]
    n_employees_total: int
    n_valid_salary: int
    n_excluded_invalid_salary: int
    example_excluded_salary_value: Optional[str]
    department_variances: list[DepartmentBudgetVariance]
    department_normalization_notes: list[str]
    company_actual_headcount: int
    company_actual_total_payroll_sar: float
    company_planned_headcount: Optional[int]
    company_planned_total_payroll_sar: Optional[float]
    company_headcount_variance: Optional[int]
    company_headcount_variance_pct: Optional[float]
    company_payroll_cost_variance_sar: Optional[float]
    company_payroll_cost_variance_pct: Optional[float]
    departments_missing_planned_budget: list[str]
    planned_departments_missing_actual_data: list[str]
    narrative_en: str
    narrative_ar: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_payroll_budget_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> PayrollBudgetResult:
    return PayrollBudgetResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        salary_column=None, department_column=None, n_employees_total=0, n_valid_salary=0,
        n_excluded_invalid_salary=0, example_excluded_salary_value=None,
        department_variances=[], department_normalization_notes=[],
        company_actual_headcount=0, company_actual_total_payroll_sar=0.0,
        company_planned_headcount=None, company_planned_total_payroll_sar=None,
        company_headcount_variance=None, company_headcount_variance_pct=None,
        company_payroll_cost_variance_sar=None, company_payroll_cost_variance_pct=None,
        departments_missing_planned_budget=[], planned_departments_missing_actual_data=[],
        narrative_en="Payroll budget variance not available for this dataset.",
        narrative_ar="مقارنة ميزانية الرواتب غير متاحة لهذه البيانات.",
        disclaimer_en=PAYROLL_BUDGET_DISCLAIMER_EN, disclaimer_ar=PAYROLL_BUDGET_DISCLAIMER_AR,
        governance_note="No variance is computed without a real department column and at least one usable numeric salary.",
        sources=PAYROLL_BUDGET_SOURCES, computed_at=_now(),
    )


def compute_payroll_budget_variance(
    df: pd.DataFrame,
    planned_by_department: dict[str, PlannedDepartmentBudget],
) -> PayrollBudgetResult:
    """Never raises — exceptions should be caught by the caller and
    surfaced via unavailable_payroll_budget_result.

    `planned_by_department` MUST be keyed by the exact normalized
    department labels this function itself would produce (i.e., the
    frontend calls the department-listing step first) — see module
    docstring for why no fuzzy name-matching is attempted here."""
    if df is None or df.empty:
        return unavailable_payroll_budget_result("No data available for payroll budget comparison.")

    salary_col = _find_column(df, _SALARY_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    columns_detected = {"salary": salary_col is not None, "department": dept_col is not None}

    if salary_col is None or dept_col is None:
        missing = []
        if salary_col is None:
            missing.append("a numeric salary column")
        if dept_col is None:
            missing.append("a department column")
        return unavailable_payroll_budget_result(
            f"Payroll budget comparison requires {' and '.join(missing)} in the uploaded "
            "employee data.",
            columns_detected,
        )

    salary_valid, n_excluded, example_excluded = _extract_strict_numeric_salary(df, salary_col)
    dept_result = normalize_department_series(df[dept_col].astype(object))
    dept_notes: list[str] = []
    for merge in dept_result.merges_applied:
        variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
        dept_notes.append(f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}.")
    for grp in dept_result.unmerged_similar_variants:
        dept_notes.append(f"Found similarly-named but NOT merged department values {', '.join(repr(v) for v in grp)} — review manually.")
    keys = pd.Series(dept_result.normalized_keys.values, index=df.index)
    dept_lookup = {idx: dept_result.display_labels.get(keys.loc[idx], keys.loc[idx]) for idx in df.index}

    actual_agg: dict[str, dict[str, Any]] = {}
    for idx in df.index:
        dept = dept_lookup.get(idx)
        if dept is None:
            continue
        bucket = actual_agg.setdefault(dept, {"headcount": 0, "salary_sum": 0.0, "n_valid": 0, "n_excluded": 0})
        bucket["headcount"] += 1
        wage = salary_valid.get(idx)
        if wage is not None:
            bucket["salary_sum"] += wage
            bucket["n_valid"] += 1
        elif not _is_missing_value(df.at[idx, salary_col]):
            bucket["n_excluded"] += 1

    all_departments = sorted(set(actual_agg.keys()) | set(planned_by_department.keys()))
    variances: list[DepartmentBudgetVariance] = []
    departments_missing_planned: list[str] = []
    planned_missing_actual: list[str] = []

    company_actual_headcount = 0
    company_actual_total = 0.0
    company_planned_headcount = 0
    company_planned_total = 0.0
    any_planned = bool(planned_by_department)

    for dept in all_departments:
        actual = actual_agg.get(dept)
        planned = planned_by_department.get(dept)
        actual_present = actual is not None
        planned_submitted = planned is not None

        actual_headcount = actual["headcount"] if actual else 0
        actual_avg = round(actual["salary_sum"] / actual["n_valid"], 2) if actual and actual["n_valid"] > 0 else None
        # The REAL sum of only the clean numeric salaries actually found —
        # never avg*headcount, which would silently impute the average onto
        # employees whose salary was excluded (see module docstring).
        actual_total = round(actual["salary_sum"], 2) if actual and actual["n_valid"] > 0 else None

        planned_headcount = planned.planned_headcount if planned else None
        planned_avg = planned.planned_avg_salary_sar if planned else None
        planned_total = round(planned_headcount * planned_avg, 2) if planned else None

        hc_variance = (actual_headcount - planned_headcount) if (actual_present and planned_submitted) else None
        hc_variance_pct = (
            round(100.0 * hc_variance / planned_headcount, 1)
            if hc_variance is not None and planned_headcount not in (None, 0) else None
        )
        cost_variance = (
            round(actual_total - planned_total, 2)
            if actual_total is not None and planned_total is not None else None
        )
        cost_variance_pct = (
            round(100.0 * cost_variance / planned_total, 1)
            if cost_variance is not None and planned_total not in (None, 0) else None
        )

        variances.append(DepartmentBudgetVariance(
            department=dept, actual_present=actual_present, planned_submitted=planned_submitted,
            actual_headcount=actual_headcount, actual_avg_salary_sar=actual_avg,
            actual_total_payroll_sar=actual_total,
            n_excluded_invalid_salary=actual["n_excluded"] if actual else 0,
            planned_headcount=planned_headcount, planned_avg_salary_sar=planned_avg,
            planned_total_payroll_sar=planned_total,
            headcount_variance=hc_variance, headcount_variance_pct=hc_variance_pct,
            payroll_cost_variance_sar=cost_variance, payroll_cost_variance_pct=cost_variance_pct,
        ))

        if actual_present and not planned_submitted:
            departments_missing_planned.append(dept)
        if planned_submitted and not actual_present:
            planned_missing_actual.append(dept)

        company_actual_headcount += actual_headcount
        if actual_total is not None:
            company_actual_total += actual_total
        if planned_submitted:
            company_planned_headcount += planned_headcount
            company_planned_total += planned_total

    variances.sort(key=lambda v: (v.payroll_cost_variance_sar is None, abs(v.payroll_cost_variance_sar or 0)), reverse=True)

    company_hc_variance = (company_actual_headcount - company_planned_headcount) if any_planned else None
    company_hc_variance_pct = (
        round(100.0 * company_hc_variance / company_planned_headcount, 1)
        if company_hc_variance is not None and company_planned_headcount else None
    )
    company_cost_variance = (round(company_actual_total - company_planned_total, 2) if any_planned else None)
    company_cost_variance_pct = (
        round(100.0 * company_cost_variance / company_planned_total, 1)
        if company_cost_variance is not None and company_planned_total else None
    )

    narrative_en = (
        f"{len(actual_agg)} department(s) with real actual headcount found in your upload "
        f"({sum(a['n_valid'] for a in actual_agg.values())} of {len(df)} employees had a "
        f"usable numeric salary, {salary_col})."
    )
    narrative_ar = (
        f"تم العثور على {len(actual_agg)} قسماً بحجم عمالة فعلي حقيقي في ملفك المُحمّل "
        f"({sum(a['n_valid'] for a in actual_agg.values())} من أصل {len(df)} موظفاً لديهم "
        f"راتب رقمي صالح، {salary_col})."
    )
    if not any_planned:
        narrative_en += " No planned/budgeted figures were submitted — showing actual figures only."
        narrative_ar += " لم تُقدَّم أرقام مخططة/ميزانية — يتم عرض الأرقام الفعلية فقط."
    elif departments_missing_planned:
        narrative_en += f" {len(departments_missing_planned)} department(s) have actual data but no submitted budget."
        narrative_ar += f" لدى {len(departments_missing_planned)} قسماً بيانات فعلية دون ميزانية مُقدَّمة."
    if n_excluded > 0:
        narrative_en += (
            f" {n_excluded} employee(s) excluded from actual payroll totals — salary value "
            "not a clean number (real headcount still includes them, so actual payroll cost "
            "figures may understate the true total)."
        )
        narrative_ar += (
            f" استُبعد {n_excluded} موظفاً من إجمالي الرواتب الفعلي — قيمة الراتب ليست رقماً "
            "صريحاً (يظل حجم العمالة الفعلي شاملاً لهم، لذا قد تكون أرقام تكلفة الرواتب "
            "الفعلية أقل من الإجمالي الحقيقي)."
        )

    return PayrollBudgetResult(
        available=True, reason=None, columns_detected=columns_detected,
        salary_column=salary_col, department_column=dept_col,
        n_employees_total=len(df), n_valid_salary=sum(a["n_valid"] for a in actual_agg.values()),
        n_excluded_invalid_salary=n_excluded, example_excluded_salary_value=example_excluded,
        department_variances=variances, department_normalization_notes=dept_notes,
        company_actual_headcount=company_actual_headcount,
        company_actual_total_payroll_sar=round(company_actual_total, 2),
        company_planned_headcount=company_planned_headcount if any_planned else None,
        company_planned_total_payroll_sar=round(company_planned_total, 2) if any_planned else None,
        company_headcount_variance=company_hc_variance, company_headcount_variance_pct=company_hc_variance_pct,
        company_payroll_cost_variance_sar=company_cost_variance, company_payroll_cost_variance_pct=company_cost_variance_pct,
        departments_missing_planned_budget=departments_missing_planned,
        planned_departments_missing_actual_data=planned_missing_actual,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        disclaimer_en=PAYROLL_BUDGET_DISCLAIMER_EN, disclaimer_ar=PAYROLL_BUDGET_DISCLAIMER_AR,
        governance_note=(
            "Actual figures are computed only from clean numeric salary values (never "
            "approximated from range-text); planned figures are exactly what was entered, "
            "never estimated on the user's behalf."
        ),
        sources=PAYROLL_BUDGET_SOURCES, computed_at=_now(),
    )


def payroll_budget_result_to_dict(r: PayrollBudgetResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "salary_column": r.salary_column, "department_column": r.department_column,
        "n_employees_total": r.n_employees_total, "n_valid_salary": r.n_valid_salary,
        "n_excluded_invalid_salary": r.n_excluded_invalid_salary,
        "example_excluded_salary_value": r.example_excluded_salary_value,
        "department_variances": [
            {
                "department": v.department, "actual_present": v.actual_present,
                "planned_submitted": v.planned_submitted, "actual_headcount": v.actual_headcount,
                "actual_avg_salary_sar": v.actual_avg_salary_sar,
                "actual_total_payroll_sar": v.actual_total_payroll_sar,
                "n_excluded_invalid_salary": v.n_excluded_invalid_salary,
                "planned_headcount": v.planned_headcount, "planned_avg_salary_sar": v.planned_avg_salary_sar,
                "planned_total_payroll_sar": v.planned_total_payroll_sar,
                "headcount_variance": v.headcount_variance, "headcount_variance_pct": v.headcount_variance_pct,
                "payroll_cost_variance_sar": v.payroll_cost_variance_sar,
                "payroll_cost_variance_pct": v.payroll_cost_variance_pct,
            }
            for v in r.department_variances
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "company_actual_headcount": r.company_actual_headcount,
        "company_actual_total_payroll_sar": r.company_actual_total_payroll_sar,
        "company_planned_headcount": r.company_planned_headcount,
        "company_planned_total_payroll_sar": r.company_planned_total_payroll_sar,
        "company_headcount_variance": r.company_headcount_variance,
        "company_headcount_variance_pct": r.company_headcount_variance_pct,
        "company_payroll_cost_variance_sar": r.company_payroll_cost_variance_sar,
        "company_payroll_cost_variance_pct": r.company_payroll_cost_variance_pct,
        "departments_missing_planned_budget": r.departments_missing_planned_budget,
        "planned_departments_missing_actual_data": r.planned_departments_missing_actual_data,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }
