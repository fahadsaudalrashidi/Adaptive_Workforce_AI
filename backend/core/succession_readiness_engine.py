"""
Succession Planning / Internal Mobility Readiness — Phase 8.

**Why this exists, and why it doesn't reuse the dead `CareerProgression`/
`TenureRatio` constructs verbatim** (see SUCCESSION_READINESS_INVESTIGATION.md
for the full trace): those two paper-formula constructs in
`theory_grounded_construct_engine.py` are well-designed but (a) confirmed
dead — reachable only from an endpoint `executive-ui` never calls — and
(b) `TenureRatio` requires `TotalWorkingYears`, a column that does not exist
in any fixture in this repository. Substituting `YearsAtCompany` in its
place would silently change the ratio's actual meaning (Mobley's theory
distinguishes organizational tenure from total career tenure) and produce a
near-constant, non-discriminating value for anyone with meaningful
company tenure — the same "number that looks scientific but carries no
real signal" failure class this session already found and fixed twice (the
`ethical_ai.py` age-disparity bug, the Nitaqat premium constant). Instead,
this is a new, purpose-built engine using columns confirmed genuinely
present in real data today.

**Honest framing (same discipline as `nitaqat_compliance_engine.py`, but a
different kind of caveat):** the *inputs* here (PerformanceRating,
YearsAtCompany, JobLevel, PromotionFairness) are real, directly-relevant HR
signals — unlike Nitaqat, where the underlying HRSD formula itself is
unavailable, here the inputs are trustworthy. What is NOT validated is the
specific *combination formula* below: it is this platform's own constructed
heuristic for turning those real inputs into a single "readiness score,"
not a peer-reviewed or vendor-validated instrument. Every result therefore
carries `is_validated_instrument=False` and an explicit disclaimer.

**Core formula:**
    performance_percentile = 100 * (rating - min_observed) / (max_observed - min_observed)
    tenure_factor           = min(1.0, YearsAtCompany / TENURE_WINDOW_YEARS)
    readiness_score          = performance_percentile * tenure_factor

Plain-language logic: sustained high performance over a reasonable tenure
window signals promotion/internal-mobility readiness. `tenure_factor`
saturates at 1.0 after `TENURE_WINDOW_YEARS` (an illustrative "long enough
to have demonstrated it's not a new-hire honeymoon rating" window, not a
validated cutoff) — a brand-new high performer is not penalized forever,
just not yet credited with having *sustained* it. `performance_percentile`
is computed relative to the observed min/max *within the uploaded dataset*
(not a fixed assumed scale like 1-4 or 1-5), since different real HR exports
use different rating scales — this is a deliberate design choice to avoid
assuming a scale that might not match the real uploaded file, at the cost
of being a within-dataset relative measure rather than an absolute one
(disclosed in every result).

**Optional richer signals, gracefully degrading when absent:**
  - "Stuck high performer": if `JobLevel` is present, flags a top-quartile
    performer who has spent a top-quartile *tenure* relative to same-JobLevel
    peers — approximating "time in current level" from `YearsAtCompany`
    since no level-change-date column exists in any real fixture today (a
    documented approximation, not a precise value).
  - Promotion-fairness cross-reference: if a `PromotionFairness`-style
    Likert column is present (see `theory_aware_column_mapper.py`'s
    construct of the same name), flags "high readiness + low promotion-
    fairness perception" — a specific, actionable combination (a strong
    internal candidate who feels overlooked), distinct from either signal
    alone.

**Designed for future enhancement, not future rebuild:** `TotalWorkingYears`
(a richer tenure denominator), actual promotion-date history (replacing the
`YearsAtCompany`-as-proxy approximation for "time in current level"), and
training-completion data are all plausible future optional inputs. The
per-employee computation is isolated in `_compute_candidate()` specifically
so a future session can add these as additional optional parameters with a
graceful fallback to today's formula when absent, rather than needing to
redesign the module — see that function's docstring.

**Department grouping** reuses `backend/core/department_normalizer.py`
verbatim, same as every other module this session with a department/sector
dimension. **Deduplication** is not reimplemented — `SecureFileIngestion.scan()`
already deduplicates every uploaded dataframe once, pipeline-level, before
this module ever sees it. **Per-employee identifiers** are one-way hashed
using the exact same scheme as `employee_risk_scoring.py`'s
`_make_record_id()` (sha256, first 6 hex chars, `EMP-XXXXXX` format) — no
raw employee identifier is ever returned.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series

# ── Column detection patterns (English + Arabic, this codebase's convention) ──

_PERFORMANCE_PATTERNS = re.compile(
    r"\b(performance[_\s]?rating|performance[_\s]?score|perf[_\s]?rating|"
    r"تقييم[_\s]?الأداء)\b",
    re.I,
)
_TENURE_PATTERNS = re.compile(
    r"\b(years[_\s]?at[_\s]?company|tenure[_\s]?years|tenure|years[_\s]?of[_\s]?service|"
    r"سنوات[_\s]?الخدمة|مدة[_\s]?العمل)\b",
    re.I,
)
_JOB_LEVEL_PATTERNS = re.compile(
    r"\b(job[_\s]?level|joblevel|career[_\s]?level|grade[_\s]?level|"
    r"المستوى[_\s]?الوظيفي|الدرجة[_\s]?الوظيفية)\b",
    re.I,
)
_PROMOTION_FAIRNESS_PATTERNS = re.compile(
    r"\b(promotion[_\s]?fairness|promotion[_\s]?justice|promotion[_\s]?equity|"
    r"عدالة[_\s]?الترقية|إنصاف[_\s]?الترقية)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b",
    re.I,
)

# ── Illustrative constants (this module's own construction — see docstring) ──

TENURE_WINDOW_YEARS = 2.0
# High/low percentile cut points for the optional "stuck high performer" and
# promotion-fairness cross-reference signals — quartile-based, round numbers,
# not validated cutoffs.
HIGH_PERFORMANCE_PERCENTILE_THRESHOLD = 75.0
LOW_FAIRNESS_PERCENTILE_THRESHOLD = 25.0
STUCK_TENURE_PERCENTILE_THRESHOLD = 75.0
# Same small-sample-suppression discipline as config.settings.MIN_DEPT_GROUP_SIZE
# (5) — a same-JobLevel peer cohort smaller than this produces a meaningless
# tenure percentile, so the stuck-performer signal is skipped for that cohort
# rather than computed on noise.
MIN_PEER_GROUP_SIZE_FOR_STUCK_SIGNAL = 5

READINESS_TIER_THRESHOLDS: dict[str, float] = {
    "High Readiness": 70.0,
    "Emerging Readiness": 40.0,
    "Developing": 0.0,
}

IS_VALIDATED_INSTRUMENT = False
READINESS_CALCULATION_CONFIDENCE = "constructed_heuristic_not_validated"
READINESS_DISCLAIMER_EN = (
    "Constructed heuristic — NOT a validated psychometric or vendor-benchmarked "
    "succession-planning instrument. The underlying inputs (performance rating, "
    "tenure) are real data from your upload, but the specific formula combining "
    "them into a single readiness score is this platform's own construction, "
    "not a peer-reviewed replication. Use as a discussion starting point for "
    "HR/talent review, never as the sole basis for promotion or succession decisions."
)
READINESS_DISCLAIMER_AR = (
    "أداة إرشادية من تصميم هذه المنصة — وليست أداة نفسية معتمدة أو مقاسة مقابل "
    "معيار صناعي لتخطيط التعاقب الوظيفي. المدخلات (تقييم الأداء، مدة الخدمة) "
    "بيانات حقيقية من الملف الذي تم تحميله، لكن الصيغة التي تجمعها في درجة "
    "جاهزية واحدة هي بناء داخلي لهذه المنصة وليست نسخة علمية موثقة. تُستخدم "
    "كنقطة انطلاق للنقاش مع فريق الموارد البشرية، وليست الأساس الوحيد لأي قرار ترقية."
)


def _is_missing_value(raw: object) -> bool:
    """Same missing-value discipline established across this codebase's other
    Phase 5-7 fixes — checked before any string/numeric operation."""
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _make_record_id(raw_id: Any, idx: int) -> str:
    """Same one-way-hash scheme as employee_risk_scoring.py's _make_record_id."""
    if raw_id is not None and not _is_missing_value(raw_id):
        h = hashlib.sha256(str(raw_id).encode()).hexdigest()[:6].upper()
        return f"EMP-{h}"
    return f"EMP-{idx + 1:04d}"


