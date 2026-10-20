"""
Risk Intelligence — Multi-Layer Workforce Risk Scoring

Computes risk at three levels: individual, departmental, and organisational.
Handles HR attrition, burnout, engagement, sustainability, and financial exposure.
Safe for datasets without all required fields — gracefully degrades.

Enterprise governance:
- BurnoutRisk returns None (not 0) when evidence is insufficient
- Department column detected via broad synonym list
- Financial exposure denominated in configured currency
- No fake "All Employees" department when real departments exist
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from config.settings import (
    RISK_LEVELS, BURNOUT_THRESHOLDS, ENGAGEMENT_THRESHOLDS,
    ATTRITION_REPLACEMENT_COST_FACTOR,
    DEFAULT_ANNUAL_SALARY_LOCAL,
    DEFAULT_CURRENCY, CURRENCY_SYMBOLS, CURRENCY_FROM_USD,
    MIN_DEPT_GROUP_SIZE,
)
from .semantic_mapper import SemanticMap


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCT EVIDENCE MODES
# ─────────────────────────────────────────────────────────────────────────────

CONSTRUCT_MODE_DIRECT    = "Direct"       # measured directly in dataset
CONSTRUCT_MODE_PROXY     = "Proxy"        # estimated from related indicators
CONSTRUCT_MODE_ENGINEERED = "Engineered"  # computed by feature factory
CONSTRUCT_MODE_UNAVAILABLE = "Not Available"  # insufficient evidence

# Department column synonyms (order matters — more specific first)
DEPT_SYNONYMS = [
    "department", "dept", "division", "businessunit", "business_unit",
    "business unit", "unit", "section", "team", "job_department",
    "jobdepartment", "organization_unit", "org_unit", "orgunit",
    "cost_center", "costcenter", "function", "job_function",
    # Arabic synonyms (transliterated column names)
    "idara", "qism",
]


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConstructEvidence:
    """Tracks whether a construct (burnout, engagement) is evidenced in the data."""
    construct_name: str
    mode: str                    # CONSTRUCT_MODE_*
    confidence: float            # 0–1
    source_columns: List[str]
    caveat: str                  # shown in UI when mode != Direct


@dataclass
class IndividualRisk:
    employee_idx: Any
    attrition_probability: float
    risk_level: str
    burnout_risk: Optional[float]          # None = not available
    burnout_mode: str                      # CONSTRUCT_MODE_*
    engagement_risk: Optional[float]
    engagement_mode: str
    financial_exposure: float              # in configured currency
    currency: str
    top_risk_drivers: List[str] = field(default_factory=list)
    # backward-compat alias kept for existing code
    @property
    def financial_exposure_usd(self) -> float:
        return self.financial_exposure


@dataclass
class DepartmentRisk:
    department: str
    n_employees: int
    avg_attrition_prob: float
    high_risk_count: int
    high_risk_pct: float
    avg_burnout: Optional[float]
    avg_engagement: Optional[float]
    total_financial_exposure: float
    currency: str
    reliability_flag: str
    construct_scores: Dict[str, float] = field(default_factory=dict)
    # backward-compat
    @property
    def total_financial_exposure_usd(self) -> float:
        return self.total_financial_exposure


@dataclass
class OrganizationalRisk:
    total_employees: int
    overall_attrition_risk: float
    high_risk_employees: int
    high_risk_pct: float
    total_financial_exposure: float
    currency: str
    burnout_hotspot: Optional[str]
    most_at_risk_dept: Optional[str]
    sustainability_score: float
    early_warning_level: str
    department_column_found: bool          # False → no real dept breakdown
    department_risks: List[DepartmentRisk] = field(default_factory=list)
    top_risk_factors: List[str] = field(default_factory=list)
    # backward-compat
    @property
    def total_financial_exposure_usd(self) -> float:
        return self.total_financial_exposure


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_series(df: pd.DataFrame, sem_map: Optional[SemanticMap],
                category: str, fallback_col: Optional[str] = None) -> Optional[pd.Series]:
    if sem_map:
        cols = sem_map.get(category)
        for c in cols:
            if c in df.columns:
                return pd.to_numeric(df[c], errors="coerce")
    if fallback_col and fallback_col in df.columns:
        return pd.to_numeric(df[fallback_col], errors="coerce")
    return None


def _risk_label(prob: float) -> str:
    for level, cfg in RISK_LEVELS.items():
        if prob >= cfg["min"]:
            return cfg["label"]
    return "Low"


def _reliability_flag(n: int) -> str:
    if n < MIN_DEPT_GROUP_SIZE:
        return "Insufficient Statistical Reliability — small sample, interpret cautiously"
    if n < 10:
        return "Low Reliability Warning — interpret cautiously"
    return "Sufficient"


def _detect_dept_column(df: pd.DataFrame,
                         sem_map: Optional[SemanticMap] = None) -> Optional[str]:
    """
    Find the department column using semantic mapping then synonym matching.
    Returns None if no department column is found (never fakes one).
    """
    # 1. Semantic mapper knows best
    if sem_map:
        cols = sem_map.get("department")
        for c in cols:
            if c in df.columns:
                return c

    # 2. Normalised column name matching
    col_lower = {c: re.sub(r"[\s_\-\.]+", "", c.lower()) for c in df.columns}
    for syn in DEPT_SYNONYMS:
        syn_norm = re.sub(r"[\s_\-\.]+", "", syn.lower())
        for orig, norm in col_lower.items():
            if norm == syn_norm:
                return orig

    # 3. Contains-check (word-boundary safe)
    for syn in ["department", "dept", "division", "unit", "team", "section"]:
        pattern = re.compile(r'\b' + re.escape(syn) + r'\b', re.IGNORECASE)
        for col in df.columns:
            if pattern.search(col):
                return col

    return None


def _build_construct_evidence(
    df: pd.DataFrame,
    sem_map: Optional[SemanticMap],
    construct: str,
    engineered_col: str,
    direct_cats: List[str],
) -> Tuple[Optional[pd.Series], ConstructEvidence]:
    """
    Returns (series_or_None, ConstructEvidence).
    Priority: engineered column → direct semantic columns → None.
    """
    sources: List[str] = []

    # Engineered column (produced by feature_factory)
    if engineered_col in df.columns:
        s = pd.to_numeric(df[engineered_col], errors="coerce")
        valid = s.dropna()
        if len(valid) > 0 and valid.std() > 0:
            return s, ConstructEvidence(
                construct_name=construct,
                mode=CONSTRUCT_MODE_ENGINEERED,
                confidence=0.70,
                source_columns=[engineered_col],
                caveat=f"{construct} is estimated from engineered composite features, not directly measured.",
            )

    # Direct semantic columns
    if sem_map:
        cols = sem_map.get(construct.lower().replace(" ", "_"))
        for c in cols:
            if c in df.columns:
                sources.append(c)
    if sources:
        s = pd.to_numeric(df[sources[0]], errors="coerce")
        valid = s.dropna()
        if len(valid) > 0:
            return s, ConstructEvidence(
                construct_name=construct,
                mode=CONSTRUCT_MODE_DIRECT,
                confidence=0.90,
                source_columns=sources,
                caveat="",
            )

    return None, ConstructEvidence(
        construct_name=construct,
        mode=CONSTRUCT_MODE_UNAVAILABLE,
        confidence=0.0,
        source_columns=[],
        caveat=(
            f"{construct} evidence is not available in this dataset. "
            "Display suppressed to avoid misleading values."
        ),
    )


def _fmt_currency(amount: float, currency: str) -> str:
    sym = CURRENCY_SYMBOLS.get(currency, currency)
    if sym in ("SAR", "AED", "USD"):
        return f"{sym} {amount:,.0f}"
    return f"{sym}{amount:,.0f}"


def _convert_salary(salary_usd: float, currency: str) -> float:
    rate = CURRENCY_FROM_USD.get(currency, 1.0)
    return salary_usd * rate


# ─────────────────────────────────────────────────────────────────────────────
# INDIVIDUAL RISK SCORER
# ─────────────────────────────────────────────────────────────────────────────

def score_individuals(df: pd.DataFrame,
                       attrition_probs: np.ndarray,
                       sem_map: Optional[SemanticMap] = None,
                       salary_col: Optional[str] = None,
                       currency: str = DEFAULT_CURRENCY) -> List[IndividualRisk]:
    n = len(df)

    # ── Salary (financial exposure) ──────────────────────────────────────────
    salary_series = _get_series(df, sem_map, "salary", salary_col)
    if salary_series is not None:
        sal_vals = salary_series.fillna(DEFAULT_ANNUAL_SALARY_LOCAL)
        # Monthly salary detected → annualise
        if sal_vals.median() < 10_000:
            sal_vals = sal_vals * 12
        # Convert from USD if salary is assumed USD-based
        sal_vals = sal_vals.apply(lambda v: _convert_salary(v, currency)
                                   if currency != "USD" and sal_vals.median() < 200_000
                                   else v)
        sal_vals = sal_vals.values
    else:
        sal_vals = np.full(n, DEFAULT_ANNUAL_SALARY_LOCAL)

    # ── Burnout construct ────────────────────────────────────────────────────
    burnout_series, burnout_ev = _build_construct_evidence(
        df, sem_map, "Burnout Risk",
        engineered_col="BurnoutRiskComposite",
        direct_cats=["burnout"],
    )

    # ── Engagement construct ─────────────────────────────────────────────────
    engagement_series, engagement_ev = _build_construct_evidence(
        df, sem_map, "Engagement",
        engineered_col="EngagementScore",
        direct_cats=["engagement", "satisfaction"],
    )

    results: List[IndividualRisk] = []
    for i in range(n):
        prob    = float(np.clip(attrition_probs[i], 0, 1))
        salary  = float(sal_vals[i])
        fin_exp = salary * ATTRITION_REPLACEMENT_COST_FACTOR * prob

        # Burnout — None when evidence unavailable
        if burnout_ev.mode == CONSTRUCT_MODE_UNAVAILABLE:
            burnout_v = None
        else:
            raw = float(burnout_series.iloc[i]) if (burnout_series is not None and i < len(burnout_series)) else None
            burnout_v = None if (raw is None or np.isnan(raw)) else round(float(np.clip(raw, 0, 1)), 4)

        # Engagement — None when evidence unavailable
        if engagement_ev.mode == CONSTRUCT_MODE_UNAVAILABLE:
            engagement_v = None
        else:
            raw = float(engagement_series.iloc[i]) if (engagement_series is not None and i < len(engagement_series)) else None
            engagement_v = None if (raw is None or np.isnan(raw)) else round(float(np.clip(raw, 0, 1)), 4)

        # Risk drivers (only include constructs that have real evidence)
        drivers: List[str] = []
        if burnout_v is not None and burnout_v >= 0.65:
            drivers.append("Elevated burnout indicator")
        if engagement_v is not None and (1 - engagement_v) >= 0.65:
            drivers.append("Low engagement indicator")
        if prob >= 0.70:
            drivers.append("High predicted attrition probability")

        results.append(IndividualRisk(
            employee_idx           = df.index[i] if hasattr(df, "index") else i,
            attrition_probability  = round(prob, 4),
            risk_level             = _risk_label(prob),
            burnout_risk           = burnout_v,
            burnout_mode           = burnout_ev.mode,
            engagement_risk        = (None if engagement_v is None else round(1 - engagement_v, 4)),
            engagement_mode        = engagement_ev.mode,
            financial_exposure     = round(fin_exp, 2),
            currency               = currency,
            top_risk_drivers       = drivers,
        ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# DEPARTMENT-LEVEL RISK
# ─────────────────────────────────────────────────────────────────────────────

def score_departments(df: pd.DataFrame,
                       attrition_probs: np.ndarray,
                       individual_risks: List[IndividualRisk],
                       sem_map: Optional[SemanticMap] = None,
                       dept_col: Optional[str] = None,
                       currency: str = DEFAULT_CURRENCY) -> List[DepartmentRisk]:
    # Prefer explicit dept_col, then detect
    resolved_col = dept_col or _detect_dept_column(df, sem_map)

    if resolved_col is None or resolved_col not in df.columns:
        # No department column — return EMPTY list (not a fake All Employees)
        logger.info("No department column detected — department breakdown unavailable.")
        return []

    dept_series = df[resolved_col].astype(str).fillna("Unknown").str.strip()
    dept_results: List[DepartmentRisk] = []

    for dept in sorted(dept_series.unique()):
        if dept in ("", "nan", "None", "NaN"):
            continue
        mask       = (dept_series == dept).values
        dept_probs = attrition_probs[mask]
        dept_risks = [r for r, m in zip(individual_risks, mask) if m]
        if len(dept_risks) == 0:
            continue
        dept_results.append(_agg_dept(dept, df[mask], dept_probs, dept_risks, currency))

    return sorted(dept_results, key=lambda d: d.avg_attrition_prob, reverse=True)


def _agg_dept(dept_name: str,
              dept_df: pd.DataFrame,
              dept_probs: np.ndarray,
              dept_risks: List[IndividualRisk],
              currency: str = DEFAULT_CURRENCY) -> DepartmentRisk:
    n         = len(dept_df)
    avg_prob  = float(np.mean(dept_probs))
    high_risk = sum(1 for r in dept_risks if r.risk_level in ("High", "Critical"))
    fin_exp   = sum(r.financial_exposure for r in dept_risks)

    # Only aggregate burnout/engagement when evidence is available
    burnout_vals = [r.burnout_risk for r in dept_risks if r.burnout_risk is not None]
    avg_burn = float(np.mean(burnout_vals)) if burnout_vals else None

    engagement_vals = [r.engagement_risk for r in dept_risks if r.engagement_risk is not None]
    avg_eng = float(np.mean(engagement_vals)) if engagement_vals else None

    # Construct scores from engineered features
    construct_scores: Dict[str, float] = {}
    for col in ["BurnoutRiskComposite", "SatisfactionIndex", "EngagementScore",
                "RetentionRisk", "ManagerialSupportIndex"]:
        if col in dept_df.columns:
            s = pd.to_numeric(dept_df[col], errors="coerce").dropna()
            if len(s) > 0:
                construct_scores[col] = round(float(s.mean()), 4)

    return DepartmentRisk(
        department                = dept_name,
        n_employees               = n,
        avg_attrition_prob        = round(avg_prob, 4),
        high_risk_count           = high_risk,
        high_risk_pct             = round(high_risk / max(n, 1), 4),
        avg_burnout               = round(avg_burn, 4) if avg_burn is not None else None,
        avg_engagement            = round(1.0 - avg_eng, 4) if avg_eng is not None else None,
        total_financial_exposure  = round(fin_exp, 2),
        currency                  = currency,
        reliability_flag          = _reliability_flag(n),
        construct_scores          = construct_scores,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ORGANISATIONAL RISK
# ─────────────────────────────────────────────────────────────────────────────

def score_organization(individual_risks: List[IndividualRisk],
                        department_risks: List[DepartmentRisk],
                        currency: str = DEFAULT_CURRENCY) -> OrganizationalRisk:
    n_total = len(individual_risks)
    dept_col_found = len(department_risks) > 0

    if n_total == 0:
        return OrganizationalRisk(
            total_employees=0, overall_attrition_risk=0, high_risk_employees=0,
            high_risk_pct=0, total_financial_exposure=0, currency=currency,
            burnout_hotspot=None, most_at_risk_dept=None,
            sustainability_score=50, early_warning_level="Stable",
            department_column_found=dept_col_found,
        )

    overall_risk = float(np.mean([r.attrition_probability for r in individual_risks]))
    high_risk_n  = sum(1 for r in individual_risks if r.risk_level in ("High", "Critical"))
    total_fin    = sum(r.financial_exposure for r in individual_risks)

    most_at_risk = (max(department_risks, key=lambda d: d.avg_attrition_prob).department
                    if department_risks else None)
    burnout_hot  = (max((d for d in department_risks if d.avg_burnout is not None),
                        key=lambda d: d.avg_burnout).department
                    if any(d.avg_burnout is not None for d in department_risks) else None)

    # Sustainability calculation — only use constructs with evidence
    burnout_vals = [r.burnout_risk for r in individual_risks if r.burnout_risk is not None]
    engage_vals  = [r.engagement_risk for r in individual_risks if r.engagement_risk is not None]
    avg_burnout_org = float(np.mean(burnout_vals)) if burnout_vals else 0.0
    avg_engage_org  = float(np.mean(engage_vals)) if engage_vals else 0.0

    sustainability = round(100.0 * (1 - overall_risk * 0.50
                                    - avg_burnout_org * 0.30
                                    + (1 - avg_engage_org) * 0.20), 1)
    sustainability = float(np.clip(sustainability, 0, 100))

    if overall_risk >= 0.65 or high_risk_n / max(n_total, 1) >= 0.30:
        ew_level = "Critical"
    elif overall_risk >= 0.45 or high_risk_n / max(n_total, 1) >= 0.20:
        ew_level = "Elevated"
    elif overall_risk >= 0.30:
        ew_level = "Watchlist"
    else:
        ew_level = "Stable"

    all_drivers: Dict[str, int] = {}
    for r in individual_risks:
        for d in r.top_risk_drivers:
            all_drivers[d] = all_drivers.get(d, 0) + 1
    top_factors = [k for k, _ in sorted(all_drivers.items(),
                                         key=lambda x: x[1], reverse=True)[:5]]

    return OrganizationalRisk(
        total_employees              = n_total,
        overall_attrition_risk       = round(overall_risk, 4),
        high_risk_employees          = high_risk_n,
        high_risk_pct                = round(high_risk_n / max(n_total, 1), 4),
        total_financial_exposure     = round(total_fin, 2),
        currency                     = currency,
        burnout_hotspot              = burnout_hot,
        most_at_risk_dept            = most_at_risk,
        sustainability_score         = sustainability,
        early_warning_level          = ew_level,
        department_column_found      = dept_col_found,
        department_risks             = department_risks,
        top_risk_factors             = top_factors,
    )


# ─────────────────────────────────────────────────────────────────────────────
# UNSUPERVISED RISK SCORING
# ─────────────────────────────────────────────────────────────────────────────

def unsupervised_risk_scores(df: pd.DataFrame,
                              sem_map: Optional[SemanticMap] = None) -> np.ndarray:
    n     = len(df)
    score = np.zeros(n)
    total_weight = 0.0

    risk_features = [
        ("BurnoutRiskComposite",    0.30, False),
        ("RetentionRisk",           0.25, False),
        ("SatisfactionIndex",       0.20, True),
        ("EngagementScore",         0.15, True),
        ("EmployeeStabilityRisk",   0.10, False),
    ]
    for col, w, inverted in risk_features:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").fillna(0.5).values
            score += (1 - s if inverted else s) * w
            total_weight += w

    if total_weight > 0:
        score /= total_weight
    else:
        num_df = df.select_dtypes(include=[np.number])
        if len(num_df.columns) > 0:
            from sklearn.preprocessing import MinMaxScaler
            scaled = MinMaxScaler().fit_transform(num_df.fillna(0))
            score  = scaled.mean(axis=1)

    return np.clip(score, 0, 1).astype(float)
