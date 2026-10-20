"""
Job Pattern Grouping & Market Research Export — Phase 19 (base) / Phase 20
(5th dimension: academic qualification).

A fully offline module: groups the user's own uploaded workforce data into
job "patterns" (job title x level x department x experience band x academic
qualification) and produces an aggregate-only worksheet the user takes to an
external tool of their own choosing (a recruiter, Bayt.com/GulfTalent, or an
AI assistant) to research current market salary ranges. This module makes
ZERO network calls of any kind — it never contacts a job board,
salary-survey API, or LLM itself. That is the entire point: it sidesteps
both the legal risk of scraping job boards and this platform's offline-first
architecture (`backend/core/offline_mode_guard.py`, installed at process
start via `local_enterprise_runtime.py` — any accidental network call
anywhere in this process would already raise `OfflinePolicyViolation`, not
just here).

**Normalization approach — reuse, not reimplementation, with one documented
exception.** Department normalization reuses `department_normalizer.py`'s
`normalize_department_series()` directly and unchanged (real reuse: same
function, same import, zero duplicated logic).

Job-title normalization is different: `department_normalizer.py`'s curated
synonym table is deliberately small (~19 entries) because there are only
so many corporate department names in practice. Job titles have a far
larger, effectively open vocabulary (compound titles like "Senior Regional
Sales Manager" vs. "Sr. Sales Mgr - Regional"), so a single shared lookup
table sized for department names would not generalize. Rather than
cross-importing `department_normalizer.py`'s underscore-prefixed internals
(`_exact_normalize`, `_is_latin_script`, `_find_unmerged_similar_variants`)
across a module boundary they were never meant to expose, this module
follows this session's own established convention for this exact situation
— see `recruitment_pipeline_engine.py`'s `_is_missing_value()`, which
mirrors `department_normalizer._is_missing_department()`'s discipline via a
small local reimplementation rather than a private cross-import, and
`contract_expiry_engine.py`'s module docstring, which documents the same
choice for column-detection. This module's `normalize_title_series()`
below reproduces the exact same TWO-TIER architecture
(exact-normalize-always tier + same-script near-duplicate difflib flagging,
never auto-merged, for human review) plus its own small, explicitly
non-exhaustive curated EN/AR table of common generic Saudi/GCC job titles
(the same "small, hand-curated, disclosed, not exhaustive" shape as
`EN_AR_DEPARTMENT_SYNONYMS`) — never a silent cross-script auto-merge.

**Academic qualification (5th dimension, Phase 20).** Unlike job titles,
academic degree LEVELS are a genuinely small, bounded vocabulary (Bachelor's
/ Master's / PhD / Diploma...) — much closer in shape to department names
than to open-vocabulary job titles. `normalize_degree_series()` therefore
reuses the exact same two-tier architecture as `normalize_title_series()`
(kept as separate, independently-tested code rather than a shared parametrized
helper — a deliberate choice: the two tables and their missing-value labels
are semantically distinct, and duplicating ~40 lines of already-tested logic
carries far less regression risk than refactoring `normalize_title_series()`,
which 15 pre-existing Phase 19 tests depend on, while mid-phase). A second,
independent education-FIELD/major column (e.g. "Computer Science", "Business
Administration") is detected separately when present — degree LEVEL and
degree FIELD are two genuinely different things, same "two separate
signals, never conflated" principle `contract_expiry_engine.py` established
for ContractEndDate vs. IqamaExpiry. When both are present they combine into
one composite qualification label ("Bachelor's — Computer Science"); when
only one is present, that one is used alone; when neither is present, the
qualification dimension is simply omitted from grouping (same graceful
degradation as level/department/experience), never fabricated.

**Qualification gets its own dedicated column, not a suffix on Job Title.**
Job Level, Department, and Experience Range already each render as their own
column in both the on-screen table and the Excel export — folding
qualification into the Job Title string instead would break that established
one-dimension-per-column convention and make the export harder to filter/sort
in Excel. Pattern IDs ("P001", "P002"...) remain plain sequence numbers, as
they always have — none of the other 4 dimensions are encoded into the ID
either, so encoding only qualification there would be an inconsistent,
partial change; the dimension is fully visible in its own column instead.

**Experience bands** (Entry-Level 0-2 / Mid-Level 3-5 / Senior 6-10 /
Expert-Leadership 11+ years) mirror common Gulf-region salary-survey
banding conventions. Like every tier boundary chosen this session
(see `contract_expiry_engine.py`'s urgency tiers), this is disclosed as
this platform's own illustrative heuristic, not a certified industry
standard.

**Minimum-group-size floor, re-verified for Phase 20.** Live-tested against
the real "Original Dataset of Employee Attrition" (1,191 rows; not checked
into this repo, but the platform's own `saudi_attrition_normalizer.py` and
`SAUDI_ATTRITION_DATASET_MAPPING_AUDIT.md` were both built against it — see
the Phase 20 report for the exact path used): Phase 19's 4-dimension
grouping produces 118 patterns on this dataset; adding academic qualification
as a 5th dimension produces more, smaller patterns (see report for the exact
before/after count). `MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE` (below) was
re-verified against this real 5-dimension output rather than left unchanged
on assumption — see the constant's own comment for the conclusion reached.

**PII safety — aggregate pattern-level data only, with a minimum-group-size
floor.** The export never includes employee names or IDs (same principle as
`exit_interview_intelligence_engine.py`'s no-raw-text rule). Beyond that:
a pattern's average/median/min/max salary figures are additionally
suppressed whenever fewer than `MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE`
employees in that pattern have a valid salary value — because unlike a
statistical disparity test (`pay_equity_engine.py`'s
`_MIN_GROUP_SIZE_FOR_DISPARITY=20`, chosen for test validity) or a
free-text narrative floor (`exit_interview_intelligence_engine.py`'s
`MIN_RESPONSES_FOR_AGGREGATE=5`), a single min-max salary RANGE computed
from only 1-2 employees is not a statistical claim at all — it is one or
two employees' literal salary figures wearing an aggregate label. This
module's own, smaller floor is a basic re-identification safeguard for
that specific case, not a claim of statistical validity.

**Known, documented, out-of-scope limitation found while live-testing this
phase against the real attrition dataset**: that dataset's `MonthlySalary`
column is range-text ("From 5000 to 10000 S.R", "Less than 5000 SAR"), and
its `Years_Experience` column is also range-text ("Less than 5 years", "From
5 to 10 years") — neither parses under this module's numeric-only
`pd.to_numeric(errors="coerce")` discipline (same "exclude rather than guess"
principle as every other module this session), so on that specific dataset
both correctly, honestly show as "not available" rather than fabricating a
number. Fixing this is a real, separate piece of work (reusing
`saudi_attrition_normalizer._parse_salary_range()`'s already-built
range-text parser would be the natural next step) explicitly out of scope
for this phase's 5th-dimension task — flagged here rather than silently
left for a future session to rediscover.
"""

