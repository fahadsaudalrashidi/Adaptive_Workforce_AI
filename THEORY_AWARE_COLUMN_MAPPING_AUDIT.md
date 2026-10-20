# Theory-Aware Column Mapping Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Phase 1 — Theory-Aware Adaptive Column Understanding for Saudi HR Datasets  
**Module:** `backend/core/theory_aware_column_mapper.py`

---

## Purpose

This module maps raw dataset columns to organizational psychology constructs using
**construct-level theory validation**, not keyword matching. It is the scientific
foundation for all downstream feature engineering.

It does NOT compute constructs, modify models, or change the UI.
It ONLY classifies columns into theoretically-grounded categories with
evidence strength, scale validation, and leakage governance.

---

## Mapping Logic

### Four-Stage Pipeline

```
Column name
    │
    ├─ Stage 1: IBM HR exact match  → DIRECT evidence, confidence 0.95
    │   (camelCase split + lowercase normalisation)
    │
    ├─ Stage 2: English synonym exact match → STRONG_PROXY, confidence 0.85
    │   (Saudi HR English synonyms, camelCase-normalised)
    │
    ├─ Stage 3: Arabic exact match → STRONG_PROXY, confidence 0.85
    │   (Unicode-aware, Arabic diacritics stripped)
    │
    └─ Stage 4: Keyword substring match → WEAK_PROXY, confidence 0.38–0.65
        (both English and Arabic normalised forms searched)
        
    → If no match: UNSUPPORTED, confidence 0.00
```

**camelCase normalisation:** `MonthlySalary` → `monthly_salary` before lookup,
ensuring Saudi datasets with PascalCase export formats are handled correctly.

### Scale Validation

Each construct has an expected scale type. The actual column distribution is
checked against this expectation to produce a `scale_confidence` (0–1):

| Expected Scale | High Confidence Condition |
|---------------|--------------------------|
| `binary` | Values in {Yes, No, Y, N, 0, 1} |
| `likert_4` | Integer range 1–4, ≤4 unique values |
| `likert_5` | Integer range 1–5, ≤5 unique values |
| `ordinal_small` | Integer range 1–10, ≤10 unique values |
| `continuous_positive` | Positive integers, max ≤ 100 |
| `continuous_large` | Mean ≥ 1000 (salary-scale) |
| `continuous_bounded` | Range 0–100 (percentage) |
| `categorical` | Non-numeric dtype |

Scale mismatches reduce `scale_confidence` and add warnings.  
They do NOT block the column — human review is required.

---

## Supported Constructs

### Category 1: SATISFACTION_HYGIENE (COR + FFM)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `JobSatisfaction` | `JobSatisfaction` | COR + FFM (inverse Neuroticism) |
| `EnvironmentSatisfaction` | `EnvironmentSatisfaction` | COR condition resource |
| `RelationshipSatisfaction` | `RelationshipSatisfaction` | FFM Agreeableness proxy |
| `WorkLifeBalance` | `WorkLifeBalance` | COR energy resource + JD-R |

**Saudi synonyms supported:**
- `الرضا الوظيفي`, `رضا الموظف`, `الرضا العام`
- `الرضا عن بيئة العمل`, `الرضا عن العلاقات`
- `التوازن بين العمل والحياة`, `توازن الحياة المهنية`
- English: `job_satisfaction`, `employee_satisfaction`, `work_life_balance`, etc.

### Category 2: JOB_DEMANDS (JD-R)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `OverTime` | `OverTime` | JD-R demand gate for BurnoutRisk |
| `WorkPressure` | *(Saudi only)* | JD-R demand (WEAK_PROXY) |

**Important:** `WorkPressure` is a WEAK_PROXY for `OverTime`. It **cannot** substitute
the binary gate in `BurnoutRisk = OverTime × (5 − WorkLifeBalance)`.

**Arabic:** `ساعات إضافية`, `العمل الإضافي`, `ضغط العمل`, `الضغط الوظيفي`

### Category 3: JOB_RESOURCES (JD-R + COR)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `WorkLifeBalance` | `WorkLifeBalance` | COR energy resource |
| `ManagerialSupport` | *(Saudi only)* | JD-R resource buffer |
| `TrainingHours` | `TrainingTimesLastYear` | JD-R growth resource |

**Arabic:** `دعم المدير`, `دعم القيادة`, `التدريب`, `ساعات التدريب`

### Category 4: ENGAGEMENT_INVOLVEMENT (JD-R + FFM)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `JobInvolvement` | `JobInvolvement` | Conscientiousness proxy (FFM) |
| `EmployeeEngagement` | *(Saudi only)* | Kahn (1990) STRONG_PROXY |

