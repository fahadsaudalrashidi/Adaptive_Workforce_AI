# Enterprise Risk Language Audit
**Module:** `backend/core/enterprise_language_guard.py`
**Phase:** 5 — Saudi Enterprise Validation & Commercial Hardening
**Status:** PRODUCTION READY
**Date:** 2026-05-20

---

## 1. Purpose

Machine learning outputs describing individual employees carry legal, cultural, and regulatory risk when rendered in natural language. The `EnterpriseLanguageGuard` audits any text string — report narratives, dashboard labels, API response descriptions, HR recommendation text — before it is surfaced to an end user.

The guard addresses three distinct risk categories:
1. **Legal risk** — statements that could expose the deploying organization to wrongful termination claims, discrimination litigation, or PDPL violations.
2. **Scientific risk** — deterministic or causal language that misrepresents probabilistic model output as certain prediction.
3. **Cultural risk** — language inappropriate for Saudi Arabian workplace context, including nationality-linked attrition claims and Islamically insensitive phrasing.

---

## 2. Violation Categories

### 2.1 DETERMINISTIC_CLAIM (HIGH)

Language that presents a probabilistic output as a certain prediction.

**Blocked patterns:**
- `"will resign"`, `"will leave"`, `"will quit"`, `"will stay"`, `"will be terminated"`
- `"is going to leave"`, `"is certain to"`, `"is guaranteed to"`
- `"100% chance"`, `"certain to leave"`, `"guaranteed to leave"`

**Why critical:** Saudi Labour Law (Art. 74–79) governs termination conditions. Using deterministic language in an HR decision document creates a paper trail that could be interpreted as a unilateral employment decision, regardless of intent. It also violates the fundamental epistemic constraint that model outputs are probabilities, not facts.

**Safe alternative:** `"elevated attrition risk indicator"`, `"statistical risk signal"`, `"model-identified risk pattern"`

### 2.2 CAUSAL_LANGUAGE (MEDIUM)

Language that implies the model identified a causal mechanism.

**Blocked patterns:**
- `"causes turnover"`, `"leads to resignation"`, `"results in attrition"`
- `"because of low satisfaction"`, `"due to burnout"`
- `"is the reason for"`

**Why blocked:** The model is correlational, not causal. Peer-reviewed organizational research establishes theoretical causal chains (COR, JD-R), but the model predicts from observed patterns, not verified mechanisms. Causal language in HR reports misleads managers into interventions that may not address the actual driver.

**Safe alternative:** `"associated with"`, `"correlated with"`, `"co-occurs with"`, `"risk pattern includes"`

### 2.3 MEDICAL_LANGUAGE (HIGH)

Clinical or diagnostic terminology applied to employee states.

**Blocked patterns:**
- `"clinically depressed"`, `"mentally ill"`, `"has burnout disorder"`
- `"psychological diagnosis"`, `"medical condition"`, `"treatment required"`
- `"stress disorder"`, `"anxiety disorder"`

**Why critical:** HR systems are not clinical diagnostic tools. Using medical language in an employment context violates multiple regulatory frameworks and creates liability under Saudi health privacy rules. The model's `BurnoutRisk` construct is an organizational resource-depletion indicator (JD-R), not a clinical burnout diagnosis (Maslach).

**Safe alternative:** `"resource depletion signal"`, `"workload sustainability concern"`, `"engagement risk pattern"`

### 2.4 LEGAL_RISK (CRITICAL)

Language that could constitute or document a discriminatory employment decision.

**Blocked patterns:**
- `"terminate"`, `"fire"`, `"dismiss"`, `"make redundant"` (when paired with individual employee context)
- `"must be removed"`, `"should be let go"`, `"recommend dismissal"`
- `"not worth retaining"`, `"poor investment"`

**Why critical:** Any text containing this language in an HR analytics report could be discoverable in an employment tribunal. Saudi Labour Law Art. 80 specifies lawful termination grounds; AI-generated dismissal language that does not reference these grounds creates legal exposure.

