"""
Inventory Intelligence — Phase 32 (Business Intelligence Suite, Module 3).

A fourth, genuinely distinct data shape for this platform: item-level stock/
transaction data (SKU, quantity, unit cost, movement history) — not an
employee roster, not a general financial transaction list (Phase 30), and
not a double-entry GL export (Phase 31). Kept fully separate from both
`financial_intelligence_reporting_engine.py` and
`accounting_intelligence_engine.py` — no shared column-pattern constants or
imports between the three, per this session's established one-module-per-
domain convention.

**Two supported upload shapes, detected independently, never assumed:**
  1. A SNAPSHOT (a current-inventory export): SKU + QuantityOnHand + UnitCost
     + Category — a single point-in-time state, no movement history.
  2. A TRANSACTION LOG (a movement ledger): SKU + TransactionDate +
     TransactionType (Receipt/Issue) + QuantityMoved + UnitCost, one row per
     stock movement. Current stock is DERIVED as the net of all movements
     per SKU (sum of receipts minus sum of issues) — a real computation
     from the uploaded data, not a fabrication, and disclosed as such.
  A single upload may contain both a QuantityOnHand column AND movement
  columns (a richer export); in that case QuantityOnHand is used directly
  for "current stock" (it is the more authoritative source — a system's own
  stated on-hand figure) while movement history still powers every
  movement-dependent computation below.

**Honest snapshot-vs-history distinction — same discipline this session
already established for Payroll Movements' `data_mode` (`longitudinal` vs
`cross_sectional_snapshot`).** Only two of the six items below can be
computed from a snapshot alone (Current Stock Levels, ABC Analysis — both
need only a point-in-time quantity and unit cost). The other four
(Turnover, Stock Aging/Dead-Stock, Reorder Point & Safety Stock, Overstock/
Stockout Risk) all require real movement history and honestly report
not-computable without it — never approximated from a single snapshot.

**Turnover formula choice, disclosed via `formula_used`:**
  - `cogs_over_avg_inventory_value` — cost of goods issued (total issued
    quantity x unit cost) over the period, divided by AVERAGE inventory
    value over the period (not a crude two-point (opening+closing)/2
    average — a full daily-resampled running-balance series, averaged, for
    a more robust figure when transactions are lumpy). Used when unit cost
    is present.
  - `units_moved_over_avg_units_on_hand` — the same shape in raw units
    instead of value, used only when unit cost is not present. These two
    formulas are NOT interchangeable (one is value-weighted, one is not)
    and this platform never silently substitutes one for the other without
    disclosing which was actually used.

**Stock Aging tiers** (documented thresholds, mirroring
`contract_expiry_engine.py`'s honesty framing for its own 30/60/90-day
urgency bands): active (<=30 days since last movement) / watch (31-90) /
slow_moving (91-180) / dead_stock (180+). This is this platform's own
illustrative planning heuristic, common in inventory-management practice —
not tied to a specific regulatory or accounting standard, same as Contract
Expiry's tier boundaries were disclosed as an internal heuristic.

**ABC Analysis convention**: the standard 80/15/5 cumulative-value Pareto
split (A = items whose cumulative value contribution reaches the first 80%,
B = the next 15% up to 95%, C = the remaining 5%) — a widely used inventory-
management heuristic with several textbook variants (e.g. 70/20/10); this
platform uses the most common 80/15/5 split and discloses that choice
rather than presenting it as the only possible convention.

**Reorder Point & Safety Stock — two formulas, disclosed via
`formula_used`, chosen per item based on data actually present:**
  - `lead_time_variability` (the standard formula) — used only when a
    SKU has a real LeadTimeDays value: Safety Stock = Z x sigma_demand x
    sqrt(lead_time_days) (Z=1.65, a 95%-service-level constant — a common
    textbook default, not sourced to a specific external benchmark, same
    honesty framing as Pay Equity's disclosed statistical constants);
    Reorder Point = (average daily demand x lead_time_days) + Safety Stock.
  - `average_demand_days_of_supply` (the honest fallback) — used when
    movement history exists but NO lead-time value is present for that
    SKU. Rather than fabricate a lead-time assumption (explicitly
    prohibited by this phase's brief), this mode reports average daily
    demand and DAYS OF SUPPLY REMAINING (current stock / average daily
    demand) instead of an absolute reorder-point quantity, and flags
    stockout risk / overstock using a documented days-of-supply floor/
    ceiling (14 / 180 days) instead of a lead-time-derived number. This is
    a genuinely simpler, different metric — never presented as a true
    lead-time-aware reorder point.
  Lead time is evaluated PER SKU (a single upload may have real lead times
  for some items and not others — both formulas can appear side by side in
  the same result, disclosed per item).

**Overstock & Stockout Risk reuses item 5's own computed figures — not a
separate parallel calculation** (per this phase's explicit brief): both
flags are computed as fields on the same per-item reorder-point record
inside `analyze_reorder_points()`, and this item's result is built by
filtering that same list, never recomputed independently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

# ── Column detection (local-regex convention, fresh to this module) ────────

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
_QUANTITY_ON_HAND_PATTERNS = re.compile(
    r"\b(quantity[_\s]?on[_\s]?hand|qty[_\s]?on[_\s]?hand|current[_\s]?stock|stock[_\s]?level|"
    r"on[_\s]?hand[_\s]?qty|onhand|"
    r"الكمية[_\s]?المتوفرة|كمية[_\s]?المخزون)\b", re.I,
)
_UNIT_COST_PATTERNS = re.compile(
    r"\b(unit[_\s]?cost|cost[_\s]?per[_\s]?unit|unit[_\s]?price|cost|"
    r"سعر[_\s]?الوحدة|تكلفة[_\s]?الوحدة)\b", re.I,
)
_TRANSACTION_DATE_PATTERNS = re.compile(
    r"\b(transaction[_\s]?date|movement[_\s]?date|entry[_\s]?date|posting[_\s]?date|date|"
    r"تاريخ[_\s]?الحركة|تاريخ[_\s]?المعاملة)\b", re.I,
)
_TRANSACTION_TYPE_PATTERNS = re.compile(
    r"\b(transaction[_\s]?type|movement[_\s]?type|type|"
    r"نوع[_\s]?الحركة|النوع)\b", re.I,
)
_QUANTITY_MOVED_PATTERNS = re.compile(
    r"\b(quantity[_\s]?moved|qty[_\s]?moved|quantity|qty|units[_\s]?moved|"
    r"الكمية[_\s]?المتحركة|الكمية)\b", re.I,
)
_WAREHOUSE_PATTERNS = re.compile(
    r"\b(warehouse|location|store|branch|"
    r"المستودع|الموقع|الفرع)\b", re.I,
)
_LEAD_TIME_PATTERNS = re.compile(
    r"\b(lead[_\s]?time[_\s]?days|lead[_\s]?time|leadtime|"
    r"مدة[_\s]?التوريد|مهلة[_\s]?التوريد)\b", re.I,
)

_IN_TOKENS = frozenset({
    "receipt", "receive", "received", "in", "purchase", "return", "inbound", "restock",
    "استلام", "وارد", "شراء",
})
_OUT_TOKENS = frozenset({
    "issue", "issued", "out", "sale", "sold", "shipment", "consumption", "outbound", "usage",
    "صرف", "صادر", "بيع",
})

_Z_SERVICE_LEVEL = 1.65
_STOCKOUT_DAYS_THRESHOLD = 14
_OVERSTOCK_DAYS_THRESHOLD = 180
_OVERSTOCK_MULTIPLE = 3.0
_ABC_A_THRESHOLD_PCT = 80.0
_ABC_B_THRESHOLD_PCT = 95.0
_AGING_ACTIVE_MAX_DAYS = 30
_AGING_WATCH_MAX_DAYS = 90
_AGING_SLOW_MOVING_MAX_DAYS = 180

INVENTORY_CONFIDENCE = "derived_from_upload_planning_aid_not_certified"
INVENTORY_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded inventory data — they are a "
    "computational planning aid, not a certified stock valuation or audit. Reorder point, "
    "safety stock, and ABC thresholds use this platform's own disclosed conventions (see each "
    "section) — qualified inventory/operations review is required before any purchasing or "
    "stocking decision based on these figures."
)
INVENTORY_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات المخزون المُحمّلة — وهي أداة تخطيط حسابية مساعدة، "
    "وليست تقييماً معتمداً للمخزون أو تدقيقاً. تستخدم نقطة إعادة الطلب ومخزون الأمان وحدود "
    "تحليل ABC معايير داخلية مُفصح عنها لهذه المنصة — تلزم مراجعة متخصصي المخزون/العمليات قبل "
    "أي قرار شراء أو تخزين يُبنى على هذه الأرقام."
)
_SOURCES = [
    "ABC Analysis uses the standard 80/15/5 cumulative-value Pareto convention — a widely used "
    "inventory-management heuristic (several textbook variants exist, e.g. 70/20/10); this "
    "platform discloses the specific split it uses rather than presenting it as the only one.",
    "Stock Aging tiers (active <=30d / watch 31-90d / slow_moving 91-180d / dead_stock 180+d) "
    "are this platform's own illustrative planning heuristic, mirroring the disclosed-threshold "
    "discipline already used by contract_expiry_engine.py's urgency tiers.",
    "Safety Stock uses Z=1.65 (95% service level) — a common textbook default, not sourced to a "
    "specific external benchmark.",
    "Turnover and average-inventory figures are computed entirely from the uploaded data's own "
    "quantity/cost/date columns — no external benchmark or industry ratio is used anywhere in "
    "this module.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "sku": "SKU / item code (required)",
    "item_name": "Item name (optional)",
    "category": "Category (optional)",
    "quantity_on_hand": "Quantity on hand (snapshot; optional if movement history is present)",
    "unit_cost": "Unit cost (required for value-based views)",
    "transaction_date": "Transaction/movement date (required for movement-dependent views)",
    "transaction_type": "Transaction type — Receipt/Issue (required for movement-dependent views)",
    "quantity_moved": "Quantity moved (required for movement-dependent views)",
    "lead_time_days": "Lead time in days (optional — enables the full reorder-point formula)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "sku": "رمز الصنف (مطلوب)",
    "item_name": "اسم الصنف (اختياري)",
    "category": "الفئة (اختياري)",
    "quantity_on_hand": "الكمية المتوفرة (لقطة؛ اختياري إذا وُجد سجل حركة)",
    "unit_cost": "تكلفة الوحدة (مطلوبة للعروض المعتمدة على القيمة)",
    "transaction_date": "تاريخ الحركة (مطلوب للعروض المعتمدة على الحركة)",
    "transaction_type": "نوع الحركة — استلام/صرف (مطلوب للعروض المعتمدة على الحركة)",
    "quantity_moved": "الكمية المتحركة (مطلوبة للعروض المعتمدة على الحركة)",
    "lead_time_days": "مدة التوريد بالأيام (اختياري — يُفعّل صيغة نقطة الطلب الكاملة)",
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


def _classify_movement(raw: object) -> Optional[str]:
    """Returns 'in'|'out'|None — never guessed."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _IN_TOKENS:
        return "in"
    if key in _OUT_TOKENS:
        return "out"
    for token in _IN_TOKENS:
        if token in key:
            return "in"
    for token in _OUT_TOKENS:
        if token in key:
            return "out"
    return None


