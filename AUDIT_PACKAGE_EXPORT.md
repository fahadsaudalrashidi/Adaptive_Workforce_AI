# Audit Package Export — Phase 9

**Document Type:** Governance & Audit Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** Compliance Teams, External Auditors, Legal Counsel, CIO

---

## Purpose

The Audit Package Export provides a structured, tamper-evident export of governance evidence for a single tenant. It is designed to support:
- Internal compliance reviews
- PDPL audit documentation (PDPL Article 31: Records of Processing)
- External security audits
- Regulatory inquiries

---

## Package Contents

Every audit package is a ZIP archive containing:

| File | Description |
|------|-------------|
| `scan_summary.json` | Governance scan result: readiness level, PII/leakage findings, blocking reasons |
| `ingestion_metadata.json` | File parsing metadata: row count, column headers, transformations (no raw rows) |
| `report_manifest.json` | List of generated reports with SHA-256 checksums and timestamps |
| `governance_snapshot.json` | Production governance lock values at export time |
| `audit_events_excerpt.json` | PII-safe subset of the audit event log |
| `README.txt` | Human-readable package description and legal notices |
| `MANIFEST.json` | Per-file SHA-256 checksums + package manifest checksum |

---

## Package Integrity

### Per-File Checksums

Every file in the package has a SHA-256 checksum recorded in `MANIFEST.json`:
```json
{
  "filename": "scan_summary.json",
  "checksum_sha256": "a3f9...",
  "size_bytes": 1842,
  "created_at": "2026-05-21T10:30:00Z"
}
```

### Manifest Checksum

The manifest itself is SHA-256 hashed to create a package-level integrity seal:
```python
manifest_checksum: str  # SHA-256 of sorted JSON manifest entries
```

Recipients can verify the package has not been tampered with by:
1. Recomputing SHA-256 of each file and comparing to `MANIFEST.json`
2. Recomputing SHA-256 of the manifest and comparing to `package.manifest_checksum`

---

## Privacy Controls

**No raw employee data appears in any file in the package.** Specifically:

### scan_summary.json
Contains: `readiness_level`, `pii_columns_detected`, `feature_columns`, `blocking_reasons`, `warnings`  
Does NOT contain: Any employee rows, values, or individual records

### ingestion_metadata.json
Contains: `row_count`, `column_count`, `original_headers`, `encoding_used`, `transformations`  
Does NOT contain: `df` (the raw DataFrame is explicitly excluded)

### audit_events_excerpt.json
PII fields stripped from all events:
- `employee_id` removed
- `full_name` removed
- `email` removed
- `national_id` removed
- `iqama` removed

National ID and Iqama patterns in `summary` text fields are replaced with `[REDACTED]`.

---

## Governance Snapshot

The `governance_snapshot.json` records the production lock values at the time of package creation. This creates an auditable record that the platform was correctly configured.

Example snapshot:
```json
{
  "snapshot_at": "2026-05-21 10:30:00 UTC",
  "governance_locks": {
    "DEBUG": false,
    "EMPLOYEE_LEVEL_OUTPUT_ENABLED": false,
    "SCIENTIFIC_FEATURE_MODE": "theory_grounded",
    "LEGACY_CONSTRUCTS_DISABLED": true,
    "PDPL_WARNING_ENABLED": true,
    ...
  },
  "all_locks_active": true,
  "note": "Governance locks are code constants — cannot be overridden by configuration."
}
```

---

## API Usage

### Summary (JSON)
```
POST /v1/tenants/{tenant_id}/reports/audit-package
Body: {"governance_locks": {...}}  # optional; uses production values by default

Response: JSON summary with package_id, file_count, manifest_checksum
```

### ZIP Download
```
POST /v1/tenants/{tenant_id}/reports/audit-package/download
Content-Type: application/json

Response: application/zip
Content-Disposition: attachment; filename="audit_package_{tenant_id}.zip"
X-Package-ID: pkg_...
X-Governance-Verified: true
```

---

## PDPL Documentation Support

The audit package supports PDPL Article 31 documentation requirements:

| PDPL Requirement | Package Evidence |
|-----------------|-----------------|
| Records of processing activities | `scan_summary.json` + `ingestion_metadata.json` |
| Processing purpose | `scan_summary.json` (stability analytics only) |
| Technical safeguards | `governance_snapshot.json` |
| Data minimization evidence | No raw rows in any file |
| Processing timestamps | `created_at` fields on all entries |
| Data controller records | `tenant_id` on all files |

**Important:** This package provides technical evidence. Legal compliance determination requires review by qualified Saudi legal counsel.

---

## Retention

Audit packages should be retained per your organization's data governance policy. The platform does not impose a retention period on exported packages — retention is the responsibility of the receiving organization.

For internal platform audit logs (recorded in the `AuditLogger`), retention is configured at `AUDIT_LOG_RETENTION_DAYS = 2555` (7 years) per Saudi enterprise compliance guidance.