**Safe alternative:** `"retention intervention recommended"`, `"engagement support warranted"`, `"HR review suggested"`

### 2.5 INDIVIDUAL_TARGETING (CRITICAL)

Language that names or uniquely identifies an individual employee alongside a risk assessment.

**Blocked patterns:**
- Regex: `(employee|staff member|worker)\s+\d+` (employee ID + risk)
- `"[Name] is at high risk"`
- `"this specific employee"`
- National ID or Iqama numbers in text

**Why critical:** PDPL (Saudi Personal Data Protection Law) requires that automated individual profiling results cannot be surfaced without data subject consent and appropriate governance controls. Individual-level targeting in report text bypasses these controls.

**Safe alternative:** Use aggregate statistics, risk bands, or cohort-level descriptions. Individual risk data must be accessed through controlled HR workflows, not report narratives.

### 2.6 CULTURAL_SENSITIVITY (HIGH)

Language inappropriate for Saudi Arabian workplace context.

**Blocked patterns:**
- Nationality + attrition claim regex: `(saudi|expat|foreign|non-saudi).*(higher|lower|more|less).*(attrition|turnover|risk|likely)`
- `"cultural fit"` (loaded term with nationality discrimination implications)
- `"local hire"` (Saudization context makes this sensitive)
- `"western standards"`, `"international norms"` as quality comparisons

**Why blocked:** Saudi workforce is regulated under Nitaqat/Saudization policy. Language that links nationality to attrition risk — even statistically accurate statements — creates regulatory exposure under HRDF guidelines and anti-discrimination provisions in the Saudi Labour Law.

**Safe alternative:** `"workforce segment"`, `"employee cohort"`, `"organizational unit analysis"`

### 2.7 UNSUPPORTED_CERTAINTY (MEDIUM)

Epistemic overclaiming short of full determinism.

**Blocked patterns:**
- `"definitely"`, `"absolutely"`, `"certainly"` (when modifying predictions)
- `"proven to"`, `"scientifically proven"` (specific intervention claims)
- `"always"`, `"never"` (universal quantifiers in individual risk context)

**Safe alternative:** `"evidence suggests"`, `"research indicates"`, `"risk patterns consistent with"`

### 2.8 PII_LANGUAGE (CRITICAL)

Sensitive personal data appearing as literal text in report strings.

**Blocked patterns:**
- `"national id"`, `"iqama"`, `"passport number"`, `"iban"`
- `"رقم الهوية"`, `"رقم الإقامة"` (Arabic forms)
- Patterns matching 10-digit Saudi National ID format: `\b\d{10}\b`
- Patterns matching IBAN: `\bSA\d{2}[A-Z0-9]{18}\b`

**Why critical:** PDPL Art. 29 prohibits processing of sensitive personal data without explicit consent. Sensitive data appearing in report text means it has already escaped controlled storage — this is a breach indicator, not just a style concern.

---

## 3. Safe Vocabulary Reference (`SAFE_ATTRITION_VOCABULARY`)

The module exports a reference dictionary mapping unsafe terms to approved alternatives:

| Unsafe Term | Approved Alternative |
|---|---|
| `"will resign"` | `"elevated attrition risk indicator"` |
| `"is going to leave"` | `"statistical risk signal"` |
| `"causes turnover"` | `"associated with attrition risk"` |
| `"burnout disorder"` | `"resource depletion pattern"` |
| `"terminate"` | `"retention intervention recommended"` |
| `"fire"` | `"HR review suggested"` |
| `"100% certain"` | `"model confidence score: X%"` |
| `"proven to cause"` | `"evidence suggests association with"` |

---

## 4. `LanguageAuditReport` Fields

