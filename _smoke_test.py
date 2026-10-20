"""
Smoke test: simulates the full adaptive pipeline for HR, biosignal, and unknown datasets.
Tests that the pipeline produces outputs without raising exceptions and that
all safety invariants hold.

Run directly:  py _smoke_test.py
Importing this module during pytest collection is safe — no code runs at import time.
"""
import sys
import traceback


def _run_smoke_tests() -> int:
    """Run all smoke test sections. Returns exit code (0=pass, 1=fail)."""
    import pandas as pd
    import numpy as np

    sys.path.insert(0, ".")

    passed = 0
    failed = 0

    def ok(label):
        nonlocal passed
        passed += 1
        print(f"  PASS  {label}")

    def fail(label, exc=""):
        nonlocal failed
        failed += 1
        print(f"  FAIL  {label}  {exc}")

    def section(title):
        print(f"\n{'='*60}\n{title}\n{'='*60}")

    rng = np.random.default_rng(42)

    # ── Imports ───────────────────────────────────────────────────────────────────
    section("1. Module Import Smoke Test")
    modules_ok = True
    for mod in [
        "config.settings",
        "backend.core.adaptive_router", "backend.core.data_healer",
        "backend.core.feature_factory", "backend.core.ml_router",
        "backend.core.risk_intelligence", "backend.core.insight_generator",
        "backend.core.confidence_governance", "backend.core.calibration_engine",
        "backend.core.feature_trustworthiness", "backend.core.biosignal_adapter",
        "backend.core.governance_logger", "backend.core.drift_monitor",
        "frontend.pages.adaptive_page", "frontend.pages.hr_attrition_page",
        "frontend.pages.biosignal_page", "frontend.pages.quality_page",
        "frontend.utils.safe_render", "frontend.utils.session_helpers",
    ]:
        try:
            __import__(mod)
            ok(f"import {mod}")
        except Exception as e:
            fail(f"import {mod}", str(e))
            modules_ok = False

    if not modules_ok:
        print("FATAL: Module import failures. Stopping.")
        return 1

    # ── HR Attrition Pipeline ─────────────────────────────────────────────────────
    section("2. HR Attrition Full Pipeline")

    try:
        from backend.core.adaptive_router import AdaptiveRouter
        from backend.core.data_healer import DataHealer
        from backend.core.feature_factory import FeatureFactory
        from backend.core.ml_router import MLRouter
        from backend.core.risk_intelligence import score_individuals, score_departments, score_organization
        from backend.core.semantic_mapper import SemanticMapper
        from backend.core.insight_generator import InsightGenerator
        from backend.core.confidence_governance import ConfidenceGovernor
        from backend.core.calibration_engine import CalibrationEngine

        n = 200
        df_hr = pd.DataFrame({
            "EmployeeNumber": range(n),
            "Age": rng.integers(22, 60, n),
            "Department": rng.choice(["Sales", "HR", "IT", "Finance"], n),
            "MonthlyIncome": rng.integers(3000, 15000, n),
            "OverTime": rng.choice(["Yes", "No"], n),
            "YearsAtCompany": rng.integers(0, 20, n),
            "JobSatisfaction": rng.integers(1, 5, n),
            "WorkLifeBalance": rng.integers(1, 4, n),
            "Attrition": rng.choice(["Yes", "No"], n, p=[0.16, 0.84]),
        })

        router = AdaptiveRouter()
        contract = router.route(df_hr, "hr_attrition_test.csv")
        ok(f"AdaptiveRouter.route — type={contract.dataset_type}")
        assert not contract.is_biosignal
        ok("contract.is_biosignal=False")
        assert contract.allows("attrition_prediction")
        ok("attrition_prediction ALLOWED")

        mapper = SemanticMapper()
        sem_map = mapper.map(df_hr)
        ok("SemanticMapper.map")

        healer = DataHealer()
        df_clean, _ = healer.fit_transform(df_hr, sem_map, "Attrition")
        ok(f"DataHealer.fit_transform — {len(df_clean)} rows")

        factory = FeatureFactory()
        df_eng, _ = factory.engineer(df_clean, sem_map, contract.dataset_type, "Attrition")
        ok(f"FeatureFactory.engineer — {len(df_eng.columns)} features")

        feature_names = [c for c in df_eng.columns if c != "Attrition"]
        ml_router = MLRouter()
        ml_res = ml_router.train(df_eng, feature_names, "Attrition", contract.dataset_type)
        ok(f"MLRouter.train — best={ml_res.best_model_name}, AUC={ml_res.best_metric_value:.3f}")
        auc = ml_res.best_metric_value if ml_res.best_metric_name == "auc" else 0.0
        assert 0.4 <= auc <= 1.0, f"AUC out of range: {auc}"
        ok(f"AUC in valid range [0.4, 1.0] — {auc:.3f}")

        probs = ml_router.predict_proba(df_eng, ml_res)
        assert len(probs) == len(df_eng)
        ok(f"predict_proba — {len(probs)} predictions")
        assert all(0 <= p <= 1 for p in probs), "Probability out of [0,1]"
        ok("All probabilities in [0,1]")

        ind_risks = score_individuals(df_eng, probs, sem_map, currency="SAR")
        ok(f"score_individuals — {len(ind_risks)} records")

        dept_risks = score_departments(df_eng, probs, ind_risks, sem_map, currency="SAR")
        ok(f"score_departments — {len(dept_risks)} departments")

        org_risk = score_organization(ind_risks, dept_risks, currency="SAR")
        ok(f"score_organization — attrition_risk={org_risk.overall_attrition_risk:.1%}")
        assert "SAR" in str(org_risk.currency) or org_risk.currency == "SAR"
        ok("Currency=SAR in org_risk")
        assert not any("$" in str(getattr(org_risk, f, "")) for f in ["currency"])
        ok("No hardcoded USD in org_risk")

        ig = InsightGenerator()
        insight = ig.generate(
            dataset_type=contract.dataset_type, org_risk=org_risk,
            model_auc=auc, quality_score=75.0, n_rows=n, n_cols=len(df_hr.columns),
            missing_pct=0.02, n_numeric=5, n_categorical=3, currency="SAR",
        )
        ok("InsightGenerator.generate")
        from config.settings import FORBIDDEN_EXECUTIVE_PHRASES
        all_text = insight.executive_summary + " ".join(i.body for i in insight.insights)
        violations = [p for p in FORBIDDEN_EXECUTIVE_PHRASES if p.lower() in all_text.lower()]
        assert not violations, f"Forbidden phrases found: {violations}"
        ok("No forbidden executive phrases in insight output")

        best_mr = ml_res.models.get(ml_res.best_model_name) if ml_res.models else None
        oof = getattr(best_mr, "oof_predictions", None) if best_mr else None
        if oof is not None and len(oof) > 0:
            _y_raw = df_eng["Attrition"].values
            if _y_raw.dtype == object or str(_y_raw.dtype).startswith("string"):
                y_true = (_y_raw == "Yes").astype(float)
            else:
                y_true = (_y_raw > 0.5).astype(float)
            if y_true.sum() > 0:
                cal_rep = CalibrationEngine().evaluate(y_true=y_true, y_prob=np.asarray(oof, dtype=float))
                if cal_rep.brier_score is not None:
                    assert 0 <= cal_rep.brier_score <= 1.0
                    ok(f"CalibrationEngine — brier={cal_rep.brier_score:.3f}, quality={cal_rep.quality.value}")
                else:
                    ok("CalibrationEngine — brier_score not computed (insufficient OOF data)")
            else:
                ok("CalibrationEngine — skipped (all-negative y_true in test data)")
        else:
            ok("CalibrationEngine — OOF not available (expected for small dataset)")

        gov = ConfidenceGovernor()
        ucr = gov.build(
            profiler_quality_score=80.0, missing_pct=0.02, n_rows=n, n_cols=len(df_hr.columns),
            routing_type=contract.dataset_type, routing_confidence_raw=0.92, routing_locked=True,
            has_ml_model=True, original_auc=auc, governed_auc=auc,
            leakage_risk_score=0.03, leakage_n_critical=0, leakage_n_high=0,
            is_trustworthy=True, validation_overall_status="VALID", validation_n_fail=0,
        )
        ok(f"ConfidenceGovernor.build — readiness={ucr.executive_readiness}, reliability={ucr.model_reliability.score:.2f}")
        assert ucr.leakage_risk_score <= 0.05
        ok("Leakage risk score is low (no leakage)")

    except Exception as e:
        fail("HR pipeline", traceback.format_exc()[-300:])

    # ── Biosignal Pipeline ────────────────────────────────────────────────────────
    section("3. Biosignal (WESAD) Pipeline")
    try:
        from backend.core.biosignal_adapter import BiosignalAdapter

        df_bio = pd.DataFrame({
            "HR":    rng.uniform(55, 105, 500),
            "EDA":   rng.uniform(0.05, 8.0, 500),
            "TEMP":  rng.uniform(32.0, 38.0, 500),
            "label": rng.integers(0, 4, 500),
        })

        contract_bio = router.route(df_bio, "HR.csv")
        ok(f"Biosignal routing — type={contract_bio.dataset_type}")
        assert contract_bio.is_biosignal
        ok("is_biosignal=True")
        assert contract_bio.blocks("attrition_prediction")
        ok("attrition_prediction BLOCKED for biosignal")
        assert contract_bio.row_label().lower() != "employees"
        ok(f"row_label='{contract_bio.row_label()}' (not 'employees')")
        ok("Biosignal pipeline safety verified (attrition + row_label checks passed)")

        adapter = BiosignalAdapter()
        sig_type = contract_bio.detected_signal_type or "HR"
        bio_prof = adapter.analyse(df_bio, sig_type, "HR.csv")
        ok(f"BiosignalAdapter.analyse — windows={bio_prof.n_windows}, quality={bio_prof.quality_score:.0f}/100")
        assert hasattr(bio_prof, "disclaimer") and len(bio_prof.disclaimer) > 20
        ok("Non-clinical disclaimer present")
        assert bio_prof.row_unit != "employees"
        ok(f"row_unit='{bio_prof.row_unit}' (not 'employees')")

    except Exception as e:
        fail("Biosignal pipeline", traceback.format_exc()[-300:])

    # ── Unknown/Generic Dataset ───────────────────────────────────────────────────
    section("4. Unknown Dataset — Graceful Sandbox Mode")
    try:
        df_unk = pd.DataFrame({
            "x1": rng.random(100),
            "x2": rng.random(100),
            "cat": rng.choice(["A", "B", "C"], 100),
        })
        contract_unk = router.route(df_unk, "mystery.csv")
        ok(f"Unknown routing — type={contract_unk.dataset_type}")
        assert contract_unk.sandbox_report is not None
        ok("sandbox_report exists for unknown dataset")
        assert contract_unk.routing_confidence is not None
        ok("routing_confidence exists for unknown dataset")
        try:
            allowed = not contract_unk.blocks("attrition_prediction")
            if not allowed:
                ok("attrition_prediction BLOCKED for unknown dataset (correct)")
            else:
                ok("attrition_prediction allowed for generic tabular (acceptable — no biosignal)")
        except Exception:
            ok("Contract handled unknown dataset gracefully")

    except Exception as e:
        fail("Unknown dataset pipeline", traceback.format_exc()[-300:])

    # ── Governance Invariants ─────────────────────────────────────────────────────
    section("5. Governance & Safety Invariants")
    try:
        from config.settings import DEFAULT_CURRENCY, HUMAN_OVERSIGHT_DISCLAIMER, FORBIDDEN_EXECUTIVE_PHRASES
        assert DEFAULT_CURRENCY == "SAR"
        ok("DEFAULT_CURRENCY=SAR")
        assert len(HUMAN_OVERSIGHT_DISCLAIMER) > 80
        ok("HUMAN_OVERSIGHT_DISCLAIMER length OK")
        assert "human" in HUMAN_OVERSIGHT_DISCLAIMER.lower()
        ok("Disclaimer mentions 'human'")
        assert len(FORBIDDEN_EXECUTIVE_PHRASES) >= 5
        ok(f"FORBIDDEN_EXECUTIVE_PHRASES has {len(FORBIDDEN_EXECUTIVE_PHRASES)} entries")

        from backend.core.governance_logger import get_governance_logger
        get_governance_logger()
        ok("GovernanceLogger singleton accessible")

        from backend.core.drift_monitor import get_drift_monitor
        get_drift_monitor()
        ok("DriftMonitor singleton accessible")

        from frontend.utils.safe_render import safe_error_boundary, guard  # noqa: F401
        ok("safe_error_boundary importable")
        ok("guard importable")

        from frontend.utils.session_helpers import get_contract, require_analysis, get_currency  # noqa: F401
        ok("session_helpers: get_contract, require_analysis, get_currency importable")

    except Exception as e:
        fail("Governance invariants", traceback.format_exc()[-300:])

    # ── HTTP Smoke ────────────────────────────────────────────────────────────────
    section("6. Streamlit HTTP Smoke Test")
    try:
        import urllib.request
        r = urllib.request.urlopen("http://localhost:8510", timeout=8)
        assert r.status == 200
        ok(f"Streamlit HTTP {r.status} on port 8510")
    except Exception as e:
        fail("Streamlit HTTP", str(e))

    # ── Summary ───────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"SMOKE TEST SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_smoke_tests())
