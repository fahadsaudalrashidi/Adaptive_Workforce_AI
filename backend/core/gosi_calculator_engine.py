"""
GOSI (General Organization for Social Insurance) Contribution Calculator — Phase 37.

Computes REAL government social-insurance contribution amounts per employee
and per department — the same "real legally-owed amount, not an
illustrative estimate" discipline `labor_law_calculators.py` established
for gratuity/leave, applied here to a genuinely different, currently
mid-transition regulatory figure.

**Live-verified rates (August 2026) — see PHASE_25_GOSI_BUDGET_ZAKAT_REPORT.md
for full sources.** Saudi Arabia runs TWO PARALLEL GOSI systems since the
New Social Insurance Law took effect 3 July 2024:

- **Old System** (Saudi nationals registered before 3 July 2024): flat
  21.5% total (employer 11.75% = 9% retirement + 2% occupational hazards +
  0.75% unemployment/SANED; employee 9.75% = 9% retirement + 0.75%
  unemployment). This rate is NOT scheduled to change.
- **New System** (Saudi nationals registered on/after 3 July 2024): total
  rate rises 0.5 percentage points EVERY JULY until finalized around July
  2028. For the CURRENT period this module was built and verified against
  (July-December 2026): 23.5% total (employer 12.75% = 10% retirement + 2%
  occupational hazards + 0.75% SANED; employee 10.75% = 10% retirement +
  0.75% SANED).
- **Non-Saudi employees**: 0% employee deduction. Employer pays a flat 2%
  for Occupational Hazards/Accidents Insurance only (no retirement, no
  unemployment coverage) — same contribution-base rules as Saudi nationals.
- **Contribution base, BOTH systems, BOTH nationalities**: basic salary +
  housing allowance, capped at SAR 45,000/month. Other allowances
  (transport, phone, commission, bonus) are excluded from the base. This
  directly corrects a preliminary assumption in this module's original
  brief that non-Saudi contributions might be uncapped — live search found
  multiple independent, consistent sources confirming the SAME SAR 45,000
  cap applies to non-Saudi employer contributions too.

**Because these rates change on a fixed annual schedule that will have
moved past this module's "current period" by the time it is read, and
different sources disagree on the exact FINAL 2028 endpoint split, this
module deliberately hardcodes only the well-corroborated CURRENT-PERIOD
rates and does NOT attempt to encode a multi-year rate schedule table. The
UI and every result explicitly discloses the effective period and instructs
the user to reconfirm current rates directly via GOSI/Ta'meenati before
acting — the same "living regulatory figure" caveat `labor_law_calculators.py`
uses for Article 87.**

**Registration-system detection — never guessed.** Whether a specific Saudi
employee falls under the Old or New System depends on their actual GOSI
registration date, which this platform cannot reliably infer from a hire
date (registration and hire dates are related but not guaranteed
identical, and guessing the wrong system produces a wrong real government
contribution figure — the same "never guess a legally consequential
classification" principle Phase 21 applies to gratuity separation type).
This module ONLY classifies an employee's system from an EXPLICIT
system/tier column if one is detected; when absent (the expected, common
case for typical HR exports), BOTH systems' figures are computed and shown
side by side for every Saudi employee — the same "show both, don't guess"
pattern Phase 21 established for unspecified separation type. When
genuinely unspecified, the New System figure is used as the single
"applicable" headline figure (for department rollups and KPIs) because it
is the higher of the two — the conservative choice for an employer cost-
planning tool, so this module never understates a mandatory cost.

**Column detection reuses this session's existing patterns verbatim**:
salary (`pay_equity_engine.py`/`labor_law_calculators.py`'s
`_SALARY_PATTERNS`), nationality (`nitaqat_compliance_engine.py`'s
`_NATIONALITY_PATTERNS` + Saudi/non-Saudi token classification), department
(same `_DEPARTMENT_PATTERNS` every engine this session uses) — all
duplicated locally per this codebase's established per-module convention,
not cross-imported. Housing allowance and GOSI system-tier detection are
new patterns for this module.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series

# ── Column detection (local-regex convention, see module docstring) ────────

# Reused verbatim from labor_law_calculators.py's / pay_equity_engine.py's _SALARY_PATTERNS.
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|annual[_\s]?salary|salary|wage|"
    r"compensation|basic[_\s]?pay|gross[_\s]?pay|"
    r"الراتب|الأجر|التعويض)\b", re.I,
)
_HOUSING_ALLOWANCE_PATTERNS = re.compile(
    r"\b(housing[_\s]?allowance|housing[_\s]?benefit|accommodation[_\s]?allowance|"
    r"بدل[_\s]?السكن|بدل[_\s]?سكن)\b", re.I,
)
# Reused verbatim from nitaqat_compliance_engine.py's _NATIONALITY_PATTERNS.
_NATIONALITY_PATTERNS = re.compile(
    r"\b(nationality|is[_\s]?saudi|saudi[_\s]?status|saudi[_\s]?national|citizenship|"
    r"الجنسية|جنسية|سعودي\/غير سعودي)\b", re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b", re.I,
)
_GOSI_SYSTEM_TIER_PATTERNS = re.compile(
    r"\b(gosi[_\s]?system|gosi[_\s]?tier|insurance[_\s]?system|"
    r"social[_\s]?insurance[_\s]?system|registration[_\s]?system|"
    r"نظام[_\s]?التأمينات)\b", re.I,
)

# Reused verbatim from nitaqat_compliance_engine.py's Saudi/non-Saudi token classification.
_SAUDI_TOKENS = {
    "saudi", "saudi arabia", "ksa", "sa", "1", "yes", "true",
    "سعودي", "سعودية", "السعودية", "المملكة العربية السعودية",
}
_EXPLICIT_NON_SAUDI_TOKENS = {
    "non-saudi", "non saudi", "nonsaudi", "expat", "expatriate", "foreign", "foreigner",
    "0", "no", "false", "غير سعودي", "أجنبي", "غير سعودية",
}
_OLD_SYSTEM_TOKENS = {
    "old", "old system", "system a", "existing", "existing system", "pre-2024", "pre 2024",
    "before july 2024", "النظام القديم", "قديم",
}
_NEW_SYSTEM_TOKENS = {
    "new", "new system", "system b", "post-2024", "post 2024", "after july 2024",
    "النظام الجديد", "جديد",
}

_ID_COLUMN_CANDIDATES = ("EmployeeID", "employee_id", "EmpID", "emp_id")
_MAX_ROW_LEVEL_CANDIDATES = 100

# ── Current-period rates (July-December 2026) — see module docstring ───────

GOSI_EFFECTIVE_PERIOD = "July 2026 - December 2026"
GOSI_WAGE_CAP_SAR = 45_000.0

OLD_SYSTEM_EMPLOYEE_RATE = 0.0975
OLD_SYSTEM_EMPLOYER_RATE = 0.1175
OLD_SYSTEM_TOTAL_RATE = OLD_SYSTEM_EMPLOYEE_RATE + OLD_SYSTEM_EMPLOYER_RATE  # 21.5%

NEW_SYSTEM_EMPLOYEE_RATE = 0.1075
NEW_SYSTEM_EMPLOYER_RATE = 0.1275
NEW_SYSTEM_TOTAL_RATE = NEW_SYSTEM_EMPLOYEE_RATE + NEW_SYSTEM_EMPLOYER_RATE  # 23.5%

NON_SAUDI_EMPLOYEE_RATE = 0.0
NON_SAUDI_EMPLOYER_RATE = 0.02

GOSI_SOURCES = [
    "GOSI Contributions in Saudi Arabia: 2026 Rates, Rules & Compliance Guide — Mercans "
    "(https://mercans.com/glossary/gosi-contributions/): Old System 21.5% total "
    "(employer 11.75%, employee 9.75%); New System July-Dec 2026 23.5% total (employer "
    "12.75%, employee 10.75%), up from 22.5% Jan-Jun 2026; contribution base capped at "
    "SAR 45,000/month (basic + housing).",
    "Saudi Arabia: GOSI Contribution Rates & SANED Unemployment Fund 2026 — Mercans "
    "(https://mercans.com/resources/statutory-alerts/saudi-arabia-gosi-contribution-rates-saned-unemployment-fund-2026/): "
    "confirms the July 2026 rate step and non-Saudi employees do not contribute from "
    "salary; employer pays 2% of contributable wage for occupational hazards only.",
    "Saudi GOSI 2026: Contribution Rates, Wage Ceiling, Deadlines — kiework "
    "(https://kiework.ai/compliance/gosi): confirms SAR 45,000/month wage ceiling applies "
    "identically to non-Saudi employer contributions (not uncapped, correcting this "
    "module's original brief).",
    "The July 2026 GOSI Rate Increase: Mandatory Saudi Payroll Rules — Saudi Compliance "
    "Institute (https://saudicomplianceinstitute.com/en/blogs/news/july-2026-gosi-rate-increase-saudi-payroll-rules): "
    "confirms New System component breakdown (pension 10%+10%, occupational hazards 2% "
    "employer only, SANED 0.75%+0.75%) and the annual 0.5-point rise every July through 2028.",
    "Saudi Social Insurance GOSI Rates 2026 — Silberson "
    "(https://www.silberson.com/2025/09/saudi-social-insurance-law-2025/): confirms Old "
    "System component breakdown (retirement 9%+9%, occupational hazards 2% employer, "
    "unemployment 0.75%+0.75%).",
    "Sources disagree on the exact FINAL July 2028 endpoint split (figures found ranged "
    "from 24% to 25% combined) — this module deliberately does NOT hardcode a future rate "
    "table and instructs users to reconfirm current rates via GOSI/Ta'meenati directly.",
]

GOSI_DISCLAIMER_EN = (
    "These figures compute REAL government social-insurance contribution amounts based on "
    "current published GOSI rates for the period " + GOSI_EFFECTIVE_PERIOD + " — they are "
    "NOT illustrative planning estimates like other modules on this platform. GOSI New "
    "System rates rise on a fixed annual schedule every July; reconfirm the currently "
    "applicable rate directly via GOSI/Ta'meenati before relying on this figure for any "
    "actual payroll, budgeting, or compliance action, especially outside the stated "
    "effective period. This module never substitutes an estimated salary when a real "
    "numeric wage isn't available — see the numeric-salary requirement below."
)
GOSI_DISCLAIMER_AR = (
    "تحتسب هذه الأرقام مبالغ اشتراكات تأمينية حكومية حقيقية استناداً إلى معدلات التأمينات "
    "الاجتماعية (GOSI) المنشورة حالياً لفترة " + GOSI_EFFECTIVE_PERIOD + " — وهي ليست "
    "تقديرات تخطيطية إرشادية كباقي وحدات هذه المنصة. ترتفع معدلات النظام الجديد وفق جدول "
    "سنوي ثابت كل يوليو؛ يرجى التحقق من المعدل الحالي المطبق مباشرة عبر التأمينات "
    "الاجتماعية (تأميناتي) قبل الاعتماد على هذا الرقم في أي إجراء فعلي للرواتب أو التخطيط "
    "أو الامتثال، خصوصاً خارج الفترة المذكورة. لا تستبدل هذه الوحدة أبداً راتباً تقديرياً "
    "عند عدم توفر راتب رقمي حقيقي."
)

_NUMERIC_SALARY_NOTE_EN = (
    "GOSI contributions are a real government-owed amount, so this module requires an "
    "exact numeric salary — it never uses a range-text midpoint. Rows where salary could "
    "not be read as a clean number are excluded from computed figures, not approximated."
)
_NUMERIC_SALARY_NOTE_AR = (
    "اشتراكات التأمينات الاجتماعية مبلغ حكومي مستحق فعلياً، لذا تتطلب هذه الوحدة راتباً "
    "رقمياً دقيقاً — ولا تستخدم أبداً متوسط نطاق نصي. تُستبعد الصفوف التي تعذّرت قراءة "
    "الراتب فيها كرقم صريح من الأرقام المحتسبة، ولا تُقدَّر تقريبياً."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _safe_record_id(raw_id: Any) -> str:
    h = hashlib.sha256(str(raw_id).encode()).hexdigest()[:6].upper()
    return f"EMP-{h}"


def _classify_saudi_status(raw: object) -> Optional[bool]:
    """True=Saudi, False=non-Saudi, None=unclassifiable (never guessed)."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _SAUDI_TOKENS:
        return True
    if key in _EXPLICIT_NON_SAUDI_TOKENS:
        return False
    return False  # any other real nationality value is non-Saudi


