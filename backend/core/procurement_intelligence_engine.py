"""
Procurement Intelligence — Phase 33 (Business Intelligence Suite, Module 4).

Purchase-order/supplier-level data — related to Inventory Intelligence
(Phase 32, which tracks stock ON HAND) but genuinely distinct: this module
tracks the BUYING PROCESS and supplier relationships that replenish that
stock (who was bought from, at what price, on what schedule). Kept as a
fully separate engine — no shared imports with
`inventory_intelligence_engine.py`, per this session's established
one-module-per-domain convention, even though the item/SKU concept is
similar in spirit (column-pattern constants are re-declared fresh here,
not imported).

**Column detection**: supplier name, SKU/item code, item name, category, PO
date, unit price, quantity, total spend (optional direct column — derived
from unit_price x quantity when absent, disclosed via
`total_spend_source`), expected delivery date, actual delivery date
(both optional, independently detected per supplier/row — a real, common
case is that delivery-date tracking exists for some suppliers/rows and not
others, and this module degrades PER SUPPLIER, not just at the whole-file
level).

**Price trend detection — same minimum-sample discipline as this session's
other statistical modules** (`pay_equity_engine.py`'s
`_MIN_GROUP_SIZE_FOR_DISPARITY`, `accounting_intelligence_engine.py`'s
`_MIN_SAMPLE_SIZE_FOR_ANOMALY`). A price "trend" for a single (supplier,
SKU) pair is only declared when there are at least `_MIN_PERIODS_FOR_TREND`
(2) distinct monthly periods of purchase data AND at least
`_MIN_POS_FOR_TREND` (4) total purchase-order line observations across
those periods — a two-point comparison from just two POs is exactly the
kind of noise this gate exists to prevent. Pairs below the floor are
counted and disclosed as suppressed, never silently dropped without a
trace. Period-over-period variance reuses the exact field-naming and
calculation shape already established in `payroll_budget_engine.py` /
`financial_intelligence_reporting_engine.py` / `accounting_intelligence_
engine.py`'s variance dataclasses (`X_variance = current - prior`,
`X_variance_pct = round(100 * variance / prior, 1)`, sorted by absolute
magnitude) — not a new invented shape.

**Supplier performance scoring — constructed heuristic, NOT a validated
instrument**, same framing as `succession_readiness_engine.py`'s readiness
score (`IS_VALIDATED_INSTRUMENT = False`,
`confidence = "constructed_heuristic_not_validated"`). Combines two
components where real data supports them — on-time delivery percentage,
and a price-trend component derived from eligible price-trend pairs only
(never from suppressed/insufficient-sample pairs) — with a disclosed 50/50
weighting when both are available, or a single-component score when only
one is. A supplier with NEITHER component computable is excluded from
scoring entirely, never force-scored from nothing.

**Cost-reduction opportunity flagging** is a direct, real comparison of
this platform's own uploaded multi-supplier price data — average price per
supplier for the same SKU, flagged when the spread exceeds a disclosed
threshold (`_COST_REDUCTION_THRESHOLD_PCT` = 8%). This is explicitly NOT an
external market-price comparison (this platform has no live market-price
search capability) — every number traces to the user's own purchase
history, with the observation count for each supplier disclosed so
confidence can be judged.

**Explicitly deferred this phase** (see PHASE_33 report for the full
list): supplier risk scoring beyond this performance composite (true risk
scoring needs external data — financial health, credit ratings — this
platform cannot access) and anything requiring live external market-price
comparison.

**Phase 34 update**: the on-time-delivery arithmetic in
`_delivery_from_lines()` below was extracted into
`backend/core/delivery_performance_utils.py`'s `compute_on_time_performance()`
so `logistics_intelligence_engine.py` could reuse the exact same
computation for outbound carrier delivery performance instead of
duplicating it — see that module's docstring. This function still owns
all of the procurement-domain column detection, PO-line building, and the
`SupplierDeliveryItem`/`DeliveryPerformanceResult` shape; only the
group-by-date-pair on-time math itself is shared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.delivery_performance_utils import compute_on_time_performance

# ── Column detection (local-regex convention, fresh to this module) ────────

_SUPPLIER_PATTERNS = re.compile(
    r"\b(supplier[_\s]?name|supplier[_\s]?id|supplier|vendor[_\s]?name|vendor|"
    r"المورد|اسم[_\s]?المورد)\b", re.I,
)
_SKU_PATTERNS = re.compile(
    r"\b(sku|item[_\s]?code|item[_\s]?no|product[_\s]?code|part[_\s]?number|"
    r"رمز[_\s]?الصنف|كود[_\s]?الصنف|كود[_\s]?المنتج)\b", re.I,
)
_ITEM_NAME_PATTERNS = re.compile(
    r"\b(item[_\s]?name|product[_\s]?name|description|"
    r"اسم[_\s]?الصنف|اسم[_\s]?المنتج)\b", re.I,
)
_CATEGORY_PATTERNS = re.compile(
    r"\b(item[_\s]?category|product[_\s]?category|category|"
    r"فئة[_\s]?الصنف|الفئة)\b", re.I,
)
_PO_DATE_PATTERNS = re.compile(
    r"\b(po[_\s]?date|order[_\s]?date|purchase[_\s]?date|purchase[_\s]?order[_\s]?date|date|"
    r"تاريخ[_\s]?الطلب|تاريخ[_\s]?الشراء)\b", re.I,
)
_UNIT_PRICE_PATTERNS = re.compile(
    r"\b(unit[_\s]?price|price[_\s]?per[_\s]?unit|price|unit[_\s]?cost|"
    r"سعر[_\s]?الوحدة|السعر)\b", re.I,
)
_QUANTITY_PATTERNS = re.compile(
    r"\b(quantity|qty|units[_\s]?ordered|"
    r"الكمية)\b", re.I,
)
_TOTAL_SPEND_PATTERNS = re.compile(
    r"\b(total[_\s]?spend|total[_\s]?cost|total[_\s]?amount|po[_\s]?amount|order[_\s]?total|"
    r"إجمالي[_\s]?الإنفاق|إجمالي[_\s]?المبلغ)\b", re.I,
)
_EXPECTED_DELIVERY_PATTERNS = re.compile(
    r"\b(expected[_\s]?delivery[_\s]?date|expected[_\s]?date|promised[_\s]?date|due[_\s]?delivery[_\s]?date|"
    r"تاريخ[_\s]?التسليم[_\s]?المتوقع)\b", re.I,
)
_ACTUAL_DELIVERY_PATTERNS = re.compile(
    r"\b(actual[_\s]?delivery[_\s]?date|delivery[_\s]?date|received[_\s]?date|actual[_\s]?date|"
    r"تاريخ[_\s]?الاستلام|تاريخ[_\s]?التسليم[_\s]?الفعلي)\b", re.I,
)

_MIN_PERIODS_FOR_TREND = 2
_MIN_POS_FOR_TREND = 4
_COST_REDUCTION_THRESHOLD_PCT = 8.0

IS_VALIDATED_INSTRUMENT = False
PERFORMANCE_SCORE_CONFIDENCE = "constructed_heuristic_not_validated"
PERFORMANCE_SCORE_DISCLAIMER_EN = (
    "Supplier performance scores are this platform's own CONSTRUCTED HEURISTIC combining real "
    "on-time-delivery percentage and price-trend data where available — NOT a validated, "
    "peer-reviewed, or industry-benchmarked supplier rating. The 50/50 component weighting is an "
    "illustrative default, not a validated weighting scheme. Qualified procurement review is "
    "required before any sourcing decision based on this score."
)
PERFORMANCE_SCORE_DISCLAIMER_AR = (
    "درجات أداء الموردين هي معيار داخلي مُركّب من تصميم هذه المنصة، يجمع نسبة التسليم في الموعد "
    "واتجاه السعر عند توفرهما — وليست تقييماً معتمداً أو مُحكَّماً أو معيارياً للصناعة. تلزم "
    "مراجعة متخصصي المشتريات قبل أي قرار توريد يُبنى على هذه الدرجة."
)
PROCUREMENT_CONFIDENCE = "derived_from_upload_planning_aid_not_certified"
PROCUREMENT_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded purchase-order data — a "
    "computational planning aid, not an audited procurement report. No external market-price "
    "benchmark is used anywhere in this module — cost-reduction flags compare only your own "
    "real multi-supplier purchase history."
)
PROCUREMENT_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات أوامر الشراء المُحمّلة — أداة تخطيط حسابية مساعدة، "
    "وليست تقريراً مُدقَّقاً للمشتريات. لا يُستخدم أي معيار سوقي خارجي في هذه الوحدة."
)
_SOURCES = [
    "Price-trend variance reuses the exact field-naming and calculation shape already "
    "established in payroll_budget_engine.py / financial_intelligence_reporting_engine.py / "
    "accounting_intelligence_engine.py's variance dataclasses.",
    "Price-trend detection requires at least 2 distinct monthly periods AND at least 4 total "
    "purchase-order observations for a (supplier, SKU) pair — the same disclosed-suppression "
    "discipline as pay_equity_engine.py's minimum-group-size gate and accounting_intelligence_"
    "engine.py's minimum-sample-size gate for anomaly detection.",
    "Supplier performance scoring is a constructed heuristic (see disclaimer), not a validated "
    "instrument — same framing as succession_readiness_engine.py's readiness score.",
    "Cost-reduction flags compare only the uploaded data's own multi-supplier prices for the "
    "same SKU — no external market-price benchmark is used anywhere in this module.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "supplier": "Supplier name/ID (required)",
    "sku": "SKU / item code (required)",
    "item_name": "Item name (optional)",
    "category": "Category (optional)",
    "po_date": "PO/order date (required for price-trend and delivery views)",
    "unit_price": "Unit price (required, unless a direct total-spend column exists)",
    "quantity": "Quantity (required, unless a direct total-spend column exists)",
    "total_spend": "Total spend (optional direct column — derived from price x quantity if absent)",
    "expected_delivery_date": "Expected delivery date (optional — enables delivery performance)",
    "actual_delivery_date": "Actual delivery date (optional — enables delivery performance)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "supplier": "اسم/رمز المورد (مطلوب)",
    "sku": "رمز الصنف (مطلوب)",
    "item_name": "اسم الصنف (اختياري)",
    "category": "الفئة (اختياري)",
    "po_date": "تاريخ الطلب (مطلوب لعروض اتجاه السعر والتسليم)",
    "unit_price": "سعر الوحدة (مطلوب ما لم يوجد عمود إجمالي إنفاق مباشر)",
    "quantity": "الكمية (مطلوبة ما لم يوجد عمود إجمالي إنفاق مباشر)",
    "total_spend": "إجمالي الإنفاق (عمود مباشر اختياري)",
    "expected_delivery_date": "تاريخ التسليم المتوقع (اختياري)",
    "actual_delivery_date": "تاريخ التسليم الفعلي (اختياري)",
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


def _detect_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    supplier_col = _find_column(df, _SUPPLIER_PATTERNS)
    exclude: set = {supplier_col} if supplier_col else set()
    sku_col = _find_column(df, _SKU_PATTERNS, exclude=frozenset(exclude))
    if sku_col:
        exclude.add(sku_col)
    item_name_col = _find_column(df, _ITEM_NAME_PATTERNS, exclude=frozenset(exclude))
    if item_name_col:
        exclude.add(item_name_col)
    category_col = _find_column(df, _CATEGORY_PATTERNS, exclude=frozenset(exclude))
    po_date_col = _find_column(df, _PO_DATE_PATTERNS)
    unit_price_col = _find_column(df, _UNIT_PRICE_PATTERNS)
    quantity_col = _find_column(df, _QUANTITY_PATTERNS)
    total_spend_col = _find_column(df, _TOTAL_SPEND_PATTERNS)
    expected_col = _find_column(df, _EXPECTED_DELIVERY_PATTERNS)
    actual_exclude = {expected_col} if expected_col else set()
    actual_col = _find_column(df, _ACTUAL_DELIVERY_PATTERNS, exclude=frozenset(actual_exclude))
    return {
        "supplier": supplier_col, "sku": sku_col, "item_name": item_name_col, "category": category_col,
        "po_date": po_date_col, "unit_price": unit_price_col, "quantity": quantity_col,
        "total_spend": total_spend_col, "expected_delivery_date": expected_col, "actual_delivery_date": actual_col,
    }


@dataclass(frozen=True)
class _POLine:
    supplier: str
    sku: str
    item_name: Optional[str]
    category: Optional[str]
    date: Optional[pd.Timestamp]
    unit_price: Optional[float]
    quantity: Optional[float]
    spend: Optional[float]
    spend_source: str  # "direct_column" | "price_times_quantity"
    expected_delivery: Optional[pd.Timestamp]
    actual_delivery: Optional[pd.Timestamp]


def _build_po_lines(df: pd.DataFrame, cols: dict[str, Optional[str]]) -> list[_POLine]:
    supplier_col, sku_col, name_col, cat_col = cols["supplier"], cols["sku"], cols["item_name"], cols["category"]
    date_col, price_col, qty_col, spend_col = cols["po_date"], cols["unit_price"], cols["quantity"], cols["total_spend"]
    exp_col, act_col = cols["expected_delivery_date"], cols["actual_delivery_date"]

    lines: list[_POLine] = []
    for idx in df.index:
        raw_supplier = df.at[idx, supplier_col]
        raw_sku = df.at[idx, sku_col]
        if _is_missing_value(raw_supplier) or _is_missing_value(raw_sku):
            continue
        supplier = " ".join(str(raw_supplier).split())
        sku = " ".join(str(raw_sku).split())
        name = str(df.at[idx, name_col]).strip() if name_col and not _is_missing_value(df.at[idx, name_col]) else None
        category = str(df.at[idx, cat_col]).strip() if cat_col and not _is_missing_value(df.at[idx, cat_col]) else None

        date = None
        if date_col is not None:
            parsed = pd.to_datetime(df.at[idx, date_col], errors="coerce")
            date = parsed if pd.notna(parsed) else None

        price = _numeric_or_none(df.at[idx, price_col]) if price_col else None
        qty = _numeric_or_none(df.at[idx, qty_col]) if qty_col else None

        spend = None
        spend_source = "unavailable"
        if spend_col is not None:
            direct = _numeric_or_none(df.at[idx, spend_col])
            if direct is not None:
                spend = direct
                spend_source = "direct_column"
        if spend is None and price is not None and qty is not None:
            spend = price * qty
            spend_source = "price_times_quantity"

        expected = None
        actual = None
        if exp_col is not None:
            p = pd.to_datetime(df.at[idx, exp_col], errors="coerce")
            expected = p if pd.notna(p) else None
        if act_col is not None:
            p = pd.to_datetime(df.at[idx, act_col], errors="coerce")
            actual = p if pd.notna(p) else None

        lines.append(_POLine(
            supplier=supplier, sku=sku, item_name=name, category=category, date=date,
            unit_price=price, quantity=qty, spend=spend, spend_source=spend_source,
            expected_delivery=expected, actual_delivery=actual,
        ))
    return lines


# ── 1. Supplier Spend Analysis ──────────────────────────────────────────────

@dataclass(frozen=True)
class CategorySpend:
    category: str
    total_spend: float
    n_pos: int


@dataclass(frozen=True)
class SupplierSpendItem:
    supplier: str
    total_spend: float
    n_pos: int
    category_breakdown: list[CategorySpend]


@dataclass(frozen=True)
class SupplierSpendResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    total_spend_all_suppliers: Optional[float]
    items: list[SupplierSpendItem]
    narrative_en: str
    narrative_ar: str


def unavailable_supplier_spend_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> SupplierSpendResult:
    return SupplierSpendResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        total_spend_all_suppliers=None, items=[],
        narrative_en="Supplier spend analysis not available for this dataset.",
        narrative_ar="تحليل إنفاق الموردين غير متاح لهذه البيانات.",
    )


def _supplier_spend_from_lines(lines: list[_POLine], columns_detected: dict[str, bool]) -> SupplierSpendResult:
    valid = [l for l in lines if l.spend is not None]
    if not valid:
        return unavailable_supplier_spend_result(
            "No purchase-order line had a computable spend amount — either a total-spend column "
            "or both unit price and quantity are required.", columns_detected,
        )
    by_supplier: dict[str, list[_POLine]] = {}
    for l in valid:
        by_supplier.setdefault(l.supplier, []).append(l)

    items = []
    total_all = 0.0
    for supplier, sup_lines in by_supplier.items():
        total = sum(l.spend for l in sup_lines)
        total_all += total
        by_cat: dict[str, list[float]] = {}
        for l in sup_lines:
            if l.category:
                by_cat.setdefault(l.category, []).append(l.spend)
        cat_breakdown = [
            CategorySpend(category=c, total_spend=round(sum(v), 2), n_pos=len(v))
            for c, v in sorted(by_cat.items(), key=lambda kv: -sum(kv[1]))
        ]
        items.append(SupplierSpendItem(
            supplier=supplier, total_spend=round(total, 2), n_pos=len(sup_lines),
            category_breakdown=cat_breakdown,
        ))
    items.sort(key=lambda i: -i.total_spend)

    narrative_en = f"{len(items)} supplier(s), total spend SAR {total_all:,.2f} across {len(valid)} purchase-order line(s)."
    narrative_ar = f"{len(items)} مورداً، إجمالي الإنفاق {total_all:,.2f} ريال عبر {len(valid)} بند أمر شراء."

    return SupplierSpendResult(
        available=True, reason=None, columns_detected=columns_detected,
        total_spend_all_suppliers=round(total_all, 2), items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 2. Purchase Order & Price Analysis ──────────────────────────────────────

@dataclass(frozen=True)
class POPricePoint:
    date: Optional[str]
    unit_price: float
    quantity: Optional[float]


@dataclass(frozen=True)
class ItemPriceHistory:
    supplier: str
    sku: str
    item_name: Optional[str]
    n_pos: int
    avg_price: float
    min_price: float
    max_price: float
    price_points: list[POPricePoint]


@dataclass(frozen=True)
class POPriceAnalysisResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    items: list[ItemPriceHistory]
    narrative_en: str
    narrative_ar: str


def unavailable_po_price_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> POPriceAnalysisResult:
    return POPriceAnalysisResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, items=[],
        narrative_en="Purchase order / price analysis not available for this dataset.",
        narrative_ar="تحليل أوامر الشراء والأسعار غير متاح لهذه البيانات.",
    )


def _po_price_from_lines(lines: list[_POLine], columns_detected: dict[str, bool]) -> POPriceAnalysisResult:
    priced = [l for l in lines if l.unit_price is not None]
    if not priced:
        return unavailable_po_price_result(
            "Purchase order / price analysis requires a unit-price column — a total-spend-only "
            "upload cannot show per-item price history.", columns_detected,
        )
    by_pair: dict[tuple[str, str], list[_POLine]] = {}
    for l in priced:
        by_pair.setdefault((l.supplier, l.sku), []).append(l)

    items = []
    for (supplier, sku), pair_lines in by_pair.items():
        pair_lines_sorted = sorted(pair_lines, key=lambda l: (l.date is None, l.date))
        prices = [l.unit_price for l in pair_lines_sorted]
        items.append(ItemPriceHistory(
            supplier=supplier, sku=sku, item_name=pair_lines_sorted[0].item_name,
            n_pos=len(pair_lines_sorted), avg_price=round(sum(prices) / len(prices), 4),
            min_price=round(min(prices), 4), max_price=round(max(prices), 4),
            price_points=[
                POPricePoint(
                    date=(l.date.strftime("%Y-%m-%d") if l.date is not None else None),
                    unit_price=round(l.unit_price, 4), quantity=l.quantity,
                )
                for l in pair_lines_sorted
            ],
        ))
    items.sort(key=lambda i: (i.supplier, i.sku))

    narrative_en = f"Price history computed for {len(items)} supplier-item pair(s)."
    narrative_ar = f"تم احتساب تاريخ الأسعار لـ {len(items)} زوج مورد-صنف."

    return POPriceAnalysisResult(
        available=True, reason=None, columns_detected=columns_detected, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 3. Price Variance / Price Change Tracking ───────────────────────────────

@dataclass(frozen=True)
class PricePeriodVariance:
    period: str
    prior_period: str
    avg_price_prior: float
    avg_price_current: float
    price_variance: float
    price_variance_pct: Optional[float]


@dataclass(frozen=True)
class PriceTrendItem:
    supplier: str
    sku: str
    item_name: Optional[str]
    n_pos: int
    n_periods: int
    overall_change_pct: Optional[float]
    period_variances: list[PricePeriodVariance]


@dataclass(frozen=True)
class PriceTrendResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    min_periods_required: int
    min_pos_required: int
    n_pairs_suppressed_insufficient_sample: int
    items: list[PriceTrendItem]
    narrative_en: str
    narrative_ar: str


def unavailable_price_trend_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> PriceTrendResult:
    return PriceTrendResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        min_periods_required=_MIN_PERIODS_FOR_TREND, min_pos_required=_MIN_POS_FOR_TREND,
        n_pairs_suppressed_insufficient_sample=0, items=[],
        narrative_en="Price trend analysis not available for this dataset.",
        narrative_ar="تحليل اتجاه الأسعار غير متاح لهذه البيانات.",
    )


def _price_trend_from_lines(lines: list[_POLine], columns_detected: dict[str, bool]) -> PriceTrendResult:
    dated = [l for l in lines if l.unit_price is not None and l.date is not None]
    if not dated:
        return unavailable_price_trend_result(
            "Price trend tracking requires both a unit-price column and a real PO-date column — "
            "a trend cannot be computed without knowing when each purchase happened.",
            columns_detected,
        )
    by_pair: dict[tuple[str, str], list[_POLine]] = {}
    for l in dated:
        by_pair.setdefault((l.supplier, l.sku), []).append(l)

    items = []
    n_suppressed = 0
    for (supplier, sku), pair_lines in by_pair.items():
        n_pos = len(pair_lines)
        period_map: dict[str, list[float]] = {}
        for l in pair_lines:
            period = l.date.strftime("%Y-%m")
            period_map.setdefault(period, []).append(l.unit_price)
        n_periods = len(period_map)

        if n_pos < _MIN_POS_FOR_TREND or n_periods < _MIN_PERIODS_FOR_TREND:
            n_suppressed += 1
            continue

        period_avg = {p: sum(v) / len(v) for p, v in period_map.items()}
        sorted_periods = sorted(period_avg.keys())
        variances = []
        for i in range(1, len(sorted_periods)):
            prior, curr = sorted_periods[i - 1], sorted_periods[i]
            prior_avg, curr_avg = period_avg[prior], period_avg[curr]
            variance = round(curr_avg - prior_avg, 4)
            variance_pct = round(100.0 * variance / prior_avg, 2) if prior_avg else None
            variances.append(PricePeriodVariance(
                period=curr, prior_period=prior, avg_price_prior=round(prior_avg, 4),
                avg_price_current=round(curr_avg, 4), price_variance=variance, price_variance_pct=variance_pct,
            ))
        variances.sort(key=lambda v: abs(v.price_variance_pct or 0), reverse=True)

        first_avg, last_avg = period_avg[sorted_periods[0]], period_avg[sorted_periods[-1]]
        overall_change = round(100.0 * (last_avg - first_avg) / first_avg, 2) if first_avg else None

        items.append(PriceTrendItem(
            supplier=supplier, sku=sku, item_name=pair_lines[0].item_name, n_pos=n_pos,
            n_periods=n_periods, overall_change_pct=overall_change, period_variances=variances,
        ))
    items.sort(key=lambda i: abs(i.overall_change_pct or 0), reverse=True)

    narrative_en = (
        f"{len(items)} supplier-item pair(s) had enough history (>= {_MIN_PERIODS_FOR_TREND} periods, "
        f">= {_MIN_POS_FOR_TREND} purchase orders) for a real trend. {n_suppressed} pair(s) were "
        f"suppressed for insufficient sample — never guessed from too few observations."
    )
    narrative_ar = (
        f"توفرت بيانات كافية لـ {len(items)} زوج مورد-صنف لاحتساب اتجاه حقيقي. تم استبعاد "
        f"{n_suppressed} زوجاً لقلة عدد المشاهدات."
    )

    return PriceTrendResult(
        available=True, reason=None, columns_detected=columns_detected,
        min_periods_required=_MIN_PERIODS_FOR_TREND, min_pos_required=_MIN_POS_FOR_TREND,
        n_pairs_suppressed_insufficient_sample=n_suppressed, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 4. Delivery / On-Time Performance ───────────────────────────────────────

@dataclass(frozen=True)
class SupplierDeliveryItem:
    supplier: str
    n_pos_with_delivery_data: int
    n_on_time: int
    on_time_pct: float


@dataclass(frozen=True)
class DeliveryPerformanceResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    n_suppliers_without_delivery_data: int
    suppliers_without_delivery_data: list[str]
    items: list[SupplierDeliveryItem]
    narrative_en: str
    narrative_ar: str


def unavailable_delivery_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> DeliveryPerformanceResult:
    return DeliveryPerformanceResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        n_suppliers_without_delivery_data=0, suppliers_without_delivery_data=[], items=[],
        narrative_en="Delivery / on-time performance not available for this dataset.",
        narrative_ar="أداء التسليم في الموعد غير متاح لهذه البيانات.",
    )


def _delivery_from_lines(lines: list[_POLine], columns_detected: dict[str, bool]) -> DeliveryPerformanceResult:
    if not any(l.expected_delivery is not None or l.actual_delivery is not None for l in lines):
        return unavailable_delivery_result(
            "Delivery performance requires both an expected-delivery-date and an actual-delivery-"
            "date column — neither was detected in this upload.", columns_detected,
        )

    shared = compute_on_time_performance([(l.supplier, l.expected_delivery, l.actual_delivery) for l in lines])
    if not shared.available:
        return unavailable_delivery_result(
            "Delivery-date columns were detected, but no row had both a valid expected and "
            "actual delivery date.", columns_detected,
        )

    items = [
        SupplierDeliveryItem(
            supplier=i.group, n_pos_with_delivery_data=i.n_with_complete_dates,
            n_on_time=i.n_on_time, on_time_pct=i.on_time_pct,
        )
        for i in shared.items
    ]

    n_complete = sum(i.n_with_complete_dates for i in shared.items)
    narrative_en = f"On-time delivery computed for {len(items)} supplier(s) from {n_complete} PO line(s) with complete delivery-date data."
    narrative_ar = f"تم احتساب التسليم في الموعد لـ {len(items)} مورداً."
    if shared.groups_without_data:
        narrative_en += f" {len(shared.groups_without_data)} supplier(s) had no delivery-date data at all: {', '.join(shared.groups_without_data)}."
        narrative_ar += f" لا تتوفر بيانات تسليم لـ {len(shared.groups_without_data)} مورداً."

    return DeliveryPerformanceResult(
        available=True, reason=None, columns_detected=columns_detected,
        n_suppliers_without_delivery_data=shared.n_groups_without_data,
        suppliers_without_delivery_data=shared.groups_without_data,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 5. Supplier Performance Scoring (constructed heuristic) ────────────────

@dataclass(frozen=True)
class SupplierPerformanceItem:
    supplier: str
    delivery_component: Optional[float]
    price_trend_component: Optional[float]
    composite_score: float
    components_used: list[str]


@dataclass(frozen=True)
class SupplierPerformanceResult:
    available: bool
    reason: Optional[str]
    is_validated_instrument: bool
    confidence: str
    n_suppliers_excluded_no_data: int
    items: list[SupplierPerformanceItem]
    narrative_en: str
    narrative_ar: str
    disclaimer_en: str
    disclaimer_ar: str


def unavailable_performance_result(reason: str) -> SupplierPerformanceResult:
    return SupplierPerformanceResult(
        available=False, reason=reason, is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        confidence=PERFORMANCE_SCORE_CONFIDENCE, n_suppliers_excluded_no_data=0, items=[],
        narrative_en="Supplier performance scoring not available for this dataset.",
        narrative_ar="تقييم أداء الموردين غير متاح لهذه البيانات.",
        disclaimer_en=PERFORMANCE_SCORE_DISCLAIMER_EN, disclaimer_ar=PERFORMANCE_SCORE_DISCLAIMER_AR,
    )


def _performance_from_components(
    delivery: DeliveryPerformanceResult, price_trend: PriceTrendResult, all_suppliers_in_data: frozenset[str],
) -> SupplierPerformanceResult:
    delivery_by_supplier = {i.supplier: i.on_time_pct for i in delivery.items} if delivery.available else {}

    price_component_by_supplier: dict[str, list[float]] = {}
    if price_trend.available:
        for item in price_trend.items:
            if item.overall_change_pct is not None:
                component = max(0.0, min(100.0, 100.0 - max(0.0, item.overall_change_pct)))
                price_component_by_supplier.setdefault(item.supplier, []).append(component)

    all_suppliers = set(all_suppliers_in_data) or (set(delivery_by_supplier.keys()) | set(price_component_by_supplier.keys()))
    if not all_suppliers:
        return unavailable_performance_result(
            "Supplier performance scoring requires either delivery-date data or a computable "
            "price trend for at least one supplier — neither is available in this dataset.",
        )

    items = []
    n_excluded = 0
    for supplier in all_suppliers:
        d = delivery_by_supplier.get(supplier)
        p_list = price_component_by_supplier.get(supplier)
        p = (sum(p_list) / len(p_list)) if p_list else None
        components_used = []
        if d is not None:
            components_used.append("delivery_on_time_pct")
        if p is not None:
            components_used.append("price_trend")
        if not components_used:
            n_excluded += 1
            continue
        if d is not None and p is not None:
            composite = round(0.5 * d + 0.5 * p, 1)
        elif d is not None:
            composite = round(d, 1)
        else:
            composite = round(p, 1)
        items.append(SupplierPerformanceItem(
            supplier=supplier, delivery_component=(round(d, 1) if d is not None else None),
            price_trend_component=(round(p, 1) if p is not None else None),
            composite_score=composite, components_used=components_used,
        ))
    items.sort(key=lambda i: -i.composite_score)

    if not items:
        return unavailable_performance_result(
            "No supplier had at least one computable component (delivery on-time % or price trend).",
        )

    narrative_en = (
        f"{len(items)} supplier(s) scored using a constructed heuristic (delivery on-time % and/or "
        f"price trend, 50/50 weighted when both available). {n_excluded} supplier(s) had neither "
        f"component computable and were excluded, never force-scored."
    )
    narrative_ar = (
        f"تم تقييم {len(items)} مورداً باستخدام معيار داخلي مُركّب. تم استبعاد {n_excluded} مورداً "
        "لعدم توفر أي مكوّن قابل للاحتساب."
    )

    return SupplierPerformanceResult(
        available=True, reason=None, is_validated_instrument=IS_VALIDATED_INSTRUMENT,
        confidence=PERFORMANCE_SCORE_CONFIDENCE, n_suppliers_excluded_no_data=n_excluded,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
        disclaimer_en=PERFORMANCE_SCORE_DISCLAIMER_EN, disclaimer_ar=PERFORMANCE_SCORE_DISCLAIMER_AR,
    )


# ── 6. Cost-Reduction Opportunity Flagging ──────────────────────────────────

@dataclass(frozen=True)
class CostReductionOpportunity:
    sku: str
    item_name: Optional[str]
    cheapest_supplier: str
    cheapest_avg_price: float
    cheapest_n_pos: int
    priciest_supplier: str
    priciest_avg_price: float
    priciest_n_pos: int
    price_diff_pct: float


@dataclass(frozen=True)
class CostReductionResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    threshold_pct: float
    items: list[CostReductionOpportunity]
    narrative_en: str
    narrative_ar: str


def unavailable_cost_reduction_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> CostReductionResult:
    return CostReductionResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        threshold_pct=_COST_REDUCTION_THRESHOLD_PCT, items=[],
        narrative_en="Cost-reduction opportunity flagging not available for this dataset.",
        narrative_ar="رصد فرص خفض التكلفة غير متاح لهذه البيانات.",
    )


def _cost_reduction_from_lines(lines: list[_POLine], columns_detected: dict[str, bool]) -> CostReductionResult:
    priced = [l for l in lines if l.unit_price is not None]
    if not priced:
        return unavailable_cost_reduction_result(
            "Cost-reduction flagging requires a unit-price column to compare suppliers.",
            columns_detected,
        )
    by_sku: dict[str, list[_POLine]] = {}
    for l in priced:
        by_sku.setdefault(l.sku, []).append(l)

    items = []
    for sku, sku_lines in by_sku.items():
        by_supplier: dict[str, list[float]] = {}
        for l in sku_lines:
            by_supplier.setdefault(l.supplier, []).append(l.unit_price)
        if len(by_supplier) < 2:
            continue
        avg_by_supplier = {s: (sum(v) / len(v), len(v)) for s, v in by_supplier.items()}
        cheapest_sup = min(avg_by_supplier, key=lambda s: avg_by_supplier[s][0])
        priciest_sup = max(avg_by_supplier, key=lambda s: avg_by_supplier[s][0])
        cheapest_price, cheapest_n = avg_by_supplier[cheapest_sup]
        priciest_price, priciest_n = avg_by_supplier[priciest_sup]
        if cheapest_price <= 0:
            continue
        diff_pct = round(100.0 * (priciest_price - cheapest_price) / cheapest_price, 2)
        if diff_pct < _COST_REDUCTION_THRESHOLD_PCT:
            continue
        items.append(CostReductionOpportunity(
            sku=sku, item_name=sku_lines[0].item_name,
            cheapest_supplier=cheapest_sup, cheapest_avg_price=round(cheapest_price, 4), cheapest_n_pos=cheapest_n,
            priciest_supplier=priciest_sup, priciest_avg_price=round(priciest_price, 4), priciest_n_pos=priciest_n,
            price_diff_pct=diff_pct,
        ))
    items.sort(key=lambda i: -i.price_diff_pct)

    narrative_en = (
        f"{len(items)} item(s) sourced from multiple suppliers at a price spread of "
        f"{_COST_REDUCTION_THRESHOLD_PCT}% or more — computed only from your own uploaded "
        f"purchase history, no external market comparison."
    )
    narrative_ar = f"تم رصد {len(items)} صنفاً بفارق سعر {_COST_REDUCTION_THRESHOLD_PCT}% أو أكثر بين الموردين."

    return CostReductionResult(
        available=True, reason=None, columns_detected=columns_detected,
        threshold_pct=_COST_REDUCTION_THRESHOLD_PCT, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Top-level bundle ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProcurementIntelligenceResult:
    supplier_spend: SupplierSpendResult
    po_price_analysis: POPriceAnalysisResult
    price_trend: PriceTrendResult
    delivery_performance: DeliveryPerformanceResult
    supplier_performance: SupplierPerformanceResult
    cost_reduction: CostReductionResult
    disclaimer_en: str
    disclaimer_ar: str
    confidence: str
    sources: list[str]
    computed_at: str


def _all_unavailable(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ProcurementIntelligenceResult:
    return ProcurementIntelligenceResult(
        supplier_spend=unavailable_supplier_spend_result(reason, columns_detected),
        po_price_analysis=unavailable_po_price_result(reason, columns_detected),
        price_trend=unavailable_price_trend_result(reason, columns_detected),
        delivery_performance=unavailable_delivery_result(reason, columns_detected),
        supplier_performance=unavailable_performance_result(reason),
        cost_reduction=unavailable_cost_reduction_result(reason, columns_detected),
        disclaimer_en=PROCUREMENT_DISCLAIMER_EN, disclaimer_ar=PROCUREMENT_DISCLAIMER_AR,
        confidence=PROCUREMENT_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


def analyze_procurement_intelligence(df: pd.DataFrame) -> ProcurementIntelligenceResult:
    """Never raises. Detects columns once, builds per-PO-line records once,
    then feeds all 6 items from that shared computation."""
    if df is None or df.empty:
        return _all_unavailable("No data available for procurement intelligence analysis.")

    try:
        cols = _detect_columns(df)
        columns_detected = {
            "supplier": cols["supplier"] is not None, "sku": cols["sku"] is not None,
            "item_name": cols["item_name"] is not None, "category": cols["category"] is not None,
            "po_date": cols["po_date"] is not None, "unit_price": cols["unit_price"] is not None,
            "quantity": cols["quantity"] is not None, "total_spend": cols["total_spend"] is not None,
            "expected_delivery_date": cols["expected_delivery_date"] is not None,
            "actual_delivery_date": cols["actual_delivery_date"] is not None,
        }
        if cols["supplier"] is None or cols["sku"] is None:
            return _all_unavailable(
                "No supplier and/or SKU/item-code column detected — every figure in this module "
                "is keyed by supplier and item, without both nothing can be computed.",
                columns_detected,
            )
        has_spend_signal = cols["total_spend"] is not None or (cols["unit_price"] is not None and cols["quantity"] is not None)
        if not has_spend_signal and cols["unit_price"] is None:
            return _all_unavailable(
                "Neither a total-spend column nor a unit-price column was detected — no spend or "
                "price figure can be computed.", columns_detected,
            )

        lines = _build_po_lines(df, cols)
        supplier_spend = _supplier_spend_from_lines(lines, columns_detected)
        po_price_analysis = _po_price_from_lines(lines, columns_detected)
        price_trend = _price_trend_from_lines(lines, columns_detected)
        delivery_performance = _delivery_from_lines(lines, columns_detected)
        all_suppliers_in_data = frozenset(l.supplier for l in lines)
        supplier_performance = _performance_from_components(delivery_performance, price_trend, all_suppliers_in_data)
        cost_reduction = _cost_reduction_from_lines(lines, columns_detected)
    except Exception as exc:
        return _all_unavailable(f"Procurement intelligence analysis encountered an error: {exc}")

    return ProcurementIntelligenceResult(
        supplier_spend=supplier_spend, po_price_analysis=po_price_analysis, price_trend=price_trend,
        delivery_performance=delivery_performance, supplier_performance=supplier_performance,
        cost_reduction=cost_reduction,
        disclaimer_en=PROCUREMENT_DISCLAIMER_EN, disclaimer_ar=PROCUREMENT_DISCLAIMER_AR,
        confidence=PROCUREMENT_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _spend_to_dict(r: SupplierSpendResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "total_spend_all_suppliers": r.total_spend_all_suppliers,
        "items": [
            {"supplier": i.supplier, "total_spend": i.total_spend, "n_pos": i.n_pos,
             "category_breakdown": [{"category": c.category, "total_spend": c.total_spend, "n_pos": c.n_pos} for c in i.category_breakdown]}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _po_price_to_dict(r: POPriceAnalysisResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "items": [
            {"supplier": i.supplier, "sku": i.sku, "item_name": i.item_name, "n_pos": i.n_pos,
             "avg_price": i.avg_price, "min_price": i.min_price, "max_price": i.max_price,
             "price_points": [{"date": p.date, "unit_price": p.unit_price, "quantity": p.quantity} for p in i.price_points]}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _price_trend_to_dict(r: PriceTrendResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "min_periods_required": r.min_periods_required, "min_pos_required": r.min_pos_required,
        "n_pairs_suppressed_insufficient_sample": r.n_pairs_suppressed_insufficient_sample,
        "items": [
            {"supplier": i.supplier, "sku": i.sku, "item_name": i.item_name, "n_pos": i.n_pos,
             "n_periods": i.n_periods, "overall_change_pct": i.overall_change_pct,
             "period_variances": [
                 {"period": v.period, "prior_period": v.prior_period, "avg_price_prior": v.avg_price_prior,
                  "avg_price_current": v.avg_price_current, "price_variance": v.price_variance,
                  "price_variance_pct": v.price_variance_pct}
                 for v in i.period_variances
             ]}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _delivery_to_dict(r: DeliveryPerformanceResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "n_suppliers_without_delivery_data": r.n_suppliers_without_delivery_data,
        "suppliers_without_delivery_data": r.suppliers_without_delivery_data,
        "items": [
            {"supplier": i.supplier, "n_pos_with_delivery_data": i.n_pos_with_delivery_data,
             "n_on_time": i.n_on_time, "on_time_pct": i.on_time_pct}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _performance_to_dict(r: SupplierPerformanceResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "is_validated_instrument": r.is_validated_instrument,
        "confidence": r.confidence, "n_suppliers_excluded_no_data": r.n_suppliers_excluded_no_data,
        "items": [
            {"supplier": i.supplier, "delivery_component": i.delivery_component,
             "price_trend_component": i.price_trend_component, "composite_score": i.composite_score,
             "components_used": i.components_used}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
    }


def _cost_reduction_to_dict(r: CostReductionResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "threshold_pct": r.threshold_pct,
        "items": [
            {"sku": i.sku, "item_name": i.item_name, "cheapest_supplier": i.cheapest_supplier,
             "cheapest_avg_price": i.cheapest_avg_price, "cheapest_n_pos": i.cheapest_n_pos,
             "priciest_supplier": i.priciest_supplier, "priciest_avg_price": i.priciest_avg_price,
             "priciest_n_pos": i.priciest_n_pos, "price_diff_pct": i.price_diff_pct}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def procurement_intelligence_to_dict(r: ProcurementIntelligenceResult) -> dict[str, Any]:
    return {
        "supplier_spend": _spend_to_dict(r.supplier_spend),
        "po_price_analysis": _po_price_to_dict(r.po_price_analysis),
        "price_trend": _price_trend_to_dict(r.price_trend),
        "delivery_performance": _delivery_to_dict(r.delivery_performance),
        "supplier_performance": _performance_to_dict(r.supplier_performance),
        "cost_reduction": _cost_reduction_to_dict(r.cost_reduction),
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "confidence": r.confidence, "sources": r.sources, "computed_at": r.computed_at,
    }
