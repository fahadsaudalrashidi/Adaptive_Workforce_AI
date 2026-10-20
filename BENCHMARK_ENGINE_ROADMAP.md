# AWI BENCHMARK ENGINE ROADMAP
## Anonymised Sector Benchmark Database — Architecture & Delivery Plan

**Prepared by:** Chief AI Officer / Chief Strategy Officer  
**Date:** 2026-06-01  
**Classification:** INTERNAL — STRATEGIC ROADMAP  
**Target Delivery:** Phase 31 (Q3 2026)

---

## EXECUTIVE SUMMARY

The AWI Benchmark Engine creates a defensible data network effect moat: as more Saudi organisations use AWI, the platform aggregates **anonymised, sector-level workforce metrics** that no competitor can replicate. Clients will be able to compare their Workforce Stability Index (WSI) against the Saudi Banking sector average, their Human Capital Risk Index (HCRI) against similar-size O&G organisations, and their attrition cost exposure against Nitaqat-equivalent peers.

**This is Moat 6** from the Competitive Advantage Report — the client data network effect.

---

## 1. ARCHITECTURE OVERVIEW

### 1.1 Privacy-by-Design Principles

The benchmark engine is built on three non-negotiable privacy principles:

1. **Aggregation-only**: No individual employee record ever leaves the client's infrastructure. Only sector-level aggregates (mean, median, P25, P75, count) are contributed.
2. **K-anonymity floor**: A sector metric is only published if ≥5 organisations have contributed. No single organisation's data can be reverse-engineered.
3. **Differential privacy noise**: Before publication, Gaussian noise (ε=0.5, δ=1e-5) is added to all aggregate outputs. Prevents membership inference attacks.
4. **Client consent-gated**: Contribution is explicit opt-in per organisation, per sector, per metric. Default is non-contributing.

### 1.2 Data Flow Architecture

```
Client Org A (AWI On-Premises)
  └─► Contribution Agent (local, encrypted)
        └─► Aggregate: {sector, n_employees_range, WSI_mean, RHI_mean, HCRI_mean, ...}
              └─► Noise injection (local, before upload)
                    └─► AWI Benchmark API (Saudi data center, PDPL-compliant)
                          └─► K-anonymity check (k≥5)
                                └─► Benchmark Database (sector_benchmarks table)

Client Org B (AWI On-Premises)
  └─► Benchmark Query API
        └─► Returns: sector_avg_WSI, sector_P25_WSI, sector_P75_WSI (k≥5 gate)
              └─► Displayed: "Your WSI: 74.3 vs. Saudi Banking sector avg: 68.1"
```

### 1.3 Benchmark Database Schema

```sql
-- Sector benchmark snapshots (published quarterly)
CREATE TABLE sector_benchmarks (
    id              INTEGER PRIMARY KEY,
    sector          TEXT NOT NULL,                    -- 'banking', 'oil_gas', 'telecom', 'government'
    period          TEXT NOT NULL,                    -- 'Q2_2026'
    n_contributors  INTEGER NOT NULL,                 -- must be ≥ 5 to publish
    employee_range  TEXT NOT NULL,                    -- '500-2000', '2000-10000', '>10000'
    
    -- AWI Index Benchmarks
    wsi_mean        REAL, wsi_p25 REAL, wsi_p75 REAL, wsi_median REAL,
    rhi_mean        REAL, rhi_p25 REAL, rhi_p75 REAL,
    tfri_mean       REAL, tfri_p25 REAL, tfri_p75 REAL,
    hcri_mean       REAL, hcri_p25 REAL, hcri_p75 REAL,
    lsi_mean        REAL, ori_mean REAL,
    
    -- Risk Band Benchmarks
    pct_stable_mean     REAL,
    pct_monitoring_mean REAL,
    pct_concern_mean    REAL,
    pct_priority_mean   REAL,
    
    -- Financial Benchmarks
    cost_per_departure_sar_mean REAL,
    cost_per_departure_sar_p75  REAL,
    
    -- Governance
    dp_epsilon      REAL DEFAULT 0.5,               -- differential privacy parameter
    k_anonymity     INTEGER DEFAULT 5,
    published_at    TEXT,
    
    UNIQUE (sector, period, employee_range)
);

-- Client contribution log (local to AWI Benchmark API)
CREATE TABLE benchmark_contributions (
    id              INTEGER PRIMARY KEY,
    org_hash        TEXT NOT NULL,                  -- one-way hash, not reversible
    sector          TEXT NOT NULL,
    period          TEXT NOT NULL,
    contributed_at  TEXT NOT NULL,
    metrics_json    TEXT NOT NULL,                  -- noise-injected aggregates only
    consent_version TEXT NOT NULL
);
```

