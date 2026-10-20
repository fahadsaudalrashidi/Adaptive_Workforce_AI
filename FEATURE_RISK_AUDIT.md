# Feature Risk Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Proxy/leakage feature detection, high-cardinality governance, department one-hot reconstruction

---

## Summary

| Category | Previous | v2.5.1 |
|----------|---------|--------|
| Proxy leakage keywords | 9 | 23 |
| Leakage check types | 12 | 14 |
| High-cardinality governance | Basic (>50% unique) | Enhanced (one-hot group detection) |
| Department one-hot detection | None | Added (check 14) |
| Threshold concentration check | None | Added (check 13) |

---

## Proxy Leakage Keywords (Expanded)

The `_PROXY_KEYWORDS` list in `leakage_detector.py` now includes 23 terms:

```python
# v2.4.x (9 keywords)
"attrition", "exit", "resigned", "turnover", "left", "terminated",
"churn", "quit", "separated"

# v2.5.1 additions (14 new keywords)
"resignation", "termination", "separation",
"leave", "voluntary", "involuntary",
"last_day", "final_day",
"reason_for", "job_opportunities", "no_longer",
"departure", "status_change", "end_date", "offboard"
```

**Rationale:** Datasets exported from HRIS systems often include reason codes, separation dates,
and categorical labels that implicitly encode whether an employee left. These were previously
not caught by the 9-keyword list.

---

## New Leakage Checks (v2.5.1)

### Check 13: THRESHOLD_RISK_CONCENTRATION

**Trigger:** >40% of OOF predictions ≥ optimal threshold  
**Severity:** MEDIUM (40–55% flagged) or HIGH (>55%)  
**Action:** Warn about threshold selection; recommend "priority review segment" language  
**Risk:** Low thresholds (e.g. 0.15 from F1-optimized selection) flag too large a segment

### Check 14: DEPT_ONEHOT_GROUP_DOMINANCE

**Trigger:** Columns starting with `department_`, `dept_`, `division_`, `unit_`, `group_`, `team_`
with combined importance > 35%  
**Severity:** MEDIUM  
**Action:** Recommend reconstructing a single `Department` column  
**Risk:** One-hot departments prevent department-level risk aggregation in the HR analytics panel

---

## High-Cardinality Governance

### Existing Check (Check 5)
- Categorical columns with >50% unique values → HIGH flag
- Applies to any object/category dtype column

### New Check in ModelTruthAuditor (v2.5.1)
- Detects `jobtitle`, `job_title`, `title`, `name`, `role`, `designation` in feature names
- If these fields have >30% importance → FLAG
- Single-feature dominance >50% → FLAG

### Recommended Encoding
For high-cardinality categorical features (JobTitle, etc.):
1. Target-encoding with leave-one-out smoothing (inside CV folds only)
2. Or: Group rare categories (< 5 occurrences) into "Other"
3. Never apply target-encoding on the full dataset before splitting

---

## Department One-Hot Reconstruction

### Problem
Many HR datasets are exported with one-hot encoded departments:
```
Department_Sales | Department_IT | Department_HR | Department_Finance
         1       |       0       |       0       |         0
```
The department risk panel requires a single `Department` column to aggregate by department.
Without reconstruction, the panel reports "department column not available."

### Detection (v2.5.1)
`ModelTruthAuditor._check_dept_onehot_detected()` scans feature_names for prefixes:
- `department_`, `dept_`, `division_`, `unit_`, `group_`, `team_`

### Recommended Reconstruction Pattern
```python
dept_cols = [c for c in df.columns if c.lower().startswith("department_")]
if dept_cols:
    df["Department_reconstructed"] = df[dept_cols].idxmax(axis=1).str.replace("department_", "", case=False)
```

**Advisory:** Reconstructed column should be flagged in the UI:
> "Department derived from one-hot encoded columns — verify against source data."

---

## Feature Risk Classification (Conceptual)

For datasets with identifiable feature groups, features can be classified as:

| Group | Examples | Risk Level |
|-------|---------|-----------|
| Direct leakage | Columns matching proxy keywords | CRITICAL |
| ID columns | EmployeeID, RowNum | CRITICAL |
| High-cardinality | JobTitle (>50% unique) | HIGH |
| Department one-hot | Department_Sales, Dept_IT | MEDIUM |
| Engineered features | Tenure_bucket, Income_scaled | LOW |
| Core HR features | Age, YearsAtCompany, Satisfaction | LOW |
| Construct features | BurnoutScore, EngagementIndex | LOW |

---

## Ablation Test Framework (Deferred to v3.0)

Full ablation testing (6 model variants) is deferred. The ModelTruthAuditor provides
ablation planning output by classifying features into risk groups in the
`feature_risk_summary` field of `ModelTruthAuditReport`.

Planned ablation variants for v3.0:
1. Full model (baseline)
2. No-leakage-features (remove CRITICAL/HIGH proxy columns)
3. No-high-cardinality (remove JobTitle and similar)
4. No-one-hot-dept (remove Department_* group)
5. Raw-HR-only (Age, Tenure, Salary, Satisfaction)
6. Constructs-only (BurnoutScore, EngagementIndex, etc.)
