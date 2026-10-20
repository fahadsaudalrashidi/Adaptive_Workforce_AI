"""
Contract Expiry & Renewal Monitoring — Phase 18.

A genuinely new domain for this platform: employment-contract and Iqama
(Saudi residency permit) lifecycle tracking. In the Saudi context both have
defined validity periods with real legal/compliance consequences if missed
— a distinct, urgent kind of risk this platform previously had zero
visibility into.

**Column-detection approach — a deliberate choice, not the two modules
named in the original brief.** `theory_aware_column_mapper.py` is built
around `ConstructDefinition`/`ConstructMapping` for Likert-scale survey
columns (psychometric constructs with confidence scoring) — not a fit for
a single date column. `saudi_schema_intelligence.py` is a whole ERP-schema
classifier already confirmed dead relative to the live product (see
`nitaqat_compliance_engine.py`'s own module docstring, citing
`NITAQAT_COMPLIANCE_INVESTIGATION.md §2`, and confirmed independently here
by grepping the backend: it is referenced only in a placeholder string in
`enterprise_routes.py`, never actually called). This module instead reuses
the local-regex `_find_column()` convention already established in every
other Phase 5-17 engine (succession, overtime, nitaqat, pay equity) — the
same reasoning documented in each of those modules' docstrings applies
here unchanged.

**Two genuinely separate signals, never merged.** A contract end date and
an Iqama/visa expiry date are different real-world things (one is an
employment-relationship boundary, the other is a legal work-authorization
boundary) that can — and often do — diverge for the same employee. Two
independent regex patterns and two independent parsing/tiering passes are
used; an employee can appear in both, one, or neither breakdown.

**Urgency tiers** (overdue / ≤30 days / 31-60 days / 61-90 days / 90+
days) mirror the boundaries the brief itself proposed, which line up with
standard HR/visa-renewal planning practice (a 90-day outer horizon to
start planning, a 30-day inner horizon where action is genuinely urgent).
These are explicitly disclosed as this platform's own illustrative
planning heuristic, NOT a legally mandated renewal timeline — actual
Iqama/visa renewal deadlines, grace periods, and penalties are governed by
real Saudi immigration regulations this module does not verify
per-employee (no live regulatory research was performed for this specific
claim this phase, unlike Phase 17's Qiwa contract-authentication finding,
which WAS independently verified — this module's tier boundaries are
disclosed as a planning aid precisely because they have not been).

**Cross-links follow the exact Phase 8 architectural precedent**
(`nitaqat_compliance_engine.get_saudi_status_by_record_id` /
`local_analysis_routes.py`'s `/succession-readiness` route): this module
never imports `succession_readiness_engine.py` or
`nitaqat_compliance_engine.py`, and neither of those imports this module.
`get_expiry_signals_by_record_id()` below returns a PII-safe,
one-way-hashed `{record_id_safe: {...}}` map using the EXACT SAME hash
scheme as `employee_risk_scoring.py`'s / `succession_readiness_engine.py`'s
/ `nitaqat_compliance_engine.py`'s `_make_record_id()`
(`sha256(raw_id)[:6].upper()`, `"EMP-"`-prefixed) — and, like
`get_saudi_status_by_record_id()`, returns `None` rather than falling back
to a positional index whenever no real named ID column exists, for the
identical reason: a positional fallback computed over THIS module's
valid-row subset would not reliably refer to the same employee as another
module's positional fallback computed over a DIFFERENT valid-row subset.
The route layer (which already imports every engine independently) is the
only place that combines them.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series

# ── Column detection (local-regex convention, see module docstring) ────────

_CONTRACT_END_PATTERNS = re.compile(
    r"\b(contract[_\s]?end[_\s]?date|contract[_\s]?expiry|contract[_\s]?expiration|"
    r"contractenddate|contract[_\s]?termination[_\s]?date|"
    r"تاريخ[_\s]?انتهاء[_\s]?العقد|نهاية[_\s]?العقد)\b",
    re.I,
)
_IQAMA_EXPIRY_PATTERNS = re.compile(
    r"\b(iqama[_\s]?expiry|iqama[_\s]?expiration|iqamaexpirydate|iqama[_\s]?end[_\s]?date|"
    r"visa[_\s]?expiry|visa[_\s]?expiration|visaexpirydate|"
    r"residency[_\s]?permit[_\s]?expiry|residency[_\s]?expiry|"
    r"انتهاء[_\s]?الإقامة|تاريخ[_\s]?انتهاء[_\s]?الإقامة|انتهاء[_\s]?التأشيرة)\b",
    re.I,
)
_DEPARTMENT_PATTERNS = re.compile(
    r"\b(department|dept|division|القسم|الإدارة)\b",
    re.I,
)

# Same named-ID-column convention as nitaqat_compliance_engine.py's
# _ID_COLUMN_CANDIDATES — deliberately duplicated locally rather than
# imported, matching this codebase's established per-module convention for
# small, fixed detection constants (see succession/overtime/nitaqat/pay
# equity engines, none of which import each other's column-pattern
# constants either).
_ID_COLUMN_CANDIDATES = ("EmployeeID", "employee_id", "EmpID", "emp_id")

# ── Urgency tiers ────────────────────────────────────────────────────────────

_TIER_ORDER = ["overdue", "critical_0_30", "urgent_31_60", "upcoming_61_90", "monitored_90_plus"]

_TIER_LABELS_EN: dict[str, str] = {
    "overdue": "Overdue / Expired",
    "critical_0_30": "Critical (≤30 days)",
    "urgent_31_60": "Urgent (31-60 days)",
    "upcoming_61_90": "Upcoming (61-90 days)",
    "monitored_90_plus": "Monitored (90+ days)",
}
_TIER_LABELS_AR: dict[str, str] = {
    "overdue": "منتهي / متأخر",
    "critical_0_30": "حرج (≤30 يوماً)",
    "urgent_31_60": "عاجل (31-60 يوماً)",
    "upcoming_61_90": "قادم (61-90 يوماً)",
    "monitored_90_plus": "مُراقب (90+ يوماً)",
}

# Tiers shown in the row-level "who exactly" table — anything 90+ days out
# is aggregate-only (tier_counts), not individually actionable yet.
_ROW_LEVEL_TIERS = frozenset({"overdue", "critical_0_30", "urgent_31_60", "upcoming_61_90"})
_MAX_ROW_LEVEL_CANDIDATES = 50

# The threshold both cross-links use for "expiring soon" — see module
# docstring for why 90 days (outer planning horizon) was chosen over the
# narrower 30/60-day tiers: a leadership-critical or compliance-relevant
# flag should surface as soon as planning should realistically begin, not
# only once it is already urgent.
CROSS_LINK_HORIZON_DAYS = 90

CONTRACT_EXPIRY_CONFIDENCE = "planning_aid_not_legal_advice"
CONTRACT_EXPIRY_DISCLAIMER_EN = (
    "Contract/Iqama expiry tracking is a planning aid based on the expiry dates present "
    "in your uploaded data — it is NOT legal or immigration advice. The urgency tiers "
    "(≤30 / 31-60 / 61-90 / 90+ days) are this platform's own illustrative planning "
    "heuristic, not a legally mandated renewal timeline. Actual Iqama/visa renewal "
    "deadlines, grace periods, and penalties are governed by real Saudi immigration "
    "regulations this platform does not verify per-employee. Qualified HR and legal "
    "review is required before any renewal, compliance, or employment action."
)
CONTRACT_EXPIRY_DISCLAIMER_AR = (
    "متابعة انتهاء العقود/الإقامات أداة إرشادية للتخطيط استناداً إلى تواريخ الانتهاء "
    "الموجودة في بياناتك المُحمّلة — وليست استشارة قانونية أو استشارة هجرة. مستويات "
    "الإلحاح (≤30 / 31-60 / 61-90 / 90+ يوماً) هي معيار إرشادي داخلي من تصميم هذه "
    "المنصة، وليست جدولاً زمنياً قانونياً مُلزماً للتجديد. المواعيد الفعلية لتجديد "
    "الإقامة/التأشيرة، وفترات السماح، والغرامات تحكمها أنظمة الهجرة السعودية الفعلية "
    "التي لا تتحقق منها هذه المنصة لكل موظف. تلزم مراجعة متخصصي الموارد البشرية "
    "والقانون قبل أي إجراء متعلق بالتجديد أو الامتثال أو التوظيف."
)

_SOURCES = [
    "Department-level grouping reused verbatim from department_normalizer.py "
    "(the same fix already applied to HR department data across every module "
    "this session).",
    "Urgency-tier boundaries (30/60/90 days) are this platform's own "
    "illustrative planning heuristic — see module docstring — not sourced to "
    "a specific published Saudi immigration regulation.",
]

_COLUMN_LABELS_EN: dict[str, str] = {
    "contract_end_date": "Contract end date (e.g. ContractEndDate, ContractExpiry)",
    "iqama_or_visa_expiry": "Iqama / visa expiry date (e.g. IqamaExpiry, VisaExpiryDate)",
    "department": "Department (optional — enables department-level rollup)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "contract_end_date": "تاريخ انتهاء العقد (مثال: ContractEndDate)",
    "iqama_or_visa_expiry": "تاريخ انتهاء الإقامة / التأشيرة (مثال: IqamaExpiry)",
    "department": "القسم (اختياري — يفعّل التجميع حسب القسم)",
}


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
    """Same one-way-hash scheme as employee_risk_scoring.py's /
    succession_readiness_engine.py's / nitaqat_compliance_engine.py's
    `_make_record_id()` — see module docstring."""
    h = hashlib.sha256(str(raw_id).encode()).hexdigest()[:6].upper()
    return f"EMP-{h}"


def _tier_for_days(days: int) -> str:
    if days < 0:
        return "overdue"
    if days <= 30:
        return "critical_0_30"
    if days <= 60:
        return "urgent_31_60"
    if days <= 90:
        return "upcoming_61_90"
    return "monitored_90_plus"


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExpiryCandidate:
    record_id_safe: str
    department: Optional[str]
    signal_type: str          # "contract" | "iqama"
    expiry_date: str          # ISO date (YYYY-MM-DD)
    days_remaining: int
    urgency_tier: str
    # Phase 40 — see PHASE_27 report §3. This platform is used single-tenant
    # on the uploader's own local data, not a shared/redistributed
    # anonymized dataset, so showing the REAL uploaded ID (when present) is
    # more useful than a hash the user can't cross-reference against their
    # own spreadsheet. record_id_safe is KEPT unchanged (still used
    # internally for cross-link joins, e.g. Phase 8/18's decoupled-engine
    # pattern) — this is purely an additional display field, never fabricated
    # when no real ID column exists.
    employee_id_raw: Optional[str] = None


@dataclass(frozen=True)
class DepartmentExpiryBreakdown:
    department: str
    signal_type: str          # "contract" | "iqama"
    n_total: int
    n_overdue: int
    n_critical_0_30: int
    n_urgent_31_60: int


@dataclass(frozen=True)
class ContractExpiryResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    contract_end_column: Optional[str]
    iqama_expiry_column: Optional[str]
    n_employees_total: int
    n_contract_records_valid: int
    n_iqama_records_valid: int
    n_invalid_dates_excluded: int
    date_quality_warnings: list[str]
    contract_tier_counts: dict[str, int]
    iqama_tier_counts: dict[str, int]
    candidates: list[ExpiryCandidate]
    department_breakdown: list[DepartmentExpiryBreakdown]
    department_normalization_notes: list[str]
    narrative_en: str
    narrative_ar: str
    contract_expiry_confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_contract_expiry_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> ContractExpiryResult:
    return ContractExpiryResult(
        available=False,
        reason=reason,
        columns_detected=columns_detected or {},
        contract_end_column=None,
        iqama_expiry_column=None,
        n_employees_total=0,
        n_contract_records_valid=0,
        n_iqama_records_valid=0,
        n_invalid_dates_excluded=0,
        date_quality_warnings=[],
        contract_tier_counts={},
        iqama_tier_counts={},
        candidates=[],
        department_breakdown=[],
        department_normalization_notes=[],
        narrative_en="Contract/Iqama expiry monitoring not available for this dataset.",
        narrative_ar="متابعة انتهاء العقود/الإقامات غير متاحة لهذه البيانات.",
        contract_expiry_confidence=CONTRACT_EXPIRY_CONFIDENCE,
        disclaimer_en=CONTRACT_EXPIRY_DISCLAIMER_EN,
        disclaimer_ar=CONTRACT_EXPIRY_DISCLAIMER_AR,
        governance_note=(
            "No expiry figures are computed or displayed when no contract-end or "
            "Iqama/visa-expiry column is detected — this platform never fabricates "
            "a renewal date."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


def _parse_signal(
    df: pd.DataFrame,
    date_col: str,
    id_col: Optional[str],
    dept_keys: Optional[pd.Series],
    dept_labels: dict[str, str],
    signal_type: str,
    as_of: pd.Timestamp,
) -> tuple[list[ExpiryCandidate], dict[str, int], int, dict[str, dict[str, int]], dict[str, int]]:
    """
    Parse one expiry-date column into candidates + tier counts.
    Returns (candidates, tier_counts, n_invalid, dept_counts, id_to_days).
    `id_to_days` maps record_id_safe -> days_remaining, used by
    `get_expiry_signals_by_record_id()` — kept separate from `candidates`
    because candidates are capped/filtered for display, but the cross-link
    lookup must not silently drop employees just because they didn't make
    the display cap.
    """
    parsed = pd.to_datetime(df[date_col], errors="coerce")
    valid_mask = parsed.notna()
    n_invalid = int((~valid_mask).sum())

    days_remaining = (parsed - as_of).dt.days
    tier_counts: dict[str, int] = {t: 0 for t in _TIER_ORDER}
    dept_counts: dict[str, dict[str, int]] = {}
    candidates: list[ExpiryCandidate] = []
    id_to_days: dict[str, int] = {}

    for idx in df.index[valid_mask]:
        days = int(days_remaining.loc[idx])
        tier = _tier_for_days(days)
        tier_counts[tier] += 1

        dept_label = None
        if dept_keys is not None:
            key = dept_keys.loc[idx]
            dept_label = dept_labels.get(key, key) if key is not None else None
            if dept_label:
                bucket = dept_counts.setdefault(dept_label, {"n_total": 0, "n_overdue": 0, "n_critical_0_30": 0, "n_urgent_31_60": 0})
                bucket["n_total"] += 1
                if tier == "overdue":
                    bucket["n_overdue"] += 1
                elif tier == "critical_0_30":
                    bucket["n_critical_0_30"] += 1
                elif tier == "urgent_31_60":
                    bucket["n_urgent_31_60"] += 1

        record_id = None
        raw_id_display: Optional[str] = None
        if id_col is not None and not _is_missing_value(df.at[idx, id_col]):
            record_id = _safe_record_id(df.at[idx, id_col])
            raw_id_display = str(df.at[idx, id_col]).strip()
            id_to_days[record_id] = days

        if tier in _ROW_LEVEL_TIERS:
            candidates.append(ExpiryCandidate(
                record_id_safe=record_id or f"ROW-{idx}",
                department=dept_label,
                signal_type=signal_type,
                expiry_date=str(parsed.loc[idx].date()),
                days_remaining=days,
                urgency_tier=tier,
                employee_id_raw=raw_id_display,
            ))

    return candidates, tier_counts, n_invalid, dept_counts, id_to_days


# ── Main API ──────────────────────────────────────────────────────────────────

def analyze_contract_expiry(df: pd.DataFrame) -> ContractExpiryResult:
    """
    Real contract/Iqama expiry analysis. Never raises — exceptions should
    be caught by the caller and surfaced via `unavailable_contract_expiry_result`.
    """
    if df is None or df.empty:
        return unavailable_contract_expiry_result("No data available for contract expiry analysis.")

    contract_col = _find_column(df, _CONTRACT_END_PATTERNS)
    iqama_col = _find_column(df, _IQAMA_EXPIRY_PATTERNS)
    dept_col = _find_column(df, _DEPARTMENT_PATTERNS)
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)

    columns_detected = {
        "contract_end_date": contract_col is not None,
        "iqama_or_visa_expiry": iqama_col is not None,
        "department": dept_col is not None,
    }

    if contract_col is None and iqama_col is None:
        return unavailable_contract_expiry_result(
            "No contract-end-date or Iqama/visa-expiry column detected. This is the "
            "expected result for most HR exports in this session, none of which track "
            "contract or residency-permit expiry dates.",
            columns_detected,
        )

    dept_keys: Optional[pd.Series] = None
    dept_labels: dict[str, str] = {}
    dept_norm_notes: list[str] = []
    if dept_col is not None:
        norm_result = normalize_department_series(df[dept_col].astype(str))
        dept_keys = pd.Series(norm_result.normalized_keys.values, index=df.index)
        dept_labels = norm_result.display_labels
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

    as_of = pd.Timestamp(datetime.now(timezone.utc).date())
    date_quality_warnings: list[str] = []
    all_candidates: list[ExpiryCandidate] = []
    dept_breakdown: list[DepartmentExpiryBreakdown] = []
    contract_tier_counts: dict[str, int] = {t: 0 for t in _TIER_ORDER}
    iqama_tier_counts: dict[str, int] = {t: 0 for t in _TIER_ORDER}
    n_contract_valid = 0
    n_iqama_valid = 0
    n_invalid_total = 0

    if contract_col is not None:
        cands, tiers, n_invalid, dept_counts, _ = _parse_signal(
            df, contract_col, id_col, dept_keys, dept_labels, "contract", as_of,
        )
        all_candidates.extend(cands)
        contract_tier_counts = tiers
        n_contract_valid = sum(tiers.values())
        n_invalid_total += n_invalid
        if n_invalid > 0:
            date_quality_warnings.append(
                f"{n_invalid} row(s) had an unparseable contract-end-date value — "
                "excluded from contract expiry tiering rather than guessed."
            )
        for dept, counts in dept_counts.items():
            dept_breakdown.append(DepartmentExpiryBreakdown(department=dept, signal_type="contract", **counts))

    if iqama_col is not None:
        cands, tiers, n_invalid, dept_counts, _ = _parse_signal(
            df, iqama_col, id_col, dept_keys, dept_labels, "iqama", as_of,
        )
        all_candidates.extend(cands)
        iqama_tier_counts = tiers
        n_iqama_valid = sum(tiers.values())
        n_invalid_total += n_invalid
        if n_invalid > 0:
            date_quality_warnings.append(
                f"{n_invalid} row(s) had an unparseable Iqama/visa-expiry value — "
                "excluded from Iqama expiry tiering rather than guessed."
            )
        for dept, counts in dept_counts.items():
            dept_breakdown.append(DepartmentExpiryBreakdown(department=dept, signal_type="iqama", **counts))

    if n_contract_valid == 0 and n_iqama_valid == 0:
        return unavailable_contract_expiry_result(
            "A contract-end-date or Iqama/visa-expiry column was detected, but every "
            "value was unparseable — no valid expiry date to analyze.",
            columns_detected,
        )

    # Sort candidates by urgency (overdue first, then soonest expiry).
    all_candidates.sort(key=lambda c: (_TIER_ORDER.index(c.urgency_tier), c.days_remaining))
    all_candidates = all_candidates[:_MAX_ROW_LEVEL_CANDIDATES]

    n_contract_urgent = sum(contract_tier_counts.get(t, 0) for t in ("overdue", "critical_0_30", "urgent_31_60"))
    n_iqama_urgent = sum(iqama_tier_counts.get(t, 0) for t in ("overdue", "critical_0_30", "urgent_31_60"))

    narrative_parts_en = []
    narrative_parts_ar = []
    if contract_col is not None:
        narrative_parts_en.append(
            f"{n_contract_valid} employee(s) have a parseable contract end date; "
            f"{n_contract_urgent} fall within 60 days (urgent or overdue)."
        )
        narrative_parts_ar.append(
            f"لدى {n_contract_valid} موظفاً تاريخ انتهاء عقد قابل للقراءة؛ "
            f"{n_contract_urgent} منهم ضمن 60 يوماً (عاجل أو متأخر)."
        )
    if iqama_col is not None:
        narrative_parts_en.append(
            f"{n_iqama_valid} employee(s) have a parseable Iqama/visa expiry date; "
            f"{n_iqama_urgent} fall within 60 days (urgent or overdue)."
        )
        narrative_parts_ar.append(
            f"لدى {n_iqama_valid} موظفاً تاريخ انتهاء إقامة/تأشيرة قابل للقراءة؛ "
            f"{n_iqama_urgent} منهم ضمن 60 يوماً (عاجل أو متأخر)."
        )

    return ContractExpiryResult(
        available=True,
        reason=None,
        columns_detected=columns_detected,
        contract_end_column=contract_col,
        iqama_expiry_column=iqama_col,
        n_employees_total=len(df),
        n_contract_records_valid=n_contract_valid,
        n_iqama_records_valid=n_iqama_valid,
        n_invalid_dates_excluded=n_invalid_total,
        date_quality_warnings=date_quality_warnings,
        contract_tier_counts=contract_tier_counts,
        iqama_tier_counts=iqama_tier_counts,
        candidates=all_candidates,
        department_breakdown=dept_breakdown,
        department_normalization_notes=dept_norm_notes,
        narrative_en=" ".join(narrative_parts_en),
        narrative_ar=" ".join(narrative_parts_ar),
        contract_expiry_confidence=CONTRACT_EXPIRY_CONFIDENCE,
        disclaimer_en=CONTRACT_EXPIRY_DISCLAIMER_EN,
        disclaimer_ar=CONTRACT_EXPIRY_DISCLAIMER_AR,
        governance_note=(
            "Expiry tiers are computed only from real dates present in your upload; "
            "rows with an unparseable date are excluded and disclosed, never guessed."
        ),
        sources=_SOURCES,
        computed_at=_now(),
    )


# ── Cross-link join key (Phase 8 pattern — see module docstring) ───────────

def get_expiry_signals_by_record_id(df: pd.DataFrame) -> Optional[dict[str, dict[str, Any]]]:
    """
    Return {record_id_safe: {"contract_days_remaining": int|None,
    "iqama_days_remaining": int|None}} for every employee with a usable
    named ID and at least one valid expiry date, or None when no cross-link
    is possible (no real named ID column, or neither expiry column exists
    at all). Route layer only — this function is the sole join surface;
    `contract_expiry_engine.py` never imports `succession_readiness_engine.py`
    or `nitaqat_compliance_engine.py`, and neither imports this module.
    """
    if df is None or len(df) == 0:
        return None
    id_col = next((c for c in _ID_COLUMN_CANDIDATES if c in df.columns), None)
    if id_col is None:
        return None

    contract_col = _find_column(df, _CONTRACT_END_PATTERNS)
    iqama_col = _find_column(df, _IQAMA_EXPIRY_PATTERNS)
    if contract_col is None and iqama_col is None:
        return None

    as_of = pd.Timestamp(datetime.now(timezone.utc).date())
    contract_days: dict[str, int] = {}
    iqama_days: dict[str, int] = {}

    if contract_col is not None:
        _, _, _, _, contract_days = _parse_signal(df, contract_col, id_col, None, {}, "contract", as_of)
    if iqama_col is not None:
        _, _, _, _, iqama_days = _parse_signal(df, iqama_col, id_col, None, {}, "iqama", as_of)

    all_ids = set(contract_days) | set(iqama_days)
    if not all_ids:
        return None

    return {
        rid: {
            "contract_days_remaining": contract_days.get(rid),
            "iqama_days_remaining": iqama_days.get(rid),
        }
        for rid in all_ids
    }


# ── Serialization ─────────────────────────────────────────────────────────────

def _candidate_to_dict(c: ExpiryCandidate) -> dict[str, Any]:
    return {
        "record_id_safe": c.record_id_safe,
        "employee_id_raw": c.employee_id_raw,
        "department": c.department,
        "signal_type": c.signal_type,
        "expiry_date": c.expiry_date,
        "days_remaining": c.days_remaining,
        "urgency_tier": c.urgency_tier,
        "urgency_tier_label_en": _TIER_LABELS_EN[c.urgency_tier],
        "urgency_tier_label_ar": _TIER_LABELS_AR[c.urgency_tier],
    }


def _dept_breakdown_to_dict(d: DepartmentExpiryBreakdown) -> dict[str, Any]:
    return {
        "department": d.department,
        "signal_type": d.signal_type,
        "n_total": d.n_total,
        "n_overdue": d.n_overdue,
        "n_critical_0_30": d.n_critical_0_30,
        "n_urgent_31_60": d.n_urgent_31_60,
    }


def contract_expiry_to_dict(r: ContractExpiryResult) -> dict[str, Any]:
    return {
        "available": r.available,
        "reason": r.reason,
        "columns_detected": r.columns_detected,
        "contract_end_column": r.contract_end_column,
        "iqama_expiry_column": r.iqama_expiry_column,
        "n_employees_total": r.n_employees_total,
        "n_contract_records_valid": r.n_contract_records_valid,
        "n_iqama_records_valid": r.n_iqama_records_valid,
        "n_invalid_dates_excluded": r.n_invalid_dates_excluded,
        "date_quality_warnings": r.date_quality_warnings,
        "contract_tier_counts": r.contract_tier_counts,
        "iqama_tier_counts": r.iqama_tier_counts,
        "tier_labels_en": _TIER_LABELS_EN,
        "tier_labels_ar": _TIER_LABELS_AR,
        "candidates": [_candidate_to_dict(c) for c in r.candidates],
        "department_breakdown": [_dept_breakdown_to_dict(d) for d in r.department_breakdown],
        "department_normalization_notes": r.department_normalization_notes,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "contract_expiry_confidence": r.contract_expiry_confidence,
        "disclaimer_en": r.disclaimer_en,
        "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