def _detect_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    sku_col = _find_column(df, _SKU_PATTERNS)
    exclude = {sku_col} if sku_col else set()
    item_name_col = _find_column(df, _ITEM_NAME_PATTERNS, exclude=frozenset(exclude))
    if item_name_col:
        exclude.add(item_name_col)
    category_col = _find_column(df, _CATEGORY_PATTERNS, exclude=frozenset(exclude))
    qoh_col = _find_column(df, _QUANTITY_ON_HAND_PATTERNS)
    unit_cost_col = _find_column(df, _UNIT_COST_PATTERNS)
    date_col = _find_column(df, _TRANSACTION_DATE_PATTERNS)
    type_col = _find_column(df, _TRANSACTION_TYPE_PATTERNS)
    qty_moved_exclude = {qoh_col} if qoh_col else set()
    qty_moved_col = _find_column(df, _QUANTITY_MOVED_PATTERNS, exclude=frozenset(qty_moved_exclude))
    warehouse_col = _find_column(df, _WAREHOUSE_PATTERNS)
    lead_time_col = _find_column(df, _LEAD_TIME_PATTERNS)
    return {
        "sku": sku_col, "item_name": item_name_col, "category": category_col,
        "quantity_on_hand": qoh_col, "unit_cost": unit_cost_col,
        "transaction_date": date_col, "transaction_type": type_col,
        "quantity_moved": qty_moved_col, "warehouse": warehouse_col,
        "lead_time_days": lead_time_col,
    }