**Governance:** `EmployeeEngagement` composite scores **cannot substitute**
`JobInvolvement × JobSatisfaction` without construct validity review.

**Arabic:** `الاندماج الوظيفي`, `المشاركة الوظيفية`, `مستوى الاندماج`

### Category 5: EQUITY_FAIRNESS (Adams 1963 + COR)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `PromotionFairness` | *(Saudi only)* | Adams Equity perception |
| `SalaryFairness` | *(Saudi only)* | Adams Equity perception |

**Arabic:** `عدالة الترقية`, `استحقاق الترقية`, `عدالة الراتب`, `إنصاف الراتب`

### Category 6: COMMITMENT_ATTACHMENT (Allen & Meyer + COR)

| Construct | IBM HR Column | Theory Anchor |
|-----------|--------------|--------------|
| `OrganizationalCommitment` | *(Saudi only)* | Affective commitment |

**Arabic:** `الالتزام التنظيمي`, `الولاء التنظيمي`, `الانتماء`

### Category 7: RETENTION_WITHDRAWAL (Mobley 1977) — LEAKAGE MODERATED

| Construct | Leakage Risk | Scientific Baseline | Advanced Mode |
|-----------|-------------|--------------------|----|
| `IntentToLeave` | HIGH | BLOCKED | Allowed |
| `ExternalJobOpportunities` | MODERATE | BLOCKED | Allowed |

**Arabic:** `نية ترك العمل`, `التفكير بالاستقالة`, `فرص عمل خارجية`

### Category 8: STRUCTURAL_HR_BASELINE

| Construct | IBM HR Column | Required For |
|-----------|--------------|-------------|
| `YearsAtCompany` | `YearsAtCompany` | TenureRatio numerator, CareerProgression |
| `TotalWorkingYears` | `TotalWorkingYears` | TenureRatio denominator |
| `MonthlyIncome` | `MonthlyIncome` | IncomePerLevel numerator |
| `JobLevel` | `JobLevel` | IncomePerLevel denominator, CareerProgression |
| `PercentSalaryHike` | `PercentSalaryHike` | SalaryGrowth |
| `PerformanceRating` | `PerformanceRating` | SalaryGrowth |
| `Age` | `Age` | Structural demographic |
| `Department` | `Department` | Department risk panel |
| `Absence` | *(Saudi only)* | Behavioural indicator |

**Arabic:** `مدة الخدمة`, `إجمالي سنوات الخبرة`, `الراتب الشهري`,
`المستوى الوظيفي`, `تقييم الأداء`, `القسم`, `الغياب`

### Category 9: TARGET_ADJACENT_LEAKAGE — BLOCKED

| Construct | English Examples | Arabic Examples | Advanced Mode |
|-----------|-----------------|-----------------|--------------|
| `AttritionRisk_Derived` | attrition_risk, churn_score | خطر الاستقالة | BLOCKED |
| `ExitReason` | exit_reason, final_status | سبب الخروج, حالة الموظف النهائية | BLOCKED |
| `RetentionRisk_Derived` | retention_risk, flight_risk | احتمالية المغادرة | BLOCKED |

---

## Arabic/English Synonym Support

### Language Detection

| Language | Detection Method | Example |
|---------|-----------------|---------|
| Arabic | Unicode range U+0600–U+06FF | `الرضا الوظيفي` |
| English | ASCII alpha characters | `JobSatisfaction` |
| Mixed | Both present | `HR_الأداء` |
| Unknown | Neither | `123_code` |

### Arabic Normalization

Arabic diacritics (U+064B–U+065F, U+0670) are stripped before lookup.
This allows matching `الرِّضا الوظيفي` (with harakat) against `الرضا الوظيفي` (without).

### English CamelCase Normalization

`MonthlySalary` → `monthly_salary` before lookup.
`DepartmentName` → `department_name`.
`PerformanceScore` → `performance_score`.

This handles HRIS exports that use PascalCase or camelCase column names.

---

## Saudi HR Context Assumptions

1. **Payroll-only datasets** (Salary + Department + Tenure only) will map these
   structural columns correctly but will have NO satisfaction/engagement/demand
   constructs. The system will report which paper features can and cannot be computed.

2. **Attendance-only datasets** (Absence + LateAttendance) provide only the
   `Absence` structural indicator. This is NOT sufficient evidence for burnout
   or engagement inference.

3. **Survey-based datasets** (satisfaction/engagement Likert scales) will receive
   the highest mapping quality for psychological constructs.

4. **HRIS exports** (mixed structural + survey) are the primary target — the mapper
   handles their typically PascalCase column names through camelCase normalisation.

