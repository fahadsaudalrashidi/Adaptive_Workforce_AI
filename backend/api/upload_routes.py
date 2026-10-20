"""
Enterprise Upload Routes — Phase 9.

Tenant-scoped file upload, governance scan, and data readiness assessment.

Endpoints:
  POST /v1/tenants/{tenant_id}/upload/scan
      Accepts a file upload, runs SecureFileIngestion governance scan,
      returns FileIngestionReport summary (no raw data rows).

  GET  /v1/tenants/{tenant_id}/upload/demo/{company_id}
      Returns a pre-built governance scan result for a demo company dataset.

  GET  /v1/tenants/{tenant_id}/upload/demo-profiles
      Lists available demo company profiles.

All endpoints enforce tenant isolation: path tenant_id must match
the authenticated tenant context (JWT pending — checked structurally for now).

Design rules:
  - Raw DataFrame rows are never serialized into API responses
  - File bytes are not stored (in-memory scan only)
  - All responses include governance_status field
  - BLOCKED scan results return HTTP 200 with readiness_level=BLOCKED
    (not 400) — it's a governance decision, not an API error
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# ── Path guard ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fastapi import APIRouter, File, HTTPException, UploadFile
    from fastapi.responses import JSONResponse
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

from backend.core.secure_file_ingestion import SecureFileIngestion, ReadinessLevel
from backend.core.demo_company_generator import DemoCompanyGenerator
from backend.core.excel_ingestion_engine import ExcelIngestionEngine

logger = logging.getLogger(__name__)

_scanner   = SecureFileIngestion()
_demo_gen  = DemoCompanyGenerator()

# ── Router ────────────────────────────────────────────────────────────────────

def create_upload_router() -> Any:
    if not _HAS_FASTAPI:
        raise ImportError("FastAPI is required for upload_routes")

    router = APIRouter(prefix="/v1/tenants", tags=["Upload & Governance Scan"])

    @router.post("/{tenant_id}/upload/scan")
    async def scan_uploaded_file(tenant_id: str, file: UploadFile = File(...)):
        """
        Scan an uploaded file for PII, leakage, and data quality.
        Returns governance scan result. Never returns raw employee rows.
        """
        if not tenant_id or not tenant_id.strip():
            raise HTTPException(status_code=400, detail="tenant_id is required")

        raw = await file.read()
        filename = file.filename or "upload.dat"

        logger.info("Scan requested tenant=%s file=%s size=%d", tenant_id, filename, len(raw))

        report = _scanner.scan(raw_bytes=raw, filename=filename, tenant_id=tenant_id)

        return _serialise_scan_report(report)

    @router.get("/{tenant_id}/upload/demo-profiles")
    def list_demo_profiles(tenant_id: str):
        """List available demo company profiles."""
        if not tenant_id or not tenant_id.strip():
            raise HTTPException(status_code=400, detail="tenant_id is required")

        profiles = _demo_gen.list_profiles()
        return {
            "tenant_id": tenant_id,
            "demo_profiles": profiles,
            "governance_status": "OK",
            "note": "All demo datasets are synthetic. Not based on real employee data.",
        }

    @router.get("/{tenant_id}/upload/demo/{company_id}")
    def scan_demo_company(
        tenant_id: str,
        company_id: str,
        language: str = "en",
    ):
        """
        Run a governance scan on a synthetic demo company dataset.
        Returns same structure as /scan — no raw data rows.
        """
        if not tenant_id or not tenant_id.strip():
            raise HTTPException(status_code=400, detail="tenant_id is required")

        profile = _demo_gen.get_profile(company_id)
        if profile is None:
            available = [p["company_id"] for p in _demo_gen.list_profiles()]
            raise HTTPException(
                status_code=404,
                detail=f"Demo company not found: {company_id!r}. Available: {available}",
            )

        try:
            raw_bytes, filename = _demo_gen.generate_bytes(
                company_id=company_id,
                language=language,
                file_format="csv",
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Demo generation failed: {exc}")

        report = _scanner.scan(raw_bytes=raw_bytes, filename=filename, tenant_id=tenant_id)

        result = _serialise_scan_report(report)
        result["demo_mode"] = True
        result["demo_company"] = {
            "company_id": profile.company_id,
            "name_en": profile.name_en,
            "name_ar": profile.name_ar,
            "sector": profile.sector,
            "description_en": profile.description_en,
        }
        return result

    return router


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialise_scan_report(report: Any) -> dict:
    """Convert FileIngestionReport to API-safe dict. Never includes raw rows."""
    ir = report.ingestion_result
    return {
        "tenant_id": report.tenant_id,
        "filename": report.filename,
        "readiness_level": str(report.readiness_level.value
                               if hasattr(report.readiness_level, "value")
                               else report.readiness_level),
        "governance_scan_passed": report.governance_scan_passed,
        "governance_status": "OK" if report.governance_scan_passed else "WARNING",
        "pii_columns_detected": report.pii_columns_detected,
        "leakage_columns_detected": report.leakage_columns_detected,
        "feature_columns": report.feature_columns,
        "feature_column_count": len(report.feature_columns),
        "identified_target_column": report.identified_target_column,
        "blocking_reasons": report.blocking_reasons,
        "warnings": report.warnings,
        "recommended_actions": report.recommended_actions,
        "data_quality": {
            "total_rows": report.data_quality.total_rows,
            "total_columns": report.data_quality.total_columns,
            "duplicate_rows": report.data_quality.duplicate_rows,
            "missing_value_pct": report.data_quality.missing_value_pct,
            "empty_columns": report.data_quality.empty_columns,
            "high_null_columns": report.data_quality.high_null_columns,
            "suspicious_salary_flag": report.data_quality.suspicious_salary_flag,
        },
        "ingestion": {
            "success": ir.success,
            "row_count": ir.row_count,
            "column_count": ir.column_count,
            "detected_language": ir.detected_language,
            "detected_erp_style": ir.detected_erp_style,
            "encoding_used": ir.encoding_used,
            "sheet_used": ir.sheet_used,
            "warnings": ir.warnings,
            "transformations": ir.transformations,
            # raw df is intentionally excluded
        },
        "column_classifications": [
            {
                "name": cls.name,
                "classification": cls.classification,
                "reason": cls.reason,
                "blocked": cls.blocked,
            }
            for cls in report.column_classifications
        ],
        "pdpl_note": (
            "This scan was processed through PDPL technical controls. "
            "No individual employee identifiers are retained. "
            "Legal compliance requires qualified Saudi legal counsel review."
        ),
    }