@dataclass(frozen=True)
class _ItemMovementData:
    """Internal per-SKU aggregate, built once and reused across items 1-6."""
    sku: str
    item_name: Optional[str]
    category: Optional[str]
    unit_cost: Optional[float]
    current_stock: Optional[float]
    current_stock_source: str  # "snapshot_column" | "derived_from_movement"
    has_movement: bool
    total_issued: float
    total_received: float
    first_movement_date: Optional[pd.Timestamp]
    last_movement_date: Optional[pd.Timestamp]
    daily_balance: Optional[pd.Series]     # date-indexed running balance (units)
    daily_issues: Optional[pd.Series]      # date-indexed issued qty (0-filled)
    lead_time_days: Optional[float]


def _build_item_data(df: pd.DataFrame, cols: dict[str, Optional[str]], as_of: pd.Timestamp) -> dict[str, _ItemMovementData]:
    sku_col, name_col, cat_col = cols["sku"], cols["item_name"], cols["category"]
    qoh_col, cost_col = cols["quantity_on_hand"], cols["unit_cost"]
    date_col, type_col, qty_col = cols["transaction_date"], cols["transaction_type"], cols["quantity_moved"]
    lead_col = cols["lead_time_days"]

    has_movement_cols = date_col is not None and type_col is not None and qty_col is not None

    items: dict[str, _ItemMovementData] = {}
    rows_by_sku: dict[str, list[int]] = {}
    for idx in df.index:
        raw_sku = df.at[idx, sku_col]
        if _is_missing_value(raw_sku):
            continue
        sku = " ".join(str(raw_sku).split())
        rows_by_sku.setdefault(sku, []).append(idx)

    for sku, idxs in rows_by_sku.items():
        name = None
        category = None
        unit_cost = None
        lead_time = None
        if name_col:
            for idx in idxs:
                if not _is_missing_value(df.at[idx, name_col]):
                    name = str(df.at[idx, name_col]).strip()
                    break
        if cat_col:
            for idx in idxs:
                if not _is_missing_value(df.at[idx, cat_col]):
                    category = str(df.at[idx, cat_col]).strip()
                    break
        if cost_col:
            for idx in idxs:
                v = _numeric_or_none(df.at[idx, cost_col])
                if v is not None:
                    unit_cost = v
                    break
        if lead_col:
            for idx in idxs:
                v = _numeric_or_none(df.at[idx, lead_col])
                if v is not None:
                    lead_time = v
                    break

        qoh_direct = None
        if qoh_col:
            for idx in idxs:
                v = _numeric_or_none(df.at[idx, qoh_col])
                if v is not None:
                    qoh_direct = v

        total_issued = 0.0
        total_received = 0.0
        movement_rows: list[tuple[pd.Timestamp, str, float]] = []
        if has_movement_cols:
            for idx in idxs:
                raw_date = df.at[idx, date_col]
                raw_type = df.at[idx, type_col]
                raw_qty = df.at[idx, qty_col]
                parsed_date = pd.to_datetime(raw_date, errors="coerce")
                direction = _classify_movement(raw_type)
                qty = _numeric_or_none(raw_qty)
                if pd.isna(parsed_date) or direction is None or qty is None:
                    continue
                movement_rows.append((parsed_date, direction, qty))
                if direction == "in":
                    total_received += qty
                else:
                    total_issued += qty

        has_movement = len(movement_rows) > 0
        first_move = min((m[0] for m in movement_rows), default=None)
        last_move = max((m[0] for m in movement_rows), default=None)

        daily_balance = None
        daily_issues = None
        if has_movement and first_move is not None:
            daily_idx = pd.date_range(first_move.normalize(), as_of.normalize(), freq="D")
            signed = pd.Series(
                [q if d == "in" else -q for _, d, q in movement_rows],
                index=[t for t, _, _ in movement_rows],
            ).groupby(level=0).sum()
            daily_balance = signed.reindex(daily_idx, fill_value=0.0).cumsum()
            issues = pd.Series(
                [q for _, d, q in movement_rows if d == "out"],
                index=[t for t, d, _ in movement_rows if d == "out"],
            )
            issues = issues.groupby(level=0).sum() if len(issues) else issues
            daily_issues = issues.reindex(daily_idx, fill_value=0.0)

        if qoh_direct is not None:
            current_stock = qoh_direct
            source = "snapshot_column"
        elif has_movement:
            current_stock = total_received - total_issued
            source = "derived_from_movement"
        else:
            current_stock = None
            source = "unavailable"

        items[sku] = _ItemMovementData(
            sku=sku, item_name=name, category=category, unit_cost=unit_cost,
            current_stock=current_stock, current_stock_source=source,
            has_movement=has_movement, total_issued=total_issued, total_received=total_received,
            first_movement_date=first_move, last_movement_date=last_move,
            daily_balance=daily_balance, daily_issues=daily_issues, lead_time_days=lead_time,
        )
    return items