def _classify_gosi_system(raw: object) -> Optional[str]:
    """Returns 'old' | 'new' | None (unclassifiable/absent — never guessed)."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _OLD_SYSTEM_TOKENS:
        return "old"
    if key in _NEW_SYSTEM_TOKENS:
        return "new"
    for token in _OLD_SYSTEM_TOKENS:
        if token in key:
            return "old"
    for token in _NEW_SYSTEM_TOKENS:
        if token in key:
            return "new"
    return None


def _extract_strict_numeric_salary(df: pd.DataFrame, salary_col: Optional[str]) -> tuple[dict[Any, float], int, Optional[str]]:
    """Same strict "clean number or excluded, never approximated" rule as
    labor_law_calculators._extract_strict_numeric_salary(), reproduced
    locally per this codebase's per-module convention (see module
    docstring)."""
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


# ═════════════════════════════════════════════════════════════════════════
# Result types
# ═════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GosiCandidate:
    record_id_safe: str
    department: Optional[str]
    is_saudi: bool
    subject_wage_sar: float
    subject_wage_capped: bool
    old_system_employee_sar: Optional[float]
    old_system_employer_sar: Optional[float]
    old_system_total_sar: Optional[float]
    new_system_employee_sar: Optional[float]
    new_system_employer_sar: Optional[float]
    new_system_total_sar: Optional[float]
    applicable_system: str  # "old" | "new" | "unspecified_both_shown" | "non_saudi"
    applicable_employee_sar: float
    applicable_employer_sar: float
    applicable_total_sar: float
    # Phase 40 — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md
    # §3. This platform is used single-tenant on the uploader's own local
    # data, so the REAL uploaded ID (when present) is shown alongside
    # record_id_safe (kept unchanged for cross-link compatibility), rather
    # than only a hash the user can't cross-reference against their own file.
    employee_id_raw: Optional[str] = None


@dataclass(frozen=True)
class DepartmentGosiBreakdown:
    department: str
    n_employees: int
    total_employee_contribution_sar: float
    total_employer_contribution_sar: float
    total_contribution_sar: float


@dataclass(frozen=True)
class GosiResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    salary_column: Optional[str]
    housing_allowance_column: Optional[str]
    nationality_column: Optional[str]
    system_tier_column: Optional[str]
    department_column: Optional[str]
    housing_allowance_understated_note: Optional[str]
    n_employees_total: int
    n_valid_computed: int
    n_excluded_invalid_salary: int
    n_excluded_unclassifiable_nationality: int
    example_excluded_salary_value: Optional[str]
    candidates: list[GosiCandidate]
    n_candidates_truncated: int
    department_breakdown: list[DepartmentGosiBreakdown]
    department_normalization_notes: list[str]
    narrative_en: str
    narrative_ar: str
    numeric_salary_required_note_en: str
    numeric_salary_required_note_ar: str
    effective_period: str
    wage_cap_sar: float
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_gosi_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> GosiResult:
    return GosiResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        salary_column=None, housing_allowance_column=None, nationality_column=None,
        system_tier_column=None, department_column=None, housing_allowance_understated_note=None,
        n_employees_total=0, n_valid_computed=0, n_excluded_invalid_salary=0,
        n_excluded_unclassifiable_nationality=0, example_excluded_salary_value=None,
        candidates=[], n_candidates_truncated=0, department_breakdown=[],
        department_normalization_notes=[],
        narrative_en="GOSI contribution calculation not available for this dataset.",
        narrative_ar="حساب اشتراكات التأمينات الاجتماعية غير متاح لهذه البيانات.",
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        effective_period=GOSI_EFFECTIVE_PERIOD, wage_cap_sar=GOSI_WAGE_CAP_SAR,
        disclaimer_en=GOSI_DISCLAIMER_EN, disclaimer_ar=GOSI_DISCLAIMER_AR,
        governance_note=(
            "No GOSI figures are computed without an exact numeric salary and a "
            "classifiable nationality value for an employee — this platform never "
            "estimates a real government contribution amount."
        ),
        sources=GOSI_SOURCES, computed_at=_now(),
    )


def analyze_gosi_contributions(df: pd.DataFrame) -> GosiResult:
    """Never raises — exceptions should be caught by the caller and surfaced
    via unavailable_gosi_result."""
    if df is None or df.empty:
        return unavailable_gosi_result("No data available for GOSI calculation.")

    salary_col = _find_column(df, _SALARY_PATTERNS)
    housing_col = _find_column(df, _HOUSING_ALLOWANCE_PATTERNS)
    nationality_col = _find_column(df, _NATIONALITY_PATTERNS)
    system_col = _find_column(df, _GOSI_SYSTEM_TIER_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)

    columns_detected = {
        "salary": salary_col is not None,
        "nationality": nationality_col is not None,
        "housing_allowance": housing_col is not None,
        "gosi_system_tier": system_col is not None,
        "department": dept_col is not None,
    }

    if salary_col is None or nationality_col is None:
        missing = []
        if salary_col is None:
            missing.append("a numeric salary column")
        if nationality_col is None:
            missing.append("a nationality/Saudi-status column")
        return unavailable_gosi_result(
            f"GOSI calculation requires {' and '.join(missing)} — contribution rates "
            "differ radically by nationality and cannot be assumed for a real government "
            "contribution figure.",
            columns_detected,
        )

    salary_valid, n_excluded_salary, example_excluded = _extract_strict_numeric_salary(df, salary_col)
    housing_valid, _, _ = _extract_strict_numeric_salary(df, housing_col) if housing_col else ({}, 0, None)
    dept_result = normalize_department_series(df[dept_col].astype(object)) if dept_col else None
    dept_notes: list[str] = []
    dept_lookup: dict[Any, Optional[str]] = {}
    if dept_result is not None:
        for merge in dept_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_notes.append(f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}.")
        for grp in dept_result.unmerged_similar_variants:
            dept_notes.append(f"Found similarly-named but NOT merged department values {', '.join(repr(v) for v in grp)} — review manually.")
        keys = pd.Series(dept_result.normalized_keys.values, index=df.index)
        dept_lookup = {idx: dept_result.display_labels.get(keys.loc[idx], keys.loc[idx]) for idx in df.index}

    candidates: list[GosiCandidate] = []
    n_excluded_nationality = 0
    dept_agg: dict[str, dict[str, float]] = {}

    for idx in df.index:
        wage = salary_valid.get(idx)
        if wage is None:
            continue
        saudi_status = _classify_saudi_status(df.at[idx, nationality_col])
        if saudi_status is None:
            n_excluded_nationality += 1
            continue

        housing = housing_valid.get(idx, 0.0) if housing_col else 0.0
        raw_subject_wage = wage + housing
        subject_wage = min(raw_subject_wage, GOSI_WAGE_CAP_SAR)
        capped = raw_subject_wage > GOSI_WAGE_CAP_SAR

        record_id = _safe_record_id(df.at[idx, id_col]) if id_col is not None and not _is_missing_value(df.at[idx, id_col]) else f"ROW-{idx}"
        raw_id_display = str(df.at[idx, id_col]).strip() if id_col is not None and not _is_missing_value(df.at[idx, id_col]) else None
        dept = dept_lookup.get(idx)

        if saudi_status:
            old_employee = round(subject_wage * OLD_SYSTEM_EMPLOYEE_RATE, 2)
            old_employer = round(subject_wage * OLD_SYSTEM_EMPLOYER_RATE, 2)
            new_employee = round(subject_wage * NEW_SYSTEM_EMPLOYEE_RATE, 2)
            new_employer = round(subject_wage * NEW_SYSTEM_EMPLOYER_RATE, 2)

            tier = _classify_gosi_system(df.at[idx, system_col]) if system_col is not None else None
            if tier == "old":
                applicable_system = "old"
                applicable_employee, applicable_employer = old_employee, old_employer
            elif tier == "new":
                applicable_system = "new"
                applicable_employee, applicable_employer = new_employee, new_employer
            else:
                # Conservative default when unspecified — see module docstring.
                applicable_system = "unspecified_both_shown"
                applicable_employee, applicable_employer = new_employee, new_employer

            candidates.append(GosiCandidate(
                record_id_safe=record_id, department=dept, is_saudi=True,
                subject_wage_sar=subject_wage, subject_wage_capped=capped,
                old_system_employee_sar=old_employee, old_system_employer_sar=old_employer,
                old_system_total_sar=round(old_employee + old_employer, 2),
                new_system_employee_sar=new_employee, new_system_employer_sar=new_employer,
                new_system_total_sar=round(new_employee + new_employer, 2),
                applicable_system=applicable_system,
                applicable_employee_sar=applicable_employee, applicable_employer_sar=applicable_employer,
                applicable_total_sar=round(applicable_employee + applicable_employer, 2),
                employee_id_raw=raw_id_display,
            ))
        else:
            employer = round(subject_wage * NON_SAUDI_EMPLOYER_RATE, 2)
            candidates.append(GosiCandidate(
                record_id_safe=record_id, department=dept, is_saudi=False,
                subject_wage_sar=subject_wage, subject_wage_capped=capped,
                old_system_employee_sar=None, old_system_employer_sar=None, old_system_total_sar=None,
                new_system_employee_sar=None, new_system_employer_sar=None, new_system_total_sar=None,
                applicable_system="non_saudi",
                applicable_employee_sar=0.0, applicable_employer_sar=employer,
                applicable_total_sar=employer,
                employee_id_raw=raw_id_display,
            ))

        if dept:
            bucket = dept_agg.setdefault(dept, {"n": 0, "employee": 0.0, "employer": 0.0})
            bucket["n"] += 1
            bucket["employee"] += candidates[-1].applicable_employee_sar
            bucket["employer"] += candidates[-1].applicable_employer_sar

    if not candidates:
        detail = (
            f"Found a salary column ('{salary_col}') and a nationality column "
            f"('{nationality_col}'), but no single employee row had BOTH values as clean, "
            "usable — most commonly because the salary column uses range-text rather than "
            "exact figures, or the nationality value could not be classified."
        )
        if example_excluded:
            detail += f" Example unusable salary value from '{salary_col}': {example_excluded!r}."
        return unavailable_gosi_result(detail, columns_detected)

    department_breakdown = [
        DepartmentGosiBreakdown(
            department=dept, n_employees=int(b["n"]),
            total_employee_contribution_sar=round(b["employee"], 2),
            total_employer_contribution_sar=round(b["employer"], 2),
            total_contribution_sar=round(b["employee"] + b["employer"], 2),
        )
        for dept, b in dept_agg.items()
    ]
    department_breakdown.sort(key=lambda d: d.total_contribution_sar, reverse=True)

    candidates.sort(key=lambda c: c.applicable_total_sar, reverse=True)
    n_truncated = max(0, len(candidates) - _MAX_ROW_LEVEL_CANDIDATES)
    candidates_display = candidates[:_MAX_ROW_LEVEL_CANDIDATES]

    n_saudi = sum(1 for c in candidates if c.is_saudi)
    n_unspecified_system = sum(1 for c in candidates if c.applicable_system == "unspecified_both_shown")

    narrative_en = (
        f"{len(candidates)} of {len(df)} employees had both a clean numeric salary "
        f"({salary_col}) and a classifiable nationality ({nationality_col}) usable for a "
        f"real GOSI calculation — {n_saudi} Saudi, {len(candidates) - n_saudi} non-Saudi."
    )
    narrative_ar = (
        f"لدى {len(candidates)} من أصل {len(df)} موظفاً راتب رقمي دقيق ({salary_col}) "
        f"وجنسية قابلة للتصنيف ({nationality_col}) صالحة لحساب اشتراكات حقيقية — "
        f"{n_saudi} سعوديين و{len(candidates) - n_saudi} غير سعوديين."
    )
    if n_excluded_salary > 0:
        narrative_en += f" {n_excluded_salary} employee(s) excluded — salary value not a clean number."
        narrative_ar += f" استُبعد {n_excluded_salary} موظفاً — قيمة الراتب ليست رقماً صريحاً."
    if n_excluded_nationality > 0:
        narrative_en += f" {n_excluded_nationality} employee(s) excluded — nationality value not classifiable."
        narrative_ar += f" استُبعد {n_excluded_nationality} موظفاً — تعذّر تصنيف الجنسية."
    if system_col is None and n_saudi > 0:
        narrative_en += (
            " No GOSI system/tier column detected — both Old System and New System figures "
            "are shown for every Saudi employee; the New System (higher) figure is used as "
            "the applicable default for rollups."
        )
        narrative_ar += (
            " لم يتم اكتشاف عمود نظام التأمينات — تُعرض أرقام النظامين القديم والجديد لكل "
            "موظف سعودي؛ يُستخدم رقم النظام الجديد (الأعلى) كافتراضي في التجميعات."
        )
    elif n_unspecified_system > 0:
        narrative_en += f" {n_unspecified_system} Saudi employee(s) had an unclassifiable system value — both scenarios shown."
        narrative_ar += f" لدى {n_unspecified_system} موظفاً سعودياً قيمة نظام غير قابلة للتصنيف — عُرض كلا السيناريوهين."

    housing_note_en = housing_note_ar = None
    if housing_col is None:
        housing_note_en = (
            "No housing-allowance column detected — the GOSI subject wage below uses "
            "salary alone, which may understate the real contribution base for Saudi "
            "employees whose actual wage includes a separate housing allowance."
        )
        housing_note_ar = (
            "لم يتم اكتشاف عمود بدل سكن — يعتمد وعاء اشتراك التأمينات أدناه على الراتب "
            "فقط، وقد يكون أقل من الوعاء الفعلي للموظفين الذين لديهم بدل سكن منفصل."
        )

    return GosiResult(
        available=True, reason=None, columns_detected=columns_detected,
        salary_column=salary_col, housing_allowance_column=housing_col,
        nationality_column=nationality_col, system_tier_column=system_col, department_column=dept_col,
        housing_allowance_understated_note=housing_note_en if housing_note_en else None,
        n_employees_total=len(df), n_valid_computed=len(candidates),
        n_excluded_invalid_salary=n_excluded_salary,
        n_excluded_unclassifiable_nationality=n_excluded_nationality,
        example_excluded_salary_value=example_excluded,
        candidates=candidates_display, n_candidates_truncated=n_truncated,
        department_breakdown=department_breakdown, department_normalization_notes=dept_notes,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        effective_period=GOSI_EFFECTIVE_PERIOD, wage_cap_sar=GOSI_WAGE_CAP_SAR,
        disclaimer_en=GOSI_DISCLAIMER_EN, disclaimer_ar=GOSI_DISCLAIMER_AR,
        governance_note=(
            "No employee names are included — record_id_safe is a one-way hash. Salary "
            "values that were not clean numbers, and nationality values that could not be "
            "classified, were excluded, never estimated."
        ),
        sources=GOSI_SOURCES, computed_at=_now(),
    )


def gosi_result_to_dict(r: GosiResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "salary_column": r.salary_column, "housing_allowance_column": r.housing_allowance_column,
        "nationality_column": r.nationality_column, "system_tier_column": r.system_tier_column,
        "department_column": r.department_column,
        "housing_allowance_understated_note": r.housing_allowance_understated_note,
        "n_employees_total": r.n_employees_total, "n_valid_computed": r.n_valid_computed,
        "n_excluded_invalid_salary": r.n_excluded_invalid_salary,
        "n_excluded_unclassifiable_nationality": r.n_excluded_unclassifiable_nationality,
        "example_excluded_salary_value": r.example_excluded_salary_value,
        "candidates": [
            {
                "record_id_safe": c.record_id_safe, "employee_id_raw": c.employee_id_raw,
                "department": c.department, "is_saudi": c.is_saudi,
                "subject_wage_sar": c.subject_wage_sar, "subject_wage_capped": c.subject_wage_capped,
                "old_system_employee_sar": c.old_system_employee_sar,
                "old_system_employer_sar": c.old_system_employer_sar,
                "old_system_total_sar": c.old_system_total_sar,
                "new_system_employee_sar": c.new_system_employee_sar,
                "new_system_employer_sar": c.new_system_employer_sar,
                "new_system_total_sar": c.new_system_total_sar,
                "applicable_system": c.applicable_system,
                "applicable_employee_sar": c.applicable_employee_sar,
                "applicable_employer_sar": c.applicable_employer_sar,
                "applicable_total_sar": c.applicable_total_sar,
            }
            for c in r.candidates
        ],
        "n_candidates_truncated": r.n_candidates_truncated,
        "department_breakdown": [
            {"department": d.department, "n_employees": d.n_employees,
             "total_employee_contribution_sar": d.total_employee_contribution_sar,
             "total_employer_contribution_sar": d.total_employer_contribution_sar,
             "total_contribution_sar": d.total_contribution_sar}
            for d in r.department_breakdown
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "numeric_salary_required_note_en": r.numeric_salary_required_note_en,
        "numeric_salary_required_note_ar": r.numeric_salary_required_note_ar,
        "effective_period": r.effective_period, "wage_cap_sar": r.wage_cap_sar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }
