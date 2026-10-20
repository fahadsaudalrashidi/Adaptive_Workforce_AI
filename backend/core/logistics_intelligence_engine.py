"""
Logistics Intelligence — Phase 34 (Business Intelligence Suite, Module 5).

Shipment/delivery-level data — related to Procurement Intelligence's
delivery-performance item (Phase 33) but a genuinely different focus:
Procurement measures whether a SUPPLIER delivered INBOUND goods to this
platform's owner on time; Logistics measures this platform owner's own
OUTBOUND shipping performance to THEIR customers — carrier reliability,
shipping cost, and returns. Kept as a separate engine.

**On-time-performance sharing decision**: the actual on-time arithmetic
(group by an entity name, compare expected vs. actual date, compute a
percentage) is EXACTLY the same computation Procurement already built —
not just "similar," identical. Rather than duplicate it, both modules now
call the same extracted utility, `backend.core.delivery_performance_utils.
compute_on_time_performance()` (Phase 34 also refactored
`procurement_intelligence_engine.py` to use it — see that module's
docstring). Each module maps the shared, domain-agnostic output into its
own domain-specific result dataclass (`SupplierDeliveryItem` there,
`CarrierPerformanceItem`/route breakdown here) — the column detection,
PO-vs-shipment record building, and narrative framing are NOT shared
(genuinely different upload shapes and business meaning), only the
group-by-date-pair math itself.

**Returns theme extraction**: reuses the domain-agnostic TF-IDF/word-
frequency extraction machinery promoted to public functions in
`exit_interview_intelligence_engine.py` this same phase
(`extract_top_terms_tfidf`, `extract_top_terms_word_frequency`,
`scrub_pii`, `SKLEARN_AVAILABLE`, `MIN_DOCUMENT_FREQUENCY`,
`MIN_RESPONSES_FOR_AGGREGATE`) rather than re-implementing TF-IDF a second
time. Deliberately does NOT reuse that module's `THEME_KEYWORDS` /
`_classify_response()` — those encode HR attrition constructs (JD-R, COR,
Equity, Mobley, FFM) with zero semantic overlap with logistics return
reasons ("damaged in transit", "wrong item") — reusing them wholesale
would silently produce an empty/wrong result. A fresh, logistics-specific
theme dictionary is defined here instead, while the extraction mechanism
and the >=3-distinct-shipments suppression discipline are genuinely
shared.

**Delay analysis minimum-sample discipline**: a carrier or route is only
labeled a delay "concentration" (`is_concentration_flagged=True`) once it
has at least `_MIN_LATE_FOR_CONCENTRATION_FLAG` (3) late shipments — the
same disclosed-suppression floor used throughout this session
(pay_equity_engine.py, accounting_intelligence_engine.py,
procurement_intelligence_engine.py). Raw counts below the floor are still
shown (never hidden), just not editorialized as a "problem."

**Explicitly out of scope this phase** (see PHASE_34 report): delay
forecasting/prediction, supply-chain risk scoring beyond the carrier
performance composite, and route optimization — the last of these is a
genuinely different KIND of feature (a combinatorial/operations-research
optimization problem) from every reporting/analytics feature built in
this Business Intelligence suite so far, not a reporting gap to close
later with more data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.delivery_performance_utils import compute_on_time_performance
from backend.core.exit_interview_intelligence_engine import (
    MIN_DOCUMENT_FREQUENCY,
    MIN_RESPONSES_FOR_AGGREGATE,
    SKLEARN_AVAILABLE,
    extract_top_terms_tfidf,
    extract_top_terms_word_frequency,
    scrub_pii,
)

# ── Column detection (local-regex convention, fresh to this module) ────────

_SHIPMENT_ID_PATTERNS = re.compile(
    r"\b(shipment[_\s]?id|order[_\s]?id|tracking[_\s]?number|tracking[_\s]?id|"
    r"رقم[_\s]?الشحنة|رقم[_\s]?التتبع)\b", re.I,
)
_CARRIER_PATTERNS = re.compile(
    r"\b(carrier|shipping[_\s]?carrier|courier|shipper|"
    r"شركة[_\s]?الشحن|الناقل)\b", re.I,
)
_ROUTE_PATTERNS = re.compile(r"\b(route|lane|شحنة[_\s]?مسار|المسار)\b", re.I)
_ORIGIN_PATTERNS = re.compile(r"\b(origin|from[_\s]?city|source[_\s]?city|المنشأ)\b", re.I)
_DESTINATION_PATTERNS = re.compile(r"\b(destination|to[_\s]?city|dest[_\s]?city|الوجهة)\b", re.I)
_SHIP_DATE_PATTERNS = re.compile(
    r"\b(ship[_\s]?date|dispatch[_\s]?date|shipped[_\s]?date|order[_\s]?date|"
    r"تاريخ[_\s]?الشحن)\b", re.I,
)
_EXPECTED_DELIVERY_PATTERNS = re.compile(
    r"\b(expected[_\s]?delivery[_\s]?date|expected[_\s]?date|promised[_\s]?date|eta|"
    r"تاريخ[_\s]?التسليم[_\s]?المتوقع)\b", re.I,
)
_ACTUAL_DELIVERY_PATTERNS = re.compile(
    r"\b(actual[_\s]?delivery[_\s]?date|delivery[_\s]?date|received[_\s]?date|actual[_\s]?date|"
    r"تاريخ[_\s]?التسليم[_\s]?الفعلي|تاريخ[_\s]?الاستلام)\b", re.I,
)
_STATUS_PATTERNS = re.compile(r"\b(status|shipment[_\s]?status|الحالة)\b", re.I)
_COST_PATTERNS = re.compile(
    r"\b(shipping[_\s]?cost|freight[_\s]?cost|cost|shipping[_\s]?fee|"
    r"تكلفة[_\s]?الشحن|التكلفة)\b", re.I,
)
_RETURN_FLAG_PATTERNS = re.compile(r"\b(is[_\s]?return(ed)?|return[_\s]?flag|مرتجع)\b", re.I)
_RETURN_REASON_PATTERNS = re.compile(
    r"\b(return[_\s]?reason|reason[_\s]?for[_\s]?return|سبب[_\s]?الإرجاع|سبب[_\s]?الارجاع)\b", re.I,
)
_DELAY_REASON_PATTERNS = re.compile(
    r"\b(delay[_\s]?reason|delay[_\s]?cause|reason[_\s]?for[_\s]?delay|سبب[_\s]?التأخير)\b", re.I,
)

_DELIVERED_TOKENS = frozenset({"delivered", "complete", "completed", "fulfilled", "تم التسليم", "مكتمل"})
_IN_TRANSIT_TOKENS = frozenset({"in transit", "intransit", "shipped", "pending", "processing", "قيد الشحن", "قيد النقل"})
_DELAYED_TOKENS = frozenset({"delayed", "late", "overdue", "متأخر"})
_RETURNED_TOKENS = frozenset({"returned", "return", "rejected", "مرتجع"})

_MIN_LATE_FOR_CONCENTRATION_FLAG = 3
_MIN_PERIODS_FOR_COST_TREND = 2

IS_VALIDATED_INSTRUMENT = False
CARRIER_SCORE_CONFIDENCE = "constructed_heuristic_not_validated"
CARRIER_SCORE_DISCLAIMER_EN = (
    "Carrier performance scores are this platform's own CONSTRUCTED HEURISTIC combining real "
    "on-time-delivery percentage and relative shipping cost — NOT a validated, peer-reviewed, or "
    "industry-benchmarked carrier rating. The 50/50 component weighting is an illustrative "
    "default. Qualified logistics review is required before any carrier sourcing decision based "
    "on this score."
)
CARRIER_SCORE_DISCLAIMER_AR = (
    "درجات أداء شركات الشحن هي معيار داخلي مُركّب من تصميم هذه المنصة، يجمع نسبة التسليم في "
    "الموعد والتكلفة النسبية — وليست تقييماً معتمداً أو معيارياً للصناعة. تلزم مراجعة متخصصي "
    "اللوجستيات قبل أي قرار يُبنى على هذه الدرجة."
)
LOGISTICS_CONFIDENCE = "derived_from_upload_planning_aid_not_certified"
LOGISTICS_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded shipment data — a computational "
    "planning aid, not an audited logistics report."
)
LOGISTICS_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات الشحنات المُحمّلة — أداة تخطيط حسابية مساعدة، وليست "
    "تقريراً لوجستياً مُدقَّقاً."
)
_SOURCES = [
    "On-time-delivery arithmetic is shared verbatim with procurement_intelligence_engine.py via "
    "backend/core/delivery_performance_utils.py's compute_on_time_performance() — computed once, "
    "not duplicated.",
    "Carrier performance scoring is a constructed heuristic (see disclaimer), not a validated "
    "instrument — same framing as succession_readiness_engine.py's readiness score and "
    "procurement_intelligence_engine.py's supplier score.",
    "Delay concentration flags require at least 3 late shipments for a carrier/route before "
    "being labeled a concentration — the same disclosed-suppression discipline used throughout "
    "this session's statistical modules.",
    "Return-reason theme extraction reuses exit_interview_intelligence_engine.py's TF-IDF/word-"
    "frequency machinery and >=3-distinct-shipments suppression threshold — a fresh, logistics-"
    "specific theme dictionary, not the HR attrition construct dictionary.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "shipment_id": "Shipment/order ID (optional)",
    "carrier": "Carrier (required for carrier-level views)",
    "route": "Route / origin-destination (optional)",
    "ship_date": "Ship date (required for cost-trend view)",
    "expected_delivery_date": "Expected delivery date (required for on-time/delay views)",
    "actual_delivery_date": "Actual delivery date (required for on-time/delay views)",
    "status": "Status (required for the shipment status overview)",
    "cost": "Shipping cost (required for cost views)",
    "return_reason": "Return reason — free text (optional, enables returns theme analysis)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "shipment_id": "رقم الشحنة/الطلب (اختياري)",
    "carrier": "شركة الشحن (مطلوبة لعروض مستوى الناقل)",
    "route": "المسار / المنشأ-الوجهة (اختياري)",
    "ship_date": "تاريخ الشحن (مطلوب لعرض اتجاه التكلفة)",
    "expected_delivery_date": "تاريخ التسليم المتوقع (مطلوب لعروض الالتزام والتأخير)",
    "actual_delivery_date": "تاريخ التسليم الفعلي (مطلوب لعروض الالتزام والتأخير)",
    "status": "الحالة (مطلوبة لنظرة عامة على حالة الشحنات)",
    "cost": "تكلفة الشحن (مطلوبة لعروض التكلفة)",
    "return_reason": "سبب الإرجاع — نص حر (اختياري)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern, exclude: frozenset = frozenset()) -> Optional[str]:
    for col in df.columns:
        if col in exclude:
            continue
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


def _numeric_or_none(raw: object) -> Optional[float]:
    if _is_missing_value(raw):
        return None
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        return None
    return float(val)


def _classify_status(raw: object) -> Optional[str]:
    """Returns 'delivered'|'in_transit'|'delayed'|'returned'|None — never guessed."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    for tokens, label in (
        (_DELIVERED_TOKENS, "delivered"), (_RETURNED_TOKENS, "returned"),
        (_DELAYED_TOKENS, "delayed"), (_IN_TRANSIT_TOKENS, "in_transit"),
    ):
        if key in tokens:
            return label
    for tokens, label in (
        (_RETURNED_TOKENS, "returned"), (_DELAYED_TOKENS, "delayed"),
        (_DELIVERED_TOKENS, "delivered"), (_IN_TRANSIT_TOKENS, "in_transit"),
    ):
        if any(t in key for t in tokens):
            return label
    return None