# ── 1. Current Stock Levels & Movement ──────────────────────────────────────

@dataclass(frozen=True)
class StockLevelItem:
    sku: str
    item_name: Optional[str]
    category: Optional[str]
    current_stock: float
    current_stock_source: str
    total_received: Optional[float]
    total_issued: Optional[float]
    last_movement_date: Optional[str]


@dataclass(frozen=True)
class StockLevelsResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    has_movement_history: bool
    n_items: int
    items: list[StockLevelItem]
    narrative_en: str
    narrative_ar: str


def unavailable_stock_levels_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> StockLevelsResult:
    return StockLevelsResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        has_movement_history=False, n_items=0, items=[],
        narrative_en="Stock level analysis not available for this dataset.",
        narrative_ar="تحليل مستويات المخزون غير متاح لهذه البيانات.",
    )


def _stock_levels_from_items(item_data: dict[str, _ItemMovementData], has_movement_cols: bool, columns_detected: dict[str, bool]) -> StockLevelsResult:
    usable = {sku: d for sku, d in item_data.items() if d.current_stock is not None}
    if not usable:
        return unavailable_stock_levels_result(
            "No item had a computable current stock — either a QuantityOnHand snapshot column "
            "or a complete movement history (date + type + quantity) is required.",
            columns_detected,
        )
    items = [
        StockLevelItem(
            sku=d.sku, item_name=d.item_name, category=d.category,
            current_stock=round(d.current_stock, 2), current_stock_source=d.current_stock_source,
            total_received=(round(d.total_received, 2) if d.has_movement else None),
            total_issued=(round(d.total_issued, 2) if d.has_movement else None),
            last_movement_date=(d.last_movement_date.strftime("%Y-%m-%d") if d.last_movement_date is not None else None),
        )
        for d in usable.values()
    ]
    items.sort(key=lambda i: i.sku)
    has_movement_history = any(d.has_movement for d in usable.values())

    narrative_en = f"{len(items)} item(s) with a computable current stock level."
    narrative_ar = f"{len(items)} صنفاً بمستوى مخزون قابل للاحتساب."
    if has_movement_history:
        narrative_en += " Real movement (in/out) history is available for this upload."
        narrative_ar += " تتوفر بيانات حركة فعلية (وارد/صادر) لهذا الملف."
    else:
        narrative_en += (
            " Only a point-in-time QuantityOnHand snapshot is available — no movement history was "
            "detected, so no in/out trend can be shown (same honesty distinction as this platform's "
            "Payroll Movements module)."
        )
        narrative_ar += " تتوفر لقطة كمية لحظية فقط — لا يمكن عرض اتجاه حركة دون سجل حركة فعلي."

    return StockLevelsResult(
        available=True, reason=None, columns_detected=columns_detected,
        has_movement_history=has_movement_history, n_items=len(items), items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 2. Inventory Turnover ───────────────────────────────────────────────────

@dataclass(frozen=True)
class TurnoverItem:
    sku: str
    item_name: Optional[str]
    total_issued: float
    avg_units_on_hand: float
    avg_inventory_value: Optional[float]
    turnover_ratio: Optional[float]


@dataclass(frozen=True)
class TurnoverResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    formula_used: Optional[str]
    items: list[TurnoverItem]
    narrative_en: str
    narrative_ar: str


def unavailable_turnover_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> TurnoverResult:
    return TurnoverResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        formula_used=None, items=[],
        narrative_en="Inventory turnover not available for this dataset.",
        narrative_ar="معدل دوران المخزون غير متاح لهذه البيانات.",
    )


