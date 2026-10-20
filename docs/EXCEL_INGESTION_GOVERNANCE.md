# Excel Ingestion Governance — Phase 9

**Document Type:** Security & Governance Reference  
**Phase:** 9  
**Date:** 2026-05-21  
**Audience:** Security Review, Compliance, Data Engineering

---

## Purpose

This document describes the security controls applied during file parsing in the `ExcelIngestionEngine`. It explains why each control exists and how it maps to Saudi PDPL and general data handling principles.

---

## Security Controls

### 1. Formula Execution Prevention

**Risk:** An attacker uploads an Excel file with a malicious formula (e.g., `=HYPERLINK(...)`, DDE payloads) that executes when the file is opened.

**Control:** openpyxl is called with `data_only=True`:
```python
wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
```

This causes openpyxl to read only the cached computed values — never the formula strings. Formula cells that have never been computed return `None`, which is handled as empty.

**Coverage:** Prevents server-side formula execution for all `.xlsx` and `.xls` files.

---

### 2. Encoding-Safe CSV Parsing

**Risk:** A file saved with Windows Arabic encoding (cp1256 / windows-1256) is misread as garbage, causing incorrect column detection or silent data corruption.

**Control:** Multi-encoding fallback chain:
```python
encodings = ["utf-8-sig", "utf-8", "cp1256", "windows-1256", "latin-1"]
```

Each encoding is attempted in order. If a `UnicodeDecodeError` occurs, the next encoding is tried. The first successful decode is used. The encoding is logged in `IngestionResult.encoding_used`.

**Coverage:** Handles UTF-8 with BOM (Windows Save As), pure UTF-8, Arabic Windows encodings, and Western European fallback.

---

### 3. Sheet Selection Scoring

**Risk:** An HR dataset in a multi-sheet Excel file includes a secondary sheet containing PII (e.g., a "Summary" tab with executive names). Selecting the wrong sheet could pass PII to the analysis pipeline.

**Control:** Sheet selection is scored by:
1. Sheet name keyword match (HR-related English and Arabic terms)
2. Column header HR-relevance (COR/JD-R construct keywords)

The highest-scoring sheet is selected. A warning is added when multiple sheets exist. The `sheet_used` field in `IngestionResult` records which sheet was selected, enabling downstream audit.

**Limitation:** The SecureFileIngestion governance scan then checks ALL column names in the selected sheet for PII — so even if the wrong sheet is selected, PII blocking still occurs.

---

### 4. Salary Column Normalization (Safe)

**Risk:** Salary values stored as `"SAR 12,500"` or `"12.500,00"` are parsed as strings, causing the calibration engine to fail silently on a key construct (SalaryGrowth, IncomePerLevel).

**Control:** Salary-related columns (detected by keyword: "salary", "راتب", "income", "pay", "compensation") are normalized:
1. All spaces, commas, and non-numeric characters stripped
2. `pd.to_numeric(..., errors="coerce")` applied
3. Non-parseable values become NaN (not crashes)

**Audit:** Transformation logged as `"Normalized salary column '{col}' (removed currency/commas)"`.

---

### 5. Duplicate Column Renaming

**Risk:** An Excel file exported from SAP may have two columns named "Rating" (performance and peer rating). Pandas silently drops one, causing data loss.

**Control:** Duplicate column names are detected before DataFrame creation:
```python
df.columns = new_cols  # e.g., "Rating", "Rating_1"
```

A warning is added for each renamed column. The `original_headers` field preserves the original names for audit purposes.

---

### 6. Hidden Row Disclosure

**Risk:** Excel files may contain hidden rows (e.g., rows flagged for deletion but not yet removed). These rows might contain PII or anomalous data.

**Control:** Hidden rows are counted and disclosed in `warnings`:
```
"3 hidden row(s) detected in sheet. These will be included."
```

Hidden rows are included in the DataFrame — they are not silently dropped. The SecureFileIngestion PII scanner then checks all rows.

---

## ERP System Detection

The engine detects ERP system provenance to inform column mapping:

| ERP System | Detection Signal |
|-----------|-----------------|
| Workday | `workday`, `wd_`, `worker_id` in headers |
| SAP SuccessFactors | `successfactors`, `sf_`, `ecf_` in headers |
| Oracle HCM | `oracle`, `hcm_`, `person_number` in headers |
| Mudad (Saudi Payroll) | `mudad`, `مدد`, `الراتب_الأساسي` in headers |
| Qiwa (Saudi Labour) | `qiwa`, `qiwa_`, `saudization` in headers |
| BambooHR | `bamboohr`, `bamboo` in headers |

This is advisory only — it does not affect processing. It is logged in `IngestionResult.detected_erp_style` for downstream reference.

---

## Language Detection

Arabic Unicode characters are detected via:
```python
_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
```

Columns are scored:
- `arabic_count > english_count` → `'ar'`
- Both > 0 → `'mixed'`
- English only → `'en'`
- Neither → `'unknown'`

Mixed-language files are fully supported. The `TheoryAwareColumnMapper` handles Arabic synonym mapping for HR constructs.

---

## What the Ingestion Engine Does NOT Do

- It does NOT execute any Python code embedded in file content
- It does NOT make network requests during parsing
- It does NOT write any files to disk
- It does NOT store the parsed DataFrame (in-memory only, discarded after scan)
- It does NOT log individual row values — only metadata