def _detect_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    shipment_id_col = _find_column(df, _SHIPMENT_ID_PATTERNS)
    carrier_col = _find_column(df, _CARRIER_PATTERNS)
    route_col = _find_column(df, _ROUTE_PATTERNS)
    origin_col = destination_col = None
    if route_col is None:
        origin_col = _find_column(df, _ORIGIN_PATTERNS)
        destination_col = _find_column(df, _DESTINATION_PATTERNS)
    ship_date_col = _find_column(df, _SHIP_DATE_PATTERNS)
    expected_col = _find_column(df, _EXPECTED_DELIVERY_PATTERNS)
    actual_exclude = {expected_col} if expected_col else set()
    actual_col = _find_column(df, _ACTUAL_DELIVERY_PATTERNS, exclude=frozenset(actual_exclude))
    status_col = _find_column(df, _STATUS_PATTERNS)
    cost_col = _find_column(df, _COST_PATTERNS)
    return_flag_col = _find_column(df, _RETURN_FLAG_PATTERNS)
    return_reason_col = _find_column(df, _RETURN_REASON_PATTERNS)
    delay_reason_col = _find_column(df, _DELAY_REASON_PATTERNS)
    return {
        "shipment_id": shipment_id_col, "carrier": carrier_col, "route": route_col,
        "origin": origin_col, "destination": destination_col, "ship_date": ship_date_col,
        "expected_delivery_date": expected_col, "actual_delivery_date": actual_col,
        "status": status_col, "cost": cost_col, "return_flag": return_flag_col,
        "return_reason": return_reason_col, "delay_reason": delay_reason_col,
    }


