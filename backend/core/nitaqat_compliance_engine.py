"""
Nitaqat / Saudization Compliance — Phase 7.

**Critical framing, non-negotiable (see NITAQAT_COMPLIANCE_INVESTIGATION.md
for the full research trail):** this module NEVER claims to replicate the
official HRSD/Qiwa Nitaqat Mutawar calculation. The real program computes a
required Saudization percentage per company via a logarithmic formula with
per-economic-sub-activity coefficients (`Required % = MAX(0, m * ln(headcount) + c)`)
that are not published in any accessible primary source — the official HRSD
procedural-guideline PDF returned HTTP 403 when fetched directly during
investigation, and Qiwa's own calculator is an interactive JS tool, not a
static published table. Every result this module returns therefore carries
`is_official_calculation=False` and an explicit illustrative-estimate
disclaimer, in both the API response and (mandatory) the UI — this is the
same honesty discipline already established for
`financial_intelligence_engine.py`'s `SECTOR_BENCHMARK_CONFIDENCE`
("uncalibrated_generic_estimate") and Phase 5's refusal to invent a
Saudi-specific cost-per-hire figure.

**What IS real and cited** (confirmed via live web search, not memory):
  - Band names: Platinum, High Green, Mid Green, Low Green, Red — the Yellow
    band was eliminated in 2025 (establishments previously Yellow were
    reclassified to Red). Source: Mercans
    (https://mercans.com/glossary/saudization-nitaqat/, accessed 2026-08-06)
    and Middle East Briefing
    (https://www.middleeastbriefing.com/news/saudi-arabias-nitaqat-2026-update-latest-quotas-by-sector-and-what-foreign-employers-need-to-comply-now/,
    published 2026-05-15).
  - Small establishments ("Entity Size A", <=5 employees) use a genuinely
    simplified two-tier system (Green/Red only) — must employ at least 1
    Saudi to be Green. Source: Jisr HRMS / Token Talent Nitaqat-calculator
    summaries, cross-referenced during investigation.

**What is NOT real / is this module's own illustrative construction:**
  - The specific Saudization-percentage cut points between Platinum/High
    Green/Mid Green/Low Green/Red below (75% / 60% / 40% / 20%) are a
    deliberately simple, round, ILLUSTRATIVE heuristic of this module's own
    construction — not derived from any HRSD source, and explicitly NOT a
    substitute for the real per-sector logarithmic calculation. Every result
    says so.

**Band thresholds recalibrated (post-Phase-7 correction):** live browser
testing with a realistic 220-employee/9-department dataset (61.4%
Saudization overall, department range 46.7%-75.0% — see
`nitaqat_realistic_multidept_test_data.csv`) found the ORIGINAL thresholds
(Platinum ≥40% / High Green ≥30% / Mid Green ≥20% / Low Green ≥10% / Red
≥0%) classified every single department as "Platinum," since realistic
Saudi-org Saudization levels commonly cluster well above 40%. This wasn't a
correctness bug (the underlying percentages were right) — the illustrative
resolution was simply too coarse to be useful. A second live search (2026-08-07,
same discipline as the Phase 7 investigation) was run specifically to check
for any newly-published real distribution/cut-point data before adjusting
these by judgment call — none was found (Saudizationmeter's own compliance
guide and Mercans both confirm the real per-sector `y = m*ln(x) + c`
cut-points remain unpublished, same conclusion as the original Phase 7
investigation). What the search DID surface, and is cited below, is real
data on where sector-level Saudization *requirements* actually cluster
(20%-70%+, e.g. engineering 30%, retail 50-70%, procurement 70%, healthcare
50-60%) — which supports the judgment call that the illustrative bands
needed finer resolution spread across that 20-75% zone specifically, with
Platinum narrowed to a genuinely top-tier ≥75% rather than "anything above
40%." Real band *names* are unchanged (still the four cited above).

**Phase 17 regulatory update (2026-08):** live web research confirmed a
real rule change that further widens the gap between this module's
nationality-only estimate and the true official count. Effective
2026-04-15, Saudi MHRSD requires a Saudi employee's contract to be
electronically documented AND authenticated on the Qiwa platform before it
counts toward Nitaqat headcount — GOSI registration / a nationality field
alone is no longer sufficient. Phased compliance targets: 85% of contracts
documented by 2026-04-30, 90% by 2026-06-30. Sources (multiply
corroborated): Saudi MHRSD official announcement
(hrsd.gov.sa/en/media-center/news); Saudi Gazette,
"Saudi Arabia updates Nitaqat Saudization calculation through Qiwa
contracts" (saudigazette.com.sa/article/659791); Erickson Immigration
Group legal update citing the same MHRSD announcement
(eiglaw.com/saudi-arabia-saudization-updates-qiwa-contract-documentation-impacts-nitaqat-calculations).
This module has zero visibility into Qiwa contract-authentication status —
it only ever sees a nationality/Saudi-status column — so this is disclosed
explicitly via `NITAQAT_QIWA_CONTRACT_NOTE_EN`/`_AR`, appended to the
existing illustrative-estimate disclaimer rather than replacing it.

**Department/economic-activity grouping** reuses
`backend/core/department_normalizer.py` verbatim (the same shared fix
already applied to HR department data and recruitment pipeline data) — a
sector/activity column has the identical Arabic/English/casing
inconsistency problem.

**Column detection** follows this codebase's established local-regex
convention (`_find_column()` + per-field `re.compile`, English + Arabic in
one pattern) rather than reinventing a fuzzy matcher — same reasoning
already documented in `recruitment_pipeline_engine.py`'s module docstring:
`theory_aware_column_mapper.py`'s `ConstructDefinition` model is built for
Likert-scale survey columns, `saudi_schema_intelligence.py` is a whole
ERP-schema classifier (and confirmed dead relative to the live product,
per NITAQAT_COMPLIANCE_INVESTIGATION.md §2) — neither fits a small, fixed
set of compliance fields.

**Deduplication** is not reimplemented here — `SecureFileIngestion.scan()`
already deduplicates every uploaded dataframe once, pipeline-level, before
any module (this one included) ever sees it.
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

_NATIONALITY_PATTERNS = re.compile(
    r"\b(nationality|is[_\s]?saudi|saudi[_\s]?status|saudi[_\s]?national|citizenship|"
    r"الجنسية|جنسية|سعودي\/غير سعودي)\b",
    re.I,
)
_SECTOR_OR_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|sector|economic[_\s]?activity|business[_\s]?activity|"
    r"القسم|الإدارة|النشاط[_\s]?الاقتصادي|القطاع)\b",
    re.I,
)

# ── Saudi/non-Saudi value classification ────────────────────────────────────
# A single token check handles both an explicit boolean-style column
# (IsSaudi: Yes/No, 1/0) and a free-text Nationality column (Saudi/India/
# Egypt/...): anything matching a Saudi token is Saudi; any other non-missing
# value is treated as non-Saudi (a real nationality column's non-Saudi
# entries name dozens of different countries — there is no useful
# "unclassified" middle ground for a genuinely free-text nationality field).

_SAUDI_TOKENS = {
    "saudi", "saudi arabia", "ksa", "sa", "1", "yes", "true",
    "سعودي", "سعودية", "السعودية", "المملكة العربية السعودية",
}
_EXPLICIT_NON_SAUDI_TOKENS = {
    "non-saudi", "non saudi", "nonsaudi", "expat", "expatriate", "foreign", "foreigner",
    "0", "no", "false", "غير سعودي", "أجنبي", "غير سعودية",
}


def _is_missing_value(raw: object) -> bool:
    """Same missing-value discipline established across this codebase's
    other Phase 6/5 fixes — checked before any string operation, since
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