5. **SAR currency**: `MonthlyIncome` scale validation expects mean ≥ 1000.
   Saudi SAR salary ranges (5,000–30,000 SAR monthly) satisfy this threshold.

---

## Governance Rules

| Rule | Detail |
|------|--------|
| No burnout from absence alone | `Absence` maps to `STRUCTURAL_HR_BASELINE`, not `JOB_DEMANDS` |
| No engagement from salary | Salary maps to COR object resource, not Kahn engagement |
| No personality trait inference | FFM constructs require validated psychometric instruments |
| No post-outcome features | `ExitReason`, `FinalStatus` → TARGET_ADJACENT_LEAKAGE, blocked |
| No silent substitution | Missing IBM HR columns are not silently replaced |
| No target-adjacent in baseline | `IntentToLeave`, `ExternalJobOpportunities` blocked from Scientific Baseline |
| No circular leakage | Derived risk scores (AttritionRisk, RetentionRisk) blocked everywhere |

---

## Blocked Leakage Examples

| Column | Why Blocked | Mode |
|--------|------------|------|
| `AttritionRisk` | Derived score encoding target | ALL blocked |
| `ResignationScore` | Encodes attrition probability | ALL blocked |
| `ExitReason` | Post-outcome administrative data | ALL blocked |
| `FinalStatus` | Records the target outcome | ALL blocked |
| `RetentionRisk` | Circular: trained on target | ALL blocked |
| `خطر الاستقالة` | Arabic: attrition risk score | ALL blocked |
| `حالة الموظف النهائية` | Arabic: employee final status | ALL blocked |
| `IntentToLeave` | Pre-decision target proxy | Scientific Baseline blocked |
| `ExternalJobOpportunities` | Withdrawal signal | Scientific Baseline blocked |

---

## Unsupported Column Examples

| Column | Reason |
|--------|--------|
| `RandomCode` | No construct match |
| `DeviceID` | Technology identifier |
| `BadgeNumber` | Administrative ID |
| `InternetUsage` | No theory anchor in HR attrition literature |
| `CommentText` | Free text — NLP pipeline required |
| `FileName` | System artefact |

Unsupported columns receive `semantic_confidence=0.00`, `UNSUPPORTED` evidence,
and are excluded from all modes until manually categorised.

---

## Test Results

| Test Suite | Tests | Status |
|-----------|-------|--------|
| IBM HR exact columns (12 columns) | 15 | ✅ PASS |
| Saudi English synonyms (10 columns) | 11 | ✅ PASS |
| Arabic columns (12 columns) | 12 | ✅ PASS |
| Leakage-risk columns (10 columns) | 12 | ✅ PASS |
| Unsupported/noise columns (6 columns) | 8 | ✅ PASS |
| Edge cases and governance | 9 | ✅ PASS |
| **Total** | **67** | **✅ 67/67 PASS** |

Pre-existing test suite: **79/79 PASS** (no regressions)

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Arabic diacritics stripped only (no full Unicode normalisation) | Rare encoding variants may miss | Manual override via user_overrides |
| Mixed Arabic-English columns tried as English then Arabic | Some edge cases may miss | Both lookups attempted |
| Keyword matching is substring-only | Short keywords may produce false positives | Weak proxy evidence flagged for review |
| Scale validation requires numeric columns | Text scales (e.g. "Low/Medium/High") have neutral confidence | Warning issued, human review required |
| `WorkPressure` cannot substitute `OverTime` in BurnoutRisk | Saudi datasets without binary OverTime cannot compute BurnoutRisk | Governance note issued; feature skipped |
| `EmployeeEngagement` cannot substitute `JobInvolvement × JobSatisfaction` | Composite scores miss Kahn simultaneity | STRONG_PROXY flagged; formula incompatibility noted |

---

## Next Recommended Phase

**Phase 2 — Theory-Grounded Feature Computation**

Given the column mapping from Phase 1:

1. Check which of the 7 paper features have ALL required columns present
   (using `DIRECT` or `STRONG_PROXY` evidence, scale_confidence ≥ 0.70)
2. Implement exact paper formulas ONLY when required columns are confirmed
3. Disable features when required columns are absent or incompatible
4. Flag partial features (e.g., 3 of 4 SatisfactionIndex columns present)
5. Log which constructs were computed, skipped, or approximated

**Do NOT begin Phase 2 until:**
- All Phase 1 acceptance criteria are confirmed (67 tests pass ✅)
- Column mapping for the target dataset has been reviewed by HR analyst
- Column governance decisions (override any blocked columns) have been made
