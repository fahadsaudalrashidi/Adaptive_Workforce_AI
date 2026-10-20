"""
Pay Equity Analysis — Phase 17.

Answers a narrower, more specific question than Phase 6's Fairness/Bias
Audit (`ethical_ai.py`, which looks at OUTCOME rates like attrition risk):
"are people in comparable roles/levels paid comparably, after accounting
for legitimate factors like seniority and role level?" This is a
standard, industry-recognised capability shipped as its own named module
by HR analytics platforms (Visier, Culture Amp, and peers, per 2026 market
research) — distinct enough from general fairness auditing to warrant its
own engine rather than another metric bolted onto `ethical_ai.py`.

**Reuse, not reimplementation** — this module deliberately reuses three
things from `ethical_ai.py` rather than re-deriving them:
  1. `_detect_protected_attributes()` — the exact same keyword-based
     detector (gender/age/nationality/etc.), called verbatim.
  2. `_MIN_GROUP_SIZE_FOR_DISPARITY` (=20) — the exact same minimum-
     group-size floor, for the exact same reason: a comparison between two
     small groups is dominated by sampling noise, not a real signal (see
     ethical_ai.py's module docstring for the fabricated-disparity bug
     this floor was built to prevent).
  3. `_bucket_or_skip_for_disparity()` — the exact same high-cardinality
     guard (a protected attribute with too many distinct raw values, e.g.
     Age, is bucketed into quantile bands or skipped — never compared on
     raw values).
`department_normalizer.py`'s `normalize_department_series()` is reused
verbatim for department-level grouping, same as every other module this
session (Overtime, Nitaqat, Recruitment, Payroll).

**What is genuinely NEW, not reused** — the significance test.
`ethical_ai.py`'s `_two_proportion_z_test()` compares two RATES/proportions
(e.g. attrition rate between groups) and would be statistically wrong
applied here — pay equity compares two MEANS of continuous salary data.
This module implements Welch's two-sample t-test (`_welch_t_test()`)
instead — the correct test for this shape of comparison — following the
identical discipline (scipy-optional import guard, never fabricates a
p-value, same `_SIGNIFICANCE_ALPHA=0.05` threshold reused from
`ethical_ai.py`).

**Comparability cohorts**: within each Job Level, department-level
splitting is tried first (the more specific, preferred comparability
basis); whether "department cells are too small" is judged empirically —
by whether the split actually leaves at least one department cohort with
2+ protected-attribute groups clearing `_MIN_GROUP_SIZE_FOR_DISPARITY` —
rather than a pre-emptive department-size-only heuristic (which was tried
first and rejected: it fragmented large, evenly-spread job levels into
per-department cells that each individually failed the floor once ALSO
split by the protected attribute, discarding a sample that was in fact
large enough for a whole-job-level comparison). Falls back to the whole
job level (department ignored) whenever the split produces nothing usable.
This mirrors the same "don't compare on cells too small to mean anything"
discipline as the group-size floor itself, applied
one level up (at cohort-construction time, before the protected-attribute
comparison even starts).

**Honesty framing (non-negotiable, same as every module this session)**:
every result carries `pay_equity_confidence` = "statistical_indicator_not_
legal_certification" and an explicit disclaimer — this is a statistical
pay-gap INDICATOR for internal HR review, never a legal pay-equity
certification, and a confirmed/significant gap requires qualified HR/legal
review before any compensation action. A gap that fails the significance
test is reported as such, not silently dropped — same "plausibly sampling
noise" caveat language already established in `ethical_ai.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series
from backend.core.ethical_ai import (
    _MIN_GROUP_SIZE_FOR_DISPARITY,
    _SIGNIFICANCE_ALPHA,
    _bucket_or_skip_for_disparity,
    _detect_protected_attributes,
    ProtectedAttribute,
)

try:
    from scipy import stats as _scipy_stats
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


# ── Column detection (same local-regex convention as every other module) ───

_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|annual[_\s]?salary|salary|wage|"
    r"compensation|basic[_\s]?pay|gross[_\s]?pay|"
    r"الراتب|الأجر|التعويض)\b",
    re.I,
)
_JOB_LEVEL_PATTERNS = re.compile(
    r"\b(job[_\s]?level|joblevel|career[_\s]?level|grade[_\s]?level|"
    r"المستوى[_\s]?الوظيفي|الدرجة[_\s]?الوظيفية)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b",
    re.I,
)

# Protected-attribute types relevant to pay equity specifically (per spec:
# Gender, Nationality, Age) — ethical_ai.py's detector also recognises
# religion/disability/marital, which are real protected characteristics but
# outside this module's requested scope.
_RELEVANT_ATTRIBUTE_TYPES = frozenset({"gender", "nationality", "race", "age"})

_COLUMN_LABELS_EN: dict[str, str] = {
    "salary_or_compensation": "Salary / compensation (e.g. MonthlyIncome)",
    "protected_attribute": "A protected attribute (Gender, Nationality, or Age)",
    "job_level": "Job level / career grade (optional — enables role-level comparison)",
    "department": "Department (optional — enables department-level comparison)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "salary_or_compensation": "الراتب / التعويض (مثال: MonthlyIncome)",
    "protected_attribute": "خاصية محمية (الجنس أو الجنسية أو العمر)",
    "job_level": "المستوى الوظيفي (اختياري — يفعّل المقارنة حسب المستوى)",
    "department": "القسم (اختياري — يفعّل المقارنة حسب القسم)",
}

PAY_EQUITY_CONFIDENCE = "statistical_indicator_not_legal_certification"
PAY_EQUITY_DISCLAIMER_EN = (
    "Statistical pay-gap indicator for internal HR review — NOT a legal pay-equity "
    "certification or audit. Gaps are only computed within comparable groups (same "
    "job level and/or department), using the same minimum-group-size floor (n≥20 "
    "per group) and statistical-significance testing (p<0.05) discipline already "
    "established for this platform's Fairness/Bias Audit. A confirmed, statistically "
    "significant gap is a signal to investigate — not proof of unlawful discrimination. "
    "Qualified HR and legal review is required before any compensation action."
)
PAY_EQUITY_DISCLAIMER_AR = (
    "مؤشر إحصائي لفجوة الأجور لأغراض المراجعة الداخلية للموارد البشرية — وليس "
    "شهادة أو تدقيقاً قانونياً لعدالة الأجور. تُحتسب الفجوات فقط ضمن مجموعات "
    "قابلة للمقارنة (نفس المستوى الوظيفي و/أو القسم)، باستخدام نفس حد الحد "
    "الأدنى لحجم المجموعة (٢٠ فرداً على الأقل) واختبار الدلالة الإحصائية "
    "(p<0.05) المعتمد بالفعل في تدقيق العدالة والتحيّز بهذه المنصة. الفجوة "
    "المؤكدة ذات الدلالة الإحصائية هي إشارة للتحقيق، وليست دليلاً على تمييز "
    "غير قانوني. تلزم مراجعة متخصصي الموارد البشرية والقانون قبل أي إجراء "
    "متعلق بالتعويضات."
)

_SOURCES = [
    "Welch, B.L. (1947). 'The generalization of Student's problem when several "
    "different population variances are involved.' Biometrika, 34(1-2), 28-35 "
    "— statistical method (Welch's unequal-variance t-test) used for pay-gap "
    "significance testing.",
    "Minimum-group-size floor and high-cardinality bucketing guard reused "
    "verbatim from this platform's Fairness/Bias Audit "
    "(backend/core/ethical_ai.py) — see ETHICAL_AI_ENGINE_INVESTIGATION.md.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _welch_t_test(sample_a: pd.Series, sample_b: pd.Series) -> Optional[float]:
    """
    Welch's two-sample t-test (unequal variance) p-value between two groups'
    continuous salary distributions — the correct test for comparing two
    MEANS. NOT the same test as ethical_ai.py's `_two_proportion_z_test`
    (which compares two RATES/proportions and would be statistically wrong
    applied to salary data) — same discipline, different, appropriate test.
    Never fabricates a p-value: returns None if scipy is unavailable or
    either sample has fewer than 2 observations.
    """
    if not _SCIPY_AVAILABLE or len(sample_a) < 2 or len(sample_b) < 2:
        return None
    try:
        _stat, p = _scipy_stats.ttest_ind(sample_a, sample_b, equal_var=False)
        p = float(p)
        if p != p:  # NaN
            return None
        return round(p, 4)
    except Exception:
        return None


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PayGapComparison:
    cohort_label_en: str
    cohort_label_ar: str
    comparability_basis: str        # "job_level" | "job_level_and_department" | "department" | "organisation_wide"
    protected_attribute: str        # source column name, e.g. "Gender"
    protected_attribute_type: str   # "gender" | "nationality" | "race" | "age"
    was_bucketed: bool              # True if the attribute was quantile-bucketed (e.g. Age) before comparison
    higher_paid_group: str
    lower_paid_group: str
    higher_paid_group_n: int
    lower_paid_group_n: int
    higher_paid_group_mean_sar: float
    lower_paid_group_mean_sar: float
    pay_gap_pct: float               # (higher - lower) / higher * 100
    p_value: Optional[float]
    statistically_significant: Optional[bool]
    interpretation_en: str
    interpretation_ar: str


@dataclass(frozen=True)
class PayEquityResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    salary_column: Optional[str]
    protected_attributes_used: list[str]
    comparability_factors_used: list[str]
    n_employees_total: int
    n_comparisons_computed: int
    n_comparisons_suppressed_small_sample: int
    comparisons: list[PayGapComparison]
    n_significant_gaps: int
    narrative_en: str
    narrative_ar: str
    granularity_notes: list[str]
    department_normalization_notes: list[str]
    pay_equity_confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_pay_equity_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> PayEquityResult:
    return PayEquityResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {},
        salary_column=None,
        protected_attributes_used=[],
        comparability_factors_used=[],
        n_employees_total=0,
        n_comparisons_computed=0,
        n_comparisons_suppressed_small_sample=0,
        comparisons=[],
        n_significant_gaps=0,
        narrative_en="Pay equity analysis not available for this dataset.",
        narrative_ar="تحليل عدالة الأجور غير متاح لهذه البيانات.",
        granularity_notes=[],
        department_normalization_notes=[],
        pay_equity_confidence=PAY_EQUITY_CONFIDENCE,
        disclaimer_en=PAY_EQUITY_DISCLAIMER_EN,
        disclaimer_ar=PAY_EQUITY_DISCLAIMER_AR,
        governance_note=(
            "No pay-gap figures are computed or displayed when required columns "
            "are missing — this platform never fabricates a compensation comparison."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


# ── Cohort construction ──────────────────────────────────────────────────────

def _cohorts_for_job_level_and_attribute(
    sub: pd.DataFrame, dept_present: bool,
) -> tuple[list[tuple[Optional[str], pd.DataFrame]], bool]:
    """
    Decide whether a job-level slice should be split by department for THIS
    protected attribute's comparison. Department-level cohorts are tried
    first (the more specific, preferred comparability basis); whether
    "department cells are too small" is judged empirically — by whether
    splitting actually leaves at least one department cohort with 2+ groups
    clearing the minimum-group-size floor for THIS attribute — rather than a
    pre-emptive department-size-only heuristic. A pre-emptive check on raw
    department size (ignoring the attribute's own group split) was tried
    first and rejected: it fragmented large, evenly-spread job levels (e.g.
    110 employees across 5 departments) into per-department cells that each
    individually failed the floor once ALSO split by gender, discarding a
    sample that was in fact large enough for a whole-job-level comparison.
    Falls back to the whole job level (department ignored) whenever the
    department split produces zero usable comparisons — this is what "same
    JobLevel alone if department cells are too small" means in practice.

    Returns (cohorts, used_department_split).
    """
    if not dept_present:
        return [(None, sub)], False

    dept_cohorts = [(dept, grp) for dept, grp in sub.groupby("_dept")]
    any_usable = any(
        grp.groupby("_attr").size().ge(_MIN_GROUP_SIZE_FOR_DISPARITY).sum() >= 2
        for _dept, grp in dept_cohorts
    )
    if any_usable:
        return dept_cohorts, True
    return [(None, sub)], False


def _compare_groups_in_cohort(
    cohort_df: pd.DataFrame,
) -> Optional[tuple[str, str, int, int, float, float, float, Optional[float], Optional[bool]]]:
    """
    Compare the highest-mean-salary vs. lowest-mean-salary protected-
    attribute group within one comparability cohort, mirroring ethical_ai.py's
    "compare highest/lowest surviving group" pattern. Returns None
    (suppressed) if fewer than 2 groups meet `_MIN_GROUP_SIZE_FOR_DISPARITY`.
    """
    sizes = cohort_df.groupby("_attr").size()
    eligible = sizes[sizes >= _MIN_GROUP_SIZE_FOR_DISPARITY].index.tolist()
    if len(eligible) < 2:
        return None

    means = cohort_df.groupby("_attr")["_salary"].mean()
    eligible_means = means.loc[eligible]
    hi_group = str(eligible_means.idxmax())
    lo_group = str(eligible_means.idxmin())
    if hi_group == lo_group:
        return None

    hi_vals = cohort_df.loc[cohort_df["_attr"].astype(str) == hi_group, "_salary"]
    lo_vals = cohort_df.loc[cohort_df["_attr"].astype(str) == lo_group, "_salary"]
    hi_mean = float(hi_vals.mean())
    lo_mean = float(lo_vals.mean())
    if hi_mean <= 0:
        return None
    gap_pct = round((hi_mean - lo_mean) / hi_mean * 100, 1)
    p_value = _welch_t_test(hi_vals, lo_vals)
    significant = (p_value < _SIGNIFICANCE_ALPHA) if p_value is not None else None

    return (
        hi_group, lo_group, len(hi_vals), len(lo_vals),
        round(hi_mean, 0), round(lo_mean, 0), gap_pct, p_value, significant,
    )


def _sar(n: float) -> str:
    if abs(n) >= 1_000:
        return f"SAR {n / 1_000:.1f}K"
    return f"SAR {n:.0f}"


# ── Main API ──────────────────────────────────────────────────────────────────

def analyze_pay_equity(df: pd.DataFrame) -> PayEquityResult:
    """
    Real pay-equity analysis: within each comparable-role cohort (job level,
    and department where department cells are large enough), compute the
    pay gap between protected-attribute groups, gated by the same
    minimum-group-size floor and significance testing discipline as
    ethical_ai.py. Never raises — exceptions should be caught by the caller
    and surfaced via `unavailable_pay_equity_result`.
    """
    if df is None or df.empty:
        return unavailable_pay_equity_result("No data available for pay equity analysis.")

    salary_col = _find_column(df, _SALARY_PATTERNS)
    job_level_col = _find_column(df, _JOB_LEVEL_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    protected_attrs = [
        a for a in _detect_protected_attributes(df)
        if a.attribute_type in _RELEVANT_ATTRIBUTE_TYPES
    ]

    columns_detected = {
        "salary_or_compensation": salary_col is not None,
        "protected_attribute": len(protected_attrs) > 0,
        "job_level": job_level_col is not None,
        "department": dept_col is not None,
    }

    if salary_col is None:
        return unavailable_pay_equity_result(
            "No salary/compensation column detected (e.g. MonthlyIncome). Pay "
            "equity analysis requires a numeric compensation column.",
            columns_detected,
        )
    if not protected_attrs:
        return unavailable_pay_equity_result(
            "No protected attribute (Gender, Nationality, or Age) detected. Pay "
            "equity compares compensation between protected-attribute groups "
            "within comparable roles.",
            columns_detected,
        )
    if job_level_col is None and dept_col is None:
        return unavailable_pay_equity_result(
            "No comparability factor (JobLevel or Department) detected. Pay "
            "equity requires at least one legitimate factor to define "
            "'comparable roles' — otherwise a raw pay difference would conflate "
            "role/seniority mix with bias, which this platform will not do.",
            columns_detected,
        )

    salary = pd.to_numeric(df[salary_col], errors="coerce")
    work = pd.DataFrame(index=df.index)
    work["_salary"] = salary
    work["_job_level"] = df[job_level_col].astype(str) if job_level_col is not None else None

    dept_norm_notes: list[str] = []
    dept_labels: dict[str, str] = {}
    if dept_col is not None:
        norm_result = normalize_department_series(df[dept_col].astype(str))
        for merge in norm_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_norm_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}."
            )
        for grp in norm_result.unmerged_similar_variants:
            dept_norm_notes.append(
                f"Found similarly-named but NOT merged department values "
                f"{', '.join(repr(v) for v in grp)} — review manually."
            )
        work["_dept"] = norm_result.normalized_keys.values
        dept_labels = norm_result.display_labels

    work = work[work["_salary"].notna() & (work["_salary"] > 0)]
    if work.empty:
        return unavailable_pay_equity_result(
            "No valid (numeric, positive) salary values found.", columns_detected,
        )

    granularity_notes: list[str] = []
    comparisons: list[PayGapComparison] = []
    n_suppressed = 0
    dept_present = dept_col is not None
    comparability_factors_used = [f for f, present in (
        ("job_level", job_level_col is not None), ("department", dept_col is not None),
    ) if present]

    job_level_values = work["_job_level"].dropna().unique().tolist() if job_level_col is not None else [None]
    if not job_level_values:
        job_level_values = [None]

    for attr in protected_attrs:
        grouped_values, bucket_note = _bucket_or_skip_for_disparity(df, attr)
        if bucket_note:
            granularity_notes.append(bucket_note)
        if grouped_values is None:
            continue
        was_bucketed = bucket_note is not None

        for jl in job_level_values:
            sub = work if jl is None else work[work["_job_level"] == jl]
            if sub.empty:
                continue
            sub = sub.copy()
            sub["_attr"] = grouped_values.reindex(sub.index)
            sub = sub[sub["_attr"].notna()]
            if sub.empty:
                continue

            cohorts, used_dept_split = _cohorts_for_job_level_and_attribute(sub, dept_present)

            for dept_key, cohort_df in cohorts:
                n_groups_present = cohort_df["_attr"].nunique()
                result = _compare_groups_in_cohort(cohort_df)

                if result is None:
                    if n_groups_present >= 2:
                        n_suppressed += 1
                    continue

                (hi, lo, n_hi, n_lo, mean_hi, mean_lo, gap_pct, p_value, significant) = result

                dept_label = dept_labels.get(dept_key, dept_key) if dept_key and used_dept_split else None
                if jl is not None and dept_label:
                    basis = "job_level_and_department"
                    label_en = f"Job Level {jl} · {dept_label}"
                    label_ar = f"المستوى الوظيفي {jl} · {dept_label}"
                elif jl is not None:
                    basis = "job_level"
                    label_en = f"Job Level {jl}"
                    label_ar = f"المستوى الوظيفي {jl}"
                elif dept_label:
                    basis = "department"
                    label_en = dept_label
                    label_ar = dept_label
                else:
                    basis = "organisation_wide"
                    label_en = "All Employees"
                    label_ar = "جميع الموظفين"

                if significant is True:
                    interp_en = (
                        f"Within {label_en}, '{lo}' employees earn {gap_pct:.1f}% less than "
                        f"'{hi}' employees on average ({_sar(mean_lo)} vs {_sar(mean_hi)}, "
                        f"n={n_lo} vs n={n_hi}) — statistically significant (p={p_value:.3f})."
                    )
                    interp_ar = (
                        f"ضمن {label_ar}، يكسب موظفو '{lo}' أقل بنسبة {gap_pct:.1f}% من موظفي "
                        f"'{hi}' في المتوسط (n={n_lo} مقابل n={n_hi}) — ذو دلالة إحصائية "
                        f"(p={p_value:.3f})."
                    )
                elif significant is False:
                    interp_en = (
                        f"Within {label_en}, '{lo}' employees show a {gap_pct:.1f}% lower average "
                        f"than '{hi}' employees, but this is NOT statistically significant at "
                        f"p<0.05 (p={p_value:.3f}) — plausibly sampling noise, not a confirmed gap."
                    )
                    interp_ar = (
                        f"ضمن {label_ar}، يُظهر موظفو '{lo}' متوسطاً أقل بنسبة {gap_pct:.1f}% من "
                        f"'{hi}'، لكن هذا غير ذي دلالة إحصائية عند p<0.05 (p={p_value:.3f}) — "
                        "على الأرجح تباين عشوائي، وليس فجوة مؤكدة."
                    )
                else:
                    interp_en = (
                        f"Within {label_en}, '{lo}' employees show a {gap_pct:.1f}% lower average "
                        f"than '{hi}' employees. Significance could not be computed."
                    )
                    interp_ar = (
                        f"ضمن {label_ar}، يُظهر موظفو '{lo}' متوسطاً أقل بنسبة {gap_pct:.1f}% من "
                        f"'{hi}'. تعذّر احتساب الدلالة الإحصائية."
                    )

                comparisons.append(PayGapComparison(
                    cohort_label_en=label_en,
                    cohort_label_ar=label_ar,
                    comparability_basis=basis,
                    protected_attribute=attr.column_name,
                    protected_attribute_type=attr.attribute_type,
                    was_bucketed=was_bucketed,
                    higher_paid_group=hi,
                    lower_paid_group=lo,
                    higher_paid_group_n=n_hi,
                    lower_paid_group_n=n_lo,
                    higher_paid_group_mean_sar=mean_hi,
                    lower_paid_group_mean_sar=mean_lo,
                    pay_gap_pct=gap_pct,
                    p_value=p_value,
                    statistically_significant=significant,
                    interpretation_en=interp_en,
                    interpretation_ar=interp_ar,
                ))

    n_significant = sum(1 for c in comparisons if c.statistically_significant is True)

    if comparisons:
        if n_significant > 0:
            narrative_en = (
                f"Computed {len(comparisons)} comparable-role pay comparison(s) across "
                f"{len(protected_attrs)} protected attribute(s). {n_significant} showed a "
                f"statistically significant pay gap (p<0.05) — see the comparisons below for "
                f"details. {n_suppressed} comparison(s) were suppressed for having fewer than "
                f"{_MIN_GROUP_SIZE_FOR_DISPARITY} employees in a group."
            )
            narrative_ar = (
                f"تم احتساب {len(comparisons)} مقارنة أجور ضمن أدوار قابلة للمقارنة عبر "
                f"{len(protected_attrs)} خاصية محمية. أظهرت {n_significant} فجوة أجور ذات دلالة "
                f"إحصائية (p<0.05). تم استبعاد {n_suppressed} مقارنة لعدم وجود ٢٠ موظفاً على "
                "الأقل في إحدى المجموعات."
            )
        else:
            narrative_en = (
                f"Computed {len(comparisons)} comparable-role pay comparison(s) — none showed "
                f"a statistically significant pay gap at p<0.05. {n_suppressed} comparison(s) "
                f"were suppressed for having fewer than {_MIN_GROUP_SIZE_FOR_DISPARITY} employees "
                "in a group."
            )
            narrative_ar = (
                f"تم احتساب {len(comparisons)} مقارنة أجور ضمن أدوار قابلة للمقارنة — لم تُظهر "
                f"أي منها فجوة ذات دلالة إحصائية عند p<0.05. تم استبعاد {n_suppressed} مقارنة "
                "لعدم وجود ٢٠ موظفاً على الأقل في إحدى المجموعات."
            )
    else:
        narrative_en = (
            "No comparable-role cohort in this dataset had at least two protected-attribute "
            f"groups with {_MIN_GROUP_SIZE_FOR_DISPARITY}+ employees each — no pay comparison "
            "could be computed without relying on too-small samples."
        )
        narrative_ar = (
            "لم تحتوِ أي مجموعة أدوار قابلة للمقارنة في هذه البيانات على خاصيتين محميتين "
            f"بحجم {_MIN_GROUP_SIZE_FOR_DISPARITY} موظفاً على الأقل لكل منهما — تعذّر احتساب "
            "أي مقارنة أجور دون الاعتماد على عينات صغيرة جداً."
        )

    return PayEquityResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        salary_column=salary_col,
        protected_attributes_used=[a.column_name for a in protected_attrs],
        comparability_factors_used=comparability_factors_used,
        n_employees_total=len(work),
        n_comparisons_computed=len(comparisons),
        n_comparisons_suppressed_small_sample=n_suppressed,
        comparisons=comparisons,
        n_significant_gaps=n_significant,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        granularity_notes=granularity_notes,
        department_normalization_notes=dept_norm_notes,
        pay_equity_confidence=PAY_EQUITY_CONFIDENCE,
        disclaimer_en=PAY_EQUITY_DISCLAIMER_EN,
        disclaimer_ar=PAY_EQUITY_DISCLAIMER_AR,
        governance_note=(
            "Pay gaps are computed only within comparable cohorts meeting the "
            f"minimum-group-size floor (n≥{_MIN_GROUP_SIZE_FOR_DISPARITY} per group) — "
            "smaller comparisons are suppressed, never reported on insufficient data."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _comparison_to_dict(c: PayGapComparison) -> dict[str, Any]:
    return {
        "cohort_label_en": c.cohort_label_en,
        "cohort_label_ar": c.cohort_label_ar,
        "comparability_basis": c.comparability_basis,
        "protected_attribute": c.protected_attribute,
        "protected_attribute_type": c.protected_attribute_type,
        "was_bucketed": c.was_bucketed,
        "higher_paid_group": c.higher_paid_group,
        "lower_paid_group": c.lower_paid_group,
        "higher_paid_group_n": c.higher_paid_group_n,
        "lower_paid_group_n": c.lower_paid_group_n,
        "higher_paid_group_mean_sar": c.higher_paid_group_mean_sar,
        "lower_paid_group_mean_sar": c.lower_paid_group_mean_sar,
        "pay_gap_pct": c.pay_gap_pct,
        "p_value": c.p_value,
        "statistically_significant": c.statistically_significant,
        "interpretation_en": c.interpretation_en,
        "interpretation_ar": c.interpretation_ar,
    }


def pay_equity_to_dict(r: PayEquityResult) -> dict[str, Any]:
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "salary_column": r.salary_column,
        "protected_attributes_used": r.protected_attributes_used,
        "comparability_factors_used": r.comparability_factors_used,
        "n_employees_total": r.n_employees_total,
        "n_comparisons_computed": r.n_comparisons_computed,
        "n_comparisons_suppressed_small_sample": r.n_comparisons_suppressed_small_sample,
        "comparisons": [_comparison_to_dict(c) for c in r.comparisons],
        "n_significant_gaps": r.n_significant_gaps,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "granularity_notes": r.granularity_notes,
        "department_normalization_notes": r.department_normalization_notes,
        "pay_equity_confidence": r.pay_equity_confidence,
        "disclaimer_en": r.disclaimer_en,
        "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