@dataclass(frozen=True)
class _Shipment:
    shipment_id: Optional[str]
    carrier: Optional[str]
    route: Optional[str]
    ship_date: Optional[pd.Timestamp]
    expected_delivery: Optional[pd.Timestamp]
    actual_delivery: Optional[pd.Timestamp]
    status: Optional[str]
    cost: Optional[float]
    is_returned: bool
    return_reason: Optional[str]


def _build_shipments(df: pd.DataFrame, cols: dict[str, Optional[str]]) -> list[_Shipment]:
    shipments = []
    for idx in df.index:
        sid_col = cols["shipment_id"]
        shipment_id = str(df.at[idx, sid_col]).strip() if sid_col and not _is_missing_value(df.at[idx, sid_col]) else None
        carrier = str(df.at[idx, cols["carrier"]]).strip() if cols["carrier"] and not _is_missing_value(df.at[idx, cols["carrier"]]) else None

        route = None
        if cols["route"]:
            route = str(df.at[idx, cols["route"]]).strip() if not _is_missing_value(df.at[idx, cols["route"]]) else None
        elif cols["origin"] and cols["destination"]:
            o = df.at[idx, cols["origin"]]
            dst = df.at[idx, cols["destination"]]
            if not _is_missing_value(o) and not _is_missing_value(dst):
                route = f"{str(o).strip()} → {str(dst).strip()}"

        ship_date = None
        if cols["ship_date"]:
            p = pd.to_datetime(df.at[idx, cols["ship_date"]], errors="coerce")
            ship_date = p if pd.notna(p) else None
        expected = None
        if cols["expected_delivery_date"]:
            p = pd.to_datetime(df.at[idx, cols["expected_delivery_date"]], errors="coerce")
            expected = p if pd.notna(p) else None
        actual = None
        if cols["actual_delivery_date"]:
            p = pd.to_datetime(df.at[idx, cols["actual_delivery_date"]], errors="coerce")
            actual = p if pd.notna(p) else None

        status = _classify_status(df.at[idx, cols["status"]]) if cols["status"] else None
        cost = _numeric_or_none(df.at[idx, cols["cost"]]) if cols["cost"] else None

        return_flag = False
        if cols["return_flag"]:
            raw = df.at[idx, cols["return_flag"]]
            if not _is_missing_value(raw):
                return_flag = str(raw).strip().lower() in {"true", "yes", "1", "y"}
        is_returned = (status == "returned") or return_flag

        return_reason = None
        if cols["return_reason"] and not _is_missing_value(df.at[idx, cols["return_reason"]]):
            return_reason = str(df.at[idx, cols["return_reason"]])

        if carrier is None and route is None and status is None and cost is None:
            continue

        shipments.append(_Shipment(
            shipment_id=shipment_id, carrier=carrier, route=route, ship_date=ship_date,
            expected_delivery=expected, actual_delivery=actual, status=status, cost=cost,
            is_returned=is_returned, return_reason=return_reason,
        ))
    return shipments


# ── 1. Shipment Volume & Status Overview ────────────────────────────────────

@dataclass(frozen=True)
class StatusCount:
    status: str
    n: int
    pct: float


@dataclass(frozen=True)
class ShipmentStatusResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_shipments_total: int
    n_unclassified: int
    status_counts: list[StatusCount]
    narrative_en: str
    narrative_ar: str


def unavailable_status_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ShipmentStatusResult:
    return ShipmentStatusResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        n_shipments_total=0, n_unclassified=0, status_counts=[],
        narrative_en="Shipment status overview not available for this dataset.",
        narrative_ar="نظرة عامة على حالة الشحنات غير متاحة لهذه البيانات.",
    )


