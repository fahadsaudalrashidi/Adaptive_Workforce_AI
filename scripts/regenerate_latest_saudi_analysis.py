"""
Repair script — Phase 27B.

Runs the real Saudi Excel dataset through the full backend analysis pipeline
(governance scan → employee scoring → ML validation → simulation → decision
intelligence → DB persistence) WITHOUT requiring a browser upload.

Usage:
    py scripts/regenerate_latest_saudi_analysis.py

Output:
    EMPLOYEE_SCORING_AVAILABLE=True
    TOTAL_EMPLOYEES=1191
    SIMULATION_AVAILABLE=True
    SCENARIOS_COUNT=8
    RECOMMENDED_STRATEGY=True
    SESSION_SAVED=True

After running this script, open the Strategy Simulator and click
"Load from latest analysis" to activate the simulation without re-uploading.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── Saudi dataset location ────────────────────────────────────────────────────
_DATASET_SEARCH_PATHS = [
    pathlib.Path("C:/Users/PvP-Pc/Desktop/datasetssaudi/Original Dataset of Employee Attrition (1).xlsx"),
    _ROOT / "data" / "Original Dataset of Employee Attrition (1).xlsx",
    _ROOT / "uploads" / "Original Dataset of Employee Attrition (1).xlsx",
    _ROOT / "data" / "uploads" / "Original Dataset of Employee Attrition (1).xlsx",
]


def _find_dataset() -> pathlib.Path:
    for p in _DATASET_SEARCH_PATHS:
        if p.exists():
            return p
    # Fallback: search Desktop recursively
    desktop = pathlib.Path("C:/Users/PvP-Pc/Desktop")
    for candidate in desktop.rglob("Original Dataset of Employee Attrition*.xlsx"):
        return candidate
    raise FileNotFoundError(
        "Saudi dataset not found. Searched:\n"
        + "\n".join(f"  {p}" for p in _DATASET_SEARCH_PATHS)
    )


def main() -> None:
    print("=" * 60)
    print("Phase 27B — Saudi Dataset Analysis Repair Script")
    print("=" * 60)

    # ── Find dataset ──────────────────────────────────────────────────────────
    try:
        dataset_path = _find_dataset()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"\nDataset: {dataset_path}")
    print(f"Size:    {dataset_path.stat().st_size:,} bytes")

    raw = dataset_path.read_bytes()
    filename = dataset_path.name
    dataset_hash = hashlib.sha256(raw).hexdigest()[:16]

    # ── Import backend modules ────────────────────────────────────────────────
    from backend.core.secure_file_ingestion import SecureFileIngestion
    from backend.core.dataset_type_classifier import DatasetTypeClassifier
    from backend.core.employee_risk_scoring import EmployeeRiskScorer
    from backend.core.employee_risk_scoring import (
        scored_employee_to_dict,
        dept_summary_to_dict,
    )
    from backend.core.executive_narrative_engine import (
        generate_org_narrative,
        narrative_to_dict,
    )
    from backend.core.workforce_forecasting_engine import (
        generate_workforce_forecast,
        forecast_to_dict,
    )
    from backend.core.ml_validation_engine import run_ml_validation
    from backend.core.workforce_simulation_engine import run_workforce_simulation
    from backend.core.executive_decision_intelligence import (
        run_executive_decision_intelligence,
    )
    from backend.core.executive_index_engine import (
        compute_executive_indices,
        executive_indices_to_dict,
    )
    import backend.core.local_database as _db

    scanner    = SecureFileIngestion()
    classifier = DatasetTypeClassifier()
    scorer     = EmployeeRiskScorer()

    # ── Step 1: Governance scan ───────────────────────────────────────────────
    print("\n[1/7] Governance scan...")
    t0 = time.perf_counter()
    report = scanner.scan(raw, filename, "local")
    ir = report.ingestion_result
    print(f"      readiness_level = {report.readiness_level.value}")
    print(f"      ir.success      = {ir.success}")
    print(f"      ir.row_count    = {ir.row_count}")
    print(f"      pii_detected    = {report.pii_columns_detected}")
    print(f"      leakage         = {report.leakage_columns_detected}")

    if not ir.success or ir.df is None or ir.row_count == 0:
        print("ERROR: File ingestion failed — cannot continue.")
        sys.exit(1)

    # ── Step 2: Dataset classification ───────────────────────────────────────
    print("\n[2/7] Dataset classification...")
    try:
        clf = classifier.classify(ir.df, filename=filename)
        dataset_type = clf.dataset_type.value
        attrition_allowed = clf.attrition_modeling_allowed
        print(f"      dataset_type        = {dataset_type}")
        print(f"      attrition_allowed   = {attrition_allowed}")
        print(f"      confidence          = {round(clf.confidence * 100)}%")
    except Exception as exc:
        print(f"      Classification failed (non-fatal): {exc}")
        dataset_type = "EMPLOYEE_ATTRITION_DATASET"
        attrition_allowed = True

    # ── Step 3: Employee risk scoring ─────────────────────────────────────────
    print("\n[3/7] Employee risk scoring...")
    t3 = time.perf_counter()
    try:
        scored = scorer.score_dataframe(
            ir.df, 1, 5000, None, None, None, "risk_score_0_100", "desc",
        )
        print(f"      total_employee_records    = {scored.total_employee_records}")
        print(f"      average_risk_score        = {round(scored.average_risk_score, 2)}")
        print(f"      average_stability_score   = {round(scored.average_stability_score, 2)}")
        print(f"      risk_band_counts          = {scored.risk_band_counts}")
        print(f"      matched_construct_count   = {scored.matched_construct_count}")
        print(f"      time                      = {time.perf_counter()-t3:.1f}s")
    except Exception as exc:
        print(f"ERROR: Employee scoring failed: {exc}")
        sys.exit(1)

    print(f"\n{'EMPLOYEE_SCORING_AVAILABLE':40s} = True")
    print(f"{'TOTAL_EMPLOYEES':40s} = {scored.total_employee_records}")

    _emp_dicts  = [scored_employee_to_dict(r) for r in scored.scored_records]
    _dept_dicts = [dept_summary_to_dict(s)    for s in scored.department_summary]

    # ── Step 4: Narrative + forecast ──────────────────────────────────────────
    print("\n[4/7] Narrative + workforce forecast...")
    _narrative_dict: dict[str, Any] = {}
    _forecast_dict:  dict[str, Any] = {}
    try:
        _narrative = generate_org_narrative(
            total_records=scored.total_employee_records,
            average_risk_score=scored.average_risk_score,
            average_stability_score=scored.average_stability_score,
            risk_band_counts=scored.risk_band_counts,
            department_summary=_dept_dicts,
            org_risk_driver_summary=scored.org_risk_driver_summary,
            matched_construct_count=scored.matched_construct_count,
            filename=filename,
        )
        _narrative_dict = narrative_to_dict(_narrative)
        print("      Narrative OK")
    except Exception as exc:
        print(f"      Narrative failed (non-fatal): {exc}")

    try:
        _forecast = generate_workforce_forecast(
            total_records=scored.total_employee_records,
            average_risk_score=scored.average_risk_score,
            risk_band_counts=scored.risk_band_counts,
            department_summary=_dept_dicts,
            scored_records_sample=_emp_dicts[:200],
        )
        _forecast_dict = forecast_to_dict(_forecast)
        print("      Forecast OK")
    except Exception as exc:
        print(f"      Forecast failed (non-fatal): {exc}")

    # ── Step 5: ML validation ─────────────────────────────────────────────────
    print("\n[5/7] ML validation...")
    t5 = time.perf_counter()
    _ml: dict[str, Any] = {}
    try:
        _ml = run_ml_validation(ir.df)
        print(f"      available     = {_ml.get('available')}")
        print(f"      target_column = {_ml.get('target_column')}")
        print(f"      best_model    = {_ml.get('best_model')}")
        roc = (_ml.get("conservative") or {}).get("selected_metrics") or {}
        print(f"      conservative_roc_auc = {roc.get('mean_roc_auc')}")
        print(f"      time = {time.perf_counter()-t5:.1f}s")
    except Exception as exc:
        print(f"      ML validation failed (non-fatal): {exc}")

    # ── Step 6: Workforce simulation ──────────────────────────────────────────
    print("\n[6/7] Workforce simulation...")
    _sim: dict[str, Any] = {"available": False, "reason": "Simulation not run"}
    try:
        _sim = run_workforce_simulation(
            scored.total_employee_records,
            scored.average_risk_score,
            scored.average_stability_score,
            scored.risk_band_counts,
            _dept_dicts,
            scored.org_risk_driver_summary,
            _ml if _ml else None,
        )
        print(f"      available            = {_sim['available']}")
        print(f"      scenarios_count      = {len(_sim.get('scenarios', []))}")
        print(f"      recommended_strategy = {_sim.get('recommended_strategy') is not None}")
        if _sim.get("scenarios"):
            for s in _sim["scenarios"][:3]:
                print(f"        [{s['confidence']:6s}] {s['scenario_name_en']}: -{s['estimated_risk_reduction_pct']}%")
    except Exception as exc:
        print(f"      Simulation failed (non-fatal): {exc}")
        _sim = {"available": False, "reason": f"Simulation error: {exc}"}

    print(f"\n{'SIMULATION_AVAILABLE':40s} = {_sim.get('available', False)}")
    print(f"{'SCENARIOS_COUNT':40s} = {len(_sim.get('scenarios', []))}")
    print(f"{'RECOMMENDED_STRATEGY':40s} = {_sim.get('recommended_strategy') is not None}")

    # ── Step 7: Decision intelligence ─────────────────────────────────────────
    print("\n[7/7] Decision intelligence...")
    _di: dict[str, Any] = {"available": False, "reason": "Decision intelligence not run"}
    try:
        _gov_warnings = list(
            (_ml.get("governance") or {}).get("ml_governance_warnings", [])
        ) if _ml else []
        _di = run_executive_decision_intelligence(
            scored.total_employee_records,
            scored.average_risk_score,
            scored.average_stability_score,
            scored.risk_band_counts,
            _dept_dicts,
            scored.org_risk_driver_summary,
            _ml if _ml else None,
            _sim if _sim else None,
            _forecast_dict if _forecast_dict else None,
            _gov_warnings,
        )
        print(f"      available            = {_di.get('available')}")
        print(f"      readiness_level      = {_di.get('decision_readiness_level')}")
        print(f"      priorities           = {len(_di.get('strategic_priorities', []))}")
    except Exception as exc:
        print(f"      Decision intelligence failed (non-fatal): {exc}")

    # ── Step 7B: Executive indices ────────────────────────────────────────────
    print("\n[7B] Executive Index Engine...")
    _executive_indices: dict[str, Any] = {}
    try:
        _idx = compute_executive_indices(
            total_employee_records  = scored.total_employee_records,
            average_risk_score      = scored.average_risk_score,
            average_stability_score = scored.average_stability_score,
            risk_band_counts        = scored.risk_band_counts,
            department_summary      = _dept_dicts,
            org_risk_driver_summary = scored.org_risk_driver_summary,
            matched_construct_count = scored.matched_construct_count,
            ml_validation           = _ml if _ml else None,
        )
        _executive_indices = executive_indices_to_dict(_idx)
        print(f"      HCRI = {_idx.hcri:.1f} ({_idx.hcri_grade})")
        print(f"      WSI  = {_idx.wsi:.1f} ({_idx.wsi_grade})")
        print(f"      RHI  = {_idx.rhi:.1f} ({_idx.rhi_grade})")
        print(f"      TFRI = {_idx.tfri:.1f} ({_idx.tfri_grade})")
        print(f"      LSI  = {_idx.lsi:.1f} ({_idx.lsi_grade})")
        print(f"      ORI  = {_idx.ori:.1f} ({_idx.ori_grade})")
    except Exception as exc:
        print(f"      Executive indices failed (non-fatal): {exc}")

    # ── Build result_summary for DB ───────────────────────────────────────────
    result_summary: dict[str, Any] = {
        "readiness_level":          report.readiness_level.value,
        "row_count":                ir.row_count,
        "column_count":             ir.column_count,
        "dataset_type":             dataset_type,
        "attrition_modeling_allowed": attrition_allowed,
        "governance_scan_passed":   report.governance_scan_passed,
        "pii_columns_detected":     report.pii_columns_detected,
        "leakage_columns_detected": report.leakage_columns_detected,
        "employee_scoring_available": True,
        "total_employee_records":   scored.total_employee_records,
        "matched_construct_count":  scored.matched_construct_count,
        "average_risk_score":       scored.average_risk_score,
        "average_stability_score":  scored.average_stability_score,
        "risk_band_counts":         scored.risk_band_counts,
        "executive_summary":        scored.executive_summary,
        "governance_status":        scored.governance_status,
        "scoring_warnings":         scored.warnings,
        "department_summary":       _dept_dicts,
        "specialty_summary":        [
            dept_summary_to_dict(s) for s in scored.specialty_summary
        ],
        "org_risk_driver_summary":  scored.org_risk_driver_summary,
        "org_narrative":            _narrative_dict,
        "workforce_forecast":       _forecast_dict,
        "ml_validation":            _ml,
        "simulation_result":        _sim,
        "decision_intelligence":    _di,
        "executive_indices":        _executive_indices,
    }

    # ── Persist to DB ─────────────────────────────────────────────────────────
    print("\n[DB] Saving session to local_intelligence.db...")
    session_saved = False
    try:
        target_col = _ml.get("target_column") if _ml else None
        session_id = _db.save_session(
            dataset_name=filename,
            dataset_hash=dataset_hash,
            row_count=ir.row_count,
            column_count=ir.column_count,
            target_column=target_col,
            readiness_level=report.readiness_level.value,
        )
        # Strip employee_risk_table from result_summary (too large for DB)
        _db.save_analysis_result(
            session_id=session_id,
            employee_count=scored.total_employee_records,
            avg_risk_score=scored.average_risk_score,
            avg_stability_score=scored.average_stability_score,
            risk_band_counts=scored.risk_band_counts,
            result_summary=result_summary,
        )
        if _ml.get("available"):
            _db.save_ml_validation(session_id, _ml)
        gov = {
            "pii_columns_removed":        report.pii_columns_detected,
            "leakage_columns_removed":    report.leakage_columns_detected,
            "identifier_columns_removed": (_ml.get("governance") or {}).get("identifier_columns_removed", []),
            "ml_governance_warnings":     (_ml.get("governance") or {}).get("ml_governance_warnings", []),
        }
        proxy_detected = bool(_ml.get("original_has_proxy_warning", False))
        _db.save_governance_audit(session_id, gov, proxy_detected)
        print(f"      session_id = {session_id}")
        session_saved = True
    except Exception as exc:
        print(f"      DB save failed (non-fatal): {exc}")

    print(f"\n{'SESSION_SAVED':40s} = {session_saved}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'EMPLOYEE_SCORING_AVAILABLE':40s} = True")
    print(f"{'TOTAL_EMPLOYEES':40s} = {scored.total_employee_records}")
    print(f"{'SIMULATION_AVAILABLE':40s} = {_sim.get('available', False)}")
    print(f"{'SCENARIOS_COUNT':40s} = {len(_sim.get('scenarios', []))}")
    print(f"{'RECOMMENDED_STRATEGY':40s} = {_sim.get('recommended_strategy') is not None}")
    print(f"{'SESSION_SAVED':40s} = {session_saved}")
    print()

    if _sim.get("available") and session_saved:
        print("OK: Analysis saved. Open the Strategy Simulator and click")
        print("    'Load from latest analysis' to activate the simulation.")
    elif not session_saved:
        print("WARN: Session was not saved to DB. Check backend logs.")
    else:
        print("WARN: Simulation not available. Check backend logs.")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
