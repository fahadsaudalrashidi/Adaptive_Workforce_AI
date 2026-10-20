"""
AI Business Analyst — Phase 37 (capstone: natural-language Q&A over every
HR module and all 6 Business Intelligence domains).

**This is a security-critical feature. Read this docstring before touching
the dispatch logic.**

═══════════════════════════════════════════════════════════════════════════
ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════

    User question
        │
        ▼
    Deterministic intent classifier (regex/keyword, ALWAYS runs — see
    "Why dispatch is never LLM-driven" below)
        │
        ▼
    Allowlisted Query Registry (QUERY_REGISTRY, a fixed dict literal below)
        │                                          │
        ▼                                          ▼
    Engines (computed_metric evidence)      RAG over project docs
    — calls ONE real, already-existing      (knowledge_context evidence)
      engine function per registry entry.   — TF-IDF retrieval over this
      Never eval, never dynamic dispatch,     session's own PHASE_*.md /
      never free-form code generation.        BUSINESS_INTELLIGENCE_SUITE_
                                               OVERVIEW.md corpus. NEVER
                                               reads live business data.
        │                                          │
        └──────────────► Unified Evidence Pack ◄───┘
                                │
                                ▼
                    Local LLM (Ollama, optional) — PHRASING ONLY,
                    never dispatch. A numeric guard verifies every
                    number in the LLM's phrased answer against the
                    Evidence Pack; any untraceable number discards
                    the LLM phrasing and falls back to the
                    deterministic template.
                                │
                                ▼
                    AnalystAnswer (Answer / Key Evidence / Source
                    Engine / Data Period / Evidence Level / Limitations)

**Why dispatch is never LLM-driven.** An earlier design considered asking
the LLM to classify intent and pick a registry key. Rejected: that would
make the LLM's raw output control which code path executes — precisely
the "LLM decides what to compute" failure mode Section 6 of this phase's
brief prohibits. Instead, intent classification and registry lookup are
100% deterministic regex/keyword matching, identical whether or not Ollama
is available. The LLM (when present) touches ONLY the already-verified
Evidence Pack's numbers to produce prose — it is structurally incapable of
choosing what gets computed, because that decision is made and finalized
before the LLM is ever invoked.

═══════════════════════════════════════════════════════════════════════════
EVIDENCE PACK — HARD SEPARATION OF THE TWO EVIDENCE TYPES
═══════════════════════════════════════════════════════════════════════════

Every Evidence Pack entry is EITHER a `ComputedMetricEvidence` (a real
number from calling an existing engine, carries an Evidence Level) OR a
`KnowledgeContextEvidence` (a retrieved documentation excerpt, carries a
source file/section, structurally has NO evidence_level field and NO
numeric business-metric field at all). This is enforced by the type
system, not just convention: `KnowledgeContextEvidence` cannot carry an
Evidence Level because the dataclass has no such attribute, so a RAG
excerpt that happens to contain a number (e.g. "Article 84", "a 50%
premium") can never be rendered with a 🟢/🟡/🔴 badge or presented in the
"Key Evidence" numeric-metric slot — see `test_ai_business_analyst_engine.
py::TestEvidencePackSeparation::test_rag_chunk_number_never_becomes_metric`.

═══════════════════════════════════════════════════════════════════════════
RAG — WHY TF-IDF, NOT A LOCAL EMBEDDING MODEL
═══════════════════════════════════════════════════════════════════════════

Considered a local embedding model (e.g. sentence-transformers) + vector
store. Rejected in favor of TF-IDF for three concrete reasons:
  1. Genuine precedent reuse. This session already built and shipped a
     TF-IDF retrieval mechanism three times (exit_interview_intelligence_
     engine.py's `extract_top_terms_tfidf`, reused verbatim by Logistics
     Returns and Operations Downtime). Reusing the SAME scikit-learn
     machinery for a fourth, structurally similar job (finding the most
     relevant text for a query) is consistent, not a new dependency.
  2. Zero new installs. A local embedding model requires downloading
     model weights this environment has not necessarily fetched. TF-IDF
     needs only scikit-learn, already a platform dependency — fully
     offline with nothing to pull, consistent with `offline_mode_guard.py`
     and this phase's explicit "do not install without approval" rule.
  3. The corpus fits the tool. ~36 structured markdown phase reports with
     clear headers/sections is exactly the kind of corpus where exact
     terminology retrieval (TF-IDF) outperforms semantic-paraphrase
     retrieval (embeddings) for "why does X use formula Y"-style
     questions — the answer is almost always phrased using the same
     words the question uses ("gratuity", "Article 84", "Welch's t-test").

Unlike the exit-interview/returns/downtime reuse (which reused
`MIN_DOCUMENT_FREQUENCY=3` to suppress rare mentions for PRIVACY), this
module does NOT reuse that constant — RAG retrieval over a fixed,
already-published documentation corpus has no re-identification risk, and
suppressing rare/distinctive terms here would make retrieval WORSE (a
document's most specific terms are exactly what makes TF-IDF find it).

═══════════════════════════════════════════════════════════════════════════
CROSS-DOMAIN QUERIES — ADAPTED RECORD-ID JOIN PATTERN
═══════════════════════════════════════════════════════════════════════════

Reuses the Phase 8 architectural precedent (`contract_expiry_engine.py`'s
`get_expiry_signals_by_record_id()` / `nitaqat_compliance_engine.py`'s
`get_saudi_status_by_record_id()`): each source engine is called
independently, neither engine imports the other, and only ONE layer (here,
this module — playing the same role the route layer plays for the Phase 8
pair) is allowed to combine their outputs, joining on a REAL shared key and
returning "insufficient data" rather than guessing when no real join is
possible. The one adaptation: Phase 8's join key is a hashed employee
record ID; this module's only implemented cross-domain pairing (overtime
cost vs. operational downtime) has no shared employee identity between the
two domains — the real, honest join key is DEPARTMENT NAME, normalized via
`department_normalizer.normalize_department_series()` on both sides
independently. If the two uploads' department names don't overlap after
normalization, this module reports zero matched records rather than
fabricating a relationship — see
`test_ai_business_analyst_engine.py::TestCrossDomainCorrelation`.

═══════════════════════════════════════════════════════════════════════════
CORRELATION SAFETY
═══════════════════════════════════════════════════════════════════════════

`_pearson_correlation()` below never returns a correlation coefficient
computed on fewer than `_MIN_N_FOR_CORRELATION` (5) matched observations —
returns None instead, same "never fabricate a statistic from too few
points" discipline as `pay_equity_engine.py`'s Welch's t-test (scipy-
optional import guard, same never-fabricate-on-insufficient-N principle).
5, not pay_equity's 20, because this module correlates DEPARTMENT-level
aggregates (a company realistically has 5-15 departments, not 20+), so
reusing the employee-level threshold would make cross-department
correlation permanently unavailable regardless of data quality — a
different, disclosed, department-appropriate floor for a different
statistical unit of analysis.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series
from backend.core.exit_interview_intelligence_engine import (
    SKLEARN_AVAILABLE,
)
from backend.core.financial_intelligence_reporting_engine import analyze_financial_intelligence
from backend.core.accounting_intelligence_engine import analyze_accounting_intelligence
from backend.core.inventory_intelligence_engine import analyze_inventory_intelligence
from backend.core.procurement_intelligence_engine import analyze_procurement_intelligence
from backend.core.logistics_intelligence_engine import analyze_logistics_intelligence
from backend.core.operations_intelligence_engine import analyze_operations_intelligence
from backend.core.overtime_cost_intelligence_engine import analyze_overtime_cost_intelligence

try:
    from scipy import stats as _scipy_stats
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = None  # type: ignore[assignment,misc]
    cosine_similarity = None  # type: ignore[assignment]

# ── Constants ────────────────────────────────────────────────────────────────

SUPPORTED_INTENTS: tuple[str, ...] = (
    "WHY_CHANGE", "TOP", "BOTTOM", "COMPARE", "TREND", "TOTAL", "AVERAGE", "RANK",
)

EVIDENCE_HIGH = "high"
EVIDENCE_LIMITED = "limited"
EVIDENCE_INSUFFICIENT = "insufficient"

_MIN_N_FOR_CORRELATION = 5

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_TIMEOUT_SECS = 60

# Accepts an ASCII hyphen-minus OR a Unicode minus sign (U+2212, which some
# LLM output/fonts use for negative numbers) as the sign character.
_NUMBER_PATTERN = re.compile(r"[-−]?\d[\d,]*\.?\d*")

_INJECTION_PATTERNS = re.compile(
    r"\b(ignore (all|previous|prior|above) instructions?|disregard (all|previous|your) instructions?|"
    r"run (this|the following|a)( \w+){0,2} command|execute (this|the following|arbitrary)( \w+){0,2} (code|command|script)|"
    r"you are now|act as|jailbreak|system prompt|reveal your (prompt|instructions)|"
    r"drop table|delete from|rm -rf|import os|subprocess|os\.system|exec\(|eval\()\b",
    re.I,
)

_KNOWLEDGE_TRIGGER_PATTERN = re.compile(
    r"\b(why does|why is|how does|how is|what does .* mean|what is the (methodology|formula|source|"
    r"citation|basis|convention)|which (law|article|regulation|standard)|explain|methodology|"
    r"cite|citation|source(d)? (from|to)|confidence level mean)\b",
    re.I,
)

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "WHY_CHANGE": ("why did", "why has", "why was", "what caused", "reason for the change", "reason it changed"),
    "COMPARE": ("compare", " vs ", " versus ", "difference between", "correlate", "correlation", "relate to"),
    "TOP": ("top", "highest", "best", "most", "largest", "biggest"),
    "BOTTOM": ("bottom", "lowest", "worst", "least", "smallest", "bottleneck", "underperform"),
    "TREND": ("trend", "over time", "trajectory", "increasing", "decreasing", "month over month", "period over period"),
    "RANK": ("rank", "ranking", "ranked", "list all", "order them", "order by"),
    "AVERAGE": ("average", "mean", "typical", "on average", "on time", "on-time", "rate"),
    "TOTAL": ("total", "sum", "how much", "overall", "grand total", "trial balance", "balanced", "how many", "profit", "net profit", "p&l"),
}
# Priority order for resolving overlaps (e.g. "why did the trend change" -> WHY_CHANGE, not TREND).
_INTENT_PRIORITY = ("WHY_CHANGE", "COMPARE", "RANK", "TOP", "BOTTOM", "TREND", "AVERAGE", "TOTAL")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Evidence Pack ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ComputedMetricEvidence:
    """A real number traced to one existing engine call. `kind` is a
    literal discriminator used by rendering code — never re-typed as
    knowledge_context."""
    kind: str = field(default="computed_metric", init=False)
    label: str = ""
    value: Any = None
    unit: Optional[str] = None
    source_engine: str = ""
    data_period: Optional[str] = None
    evidence_level: str = EVIDENCE_INSUFFICIENT
    evidence_level_reason: str = ""


@dataclass(frozen=True)
class KnowledgeContextEvidence:
    """A retrieved documentation excerpt. Structurally carries NO numeric
    business-metric field and NO evidence_level — a RAG chunk can never be
    mistaken for a computed metric because the type has no slot for either
    a formal value or a 🟢/🟡/🔴 badge."""
    kind: str = field(default="knowledge_context", init=False)
    label: str = ""
    excerpt: str = ""
    source_file: str = ""
    source_section: Optional[str] = None
    relevance_score: float = 0.0


EvidenceEntry = Any  # ComputedMetricEvidence | KnowledgeContextEvidence


# ── Query Registry types ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class QueryOutcome:
    available: bool
    reason: Optional[str]
    metrics: list[ComputedMetricEvidence]
    source_engine: str
    data_period: Optional[str] = None


def unavailable_outcome(reason: str, source_engine: str) -> QueryOutcome:
    return QueryOutcome(available=False, reason=reason, metrics=[], source_engine=source_engine)


@dataclass(frozen=True)
class QueryDefinition:
    query_id: str
    intent: str
    domain: str
    keywords: tuple[str, ...]
    description_en: str
    description_ar: str
    handler: Callable[[dict[str, Any]], QueryOutcome]


# ── Domain analyzers (the ONLY functions the registry may call) ────────────

_DOMAIN_ANALYZERS: dict[str, Callable[[pd.DataFrame], Any]] = {
    "financial": analyze_financial_intelligence,
    "accounting": analyze_accounting_intelligence,
    "inventory": analyze_inventory_intelligence,
    "procurement": analyze_procurement_intelligence,
    "logistics": analyze_logistics_intelligence,
    "operations": analyze_operations_intelligence,
    "hr_overtime": analyze_overtime_cost_intelligence,
}


def analyze_uploaded_files(files: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    For each uploaded (filename, dataframe), try every registered domain
    analyzer and keep the domain's result under its domain key wherever
    that domain reports it found a genuinely usable signal in the file
    (mirrors this session's established "let the data speak, don't force
    the user to pick a mode" fuzzy-detection philosophy). A single file
    may legitimately match zero, one, or (rarely) more than one domain;
    the caller only ever sees domains that actually produced a usable
    result. Never raises — a domain whose analyzer errors on a given file
    is simply skipped for that file.
    """
    domain_results: dict[str, Any] = {}
    for _filename, df in files.items():
        for domain, analyzer in _DOMAIN_ANALYZERS.items():
            if domain in domain_results:
                continue  # first successful file for a domain wins; keep it simple and auditable
            try:
                result = analyzer(df)
            except Exception:
                continue
            if _result_has_any_available_section(result):
                domain_results[domain] = result
    return domain_results


