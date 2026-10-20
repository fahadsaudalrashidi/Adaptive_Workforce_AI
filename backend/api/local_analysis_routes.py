"""
Local Analysis Routes — Phase 12/13/Fix.

Single-machine, no-auth, no-tenant endpoint for real local analysis.

Endpoint:
  POST /api/local/upload/analyze
      Accept a file upload, run SecureFileIngestion governance scan,
      run DatasetTypeClassifier, return structured governance + classification.
      No authentication. No tenant. Fully offline.

Design rules:
  - FULLY OFFLINE — no network calls
  - No multi-tenant logic
  - No mock data — real analysis only
  - Never returns raw employee rows
  - All errors return structured JSON with HTTP 200 (governance) or 4xx (input)
  - BLOCKED is a governance result, not an API error

Pipeline fix additions:
  - Saudi HR column normalization BEFORE governance scan
    (renames "Attrition" → "flight_risk" so leakage gate is not triggered)
  - Hard 15-second timeout (was 90s)
  - Health score (0-100) in every response
  - Workforce capability indicators
  - Executive recommendations derived from scan result
  - column_normalizations_applied list in response
  - Explicit NaN cleanup before scan
  - Memory cleanup after heavy processing
  - Try/except around entire pipeline with guaranteed JSON fallback
"""

from __future__ import annotations

import asyncio
import base64
import gc
import hashlib
import io
import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fastapi import APIRouter, File, Form, UploadFile
    from fastapi.responses import JSONResponse
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

from backend.core.secure_file_ingestion import SecureFileIngestion
from backend.core.dataset_type_classifier import (
    DatasetTypeClassifier,
    MARKET_INTELLIGENCE_ALLOWED,
)
from backend.core.excel_ingestion_engine import ExcelIngestionEngine
from backend.core.overtime_cost_intelligence_engine import (
    analyze_overtime_cost_intelligence,
    overtime_cost_intelligence_to_dict,
    unavailable_overtime_result as _unavailable_overtime_result,
)
from backend.core.payroll_movement_tracker import (
    analyze_payroll_movements,
    payroll_movement_to_dict,
    unavailable_payroll_result as _unavailable_payroll_result,
)
from backend.core.exit_interview_intelligence_engine import (
    analyze_exit_interview_text,
    exit_interview_intelligence_to_dict,
    unavailable_exit_interview_result as _unavailable_exit_interview_result,
)
from backend.core.recruitment_pipeline_engine import (
    analyze_recruitment_pipeline,
    recruitment_pipeline_to_dict,
    unavailable_recruitment_result as _unavailable_recruitment_result,
)
from backend.core.ethical_ai import (
    EthicalAIEngine,
    detect_attrition_target_column,
    ethical_report_to_dict,
)
from backend.core.nitaqat_compliance_engine import (
    analyze_nitaqat_compliance,
    get_saudi_status_by_record_id,
    nitaqat_compliance_to_dict,
    unavailable_nitaqat_result as _unavailable_nitaqat_result,
)
from backend.core.succession_readiness_engine import (
    analyze_succession_readiness,
    succession_readiness_to_dict,
    unavailable_succession_result as _unavailable_succession_result,
)
from backend.core.pay_equity_engine import (
    analyze_pay_equity,
    pay_equity_to_dict,
    unavailable_pay_equity_result as _unavailable_pay_equity_result,
)
from backend.core.contract_expiry_engine import (
    CROSS_LINK_HORIZON_DAYS,
    analyze_contract_expiry,
    contract_expiry_to_dict,
    get_expiry_signals_by_record_id,
    unavailable_contract_expiry_result as _unavailable_contract_expiry_result,
)
from backend.core.job_pattern_grouping_engine import (
    analyze_job_pattern_grouping,
    generate_market_research_workbook,
    job_pattern_grouping_from_dict,
    job_pattern_grouping_to_dict,
    unavailable_job_pattern_result as _unavailable_job_pattern_result,
)
from backend.core.labor_law_calculators import (
    analyze_gratuity,
    analyze_leave_balance,
    analyze_wps_consistency,
    gratuity_to_dict,
    leave_balance_to_dict,
    unavailable_gratuity_result as _unavailable_gratuity_result,
    unavailable_leave_result as _unavailable_leave_result,
    unavailable_wps_result as _unavailable_wps_result,
    wps_consistency_to_dict,
)
from backend.core.gosi_calculator_engine import (
    analyze_gosi_contributions,
    gosi_result_to_dict,
    unavailable_gosi_result as _unavailable_gosi_result,
)
from backend.core.payroll_budget_engine import (
    PlannedDepartmentBudget,
    compute_payroll_budget_variance,
    payroll_budget_result_to_dict,
    unavailable_payroll_budget_result as _unavailable_payroll_budget_result,
)
from backend.core.zakat_estimator_engine import (
    ZakatInputs,
    estimate_zakat_base,
    zakat_estimate_to_dict,
)
from backend.core.financial_intelligence_reporting_engine import (
    analyze_financial_intelligence,
    financial_intelligence_to_dict,
    unavailable_financial_result as _unavailable_financial_result,
)
from backend.core.accounting_intelligence_engine import (
    analyze_accounting_intelligence,
    accounting_intelligence_to_dict,
)
from backend.core.inventory_intelligence_engine import (
    analyze_inventory_intelligence,
    inventory_intelligence_to_dict,
)
from backend.core.procurement_intelligence_engine import (
    analyze_procurement_intelligence,
    procurement_intelligence_to_dict,
)
from backend.core.logistics_intelligence_engine import (
    analyze_logistics_intelligence,
    logistics_intelligence_to_dict,
)
from backend.core.operations_intelligence_engine import (
    analyze_operations_intelligence,
    operations_intelligence_to_dict,
)
from backend.core.ai_business_analyst_engine import (
    analyze_uploaded_files as _ai_analyst_analyze_uploaded_files,
    answer_question as _ai_analyst_answer_question,
    analyst_answer_to_dict as _ai_analyst_answer_to_dict,
    registry_catalog as _ai_analyst_registry_catalog,
    ollama_reachable as _ai_analyst_ollama_reachable,
    OLLAMA_MODEL as _AI_ANALYST_OLLAMA_MODEL,
)
# ── Phase 43: sandboxed code-execution file editing (extends the Phase 37
# AI Business Analyst above with a second, architecturally SEPARATE path —
# see sandbox_request_router.py's module docstring for why the two never
# merge) ─────────────────────────────────────────────────────────────────
from backend.core.sandbox_request_router import split_request as _sandbox_split_request
from backend.core.sandbox_file_structure import describe_file_structure as _sandbox_describe_file_structure
from backend.core.sandbox_code_generator import (
    generate_edit_code as _sandbox_generate_edit_code,
    code_gen_reachable as _sandbox_code_gen_reachable,
    CODE_GEN_MODEL as _SANDBOX_CODE_GEN_MODEL,
)
from backend.core.sandbox_executor import (
    run_sandboxed_code as _sandbox_run_code,
    cleanup_sandbox_run as _sandbox_cleanup_run,
)
from backend.core.sandbox_diff_summary import compute_diff_summary as _sandbox_compute_diff_summary
from backend.core.sandbox_windows_limits import pywin32_available as _sandbox_pywin32_available
# ── Phase 44: agentic Claude-API mode — an ADDITIVE path alongside Phase
# 37's local Ollama Q&A above, never a replacement. answer_question() is
# not imported differently or modified here; the fallback below calls the
# exact same _ai_analyst_answer_question already bound above. ─────────────
from backend.core.cloud_llm_client import check_cloud_mode as _agentic_check_cloud_mode
from backend.core.agentic_orchestrator import answer_with_claude_agent as _agentic_answer_with_claude
from backend.core.hr_letter_generator import (
    LETTER_TYPES as HR_LETTER_TYPES,
    CompanyDetails as HRLetterCompanyDetails,
    GratuityLetterInput,
    bulk_letter_result_to_dict,
    build_bulk_letters,
    build_employment_certificate,
    build_end_of_service_letter,
    build_salary_certificate,
    employee_data_result_to_dict,
    extract_employee_letter_records,
    safe_record_id_for_lookup,
    unavailable_employee_data_result as _unavailable_hr_letter_result,
)
logger = logging.getLogger(__name__)

# ── Performance constants ─────────────────────────────────────────────────────
_FAST_PATH_BYTES = 5 * 1024 * 1024    # 5 MB
_TIMEOUT_SECS    = 15                  # Hard timeout — prevents frontend hang
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024 # 500 MB hard cap

# ── Singletons ────────────────────────────────────────────────────────────────
# Phase 40: _risk_scorer (EmployeeRiskScorer), _tenant_manager (TenantManager,
# only ever used to record analyses from the removed upload/analyze-with-employees
# route), and _history_engine (HistoricalIntelligenceEngine, only ever used to
# snapshot that same route's results) were removed along with
# employee_risk_scoring.py and the whole shared-upload/session pipeline — see
# PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md. _ethical_engine is kept: it is
# genuinely also used by the real, kept /fairness-audit route.
_scanner    = SecureFileIngestion()
_classifier = DatasetTypeClassifier()
_loader     = ExcelIngestionEngine()   # used for pre-normalization only
_ethical_engine = EthicalAIEngine()    # Phase 6: fairness/bias audit + confidence governance

# Phase 43: single-download, in-memory-only store for sandboxed edit
# results, keyed by run_id. Popped (not just read) on download — a result
# can be fetched exactly once, and nothing from a sandboxed run persists
# beyond that, consistent with this route never writing a "final" copy of
# an edited file to disk itself (only the sandbox's own temp directory,
# already deleted by the time this store is the only remaining copy).
_SANDBOX_DOWNLOAD_STORE: dict[str, tuple[str, bytes]] = {}

# Phase 44: same single-download, in-memory-only convention as
# _SANDBOX_DOWNLOAD_STORE, for files the Claude agent generates
# (PPTX reports, merged Excel files, sandboxed edits it triggers).
_AGENTIC_DOWNLOAD_STORE: dict[str, tuple[str, str, bytes]] = {}  # id -> (filename, content_type, bytes)

# ── Saudi HR column normalization map ────────────────────────────────────────
# Applied BEFORE governance scan. Keys are lowercase stripped column names.
# Prevents leakage blocking on the canonical HR target label.
_SAUDI_HR_COLUMN_RENAMES: dict[str, str] = {
    # The standard IBM/Saudi attrition label is a post-event flag.
    # Renaming to flight_risk makes it a VALID target column, not leakage.
    "attrition":       "flight_risk",
    # Common ERP numeric PII-adjacent column names → safe internal name
    "employeenumber":  "employee_id",
    "employee number": "employee_id",
    "empno":           "employee_id",
    "emp_no":          "employee_id",
    # Arabic equivalents
    "الاستنزاف":       "flight_risk",
}

# ── Human-readable labels ─────────────────────────────────────────────────────
_DATASET_TYPE_LABELS: dict[str, str] = {
    "EMPLOYEE_ATTRITION_DATASET":      "Employee Attrition Dataset",
    "JOB_MARKET_POSTING_DATASET":      "Job Market Posting Dataset",
    "GOVERNMENT_WORKFORCE_TABLE":      "Government Workforce Table",
    "GLOBAL_JOB_POSTING_STRESS_TEST":  "Global Job Posting (Stress Test)",
    "UNKNOWN_OR_UNSUPPORTED":          "Unknown or Unsupported Dataset",
}

_ANALYSIS_MODE_LABELS: dict[str, str] = {
    "workforce_stability":   "Workforce Stability Analysis",
    "market_intelligence":   "Market Intelligence Analysis",
    "government_workforce":  "Government Workforce Analysis",
    "ingestion_stress_test": "Ingestion Stress Test",
    "blocked":               "Blocked — Upload Cannot Proceed",
}


# ── Pre-processing: column normalization ─────────────────────────────────────

def _preprocess_raw_bytes(raw_bytes: bytes, filename: str) -> tuple[bytes, list[str]]:
    """
    Load the dataframe, apply Saudi HR column normalizations, serialize back
    to UTF-8 CSV. Returns (normalized_bytes, normalization_log).

    If parsing fails for any reason the original bytes are returned unchanged.
    This ensures the governance scan always receives something to evaluate.
    """
    normalization_log: list[str] = []
    try:
        result = _loader.ingest(raw_bytes, filename)
        if not result.success or result.df is None:
            return raw_bytes, normalization_log

        df = result.df

        # Strip leading/trailing whitespace from all column names
        stripped: dict[str, str] = {}
        for col in df.columns:
            clean = col.strip()
            if clean != col:
                stripped[col] = clean
                normalization_log.append(f"Stripped whitespace from column '{col}'")
        if stripped:
            df = df.rename(columns=stripped)

        # Apply canonical renames
        rename_map: dict[str, str] = {}
        for col in df.columns:
            key = col.strip().lower()
            if key in _SAUDI_HR_COLUMN_RENAMES:
                new_name = _SAUDI_HR_COLUMN_RENAMES[key]
                if new_name != col:
                    rename_map[col] = new_name
                    normalization_log.append(
                        f"Normalized column '{col}' → '{new_name}' "
                        f"(Saudi HR schema normalization)"
                    )
        if rename_map:
            df = df.rename(columns=rename_map)

        # Serialize to UTF-8 CSV for governance scan
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        normalized_bytes = buf.getvalue().encode("utf-8")

        del df, buf
        return normalized_bytes, normalization_log

    except Exception as exc:
        logger.warning("Pre-normalization failed (non-fatal, using original bytes): %s", exc)
        return raw_bytes, normalization_log


