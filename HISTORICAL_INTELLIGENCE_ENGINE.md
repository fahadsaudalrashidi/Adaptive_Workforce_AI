# AWI Historical Workforce Intelligence Engine
## Phase 30E — Longitudinal Workforce Analytics

**Version:** v2.0.0-enterprise  
**Date:** 2026-06-01  
**Status:** Foundation Complete — Production-Ready

---

## Purpose

AWI now captures a permanent record of every workforce intelligence assessment. Over time, these snapshots form a longitudinal picture of workforce health — enabling CHRO teams to track whether interventions are working, detect early warning signals before they become crisis events, and present trend evidence to boards.

**What this enables:**
- "Our Priority Review count dropped from 8.4% to 3.8% after the compensation review program" — backed by data
- "The Engineering department has shown declining stability for 3 consecutive quarters" — early warning
- "Workforce stability has improved 6.2 points since H1 2025" — board narrative with evidence

---

## Architecture

```
Workforce Analysis Run
        │
        ▼
HistoricalIntelligenceEngine.create_snapshot_from_analysis()
        │
        ▼
WorkforceSnapshot (aggregate only — no employee PII)
        │
        ▼
SQLite: awi_history.db → workforce_snapshots table
        │
        ▼
HistoricalIntelligenceEngine.analyze_trends()
        │
        ▼
TrendAnalysis → Board-level historical narrative
```

---

## Core Data Structure: WorkforceSnapshot

Every analysis session generates one `WorkforceSnapshot`. It captures:

| Field | Type | Description |
|---|---|---|
| `snapshot_id` | string | Unique identifier |
| `tenant_id` | string | Organisation namespace |
| `period` | enum | monthly / quarterly / annual / ad_hoc |
| `period_label` | string | e.g. "2026-Q1", "2026-05" |
| `total_employees` | int | Total analysed employees |
| `stable_count` | int | Count in Stable band |
| `monitoring_count` | int | Count in Monitoring band |
| `concern_count` | int | Count in Strategic Concern |
| `priority_review_count` | int | Count in Priority Review |
| `workforce_stability_index` | float | 0–100 composite index |
| `avg_risk_score` | float | 0–100 average |
| `priority_review_pct` | float | Priority Review as % of total |
| `ml_auc` | float | Conservative AUC for this run |
| `top_risk_drivers` | list[str] | Aggregate top 5 risk drivers |
| `department_scores` | dict | Department → stability score |
| `estimated_attrition_cost_sar` | float | ROI engine output |

**No individual employee names, IDs, or scores are stored.** PDPL compliant by design.

---

## Trend Analysis

The `analyze_trends()` method generates a `TrendAnalysis` object from any series of snapshots. Key outputs:

### Stability Trend Classification

| Category | Threshold | Meaning |
|---|---|---|
| **Improving** | +3.0+ over 3 periods | Sustained positive trend |
| **Stable** | Within ±3.0 | No significant change |
| **Declining** | −3.0+ over 3 periods | Sustained negative trend |
| **Volatile** | No consistent direction | High variance — investigate |

### Risk Driver Intelligence

The engine tracks which risk drivers persist, emerge, or resolve across periods:

- **Persistent drivers**: Appear in top 5 for 3+ consecutive periods → structural problem requiring strategic intervention
- **Emerging drivers**: Appeared in last 2 periods but not before → early warning signal
- **Resolved drivers**: Previously persistent, now absent → intervention likely working

### Forecast

Simple linear extrapolation from recent trend. Confidence levels:
- **Low**: < 6 periods of history
- **Medium**: 6–11 periods
- **High**: 12+ periods

---

## Integration Point

The engine integrates into the main analysis pipeline in `local_analysis_routes.py`. After each successful analysis, a snapshot is automatically saved:

```python
from backend.core.historical_intelligence_engine import (
    HistoricalIntelligenceEngine, SnapshotPeriod
)

# After analysis completes:
hist_engine = HistoricalIntelligenceEngine()
snapshot = hist_engine.create_snapshot_from_analysis(
    tenant_id=tenant_id,
    analysis_result=result,
    period=SnapshotPeriod.MONTHLY,
    session_id=session_id,
)

# Trend intelligence:
trends = hist_engine.analyze_trends(tenant_id, lookback=12)
if trends:
    result["historical_intelligence"] = trends.to_dict()
```

---

## Board Narrative Format

Historical intelligence feeds directly into the Board Report and Decision Center. Sample narrative:

> **Workforce Stability Trend — Q1 2026 to Q2 2026**
>
> AWI has tracked 6 consecutive monthly assessments for Saudi National Bank. Workforce stability has improved 4.8 points (68.2 → 73.0) over this period. The Priority Review population has decreased from 9.1% to 5.6%, consistent with the Internal Mobility Programme launched in January 2026.
>
> **Persistent risk driver: Job Opportunities** — appeared in top 5 for all 6 periods. The compensation review program has not yet addressed this construct. Strategic attention required.
>
> **Emerging concern: Department — Engineering** — appeared in the Priority Review band in the last 2 assessments. Structured HR review recommended within 60 days.

---

## PDPL Compliance

All historical storage is aggregate-only:

| Stored | Not Stored |
|---|---|
| Band counts (stable=412, monitoring=187...) | Individual employee names |
| Average risk score (65.4) | Individual employee IDs |
| Department stability scores | Individual risk scores |
| Top risk drivers (aggregate) | Employee demographics |
| ROI estimates | Employee salary data |

The `workforce_snapshots` table contains zero personally identifiable information and does not fall under PDPL Article 6 data processing restrictions.

---

## Database File

`awi_history.db` — separate from the main session database (`awi_sessions.db`) and tenant registry (`awi_tenants.db`). This ensures historical data persists even when session data is cleared.

WAL (Write-Ahead Logging) mode enabled for concurrent reads during active analysis sessions.

---

## Phase 31 Extensions

- **UI: Workforce History Timeline** — trend chart on Executive Dashboard showing 12-month stability trend
- **Quarterly intelligence report**: auto-generated PDF comparing current quarter to prior 3 quarters
- **Intervention effectiveness tracking**: tag an intervention date, measure delta pre/post
- **Benchmark comparison**: compare trend against sector benchmarks (Phase 31 Benchmark Engine)
- **Alert engine**: notify CHRO when stability drops >3 points or Priority Review rises >2%

---

*AWI Historical Workforce Intelligence Engine — Phase 30E | 2026-06-01*
