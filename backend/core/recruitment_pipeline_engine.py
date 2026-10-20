"""
Recruitment Pipeline Status Tracker — Phase 5.

This platform's other modules are all retention/attrition-focused (who might
LEAVE). This module covers the opposite side of the workforce lifecycle: who
is being brought IN. It is a genuinely new domain, so it is built with the
same "never fabricate what the data doesn't support" discipline as
payroll_movement_tracker.py rather than assuming every upload has a
recruitment funnel to report on.

**Reality check, stated up front:** the platform's primary test datasets
(the Saudi attrition research CSV, and messy_test_data.csv) are structured
HR *employee* data — they have no candidate/applicant/hiring-stage columns
at all. Uploading either against this module is expected to, and does,
return `available=False` with a clear list of which columns would activate
the feature — never a fabricated funnel.

Column detection follows this codebase's established local-regex convention
(see payroll_movement_tracker.py's/overtime_cost_intelligence_engine.py's
`_find_column()` + per-field `re.compile` patterns, each already combining
English and Arabic keywords in one pattern) rather than reinventing a fuzzy
matcher. `theory_aware_column_mapper.py` and `saudi_schema_intelligence.py`
were both reviewed first: the former's `ConstructDefinition` model is
purpose-built for Likert-scale psychological survey columns, the latter is a
whole ERP-schema classifier — neither fits a small, fixed set of recruitment
funnel fields, so the lighter existing pattern already used by every other
Phase-4/35 module is reused here instead, consistent with them.

**Department/role grouping** reuses `backend/core/department_normalizer.py`
verbatim (the same shared fix that merged "Sales"/"مبيعات" for HR data) —
recruitment data has the identical Arabic/English/casing inconsistency
problem for the "department/role applied for" column.

**Pipeline stage grouping** ("Applied"/"Screening"/"Interview"/"Offer"/
"Hired"/"Rejected", each with English/Arabic/casing variants) is a
*different* value domain from department names, so it is NOT routed through
department_normalizer.py's department-specific synonym table — it reuses
the same two-tier *pattern* (exact trim+casefold, then a curated EN/AR
synonym table, disclosed when it fires) implemented locally, exactly as
overtime_cost_intelligence_engine.py and payroll_movement_tracker.py each
keep their own local salary/hours column patterns rather than sharing an
unrelated module's domain-specific table.

**Deduplication** is NOT reimplemented here. `SecureFileIngestion.scan()`
(backend/core/secure_file_ingestion.py) already deduplicates every uploaded
dataframe once, pipeline-level, before any module (this one included) ever
sees it — see PHASE_4_CORRECTIONS_REPORT.md §2. A duplicate candidate row is
therefore already gone by the time `analyze_recruitment_pipeline()` runs.

**Rejection-reason themes** reuse `exit_interview_intelligence_engine.py`'s
`analyze_exit_interview_text()` directly — same TF-IDF/keyword-construct
approach, same privacy guarantees (no raw text ever returned, minimum-3-
respondents-per-theme threshold) — rather than building a second NLP
pipeline.

**Cost-per-hire** never introduces a sixth cost formula. When the dataset
has a real recruitment-cost column, that observed figure is used directly.
When it doesn't, this module calls `financial_intelligence_engine.py`'s
existing, already-canonical `estimate_monthly_salary()` (the same function
overtime_cost_intelligence_engine.py calls) and applies a single, explicitly
non-Saudi-specific, non-cited multiplier (a widely repeated general HR
rule of thumb: ~20% of one year's estimated salary) — labeled
`SECTOR_BENCHMARK_CONFIDENCE` ("uncalibrated_generic_estimate"), the exact
same constant Phase 4 already uses for its own uncalibrated salary
fallback, imported rather than redefined. This is the honest option: a
live search for a freely citable Saudi-market cost-per-hire benchmark
(mirroring Phase 4's GASTAT research) did not surface one, so no false
precision is claimed for that figure specifically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.core.department_normalizer import normalize_department_series
from backend.core.exit_interview_intelligence_engine import (
    MIN_RESPONSES_FOR_AGGREGATE,
    analyze_exit_interview_text,
    exit_interview_intelligence_to_dict,
)
from backend.core.financial_intelligence_engine import (
    SECTOR_BENCHMARK_CONFIDENCE,
    estimate_monthly_salary,
)

# ── Column detection patterns (English + Arabic, this codebase's convention) ──

_CANDIDATE_ID_PATTERNS = re.compile(
    r"\b(candidate[_\s]?id|applicant[_\s]?id|candidate[_\s]?no|applicant[_\s]?no|"
    r"candidate[_\s]?number|رقم[_\s]?المرشح|رقم[_\s]?المتقدم)\b",
    re.I,
)
_STAGE_PATTERNS = re.compile(
    r"\b(pipeline[_\s]?stage|application[_\s]?stage|hiring[_\s]?stage|recruitment[_\s]?status|"
    r"candidate[_\s]?status|stage|status|المرحلة|حالة[_\s]?الطلب|حالة[_\s]?المتقدم)\b",
    re.I,
)
_APPLICATION_DATE_PATTERNS = re.compile(
    r"\b(application[_\s]?date|applied[_\s]?date|apply[_\s]?date|date[_\s]?applied|"
    r"تاريخ[_\s]?التقديم)\b",
    re.I,
)
_OFFER_DATE_PATTERNS = re.compile(
    r"\b(offer[_\s]?date|offer[_\s]?extended[_\s]?date|date[_\s]?offered|تاريخ[_\s]?العرض)\b",
    re.I,
)
_HIRE_DATE_PATTERNS = re.compile(
    r"\b(hire[_\s]?date|hired[_\s]?date|start[_\s]?date|joining[_\s]?date|join[_\s]?date|"
    r"date[_\s]?hired|تاريخ[_\s]?التوظيف|تاريخ[_\s]?الالتحاق|تاريخ[_\s]?المباشرة)\b",
    re.I,
)
_REJECTION_DATE_PATTERNS = re.compile(
    r"\b(rejection[_\s]?date|reject[_\s]?date|declined[_\s]?date|date[_\s]?rejected|"
    r"تاريخ[_\s]?الرفض)\b",
    re.I,
)
_SOURCE_PATTERNS = re.compile(
    r"\b(source|channel|recruitment[_\s]?source|referral[_\s]?source|application[_\s]?source|"
    r"hiring[_\s]?channel|مصدر[_\s]?التقديم|مصدر|قناة)\b",
    re.I,
)
_REJECTION_REASON_PATTERNS = re.compile(
    r"\b(rejection[_\s]?reason|reject[_\s]?reason|decline[_\s]?reason|reason[_\s]?for[_\s]?rejection|"
    r"سبب[_\s]?الرفض)\b",
    re.I,
)
_ROLE_OR_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|role|position|job[_\s]?title|applied[_\s]?for|"
    r"position[_\s]?applied|position[_\s]?applied[_\s]?for|القسم|الإدارة|المسمى[_\s]?الوظيفي|"
    r"الوظيفة[_\s]?المتقدم[_\s]?لها)\b",
    re.I,
)
_RECRUITMENT_COST_PATTERNS = re.compile(
    r"\b(recruitment[_\s]?cost|cost[_\s]?per[_\s]?hire|hiring[_\s]?cost|agency[_\s]?fee|"
    r"تكلفة[_\s]?التوظيف)\b",
    re.I,
)

# ── Pipeline-stage synonym table (own domain, own tier-2 table — see module
#    docstring for why this is separate from department_normalizer.py) ─────────

_STAGE_ORDER = ["Applied", "Screening", "Interview", "Offer", "Hired"]
_TERMINAL_REJECTED = "Rejected"
_UNRECOGNIZED_STAGE_LABEL = "Unrecognized / Other Stage"

_STAGE_SYNONYMS: dict[str, list[str]] = {
    "Applied":    ["applied", "application", "new", "new application", "قدم", "تقديم", "طلب جديد"],
    "Screening":  ["screening", "screen", "phone screen", "resume screening", "شاشة", "فرز", "غربلة"],
    "Interview":  ["interview", "interviewing", "interview scheduled", "مقابلة", "مقابلة شخصية"],
    "Offer":      ["offer", "offer extended", "offer sent", "عرض", "عرض وظيفي"],
    "Hired":      ["hired", "hire", "joined", "onboarded", "تعيين", "توظيف", "التحق"],
    "Rejected":   ["rejected", "reject", "declined", "not selected", "مرفوض", "رفض"],
}


def _build_stage_reverse_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, variants in _STAGE_SYNONYMS.items():
        lookup[canonical.strip().lower()] = canonical
        for v in variants:
            lookup[v.strip().lower()] = canonical
    return lookup


_STAGE_REVERSE_LOOKUP = _build_stage_reverse_lookup()


def _is_missing_value(raw: object) -> bool:
    """Same missing-value discipline as department_normalizer.py's
    _is_missing_department() — checked before any string operation, since
    Series.astype(str)/str() does not reliably stringify NaN on every
    pandas version (see PHASE_4_CORRECTIONS_REPORT.md §5)."""
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _normalize_stage_value(raw: object) -> str:
    if _is_missing_value(raw):
        return _UNRECOGNIZED_STAGE_LABEL
    key = " ".join(str(raw).split()).casefold()
    return _STAGE_REVERSE_LOOKUP.get(key, _UNRECOGNIZED_STAGE_LABEL)


def _normalize_stage_series(raw: pd.Series) -> tuple[pd.Series, list[str]]:
    """Normalize a raw stage-value Series, disclosing every EN/AR merge that
    fired, mirroring department_normalizer.py's disclosure discipline."""
    from collections import Counter

    raw_str = raw.map(lambda v: _UNRECOGNIZED_STAGE_LABEL if _is_missing_value(v) else str(v))
    normalized = raw_str.map(_normalize_stage_value)

    variants_by_stage: dict[str, Counter] = {}
    for raw_val, stage in zip(raw_str, normalized):
        variants_by_stage.setdefault(stage, Counter())[raw_val] += 1

    notes: list[str] = []
    for stage, counter in variants_by_stage.items():
        if stage != _UNRECOGNIZED_STAGE_LABEL and len(counter) > 1:
            notes.append(
                f"Merged {', '.join(f'{v!r}' for v in sorted(counter))} into "
                f"'{stage}' (recognised as the same pipeline stage): {dict(counter)}."
            )
    return normalized, notes


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StageFunnelCount:
    stage: str
    n_candidates: int
    pct_of_total: float
    conversion_from_previous_pct: Optional[float]  # None for the first ladder stage


