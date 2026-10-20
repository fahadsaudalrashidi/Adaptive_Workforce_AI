"""
Saudi Labor Law Calculators — Phase 21.

Three related, offline calculators: End-of-Service Gratuity (Part 1), a WPS/
Payroll internal consistency pre-check (Part 2), and Leave Balance &
Compensation (Part 3). Kept in one file — all three share the same strict
numeric-salary utility below, the same department-rollup reuse, and the same
"real legal payment, not an illustrative estimate" framing; splitting them
into three files would only duplicate that shared machinery three times
(the same reasoning `job_pattern_grouping_engine.py` used to keep its Excel
exporter alongside its analysis code rather than a separate file).

**Part 0 investigation (done before writing any of this): does real gratuity
logic already exist?** `saudi_data_governance.py` — despite being the file
named in the original brief — contains no gratuity calculation at all; its
"termination"/"separation" references are PII/leakage-detection field names
(post-outcome data-leakage guards), unrelated to Article 84 math.
`financial_intelligence_engine.py` DOES define real, correctly-sourced
constants — `ESG_SHORT_TENURE_PER_YEAR = 0.5` and `ESG_LONG_TENURE_PER_YEAR
= 1.0`, cited to "Saudi Labour Law — Article 84" — and `executive_roi_engine.py`
already imports and uses them (lines 50-51, 326-331) for a **portfolio-level
average-tenure ROI exposure estimate** (illustrative board-level "at-risk
liability" sizing, built on a sector/seniority BENCHMARK salary, not a real
per-employee wage). There is no per-employee, per-department gratuity
calculator anywhere, and — critically — no implementation of Article 85's
resignation reduction tiers at all. Conclusion: the base-formula CONSTANTS
are real and reused directly (imported below, not duplicated — the same
cross-import precedent `executive_roi_engine.py` already established for
these specific public constants); everything else (per-employee
calculation, resignation tiers, leave, WPS consistency) is built fresh here.

**Why this module is stricter about salary than every prior module this
session.** Every illustrative module so far (Overtime Cost Intelligence,
Sector Benchmarking, `financial_intelligence_engine.estimate_monthly_salary()`
itself) falls back to a sector/seniority BENCHMARK salary when a real salary
column isn't available — appropriate for planning-level estimates, where the
UI already frames the number as illustrative. End-of-Service Gratuity and
Leave Compensation are different in kind: they are the actual legally-owed
SAR amount a real person would actually receive or pay. Substituting a
benchmark estimate here would silently misrepresent a real legal figure as
if it were computed from the employee's actual wage. `_extract_strict_numeric_salary()`
below therefore does the opposite of `estimate_monthly_salary()`'s fallback
chain: if a salary value is not a clean, parseable number, it is EXCLUDED
from any legal-figure computation and disclosed — never approximated via a
range-text midpoint the way `saudi_attrition_normalizer.py` does for
illustrative figures elsewhere on this platform. Live-tested against the
real "Original Dataset of Employee Attrition" (see Phase 20's report for the
exact file path — not checked into this repo), whose `MonthlySalary` column
is 100% range-text ("From 5000 to 10000 S.R"): every legal figure in this
module correctly renders as unavailable on that data, not a fabricated
midpoint-based number. See the module's README-style report
(`PHASE_21_LABOR_LAW_CALCULATORS_REPORT.md`) for the live screenshot proving
this.

**Years-of-service column detection is deliberately narrower than
`job_pattern_grouping_engine.py`'s experience-band pattern**, for the same
legal-accuracy reason. The real attrition dataset has TWO experience-shaped
columns with different meanings: `Years_Experience` (total career
experience, any employer) and `Years_experience_lastorganization` (tenure at
THIS employer — the "last organisation" the record was pulled from, i.e.
the current one). End-of-Service Gratuity is legally computed on tenure AT
THE CURRENT EMPLOYER, not total career experience — using the wrong one
would produce a materially wrong legal figure. `_YEARS_OF_SERVICE_PATTERNS`
below is written to match `Years_experience_lastorganization` (via its
"...last organi[sz]ation" suffix) and common "at company"/"of service"/
"tenure" phrasings, while deliberately NOT matching a bare "Years_Experience"-
style column with no company/tenure/service qualifier — confirmed against
both real columns during live testing (see report).

**Wage base note.** Multiple independent sources (live-searched — see report
for citations) describe the Article 84/111 wage base as the worker's "last
actual wage" (basic salary + regular fixed allowances/commissions), not
"basic wage" alone. This module computes on whatever numeric salary column
is actually detected in the upload and DISCLOSES that column's name in every
result — it cannot know whether a given "Salary" column already includes
allowances or represents basic pay only, so it never claims to have used
"total wage" when it only observed one column. This caveat is rendered in
the UI, not just documented here.

**Phase 41 — date-based tenure takes priority over a supplied
years-of-service column.** `Copy of EOS Report.xlsx`'s "New" sheet computes
tenure as `(LastWorkingDay - DateOfJoining + 1) / 365` — an exact day count,
not a pre-rounded figure. When both a hire-date and a last-working-day (or,
for still-active employees, an "as of" snapshot date) column are present in
the upload, `_date_based_tenure_by_row()` replicates that exact formula and
its result is used in place of any `years_of_service`-pattern column for
that row — the dates are the more precise, more authoritative source when
both exist. The years-of-service column is used only as a per-row fallback,
for rows where no valid date pair is present. No rounding, business-day
adjustment, or other interpretation is added beyond the Excel's own formula
— see PHASE_28_EXACT_PRECISION_AND_DATE_BASED_TENURE.md.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series
from backend.core.financial_intelligence_engine import (
    ESG_LONG_TENURE_PER_YEAR,
    ESG_SHORT_TENURE_PER_YEAR,
)

# ── Column detection (local-regex convention, see every Phase 5-20 engine) ─

_ID_COLUMN_CANDIDATES = ("EmployeeID", "employee_id", "EmpID", "emp_id")

_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b", re.I,
)
# Reused verbatim from pay_equity_engine.py's _SALARY_PATTERNS.
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|annual[_\s]?salary|salary|wage|"
    r"compensation|basic[_\s]?pay|gross[_\s]?pay|"
    r"الراتب|الأجر|التعويض)\b", re.I,
)
# Deliberately narrower than job_pattern_grouping_engine.py's experience
# pattern — see module docstring for why (company tenure, not total career
# experience, is the legally relevant figure here).
_YEARS_OF_SERVICE_PATTERNS = re.compile(
    r"\b(years[_\s]?at[_\s]?company|years[_\s]?of[_\s]?service|service[_\s]?years|"
    r"tenure[_\s]?years|tenure|"
    r"years[_\s]?in[_\s]?(current[_\s]?)?(org|organi[sz]ation|company)|"
    r"years[_\s]?experience[_\s]?last[_\s]?organi[sz]ation|"
    r"سنوات[_\s]?الخدمة|مدة[_\s]?العمل)\b", re.I,
)
# Phase 41 addition — see PHASE_28_EXACT_PRECISION_AND_DATE_BASED_TENURE.md.
# Same local-regex convention as contract_expiry_engine.py's
# _CONTRACT_END_PATTERNS/_IQAMA_EXPIRY_PATTERNS (deliberately duplicated
# locally rather than imported — see that module's own comment on this).
# Two separate date signals, never conflated with contract_expiry_engine.py's
# own ContractEndDate detection: that module tracks a FUTURE contract
# expiry for planning; this one derives tenure from a hire date and an
# ALREADY-KNOWN last working day (or an as-of date for still-active staff).
_HIRE_DATE_PATTERNS = re.compile(
    r"\b(date[_\s]?of[_\s]?joining|joining[_\s]?date|hire[_\s]?date|hiredate|"
    r"start[_\s]?date|employment[_\s]?start[_\s]?date|"
    r"تاريخ[_\s]?التعيين|تاريخ[_\s]?الالتحاق|تاريخ[_\s]?المباشرة)\b", re.I,
)
_LAST_WORKING_DAY_PATTERNS = re.compile(
    r"\b(last[_\s]?working[_\s]?day|last[_\s]?working[_\s]?date|"
    r"last[_\s]?day[_\s]?worked|separation[_\s]?date|resignation[_\s]?date|"
    r"termination[_\s]?date|leaving[_\s]?date|end[_\s]?of[_\s]?service[_\s]?date|"
    r"تاريخ[_\s]?آخر[_\s]?يوم[_\s]?عمل|تاريخ[_\s]?الانفصال|تاريخ[_\s]?ترك[_\s]?العمل)\b", re.I,
)
# Fallback end-date signal for still-active employees, who have no real
# separation date yet — an explicit "as of" snapshot date stands in for
# D14 in the Excel formula (see module docstring's Phase 41 section).
_AS_OF_DATE_PATTERNS = re.compile(
    r"\b(as[_\s]?of[_\s]?date|analysis[_\s]?date|reporting[_\s]?date|snapshot[_\s]?date|"
    r"تاريخ[_\s]?التقرير|تاريخ[_\s]?اليوم)\b", re.I,
)
_SEPARATION_TYPE_PATTERNS = re.compile(
    r"\b(separation[_\s]?type|separation[_\s]?reason|termination[_\s]?type|"
    r"termination[_\s]?reason|exit[_\s]?type|leaving[_\s]?reason|"
    r"reason[_\s]?for[_\s]?leaving|attrition[_\s]?reason|"
    r"سبب[_\s]?الانفصال|نوع[_\s]?الإنهاء)\b", re.I,
)
_RESIGNATION_TOKENS = frozenset({
    "resignation", "resigned", "voluntary", "voluntary resignation", "quit", "استقالة",
})
_TERMINATION_TOKENS = frozenset({
    "termination", "terminated", "dismissal", "dismissed", "involuntary",
    "layoff", "laid off", "end of contract", "contract end", "contract ended",
    "إنهاء", "فصل", "انتهاء العقد",
})
# Phase 39 addition — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md §1.
# Distinguishing "Termination (80)" from ordinary "Termination" was found to be
# legally significant, not a synonym: this platform's authoritative reference
# file (Copy of EOS Report.xlsx, sheet "نموذج يدوي" cell K11 / sheet "نهاية
# الخدمة" cell I11) lists "Termination (80)" as its own selectable separation
# type, distinct from ordinary "EndOfContract"/generic termination. Live search
# confirms Article 80 lets an employer dismiss for one of 9 specific
# for-cause grounds WITHOUT notice, gratuity, or indemnity — a real forfeiture,
# not the "full award" every OTHER termination reason gets under this module.
# Checked BEFORE the generic _TERMINATION_TOKENS fallback (see
# _classify_separation_type) since "Termination (80)" would otherwise substring-
# match the generic "termination" token first.
_ARTICLE_80_TOKENS = frozenset({
    "termination (80)", "termination(80)", "art 80", "art. 80", "article 80",
    "dismissal for cause", "dismissed for cause", "gross misconduct", "misconduct",
    "المادة 80", "فصل تأديبي", "إنهاء تأديبي", "فصل بدون مكافأة",
})

# Part 2 — WPS/payroll consistency columns.
_CONTRACT_BASIC_SALARY_PATTERNS = re.compile(
    r"\b(contract[_\s]?salary|contractual[_\s]?salary|basic[_\s]?salary|"
    r"base[_\s]?salary|basic[_\s]?wage|"
    r"الراتب[_\s]?الأساسي|الراتب[_\s]?التعاقدي)\b", re.I,
)
_ACTUAL_PAID_SALARY_PATTERNS = re.compile(
    r"\b(actual[_\s]?paid[_\s]?salary|actual[_\s]?salary|paid[_\s]?salary|"
    r"net[_\s]?salary|disbursed[_\s]?salary|total[_\s]?salary|gross[_\s]?salary|"
    r"الراتب[_\s]?الفعلي|الراتب[_\s]?المدفوع|صافي[_\s]?الراتب)\b", re.I,
)
_ALLOWANCES_PATTERNS = re.compile(
    r"\b(allowances?|housing[_\s]?allowance|transport[_\s]?allowance|بدلات|البدلات)\b", re.I,
)

# Part 3 — leave columns. Balance and taken are two separate signals, same
# "never conflate" principle contract_expiry_engine.py established.
#
# Phase 23 fix: the original pattern's trailing `\b` broke on real
# PascalCase/camelCase column names where a suffix word immediately follows
# the core keyword with no separator (e.g. "LeaveBalanceDays" — no boundary
# exists between "Balance" and "Days" since both are word characters, so
# `\bleave[_\s]?balance\b` never matched even though "LeaveBalance" is a
# substring). Fixed by making the trailing suffix word an explicit optional
# part of each alternative (`([_\s]?days)?`) so the `\b` correctly lands at
# the true end of the compound phrase, plus added alternatives for
# real-world word orders/synonyms this narrow pattern was missing entirely
# (AnnualLeaveBalance, RemainingLeaveDays, LeaveDaysTaken, UsedLeaveDays) —
# see PHASE_23_LEAVE_BALANCE_DETECTION_FIX.md for the full trace.
_LEAVE_BALANCE_PATTERNS = re.compile(
    r"\b((annual[_\s]?)?leave[_\s]?balance([_\s]?days)?|"
    r"remaining[_\s]?leave([_\s]?days)?|"
    r"leave[_\s]?days[_\s]?remaining|"
    r"رصيد[_\s]?الإجاز(?:ات|ة)([_\s]?السنوية)?)\b", re.I,
)
# Phase 42 fix: same structural flaw as the Phase 23 balance-pattern fix
# above, on the trailing side instead — a real-world column name
# ("LeaveDaysTakenThisYear") has a suffix word immediately following "Taken"
# with no separator, so the old trailing `\b` never found a boundary there
# and the whole pattern failed to match. Also added the "annual" prefix
# variant (AnnualLeaveTaken) mirroring _LEAVE_BALANCE_PATTERNS' existing
# `(annual[_\s]?)?` handling. Fixed the same way as Phase 23: make the extra
# word an explicit optional part of the alternative instead of leaving it
# outside the match. See PHASE_42_LEAVE_TAKEN_DETECTION_FIX.md.
_LEAVE_TAKEN_PATTERNS = re.compile(
    r"\b((annual[_\s]?)?leave[_\s]?taken([_\s]?this[_\s]?year)?|leave[_\s]?used|leave[_\s]?days[_\s]?used|"
    r"leave[_\s]?days[_\s]?taken([_\s]?this[_\s]?year)?|used[_\s]?leave([_\s]?days)?|"
    r"taken[_\s]?leave([_\s]?days)?|"
    r"الإجاز(?:ات|ة)[_\s]?المستخدمة)\b", re.I,
)

_MAX_ROW_LEVEL_CANDIDATES = 100

STRICT_SALARY_CONFIDENCE = "real_legal_payment_not_illustrative_estimate"

LABOR_LAW_DISCLAIMER_EN = (
    "These figures compute REAL amounts owed under Saudi Labor Law based on the data "
    "in your upload — they are NOT illustrative planning estimates like other modules "
    "on this platform. For that reason, this module never substitutes a benchmark or "
    "estimated salary when a real numeric wage isn't available — see the numeric-salary "
    "requirement below. This is a computational aid for HR planning, not a substitute "
    "for qualified legal/HR review before any actual payment or compliance action. "
    "Article citations are provided for reference; always confirm current provisions "
    "with qualified counsel before acting on these figures."
)
LABOR_LAW_DISCLAIMER_AR = (
    "تحتسب هذه الأرقام مبالغ حقيقية مستحقة بموجب نظام العمل السعودي استناداً إلى "
    "بياناتك المُحمّلة — وهي ليست تقديرات تخطيطية إرشادية كباقي وحدات هذه المنصة. "
    "لهذا السبب، لا تستبدل هذه الوحدة أبداً راتباً تقديرياً أو معيارياً عند عدم توفر "
    "راتب رقمي حقيقي — انظر شرط الراتب الرقمي أدناه. هذه أداة حسابية مساعدة لتخطيط "
    "الموارد البشرية، وليست بديلاً عن المراجعة القانونية المتخصصة قبل أي دفعة أو "
    "إجراء امتثال فعلي. الاستشهادات بالمواد النظامية لغرض المرجعية فقط — يرجى دائماً "
    "التحقق من الأحكام الحالية مع مستشار قانوني مختص قبل التصرف بناءً على هذه الأرقام."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _is_missing_value(raw: object) -> bool:
    """Same missing-value discipline as department_normalizer.py's
    _is_missing_department()."""
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _safe_record_id(raw_id: Any) -> str:
    """Same one-way-hash scheme as every other cross-link-participating
    engine this session (employee_risk_scoring.py's _make_record_id())."""
    h = hashlib.sha256(str(raw_id).encode()).hexdigest()[:6].upper()
    return f"EMP-{h}"


def _raw_id_display(df: pd.DataFrame, idx: Any, id_col: Optional[str]) -> Optional[str]:
    """Phase 40 — see PHASE_27 report §3. This platform is used single-
    tenant on the uploader's own local data, so the REAL uploaded ID (when
    present) is more useful to display than record_id_safe's hash, which
    the user can't cross-reference against their own spreadsheet.
    record_id_safe itself is kept unchanged everywhere (still used for
    cross-link joins) — this only supplies an additional display value,
    never fabricated when no real ID column exists."""
    if id_col is None or _is_missing_value(df.at[idx, id_col]):
        return None
    return str(df.at[idx, id_col]).strip()


def _classify_separation_type(raw: object) -> Optional[str]:
    """Returns 'resignation' | 'employer_termination_or_end_of_contract' |
    'termination_for_cause_article_80' | None (unclassifiable — never
    guessed). Article-80 tokens are checked BEFORE the generic termination
    fallback — "Termination (80)" contains the substring "termination" and
    would otherwise be silently absorbed into the ordinary full-award
    bucket, exactly the discrepancy PHASE_27's Excel reconciliation found."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _RESIGNATION_TOKENS:
        return "resignation"
    if key in _ARTICLE_80_TOKENS:
        return "termination_for_cause_article_80"
    if key in _TERMINATION_TOKENS:
        return "employer_termination_or_end_of_contract"
    for token in _RESIGNATION_TOKENS:
        if token in key:
            return "resignation"
    for token in _ARTICLE_80_TOKENS:
        if token in key:
            return "termination_for_cause_article_80"
    for token in _TERMINATION_TOKENS:
        if token in key:
            return "employer_termination_or_end_of_contract"
    return None


# ── Strict numeric-salary extraction (shared by all 3 parts) ───────────────

@dataclass(frozen=True)
class StrictSalaryExtraction:
    salary_column: Optional[str]
    valid_by_row: dict[Any, float]      # df index -> clean numeric wage
    n_total_rows: int
    n_valid: int
    n_excluded_non_numeric: int
    example_excluded_raw_value: Optional[str]


def _extract_strict_numeric_salary(df: pd.DataFrame, salary_col: Optional[str]) -> StrictSalaryExtraction:
    """
    Unlike financial_intelligence_engine.estimate_monthly_salary() (which
    falls back to a sector/seniority benchmark for illustrative cost
    planning), this NEVER substitutes an estimate. A row's salary is used
    only if it parses as a clean number; every other row is excluded and
    counted, with one example raw value preserved (not PII — a data-shape
    example, e.g. "From 5000 to 10000 S.R") so the UI can explain WHY rather
    than just saying "invalid." See module docstring.
    """
    if salary_col is None:
        return StrictSalaryExtraction(None, {}, len(df), 0, 0, None)

    raw_series = df[salary_col]
    numeric = pd.to_numeric(raw_series, errors="coerce")
    valid_by_row: dict[Any, float] = {}
    example_excluded: Optional[str] = None
    n_excluded = 0
    for idx in df.index:
        val = numeric.loc[idx]
        if pd.notna(val) and float(val) > 0:
            valid_by_row[idx] = float(val)
        else:
            raw_val = raw_series.loc[idx]
            if not _is_missing_value(raw_val):
                n_excluded += 1
                if example_excluded is None:
                    example_excluded = str(raw_val).strip()
            elif pd.notna(val) is False and not _is_missing_value(raw_val):
                n_excluded += 1

    return StrictSalaryExtraction(
        salary_column=salary_col,
        valid_by_row=valid_by_row,
        n_total_rows=len(df),
        n_valid=len(valid_by_row),
        n_excluded_non_numeric=n_excluded,
        example_excluded_raw_value=example_excluded,
    )


def _years_of_service_by_row(df: pd.DataFrame, years_col: Optional[str]) -> dict[Any, float]:
    if years_col is None:
        return {}
    numeric = pd.to_numeric(df[years_col], errors="coerce")
    return {idx: float(numeric.loc[idx]) for idx in df.index if pd.notna(numeric.loc[idx]) and float(numeric.loc[idx]) >= 0}


def _date_based_tenure_by_row(df: pd.DataFrame, hire_col: Optional[str], end_col: Optional[str]) -> dict[Any, float]:
    """Exact replica of `Copy of EOS Report.xlsx`'s "New" sheet formula chain
    (D15 = D14-D13+1, F15 = D15/365) — see module docstring's Phase 41
    section. Only rows where BOTH dates parse cleanly get a value; nothing
    is guessed for a partially-missing date pair."""
    if hire_col is None or end_col is None:
        return {}
    hire = pd.to_datetime(df[hire_col], errors="coerce")
    end = pd.to_datetime(df[end_col], errors="coerce")
    result: dict[Any, float] = {}
    for idx in df.index:
        h, e = hire.loc[idx], end.loc[idx]
        if pd.isna(h) or pd.isna(e):
            continue
        days = (e - h).days + 1
        result[idx] = days / 365
    return result


def _resolve_years_of_service(
    df: pd.DataFrame,
    years_col: Optional[str],
    hire_col: Optional[str],
    end_col: Optional[str],
) -> tuple[dict[Any, float], int, int]:
    """Combines the two tenure sources with dates taking priority per row —
    see module docstring's Phase 41 section. Returns
    (years_by_row, n_excluded_no_usable_source, n_from_dates)."""
    column_based = _years_of_service_by_row(df, years_col)
    date_based = _date_based_tenure_by_row(df, hire_col, end_col)
    combined = {**column_based, **date_based}  # date-based wins per row

    n_excluded = 0
    for idx in df.index:
        if idx in combined:
            continue
        had_years_raw = years_col is not None and not _is_missing_value(df.at[idx, years_col])
        had_dates_raw = (
            hire_col is not None and end_col is not None
            and not _is_missing_value(df.at[idx, hire_col])
            and not _is_missing_value(df.at[idx, end_col])
        )
        if had_years_raw or had_dates_raw:
            n_excluded += 1

    return combined, n_excluded, len(date_based)


def _department_lookup(df: pd.DataFrame, dept_col: Optional[str]) -> tuple[dict[Any, Optional[str]], list[str]]:
    """Returns ({row_index: department_display_label}, normalization_notes)."""
    if dept_col is None:
        return {}, []
    result = normalize_department_series(df[dept_col].astype(object))
    notes: list[str] = []
    for merge in result.merges_applied:
        variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
        notes.append(f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}.")
    for grp in result.unmerged_similar_variants:
        notes.append(f"Found similarly-named but NOT merged department values {', '.join(repr(v) for v in grp)} — review manually.")
    keys = pd.Series(result.normalized_keys.values, index=df.index)
    lookup = {idx: result.display_labels.get(keys.loc[idx], keys.loc[idx]) for idx in df.index}
    return lookup, notes


# ═════════════════════════════════════════════════════════════════════════
# PART 1 — End-of-Service Gratuity (Articles 84, 85, 87)
# ═════════════════════════════════════════════════════════════════════════

# Article 85 resignation reduction tiers — exact text confirmed via live
# search (see PHASE_21_LABOR_LAW_CALCULATORS_REPORT.md for sources):
# "<2 years: none; 2-5 years (inclusive): one-third; more than 5 but less
# than 10 years: two-thirds; 10+ years: full award."
_RESIGNATION_FRACTION_UNDER_2Y = 0.0
_RESIGNATION_FRACTION_2_TO_5Y = 1.0 / 3.0
_RESIGNATION_FRACTION_5_TO_10Y = 2.0 / 3.0
_RESIGNATION_FRACTION_10Y_PLUS = 1.0

GRATUITY_SOURCES = [
    "Saudi Labor Law (Royal Decree M/51) Article 84 — base formula: half a month's wage "
    "per year for the first 5 years of service, a full month's wage per year thereafter, "
    "prorated for partial years, computed on the worker's last actual wage.",
    "Saudi Labor Law Article 85 — resignation reduction tiers: <2 years service = no "
    "gratuity; 2-5 years = one-third of the full award; more than 5 but less than 10 "
    "years = two-thirds; 10+ years = full award.",
    "Saudi Labor Law Article 87 — full award exceptions (force majeure beyond the "
    "worker's control; a female worker ending her contract within 6 months of marriage "
    "or 3 months of childbirth) are NOT computed by this module — the underlying reason "
    "for separation beyond resignation/termination is not reliably present in typical "
    "HR export data, so this module never guesses at Article 87 eligibility.",
    "ESG_SHORT_TENURE_PER_YEAR / ESG_LONG_TENURE_PER_YEAR constants reused verbatim "
    "from financial_intelligence_engine.py (already cited there to Article 84).",
    "Live web search performed this phase to confirm these provisions are current — "
    "see PHASE_21_LABOR_LAW_CALCULATORS_REPORT.md for the exact sources retrieved.",
    "Saudi Labor Law Article 80 — an employer may dismiss a worker WITHOUT notice, "
    "gratuity, or indemnity for one of 9 specific for-cause grounds (serious misconduct, "
    "dishonesty, assault, unauthorized absence, etc.), subject to giving the worker a "
    "chance to respond first; courts interpret these grounds narrowly. Multiple secondary "
    "law-firm sources (not a directly-quoted statute excerpt, unlike Articles 84/85 above "
    "— see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md §1 for the exact "
    "sources and this caveat) describe an Article 87 exception preserving HALF the award "
    "for workers with 5+ years of service even under an Article 80 dismissal. This "
    "module NEVER auto-applies this forfeiture to applicable_amount_sar — it only "
    "surfaces article_80_reduced_award_sar as an additional disclosed data point when a "
    "separation-type value indicates Article 80 (e.g. 'Termination (80)', matching this "
    "platform's own authoritative reference file's own terminology) — actual forfeiture "
    "requires verified compliance with Article 80's specific grounds and procedure, which "
    "no bare text classification can confirm.",
]


def _resignation_fraction(years: float) -> float:
    if years < 2:
        return _RESIGNATION_FRACTION_UNDER_2Y
    if years <= 5:
        return _RESIGNATION_FRACTION_2_TO_5Y
    if years < 10:
        return _RESIGNATION_FRACTION_5_TO_10Y
    return _RESIGNATION_FRACTION_10Y_PLUS


def _base_gratuity_sar(monthly_wage: float, years: float) -> float:
    if years <= 5:
        return monthly_wage * years * ESG_SHORT_TENURE_PER_YEAR
    return (
        monthly_wage * 5 * ESG_SHORT_TENURE_PER_YEAR
        + monthly_wage * (years - 5) * ESG_LONG_TENURE_PER_YEAR
    )


@dataclass(frozen=True)
class GratuityCandidate:
    record_id_safe: str
    department: Optional[str]
    years_of_service: float
    monthly_wage_sar: float
    separation_type: Optional[str]
    gratuity_full_award_sar: float
    gratuity_if_resignation_sar: float
    applicable_amount_sar: float
    applicable_scenario: str  # "resignation" | "full_termination" | "unspecified_both_shown" | "termination_for_cause_article_80_flagged"
    # Phase 39 — see GRATUITY_SOURCES' Article 80 entry. Populated only when
    # separation_type == "termination_for_cause_article_80": 0 if years<5,
    # else half of gratuity_full_award_sar. NEVER folded into
    # applicable_amount_sar automatically — disclosed separately since this
    # provision is less certain than Articles 84/85 (see sources) and actual
    # forfeiture requires verified Article 80 compliance this module cannot confirm.
    article_80_reduced_award_sar: Optional[float] = None
    # Phase 40 — see _raw_id_display()'s docstring and PHASE_27 report §3.
    employee_id_raw: Optional[str] = None


@dataclass(frozen=True)
class DepartmentGratuityBreakdown:
    department: str
    n_employees: int
    total_full_award_sar: float
    total_if_resignation_sar: float


@dataclass(frozen=True)
class GratuityResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    salary_column: Optional[str]
    years_of_service_column: Optional[str]
    separation_type_column: Optional[str]
    department_column: Optional[str]
    n_employees_total: int
    n_valid_computed: int
    n_excluded_invalid_salary: int
    n_excluded_invalid_years: int
    example_excluded_salary_value: Optional[str]
    candidates: list[GratuityCandidate]
    n_candidates_truncated: int
    department_breakdown: list[DepartmentGratuityBreakdown]
    department_normalization_notes: list[str]
    narrative_en: str
    narrative_ar: str
    numeric_salary_required_note_en: str
    numeric_salary_required_note_ar: str
    confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str
    # Phase 41 — see module docstring. hire_date_column/last_working_day_column
    # are populated only when BOTH are detected; n_tenure_computed_from_dates
    # counts rows whose years_of_service came from that exact-day-count
    # formula rather than years_of_service_column.
    hire_date_column: Optional[str] = None
    last_working_day_column: Optional[str] = None
    n_tenure_computed_from_dates: int = 0


_NUMERIC_SALARY_NOTE_EN = (
    "End-of-Service Gratuity is a real legal payment amount, so this module requires an "
    "exact numeric salary — it never uses a range-text midpoint (e.g. 'From 5000 to "
    "10000 SAR' -> ~7500) the way illustrative modules elsewhere on this platform do. "
    "Rows where salary and/or years-of-service could not be read as clean numbers are "
    "excluded from computed figures, not approximated."
)
_NUMERIC_SALARY_NOTE_AR = (
    "مكافأة نهاية الخدمة مبلغ قانوني حقيقي، لذا تتطلب هذه الوحدة راتباً رقمياً دقيقاً — "
    "ولا تستخدم أبداً متوسط نطاق نصي (مثال: 'من 5000 إلى 10000 ريال' -> ~7500) كما تفعل "
    "الوحدات الإرشادية الأخرى في هذه المنصة. تُستبعد الصفوف التي تعذّرت قراءة الراتب "
    "و/أو سنوات الخدمة فيها كأرقام صريحة من الأرقام المحتسبة، ولا تُقدَّر تقريبياً."
)


def unavailable_gratuity_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> GratuityResult:
    return GratuityResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        salary_column=None, years_of_service_column=None, separation_type_column=None,
        department_column=None, n_employees_total=0, n_valid_computed=0,
        n_excluded_invalid_salary=0, n_excluded_invalid_years=0,
        example_excluded_salary_value=None, candidates=[], n_candidates_truncated=0,
        department_breakdown=[], department_normalization_notes=[],
        narrative_en="End-of-Service Gratuity calculation not available for this dataset.",
        narrative_ar="حساب مكافأة نهاية الخدمة غير متاح لهذه البيانات.",
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        confidence=STRICT_SALARY_CONFIDENCE,
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note=(
            "No gratuity figures are computed or displayed without an exact numeric "
            "salary and years-of-service value for an employee — this platform never "
            "estimates a real legal payment amount."
        ),
        sources=GRATUITY_SOURCES, computed_at=_now(),
    )


def analyze_gratuity(df: pd.DataFrame) -> GratuityResult:
    """Never raises — exceptions should be caught by the caller and surfaced
    via unavailable_gratuity_result."""
    if df is None or df.empty:
        return unavailable_gratuity_result("No data available for gratuity calculation.")

    salary_col = _find_column(df, _SALARY_PATTERNS)
    years_col = _find_column(df, _YEARS_OF_SERVICE_PATTERNS)
    hire_col = _find_column(df, _HIRE_DATE_PATTERNS)
    end_col = _find_column(df, _LAST_WORKING_DAY_PATTERNS) or _find_column(df, _AS_OF_DATE_PATTERNS)
    sep_col = _find_column(df, _SEPARATION_TYPE_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)

    has_dates = hire_col is not None and end_col is not None
    columns_detected = {
        "salary": salary_col is not None,
        "years_of_service": years_col is not None,
        "hire_date": hire_col is not None,
        "last_working_day": end_col is not None,
        "separation_type": sep_col is not None,
        "department": dept_col is not None,
    }

    if salary_col is None or (years_col is None and not has_dates):
        missing = []
        if salary_col is None:
            missing.append("a numeric salary column")
        if years_col is None and not has_dates:
            missing.append("a years-of-service column (or hire-date + last-working-day columns)")
        return unavailable_gratuity_result(
            f"Gratuity calculation requires {' and '.join(missing)} — neither can be "
            "assumed for a real legal payment figure.",
            columns_detected,
        )

    salary_extract = _extract_strict_numeric_salary(df, salary_col)
    years_by_row, n_excluded_years, n_from_dates = _resolve_years_of_service(df, years_col, hire_col, end_col)
    dept_lookup, dept_notes = _department_lookup(df, dept_col)

    candidates: list[GratuityCandidate] = []
    dept_agg: dict[str, dict[str, float]] = {}
    for idx in df.index:
        wage = salary_extract.valid_by_row.get(idx)
        years = years_by_row.get(idx)
        if wage is None or years is None:
            continue

        full_award = round(_base_gratuity_sar(wage, years), 2)
        resignation_amount = round(full_award * _resignation_fraction(years), 2)

        sep_type = _classify_separation_type(df.at[idx, sep_col]) if sep_col is not None else None
        article_80_reduced: Optional[float] = None
        if sep_type == "resignation":
            applicable, scenario = resignation_amount, "resignation"
        elif sep_type == "termination_for_cause_article_80":
            # Never auto-reduced — see GratuityCandidate.article_80_reduced_award_sar
            # docstring and GRATUITY_SOURCES' Article 80 entry.
            applicable, scenario = full_award, "termination_for_cause_article_80_flagged"
            article_80_reduced = 0.0 if years < 5 else round(full_award * 0.5, 2)
        elif sep_type == "employer_termination_or_end_of_contract":
            applicable, scenario = full_award, "full_termination"
        else:
            applicable, scenario = full_award, "unspecified_both_shown"

        record_id = _safe_record_id(df.at[idx, id_col]) if id_col is not None and not _is_missing_value(df.at[idx, id_col]) else f"ROW-{idx}"
        dept = dept_lookup.get(idx)

        candidates.append(GratuityCandidate(
            record_id_safe=record_id, department=dept, years_of_service=years,
            monthly_wage_sar=wage, separation_type=sep_type,
            gratuity_full_award_sar=full_award, gratuity_if_resignation_sar=resignation_amount,
            applicable_amount_sar=applicable, applicable_scenario=scenario,
            article_80_reduced_award_sar=article_80_reduced,
            employee_id_raw=_raw_id_display(df, idx, id_col),
        ))

        if dept:
            bucket = dept_agg.setdefault(dept, {"n": 0, "full": 0.0, "resign": 0.0})
            bucket["n"] += 1
            bucket["full"] += full_award
            bucket["resign"] += resignation_amount

    years_source_desc_en = years_col if years_col else f"{hire_col} → {end_col}"
    years_source_desc_ar = years_col if years_col else f"{hire_col} ← {end_col}"

    if not candidates:
        detail = (
            f"Found a salary column ('{salary_col}') and a tenure source "
            f"('{years_source_desc_en}'), but no single employee row had BOTH values as "
            "clean, usable numbers — most commonly because the salary column uses "
            "range-text (e.g. 'From 5000 to 10000 SAR') rather than exact figures."
        )
        if salary_extract.example_excluded_raw_value:
            detail += f" Example unusable salary value from '{salary_col}': {salary_extract.example_excluded_raw_value!r}."
        return unavailable_gratuity_result(detail, columns_detected)

    department_breakdown = [
        DepartmentGratuityBreakdown(
            department=dept, n_employees=int(b["n"]),
            total_full_award_sar=round(b["full"], 2), total_if_resignation_sar=round(b["resign"], 2),
        )
        for dept, b in dept_agg.items()
    ]
    department_breakdown.sort(key=lambda d: d.total_full_award_sar, reverse=True)

    candidates.sort(key=lambda c: c.applicable_amount_sar, reverse=True)
    n_truncated = max(0, len(candidates) - _MAX_ROW_LEVEL_CANDIDATES)
    candidates_display = candidates[:_MAX_ROW_LEVEL_CANDIDATES]

    narrative_en = (
        f"{len(candidates)} of {len(df)} employees had both a clean numeric salary "
        f"({salary_col}) and years of service ({years_source_desc_en}) usable for a real "
        f"gratuity calculation."
    )
    narrative_ar = (
        f"لدى {len(candidates)} من أصل {len(df)} موظفاً راتب رقمي دقيق ({salary_col}) "
        f"وسنوات خدمة ({years_source_desc_ar}) صالحة لحساب مكافأة نهاية الخدمة الحقيقية."
    )
    if salary_extract.n_excluded_non_numeric > 0:
        narrative_en += (
            f" {salary_extract.n_excluded_non_numeric} employee(s) excluded — salary "
            f"value not a clean number (e.g. {salary_extract.example_excluded_raw_value!r})."
        )
        narrative_ar += f" استُبعد {salary_extract.n_excluded_non_numeric} موظفاً — قيمة الراتب ليست رقماً صريحاً."
    if n_excluded_years > 0:
        narrative_en += f" {n_excluded_years} employee(s) excluded — years-of-service value not a clean number."
        narrative_ar += f" استُبعد {n_excluded_years} موظفاً — قيمة سنوات الخدمة ليست رقماً صريحاً."
    if n_from_dates > 0:
        narrative_en += (
            f" Tenure for {n_from_dates} employee(s) was computed from exact hire/"
            f"last-working-day dates ({hire_col} → {end_col}) rather than the "
            "years-of-service column, for full day-count precision — this takes "
            "priority over a provided years figure whenever both dates are present."
        )
        narrative_ar += (
            f" احتُسبت مدة الخدمة لـ {n_from_dates} موظفاً من تاريخي التعيين وآخر يوم "
            f"عمل الفعليين ({hire_col} ← {end_col}) بدلاً من عمود سنوات الخدمة، لأقصى "
            "دقة بعدد الأيام — ولها الأولوية على أي رقم سنوات مُقدَّم عند توفر التاريخين."
        )
    if sep_col is None:
        narrative_en += " No separation-type column detected — both resignation and full-termination figures are shown for every employee."
        narrative_ar += " لم يتم اكتشاف عمود نوع الانفصال — تُعرض أرقام الاستقالة والإنهاء الكامل لكل موظف."
    n_article_80 = sum(1 for c in candidates if c.separation_type == "termination_for_cause_article_80")
    if n_article_80 > 0:
        narrative_en += (
            f" {n_article_80} employee(s) have an Article 80 (for-cause dismissal) "
            "separation type — the full award is still shown as the applicable figure "
            "(never auto-reduced), with the possible Article 80 forfeiture amount "
            "disclosed separately; see the Article 80 source note before relying on it."
        )
        narrative_ar += (
            f" لدى {n_article_80} موظفاً نوع انفصال يشير إلى المادة 80 (الفصل التأديبي) "
            "— يظل المبلغ الكامل هو الرقم المُطبَّق (لا يُخفَّض تلقائياً أبداً)، مع الكشف "
            "عن مبلغ إسقاط المادة 80 المحتمل بشكل منفصل."
        )

    return GratuityResult(
        available=True, reason=None, columns_detected=columns_detected,
        salary_column=salary_col, years_of_service_column=years_col,
        separation_type_column=sep_col, department_column=dept_col,
        n_employees_total=len(df), n_valid_computed=len(candidates),
        n_excluded_invalid_salary=salary_extract.n_excluded_non_numeric,
        n_excluded_invalid_years=n_excluded_years,
        example_excluded_salary_value=salary_extract.example_excluded_raw_value,
        candidates=candidates_display, n_candidates_truncated=n_truncated,
        department_breakdown=department_breakdown, department_normalization_notes=dept_notes,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        confidence=STRICT_SALARY_CONFIDENCE,
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note=(
            "No employee names are included — record_id_safe is a one-way hash. Salary "
            "and years-of-service values that were not clean numbers were excluded, "
            "never estimated. Article 87 special-circumstance full-award exceptions "
            "(force majeure, marriage/childbirth) are not computed — see sources."
        ),
        hire_date_column=hire_col, last_working_day_column=end_col,
        n_tenure_computed_from_dates=n_from_dates,
        sources=GRATUITY_SOURCES, computed_at=_now(),
    )


def gratuity_to_dict(r: GratuityResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "salary_column": r.salary_column, "years_of_service_column": r.years_of_service_column,
        "hire_date_column": r.hire_date_column, "last_working_day_column": r.last_working_day_column,
        "n_tenure_computed_from_dates": r.n_tenure_computed_from_dates,
        "separation_type_column": r.separation_type_column, "department_column": r.department_column,
        "n_employees_total": r.n_employees_total, "n_valid_computed": r.n_valid_computed,
        "n_excluded_invalid_salary": r.n_excluded_invalid_salary,
        "n_excluded_invalid_years": r.n_excluded_invalid_years,
        "example_excluded_salary_value": r.example_excluded_salary_value,
        "candidates": [
            {
                "record_id_safe": c.record_id_safe, "employee_id_raw": c.employee_id_raw,
                "department": c.department,
                "years_of_service": c.years_of_service, "monthly_wage_sar": c.monthly_wage_sar,
                "separation_type": c.separation_type,
                "gratuity_full_award_sar": c.gratuity_full_award_sar,
                "gratuity_if_resignation_sar": c.gratuity_if_resignation_sar,
                "applicable_amount_sar": c.applicable_amount_sar,
                "applicable_scenario": c.applicable_scenario,
                "article_80_reduced_award_sar": c.article_80_reduced_award_sar,
            }
            for c in r.candidates
        ],
        "n_candidates_truncated": r.n_candidates_truncated,
        "department_breakdown": [
            {"department": d.department, "n_employees": d.n_employees,
             "total_full_award_sar": d.total_full_award_sar, "total_if_resignation_sar": d.total_if_resignation_sar}
            for d in r.department_breakdown
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "numeric_salary_required_note_en": r.numeric_salary_required_note_en,
        "numeric_salary_required_note_ar": r.numeric_salary_required_note_ar,
        "confidence": r.confidence, "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }


# ═════════════════════════════════════════════════════════════════════════
# PART 2 — WPS / Payroll Internal Consistency Pre-Check
# ═════════════════════════════════════════════════════════════════════════

WPS_SOURCES = [
    "This is an INTERNAL consistency check within your uploaded file only — it does "
    "NOT connect to, query, or verify against live Qiwa, Mudad, or GOSI systems. No "
    "government API integration exists or is claimed here.",
    "Checks whether a contract/basic-salary column and an actual-paid/net/total-salary "
    "column reconcile within a documented tolerance, and (when present) whether basic "
    "salary + allowances sums to the total salary column.",
    "This class of 'silent drift' between promised and actually-paid salary is the same "
    "kind of mismatch this session's Qiwa research found triggers real penalties when "
    "it reaches the actual government Compliance Chain — catching it internally first "
    "has real value even without live API access.",
]
# Tolerance for flagging a mismatch: an illustrative practical threshold (not
# a legal or WPS-system-defined figure), chosen the same way this session's
# other numeric thresholds were (e.g. contract_expiry_engine.py's 30/60/90
# day tiers) — large enough to avoid flagging simple rounding, small enough
# to catch a real systemic drift.
WPS_MISMATCH_ABS_TOLERANCE_SAR = 10.0
WPS_MISMATCH_REL_TOLERANCE = 0.01  # 1%


@dataclass(frozen=True)
class SalaryMismatchCandidate:
    record_id_safe: str
    department: Optional[str]
    mismatch_type: str  # "contract_vs_actual" | "base_plus_allowances_vs_total"
    expected_sar: float
    actual_sar: float
    difference_sar: float
    employee_id_raw: Optional[str] = None  # Phase 40 — see _raw_id_display()'s docstring.


@dataclass(frozen=True)
class WpsConsistencyResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    check_applicable: bool
    basic_salary_column: Optional[str]
    actual_salary_column: Optional[str]
    allowances_column: Optional[str]
    department_column: Optional[str]
    n_employees_checked: int
    n_mismatches: int
    mismatch_rate_pct: Optional[float]
    candidates: list[SalaryMismatchCandidate]
    n_candidates_truncated: int
    narrative_en: str
    narrative_ar: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_wps_result(reason: str, columns_detected: Optional[dict[str, bool]] = None, check_applicable: bool = False) -> WpsConsistencyResult:
    return WpsConsistencyResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        check_applicable=check_applicable, basic_salary_column=None, actual_salary_column=None,
        allowances_column=None, department_column=None, n_employees_checked=0, n_mismatches=0,
        mismatch_rate_pct=None, candidates=[], n_candidates_truncated=0,
        narrative_en="WPS/Payroll consistency check not available for this dataset.",
        narrative_ar="فحص اتساق الرواتب (نظام حماية الأجور) غير متاح لهذه البيانات.",
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note="No mismatch is ever fabricated when there is no second salary-related column to cross-reconcile against.",
        sources=WPS_SOURCES, computed_at=_now(),
    )


def analyze_wps_consistency(df: pd.DataFrame) -> WpsConsistencyResult:
    """Never raises — exceptions should be caught by the caller and surfaced
    via unavailable_wps_result."""
    if df is None or df.empty:
        return unavailable_wps_result("No data available for WPS consistency check.")

    basic_col = _find_column(df, _CONTRACT_BASIC_SALARY_PATTERNS)
    actual_col = _find_column(df, _ACTUAL_PAID_SALARY_PATTERNS)
    allowances_col = _find_column(df, _ALLOWANCES_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)

    columns_detected = {
        "basic_or_contract_salary": basic_col is not None,
        "actual_or_total_salary": actual_col is not None,
        "allowances": allowances_col is not None,
    }

    has_two_reconcilable = basic_col is not None and actual_col is not None and basic_col != actual_col
    has_three_way = basic_col is not None and allowances_col is not None and actual_col is not None

    if not has_two_reconcilable:
        n_salary_like_cols = sum(1 for c in df.columns if _SALARY_PATTERNS.search(str(c)))
        return unavailable_wps_result(
            "This dataset does not have two distinct, clearly-labeled salary-related "
            "columns to cross-reconcile (e.g. a contract/basic-salary column AND a "
            "separate actual-paid/net/total-salary column). "
            f"{n_salary_like_cols} salary-like column(s) detected in total — with only "
            "one, there is nothing to reconcile against, so this check honestly reports "
            "not applicable rather than fabricating a mismatch check.",
            columns_detected, check_applicable=False,
        )

    basic_extract = _extract_strict_numeric_salary(df, basic_col)
    actual_extract = _extract_strict_numeric_salary(df, actual_col)
    allowances_extract = _extract_strict_numeric_salary(df, allowances_col) if allowances_col else None
    dept_lookup, _ = _department_lookup(df, dept_col)

    candidates: list[SalaryMismatchCandidate] = []
    n_checked = 0
    for idx in df.index:
        basic = basic_extract.valid_by_row.get(idx)
        actual = actual_extract.valid_by_row.get(idx)
        if basic is None or actual is None:
            continue
        n_checked += 1
        record_id = _safe_record_id(df.at[idx, id_col]) if id_col is not None and not _is_missing_value(df.at[idx, id_col]) else f"ROW-{idx}"
        dept = dept_lookup.get(idx)

        if has_three_way and allowances_extract is not None:
            allowance = allowances_extract.valid_by_row.get(idx)
            if allowance is not None:
                expected = basic + allowance
                diff = actual - expected
                tolerance = max(WPS_MISMATCH_ABS_TOLERANCE_SAR, expected * WPS_MISMATCH_REL_TOLERANCE)
                if abs(diff) > tolerance:
                    candidates.append(SalaryMismatchCandidate(
                        record_id_safe=record_id, department=dept,
                        mismatch_type="base_plus_allowances_vs_total",
                        expected_sar=round(expected, 2), actual_sar=round(actual, 2),
                        difference_sar=round(diff, 2),
                        employee_id_raw=_raw_id_display(df, idx, id_col),
                    ))
                continue

        tolerance = max(WPS_MISMATCH_ABS_TOLERANCE_SAR, basic * WPS_MISMATCH_REL_TOLERANCE)
        diff = actual - basic
        if abs(diff) > tolerance:
            candidates.append(SalaryMismatchCandidate(
                record_id_safe=record_id, department=dept, mismatch_type="contract_vs_actual",
                expected_sar=round(basic, 2), actual_sar=round(actual, 2), difference_sar=round(diff, 2),
                employee_id_raw=_raw_id_display(df, idx, id_col),
            ))

    if n_checked == 0:
        return unavailable_wps_result(
            f"Both {basic_col} and {actual_col} were detected, but no employee row had "
            "clean numeric values in both — no reconciliation could be performed.",
            columns_detected, check_applicable=True,
        )

    candidates.sort(key=lambda c: abs(c.difference_sar), reverse=True)
    n_truncated = max(0, len(candidates) - _MAX_ROW_LEVEL_CANDIDATES)
    candidates_display = candidates[:_MAX_ROW_LEVEL_CANDIDATES]
    mismatch_rate = round(100.0 * len(candidates) / n_checked, 1) if n_checked else None

    narrative_en = (
        f"{n_checked} employees checked for {basic_col} vs. {actual_col} consistency"
        f"{' (including allowances via ' + allowances_col + ')' if has_three_way else ''}. "
        f"{len(candidates)} mismatch(es) found ({mismatch_rate}%) beyond the "
        f"SAR {WPS_MISMATCH_ABS_TOLERANCE_SAR:.0f}/{WPS_MISMATCH_REL_TOLERANCE*100:.0f}% tolerance."
    )
    narrative_ar = (
        f"تم فحص {n_checked} موظفاً لاتساق {basic_col} مقابل {actual_col}. "
        f"عُثر على {len(candidates)} حالة عدم اتساق ({mismatch_rate}%) تتجاوز هامش التسامح."
    )

    return WpsConsistencyResult(
        available=True, reason=None, columns_detected=columns_detected, check_applicable=True,
        basic_salary_column=basic_col, actual_salary_column=actual_col,
        allowances_column=allowances_col, department_column=dept_col,
        n_employees_checked=n_checked, n_mismatches=len(candidates), mismatch_rate_pct=mismatch_rate,
        candidates=candidates_display, n_candidates_truncated=n_truncated,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note=(
            "This checks internal consistency within your uploaded file only. It does NOT "
            "verify against live Qiwa, Mudad, or GOSI records — confirm actual WPS "
            "compliance via those official platforms before relying on this check alone."
        ),
        sources=WPS_SOURCES, computed_at=_now(),
    )


def wps_consistency_to_dict(r: WpsConsistencyResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "check_applicable": r.check_applicable, "basic_salary_column": r.basic_salary_column,
        "actual_salary_column": r.actual_salary_column, "allowances_column": r.allowances_column,
        "department_column": r.department_column, "n_employees_checked": r.n_employees_checked,
        "n_mismatches": r.n_mismatches, "mismatch_rate_pct": r.mismatch_rate_pct,
        "candidates": [
            {"record_id_safe": c.record_id_safe, "employee_id_raw": c.employee_id_raw,
             "department": c.department, "mismatch_type": c.mismatch_type,
             "expected_sar": c.expected_sar, "actual_sar": c.actual_sar, "difference_sar": c.difference_sar}
            for c in r.candidates
        ],
        "n_candidates_truncated": r.n_candidates_truncated,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }


# ═════════════════════════════════════════════════════════════════════════
# PART 3 — Leave Balance & Compensation (Articles 109, 111)
# ═════════════════════════════════════════════════════════════════════════

ANNUAL_LEAVE_DAYS_UNDER_5YR = 21
ANNUAL_LEAVE_DAYS_5YR_PLUS = 30
LEAVE_COMPENSATION_DAY_DIVISOR = 30  # Article 111: daily wage = monthly wage / 30

LEAVE_SOURCES = [
    "Saudi Labor Law Article 109 — annual leave entitlement: 21 days/year for the first "
    "5 years of service, 30 days/year thereafter.",
    "Saudi Labor Law Article 111 — compensation for unused leave upon separation: "
    "daily wage (monthly wage / 30) x unused leave days.",
    "Live web search performed this phase to confirm these provisions are current — "
    "see PHASE_21_LABOR_LAW_CALCULATORS_REPORT.md for the exact sources retrieved.",
]


def _cumulative_entitlement_days(years: float) -> float:
    if years <= 5:
        return years * ANNUAL_LEAVE_DAYS_UNDER_5YR
    return 5 * ANNUAL_LEAVE_DAYS_UNDER_5YR + (years - 5) * ANNUAL_LEAVE_DAYS_5YR_PLUS


@dataclass(frozen=True)
class LeaveCandidate:
    record_id_safe: str
    department: Optional[str]
    years_of_service: float
    cumulative_entitlement_days: float
    leave_balance_days: Optional[float]
    monthly_wage_sar: Optional[float]
    compensation_sar: Optional[float]
    employee_id_raw: Optional[str] = None  # Phase 40 — see _raw_id_display()'s docstring.


@dataclass(frozen=True)
class LeaveResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    years_of_service_column: Optional[str]
    salary_column: Optional[str]
    leave_balance_column: Optional[str]
    leave_taken_column: Optional[str]
    department_column: Optional[str]
    has_real_balance_data: bool
    n_employees_total: int
    n_valid_computed: int
    n_excluded_invalid_years: int
    n_excluded_invalid_salary: int
    candidates: list[LeaveCandidate]
    n_candidates_truncated: int
    department_breakdown: list[dict[str, Any]]
    department_normalization_notes: list[str]
    narrative_en: str
    narrative_ar: str
    numeric_salary_required_note_en: str
    numeric_salary_required_note_ar: str
    confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str
    # Phase 41 — see labor_law_calculators.py module docstring's Phase 41
    # section (same convention as GratuityResult's matching fields).
    hire_date_column: Optional[str] = None
    last_working_day_column: Optional[str] = None
    n_tenure_computed_from_dates: int = 0


def unavailable_leave_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> LeaveResult:
    return LeaveResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        years_of_service_column=None, salary_column=None, leave_balance_column=None,
        leave_taken_column=None, department_column=None, has_real_balance_data=False,
        n_employees_total=0, n_valid_computed=0, n_excluded_invalid_years=0,
        n_excluded_invalid_salary=0, candidates=[], n_candidates_truncated=0,
        department_breakdown=[], department_normalization_notes=[],
        narrative_en="Leave balance calculation not available for this dataset.",
        narrative_ar="حساب رصيد الإجازات غير متاح لهذه البيانات.",
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        confidence=STRICT_SALARY_CONFIDENCE,
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note="No leave entitlement is computed without a usable years-of-service value for an employee.",
        sources=LEAVE_SOURCES, computed_at=_now(),
    )


def analyze_leave_balance(df: pd.DataFrame) -> LeaveResult:
    """Never raises — exceptions should be caught by the caller and surfaced
    via unavailable_leave_result."""
    if df is None or df.empty:
        return unavailable_leave_result("No data available for leave balance calculation.")

    years_col = _find_column(df, _YEARS_OF_SERVICE_PATTERNS)
    salary_col = _find_column(df, _SALARY_PATTERNS)
    hire_col = _find_column(df, _HIRE_DATE_PATTERNS)
    end_col = _find_column(df, _LAST_WORKING_DAY_PATTERNS) or _find_column(df, _AS_OF_DATE_PATTERNS)
    balance_col = _find_column(df, _LEAVE_BALANCE_PATTERNS)
    taken_col = _find_column(df, _LEAVE_TAKEN_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)

    has_dates = hire_col is not None and end_col is not None
    columns_detected = {
        "years_of_service": years_col is not None,
        "salary": salary_col is not None,
        "hire_date": hire_col is not None,
        "last_working_day": end_col is not None,
        "leave_balance": balance_col is not None,
        "leave_taken": taken_col is not None,
    }

    if years_col is None and not has_dates:
        return unavailable_leave_result(
            "No years-of-service column (or hire-date + last-working-day columns) "
            "detected. Leave entitlement accrual is computed from tenure — without it, "
            "no accrual figure can be calculated.",
            columns_detected,
        )

    years_by_row, n_excluded_years, n_from_dates = _resolve_years_of_service(df, years_col, hire_col, end_col)
    salary_extract = _extract_strict_numeric_salary(df, salary_col) if salary_col else None
    balance_extract_raw = pd.to_numeric(df[balance_col], errors="coerce") if balance_col else None
    taken_extract_raw = pd.to_numeric(df[taken_col], errors="coerce") if taken_col else None
    dept_lookup, dept_notes = _department_lookup(df, dept_col)

    has_real_balance_data = balance_col is not None or taken_col is not None

    candidates: list[LeaveCandidate] = []
    dept_agg: dict[str, dict[str, float]] = {}
    for idx in df.index:
        years = years_by_row.get(idx)
        if years is None:
            continue

        entitlement = round(_cumulative_entitlement_days(years), 1)

        leave_balance_days: Optional[float] = None
        if balance_extract_raw is not None and pd.notna(balance_extract_raw.loc[idx]):
            leave_balance_days = float(balance_extract_raw.loc[idx])
        elif taken_extract_raw is not None and pd.notna(taken_extract_raw.loc[idx]):
            taken = float(taken_extract_raw.loc[idx])
            leave_balance_days = round(entitlement - taken, 1)

        wage = salary_extract.valid_by_row.get(idx) if salary_extract is not None else None
        compensation: Optional[float] = None
        if leave_balance_days is not None and wage is not None:
            daily_wage = wage / LEAVE_COMPENSATION_DAY_DIVISOR
            compensation = round(daily_wage * max(leave_balance_days, 0.0), 2)

        record_id = _safe_record_id(df.at[idx, id_col]) if id_col is not None and not _is_missing_value(df.at[idx, id_col]) else f"ROW-{idx}"
        dept = dept_lookup.get(idx)

        candidates.append(LeaveCandidate(
            record_id_safe=record_id, department=dept, years_of_service=years,
            cumulative_entitlement_days=entitlement, leave_balance_days=leave_balance_days,
            monthly_wage_sar=wage, compensation_sar=compensation,
            employee_id_raw=_raw_id_display(df, idx, id_col),
        ))

        if dept:
            bucket = dept_agg.setdefault(dept, {"n": 0, "entitlement": 0.0, "compensation": 0.0, "n_with_comp": 0})
            bucket["n"] += 1
            bucket["entitlement"] += entitlement
            if compensation is not None:
                bucket["compensation"] += compensation
                bucket["n_with_comp"] += 1

    years_source_desc_en = years_col if years_col else f"{hire_col} → {end_col}"
    years_source_desc_ar = years_col if years_col else f"{hire_col} ← {end_col}"

    if not candidates:
        return unavailable_leave_result(
            f"Found a tenure source ('{years_source_desc_en}'), but no employee row had "
            "a usable numeric value in it (e.g. it may use range-text like 'Less than "
            "5 years' rather than an exact figure).",
            columns_detected,
        )

    department_breakdown = [
        {
            "department": dept, "n_employees": int(b["n"]),
            "total_entitlement_days": round(b["entitlement"], 1),
            "total_compensation_sar": round(b["compensation"], 2) if b["n_with_comp"] > 0 else None,
        }
        for dept, b in dept_agg.items()
    ]
    department_breakdown.sort(key=lambda d: d["n_employees"], reverse=True)

    candidates.sort(key=lambda c: c.years_of_service, reverse=True)
    n_truncated = max(0, len(candidates) - _MAX_ROW_LEVEL_CANDIDATES)
    candidates_display = candidates[:_MAX_ROW_LEVEL_CANDIDATES]

    n_with_compensation = sum(1 for c in candidates if c.compensation_sar is not None)
    narrative_en = f"{len(candidates)} of {len(df)} employees had a usable years-of-service value ({years_source_desc_en}) for entitlement accrual."
    narrative_ar = f"لدى {len(candidates)} من أصل {len(df)} موظفاً قيمة سنوات خدمة صالحة ({years_source_desc_ar}) لاحتساب الاستحقاق."
    if n_from_dates > 0:
        narrative_en += (
            f" Tenure for {n_from_dates} employee(s) was computed from exact hire/"
            f"last-working-day dates ({hire_col} → {end_col}) rather than the "
            "years-of-service column, for full day-count precision."
        )
        narrative_ar += (
            f" احتُسبت مدة الخدمة لـ {n_from_dates} موظفاً من تاريخي التعيين وآخر يوم "
            f"عمل الفعليين ({hire_col} ← {end_col}) بدلاً من عمود سنوات الخدمة، لأقصى "
            "دقة بعدد الأيام."
        )
    if not has_real_balance_data:
        narrative_en += (
            " No leave-balance or leave-taken column detected — figures shown are "
            "CUMULATIVE ENTITLEMENT ACCRUED since hire, not actual remaining balance "
            "(leave already taken is unknown), and no compensation figure is computed."
        )
        narrative_ar += (
            " لم يتم اكتشاف عمود رصيد إجازات أو إجازات مستخدمة — الأرقام المعروضة هي "
            "الاستحقاق التراكمي منذ التوظيف، وليست الرصيد الفعلي المتبقي، ولا يُحتسب "
            "مبلغ تعويض."
        )
    elif n_with_compensation < len(candidates):
        narrative_en += f" Compensation computed for {n_with_compensation} employee(s) with both a leave balance and a clean numeric salary."
        narrative_ar += f" تم احتساب التعويض لـ {n_with_compensation} موظفاً ممن لديهم رصيد إجازات وراتب رقمي صريح."

    return LeaveResult(
        available=True, reason=None, columns_detected=columns_detected,
        years_of_service_column=years_col, salary_column=salary_col,
        leave_balance_column=balance_col, leave_taken_column=taken_col, department_column=dept_col,
        has_real_balance_data=has_real_balance_data, n_employees_total=len(df),
        n_valid_computed=len(candidates), n_excluded_invalid_years=n_excluded_years,
        n_excluded_invalid_salary=(salary_extract.n_excluded_non_numeric if salary_extract else 0),
        candidates=candidates_display, n_candidates_truncated=n_truncated,
        department_breakdown=department_breakdown, department_normalization_notes=dept_notes,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        numeric_salary_required_note_en=_NUMERIC_SALARY_NOTE_EN,
        numeric_salary_required_note_ar=_NUMERIC_SALARY_NOTE_AR,
        confidence=STRICT_SALARY_CONFIDENCE,
        disclaimer_en=LABOR_LAW_DISCLAIMER_EN, disclaimer_ar=LABOR_LAW_DISCLAIMER_AR,
        governance_note=(
            "No employee names are included — record_id_safe is a one-way hash. "
            "Compensation is only computed when both a real leave balance and a clean "
            "numeric salary are available — never estimated."
        ),
        hire_date_column=hire_col, last_working_day_column=end_col,
        n_tenure_computed_from_dates=n_from_dates,
        sources=LEAVE_SOURCES, computed_at=_now(),
    )


def leave_balance_to_dict(r: LeaveResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "years_of_service_column": r.years_of_service_column, "salary_column": r.salary_column,
        "hire_date_column": r.hire_date_column, "last_working_day_column": r.last_working_day_column,
        "n_tenure_computed_from_dates": r.n_tenure_computed_from_dates,
        "leave_balance_column": r.leave_balance_column, "leave_taken_column": r.leave_taken_column,
        "department_column": r.department_column, "has_real_balance_data": r.has_real_balance_data,
        "n_employees_total": r.n_employees_total, "n_valid_computed": r.n_valid_computed,
        "n_excluded_invalid_years": r.n_excluded_invalid_years,
        "n_excluded_invalid_salary": r.n_excluded_invalid_salary,
        "candidates": [
            {"record_id_safe": c.record_id_safe, "employee_id_raw": c.employee_id_raw,
             "department": c.department,
             "years_of_service": c.years_of_service, "cumulative_entitlement_days": c.cumulative_entitlement_days,
             "leave_balance_days": c.leave_balance_days, "monthly_wage_sar": c.monthly_wage_sar,
             "compensation_sar": c.compensation_sar}
            for c in r.candidates
        ],
        "n_candidates_truncated": r.n_candidates_truncated,
        "department_breakdown": r.department_breakdown,
        "department_normalization_notes": r.department_normalization_notes,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "numeric_salary_required_note_en": r.numeric_salary_required_note_en,
        "numeric_salary_required_note_ar": r.numeric_salary_required_note_ar,
        "confidence": r.confidence, "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }
