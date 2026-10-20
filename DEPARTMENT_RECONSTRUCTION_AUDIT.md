# Department Reconstruction Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Department column detection, one-hot reconstruction, department risk panel availability

---

## Problem Statement

Many HR datasets exported from HRIS systems (Workday, SuccessFactors, etc.) contain
department information as one-hot encoded columns rather than a single categorical column:

```
Department_Sales | Department_IT | Department_HR | Department_Finance
         1       |       0       |       0       |         0
```

The platform's department risk panel requires a single `Department` column to:
1. Group employees by department for aggregated risk scoring
2. Identify most-at-risk and burnout hotspot departments
3. Display department-level attrition probability distributions

Without reconstruction, the panel reports "Department analysis not available."

---

## Detection (v2.5.1)

### Leakage Detector — Check 14: DEPT_ONEHOT_GROUP_DOMINANCE

**Location:** `backend/core/leakage_detector.py` — `_check_department_onehot_dominance()`

**Detection logic:**
- Scans feature_names for columns starting with: `department_`, `dept_`, `division_`, `unit_`, `group_`, `team_`
- If any matching columns found → advisory flag generated
- If combined importance > 35% of total → FLAG severity

**Prefix list:**
```python
_DEPT_ONEHOT_PREFIXES = [
    "department_", "dept_", "division_", "unit_", "group_", "team_",
]
```

### ModelTruthAuditor — Check 6: DEPT_ONEHOT_DETECTED

**Location:** `backend/core/model_truth_audit.py` — `_check_dept_onehot_detected()`

Provides a higher-level advisory with reconstruction recommendation. Returns WARN or FLAG
depending on the group's importance share.

---

## Reconstruction Pattern

When one-hot department columns are detected, the recommended reconstruction creates a
single categorical column:

```python
import pandas as pd

def reconstruct_department_column(df: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct a single Department column from one-hot encoded group."""
    dept_prefixes = ["department_", "dept_", "division_", "unit_", "group_", "team_"]
    dept_cols = [c for c in df.columns if any(c.lower().startswith(p) for p in dept_prefixes)]

    if not dept_cols:
        return df  # no one-hot group found

    # Reconstruct: take the column name with max value per row
    dept_vals = df[dept_cols].idxmax(axis=1)
    # Strip prefix to get department name
    for prefix in dept_prefixes:
        dept_vals = dept_vals.str.replace(prefix, "", case=False, regex=False)

    df["Department_reconstructed"] = dept_vals
    return df
```

**Caveat required in UI:**
> "Department column was reconstructed from one-hot encoded source columns.
> Verify reconstruction accuracy against original data before using for decisions."

---

## Semantic Mapper Integration

The `SemanticMapper` (`backend/core/semantic_mapper.py`) uses a synonym list to detect
department columns. If `Department_reconstructed` is present, it should be mapped to
semantic category `"department"`.

This mapping should be applied in the `FeatureFactory` or `DataHealer` step.

**Current status:** Reconstruction is advisory — no automatic reconstruction applied in v2.5.1.
Manual reconstruction or dataset-level fix is recommended.

---

## Platform Department Analysis Path

```
df uploaded → AdaptiveRouter.route() → DatasetContract
→ SemanticMapper.map() → sem_map["department"] = "Department" (or None)
→ DataHealer.fit_transform() → df_clean
→ FeatureFactory.engineer() → df_eng
→ MLRouter.train() → TrainingResult
→ score_departments(df_eng, probs, ind_risks, sem_map) → DepartmentRisk[]
→ score_organization(ind_risks, dept_risks) → OrganizationalRisk
```

If `sem_map["department"] is None` (because no department column was found):
- `score_departments()` returns empty list
- `org_risk.most_at_risk_dept = None`
- Department panel shows "department analysis not available"

---

## Governance Advisory

When department one-hot columns are detected:

1. **In the Model Truth Audit:** Check 6 generates WARN or FLAG
2. **In the Leakage Report:** Check 14 generates MEDIUM flag with recommendation
3. **In the UI:** The department panel should show:
   > "Department analysis requires a single Department column. This dataset contains
   > one-hot encoded department columns (e.g. Department_Sales). Reconstruct the
   > Department column from the source data to enable department risk aggregation."

---

## Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Reconstruction assumes one-hot is exclusive (exactly one 1 per row) | May fail for multi-value encodings | Validate reconstruction against row sums |
| Department names lose original case and formatting | Cosmetic | Apply title-casing post-reconstruction |
| Unlabeled rows (all zeros) become the last column's name | Wrong label | Filter rows where sum == 0 before reconstruction |
| Auto-reconstruction not implemented | Department panel remains unavailable | Manual or upstream fix required |
