"""
Semantic Mapper — AI Column Mapping Engine

Maps raw column names → semantic categories using a multi-stage pipeline:
  1. Exact / normalized alias match
  2. Keyword substring scoring
  3. Fuzzy token matching (rapidfuzz)
  4. Value-distribution heuristics (binary Yes/No → target/flag, etc.)

Returns a SemanticMap with per-column assignments and confidence scores.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ── optional: rapidfuzz ────────────────────────────────────────────────────
try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_FUZZ = True
except ImportError:
    _HAS_FUZZ = False
    logger.debug("rapidfuzz not installed — fuzzy matching disabled")

from config.settings import (
    SEMANTIC_CATEGORIES,
    SEMANTIC_EXACT_SCORE,
    SEMANTIC_HIGH_SCORE,
    SEMANTIC_MEDIUM_SCORE,
    SEMANTIC_LOW_SCORE,
    SEMANTIC_REJECT_SCORE,
    FUZZY_MATCH_CUTOFF,
)


# ─────────────────────────────────────────────────────────────────────────────
# ALIAS DICTIONARY  (category → list of exact / near-exact column names)
# ─────────────────────────────────────────────────────────────────────────────

_ALIASES: Dict[str, List[str]] = {
    "target": [
        "attrition", "turnover", "left_company", "left", "churned", "churn",
        "resigned", "terminated", "separated", "exit_flag", "is_attrition",
        "attrition_flag", "voluntary_exit", "outcome", "target", "label", "y",
    ],
    "employee_id": [
        "employee_id", "emp_id", "employeeid", "staff_id", "worker_id",
        "person_id", "id", "employee_number", "emp_no", "emp_number",
    ],
    "timestamp": [
        "date", "timestamp", "datetime", "created_at", "updated_at",
        "hire_date", "join_date", "start_date", "end_date", "survey_date",
        "record_date", "period", "month", "year",
    ],
    "age": ["age", "employee_age", "age_years", "dob", "birth_year"],
    "tenure": [
        "tenure", "years_at_company", "yearsatcompany", "years_experience",
        "total_working_years", "totalworkingyears", "years_in_role",
        "years_with_curr_manager", "months_at_company", "seniority",
        "service_length", "service_years",
    ],
    "department": [
        "department", "dept", "division", "business_unit", "team",
        "function", "group", "unit", "org_unit", "department_name",
    ],
    "job_level": [
        "job_level", "joblevel", "level", "grade", "seniority_level",
        "salary_level", "pay_grade", "band", "tier", "rank", "position_level",
        "job_grade",
    ],
    "gender": [
        "gender", "sex", "gender_identity", "employee_gender",
    ],
    "education": [
        "education", "education_level", "education_field", "degree",
        "qualification", "academic_level", "educationlevel",
    ],
    "salary": [
        "salary", "monthly_income", "monthlyincome", "annual_salary",
        "compensation", "total_comp", "base_pay", "wage", "income",
        "hourly_rate", "daily_rate", "monthly_rate", "pay",
    ],
    "performance": [
        "performance_rating", "performancerating", "performance_score",
        "perf_rating", "appraisal_score", "review_score", "kpi_score",
        "rating", "performance",
    ],
    "satisfaction": [
        "satisfaction", "job_satisfaction", "jobsatisfaction",
        "environment_satisfaction", "environmentsatisfaction",
        "relationship_satisfaction", "relationshipsatisfaction",
        "work_life_balance", "worklifebalance", "employee_satisfaction",
        "life_satisfaction",
    ],
    "engagement": [
        "engagement", "engagement_score", "employee_engagement",
        "enps", "pulse_score", "motivation", "involvement",
        "job_involvement", "jobinvolvement",
    ],
    "burnout": [
        "burnout", "burnout_score", "emotional_exhaustion", "exhaustion",
        "cynicism", "depersonalization", "maslach_score", "mbi_score",
    ],
    "overtime": [
        "overtime", "over_time", "extra_hours", "overtime_flag",
        "works_overtime", "ot_hours",
    ],
    "workload": [
        "workload", "work_pressure", "num_projects", "numprojects",
        "hours_per_week", "hoursperweek", "work_hours", "weekly_hours",
        "projects_completed", "task_count",
    ],
    "manager_quality": [
        "manager_rating", "manager_score", "manager_support",
        "years_with_manager", "yearswithcurrmanager", "supervisor_rating",
        "managerial_support", "manager_effectiveness",
    ],
    "team_size": [
        "team_size", "direct_reports", "reports_to", "num_direct_reports",
        "headcount", "span_of_control",
    ],
    "distance": [
        "distance", "distance_from_home", "distancefromhome",
        "commute_distance", "commute_km", "commute_miles",
    ],
    "promotion": [
        "promotion", "years_since_last_promotion", "yearssincellastpromotion",
        "last_promotion", "promotions_in_last5years", "promotion_rate",
        "was_promoted",
    ],
    "training": [
        "training", "training_times_last_year", "trainingtimeslastyear",
        "training_hours", "courses_completed", "certifications",
        "learning_hours",
    ],
    "absence": [
        "absence", "absences", "absence_rate", "sick_days", "days_absent",
        "absenteeism",
    ],
    "role_change": [
        "num_companies_worked", "numcompaniesworked", "job_changes",
        "company_count", "previous_employers", "career_changes",
        "role_changes",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# KEYWORD SIGNALS (category → substrings to scan in column name)
# ─────────────────────────────────────────────────────────────────────────────

_KEYWORDS: Dict[str, List[str]] = {
    "target":          ["attrit", "churn", "exit", "left", "resign", "terminat", "turnover"],
    "employee_id":     ["id", "emp", "staff", "worker", "person", "number"],
    "timestamp":       ["date", "time", "month", "year", "period", "created", "hired"],
    "age":             ["age", "birth", "dob"],
    "tenure":          ["tenure", "years", "service", "seniority", "months_at"],
    "department":      ["dept", "department", "division", "unit", "function", "team"],
    "job_level":       ["level", "grade", "band", "tier", "rank", "salary_level"],
    "gender":          ["gender", "sex"],
    "education":       ["educat", "degree", "qualif", "academic"],
    "salary":          ["salary", "income", "wage", "pay", "comp", "rate"],
    "performance":     ["performance", "perf", "rating", "apprais", "review", "kpi"],
    "satisfaction":    ["satisf", "balance", "wellbeing"],
    "engagement":      ["engag", "motivat", "involve", "enps", "pulse"],
    "burnout":         ["burnout", "exhaust", "cynicism", "deperso", "mbi"],
    "overtime":        ["overtime", "over_time", "ot_"],
    "workload":        ["workload", "hours", "projects", "tasks", "load"],
    "manager_quality": ["manager", "supervisor", "lead"],
    "team_size":       ["team_size", "direct_report", "headcount", "span"],
    "distance":        ["distance", "commute"],
    "promotion":       ["promot", "last_promo"],
    "training":        ["train", "course", "certif", "learning"],
    "absence":         ["absence", "absent", "sick"],
    "role_change":     ["compan", "job_change", "previous_employer"],
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColumnMapping:
    original_name: str
    semantic_category: str
    confidence: float       # 0–1
    method: str             # "exact", "keyword", "fuzzy", "value_heuristic", "unknown"
    alternative_categories: List[Tuple[str, float]] = field(default_factory=list)
    notes: str = ""


@dataclass
class SemanticMap:
    mappings: Dict[str, ColumnMapping]      # original_name → mapping
    target_col: Optional[str]   = None
    id_col: Optional[str]       = None
    date_cols: List[str]        = field(default_factory=list)
    feature_cols: List[str]     = field(default_factory=list)
    unmapped_cols: List[str]    = field(default_factory=list)
    coverage: float             = 0.0   # fraction of cols mapped with confidence ≥ threshold

    def get(self, category: str) -> List[str]:
        """Return all columns assigned to a given semantic category."""
        return [m.original_name for m in self.mappings.values()
                if m.semantic_category == category]

    def confident(self, threshold: float = SEMANTIC_LOW_SCORE) -> List[ColumnMapping]:
        return [m for m in self.mappings.values() if m.confidence >= threshold]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: normalise column name
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    """Lowercase, strip, collapse separators to underscore."""
    s = name.lower().strip()
    s = re.sub(r"[\s\-./]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: Exact alias match
# ─────────────────────────────────────────────────────────────────────────────

def _stage_exact(norm: str) -> Tuple[Optional[str], float]:
    for cat, aliases in _ALIASES.items():
        if norm in [_normalise(a) for a in aliases]:
            return cat, SEMANTIC_EXACT_SCORE
    return None, 0.0


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: Keyword substring scoring
# ─────────────────────────────────────────────────────────────────────────────

def _stage_keyword(norm: str) -> List[Tuple[str, float]]:
    scores: Dict[str, float] = {}
    for cat, kws in _KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in norm)
        if hits:
            scores[cat] = min(SEMANTIC_HIGH_SCORE,
                              SEMANTIC_MEDIUM_SCORE + hits * 0.10)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3: Fuzzy token matching
# ─────────────────────────────────────────────────────────────────────────────

def _stage_fuzzy(norm: str) -> List[Tuple[str, float]]:
    if not _HAS_FUZZ:
        return []
    scores: Dict[str, float] = {}
    for cat, aliases in _ALIASES.items():
        best = 0.0
        for alias in aliases:
            ratio = _fuzz.token_set_ratio(norm, _normalise(alias)) / 100.0
            if ratio > best:
                best = ratio
        if best >= FUZZY_MATCH_CUTOFF:
            scores[cat] = round(best * SEMANTIC_MEDIUM_SCORE, 4)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 4: Value-distribution heuristics
# ─────────────────────────────────────────────────────────────────────────────

def _stage_value_heuristic(series: pd.Series) -> Tuple[Optional[str], float, str]:
    """Infer semantic category from the actual value distribution."""
    s    = series.dropna()
    n_u  = s.nunique()
    note = ""

    if n_u == 0:
        return None, 0.0, ""

    if n_u == 2:
        vals = set(str(v).lower().strip() for v in s.unique())
        if vals <= {"yes", "no", "y", "n", "1", "0", "true", "false"}:
            # check if name contains target-like words
            col_l = series.name.lower() if series.name else ""
            for kw in ["attrit", "exit", "left", "churn", "resign", "turnover"]:
                if kw in col_l:
                    return "target", SEMANTIC_HIGH_SCORE, "binary Yes/No with target keyword"
            return "binary_flag", SEMANTIC_MEDIUM_SCORE, "binary Yes/No field"

    if pd.api.types.is_numeric_dtype(s):
        # Detect Likert scales (1–5 or 1–7 integers)
        if s.min() >= 1 and s.max() <= 7 and n_u <= 7 and (s == s.round()).all():
            note = f"Likert scale 1–{int(s.max())}"
            return "psychological_score", SEMANTIC_MEDIUM_SCORE, note

        # Large range positive floats → likely salary
        if s.min() >= 1000 and s.max() >= 30000:
            return "salary", SEMANTIC_LOW_SCORE, "large positive numeric → possible salary"

        # 0–100 range floats → likely score/rating
        if 0 <= s.min() and s.max() <= 100 and n_u > 5:
            return "numeric_kpi", SEMANTIC_LOW_SCORE, "0–100 range → score/KPI"

    return None, 0.0, ""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MAPPER
# ─────────────────────────────────────────────────────────────────────────────

class SemanticMapper:
    """
    Maps a DataFrame's columns to semantic categories.

    Usage:
        mapper = SemanticMapper()
        sem_map = mapper.map(df)
    """

    def map(self, df: pd.DataFrame,
            user_overrides: Optional[Dict[str, str]] = None) -> SemanticMap:
        """
        Parameters
        ----------
        df             : input DataFrame
        user_overrides : {original_col: category} — hard-coded by user in UI
        """
        user_overrides = user_overrides or {}
        mappings: Dict[str, ColumnMapping] = {}

        for col in df.columns:
            # User override takes absolute precedence
            if col in user_overrides:
                mappings[col] = ColumnMapping(
                    original_name      = col,
                    semantic_category  = user_overrides[col],
                    confidence         = SEMANTIC_EXACT_SCORE,
                    method             = "user_override",
                )
                continue

            norm = _normalise(col)
            alts: List[Tuple[str, float]] = []

            # Stage 1: exact
            cat, conf = _stage_exact(norm)
            method = "exact"

            # Stage 2: keyword
            if cat is None or conf < SEMANTIC_HIGH_SCORE:
                kw_ranked = _stage_keyword(norm)
                if kw_ranked:
                    top_cat, top_conf = kw_ranked[0]
                    if top_conf > conf:
                        cat, conf = top_cat, top_conf
                        method    = "keyword"
                    alts.extend(kw_ranked[1:4])

            # Stage 3: fuzzy
            if cat is None or conf < SEMANTIC_MEDIUM_SCORE:
                fz_ranked = _stage_fuzzy(norm)
                if fz_ranked:
                    top_cat, top_conf = fz_ranked[0]
                    if top_conf > conf:
                        cat, conf = top_cat, top_conf
                        method    = "fuzzy"
                    alts.extend(fz_ranked[1:3])

            # Stage 4: value heuristic
            if cat is None or conf < SEMANTIC_LOW_SCORE:
                vh_cat, vh_conf, vh_note = _stage_value_heuristic(df[col])
                if vh_cat and vh_conf > conf:
                    cat, conf = vh_cat, vh_conf
                    method    = "value_heuristic"

            # Final decision
            if cat is None or conf < SEMANTIC_REJECT_SCORE:
                cat    = "unknown"
                method = "unknown"
                conf   = 0.0

            # Deduplicate alts
            seen = {cat}
            clean_alts = []
            for a_cat, a_conf in alts:
                if a_cat not in seen:
                    clean_alts.append((a_cat, a_conf))
                    seen.add(a_cat)

            mappings[col] = ColumnMapping(
                original_name            = col,
                semantic_category        = cat,
                confidence               = round(conf, 4),
                method                   = method,
                alternative_categories   = clean_alts[:3],
            )

        # ── build SemanticMap meta ──────────────────────────────────────
        target_candidates = [m for m in mappings.values()
                             if m.semantic_category == "target"
                             and m.confidence >= SEMANTIC_LOW_SCORE]
        target_col = target_candidates[0].original_name if target_candidates else None

        id_candidates = [m for m in mappings.values()
                         if m.semantic_category == "employee_id"]
        id_col = id_candidates[0].original_name if id_candidates else None

        date_cols = [m.original_name for m in mappings.values()
                     if m.semantic_category == "timestamp"]

        skip_cats = {"target", "employee_id", "timestamp", "text_free", "unknown"}
        feature_cols = [m.original_name for m in mappings.values()
                        if m.semantic_category not in skip_cats
                        and m.confidence >= SEMANTIC_REJECT_SCORE]

        unmapped = [m.original_name for m in mappings.values()
                    if m.semantic_category == "unknown"]

        n_mapped = sum(1 for m in mappings.values()
                       if m.semantic_category != "unknown"
                       and m.confidence >= SEMANTIC_LOW_SCORE)
        coverage = n_mapped / max(len(mappings), 1)

        sem_map = SemanticMap(
            mappings     = mappings,
            target_col   = target_col,
            id_col       = id_col,
            date_cols    = date_cols,
            feature_cols = feature_cols,
            unmapped_cols = unmapped,
            coverage     = round(coverage, 4),
        )

        logger.info(
            "Semantic mapping: %d/%d cols mapped (coverage=%.0f%%), target=%s",
            n_mapped, len(mappings), coverage * 100, target_col,
        )
        return sem_map

    def describe(self, sem_map: SemanticMap) -> str:
        """Human-readable summary of the mapping."""
        lines = [f"Semantic Map — {len(sem_map.mappings)} columns, "
                 f"coverage={sem_map.coverage:.0%}",
                 f"Target: {sem_map.target_col or 'NOT FOUND'}",
                 f"ID col: {sem_map.id_col or 'not detected'}",
                 f"Date cols: {', '.join(sem_map.date_cols) or 'none'}",
                 ""]
        for col, m in sem_map.mappings.items():
            flag = "✓" if m.confidence >= SEMANTIC_LOW_SCORE else "?"
            lines.append(f"  {flag} {col:35s}→ {m.semantic_category:25s} "
                         f"[{m.confidence:.2f}, {m.method}]")
        if sem_map.unmapped_cols:
            lines.append(f"\nUnmapped ({len(sem_map.unmapped_cols)}): "
                         f"{', '.join(sem_map.unmapped_cols)}")
        return "\n".join(lines)