### 1.4 Contribution Agent (On-Premises)

The contribution agent runs inside the client's AWI instance. It:
- Computes sector aggregates from `EmployeeRiskData` (local computation only)
- Injects Gaussian noise before any data leaves the local machine
- Uploads only the noised aggregate, not raw rows
- Requires explicit user confirmation in the AWI UI before each contribution

```python
# backend/core/benchmark_contribution_agent.py (Phase 31 target)
def compute_contribution_payload(
    scored_data: dict,
    sector: str,
    consent_token: str,
) -> dict:
    """
    Local computation only. Output is noise-injected aggregate.
    No individual employee data is included or derivable.
    """
    ...
```

---

## 2. BENCHMARK QUERY API

### 2.1 Endpoints

```
GET  /api/benchmark/sector/{sector}
     Returns: sector-level benchmark metrics for all available periods.
     Gate: k≥5 contributors. Returns 404 if insufficient data.

GET  /api/benchmark/compare
     Body: { sector, wsi, rhi, hcri, employee_count_range, period }
     Returns: percentile rank of client org against sector.
     Example response:
       { "wsi_percentile": 72, "rhi_percentile": 45, "sector_avg_wsi": 68.1 }

GET  /api/benchmark/sectors
     Returns: list of available sectors with contributor counts (k-gated).

POST /api/benchmark/contribute
     Body: { sector, period, metrics, consent_token }
     Requires: valid consent_token from client UI
```

### 2.2 UI Integration (Phase 31)

On the CEO Dashboard and Executive Dashboard:
- New section: **"Sector Benchmark Comparison"**
- Shows: "Your WSI vs. Saudi {sector} sector average"
- Percentile bar: "You are in the top 28% of Saudi Banking organisations"
- Available only when:
  1. Client has opted into benchmark contribution (or is in read-only benchmark mode)
  2. Sector has ≥5 contributing organisations

---

## 3. PRIVACY AUDIT CONTROLS

### 3.1 Differential Privacy Budget

Each contribution consumes from the client's privacy budget (ε=2.0 per year):
- WSI contribution: ε=0.3 per metric group
- Full benchmark suite (all 6 indices): ε=0.5 total per quarter
- Maximum 4 contributions per year before budget exhaustion

### 3.2 K-Anonymity Enforcement

The benchmark API enforces k≥5 at query time:
```python
def get_sector_benchmark(sector: str, period: str) -> dict | None:
    row = db.query("SELECT * FROM sector_benchmarks WHERE sector=? AND period=? AND n_contributors>=5", ...)
    if row is None:
        return None  # Never return partial data — k<5 is suppressed entirely
    return row
```

### 3.3 PDPL Compliance

The benchmark database is hosted in a Saudi-certified data center (PDPL Article 5 compliance):
- Data never leaves the Kingdom
- Saudi PDPL DPA registration required before going live
- Annual privacy impact assessment (PIA) required
- Contributor organisations must sign the AWI Benchmark Data Sharing Agreement

---

## 4. COMMERCIAL MODEL