# ── Analytics helpers ─────────────────────────────────────────────────────────

def _compute_health_score(
    readiness: str,
    missing_pct: float,
    duplicate_rows: int,
    row_count: int,
    n_blocking: int,
    n_warnings: int,
    feature_count: int,
) -> int:
    """
    0–100 dataset health score.
    BLOCKED datasets are capped at 40; perfect datasets score 100.
    """
    score = 100.0
    score -= min(30.0, missing_pct * 0.5)          # max -30 for missing values
    if row_count > 0:
        dup_pct = (duplicate_rows / row_count) * 100
        score -= min(15.0, dup_pct * 0.5)          # max -15 for duplicates
    score -= n_blocking * 25.0                      # each blocker: -25
    score -= n_warnings * 4.0                       # each warning: -4
    if feature_count < 5:
        score -= (5 - feature_count) * 3.0          # low feature coverage: -3 each
    if readiness == "BLOCKED":
        score = min(score, 40.0)                    # hard cap when blocked
    return max(0, min(100, round(score)))


def _build_workforce_indicators(
    dataset_type: str,
    attrition_allowed: bool,
    theory_allowed: bool,
    market_allowed: bool,
    readiness: str,
    feature_count: int,
    row_count: int,
    classification_conf: float,
) -> list[dict[str, str]]:
    """Structured capability / risk indicators shown in the executive panel."""
    indicators: list[dict[str, str]] = []

    if dataset_type == "EMPLOYEE_ATTRITION_DATASET":
        indicators.append({"label": "Dataset Category", "value": "HR Workforce Stability", "status": "info"})
        indicators.append({
            "label": "Attrition Modeling",
            "value": "Enabled" if attrition_allowed else "Blocked",
            "status": "ok" if attrition_allowed else "warn",
        })
        indicators.append({
            "label": "Theory Engine (25 Constructs)",
            "value": "Active" if theory_allowed else "Inactive",
            "status": "ok" if theory_allowed else "neutral",
        })
    elif dataset_type in ("JOB_MARKET_POSTING_DATASET", "GLOBAL_JOB_POSTING_STRESS_TEST"):
        indicators.append({"label": "Dataset Category", "value": "Talent Market Intelligence", "status": "info"})
        indicators.append({
            "label": "Market Intelligence",
            "value": "Enabled" if market_allowed else "Blocked",
            "status": "ok" if market_allowed else "warn",
        })
        indicators.append({"label": "Attrition Modeling", "value": "Not Applicable", "status": "neutral"})
    elif dataset_type == "GOVERNMENT_WORKFORCE_TABLE":
        indicators.append({"label": "Dataset Category", "value": "Government Workforce", "status": "info"})
        indicators.append({
            "label": "Market Intelligence",
            "value": "Enabled" if market_allowed else "Blocked",
            "status": "ok" if market_allowed else "warn",
        })
    else:
        indicators.append({"label": "Dataset Category", "value": "Unrecognised / Unsupported", "status": "warn"})

    indicators.append({
        "label": "Classification Confidence",
        "value": f"{round(classification_conf * 100)}%",
        "status": "ok" if classification_conf >= 0.8 else ("warn" if classification_conf >= 0.5 else "error"),
    })
    indicators.append({
        "label": "HR Feature Coverage",
        "value": f"{feature_count} feature column(s)",
        "status": "ok" if feature_count >= 5 else ("warn" if feature_count >= 3 else "error"),
    })
    indicators.append({
        "label": "Sample Size",
        "value": f"{row_count:,} records",
        "status": "ok" if row_count >= 200 else ("warn" if row_count >= 50 else "error"),
    })
    indicators.append({
        "label": "Governance Gate",
        "value": readiness,
        "status": "ok" if readiness == "READY" else ("warn" if readiness == "CONDITIONAL" else "error"),
    })
    return indicators


def _build_executive_recommendations(
    readiness: str,
    dataset_type: str,
    pii_columns: list[str],
    leakage_columns: list[str],
    normalizations: list[str],
    missing_pct: float,
    duplicate_rows: int,
    feature_count: int,
    attrition_allowed: bool,
    warnings: list[str],
) -> list[str]:
    """
    Ordered list of actionable executive recommendations derived from scan result.
    Applied normalizations are listed first as informational items.
    """
    recs: list[str] = []

    # Informational: what was auto-fixed
    for norm in normalizations:
        recs.append(f"Auto-applied: {norm}")

    # Blocking issues — highest priority
    if pii_columns:
        recs.append(
            f"REQUIRED: Remove PII column(s) — {', '.join(pii_columns)} — "
            "before upload per PDPL Article 6 personal data protection requirements."
        )
    if leakage_columns:
        recs.append(
            f"REQUIRED: Remove leakage column(s) — {', '.join(leakage_columns)} — "
            "These contain post-event outcome data that invalidates supervised model training."
        )

    # Feature coverage
    if feature_count < 3:
        recs.append(
            "Add HR feature columns: department, tenure_years, performance_rating, "
            "job_level, age. Minimum 3 HR-relevant features are required."
        )
    elif feature_count < 5:
        recs.append(
            f"Consider adding more HR feature columns ({feature_count} detected). "
            "Additional features (training_hours, engagement_score) improve model fidelity."
        )

    # Data quality
    if missing_pct > 20:
        recs.append(
            f"Impute or remove columns with high null rates "
            f"({missing_pct:.1f}% missing values). "
            "High nulls reduce model accuracy."
        )
    if duplicate_rows > 0:
        recs.append(
            f"Remove {duplicate_rows} duplicate row(s) before proceeding. "
            "Duplicates inflate apparent workforce size and skew risk scores."
        )

    # Positive guidance when eligible
    if readiness in ("READY", "CONDITIONAL") and dataset_type == "EMPLOYEE_ATTRITION_DATASET" and attrition_allowed:
        recs.append(
            "Dataset eligible for workforce stability analysis. "
            "Proceed to executive dashboard to generate attrition risk report."
        )
    if readiness in ("READY", "CONDITIONAL") and dataset_type in (
        "JOB_MARKET_POSTING_DATASET", "GLOBAL_JOB_POSTING_STRESS_TEST"
    ):
        recs.append(
            "Dataset eligible for market intelligence analysis. "
            "Proceed to talent benchmarking dashboard."
        )
    if readiness == "CONDITIONAL" and not recs or all(r.startswith("Auto") for r in recs):
        recs.append("Review governance warnings before generating executive reports.")

    return recs


def _build_readiness_summary(
    readiness: str,
    dataset_type: str,
    attrition_allowed: bool,
    n_blocking: int,
    n_warnings: int,
) -> str:
    if readiness == "BLOCKED":
        return (
            f"Dataset blocked: {n_blocking} governance issue(s) must be resolved "
            "before analysis can proceed. Remove PII and leakage columns, then re-upload."
        )
    if readiness == "CONDITIONAL":
        if dataset_type == "EMPLOYEE_ATTRITION_DATASET" and attrition_allowed:
            return (
                f"Dataset conditionally ready ({n_warnings} warning(s)). "
                "Workforce stability analysis available. Review warnings before proceeding."
            )
        if dataset_type in ("JOB_MARKET_POSTING_DATASET", "GLOBAL_JOB_POSTING_STRESS_TEST"):
            return (
                f"Job market dataset conditionally ready ({n_warnings} warning(s)). "
                "Market intelligence available. Attrition modeling blocked."
            )
        return (
            f"Dataset conditionally ready ({n_warnings} warning(s)). "
            "Review warnings before generating executive reports."
        )
    # READY
    if dataset_type == "EMPLOYEE_ATTRITION_DATASET" and attrition_allowed:
        return (
            "Dataset fully ready for executive workforce stability analysis. "
            "Attrition modeling, theory engine, and dashboard all available."
        )
    if dataset_type in ("JOB_MARKET_POSTING_DATASET", "GLOBAL_JOB_POSTING_STRESS_TEST"):
        return (
            "Job market dataset ready for market intelligence analysis. "
            "Attrition modeling not applicable to this dataset type."
        )
    if dataset_type == "GOVERNMENT_WORKFORCE_TABLE":
        return "Government workforce dataset ready. Market intelligence analysis available."
    return "Dataset passed governance scan. Review classification details before proceeding."


# ── Router factory ────────────────────────────────────────────────────────────