@dataclass(frozen=True)
class DepartmentPipelineBreakdown:
    department: str
    n_candidates: int
    n_hired: int
    hire_rate_pct: float


@dataclass(frozen=True)
class SourceChannelBreakdown:
    source: str
    n_candidates: int
    n_hired: int
    hire_rate_pct: float


@dataclass(frozen=True)
class RecruitmentPipelineResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_candidates_total: int
    current_stage_distribution: list[StageFunnelCount]
    department_breakdown: list[DepartmentPipelineBreakdown]
    source_breakdown: list[SourceChannelBreakdown]
    biggest_dropoff_stage: Optional[str]
    n_rejected: int
    rejection_rate_pct: Optional[float]
    avg_time_to_hire_days: Optional[float]
    n_time_to_hire_computed: int
    avg_time_to_reject_days: Optional[float]
    n_time_to_reject_computed: int
    invalid_date_sequences_excluded: int
    date_quality_warnings: list[str]
    department_normalization_notes: list[str]
    stage_normalization_notes: list[str]
    rejection_reason_themes: Optional[dict] = None
    cost_per_hire_sar: Optional[float] = None
    cost_per_hire_confidence: Optional[str] = None
    narrative_en: str = ""
    narrative_ar: str = ""
    governance_note: str = ""
    sources: list[str] = field(default_factory=list)
    computed_at: str = ""


