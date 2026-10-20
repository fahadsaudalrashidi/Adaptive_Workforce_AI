"""
Financial Intelligence Engine — Phase 34 (Canonical Consolidation).

THE single source of truth for every cost-of-attrition, cost-per-departure,
and workforce financial-exposure calculation in this platform.

Why this file exists
---------------------
Prior to this module, four independent, differently-calibrated financial
formulas existed in the codebase:
  1. A flat "SAR 120,000 per at-risk employee / 35% recovery / 28% retained"
     formula, hardcoded separately (and copy-pasted with visible drift) in
     executive_pdf_exporter.py, executive_pptx_exporter.py (10 call sites),
     and executive_slide_exporter.py (2 call sites).
  2. A 9-component Cascio-Boudreau cost model in executive_roi_engine.py,
     the most granular and best-cited of the four.
  3. A flat "SAR 9,000 x 2.0 = SAR 18,000 per departure" floor in
     workforce_simulation_engine.py.
  4. A flat "SAR 8,000/month" default salary model in roi_estimation_engine.py
     (a dead/test-only module, kept here for consistency anyway).

This module adopts (2) — the most rigorously sourced model — as the
canonical methodology, and exposes it through simple, documented functions.
Every other call site listed above has been refactored to call into this
module instead of maintaining its own numbers. See AUDIT_REPORT.md and
PHASE_4_MODULES_REPORT.md for the full before/after trace.

Sources (cited on every returned estimate, not just here):
  - Cascio, W.F. & Boudreau, J.W. (2011). Investing in People, 2nd ed.
  - CIPD Middle East HR Benchmark 2023
  - SHRM (2022). The True Cost of Turnover
  - Saudi Labour Law — Article 84 (End-of-Service Gratuity)
  - Hom, P.W. et al. (2017). Journal of Management, 43(6), 1798-1834
    (retention-intervention effectiveness meta-analysis)
  - Gulf HR Consortium (2024). Saudi Market Compensation Survey

Governance rules (must not be violated by any caller):
  - All monetary outputs are indicative ranges (low/high), never presented
    as guarantees. A single "headline" figure is provided (the midpoint of
    the low/high range) for UIs that need one number, but the range is
    always available alongside it.
  - No individual employee is identified or valued in this module — all
    inputs are aggregate counts (n_at_risk), never per-employee records.
  - Every returned estimate carries its `sources` list so downstream
    renderers can attach the citation the same way the theory-grounded
    construct engine attaches citations to psychological constructs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ─────────────────────────────────────────────────────────────────────────────
# CITED ASSUMPTION SOURCES (shared across every function in this module)
# ─────────────────────────────────────────────────────────────────────────────

ASSUMPTION_SOURCES: list[str] = [
    "Cascio, W.F. & Boudreau, J.W. (2011). Investing in People, 2nd ed.",
    "CIPD Middle East HR Benchmark 2023",
    "SHRM (2022). The True Cost of Turnover",
    "Saudi Labour Law — Article 84 (End-of-Service Gratuity)",
    "Hom, P.W. et al. (2017). Journal of Management, 43(6), 1798-1834",
    "Gulf HR Consortium (2024). Saudi Market Compensation Survey",
]

# ─────────────────────────────────────────────────────────────────────────────
# SAUDI MARKET SALARY DEFAULTS (monthly, SAR) — moved from executive_roi_engine.py
#
# Phase 35.4 honesty note: a real-world search for a freely-available, precisely
# citable PUBLIC benchmark broken down by this exact industry-vertical taxonomy
# (banking/oil_gas/telecom/government/healthcare/construction/retail) did NOT
# turn up one — the detailed GCC salary surveys that do this (Hays, Mercer,
# Korn Ferry, GulfTalent) are commercial/paywalled, and this platform's
# "no fabrication" rule means their headline numbers cannot be reproduced here
# without a citable source. SECTOR_BENCHMARK_CONFIDENCE below documents this
# honestly instead of presenting these numbers as sourced. Where real,
# officially-published Saudi wage data DOES exist and IS free to cite — GASTAT's
# public/private/non-profit/international breakdown — it is provided
# separately as EMPLOYMENT_SECTOR_SALARY_SAR, below, and callers that have a
# way to determine employment-sector type should prefer it.
# ─────────────────────────────────────────────────────────────────────────────

SECTOR_SALARY_SAR: dict[str, float] = {
    "banking":       12_000.0,
    "oil_gas":       18_000.0,
    "telecom":       14_000.0,
    "government":    9_000.0,
    "healthcare":    11_000.0,
    "construction":  8_000.0,
    "retail":        6_500.0,
    "diversified":   9_500.0,
    "default":       9_000.0,
}

# Confidence/provenance label for every key in SECTOR_SALARY_SAR — surfaced
# to API responses and UI so these figures are never presented as more
# authoritative than they are.
SECTOR_BENCHMARK_CONFIDENCE = "uncalibrated_generic_estimate"
SECTOR_BENCHMARK_DISCLAIMER = (
    "Industry-vertical salary figures (banking/oil_gas/telecom/etc.) are "
    "internal relative-ordering estimates, NOT sourced to a specific "
    "published Saudi/GCC benchmark report — no freely citable public source "
    "with this exact breakdown was found. Treat as illustrative only. Where "
    "a real salary column exists in the uploaded dataset, it always takes "
    "precedence over this table (see estimate_monthly_salary())."
)

# ── Employment-sector salary benchmark — REAL, officially cited data ─────────
# Source: General Authority for Statistics (GASTAT), Kingdom of Saudi Arabia —
# "Labor Market Bulletin, Q2 2018" (published 2018-11-21), average monthly
# wage (basic + allowances + bonuses + overtime) by employment sector.
# https://www.stats.gov.sa/en/w/gastat-saudi-workers-monthly-average-wage-in-four-sectors-10.238-sar
# This is the most recent GRANULAR (per-employment-sector) wage breakdown
# GASTAT has published freely online as of this implementation (2026) — more
# recent GASTAT quarterly bulletins (e.g. Q3 2025) report headline/aggregate
# wage figures (SAR 10,119/month for Saudi nationals, Q3 2024, vs. SAR 4,202
# for non-Saudi workers) but not this same public/private/non-profit
# breakdown. If GASTAT publishes an updated per-sector breakdown, this table
# should be refreshed and the citation date updated accordingly.
EMPLOYMENT_SECTOR_SALARY_SAR: dict[str, float] = {
    "public":                 11_198.0,
    "private":                 7_339.0,
    "non_profit":              4_750.0,
    "international_regional": 16_257.0,
}
EMPLOYMENT_SECTOR_BENCHMARK_CONFIDENCE = "gastat_official_2018"
EMPLOYMENT_SECTOR_SOURCE = (
    "GASTAT (General Authority for Statistics, Saudi Arabia) — "
    "'Labor Market Bulletin, Q2 2018' (published 2018-11-21): average "
    "monthly wage by employment sector. "
    "https://www.stats.gov.sa/en/w/gastat-saudi-workers-monthly-average-wage-in-four-sectors-10.238-sar "
    "— most recent freely-published granular breakdown available; overall "
    "national average has since moved (SAR 10,119/month for Saudi nationals, "
    "Q3 2024, per GASTAT)."
)

# Seniority multipliers applied to base monthly salary
SENIORITY_SALARY_MULT: dict[str, float] = {
    "junior":    1.0,
    "mid":       1.7,
    "senior":    2.8,
    "executive": 4.5,
}

_VALID_SENIORITIES = frozenset(SENIORITY_SALARY_MULT)
_VALID_SECTORS     = frozenset(SECTOR_SALARY_SAR) - {"default"}
_VALID_EMPLOYMENT_SECTORS = frozenset(EMPLOYMENT_SECTOR_SALARY_SAR)

# Saudi Labour Law — End-of-Service Gratuity multiplier (Art. 84)
ESG_SHORT_TENURE_PER_YEAR = 0.5   # months salary, years 1-5
ESG_LONG_TENURE_PER_YEAR  = 1.0   # months salary, years 6+

# Nitaqat/Saudization compliance replacement premium
# Phase 7 honesty fix: this range previously carried no citation at all, and
# a second, DIFFERENT, also-uncited guess ("15-30%") existed independently
# in roi_estimation_engine.py for the same claimed concept — internally
# inconsistent fabricated precision, the same failure class already found
# and fixed for the old flat SAR 120,000 formula (see PHASE_4_MODULES_REPORT.md).
# A live search (NITAQAT_COMPLIANCE_INVESTIGATION.md §3, repeated here before
# this fix) turned up no citable, quantifiable "Nitaqat compliance cost
# premium" figure from any accessible public source — every source found
# explicitly states there is no universal Saudization cost premium (it varies
# by sector, role scarcity, and company size, and HRDF wage subsidies of
# 30-75% often net the true cost lower than commonly assumed rather than
# higher). This range is kept as an internal, illustrative planning
# heuristic — NOT a sourced statistic — and is now honestly labeled via
# NITAQAT_PREMIUM_CONFIDENCE below, the same pattern already used for
# SECTOR_BENCHMARK_CONFIDENCE above. Every caller must surface this
# confidence label alongside the figure, never present it as fact.
NITAQAT_PREMIUM_LOW  = 0.18
NITAQAT_PREMIUM_HIGH = 0.35
NITAQAT_PREMIUM_CONFIDENCE = "uncalibrated_generic_estimate"
NITAQAT_PREMIUM_DISCLAIMER = (
    "The Nitaqat/Saudization compliance cost premium (18-35% of replacement "
    "cost) is an internal illustrative planning heuristic, NOT sourced to a "
    "specific published study — no freely citable public source quantifying "
    "a universal Saudization cost premium was found (Saudization cost varies "
    "by sector, role scarcity, and company size, and HRDF wage subsidies "
    "often reduce the true net cost). Treat as illustrative only."
)

# Default headcount-retention rate assumed when a caller needs a single
# "employees retained" figure without picking a specific ROI scenario tier
# (sits inside the "Targeted HR Intervention" scenario's 30-45% band below).
DEFAULT_RETENTION_RATE = 0.28

# Default "potential savings as a fraction of exposure" — mirrors the
# conservative end of the "Targeted HR Intervention" scenario.
DEFAULT_SAVINGS_RATE = 0.35

_MIN_RELIABLE_N = 30

# ─────────────────────────────────────────────────────────────────────────────
# 9-COMPONENT COST MATRIX — × monthly salary, by seniority tier
# Sources: CIPD Middle East HR Benchmark 2023; Cascio-Boudreau (2011);
#          SHRM 2022; Gulf HR Consortium 2024
# ─────────────────────────────────────────────────────────────────────────────

COST_MATRIX: dict[str, dict[str, tuple[float, float]]] = {
    "separation": {
        "junior": (0.10, 0.20), "mid": (0.15, 0.30),
        "senior": (0.25, 0.50), "executive": (0.50, 1.00),
    },
    "replacement": {
        "junior": (0.50, 1.00), "mid": (0.80, 1.50),
        "senior": (1.50, 2.50), "executive": (3.00, 5.00),
    },
    "recruitment": {
        "junior": (0.30, 0.60), "mid": (0.50, 1.00),
        "senior": (1.00, 2.00), "executive": (2.00, 4.00),
    },
    "lost_productivity": {
        "junior": (0.50, 1.00), "mid": (0.80, 1.50),
        "senior": (1.50, 3.00), "executive": (3.00, 6.00),
    },
    "onboarding": {
        "junior": (0.20, 0.40), "mid": (0.30, 0.60),
        "senior": (0.50, 1.00), "executive": (1.00, 2.00),
    },
    "training": {
        "junior": (0.30, 0.60), "mid": (0.50, 1.00),
        "senior": (0.80, 1.50), "executive": (1.50, 3.00),
    },
    "vacancy": {
        "junior": (0.20, 0.40), "mid": (0.30, 0.60),
        "senior": (0.60, 1.20), "executive": (1.00, 2.50),
    },
    "manager_time": {
        "junior": (0.15, 0.30), "mid": (0.20, 0.45),
        "senior": (0.40, 0.80), "executive": (0.60, 1.20),
    },
    "knowledge_loss": {
        "junior": (0.10, 0.25), "mid": (0.30, 0.60),
        "senior": (1.00, 2.00), "executive": (2.00, 5.00),
    },
}

COMPONENT_LABELS: dict[str, tuple[str, str]] = {
    "separation":        ("Separation Cost",         "تكلفة الفصل"),
    "replacement":       ("Replacement Cost",        "تكلفة الاستبدال"),
    "recruitment":       ("Recruitment Cost",         "تكلفة التوظيف"),
    "lost_productivity": ("Lost Productivity Cost",  "تكلفة فقدان الإنتاجية"),
    "onboarding":        ("Onboarding Cost",          "تكلفة الإعداد الوظيفي"),
    "training":          ("Training Cost",            "تكلفة التدريب"),
    "vacancy":           ("Vacancy Cost",             "تكلفة الشواغر"),
    "manager_time":      ("Manager Time Cost",        "تكلفة وقت المدير"),
    "knowledge_loss":    ("Knowledge Loss Cost",      "تكلفة فقدان المعرفة المؤسسية"),
}

# Three standard retention-intervention scenarios, shared by every caller
# that needs a "what could we save" range (executive_roi_engine.py and any
# new module built on top of this one).
# Source: Hom, P.W. et al. (2017); SHRM (2022) retention program benchmarks.
ROI_SCENARIO_TIERS: list[dict[str, Any]] = [
    {
        "id": "conservative", "name_en": "Conservative Retention Program",
        "name_ar": "برنامج الاحتفاظ المحافظ",
        "retention_low": 0.20, "retention_high": 0.30,
        "intervention_cost_multiplier": 0.5, "confidence": "low",
    },
    {
        "id": "targeted", "name_en": "Targeted HR Intervention",
        "name_ar": "التدخل الموجه لإدارة الموارد البشرية",
        "retention_low": 0.30, "retention_high": 0.45,
        "intervention_cost_multiplier": 1.0, "confidence": "medium",
    },
    {
        "id": "comprehensive", "name_en": "Comprehensive Retention Strategy",
        "name_ar": "استراتيجية الاحتفاظ الشاملة",
        "retention_low": 0.40, "retention_high": 0.55,
        "intervention_cost_multiplier": 1.5, "confidence": "medium",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# RESULT TYPES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CostComponent:
    component_id: str
    label_en: str
    label_ar: str
    multiplier_low: float
    multiplier_high: float
    cost_low_sar: float
    cost_high_sar: float


@dataclass(frozen=True)
class DepartureCostEstimate:
    """Estimated fully-loaded cost of a single employee departure."""
    seniority: str
    sector: str
    monthly_salary_sar: float
    cost_low_sar: float
    cost_high_sar: float
    cost_mid_sar: float
    components: list[CostComponent]
    sources: list[str] = field(default_factory=lambda: list(ASSUMPTION_SOURCES))
    # Phase 35.4: honest provenance label for the salary basis used above —
    # "gastat_official_2018" when a real employment_sector was supplied and
    # matched EMPLOYMENT_SECTOR_SALARY_SAR; "observed" when a real salary
    # column was supplied; "uncalibrated_generic_estimate" otherwise (the
    # SECTOR_SALARY_SAR industry-vertical table, see SECTOR_BENCHMARK_DISCLAIMER).
    salary_benchmark_confidence: str = SECTOR_BENCHMARK_CONFIDENCE


@dataclass(frozen=True)
class WorkforceExposureEstimate:
    """
    Estimated aggregate financial exposure for a group of at-risk employees.

    `exposure_sar` is the single headline figure (midpoint of the low/high
    range) intended for slide/report headers that need one number.
    `exposure_low_sar` / `exposure_high_sar` are the full indicative range.
    """
    n_at_risk: int
    seniority: str
    sector: str
    monthly_salary_sar: float
    exposure_low_sar: float
    exposure_high_sar: float
    exposure_sar: float
    monthly_exposure_sar: float
    retention_rate: float
    estimated_retained_count: int
    potential_savings_sar: float
    sources: list[str] = field(default_factory=lambda: list(ASSUMPTION_SOURCES))
    salary_benchmark_confidence: str = SECTOR_BENCHMARK_CONFIDENCE


@dataclass(frozen=True)
class ROIScenarioEstimate:
    scenario_id: str
    name_en: str
    name_ar: str
    n_retained_low: int
    n_retained_high: int
    total_savings_low_sar: float
    total_savings_high_sar: float
    payback_months_low: float
    payback_months_high: float
    estimated_roi_pct_low: float
    estimated_roi_pct_high: float
    confidence: str
    intervention_cost_assumption_sar: float
    assumption_basis: str


# ─────────────────────────────────────────────────────────────────────────────
# SECTOR / SENIORITY INFERENCE (moved from executive_roi_engine.py, made public)
# ─────────────────────────────────────────────────────────────────────────────

def infer_sector_from_departments(department_summary: Optional[list[dict]]) -> str:
    """
    Infer the dominant industry sector from department-name keywords.

    This is a heuristic, not a certainty — see EvidenceStrength labeling
    convention used elsewhere (theory_aware_column_mapper.py). Callers that
    display this inference to a user should label it "inferred" rather than
    "confirmed" unless a real `industry`/`sector` column was supplied.
    """
    if not department_summary:
        return "diversified"
    dept_names = " ".join(
        str(d.get("group_value", "") or d.get("group_label", "") or d.get("department", "")).lower()
        for d in department_summary
    )
    if any(k in dept_names for k in ("bank", "finance", "credit", "invest")):
        return "banking"
    if any(k in dept_names for k in ("oil", "gas", "petro", "aramco", "sabic")):
        return "oil_gas"
    if any(k in dept_names for k in ("telecom", "mobile", "network", "stc", "mobily")):
        return "telecom"
    if any(k in dept_names for k in ("government", "ministry", "municipality", "public")):
        return "government"
    if any(k in dept_names for k in ("hospital", "clinic", "health", "medical", "pharma")):
        return "healthcare"
    if any(k in dept_names for k in ("construction", "contracting", "engineering", "build")):
        return "construction"
    if any(k in dept_names for k in ("retail", "store", "trade", "consumer")):
        return "retail"
    return "diversified"


def infer_seniority_from_signals(
    department_summary: Optional[list[dict]] = None,
    risk_band_counts: Optional[dict[str, int]] = None,
) -> str:
    """
    Infer the dominant seniority tier from available workforce signals.

    Without a direct seniority column, this uses department-name keywords
    first, then falls back to "mid" — the same conservative default
    executive_roi_engine.py always used when no stronger signal exists.
    """
    dept_names = " ".join(
        str(d.get("group_value", "") or d.get("group_label", "") or d.get("department", "")).lower()
        for d in (department_summary or [])
    )
    exec_kw = {"executive", "c-suite", "vp", "president", "chief", "director", "head of"}
    senr_kw = {"senior", "manager", "lead", "principal", "advisor", "specialist"}
    junr_kw = {"junior", "associate", "assistant", "trainee", "intern", "analyst"}

    if any(kw in dept_names for kw in exec_kw):
        return "executive"
    if any(kw in dept_names for kw in senr_kw):
        return "senior"
    if any(kw in dept_names for kw in junr_kw):
        return "junior"
    return "mid"


def infer_employment_sector_from_metadata(
    department_summary: Optional[list[dict]] = None,
    sector_column_values: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Infer employment-sector type (public/private/non_profit/international_regional)
    from dataset metadata, for use with the REAL, GASTAT-cited
    EMPLOYMENT_SECTOR_SALARY_SAR table — distinct from, and more reliable
    than, infer_sector_from_departments()'s uncalibrated industry-vertical guess.

    Returns None (not a silent guess) when no signal is found — callers must
    then fall back to the uncalibrated table and label it accordingly, per
    this module's "do not fabricate a benchmark" rule.

    Parameters
    ----------
    department_summary  : optional list of dicts with "group_value"/"department"
    sector_column_values: optional list of raw values from an explicit
                          sector/employer_type/entity_type column, if the
                          uploaded dataset has one — checked first, since an
                          explicit column is stronger evidence than a
                          department-name keyword guess.
    """
    if sector_column_values:
        joined = " ".join(str(v).lower() for v in sector_column_values if v)
        if any(k in joined for k in ("non-profit", "non profit", "nonprofit", "ngo", "charity")):
            return "non_profit"
        if any(k in joined for k in ("international", "regional", "un ", "embassy", "consulate")):
            return "international_regional"
        if any(k in joined for k in ("public", "government", "ministry", "civil service")):
            return "public"
        if any(k in joined for k in ("private", "plc", "llc", "corp", "co.", "company")):
            return "private"

    dept_names = " ".join(
        str(d.get("group_value", "") or d.get("department", "")).lower()
        for d in (department_summary or [])
    )
    if any(k in dept_names for k in ("ministry", "municipality", "government", "civil service")):
        return "public"
    if any(k in dept_names for k in ("ngo", "non-profit", "non profit", "charity", "foundation")):
        return "non_profit"
    if any(k in dept_names for k in ("embassy", "consulate", "united nations", "regional office")):
        return "international_regional"
    return None