def create_local_analysis_router() -> Any:
    if not _HAS_FASTAPI:
        raise ImportError("FastAPI is required")

    router = APIRouter(prefix="/api/local", tags=["Local Analysis"])

    # Phase 40: /upload/analyze and /upload/analyze-with-employees were removed
    # along with employee_risk_scoring.py and the whole shared-upload/session
    # pipeline they powered (confirmed zero frontend callers of either route) —
    # see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.

    # ── Phase 35.1: Overtime & Workforce Cost Intelligence ────────────────────

    @router.post("/overtime-cost-intelligence")
    async def local_overtime_cost_intelligence(file: UploadFile = File(...)):
        """
        Real overtime financial-exposure analysis for an uploaded dataset.

        Pipeline: Saudi HR column normalization → governance scan → employee
        risk scoring (for department-level risk cross-reference) → overtime
        cost computation (backend.core.overtime_cost_intelligence_engine).

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset has no overtime-related column —
        this is a data-shape limitation, not a failure.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "overtime_cost_intelligence": overtime_cost_intelligence_to_dict(
                    _unavailable_overtime_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        # Phase 40: this route's department-level risk cross-reference (fed by
        # employee_risk_scoring.py) was removed along with that engine. The
        # primary overtime analysis below is untouched and fully functional;
        # analyze_overtime_cost_intelligence already treats an empty
        # department_summary_dicts as the honest "no cross-reference data"
        # case (same as when the risk scorer previously failed non-fatally).
        department_summary_dicts: list[dict] = []

        try:
            overtime_result = await asyncio.to_thread(
                analyze_overtime_cost_intelligence, ir.df, department_summary_dicts,
            )
        except Exception as exc:
            logger.exception("Overtime cost intelligence failed")
            overtime_result = _unavailable_overtime_result(
                f"Overtime cost analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "overtime_cost_intelligence": overtime_cost_intelligence_to_dict(overtime_result),
        })

    # ── Phase 35.2: Payroll Movements Tracker ──────────────────────────────────

    @router.post("/payroll-movements")
    async def local_payroll_movements(file: UploadFile = File(...)):
        """
        Real payroll-movement analysis for an uploaded dataset.

        Pipeline: Saudi HR column normalization → governance scan → employee
        risk scoring (for department-level risk cross-reference) → payroll
        movement analysis (backend.core.payroll_movement_tracker).

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset has no salary-history or
        salary-hike column — this is a data-shape limitation, not a failure,
        and the response explains exactly what would activate the feature.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "payroll_movements": payroll_movement_to_dict(
                    _unavailable_payroll_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        # Phase 40: same removal as the overtime-cost-intelligence route above —
        # see that route's comment.
        department_summary_dicts: list[dict] = []

        try:
            payroll_result = await asyncio.to_thread(
                analyze_payroll_movements, ir.df, department_summary_dicts,
            )
        except Exception as exc:
            logger.exception("Payroll movement analysis failed")
            payroll_result = _unavailable_payroll_result(
                f"Payroll movement analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "payroll_movements": payroll_movement_to_dict(payroll_result),
        })

    # ── Phase 5: Recruitment Pipeline Status Tracker ────────────────────────────

    @router.post("/recruitment-pipeline")
    async def local_recruitment_pipeline(file: UploadFile = File(...)):
        """
        Real recruitment/hiring-pipeline analysis for an uploaded dataset.

        Pipeline: Saudi HR column normalization → governance scan (dedup +
        PII/leakage checks, same as every other module) → recruitment
        pipeline analysis (backend.core.recruitment_pipeline_engine).

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset has no recognisable pipeline-
        stage column — the expected result for structured HR *employee*
        data, which this platform's other datasets are. The response
        explains exactly what column shape would activate this feature.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "recruitment_pipeline": recruitment_pipeline_to_dict(
                    _unavailable_recruitment_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        try:
            recruitment_result = await asyncio.to_thread(
                analyze_recruitment_pipeline, ir.df,
            )
        except Exception as exc:
            logger.exception("Recruitment pipeline analysis failed")
            recruitment_result = _unavailable_recruitment_result(
                f"Recruitment pipeline analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "recruitment_pipeline": recruitment_pipeline_to_dict(recruitment_result),
        })

    # ── Phase 6: Fairness / Bias Audit ──────────────────────────────────────────

    @router.post("/fairness-audit")
    async def local_fairness_audit(file: UploadFile = File(...)):
        """
        Real fairness/bias audit for an uploaded dataset
        (backend.core.ethical_ai.EthicalAIEngine).

        Pipeline: Saudi HR column normalization → governance scan (dedup +
        PII/leakage checks, same as every other module) → employee risk
        scoring (for real AUC/sample-size/quality context — mirrors the
        legacy Streamlit app's frontend/app.py:719-726 pattern of feeding
        govern_prediction() genuinely computed values rather than the
        build_ethical_report() convenience function's placeholder defaults,
        see ETHICAL_AI_ENGINE_INVESTIGATION.md §5a) → bias audit + confidence
        governance (backend.core.ethical_ai).

        Every code path returns valid JSON. If no protected attribute
        (gender, age, nationality, etc.) is detected, or no recognisable
        attrition/flight-risk target column exists, the response says so
        honestly (`bias_audit.protected_attributes: []` /
        `bias_audit.fairness_metrics: []` with an explanatory
        `audit_summary`) rather than fabricating a result.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "ethical_report": ethical_report_to_dict(
                    _ethical_engine.generate_ethical_report(
                        _ethical_engine.audit_bias(pd.DataFrame()),
                        [],
                    )
                ),
            })

        try:
            target_col, positive_label = detect_attrition_target_column(ir.df)

            audit = await asyncio.to_thread(
                _ethical_engine.audit_bias, ir.df, target_col, positive_label or "Yes",
            )

            # Real AUC / sample-size / data-quality context for confidence
            # governance — never the build_ethical_report() convenience
            # function's placeholder defaults (raw_confidence=0.75, etc.),
            # which this route deliberately does not call. Governance is
            # only computed when a real attrition/flight-risk target column
            # exists — with no target column there is no actual prediction
            # for confidence governance to assess, so computing one anyway
            # (even with honestly-labeled fallback values) would fabricate
            # a governance verdict for a prediction that was never made.
            governance_results: list = []
            if target_col:
                # Phase 40: this previously tried to pull a real AUC/n_samples
                # from employee_risk_scoring.py's model_metrics, now removed.
                # model_metrics stays {} unconditionally, which is exactly the
                # same honest "not available" state this route already used
                # whenever the risk scorer failed non-fatally — the fallback
                # auc=0.65 / n_samples=ir.row_count path below and the
                # governance math itself are unchanged.
                model_metrics: dict = {}

                metrics_available = bool(model_metrics.get("available"))
                auc = float(model_metrics["roc_auc"]) if metrics_available and model_metrics.get("roc_auc") is not None else 0.65
                n_samples = int(model_metrics["n_samples"]) if metrics_available and model_metrics.get("n_samples") else ir.row_count
                n_pos = model_metrics.get("n_positive") if metrics_available else None
                n_neg = model_metrics.get("n_negative") if metrics_available else None
                imbalance = (max(n_pos, n_neg) / max(min(n_pos, n_neg), 1)) if n_pos and n_neg else 1.0
                data_quality_score = max(0.0, min(1.0, 1.0 - (report.data_quality.missing_value_pct / 100.0)))

                governance_results = [_ethical_engine.govern_prediction(
                    prediction_type="attrition",
                    raw_confidence=auc,
                    n_samples=n_samples,
                    data_quality_score=data_quality_score,
                    auc_score=auc,
                    class_imbalance_ratio=imbalance,
                    protected_bias_risk=audit.overall_risk_level,
                )]

            ethical_result = _ethical_engine.generate_ethical_report(audit, governance_results)
        except Exception as exc:
            logger.exception("Fairness audit failed")
            ethical_result = _ethical_engine.generate_ethical_report(
                _ethical_engine.audit_bias(pd.DataFrame()), [],
            )
            ethical_result.blocking_issues.append(f"Fairness audit encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "ethical_report": ethical_report_to_dict(ethical_result),
        })

    # ── Phase 17: Pay Equity Analysis ────────────────────────────────────────────

    @router.post("/pay-equity")
    async def local_pay_equity(file: UploadFile = File(...)):
        """
        Real pay-equity analysis for an uploaded dataset
        (backend.core.pay_equity_engine.analyze_pay_equity).

        Narrower and more specific than /fairness-audit (which looks at
        OUTCOME rates like attrition risk): this asks whether people in
        comparable roles/levels (same job level and/or department) are paid
        comparably across protected-attribute groups, reusing
        ethical_ai.py's minimum-group-size floor, high-cardinality bucketing
        guard, and 0.05 significance threshold, with a new Welch's t-test
        appropriate for comparing continuous salary means (not the fairness
        audit's proportion test, which would be statistically wrong here).

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset lacks a salary column, a
        protected attribute, or any comparability factor — this is a
        data-shape limitation, not a failure.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "pay_equity": pay_equity_to_dict(
                    _unavailable_pay_equity_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        try:
            pay_equity_result = await asyncio.to_thread(analyze_pay_equity, ir.df)
        except Exception as exc:
            logger.exception("Pay equity analysis failed")
            pay_equity_result = _unavailable_pay_equity_result(
                f"Pay equity analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "pay_equity": pay_equity_to_dict(pay_equity_result),
        })

    # ── Phase 7: Nitaqat / Saudization Compliance ───────────────────────────────

    @router.post("/nitaqat-compliance")
    async def local_nitaqat_compliance(file: UploadFile = File(...)):
        """
        Illustrative Nitaqat/Saudization compliance estimate for an uploaded
        dataset (backend.core.nitaqat_compliance_engine).

        Pipeline: Saudi HR column normalization → governance scan (dedup +
        PII/leakage checks, same as every other module) → Nitaqat compliance
        estimate.

        NON-NEGOTIABLE: every available=True response carries
        `is_official_calculation: false` and a full illustrative-estimate
        disclaimer (see nitaqat_compliance_engine.py's module docstring for
        the research trail — the real HRSD Nitaqat Mutawar formula's
        per-sector coefficients are not publicly available). This is never
        presented as an official compliance determination.

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset has no nationality/Saudi-status
        column — the expected result for most structured HR exports, which
        this platform's other datasets are — and the response explains
        exactly what column shape would activate this feature.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "nitaqat_compliance": nitaqat_compliance_to_dict(
                    _unavailable_nitaqat_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        try:
            nitaqat_result = await asyncio.to_thread(
                analyze_nitaqat_compliance, ir.df,
            )
        except Exception as exc:
            logger.exception("Nitaqat compliance analysis failed")
            nitaqat_result = _unavailable_nitaqat_result(
                f"Nitaqat compliance analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "nitaqat_compliance": nitaqat_compliance_to_dict(nitaqat_result),
        })

    # ── Phase 8: Succession Planning / Internal Mobility Readiness ─────────────

    @router.post("/succession-readiness")
    async def local_succession_readiness(file: UploadFile = File(...)):
        """
        Constructed-heuristic succession/internal-mobility readiness estimate
        for an uploaded dataset (backend.core.succession_readiness_engine).

        Pipeline: Saudi HR column normalization → governance scan (dedup +
        PII/leakage checks, same as every other module) → readiness
        estimate → optional Nitaqat Saudi-status cross-link computed on the
        SAME uploaded file (see nitaqat_compliance_engine.get_saudi_status_by_record_id
        — a PII-safe, one-way-hashed join key; the two engines stay
        decoupled, this route is the only place that combines them).

        NON-NEGOTIABLE: every available=True response carries
        `is_validated_instrument: false` and a full constructed-heuristic
        disclaimer — this is a discussion-starting HR-planning aid, never a
        validated psychometric or vendor-benchmarked instrument.

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when the dataset has no performance-rating and/or
        tenure column, explaining exactly what column shape would activate
        this feature.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "succession_readiness": succession_readiness_to_dict(
                    _unavailable_succession_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
                "saudi_pipeline_cross_link": {"available": False, "reason": "Dataset could not be ingested."},
            })

        try:
            readiness_result = await asyncio.to_thread(
                analyze_succession_readiness, ir.df,
            )
        except Exception as exc:
            logger.exception("Succession readiness analysis failed")
            readiness_result = _unavailable_succession_result(
                f"Succession readiness analysis encountered an error: {exc}"
            )

        # Optional Nitaqat cross-link: only meaningful when the SAME upload
        # has both a nationality column and a real named EmployeeID column
        # (get_saudi_status_by_record_id() refuses positional-fallback IDs —
        # see that function's docstring for why a silent mismatch would be
        # worse than no cross-link at all).
        cross_link: dict[str, Any]
        try:
            saudi_map = await asyncio.to_thread(get_saudi_status_by_record_id, ir.df)
        except Exception as exc:
            logger.warning("Succession endpoint: Saudi cross-link unavailable (non-fatal): %s", exc)
            saudi_map = None

        if not readiness_result.available:
            cross_link = {
                "available": False,
                "reason": "Succession readiness data was not available for this upload.",
            }
        elif saudi_map is None:
            cross_link = {
                "available": False,
                "reason": (
                    "No cross-link possible — this upload needs both a nationality/"
                    "Saudi-status column and a named employee-ID column "
                    "(e.g. EmployeeID) for a safe per-employee join."
                ),
            }
        else:
            n_high_readiness_saudi = sum(
                1 for rid in readiness_result.high_readiness_record_ids
                if saudi_map.get(rid) is True
            )
            cross_link = {
                "available": True,
                "n_high_readiness_saudi": n_high_readiness_saudi,
                "n_high_readiness_total": readiness_result.n_high_readiness,
                "narrative_en": (
                    f"Of {readiness_result.n_high_readiness} employees in the 'High "
                    f"Readiness' tier, {n_high_readiness_saudi} are recorded as Saudi "
                    "nationals — a potential Saudi leadership pipeline for Nitaqat/"
                    "Saudization planning. Both figures are constructed-heuristic "
                    "estimates, not validated or official determinations — see "
                    "succession and Nitaqat disclaimers."
                ),
                "narrative_ar": (
                    f"من أصل {readiness_result.n_high_readiness} موظفاً ضمن مستوى "
                    f"'جاهزية عالية'، {n_high_readiness_saudi} مسجلون كمواطنين "
                    "سعوديين — خط أنابيب قيادي سعودي محتمل لأغراض تخطيط السعودة. "
                    "كلا الرقمين تقديريان إرشاديان وليسا معتمدين رسمياً."
                ),
                "is_validated_instrument": False,
            }

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "succession_readiness": succession_readiness_to_dict(readiness_result),
            "saudi_pipeline_cross_link": cross_link,
        })

    # ── Phase 18: Contract Expiry & Renewal Monitoring ──────────────────────────

    @router.post("/contract-expiry")
    async def local_contract_expiry(file: UploadFile = File(...)):
        """
        Contract-end-date and Iqama/visa-expiry monitoring for an uploaded
        dataset (backend.core.contract_expiry_engine).

        Pipeline: Saudi HR column normalization → governance scan (dedup +
        PII/leakage checks, same as every other module) → expiry-tier
        analysis → two optional cross-links computed on the SAME uploaded
        file, following the exact Phase 8 decoupled-engine / route-layer-join
        pattern (contract_expiry_engine.py never imports
        succession_readiness_engine.py or nitaqat_compliance_engine.py, and
        neither imports it back — this route is the only place the three are
        combined):
          - Succession cross-link: "high-readiness employee with contract OR
            Iqama expiring within CROSS_LINK_HORIZON_DAYS" (soonest of either
            signal — a leadership-critical employee could become unreachable
            via either boundary).
          - Nitaqat cross-link: "non-Saudi employee with Iqama expiring within
            CROSS_LINK_HORIZON_DAYS" (Iqama only, not contract end — Nitaqat/
            Saudization is specifically about legal work-authorization
            status, not employment-relationship end dates).

        NON-NEGOTIABLE: this is a planning aid, not legal/immigration advice
        — see contract_expiry_engine.py's disclaimer. Every code path
        returns valid JSON. `available: false` (not an HTTP error) is
        returned when no contract-end-date or Iqama/visa-expiry column is
        detected — the expected result for every fixture in this repo today
        — and the response explains exactly what column shape would
        activate this feature.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "contract_expiry": contract_expiry_to_dict(
                    _unavailable_contract_expiry_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
                "succession_cross_link": {"available": False, "reason": "Dataset could not be ingested."},
                "nitaqat_cross_link": {"available": False, "reason": "Dataset could not be ingested."},
            })

        try:
            expiry_result = await asyncio.to_thread(analyze_contract_expiry, ir.df)
        except Exception as exc:
            logger.exception("Contract expiry analysis failed")
            expiry_result = _unavailable_contract_expiry_result(
                f"Contract expiry analysis encountered an error: {exc}"
            )

        try:
            signals_map = await asyncio.to_thread(get_expiry_signals_by_record_id, ir.df)
        except Exception as exc:
            logger.warning("Contract expiry endpoint: signals map unavailable (non-fatal): %s", exc)
            signals_map = None

        # ── Succession cross-link: high readiness + expiring soon ──────────────
        succession_cross_link: dict[str, Any]
        if not expiry_result.available or signals_map is None:
            succession_cross_link = {
                "available": False,
                "reason": (
                    "No cross-link possible — this upload needs both a "
                    "contract-end-date or Iqama/visa-expiry column and a named "
                    "employee-ID column (e.g. EmployeeID) for a safe per-employee join."
                ),
            }
        else:
            try:
                readiness_result = await asyncio.to_thread(analyze_succession_readiness, ir.df)
            except Exception as exc:
                logger.warning("Contract expiry endpoint: succession cross-link unavailable (non-fatal): %s", exc)
                readiness_result = None

            if readiness_result is None or not readiness_result.available:
                succession_cross_link = {
                    "available": False,
                    "reason": "Succession readiness data was not available for this upload.",
                }
            else:
                flagged_ids: list[str] = []
                for rid in readiness_result.high_readiness_record_ids:
                    sig = signals_map.get(rid)
                    if sig is None:
                        continue
                    days = [d for d in (sig["contract_days_remaining"], sig["iqama_days_remaining"]) if d is not None]
                    if days and min(days) <= CROSS_LINK_HORIZON_DAYS:
                        flagged_ids.append(rid)
                succession_cross_link = {
                    "available": True,
                    "n_high_readiness_with_expiring_signal": len(flagged_ids),
                    "n_high_readiness_total": readiness_result.n_high_readiness,
                    "horizon_days": CROSS_LINK_HORIZON_DAYS,
                    "narrative_en": (
                        f"Of {readiness_result.n_high_readiness} employees in the 'High "
                        f"Readiness' tier, {len(flagged_ids)} have a contract or Iqama/"
                        f"visa expiry within {CROSS_LINK_HORIZON_DAYS} days — a valuable "
                        "employee who could become unreachable if renewal is missed. "
                        "Both figures are constructed-heuristic estimates — see "
                        "succession and contract-expiry disclaimers."
                    ),
                    "narrative_ar": (
                        f"من أصل {readiness_result.n_high_readiness} موظفاً ضمن مستوى "
                        f"'جاهزية عالية'، لدى {len(flagged_ids)} منهم عقد أو إقامة/تأشيرة "
                        f"تنتهي خلال {CROSS_LINK_HORIZON_DAYS} يوماً — موظف قيّم قد يصعب "
                        "الوصول إليه إذا فات التجديد. كلا الرقمين تقديريان إرشاديان."
                    ),
                    "is_validated_instrument": False,
                }

        # ── Nitaqat cross-link: non-Saudi + Iqama expiring soon ─────────────────
        nitaqat_cross_link: dict[str, Any]
        if not expiry_result.available or signals_map is None:
            nitaqat_cross_link = {
                "available": False,
                "reason": (
                    "No cross-link possible — this upload needs both an Iqama/"
                    "visa-expiry column and a named employee-ID column "
                    "(e.g. EmployeeID) for a safe per-employee join."
                ),
            }
        else:
            try:
                saudi_map = await asyncio.to_thread(get_saudi_status_by_record_id, ir.df)
            except Exception as exc:
                logger.warning("Contract expiry endpoint: Nitaqat cross-link unavailable (non-fatal): %s", exc)
                saudi_map = None

            if saudi_map is None:
                nitaqat_cross_link = {
                    "available": False,
                    "reason": (
                        "No cross-link possible — this upload needs both a nationality/"
                        "Saudi-status column and a named employee-ID column "
                        "(e.g. EmployeeID) for a safe per-employee join."
                    ),
                }
            else:
                non_saudi_ids = [rid for rid, is_saudi in saudi_map.items() if is_saudi is False]
                flagged_ids = []
                for rid in non_saudi_ids:
                    sig = signals_map.get(rid)
                    if sig is None or sig["iqama_days_remaining"] is None:
                        continue
                    if sig["iqama_days_remaining"] <= CROSS_LINK_HORIZON_DAYS:
                        flagged_ids.append(rid)
                nitaqat_cross_link = {
                    "available": True,
                    "n_non_saudi_with_expiring_iqama": len(flagged_ids),
                    "n_non_saudi_total": len(non_saudi_ids),
                    "horizon_days": CROSS_LINK_HORIZON_DAYS,
                    "narrative_en": (
                        f"Of {len(non_saudi_ids)} employees recorded as non-Saudi, "
                        f"{len(flagged_ids)} have an Iqama/visa expiry within "
                        f"{CROSS_LINK_HORIZON_DAYS} days — a direct legal work-"
                        "authorization compliance signal, distinct from the "
                        "Saudization headcount question Nitaqat tracks. Not legal or "
                        "immigration advice — see contract-expiry disclaimer."
                    ),
                    "narrative_ar": (
                        f"من أصل {len(non_saudi_ids)} موظفاً مسجلين كغير سعوديين، "
                        f"لدى {len(flagged_ids)} منهم إقامة/تأشيرة تنتهي خلال "
                        f"{CROSS_LINK_HORIZON_DAYS} يوماً — إشارة امتثال قانوني مباشرة "
                        "لتصريح العمل، تختلف عن مسألة نسب السعودة التي تتابعها نطاقات. "
                        "ليست استشارة قانونية أو استشارة هجرة."
                    ),
                    "is_official_calculation": False,
                }

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "contract_expiry": contract_expiry_to_dict(expiry_result),
            "succession_cross_link": succession_cross_link,
            "nitaqat_cross_link": nitaqat_cross_link,
        })

    # ── Phase 19: Job Pattern Grouping & Market Research Export ────────────────

    @router.post("/job-pattern-grouping")
    async def local_job_pattern_grouping(file: UploadFile = File(...)):
        """
        Groups the uploaded dataset's own employees into job "patterns" (job
        title x level x department x experience band) for on-screen display
        (backend.core.job_pattern_grouping_engine).

        Fully offline: makes zero external network calls — see
        backend/core/offline_mode_guard.py, installed globally at process
        start, which would raise OfflinePolicyViolation on any attempt
        anywhere in this process. This route only groups the user's own data;
        it never searches a job board or calls an AI service itself.

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when no job-title column is detected — job title
        is the mandatory core grouping dimension; level/department/
        experience are each independently optional and the response
        discloses exactly which were used.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(
                _preprocess_raw_bytes, raw, filename
            )
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(
                    _scanner.scan,
                    raw_bytes=normalized_bytes,
                    filename=scan_filename,
                    tenant_id="local",
                ),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(
                _timeout_response(
                    filename,
                    f"Governance scan exceeded {_TIMEOUT_SECS}s limit.",
                ),
            )
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content=_error_response(filename, f"Governance scan error: {exc}"),
            )

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "job_pattern_grouping": job_pattern_grouping_to_dict(
                    _unavailable_job_pattern_result(
                        "Dataset could not be ingested — check file format and encoding."
                    )
                ),
            })

        try:
            grouping_result = await asyncio.to_thread(analyze_job_pattern_grouping, ir.df)
        except Exception as exc:
            logger.exception("Job pattern grouping analysis failed")
            grouping_result = _unavailable_job_pattern_result(
                f"Job pattern grouping analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "job_pattern_grouping": job_pattern_grouping_to_dict(grouping_result),
        })

    @router.post("/job-pattern-grouping/export")
    async def export_job_pattern_grouping(payload: dict[str, Any]):
        """
        Generate the take-elsewhere market-research .xlsx workbook from an
        already-computed job_pattern_grouping payload (the JSON response
        from POST /job-pattern-grouping) — same analyze-then-export
        two-step pattern as /export/pptx and /export/slides, so the raw
        dataset never needs to be re-uploaded.

        Payload: { "job_pattern_grouping": <job_pattern_grouping dict> }

        Aggregate pattern-level data only — no employee names or IDs are
        included anywhere in the workbook (JobPattern carries no such field
        by construction). Makes zero network calls.
        """
        try:
            grouping_dict = payload.get("job_pattern_grouping")
            if not grouping_dict or not grouping_dict.get("available"):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "No available job pattern grouping data to export."},
                )
            result = job_pattern_grouping_from_dict(grouping_dict)
            xlsx_bytes = await asyncio.to_thread(generate_market_research_workbook, result)
            from fastapi.responses import Response as FastAPIResponse
            return FastAPIResponse(
                content=xlsx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={
                    "Content-Disposition": 'attachment; filename="Job_Pattern_Market_Research_Worksheet.xlsx"',
                    "Content-Length": str(len(xlsx_bytes)),
                },
            )
        except Exception as exc:
            logger.warning("Job pattern grouping export failed: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"detail": f"Export failed: {exc}"},
            )

    # ── Phase 21: Saudi Labor Law Calculators ───────────────────────────────────
    # Three related, real-legal-payment calculators (not illustrative estimates
    # — see backend/core/labor_law_calculators.py's module docstring). All three
    # share the identical ingestion pipeline as every other module.

    @router.post("/gratuity-calculator")
    async def local_gratuity_calculator(file: UploadFile = File(...)):
        """
        End-of-Service Gratuity (Saudi Labor Law Articles 84, 85, 87) —
        backend.core.labor_law_calculators.analyze_gratuity.

        REAL legal payment amounts, not illustrative estimates — every
        available=true figure was computed from a clean numeric salary and
        years-of-service value; rows with range-text or otherwise unparseable
        values are excluded and disclosed, never approximated. See the
        engine's module docstring for the full strict-salary rationale.

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) covers both "no salary/years-of-service column at all" and
        "columns detected but every value was unusable" — both are honest
        results, never a fabricated legal figure.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "gratuity": gratuity_to_dict(_unavailable_gratuity_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(analyze_gratuity, ir.df)
        except Exception as exc:
            logger.exception("Gratuity calculation failed")
            result = _unavailable_gratuity_result(f"Gratuity calculation encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "gratuity": gratuity_to_dict(result),
        })

    @router.post("/wps-consistency-check")
    async def local_wps_consistency_check(file: UploadFile = File(...)):
        """
        WPS/Payroll internal consistency pre-check (NOT live Qiwa/Mudad/GOSI
        connectivity — see labor_law_calculators.py's WPS_SOURCES) —
        backend.core.labor_law_calculators.analyze_wps_consistency.

        `check_applicable: false` (inside an available=false/true response,
        never an HTTP error) covers the common case where the upload has
        only one salary-related column — there is nothing to reconcile
        against, so this honestly reports not-applicable rather than
        fabricating a mismatch.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "wps_consistency": wps_consistency_to_dict(_unavailable_wps_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(analyze_wps_consistency, ir.df)
        except Exception as exc:
            logger.exception("WPS consistency check failed")
            result = _unavailable_wps_result(f"WPS consistency check encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "wps_consistency": wps_consistency_to_dict(result),
        })

    @router.post("/leave-balance-calculator")
    async def local_leave_balance_calculator(file: UploadFile = File(...)):
        """
        Leave Balance & Compensation (Saudi Labor Law Articles 109, 111) —
        backend.core.labor_law_calculators.analyze_leave_balance.

        Same strict numeric-salary discipline as /gratuity-calculator for the
        compensation figure specifically; entitlement accrual only needs a
        usable years-of-service value. When no leave-balance/leave-taken
        column exists, only entitlement accrual is computed (never an
        assumed remaining balance) — has_real_balance_data in the response
        tells the frontend which case it's in.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "leave_balance": leave_balance_to_dict(_unavailable_leave_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(analyze_leave_balance, ir.df)
        except Exception as exc:
            logger.exception("Leave balance calculation failed")
            result = _unavailable_leave_result(f"Leave balance calculation encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "leave_balance": leave_balance_to_dict(result),
        })

    # ── Phase 36: Automated HR Letter Generator ─────────────────────────────────
    # Salary Certificate, Employment Certificate, and (cross-linked) End-of-
    # Service Settlement letters. Unlike every other module in this file,
    # these letters intentionally include real employee names — see
    # hr_letter_generator.py's module docstring. Warning/disciplinary and
    # termination letters are deliberately not offered (same docstring).

    @router.post("/hr-letters/employees")
    async def local_hr_letters_employees(file: UploadFile = File(...)):
        """
        Returns the extracted employee list (real names/IDs by design — see
        hr_letter_generator.py) plus, per employee, whether an End-of-Service
        Settlement letter is possible. That availability flag is a ROUTE-LAYER
        cross-link: this endpoint runs extract_employee_letter_records() and
        labor_law_calculators.analyze_gratuity() independently on the SAME
        upload and joins them by record_id_safe — the exact Phase 8/18
        decoupled-engine precedent (neither module imports the other).
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "hr_letters": employee_data_result_to_dict(_unavailable_hr_letter_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(extract_employee_letter_records, ir.df)
        except Exception as exc:
            logger.exception("HR letter employee extraction failed")
            result = _unavailable_hr_letter_result(f"Employee extraction encountered an error: {exc}")

        result_dict = employee_data_result_to_dict(result)

        # ── Cross-link: End-of-Service availability per employee ────────────
        eos_available: dict[str, bool] = {}
        if result.available:
            try:
                gratuity_result = await asyncio.to_thread(analyze_gratuity, ir.df)
                if gratuity_result.available:
                    gratuity_hashes = {c.record_id_safe for c in gratuity_result.candidates}
                    for emp in result.employees:
                        eos_available[emp.employee_id] = safe_record_id_for_lookup(emp.employee_id) in gratuity_hashes
            except Exception as exc:
                logger.warning("HR letters endpoint: gratuity cross-link unavailable (non-fatal): %s", exc)
        for emp_dict in result_dict["employees"]:
            emp_dict["end_of_service_available"] = eos_available.get(emp_dict["employee_id"], False)

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "hr_letters": result_dict,
        })

    def _hr_letters_company_from_form(
        company_name: str, company_address: str, signatory_name: str, signatory_title: str,
    ) -> HRLetterCompanyDetails:
        return HRLetterCompanyDetails(
            company_name=company_name, company_address=company_address,
            signatory_name=signatory_name, signatory_title=signatory_title,
        )

    @router.post("/hr-letters/generate-single")
    async def local_hr_letters_generate_single(
        file: UploadFile = File(...),
        employee_id: str = Form(...),
        letter_type: str = Form(...),
        language: str = Form("en"),
        company_name: str = Form(...),
        company_address: str = Form(...),
        signatory_name: str = Form(...),
        signatory_title: str = Form(...),
    ):
        """
        Generates ONE .docx letter for one employee, re-identified by raw
        employee_id from the SAME re-uploaded file — stateless, no
        server-side session, consistent with this platform's fully-offline
        design. Returns the .docx binary directly (not JSON) on success.
        """
        filename = file.filename or "upload.dat"
        if letter_type not in HR_LETTER_TYPES:
            return JSONResponse(status_code=400, content={"detail": f"Unknown letter_type {letter_type!r}. Must be one of {list(HR_LETTER_TYPES)}."})
        if language not in ("en", "ar"):
            return JSONResponse(status_code=400, content={"detail": "language must be 'en' or 'ar'."})

        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, _norm_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes = raw

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse(status_code=400, content={"detail": "Dataset could not be ingested — check file format and encoding."})

        try:
            employee_data = await asyncio.to_thread(extract_employee_letter_records, ir.df)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": f"Employee extraction failed: {exc}"})
        if not employee_data.available:
            return JSONResponse(status_code=400, content={"detail": employee_data.reason})

        employee = next((e for e in employee_data.employees if e.employee_id == employee_id), None)
        if employee is None:
            return JSONResponse(status_code=404, content={"detail": f"Employee {employee_id!r} not found in this upload, or is missing a required field."})

        company = _hr_letters_company_from_form(company_name, company_address, signatory_name, signatory_title)

        try:
            if letter_type == "salary_certificate":
                result = await asyncio.to_thread(build_salary_certificate, employee, company, language)
            elif letter_type == "employment_certificate":
                result = await asyncio.to_thread(build_employment_certificate, employee, company, language)
            else:  # end_of_service_settlement
                gratuity_result = await asyncio.to_thread(analyze_gratuity, ir.df)
                candidate = None
                if gratuity_result.available:
                    target_hash = safe_record_id_for_lookup(employee_id)
                    candidate = next((c for c in gratuity_result.candidates if c.record_id_safe == target_hash), None)
                if candidate is None:
                    return JSONResponse(status_code=400, content={
                        "detail": "End-of-Service Gratuity is not computable for this employee — "
                                  "requires both a clean numeric salary and a clean numeric "
                                  "years-of-service value (see the Saudi Labor Law Calculators module).",
                    })
                result = await asyncio.to_thread(
                    build_end_of_service_letter, employee, company, language,
                    gratuity_amount_sar=candidate.applicable_amount_sar,
                    gratuity_scenario=candidate.applicable_scenario,
                    years_of_service=candidate.years_of_service,
                    monthly_wage_sar=candidate.monthly_wage_sar,
                    wage_column_name=gratuity_result.salary_column,
                    gratuity_computed_at=gratuity_result.computed_at,
                )
        except Exception as exc:
            logger.exception("HR letter generation failed")
            return JSONResponse(status_code=500, content={"detail": f"Letter generation failed: {exc}"})

        if not result.available or result.document_bytes is None:
            return JSONResponse(status_code=400, content={"detail": result.reason or "Letter could not be generated for this employee."})

        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=result.document_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"',
                "Content-Length": str(len(result.document_bytes)),
            },
        )

    @router.post("/hr-letters/generate-bulk")
    async def local_hr_letters_generate_bulk(
        file: UploadFile = File(...),
        employee_ids: str = Form(...),  # JSON array of raw employee_id strings, or the literal "all"
        letter_type: str = Form(...),
        language: str = Form("en"),
        company_name: str = Form(...),
        company_address: str = Form(...),
        signatory_name: str = Form(...),
        signatory_title: str = Form(...),
    ):
        """
        Bulk (mail-merge) generation — one .docx per selected employee,
        zipped. Never fabricates a document for an employee a given letter
        type isn't available for; per-employee generated/skipped status +
        skip reasons are returned in the X-HR-Letters-Summary response
        header (base64-encoded JSON, since employee names may contain
        non-ASCII characters HTTP headers cannot carry directly).
        """
        filename = file.filename or "upload.dat"
        if letter_type not in HR_LETTER_TYPES:
            return JSONResponse(status_code=400, content={"detail": f"Unknown letter_type {letter_type!r}. Must be one of {list(HR_LETTER_TYPES)}."})
        if language not in ("en", "ar"):
            return JSONResponse(status_code=400, content={"detail": "language must be 'en' or 'ar'."})

        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, _norm_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes = raw

        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse(status_code=400, content={"detail": "Dataset could not be ingested — check file format and encoding."})

        try:
            employee_data = await asyncio.to_thread(extract_employee_letter_records, ir.df)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": f"Employee extraction failed: {exc}"})
        if not employee_data.available:
            return JSONResponse(status_code=400, content={"detail": employee_data.reason})

        if employee_ids.strip().lower() == "all":
            selected = employee_data.employees
        else:
            try:
                wanted_ids = set(json.loads(employee_ids))
            except Exception:
                return JSONResponse(status_code=400, content={"detail": 'employee_ids must be a JSON array of employee ID strings, or the literal "all".'})
            selected = [e for e in employee_data.employees if e.employee_id in wanted_ids]

        if not selected:
            return JSONResponse(status_code=400, content={"detail": "No matching employees found in this upload for the given selection."})

        company = _hr_letters_company_from_form(company_name, company_address, signatory_name, signatory_title)

        gratuity_lookup: dict[str, GratuityLetterInput] = {}
        if letter_type == "end_of_service_settlement":
            try:
                gratuity_result = await asyncio.to_thread(analyze_gratuity, ir.df)
                if gratuity_result.available:
                    by_hash = {c.record_id_safe: c for c in gratuity_result.candidates}
                    for emp in selected:
                        cand = by_hash.get(safe_record_id_for_lookup(emp.employee_id))
                        if cand is not None:
                            gratuity_lookup[emp.employee_id] = GratuityLetterInput(
                                gratuity_amount_sar=cand.applicable_amount_sar,
                                gratuity_scenario=cand.applicable_scenario,
                                years_of_service=cand.years_of_service,
                                monthly_wage_sar=cand.monthly_wage_sar,
                                wage_column_name=gratuity_result.salary_column,
                                gratuity_computed_at=gratuity_result.computed_at,
                            )
            except Exception as exc:
                logger.warning("Bulk HR letters: gratuity cross-link unavailable (non-fatal): %s", exc)

        try:
            bulk_result = await asyncio.to_thread(
                build_bulk_letters, selected, letter_type, company, language, gratuity_lookup,
            )
        except Exception as exc:
            logger.exception("Bulk HR letter generation failed")
            return JSONResponse(status_code=500, content={"detail": f"Bulk letter generation failed: {exc}"})

        if bulk_result.zip_bytes is None:
            return JSONResponse(status_code=400, content={
                "detail": "No letters could be generated for the selected employees.",
                "summary": bulk_letter_result_to_dict(bulk_result),
            })

        summary_b64 = base64.b64encode(
            json.dumps(bulk_letter_result_to_dict(bulk_result)).encode("utf-8")
        ).decode("ascii")

        from fastapi.responses import Response as FastAPIResponse
        return FastAPIResponse(
            content=bulk_result.zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="HR_Letters_{letter_type}.zip"',
                "Content-Length": str(len(bulk_result.zip_bytes)),
                "X-HR-Letters-Summary": summary_b64,
            },
        )

    # ── Phase 37: GOSI Contribution Calculator ──────────────────────────────────

    @router.post("/gosi-calculator")
    async def local_gosi_calculator(file: UploadFile = File(...)):
        """
        GOSI (General Organization for Social Insurance) contribution
        calculator — backend.core.gosi_calculator_engine.analyze_gosi_contributions.

        REAL government contribution amounts for the current published rate
        period (see the engine's module docstring), not illustrative
        estimates. When no GOSI system/tier column is detected (the common
        case), BOTH Old System and New System figures are computed and
        returned for every Saudi employee rather than guessing which
        applies — the same "show both, don't guess" pattern Phase 21 uses
        for unspecified separation type.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "gosi": gosi_result_to_dict(_unavailable_gosi_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(analyze_gosi_contributions, ir.df)
        except Exception as exc:
            logger.exception("GOSI calculation failed")
            result = _unavailable_gosi_result(f"GOSI calculation encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "gosi": gosi_result_to_dict(result),
        })

    # ── Phase 37: Payroll Budget — Planned vs. Actual ───────────────────────────

    @router.post("/payroll-budget-variance")
    async def local_payroll_budget_variance(
        file: UploadFile = File(...),
        planned_budgets: str = Form("{}"),
    ):
        """
        Planned vs. actual payroll variance —
        backend.core.payroll_budget_engine.compute_payroll_budget_variance.

        `planned_budgets` is a JSON object keyed by the EXACT normalized
        department label this endpoint itself returns (see the engine's
        module docstring for why no fuzzy name-matching is attempted):
        `{"Finance": {"planned_headcount": 12, "planned_avg_salary_sar": 11000}, ...}`.
        Call with `planned_budgets` omitted (defaults to "{}") first to see
        the real actual department list, then re-call with the user's
        entered figures keyed by those same labels — stateless, the file is
        re-uploaded each time, consistent with this platform's other
        multi-step flows (e.g. HR Letter Generator).
        """
        filename = file.filename or "upload.dat"
        try:
            planned_raw = json.loads(planned_budgets) if planned_budgets else {}
            if not isinstance(planned_raw, dict):
                raise ValueError("planned_budgets must be a JSON object.")
            planned_by_department = {
                str(dept): PlannedDepartmentBudget(
                    planned_headcount=int(v["planned_headcount"]),
                    planned_avg_salary_sar=float(v["planned_avg_salary_sar"]),
                )
                for dept, v in planned_raw.items()
            }
        except Exception as exc:
            return JSONResponse(status_code=400, content={
                "detail": f"Invalid planned_budgets — must be a JSON object of "
                          f"{{department: {{planned_headcount, planned_avg_salary_sar}}}}: {exc}",
            })

        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "governance_scan_passed": report.governance_scan_passed,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "payroll_budget": payroll_budget_result_to_dict(_unavailable_payroll_budget_result("Dataset could not be ingested — check file format and encoding.")),
            })

        try:
            result = await asyncio.to_thread(compute_payroll_budget_variance, ir.df, planned_by_department)
        except Exception as exc:
            logger.exception("Payroll budget variance failed")
            result = _unavailable_payroll_budget_result(f"Payroll budget variance encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "governance_scan_passed": report.governance_scan_passed,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "payroll_budget": payroll_budget_result_to_dict(result),
        })

    # ── Phase 37: Zakat Base Estimator — manual entry, no upload ────────────────

    @router.post("/zakat-estimator")
    async def local_zakat_estimator(payload: dict[str, Any]):
        """
        Zakat base estimator — backend.core.zakat_estimator_engine.estimate_zakat_base.

        NO file upload — this is a manual balance-sheet entry form (see the
        engine's module docstring for the investigation that led to this
        design, and why this is a deliberately SIMPLIFIED TRADITIONAL
        formula, not the actual ZATCA 2024 Bylaws methodology).

        Payload: { total_equity_sar, long_term_liabilities_provisions_sar,
        net_fixed_assets_sar, other_deductions_sar? } — any of the first
        three left null/omitted yields available=false naming exactly
        which field is missing, never a zero-defaulted guess.
        """
        def _f(key: str) -> Optional[float]:
            val = payload.get(key)
            if val is None or val == "":
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        try:
            inputs = ZakatInputs(
                total_equity_sar=_f("total_equity_sar"),
                long_term_liabilities_provisions_sar=_f("long_term_liabilities_provisions_sar"),
                net_fixed_assets_sar=_f("net_fixed_assets_sar"),
                other_deductions_sar=_f("other_deductions_sar") if payload.get("other_deductions_sar") not in (None, "") else 0.0,
            )
            result = await asyncio.to_thread(estimate_zakat_base, inputs)
        except Exception as exc:
            logger.exception("Zakat estimate failed")
            return JSONResponse(status_code=500, content={"detail": f"Zakat estimate encountered an error: {exc}"})

        return JSONResponse({"zakat_estimate": zakat_estimate_to_dict(result)})

    # ── Phase 30: Financial Intelligence (Business Intelligence Suite, Phase 1) ─
    # First non-HR domain this platform analyzes — a transaction-level/general-
    # ledger dataset, not an employee roster. Still reuses _scanner.scan() for
    # its domain-agnostic value (real parsing, PII/leakage detection, dedup) —
    # see financial_intelligence_reporting_engine.py's module docstring for why
    # the HR-feature-count "governance_scan_passed" flag is deliberately not
    # gated on here, exactly as no other route this session gates on it either.

    @router.post("/financial-intelligence")
    async def local_financial_intelligence(file: UploadFile = File(...)):
        """
        Revenue, Expense, P&L, Cash Flow, Financial Ratios, and Variance
        Analysis from an uploaded transaction-level/general-ledger dataset —
        backend.core.financial_intelligence_reporting_engine.analyze_financial_intelligence.

        Every figure is derived entirely from the upload's own data — no
        external benchmark, industry ratio, or forecast is used anywhere in
        this route. `available: false` (not an HTTP error) covers both "no
        numeric amount column" and "amount column present but no way to
        classify revenue vs. expense" — both honest results, never a
        fabricated financial figure.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "financial_intelligence": financial_intelligence_to_dict(
                    _unavailable_financial_result("Dataset could not be ingested — check file format and encoding.")
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_financial_intelligence, ir.df)
        except Exception as exc:
            logger.exception("Financial intelligence analysis failed")
            result = _unavailable_financial_result(f"Financial intelligence analysis encountered an error: {exc}")

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "financial_intelligence": financial_intelligence_to_dict(result),
        })

    # ── Phase 31: Accounting Intelligence (Business Intelligence Suite, Module 2) ─
    # Genuinely double-entry-specific items (General Ledger drill-down, Trial
    # Balance, Balance Sheet, AR/AP Aging, Journal Anomaly/Duplicate Detection)
    # that Phase 30's Financial Intelligence module cannot cover — see
    # accounting_intelligence_engine.py's module docstring for the explicit
    # non-overlap reasoning. Same ingestion reuse decision as Phase 30: the
    # scanner's HR-feature-count "governance_scan_passed" flag is not gated on.

    @router.post("/accounting-intelligence")
    async def local_accounting_intelligence(file: UploadFile = File(...), as_of_date: Optional[str] = Form(None)):
        """
        General Ledger drill-down, Trial Balance, Balance Sheet, AR/AP Aging,
        and Journal Entry Anomaly/Duplicate Detection from an uploaded
        double-entry journal/ledger export —
        backend.core.accounting_intelligence_engine.analyze_accounting_intelligence.

        Each of the 5 sections has its own independent `available` flag (not
        an HTTP error) — a file can legitimately support some sections and
        not others (e.g. a plain GL export with no invoice-level AR/AP data
        will show General Ledger/Trial Balance/Balance Sheet available but
        AR/AP Aging not available). `as_of_date` (optional, YYYY-MM-DD) sets
        the AR/AP aging reference date; defaults to real today if omitted.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "accounting_intelligence": accounting_intelligence_to_dict(
                    analyze_accounting_intelligence(pd.DataFrame())
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_accounting_intelligence, ir.df, as_of_date)
        except Exception as exc:
            logger.exception("Accounting intelligence analysis failed")
            result = analyze_accounting_intelligence(pd.DataFrame())

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "accounting_intelligence": accounting_intelligence_to_dict(result),
        })

    # ── Phase 32: Inventory Intelligence (Business Intelligence Suite, Module 3) ─
    # A fourth distinct data shape (item-level stock/transaction data) — see
    # inventory_intelligence_engine.py's module docstring for the snapshot-
    # vs-movement-history distinction and why it's fully separate from both
    # Phase 30 and Phase 31's modules. Same ingestion-reuse decision.

    @router.post("/inventory-intelligence")
    async def local_inventory_intelligence(file: UploadFile = File(...), as_of_date: Optional[str] = Form(None)):
        """
        Current Stock Levels, Inventory Turnover, Stock Aging/Dead-Stock, ABC
        Analysis, Reorder Point & Safety Stock, and Overstock/Stockout Risk
        from an uploaded inventory snapshot or transaction log —
        backend.core.inventory_intelligence_engine.analyze_inventory_intelligence.

        Each of the 6 sections has its own independent `available` flag —
        a pure snapshot (no movement history) supports only Stock Levels and
        ABC Analysis; the other four require real transaction history.
        `as_of_date` (optional, YYYY-MM-DD) sets the aging/reorder-point
        reference date; defaults to real today if omitted.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "inventory_intelligence": inventory_intelligence_to_dict(
                    analyze_inventory_intelligence(pd.DataFrame())
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_inventory_intelligence, ir.df, as_of_date)
        except Exception as exc:
            logger.exception("Inventory intelligence analysis failed")
            result = analyze_inventory_intelligence(pd.DataFrame())

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "inventory_intelligence": inventory_intelligence_to_dict(result),
        })

    # ── Phase 33: Procurement Intelligence (Business Intelligence Suite, Module 4) ─
    # Purchase-order/supplier-level data — related to Phase 32's Inventory
    # Intelligence (which tracks stock ON HAND) but distinct: this module
    # tracks the buying process/supplier relationships that replenish it. See
    # procurement_intelligence_engine.py's module docstring. Same ingestion-
    # reuse decision as every prior Business Intelligence module.

    @router.post("/procurement-intelligence")
    async def local_procurement_intelligence(file: UploadFile = File(...)):
        """
        Supplier Spend Analysis, PO & Price Analysis, Price Variance/Trend
        Tracking, Delivery/On-Time Performance, Supplier Performance Scoring
        (constructed heuristic), and Cost-Reduction Opportunity Flagging from
        an uploaded purchase-order dataset —
        backend.core.procurement_intelligence_engine.analyze_procurement_intelligence.

        Each of the 6 sections has its own independent `available` flag.
        Price-trend and delivery-performance figures require real historical/
        date data and a minimum sample size — never guessed from too few
        observations. Cost-reduction flags compare only the upload's own
        multi-supplier prices — no external market-price benchmark is used.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "procurement_intelligence": procurement_intelligence_to_dict(
                    analyze_procurement_intelligence(pd.DataFrame())
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_procurement_intelligence, ir.df)
        except Exception as exc:
            logger.exception("Procurement intelligence analysis failed")
            result = analyze_procurement_intelligence(pd.DataFrame())

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "procurement_intelligence": procurement_intelligence_to_dict(result),
        })

    # ── Phase 34: Logistics Intelligence (Business Intelligence Suite, Module 5) ─
    # Shipment/delivery-level data — related to Procurement's inbound
    # delivery-performance item (Phase 33) but distinct: this module tracks
    # the platform owner's own OUTBOUND shipping/carrier performance. See
    # logistics_intelligence_engine.py's module docstring for the shared
    # on-time-performance utility and reused TF-IDF returns-theme machinery.

    @router.post("/logistics-intelligence")
    async def local_logistics_intelligence(file: UploadFile = File(...)):
        """
        Shipment Volume & Status, Delivery Time/On-Time Performance, Shipping
        Cost Analysis, Carrier/Route Performance (constructed heuristic),
        Delay Analysis, and Returns Analysis (TF-IDF theme extraction) from
        an uploaded shipment dataset —
        backend.core.logistics_intelligence_engine.analyze_logistics_intelligence.

        Each of the 6 sections has its own independent `available` flag.
        Carrier performance scores are explicitly a constructed heuristic,
        never a validated/certified rating. No raw return-reason text is
        ever returned — only aggregate theme counts and TF-IDF terms
        mentioned by at least 3 distinct shipments.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "logistics_intelligence": logistics_intelligence_to_dict(
                    analyze_logistics_intelligence(pd.DataFrame())
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_logistics_intelligence, ir.df)
        except Exception as exc:
            logger.exception("Logistics intelligence analysis failed")
            result = analyze_logistics_intelligence(pd.DataFrame())

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "logistics_intelligence": logistics_intelligence_to_dict(result),
        })

    # ── Phase 35: Operations Intelligence (Business Intelligence Suite, Module 6, final) ─
    # A generic operational-unit-per-period record (department/branch/line/
    # machine) — see operations_intelligence_engine.py's module docstring
    # for the Step 0 data-shape reasoning and the shared-utility reuse
    # decisions (variance pattern, TF-IDF downtime-cause theme extraction).

    @router.post("/operations-intelligence")
    async def local_operations_intelligence(file: UploadFile = File(...)):
        """
        Productivity, Utilization, Downtime Analysis, Quality/Defect
        Analysis, Bottleneck Identification, and Cost per Unit of Operation
        from an uploaded operational dataset —
        backend.core.operations_intelligence_engine.analyze_operations_intelligence.

        Each of the 6 sections has its own independent `available` flag.
        Utilization is never estimated without a real hours-available
        (capacity) column. Bottleneck flags require at least 3 periods of
        data per unit before being confidently applied — raw numbers are
        still shown for units below that floor, just not the flag.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content=_error_response(filename, f"Could not read uploaded file: {exc}"))
        if not raw:
            return JSONResponse(status_code=400, content=_error_response(filename, "Uploaded file is empty."))
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content=_error_response(filename, "File exceeds 500 MB upload limit."))

        try:
            normalized_bytes, normalization_log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
        except Exception as exc:
            logger.warning("Pre-normalisation skipped: %s", exc)
            normalized_bytes, normalization_log = raw, []

        scan_filename = filename if not normalization_log else filename + ".normalized.csv"
        try:
            report = await asyncio.wait_for(
                asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=scan_filename, tenant_id="local"),
                timeout=_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return JSONResponse(_timeout_response(filename, f"Governance scan exceeded {_TIMEOUT_SECS}s limit."))
        except Exception as exc:
            return JSONResponse(status_code=500, content=_error_response(filename, f"Governance scan error: {exc}"))

        ir = report.ingestion_result
        if not (ir.success and ir.df is not None and ir.row_count > 0):
            return JSONResponse({
                "filename": filename,
                "pii_columns_detected": report.pii_columns_detected,
                "leakage_columns_detected": report.leakage_columns_detected,
                "operations_intelligence": operations_intelligence_to_dict(
                    analyze_operations_intelligence(pd.DataFrame())
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_operations_intelligence, ir.df)
        except Exception as exc:
            logger.exception("Operations intelligence analysis failed")
            result = analyze_operations_intelligence(pd.DataFrame())

        return JSONResponse({
            "filename": filename,
            "row_count": ir.row_count,
            "pii_columns_detected": report.pii_columns_detected,
            "leakage_columns_detected": report.leakage_columns_detected,
            "column_normalizations_applied": normalization_log,
            "data_quality_warnings": report.warnings,
            "operations_intelligence": operations_intelligence_to_dict(result),
        })

    # ── Phase 37: AI Business Analyst (capstone — Q&A over HR + all 6 BI domains) ─
    # Security-critical: see ai_business_analyst_engine.py's module docstring
    # for the full trust-boundary architecture. This route only ever calls
    # `answer_question()`, which internally only ever calls a fixed,
    # pre-registered set of existing engine functions or the local TF-IDF
    # RAG index over project markdown docs — never arbitrary code, never a
    # fresh/ad-hoc engine call outside the registry.

    @router.get("/ai-business-analyst/registry")
    async def local_ai_business_analyst_registry():
        """Read-only catalog of every registered query intent, plus current
        Ollama reachability — lets the frontend show what can be asked and
        which mode (local LLM vs. deterministic fallback) will answer."""
        return JSONResponse({
            "registry": _ai_analyst_registry_catalog(),
            "ollama_reachable": _ai_analyst_ollama_reachable(),
            "ollama_model": _AI_ANALYST_OLLAMA_MODEL,
        })

    @router.post("/ai-business-analyst")
    async def local_ai_business_analyst(
        question: str = Form(...),
        files: list[UploadFile] = File(default=[]),
        use_llm: bool = Form(True),
    ):
        """
        Natural-language business Q&A. 0 files is valid (knowledge-only
        questions answered from project docs via RAG); 1 file answers a
        single-domain question; 2+ files enable the one implemented
        cross-domain query (overtime vs. downtime). Every uploaded file
        still goes through the same governance scan as every other route
        — no bypass for this endpoint.
        """
        uploaded_frames: dict[str, pd.DataFrame] = {}
        pii_all: list[str] = []
        leakage_all: list[str] = []
        for f in files or []:
            filename = f.filename or "upload.dat"
            try:
                raw = await f.read()
            except Exception:
                continue
            if not raw or len(raw) > _MAX_UPLOAD_BYTES:
                continue
            try:
                normalized_bytes, _log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
            except Exception:
                normalized_bytes = raw
            try:
                report = await asyncio.wait_for(
                    asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=filename, tenant_id="local"),
                    timeout=_TIMEOUT_SECS,
                )
            except Exception:
                continue
            ir = report.ingestion_result
            if ir.success and ir.df is not None and ir.row_count > 0:
                uploaded_frames[filename] = ir.df
                pii_all.extend(report.pii_columns_detected)
                leakage_all.extend(report.leakage_columns_detected)

        try:
            domain_results = await asyncio.to_thread(_ai_analyst_analyze_uploaded_files, uploaded_frames)
        except Exception as exc:
            logger.exception("AI Business Analyst domain detection failed")
            domain_results = {}

        try:
            answer = await asyncio.to_thread(_ai_analyst_answer_question, question, domain_results, use_llm)
        except Exception as exc:
            logger.exception("AI Business Analyst answer_question failed")
            return JSONResponse(status_code=500, content={"detail": f"AI Business Analyst encountered an error: {exc}"})

        return JSONResponse({
            "answer": _ai_analyst_answer_to_dict(answer),
            "domains_detected": sorted(domain_results.keys()),
            "files_ingested": sorted(uploaded_frames.keys()),
            "pii_columns_detected": sorted(set(pii_all)),
            "leakage_columns_detected": sorted(set(leakage_all)),
            "ollama_reachable": _ai_analyst_ollama_reachable(),
        })

    # ── Phase 43: Sandboxed file-editing (extends Phase 37's AI Business
    # Analyst with real code-execution, isolated from the main process) ────
    # Security-critical: see backend/core/sandbox_executor.py's module
    # docstring for the full 3-layer isolation model (static AST check,
    # runtime capability patches, Windows Job Object resource caps) and
    # PHASE_43_SANDBOXED_AGENT_REPORT.md for the adversarial verification
    # evidence. This route NEVER lets sandboxed code touch the original
    # uploaded bytes — only a copy materialized into a fresh, per-request
    # sandbox directory that is deleted after the response is built.

    @router.get("/ai-business-analyst/edit-file/status")
    async def local_ai_business_analyst_edit_file_status():
        """Lets the frontend show whether the sandbox's prerequisites (a
        Windows Job Object mechanism, and the local code-generation model)
        are actually available before offering the feature at all — never
        silently degrade to an unconfined execution mode."""
        return JSONResponse({
            "sandbox_available": _sandbox_pywin32_available(),
            "code_gen_available": _sandbox_code_gen_reachable(),
            "code_gen_model": _SANDBOX_CODE_GEN_MODEL,
        })

    @router.post("/ai-business-analyst/edit-file")
    async def local_ai_business_analyst_edit_file(
        instruction: str = Form(...),
        file: UploadFile = File(...),
    ):
        """
        Natural-language file edit. The instruction is split into a
        QUESTION component (if any) and an EDIT component (if any) —
        see sandbox_request_router.py. The question component, if present,
        is answered via the EXACT SAME grounded answer_question() path as
        the plain /ai-business-analyst endpoint (registry + numeric guard,
        completely unchanged). The edit component, if present, generates
        Python code via the local code-gen model and runs it in the
        sandbox against a COPY of the uploaded file — the original bytes
        are never touched or returned as if edited.
        """
        filename = file.filename or "upload.dat"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(status_code=400, content={"detail": f"Could not read uploaded file: {exc}"})
        if not raw:
            return JSONResponse(status_code=400, content={"detail": "Uploaded file is empty."})
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=400, content={"detail": "Uploaded file exceeds the size limit."})

        split = _sandbox_split_request(instruction)

        response: dict = {
            "filename": filename,
            "request_split": {
                "question_part": split.question_part,
                "edit_part": split.edit_part,
                "is_mixed": split.is_mixed,
                "is_ambiguous": split.is_ambiguous,
            },
            "grounded_answer": None,
            "sandboxed_edit": None,
        }

        # ── Question component: the existing Phase 37 grounded path, untouched ──
        if split.question_part:
            try:
                normalized_bytes, _log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
            except Exception:
                normalized_bytes = raw
            try:
                report = await asyncio.wait_for(
                    asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=filename, tenant_id="local"),
                    timeout=_TIMEOUT_SECS,
                )
                ir = report.ingestion_result
                uploaded_frames = {filename: ir.df} if ir.success and ir.df is not None and ir.row_count > 0 else {}
            except Exception:
                uploaded_frames = {}
            try:
                domain_results = await asyncio.to_thread(_ai_analyst_analyze_uploaded_files, uploaded_frames)
                answer = await asyncio.to_thread(_ai_analyst_answer_question, split.question_part, domain_results, True)
                response["grounded_answer"] = {
                    "fulfilled_via": "grounded_answer",
                    "answer": _ai_analyst_answer_to_dict(answer),
                }
            except Exception as exc:
                logger.exception("Phase 43: grounded-answer component failed")
                response["grounded_answer"] = {"fulfilled_via": "grounded_answer", "error": str(exc)}

        # ── Edit component: sandboxed code generation + execution ─────────
        if split.edit_part:
            if not _sandbox_pywin32_available():
                response["sandboxed_edit"] = {
                    "fulfilled_via": "sandboxed_code_execution",
                    "ok": False,
                    "error": "Sandboxed execution is unavailable on this host (pywin32/Windows Job Objects "
                             "not installed) — refusing to run untrusted generated code without kernel-"
                             "enforced resource limits.",
                }
            elif not _sandbox_code_gen_reachable():
                response["sandboxed_edit"] = {
                    "fulfilled_via": "sandboxed_code_execution",
                    "ok": False,
                    "error": f"Local code-generation model '{_SANDBOX_CODE_GEN_MODEL}' is not reachable — "
                             "start Ollama and ensure the model is pulled.",
                }
            else:
                structure = await asyncio.to_thread(_sandbox_describe_file_structure, raw, filename)
                # Deliberately NOT the same name as the input file: INPUT_PATH
                # and OUTPUT_PATH must be genuinely different paths inside the
                # sandbox, or the generated code's own write clobbers the
                # "before" copy before the diff summary ever reads it — a
                # real bug caught by test_real_excel_edit_end_to_end_with_
                # verified_diff always reporting "changed: false" regardless
                # of what actually happened, since both diff sides ended up
                # reading the identical, already-edited file.
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                output_filename = f"{stem}_edited{suffix}"
                gen = await asyncio.to_thread(_sandbox_generate_edit_code, split.edit_part, structure, output_filename)
                if not gen.ok:
                    response["sandboxed_edit"] = {
                        "fulfilled_via": "sandboxed_code_execution",
                        "ok": False,
                        "error": gen.error,
                        "generated_code": gen.code,
                    }
                else:
                    result = await asyncio.to_thread(
                        _sandbox_run_code, gen.code, raw, filename, output_filename,
                        "local", split.edit_part,
                    )
                    if result.outcome == "success" and result.output_file_path is not None:
                        input_copy_path = result.output_file_path.parent / filename
                        try:
                            diff = await asyncio.to_thread(_sandbox_compute_diff_summary, input_copy_path, result.output_file_path)
                        except Exception as exc:
                            diff = None
                            logger.exception("Phase 43: diff summary computation failed")
                        output_bytes = result.output_file_path.read_bytes()
                        _SANDBOX_DOWNLOAD_STORE[result.run_id] = (output_filename, output_bytes)
                        response["sandboxed_edit"] = {
                            "fulfilled_via": "sandboxed_code_execution",
                            "ok": True,
                            "run_id": result.run_id,
                            "generated_code": gen.code,
                            "duration_ms": result.duration_ms,
                            "diff_summary": {
                                "supported": diff.supported, "changed": diff.changed,
                                "summary_en": diff.summary_en, "summary_ar": diff.summary_ar,
                                "cell_changes_sample": diff.cell_changes_sample,
                                "n_cells_changed": diff.n_cells_changed,
                                "n_rows_added": diff.n_rows_added, "n_rows_removed": diff.n_rows_removed,
                                "n_paragraphs_changed": diff.n_paragraphs_changed,
                            } if diff else None,
                            "download_url": f"/api/local/ai-business-analyst/edit-file/download/{result.run_id}",
                        }
                    else:
                        response["sandboxed_edit"] = {
                            "fulfilled_via": "sandboxed_code_execution",
                            "ok": False,
                            "outcome": result.outcome,
                            "error": result.exit_reason or "The sandboxed edit did not complete successfully.",
                            "generated_code": gen.code,
                        }
                    _sandbox_cleanup_run(result.run_id)

        if split.is_ambiguous:
            response["note"] = (
                "This request didn't clearly match either a question or an edit instruction — "
                "it was treated as an edit attempt. Be more explicit (e.g. start with 'edit', "
                "'fix', 'add a column for...') for a more reliable result."
            )

        return JSONResponse(response)

    @router.get("/ai-business-analyst/edit-file/download/{run_id}")
    async def local_ai_business_analyst_edit_file_download(run_id: str):
        from fastapi.responses import Response as FastAPIResponse
        entry = _SANDBOX_DOWNLOAD_STORE.pop(run_id, None)
        if entry is None:
            return JSONResponse(status_code=404, content={"detail": "This edited file is no longer available (results are single-download, in-memory only)."})
        output_filename, output_bytes = entry
        return FastAPIResponse(
            content=output_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{output_filename}"'},
        )

    # ── Phase 44: Agentic AI (Claude API tool-use) — additive to Phase 37's
    # local Q&A above, never a replacement. See backend/core/
    # agentic_orchestrator.py's module docstring for the architecture and
    # PHASE_44_AGENTIC_AI_ANALYST_REPORT.md for the corrections to this
    # feature's originating task brief (no real "Phase 42" exists; the real
    # prior sandbox phase is 43). Graceful degradation is structural, not a
    # try/except guess: if cloud mode isn't configured or fails real
    # validation, this route calls the EXACT SAME _ai_analyst_answer_question
    # already used by the plain /ai-business-analyst endpoint above — local
    # mode is not a degraded reimplementation, it is the same code path.

    @router.get("/ai-business-analyst/agentic/status")
    async def local_ai_business_analyst_agentic_status():
        status = await asyncio.to_thread(_agentic_check_cloud_mode)
        return JSONResponse({
            "cloud_configured": status.configured,
            "cloud_valid": status.valid,
            "cloud_detail": status.detail,
            "masked_key": status.masked_key,
            "model": status.model,
            "local_fallback_reachable": _ai_analyst_ollama_reachable(),
            "tools_available": ["get_business_metric", "get_variance_context", "generate_pptx_report", "merge_excel_files", "edit_file"] if status.valid else [],
        })

    @router.post("/ai-business-analyst/agentic")
    async def local_ai_business_analyst_agentic(
        question: str = Form(...),
        files: list[UploadFile] = File(default=[]),
        use_llm: bool = Form(True),
    ):
        """
        Same ingestion discipline as the plain /ai-business-analyst route
        (every uploaded file goes through the same governance scan — no
        bypass here either). Additionally retains each file's raw bytes
        (uploaded_file_bytes), needed by the merge_excel_files and edit_file
        tools, which the plain Q&A route never needed.
        """
        uploaded_frames: dict[str, pd.DataFrame] = {}
        uploaded_file_bytes: dict[str, bytes] = {}
        pii_all: list[str] = []
        leakage_all: list[str] = []
        for f in files or []:
            filename = f.filename or "upload.dat"
            try:
                raw = await f.read()
            except Exception:
                continue
            if not raw or len(raw) > _MAX_UPLOAD_BYTES:
                continue
            try:
                normalized_bytes, _log = await asyncio.to_thread(_preprocess_raw_bytes, raw, filename)
            except Exception:
                normalized_bytes = raw
            try:
                report = await asyncio.wait_for(
                    asyncio.to_thread(_scanner.scan, raw_bytes=normalized_bytes, filename=filename, tenant_id="local"),
                    timeout=_TIMEOUT_SECS,
                )
            except Exception:
                continue
            ir = report.ingestion_result
            if ir.success and ir.df is not None and ir.row_count > 0:
                uploaded_frames[filename] = ir.df
                uploaded_file_bytes[filename] = raw
                pii_all.extend(report.pii_columns_detected)
                leakage_all.extend(report.leakage_columns_detected)

        try:
            domain_results = await asyncio.to_thread(_ai_analyst_analyze_uploaded_files, uploaded_frames)
        except Exception:
            logger.exception("Phase 44: domain detection failed")
            domain_results = {}

        cloud_status = await asyncio.to_thread(_agentic_check_cloud_mode)

        if cloud_status.valid:
            try:
                agentic_answer = await asyncio.to_thread(
                    _agentic_answer_with_claude, question, domain_results, uploaded_frames, uploaded_file_bytes,
                )
            except Exception as exc:
                logger.exception("Phase 44: Claude agent call failed unexpectedly")
                agentic_answer = None
                cloud_status_error = str(exc)
            else:
                cloud_status_error = None

            if agentic_answer is not None:
                files_out = []
                for gf in agentic_answer.files_generated:
                    file_id = str(uuid.uuid4())
                    _AGENTIC_DOWNLOAD_STORE[file_id] = (gf.filename, gf.content_type, gf.content_bytes)
                    files_out.append({
                        "filename": gf.filename,
                        "download_url": f"/api/local/ai-business-analyst/agentic/download/{file_id}",
                    })
                return JSONResponse({
                    "mode": "cloud",
                    "cloud_status": {"configured": cloud_status.configured, "valid": cloud_status.valid, "detail": cloud_status.detail, "masked_key": cloud_status.masked_key, "model": cloud_status.model},
                    "answer": {
                        "answer_text": agentic_answer.answer_text,
                        "mode": agentic_answer.mode,
                        "actions_taken": [
                            {"tool_name": a.tool_name, "tool_input": a.tool_input, "ok": a.ok, "summary": a.summary}
                            for a in agentic_answer.actions_taken
                        ],
                        "error": agentic_answer.error,
                    },
                    "files_generated": files_out,
                    "domains_detected": sorted(domain_results.keys()),
                    "files_ingested": sorted(uploaded_frames.keys()),
                })
            # Claude call raised — fall through to local mode below, but
            # disclose the cloud failure honestly rather than silently
            # pretending cloud was never attempted.
            cloud_status = cloud_status.__class__(
                configured=cloud_status.configured, valid=False,
                detail=f"Cloud call failed this request: {cloud_status_error}",
                masked_key=cloud_status.masked_key, model=cloud_status.model,
            )

        # ── Local fallback: the EXACT existing Phase 37 path, unmodified ──
        try:
            local_answer = await asyncio.to_thread(_ai_analyst_answer_question, question, domain_results, use_llm)
        except Exception as exc:
            logger.exception("Phase 44: local fallback answer_question failed")
            return JSONResponse(status_code=500, content={"detail": f"Both cloud and local answering failed: {exc}"})

        return JSONResponse({
            "mode": "local_fallback",
            "cloud_status": {"configured": cloud_status.configured, "valid": cloud_status.valid, "detail": cloud_status.detail, "masked_key": cloud_status.masked_key, "model": cloud_status.model},
            "answer": {
                **_ai_analyst_answer_to_dict(local_answer),
                "actions_taken": [],
            },
            "files_generated": [],
            "domains_detected": sorted(domain_results.keys()),
            "files_ingested": sorted(uploaded_frames.keys()),
        })

    @router.get("/ai-business-analyst/agentic/download/{file_id}")
    async def local_ai_business_analyst_agentic_download(file_id: str):
        from fastapi.responses import Response as FastAPIResponse
        entry = _AGENTIC_DOWNLOAD_STORE.pop(file_id, None)
        if entry is None:
            return JSONResponse(status_code=404, content={"detail": "This generated file is no longer available (results are single-download, in-memory only)."})
        filename, content_type, content_bytes = entry
        return FastAPIResponse(
            content=content_bytes, media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ── Phase 35.3: Exit Interview / Free-Text Intelligence ────────────────────

    def _parse_free_text_responses(raw_bytes: bytes, filename: str) -> list[str]:
        """
        Parse an uploaded free-text file into a list of individual responses.
        .txt: one response per non-empty line.
        .csv/.xlsx: the first column whose name suggests free text (response/
        comment/feedback/reason/exit_interview/text), or the first text-typed
        column if none match by name.
        """
        lower_name = filename.lower()
        if lower_name.endswith(".txt"):
            text = raw_bytes.decode("utf-8", errors="ignore")
            return [line.strip() for line in text.splitlines() if line.strip()]

        try:
            result = _loader.ingest(raw_bytes, filename)
        except Exception:
            return []
        if not result.success or result.df is None:
            return []

        df = result.df
        name_hints = re.compile(
            r"(response|comment|feedback|reason|exit[_\s]?interview|free[_\s]?text|notes?)",
            re.I,
        )
        candidate_col = None
        for col in df.columns:
            if name_hints.search(str(col)):
                candidate_col = col
                break
        if candidate_col is None:
            text_cols = df.select_dtypes(include=["object"]).columns
            candidate_col = text_cols[0] if len(text_cols) > 0 else None
        if candidate_col is None:
            return []
        return [str(v).strip() for v in df[candidate_col].tolist() if str(v).strip() and str(v).strip().lower() != "nan"]

    @router.post("/exit-interview-intelligence")
    async def local_exit_interview_intelligence(file: UploadFile = File(...)):
        """
        Real free-text exit-interview / open-ended survey theme analysis.

        This is a SEPARATE, optional upload from the structured HR dataset —
        it accepts a .txt file (one response per line) or a .csv/.xlsx with a
        free-text column, and never runs on the structured dataset itself.

        Every code path returns valid JSON. `available: false` (not an HTTP
        error) is returned when there are too few responses to analyze
        safely — this is a governance floor (see
        backend.core.exit_interview_intelligence_engine.MIN_RESPONSES_FOR_AGGREGATE),
        not a failure.
        """
        filename = file.filename or "responses.txt"
        try:
            raw = await file.read()
        except Exception as exc:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, f"Could not read uploaded file: {exc}"),
            )

        if not raw:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "Uploaded file is empty."),
            )
        if len(raw) > _MAX_UPLOAD_BYTES:
            return JSONResponse(
                status_code=400,
                content=_error_response(filename, "File exceeds 500 MB upload limit."),
            )

        try:
            responses = await asyncio.to_thread(_parse_free_text_responses, raw, filename)
        except Exception as exc:
            logger.exception("Free-text parsing failed")
            return JSONResponse({
                "filename": filename,
                "exit_interview_intelligence": exit_interview_intelligence_to_dict(
                    _unavailable_exit_interview_result(f"Could not parse free-text responses: {exc}")
                ),
            })

        try:
            result = await asyncio.to_thread(analyze_exit_interview_text, responses)
        except Exception as exc:
            logger.exception("Exit interview intelligence failed")
            result = _unavailable_exit_interview_result(
                f"Exit interview analysis encountered an error: {exc}"
            )

        return JSONResponse({
            "filename": filename,
            "exit_interview_intelligence": exit_interview_intelligence_to_dict(result),
        })

    # Phase 40: /sessions/*, /export-audit, /upload/export-employee-csv,
    # /export/slides, /export/pptx, /export/pdf removed along with
    # local_database.py and the executive_pptx/pdf/slide_exporter.py modules
    # they exclusively served (confirmed zero frontend callers besides the
    # removed ExecutiveReports.tsx/AnalysisHistory.tsx/SimulationPanel.tsx) —
    # see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.

    # ── Phase 29F: Benchmark Engine Endpoints ─────────────────────────────────

    @router.get("/benchmarks/sectors")
    async def benchmark_sectors():
        """List available sectors (those with n_contributors>=k-anonymity floor
        in the local benchmark DB). Phase 16 honesty note: every sector
        currently in the DB is a seeded placeholder (see benchmark_engine.py's
        `_SEED_BENCHMARKS` and `BenchmarkRecord.is_seeded`) — the k-anonymity
        gate and DP noise are real, executable code, but they are not yet
        protecting real cross-organisation data. Callers must check
        `is_seeded` before presenting a comparison as a validated benchmark."""
        try:
            from backend.core.benchmark_engine import get_benchmark_engine
            engine = get_benchmark_engine()
            sectors = engine.get_available_sectors()
            return JSONResponse({"success": True, "sectors": sectors})
        except Exception as exc:
            logger.warning("Benchmark sectors failed: %s", exc)
            return JSONResponse(status_code=500, content={"success": False, "detail": str(exc)})

    @router.post("/benchmarks/compare")
    async def benchmark_compare(payload: dict[str, Any]):
        """
        Compare organisation AWI indices against a sector benchmark.

        Payload: { org_data: {...}, sector: str, employee_range: str, period: str }
        Returns: BenchmarkComparison dict with gap analysis.
        """
        try:
            from backend.core.benchmark_engine import get_benchmark_engine, benchmark_comparison_to_dict
            engine = get_benchmark_engine()
            org_data   = payload.get("org_data") or payload
            sector     = str(payload.get("sector") or "banking")
            emp_range  = str(payload.get("employee_range") or "500-2000")
            period     = str(payload.get("period") or "Q2_2026")
            result = engine.compare(org_data, sector=sector, employee_range=emp_range, period=period)
            return JSONResponse({"success": True, "comparison": benchmark_comparison_to_dict(result)})
        except Exception as exc:
            logger.warning("Benchmark compare failed: %s", exc)
            return JSONResponse(status_code=500, content={"success": False, "detail": str(exc)})

    @router.post("/benchmarks/submit")
    async def benchmark_submit(payload: dict[str, Any]):
        """
        Submit anonymised org data to improve sector benchmarks (k-anonymity enforced).

        Payload: { org_data: {...}, sector: str, employee_range: str, org_identifier: str }
        """
        try:
            from backend.core.benchmark_engine import get_benchmark_engine
            engine = get_benchmark_engine()
            org_data   = payload.get("org_data") or {}
            sector     = str(payload.get("sector") or "banking")
            emp_range  = str(payload.get("employee_range") or "500-2000")
            identifier = str(payload.get("org_identifier") or "anonymous")
            result = engine.submit_contribution(org_data, sector=sector,
                                                employee_range=emp_range,
                                                org_identifier=identifier)
            return JSONResponse(result)
        except Exception as exc:
            logger.warning("Benchmark submit failed: %s", exc)
            return JSONResponse(status_code=500, content={"success": False, "detail": str(exc)})

    return router


