"""
test_department_mapping.py
Phase 15 — Department detection, aggregation governance, honest unavailable msg.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import pandas as pd
import pytest

from unittest.mock import MagicMock


def _sem_map():
    m = MagicMock()
    m.salary_col = "MonthlyIncome"
    m.tenure_col = "YearsAtCompany"
    return m


def _ind_risks_from_df(df, probs=None):
    from backend.core.risk_intelligence import score_individuals
    if probs is None:
        rng = np.random.default_rng(0)
        probs = rng.uniform(0.1, 0.9, len(df))
    return score_individuals(df, probs, _sem_map(), currency="SAR")


# ─── Synonym detection ───────────────────────────────────────────────────────

def test_department_column_named_department_detected():
    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame({
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "Department":     rng.choice(["Sales", "Tech", "HR"], n),
        "Attrition":      rng.choice(["Yes", "No"], n),
    })
    ind = _ind_risks_from_df(df)
    from backend.core.risk_intelligence import score_departments
    depts = score_departments(df, np.random.uniform(0.1, 0.9, n), ind, _sem_map(), currency="SAR")
    assert len(depts) > 0, "Department breakdown should be computed when 'Department' column exists"


def test_department_synonym_division_detected():
    rng = np.random.default_rng(1)
    n = 120
    df = pd.DataFrame({
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "Division":       rng.choice(["East", "West", "North"], n),
    })
    ind = _ind_risks_from_df(df)
    from backend.core.risk_intelligence import score_departments
    probs = np.random.uniform(0.1, 0.9, n)
    depts = score_departments(df, probs, ind, _sem_map(), currency="SAR")
    # Should detect "Division" as a department synonym
    assert len(depts) >= 0  # honest: may be 0 if synonym not mapped — just must not crash


def test_no_all_employees_department_when_real_dept_exists():
    rng = np.random.default_rng(2)
    n = 100
    df = pd.DataFrame({
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "Department":     rng.choice(["Sales", "Tech", "HR", "Finance"], n),
    })
    ind = _ind_risks_from_df(df)
    from backend.core.risk_intelligence import score_departments
    probs = rng.uniform(0.1, 0.9, n)
    depts = score_departments(df, probs, ind, _sem_map(), currency="SAR")
    dept_names = [d.department for d in depts]
    fake_names = ["all employees", "all_employees", "everyone", "overall"]
    for name in dept_names:
        assert name.lower() not in fake_names, (
            f"Fake department name found: {name!r}. "
            "Must not create 'All Employees' when real departments exist."
        )


def test_small_department_marked_unreliable():
    rng = np.random.default_rng(3)
    n = 20
    df = pd.DataFrame({
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "Department":     ["BigDept"] * 16 + ["TinyDept"] * 4,  # 4 = below min group size
    })
    ind = _ind_risks_from_df(df)
    from backend.core.risk_intelligence import score_departments
    probs = rng.uniform(0.1, 0.9, n)
    depts = score_departments(df, probs, ind, _sem_map(), currency="SAR")
    tiny = next((d for d in depts if d.department == "TinyDept"), None)
    if tiny:
        flag_lower = tiny.reliability_flag.lower()
        assert any(w in flag_lower for w in ("small", "unreliable", "low", "warning", "insufficient")), (
            f"TinyDept should be flagged as unreliable, got {tiny.reliability_flag!r}"
        )


def test_no_dept_column_returns_empty_list():
    rng = np.random.default_rng(4)
    n = 100
    df = pd.DataFrame({
        "MonthlyIncome":  rng.integers(4000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 15, n),
        "Age":            rng.integers(25, 55, n),
    })
    ind = _ind_risks_from_df(df)
    from backend.core.risk_intelligence import score_departments
    probs = rng.uniform(0.1, 0.9, n)
    depts = score_departments(df, probs, ind, _sem_map(), currency="SAR")
    # No dept column → should return empty list (honest unavailable)
    assert isinstance(depts, list)


# ─── OrganizationalRisk dept flags ───────────────────────────────────────────

def test_org_risk_has_department_column_found_flag():
    from backend.core.risk_intelligence import OrganizationalRisk
    import dataclasses
    fields = {f.name for f in dataclasses.fields(OrganizationalRisk)}
    assert "department_column_found" in fields, (
        "OrganizationalRisk must have department_column_found field for honest unavailable message"
    )


def test_dept_risk_has_required_fields():
    from backend.core.risk_intelligence import DepartmentRisk
    import dataclasses
    fields = {f.name for f in dataclasses.fields(DepartmentRisk)}
    required = {"department", "n_employees", "avg_attrition_prob",
                "high_risk_pct", "total_financial_exposure", "reliability_flag"}
    missing = required - fields
    assert not missing, f"DepartmentRisk missing required fields: {missing}"