from __future__ import annotations

import difflib
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
from openpyxl.styles import Alignment, Font

from backend.core.department_normalizer import normalize_department_series

# ── Column detection (local-regex convention, see every Phase 5-19 engine) ─

_JOB_TITLE_PATTERNS = re.compile(
    r"\b(job[_\s]?title|jobtitle|job[_\s]?role|jobrole|position[_\s]?title|"
    r"position|occupation|role[_\s]?title|"
    r"المسمى[_\s]?الوظيفي|المسمى|الوظيفة|المنصب)\b",
    re.I,
)
# Reused verbatim from succession_readiness_engine.py's _JOB_LEVEL_PATTERNS
# (duplicated locally per this session's established per-module convention
# for small fixed detection constants — see contract_expiry_engine.py's
# module docstring for the same citation pattern).
_JOB_LEVEL_PATTERNS = re.compile(
    r"\b(job[_\s]?level|joblevel|career[_\s]?level|grade[_\s]?level|"
    r"المستوى[_\s]?الوظيفي|الدرجة[_\s]?الوظيفية)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b",
    re.I,
)
# Reused verbatim from succession_readiness_engine.py's _TENURE_PATTERNS,
# extended with the brief's own suggested "Years_Experience" variant.
_EXPERIENCE_PATTERNS = re.compile(
    r"\b(years[_\s]?at[_\s]?company|tenure[_\s]?years|tenure|years[_\s]?of[_\s]?service|"
    r"years[_\s]?experience|total[_\s]?experience|experience[_\s]?years|"
    r"سنوات[_\s]?الخدمة|سنوات[_\s]?الخبرة|مدة[_\s]?العمل)\b",
    re.I,
)
# Reused verbatim from pay_equity_engine.py's _SALARY_PATTERNS.
_SALARY_PATTERNS = re.compile(
    r"\b(monthly[_\s]?income|monthly[_\s]?salary|annual[_\s]?salary|salary|wage|"
    r"compensation|basic[_\s]?pay|gross[_\s]?pay|"
    r"الراتب|الأجر|التعويض)\b",
    re.I,
)
# Phase 20 — 5th dimension. "Academic_degree" (with its real-world NBSP/
# trailing-space messiness, see saudi_attrition_normalizer.py) is the
# concrete column this pattern was built against; the rest are realistic
# variants following the same convention as every other detection pattern
# in this module.
_ACADEMIC_DEGREE_PATTERNS = re.compile(
    r"\b(academic[_\s]?degree|education[_\s]?level|qualification|degree[_\s]?level|"
    r"highest[_\s]?degree|degree|"
    r"المؤهل[_\s]?العلمي|الدرجة[_\s]?العلمية|المستوى[_\s]?التعليمي)\b",
    re.I,
)
# Genuinely separate from degree LEVEL — see module docstring. Not detected
# in the real attrition dataset this phase was live-tested against (that
# dataset has no field/major column at all), so this path is exercised only
# by synthetic test fixtures — documented honestly, not assumed to work.
_EDUCATION_FIELD_PATTERNS = re.compile(
    r"\b(education[_\s]?field|field[_\s]?of[_\s]?study|major|specialization|"
    r"academic[_\s]?major|study[_\s]?field|"
    r"التخصص[_\s]?الأكاديمي|مجال[_\s]?الدراسة|التخصص)\b",
    re.I,
)

_ID_COLUMN_CANDIDATES = ("EmployeeID", "employee_id", "EmpID", "emp_id")

# ── Job-title curated synonym table (small, disclosed, NOT exhaustive) ─────
# Same shape/spirit as department_normalizer.EN_AR_DEPARTMENT_SYNONYMS: a
# short, hand-curated list of common single/short-phrase Saudi/GCC corporate
# job titles. Compound titles ("Senior Regional Sales Manager") are handled
# by the exact-normalize tier + same-script near-duplicate flagging below,
# not by this table — a lookup table cannot scale to open-vocabulary
# compound titles the way it can for ~19 department names.
EN_AR_JOB_TITLE_SYNONYMS: dict[str, list[str]] = {
    "Manager":            ["manager", "مدير"],
    "Senior Manager":     ["senior manager", "sr. manager", "sr manager", "مدير أول"],
    "Director":           ["director", "مدير عام"],
    "Supervisor":         ["supervisor", "مشرف"],
    "Team Leader":        ["team leader", "team lead", "قائد فريق"],
    "Engineer":           ["engineer", "eng.", "مهندس"],
    "Senior Engineer":    ["senior engineer", "sr. engineer", "sr engineer", "مهندس أول"],
    "Accountant":         ["accountant", "محاسب"],
    "Senior Accountant":  ["senior accountant", "محاسب أول"],
    "Sales Executive":    ["sales executive", "sales exec", "sales exec.", "مندوب مبيعات", "تنفيذي مبيعات"],
    "Sales Manager":      ["sales manager", "مدير مبيعات"],
    "Marketing Specialist": ["marketing specialist", "أخصائي تسويق"],
    "HR Specialist":      ["hr specialist", "human resources specialist", "أخصائي موارد بشرية"],
    "HR Manager":         ["hr manager", "human resources manager", "مدير موارد بشرية"],
    "Customer Service Representative": [
        "customer service representative", "customer service rep", "csr", "ممثل خدمة العملاء",
    ],
    "Administrative Assistant": ["administrative assistant", "admin assistant", "مساعد إداري"],
    "Receptionist":       ["receptionist", "موظف استقبال"],
    "Driver":             ["driver", "سائق"],
    "Technician":         ["technician", "فني"],
    "Analyst":            ["analyst", "محلل"],
    "Senior Analyst":     ["senior analyst", "محلل أول"],
    "Coordinator":        ["coordinator", "منسق"],
    "Specialist":         ["specialist", "أخصائي"],
}
_SIMILARITY_REVIEW_THRESHOLD = 0.82  # same threshold department_normalizer.py uses
MISSING_TITLE_LABEL = "Unknown / Unspecified Job Title"