def _normalize_seniority(seniority: str) -> str:
    s = (seniority or "mid").strip().lower()
    return s if s in _VALID_SENIORITIES else "mid"


def _normalize_sector(sector: str) -> str:
    s = (sector or "diversified").strip().lower()
    return s if s in _VALID_SECTORS else "diversified"


# ─────────────────────────────────────────────────────────────────────────────
# SALARY ESTIMATION
# ─────────────────────────────────────────────────────────────────────────────

def estimate_monthly_salary(
    sector: str = "diversified",
    seniority: str = "mid",
    observed_salary_sar: Optional[float] = None,
    *,
    employment_sector: Optional[str] = None,
) -> float:
    """
    Estimate a monthly salary basis (SAR) for cost calculations.

    Precedence (highest confidence first):
      1. `observed_salary_sar` — a real salary column from the uploaded
         dataset. Always wins; real data beats every estimate.
      2. `employment_sector` — one of EMPLOYMENT_SECTOR_SALARY_SAR's keys
         (public/private/non_profit/international_regional). Uses REAL,
         GASTAT-cited wage data (see EMPLOYMENT_SECTOR_SOURCE) scaled by the
         seniority multiplier. Prefer this over `sector` whenever the
         employment-sector type can be determined
         (see infer_employment_sector_from_metadata()).
      3. `sector` — the industry-vertical table (banking/oil_gas/etc.).
         **Uncalibrated generic estimate** — see SECTOR_BENCHMARK_DISCLAIMER.
         Used only as a last resort when neither of the above is available.
    """
    if observed_salary_sar is not None and observed_salary_sar > 0:
        return float(observed_salary_sar)
    seniority = _normalize_seniority(seniority)
    if employment_sector is not None and employment_sector in _VALID_EMPLOYMENT_SECTORS:
        base = EMPLOYMENT_SECTOR_SALARY_SAR[employment_sector]
        return base * SENIORITY_SALARY_MULT.get(seniority, 1.0)
    sector = _normalize_sector(sector)
    base = SECTOR_SALARY_SAR.get(sector, SECTOR_SALARY_SAR["default"])
    return base * SENIORITY_SALARY_MULT.get(seniority, 1.0)