def _result_has_any_available_section(result: Any) -> bool:
    """True if `result` (or any of its dataclass sub-results) reports
    available=True. Handles both single-result engines (overtime) and
    bundle engines (financial/accounting/.../operations)."""
    if result is None:
        return False
    direct = getattr(result, "available", None)
    if direct is True:
        return True
    if direct is False and not hasattr(result, "__dataclass_fields__"):
        return False
    for f in getattr(result, "__dataclass_fields__", {}):
        sub = getattr(result, f, None)
        if hasattr(sub, "available") and getattr(sub, "available") is True:
            return True
    return False


# ── Statistics (correlation safety) ─────────────────────────────────────────

def _pearson_correlation(paired_x: list[float], paired_y: list[float]) -> Optional[tuple[float, float, int]]:
    """Returns (r, p_value, n) or None. Never fabricates a correlation from
    fewer than _MIN_N_FOR_CORRELATION matched observations, and never runs
    at all without scipy — same never-fabricate discipline as pay_equity_
    engine.py's _welch_t_test()."""
    n = len(paired_x)
    if n != len(paired_y) or n < _MIN_N_FOR_CORRELATION or not _SCIPY_AVAILABLE:
        return None
    try:
        r, p = _scipy_stats.pearsonr(paired_x, paired_y)
        if r != r or p != p:  # NaN
            return None
        return round(float(r), 4), round(float(p), 4), n
    except Exception:
        return None