_ALL_COLUMN_LABELS: dict[str, str] = {
    "candidate_id":    "candidate/applicant ID (e.g. CandidateID)",
    "stage":           "pipeline stage (e.g. Stage/Status — Applied/Screening/Interview/Offer/Hired/Rejected)",
    "application_date": "application date (e.g. ApplicationDate)",
    "offer_date":      "offer date (e.g. OfferDate)",
    "hire_date":       "hire/start date (e.g. HireDate)",
    "rejection_date":  "rejection date (e.g. RejectionDate)",
    "source":          "source/channel (e.g. Source — referral, job board, LinkedIn, agency)",
    "rejection_reason": "rejection reason (free text or categorical)",
    "department_or_role": "department/role applied for",
    "recruitment_cost": "recruitment cost / cost per hire",
}


def unavailable_recruitment_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> RecruitmentPipelineResult:
    """Public constructor for an `available=False` result — used both when no
    recruitment columns exist at all and by API routes that need to
    short-circuit before calling analyze_recruitment_pipeline()."""
    return RecruitmentPipelineResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {k: False for k in _ALL_COLUMN_LABELS},
        n_candidates_total=0,
        current_stage_distribution=[],
        department_breakdown=[],
        source_breakdown=[],
        biggest_dropoff_stage=None,
        n_rejected=0,
        rejection_rate_pct=None,
        avg_time_to_hire_days=None,
        n_time_to_hire_computed=0,
        avg_time_to_reject_days=None,
        n_time_to_reject_computed=0,
        invalid_date_sequences_excluded=0,
        date_quality_warnings=[],
        department_normalization_notes=[],
        stage_normalization_notes=[],
        narrative_en=reason,
        narrative_ar="لا تتوفر بيانات مسار التوظيف في مجموعة البيانات المرفوعة.",
        governance_note=(
            "Recruitment pipeline tracking activates automatically when the "
            "uploaded dataset contains a recognisable pipeline-stage column. "
            "No funnel, conversion rate, or time-to-hire figure is ever "
            "fabricated when this data is absent."
        ),
        sources=[],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def analyze_recruitment_pipeline(df: pd.DataFrame) -> RecruitmentPipelineResult:
    """
    Analyze a recruitment/hiring dataset's pipeline funnel, conversion rates,
    time-to-hire, drop-off points, and (if present) rejection-reason themes.

    Returns `available=False` — never a fabricated funnel — when no
    recognisable pipeline-stage column is found. See module docstring for
    the full list of reused components (department_normalizer.py,
    exit_interview_intelligence_engine.py, financial_intelligence_engine.py)
    and why stage normalization is implemented locally rather than through
    department_normalizer.py.
    """
    if df is None or len(df) == 0:
        return unavailable_recruitment_result(
            "Uploaded dataset is empty — no recruitment pipeline analysis possible."
        )

    n_total = len(df)

    candidate_id_col = _find_column(df, _CANDIDATE_ID_PATTERNS)
    stage_col = _find_column(df, _STAGE_PATTERNS)
    application_date_col = _find_column(df, _APPLICATION_DATE_PATTERNS)
    offer_date_col = _find_column(df, _OFFER_DATE_PATTERNS)
    hire_date_col = _find_column(df, _HIRE_DATE_PATTERNS)
    rejection_date_col = _find_column(df, _REJECTION_DATE_PATTERNS)
    source_col = _find_column(df, _SOURCE_PATTERNS)
    rejection_reason_col = _find_column(df, _REJECTION_REASON_PATTERNS)
    dept_col = _find_column(df, _ROLE_OR_DEPARTMENT_PATTERNS)
    cost_col = _find_column(df, _RECRUITMENT_COST_PATTERNS)

    columns_detected = {
        "candidate_id": candidate_id_col is not None,
        "stage": stage_col is not None,
        "application_date": application_date_col is not None,
        "offer_date": offer_date_col is not None,
        "hire_date": hire_date_col is not None,
        "rejection_date": rejection_date_col is not None,
        "source": source_col is not None,
        "rejection_reason": rejection_reason_col is not None,
        "department_or_role": dept_col is not None,
        "recruitment_cost": cost_col is not None,
    }

    # The pipeline-stage column is the essential signal — without it, there
    # is no funnel to report, regardless of what else is present.
    if stage_col is None:
        missing = ", ".join(
            _ALL_COLUMN_LABELS[k] for k, present in columns_detected.items() if not present
        )
        return unavailable_recruitment_result(
            "No recruitment pipeline-stage column was detected in this dataset "
            "(e.g. a column named 'Stage' or 'Status' with values like Applied/"
            "Screening/Interview/Offer/Hired/Rejected). This looks like "
            "structured HR employee data, not recruitment/candidate data. "
            f"Columns that would activate this feature if present: {missing}.",
            columns_detected=columns_detected,
        )

    # ── Stage normalization (own domain — see module docstring) ────────────
    normalized_stage, stage_notes = _normalize_stage_series(df[stage_col])
    work = pd.DataFrame({"_stage": normalized_stage})

    # ── Department/role normalization (shared canonical fix) ───────────────
    dept_notes: list[str] = []
    if dept_col is not None:
        dept_norm = normalize_department_series(df[dept_col])
        work["_dept"] = dept_norm.normalized_keys.map(
            lambda k: dept_norm.display_labels.get(k, k)
        ).values
        for merge in dept_norm.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}' "
                f"(recognised as the same department): {merge.counts_per_variant}."
            )
        for group in dept_norm.unmerged_similar_variants:
            dept_notes.append(
                f"Found similarly-named but NOT merged department values "
                f"{', '.join(repr(v) for v in group)} — review manually."
            )

    if source_col is not None:
        work["_source"] = df[source_col].map(
            lambda v: "Unspecified" if _is_missing_value(v) else " ".join(str(v).split())
        ).values

    # ── Date parsing + invalid-sequence guard ───────────────────────────────
    date_quality_warnings: list[str] = []
    app_dates = pd.to_datetime(df[application_date_col], errors="coerce") if application_date_col else None
    hire_dates = pd.to_datetime(df[hire_date_col], errors="coerce") if hire_date_col else None
    reject_dates = pd.to_datetime(df[rejection_date_col], errors="coerce") if rejection_date_col else None

    avg_time_to_hire_days: Optional[float] = None
    n_time_to_hire_computed = 0
    invalid_hire_sequences = 0
    if app_dates is not None and hire_dates is not None:
        both_present = app_dates.notna() & hire_dates.notna()
        deltas = (hire_dates - app_dates).dt.days
        valid = both_present & (deltas >= 0)
        invalid_hire_sequences = int((both_present & (deltas < 0)).sum())
        n_time_to_hire_computed = int(valid.sum())
        if n_time_to_hire_computed > 0:
            avg_time_to_hire_days = round(float(deltas[valid].mean()), 1)

    avg_time_to_reject_days: Optional[float] = None
    n_time_to_reject_computed = 0
    invalid_reject_sequences = 0
    if app_dates is not None and reject_dates is not None:
        both_present = app_dates.notna() & reject_dates.notna()
        deltas = (reject_dates - app_dates).dt.days
        valid = both_present & (deltas >= 0)
        invalid_reject_sequences = int((both_present & (deltas < 0)).sum())
        n_time_to_reject_computed = int(valid.sum())
        if n_time_to_reject_computed > 0:
            avg_time_to_reject_days = round(float(deltas[valid].mean()), 1)

    invalid_total = invalid_hire_sequences + invalid_reject_sequences
    if invalid_hire_sequences > 0:
        date_quality_warnings.append(
            f"{invalid_hire_sequences} row(s) had a hire date before the application "
            "date (an impossible sequence) — excluded from the time-to-hire average "
            "rather than silently producing a negative duration."
        )
    if invalid_reject_sequences > 0:
        date_quality_warnings.append(
            f"{invalid_reject_sequences} row(s) had a rejection date before the "
            "application date (an impossible sequence) — excluded from the "
            "time-to-reject average."
        )

    # ── Current-stage distribution (simple histogram — see module docstring:
    #    a static export has no per-candidate stage-history) ────────────────
    stage_counts = work["_stage"].value_counts()
    n_rejected = int(stage_counts.get(_TERMINAL_REJECTED, 0))
    rejection_rate_pct = round(100.0 * n_rejected / n_total, 1) if n_total else None

    # ── Ordinal funnel + conversion (Hired implies every prior ladder stage
    #    was reached — a standard, explicitly-disclosed funnel convention,
    #    not a claim of observed per-candidate history) ─────────────────────
    # Every row in a recruitment dataset represents someone who applied, so
    # "Rejected" and unrecognized stage values still count toward the
    # "Applied" floor (rank 0) — they just don't count toward later stages,
    # since we have no evidence of how far they progressed before rejection.
    stage_rank = {s: i for i, s in enumerate(_STAGE_ORDER)}
    ladder_reached = pd.Series(
        [stage_rank.get(s, 0) for s in work["_stage"]], index=work.index,
    )
    current_stage_distribution: list[StageFunnelCount] = []
    prev_reached: Optional[int] = None
    for i, stage_name in enumerate(_STAGE_ORDER):
        n_reached = int((ladder_reached >= i).sum())
        conversion = None
        if prev_reached is not None:
            conversion = round(100.0 * n_reached / prev_reached, 1) if prev_reached > 0 else 0.0
        current_stage_distribution.append(StageFunnelCount(
            stage=stage_name,
            n_candidates=n_reached,
            pct_of_total=round(100.0 * n_reached / n_total, 1) if n_total else 0.0,
            conversion_from_previous_pct=conversion,
        ))
        prev_reached = n_reached

    biggest_dropoff_stage: Optional[str] = None
    worst_conversion = 101.0
    for sf in current_stage_distribution:
        if sf.conversion_from_previous_pct is not None and sf.conversion_from_previous_pct < worst_conversion:
            worst_conversion = sf.conversion_from_previous_pct
            biggest_dropoff_stage = sf.stage

    # ── Department/role breakdown (hire rate) ───────────────────────────────
    department_breakdown: list[DepartmentPipelineBreakdown] = []
    if "_dept" in work.columns:
        for dept_name, grp in work.groupby("_dept"):
            n_grp = len(grp)
            n_hired_grp = int((grp["_stage"] == "Hired").sum())
            department_breakdown.append(DepartmentPipelineBreakdown(
                department=str(dept_name),
                n_candidates=n_grp,
                n_hired=n_hired_grp,
                hire_rate_pct=round(100.0 * n_hired_grp / n_grp, 1) if n_grp else 0.0,
            ))
        department_breakdown.sort(key=lambda d: d.hire_rate_pct)

    # ── Source/channel breakdown (hire rate) ────────────────────────────────
    source_breakdown: list[SourceChannelBreakdown] = []
    if "_source" in work.columns:
        for source_name, grp in work.groupby("_source"):
            n_grp = len(grp)
            n_hired_grp = int((grp["_stage"] == "Hired").sum())
            source_breakdown.append(SourceChannelBreakdown(
                source=str(source_name),
                n_candidates=n_grp,
                n_hired=n_hired_grp,
                hire_rate_pct=round(100.0 * n_hired_grp / n_grp, 1) if n_grp else 0.0,
            ))
        source_breakdown.sort(key=lambda s: s.hire_rate_pct)

    # ── Rejection-reason themes (reuses exit_interview engine wholesale) ────
    rejection_reason_themes: Optional[dict] = None
    if rejection_reason_col is not None:
        responses = [
            str(v) for v in df[rejection_reason_col]
            if not _is_missing_value(v)
        ]
        if len(responses) >= MIN_RESPONSES_FOR_AGGREGATE:
            theme_result = analyze_exit_interview_text(responses)
            rejection_reason_themes = exit_interview_intelligence_to_dict(theme_result)

    # ── Cost per hire (never a new formula — see module docstring) ─────────
    cost_per_hire_sar: Optional[float] = None
    cost_per_hire_confidence: Optional[str] = None
    n_hired_total = int(stage_counts.get("Hired", 0))
    if n_hired_total > 0:
        if cost_col is not None:
            observed_costs = pd.to_numeric(df[cost_col], errors="coerce").dropna()
            if len(observed_costs) > 0:
                cost_per_hire_sar = round(float(observed_costs.mean()), 0)
                cost_per_hire_confidence = "observed"
        if cost_per_hire_sar is None:
            monthly_salary = estimate_monthly_salary("diversified", "mid")
            cost_per_hire_sar = round(monthly_salary * 12 * 0.20, 0)
            cost_per_hire_confidence = SECTOR_BENCHMARK_CONFIDENCE

    # ── Narrative (non-causal, honest about the funnel-convention used) ────
    hire_rate_overall = round(100.0 * n_hired_total / n_total, 1) if n_total else 0.0
    narrative_en = (
        f"Of {n_total} candidates in this dataset, {n_hired_total} ({hire_rate_overall:.1f}%) "
        f"reached 'Hired'. {n_rejected} ({rejection_rate_pct:.1f}%) were marked 'Rejected'. "
        "Stage figures reflect each candidate's current or final recorded stage, not an "
        "observed per-candidate timeline — a candidate at 'Hired' is counted as having "
        "reached every earlier stage."
    )
    narrative_ar = (
        f"من أصل {n_total} مرشحاً في هذه البيانات، وصل {n_hired_total} "
        f"({hire_rate_overall:.1f}%) إلى مرحلة 'تم التعيين'. تم رفض {n_rejected} "
        f"({rejection_rate_pct:.1f}%)."
    )

    sources: list[str] = [
        "Department/role grouping reuses backend/core/department_normalizer.py "
        "(the same fix applied to HR department data).",
    ]
    if rejection_reason_themes is not None:
        sources.append(
            "Rejection-reason theme extraction reuses "
            "backend/core/exit_interview_intelligence_engine.py's analyze_exit_interview_text()."
        )
    if cost_per_hire_confidence == "observed":
        sources.append("Cost per hire computed directly from the uploaded dataset's own cost column.")
    elif cost_per_hire_confidence == SECTOR_BENCHMARK_CONFIDENCE:
        sources.append(
            "Cost per hire estimated as ~20% of one year's estimated salary "
            "(financial_intelligence_engine.py's estimate_monthly_salary()) — a "
            "widely repeated general HR rule of thumb, NOT a Saudi-market-specific "
            "citation. No freely citable Saudi cost-per-hire benchmark was found."
        )

    return RecruitmentPipelineResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        n_candidates_total=n_total,
        current_stage_distribution=current_stage_distribution,
        department_breakdown=department_breakdown,
        source_breakdown=source_breakdown,
        biggest_dropoff_stage=biggest_dropoff_stage,
        n_rejected=n_rejected,
        rejection_rate_pct=rejection_rate_pct,
        avg_time_to_hire_days=avg_time_to_hire_days,
        n_time_to_hire_computed=n_time_to_hire_computed,
        avg_time_to_reject_days=avg_time_to_reject_days,
        n_time_to_reject_computed=n_time_to_reject_computed,
        invalid_date_sequences_excluded=invalid_total,
        date_quality_warnings=date_quality_warnings,
        department_normalization_notes=dept_notes,
        stage_normalization_notes=stage_notes,
        rejection_reason_themes=rejection_reason_themes,
        cost_per_hire_sar=cost_per_hire_sar,
        cost_per_hire_confidence=cost_per_hire_confidence,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        governance_note=(
            "Recruitment pipeline figures are statistical indicators for HR planning, "
            "never a substitute for reviewing individual candidate records, and must "
            "not be used as the sole basis for hiring decisions. Stage-reach counts "
            "assume later stages imply earlier ones were passed, and every candidate "
            "(including those later rejected) counts toward the 'Applied' floor — "
            "this dataset does not contain a per-candidate stage-history timeline."
        ),
        sources=sources,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def recruitment_pipeline_to_dict(r: RecruitmentPipelineResult) -> dict[str, Any]:
    """Serialize RecruitmentPipelineResult to a JSON-safe dict."""
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "n_candidates_total": r.n_candidates_total,
        "current_stage_distribution": [
            {
                "stage": s.stage,
                "n_candidates": s.n_candidates,
                "pct_of_total": s.pct_of_total,
                "conversion_from_previous_pct": s.conversion_from_previous_pct,
            }
            for s in r.current_stage_distribution
        ],
        "department_breakdown": [
            {
                "department": d.department,
                "n_candidates": d.n_candidates,
                "n_hired": d.n_hired,
                "hire_rate_pct": d.hire_rate_pct,
            }
            for d in r.department_breakdown
        ],
        "source_breakdown": [
            {
                "source": s.source,
                "n_candidates": s.n_candidates,
                "n_hired": s.n_hired,
                "hire_rate_pct": s.hire_rate_pct,
            }
            for s in r.source_breakdown
        ],
        "biggest_dropoff_stage": r.biggest_dropoff_stage,
        "n_rejected": r.n_rejected,
        "rejection_rate_pct": r.rejection_rate_pct,
        "avg_time_to_hire_days": r.avg_time_to_hire_days,
        "n_time_to_hire_computed": r.n_time_to_hire_computed,
        "avg_time_to_reject_days": r.avg_time_to_reject_days,
        "n_time_to_reject_computed": r.n_time_to_reject_computed,
        "invalid_date_sequences_excluded": r.invalid_date_sequences_excluded,
        "date_quality_warnings": r.date_quality_warnings,
        "department_normalization_notes": r.department_normalization_notes,
        "stage_normalization_notes": r.stage_normalization_notes,
        "rejection_reason_themes": r.rejection_reason_themes,
        "cost_per_hire_sar": r.cost_per_hire_sar,
        "cost_per_hire_confidence": r.cost_per_hire_confidence,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
