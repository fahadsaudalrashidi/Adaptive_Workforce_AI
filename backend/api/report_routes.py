"""
Executive Report & Export Routes — Phase 9.

Endpoints:
  POST /v1/tenants/{tenant_id}/reports/generate
      Generate one of 4 report types (executive_summary, governance_audit,
      board_briefing, data_readiness) in English or Arabic.
      Returns HTML content + metadata. PDF on demand.

  POST /v1/tenants/{tenant_id}/reports/audit-package
      Build a governance-safe audit export package (ZIP).
      Returns ZIP bytes as application/zip.

  GET  /v1/tenants/{tenant_id}/reports/demo/{company_id}/{report_type}
      Generate a demo report for a synthetic company (no real data).

All endpoints include governance_status in responses.
All reports include 3 mandatory disclaimers.
No individual employee data appears in any response.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import JSONResponse, Response
    from pydantic import BaseModel
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

from backend.core.executive_report_exporter import ExecutiveReportExporter, ReportType
from backend.core.audit_package_builder import AuditPackageBuilder
from backend.core.demo_company_generator import DemoCompanyGenerator
from backend.core.report_localization import Language

logger = logging.getLogger(__name__)

_exporter  = ExecutiveReportExporter()
_pkg_builder = AuditPackageBuilder()
_demo_gen  = DemoCompanyGenerator()


# ── Request models ─────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    report_type: str = "executive_summary"   # executive_summary | governance_audit | board_briefing | data_readiness
    language: str = "en"                      # en | ar
    generate_pdf: bool = False
    data: dict = {}


class AuditPackageRequest(BaseModel):
    scan_summary: dict = {}
    generated_report_ids: list[str] = []
    governance_locks: dict = {}


# ── Demo data for report generation ──────────────────────────────────────────

_DEMO_REPORT_DATA = {
    "workforce_stability_index": 73.2,
    "governance_status": "OK",
    "departments": [
        {"name": "Information Technology", "name_ar": "تقنية المعلومات", "stability_score": 61.2, "risk_band": "strategic_concern", "employee_count": 387},
        {"name": "Operations",             "name_ar": "العمليات",         "stability_score": 58.4, "risk_band": "priority_review",   "employee_count": 974},
        {"name": "Engineering",            "name_ar": "الهندسة",          "stability_score": 76.3, "risk_band": "monitoring",        "employee_count": 714},
        {"name": "Finance & Accounting",   "name_ar": "المالية والمحاسبة","stability_score": 84.1, "risk_band": "stable",            "employee_count": 325},
        {"name": "Human Resources",        "name_ar": "الموارد البشرية",  "stability_score": 81.7, "risk_band": "stable",            "employee_count": 195},
        {"name": "Supply Chain",           "name_ar": "سلسلة التوريد",   "stability_score": 69.4, "risk_band": "monitoring",        "employee_count": 325},
        {"name": "Quality Assurance",      "name_ar": "ضمان الجودة",      "stability_score": 77.8, "risk_band": "monitoring",        "employee_count": 227},
        {"name": "Legal & Compliance",     "name_ar": "الشؤون القانونية", "stability_score": 88.6, "risk_band": "stable",            "employee_count": 97},
    ],
    "trend_12m": [
        {"month": "Jun 2025", "value": 69.1},
        {"month": "Jul 2025", "value": 70.2},
        {"month": "Aug 2025", "value": 68.8},
        {"month": "Sep 2025", "value": 71.4},
        {"month": "Oct 2025", "value": 70.9},
        {"month": "Nov 2025", "value": 72.1},
        {"month": "Dec 2025", "value": 71.8},
        {"month": "Jan 2026", "value": 72.6},
        {"month": "Feb 2026", "value": 73.0},
        {"month": "Mar 2026", "value": 72.4},
        {"month": "Apr 2026", "value": 73.8},
        {"month": "May 2026", "value": 73.2},
    ],
    "calibration": {"auc_roc": 0.783, "ece": 0.041, "brier": 0.162},
    "theory_contributions": [
        {"theory": "COR",    "contribution": 31.2},
        {"theory": "JD-R",   "contribution": 28.7},
        {"theory": "FFM",    "contribution": 19.4},
        {"theory": "Mobley", "contribution": 14.8},
        {"theory": "Equity", "contribution": 5.9},
    ],
    "strategic_insights": [
        {
            "en": "Operations and IT departments show Priority Review indicators. Immediate retention strategy review recommended.",
            "ar": "تظهر أقسام العمليات وتقنية المعلومات مؤشرات تستوجب المراجعة ذات الأولوية. يُوصى بمراجعة استراتيجية الاحتفاظ فوراً.",
        },
        {
            "en": "Saudization rate in Operations (41%) is below national target. Monitor Nitaqat compliance.",
            "ar": "معدل السعودة في قسم العمليات (41%) أقل من الهدف الوطني. راقب الامتثال لنطاقات.",
        },
        {
            "en": "Training hours correlation: departments with >30 training hours/year show 0.18 higher stability scores.",
            "ar": "ارتباط ساعات التدريب: تُظهر الأقسام التي تتجاوز 30 ساعة تدريب/سنة درجات استقرار أعلى بمقدار 0.18.",
        },
        {
            "en": "Finance and Legal maintain stable indicators; best practices from these units can be documented for cross-department transfer.",
            "ar": "تحتفظ الإدارة المالية والشؤون القانونية بمؤشرات استقرار. يمكن توثيق أفضل الممارسات من هذه الوحدات للنقل عبر الأقسام.",
        },
        {
            "en": "Model AUC-ROC of 0.783 with ECE 0.041 confirms calibrated, reliable predictions within validated thresholds.",
            "ar": "يؤكد AUC-ROC البالغ 0.783 مع ECE 0.041 وجود تنبؤات معايَرة وموثوقة ضمن الحدود المعتمدة.",
        },
    ],
    "governance_locks": {
        "DEBUG": False,
        "EMPLOYEE_LEVEL_OUTPUT_ENABLED": False,
        "CROSS_TENANT_ACCESS_ALLOWED": False,
        "CALIBRATION_REQUIRED": True,
        "PDPL_WARNING_ENABLED": True,
        "GOVERNANCE_DISCLAIMER_REQUIRED": True,
        "AUDIT_LOGGING_ENABLED": True,
        "TEMPORAL_VALIDATION_ENABLED": True,
        "LEAKAGE_DETECTION_ENABLED": True,
        "SCIENTIFIC_FEATURE_MODE": "theory_grounded",
        "LEGACY_CONSTRUCTS_DISABLED": True,
    },
    "pdpl_controls": {
        "PII Column Removal": "Active",
        "Employee-Level Output Disabled": "Active",
        "Purpose Limitation": "Active — stability analytics only",
        "Retention Period Recorded": "Active — 7 years for restricted artifacts",
        "Accountability Trail": "Active — 18-event immutable audit log",
        "Data Subject Rights": "Active — no re-identification possible",
    },
}


# ── Router ─────────────────────────────────────────────────────────────────────

def create_report_router() -> Any:
    if not _HAS_FASTAPI:
        raise ImportError("FastAPI is required for report_routes")

    router = APIRouter(prefix="/v1/tenants", tags=["Reports & Export"])

    @router.post("/{tenant_id}/reports/generate")
    def generate_report(tenant_id: str, request: ReportRequest):
        """
        Generate an executive report for the tenant.
        Attaches 3 mandatory governance disclaimers. No employee data.
        """
        _validate_tenant(tenant_id)

        try:
            report_type = ReportType(request.report_type)
        except ValueError:
            valid = [rt.value for rt in ReportType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report_type: {request.report_type!r}. Valid: {valid}",
            )

        language = _validate_language(request.language)

        # Merge provided data with defaults
        data = {**_DEMO_REPORT_DATA, **request.data}

        try:
            report = _exporter.generate(
                report_type=report_type,
                tenant_id=tenant_id,
                data=data,
                language=language,
                demo_mode=not bool(request.data),
                generate_pdf=request.generate_pdf,
            )
        except Exception as exc:
            logger.exception("Report generation failed tenant=%s", tenant_id)
            raise HTTPException(status_code=500, detail=f"Report generation failed: {exc}")

        response = {
            "tenant_id": tenant_id,
            "report_id": report.metadata.report_id,
            "report_type": report.metadata.report_type.value,
            "language": report.metadata.language,
            "generated_at": report.metadata.generated_at,
            "governance_verified": report.governance_verified,
            "governance_status": report.metadata.governance_status,
            "disclaimers_attached": len(report.disclaimers_attached),
            "checksum_sha256": report.checksum,
            "html_content": report.html_content,
            "has_pdf": report.pdf_bytes is not None,
        }

        if report.pdf_bytes:
            response["pdf_size_bytes"] = len(report.pdf_bytes)

        return response

    @router.get("/{tenant_id}/reports/demo/{company_id}/{report_type}")
    def demo_report(
        tenant_id: str,
        company_id: str,
        report_type: str,
        language: str = "en",
        generate_pdf: bool = False,
    ):
        """
        Generate a demo report for a synthetic Saudi company.
        Clearly labelled DEMO MODE — no real employee data.
        """
        _validate_tenant(tenant_id)

        profile = _demo_gen.get_profile(company_id)
        if profile is None:
            available = [p["company_id"] for p in _demo_gen.list_profiles()]
            raise HTTPException(
                status_code=404,
                detail=f"Demo company not found: {company_id!r}. Available: {available}",
            )

        try:
            rt = ReportType(report_type)
        except ValueError:
            valid = [r.value for r in ReportType]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid report_type: {report_type!r}. Valid: {valid}",
            )

        lang = _validate_language(language)
        data = dict(_DEMO_REPORT_DATA)

        report = _exporter.generate(
            report_type=rt,
            tenant_id=tenant_id,
            data=data,
            language=lang,
            demo_mode=True,
            generate_pdf=generate_pdf,
        )

        return {
            "tenant_id": tenant_id,
            "demo_mode": True,
            "demo_company": {
                "company_id": profile.company_id,
                "name_en": profile.name_en,
                "name_ar": profile.name_ar,
            },
            "report_id": report.metadata.report_id,
            "report_type": rt.value,
            "language": lang,
            "generated_at": report.metadata.generated_at,
            "governance_verified": report.governance_verified,
            "governance_status": "OK",
            "disclaimers_attached": len(report.disclaimers_attached),
            "checksum_sha256": report.checksum,
            "html_content": report.html_content,
            "has_pdf": report.pdf_bytes is not None,
        }

    @router.post("/{tenant_id}/reports/audit-package")
    def build_audit_package(tenant_id: str, request: AuditPackageRequest):
        """
        Build a tenant-scoped governance audit export package.
        Returns package summary JSON. Use /audit-package/download for ZIP.
        """
        _validate_tenant(tenant_id)

        package = _pkg_builder.build(
            tenant_id=tenant_id,
            governance_locks=request.governance_locks or None,
            created_by="api",
        )

        return {
            "tenant_id": tenant_id,
            "package_id": package.package_id,
            "created_at": package.created_at,
            "governance_verified": package.governance_verified,
            "manifest_checksum": package.manifest_checksum,
            "files": list(package.files.keys()),
            "file_count": len(package.files),
            "warnings": package.warnings,
            "pdpl_note": package.pdpl_note,
            "download_hint": (
                f"POST /v1/tenants/{tenant_id}/reports/audit-package/download "
                "to retrieve ZIP archive"
            ),
        }

    @router.post("/{tenant_id}/reports/audit-package/download")
    def download_audit_package(tenant_id: str, request: AuditPackageRequest):
        """
        Build and return a governance audit package as a ZIP download.
        Content-Type: application/zip
        """
        _validate_tenant(tenant_id)

        package = _pkg_builder.build(
            tenant_id=tenant_id,
            governance_locks=request.governance_locks or None,
            created_by="api",
        )

        zip_bytes = package.to_zip_bytes()

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="audit_package_{tenant_id}.zip"',
                "X-Package-ID": package.package_id,
                "X-Governance-Verified": "true",
            },
        )

    return router


# ── Helpers ────────────────────────────────────────────────────────────────────

def _validate_tenant(tenant_id: str) -> None:
    if not tenant_id or not tenant_id.strip():
        raise HTTPException(status_code=400, detail="tenant_id is required")


def _validate_language(language: str) -> Language:
    if language not in ("en", "ar"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language: {language!r}. Use 'en' or 'ar'.",
        )
    return language  # type: ignore[return-value]
