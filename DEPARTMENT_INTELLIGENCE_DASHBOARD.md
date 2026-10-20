# Department Intelligence Dashboard

**Feature:** Employee Risk Dashboard → Department Intelligence  
**Phase:** 14  
**Page:** `EmployeeRiskDashboard` → Department sections

---

## 1. Overview

The Department Intelligence section aggregates individual employee risk scores to the department and specialty/job-group level. It provides HR leaders and executives with a group-level view of organisational risk concentration — without exposing individual employee identifiers.

---

## 2. Grouping Column Detection

AWI automatically detects the most appropriate grouping column from the uploaded dataset. Detection order:

**Department grouping (primary):**
```
Department → JobLevel → Academic_degree → Education →
section → division → team → unit → القسم
```

**Specialty grouping (secondary):**
```
Specialty → JobRole → التخصص → المسمى_الوظيفي →
position → title
```

If the department and specialty columns are identical, the specialty grouping is suppressed to avoid duplication.

---

## 3. Group-Level Metrics

For each detected group, AWI computes:

| Metric | Description |
|---|---|
| `total_records` | Number of employee records in the group |
| `average_risk_score` | Mean risk indicator (0–100) |
| `average_stability_score` | Mean stability score (0–100) |
| `stable_count` | Records in Stable band |
| `monitoring_count` | Records in Monitoring band |
| `strategic_concern_count` | Records in Strategic Concern band |
| `priority_review_count` | Records in Priority Review band |
| `top_risk_drivers` | Most common risk factors across group records |
| `top_protective_drivers` | Most common protective factors across group records |
| `governance_notes` | Automatic governance observations |

---

## 4. Dashboard Visualisations

### 4.1 Stacked Bar Chart (Department Risk Distribution)

- X-axis: Department names (top 12 by average risk score)
- Y-axis: Record count
- Bars: Stacked by band colour — Stable (green), Monitoring (amber), Strategic Concern (orange), Priority Review (red)
- Tooltip: Full department name + band breakdown

### 4.2 Expandable Department Cards

Each department row includes:
- Average risk score
- Mini progress bar (band proportions)
- Expandable detail: per-band counts, top risk drivers, top protective factors

### 4.3 Specialty / Job Group Intelligence

Same visualisation structure applied to the secondary grouping column (e.g., JobRole).

---

## 5. Automatic Governance Notes

AWI generates governance notes for each group automatically:

- Always includes: "Scores are statistical indicators requiring qualified HR review."
- When Priority Review > 0: "X% of records in this group are in Priority Review band — recommend HR lead review."

---

## 6. Sorting

Department summary is sorted by `average_risk_score` (descending) by default, placing the highest-risk groups at the top for immediate executive attention.

---

## 7. Export: Department Risk CSV

Available via `export_department_risk_csv()`:

```csv
# GOVERNANCE DISCLAIMER
# Statistical workforce risk indicators for HR review only...
group_label,group_value,total_records,average_risk_score,...
Department,Engineering,142,58.3,...
Department,Sales,89,72.1,...
```

---

## 8. Governance Rules for Group Data

Even at the group level:
- Group labels must not be derivable to individuals (groups with < 3 records are retained but HR should note the identification risk)
- Risk driver labels are construct names (e.g., "Overtime Demand"), not column values
- No raw employee data is included in any group output
- All exports include the mandatory governance disclaimer

---

## 9. Interpretation Guidance

| Average Risk Score | Recommended Action |
|---|---|
| 0–30 | Maintain current practices; standard check-in |
| 30–55 | Monitor workload and engagement indicators |
| 55–75 | Schedule department-level HR review |
| 75–100 | Urgent department-wide HR intervention recommended |

**Note:** These thresholds are guidance only. All interpretations require qualified HR professional judgement.