# ── Academic-degree curated synonym table (Phase 20) ────────────────────────
# A genuinely small, bounded vocabulary (unlike job titles) — grounded in the
# real values observed in the "Original Dataset of Employee Attrition"
# (Bachelor's / Master's / Ph.D / "Diploma or secondary"), plus common EN/AR
# variants following the same small-and-disclosed convention as every other
# curated table in this module. "Diploma or Secondary" is kept as ONE
# canonical bucket matching that dataset's own combined category — this
# module does not split it further, since doing so from the label alone
# would be guessing which of the two it actually is.
EN_AR_DEGREE_SYNONYMS: dict[str, list[str]] = {
    "PhD":                  ["phd", "ph.d", "ph.d.", "doctorate", "doctoral", "دكتوراه"],
    "Master's":             ["master's", "masters", "master", "msc", "m.sc", "ماجستير"],
    "Bachelor's":           ["bachelor's", "bachelors", "bachelor", "bsc", "b.sc", "بكالوريوس"],
    "Diploma or Secondary": [
        "diploma or secondary", "diploma", "secondary", "high school",
        "دبلوم", "ثانوية عامة", "الثانوية العامة",
    ],
}
MISSING_DEGREE_LABEL = "Unknown / Unspecified Academic Qualification"

# ── Experience bands ─────────────────────────────────────────────────────────
# Illustrative planning heuristic (see module docstring), not a certified
# industry standard.
_EXPERIENCE_BANDS = [
    (0, 2, "Entry-Level (0-2 yrs)"),
    (3, 5, "Mid-Level (3-5 yrs)"),
    (6, 10, "Senior (6-10 yrs)"),
    (11, None, "Expert / Leadership (11+ yrs)"),
]

# Phase 20 re-verification: live-tested at 3 (Phase 19's original value)
# against the real 5-dimension output on the "Original Dataset of Employee
# Attrition" (1,191 employees). Conclusion: left UNCHANGED at 3, backed by
# a real measurement, not assumption. Adding the 5th dimension does grow a
# long tail of small niche patterns (218 patterns total vs. Phase 19's 118
# on the same data; 112 of the 200 displayed patterns fall under n=3) — but
# by EMPLOYEE coverage, not pattern count, 1,032 of 1,191 employees (~87%)
# still land in a pattern at or above the floor. The long tail is real, rare
# title+department+experience+qualification combinations genuinely only
# have 1-2 people — that is a true small sample, not an artifact of the
# floor being miscalibrated, so suppressing it is correct behavior, not a
# degradation. (Separately, salary itself was 100% unavailable on this
# specific real dataset for an unrelated reason — its salary column is
# range-text, not a plain number; see the module docstring's "known
# limitation" section — so this floor's effect on salary specifically was
# verified instead against a synthetic fixture with working numeric salary,
# see tests/test_job_pattern_grouping_engine.py.) Lowering the floor below 3
# was rejected outright regardless of these numbers: 2 employees'
# "aggregate" is still just two people's literal pay.
MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE = 3
_MAX_DISPLAY_PATTERNS = 200