### 4.1 Benchmark Access Tiers

| Tier | Access | Price |
|------|--------|-------|
| Contributing Member | Full sector benchmarks + percentile ranking | Included in Professional/Enterprise tiers |
| Read-Only Member | Sector averages (no percentile rank) | SAR 20,000/year add-on |
| Government | Full access via Ministry endorsement | Included in Government tier |

### 4.2 Data Network Effect Value

Benchmark data creates a compounding competitive moat:
- **Year 1** (5 contributors): Basic sector averages available
- **Year 2** (20 contributors): Statistically robust percentile rankings by employee size
- **Year 3** (50 contributors): Time-series trends, department-level sector benchmarks
- **Year 4** (100 contributors): Saudi national workforce stability index (publishable)

At 100 clients, AWI can publish the **Saudi Workforce Stability Index (SA-WSI)** — a national benchmark that positions AWI as the definitive Saudi HR analytics authority.

### 4.3 Revenue Impact

- 20 read-only subscribers × SAR 20K = SAR 400K additional ARR
- Benchmark exclusivity increases Professional tier upsell success rate by estimated 30%
- National index publication creates media coverage worth SAR 2M+ equivalent in brand value

---

## 5. IMPLEMENTATION PHASES

### Phase 31A — Backend Foundation (4 weeks)
- `backend/core/benchmark_contribution_agent.py` — local aggregate computation + noise injection
- `backend/core/benchmark_query_engine.py` — k-gated query API
- `backend/core/local_benchmark_database.py` — local benchmark cache (offline mode)
- `backend/api/benchmark_routes.py` — FastAPI endpoints

### Phase 31B — Privacy Validation (2 weeks)
- Differential privacy audit (ε accounting)
- K-anonymity penetration test (can sector average be used to infer any single org?)
- PDPL legal review of benchmark data sharing agreement template

### Phase 31C — UI Integration (2 weeks)
- CEO Dashboard: "Sector Benchmark" panel
- Executive Dashboard: WSI comparison widget
- Opt-in consent flow in Settings page

### Phase 31D — Commercial Launch (2 weeks)
- First 5 beta clients recruited from Phase 29 pilot programme
- Benchmark data sharing agreement signed
- First sector benchmark published (minimum k=5)

---

## 6. TECHNICAL RISKS AND MITIGATIONS

| Risk | Severity | Mitigation |
|------|----------|------------|
| k<5 for niche sectors | Medium | Suppress output; offer "early adopter" cohort incentive |
| Client refuses to contribute | Low | Offer read-only access at lower price point |
| PDPL regulatory challenge | Low | Pre-engage with NDMO; data stays in KSA; PIA on file |
| Noise injection degrades benchmark accuracy | Medium | Calibrate ε to balance privacy vs. utility; validate with synthetic data |
| Competitive replication | Low | Benchmark network effect requires years to replicate; first-mover advantage is durable |

---

## 7. SUCCESS METRICS

| Metric | Q4 2026 Target | Q4 2027 Target |
|--------|---------------|---------------|
| Contributing organisations | 5 | 25 |
| Sectors with published benchmarks | 2 | 5 |
| Read-only benchmark subscribers | 10 | 40 |
| Benchmark ARR contribution | SAR 200K | SAR 800K |
| National WSI published? | No | Yes |

---

## CONCLUSION

The AWI Benchmark Engine is a strategic capability, not just a feature. It creates:
1. A **data moat** that compounds over time (no competitor can replicate without years of market presence)
2. A **commercial reason** to switch from read-only to contributing membership
3. A **national authority** positioning for AWI as the definitive Saudi workforce analytics platform

Phase 31 delivery timeline: **Q3 2026**, following the Phase 29 pilot programme and first 3 reference clients.

---

*Classification: INTERNAL — STRATEGIC ROADMAP*  
*Prepared: 2026-06-01 | AWI Enterprise Strategy*