def _status_overview_from_shipments(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> ShipmentStatusResult:
    if not columns_detected.get("status"):
        return unavailable_status_result(
            "No status column was detected — shipment volume/status counts require a status "
            "column with classifiable values (Delivered/In Transit/Delayed/Returned).",
            columns_detected,
        )
    n_total = len(shipments)
    counts: dict[str, int] = {}
    n_unclassified = 0
    for s in shipments:
        if s.status is None:
            n_unclassified += 1
        else:
            counts[s.status] = counts.get(s.status, 0) + 1
    status_counts = [
        StatusCount(status=st, n=n, pct=round(100.0 * n / n_total, 1) if n_total else 0.0)
        for st, n in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
    narrative_en = f"{n_total} shipment(s) total. " + ", ".join(f"{c.n} {c.status}" for c in status_counts) + "."
    narrative_ar = f"{n_total} شحنة إجمالاً."
    if n_unclassified:
        narrative_en += f" {n_unclassified} shipment(s) had an unclassifiable status value."
        narrative_ar += f" تعذّر تصنيف حالة {n_unclassified} شحنة."

    return ShipmentStatusResult(
        available=True, reason=None, columns_detected=columns_detected,
        n_shipments_total=n_total, n_unclassified=n_unclassified, status_counts=status_counts,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 2. Delivery Time / On-Time Performance (overall) ────────────────────────

@dataclass(frozen=True)
class DeliveryTimeResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_with_complete_dates: int
    n_on_time: int
    on_time_pct: float
    avg_delivery_days: Optional[float]
    narrative_en: str
    narrative_ar: str


def unavailable_delivery_time_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> DeliveryTimeResult:
    return DeliveryTimeResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        n_with_complete_dates=0, n_on_time=0, on_time_pct=0.0, avg_delivery_days=None,
        narrative_en="Delivery time / on-time performance not available for this dataset.",
        narrative_ar="أداء وقت التسليم غير متاح لهذه البيانات.",
    )


def _delivery_time_from_shipments(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> DeliveryTimeResult:
    if not (columns_detected.get("expected_delivery_date") and columns_detected.get("actual_delivery_date")):
        return unavailable_delivery_time_result(
            "Delivery time / on-time performance requires both an expected-delivery-date and an "
            "actual-delivery-date column.", columns_detected,
        )
    complete = [s for s in shipments if s.expected_delivery is not None and s.actual_delivery is not None]
    if not complete:
        return unavailable_delivery_time_result(
            "Delivery-date columns were detected, but no shipment had both a valid expected and "
            "actual delivery date.", columns_detected,
        )
    n_on_time = sum(1 for s in complete if s.actual_delivery <= s.expected_delivery)
    on_time_pct = round(100.0 * n_on_time / len(complete), 1)

    with_ship_date = [s for s in complete if s.ship_date is not None]
    avg_delivery_days = (
        round(sum((s.actual_delivery - s.ship_date).days for s in with_ship_date) / len(with_ship_date), 1)
        if with_ship_date else None
    )

    narrative_en = f"{n_on_time} of {len(complete)} shipment(s) with complete delivery-date data were on time ({on_time_pct}%)."
    narrative_ar = f"{n_on_time} من {len(complete)} شحنة وصلت في الموعد ({on_time_pct}%)."
    if avg_delivery_days is not None:
        narrative_en += f" Average delivery time: {avg_delivery_days} day(s) from ship date."
        narrative_ar += f" متوسط وقت التسليم: {avg_delivery_days} يوماً."

    return DeliveryTimeResult(
        available=True, reason=None, columns_detected=columns_detected,
        n_with_complete_dates=len(complete), n_on_time=n_on_time, on_time_pct=on_time_pct,
        avg_delivery_days=avg_delivery_days, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 3. Shipping Cost Analysis ────────────────────────────────────────────────

@dataclass(frozen=True)
class CarrierCost:
    carrier: str
    total_cost: float
    avg_cost: float
    n_shipments: int


@dataclass(frozen=True)
class CostPeriodVariance:
    period: str
    prior_period: str
    total_cost_prior: float
    total_cost_current: float
    cost_variance: float
    cost_variance_pct: Optional[float]


@dataclass(frozen=True)
class ShippingCostResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    total_cost: float
    avg_cost_per_shipment: float
    n_shipments_costed: int
    by_carrier: list[CarrierCost]
    period_variances: list[CostPeriodVariance]
    min_periods_required: int
    narrative_en: str
    narrative_ar: str


def unavailable_cost_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ShippingCostResult:
    return ShippingCostResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        total_cost=0.0, avg_cost_per_shipment=0.0, n_shipments_costed=0, by_carrier=[],
        period_variances=[], min_periods_required=_MIN_PERIODS_FOR_COST_TREND,
        narrative_en="Shipping cost analysis not available for this dataset.",
        narrative_ar="تحليل تكلفة الشحن غير متاح لهذه البيانات.",
    )


def _cost_from_shipments(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> ShippingCostResult:
    costed = [s for s in shipments if s.cost is not None]
    if not costed:
        return unavailable_cost_result(
            "Shipping cost analysis requires a cost column.", columns_detected,
        )
    total_cost = sum(s.cost for s in costed)
    avg_cost = total_cost / len(costed)

    by_carrier_map: dict[str, list[float]] = {}
    for s in costed:
        if s.carrier:
            by_carrier_map.setdefault(s.carrier, []).append(s.cost)
    by_carrier = [
        CarrierCost(carrier=c, total_cost=round(sum(v), 2), avg_cost=round(sum(v) / len(v), 2), n_shipments=len(v))
        for c, v in by_carrier_map.items()
    ]
    by_carrier.sort(key=lambda c: -c.total_cost)

    period_variances: list[CostPeriodVariance] = []
    dated_costed = [s for s in costed if s.ship_date is not None]
    if dated_costed:
        period_map: dict[str, float] = {}
        for s in dated_costed:
            period = s.ship_date.strftime("%Y-%m")
            period_map[period] = period_map.get(period, 0.0) + s.cost
        sorted_periods = sorted(period_map.keys())
        if len(sorted_periods) >= _MIN_PERIODS_FOR_COST_TREND:
            for i in range(1, len(sorted_periods)):
                prior, curr = sorted_periods[i - 1], sorted_periods[i]
                prior_total, curr_total = period_map[prior], period_map[curr]
                variance = round(curr_total - prior_total, 2)
                variance_pct = round(100.0 * variance / prior_total, 1) if prior_total else None
                period_variances.append(CostPeriodVariance(
                    period=curr, prior_period=prior, total_cost_prior=round(prior_total, 2),
                    total_cost_current=round(curr_total, 2), cost_variance=variance, cost_variance_pct=variance_pct,
                ))
            period_variances.sort(key=lambda v: abs(v.cost_variance_pct or 0), reverse=True)

    narrative_en = f"Total shipping cost SAR {total_cost:,.2f} across {len(costed)} shipment(s), average SAR {avg_cost:,.2f} per shipment."
    narrative_ar = f"إجمالي تكلفة الشحن {total_cost:,.2f} ريال عبر {len(costed)} شحنة."

    return ShippingCostResult(
        available=True, reason=None, columns_detected=columns_detected,
        total_cost=round(total_cost, 2), avg_cost_per_shipment=round(avg_cost, 2),
        n_shipments_costed=len(costed), by_carrier=by_carrier, period_variances=period_variances,
        min_periods_required=_MIN_PERIODS_FOR_COST_TREND, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 4. Carrier / Route Performance Comparison (constructed heuristic) ──────

@dataclass(frozen=True)
class CarrierPerformanceItem:
    carrier: str
    delivery_component: Optional[float]
    cost_component: Optional[float]
    composite_score: Optional[float]
    components_used: list[str]
    avg_cost: Optional[float]
    n_shipments: int


@dataclass(frozen=True)
class RoutePerformanceItem:
    route: str
    on_time_pct: Optional[float]
    avg_cost: Optional[float]
    n_shipments: int


@dataclass(frozen=True)
class CarrierRoutePerformanceResult:
    available: bool
    reason: Optional[str]
    is_validated_instrument: bool
    confidence: str
    n_carriers_excluded_no_data: int
    carrier_items: list[CarrierPerformanceItem]
    route_items: list[RoutePerformanceItem]
    narrative_en: str
    narrative_ar: str
    disclaimer_en: str
    disclaimer_ar: str


def unavailable_carrier_route_result(reason: str) -> CarrierRoutePerformanceResult:
    return CarrierRoutePerformanceResult(
        available=False, reason=reason, is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        confidence=CARRIER_SCORE_CONFIDENCE, n_carriers_excluded_no_data=0, carrier_items=[], route_items=[],
        narrative_en="Carrier/route performance comparison not available for this dataset.",
        narrative_ar="مقارنة أداء شركات الشحن/المسارات غير متاحة لهذه البيانات.",
        disclaimer_en=CARRIER_SCORE_DISCLAIMER_EN, disclaimer_ar=CARRIER_SCORE_DISCLAIMER_AR,
    )


def _carrier_route_performance(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> CarrierRoutePerformanceResult:
    if not columns_detected.get("carrier"):
        return unavailable_carrier_route_result(
            "Carrier/route performance requires a carrier column.",
        )
    all_carriers = {s.carrier for s in shipments if s.carrier}
    if not all_carriers:
        return unavailable_carrier_route_result("No shipment had a valid carrier value.")

    on_time = compute_on_time_performance([(s.carrier, s.expected_delivery, s.actual_delivery) for s in shipments if s.carrier])
    on_time_by_carrier = {i.group: i.on_time_pct for i in on_time.items} if on_time.available else {}

    cost_by_carrier: dict[str, list[float]] = {}
    for s in shipments:
        if s.carrier and s.cost is not None:
            cost_by_carrier.setdefault(s.carrier, []).append(s.cost)
    avg_cost_by_carrier = {c: sum(v) / len(v) for c, v in cost_by_carrier.items()}
    min_avg_cost = min(avg_cost_by_carrier.values()) if avg_cost_by_carrier else None

    n_shipments_by_carrier: dict[str, int] = {}
    for s in shipments:
        if s.carrier:
            n_shipments_by_carrier[s.carrier] = n_shipments_by_carrier.get(s.carrier, 0) + 1

    carrier_items = []
    n_excluded = 0
    for carrier in all_carriers:
        delivery_component = on_time_by_carrier.get(carrier)
        cost_component = None
        avg_cost = avg_cost_by_carrier.get(carrier)
        if avg_cost is not None and min_avg_cost is not None and min_avg_cost > 0:
            cost_component = max(0.0, min(100.0, 100.0 - 100.0 * (avg_cost - min_avg_cost) / min_avg_cost))
        components_used = []
        if delivery_component is not None:
            components_used.append("delivery_on_time_pct")
        if cost_component is not None:
            components_used.append("relative_cost")
        if not components_used:
            n_excluded += 1
            continue
        if delivery_component is not None and cost_component is not None:
            composite = round(0.5 * delivery_component + 0.5 * cost_component, 1)
        elif delivery_component is not None:
            composite = round(delivery_component, 1)
        else:
            composite = round(cost_component, 1)
        carrier_items.append(CarrierPerformanceItem(
            carrier=carrier, delivery_component=(round(delivery_component, 1) if delivery_component is not None else None),
            cost_component=(round(cost_component, 1) if cost_component is not None else None),
            composite_score=composite, components_used=components_used,
            avg_cost=(round(avg_cost, 2) if avg_cost is not None else None),
            n_shipments=n_shipments_by_carrier.get(carrier, 0),
        ))
    carrier_items.sort(key=lambda i: -(i.composite_score or 0))

    if not carrier_items:
        return unavailable_carrier_route_result(
            "No carrier had at least one computable component (on-time % or relative cost).",
        )

    route_items = []
    routes = {s.route for s in shipments if s.route}
    if routes:
        on_time_route = compute_on_time_performance([(s.route, s.expected_delivery, s.actual_delivery) for s in shipments if s.route])
        on_time_by_route = {i.group: i.on_time_pct for i in on_time_route.items} if on_time_route.available else {}
        cost_by_route: dict[str, list[float]] = {}
        n_by_route: dict[str, int] = {}
        for s in shipments:
            if s.route:
                n_by_route[s.route] = n_by_route.get(s.route, 0) + 1
                if s.cost is not None:
                    cost_by_route.setdefault(s.route, []).append(s.cost)
        for route in routes:
            avg_cost_r = (sum(cost_by_route[route]) / len(cost_by_route[route])) if route in cost_by_route else None
            route_items.append(RoutePerformanceItem(
                route=route, on_time_pct=on_time_by_route.get(route),
                avg_cost=(round(avg_cost_r, 2) if avg_cost_r is not None else None),
                n_shipments=n_by_route.get(route, 0),
            ))
        route_items.sort(key=lambda r: (r.on_time_pct is None, r.on_time_pct or 0))

    narrative_en = f"{len(carrier_items)} carrier(s) scored using a constructed heuristic (on-time % and/or relative cost, 50/50 weighted when both available). {n_excluded} carrier(s) excluded — no computable component."
    narrative_ar = f"تم تقييم {len(carrier_items)} شركة شحن باستخدام معيار داخلي مُركّب."

    return CarrierRoutePerformanceResult(
        available=True, reason=None, is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        confidence=CARRIER_SCORE_CONFIDENCE, n_carriers_excluded_no_data=n_excluded,
        carrier_items=carrier_items, route_items=route_items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        disclaimer_en=CARRIER_SCORE_DISCLAIMER_EN, disclaimer_ar=CARRIER_SCORE_DISCLAIMER_AR,
    )


# ── 5. Delay Analysis ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class DelayGroupStat:
    group_type: str  # "carrier" | "route" | "carrier_route"
    group: str
    n_late: int
    avg_days_late: float
    is_concentration_flagged: bool


@dataclass(frozen=True)
class DelayAnalysisResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    min_late_for_flag: int
    n_late_total: int
    has_delay_cause_data: bool
    by_carrier: list[DelayGroupStat]
    by_route: list[DelayGroupStat]
    by_carrier_route: list[DelayGroupStat]
    narrative_en: str
    narrative_ar: str


def unavailable_delay_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> DelayAnalysisResult:
    return DelayAnalysisResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        min_late_for_flag=_MIN_LATE_FOR_CONCENTRATION_FLAG, n_late_total=0, has_delay_cause_data=False,
        by_carrier=[], by_route=[], by_carrier_route=[],
        narrative_en="Delay analysis not available for this dataset.",
        narrative_ar="تحليل التأخير غير متاح لهذه البيانات.",
    )


def _delay_group_stats(group_type: str, late: list[_Shipment], key_fn) -> list[DelayGroupStat]:
    by_group: dict[str, list[int]] = {}
    for s in late:
        key = key_fn(s)
        if key is None:
            continue
        days_late = (s.actual_delivery - s.expected_delivery).days
        by_group.setdefault(key, []).append(days_late)
    stats = [
        DelayGroupStat(
            group_type=group_type, group=g, n_late=len(days), avg_days_late=round(sum(days) / len(days), 1),
            is_concentration_flagged=len(days) >= _MIN_LATE_FOR_CONCENTRATION_FLAG,
        )
        for g, days in by_group.items()
    ]
    stats.sort(key=lambda s: -s.n_late)
    return stats


def _delay_analysis_from_shipments(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> DelayAnalysisResult:
    if not (columns_detected.get("expected_delivery_date") and columns_detected.get("actual_delivery_date")):
        return unavailable_delay_result(
            "Delay analysis requires both an expected-delivery-date and an actual-delivery-date "
            "column to compute real lateness.", columns_detected,
        )
    complete = [s for s in shipments if s.expected_delivery is not None and s.actual_delivery is not None]
    late = [s for s in complete if s.actual_delivery > s.expected_delivery]
    if not late:
        return DelayAnalysisResult(
            available=True, reason=None, columns_detected=columns_detected,
            min_late_for_flag=_MIN_LATE_FOR_CONCENTRATION_FLAG, n_late_total=0,
            has_delay_cause_data=columns_detected.get("delay_reason", False),
            by_carrier=[], by_route=[], by_carrier_route=[],
            narrative_en="No late shipments detected in this dataset.",
            narrative_ar="لم يتم رصد أي شحنات متأخرة في هذه البيانات.",
        )

    by_carrier = _delay_group_stats("carrier", late, lambda s: s.carrier)
    by_route = _delay_group_stats("route", late, lambda s: s.route)
    by_carrier_route = _delay_group_stats(
        "carrier_route", late, lambda s: f"{s.carrier} · {s.route}" if s.carrier and s.route else None,
    )

    flagged = [s for s in by_carrier_route if s.is_concentration_flagged]
    narrative_en = f"{len(late)} late shipment(s) out of {len(complete)} with complete delivery-date data."
    narrative_ar = f"{len(late)} شحنة متأخرة من أصل {len(complete)}."
    if flagged:
        top = flagged[0]
        narrative_en += f" Delay concentration flagged: {top.group} ({top.n_late} late shipments, avg {top.avg_days_late} days late) — meets the {_MIN_LATE_FOR_CONCENTRATION_FLAG}-shipment minimum-sample floor."
        narrative_ar += f" تم رصد تركّز تأخير في {top.group}."
    else:
        narrative_en += f" No carrier/route combination reached the {_MIN_LATE_FOR_CONCENTRATION_FLAG}-late-shipment floor for a concentration flag — too few data points to call any single carrier/route problematic yet."
        narrative_ar += " لا يوجد تركّز تأخير يتجاوز الحد الأدنى للعينة بعد."

    return DelayAnalysisResult(
        available=True, reason=None, columns_detected=columns_detected,
        min_late_for_flag=_MIN_LATE_FOR_CONCENTRATION_FLAG, n_late_total=len(late),
        has_delay_cause_data=columns_detected.get("delay_reason", False),
        by_carrier=by_carrier, by_route=by_route, by_carrier_route=by_carrier_route,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 6. Returns Analysis (reuses Exit Interview's TF-IDF machinery) ─────────

_RETURN_THEME_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "Damaged in Transit": {
        "direct": ["arrived damaged", "damaged in transit", "package was damaged", "damaged on arrival"],
        "proxy": ["broken", "crushed box", "damaged packaging", "packaging broken"],
    },
    "Wrong Item Shipped": {
        "direct": ["wrong item", "received wrong product", "incorrect item shipped", "wrong item shipped"],
        "proxy": ["wrong size", "wrong color", "not what i ordered", "incorrect product"],
    },
    "Defective Product": {
        "direct": ["defective", "doesn't work", "does not work", "stopped working", "product malfunction"],
        "proxy": ["poor quality", "faulty"],
    },
    "Late Delivery": {
        "direct": ["arrived too late", "delivery was late", "took too long to arrive"],
        "proxy": ["slow shipping", "delayed too long"],
    },
    "Customer Changed Mind": {
        "direct": ["no longer needed", "changed my mind", "ordered by mistake"],
        "proxy": ["don't need it", "duplicate order"],
    },
}


@dataclass(frozen=True)
class ReturnThemeFrequency:
    theme: str
    n_shipments_mentioned: int
    pct_of_reasons_provided: float


@dataclass(frozen=True)
class ReturnsAnalysisResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_shipments_total: int
    n_returned: int
    return_rate_pct: float
    n_reasons_provided: int
    min_mentions_for_theme: int
    theme_frequencies: list[ReturnThemeFrequency]
    top_terms: list[tuple[str, int]]
    term_extraction_method: str
    narrative_en: str
    narrative_ar: str
    governance_note: str


def unavailable_returns_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ReturnsAnalysisResult:
    return ReturnsAnalysisResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        n_shipments_total=0, n_returned=0, return_rate_pct=0.0, n_reasons_provided=0,
        min_mentions_for_theme=MIN_DOCUMENT_FREQUENCY, theme_frequencies=[], top_terms=[],
        term_extraction_method="unavailable",
        narrative_en="Returns analysis not available for this dataset.",
        narrative_ar="تحليل المرتجعات غير متاح لهذه البيانات.",
        governance_note="No raw return-reason text is ever returned, logged, or exported; only aggregate counts.",
    )


def _classify_return_reason(scrubbed_text: str) -> Optional[str]:
    lowered = scrubbed_text.lower()
    for theme, spec in _RETURN_THEME_KEYWORDS.items():
        if any(p in lowered for p in spec["direct"]):
            return theme
    for theme, spec in _RETURN_THEME_KEYWORDS.items():
        if any(p in lowered for p in spec["proxy"]):
            return theme
    return None


def _returns_from_shipments(shipments: list[_Shipment], columns_detected: dict[str, bool]) -> ReturnsAnalysisResult:
    if not (columns_detected.get("status") or columns_detected.get("return_flag")):
        return unavailable_returns_result(
            "Returns analysis requires a status column (with a 'Returned' value) or a dedicated "
            "return-flag column.", columns_detected,
        )
    n_total = len(shipments)
    returned = [s for s in shipments if s.is_returned]
    n_returned = len(returned)
    return_rate = round(100.0 * n_returned / n_total, 2) if n_total else 0.0

    reasons_raw = [s.return_reason for s in returned if s.return_reason]
    n_reasons = len(reasons_raw)

    if n_reasons < MIN_RESPONSES_FOR_AGGREGATE:
        return ReturnsAnalysisResult(
            available=True, reason=None, columns_detected=columns_detected,
            n_shipments_total=n_total, n_returned=n_returned, return_rate_pct=return_rate,
            n_reasons_provided=n_reasons, min_mentions_for_theme=MIN_DOCUMENT_FREQUENCY,
            theme_frequencies=[], top_terms=[], term_extraction_method="unavailable",
            narrative_en=(
                f"{n_returned} of {n_total} shipment(s) returned ({return_rate}%). Only {n_reasons} "
                f"had return-reason text — at least {MIN_RESPONSES_FOR_AGGREGATE} are required "
                "before theme analysis can run."
            ),
            narrative_ar=f"{n_returned} من {n_total} شحنة مرتجعة ({return_rate}%). عدد أسباب الإرجاع المتوفرة غير كافٍ لتحليل المواضيع.",
            governance_note="No raw return-reason text is ever returned, logged, or exported; only aggregate counts.",
        )

    cleaned = [scrub_pii(str(r).strip()) for r in reasons_raw]

    theme_hits: dict[str, int] = {t: 0 for t in _RETURN_THEME_KEYWORDS}
    for text in cleaned:
        theme = _classify_return_reason(text)
        if theme:
            theme_hits[theme] += 1

    theme_frequencies = [
        ReturnThemeFrequency(theme=t, n_shipments_mentioned=n, pct_of_reasons_provided=round(100.0 * n / n_reasons, 1))
        for t, n in theme_hits.items() if n >= MIN_DOCUMENT_FREQUENCY
    ]
    theme_frequencies.sort(key=lambda t: -t.n_shipments_mentioned)

    if SKLEARN_AVAILABLE:
        top_terms = extract_top_terms_tfidf(cleaned)
        method = "tfidf"
    else:
        top_terms = extract_top_terms_word_frequency(cleaned)
        method = "word_frequency"

    narrative_en = f"{n_returned} of {n_total} shipment(s) returned ({return_rate}%). {n_reasons} had return-reason text; "
    if theme_frequencies:
        top = theme_frequencies[0]
        narrative_en += f"most common theme: '{top.theme}' ({top.n_shipments_mentioned} shipments, {top.pct_of_reasons_provided}%)."
    else:
        narrative_en += f"no theme was mentioned by at least {MIN_DOCUMENT_FREQUENCY} distinct shipments."
    narrative_ar = f"{n_returned} من {n_total} شحنة مرتجعة ({return_rate}%)."

    return ReturnsAnalysisResult(
        available=True, reason=None, columns_detected=columns_detected,
        n_shipments_total=n_total, n_returned=n_returned, return_rate_pct=return_rate,
        n_reasons_provided=n_reasons, min_mentions_for_theme=MIN_DOCUMENT_FREQUENCY,
        theme_frequencies=theme_frequencies, top_terms=top_terms, term_extraction_method=method,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        governance_note=(
            "Themes are derived from a predefined, auditable logistics-specific keyword set — not "
            "a generative model. No raw return-reason text is ever returned, logged, or exported; "
            f"only aggregate counts. Themes/terms mentioned by fewer than {MIN_DOCUMENT_FREQUENCY} "
            "distinct shipments are suppressed."
        ),
    )


# ── Top-level bundle ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LogisticsIntelligenceResult:
    shipment_status: ShipmentStatusResult
    delivery_time: DeliveryTimeResult
    shipping_cost: ShippingCostResult
    carrier_route_performance: CarrierRoutePerformanceResult
    delay_analysis: DelayAnalysisResult
    returns_analysis: ReturnsAnalysisResult
    disclaimer_en: str
    disclaimer_ar: str
    confidence: str
    sources: list[str]
    computed_at: str


def _all_unavailable(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> LogisticsIntelligenceResult:
    return LogisticsIntelligenceResult(
        shipment_status=unavailable_status_result(reason, columns_detected),
        delivery_time=unavailable_delivery_time_result(reason, columns_detected),
        shipping_cost=unavailable_cost_result(reason, columns_detected),
        carrier_route_performance=unavailable_carrier_route_result(reason),
        delay_analysis=unavailable_delay_result(reason, columns_detected),
        returns_analysis=unavailable_returns_result(reason, columns_detected),
        disclaimer_en=LOGISTICS_DISCLAIMER_EN, disclaimer_ar=LOGISTICS_DISCLAIMER_AR,
        confidence=LOGISTICS_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


def analyze_logistics_intelligence(df: pd.DataFrame) -> LogisticsIntelligenceResult:
    """Never raises. Detects columns once, builds per-shipment records once,
    then feeds all 6 items from that shared computation."""
    if df is None or df.empty:
        return _all_unavailable("No data available for logistics intelligence analysis.")

    try:
        cols = _detect_columns(df)
        columns_detected = {
            "shipment_id": cols["shipment_id"] is not None, "carrier": cols["carrier"] is not None,
            "route": (cols["route"] is not None) or (cols["origin"] is not None and cols["destination"] is not None),
            "ship_date": cols["ship_date"] is not None,
            "expected_delivery_date": cols["expected_delivery_date"] is not None,
            "actual_delivery_date": cols["actual_delivery_date"] is not None,
            "status": cols["status"] is not None, "cost": cols["cost"] is not None,
            "return_flag": cols["return_flag"] is not None, "return_reason": cols["return_reason"] is not None,
            "delay_reason": cols["delay_reason"] is not None,
        }
        if not any([columns_detected["carrier"], columns_detected["status"], columns_detected["cost"],
                    columns_detected["expected_delivery_date"]]):
            return _all_unavailable(
                "No shipment-shaped columns detected (carrier, status, cost, or delivery dates) — "
                "this does not look like a shipment/logistics dataset.", columns_detected,
            )

        shipments = _build_shipments(df, cols)
        if not shipments:
            return _all_unavailable(
                "Shipment-shaped columns were detected, but no row had a usable shipment record.",
                columns_detected,
            )

        shipment_status = _status_overview_from_shipments(shipments, columns_detected)
        delivery_time = _delivery_time_from_shipments(shipments, columns_detected)
        shipping_cost = _cost_from_shipments(shipments, columns_detected)
        carrier_route_performance = _carrier_route_performance(shipments, columns_detected)
        delay_analysis = _delay_analysis_from_shipments(shipments, columns_detected)
        returns_analysis = _returns_from_shipments(shipments, columns_detected)
    except Exception as exc:
        return _all_unavailable(f"Logistics intelligence analysis encountered an error: {exc}")

    return LogisticsIntelligenceResult(
        shipment_status=shipment_status, delivery_time=delivery_time, shipping_cost=shipping_cost,
        carrier_route_performance=carrier_route_performance, delay_analysis=delay_analysis,
        returns_analysis=returns_analysis,
        disclaimer_en=LOGISTICS_DISCLAIMER_EN, disclaimer_ar=LOGISTICS_DISCLAIMER_AR,
        confidence=LOGISTICS_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _status_to_dict(r: ShipmentStatusResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "n_shipments_total": r.n_shipments_total, "n_unclassified": r.n_unclassified,
        "status_counts": [{"status": c.status, "n": c.n, "pct": c.pct} for c in r.status_counts],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _delivery_time_to_dict(r: DeliveryTimeResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "n_with_complete_dates": r.n_with_complete_dates, "n_on_time": r.n_on_time,
        "on_time_pct": r.on_time_pct, "avg_delivery_days": r.avg_delivery_days,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _cost_to_dict(r: ShippingCostResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "total_cost": r.total_cost, "avg_cost_per_shipment": r.avg_cost_per_shipment,
        "n_shipments_costed": r.n_shipments_costed,
        "by_carrier": [{"carrier": c.carrier, "total_cost": c.total_cost, "avg_cost": c.avg_cost, "n_shipments": c.n_shipments} for c in r.by_carrier],
        "period_variances": [
            {"period": v.period, "prior_period": v.prior_period, "total_cost_prior": v.total_cost_prior,
             "total_cost_current": v.total_cost_current, "cost_variance": v.cost_variance, "cost_variance_pct": v.cost_variance_pct}
            for v in r.period_variances
        ],
        "min_periods_required": r.min_periods_required,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _carrier_route_to_dict(r: CarrierRoutePerformanceResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "is_validated_instrument": r.is_validated_instrument,
        "confidence": r.confidence, "n_carriers_excluded_no_data": r.n_carriers_excluded_no_data,
        "carrier_items": [
            {"carrier": i.carrier, "delivery_component": i.delivery_component, "cost_component": i.cost_component,
             "composite_score": i.composite_score, "components_used": i.components_used,
             "avg_cost": i.avg_cost, "n_shipments": i.n_shipments}
            for i in r.carrier_items
        ],
        "route_items": [
            {"route": i.route, "on_time_pct": i.on_time_pct, "avg_cost": i.avg_cost, "n_shipments": i.n_shipments}
            for i in r.route_items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
    }


def _delay_group_to_dict(s: DelayGroupStat) -> dict[str, Any]:
    return {"group_type": s.group_type, "group": s.group, "n_late": s.n_late,
            "avg_days_late": s.avg_days_late, "is_concentration_flagged": s.is_concentration_flagged}


def _delay_to_dict(r: DelayAnalysisResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "min_late_for_flag": r.min_late_for_flag, "n_late_total": r.n_late_total,
        "has_delay_cause_data": r.has_delay_cause_data,
        "by_carrier": [_delay_group_to_dict(s) for s in r.by_carrier],
        "by_route": [_delay_group_to_dict(s) for s in r.by_route],
        "by_carrier_route": [_delay_group_to_dict(s) for s in r.by_carrier_route],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _returns_to_dict(r: ReturnsAnalysisResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "n_shipments_total": r.n_shipments_total, "n_returned": r.n_returned,
        "return_rate_pct": r.return_rate_pct, "n_reasons_provided": r.n_reasons_provided,
        "min_mentions_for_theme": r.min_mentions_for_theme,
        "theme_frequencies": [
            {"theme": t.theme, "n_shipments_mentioned": t.n_shipments_mentioned, "pct_of_reasons_provided": t.pct_of_reasons_provided}
            for t in r.theme_frequencies
        ],
        "top_terms": [{"term": term, "n_shipments": n} for term, n in r.top_terms],
        "term_extraction_method": r.term_extraction_method,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
    }


def logistics_intelligence_to_dict(r: LogisticsIntelligenceResult) -> dict[str, Any]:
    return {
        "shipment_status": _status_to_dict(r.shipment_status),
        "delivery_time": _delivery_time_to_dict(r.delivery_time),
        "shipping_cost": _cost_to_dict(r.shipping_cost),
        "carrier_route_performance": _carrier_route_to_dict(r.carrier_route_performance),
        "delay_analysis": _delay_to_dict(r.delay_analysis),
        "returns_analysis": _returns_to_dict(r.returns_analysis),
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "confidence": r.confidence, "sources": r.sources, "computed_at": r.computed_at,
    }