JOB_PATTERN_CONFIDENCE = "planning_aid_not_market_data"
JOB_PATTERN_DISCLAIMER_EN = (
    "This tool does NOT search the internet, contact any job board, or call any AI "
    "service — it only groups and summarizes your own uploaded data, entirely on this "
    "machine. Zero data leaves your machine. 'Current Avg Salary' reflects only what "
    "your own uploaded data reports for employees at this company today — it is NOT a "
    "market benchmark. To compare against the external market, take the exported "
    "worksheet to a source of your choosing (a recruiter, a job board, or an AI "
    "assistant) and research each pattern's row yourself."
)
JOB_PATTERN_DISCLAIMER_AR = (
    "لا تبحث هذه الأداة في الإنترنت، ولا تتصل بأي موقع وظائف، ولا تستدعي أي خدمة ذكاء "
    "اصطناعي — فهي فقط تُجمّع وتُلخّص بياناتك المُحمّلة، بالكامل على هذا الجهاز. لا "
    "تغادر أي بيانات جهازك. يعكس عمود 'متوسط الراتب الحالي' فقط ما تُبلّغ عنه بياناتك "
    "المُحمّلة لموظفي هذه الشركة اليوم — وليس معياراً سوقياً. للمقارنة مع السوق "
    "الخارجي، خذ ورقة العمل المُصدَّرة إلى مصدر من اختيارك (مسؤول توظيف، أو موقع "
    "وظائف، أو مساعد ذكاء اصطناعي) وابحث عن كل صف بنفسك."
)
_SOURCES = [
    "Department-level grouping reused verbatim from department_normalizer.py.",
    "Job-title normalization follows the same two-tier architecture "
    "(exact-normalize + same-script near-duplicate review, never auto-merged "
    "cross-script) plus a small, explicitly non-exhaustive curated EN/AR "
    "synonym table for common generic titles — see module docstring.",
    "Academic qualification (Phase 20) normalization follows the identical "
    "two-tier architecture, with its own small curated EN/AR degree-level "
    "table grounded in the real values observed in the Original Dataset of "
    "Employee Attrition — see module docstring.",
    "Experience bands (0-2 / 3-5 / 6-10 / 11+ years) are this platform's own "
    "illustrative heuristic, not a certified industry standard.",
    "Zero network calls: this module makes no external HTTP request of any "
    "kind — see backend/core/offline_mode_guard.py, installed globally at "
    "process start, which would raise OfflinePolicyViolation on any attempt.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "job_title": "Job title (e.g. JobTitle, JobRole, Position)",
    "job_level": "Job level (optional — refines grouping)",
    "department": "Department (optional — refines grouping)",
    "experience": "Tenure / years of experience (optional — refines grouping)",
    "salary": "Salary / compensation (optional — enables salary columns)",
    "academic_degree": "Academic qualification (optional — e.g. Academic_degree, refines grouping)",
    "education_field": "Field of study / major (optional — combines with qualification when both present)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "job_title": "المسمى الوظيفي (مثال: JobTitle أو JobRole)",
    "job_level": "المستوى الوظيفي (اختياري — يُحسّن التجميع)",
    "department": "القسم (اختياري — يُحسّن التجميع)",
    "experience": "سنوات الخبرة (اختياري — يُحسّن التجميع)",
    "salary": "الراتب / التعويض (اختياري — يُفعّل أعمدة الراتب)",
    "academic_degree": "المؤهل العلمي (اختياري — مثال: Academic_degree، يُحسّن التجميع)",
    "education_field": "التخصص الأكاديمي (اختياري — يُدمج مع المؤهل عند توفر كليهما)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _is_missing_value(raw: object) -> bool:
    """Same missing-value discipline as department_normalizer.py's
    _is_missing_department() — checked before any string operation, since
    Series.astype(str)/str() does not reliably stringify NaN on every
    pandas version."""
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _exact_normalize(raw: str) -> str:
    return " ".join(str(raw).split()).casefold()


# The missing-value sentinels (MISSING_TITLE_LABEL, MISSING_DEGREE_LABEL)
# pass through this same exact-normalize (trim+casefold) tier as every real
# value before becoming a grouping key, so a row-exclusion check must
# compare against THESE casefolded forms, never the original-case constants
# directly — comparing against the original-case constant silently fails to
# exclude anything (a real bug caught while building the Phase 20 degree
# dimension, whose missing-value check shares the identical pattern; fixed
# in both places at once — see tests/test_job_pattern_grouping_engine.py's
# test_missing_job_title_row_excluded_not_fabricated_as_pattern).
_MISSING_TITLE_KEY = _exact_normalize(MISSING_TITLE_LABEL)
_MISSING_DEGREE_KEY = _exact_normalize(MISSING_DEGREE_LABEL)


def _is_latin_script(s: str) -> bool:
    return all((not c.isalpha()) or ("a" <= c.lower() <= "z") for c in s)


def _bucket_for_experience(years: float) -> Optional[str]:
    if years < 0:
        return None
    for lo, hi, label in _EXPERIENCE_BANDS:
        if hi is None or years <= hi:
            if years >= lo:
                return label
    return None


# ── Job-title normalization (mirrors department_normalizer.py's two-tier
#    architecture — see module docstring for why this is a local
#    reimplementation rather than a cross-import) ──────────────────────────

@dataclass(frozen=True)
class TitleMerge:
    canonical_label: str
    variants_merged: list[str]
    counts_per_variant: dict[str, int]
    source: str


@dataclass(frozen=True)
class TitleNormalizationResult:
    normalized_keys: pd.Series
    display_labels: dict[str, str]
    merges_applied: list[TitleMerge]
    unmerged_similar_variants: list[list[str]]


def _build_title_reverse_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, variants in EN_AR_JOB_TITLE_SYNONYMS.items():
        lookup[canonical.strip().lower()] = canonical
        for v in variants:
            lookup[v.strip().lower()] = canonical
    return lookup


_TITLE_REVERSE_LOOKUP = _build_title_reverse_lookup()


def _find_unmerged_similar_title_variants(
    keys: list[str], display_labels: dict[str, str],
) -> list[list[str]]:
    labels = [display_labels[k] for k in keys]
    flagged_pairs: list[tuple[str, str]] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            if not (_is_latin_script(a) and _is_latin_script(b)):
                continue
            if a.casefold() == b.casefold():
                continue
            ratio = difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
            if ratio >= _SIMILARITY_REVIEW_THRESHOLD:
                flagged_pairs.append((a, b))

    groups: list[set[str]] = []
    for a, b in flagged_pairs:
        merged = False
        for g in groups:
            if a in g or b in g:
                g.add(a)
                g.add(b)
                merged = True
                break
        if not merged:
            groups.append({a, b})
    return [sorted(g) for g in groups]


def normalize_title_series(raw: pd.Series) -> TitleNormalizationResult:
    """Job-title equivalent of department_normalizer.normalize_department_series()
    — same two-tier architecture, see module docstring."""
    raw_str = raw.map(lambda v: MISSING_TITLE_LABEL if _is_missing_value(v) else str(v))
    exact_norm = raw_str.map(_exact_normalize)
    canonical = exact_norm.map(lambda k: _TITLE_REVERSE_LOOKUP.get(k, k))
    normalized_keys = canonical

    display_labels: dict[str, str] = {}
    variants_by_key: dict[str, Counter] = {}
    for raw_val, key in zip(raw_str, normalized_keys):
        variants_by_key.setdefault(key, Counter())[raw_val] += 1

    for key, counter in variants_by_key.items():
        if key in EN_AR_JOB_TITLE_SYNONYMS:
            display_labels[key] = key
        else:
            display_labels[key] = counter.most_common(1)[0][0]

    merges_applied: list[TitleMerge] = []
    for key, counter in variants_by_key.items():
        if key in EN_AR_JOB_TITLE_SYNONYMS and len(counter) > 1:
            merges_applied.append(TitleMerge(
                canonical_label=key,
                variants_merged=sorted(counter.keys()),
                counts_per_variant=dict(counter),
                source="curated_synonym_table",
            ))

    unmerged = _find_unmerged_similar_title_variants(list(variants_by_key.keys()), display_labels)

    return TitleNormalizationResult(
        normalized_keys=normalized_keys,
        display_labels=display_labels,
        merges_applied=merges_applied,
        unmerged_similar_variants=unmerged,
    )


# ── Academic-degree normalization (Phase 20) — same two-tier architecture as
#    normalize_title_series() above, kept as separate code rather than a
#    shared parametrized helper (see module docstring for why) ─────────────

@dataclass(frozen=True)
class DegreeMerge:
    canonical_label: str
    variants_merged: list[str]
    counts_per_variant: dict[str, int]
    source: str


@dataclass(frozen=True)
class DegreeNormalizationResult:
    normalized_keys: pd.Series
    display_labels: dict[str, str]
    merges_applied: list[DegreeMerge]
    unmerged_similar_variants: list[list[str]]


def _build_degree_reverse_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, variants in EN_AR_DEGREE_SYNONYMS.items():
        lookup[canonical.strip().lower()] = canonical
        for v in variants:
            lookup[v.strip().lower()] = canonical
    return lookup


_DEGREE_REVERSE_LOOKUP = _build_degree_reverse_lookup()


def _find_unmerged_similar_degree_variants(
    keys: list[str], display_labels: dict[str, str],
) -> list[list[str]]:
    labels = [display_labels[k] for k in keys]
    flagged_pairs: list[tuple[str, str]] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            if not (_is_latin_script(a) and _is_latin_script(b)):
                continue
            if a.casefold() == b.casefold():
                continue
            ratio = difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
            if ratio >= _SIMILARITY_REVIEW_THRESHOLD:
                flagged_pairs.append((a, b))

    groups: list[set[str]] = []
    for a, b in flagged_pairs:
        merged = False
        for g in groups:
            if a in g or b in g:
                g.add(a)
                g.add(b)
                merged = True
                break
        if not merged:
            groups.append({a, b})
    return [sorted(g) for g in groups]


def normalize_degree_series(raw: pd.Series) -> DegreeNormalizationResult:
    """Academic-degree equivalent of normalize_title_series() — same
    two-tier architecture, see module docstring."""
    raw_str = raw.map(lambda v: MISSING_DEGREE_LABEL if _is_missing_value(v) else str(v))
    exact_norm = raw_str.map(_exact_normalize)
    canonical = exact_norm.map(lambda k: _DEGREE_REVERSE_LOOKUP.get(k, k))
    normalized_keys = canonical

    display_labels: dict[str, str] = {}
    variants_by_key: dict[str, Counter] = {}
    for raw_val, key in zip(raw_str, normalized_keys):
        variants_by_key.setdefault(key, Counter())[raw_val] += 1

    for key, counter in variants_by_key.items():
        if key in EN_AR_DEGREE_SYNONYMS:
            display_labels[key] = key
        else:
            display_labels[key] = counter.most_common(1)[0][0]

    merges_applied: list[DegreeMerge] = []
    for key, counter in variants_by_key.items():
        if key in EN_AR_DEGREE_SYNONYMS and len(counter) > 1:
            merges_applied.append(DegreeMerge(
                canonical_label=key,
                variants_merged=sorted(counter.keys()),
                counts_per_variant=dict(counter),
                source="curated_synonym_table",
            ))

    unmerged = _find_unmerged_similar_degree_variants(list(variants_by_key.keys()), display_labels)

    return DegreeNormalizationResult(
        normalized_keys=normalized_keys,
        display_labels=display_labels,
        merges_applied=merges_applied,
        unmerged_similar_variants=unmerged,
    )


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class JobPattern:
    pattern_id: str
    job_title: str
    job_level: Optional[str]
    department: Optional[str]
    experience_bucket: Optional[str]
    experience_range_label: Optional[str]
    academic_qualification: Optional[str]
    employee_count: int
    n_with_valid_salary: int
    avg_salary_sar: Optional[float]
    median_salary_sar: Optional[float]
    salary_min_sar: Optional[float]
    salary_max_sar: Optional[float]
    salary_suppressed: bool


@dataclass(frozen=True)
class JobPatternGroupingResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    job_title_column: Optional[str]
    job_level_column: Optional[str]
    department_column: Optional[str]
    experience_column: Optional[str]
    salary_column: Optional[str]
    academic_degree_column: Optional[str]
    education_field_column: Optional[str]
    grouping_dimensions_used: list[str]
    n_employees_total: int
    n_employees_grouped: int
    n_patterns: int
    n_patterns_truncated: int
    patterns: list[JobPattern]
    title_normalization_notes: list[str]
    department_normalization_notes: list[str]
    degree_normalization_notes: list[str]
    narrative_en: str
    narrative_ar: str
    job_pattern_confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_job_pattern_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> JobPatternGroupingResult:
    return JobPatternGroupingResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {},
        job_title_column=None,
        job_level_column=None,
        department_column=None,
        experience_column=None,
        salary_column=None,
        academic_degree_column=None,
        education_field_column=None,
        grouping_dimensions_used=[],
        n_employees_total=0,
        n_employees_grouped=0,
        n_patterns=0,
        n_patterns_truncated=0,
        patterns=[],
        title_normalization_notes=[],
        department_normalization_notes=[],
        degree_normalization_notes=[],
        narrative_en="Job pattern grouping not available for this dataset.",
        narrative_ar="تجميع أنماط الوظائف غير متاح لهذه البيانات.",
        job_pattern_confidence=JOB_PATTERN_CONFIDENCE,
        disclaimer_en=JOB_PATTERN_DISCLAIMER_EN,
        disclaimer_ar=JOB_PATTERN_DISCLAIMER_AR,
        governance_note=(
            "No patterns are computed or displayed when no job-title column is "
            "detected — this platform never fabricates a job pattern."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


def analyze_job_pattern_grouping(df: pd.DataFrame) -> JobPatternGroupingResult:
    """Real job-pattern-grouping analysis. Never raises — exceptions should
    be caught by the caller and surfaced via unavailable_job_pattern_result."""
    if df is None or df.empty:
        return unavailable_job_pattern_result("No data available for job pattern grouping.")

    title_col = _find_column(df, _JOB_TITLE_PATTERNS)
    level_col = _find_column(df, _JOB_LEVEL_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    exp_col = _find_column(df, _EXPERIENCE_PATTERNS)
    salary_col = _find_column(df, _SALARY_PATTERNS)
    degree_col = _find_column(df, _ACADEMIC_DEGREE_PATTERNS)
    field_col = _find_column(df, _EDUCATION_FIELD_PATTERNS)

    columns_detected = {
        "job_title": title_col is not None,
        "job_level": level_col is not None,
        "department": dept_col is not None,
        "experience": exp_col is not None,
        "salary": salary_col is not None,
        "academic_degree": degree_col is not None,
        "education_field": field_col is not None,
    }

    if title_col is None:
        return unavailable_job_pattern_result(
            "No job-title column detected (e.g. JobTitle, JobRole, Position). Job "
            "title is the core grouping dimension for this feature — without it, no "
            "pattern can be formed.",
            columns_detected,
        )

    title_result = normalize_title_series(df[title_col].astype(object))
    title_keys = pd.Series(title_result.normalized_keys.values, index=df.index)

    dept_keys: Optional[pd.Series] = None
    dept_labels: dict[str, str] = {}
    dept_norm_notes: list[str] = []
    if dept_col is not None:
        dept_result = normalize_department_series(df[dept_col].astype(object))
        dept_keys = pd.Series(dept_result.normalized_keys.values, index=df.index)
        dept_labels = dept_result.display_labels
        for merge in dept_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_norm_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}."
            )
        for grp in dept_result.unmerged_similar_variants:
            dept_norm_notes.append(
                f"Found similarly-named but NOT merged department values "
                f"{', '.join(repr(v) for v in grp)} — review manually."
            )

    title_norm_notes: list[str] = []
    for merge in title_result.merges_applied:
        variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
        title_norm_notes.append(
            f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}."
        )
    for grp in title_result.unmerged_similar_variants:
        title_norm_notes.append(
            f"Found similarly-named but NOT merged job titles "
            f"{', '.join(repr(v) for v in grp)} — review manually."
        )

    degree_keys: Optional[pd.Series] = None
    degree_labels: dict[str, str] = {}
    degree_norm_notes: list[str] = []
    if degree_col is not None:
        degree_result = normalize_degree_series(df[degree_col].astype(object))
        degree_keys = pd.Series(degree_result.normalized_keys.values, index=df.index)
        degree_labels = degree_result.display_labels
        for merge in degree_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            degree_norm_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}."
            )
        for grp in degree_result.unmerged_similar_variants:
            degree_norm_notes.append(
                f"Found similarly-named but NOT merged academic qualifications "
                f"{', '.join(repr(v) for v in grp)} — review manually."
            )

    field_vals: Optional[pd.Series] = df[field_col].astype(object) if field_col is not None else None

    level_vals: Optional[pd.Series] = df[level_col].astype(object) if level_col is not None else None
    exp_years: Optional[pd.Series] = None
    if exp_col is not None:
        exp_years = pd.to_numeric(df[exp_col], errors="coerce")
    salary_vals: Optional[pd.Series] = None
    if salary_col is not None:
        salary_vals = pd.to_numeric(df[salary_col], errors="coerce")

    grouping_dimensions_used = ["job_title"]
    if level_col is not None:
        grouping_dimensions_used.append("job_level")
    if dept_col is not None:
        grouping_dimensions_used.append("department")
    if exp_col is not None:
        grouping_dimensions_used.append("experience")
    if degree_col is not None or field_col is not None:
        grouping_dimensions_used.append("academic_qualification")

    # Build the group key per row; a missing title excludes the row entirely
    # (title is mandatory), missing level/department/experience/qualification
    # just omit that dimension from the key (graceful degradation, not row
    # exclusion).
    groups: dict[tuple, dict[str, Any]] = {}
    n_grouped = 0
    for idx in df.index:
        title_key = title_keys.loc[idx]
        if title_key == _MISSING_TITLE_KEY:
            continue
        n_grouped += 1

        level_val = None
        if level_vals is not None and not _is_missing_value(level_vals.loc[idx]):
            level_val = str(level_vals.loc[idx]).strip()

        dept_val = None
        if dept_keys is not None:
            dkey = dept_keys.loc[idx]
            dept_val = dept_labels.get(dkey, dkey) if dkey is not None else None

        exp_bucket = None
        exp_val = None
        if exp_years is not None and pd.notna(exp_years.loc[idx]):
            exp_val = float(exp_years.loc[idx])
            exp_bucket = _bucket_for_experience(exp_val)

        # Composite qualification label: degree + field when both present,
        # whichever one is present alone otherwise, None when neither.
        degree_label = None
        if degree_keys is not None:
            gkey = degree_keys.loc[idx]
            if gkey != _MISSING_DEGREE_KEY:
                degree_label = degree_labels.get(gkey, gkey)
        field_label = None
        if field_vals is not None and not _is_missing_value(field_vals.loc[idx]):
            field_label = " ".join(str(field_vals.loc[idx]).split())
        if degree_label and field_label:
            qualification_val = f"{degree_label} — {field_label}"
        elif degree_label:
            qualification_val = degree_label
        elif field_label:
            qualification_val = field_label
        else:
            qualification_val = None

        key = (title_key, level_val, dept_val, exp_bucket, qualification_val)
        bucket = groups.setdefault(key, {
            "title_display": title_result.display_labels.get(title_key, title_key),
            "level": level_val,
            "department": dept_val,
            "experience_bucket": exp_bucket,
            "qualification": qualification_val,
            "n": 0,
            "exp_values": [],
            "salary_values": [],
        })
        bucket["n"] += 1
        if exp_val is not None:
            bucket["exp_values"].append(exp_val)
        if salary_vals is not None and pd.notna(salary_vals.loc[idx]):
            bucket["salary_values"].append(float(salary_vals.loc[idx]))

    if not groups:
        return unavailable_job_pattern_result(
            "A job-title column was detected, but every value was missing — no "
            "pattern could be formed.",
            columns_detected,
        )

    patterns: list[JobPattern] = []
    total_valid_salary = 0
    for bucket in groups.values():
        salary_values = bucket["salary_values"]
        n_salary = len(salary_values)
        total_valid_salary += n_salary
        suppressed = salary_col is not None and n_salary < MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE
        if salary_col is None or suppressed or n_salary == 0:
            avg_sal = med_sal = min_sal = max_sal = None
        else:
            s = pd.Series(salary_values)
            avg_sal = round(float(s.mean()), 2)
            med_sal = round(float(s.median()), 2)
            min_sal = round(float(s.min()), 2)
            max_sal = round(float(s.max()), 2)

        exp_values = bucket["exp_values"]
        exp_range_label = None
        if exp_values:
            lo, hi = min(exp_values), max(exp_values)
            exp_range_label = f"{lo:.0f} years" if lo == hi else f"{lo:.0f}-{hi:.0f} years"

        patterns.append(JobPattern(
            pattern_id="",  # assigned after sort
            job_title=bucket["title_display"],
            job_level=bucket["level"],
            department=bucket["department"],
            experience_bucket=bucket["experience_bucket"],
            experience_range_label=exp_range_label,
            academic_qualification=bucket["qualification"],
            employee_count=bucket["n"],
            n_with_valid_salary=n_salary,
            avg_salary_sar=avg_sal,
            median_salary_sar=med_sal,
            salary_min_sar=min_sal,
            salary_max_sar=max_sal,
            salary_suppressed=suppressed,
        ))

    patterns.sort(key=lambda p: p.employee_count, reverse=True)
    n_patterns_total = len(patterns)
    n_truncated = max(0, n_patterns_total - _MAX_DISPLAY_PATTERNS)
    patterns = patterns[:_MAX_DISPLAY_PATTERNS]
    patterns = [
        JobPattern(
            pattern_id=f"P{str(i + 1).zfill(3)}",
            job_title=p.job_title, job_level=p.job_level, department=p.department,
            experience_bucket=p.experience_bucket, experience_range_label=p.experience_range_label,
            academic_qualification=p.academic_qualification,
            employee_count=p.employee_count, n_with_valid_salary=p.n_with_valid_salary,
            avg_salary_sar=p.avg_salary_sar, median_salary_sar=p.median_salary_sar,
            salary_min_sar=p.salary_min_sar, salary_max_sar=p.salary_max_sar,
            salary_suppressed=p.salary_suppressed,
        )
        for i, p in enumerate(patterns)
    ]

    missing_dims = [
        d for d in ("job_level", "department", "experience", "academic_qualification")
        if d not in grouping_dimensions_used
    ]
    narrative_en = (
        f"{n_grouped} of {len(df)} employees ({title_col} present) were grouped into "
        f"{n_patterns_total} distinct job patterns using {', '.join(grouping_dimensions_used)}."
    )
    narrative_ar = (
        f"تم تجميع {n_grouped} من أصل {len(df)} موظفاً في {n_patterns_total} نمطاً وظيفياً "
        f"مميزاً باستخدام الأبعاد: {', '.join(grouping_dimensions_used)}."
    )
    if missing_dims:
        narrative_en += (
            f" {', '.join(missing_dims)} column(s) not detected — patterns are broader "
            "than they would be with that dimension available."
        )
        narrative_ar += f" لم يتم اكتشاف عمود/أعمدة: {', '.join(missing_dims)} — الأنماط أوسع نطاقاً نتيجة لذلك."
    if salary_col is None:
        narrative_en += " No salary column detected — salary columns are not available."
        narrative_ar += " لم يتم اكتشاف عمود راتب — أعمدة الراتب غير متاحة."
    elif total_valid_salary == 0:
        narrative_en += (
            f" A salary column ({salary_col}) was detected, but no value in it could be "
            "read as a plain number (e.g. it may use range text like 'From 5000 to "
            "10000 SAR') — salary figures are not available for this upload, not "
            "suppressed for having too few employees."
        )
        narrative_ar += (
            f" تم اكتشاف عمود راتب ({salary_col})، لكن لم تُقرأ أي قيمة فيه كرقم صريح "
            "(قد يستخدم نصاً كنطاق مثل 'من 5000 إلى 10000 ريال') — أرقام الراتب غير "
            "متاحة لهذا الملف، وليست مخفية بسبب قلة عدد الموظفين."
        )

    return JobPatternGroupingResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        job_title_column=title_col,
        job_level_column=level_col,
        department_column=dept_col,
        experience_column=exp_col,
        salary_column=salary_col,
        academic_degree_column=degree_col,
        education_field_column=field_col,
        grouping_dimensions_used=grouping_dimensions_used,
        n_employees_total=len(df),
        n_employees_grouped=n_grouped,
        n_patterns=n_patterns_total,
        n_patterns_truncated=n_truncated,
        patterns=patterns,
        title_normalization_notes=title_norm_notes,
        department_normalization_notes=dept_norm_notes,
        degree_normalization_notes=degree_norm_notes,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        job_pattern_confidence=JOB_PATTERN_CONFIDENCE,
        disclaimer_en=JOB_PATTERN_DISCLAIMER_EN,
        disclaimer_ar=JOB_PATTERN_DISCLAIMER_AR,
        governance_note=(
            f"Patterns with fewer than {MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE} employees "
            "with a valid salary value have their salary figures suppressed — an aggregate "
            "of 1-2 people is not a meaningful aggregate, it is those people's literal pay. "
            "No employee names or IDs are included anywhere in this analysis or export."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _pattern_to_dict(p: JobPattern) -> dict[str, Any]:
    return {
        "pattern_id": p.pattern_id,
        "job_title": p.job_title,
        "job_level": p.job_level,
        "department": p.department,
        "experience_bucket": p.experience_bucket,
        "experience_range_label": p.experience_range_label,
        "academic_qualification": p.academic_qualification,
        "employee_count": p.employee_count,
        "n_with_valid_salary": p.n_with_valid_salary,
        "avg_salary_sar": p.avg_salary_sar,
        "median_salary_sar": p.median_salary_sar,
        "salary_min_sar": p.salary_min_sar,
        "salary_max_sar": p.salary_max_sar,
        "salary_suppressed": p.salary_suppressed,
    }


def job_pattern_grouping_to_dict(r: JobPatternGroupingResult) -> dict[str, Any]:
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "job_title_column": r.job_title_column,
        "job_level_column": r.job_level_column,
        "department_column": r.department_column,
        "experience_column": r.experience_column,
        "salary_column": r.salary_column,
        "academic_degree_column": r.academic_degree_column,
        "education_field_column": r.education_field_column,
        "grouping_dimensions_used": r.grouping_dimensions_used,
        "n_employees_total": r.n_employees_total,
        "n_employees_grouped": r.n_employees_grouped,
        "n_patterns": r.n_patterns,
        "n_patterns_truncated": r.n_patterns_truncated,
        "patterns": [_pattern_to_dict(p) for p in r.patterns],
        "title_normalization_notes": r.title_normalization_notes,
        "department_normalization_notes": r.department_normalization_notes,
        "degree_normalization_notes": r.degree_normalization_notes,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "job_pattern_confidence": r.job_pattern_confidence,
        "disclaimer_en": r.disclaimer_en,
        "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }


def job_pattern_grouping_from_dict(d: dict[str, Any]) -> JobPatternGroupingResult:
    """Reconstruct a JobPatternGroupingResult from its serialized dict form
    — used by the export route, which receives the already-computed
    on-screen payload back from the frontend rather than re-uploading and
    re-analyzing the raw file (same two-step analyze-then-export pattern as
    /export/pptx and /export/slides)."""
    patterns = [
        JobPattern(
            pattern_id=p["pattern_id"], job_title=p["job_title"], job_level=p.get("job_level"),
            department=p.get("department"), experience_bucket=p.get("experience_bucket"),
            experience_range_label=p.get("experience_range_label"),
            academic_qualification=p.get("academic_qualification"),
            employee_count=p["employee_count"], n_with_valid_salary=p["n_with_valid_salary"],
            avg_salary_sar=p.get("avg_salary_sar"), median_salary_sar=p.get("median_salary_sar"),
            salary_min_sar=p.get("salary_min_sar"), salary_max_sar=p.get("salary_max_sar"),
            salary_suppressed=p["salary_suppressed"],
        )
        for p in d.get("patterns", [])
    ]
    return JobPatternGroupingResult(
        available=d["available"], reason=d.get("reason"),
        columns_detected=d.get("columns_detected", {}),
        job_title_column=d.get("job_title_column"), job_level_column=d.get("job_level_column"),
        department_column=d.get("department_column"), experience_column=d.get("experience_column"),
        salary_column=d.get("salary_column"),
        academic_degree_column=d.get("academic_degree_column"),
        education_field_column=d.get("education_field_column"),
        grouping_dimensions_used=d.get("grouping_dimensions_used", []),
        n_employees_total=d.get("n_employees_total", 0), n_employees_grouped=d.get("n_employees_grouped", 0),
        n_patterns=d.get("n_patterns", 0), n_patterns_truncated=d.get("n_patterns_truncated", 0),
        patterns=patterns,
        title_normalization_notes=d.get("title_normalization_notes", []),
        department_normalization_notes=d.get("department_normalization_notes", []),
        degree_normalization_notes=d.get("degree_normalization_notes", []),
        narrative_en=d.get("narrative_en", ""), narrative_ar=d.get("narrative_ar", ""),
        job_pattern_confidence=d.get("job_pattern_confidence", JOB_PATTERN_CONFIDENCE),
        disclaimer_en=d.get("disclaimer_en", JOB_PATTERN_DISCLAIMER_EN),
        disclaimer_ar=d.get("disclaimer_ar", JOB_PATTERN_DISCLAIMER_AR),
        governance_note=d.get("governance_note", ""), sources=d.get("sources", _SOURCES),
        computed_at=d.get("computed_at", _now()),
    )


# ── Excel export (openpyxl via pandas.ExcelWriter — same pattern as
#    demo_company_generator.py's generate_bytes()) ──────────────────────────

def generate_market_research_workbook(result: JobPatternGroupingResult) -> bytes:
    """
    Build the take-elsewhere market-research worksheet. Two sheets:
    'Instructions' (what this is for, how to use it externally) and
    'Job Patterns' (one row per pattern, aggregate-only — no employee names
    or IDs anywhere, enforced by construction: JobPattern carries no such
    field to begin with). Makes no network call.
    """
    rows = []
    for p in result.patterns:
        rows.append({
            "Pattern ID": p.pattern_id,
            "Job Title (normalized)": p.job_title,
            "Level": p.job_level or "",
            "Department": p.department or "",
            "Academic Qualification": p.academic_qualification or "",
            "Experience Range": p.experience_range_label or "",
            "Employee Count": p.employee_count,
            "Current Avg Salary (SAR)": "" if p.salary_suppressed or p.avg_salary_sar is None else p.avg_salary_sar,
            "Current Salary Range (SAR)": (
                "Suppressed (n<3)" if p.salary_suppressed
                else "" if p.salary_min_sar is None
                else f"{p.salary_min_sar:,.0f} - {p.salary_max_sar:,.0f}"
            ),
        })
    patterns_df = pd.DataFrame(rows, columns=[
        "Pattern ID", "Job Title (normalized)", "Level", "Department", "Academic Qualification",
        "Experience Range", "Employee Count", "Current Avg Salary (SAR)", "Current Salary Range (SAR)",
    ])

    instructions_rows = [
        ["Job Pattern Grouping & Market Research Worksheet", ""],
        ["", ""],
        ["What this is", "Each row is a group of your own employees sharing a similar "
                          "job title, level, department, academic qualification, and "
                          "experience range — not an individual employee. No employee "
                          "names or IDs are included."],
        ["What this is NOT", "This platform did not search the internet, contact any job "
                              "board, or call any AI service to produce this file. "
                              "'Current Avg Salary' is only what YOUR data reports today — "
                              "it is not a market benchmark."],
        ["How to use it", "For each row, research the current external market salary range "
                           "yourself using a source of your choosing — for example, search "
                           "Bayt.com or GulfTalent, consult a recruiter, or ask an AI "
                           "assistant such as ChatGPT: 'What is the typical Riyadh salary "
                           "range for a mid-level Sales Executive with a Bachelor's degree "
                           "and 3-5 years experience?' Then compare the result against the "
                           "'Current Avg Salary' column."],
        ["Academic Qualification", "When present in your upload, this column reflects each "
                                    "pattern's academic degree level (and field of study, if "
                                    "that column also exists) — two employees with the same "
                                    "title and experience but different degrees are not "
                                    "always comparable for market research, so this column "
                                    "is blank rather than assumed when qualification data "
                                    "was not in your upload."],
        ["Small patterns", f"Patterns with fewer than {MIN_PATTERN_SIZE_FOR_SALARY_DISCLOSURE} "
                            "employees with a valid salary value show 'Suppressed (n<3)' "
                            "instead of a figure — an average of 1-2 people is not a "
                            "meaningful aggregate."],
        ["Not legal/HR advice", "This worksheet is a planning aid, not a compensation "
                                 "benchmarking certification. Qualified HR review is "
                                 "required before any compensation decision."],
    ]
    instructions_df = pd.DataFrame(instructions_rows, columns=["", ""])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        instructions_df.to_excel(writer, index=False, header=False, sheet_name="Instructions")
        patterns_df.to_excel(writer, index=False, sheet_name="Job Patterns")

        ws_instructions = writer.sheets["Instructions"]
        ws_instructions.column_dimensions["A"].width = 24
        ws_instructions.column_dimensions["B"].width = 100
        for row in ws_instructions.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

        ws_patterns = writer.sheets["Job Patterns"]
        widths = [12, 32, 16, 20, 24, 20, 16, 24, 26]
        for col_idx, width in enumerate(widths, start=1):
            ws_patterns.column_dimensions[ws_patterns.cell(row=1, column=col_idx).column_letter].width = width
        for cell in ws_patterns[1]:
            cell.font = Font(bold=True)

    return buf.getvalue()