def _turnover_from_items(item_data: dict[str, _ItemMovementData], columns_detected: dict[str, bool]) -> TurnoverResult:
    movers = {sku: d for sku, d in item_data.items() if d.has_movement and d.daily_balance is not None}
    if not movers:
        return unavailable_turnover_result(
            "Inventory turnover requires real movement history (transaction date, type, and "
            "quantity) — a point-in-time snapshot alone cannot support a turnover calculation.",
            columns_detected,
        )
    has_cost = any(d.unit_cost is not None for d in movers.values())
    formula = "cogs_over_avg_inventory_value" if has_cost else "units_moved_over_avg_units_on_hand"

    items = []
    for d in movers.values():
        avg_units = float(d.daily_balance.mean())
        if formula == "cogs_over_avg_inventory_value" and d.unit_cost is not None:
            avg_value = avg_units * d.unit_cost
            cogs = d.total_issued * d.unit_cost
            ratio = round(cogs / avg_value, 3) if avg_value else None
        else:
            avg_value = None
            ratio = round(d.total_issued / avg_units, 3) if avg_units else None
        items.append(TurnoverItem(
            sku=d.sku, item_name=d.item_name, total_issued=round(d.total_issued, 2),
            avg_units_on_hand=round(avg_units, 2),
            avg_inventory_value=(round(avg_value, 2) if avg_value is not None else None),
            turnover_ratio=ratio,
        ))
    items.sort(key=lambda i: (i.turnover_ratio is None, -(i.turnover_ratio or 0)))

    formula_desc = "cost of goods issued / average inventory value" if formula == "cogs_over_avg_inventory_value" else "units issued / average units on hand (no unit-cost column detected)"
    narrative_en = f"Turnover computed for {len(items)} item(s) using {formula_desc}."
    narrative_ar = f"تم احتساب معدل الدوران لـ {len(items)} صنفاً."

    return TurnoverResult(
        available=True, reason=None, columns_detected=columns_detected, formula_used=formula,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 3. Stock Aging / Dead Stock ─────────────────────────────────────────────

@dataclass(frozen=True)
class StockAgingItem:
    sku: str
    item_name: Optional[str]
    days_since_last_movement: int
    tier: str
    current_stock: Optional[float]
    value_on_hand: Optional[float]


@dataclass(frozen=True)
class StockAgingResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    as_of_date: Optional[str]
    tier_counts: dict[str, int]
    items: list[StockAgingItem]
    narrative_en: str
    narrative_ar: str


def unavailable_stock_aging_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> StockAgingResult:
    return StockAgingResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        as_of_date=None, tier_counts={}, items=[],
        narrative_en="Stock aging / dead-stock analysis not available for this dataset.",
        narrative_ar="تحليل تقادم المخزون غير متاح لهذه البيانات.",
    )


def _aging_tier(days: int) -> str:
    if days <= _AGING_ACTIVE_MAX_DAYS:
        return "active"
    if days <= _AGING_WATCH_MAX_DAYS:
        return "watch"
    if days <= _AGING_SLOW_MOVING_MAX_DAYS:
        return "slow_moving"
    return "dead_stock"


def _aging_from_items(item_data: dict[str, _ItemMovementData], as_of: pd.Timestamp, columns_detected: dict[str, bool]) -> StockAgingResult:
    movers = {sku: d for sku, d in item_data.items() if d.has_movement and d.last_movement_date is not None}
    if not movers:
        return unavailable_stock_aging_result(
            "Stock aging requires real transaction dates to compute how long since each item last "
            "moved — a point-in-time snapshot alone cannot show staleness.",
            columns_detected,
        )
    items = []
    tier_counts = {"active": 0, "watch": 0, "slow_moving": 0, "dead_stock": 0}
    for d in movers.values():
        days = int((as_of.normalize() - d.last_movement_date.normalize()).days)
        tier = _aging_tier(days)
        tier_counts[tier] += 1
        value = (d.current_stock * d.unit_cost) if (d.current_stock is not None and d.unit_cost is not None) else None
        items.append(StockAgingItem(
            sku=d.sku, item_name=d.item_name, days_since_last_movement=days, tier=tier,
            current_stock=(round(d.current_stock, 2) if d.current_stock is not None else None),
            value_on_hand=(round(value, 2) if value is not None else None),
        ))
    items.sort(key=lambda i: -i.days_since_last_movement)

    narrative_en = (
        f"{len(items)} item(s) analyzed as of {as_of.strftime('%Y-%m-%d')}: {tier_counts['active']} active, "
        f"{tier_counts['watch']} watch, {tier_counts['slow_moving']} slow-moving, {tier_counts['dead_stock']} dead stock."
    )
    narrative_ar = (
        f"تم تحليل {len(items)} صنفاً حتى {as_of.strftime('%Y-%m-%d')}: {tier_counts['active']} نشط، "
        f"{tier_counts['watch']} تحت المراقبة، {tier_counts['slow_moving']} بطيء الحركة، {tier_counts['dead_stock']} راكد."
    )
    return StockAgingResult(
        available=True, reason=None, columns_detected=columns_detected,
        as_of_date=as_of.strftime("%Y-%m-%d"), tier_counts=tier_counts, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 4. ABC Analysis ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ABCItem:
    sku: str
    item_name: Optional[str]
    value_on_hand: float
    cumulative_pct_before: float
    tier: str


@dataclass(frozen=True)
class ABCResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    total_value: Optional[float]
    tier_counts: dict[str, int]
    tier_value_pct: dict[str, float]
    items: list[ABCItem]
    narrative_en: str
    narrative_ar: str


def unavailable_abc_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ABCResult:
    return ABCResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        total_value=None, tier_counts={}, tier_value_pct={}, items=[],
        narrative_en="ABC analysis not available for this dataset.",
        narrative_ar="تحليل ABC غير متاح لهذه البيانات.",
    )


