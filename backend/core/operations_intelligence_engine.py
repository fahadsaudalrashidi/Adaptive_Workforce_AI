"""
Operations Intelligence — Phase 35 (Business Intelligence Suite, Module 6, final).

**Step 0 — designing the data shape.** Unlike every prior Business
Intelligence module (each had one obvious real-world shape: shipments,
purchase orders, inventory transactions), operations data has no single
canonical shape — a factory's downtime log looks nothing like a service
branch's productivity log. Rather than inventing one rigid schema, this
module works from a generic OPERATIONAL-UNIT-PER-PERIOD record: a unit
(department/branch/production-line/machine — whatever the data calls it)
observed over a period, plus whichever of the following the upload
actually contains: output, hours operated, hours available (capacity),
downtime hours (+ optional reason), a defect/quality metric, and a cost
figure. Every one of the 6 items below is designed to work from whatever
honest SUBSET of these is present — none of the six requires all of them,
and each item's own column requirements are independently gated (same
per-item `available` discipline as every other Business Intelligence
module this session).

**Utilization deliberately requires a real capacity denominator.**
Utilization = hours operated / hours available is meaningless without a
genuine "hours available" figure — this module never assumes a default
capacity (e.g. "24/7" or "8 hours/day") to manufacture a utilization rate
that isn't really in the data.

**Downtime-cause breakdown reuses the TF-IDF theme-extraction machinery
promoted to public functions in exit_interview_intelligence_engine.py —
now genuinely reused across a THIRD domain** (Exit Interview -> Logistics
Returns, Phase 34 -> Operations Downtime, this phase), each with its own
fresh, domain-specific theme dictionary (HR attrition constructs / return
reasons / downtime causes have zero semantic overlap with each other, so
only the dictionary differs — the extraction mechanism, the
MIN_DOCUMENT_FREQUENCY=3 suppression floor, and the "never surface raw
text" discipline are shared verbatim). If the downtime-reason column looks
already-categorical (few distinct short values relative to row count)
rather than free text, this module skips TF-IDF entirely and reports a
direct category breakdown instead — never forcing a text-mining pipeline
onto data that's already structured.

**Quality/defect trend** reuses the exact period-variance shape already
established in `payroll_budget_engine.py` / Phase 30/31/33/34's variance
dataclasses (`variance = current - prior`, `variance_pct`, sorted by
absolute magnitude, gated on a minimum period count) — not a new pattern.

**Bottleneck identification — same minimum-sample discipline as every
other statistical module this session** (`pay_equity_engine.py`,
`accounting_intelligence_engine.py`, `procurement_intelligence_engine.py`,
`logistics_intelligence_engine.py`). A unit is only confidently flagged as
a bottleneck once it has at least `_MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE`
(3) periods of data AND its utilization sits meaningfully below the
(sufficient-sample) fleet average — a unit with only 1-2 periods can look
just as bad or worse on paper but is deliberately NOT flagged, since one
or two bad periods could reflect a temporary anomaly rather than a
persistent pattern. Its raw numbers are still shown, never hidden — only
the confident "bottleneck" label is withheld.

**Cost-per-unit-of-operation — ownership decision (Operations vs.
Financial Intelligence), same boundary discipline as Phase 32's flagged
carrying-cost question.** This module DOES build cost-per-unit-of-output,
and that is a deliberate, documented choice: it requires joining an
operating-cost figure to a production/OUTPUT figure at the operational-
unit level — a join Financial Intelligence's upload shape (Phase 30, a
plain transaction list with no concept of "units produced") cannot make.
Financial Intelligence owns company-wide expense-category and P&L
analysis; this module owns cost EXPRESSED PER UNIT OF OUTPUT at the
production-line/branch level, which is meaningless without operational
output data Financial Intelligence never sees. The two are complementary,
not duplicative — see the PHASE_35 report for the full reasoning.

**Explicitly deferred this phase**: true SLA-compliance tracking (needs
contractually-defined SLA targets this platform has no way to know
without them being explicitly provided in the upload — if a real
SLA-target column is detected in a future upload, that would be a
plausible, easy Phase 2 addition, but this phase does not assume or
default one), and predictive/forecasting capability for any of the six
items (consistent with every other Business Intelligence domain deferring
forecasting).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.exit_interview_intelligence_engine import (
    MIN_DOCUMENT_FREQUENCY,
    MIN_RESPONSES_FOR_AGGREGATE,
    SKLEARN_AVAILABLE,
    extract_top_terms_tfidf,
    extract_top_terms_word_frequency,
    scrub_pii,
)

# ── Column detection (local-regex convention, fresh to this module) ────────

_UNIT_PATTERNS = re.compile(
    r"\b(unit|department|dept|branch|production[_\s]?line|line|machine|facility|cost[_\s]?center|"
    r"الوحدة|القسم|الفرع|خط[_\s]?الإنتاج)\b", re.I,
)
_PERIOD_PATTERNS = re.compile(
    r"\b(period|month|date|تاريخ|الفترة)\b", re.I,
)
_OUTPUT_PATTERNS = re.compile(
    r"\b(output|production[_\s]?count|units[_\s]?produced|quantity[_\s]?produced|production|"
    r"الإنتاج|الكمية[_\s]?المنتجة)\b", re.I,
)
_HOURS_OPERATED_PATTERNS = re.compile(
    r"\b(hours[_\s]?operated|operating[_\s]?hours|run[_\s]?hours|"
    r"ساعات[_\s]?التشغيل)\b", re.I,
)
_HOURS_AVAILABLE_PATTERNS = re.compile(
    r"\b(hours[_\s]?available|available[_\s]?hours|capacity[_\s]?hours|planned[_\s]?hours|"
    r"ساعات[_\s]?متاحة|الساعات[_\s]?المتاحة)\b", re.I,
)
_DOWNTIME_HOURS_PATTERNS = re.compile(
    r"\b(downtime[_\s]?hours|downtime|ساعات[_\s]?التوقف|التوقف)\b", re.I,
)
_DOWNTIME_REASON_PATTERNS = re.compile(
    r"\b(downtime[_\s]?reason|downtime[_\s]?cause|reason[_\s]?for[_\s]?downtime|"
    r"سبب[_\s]?التوقف)\b", re.I,
)
_DEFECT_COUNT_PATTERNS = re.compile(
    r"\b(defect[_\s]?count|defects|reject[_\s]?count|scrap[_\s]?count|"
    r"عدد[_\s]?العيوب)\b", re.I,
)
_QUALITY_SCORE_PATTERNS = re.compile(
    r"\b(quality[_\s]?score|defect[_\s]?rate|quality[_\s]?rate|"
    r"معدل[_\s]?الجودة)\b", re.I,
)
_COST_PATTERNS = re.compile(
    r"\b(operating[_\s]?cost|operation[_\s]?cost|cost|"
    r"تكلفة[_\s]?التشغيل|التكلفة)\b", re.I,
)

_DOWNTIME_THEME_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "Mechanical Failure": {
        "direct": ["mechanical failure", "machine broke down", "equipment malfunction",
                   "motor failure", "mechanical breakdown", "machine failure"],
        "proxy": ["broke down", "malfunction", "breakdown"],
    },
    "Material Shortage": {
        "direct": ["material shortage", "material delivery", "shortage on the line"],
        "proxy": ["raw materials", "short on"],
    },
    "Changeover/Setup": {
        "direct": ["changeover"],
        "proxy": ["product switch", "between batches", "product runs"],
    },
    "Scheduled Maintenance": {
        "direct": ["scheduled maintenance", "planned maintenance", "routine maintenance"],
        "proxy": ["maintenance performed", "maintenance downtime", "maintenance stop"],
    },
    "Power Outage": {
        "direct": ["power outage"],
        "proxy": ["power failure", "electrical outage"],
    },
}

_MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE = 3
_MIN_PERIODS_FOR_QUALITY_TREND = 2
_BOTTLENECK_UTILIZATION_GAP_PP = 15.0  # percentage points below fleet average
_CATEGORICAL_UNIQUE_RATIO_THRESHOLD = 0.5  # below this fraction unique/total -> treat as categorical
_CATEGORICAL_AVG_LEN_THRESHOLD = 25  # chars

OPERATIONS_CONFIDENCE = "derived_from_upload_planning_aid_not_certified"
OPERATIONS_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded operational data — a "
    "computational planning aid, not an audited operations report. Utilization is never "
    "estimated without a real 'hours available' capacity figure in your data."
)
OPERATIONS_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات التشغيل المُحمّلة — أداة تخطيط حسابية مساعدة، وليست "
    "تقريراً تشغيلياً مُدقَّقاً. لا يُقدَّر معدل الاستغلال أبداً دون رقم سعة (الساعات المتاحة) حقيقي."
)
_SOURCES = [
    "Quality/defect period-over-period variance reuses the exact field-naming and calculation "
    "shape already established in payroll_budget_engine.py / financial_intelligence_reporting_"
    "engine.py / accounting_intelligence_engine.py / procurement_intelligence_engine.py / "
    "logistics_intelligence_engine.py's variance dataclasses.",
    "Downtime-cause theme extraction reuses exit_interview_intelligence_engine.py's TF-IDF/word-"
    "frequency machinery and >=3-distinct-records suppression threshold (now shared across three "
    "domains: exit interviews, logistics returns, operations downtime) — a fresh, downtime-"
    "specific theme dictionary, not the HR attrition construct dictionary.",
    "Bottleneck flagging requires at least 3 periods of data before a unit is confidently "
    "labeled a bottleneck — the same disclosed-suppression discipline used throughout this "
    "session's statistical modules.",
    "Cost-per-unit-of-operation is scoped to this module (not Financial Intelligence) because it "
    "requires joining cost to a production/output figure at the operational-unit level — see "
    "module docstring for the full ownership-boundary reasoning.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "unit": "Operational unit — department/branch/line/machine (required)",
    "period": "Period (required for trend and bottleneck-confidence views)",
    "output": "Output / production count (required for productivity and cost-per-unit)",
    "hours_operated": "Hours operated (required for productivity and utilization)",
    "hours_available": "Hours available / capacity (required for utilization — never assumed)",
    "downtime_hours": "Downtime hours (required for downtime analysis)",
    "downtime_reason": "Downtime reason/cause (optional — enables cause breakdown)",
    "defect_count": "Defect count (required for quality analysis, unless a direct quality-score column exists)",
    "quality_score": "Defect rate / quality score — direct column (alternative to defect count)",
    "cost": "Operating cost (required for cost-per-unit-of-operation)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "unit": "الوحدة التشغيلية (مطلوبة)",
    "period": "الفترة (مطلوبة لعروض الاتجاه والثقة في رصد الاختناقات)",
    "output": "الإنتاج (مطلوب للإنتاجية والتكلفة لكل وحدة)",
    "hours_operated": "ساعات التشغيل (مطلوبة)",
    "hours_available": "الساعات المتاحة / السعة (مطلوبة لمعدل الاستغلال)",
    "downtime_hours": "ساعات التوقف (مطلوبة)",
    "downtime_reason": "سبب التوقف (اختياري)",
    "defect_count": "عدد العيوب (مطلوب ما لم يوجد عمود معدل جودة مباشر)",
    "quality_score": "معدل العيوب / درجة الجودة (بديل مباشر)",
    "cost": "تكلفة التشغيل (مطلوبة لتكلفة الوحدة)",
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
    unit_col = _find_column(df, _UNIT_PATTERNS)
    exclude = {unit_col} if unit_col else set()
    period_col = _find_column(df, _PERIOD_PATTERNS, exclude=frozenset(exclude))
    output_col = _find_column(df, _OUTPUT_PATTERNS)
    hours_op_col = _find_column(df, _HOURS_OPERATED_PATTERNS)
    hours_avail_col = _find_column(df, _HOURS_AVAILABLE_PATTERNS)
    downtime_hours_col = _find_column(df, _DOWNTIME_HOURS_PATTERNS)
    downtime_reason_col = _find_column(df, _DOWNTIME_REASON_PATTERNS)
    defect_count_col = _find_column(df, _DEFECT_COUNT_PATTERNS)
    quality_score_col = _find_column(df, _QUALITY_SCORE_PATTERNS)
    cost_exclude = {defect_count_col} if defect_count_col else set()
    cost_col = _find_column(df, _COST_PATTERNS, exclude=frozenset(cost_exclude))
    return {
        "unit": unit_col, "period": period_col, "output": output_col,
        "hours_operated": hours_op_col, "hours_available": hours_avail_col,
        "downtime_hours": downtime_hours_col, "downtime_reason": downtime_reason_col,
        "defect_count": defect_count_col, "quality_score": quality_score_col, "cost": cost_col,
    }


@dataclass(frozen=True)
class _UnitPeriodRecord:
    unit: str
    period: Optional[str]
    output: Optional[float]
    hours_operated: Optional[float]
    hours_available: Optional[float]
    downtime_hours: Optional[float]
    downtime_reason: Optional[str]
    defect_count: Optional[float]
    quality_score: Optional[float]
    cost: Optional[float]


def _build_records(df: pd.DataFrame, cols: dict[str, Optional[str]]) -> list[_UnitPeriodRecord]:
    records = []
    for idx in df.index:
        raw_unit = df.at[idx, cols["unit"]]
        if _is_missing_value(raw_unit):
            continue
        unit = " ".join(str(raw_unit).split())
        period = None
        if cols["period"]:
            raw_period = df.at[idx, cols["period"]]
            if not _is_missing_value(raw_period):
                parsed = pd.to_datetime(raw_period, errors="coerce")
                period = parsed.strftime("%Y-%m") if pd.notna(parsed) else str(raw_period).strip()

        def num(key):
            col = cols[key]
            return _numeric_or_none(df.at[idx, col]) if col else None

        downtime_reason = None
        if cols["downtime_reason"] and not _is_missing_value(df.at[idx, cols["downtime_reason"]]):
            downtime_reason = str(df.at[idx, cols["downtime_reason"]])

        record = _UnitPeriodRecord(
            unit=unit, period=period, output=num("output"), hours_operated=num("hours_operated"),
            hours_available=num("hours_available"), downtime_hours=num("downtime_hours"),
            downtime_reason=downtime_reason, defect_count=num("defect_count"),
            quality_score=num("quality_score"), cost=num("cost"),
        )
        if all(v is None for v in (record.output, record.hours_operated, record.hours_available,
                                     record.downtime_hours, record.defect_count, record.quality_score, record.cost)):
            continue
        records.append(record)
    return records


# ── 1. Productivity ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProductivityItem:
    unit: str
    total_output: float
    total_hours_operated: float
    productivity: float
    n_periods: int


@dataclass(frozen=True)
class ProductivityResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    items: list[ProductivityItem]
    narrative_en: str
    narrative_ar: str


def unavailable_productivity_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ProductivityResult:
    return ProductivityResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, items=[],
        narrative_en="Productivity analysis not available for this dataset.",
        narrative_ar="تحليل الإنتاجية غير متاح لهذه البيانات.",
    )


def _productivity_from_records(records: list[_UnitPeriodRecord], columns_detected: dict[str, bool]) -> ProductivityResult:
    if not (columns_detected.get("output") and columns_detected.get("hours_operated")):
        return unavailable_productivity_result(
            "Productivity requires both an output column and an hours-operated column.", columns_detected,
        )
    usable = [r for r in records if r.output is not None and r.hours_operated is not None]
    if not usable:
        return unavailable_productivity_result(
            "Output and hours-operated columns were found, but no row had both values.", columns_detected,
        )
    by_unit: dict[str, list[_UnitPeriodRecord]] = {}
    for r in usable:
        by_unit.setdefault(r.unit, []).append(r)

    items = []
    for unit, recs in by_unit.items():
        total_output = sum(r.output for r in recs)
        total_hours = sum(r.hours_operated for r in recs)
        if total_hours <= 0:
            continue
        items.append(ProductivityItem(
            unit=unit, total_output=round(total_output, 2), total_hours_operated=round(total_hours, 2),
            productivity=round(total_output / total_hours, 3), n_periods=len(recs),
        ))
    items.sort(key=lambda i: -i.productivity)

    narrative_en = f"Productivity (output per hour operated) computed for {len(items)} unit(s)."
    narrative_ar = f"تم احتساب الإنتاجية لـ {len(items)} وحدة."

    return ProductivityResult(
        available=True, reason=None, columns_detected=columns_detected, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 2. Utilization ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UtilizationItem:
    unit: str
    total_hours_operated: float
    total_hours_available: float
    utilization_pct: float
    n_periods: int


@dataclass(frozen=True)
class UtilizationResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    items: list[UtilizationItem]
    narrative_en: str
    narrative_ar: str


def unavailable_utilization_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> UtilizationResult:
    return UtilizationResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, items=[],
        narrative_en="Utilization not available for this dataset.",
        narrative_ar="معدل الاستغلال غير متاح لهذه البيانات.",
    )


def _utilization_from_records(records: list[_UnitPeriodRecord], columns_detected: dict[str, bool]) -> UtilizationResult:
    if not (columns_detected.get("hours_operated") and columns_detected.get("hours_available")):
        return unavailable_utilization_result(
            "Utilization requires both hours-operated AND hours-available (capacity) columns — "
            "it is never estimated with an assumed default capacity.", columns_detected,
        )
    usable = [r for r in records if r.hours_operated is not None and r.hours_available is not None]
    if not usable:
        return unavailable_utilization_result(
            "Hours-operated and hours-available columns were found, but no row had both values.",
            columns_detected,
        )
    by_unit: dict[str, list[_UnitPeriodRecord]] = {}
    for r in usable:
        by_unit.setdefault(r.unit, []).append(r)

    items = []
    for unit, recs in by_unit.items():
        total_op = sum(r.hours_operated for r in recs)
        total_avail = sum(r.hours_available for r in recs)
        if total_avail <= 0:
            continue
        items.append(UtilizationItem(
            unit=unit, total_hours_operated=round(total_op, 2), total_hours_available=round(total_avail, 2),
            utilization_pct=round(100.0 * total_op / total_avail, 2), n_periods=len(recs),
        ))
    items.sort(key=lambda i: i.utilization_pct)

    narrative_en = f"Utilization computed for {len(items)} unit(s) from real hours-operated/hours-available data."
    narrative_ar = f"تم احتساب معدل الاستغلال لـ {len(items)} وحدة."

    return UtilizationResult(
        available=True, reason=None, columns_detected=columns_detected, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 3. Downtime Analysis ──────────────────────────────────────────────────

@dataclass(frozen=True)
class DowntimeUnitItem:
    unit: str
    total_downtime_hours: float
    downtime_rate_pct: Optional[float]
    n_periods: int


@dataclass(frozen=True)
class DowntimeCauseTheme:
    theme: str
    n_mentions: int
    pct_of_reasons: float


@dataclass(frozen=True)
class DowntimeResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    total_downtime_hours: float
    by_unit: list[DowntimeUnitItem]
    cause_breakdown_method: str  # "tfidf" | "word_frequency" | "categorical" | "unavailable"
    cause_themes: list[DowntimeCauseTheme]
    top_terms: list[tuple[str, int]]
    min_mentions_for_theme: int
    narrative_en: str
    narrative_ar: str


def unavailable_downtime_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> DowntimeResult:
    return DowntimeResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, total_downtime_hours=0.0,
        by_unit=[], cause_breakdown_method="unavailable", cause_themes=[], top_terms=[],
        min_mentions_for_theme=MIN_DOCUMENT_FREQUENCY,
        narrative_en="Downtime analysis not available for this dataset.",
        narrative_ar="تحليل التوقف غير متاح لهذه البيانات.",
    )


def _classify_downtime_cause(scrubbed_text: str) -> Optional[str]:
    lowered = scrubbed_text.lower()
    for theme, spec in _DOWNTIME_THEME_KEYWORDS.items():
        if any(p in lowered for p in spec["direct"]):
            return theme
    for theme, spec in _DOWNTIME_THEME_KEYWORDS.items():
        if any(p in lowered for p in spec["proxy"]):
            return theme
    return None


def _downtime_from_records(records: list[_UnitPeriodRecord], columns_detected: dict[str, bool]) -> DowntimeResult:
    if not columns_detected.get("downtime_hours"):
        return unavailable_downtime_result(
            "Downtime analysis requires a downtime-hours column.", columns_detected,
        )
    usable = [r for r in records if r.downtime_hours is not None]
    if not usable:
        return unavailable_downtime_result(
            "A downtime-hours column was found, but no row had a valid value.", columns_detected,
        )
    total_downtime = sum(r.downtime_hours for r in usable)

    by_unit_map: dict[str, list[_UnitPeriodRecord]] = {}
    for r in usable:
        by_unit_map.setdefault(r.unit, []).append(r)
    by_unit = []
    for unit, recs in by_unit_map.items():
        total_dt = sum(r.downtime_hours for r in recs)
        avail_recs = [r for r in recs if r.hours_available is not None]
        rate = (round(100.0 * total_dt / sum(r.hours_available for r in avail_recs), 2)
                if avail_recs and sum(r.hours_available for r in avail_recs) > 0 else None)
        by_unit.append(DowntimeUnitItem(unit=unit, total_downtime_hours=round(total_dt, 2), downtime_rate_pct=rate, n_periods=len(recs)))
    by_unit.sort(key=lambda i: -i.total_downtime_hours)

    # ── Cause breakdown ──────────────────────────────────────────────────────
    reasons_raw = [r.downtime_reason for r in usable if r.downtime_reason]
    cause_themes: list[DowntimeCauseTheme] = []
    top_terms: list[tuple[str, int]] = []
    method = "unavailable"

    if reasons_raw:
        n_unique = len(set(reasons_raw))
        avg_len = sum(len(t) for t in reasons_raw) / len(reasons_raw)
        looks_categorical = (n_unique / len(reasons_raw)) < _CATEGORICAL_UNIQUE_RATIO_THRESHOLD and avg_len < _CATEGORICAL_AVG_LEN_THRESHOLD

        if looks_categorical:
            method = "categorical"
            counts: dict[str, int] = {}
            for t in reasons_raw:
                key = " ".join(t.split())
                counts[key] = counts.get(key, 0) + 1
            cause_themes = [
                DowntimeCauseTheme(theme=k, n_mentions=v, pct_of_reasons=round(100.0 * v / len(reasons_raw), 1))
                for k, v in counts.items()
            ]
            cause_themes.sort(key=lambda t: -t.n_mentions)
        elif len(reasons_raw) >= MIN_RESPONSES_FOR_AGGREGATE:
            cleaned = [scrub_pii(str(t).strip()) for t in reasons_raw]
            hits: dict[str, int] = {t: 0 for t in _DOWNTIME_THEME_KEYWORDS}
            for text in cleaned:
                theme = _classify_downtime_cause(text)
                if theme:
                    hits[theme] += 1
            cause_themes = [
                DowntimeCauseTheme(theme=t, n_mentions=n, pct_of_reasons=round(100.0 * n / len(reasons_raw), 1))
                for t, n in hits.items() if n >= MIN_DOCUMENT_FREQUENCY
            ]
            cause_themes.sort(key=lambda t: -t.n_mentions)
            if SKLEARN_AVAILABLE:
                top_terms = extract_top_terms_tfidf(cleaned)
                method = "tfidf"
            else:
                top_terms = extract_top_terms_word_frequency(cleaned)
                method = "word_frequency"
        else:
            method = "unavailable"

    narrative_en = f"Total downtime: {total_downtime:,.1f} hour(s) across {len(by_unit)} unit(s)."
    narrative_ar = f"إجمالي التوقف: {total_downtime:,.1f} ساعة عبر {len(by_unit)} وحدة."
    if method == "categorical":
        narrative_en += " Downtime-reason values look already-categorical — showing a direct breakdown, no text-mining applied."
        narrative_ar += " تصنيف مباشر لأسباب التوقف دون تحليل نصي."
    elif method in ("tfidf", "word_frequency"):
        narrative_en += f" Downtime-reason free text analyzed using {method}; themes mentioned by fewer than {MIN_DOCUMENT_FREQUENCY} records are suppressed."
        narrative_ar += " تم تحليل نصوص أسباب التوقف الحرة."
    elif reasons_raw:
        narrative_en += f" Only {len(reasons_raw)} downtime-reason text(s) provided — at least {MIN_RESPONSES_FOR_AGGREGATE} are required for theme analysis."
        narrative_ar += " عدد نصوص أسباب التوقف غير كافٍ لتحليل المواضيع."

    return DowntimeResult(
        available=True, reason=None, columns_detected=columns_detected,
        total_downtime_hours=round(total_downtime, 2), by_unit=by_unit, cause_breakdown_method=method,
        cause_themes=cause_themes, top_terms=top_terms, min_mentions_for_theme=MIN_DOCUMENT_FREQUENCY,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 4. Quality / Defect Analysis ─────────────────────────────────────────

@dataclass(frozen=True)
class QualityUnitItem:
    unit: str
    defect_rate_pct: Optional[float]
    n_periods: int


@dataclass(frozen=True)
class QualityPeriodVariance:
    period: str
    prior_period: str
    defect_rate_prior: float
    defect_rate_current: float
    variance: float
    variance_pct: Optional[float]


@dataclass(frozen=True)
class QualityResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    overall_defect_rate_pct: Optional[float]
    by_unit: list[QualityUnitItem]
    period_variances: list[QualityPeriodVariance]
    min_periods_required: int
    narrative_en: str
    narrative_ar: str


def unavailable_quality_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> QualityResult:
    return QualityResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, overall_defect_rate_pct=None,
        by_unit=[], period_variances=[], min_periods_required=_MIN_PERIODS_FOR_QUALITY_TREND,
        narrative_en="Quality/defect analysis not available for this dataset.",
        narrative_ar="تحليل الجودة/العيوب غير متاح لهذه البيانات.",
    )


def _quality_from_records(records: list[_UnitPeriodRecord], columns_detected: dict[str, bool]) -> QualityResult:
    has_defect_output = columns_detected.get("defect_count") and columns_detected.get("output")
    has_quality_score = columns_detected.get("quality_score")
    if not (has_defect_output or has_quality_score):
        return unavailable_quality_result(
            "Quality analysis requires either a defect-count column plus an output column, or a "
            "direct quality-score/defect-rate column.", columns_detected,
        )

    if has_defect_output:
        usable = [r for r in records if r.defect_count is not None and r.output is not None and r.output > 0]
        if not usable:
            return unavailable_quality_result(
                "Defect-count and output columns were found, but no row had both usable values.",
                columns_detected,
            )
        total_defects = sum(r.defect_count for r in usable)
        total_output = sum(r.output for r in usable)
        overall_rate = round(100.0 * total_defects / total_output, 2) if total_output else None

        by_unit_map: dict[str, list[_UnitPeriodRecord]] = {}
        for r in usable:
            by_unit_map.setdefault(r.unit, []).append(r)
        by_unit = [
            QualityUnitItem(
                unit=u, n_periods=len(recs),
                defect_rate_pct=round(100.0 * sum(r.defect_count for r in recs) / sum(r.output for r in recs), 2),
            )
            for u, recs in by_unit_map.items()
        ]
        by_unit.sort(key=lambda i: -(i.defect_rate_pct or 0))

        period_variances: list[QualityPeriodVariance] = []
        dated = [r for r in usable if r.period is not None]
        if dated:
            period_map: dict[str, list[_UnitPeriodRecord]] = {}
            for r in dated:
                period_map.setdefault(r.period, []).append(r)
            sorted_periods = sorted(period_map.keys())
            period_rate = {
                p: round(100.0 * sum(r.defect_count for r in recs) / sum(r.output for r in recs), 3)
                for p, recs in period_map.items()
            }
            if len(sorted_periods) >= _MIN_PERIODS_FOR_QUALITY_TREND:
                for i in range(1, len(sorted_periods)):
                    prior, curr = sorted_periods[i - 1], sorted_periods[i]
                    prior_rate, curr_rate = period_rate[prior], period_rate[curr]
                    variance = round(curr_rate - prior_rate, 3)
                    variance_pct = round(100.0 * variance / prior_rate, 1) if prior_rate else None
                    period_variances.append(QualityPeriodVariance(
                        period=curr, prior_period=prior, defect_rate_prior=prior_rate,
                        defect_rate_current=curr_rate, variance=variance, variance_pct=variance_pct,
                    ))
                period_variances.sort(key=lambda v: abs(v.variance_pct or 0), reverse=True)
    else:
        usable = [r for r in records if r.quality_score is not None]
        if not usable:
            return unavailable_quality_result(
                "A quality-score column was found, but no row had a valid value.", columns_detected,
            )
        overall_rate = round(sum(r.quality_score for r in usable) / len(usable), 2)
        by_unit_map = {}
        for r in usable:
            by_unit_map.setdefault(r.unit, []).append(r)
        by_unit = [
            QualityUnitItem(unit=u, n_periods=len(recs), defect_rate_pct=round(sum(r.quality_score for r in recs) / len(recs), 2))
            for u, recs in by_unit_map.items()
        ]
        by_unit.sort(key=lambda i: -(i.defect_rate_pct or 0))
        period_variances = []

    narrative_en = f"Overall defect rate: {overall_rate}%." if overall_rate is not None else "Quality metric computed per unit."
    narrative_ar = f"معدل العيوب الإجمالي: {overall_rate}%." if overall_rate is not None else "تم احتساب مؤشر الجودة لكل وحدة."
    if period_variances:
        narrative_en += f" Period-over-period trend computed across {len(period_variances) + 1} periods."
        narrative_ar += f" تم احتساب الاتجاه عبر {len(period_variances) + 1} فترة."

    return QualityResult(
        available=True, reason=None, columns_detected=columns_detected, overall_defect_rate_pct=overall_rate,
        by_unit=by_unit, period_variances=period_variances, min_periods_required=_MIN_PERIODS_FOR_QUALITY_TREND,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 5. Bottleneck Identification ─────────────────────────────────────────

@dataclass(frozen=True)
class BottleneckCandidate:
    unit: str
    n_periods: int
    sufficient_sample: bool
    utilization_pct: Optional[float]
    downtime_rate_pct: Optional[float]
    productivity: Optional[float]
    is_bottleneck: bool


@dataclass(frozen=True)
class BottleneckResult:
    available: bool
    reason: Optional[str]
    min_periods_for_confidence: int
    utilization_gap_pp_threshold: float
    fleet_avg_utilization_pct: Optional[float]
    items: list[BottleneckCandidate]
    narrative_en: str
    narrative_ar: str


def unavailable_bottleneck_result(reason: str) -> BottleneckResult:
    return BottleneckResult(
        available=False, reason=reason, min_periods_for_confidence=_MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE,
        utilization_gap_pp_threshold=_BOTTLENECK_UTILIZATION_GAP_PP, fleet_avg_utilization_pct=None, items=[],
        narrative_en="Bottleneck identification not available for this dataset.",
        narrative_ar="تحديد الاختناقات غير متاح لهذه البيانات.",
    )


def _bottleneck_from_results(utilization: UtilizationResult, downtime: DowntimeResult, productivity: ProductivityResult) -> BottleneckResult:
    if not utilization.available:
        return unavailable_bottleneck_result(
            "Bottleneck identification requires utilization data (hours operated + hours "
            "available) to rank units.",
        )
    util_by_unit = {i.unit: i for i in utilization.items}
    downtime_by_unit = {i.unit: i for i in downtime.by_unit} if downtime.available else {}
    productivity_by_unit = {i.unit: i for i in productivity.items} if productivity.available else {}

    sufficient = [i for i in utilization.items if i.n_periods >= _MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE]
    fleet_avg = round(sum(i.utilization_pct for i in sufficient) / len(sufficient), 2) if sufficient else None

    items = []
    for unit, u in util_by_unit.items():
        sufficient_sample = u.n_periods >= _MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE
        is_bottleneck = (
            sufficient_sample and fleet_avg is not None
            and (fleet_avg - u.utilization_pct) >= _BOTTLENECK_UTILIZATION_GAP_PP
        )
        d = downtime_by_unit.get(unit)
        p = productivity_by_unit.get(unit)
        items.append(BottleneckCandidate(
            unit=unit, n_periods=u.n_periods, sufficient_sample=sufficient_sample,
            utilization_pct=u.utilization_pct, downtime_rate_pct=(d.downtime_rate_pct if d else None),
            productivity=(p.productivity if p else None), is_bottleneck=is_bottleneck,
        ))
    items.sort(key=lambda i: i.utilization_pct if i.utilization_pct is not None else 999)

    n_flagged = sum(1 for i in items if i.is_bottleneck)
    n_insufficient = sum(1 for i in items if not i.sufficient_sample)
    narrative_en = (
        f"{len(items)} unit(s) ranked by utilization. {n_flagged} confidently flagged as a "
        f"bottleneck (>= {_MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE} periods of data AND utilization "
        f">= {_BOTTLENECK_UTILIZATION_GAP_PP} points below the fleet average of "
        f"{fleet_avg}%). {n_insufficient} unit(s) had too few periods to be confidently flagged, "
        "even if their raw numbers look poor."
    )
    narrative_ar = (
        f"تم ترتيب {len(items)} وحدة حسب معدل الاستغلال. تم رصد {n_flagged} وحدة كاختناق بثقة. "
        f"لم يتوفر عدد كافٍ من الفترات لـ {n_insufficient} وحدة لرصدها بثقة."
    )

    return BottleneckResult(
        available=True, reason=None, min_periods_for_confidence=_MIN_PERIODS_FOR_BOTTLENECK_CONFIDENCE,
        utilization_gap_pp_threshold=_BOTTLENECK_UTILIZATION_GAP_PP, fleet_avg_utilization_pct=fleet_avg,
        items=items, narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── 6. Cost per Unit of Operation ────────────────────────────────────────

@dataclass(frozen=True)
class CostPerUnitItem:
    unit: str
    total_cost: float
    total_output: float
    cost_per_unit: float
    n_periods: int


@dataclass(frozen=True)
class CostPerUnitResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    items: list[CostPerUnitItem]
    narrative_en: str
    narrative_ar: str


def unavailable_cost_per_unit_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> CostPerUnitResult:
    return CostPerUnitResult(
        available=False, reason=reason, columns_detected=columns_detected or {}, items=[],
        narrative_en="Cost per unit of operation not available for this dataset.",
        narrative_ar="تكلفة الوحدة التشغيلية غير متاحة لهذه البيانات.",
    )


def _cost_per_unit_from_records(records: list[_UnitPeriodRecord], columns_detected: dict[str, bool]) -> CostPerUnitResult:
    if not (columns_detected.get("cost") and columns_detected.get("output")):
        return unavailable_cost_per_unit_result(
            "Cost per unit of operation requires both an operating-cost column and an output "
            "column.", columns_detected,
        )
    usable = [r for r in records if r.cost is not None and r.output is not None and r.output > 0]
    if not usable:
        return unavailable_cost_per_unit_result(
            "Cost and output columns were found, but no row had both usable values.", columns_detected,
        )
    by_unit: dict[str, list[_UnitPeriodRecord]] = {}
    for r in usable:
        by_unit.setdefault(r.unit, []).append(r)

    items = []
    for unit, recs in by_unit.items():
        total_cost = sum(r.cost for r in recs)
        total_output = sum(r.output for r in recs)
        items.append(CostPerUnitItem(
            unit=unit, total_cost=round(total_cost, 2), total_output=round(total_output, 2),
            cost_per_unit=round(total_cost / total_output, 3), n_periods=len(recs),
        ))
    items.sort(key=lambda i: -i.cost_per_unit)

    narrative_en = f"Cost per unit of output computed for {len(items)} unit(s)."
    narrative_ar = f"تم احتساب تكلفة الوحدة لـ {len(items)} وحدة."

    return CostPerUnitResult(
        available=True, reason=None, columns_detected=columns_detected, items=items,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Top-level bundle ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OperationsIntelligenceResult:
    productivity: ProductivityResult
    utilization: UtilizationResult
    downtime: DowntimeResult
    quality: QualityResult
    bottleneck: BottleneckResult
    cost_per_unit: CostPerUnitResult
    disclaimer_en: str
    disclaimer_ar: str
    confidence: str
    sources: list[str]
    computed_at: str


def _all_unavailable(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> OperationsIntelligenceResult:
    return OperationsIntelligenceResult(
        productivity=unavailable_productivity_result(reason, columns_detected),
        utilization=unavailable_utilization_result(reason, columns_detected),
        downtime=unavailable_downtime_result(reason, columns_detected),
        quality=unavailable_quality_result(reason, columns_detected),
        bottleneck=unavailable_bottleneck_result(reason),
        cost_per_unit=unavailable_cost_per_unit_result(reason, columns_detected),
        disclaimer_en=OPERATIONS_DISCLAIMER_EN, disclaimer_ar=OPERATIONS_DISCLAIMER_AR,
        confidence=OPERATIONS_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


def analyze_operations_intelligence(df: pd.DataFrame) -> OperationsIntelligenceResult:
    """Never raises. Detects columns once, builds per-unit-per-period records
    once, then feeds all 6 items from that shared computation."""
    if df is None or df.empty:
        return _all_unavailable("No data available for operations intelligence analysis.")

    try:
        cols = _detect_columns(df)
        columns_detected = {
            "unit": cols["unit"] is not None, "period": cols["period"] is not None,
            "output": cols["output"] is not None, "hours_operated": cols["hours_operated"] is not None,
            "hours_available": cols["hours_available"] is not None,
            "downtime_hours": cols["downtime_hours"] is not None,
            "downtime_reason": cols["downtime_reason"] is not None,
            "defect_count": cols["defect_count"] is not None, "quality_score": cols["quality_score"] is not None,
            "cost": cols["cost"] is not None,
        }
        if cols["unit"] is None:
            return _all_unavailable(
                "No operational-unit column detected (department/branch/line/machine) — every "
                "figure in this module is keyed by unit, without one nothing can be computed.",
                columns_detected,
            )
        has_any_metric = any([
            columns_detected["output"], columns_detected["hours_operated"], columns_detected["hours_available"],
            columns_detected["downtime_hours"], columns_detected["defect_count"], columns_detected["quality_score"],
            columns_detected["cost"],
        ])
        if not has_any_metric:
            return _all_unavailable(
                "A unit column was detected, but none of output, hours, downtime, quality, or "
                "cost data was found.", columns_detected,
            )

        records = _build_records(df, cols)
        if not records:
            return _all_unavailable(
                "Unit and metric columns were detected, but no row had a usable operational "
                "record.", columns_detected,
            )

        productivity = _productivity_from_records(records, columns_detected)
        utilization = _utilization_from_records(records, columns_detected)
        downtime = _downtime_from_records(records, columns_detected)
        quality = _quality_from_records(records, columns_detected)
        bottleneck = _bottleneck_from_results(utilization, downtime, productivity)
        cost_per_unit = _cost_per_unit_from_records(records, columns_detected)
    except Exception as exc:
        return _all_unavailable(f"Operations intelligence analysis encountered an error: {exc}")

    return OperationsIntelligenceResult(
        productivity=productivity, utilization=utilization, downtime=downtime, quality=quality,
        bottleneck=bottleneck, cost_per_unit=cost_per_unit,
        disclaimer_en=OPERATIONS_DISCLAIMER_EN, disclaimer_ar=OPERATIONS_DISCLAIMER_AR,
        confidence=OPERATIONS_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _productivity_to_dict(r: ProductivityResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "items": [
            {"unit": i.unit, "total_output": i.total_output, "total_hours_operated": i.total_hours_operated,
             "productivity": i.productivity, "n_periods": i.n_periods}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _utilization_to_dict(r: UtilizationResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "items": [
            {"unit": i.unit, "total_hours_operated": i.total_hours_operated,
             "total_hours_available": i.total_hours_available, "utilization_pct": i.utilization_pct,
             "n_periods": i.n_periods}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _downtime_to_dict(r: DowntimeResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "total_downtime_hours": r.total_downtime_hours,
        "by_unit": [
            {"unit": i.unit, "total_downtime_hours": i.total_downtime_hours,
             "downtime_rate_pct": i.downtime_rate_pct, "n_periods": i.n_periods}
            for i in r.by_unit
        ],
        "cause_breakdown_method": r.cause_breakdown_method,
        "cause_themes": [{"theme": t.theme, "n_mentions": t.n_mentions, "pct_of_reasons": t.pct_of_reasons} for t in r.cause_themes],
        "top_terms": [{"term": term, "n": n} for term, n in r.top_terms],
        "min_mentions_for_theme": r.min_mentions_for_theme,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _quality_to_dict(r: QualityResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "overall_defect_rate_pct": r.overall_defect_rate_pct,
        "by_unit": [{"unit": i.unit, "defect_rate_pct": i.defect_rate_pct, "n_periods": i.n_periods} for i in r.by_unit],
        "period_variances": [
            {"period": v.period, "prior_period": v.prior_period, "defect_rate_prior": v.defect_rate_prior,
             "defect_rate_current": v.defect_rate_current, "variance": v.variance, "variance_pct": v.variance_pct}
            for v in r.period_variances
        ],
        "min_periods_required": r.min_periods_required,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _bottleneck_to_dict(r: BottleneckResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "min_periods_for_confidence": r.min_periods_for_confidence,
        "utilization_gap_pp_threshold": r.utilization_gap_pp_threshold,
        "fleet_avg_utilization_pct": r.fleet_avg_utilization_pct,
        "items": [
            {"unit": i.unit, "n_periods": i.n_periods, "sufficient_sample": i.sufficient_sample,
             "utilization_pct": i.utilization_pct, "downtime_rate_pct": i.downtime_rate_pct,
             "productivity": i.productivity, "is_bottleneck": i.is_bottleneck}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _cost_per_unit_to_dict(r: CostPerUnitResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "items": [
            {"unit": i.unit, "total_cost": i.total_cost, "total_output": i.total_output,
             "cost_per_unit": i.cost_per_unit, "n_periods": i.n_periods}
            for i in r.items
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def operations_intelligence_to_dict(r: OperationsIntelligenceResult) -> dict[str, Any]:
    return {
        "productivity": _productivity_to_dict(r.productivity),
        "utilization": _utilization_to_dict(r.utilization),
        "downtime": _downtime_to_dict(r.downtime),
        "quality": _quality_to_dict(r.quality),
        "bottleneck": _bottleneck_to_dict(r.bottleneck),
        "cost_per_unit": _cost_per_unit_to_dict(r.cost_per_unit),
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "confidence": r.confidence, "sources": r.sources, "computed_at": r.computed_at,
    }
