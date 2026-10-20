# Saudi Schema Intelligence Audit
**Module:** `backend/core/saudi_schema_intelligence.py`
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

The `SaudiSchemaIntelligenceEngine` solves a concrete deployment problem: Saudi enterprises use at least eight distinct HR system architectures (IBM HR Benchmark, SAP SuccessFactors, Oracle HRMS, Mudad, Qiwa, and three generic variants), each with different column naming conventions, some bilingual (Arabic + English), and some using entirely Arabic column names. Without schema intelligence, the pipeline either silently drops critical features or fails to map them correctly, producing degraded predictions with no audit trail.

This module fingerprints the source ERP, normalizes column names to a canonical standard, identifies PII and leakage columns specific to Saudi regulations, and produces a structured `SchemaIntelligenceReport` that downstream governance layers consume.

---

## 2. ERP Fingerprinting

### 2.1 Supported Systems

| Constant | System | Confidence Threshold |
|---|---|---|
| `ERP_IBM_HR` | IBM HR Analytics Benchmark | ≥10 signature columns → HIGH |
| `ERP_SAP_SF` | SAP SuccessFactors | ≥4 pattern hits → HIGH |
| `ERP_ORACLE_HRMS` | Oracle HRMS / Fusion | ≥4 pattern hits → HIGH |
| `ERP_MUDAD` | Saudi Government Payroll (Mudad) | ≥3 Arabic/bilingual patterns → HIGH |
| `ERP_QIWA` | Saudi Labor Market Platform (Qiwa) | ≥3 Saudization/contract patterns → HIGH |
| `ERP_GENERIC_SAUDI_HR` | Unrecognized Saudi HR | Arabic column presence |
| `ERP_GENERIC_BILINGUAL_HR` | Mixed Arabic-English schema | Mixed language presence |
| `ERP_GENERIC_ENGLISH_HR` | Unrecognized English HR | Default fallback |

### 2.2 IBM HR Fingerprinting

The IBM HR Benchmark dataset is the research paper's primary reference dataset. Fingerprinting uses exact column name matching against `_IBM_SIGNATURE_COLUMNS` (30+ canonical column names). A match count ≥10 yields HIGH confidence; ≥5 yields MEDIUM; ≥2 yields LOW.

**Governance note:** IBM column names are camelCase (`JobSatisfaction`, `MonthlyIncome`). The completeness check uses `.lower()` normalization on both sides to avoid false misses.

### 2.3 Saudi Government Platform Fingerprinting

**Mudad** (`_MUDAD_SIGNATURE_PATTERNS`): Matches Arabic column names used by the Saudi government payroll system, including `رقم_الموظف` (employee number), `الراتب_الأساسي` (basic salary), `الجنسية` (nationality). These appear because Mudad is a mandatory integration point for Saudi businesses with ≥50 employees.

**Qiwa** (`_QIWA_SIGNATURE_PATTERNS`): Matches Saudization percentage columns, contract type fields, and Nitaqat band indicators. These are legally significant fields — Nitaqat compliance is a government requirement and cannot be used as a predictive feature without explicit governance review.

### 2.4 Confidence Levels

`_fingerprint_erp()` returns one of four confidence strings: `HIGH`, `MEDIUM`, `LOW`, `NONE`. When confidence is `LOW` or `NONE`, the report flags the schema as unverified and downstream code must apply conservative defaults.

---

## 3. Column Normalization

### 3.1 Normalization Maps

Each recognized ERP has a dedicated normalization dictionary mapping vendor-specific column names to the canonical standard (IBM HR naming convention, which the research paper uses):

| Map | Source → Target Example |
|---|---|
| `_SAP_TO_STANDARD` | `EmployeeID` → `EmployeeNumber`, `PayGrade` → `JobLevel` |
| `_ORACLE_TO_STANDARD` | `person_id` → `EmployeeNumber`, `pay_annualized_salary` → `MonthlyIncome` |
| `_MUDAD_TO_STANDARD` | `رقم_الموظف` → `EmployeeNumber`, `الراتب_الأساسي` → `MonthlyIncome` |
| `_QIWA_TO_STANDARD` | `contract_type` → `EmploymentStatus`, `saudization_pct` → `[flagged]` |

### 3.2 `_normalize_column()` Logic

```
1. Try ERP-specific map (exact match)
2. If no hit: return original name unchanged
3. Record normalization in ColumnSchemaRecord.normalized_name
```

Normalization is never destructive: the original name is always preserved in `ColumnSchemaRecord.original_name`. This ensures the audit trail remains complete even when names are changed.

### 3.3 What Is NOT Normalized

Saudization percentage columns are flagged but NOT renamed. Renaming `saudization_pct` to something neutral would obscure its legal significance. The governance note in `SchemaIntelligenceReport` explicitly calls out nationality-linked fields.

---

## 4. PII and Leakage Detection

### 4.1 PII Column Registry (`_PII_COLUMNS`)

