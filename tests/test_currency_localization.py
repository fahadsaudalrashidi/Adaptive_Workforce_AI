"""
test_currency_localization.py
Phase 15 — SAR default everywhere; no hardcoded USD in outputs.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from config.settings import DEFAULT_CURRENCY, CURRENCY_SYMBOLS, CURRENCY_OPTIONS


# ─── settings ────────────────────────────────────────────────────────────────

def test_default_currency_is_sar():
    assert DEFAULT_CURRENCY == "SAR", f"Default currency must be SAR, got {DEFAULT_CURRENCY!r}"


def test_currency_symbols_has_sar():
    assert "SAR" in CURRENCY_SYMBOLS


def test_currency_options_includes_sar():
    assert "SAR" in CURRENCY_OPTIONS


def test_sar_symbol_not_dollar():
    assert CURRENCY_SYMBOLS["SAR"] != "$", "SAR symbol must not be $"


# ─── risk_intelligence currency propagation ───────────────────────────────────

def _make_ind_risks(currency="SAR"):
    from unittest.mock import MagicMock
    import numpy as np
    risks = []
    for i in range(50):
        r = MagicMock()
        r.attrition_probability = float(np.random.uniform(0.1, 0.9))
        r.risk_level = "High" if r.attrition_probability > 0.5 else "Low"
        r.burnout_risk = None
        r.engagement_risk = None
        r.financial_exposure = 60000.0
        r.currency = currency
        r.employee_idx = i
        risks.append(r)
    return risks


def test_score_organization_uses_sar_default():
    from backend.core.risk_intelligence import score_organization, score_individuals
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(42)
    n = 100
    df = pd.DataFrame({
        "Age": rng.integers(22, 60, n),
        "MonthlyIncome": rng.integers(3000, 20000, n).astype(float),
        "YearsAtCompany": rng.integers(0, 20, n),
    })
    from unittest.mock import MagicMock
    sem_map = MagicMock()
    sem_map.salary_col = "MonthlyIncome"
    sem_map.tenure_col = "YearsAtCompany"
    probs = rng.uniform(0.1, 0.9, n)
    ind = score_individuals(df, probs, sem_map, currency="SAR")
    org = score_organization(ind, [], currency="SAR")
    assert org.currency == "SAR", f"OrgRisk.currency should be SAR, got {org.currency!r}"


def test_insight_generator_sar_no_usd():
    from backend.core.insight_generator import InsightGenerator
    from unittest.mock import MagicMock
    org = MagicMock()
    org.overall_attrition_risk   = 0.55
    org.high_risk_employees      = 30
    org.total_employees          = 100
    org.high_risk_pct            = 0.30
    org.total_financial_exposure = 500_000.0
    org.currency                 = "SAR"
    org.total_financial_exposure_usd = 500_000.0
    org.early_warning_level      = "Elevated"
    org.most_at_risk_dept        = None
    org.department_risks         = []
    org.sustainability_score     = 65.0
    org.burnout_hotspot          = None
    rep = InsightGenerator().generate(
        dataset_type="hr_attrition",
        org_risk=org,
        currency="SAR",
    )
    full = rep.executive_summary + " ".join(i.body for i in rep.insights)
    assert "USD" not in full, f"USD found in SAR-mode insight report: {full[:200]}"


def test_report_generator_sar_no_usd():
    from backend.core.report_generator import ReportGenerator
    rep = ReportGenerator().generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="Attrition",
        n_rows=300, n_features=10,
        data_quality_score=0.80,
        target_column="Attrition",
        model_type="RandomForest",
        auc_score=0.78,
        training_mode="AutoML",
        top_features=[],
        attrition_rate=0.22,
        risk_distribution={},
        bias_risk_level="acceptable",
        ethical_disclaimer="HR review required.",
        provenance_steps=[],
        caveats=[],
        governed_confidence=0.75,
        currency="SAR",
    )
    assert "USD" not in rep.full_text, "Hardcoded USD in report full_text"


# ─── financial exposure field naming ─────────────────────────────────────────

def test_org_risk_uses_total_financial_exposure_not_usd():
    """OrganizationalRisk must have total_financial_exposure (not only _usd)."""
    from backend.core.risk_intelligence import OrganizationalRisk
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(OrganizationalRisk)}
    assert "total_financial_exposure" in field_names


def test_org_risk_usd_alias_equals_main_field():
    """backward-compat: total_financial_exposure_usd must equal total_financial_exposure."""
    import numpy as np, pandas as pd
    from backend.core.risk_intelligence import score_individuals, score_organization
    from unittest.mock import MagicMock
    rng = np.random.default_rng(0)
    n = 80
    df = pd.DataFrame({
        "MonthlyIncome": rng.integers(5000, 15000, n).astype(float),
        "YearsAtCompany": rng.integers(1, 10, n),
    })
    sem_map = MagicMock()
    sem_map.salary_col = "MonthlyIncome"
    sem_map.tenure_col = "YearsAtCompany"
    probs = rng.uniform(0.2, 0.8, n)
    ind = score_individuals(df, probs, sem_map, currency="SAR")
    org = score_organization(ind, [], currency="SAR")
    assert org.total_financial_exposure_usd == org.total_financial_exposure