def _abc_from_items(item_data: dict[str, _ItemMovementData], columns_detected: dict[str, bool]) -> ABCResult:
    valued = {
        sku: d for sku, d in item_data.items()
        if d.current_stock is not None and d.unit_cost is not None
    }
    if not valued:
        return unavailable_abc_result(
            "ABC analysis requires both a current stock quantity (snapshot or derived from "
            "movement) and a unit cost for each item — real quantity x cost, never assumed.",
            columns_detected,
        )
    ranked = sorted(valued.values(), key=lambda d: (d.current_stock * d.unit_cost), reverse=True)
    total_value = sum(d.current_stock * d.unit_cost for d in ranked)
    items = []
    tier_counts = {"A": 0, "B": 0, "C": 0}
    tier_value = {"A": 0.0, "B": 0.0, "C": 0.0}
    cum = 0.0
    for d in ranked:
        value = d.current_stock * d.unit_cost
        cum_before_pct = round(100.0 * cum / total_value, 2) if total_value else 0.0
        if cum_before_pct < _ABC_A_THRESHOLD_PCT:
            tier = "A"
        elif cum_before_pct < _ABC_B_THRESHOLD_PCT:
            tier = "B"
        else:
            tier = "C"
        cum += value
        tier_counts[tier] += 1
        tier_value[tier] += value
        items.append(ABCItem(
            sku=d.sku, item_name=d.item_name, value_on_hand=round(value, 2),
            cumulative_pct_before=cum_before_pct, tier=tier,
        ))
    tier_value_pct = {t: (round(100.0 * v / total_value, 1) if total_value else 0.0) for t, v in tier_value.items()}

    narrative_en = (
        f"{len(items)} item(s) classified by value contribution (80/15/5 cumulative-value "
        f"convention): {tier_counts['A']} A-tier ({tier_value_pct['A']}% of value), "
        f"{tier_counts['B']} B-tier ({tier_value_pct['B']}%), {tier_counts['C']} C-tier ({tier_value_pct['C']}%)."
    )
    narrative_ar = (
        f"تم تصنيف {len(items)} صنفاً حسب مساهمة القيمة: {tier_counts['A']} فئة A، "
        f"{tier_counts['B']} فئة B، {tier_counts['C']} فئة C."
    )

    return ABCResult(
        available=True, reason=None, columns_detected=columns_detected,
        total_value=round(total_value, 2), tier_counts=tier_counts, tier_value_pct=tier_value_pct,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 5 & 6. Reorder Point / Safety Stock + Overstock & Stockout Risk ────────

@dataclass(frozen=True)
class ReorderPointItem:
    sku: str
    item_name: Optional[str]
    formula_used: str  # "lead_time_variability" | "average_demand_days_of_supply"
    current_stock: float
    avg_daily_demand: float
    lead_time_days: Optional[float]
    demand_std: Optional[float]
    safety_stock: Optional[float]
    reorder_point: Optional[float]
    days_of_supply: Optional[float]
    stockout_risk: bool
    overstock: bool


@dataclass(frozen=True)
class ReorderPointResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    z_service_level: float
    stockout_days_threshold: int
    overstock_days_threshold: int
    overstock_multiple: float
    items: list[ReorderPointItem]
    narrative_en: str
    narrative_ar: str


def unavailable_reorder_point_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ReorderPointResult:
    return ReorderPointResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        z_service_level=_Z_SERVICE_LEVEL, stockout_days_threshold=_STOCKOUT_DAYS_THRESHOLD,
        overstock_days_threshold=_OVERSTOCK_DAYS_THRESHOLD, overstock_multiple=_OVERSTOCK_MULTIPLE,
        items=[],
        narrative_en="Reorder point / safety stock not available for this dataset.",
        narrative_ar="نقطة إعادة الطلب / مخزون الأمان غير متاحة لهذه البيانات.",
    )


def _reorder_points_from_items(item_data: dict[str, _ItemMovementData], as_of: pd.Timestamp, columns_detected: dict[str, bool]) -> ReorderPointResult:
    movers = {
        sku: d for sku, d in item_data.items()
        if d.has_movement and d.current_stock is not None and d.first_movement_date is not None
    }
    if not movers:
        return unavailable_reorder_point_result(
            "Reorder point and safety stock require real movement history (to estimate demand) — "
            "a point-in-time snapshot alone cannot support this calculation.",
            columns_detected,
        )
    items = []
    n_lead_time = 0
    for d in movers.values():
        observed_days = (as_of.normalize() - d.first_movement_date.normalize()).days
        avg_daily_demand = d.total_issued / observed_days if observed_days > 0 else 0.0
        if d.lead_time_days is not None and d.daily_issues is not None:
            n_lead_time += 1
            demand_std = float(d.daily_issues.std(ddof=0))
            safety_stock = _Z_SERVICE_LEVEL * demand_std * (d.lead_time_days ** 0.5)
            reorder_point = avg_daily_demand * d.lead_time_days + safety_stock
            stockout_risk = d.current_stock < safety_stock
            overstock = d.current_stock > _OVERSTOCK_MULTIPLE * reorder_point
            items.append(ReorderPointItem(
                sku=d.sku, item_name=d.item_name, formula_used="lead_time_variability",
                current_stock=round(d.current_stock, 2), avg_daily_demand=round(avg_daily_demand, 3),
                lead_time_days=d.lead_time_days, demand_std=round(demand_std, 3),
                safety_stock=round(safety_stock, 2), reorder_point=round(reorder_point, 2),
                days_of_supply=None, stockout_risk=bool(stockout_risk), overstock=bool(overstock),
            ))
        else:
            days_of_supply = d.current_stock / avg_daily_demand if avg_daily_demand else None
            stockout_risk = days_of_supply is not None and days_of_supply < _STOCKOUT_DAYS_THRESHOLD
            overstock = days_of_supply is not None and days_of_supply > _OVERSTOCK_DAYS_THRESHOLD
            items.append(ReorderPointItem(
                sku=d.sku, item_name=d.item_name, formula_used="average_demand_days_of_supply",
                current_stock=round(d.current_stock, 2), avg_daily_demand=round(avg_daily_demand, 3),
                lead_time_days=None, demand_std=None, safety_stock=None, reorder_point=None,
                days_of_supply=(round(days_of_supply, 1) if days_of_supply is not None else None),
                stockout_risk=bool(stockout_risk), overstock=bool(overstock),
            ))
    items.sort(key=lambda i: (not i.stockout_risk, not i.overstock, i.sku))

    n_simple = len(items) - n_lead_time
    narrative_en = (
        f"{len(items)} item(s) analyzed: {n_lead_time} using the full lead-time/safety-stock "
        f"formula, {n_simple} using the simpler average-demand days-of-supply fallback "
        f"(no lead-time value present for those items)."
    )
    narrative_ar = (
        f"تم تحليل {len(items)} صنفاً: {n_lead_time} باستخدام صيغة مدة التوريد الكاملة، "
        f"{n_simple} باستخدام تقدير أيام التغطية المبسّط (لا توجد مدة توريد لتلك الأصناف)."
    )

    return ReorderPointResult(
        available=True, reason=None, columns_detected=columns_detected,
        z_service_level=_Z_SERVICE_LEVEL, stockout_days_threshold=_STOCKOUT_DAYS_THRESHOLD,
        overstock_days_threshold=_OVERSTOCK_DAYS_THRESHOLD, overstock_multiple=_OVERSTOCK_MULTIPLE,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


@dataclass(frozen=True)
class OverstockStockoutResult:
    available: bool
    reason: Optional[str]
    n_stockout_risk: int
    n_overstock: int
    stockout_items: list[ReorderPointItem]
    overstock_items: list[ReorderPointItem]
    narrative_en: str
    narrative_ar: str


def _overstock_stockout_from_reorder(reorder: ReorderPointResult) -> OverstockStockoutResult:
    if not reorder.available:
        return OverstockStockoutResult(
            available=False, reason=reorder.reason, n_stockout_risk=0, n_overstock=0,
            stockout_items=[], overstock_items=[],
            narrative_en="Overstock / stockout risk not available for this dataset.",
            narrative_ar="مخاطر تكدس/نفاد المخزون غير متاحة لهذه البيانات.",
        )
    stockout_items = [i for i in reorder.items if i.stockout_risk]
    overstock_items = [i for i in reorder.items if i.overstock]
    narrative_en = f"{len(stockout_items)} item(s) at stockout risk; {len(overstock_items)} item(s) flagged as overstocked — both reuse item 5's own reorder-point figures, not a separate calculation."
    narrative_ar = f"{len(stockout_items)} صنفاً معرضاً لخطر النفاد؛ {len(overstock_items)} صنفاً مُصنّفاً كمخزون زائد."
    return OverstockStockoutResult(
        available=True, reason=None, n_stockout_risk=len(stockout_items), n_overstock=len(overstock_items),
        stockout_items=stockout_items, overstock_items=overstock_items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Top-level bundle ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InventoryIntelligenceResult:
    stock_levels: StockLevelsResult
    turnover: TurnoverResult
    stock_aging: StockAgingResult
    abc_analysis: ABCResult
    reorder_points: ReorderPointResult
    overstock_stockout: OverstockStockoutResult
    disclaimer_en: str
    disclaimer_ar: str
    confidence: str
    sources: list[str]
    computed_at: str


def _all_unavailable(reason: str) -> InventoryIntelligenceResult:
    return InventoryIntelligenceResult(
        stock_levels=unavailable_stock_levels_result(reason),
        turnover=unavailable_turnover_result(reason),
        stock_aging=unavailable_stock_aging_result(reason),
        abc_analysis=unavailable_abc_result(reason),
        reorder_points=unavailable_reorder_point_result(reason),
        overstock_stockout=OverstockStockoutResult(
            available=False, reason=reason, n_stockout_risk=0, n_overstock=0,
            stockout_items=[], overstock_items=[],
            narrative_en="Overstock / stockout risk not available for this dataset.",
            narrative_ar="مخاطر تكدس/نفاد المخزون غير متاحة لهذه البيانات.",
        ),
        disclaimer_en=INVENTORY_DISCLAIMER_EN, disclaimer_ar=INVENTORY_DISCLAIMER_AR,
        confidence=INVENTORY_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


def analyze_inventory_intelligence(df: pd.DataFrame, as_of_date: Optional[str] = None) -> InventoryIntelligenceResult:
    """Never raises. Detects columns once, builds per-SKU aggregates once,
    then feeds all 6 items from that shared computation — see module
    docstring for the snapshot-vs-movement-history distinction and each
    item's honest-degradation requirements."""
    if df is None or df.empty:
        return _all_unavailable("No data available for inventory intelligence analysis.")

    try:
        cols = _detect_columns(df)
        columns_detected = {
            "sku": cols["sku"] is not None, "item_name": cols["item_name"] is not None,
            "category": cols["category"] is not None, "quantity_on_hand": cols["quantity_on_hand"] is not None,
            "unit_cost": cols["unit_cost"] is not None, "transaction_date": cols["transaction_date"] is not None,
            "transaction_type": cols["transaction_type"] is not None, "quantity_moved": cols["quantity_moved"] is not None,
            "lead_time_days": cols["lead_time_days"] is not None,
        }
        if cols["sku"] is None:
            return _all_unavailable_with_columns(
                "No SKU/item-code column detected — every figure in this module is keyed by item, "
                "without one nothing can be computed.", columns_detected,
            )
        if cols["quantity_on_hand"] is None and (cols["transaction_date"] is None or cols["transaction_type"] is None or cols["quantity_moved"] is None):
            return _all_unavailable_with_columns(
                "Neither a QuantityOnHand snapshot column nor a complete movement history "
                "(transaction date + type + quantity, all three) was detected.", columns_detected,
            )

        as_of = pd.to_datetime(as_of_date) if as_of_date else pd.Timestamp(datetime.now(timezone.utc).date())
        item_data = _build_item_data(df, cols, as_of)
        has_movement_cols = cols["transaction_date"] is not None and cols["transaction_type"] is not None and cols["quantity_moved"] is not None

        stock_levels = _stock_levels_from_items(item_data, has_movement_cols, columns_detected)
        turnover = _turnover_from_items(item_data, columns_detected)
        stock_aging = _aging_from_items(item_data, as_of, columns_detected)
        abc_analysis = _abc_from_items(item_data, columns_detected)
        reorder_points = _reorder_points_from_items(item_data, as_of, columns_detected)
        overstock_stockout = _overstock_stockout_from_reorder(reorder_points)
    except Exception as exc:
        return _all_unavailable(f"Inventory intelligence analysis encountered an error: {exc}")

    return InventoryIntelligenceResult(
        stock_levels=stock_levels, turnover=turnover, stock_aging=stock_aging,
        abc_analysis=abc_analysis, reorder_points=reorder_points, overstock_stockout=overstock_stockout,
        disclaimer_en=INVENTORY_DISCLAIMER_EN, disclaimer_ar=INVENTORY_DISCLAIMER_AR,
        confidence=INVENTORY_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


def _all_unavailable_with_columns(reason: str, columns_detected: dict[str, bool]) -> InventoryIntelligenceResult:
    r = _all_unavailable(reason)
    return InventoryIntelligenceResult(
        stock_levels=unavailable_stock_levels_result(reason, columns_detected),
        turnover=unavailable_turnover_result(reason, columns_detected),
        stock_aging=unavailable_stock_aging_result(reason, columns_detected),
        abc_analysis=unavailable_abc_result(reason, columns_detected),
        reorder_points=unavailable_reorder_point_result(reason, columns_detected),
        overstock_stockout=r.overstock_stockout,
        disclaimer_en=INVENTORY_DISCLAIMER_EN, disclaimer_ar=INVENTORY_DISCLAIMER_AR,
        confidence=INVENTORY_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _stock_levels_to_dict(r: StockLevelsResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "has_movement_history": r.has_movement_history, "n_items": r.n_items,
        "items": [
            {"sku": i.sku, "item_name": i.item_name, "category": i.category,
             "current_stock": i.current_stock, "current_stock_source": i.current_stock_source,
             "total_received": i.total_received, "total_issued": i.total_issued,
             "last_movement_date": i.last_movement_date}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _turnover_to_dict(r: TurnoverResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "formula_used": r.formula_used,
        "items": [
            {"sku": i.sku, "item_name": i.item_name, "total_issued": i.total_issued,
             "avg_units_on_hand": i.avg_units_on_hand, "avg_inventory_value": i.avg_inventory_value,
             "turnover_ratio": i.turnover_ratio}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _aging_to_dict(r: StockAgingResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "as_of_date": r.as_of_date, "tier_counts": r.tier_counts,
        "items": [
            {"sku": i.sku, "item_name": i.item_name, "days_since_last_movement": i.days_since_last_movement,
             "tier": i.tier, "current_stock": i.current_stock, "value_on_hand": i.value_on_hand}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _abc_to_dict(r: ABCResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "total_value": r.total_value, "tier_counts": r.tier_counts, "tier_value_pct": r.tier_value_pct,
        "items": [
            {"sku": i.sku, "item_name": i.item_name, "value_on_hand": i.value_on_hand,
             "cumulative_pct_before": i.cumulative_pct_before, "tier": i.tier}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _reorder_item_to_dict(i: ReorderPointItem) -> dict[str, Any]:
    return {
        "sku": i.sku, "item_name": i.item_name, "formula_used": i.formula_used,
        "current_stock": i.current_stock, "avg_daily_demand": i.avg_daily_demand,
        "lead_time_days": i.lead_time_days, "demand_std": i.demand_std,
        "safety_stock": i.safety_stock, "reorder_point": i.reorder_point,
        "days_of_supply": i.days_of_supply, "stockout_risk": i.stockout_risk, "overstock": i.overstock,
    }


def _reorder_to_dict(r: ReorderPointResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "z_service_level": r.z_service_level, "stockout_days_threshold": r.stockout_days_threshold,
        "overstock_days_threshold": r.overstock_days_threshold, "overstock_multiple": r.overstock_multiple,
        "items": [_reorder_item_to_dict(i) for i in r.items],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _overstock_stockout_to_dict(r: OverstockStockoutResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason,
        "n_stockout_risk": r.n_stockout_risk, "n_overstock": r.n_overstock,
        "stockout_items": [_reorder_item_to_dict(i) for i in r.stockout_items],
        "overstock_items": [_reorder_item_to_dict(i) for i in r.overstock_items],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def inventory_intelligence_to_dict(r: InventoryIntelligenceResult) -> dict[str, Any]:
    return {
        "stock_levels": _stock_levels_to_dict(r.stock_levels),
        "turnover": _turnover_to_dict(r.turnover),
        "stock_aging": _aging_to_dict(r.stock_aging),
        "abc_analysis": _abc_to_dict(r.abc_analysis),
        "reorder_points": _reorder_to_dict(r.reorder_points),
        "overstock_stockout": _overstock_stockout_to_dict(r.overstock_stockout),
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "confidence": r.confidence, "sources": r.sources, "computed_at": r.computed_at,
    }