Patterns cover both English and Arabic forms of:
- National ID / Iqama number (Saudi residency permit)
- GOSI (General Organization for Social Insurance) number
- IBAN / bank account
- Phone number, personal email
- Home address, GPS coordinates
- Passport number
- Arabic equivalents: `رقم_الهوية`, `رقم_الإقامة`, `رقم_الآيبان`

These are subject to **PDPL** (Saudi Personal Data Protection Law). Detection triggers a CRITICAL severity finding in the governance report.

### 4.2 Leakage Column Registry (`_SAUDI_ERP_LEAKAGE_COLUMNS`)

Patterns cover post-hoc outcome proxies and target-adjacent fields:
- `termination_reason`, `separation_code`, `exit_reason`
- `rehire_eligible`, `final_paycheck`
- `resignation_notice`, `last_working_day`
- Arabic forms: `سبب_الإنهاء`, `تاريخ_الاستقالة`

These columns can only exist in the dataset if the employee has already left, making them perfect leakage proxies that would inflate any attrition model's AUC by 20–40 points while producing a completely non-generalizable model.

---

## 5. Schema Completeness Scoring

`SchemaIntelligenceReport.schema_completeness_score` is a float in [0.0, 1.0] computed as:

```
score = (IBM columns present) / (total IBM signature columns)
```

where presence is checked case-insensitively. A score below 0.5 triggers a governance note recommending feature subset analysis before model training. A score of 0.0 on a non-IBM schema is expected and not a failure — the score is only meaningful when `erp_system == ERP_IBM_HR`.

---

## 6. `SchemaIntelligenceReport` Fields

| Field | Type | Purpose |
|---|---|---|
| `erp_system` | str | Detected ERP constant |
| `erp_confidence` | str | HIGH / MEDIUM / LOW / NONE |
| `column_records` | list[ColumnSchemaRecord] | Per-column metadata |
| `normalized_columns` | list[str] | Columns after normalization |
| `pii_columns` | list[str] | PII-flagged column names |
| `leakage_columns` | list[str] | Leakage-flagged column names |
| `schema_completeness_score` | float | IBM coverage fraction |
| `n_arabic_columns` | int | Arabic column count |
| `is_bilingual` | bool | Mixed language schema |
| `governance_notes` | list[str] | Human-readable audit notes |
| `summary` | str | One-line report summary |

---

## 7. Governance Guarantees

1. **No hardcoded Saudi schemas** — fingerprinting is evidence-based (column intersection), not a lookup table. A schema that happens to match IBM columns partially gets partial credit; it is never forced into a bucket.
2. **Normalization is reversible** — `ColumnSchemaRecord.original_name` always preserved.
3. **PII detection is additive** — detection never suppresses columns; it flags them for human review.
4. **Arabic column support** — Arabic patterns are first-class; Mudad/Qiwa support is not an afterthought.
5. **Confidence propagation** — downstream modules check `erp_confidence` and apply conservative defaults when confidence is LOW/NONE.

---

## 8. Test Coverage

`tests/test_phase5_saudi_validation.py::TestSaudiSchemaIntelligence` — 14 tests:

| Test | Assertion |
|---|---|
| `test_ibm_schema_fingerprinted_correctly` | HIGH confidence, correct ERP constant |
| `test_ibm_schema_completeness_score` | score ≥ 0.5 on full IBM dataset |
| `test_arabic_columns_detected` | `n_arabic_columns > 0` on Mudad fixture |
| `test_bilingual_schema_detected` | `is_bilingual == True` on mixed fixture |
| `test_pii_columns_flagged` | National ID column appears in `pii_columns` |
| `test_leakage_columns_flagged` | Termination reason flagged |
| `test_oracle_schema_fingerprinted` | Oracle ERP detected |
| `test_qiwa_schema_fingerprinted` | Qiwa ERP detected |
| `test_normalization_preserves_original` | `original_name` intact after normalize |
| `test_unknown_schema_falls_back` | Generic English fallback |
| `test_governance_notes_populated` | Notes list non-empty |
| `test_report_summary_non_empty` | Summary string populated |
| `test_convenience_function` | `analyse_schema()` returns correct type |
| `test_empty_dataframe_handled` | No crash on zero-column frame |

All 14 pass. No regressions in the full 302-test suite.

---

## 9. Known Limitations

- **Mudad schema version drift:** Mudad column names are based on the 2024 integration spec. If Saudi government updates the API schema in 2025+, `_MUDAD_SIGNATURE_PATTERNS` must be updated accordingly.
- **Partial SAP schemas:** SAP SuccessFactors customers often export a subset of the full module. Partial exports may yield MEDIUM instead of HIGH confidence. This is by design — not a false negative.
- **No HRDF column support:** The Human Resources Development Fund (HRDF) training subsidy system was not included in Phase 5 scope. If HRDF data is joined into HR extracts, column patterns will not be recognized.

---

*Audit produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