| Field | Type | Purpose |
|---|---|---|
| `is_compliant` | bool | True when zero violations detected |
| `n_critical` | int | Count of CRITICAL severity violations |
| `n_high` | int | Count of HIGH severity violations |
| `n_medium` | int | Count of MEDIUM severity violations |
| `violations` | list[LanguageViolation] | Full violation records |
| `safe_text` | str | Input text with unsafe phrases replaced |
| `summary` | str | One-line audit summary |
| `governance_notes` | list[str] | Human-readable audit notes |

### 4.1 `LanguageViolation` Fields

| Field | Type | Purpose |
|---|---|---|
| `matched_text` | str | Exact text that triggered the rule |
| `category` | str | Violation category constant |
| `severity` | str | CRITICAL / HIGH / MEDIUM |
| `reason` | str | Why this text is flagged |
| `safe_alternative` | str | Recommended replacement |
| `position` | int | Character offset in original text |

---

## 5. Deduplication Logic

`_deduplicate_violations()` prevents the same text span from generating multiple violation records when multiple rules match. When two violations overlap in position, only the highest-severity one is kept. This produces cleaner audit reports and prevents double-counting in severity metrics.

---

## 6. `get_safe_text()` — Automated Remediation

`EnterpriseLanguageGuard.get_safe_text(text)` returns a copy of the input with unsafe phrases replaced by approved alternatives from `SAFE_ATTRITION_VOCABULARY`. This enables:

1. **Automatic draft remediation** — flagged text is immediately corrected for human review
2. **Diff-based review** — humans review only the deltas, not the full report

**GOVERNANCE NOTE:** `get_safe_text()` output must be reviewed by a qualified HR professional before being shown to employees. Automated text replacement is a drafting aid, not an autonomous HR decision.

---

## 7. Batch Audit (`audit_batch()`)

`audit_batch(texts: list[str])` applies the guard to a list of text strings (e.g., all narrative fields in a batch prediction run). It returns one `LanguageAuditReport` per input. Designed for integration into ETL pipelines that generate bulk HR reports.

---

## 8. Test Coverage

`tests/test_phase5_saudi_validation.py::TestEnterpriseLanguageGuard` — 16 tests:

| Test | Assertion |
|---|---|
| `test_deterministic_claim_flagged` | "will resign" → CRITICAL or HIGH |
| `test_causal_language_flagged` | "causes turnover" → MEDIUM |
| `test_medical_language_flagged` | "clinically depressed" → HIGH |
| `test_legal_risk_flagged` | "terminate this employee" → CRITICAL |
| `test_individual_targeting_flagged` | "Employee 12345 is at risk" → CRITICAL |
| `test_cultural_sensitivity_flagged` | Nationality+attrition regex → HIGH |
| `test_clean_text_passes` | Approved vocabulary → `is_compliant == True` |
| `test_safe_text_generated` | `get_safe_text()` replaces unsafe phrases |
| `test_violation_severity_ordering` | CRITICAL > HIGH > MEDIUM in report |
| `test_batch_audit_returns_list` | `audit_batch()` returns list of reports |
| `test_arabic_pii_detected` | Arabic National ID pattern flagged |
| `test_iban_pattern_detected` | IBAN format flagged |
| `test_deduplication_works` | Overlapping rules produce one violation |
| `test_is_compliant_shortcut` | `is_language_compliant()` returns bool |
| `test_governance_notes_populated` | Notes list non-empty on violations |
| `test_empty_string_passes` | Empty string → `is_compliant == True` |

All 16 pass. No regressions in the full 302-test suite.

---

## 9. Integration Points

The language guard is intended to be called at these pipeline positions:

1. **Report generation** — audit all narrative text before writing to PDF/dashboard
2. **API response** — audit `description` and `recommendation` fields before returning to client
3. **Batch prediction output** — audit all `narrative_summary` fields in bulk exports
4. **Slack/Teams integration** — audit any text sent via notification webhooks

The guard does NOT run in the model training pipeline — it governs output presentation, not feature engineering.

---

*Audit produced as part of Phase 5 — Saudi Enterprise Validation & Commercial Hardening. Scientific traceability governed by the research paper PDF as primary source of truth.*