# ── Registry handlers ────────────────────────────────────────────────────────
# Each handler calls exactly one already-computed domain result (never a
# fresh engine call, never a second code path) and extracts one metric.

def _financial_total_revenue(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("financial")
    src = "financial_intelligence_reporting_engine.analyze_financial_intelligence"
    if r is None or not r.available:
        return unavailable_outcome("No Financial Intelligence data uploaded, or the file lacks revenue-classifiable transactions.", src)
    level = EVIDENCE_HIGH if r.n_excluded_unclassified == 0 else EVIDENCE_LIMITED
    reason = "All transactions with a valid amount were classified." if level == EVIDENCE_HIGH else f"{r.n_excluded_unclassified} transaction(s) could not be classified as revenue or expense."
    period = _period_range([p.period for p in r.period_figures])
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Total Revenue", value=r.total_revenue_sar, unit="SAR", source_engine=src,
        data_period=period, evidence_level=level, evidence_level_reason=reason,
    )], src, period)


def _financial_total_expense(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("financial")
    src = "financial_intelligence_reporting_engine.analyze_financial_intelligence"
    if r is None or not r.available:
        return unavailable_outcome("No Financial Intelligence data uploaded, or the file lacks expense-classifiable transactions.", src)
    period = _period_range([p.period for p in r.period_figures])
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Total Expense", value=r.total_expense_sar, unit="SAR", source_engine=src,
        data_period=period, evidence_level=EVIDENCE_HIGH, evidence_level_reason="Computed from classified transactions.",
    )], src, period)


def _financial_net_pnl(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("financial")
    src = "financial_intelligence_reporting_engine.analyze_financial_intelligence"
    if r is None or not r.available:
        return unavailable_outcome("No Financial Intelligence data uploaded.", src)
    period = _period_range([p.period for p in r.period_figures])
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Net P&L", value=r.net_pnl_sar, unit="SAR", source_engine=src,
        data_period=period, evidence_level=EVIDENCE_HIGH,
        evidence_level_reason="Revenue minus expense from your own uploaded categorization — not a certified financial statement.",
    )], src, period)


def _financial_top_expense_category(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("financial")
    src = "financial_intelligence_reporting_engine.analyze_financial_intelligence"
    if r is None or not r.available or not r.ratios or r.ratios.top_expense_category is None:
        return unavailable_outcome("No Financial Intelligence expense-category data uploaded.", src)
    period = _period_range([p.period for p in r.period_figures])
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Top Expense Category", value=r.ratios.top_expense_category, unit=f"{r.ratios.top_expense_category_share_pct}% of expense",
        source_engine=src, data_period=period, evidence_level=EVIDENCE_HIGH,
        evidence_level_reason="Highest-total expense category from your own uploaded categorization.",
    )], src, period)


def _accounting_trial_balance(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("accounting")
    src = "accounting_intelligence_engine.analyze_trial_balance"
    if r is None or not r.trial_balance.available:
        return unavailable_outcome("No Accounting Intelligence data uploaded, or the file lacks real, separate debit/credit columns.", src)
    tb = r.trial_balance
    level = EVIDENCE_HIGH
    return QueryOutcome(True, None, [
        ComputedMetricEvidence(label="Trial Balance Difference", value=tb.difference_sar, unit="SAR", source_engine=src,
                                evidence_level=level, evidence_level_reason=f"Balanced within SAR {tb.tolerance_sar} tolerance." if tb.is_balanced else "Debits and credits do not match — a real data-quality signal."),
        ComputedMetricEvidence(label="Is Balanced", value=tb.is_balanced, unit=None, source_engine=src, evidence_level=level, evidence_level_reason=""),
    ], src)


def _accounting_anomaly_count(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("accounting")
    src = "accounting_intelligence_engine.analyze_journal_anomalies"
    if r is None or not r.journal_anomalies.available:
        return unavailable_outcome("No Accounting Intelligence data uploaded, or too few entries per account for anomaly detection.", src)
    ja = r.journal_anomalies
    n = len(ja.amount_anomalies) + len(ja.duplicate_candidates)
    level = EVIDENCE_HIGH if ja.n_accounts_suppressed_small_sample == 0 else EVIDENCE_LIMITED
    reason = "All accounts had enough entries for anomaly detection." if level == EVIDENCE_HIGH else f"{ja.n_accounts_suppressed_small_sample} account(s) had too few entries (below the minimum sample floor) and were excluded."
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Journal Anomalies Flagged", value=n, unit="entries", source_engine=src,
        evidence_level=level, evidence_level_reason=reason,
    )], src)


def _inventory_dead_stock_count(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("inventory")
    src = "inventory_intelligence_engine.analyze_inventory_intelligence"
    if r is None or not r.stock_aging.available:
        return unavailable_outcome("No Inventory Intelligence movement-history data uploaded (dead-stock aging needs real transaction dates).", src)
    n = r.stock_aging.tier_counts.get("dead_stock", 0)
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Dead Stock Items", value=n, unit="items", source_engine=src, data_period=r.stock_aging.as_of_date,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason="180+ days since last movement — this platform's own disclosed threshold.",
    )], src, r.stock_aging.as_of_date)


def _inventory_top_value_item(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("inventory")
    src = "inventory_intelligence_engine.analyze_inventory_intelligence"
    if r is None or not r.abc_analysis.available or not r.abc_analysis.items:
        return unavailable_outcome("No Inventory Intelligence value data uploaded (needs quantity and unit cost).", src)
    top = r.abc_analysis.items[0]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Highest-Value Item ({top.sku})", value=top.value_on_hand, unit="SAR", source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason="Real quantity x unit cost from your uploaded data.",
    )], src)


def _inventory_stockout_risk_count(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("inventory")
    src = "inventory_intelligence_engine.analyze_inventory_intelligence"
    if r is None or not r.overstock_stockout.available:
        return unavailable_outcome("No Inventory Intelligence movement-history data uploaded (stockout risk needs demand history).", src)
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Items at Stockout Risk", value=r.overstock_stockout.n_stockout_risk, unit="items", source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason="Current stock below computed safety stock / days-of-supply floor.",
    )], src)


def _procurement_top_supplier_spend(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("procurement")
    src = "procurement_intelligence_engine.analyze_procurement_intelligence"
    if r is None or not r.supplier_spend.available or not r.supplier_spend.items:
        return unavailable_outcome("No Procurement Intelligence spend data uploaded.", src)
    top = r.supplier_spend.items[0]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Top Supplier by Spend ({top.supplier})", value=top.total_spend, unit="SAR", source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason=f"Real spend across {top.n_pos} purchase order(s).",
    )], src)


def _procurement_cost_reduction_count(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("procurement")
    src = "procurement_intelligence_engine.analyze_procurement_intelligence"
    if r is None or not r.cost_reduction.available:
        return unavailable_outcome("No Procurement Intelligence multi-supplier price data uploaded.", src)
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Cost-Reduction Opportunities", value=len(r.cost_reduction.items), unit="items", source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason=f"Items sourced from 2+ suppliers with a >= {r.cost_reduction.threshold_pct}% price spread.",
    )], src)


def _procurement_price_trend_top(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("procurement")
    src = "procurement_intelligence_engine.analyze_procurement_intelligence"
    if r is None or not r.price_trend.available or not r.price_trend.items:
        return unavailable_outcome("No Procurement Intelligence supplier-item pair had enough purchase-order history for a price trend.", src)
    top = r.price_trend.items[0]
    level = EVIDENCE_HIGH
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Largest Price Move ({top.supplier} / {top.sku})", value=top.overall_change_pct, unit="% change", source_engine=src,
        evidence_level=level, evidence_level_reason=f"Computed from {top.n_pos} real purchase orders across {top.n_periods} periods (minimum-sample floor already applied).",
    )], src)


def _logistics_on_time_rate(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("logistics")
    src = "logistics_intelligence_engine.analyze_logistics_intelligence"
    if r is None or not r.delivery_time.available:
        return unavailable_outcome("No Logistics Intelligence delivery-date data uploaded.", src)
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="On-Time Delivery Rate", value=r.delivery_time.on_time_pct, unit="%", source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason=f"{r.delivery_time.n_on_time} of {r.delivery_time.n_with_complete_dates} shipments with complete delivery-date data.",
    )], src)


def _logistics_top_carrier(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("logistics")
    src = "logistics_intelligence_engine.analyze_logistics_intelligence"
    if r is None or not r.carrier_route_performance.available or not r.carrier_route_performance.carrier_items:
        return unavailable_outcome("No Logistics Intelligence carrier performance data uploaded.", src)
    top = r.carrier_route_performance.carrier_items[0]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Top Carrier ({top.carrier})", value=top.composite_score, unit="composite score (constructed heuristic, not a validated rating)",
        source_engine=src, evidence_level=EVIDENCE_LIMITED,
        evidence_level_reason="Constructed heuristic combining on-time % and relative cost — not a validated/certified carrier rating.",
    )], src)


def _logistics_bottom_carrier(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("logistics")
    src = "logistics_intelligence_engine.analyze_logistics_intelligence"
    if r is None or not r.carrier_route_performance.available or not r.carrier_route_performance.carrier_items:
        return unavailable_outcome("No Logistics Intelligence carrier performance data uploaded.", src)
    bottom = r.carrier_route_performance.carrier_items[-1]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Bottom Carrier ({bottom.carrier})", value=bottom.composite_score, unit="composite score (constructed heuristic, not a validated rating)",
        source_engine=src, evidence_level=EVIDENCE_LIMITED,
        evidence_level_reason="Constructed heuristic combining on-time % and relative cost — not a validated/certified carrier rating.",
    )], src)


def _logistics_carrier_ranking(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("logistics")
    src = "logistics_intelligence_engine.analyze_logistics_intelligence"
    if r is None or not r.carrier_route_performance.available:
        return unavailable_outcome("No Logistics Intelligence carrier performance data uploaded.", src)
    metrics = [
        ComputedMetricEvidence(label=f"{i+1}. {c.carrier}", value=c.composite_score, unit="composite score", source_engine=src,
                                evidence_level=EVIDENCE_LIMITED, evidence_level_reason="Constructed heuristic, not a validated rating.")
        for i, c in enumerate(r.carrier_route_performance.carrier_items)
    ]
    return QueryOutcome(True, None, metrics, src)


def _operations_bottleneck_unit(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("operations")
    src = "operations_intelligence_engine.analyze_operations_intelligence"
    if r is None or not r.bottleneck.available:
        return unavailable_outcome("No Operations Intelligence utilization data uploaded.", src)
    flagged = [i for i in r.bottleneck.items if i.is_bottleneck]
    if not flagged:
        return QueryOutcome(True, None, [ComputedMetricEvidence(
            label="Bottleneck Unit", value="None confidently flagged", unit=None, source_engine=src,
            evidence_level=EVIDENCE_LIMITED,
            evidence_level_reason=f"No unit both cleared the {r.bottleneck.min_periods_for_confidence}-period minimum-sample floor AND fell >= {r.bottleneck.utilization_gap_pp_threshold} points below the fleet average.",
        )], src)
    top = flagged[0]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Bottleneck Unit ({top.unit})", value=top.utilization_pct, unit="% utilization", source_engine=src,
        evidence_level=EVIDENCE_HIGH,
        evidence_level_reason=f"{top.n_periods} periods of data (>= the {r.bottleneck.min_periods_for_confidence}-period confidence floor), {r.bottleneck.fleet_avg_utilization_pct - top.utilization_pct:.1f} points below the fleet average.",
    )], src)


def _operations_utilization_ranking(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("operations")
    src = "operations_intelligence_engine.analyze_operations_intelligence"
    if r is None or not r.utilization.available:
        return unavailable_outcome("No Operations Intelligence hours-operated/hours-available data uploaded.", src)
    metrics = [
        ComputedMetricEvidence(label=f"{i+1}. {u.unit}", value=u.utilization_pct, unit="%", source_engine=src,
                                evidence_level=EVIDENCE_HIGH, evidence_level_reason="Real hours operated / hours available.")
        for i, u in enumerate(r.utilization.items)
    ]
    return QueryOutcome(True, None, metrics, src)


def _operations_quality_trend(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("operations")
    src = "operations_intelligence_engine.analyze_operations_intelligence"
    if r is None or not r.quality.available or not r.quality.period_variances:
        return unavailable_outcome("No Operations Intelligence quality-trend data uploaded (needs >=2 periods of defect/output data).", src)
    latest = r.quality.period_variances[-1]
    period = f"{latest.prior_period} to {latest.period}"
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Latest Defect-Rate Change", value=latest.variance_pct, unit="% change", source_engine=src,
        data_period=period, evidence_level=EVIDENCE_HIGH,
        evidence_level_reason=f"Defect rate moved from {latest.defect_rate_prior}% to {latest.defect_rate_current}%.",
    )], src, period)


def _hr_overtime_total_cost(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("hr_overtime")
    src = "overtime_cost_intelligence_engine.analyze_overtime_cost_intelligence"
    if r is None or not r.available:
        return unavailable_outcome("No HR overtime data uploaded (needs an overtime hours/flag column).", src)
    level = EVIDENCE_HIGH if r.hours_source == "observed" and r.wage_source == "observed" else EVIDENCE_LIMITED
    reason = "Real observed overtime-hours and salary columns." if level == EVIDENCE_HIGH else f"hours_source={r.hours_source}, wage_source={r.wage_source} — at least one figure is estimated, not directly observed."
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label="Total Monthly Overtime Cost", value=r.org_monthly_overtime_cost_sar, unit="SAR/month", source_engine=src,
        evidence_level=level, evidence_level_reason=reason,
    )], src)


def _hr_overtime_top_department(d: dict[str, Any]) -> QueryOutcome:
    r = d.get("hr_overtime")
    src = "overtime_cost_intelligence_engine.analyze_overtime_cost_intelligence"
    if r is None or not r.available or not r.department_breakdown:
        return unavailable_outcome("No HR overtime department-level data uploaded.", src)
    top = r.department_breakdown[0]
    return QueryOutcome(True, None, [ComputedMetricEvidence(
        label=f"Top Overtime Department ({top.department})", value=top.monthly_overtime_cost_sar, unit="SAR/month", source_engine=src,
        evidence_level=EVIDENCE_HIGH if r.hours_source == "observed" else EVIDENCE_LIMITED,
        evidence_level_reason=f"{top.n_overtime_employees} of {top.n_employees} employees flagged for overtime in this department.",
    )], src)


def _crossdomain_overtime_vs_downtime(d: dict[str, Any]) -> QueryOutcome:
    """Real cross-domain join: overtime cost per department (HR) vs.
    downtime hours per unit (Operations), joined on the department/unit
    NAME after independent normalization on each side — the department-
    key adaptation of the Phase 8 record-ID join pattern (see module
    docstring). Never joins on assumed/positional identity."""
    hr = d.get("hr_overtime")
    ops = d.get("operations")
    src = "ai_business_analyst_engine._crossdomain_overtime_vs_downtime (joins overtime_cost_intelligence_engine + operations_intelligence_engine)"
    if hr is None or not hr.available or not hr.department_breakdown:
        return unavailable_outcome("No HR overtime department data uploaded for the cross-domain comparison.", src)
    if ops is None or not ops.downtime.available or not ops.downtime.by_unit:
        return unavailable_outcome("No Operations Intelligence downtime data uploaded for the cross-domain comparison.", src)

    hr_keys = normalize_department_series(pd.Series([x.department for x in hr.department_breakdown]))
    ops_keys = normalize_department_series(pd.Series([x.unit for x in ops.downtime.by_unit]))
    hr_by_key = {k: x for k, x in zip(hr_keys.normalized_keys, hr.department_breakdown)}
    ops_by_key = {k: x for k, x in zip(ops_keys.normalized_keys, ops.downtime.by_unit)}
    matched_keys = sorted(set(hr_by_key) & set(ops_by_key))

    if not matched_keys:
        return unavailable_outcome(
            f"HR overtime departments ({', '.join(x.department for x in hr.department_breakdown)}) and "
            f"Operations units ({', '.join(x.unit for x in ops.downtime.by_unit)}) share no matching "
            "name after normalization — a real join is not possible, so no relationship is reported "
            "(never joined on assumed/positional identity).", src,
        )

    paired_x = [hr_by_key[k].monthly_overtime_cost_sar for k in matched_keys]
    paired_y = [ops_by_key[k].total_downtime_hours for k in matched_keys]
    corr = _pearson_correlation(paired_x, paired_y)

    metrics = [ComputedMetricEvidence(
        label="Matched Departments/Units", value=", ".join(matched_keys), unit=None, source_engine=src,
        evidence_level=EVIDENCE_HIGH, evidence_level_reason=f"{len(matched_keys)} department(s)/unit(s) matched by real normalized name on both sides.",
    )]
    if corr is None:
        metrics.append(ComputedMetricEvidence(
            label="Overtime Cost vs. Downtime Correlation", value=None, unit=None, source_engine=src,
            evidence_level=EVIDENCE_INSUFFICIENT,
            evidence_level_reason=(
                f"Only {len(matched_keys)} matched department(s)/unit(s) — fewer than the "
                f"{_MIN_N_FOR_CORRELATION} required for a correlation to be reported. This is a "
                "hard floor, not a formatting choice: no correlation coefficient is computed or "
                "implied below it."
            ),
        ))
        return QueryOutcome(True, None, metrics, src)

    r_val, p_val, n = corr
    significant = p_val < 0.05
    metrics.append(ComputedMetricEvidence(
        label="Overtime Cost vs. Downtime Correlation (Pearson r)", value=r_val, unit=f"p={p_val}, n={n}",
        source_engine=src, evidence_level=EVIDENCE_HIGH if significant else EVIDENCE_LIMITED,
        evidence_level_reason=(
            f"Statistically significant at p<0.05 (n={n})." if significant else
            f"NOT statistically significant at p<0.05 (n={n}) — reported as a co-occurrence "
            "observation only; this is correlation, not causation, and is not significant evidence "
            "of any real relationship."
        ),
    ))
    return QueryOutcome(True, None, metrics, src)


def _period_range(periods: list[str]) -> Optional[str]:
    clean = sorted(p for p in periods if p)
    if not clean:
        return None
    return clean[0] if clean[0] == clean[-1] else f"{clean[0]} to {clean[-1]}"


# ── The Allowlisted Query Registry ──────────────────────────────────────────

QUERY_REGISTRY: dict[str, QueryDefinition] = {
    "financial.total_revenue": QueryDefinition(
        "financial.total_revenue", "TOTAL", "financial",
        ("revenue", "sales", "income"), "Total revenue", "إجمالي الإيرادات", _financial_total_revenue,
    ),
    "financial.total_expense": QueryDefinition(
        "financial.total_expense", "TOTAL", "financial",
        ("expense", "expenses", "spend", "spending"), "Total expense", "إجمالي المصروفات", _financial_total_expense,
    ),
    "financial.net_pnl": QueryDefinition(
        "financial.net_pnl", "TOTAL", "financial",
        ("profit", "loss", "p&l", "net income", "net pnl"), "Net P&L", "صافي الربح/الخسارة", _financial_net_pnl,
    ),
    "financial.top_expense_category": QueryDefinition(
        "financial.top_expense_category", "TOP", "financial",
        ("expense category", "spending category", "cost category"), "Top expense category", "أعلى فئة مصروف", _financial_top_expense_category,
    ),
    "accounting.trial_balance": QueryDefinition(
        "accounting.trial_balance", "TOTAL", "accounting",
        ("trial balance", "balanced", "debit", "credit"), "Trial balance status", "حالة ميزان المراجعة", _accounting_trial_balance,
    ),
    "accounting.anomaly_count": QueryDefinition(
        "accounting.anomaly_count", "TOTAL", "accounting",
        ("anomaly", "anomalies", "duplicate", "journal entries flagged", "suspicious entries"),
        "Journal entry anomalies", "شذوذ القيود اليومية", _accounting_anomaly_count,
    ),
    "inventory.dead_stock_count": QueryDefinition(
        "inventory.dead_stock_count", "TOTAL", "inventory",
        ("dead stock", "slow moving", "stale inventory"), "Dead stock count", "عدد المخزون الراكد", _inventory_dead_stock_count,
    ),
    "inventory.top_value_item": QueryDefinition(
        "inventory.top_value_item", "TOP", "inventory",
        ("highest value item", "most valuable item", "top item by value"), "Top item by value", "أعلى صنف قيمة", _inventory_top_value_item,
    ),
    "inventory.stockout_risk_count": QueryDefinition(
        "inventory.stockout_risk_count", "TOTAL", "inventory",
        ("stockout", "stock out", "out of stock risk", "running low"), "Items at stockout risk", "أصناف معرضة لخطر النفاد", _inventory_stockout_risk_count,
    ),
    "procurement.top_supplier_spend": QueryDefinition(
        "procurement.top_supplier_spend", "TOP", "procurement",
        ("top supplier", "biggest supplier", "highest spend supplier"), "Top supplier by spend", "أعلى مورد إنفاقاً", _procurement_top_supplier_spend,
    ),
    "procurement.cost_reduction_count": QueryDefinition(
        "procurement.cost_reduction_count", "TOTAL", "procurement",
        ("cost reduction", "cheaper supplier", "save money on purchasing", "alternative supplier"),
        "Cost-reduction opportunities", "فرص خفض التكلفة", _procurement_cost_reduction_count,
    ),
    "procurement.price_trend_top": QueryDefinition(
        "procurement.price_trend_top", "WHY_CHANGE", "procurement",
        ("price increase", "price rose", "price change", "why did the price", "price went up", "price went down"),
        "Largest supplier price move", "أكبر تغيّر في سعر المورد", _procurement_price_trend_top,
    ),
    "logistics.on_time_rate": QueryDefinition(
        "logistics.on_time_rate", "AVERAGE", "logistics",
        ("on time", "on-time", "delivery rate", "late delivery"), "On-time delivery rate", "نسبة التسليم في الموعد", _logistics_on_time_rate,
    ),
    "logistics.top_carrier": QueryDefinition(
        "logistics.top_carrier", "TOP", "logistics",
        ("best carrier", "top carrier", "which carrier"), "Top carrier", "أفضل شركة شحن", _logistics_top_carrier,
    ),
    "logistics.bottom_carrier": QueryDefinition(
        "logistics.bottom_carrier", "BOTTOM", "logistics",
        ("worst carrier", "bottom carrier", "underperforming carrier"), "Bottom carrier", "أسوأ شركة شحن", _logistics_bottom_carrier,
    ),
    "logistics.carrier_ranking": QueryDefinition(
        "logistics.carrier_ranking", "RANK", "logistics",
        ("rank carriers", "carrier ranking", "list carriers", "all carriers"), "Carrier ranking", "ترتيب شركات الشحن", _logistics_carrier_ranking,
    ),
    "operations.bottleneck_unit": QueryDefinition(
        "operations.bottleneck_unit", "BOTTOM", "operations",
        ("bottleneck", "underperforming unit", "worst line", "worst branch", "worst department"),
        "Bottleneck unit", "الوحدة المُختنقة", _operations_bottleneck_unit,
    ),
    "operations.utilization_ranking": QueryDefinition(
        "operations.utilization_ranking", "RANK", "operations",
        ("rank units", "utilization ranking", "rank lines", "rank branches"), "Utilization ranking", "ترتيب الاستغلال", _operations_utilization_ranking,
    ),
    "operations.quality_trend": QueryDefinition(
        "operations.quality_trend", "TREND", "operations",
        ("defect rate trend", "quality trend", "quality over time", "defects over time"),
        "Defect-rate trend", "اتجاه معدل العيوب", _operations_quality_trend,
    ),
    "hr.overtime_total_cost": QueryDefinition(
        "hr.overtime_total_cost", "TOTAL", "hr_overtime",
        ("overtime cost", "overtime spend", "overtime expense"), "Total overtime cost", "إجمالي تكلفة العمل الإضافي", _hr_overtime_total_cost,
    ),
    "hr.overtime_top_department": QueryDefinition(
        "hr.overtime_top_department", "TOP", "hr_overtime",
        ("overtime department", "which department overtime", "most overtime"), "Top overtime department", "أعلى قسم عملاً إضافياً", _hr_overtime_top_department,
    ),
    "crossdomain.overtime_vs_downtime": QueryDefinition(
        "crossdomain.overtime_vs_downtime", "COMPARE", "crossdomain",
        ("overtime and downtime", "overtime vs downtime", "overtime correlate", "overtime relate to downtime"),
        "Overtime cost vs. operational downtime (cross-domain)", "العمل الإضافي مقابل التوقف التشغيلي", _crossdomain_overtime_vs_downtime,
    ),
}


def run_registered_query(query_id: str, domain_results: dict[str, Any]) -> QueryOutcome:
    """The ONLY function permitted to execute a registry entry. Raises
    KeyError for an unregistered query_id — callers must catch this and
    treat it as a hard rejection, never a silent no-op or a fallback to
    free-form execution."""
    if query_id not in QUERY_REGISTRY:
        raise KeyError(f"'{query_id}' is not a registered query intent — rejected, not attempted.")
    definition = QUERY_REGISTRY[query_id]
    return definition.handler(domain_results)


# ── Deterministic intent + registry matching (ALWAYS runs, LLM or not) ─────

def classify_intent(question: str) -> Optional[str]:
    lowered = f" {question.lower()} "
    for intent in _INTENT_PRIORITY:
        if any(kw in lowered for kw in _INTENT_KEYWORDS[intent]):
            return intent
    return None


def is_injection_attempt(question: str) -> bool:
    return bool(_INJECTION_PATTERNS.search(question))


def is_knowledge_question(question: str) -> bool:
    return bool(_KNOWLEDGE_TRIGGER_PATTERN.search(question))


_WORD_PATTERN = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> frozenset[str]:
    return frozenset(_WORD_PATTERN.findall(text.lower()))


def match_registry_entry(question: str, intent: Optional[str]) -> Optional[QueryDefinition]:
    """Deterministic keyword-overlap match, filtered to entries whose
    declared intent equals the classified intent. A registry entry's
    keyword PHRASE matches when every word of that phrase appears
    somewhere in the question (word-set subset, not exact substring) --
    e.g. the keyword "rank carriers" matches "rank all our carriers" even
    though the exact phrase isn't contiguous. This is still fully
    deterministic and auditable (plain set intersection, no fuzzy/ML
    matching) — it just isn't defeated by natural word-order variation the
    way a strict substring check was. Returns the highest-scoring match,
    or None. Never guesses across intents."""
    if intent is None:
        return None
    q_tokens = _tokenize(question)
    best: Optional[QueryDefinition] = None
    best_score = 0
    for definition in QUERY_REGISTRY.values():
        if definition.intent != intent:
            continue
        score = 0
        for kw in definition.keywords:
            kw_tokens = _tokenize(kw)
            if kw_tokens and kw_tokens <= q_tokens:
                score += 1
        if score > best_score:
            best_score = score
            best = definition
    return best if best_score > 0 else None


# ── RAG — TF-IDF retrieval over this session's own markdown corpus ─────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RAG_INDEX_CACHE: dict[str, Any] = {}


