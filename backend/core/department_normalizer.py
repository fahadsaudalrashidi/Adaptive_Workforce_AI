"""
Department Name Normalizer — Phase 35.5 (correction).

THE single canonical department-value normalization for every place this
codebase groups records by department. Fixes a confirmed, systemic bug
found via live testing with messy real-world data: three independent call
sites were grouping on raw string equality, so the SAME department typed
three different ways (e.g. "Sales" / "مبيعات" / "Finance" / "finance" /
"Operations " with trailing whitespace) each produced a separate,
incorrectly-split group — corrupting every downstream at-risk percentage,
department-level cost figure, and risk cross-reference computed from that
grouping.

Fixed call sites (see PHASE_4_CORRECTIONS_REPORT.md for the before/after
trace): backend/core/employee_risk_scoring.py (_build_group_summary — the
ROOT department_summary source almost everything else downstream reads),
backend/core/overtime_cost_intelligence_engine.py, backend/core/payroll_movement_tracker.py.

Two normalization tiers, both auditable and disclosed — never silent
where confidence is low:

  1. EXACT normalization (always applied, not disclosed because there is
     no genuine ambiguity): trim whitespace, case-fold for comparison.
     "Finance" == "finance" == " Finance " with total confidence.

  2. CURATED EN/AR SYNONYM TABLE (applied, and DISCLOSED via
     DepartmentNormalizationResult.merges_applied so a human can verify):
     a small, hand-curated list of common Saudi/GCC corporate department
     name pairs (EN_AR_DEPARTMENT_SYNONYMS below). This is NOT sourced to
     an external published standard — it is an engineering-curated lookup
     table covering common cases, explicitly labeled as such. Organizations
     with non-standard or unlisted department names will not have their
     Arabic/English variants merged.

  What is explicitly NOT attempted: automatic fuzzy/similarity matching
  ACROSS scripts (Arabic vs. Latin) — string-similarity algorithms are not
  meaningful between scripts that share no characters, so a mismatch there
  is never silently guessed at. Same-script near-duplicates (e.g.
  "Marketing" vs "Marketting") ARE detected via difflib and surfaced as
  `unmerged_similar_variants` for human review — never silently merged,
  since a near-miss could also be two genuinely different departments.
"""

from __future__ import annotations

import difflib
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# ── Curated EN/AR department synonym table ──────────────────────────────────
# Canonical English label -> every known variant spelling that should merge
# into it (English casing variants are handled automatically by the exact-
# normalization tier below and do not need to be listed here explicitly).
# Coverage: common Saudi/GCC corporate department names. NOT exhaustive —
# add entries as real-world datasets surface new unmapped variants.

EN_AR_DEPARTMENT_SYNONYMS: dict[str, list[str]] = {
    "Sales":                  ["sales", "مبيعات", "قسم المبيعات"],
    "Finance":                ["finance", "مالية", "الشؤون المالية", "المالية"],
    "Human Resources":        ["human resources", "hr", "الموارد البشرية", "شؤون الموظفين"],
    "Engineering":            ["engineering", "الهندسة"],
    "Operations":             ["operations", "العمليات"],
    "Marketing":              ["marketing", "التسويق"],
    "Information Technology": ["information technology", "it", "تقنية المعلومات", "تكنولوجيا المعلومات"],
    "Legal":                  ["legal", "الشؤون القانونية", "القانونية"],
    "Procurement":            ["procurement", "المشتريات", "التوريد"],
    "Customer Service":       ["customer service", "خدمة العملاء"],
    "Quality":                ["quality", "quality assurance", "qa", "الجودة", "ضمان الجودة"],
    "Production":             ["production", "الإنتاج"],
    "Logistics":              ["logistics", "اللوجستيات", "الإمداد"],
    "Administration":         ["administration", "admin", "الإدارة", "الشؤون الإدارية"],
    "Research and Development": ["research and development", "r&d", "البحث والتطوير"],
    "Business Development":   ["business development", "تطوير الأعمال"],
    "Accounting":             ["accounting", "المحاسبة"],
    "Maintenance":            ["maintenance", "الصيانة"],
    "Security":               ["security", "الأمن"],
    "Training":               ["training", "التدريب"],
}

# Similarity threshold for flagging same-script near-duplicates as worth
# human review. Conservative (high) on purpose — false positives waste a
# reviewer's time, false negatives just mean two groups stay split (the
# pre-fix behaviour), which is the safer failure mode.
_SIMILARITY_REVIEW_THRESHOLD = 0.82

# Bucket for rows with no usable department value (None/NaN/empty/whitespace-
# only). Rows are grouped here explicitly, never dropped and never crashed
# on — see _is_missing_department().
MISSING_DEPARTMENT_LABEL = "Unknown / Unspecified Department"


def _build_reverse_lookup() -> dict[str, str]:
    """normalized variant string -> canonical English label."""
    lookup: dict[str, str] = {}
    for canonical, variants in EN_AR_DEPARTMENT_SYNONYMS.items():
        lookup[canonical.strip().lower()] = canonical
        for v in variants:
            lookup[v.strip().lower()] = canonical
    return lookup


_REVERSE_LOOKUP = _build_reverse_lookup()


def _is_missing_department(raw: object) -> bool:
    """
    True for None/NaN/NaT/empty-or-whitespace-only values. MUST be checked
    before any string operation is attempted on *raw*.

    Do not rely on str(raw) or Series.astype(str) to normalize missing
    values to the string "nan" first — on pandas 3.x, Series.astype(str)
    leaves a float NaN as an actual float rather than stringifying it, so a
    raw NaN can otherwise reach downstream string operations (.lower(),
    iterating over characters, etc.) and raise
    `TypeError: 'float' object is not iterable`.
    """
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass  # pd.isna() only raises for non-scalar input; not a missing value here
    return not str(raw).strip()


