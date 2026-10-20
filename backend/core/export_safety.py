"""
Export Safety Validator — Phase 7.

Before any data leaves the platform (report, CSV export, API response,
dashboard display), it must pass through this validator. The validator:

  1. Removes employee IDs and individual PII fields from dict payloads
  2. Removes deterministic language from text fields (via EnterpriseLanguageGuard)
  3. Attaches a mandatory governance disclaimer
  4. Attaches a confidence/uncertainty warning
  5. Attaches a PDPL review note for exports containing HR risk data
  6. Returns an ExportSafetyReport describing all actions taken

This is the final output gate — it runs AFTER all governance modules
and BEFORE any data is returned to an external caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.core.enterprise_language_guard import EnterpriseLanguageGuard

# ── PII field names to strip from dict payloads ────────────────────────────

_PII_FIELD_PATTERNS = [
    # English patterns
    "national_id", "nationalid", "national id",
    "iqama", "iqama_number", "residency_number",
    "iban", "bank_account", "account_number",
    "phone", "mobile", "telephone", "contact_number",
    "email", "personal_email",
    "address", "home_address", "street", "postal_code",
    "passport", "passport_number",
    "gosi", "gosi_number",
    "gps", "latitude", "longitude", "location",
    "date_of_birth", "dob", "birth_date",
    # Arabic forms
    "رقم_الهوية", "رقم_الإقامة", "رقم_الآيبان", "رقم_الجوال",
    "البريد_الإلكتروني", "العنوان", "رقم_جواز_السفر",
]

# ── Employee-level output field names to strip by default ─────────────────

_EMPLOYEE_LEVEL_FIELDS = [
    "employee_number", "employeenumber", "employee_id", "employeeid",
    "emp_id", "emp_number", "staff_id", "worker_id",
    "y_prob", "y_pred", "individual_risk_score", "risk_score",
    "predicted_probability", "attrition_probability",
]

_EMPLOYEE_LEVEL_FIELDS_SET = frozenset(_EMPLOYEE_LEVEL_FIELDS)

# ── Mandatory disclaimers ─────────────────────────────────────────────────

_GOVERNANCE_DISCLAIMER = (
    "GOVERNANCE DISCLAIMER: This output is produced by an AI-assisted workforce "
    "analytics system. Risk indicators are probabilistic and do not represent "
    "determinations of individual employee intent or behavior. All HR decisions "
    "based on this output require qualified HR professional review."
)

_CONFIDENCE_WARNING = (
    "CONFIDENCE WARNING: Model predictions carry inherent uncertainty. "
    "Risk scores should be interpreted as statistical patterns in organizational "
    "data, not as predictions about specific individuals. The confidence intervals "
    "for individual-level predictions are wide and should not be used in isolation."
)

_PDPL_NOTE = (
    "PDPL REVIEW NOTE: This export may contain data relating to employees in "
    "Saudi Arabia. The Saudi Personal Data Protection Law (PDPL, Royal Decree M/19) "
    "applies to this data. Ensure that your Data Processing Agreement covers this "
    "export use case and that appropriate data subject notification has been provided. "
    "This note does not constitute legal advice or PDPL compliance certification."
)


@dataclass
class ExportSafetyReport:
    """
    Records the actions taken by the export safety validator.

    A report with is_safe=False means the export was blocked or
    could not be safely sanitized. is_safe=True means the sanitized
    output is cleared for export with the attached disclaimers.
    """
    is_safe: bool
    pii_fields_removed: list[str] = field(default_factory=list)
    employee_level_fields_removed: list[str] = field(default_factory=list)
    language_violations_corrected: int = 0
    disclaimer_attached: bool = False
    confidence_warning_attached: bool = False
    pdpl_note_attached: bool = False
    governance_status: str = "OK"
    blocking_reason: Optional[str] = None
    actions_taken: list[str] = field(default_factory=list)


@dataclass
class SafeExportPackage:
    """
    The sanitized output payload, ready for export.

    Contains the cleaned data, mandatory disclaimers, and the safety report.
    """
    data: Any                           # sanitized payload (dict, str, list, etc.)
    governance_disclaimer: str
    confidence_warning: str
    pdpl_note: str
    safety_report: ExportSafetyReport
    tenant_id: str
    export_type: str


class ExportSafetyValidator:
    """
    Stateless export safety validator.

    Run before any API response, report export, or dashboard render
    that sends HR analytics data to an external caller.
    """

    def __init__(self) -> None:
        self._guard = EnterpriseLanguageGuard()

    def validate_and_sanitize(
        self,
        data: Any,
        tenant_id: str,
        export_type: str = "report",
        attach_pdpl_note: bool = True,
        strip_employee_level: bool = True,
    ) -> SafeExportPackage:
        """
        Validate and sanitize an export payload.

        Parameters
        ----------
        data : Any
            The payload to sanitize. Supports dict, str, list[dict], list[str].
        tenant_id : str
            Owning tenant (included in the export package for traceability).
        export_type : str
            Descriptive label for the export (e.g., "executive_report", "roi_estimate").
        attach_pdpl_note : bool
            If True, attaches the PDPL review note to the export package.
        strip_employee_level : bool
            If True, strips employee-level output fields (y_prob, risk_score, etc.).
        """
        pii_removed: list[str] = []
        emp_removed: list[str] = []
        lang_corrections = 0
        actions: list[str] = []

        # ── Sanitize the payload ────────────────────────────────────────────
        if isinstance(data, dict):
            sanitized, pii_removed, emp_removed = self._sanitize_dict(
                data, strip_employee_level
            )
        elif isinstance(data, str):
            sanitized, lang_corrections = self._sanitize_text(data)
        elif isinstance(data, list):
            sanitized = []
            for item in data:
                if isinstance(item, dict):
                    clean, p, e = self._sanitize_dict(item, strip_employee_level)
                    pii_removed.extend(p)
                    emp_removed.extend(e)
                    sanitized.append(clean)
                elif isinstance(item, str):
                    clean, lc = self._sanitize_text(item)
                    lang_corrections += lc
                    sanitized.append(clean)
                else:
                    sanitized.append(item)
        else:
            sanitized = data

        # ── Build action log ────────────────────────────────────────────────
        if pii_removed:
            actions.append(
                f"Removed {len(pii_removed)} PII field(s): {', '.join(pii_removed[:5])}"
            )
        if emp_removed:
            actions.append(
                f"Removed {len(emp_removed)} employee-level output field(s): "
                + ", ".join(emp_removed[:5])
            )
        if lang_corrections > 0:
            actions.append(f"Corrected {lang_corrections} language violation(s) via EnterpriseLanguageGuard.")

        actions.append("Governance disclaimer attached.")
        actions.append("Confidence warning attached.")
        if attach_pdpl_note:
            actions.append("PDPL review note attached.")

        safety_report = ExportSafetyReport(
            is_safe=True,
            pii_fields_removed=list(set(pii_removed)),
            employee_level_fields_removed=list(set(emp_removed)),
            language_violations_corrected=lang_corrections,
            disclaimer_attached=True,
            confidence_warning_attached=True,
            pdpl_note_attached=attach_pdpl_note,
            governance_status="OK" if not pii_removed else "WARNING",
            actions_taken=actions,
        )

        return SafeExportPackage(
            data=sanitized,
            governance_disclaimer=_GOVERNANCE_DISCLAIMER,
            confidence_warning=_CONFIDENCE_WARNING,
            pdpl_note=_PDPL_NOTE if attach_pdpl_note else "",
            safety_report=safety_report,
            tenant_id=tenant_id,
            export_type=export_type,
        )

    def is_safe_for_export(self, data: Any) -> bool:
        """
        Quick check: returns True if data appears free of PII and
        deterministic language. Does not mutate data.
        """
        if isinstance(data, dict):
            for key in data:
                if self._is_pii_field(key):
                    return False
            for value in data.values():
                if isinstance(value, str):
                    audit = self._guard.audit(value)
                    if not audit.is_compliant:
                        return False
        elif isinstance(data, str):
            audit = self._guard.audit(data)
            return audit.is_compliant
        return True

    # ── Private helpers ─────────────────────────────────────────────────────

    def _sanitize_dict(
        self, data: dict, strip_employee_level: bool
    ) -> tuple[dict, list[str], list[str]]:
        pii_removed: list[str] = []
        emp_removed: list[str] = []
        clean: dict = {}

        for key, value in data.items():
            key_lower = key.lower().replace(" ", "_")

            if self._is_pii_field(key_lower):
                pii_removed.append(key)
                continue

            if strip_employee_level and self._is_employee_level_field(key_lower):
                emp_removed.append(key)
                continue

            if isinstance(value, str):
                audit = self._guard.audit(value)
                clean[key] = audit.safe_text if not audit.is_compliant else value
            elif isinstance(value, dict):
                sub, sub_pii, sub_emp = self._sanitize_dict(value, strip_employee_level)
                pii_removed.extend(sub_pii)
                emp_removed.extend(sub_emp)
                clean[key] = sub
            elif isinstance(value, list):
                clean_list = []
                for item in value:
                    if isinstance(item, dict):
                        sub, sub_pii, sub_emp = self._sanitize_dict(item, strip_employee_level)
                        pii_removed.extend(sub_pii)
                        emp_removed.extend(sub_emp)
                        clean_list.append(sub)
                    elif isinstance(item, str):
                        audit = self._guard.audit(item)
                        clean_list.append(audit.safe_text if not audit.is_compliant else item)
                    else:
                        clean_list.append(item)
                clean[key] = clean_list
            else:
                clean[key] = value

        return clean, pii_removed, emp_removed

    def _sanitize_text(self, text: str) -> tuple[str, int]:
        audit = self._guard.audit(text)
        corrections = audit.n_critical + audit.n_high + audit.n_medium
        return audit.safe_text, corrections

    def _is_pii_field(self, key_lower: str) -> bool:
        return any(pattern in key_lower for pattern in _PII_FIELD_PATTERNS)

    def _is_employee_level_field(self, key_lower: str) -> bool:
        return key_lower in _EMPLOYEE_LEVEL_FIELDS_SET


# ── Convenience functions ──────────────────────────────────────────────────

def validate_export(
    data: Any,
    tenant_id: str,
    export_type: str = "report",
    attach_pdpl_note: bool = True,
    strip_employee_level: bool = True,
) -> SafeExportPackage:
    """Convenience wrapper for ExportSafetyValidator.validate_and_sanitize()."""
    validator = ExportSafetyValidator()
    return validator.validate_and_sanitize(
        data=data,
        tenant_id=tenant_id,
        export_type=export_type,
        attach_pdpl_note=attach_pdpl_note,
        strip_employee_level=strip_employee_level,
    )
