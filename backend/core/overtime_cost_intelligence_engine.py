"""
Overtime & Workforce Cost Intelligence Engine — Phase 35.1.

Computes actual overtime cost exposure per department and organisation-wide,
in SAR, using real overtime/salary columns from the uploaded dataset where
available, and the canonical financial_intelligence_engine.py model as
fallback when real data is missing. Cross-references overtime cost against
department-level attrition risk (already computed elsewhere in the
pipeline by employee_risk_scoring.py) to surface departments where elevated
overtime spend coincides with elevated risk — a statistical association,
never presented as a causal claim.

Design rules (matching the rest of this codebase's governance discipline):
  - Real observed data (an actual overtime-hours column, an actual salary
    column) always takes precedence over an estimate. Every returned figure
    is labeled with its `hours_source` / `wage_source` ("observed" vs
    "assumed"/"estimated") so a caller can render an honest confidence cue.
  - No causal language. "Departments where overtime and risk are both
    elevated" is a co-occurrence observation, not a claim that overtime
    causes attrition risk.
  - Fully offline — no network calls, consistent with offline_mode_guard.py.
  - No individual employee is identified in the aggregate outputs.

Legal / methodological citations:
  - Saudi Labour Law, Royal Decree M/51 (1426H) — Article 107: overtime work
    is compensated at the employee's normal wage plus a minimum 50% premium.
  - Saudi Labour Law — Article 98: standard working hours are 48 hours/week
    (8 hours/day, 6 days/week) outside Ramadan, i.e. approximately 208
    hours/month (48 x 52 / 12), used here as the basis for converting a
    monthly salary into an hourly wage.
  - Where no real overtime-hours or salary column exists, this module falls
    back to backend/core/financial_intelligence_engine.py's cited salary
    model (see that module for its own CIPD/Cascio-Boudreau/SHRM/Gulf HR
    Consortium sources) rather than inventing a new figure.
  - The "assumed monthly overtime hours for a flagged (Yes/No) employee"
    constant below has NO external citation — no reliable public per-role
    benchmark was found for this specific quantity — and is explicitly
    labeled an engineering assumption, not a sourced statistic, both in
    this docstring and in every result this module returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.core.financial_intelligence_engine import (
    ASSUMPTION_SOURCES as _CANONICAL_SALARY_SOURCES,
    estimate_monthly_salary,
    infer_employment_sector_from_metadata,
    salary_benchmark_confidence_for,
)
# Phase 35.5 correction: department grouping now goes through the single
# canonical normalizer instead of raw string equality — fixes a confirmed
# bug where "Sales"/"مبيعات" and "Finance"/"finance" were counted as
# separate departments (see department_normalizer.py for the full trace).
from backend.core.department_normalizer import normalize_department_series

# ── Saudi Labour Law citations ─────────────────────────────────────────────────

OVERTIME_PREMIUM_MULTIPLIER = 1.5   # Article 107: wage + minimum 50% premium
STANDARD_MONTHLY_HOURS = 208.0      # Article 98: 48 hrs/week x 52 / 12

_LEGAL_SOURCES: list[str] = [
    "Saudi Labour Law, Royal Decree M/51 (1426H) — Article 107 (Overtime Compensation, +50% minimum premium)",
    "Saudi Labour Law, Royal Decree M/51 (1426H) — Article 98 (Standard Working Hours, 48 hrs/week)",
]

# Explicitly UNCITED engineering assumption — no public benchmark found for
# this figure. Used only when an overtime column exists as a binary Yes/No
# flag rather than an actual hours count, so a cost estimate can still be
# produced. Always surfaced to callers as an assumption, never presented as
# an observed or sourced statistic.
ASSUMED_MONTHLY_OVERTIME_HOURS_FOR_FLAGGED_EMPLOYEE = 15.0
_ASSUMED_HOURS_DISCLAIMER = (
    "No overtime-hours column was found in the uploaded dataset — only a "
    "yes/no overtime flag. Cost is estimated assuming "
    f"{ASSUMED_MONTHLY_OVERTIME_HOURS_FOR_FLAGGED_EMPLOYEE:.0f} overtime hours/month "
    "per flagged employee. This is an engineering assumption for illustrative "
    "purposes, NOT a sourced labour-market statistic. Upload a dataset with an "
    "actual overtime-hours column for a data-derived estimate."
)

# ── Column detection patterns ───────────────────────────────────────────────────

_OVERTIME_HOURS_PATTERNS = re.compile(
    r"\b(overtime[_\s]?hours?|ot[_\s]?hours?|monthly[_\s]?overtime|"
    r"weekly[_\s]?overtime|overtime[_\s]?worked)\b",
    re.I,
)
_OVERTIME_FLAG_PATTERNS = re.compile(
    r"\b(over[_\s]?time|ot[_\s]?flag|works?[_\s]?overtime)\b",
    re.I,
)
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|salary|wage|compensation|"
    r"basic[_\s]?pay|gross[_\s]?pay)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|unit|group|team|section|"
    r"القسم|الإدارة|الوحدة)\b",
    re.I,
)

_TRUE_TOKENS = {"yes", "y", "true", "1", "1.0"}


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DepartmentOvertimeCost:
    department: str
    n_employees: int
    n_overtime_employees: int
    overtime_prevalence_pct: float
    monthly_overtime_cost_sar: float
    annual_overtime_cost_sar: float
    average_risk_score: Optional[float]
    elevated_overtime_and_risk: bool


@dataclass(frozen=True)
class OvertimeCostIntelligenceResult:
    available: bool
    reason: Optional[str]
    hours_source: str            # "observed" | "assumed" | "unavailable"
    wage_source: str             # "observed" | "estimated"
    n_employees_total: int
    n_overtime_employees: int
    overtime_prevalence_pct: float
    org_monthly_overtime_cost_sar: float
    org_annual_overtime_cost_sar: float
    department_breakdown: list[DepartmentOvertimeCost]
    elevated_risk_departments: list[str]
    narrative_en: str
    narrative_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str
    # Phase 35.5: department-name merges applied/flagged during grouping —
    # see department_normalizer.py. Empty when no dept column was found.
    department_normalization_notes: list[str] = field(default_factory=list)
    # Phase 35.5 correction: honest provenance label for the salary figure
    # this cost estimate is built on — "observed" (real salary column),
    # "gastat_official_2018" (real GASTAT wage data, sector inferred from
    # dataset metadata), or "uncalibrated_generic_estimate" (last-resort
    # industry-vertical guess). See financial_intelligence_engine.py.
    salary_benchmark_confidence: str = "unavailable"
    employment_sector_used: Optional[str] = None


def unavailable_overtime_result(reason: str) -> OvertimeCostIntelligenceResult:
    """Public constructor for an `available=False` result — used by API routes
    that need to short-circuit before calling analyze_overtime_cost_intelligence
    (e.g. when the uploaded file failed to ingest at all)."""
    return _unavailable(reason)


def _unavailable(reason: str) -> OvertimeCostIntelligenceResult:
    return OvertimeCostIntelligenceResult(
        available=False,
        reason=reason,
        hours_source="unavailable",
        wage_source="unavailable",
        n_employees_total=0,
        n_overtime_employees=0,
        overtime_prevalence_pct=0.0,
        org_monthly_overtime_cost_sar=0.0,
        org_annual_overtime_cost_sar=0.0,
        department_breakdown=[],
        elevated_risk_departments=[],
        narrative_en=reason,
        narrative_ar="بيانات العمل الإضافي غير متوفرة في مجموعة البيانات المرفوعة.",
        governance_note=(
            "This analysis requires at least one overtime-related column "
            "(hours worked, or a yes/no overtime flag) in the uploaded dataset."
        ),
        sources=[],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _to_bool_series(series: pd.Series) -> pd.Series:
    def _is_true(v: Any) -> bool:
        if pd.isna(v):
            return False
        if isinstance(v, (int, float)):
            return float(v) > 0
        return str(v).strip().lower() in _TRUE_TOKENS
    return series.apply(_is_true)


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_overtime_cost_intelligence(
    df: pd.DataFrame,
    department_summary: Optional[list[dict]] = None,
    risk_elevated_threshold: float = 55.0,
) -> OvertimeCostIntelligenceResult:
    """
    Compute overtime financial exposure org-wide and per department, and
    cross-reference against department attrition risk.

    Parameters
    ----------
    df                      : the uploaded, governance-cleared dataframe
    department_summary      : optional list of dicts from EmployeeRiskScorer
                              (each with "group_value"/"department" and
                              "average_risk_score") used to cross-reference
                              overtime cost against attrition risk. If not
                              provided, department_breakdown is still
                              computed but average_risk_score is None.
    risk_elevated_threshold : average_risk_score (0-100) above which a
                              department is considered "elevated risk" for
                              the cross-reference (default 55, matching the
                              "Strategic Concern" band floor used elsewhere
                              in this codebase's risk_intelligence.py).
    """
    if df is None or len(df) == 0:
        return _unavailable("Uploaded dataset is empty — no overtime analysis possible.")

    n_total = len(df)

    hours_col = _find_column(df, _OVERTIME_HOURS_PATTERNS)
    flag_col = None if hours_col else _find_column(df, _OVERTIME_FLAG_PATTERNS)
    salary_col = _find_column(df, _SALARY_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)

    if hours_col is None and flag_col is None:
        return _unavailable(
            "No overtime-related column (hours worked, or a yes/no overtime "
            "flag) was detected in this dataset. Overtime cost intelligence "
            "requires at least one such column."
        )

    # ── Per-employee overtime hours ───────────────────────────────────────────
    if hours_col is not None:
        hours = pd.to_numeric(df[hours_col], errors="coerce").fillna(0.0).clip(lower=0.0)
        hours_source = "observed"
        hours_disclaimer = None
    else:
        flagged = _to_bool_series(df[flag_col])
        hours = flagged.astype(float) * ASSUMED_MONTHLY_OVERTIME_HOURS_FOR_FLAGGED_EMPLOYEE
        hours_source = "assumed"
        hours_disclaimer = _ASSUMED_HOURS_DISCLAIMER

    n_overtime_employees = int((hours > 0).sum())
    overtime_prevalence_pct = round(100.0 * n_overtime_employees / n_total, 1) if n_total else 0.0

    # ── Per-employee hourly wage ──────────────────────────────────────────────
    # Phase 35.5 correction: when a real salary column isn't available, infer
    # the employment sector (public/private/non_profit/international_regional)
    # from department metadata so the fallback uses the real, GASTAT-cited
    # wage table instead of the uncalibrated industry-vertical guess whenever
    # possible — and disclose exactly which was used via
    # salary_benchmark_confidence, matching the report exporters' pattern.
    employment_sector = infer_employment_sector_from_metadata(department_summary)

    if salary_col is not None:
        monthly_salary = pd.to_numeric(df[salary_col], errors="coerce")
        fallback_salary = estimate_monthly_salary("diversified", "mid", employment_sector=employment_sector)
        monthly_salary = monthly_salary.fillna(fallback_salary).clip(lower=0.0)
        wage_source = "observed"
        salary_benchmark_confidence = "observed"
    else:
        monthly_salary = pd.Series(
            estimate_monthly_salary("diversified", "mid", employment_sector=employment_sector),
            index=df.index, dtype=float,
        )
        wage_source = "estimated"
        salary_benchmark_confidence = salary_benchmark_confidence_for(employment_sector=employment_sector)

    hourly_wage = monthly_salary / STANDARD_MONTHLY_HOURS

    # ── Per-employee overtime cost (Article 107: wage x 1.5 premium) ──────────
    overtime_cost = hours * hourly_wage * OVERTIME_PREMIUM_MULTIPLIER

    org_monthly_cost = round(float(overtime_cost.sum()), 0)
    org_annual_cost = round(org_monthly_cost * 12, 0)

    # ── Department breakdown ──────────────────────────────────────────────────
    risk_by_dept: dict[str, float] = {}
    if department_summary:
        for d in department_summary:
            name = str(d.get("group_value") or d.get("department") or "").strip()
            score = d.get("average_risk_score")
            if name and score is not None:
                risk_by_dept[name.lower()] = float(score)

    dept_breakdown: list[DepartmentOvertimeCost] = []
    elevated_depts: list[str] = []
    dept_normalization_notes: list[str] = []

    if dept_col is not None:
        norm_result = normalize_department_series(df[dept_col].astype(str))
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

        work = pd.DataFrame({
            "_dept": norm_result.normalized_keys.values,
            "_hours": hours,
            "_cost": overtime_cost,
        })
        for dept_key, grp in work.groupby("_dept"):
            dept_name = norm_result.display_labels.get(dept_key, dept_key)
            n_emp = len(grp)
            n_ot = int((grp["_hours"] > 0).sum())
            monthly_dept_cost = round(float(grp["_cost"].sum()), 0)
            avg_risk = risk_by_dept.get(dept_name.strip().lower())
            is_high_overtime = n_emp > 0 and (n_ot / n_emp) >= 0.30  # >=30% of dept works overtime
            is_high_risk = avg_risk is not None and avg_risk >= risk_elevated_threshold
            elevated = bool(is_high_overtime and is_high_risk)
            if elevated:
                elevated_depts.append(dept_name)
            dept_breakdown.append(DepartmentOvertimeCost(
                department=dept_name,
                n_employees=n_emp,
                n_overtime_employees=n_ot,
                overtime_prevalence_pct=round(100.0 * n_ot / n_emp, 1) if n_emp else 0.0,
                monthly_overtime_cost_sar=monthly_dept_cost,
                annual_overtime_cost_sar=round(monthly_dept_cost * 12, 0),
                average_risk_score=avg_risk,
                elevated_overtime_and_risk=elevated,
            ))
        dept_breakdown.sort(key=lambda d: d.monthly_overtime_cost_sar, reverse=True)

    # ── Narrative (non-causal language) ───────────────────────────────────────
    sar = lambda n: f"SAR {n:,.0f}"
    narrative_en = (
        f"{overtime_prevalence_pct:.0f}% of employees ({n_overtime_employees} of {n_total}) "
        f"show recorded overtime. Estimated organisation-wide overtime cost is "
        f"{sar(org_monthly_cost)}/month ({sar(org_annual_cost)}/year), computed at a "
        f"{int((OVERTIME_PREMIUM_MULTIPLIER - 1) * 100)}% premium over the standard hourly wage "
        "per Saudi Labour Law Article 107."
    )
    if elevated_depts:
        narrative_en += (
            f" Overtime prevalence and attrition risk are both elevated in "
            f"{len(elevated_depts)} department(s): {', '.join(elevated_depts)}. "
            "This is a statistical co-occurrence, not evidence that overtime causes "
            "the elevated risk — other shared factors (workload, staffing levels, "
            "seasonal demand) may explain both. Recommended for structured HR review."
        )
    narrative_ar = (
        f"يُظهر {overtime_prevalence_pct:.0f}% من الموظفين ({n_overtime_employees} من {n_total}) "
        f"عملاً إضافياً مسجلاً. تُقدَّر تكلفة العمل الإضافي على مستوى المؤسسة بـ "
        f"{org_monthly_cost:,.0f} ريال سعودي شهرياً ({org_annual_cost:,.0f} ريال سنوياً)، "
        "بعلاوة قدرها 50% وفق المادة 107 من نظام العمل السعودي."
    )

    governance_note = (
        "Overtime cost figures are statistical estimates for HR planning, not "
        "audited payroll figures. They must not be used as the sole basis for "
        "compensation, disciplinary, or termination decisions. "
        + (hours_disclaimer + " " if hours_disclaimer else "")
        + (
            "Hourly wage is estimated from sector/seniority benchmarks, not "
            "observed salary data, and should be treated as indicative only. "
            if wage_source == "estimated" else ""
        )
    ).strip()

    sources = list(_LEGAL_SOURCES)
    if wage_source == "estimated":
        sources += list(_CANONICAL_SALARY_SOURCES)

    return OvertimeCostIntelligenceResult(
        available=True,
        reason=None,
        hours_source=hours_source,
        wage_source=wage_source,
        n_employees_total=n_total,
        n_overtime_employees=n_overtime_employees,
        overtime_prevalence_pct=overtime_prevalence_pct,
        org_monthly_overtime_cost_sar=org_monthly_cost,
        org_annual_overtime_cost_sar=org_annual_cost,
        department_breakdown=dept_breakdown,
        elevated_risk_departments=elevated_depts,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        governance_note=governance_note,
        sources=sources,
        computed_at=datetime.now(timezone.utc).isoformat(),
        department_normalization_notes=dept_normalization_notes,
        salary_benchmark_confidence=salary_benchmark_confidence,
        employment_sector_used=employment_sector,
    )


def overtime_cost_intelligence_to_dict(r: OvertimeCostIntelligenceResult) -> dict[str, Any]:
    """Serialize OvertimeCostIntelligenceResult to a JSON-safe dict."""
    return {
        "available": r.available,
        "reason": r.reason,
        "hours_source": r.hours_source,
        "wage_source": r.wage_source,
        "n_employees_total": r.n_employees_total,
        "n_overtime_employees": r.n_overtime_employees,
        "overtime_prevalence_pct": r.overtime_prevalence_pct,
        "org_monthly_overtime_cost_sar": r.org_monthly_overtime_cost_sar,
        "org_annual_overtime_cost_sar": r.org_annual_overtime_cost_sar,
        "department_breakdown": [
            {
                "department": d.department,
                "n_employees": d.n_employees,
                "n_overtime_employees": d.n_overtime_employees,
                "overtime_prevalence_pct": d.overtime_prevalence_pct,
                "monthly_overtime_cost_sar": d.monthly_overtime_cost_sar,
                "annual_overtime_cost_sar": d.annual_overtime_cost_sar,
                "average_risk_score": d.average_risk_score,
                "elevated_overtime_and_risk": d.elevated_overtime_and_risk,
            }
            for d in r.department_breakdown
        ],
        "elevated_risk_departments": r.elevated_risk_departments,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
        "department_normalization_notes": r.department_normalization_notes,
        "salary_benchmark_confidence": r.salary_benchmark_confidence,
        "employment_sector_used": r.employment_sector_used,
    }
