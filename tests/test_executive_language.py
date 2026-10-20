"""
test_executive_language.py
Phase 15 — Executive language safety: forbidden words, safe framing,
mandatory disclaimer, no employee=biosignal rows.
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from config.settings import HUMAN_OVERSIGHT_DISCLAIMER, FORBIDDEN_EXECUTIVE_PHRASES


# ─── HUMAN_OVERSIGHT_DISCLAIMER ──────────────────────────────────────────────

def test_disclaimer_exists():
    assert HUMAN_OVERSIGHT_DISCLAIMER and len(HUMAN_OVERSIGHT_DISCLAIMER) > 80

def test_disclaimer_mentions_human_oversight():
    text = HUMAN_OVERSIGHT_DISCLAIMER.lower()
    assert "human" in text or "oversight" in text

def test_disclaimer_prohibits_sole_reliance():
    text = HUMAN_OVERSIGHT_DISCLAIMER.lower()
    assert any(w in text for w in ("not", "no", "sole", "only", "without", "never"))

def test_disclaimer_no_forbidden_words():
    text = HUMAN_OVERSIGHT_DISCLAIMER.lower()
    forbidden = ["terminate", "fire ", "dismiss", "layoff", "lay off"]
    for w in forbidden:
        assert w not in text, f"Disclaimer contains forbidden word: {w!r}"


# ─── FORBIDDEN_EXECUTIVE_PHRASES ─────────────────────────────────────────────

def test_forbidden_phrases_list_exists():
    assert isinstance(FORBIDDEN_EXECUTIVE_PHRASES, (list, tuple))
    assert len(FORBIDDEN_EXECUTIVE_PHRASES) >= 5

def test_forbidden_phrases_include_critical_terms():
    combined = " ".join(FORBIDDEN_EXECUTIVE_PHRASES).lower()
    # Must block termination language
    assert any(term in combined for term in ("terminat", "fire", "layoff", "dismiss"))


# ─── InsightReport language safety ───────────────────────────────────────────

def _make_org_risk(attrition=0.70, high_risk=50, total=200,
                   financial=500000.0, currency="SAR"):
    from unittest.mock import MagicMock
    m = MagicMock()
    m.overall_attrition_risk   = attrition
    m.high_risk_employees      = high_risk
    m.total_employees          = total
    m.high_risk_pct            = high_risk / total
    m.total_financial_exposure = financial
    m.currency                 = currency
    m.total_financial_exposure_usd = financial
    m.early_warning_level      = "Critical"
    m.most_at_risk_dept        = None
    m.department_risks         = []
    m.sustainability_score     = 55.0
    m.burnout_hotspot          = None
    return m


def _insight_texts(dataset_type="hr_attrition"):
    from backend.core.insight_generator import InsightGenerator
    org = _make_org_risk()
    rep = InsightGenerator().generate(
        dataset_type=dataset_type,
        org_risk=org,
        model_auc=0.78,
    )
    texts = [rep.executive_summary]
    for ins in rep.insights:
        texts.extend([ins.title, ins.body, ins.action or ""])
    return texts


def test_no_termination_language_in_insights():
    forbidden = ["terminat", "fire ", "fires ", "dismissed", "layoff", "lay off"]
    for text in _insight_texts():
        low = text.lower()
        for word in forbidden:
            assert word not in low, f"Forbidden word {word!r} found in insight: {text[:100]}"


def test_no_usd_hardcoding_in_insights():
    texts = _insight_texts()
    for text in texts:
        assert " USD" not in text, f"Hardcoded USD found in: {text[:100]}"
        assert "$ " not in text or "SAR" in " ".join(texts), \
            f"Possible USD '$' symbol found in: {text[:100]}"


def test_financial_exposure_uses_currency():
    from backend.core.insight_generator import InsightGenerator
    org = _make_org_risk(financial=1_000_000, currency="SAR")
    rep = InsightGenerator().generate(
        dataset_type="hr_attrition",
        org_risk=org,
        currency="SAR",
    )
    full_text = rep.executive_summary + " ".join(i.body for i in rep.insights)
    # Should contain currency symbol or code, not raw USD
    assert "USD" not in full_text, "USD appears in SAR-configured report"


def test_exec_summary_uses_associative_not_causal():
    from backend.core.insight_generator import InsightGenerator
    org = _make_org_risk()
    rep = InsightGenerator().generate(
        dataset_type="hr_attrition", org_risk=org, model_auc=0.78,
    )
    causal_phrases = ["causes", "causes ", "will leave", "will resign", "will quit"]
    for phrase in causal_phrases:
        assert phrase not in rep.executive_summary.lower(), \
            f"Causal phrase {phrase!r} found in executive summary"


def test_risk_headline_is_valid_value():
    from backend.core.insight_generator import InsightGenerator
    org = _make_org_risk()
    rep = InsightGenerator().generate(
        dataset_type="hr_attrition", org_risk=org, model_auc=0.78,
    )
    assert rep.risk_headline in ("Critical", "Elevated", "Watchlist", "Stable")


# ─── Report generator scientific validity section ────────────────────────────

def test_report_has_scientific_validity_section():
    from backend.core.report_generator import ReportGenerator
    rg = ReportGenerator()
    rep = rg.generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="Workforce Survey",
        n_rows=500,
        n_features=20,
        data_quality_score=0.80,
        target_column="Attrition",
        model_type="RandomForest",
        auc_score=0.82,
        training_mode="AutoML",
        top_features=[],
        attrition_rate=0.25,
        risk_distribution={"High Risk": 50, "Lower Risk": 450},
        bias_risk_level="acceptable",
        ethical_disclaimer="All predictions require HR review.",
        provenance_steps=["Raw data", "Cleaned", "Modelled"],
        caveats=[],
        governed_confidence=0.78,
        leakage_n_critical=0,
        leakage_risk_score=0.05,
        calibration_quality_label="Good",
        brier_score=0.08,
        calibration_ece=0.03,
    )
    section_titles = [s.title for s in rep.sections]
    assert "Scientific Validity & Model Integrity" in section_titles


def test_report_scientific_section_shows_deployment_verdict():
    from backend.core.report_generator import ReportGenerator
    rg = ReportGenerator()
    rep = rg.generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="Attrition",
        n_rows=500,
        n_features=15,
        data_quality_score=0.80,
        target_column="Attrition",
        model_type="XGBoost",
        auc_score=0.79,
        training_mode="AutoML",
        top_features=[],
        attrition_rate=0.20,
        risk_distribution={},
        bias_risk_level="acceptable",
        ethical_disclaimer="HR review required.",
        provenance_steps=[],
        caveats=[],
        governed_confidence=0.75,
        leakage_n_critical=1,  # critical leakage
    )
    sci = next(s for s in rep.sections if s.title == "Scientific Validity & Model Integrity")
    assert "NOT SAFE" in sci.content or "CAUTION" in sci.content


def test_report_no_usd_in_output():
    from backend.core.report_generator import ReportGenerator
    rg = ReportGenerator()
    rep = rg.generate_hr_report(
        dataset_type="hr_attrition",
        dataset_subtype="Attrition",
        n_rows=300,
        n_features=10,
        data_quality_score=0.75,
        target_column="Attrition",
        model_type="LogisticRegression",
        auc_score=0.72,
        training_mode="AutoML",
        top_features=[],
        attrition_rate=0.18,
        risk_distribution={},
        bias_risk_level="acceptable",
        ethical_disclaimer="HR review required.",
        provenance_steps=[],
        caveats=[],
        governed_confidence=0.70,
        currency="SAR",
    )
    assert "USD" not in rep.full_text, "Hardcoded USD found in report text"