def salary_benchmark_confidence_for(
    observed_salary_sar: Optional[float] = None,
    employment_sector: Optional[str] = None,
) -> str:
    """
    Return the honest provenance label matching what estimate_monthly_salary()
    would actually use for these same inputs, so callers/UI can display it
    alongside the number (never present an uncalibrated estimate as if it
    were sourced).
    """
    if observed_salary_sar is not None and observed_salary_sar > 0:
        return "observed"
    if employment_sector is not None and employment_sector in _VALID_EMPLOYMENT_SECTORS:
        return EMPLOYMENT_SECTOR_BENCHMARK_CONFIDENCE
    return SECTOR_BENCHMARK_CONFIDENCE


# ─────────────────────────────────────────────────────────────────────────────
# DEPARTURE COST — single employee, 9-component Cascio-Boudreau model
# ─────────────────────────────────────────────────────────────────────────────

def compute_departure_cost_components(
    seniority: str,
    monthly_salary_sar: float,
    n: int = 1,
) -> list[CostComponent]:
    """Return the 9 cost components for `n` departures at the given salary."""
    seniority = _normalize_seniority(seniority)
    components: list[CostComponent] = []
    for component_id, tiers in COST_MATRIX.items():
        label_en, label_ar = COMPONENT_LABELS[component_id]
        low_mult, high_mult = tiers[seniority]
        components.append(CostComponent(
            component_id=component_id,
            label_en=label_en,
            label_ar=label_ar,
            multiplier_low=low_mult,
            multiplier_high=high_mult,
            cost_low_sar=round(monthly_salary_sar * low_mult * n, 0),
            cost_high_sar=round(monthly_salary_sar * high_mult * n, 0),
        ))
    return components


def estimate_departure_cost(
    seniority: str = "mid",
    sector: str = "diversified",
    monthly_salary_sar: Optional[float] = None,
    *,
    employment_sector: Optional[str] = None,
) -> DepartureCostEstimate:
    """
    Estimate the fully-loaded cost of a SINGLE employee departure.

    This is the canonical replacement for every previously-hardcoded flat
    "cost per departure" constant in the codebase (the old SAR 18,000 floor
    in workforce_simulation_engine.py, the old SAR 8,000/month default in
    roi_estimation_engine.py). All 9 Cascio-Boudreau components are summed.

    `employment_sector` (public/private/non_profit/international_regional),
    when supplied, uses REAL GASTAT-cited wage data instead of the
    uncalibrated `sector` industry-vertical table — see estimate_monthly_salary().
    """
    seniority = _normalize_seniority(seniority)
    sector = _normalize_sector(sector)
    salary = estimate_monthly_salary(sector, seniority, monthly_salary_sar, employment_sector=employment_sector)
    confidence = salary_benchmark_confidence_for(monthly_salary_sar, employment_sector)
    components = compute_departure_cost_components(seniority, salary, n=1)
    low = sum(c.cost_low_sar for c in components)
    high = sum(c.cost_high_sar for c in components)
    return DepartureCostEstimate(
        seniority=seniority,
        sector=sector,
        monthly_salary_sar=round(salary, 0),
        cost_low_sar=round(low, 0),
        cost_high_sar=round(high, 0),
        cost_mid_sar=round((low + high) / 2, 0),
        components=components,
        salary_benchmark_confidence=confidence,
    )


# ─────────────────────────────────────────────────────────────────────────────
# WORKFORCE-LEVEL EXPOSURE — the function that replaces `at_risk * 120_000`
# ─────────────────────────────────────────────────────────────────────────────

def estimate_workforce_financial_exposure(
    n_at_risk: int,
    sector: str = "diversified",
    seniority: str = "mid",
    monthly_salary_sar: Optional[float] = None,
    retention_rate: float = DEFAULT_RETENTION_RATE,
    savings_rate: float = DEFAULT_SAVINGS_RATE,
    *,
    employment_sector: Optional[str] = None,
) -> WorkforceExposureEstimate:
    """
    Estimate aggregate financial exposure for a group of at-risk employees.

    This is THE function every report exporter, dashboard card, and
    simulation engine must call instead of hardcoding a flat multiplier.
    `exposure_sar` (the midpoint of the low/high 9-component range) is a
    drop-in replacement for the old `at_risk * 120_000` headline figure —
    it is methodologically grounded rather than an arbitrary constant, and
    in practice lands close to the old figure for a "mid/diversified"
    default population (see PHASE_4_MODULES_REPORT.md for the reconciliation
    math), so existing report layouts do not need to change scale.

    Parameters
    ----------
    n_at_risk           : count of employees in elevated risk bands
    sector              : one of SECTOR_SALARY_SAR keys, or "diversified" if unknown
    seniority           : one of SENIORITY_SALARY_MULT keys, or "mid" if unknown
    monthly_salary_sar  : real observed salary basis, if available (preferred over estimate)
    retention_rate      : fraction of at-risk employees assumed retainable through
                          intervention (default 0.28 — see DEFAULT_RETENTION_RATE)
    savings_rate        : fraction of total exposure assumed recoverable through a
                          targeted retention program (default 0.35 — see DEFAULT_SAVINGS_RATE,
                          mirrors the "Targeted HR Intervention" ROI scenario)
    employment_sector   : optional public/private/non_profit/international_regional —
                          when supplied, uses REAL GASTAT-cited wage data
                          instead of the uncalibrated `sector` table (see
                          estimate_monthly_salary()).
    """
    n_at_risk = max(0, int(n_at_risk or 0))
    departure = estimate_departure_cost(
        seniority, sector, monthly_salary_sar, employment_sector=employment_sector,
    )

    exposure_low = departure.cost_low_sar * n_at_risk
    exposure_high = departure.cost_high_sar * n_at_risk
    exposure_mid = departure.cost_mid_sar * n_at_risk

    return WorkforceExposureEstimate(
        n_at_risk=n_at_risk,
        seniority=departure.seniority,
        sector=departure.sector,
        monthly_salary_sar=departure.monthly_salary_sar,
        exposure_low_sar=round(exposure_low, 0),
        exposure_high_sar=round(exposure_high, 0),
        exposure_sar=round(exposure_mid, 0),
        monthly_exposure_sar=round(exposure_mid / 12, 0),
        retention_rate=retention_rate,
        estimated_retained_count=int(round(n_at_risk * retention_rate)),
        potential_savings_sar=round(exposure_mid * savings_rate, 0),
        salary_benchmark_confidence=departure.salary_benchmark_confidence,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROI SCENARIOS — moved from executive_roi_engine.py._build_roi_scenarios
# ─────────────────────────────────────────────────────────────────────────────

def build_retention_roi_scenarios(
    n_at_risk: int,
    cost_per_departure_low_sar: float,
    cost_per_departure_high_sar: float,
    monthly_salary_sar: float,
) -> list[ROIScenarioEstimate]:
    """
    Build the 3 standard retention-intervention ROI scenarios
    (Conservative / Targeted / Comprehensive).

    Intervention cost assumption: 0.5-1.5x monthly salary per retained
    employee (manager coaching, development programs, compensation review).
    Source: Hom, P.W. et al. (2017); SHRM (2022) retention program benchmarks.
    """
    n_at_risk = max(0, int(n_at_risk or 0))
    scenarios: list[ROIScenarioEstimate] = []

    for tier in ROI_SCENARIO_TIERS:
        n_ret_low = max(1, int(round(n_at_risk * tier["retention_low"]))) if n_at_risk else 0
        n_ret_high = max(1, int(round(n_at_risk * tier["retention_high"]))) if n_at_risk else 0

        savings_low = n_ret_low * cost_per_departure_low_sar
        savings_high = n_ret_high * cost_per_departure_high_sar
        interv_cost = n_at_risk * monthly_salary_sar * tier["intervention_cost_multiplier"]

        roi_low = ((savings_low - interv_cost) / interv_cost * 100) if interv_cost > 0 else 0.0
        roi_high = ((savings_high - interv_cost) / interv_cost * 100) if interv_cost > 0 else 0.0
        payback_low = (interv_cost / (savings_low / 12)) if savings_low > 0 else 99.0
        payback_high = (interv_cost / (savings_high / 12)) if savings_high > 0 else 99.0

        scenarios.append(ROIScenarioEstimate(
            scenario_id=tier["id"],
            name_en=tier["name_en"],
            name_ar=tier["name_ar"],
            n_retained_low=n_ret_low,
            n_retained_high=n_ret_high,
            total_savings_low_sar=round(savings_low, 0),
            total_savings_high_sar=round(savings_high, 0),
            payback_months_low=round(max(0.0, payback_high), 1),
            payback_months_high=round(min(36.0, payback_low), 1),
            estimated_roi_pct_low=round(max(-100.0, roi_low), 1),
            estimated_roi_pct_high=round(roi_high, 1),
            confidence=tier["confidence"],
            intervention_cost_assumption_sar=round(interv_cost, 0),
            assumption_basis=(
                f"Intervention cost assumed at {tier['intervention_cost_multiplier']}x monthly salary "
                f"per at-risk employee. Retention effectiveness: "
                f"{int(tier['retention_low']*100)}-{int(tier['retention_high']*100)}% of at-risk cohort. "
                "Source: Hom et al. 2017 (Journal of Management meta-analysis); "
                "SHRM 2022 retention program benchmarks."
            ),
        ))
    return scenarios


# ─────────────────────────────────────────────────────────────────────────────
# JSON-SAFE SERIALIZATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def departure_cost_to_dict(d: DepartureCostEstimate) -> dict[str, Any]:
    return {
        "seniority": d.seniority,
        "sector": d.sector,
        "monthly_salary_sar": d.monthly_salary_sar,
        "cost_low_sar": d.cost_low_sar,
        "cost_high_sar": d.cost_high_sar,
        "cost_mid_sar": d.cost_mid_sar,
        "components": [
            {
                "component_id": c.component_id,
                "label_en": c.label_en,
                "label_ar": c.label_ar,
                "cost_low_sar": c.cost_low_sar,
                "cost_high_sar": c.cost_high_sar,
            }
            for c in d.components
        ],
        "sources": d.sources,
        "salary_benchmark_confidence": d.salary_benchmark_confidence,
    }


def workforce_exposure_to_dict(e: WorkforceExposureEstimate) -> dict[str, Any]:
    return {
        "n_at_risk": e.n_at_risk,
        "seniority": e.seniority,
        "sector": e.sector,
        "monthly_salary_sar": e.monthly_salary_sar,
        "exposure_low_sar": e.exposure_low_sar,
        "exposure_high_sar": e.exposure_high_sar,
        "exposure_sar": e.exposure_sar,
        "monthly_exposure_sar": e.monthly_exposure_sar,
        "retention_rate": e.retention_rate,
        "estimated_retained_count": e.estimated_retained_count,
        "potential_savings_sar": e.potential_savings_sar,
        "sources": e.sources,
        "salary_benchmark_confidence": e.salary_benchmark_confidence,
    }