@dataclass(frozen=True)
class _DocChunk:
    text: str
    source_file: str
    source_section: Optional[str]


_MIN_CHUNK_CHARS = 80  # skip near-empty stub sections (e.g. a bare "## Files changed" header with one line)


def _chunk_markdown(path: Path) -> list[_DocChunk]:
    """Splits on H1/H2 only (NOT H3) so each chunk keeps its H3
    subsections as context — a chunk boundary at every H3 fragmented
    substantive sections into many thin, boilerplate-titled pieces
    ("Live verification", "Files changed") that dilute TF-IDF relevance
    for genuine methodology questions. Chunks under _MIN_CHUNK_CHARS are
    dropped as near-empty stubs, not indexed."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    sections = re.split(r"(?m)^(#{1,2} .+)$", text)
    chunks: list[_DocChunk] = []
    if len(sections) <= 1:
        for i in range(0, len(text), 1200):
            piece = text[i:i + 1200].strip()
            if len(piece) >= _MIN_CHUNK_CHARS:
                chunks.append(_DocChunk(piece, path.name, None))
        return chunks
    preamble = sections[0].strip()
    if len(preamble) >= _MIN_CHUNK_CHARS:
        chunks.append(_DocChunk(preamble[:1800], path.name, None))
    for i in range(1, len(sections), 2):
        heading = sections[i].strip()
        body = sections[i + 1].strip() if i + 1 < len(sections) else ""
        piece = f"{heading}\n{body}".strip()
        if len(piece) >= _MIN_CHUNK_CHARS:
            chunks.append(_DocChunk(piece[:1800], path.name, heading.lstrip("#").strip()))
    return chunks


def build_rag_index(force_rebuild: bool = False) -> dict[str, Any]:
    """Lazily builds (and caches) a TF-IDF index over PHASE_*.md and
    BUSINESS_INTELLIGENCE_SUITE_OVERVIEW.md — this session's own project
    documentation. NEVER indexes uploaded business data files."""
    if not force_rebuild and "chunks" in _RAG_INDEX_CACHE:
        return _RAG_INDEX_CACHE
    if TfidfVectorizer is None:
        _RAG_INDEX_CACHE.update({"chunks": [], "vectorizer": None, "matrix": None})
        return _RAG_INDEX_CACHE

    doc_paths = sorted(_REPO_ROOT.glob("PHASE_*.md")) + sorted(_REPO_ROOT.glob("BUSINESS_INTELLIGENCE_SUITE_OVERVIEW.md"))
    chunks: list[_DocChunk] = []
    for p in doc_paths:
        chunks.extend(_chunk_markdown(p))

    if not chunks:
        _RAG_INDEX_CACHE.update({"chunks": [], "vectorizer": None, "matrix": None})
        return _RAG_INDEX_CACHE

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", max_features=20000)
    matrix = vectorizer.fit_transform([c.text for c in chunks])
    _RAG_INDEX_CACHE.update({"chunks": chunks, "vectorizer": vectorizer, "matrix": matrix})
    return _RAG_INDEX_CACHE


_RAG_RELEVANCE_FLOOR = 0.08
_RAG_TOP_K = 3


def retrieve_knowledge(question: str) -> list[KnowledgeContextEvidence]:
    index = build_rag_index()
    if not index["chunks"] or index["vectorizer"] is None:
        return []
    q_vec = index["vectorizer"].transform([question])
    scores = cosine_similarity(q_vec, index["matrix"])[0]
    ranked = sorted(range(len(scores)), key=lambda i: -scores[i])[:_RAG_TOP_K]
    results = []
    for i in ranked:
        if scores[i] < _RAG_RELEVANCE_FLOOR:
            continue
        c = index["chunks"][i]
        results.append(KnowledgeContextEvidence(
            label=c.source_section or c.source_file, excerpt=c.text, source_file=c.source_file,
            source_section=c.source_section, relevance_score=round(float(scores[i]), 4),
        ))
    return results


# ── Ollama phrasing (optional; dispatch-free; numeric-guarded) ─────────────

def ollama_reachable(base_url: str = OLLAMA_BASE_URL) -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _evidence_numbers(evidence: list[EvidenceEntry]) -> set[str]:
    numbers: set[str] = set()
    for e in evidence:
        if getattr(e, "kind", None) == "computed_metric":
            val = e.value
            if isinstance(val, (int, float)):
                numbers.add(_normalize_number_str(val))
    return numbers


def _normalize_number_str(val: Any) -> str:
    try:
        cleaned = str(val).replace(",", "").replace("−", "-")
        f = float(cleaned)
        return f"{f:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(val)


def _numeric_guard_passes(llm_text: str, evidence: list[EvidenceEntry]) -> bool:
    """Extracts every number-looking token from the LLM's phrased text and
    confirms each is traceable to a real Evidence Pack computed_metric
    value. Any untraceable number fails the guard — this is the actual
    enforcement mechanism, not just a prompt instruction."""
    evidence_numbers = _evidence_numbers(evidence)
    if not evidence_numbers:
        return not _NUMBER_PATTERN.search(llm_text)
    for match in _NUMBER_PATTERN.findall(llm_text):
        candidate = _normalize_number_str(match)
        if candidate in ("", "-", "."):
            continue
        if not any(_numbers_close(candidate, ev) for ev in evidence_numbers):
            return False
    return True


def _numbers_close(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < max(0.01, abs(float(b)) * 0.005)
    except (TypeError, ValueError):
        return a == b


def phrase_with_ollama(
    question: str, deterministic_answer: str, evidence: list[EvidenceEntry],
    http_call: Optional[Callable[[str], Optional[str]]] = None,
) -> tuple[str, str]:
    """
    Returns (final_text, mode) where mode is "llm" or "deterministic".
    `http_call` is injectable for tests (avoids depending on a live Ollama
    server for unit tests of the guard logic). Never lets the LLM's output
    reach the user unless every number in it traces back to the Evidence
    Pack — otherwise silently falls back to the deterministic template.
    """
    caller = http_call or _call_ollama
    prompt = (
        "You are a phrasing assistant for a business analytics platform. "
        "Rewrite the following VERIFIED FACTS into one concise, natural-language paragraph. "
        "Rules: use ONLY the numbers given below, do not calculate, estimate, round differently, "
        "or invent any number or fact not present below. Do not add caveats not present below. "
        f"\n\nQuestion: {question}\n\nVerified facts:\n{deterministic_answer}\n\nAnswer:"
    )
    try:
        llm_text = caller(prompt)
    except Exception:
        llm_text = None
    if not llm_text:
        return deterministic_answer, "deterministic"
    if not _numeric_guard_passes(llm_text, evidence):
        return deterministic_answer, "deterministic"
    return llm_text.strip(), "llm"


def _call_ollama(prompt: str) -> Optional[str]:
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate", data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


# ── Top-level answer assembly ───────────────────────────────────────────────

@dataclass(frozen=True)
class AnalystAnswer:
    answer_text: str
    key_evidence: list[EvidenceEntry]
    source_engine: Optional[str]
    data_period: Optional[str]
    evidence_level: str
    limitations: list[str]
    mode: str  # "llm" | "deterministic" | "rag" | "refused" | "unsupported"
    matched_query_id: Optional[str] = None
    computed_at: str = field(default_factory=_now)


def answer_question(question: str, domain_results: dict[str, Any], use_llm: bool = True) -> AnalystAnswer:
    """The single public entry point. Deterministic classification and
    dispatch happen unconditionally; `use_llm` only controls whether the
    (already-finalized) evidence gets an LLM phrasing pass afterward."""
    question = (question or "").strip()
    if not question:
        return AnalystAnswer("Please enter a question.", [], None, None, EVIDENCE_INSUFFICIENT, [], "unsupported")

    if is_injection_attempt(question):
        return AnalystAnswer(
            "This request looks like an attempt to make the system execute a command or ignore its "
            "own rules. The AI Business Analyst only ever runs a fixed, pre-registered list of "
            "verified business queries — it cannot execute code, run commands, access arbitrary "
            "files, or follow instructions embedded in a question. Request refused.",
            [], None, None, EVIDENCE_INSUFFICIENT, ["Trust-boundary refusal — no engine or file was accessed."], "refused",
        )

    intent = classify_intent(question)
    definition = match_registry_entry(question, intent)

    if definition is not None:
        try:
            outcome = run_registered_query(definition.query_id, domain_results)
        except KeyError:
            outcome = None
        if outcome is not None:
            return _finalize_computed_answer(question, definition, outcome, use_llm)

    # RAG is attempted ONLY when the question itself signals a knowledge/
    # methodology question (explicit trigger words) — NEVER as a blanket
    # fallback for "didn't match a registered metric." Without this
    # restriction, an unregistered business-data question (e.g. one asking
    # for a metric this phase didn't register) could spuriously match some
    # documentation paragraph on shared vocabulary and be answered from
    # project docs instead of honestly reporting "not in the registry" —
    # exactly the kind of RAG-answers-a-numeric-question conflation
    # Section 1b prohibits.
    if is_knowledge_question(question):
        knowledge = retrieve_knowledge(question)
        if knowledge:
            return _finalize_knowledge_answer(question, knowledge, use_llm)

    return AnalystAnswer(
        "I don't have a registered way to answer this question — it doesn't match any of this "
        "platform's verified business queries, and no relevant project documentation was found "
        "either. I won't guess or answer from general knowledge.",
        [], None, None, EVIDENCE_INSUFFICIENT,
        ["Unsupported question — not in the allowlisted registry, no RAG match above the relevance floor."],
        "unsupported",
    )


def _finalize_computed_answer(question: str, definition: QueryDefinition, outcome: QueryOutcome, use_llm: bool) -> AnalystAnswer:
    if not outcome.available:
        return AnalystAnswer(
            f"Insufficient data to answer this. {outcome.reason}", [], outcome.source_engine, None,
            EVIDENCE_INSUFFICIENT, [outcome.reason or ""], "unsupported", definition.query_id,
        )

    lines = [f"{m.label}: {_fmt_value(m.value, m.unit)}" for m in outcome.metrics]
    deterministic_text = f"{definition.description_en}. " + "; ".join(lines) + "."
    levels = [m.evidence_level for m in outcome.metrics]
    overall_level = EVIDENCE_INSUFFICIENT if EVIDENCE_INSUFFICIENT in levels else (EVIDENCE_LIMITED if EVIDENCE_LIMITED in levels else EVIDENCE_HIGH)
    limitations = [m.evidence_level_reason for m in outcome.metrics if m.evidence_level_reason and m.evidence_level != EVIDENCE_HIGH]

    final_text, mode = deterministic_text, "deterministic"
    if use_llm and ollama_reachable():
        final_text, mode = phrase_with_ollama(question, deterministic_text, outcome.metrics)

    return AnalystAnswer(
        final_text, outcome.metrics, outcome.source_engine, outcome.data_period, overall_level,
        limitations, mode, definition.query_id,
    )


def _finalize_knowledge_answer(question: str, knowledge: list[KnowledgeContextEvidence], use_llm: bool) -> AnalystAnswer:
    lines = [f"[{k.source_file}{' — ' + k.source_section if k.source_section else ''}] {k.excerpt[:400]}" for k in knowledge]
    deterministic_text = "Based on this platform's own documentation:\n\n" + "\n\n".join(lines)
    overall_level = EVIDENCE_HIGH if knowledge[0].relevance_score >= 0.2 else EVIDENCE_LIMITED

    final_text, mode = deterministic_text, "rag"
    if use_llm and ollama_reachable():
        # Knowledge answers phrase from a KnowledgeContextEvidence list, which
        # has NO numeric business-metric field — the numeric guard therefore
        # requires the LLM output contain no numbers at all (or only numbers
        # already present verbatim in the retrieved excerpts themselves).
        llm_text, llm_mode = phrase_with_ollama(question, deterministic_text, knowledge)
        if llm_mode == "llm":
            final_text, mode = llm_text, "rag+llm"

    return AnalystAnswer(
        final_text, knowledge, None, None, overall_level,
        ["This is retrieved documentation context, not a computed business metric — no Evidence Level badge applies to the underlying source text itself, only to this retrieval's overall relevance."],
        mode, None,
    )


def _fmt_value(value: Any, unit: Optional[str]) -> str:
    if value is None:
        return "not computed"
    if isinstance(value, float):
        text = f"{value:,.2f}"
    elif isinstance(value, bool):
        text = "Yes" if value else "No"
    else:
        text = str(value)
    return f"{text} {unit}" if unit else text


# ── Serialization ─────────────────────────────────────────────────────────────

def evidence_entry_to_dict(e: EvidenceEntry) -> dict[str, Any]:
    if e.kind == "computed_metric":
        return {
            "kind": "computed_metric", "label": e.label, "value": e.value, "unit": e.unit,
            "source_engine": e.source_engine, "data_period": e.data_period,
            "evidence_level": e.evidence_level, "evidence_level_reason": e.evidence_level_reason,
        }
    return {
        "kind": "knowledge_context", "label": e.label, "excerpt": e.excerpt,
        "source_file": e.source_file, "source_section": e.source_section,
        "relevance_score": e.relevance_score,
    }


def analyst_answer_to_dict(a: AnalystAnswer) -> dict[str, Any]:
    return {
        "answer_text": a.answer_text,
        "key_evidence": [evidence_entry_to_dict(e) for e in a.key_evidence],
        "source_engine": a.source_engine,
        "data_period": a.data_period,
        "evidence_level": a.evidence_level,
        "limitations": a.limitations,
        "mode": a.mode,
        "matched_query_id": a.matched_query_id,
        "computed_at": a.computed_at,
    }


def registry_catalog() -> list[dict[str, Any]]:
    """Public, read-only listing of every registered query — used by the
    route to let the frontend show what can be asked, and by the report."""
    return [
        {"query_id": d.query_id, "intent": d.intent, "domain": d.domain,
         "keywords": list(d.keywords), "description_en": d.description_en, "description_ar": d.description_ar}
        for d in QUERY_REGISTRY.values()
    ]
