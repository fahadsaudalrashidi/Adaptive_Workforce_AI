"""
Payroll Movements Tracker — Phase 35.2.

Tracks salary movement per employee cohort/department and compares it,
descriptively, against attrition-risk scores already computed elsewhere in
the pipeline. Because this platform's supported HR datasets are almost
always a single-point-in-time snapshot (confirmed: the IBM-HR-family schema
this codebase's normalizer/theory engine target has no period/date-indexed
salary history — see backend/core/saudi_attrition_normalizer.py and
backend/core/theory_grounded_construct_engine.py's SalaryGrowth construct,
which itself only uses a single PercentSalaryHike snapshot value), this
module operates in one of three modes, always disclosed to the caller:

  "longitudinal"             — the uploaded dataset genuinely contains
                                multiple dated records per employee. Real
                                period-over-period salary movement is
                                computed directly.
  "cross_sectional_snapshot" — no true history exists, but a recognised
                                single-snapshot proxy (e.g. PercentSalaryHike)
                                is present. A real, data-derived indicator is
                                still computed, but is explicitly labeled as
                                a snapshot proxy, not a movement history.
  "unavailable"               — neither exists. No movement data is
                                fabricated; the response explains exactly
                                what column shape would activate the
                                longitudinal or snapshot-proxy path.

No causal claims are made about salary movement and attrition risk — any
relationship reported is a descriptive group comparison, consistent with
the non-causal language discipline used throughout this codebase (see
config/settings.py's ATTRITION_LANGUAGE_SAFE / FORBIDDEN_EXECUTIVE_PHRASES
and executive_narrative_engine.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

# Phase 35.5 correction: department grouping now goes through the single
# canonical normalizer instead of raw string equality — fixes a confirmed
# bug where "Sales"/"مبيعات" and "Finance"/"finance" were counted as
# separate departments (see department_normalizer.py for the full trace).
from backend.core.department_normalizer import normalize_department_series

# ── Column detection patterns ───────────────────────────────────────────────────

_EMPLOYEE_ID_PATTERNS = re.compile(
    r"\b(employee[_\s]?id|employee[_\s]?number|emp[_\s]?id|emp[_\s]?no|empno|staff[_\s]?id)\b",
    re.I,
)
_PERIOD_PATTERNS = re.compile(
    r"\b(period|snapshot[_\s]?date|as[_\s]?of[_\s]?date|report[_\s]?date|month|quarter|year|date)\b",
    re.I,
)
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|salary|wage|compensation|basic[_\s]?pay|gross[_\s]?pay)\b",
    re.I,
)
_HIKE_SNAPSHOT_PATTERNS = re.compile(
    r"\b(percent[_\s]?salary[_\s]?hike|salary[_\s]?hike|pay[_\s]?raise|raise[_\s]?pct|"
    r"salary[_\s]?increase[_\s]?pct)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|unit|group|team|section|القسم|الإدارة)\b",
    re.I,
)

# Group comparison threshold used for both modes: employees/departments
# above the cohort median hike are compared against those below it.

_SOURCES: list[str] = [
    "This platform's own theory_grounded_construct_engine.py SalaryGrowth "
    "construct (Siegrist Effort-Reward Imbalance model) — used here as the "
    "basis for recognising PercentSalaryHike-style snapshot columns.",
]


@dataclass(frozen=True)
class DepartmentPayrollMovement:
    department: str
    n_employees: int
    avg_hike_pct: float
    avg_risk_score_above_median_hike: Optional[float]
    avg_risk_score_below_median_hike: Optional[float]


@dataclass(frozen=True)
class PayrollMovementResult:
    available: bool
    reason: Optional[str]
    data_mode: str   # "longitudinal" | "cross_sectional_snapshot" | "unavailable"
    n_employees_total: int
    org_avg_hike_pct: Optional[float]
    n_periods_detected: Optional[int]
    department_breakdown: list[DepartmentPayrollMovement]
    comparison_note_en: str
    comparison_note_ar: str
    limitation_note_en: str
    limitation_note_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str
    # Phase 35.5: department-name merges applied/flagged during grouping —
    # see department_normalizer.py.
    department_normalization_notes: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def unavailable_payroll_result(reason: str) -> PayrollMovementResult:
    """Public constructor for an `available=False` result."""
    return PayrollMovementResult(
        available=False,
        reason=reason,
        data_mode="unavailable",
        n_employees_total=0,
        org_avg_hike_pct=None,
        n_periods_detected=None,
        department_breakdown=[],
        comparison_note_en=reason,
        comparison_note_ar="بيانات حركة الرواتب غير متوفرة في مجموعة البيانات المرفوعة.",
        limitation_note_en=(
            "This capability activates automatically when the uploaded dataset "
            "contains either (a) multiple dated records per employee (a period/"
            "date column plus a repeating employee-ID column), enabling real "
            "period-over-period salary movement tracking, or (b) a recognised "
            "single-snapshot salary-change indicator such as a 'percent salary "
            "hike' column, enabling a snapshot-proxy estimate. Neither was found."
        ),
        limitation_note_ar=(
            "يتم تفعيل هذه الميزة تلقائياً عند احتواء البيانات المرفوعة إما على "
            "سجلات متعددة مؤرخة لكل موظف، أو مؤشر تغيير راتب لحظي معروف."
        ),
        governance_note=(
            "Payroll movement figures are statistical indicators for HR planning, "
            "never audited payroll records, and must not be used as the sole "
            "basis for compensation decisions."
        ),
        sources=[],
        computed_at=_now(),
    )


def _group_comparison(
    hike: pd.Series, risk: pd.Series,
) -> tuple[Optional[float], Optional[float]]:
    """
    Split employees into above/below the cohort median hike and compare
    average risk score between the two groups. Returns (None, None) if risk
    data isn't available for a meaningful comparison.
    """
    valid = risk.notna()
    if valid.sum() < 10:
        return None, None
    median_hike = float(hike[valid].median())
    above = valid & (hike >= median_hike)
    below = valid & (hike < median_hike)
    avg_above = float(risk[above].mean()) if above.sum() > 0 else None
    avg_below = float(risk[below].mean()) if below.sum() > 0 else None
    return avg_above, avg_below


def analyze_payroll_movements(
    df: pd.DataFrame,
    department_summary: Optional[list[dict]] = None,
    employee_risk_scores: Optional[pd.Series] = None,
) -> PayrollMovementResult:
    """
    Analyze salary movement and compare it descriptively against attrition
    risk. See module docstring for the three operating modes.

    Parameters
    ----------
    df                  : the uploaded, governance-cleared dataframe
    department_summary  : optional list of dicts from EmployeeRiskScorer
                          (each with "group_value"/"department" and
                          "average_risk_score"), used for department-level
                          risk context.
    employee_risk_scores: optional per-row risk score Series aligned to df's
                          index (0-100), used for the above/below-median-hike
                          group comparison. If not supplied, department
                          average_risk_score from department_summary is used
                          in its place for the department breakdown only,
                          and the org-wide group comparison is skipped.
    """
    if df is None or len(df) == 0:
        return unavailable_payroll_result("Uploaded dataset is empty — no payroll movement analysis possible.")

    n_total = len(df)
    emp_id_col = _find_column(df, _EMPLOYEE_ID_PATTERNS)
    period_col = _find_column(df, _PERIOD_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)

    # ── Mode 1: longitudinal (real multi-period history) ─────────────────────
    if emp_id_col is not None and period_col is not None:
        dup_counts = df[emp_id_col].value_counts()
        n_multi_period_employees = int((dup_counts > 1).sum())
        if n_multi_period_employees >= 5:
            salary_col = _find_column(df, _SALARY_PATTERNS)
            if salary_col is None:
                return unavailable_payroll_result(
                    "Multiple dated records per employee were detected, but no "
                    "salary column was found alongside them."
                )
            return _analyze_longitudinal(
                df, emp_id_col, period_col, salary_col, dept_col, department_summary,
            )

    # ── Mode 2: cross-sectional snapshot proxy ────────────────────────────────
    hike_col = _find_column(df, _HIKE_SNAPSHOT_PATTERNS)
    if hike_col is not None:
        return _analyze_snapshot_proxy(
            df, hike_col, dept_col, department_summary, employee_risk_scores,
        )

    # ── Mode 3: unavailable ────────────────────────────────────────────────────
    return unavailable_payroll_result(
        "No period/date-indexed salary history and no recognised single-"
        "snapshot salary-change column (e.g. 'PercentSalaryHike') were found "
        "in this dataset."
    )


def _analyze_longitudinal(
    df: pd.DataFrame,
    emp_id_col: str,
    period_col: str,
    salary_col: str,
    dept_col: Optional[str],
    department_summary: Optional[list[dict]],
) -> PayrollMovementResult:
    work = df[[emp_id_col, period_col, salary_col] + ([dept_col] if dept_col else [])].copy()
    work.columns = ["_id", "_period", "_salary"] + (["_dept"] if dept_col else [])
    work["_salary"] = pd.to_numeric(work["_salary"], errors="coerce")
    work = work.dropna(subset=["_salary"])

    dept_normalization_notes: list[str] = []
    dept_display_labels: dict[str, str] = {}
    if "_dept" in work.columns:
        norm_result = normalize_department_series(work["_dept"])
        work["_dept"] = norm_result.normalized_keys.values
        dept_display_labels = norm_result.display_labels
        for merge in norm_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_normalization_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}' "
                f"(recognised as the same department): {merge.counts_per_variant}."
            )
        for group in norm_result.unmerged_similar_variants:
            dept_normalization_notes.append(
                f"Found similarly-named but NOT merged department values "
                f"{', '.join(repr(v) for v in group)} — review manually."
            )

    # Sort within each employee by period (works for numeric years/quarters
    # and for ISO-ish date strings via pandas' flexible sort on the raw column).
    work = work.sort_values(["_id", "_period"])
    work["_pct_change"] = work.groupby("_id")["_salary"].pct_change() * 100.0
    moves = work.dropna(subset=["_pct_change"])

    n_periods = int(work["_period"].nunique())

    if len(moves) == 0:
        return unavailable_payroll_result(
            "Longitudinal structure was detected, but no employee had a "
            "computable period-over-period salary change (check for missing "
            "or non-numeric salary values)."
        )

    org_avg_hike = round(float(moves["_pct_change"].mean()), 2)

    risk_by_dept: dict[str, float] = {}
    if department_summary:
        for d in department_summary:
            name = str(d.get("group_value") or d.get("department") or "").strip().lower()
            score = d.get("average_risk_score")
            if name and score is not None:
                risk_by_dept[name] = float(score)

    dept_breakdown: list[DepartmentPayrollMovement] = []
    if "_dept" in moves.columns:
        for dept_name, grp in moves.groupby("_dept"):
            display_name = dept_display_labels.get(str(dept_name), str(dept_name))
            avg_above, avg_below = None, None
            avg_risk = risk_by_dept.get(display_name.strip().lower())
            dept_breakdown.append(DepartmentPayrollMovement(
                department=display_name,
                n_employees=int(grp["_id"].nunique()),
                avg_hike_pct=round(float(grp["_pct_change"].mean()), 2),
                avg_risk_score_above_median_hike=avg_above,
                avg_risk_score_below_median_hike=avg_below,
            ))
        dept_breakdown.sort(key=lambda d: d.avg_hike_pct, reverse=True)

    comparison_note_en = (
        f"Across {n_periods} recorded periods, employees show an average "
        f"period-over-period salary change of {org_avg_hike:+.1f}%. This is "
        "computed directly from the dataset's own dated salary history, not "
        "an estimate."
    )
    comparison_note_ar = (
        f"عبر {n_periods} فترة مسجلة، يُظهر الموظفون متوسط تغيير راتب "
        f"{org_avg_hike:+.1f}% بين الفترات، محسوباً مباشرة من سجل الرواتب الفعلي."
    )

    return PayrollMovementResult(
        available=True,
        reason=None,
        data_mode="longitudinal",
        n_employees_total=int(work["_id"].nunique()),
        org_avg_hike_pct=org_avg_hike,
        n_periods_detected=n_periods,
        department_breakdown=dept_breakdown,
        department_normalization_notes=dept_normalization_notes,
        comparison_note_en=comparison_note_en,
        comparison_note_ar=comparison_note_ar,
        limitation_note_en="",
        limitation_note_ar="",
        governance_note=(
            "Payroll movement figures are statistical indicators for HR planning, "
            "never audited payroll records, and must not be used as the sole "
            "basis for compensation decisions."
        ),
        sources=list(_SOURCES),
        computed_at=_now(),
    )


def _analyze_snapshot_proxy(
    df: pd.DataFrame,
    hike_col: str,
    dept_col: Optional[str],
    department_summary: Optional[list[dict]],
    employee_risk_scores: Optional[pd.Series],
) -> PayrollMovementResult:
    hike = pd.to_numeric(df[hike_col], errors="coerce")
    valid_mask = hike.notna()
    n_total = len(df)

    if valid_mask.sum() == 0:
        return unavailable_payroll_result(
            f"A '{hike_col}' column was found but contained no usable numeric values."
        )

    org_avg_hike = round(float(hike[valid_mask].mean()), 2)

    risk_by_dept: dict[str, float] = {}
    if department_summary:
        for d in department_summary:
            name = str(d.get("group_value") or d.get("department") or "").strip().lower()
            score = d.get("average_risk_score")
            if name and score is not None:
                risk_by_dept[name] = float(score)

    avg_above_org, avg_below_org = (None, None)
    if employee_risk_scores is not None:
        avg_above_org, avg_below_org = _group_comparison(hike, employee_risk_scores)

    dept_breakdown: list[DepartmentPayrollMovement] = []
    dept_normalization_notes: list[str] = []
    if dept_col is not None:
        work = pd.DataFrame({"_dept": df[dept_col].astype(str), "_hike": hike})
        if employee_risk_scores is not None:
            work["_risk"] = employee_risk_scores.reindex(df.index)

        norm_result = normalize_department_series(work["_dept"])
        work["_dept"] = norm_result.normalized_keys.values
        dept_display_labels = norm_result.display_labels
        for merge in norm_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_normalization_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}' "
                f"(recognised as the same department): {merge.counts_per_variant}."
            )
        for group in norm_result.unmerged_similar_variants:
            dept_normalization_notes.append(
                f"Found similarly-named but NOT merged department values "
                f"{', '.join(repr(v) for v in group)} — review manually."
            )

        for dept_name, grp in work.groupby("_dept"):
            g = grp.dropna(subset=["_hike"])
            if len(g) == 0:
                continue
            display_name = dept_display_labels.get(str(dept_name), str(dept_name))
            avg_above, avg_below = (None, None)
            if "_risk" in g.columns:
                avg_above, avg_below = _group_comparison(g["_hike"], g["_risk"])
            avg_risk = risk_by_dept.get(display_name.strip().lower())
            dept_breakdown.append(DepartmentPayrollMovement(
                department=display_name,
                n_employees=len(g),
                avg_hike_pct=round(float(g["_hike"].mean()), 2),
                avg_risk_score_above_median_hike=avg_above,
                avg_risk_score_below_median_hike=(
                    avg_below if avg_below is not None else avg_risk
                ),
            ))
        dept_breakdown.sort(key=lambda d: d.avg_hike_pct, reverse=True)

    comparison_note_en = (
        f"Average recent salary-hike snapshot across the workforce is "
        f"{org_avg_hike:+.1f}%. This is a single point-in-time indicator "
        f"('{hike_col}'), not a tracked history."
    )
    if avg_above_org is not None and avg_below_org is not None:
        direction = "lower" if avg_above_org < avg_below_org else "higher"
        comparison_note_en += (
            f" Employees with an above-median recent hike show a {direction} "
            f"average risk score ({avg_above_org:.1f}) than those below the "
            f"median ({avg_below_org:.1f}). This is a descriptive comparison "
            "only — it does not establish that salary movement causes the "
            "difference in risk; both may reflect other factors such as "
            "tenure, role, or performance."
        )
    comparison_note_ar = (
        f"متوسط مؤشر الزيادة الأخيرة في الراتب عبر القوى العاملة هو "
        f"{org_avg_hike:+.1f}%. هذا مؤشر لحظي وليس سجلاً تاريخياً متتبعاً."
    )

    limitation_note_en = (
        f"This dataset has no period/date-indexed salary history — only the "
        f"single-snapshot '{hike_col}' column. Upload a dataset with multiple "
        "dated records per employee (a period column plus a repeating "
        "employee-ID column) to unlock real period-over-period movement "
        "tracking instead of this snapshot proxy."
    )
    limitation_note_ar = (
        "لا تحتوي هذه البيانات على سجل رواتب مؤرخ عبر فترات متعددة — فقط "
        "مؤشر لحظي واحد. حمّل بيانات تحتوي على سجلات مؤرخة متعددة لكل موظف "
        "لتفعيل تتبع حركة الرواتب الفعلي بين الفترات."
    )

    return PayrollMovementResult(
        available=True,
        reason=None,
        data_mode="cross_sectional_snapshot",
        n_employees_total=n_total,
        org_avg_hike_pct=org_avg_hike,
        n_periods_detected=1,
        department_breakdown=dept_breakdown,
        department_normalization_notes=dept_normalization_notes,
        comparison_note_en=comparison_note_en,
        comparison_note_ar=comparison_note_ar,
        limitation_note_en=limitation_note_en,
        limitation_note_ar=limitation_note_ar,
        governance_note=(
            "Payroll movement figures are statistical indicators for HR planning, "
            "never audited payroll records, and must not be used as the sole "
            "basis for compensation decisions. Snapshot-proxy mode does not "
            "prove causality between salary movement and risk."
        ),
        sources=list(_SOURCES),
        computed_at=_now(),
    )


def payroll_movement_to_dict(r: PayrollMovementResult) -> dict[str, Any]:
    """Serialize PayrollMovementResult to a JSON-safe dict."""
    return {
        "available": r.available,
        "reason": r.reason,
        "data_mode": r.data_mode,
        "n_employees_total": r.n_employees_total,
        "org_avg_hike_pct": r.org_avg_hike_pct,
        "n_periods_detected": r.n_periods_detected,
        "department_breakdown": [
            {
                "department": d.department,
                "n_employees": d.n_employees,
                "avg_hike_pct": d.avg_hike_pct,
                "avg_risk_score_above_median_hike": d.avg_risk_score_above_median_hike,
                "avg_risk_score_below_median_hike": d.avg_risk_score_below_median_hike,
            }
            for d in r.department_breakdown
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "comparison_note_en": r.comparison_note_en,
        "comparison_note_ar": r.comparison_note_ar,
        "limitation_note_en": r.limitation_note_en,
        "limitation_note_ar": r.limitation_note_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