def _exact_normalize(raw: str) -> str:
    """Tier 1: whitespace trim + casefold. Always safe, no ambiguity.
    Caller must ensure *raw* is not a missing value (see _is_missing_department) —
    this function assumes it already has real text to normalize."""
    return " ".join(str(raw).split()).casefold()


def _is_latin_script(s: str) -> bool:
    return all((not c.isalpha()) or ("a" <= c.lower() <= "z") for c in s)


@dataclass(frozen=True)
class DepartmentMerge:
    canonical_label: str
    variants_merged: list[str]
    counts_per_variant: dict[str, int]
    source: str  # "curated_synonym_table" — the only auto-merge tier that gets disclosed


@dataclass(frozen=True)
class DepartmentNormalizationResult:
    # Per-original-row-index normalized grouping key (safe to pd.Series.map / groupby on).
    normalized_keys: pd.Series
    # normalized_key -> display label to show the user (most frequent original variant,
    # or the curated canonical label when the synonym table matched).
    display_labels: dict[str, str]
    # Every curated-table merge that was actually applied to this dataset, for disclosure.
    merges_applied: list[DepartmentMerge]
    # Same-script near-duplicate raw values that were NOT merged (different
    # normalized keys, but similarity above threshold) — flagged for human
    # review, never auto-merged.
    unmerged_similar_variants: list[list[str]]


def normalize_department_series(raw: pd.Series) -> DepartmentNormalizationResult:
    """
    Normalize a raw pandas Series of department-name values into safe
    grouping keys, applying exact + curated-synonym-table normalization,
    and disclosing exactly what was merged and what near-duplicate variants
    were found but deliberately NOT merged.

    Missing values (None/NaN/empty/whitespace-only) are routed into a single
    explicit MISSING_DEPARTMENT_LABEL bucket rather than crashing or being
    silently dropped — checked before any string operation is attempted,
    since Series.astype(str) does not reliably stringify NaN on every
    pandas version (see _is_missing_department).
    """
    raw_str = raw.map(lambda v: MISSING_DEPARTMENT_LABEL if _is_missing_department(v) else str(v))
    exact_norm = raw_str.map(_exact_normalize)

    # Tier 2: curated synonym table, applied on top of the exact-normalized key.
    canonical = exact_norm.map(lambda k: _REVERSE_LOOKUP.get(k, k))

    normalized_keys = canonical

    # Build display labels: for each final key, pick the most common raw
    # (un-normalized) value that produced it — but prefer the curated
    # canonical spelling when the synonym table matched at all.
    display_labels: dict[str, str] = {}
    variants_by_key: dict[str, Counter] = {}
    for raw_val, key in zip(raw_str, normalized_keys):
        variants_by_key.setdefault(key, Counter())[raw_val] += 1

    for key, counter in variants_by_key.items():
        if key in EN_AR_DEPARTMENT_SYNONYMS:
            display_labels[key] = key  # canonical label IS the key here
        else:
            display_labels[key] = counter.most_common(1)[0][0]

    # Disclosure: which curated merges actually fired on this dataset.
    merges_applied: list[DepartmentMerge] = []
    for key, counter in variants_by_key.items():
        if key in EN_AR_DEPARTMENT_SYNONYMS and len(counter) > 1:
            merges_applied.append(DepartmentMerge(
                canonical_label=key,
                variants_merged=sorted(counter.keys()),
                counts_per_variant=dict(counter),
                source="curated_synonym_table",
            ))

    # Same-script near-duplicate detection among keys that did NOT merge.
    unmerged_similar_variants = _find_unmerged_similar_variants(list(variants_by_key.keys()), display_labels)

    return DepartmentNormalizationResult(
        normalized_keys=normalized_keys,
        display_labels=display_labels,
        merges_applied=merges_applied,
        unmerged_similar_variants=unmerged_similar_variants,
    )


def _find_unmerged_similar_variants(
    keys: list[str], display_labels: dict[str, str],
) -> list[list[str]]:
    """
    Flag pairs of DISTINCT normalized keys whose display labels are
    suspiciously similar (same script only — cross-script comparison is not
    meaningful) for human review. Never auto-merged.
    """
    labels = [display_labels[k] for k in keys]
    flagged_pairs: list[tuple[str, str]] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            if not (_is_latin_script(a) and _is_latin_script(b)):
                continue  # cross-script or non-Latin comparison: not meaningful, skip
            if a.casefold() == b.casefold():
                continue  # already merged by exact-normalization tier
            ratio = difflib.SequenceMatcher(None, a.casefold(), b.casefold()).ratio()
            if ratio >= _SIMILARITY_REVIEW_THRESHOLD:
                flagged_pairs.append((a, b))

    # Merge overlapping pairs into groups for a cleaner report.
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


def normalize_department_value(raw: Optional[str]) -> Optional[str]:
    """Single-value convenience wrapper (e.g. for a per-record department field).
    Returns None for missing input (None/NaN/empty/whitespace-only) — checked
    before any string operation, see _is_missing_department."""
    if _is_missing_department(raw):
        return None
    s = str(raw).strip()
    key = _exact_normalize(s)
    canonical = _REVERSE_LOOKUP.get(key, key)
    if canonical in EN_AR_DEPARTMENT_SYNONYMS:
        return canonical
    return s  # no table match — return the original (trimmed) value unchanged


def merges_applied_to_dicts(merges: list[DepartmentMerge]) -> list[dict]:
    return [
        {
            "canonical_label": m.canonical_label,
            "variants_merged": m.variants_merged,
            "counts_per_variant": m.counts_per_variant,
            "source": m.source,
        }
        for m in merges
    ]