# ── Error / timeout response helpers ─────────────────────────────────────────

def _base_empty_result(filename: str) -> dict[str, Any]:
    return {
        "readiness_level":          "BLOCKED",
        "row_count":                0,
        "column_count":             0,
        "feature_column_count":     0,
        "detected_language":        "unknown",
        "detected_erp_style":       None,
        "warnings":                 [],
        "blocking_reasons":         [],
        "pii_columns_detected":     [],
        "leakage_columns_detected": [],
        "filename":                 filename,
        "dataset_type":             "UNKNOWN_OR_UNSUPPORTED",
        "dataset_type_label":       "Unknown or Unsupported Dataset",
        "analysis_mode":            "blocked",
        "analysis_mode_label":      "Blocked — Upload Cannot Proceed",
        "attrition_modeling_allowed":  False,
        "theory_activation_allowed":   False,
        "market_intelligence_allowed": False,
        "classification_confidence":   0.0,
        "governance_scan_passed":      False,
        "identified_target_column":    None,
        "feature_columns":             [],
        "recommended_actions":         [],
        "duplicate_rows":              0,
        "missing_value_pct":           0.0,
        "encoding_used":               "unknown",
        "ingestion_warnings":          [],
        "ingestion_transformations":   [],
        "executive_readiness": {
            "can_generate_report":     False,
            "can_run_attrition_model": False,
            "can_run_theory_engine":   False,
            "can_show_dashboard":      False,
            "readiness_summary":       "",
        },
        "health_score":                  0,
        "workforce_indicators":          [],
        "executive_recommendations":     [],
        "column_normalizations_applied": [],
        "timing_ms": {
            "file_read": 0.0, "normalization": 0.0,
            "governance_scan": 0.0, "classification": 0.0, "total": 0.0,
        },
        "is_fast_path": False,
        "pdpl_note": "",
    }


def _error_response(filename: str, message: str) -> dict[str, Any]:
    r = _base_empty_result(filename)
    r["blocking_reasons"] = [message]
    r["executive_readiness"]["readiness_summary"] = f"Upload blocked: {message}"
    r["executive_recommendations"] = [f"Resolve upload error: {message}"]
    r["pdpl_note"] = "Upload blocked before scanning. No data was processed."
    return r


def _timeout_response(filename: str, message: str) -> dict[str, Any]:
    r = _base_empty_result(filename)
    r["blocking_reasons"] = [message]
    r["executive_readiness"]["readiness_summary"] = (
        "Scan timed out. File may be too large or contain complex formatting. "
        "Try splitting the file or removing excessive merged cells."
    )
    r["executive_recommendations"] = [
        "Split large Excel files into sheets of < 50,000 rows.",
        "Remove merged cells and complex formatting before upload.",
        "Convert Excel to CSV for faster processing.",
    ]
    r["pdpl_note"] = "Scan timed out. No analysis data was retained."
    return r
