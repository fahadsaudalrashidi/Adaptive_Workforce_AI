# Export Safety Audit — Phase 7

**Document Type:** Data Governance & Output Safety Audit  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Implementation Complete — 28/28 Tests Passing  
**Module:** `backend/core/export_safety.py`

---

## 1. Purpose

Export safety is the final gate before any data leaves the platform. A report, API response, CSV download, or dashboard display that carries employee-level PII, deterministic risk language, or uncaveated predictions can:

- Violate Saudi PDPL data minimization requirements
- Create legal liability if used to justify HR decisions without appropriate caveats
- Expose the platform to reputational risk if individual employees are identifiable in outputs
- Cause regulatory non-compliance if exports reach territories with stricter data protection laws

The `ExportSafetyValidator` in Phase 7 provides a programmatic gate that runs after all governance modules and before any data is returned to an external caller.

---

## 2. What the Validator Does

The validator applies four sequential operations to every export payload:

1. **PII field removal** — strips fields whose names match known personally-identifiable patterns
2. **Employee-level field removal** — strips individual risk scores and employee identifiers (enabled by default, can be disabled for internal authorized use)
3. **Language violation correction** — passes text through `EnterpriseLanguageGuard` to correct deterministic claims
4. **Disclaimer attachment** — attaches three mandatory disclaimers to every export package

The validator supports three payload types: `dict`, `str`, and `list` (of dicts or strings). Nested dicts are sanitized recursively.

---

## 3. PII Field Patterns

The following field name patterns trigger removal from dict payloads:

**English patterns:**
- `national_id`, `nationalid`, `national id`
- `iqama`, `iqama_number`, `residency_number`
- `iban`, `bank_account`, `account_number`
- `phone`, `mobile`, `telephone`, `contact_number`
- `email`, `personal_email`
- `address`, `home_address`, `street`, `postal_code`
- `passport`, `passport_number`
- `gosi`, `gosi_number`
- `gps`, `latitude`, `longitude`, `location`
- `date_of_birth`, `dob`, `birth_date`

**Arabic patterns:**
- `رقم_الهوية` (national ID)
- `رقم_الإقامة` (residency/Iqama number)
- `رقم_الآيبان` (IBAN)
- `رقم_الجوال` (mobile number)
- `البريد_الإلكتروني` (email)
- `العنوان` (address)
- `رقم_جواز_السفر` (passport number)

Matching uses substring search on the lowercased, space-normalized field name. This means `work_email`, `home_email`, and `personal_email` all match the `email` pattern.

---

## 4. Employee-Level Field Patterns

The following field names are removed when `strip_employee_level=True` (the default):

- `employee_number`, `employeenumber`
- `employee_id`, `employeeid`
- `emp_id`, `emp_number`, `staff_id`, `worker_id`
- `y_prob`, `y_pred`
- `individual_risk_score`
- `risk_score`
- `predicted_probability`, `attrition_probability`

**Critical design note:** Employee-level field matching uses **exact matching** (the field name must equal one of the patterns exactly, after lowercasing and space-normalization). This prevents aggregate fields like `mean_risk_score` from being incorrectly stripped because they contain `risk_score` as a substring.

PII field matching uses **substring matching** because PII field names vary more widely (e.g., `work_email`, `personal_email_address`, `email`).

---

## 5. The Three Mandatory Disclaimers

Every `SafeExportPackage` carries three text fields that must be displayed to any consumer of the exported data:

### 5.1 Governance Disclaimer (`_GOVERNANCE_DISCLAIMER`)

```
GOVERNANCE DISCLAIMER: This output is produced by an AI-assisted workforce 
analytics system. Risk indicators are probabilistic and do not represent 
determinations of individual employee intent or behavior. All HR decisions 
based on this output require qualified HR professional review.
```

Rationale: Prevents outputs from being used as standalone justification for HR actions. CIPD guidance requires that AI-generated risk indicators be reviewed by qualified HR professionals.

### 5.2 Confidence Warning (`_CONFIDENCE_WARNING`)

```
CONFIDENCE WARNING: Model predictions carry inherent uncertainty. 
Risk scores should be interpreted as statistical patterns in organizational 
data, not as predictions about specific individuals. The confidence intervals 
for individual-level predictions are wide and should not be used in isolation.
```

Rationale: Communicates the inherent uncertainty of probabilistic models. Required for honest representation under scientific governance principles.

### 5.3 PDPL Note (`_PDPL_NOTE`)

```
PDPL REVIEW NOTE: This export may contain data relating to employees in 
Saudi Arabia. The Saudi Personal Data Protection Law (PDPL, Royal Decree M/19) 
applies to this data. Ensure that your Data Processing Agreement covers this 
export use case and that appropriate data subject notification has been provided. 
This note does not constitute legal advice or PDPL compliance certification.
```

Rationale: PDPL Article 4 requires that processing of personal data is disclosed to data subjects. The platform cannot guarantee the customer has met this obligation, but attaches a reminder to every export.

The PDPL note can be omitted by passing `attach_pdpl_note=False`. This is available for exports that provably contain no Saudi employee data, but the default is always `True`.

---

## 6. `ExportSafetyReport` — Action Record

Every validation run produces an `ExportSafetyReport` recording:

| Field | Type | Description |
|-------|------|-------------|
| `is_safe` | bool | True if export cleared (after sanitization) |
| `pii_fields_removed` | list[str] | Names of PII fields stripped |
| `employee_level_fields_removed` | list[str] | Names of employee-level fields stripped |
| `language_violations_corrected` | int | Count of language corrections applied |
| `disclaimer_attached` | bool | Always True after validation |
| `confidence_warning_attached` | bool | Always True after validation |
| `pdpl_note_attached` | bool | True unless explicitly disabled |
| `governance_status` | str | "OK" if no PII found, "WARNING" if PII was removed |
| `blocking_reason` | Optional[str] | Reason if export was blocked (future use) |
| `actions_taken` | list[str] | Human-readable log of actions taken |

---

## 7. `SafeExportPackage` — The Output

```python
@dataclass
class SafeExportPackage:
    data: Any                    # Sanitized payload
    governance_disclaimer: str   # Mandatory governance disclaimer text
    confidence_warning: str      # Mandatory confidence warning text
    pdpl_note: str               # PDPL note (empty string if disabled)
    safety_report: ExportSafetyReport
    tenant_id: str               # Owning tenant for traceability
    export_type: str             # Label for the export (e.g., "executive_report")
```

Callers must render `governance_disclaimer`, `confidence_warning`, and `pdpl_note` to end users. They must not be silently discarded.

---

## 8. `is_safe_for_export()` Quick Check

```python
validator.is_safe_for_export(data)  # Returns bool
```

This is a non-mutating check that returns `True` if the data appears free of PII and deterministic language, `False` otherwise. It does not sanitize — it only checks. Use it as a precondition check before expensive processing if needed. The full `validate_and_sanitize()` must still be called before export.

---

## 9. Language Safety Integration

Text payloads (strings and string values within dicts) are passed through `EnterpriseLanguageGuard.audit()`. The guard:

- Detects deterministic claims ("this employee **will** resign")
- Detects categorical certainty ("this employee **is** a flight risk")
- Suggests probabilistic rewrites ("this employee shows **elevated indicators consistent with** attrition risk")
- Returns `audit.safe_text` — the corrected version — for inclusion in the export

The `language_violations_corrected` count in `ExportSafetyReport` reflects the total number of violations corrected across the payload.

---

## 10. Governance Status Semantics

| Status | Meaning |
|--------|---------|
| `"OK"` | No PII found; export is clean |
| `"WARNING"` | PII was found and removed; consumer should verify the source dataset |
| `"BLOCKED"` | Export could not be safely sanitized (reserved for future use) |

A `"WARNING"` status does not mean the export is unsafe to use — the PII was removed. It means the source dataset contained PII fields that reached the export gate, which may indicate that the onboarding pipeline's PII detection should have flagged them earlier. Investigate and remediate at the source.

---

## 11. Test Verification Summary

```
tests/test_phase7_export_safety.py::TestExportSafetyValidatorDict   — 14 tests ✓
tests/test_phase7_export_safety.py::TestExportSafetyValidatorText   — 3 tests  ✓
tests/test_phase7_export_safety.py::TestExportSafetyValidatorList   — 2 tests  ✓
tests/test_phase7_export_safety.py::TestExportSafetyQuickCheck      — 4 tests  ✓
tests/test_phase7_export_safety.py::TestConvenienceFunction         — 5 tests  ✓

Total: 28 tests, 0 failures
```

Key scenarios verified:

| Scenario | Test |
|----------|------|
| Clean dict passes without modification | `test_clean_dict_passes` |
| English PII fields removed | `test_pii_fields_removed_from_dict` |
| Arabic PII fields removed | `test_arabic_pii_fields_removed` |
| Aggregate fields NOT removed | `test_pii_removal_does_not_remove_clean_fields` |
| Employee-level fields removed by default | `test_employee_level_fields_removed_by_default` |
| Employee-level fields kept when disabled | `test_employee_level_fields_kept_when_disabled` |
| Nested PII removed recursively | `test_nested_pii_removed` |
| All three disclaimers attached | `test_governance_disclaimer_attached`, `test_confidence_warning_attached`, `test_pdpl_note_attached_by_default` |
| PDPL note omitted when disabled | `test_pdpl_note_omitted_when_disabled` |
| List of dicts sanitized | `test_list_of_dicts_sanitized` |
| Governance status WARNING on PII | `test_validate_export_governance_status_warning_on_pii` |
| Actions taken log populated | `test_actions_taken_populated` |

---

## 12. Integration Points

The export safety validator must be called:

1. **Before every API response** that returns analytics data
2. **Before every file export** (CSV, PDF, Excel)
3. **Before every dashboard render** that sends data to the frontend
4. **After the full governance pipeline** (onboarding, theory features, calibration, language guard) — not as a substitute for earlier governance

It should NOT be used as a substitute for the onboarding PII scanner. The onboarding scanner removes PII from datasets before they enter the pipeline. The export safety validator removes PII that reached the output stage despite earlier detection. Both layers are required.

---

*The export safety validator is the last line of defence before data leaves the platform. It cannot be bypassed in normal operation. Any code path that returns HR analytics data must pass through `ExportSafetyValidator.validate_and_sanitize()`. Verify this at code review time for every new endpoint.*