def _classify_saudi_status(raw: object) -> Optional[bool]:
    """Returns True (Saudi), False (non-Saudi), or None (missing value,
    excluded from the denominator — never guessed at)."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _SAUDI_TOKENS:
        return True
    return False  # explicit non-Saudi token OR any other real nationality value


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


# ── Illustrative band thresholds (this module's own construction — see
#    module docstring for why no real HRSD table could be used, and for the
#    post-Phase-7 recalibration that produced these specific numbers) ──────

_BAND_ORDER = ["Red", "Low Green", "Mid Green", "High Green", "Platinum"]

# Recalibrated from the original 40/30/20/10 spacing (which flattened every
# realistic 40-100% department into "Platinum" — confirmed via live testing
# with a 220-employee/9-department, 46.7%-75.0%-range dataset). Even 20-point
# spacing across the 20-75% zone, where cited real-world sector Saudization
# requirements actually cluster (20%-70%+), with Platinum narrowed to a
# genuinely top-tier >=75% band rather than "anything above 40%."
ILLUSTRATIVE_BAND_THRESHOLDS: dict[str, float] = {
    "Platinum":    75.0,
    "High Green":  60.0,
    "Mid Green":   40.0,
    "Low Green":   20.0,
    "Red":          0.0,
}
# Confirmed real structural rule (not illustrative): establishments with
# <=5 total employees ("Entity Size A") use a genuinely simplified two-tier
# system — Green if >=1 Saudi employee, else Red. See module docstring.
SMALL_ESTABLISHMENT_MAX_HEADCOUNT = 5

NITAQAT_CALCULATION_CONFIDENCE = "illustrative_non_official"

# Phase 17 — regulatory update, additive to the existing disclaimer below.
# Confirmed via live web research (2026-08): Saudi MHRSD announced that,
# effective 2026-04-15, a Saudi employee's contract must be electronically
# documented AND authenticated on the Qiwa platform to count toward Nitaqat
# Saudization headcount at all — GOSI registration / a nationality field is
# no longer sufficient on its own. Phased compliance targets: 85% of
# contracts documented by 2026-04-30, 90% by 2026-06-30. Sources (multiply
# corroborated, 2026): Saudi MHRSD official announcement
# (hrsd.gov.sa/en/media-center/news — "The Ministry of Human Resources and
# Social Development has mandated the electronic documentation of
# employment contracts through the 'Qiwa' platform"); Saudi Gazette,
# "Saudi Arabia updates Nitaqat Saudization calculation through Qiwa
# contracts" (saudigazette.com.sa/article/659791); Erickson Immigration
# Group legal update citing the same MHRSD announcement
# (eiglaw.com/saudi-arabia-saudization-updates-qiwa-contract-documentation-impacts-nitaqat-calculations).
# This platform has zero visibility into Qiwa contract-authentication
# status (it only ever sees a nationality/Saudi-status column) — this note
# discloses that gap explicitly rather than silently going stale.
NITAQAT_QIWA_CONTRACT_NOTE_EN = (
    "This estimate is based on nationality data only. Since April 2026, "
    "official Nitaqat counting also requires Qiwa contract authentication "
    "status, which this platform cannot verify — actual counted headcount "
    "may differ from this estimate."
)
NITAQAT_QIWA_CONTRACT_NOTE_AR = (
    "يعتمد هذا التقدير على بيانات الجنسية فقط. اعتباراً من أبريل 2026، "
    "يتطلب الاحتساب الرسمي لنطاقات أيضاً حالة توثيق العقد عبر منصة قوى، "
    "وهو أمر لا يمكن لهذه المنصة التحقق منه — قد يختلف العدد الفعلي "
    "المُحتسب عن هذا التقدير."
)

NITAQAT_ILLUSTRATIVE_DISCLAIMER_EN = (
    "Illustrative estimate — NOT an official Nitaqat/HRSD determination. "
    "The real Nitaqat Mutawar calculation uses a per-economic-sector "
    "logarithmic formula with coefficients HRSD has not published in any "
    "accessible public source. This is a simplified, round-number band "
    "heuristic for internal HR planning only — verify actual Nitaqat status "
    "via Qiwa (qiwa.sa) before making any hiring, visa, or compliance decision. "
    + NITAQAT_QIWA_CONTRACT_NOTE_EN
)
NITAQAT_ILLUSTRATIVE_DISCLAIMER_AR = (
    "تقدير إرشادي — وليس تصنيفاً رسمياً من نطاقات أو وزارة الموارد البشرية والتنمية "
    "الاجتماعية. الحساب الفعلي لبرنامج نطاقات متطور يعتمد على معادلة لوغاريتمية "
    "خاصة بكل نشاط اقتصادي لم تُنشر معاملاتها في أي مصدر عام متاح. هذا تقدير "
    "مبسط لأغراض التخطيط الداخلي فقط — يرجى التحقق من الحالة الفعلية عبر منصة "
    "قوى (qiwa.sa) قبل اتخاذ أي قرار توظيف أو تأشيرة أو امتثال. "
    + NITAQAT_QIWA_CONTRACT_NOTE_AR
)


def _band_for_pct(pct: float) -> str:
    for band in ["Platinum", "High Green", "Mid Green", "Low Green"]:
        if pct >= ILLUSTRATIVE_BAND_THRESHOLDS[band]:
            return band
    return "Red"


def _band_for_small_establishment(n_saudi: int) -> str:
    return "Green" if n_saudi >= 1 else "Red"


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DepartmentSaudizationBreakdown:
    department: str
    n_total: int
    n_saudi: int
    n_non_saudi: int
    saudization_pct: float
    band: str


@dataclass(frozen=True)
class NitaqatComplianceResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_total: int
    n_saudi: int
    n_non_saudi: int
    n_excluded_missing: int
    saudization_pct: Optional[float]
    band: Optional[str]
    is_small_establishment: bool
    department_breakdown: list[DepartmentSaudizationBreakdown]
    department_normalization_notes: list[str]
    band_thresholds_used: dict[str, float]
    is_official_calculation: bool
    calculation_confidence: str
    narrative_en: str
    narrative_ar: str
    governance_note: str
    disclaimer_en: str
    disclaimer_ar: str
    sources: list[str]
    computed_at: str


_ALL_COLUMN_LABELS: dict[str, str] = {
    "nationality_or_saudi_status": "nationality / Saudi status (e.g. Nationality, IsSaudi)",
    "department_or_sector": "department / economic activity (optional, for a per-department breakdown)",
}


def unavailable_nitaqat_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> NitaqatComplianceResult:
    """Public constructor for an `available=False` result — used both when
    no nationality column exists and by API routes that need to
    short-circuit before calling analyze_nitaqat_compliance()."""
    return NitaqatComplianceResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {k: False for k in _ALL_COLUMN_LABELS},
        n_total=0,
        n_saudi=0,
        n_non_saudi=0,
        n_excluded_missing=0,
        saudization_pct=None,
        band=None,
        is_small_establishment=False,
        department_breakdown=[],
        department_normalization_notes=[],
        band_thresholds_used=dict(ILLUSTRATIVE_BAND_THRESHOLDS),
        is_official_calculation=False,
        calculation_confidence=NITAQAT_CALCULATION_CONFIDENCE,
        narrative_en=reason,
        narrative_ar="لا تتوفر بيانات الجنسية اللازمة لتقدير نسبة السعودة في هذه البيانات.",
        governance_note=(
            "Nitaqat/Saudization estimation activates automatically when the "
            "uploaded dataset contains a recognisable nationality or Saudi-status "
            "column. No Saudization percentage or band is ever fabricated when "
            "this data is absent."
        ),
        disclaimer_en=NITAQAT_ILLUSTRATIVE_DISCLAIMER_EN,
        disclaimer_ar=NITAQAT_ILLUSTRATIVE_DISCLAIMER_AR,
        sources=[],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def analyze_nitaqat_compliance(df: pd.DataFrame) -> NitaqatComplianceResult:
    """
    Estimate an ILLUSTRATIVE Saudization percentage and Nitaqat-style band
    from an uploaded workforce dataset. Returns `available=False` — never a
    fabricated percentage — when no recognisable nationality/Saudi-status
    column is found. See module docstring for the full honesty framing:
    every available=True result also carries `is_official_calculation=False`
    and an explicit illustrative-estimate disclaimer.
    """
    if df is None or len(df) == 0:
        return unavailable_nitaqat_result(
            "Uploaded dataset is empty — no Nitaqat/Saudization estimate possible."
        )

    nationality_col = _find_column(df, _NATIONALITY_PATTERNS)
    dept_col = _find_column(df, _SECTOR_OR_DEPARTMENT_PATTERNS)

    columns_detected = {
        "nationality_or_saudi_status": nationality_col is not None,
        "department_or_sector": dept_col is not None,
    }

    if nationality_col is None:
        missing = ", ".join(
            _ALL_COLUMN_LABELS[k] for k, present in columns_detected.items() if not present
        )
        return unavailable_nitaqat_result(
            "No nationality/Saudi-status column was detected in this dataset "
            "(e.g. a column named 'Nationality' or 'IsSaudi'). This looks like "
            "structured HR data without nationality information. "
            f"Columns that would activate this feature if present: {missing}.",
            columns_detected=columns_detected,
        )

    classified = df[nationality_col].map(_classify_saudi_status)
    n_excluded_missing = int(classified.isna().sum())
    n_saudi = int((classified == True).sum())      # noqa: E712 — explicit tri-state check (True/False/None)
    n_non_saudi = int((classified == False).sum())  # noqa: E712
    n_total = n_saudi + n_non_saudi

    if n_total == 0:
        return unavailable_nitaqat_result(
            f"A '{nationality_col}' column was found but contained no usable values "
            "(all missing/blank).",
            columns_detected=columns_detected,
        )

    saudization_pct = round(100.0 * n_saudi / n_total, 1)
    is_small = n_total <= SMALL_ESTABLISHMENT_MAX_HEADCOUNT
    band = _band_for_small_establishment(n_saudi) if is_small else _band_for_pct(saudization_pct)

    # ── Department/sector breakdown (shared canonical normalizer) ──────────
    department_breakdown: list[DepartmentSaudizationBreakdown] = []
    dept_notes: list[str] = []
    if dept_col is not None:
        dept_norm = normalize_department_series(df[dept_col])
        dept_display = dept_norm.normalized_keys.map(
            lambda k: dept_norm.display_labels.get(k, k)
        )
        for merge in dept_norm.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_notes.append(
                f"Merged {variants_str} into '{merge.canonical_label}' "
                f"(recognised as the same department/sector): {merge.counts_per_variant}."
            )
        for group in dept_norm.unmerged_similar_variants:
            dept_notes.append(
                f"Found similarly-named but NOT merged department/sector values "
                f"{', '.join(repr(v) for v in group)} — review manually."
            )

        work = pd.DataFrame({"_dept": dept_display.values, "_saudi": classified.values})
        for dept_name, grp in work.groupby("_dept"):
            grp_valid = grp[grp["_saudi"].notna()]
            n_grp_saudi = int((grp_valid["_saudi"] == True).sum())      # noqa: E712
            n_grp_non_saudi = int((grp_valid["_saudi"] == False).sum())  # noqa: E712
            n_grp_total = n_grp_saudi + n_grp_non_saudi
            if n_grp_total == 0:
                continue
            grp_pct = round(100.0 * n_grp_saudi / n_grp_total, 1)
            grp_is_small = n_grp_total <= SMALL_ESTABLISHMENT_MAX_HEADCOUNT
            grp_band = (
                _band_for_small_establishment(n_grp_saudi) if grp_is_small
                else _band_for_pct(grp_pct)
            )
            department_breakdown.append(DepartmentSaudizationBreakdown(
                department=str(dept_name),
                n_total=n_grp_total,
                n_saudi=n_grp_saudi,
                n_non_saudi=n_grp_non_saudi,
                saudization_pct=grp_pct,
                band=grp_band,
            ))
        department_breakdown.sort(key=lambda d: d.saudization_pct)

    narrative_en = (
        f"Of {n_total} classified employees, {n_saudi} ({saudization_pct:.1f}%) "
        f"are recorded as Saudi nationals. "
        + (
            f"This establishment has {n_total} total employees (<= "
            f"{SMALL_ESTABLISHMENT_MAX_HEADCOUNT}), so the simplified small-"
            f"establishment two-tier rule applies: {band}. "
            if is_small else
            f"Illustrative band: {band}. "
        )
        + "This is an illustrative estimate, not an official Nitaqat/HRSD "
        "determination — see disclaimer."
    )
    narrative_ar = (
        f"من أصل {n_total} موظفاً مصنّفاً، {n_saudi} ({saudization_pct:.1f}%) "
        f"مسجلون كمواطنين سعوديين. المستوى الإرشادي: {band}. هذا تقدير إرشادي "
        "وليس تصنيفاً رسمياً من نطاقات."
    )

    sources: list[str] = [
        "Band names (Platinum/High Green/Mid Green/Low Green/Red, Yellow eliminated "
        "2025) confirmed via live web search: Mercans "
        "(https://mercans.com/glossary/saudization-nitaqat/) and Middle East Briefing "
        "(published 2026-05-15), see NITAQAT_COMPLIANCE_INVESTIGATION.md §3.",
        "Small-establishment (<=5 employees) simplified two-tier Green/Red rule "
        "confirmed via the same investigation (Qiwa-calculator secondary-source "
        "summaries) — a real structural program rule, not illustrative.",
        "Percentage cut points between bands (75%/60%/40%/20%) are THIS MODULE'S "
        "OWN illustrative construction — no citable HRSD source publishes a "
        "universal percentage table; the real calculation is a per-sector "
        "logarithmic formula with unpublished coefficients (see module docstring). "
        "Recalibrated 2026-08-07 from the original 40%/30%/20%/10% spacing, which "
        "live testing found classified every department in a realistic 46.7%-75.0% "
        "range as 'Platinum' — too coarse to be useful, though not incorrect.",
        "Recalibration was informed by real (cited, not invented) sector "
        "Saudization-requirement examples confirming realistic percentages "
        "commonly cluster in the 20%-70%+ range — e.g. engineering 30%, retail "
        "50-70%, healthcare 50-60%, procurement 70% — via live web search: "
        "Envoy Global (envoyglobal.com), Motaded (motaded.com.sa), and "
        "Saudizationmeter's compliance guide, all accessed 2026-08-07. None of "
        "these publish actual band cut-points (confirming the same conclusion "
        "as the original Phase 7 investigation), so the specific new thresholds "
        "remain this module's own judgment call, not a cited official table.",
    ]
    if dept_col is not None:
        sources.append(
            "Department/sector grouping reuses backend/core/department_normalizer.py "
            "(the same fix applied to HR department data)."
        )

    return NitaqatComplianceResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        n_total=n_total,
        n_saudi=n_saudi,
        n_non_saudi=n_non_saudi,
        n_excluded_missing=n_excluded_missing,
        saudization_pct=saudization_pct,
        band=band,
        is_small_establishment=is_small,
        department_breakdown=department_breakdown,
        department_normalization_notes=dept_notes,
        band_thresholds_used=dict(ILLUSTRATIVE_BAND_THRESHOLDS),
        is_official_calculation=False,
        calculation_confidence=NITAQAT_CALCULATION_CONFIDENCE,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        governance_note=(
            "Nitaqat/Saudization figures here are illustrative HR-planning "
            "indicators only, never an official compliance determination, and "
            "must not be used as the sole basis for hiring, visa, or regulatory "
            "decisions. Verify actual status via Qiwa before acting."
        ),
        disclaimer_en=NITAQAT_ILLUSTRATIVE_DISCLAIMER_EN,
        disclaimer_ar=NITAQAT_ILLUSTRATIVE_DISCLAIMER_AR,
        sources=sources,
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def nitaqat_compliance_to_dict(r: NitaqatComplianceResult) -> dict[str, Any]:
    """Serialize NitaqatComplianceResult to a JSON-safe dict."""
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "n_total": r.n_total,
        "n_saudi": r.n_saudi,
        "n_non_saudi": r.n_non_saudi,
        "n_excluded_missing": r.n_excluded_missing,
        "saudization_pct": r.saudization_pct,
        "band": r.band,
        "is_small_establishment": r.is_small_establishment,
        "department_breakdown": [
            {
                "department": d.department,
                "n_total": d.n_total,
                "n_saudi": d.n_saudi,
                "n_non_saudi": d.n_non_saudi,
                "saudization_pct": d.saudization_pct,
                "band": d.band,
            }
            for d in r.department_breakdown
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "band_thresholds_used": r.band_thresholds_used,
        "is_official_calculation": r.is_official_calculation,
        "calculation_confidence": r.calculation_confidence,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
        "disclaimer_en": r.disclaimer_en,
        "disclaimer_ar": r.disclaimer_ar,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }


# ── Phase 8 extension point: per-employee Saudi-status join key ────────────
# Additive only — does not alter analyze_nitaqat_compliance()'s existing
# behaviour, return shape, or any Phase 7 code path above this line.
#
# Why this exists: succession_readiness_engine.py (Phase 8) can compute "N
# high-readiness Saudi employees identified as potential leadership
# pipeline" when a single uploaded file happens to contain BOTH a
# nationality column AND performance/tenure columns. Rather than having one
# engine import internals from another (no engine module does that anywhere
# in this codebase — department_normalizer.py is a shared *utility*, not an
# engine), this function exposes a PII-safe, one-way-hashed per-employee
# join key that the API route layer (which already imports both engines
# independently) can use to combine the two results. See
# local_analysis_routes.py's /succession-readiness route for the join.
_ID_COLUMN_CANDIDATES = ("EmployeeID", "employee_id", "EmpID", "emp_id")


def get_saudi_status_by_record_id(df: pd.DataFrame) -> Optional[dict[str, bool]]:
    """
    Return {record_id_safe: is_saudi} for every employee with both a usable
    ID and a classifiable nationality value, or None when a cross-link is
    not possible.

    `record_id_safe` uses the EXACT SAME one-way sha256(first 6 hex chars,
    uppercased, "EMP-" prefixed) scheme as employee_risk_scoring.py's and
    succession_readiness_engine.py's `_make_record_id()` — but ONLY the
    named-ID-column form, never the positional-index fallback. A positional
    fallback ID here would not reliably refer to the same employee as
    another module's positional fallback, since each module's position is
    computed over a DIFFERENT subset of rows filtered by that module's own
    valid-value criteria (e.g. rows with a usable Nationality vs. rows with
    usable PerformanceRating+YearsAtCompany are not the same rows). Rather
    than risk a silent wrong join between two different employees, this
    function returns None whenever no recognised named ID column exists in
    the upload — the same "refuse rather than guess" discipline as every
    other honesty gate in this codebase.
    """
    if df is None or len(df) == 0:
        return None
    nationality_col = _find_column(df, _NATIONALITY_PATTERNS)
    if nationality_col is None:
        return None
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)
    if id_col is None:
        return None

    result: dict[str, bool] = {}
    for raw_id, raw_nat in zip(df[id_col], df[nationality_col]):
        if _is_missing_value(raw_id):
            continue
        status = _classify_saudi_status(raw_nat)
        if status is None:
            continue
        record_hash = hashlib.sha256(str(raw_id).encode()).hexdigest()[:6].upper()
        result[f"EMP-{record_hash}"] = status
    return result