def _percentile_within_series(series: pd.Series) -> pd.Series:
    """Min-max normalize a numeric series to 0-100 within its own observed
    range. Returns 50.0 for every value when the series is constant (no
    signal to differentiate on — never divides by zero)."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series([50.0] * len(series), index=series.index)
    return ((series - lo) / (hi - lo) * 100.0).round(1)


def _tier_for_score(score: float) -> str:
    for tier in ["High Readiness", "Emerging Readiness"]:
        if score >= READINESS_TIER_THRESHOLDS[tier]:
            return tier
    return "Developing"


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReadinessCandidate:
    record_id_safe: str
    department: Optional[str]
    performance_percentile: float
    tenure_years: float
    readiness_score: float
    readiness_tier: str
    is_stuck_high_performer: bool
    high_readiness_low_fairness_flag: bool
    # Phase 40 — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md
    # §3. This platform is used single-tenant on the uploader's own local
    # data, so the REAL uploaded ID (when present) is shown alongside
    # record_id_safe (kept unchanged for cross-link compatibility).
    employee_id_raw: Optional[str] = None


@dataclass(frozen=True)
class DepartmentReadinessBreakdown:
    department: str
    n_total: int
    n_high_readiness: int
    avg_readiness_score: float


@dataclass(frozen=True)
class SuccessionReadinessResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_total: int
    n_high_readiness: int
    n_stuck_high_performers: int
    n_high_readiness_low_fairness: int
    avg_readiness_score: Optional[float]
    top_candidates: list[ReadinessCandidate]
    high_readiness_record_ids: list[str]
    department_breakdown: list[DepartmentReadinessBreakdown]
    department_normalization_notes: list[str]
    formula_description_en: str
    formula_description_ar: str
    is_validated_instrument: bool
    calculation_confidence: str
    narrative_en: str
    narrative_ar: str
    governance_note: str
    disclaimer_en: str
    disclaimer_ar: str
    sources: list[str]
    computed_at: str


_ALL_COLUMN_LABELS: dict[str, str] = {
    "performance_rating": "performance rating (e.g. PerformanceRating)",
    "tenure_years": "tenure / years at company (e.g. YearsAtCompany)",
    "job_level": "job level / career grade (optional — enables the 'stuck high performer' signal)",
    "promotion_fairness": "promotion fairness/justice perception (optional — enables the readiness + low-fairness cross-reference)",
    "department_or_sector": "department (optional, for a per-department breakdown)",
}

_FORMULA_DESCRIPTION_EN = (
    "readiness_score = performance_percentile x tenure_factor, where "
    "performance_percentile is the employee's performance rating normalized "
    f"0-100 relative to the range observed in this dataset, and tenure_factor "
    f"= min(1.0, YearsAtCompany / {TENURE_WINDOW_YEARS}) — full credit once "
    f"tenure reaches {TENURE_WINDOW_YEARS} years, partial credit before that."
)
_FORMULA_DESCRIPTION_AR = (
    "درجة الجاهزية = النسبة المئوية للأداء × عامل مدة الخدمة، حيث تُحسب "
    "النسبة المئوية للأداء بالنسبة للنطاق الملاحظ في هذه البيانات، ويُحسب عامل "
    f"مدة الخدمة كنسبة سنوات الخدمة إلى {TENURE_WINDOW_YEARS} سنة (بحد أقصى 1.0)."
)


def unavailable_succession_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> SuccessionReadinessResult:
    """Public constructor for an `available=False` result — used both when
    required columns are absent and by API routes that need to
    short-circuit before calling analyze_succession_readiness()."""
    return SuccessionReadinessResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {k: False for k in _ALL_COLUMN_LABELS},
        n_total=0,
        n_high_readiness=0,
        n_stuck_high_performers=0,
        n_high_readiness_low_fairness=0,
        avg_readiness_score=None,
        top_candidates=[],
        high_readiness_record_ids=[],
        department_breakdown=[],
        department_normalization_notes=[],
        formula_description_en=_FORMULA_DESCRIPTION_EN,
        formula_description_ar=_FORMULA_DESCRIPTION_AR,
        is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        calculation_confidence=READINESS_CALCULATION_CONFIDENCE,
        narrative_en=reason,
        narrative_ar="لا تتوفر بيانات كافية لتقدير جاهزية الترقية/التنقل الداخلي في هذه البيانات.",
        governance_note=(
            "Succession/internal-mobility readiness estimation activates "
            "automatically when the uploaded dataset contains both a "
            "performance-rating and a tenure column. No readiness score is "
            "ever fabricated when this data is absent."
        ),
        disclaimer_en=READINESS_DISCLAIMER_EN,
        disclaimer_ar=READINESS_DISCLAIMER_AR,
        sources=[],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def _compute_candidate(
    record_id: str,
    department: Optional[str],
    performance_pct: float,
    tenure_years: float,
    is_stuck: bool,
    low_fairness_flag: bool,
    # Future-enhancement optional parameters (see module docstring): when a
    # future real dataset provides these, this function can incorporate them
    # without changing its external contract for callers that don't have
    # them. Not used today because no fixture provides them.
    total_working_years: Optional[float] = None,
    promotion_date_years_ago: Optional[float] = None,
    training_completions: Optional[int] = None,
    employee_id_raw: Optional[str] = None,
) -> ReadinessCandidate:
    """
    Compute one employee's readiness candidate record.

    Isolated as its own function specifically so a future session can extend
    it with richer optional inputs (TotalWorkingYears, real promotion-date
    history replacing the YearsAtCompany-as-proxy approximation, training
    completions) via new optional parameters with a documented graceful
    fallback to today's simpler formula when they're absent — not a rebuild.
    """
    tenure_factor = min(1.0, tenure_years / TENURE_WINDOW_YEARS)
    readiness_score = round(performance_pct * tenure_factor, 1)
    return ReadinessCandidate(
        record_id_safe=record_id,
        department=department,
        performance_percentile=performance_pct,
        tenure_years=round(tenure_years, 2),
        readiness_score=readiness_score,
        readiness_tier=_tier_for_score(readiness_score),
        is_stuck_high_performer=is_stuck,
        high_readiness_low_fairness_flag=low_fairness_flag,
        employee_id_raw=employee_id_raw,
    )


def analyze_succession_readiness(df: pd.DataFrame) -> SuccessionReadinessResult:
    """
    Estimate a CONSTRUCTED-HEURISTIC succession/internal-mobility readiness
    score per employee from real performance and tenure data. Returns
    `available=False` — never a fabricated score — when the two required
    columns (a performance rating and a tenure/years-at-company column) are
    not both found. See module docstring for the full honesty framing.
    """
    if df is None or len(df) == 0:
        return unavailable_succession_result(
            "Uploaded dataset is empty — no succession readiness estimate possible."
        )

    perf_col = _find_column(df, _PERFORMANCE_PATTERNS)
    tenure_col = _find_column(df, _TENURE_PATTERNS)
    job_level_col = _find_column(df, _JOB_LEVEL_PATTERNS)
    fairness_col = _find_column(df, _PROMOTION_FAIRNESS_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)

    columns_detected = {
        "performance_rating": perf_col is not None,
        "tenure_years": tenure_col is not None,
        "job_level": job_level_col is not None,
        "promotion_fairness": fairness_col is not None,
        "department_or_sector": dept_col is not None,
    }

    if perf_col is None or tenure_col is None:
        missing = ", ".join(
            _ALL_COLUMN_LABELS[k] for k in ("performance_rating", "tenure_years")
            if not columns_detected[k]
        )
        return unavailable_succession_result(
            "No performance-rating and/or tenure column was detected in this "
            "dataset. Succession readiness estimation requires both. "
            f"Missing: {missing}.",
            columns_detected=columns_detected,
        )

    work = pd.DataFrame({
        "_perf_raw": pd.to_numeric(df[perf_col], errors="coerce"),
        "_tenure_raw": pd.to_numeric(df[tenure_col], errors="coerce"),
    })
    valid_mask = work["_perf_raw"].notna() & work["_tenure_raw"].notna() & (work["_tenure_raw"] >= 0)
    work = work[valid_mask].copy()
    original_index = work.index

    if len(work) == 0:
        return unavailable_succession_result(
            f"'{perf_col}' and '{tenure_col}' columns were found but contained "
            "no usable paired numeric values.",
            columns_detected=columns_detected,
        )

    work["_perf_pct"] = _percentile_within_series(work["_perf_raw"])

    # ── Optional: JobLevel-based "stuck high performer" signal ─────────────
    work["_is_stuck"] = False
    if job_level_col is not None:
        levels = pd.to_numeric(df.loc[original_index, job_level_col], errors="coerce")
        work["_level"] = levels
        for level_val, grp_idx in work.dropna(subset=["_level"]).groupby("_level").groups.items():
            if len(grp_idx) < MIN_PEER_GROUP_SIZE_FOR_STUCK_SIGNAL:
                continue  # peer cohort too small for a meaningful percentile — skip, don't guess
            tenure_pct_in_level = work.loc[grp_idx, "_tenure_raw"].rank(pct=True) * 100.0
            stuck_mask = (
                (work.loc[grp_idx, "_perf_pct"] >= HIGH_PERFORMANCE_PERCENTILE_THRESHOLD)
                & (tenure_pct_in_level >= STUCK_TENURE_PERCENTILE_THRESHOLD)
            )
            work.loc[grp_idx, "_is_stuck"] = stuck_mask.reindex(grp_idx, fill_value=False)

    # ── Optional: promotion-fairness cross-reference ────────────────────────
    work["_low_fairness_flag"] = False
    if fairness_col is not None:
        fairness_raw = pd.to_numeric(df.loc[original_index, fairness_col], errors="coerce")
        fairness_valid = fairness_raw.dropna()
        if len(fairness_valid) > 0:
            fairness_pct = _percentile_within_series(fairness_raw)
            tenure_factor_tmp = (work["_tenure_raw"] / TENURE_WINDOW_YEARS).clip(upper=1.0)
            readiness_tmp = work["_perf_pct"] * tenure_factor_tmp
            work["_low_fairness_flag"] = (
                (readiness_tmp >= READINESS_TIER_THRESHOLDS["High Readiness"])
                & (fairness_pct <= LOW_FAIRNESS_PERCENTILE_THRESHOLD)
            ).fillna(False)

    # ── Department normalization (shared canonical fix) ─────────────────────
    dept_notes: list[str] = []
    dept_labels: Optional[pd.Series] = None
    if dept_col is not None:
        dept_norm = normalize_department_series(df.loc[original_index, dept_col])
        dept_labels = dept_norm.normalized_keys.map(
            lambda k: dept_norm.display_labels.get(k, k)
        )
        dept_labels.index = original_index
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

    # ── Per-employee candidates ─────────────────────────────────────────────
    id_col = None
    for candidate_name in ("EmployeeID", "employee_id", "EmpID", "emp_id"):
        if candidate_name in df.columns:
            id_col = candidate_name
            break

    candidates: list[ReadinessCandidate] = []
    for pos, idx in enumerate(original_index):
        raw_id = df.loc[idx, id_col] if id_col else None
        dept_val = str(dept_labels.loc[idx]) if dept_labels is not None else None
        candidates.append(_compute_candidate(
            record_id=_make_record_id(raw_id, pos),
            department=dept_val,
            performance_pct=float(work.loc[idx, "_perf_pct"]),
            tenure_years=float(work.loc[idx, "_tenure_raw"]),
            is_stuck=bool(work.loc[idx, "_is_stuck"]),
            low_fairness_flag=bool(work.loc[idx, "_low_fairness_flag"]),
            employee_id_raw=(str(raw_id).strip() if raw_id is not None and not _is_missing_value(raw_id) else None),
        ))

    n_total = len(candidates)
    n_high_readiness = sum(1 for c in candidates if c.readiness_tier == "High Readiness")
    n_stuck = sum(1 for c in candidates if c.is_stuck_high_performer)
    n_low_fairness_combo = sum(1 for c in candidates if c.high_readiness_low_fairness_flag)
    avg_readiness = round(sum(c.readiness_score for c in candidates) / n_total, 1) if n_total else None

    top_candidates = sorted(candidates, key=lambda c: c.readiness_score, reverse=True)[:20]
    # Full high-readiness ID list (not just the top-20 display slice) — this
    # is what a Nitaqat cross-link join needs to count correctly; see
    # nitaqat_compliance_engine.py's get_saudi_status_by_record_id().
    high_readiness_record_ids = [
        c.record_id_safe for c in candidates if c.readiness_tier == "High Readiness"
    ]

    # ── Department breakdown ─────────────────────────────────────────────────
    department_breakdown: list[DepartmentReadinessBreakdown] = []
    if dept_labels is not None:
        by_dept: dict[str, list[ReadinessCandidate]] = {}
        for c in candidates:
            by_dept.setdefault(c.department or "Unknown", []).append(c)
        for dept_name, recs in sorted(by_dept.items()):
            n_grp = len(recs)
            n_grp_high = sum(1 for r in recs if r.readiness_tier == "High Readiness")
            avg_grp = round(sum(r.readiness_score for r in recs) / n_grp, 1) if n_grp else 0.0
            department_breakdown.append(DepartmentReadinessBreakdown(
                department=dept_name, n_total=n_grp, n_high_readiness=n_grp_high,
                avg_readiness_score=avg_grp,
            ))
        department_breakdown.sort(key=lambda d: d.avg_readiness_score, reverse=True)

    narrative_en = (
        f"Of {n_total} employees with usable performance and tenure data, "
        f"{n_high_readiness} ({100.0 * n_high_readiness / n_total:.1f}%) fall in the "
        f"'High Readiness' tier. Average readiness score: {avg_readiness}. "
        + (f"{n_stuck} flagged as a 'stuck high performer' (top-quartile performance, "
           "top-quartile tenure at current job level). " if job_level_col else "")
        + (f"{n_low_fairness_combo} show the high-readiness + low-promotion-fairness-"
           "perception combination. " if fairness_col else "")
        + "This is a constructed heuristic, not a validated instrument — see disclaimer."
    )
    narrative_ar = (
        f"من أصل {n_total} موظفاً ببيانات أداء ومدة خدمة قابلة للاستخدام، "
        f"{n_high_readiness} ({100.0 * n_high_readiness / n_total:.1f}%) ضمن مستوى "
        f"'جاهزية عالية'. متوسط درجة الجاهزية: {avg_readiness}. أداة إرشادية وليست معتمدة علمياً."
    )

    sources: list[str] = [
        "Formula is this platform's own constructed heuristic combining real "
        "performance-rating and tenure data — not a validated psychometric "
        "instrument (see module docstring and disclaimer).",
    ]
    if dept_col is not None:
        sources.append(
            "Department grouping reuses backend/core/department_normalizer.py "
            "(the same fix applied to HR department data)."
        )
    if job_level_col is not None:
        sources.append(
            "'Stuck high performer' signal approximates 'time in current level' "
            "from YearsAtCompany since no promotion-date/level-change-date column "
            "exists in any real fixture available today — a documented approximation."
        )

    return SuccessionReadinessResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        n_total=n_total,
        n_high_readiness=n_high_readiness,
        n_stuck_high_performers=n_stuck,
        n_high_readiness_low_fairness=n_low_fairness_combo,
        avg_readiness_score=avg_readiness,
        top_candidates=top_candidates,
        high_readiness_record_ids=high_readiness_record_ids,
        department_breakdown=department_breakdown,
        department_normalization_notes=dept_notes,
        formula_description_en=_FORMULA_DESCRIPTION_EN,
        formula_description_ar=_FORMULA_DESCRIPTION_AR,
        is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        calculation_confidence=READINESS_CALCULATION_CONFIDENCE,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        governance_note=(
            "Succession/internal-mobility readiness figures are HR-planning "
            "discussion aids only, never a validated assessment instrument, and "
            "must not be used as the sole basis for promotion, compensation, or "
            "personnel decisions. Qualified HR review required."
        ),
        disclaimer_en=READINESS_DISCLAIMER_EN,
        disclaimer_ar=READINESS_DISCLAIMER_AR,
        sources=sources,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def succession_readiness_to_dict(r: SuccessionReadinessResult) -> dict[str, Any]:
    """Serialize SuccessionReadinessResult to a JSON-safe dict."""
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "n_total": r.n_total,
        "n_high_readiness": r.n_high_readiness,
        "n_stuck_high_performers": r.n_stuck_high_performers,
        "n_high_readiness_low_fairness": r.n_high_readiness_low_fairness,
        "avg_readiness_score": r.avg_readiness_score,
        "top_candidates": [
            {
                "record_id_safe": c.record_id_safe,
                "employee_id_raw": c.employee_id_raw,
                "department": c.department,
                "performance_percentile": c.performance_percentile,
                "tenure_years": c.tenure_years,
                "readiness_score": c.readiness_score,
                "readiness_tier": c.readiness_tier,
                "is_stuck_high_performer": c.is_stuck_high_performer,
                "high_readiness_low_fairness_flag": c.high_readiness_low_fairness_flag,
            }
            for c in r.top_candidates
        ],
        "high_readiness_record_ids": r.high_readiness_record_ids,
        "department_breakdown": [
            {
                "department": d.department,
                "n_total": d.n_total,
                "n_high_readiness": d.n_high_readiness,
                "avg_readiness_score": d.avg_readiness_score,
            }
            for d in r.department_breakdown
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "formula_description_en": r.formula_description_en,
        "formula_description_ar": r.formula_description_ar,
        "is_validated_instrument": r.is_validated_instrument,
        "calculation_confidence": r.calculation_confidence,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
        "disclaimer_en": r.disclaimer_en,
        "disclaimer_ar": r.disclaimer_ar,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
