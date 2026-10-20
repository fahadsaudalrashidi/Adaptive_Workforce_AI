# AWI Benchmark Evolution Report
## Phase 30F — Industry, Sector, and Historical Benchmarking

**Version:** v2.0.0-enterprise  
**Date:** 2026-06-01  
**Status:** Foundation Operational — Phase 31 Expansion Planned

---

## Executive Summary

AWI's Benchmark Engine (deployed Phase 29F) provides Saudi-calibrated sector benchmarks with differential privacy (ε=0.5) and k-anonymity (k≥5). As of Phase 30, the engine is operational with seeded benchmarks for 6 Saudi sectors. Phase 31 will expand to GCC multi-country benchmarks, internal department-vs-department comparison, and historical organisation-vs-sector trend tracking.

---

## Current State: Phase 29F Benchmark Engine

### Operational Capabilities

| Capability | Status |
|---|---|
| Saudi sector benchmarks (Banking, Oil & Gas, Telecom, Government, Healthcare, Education) | Live |
| k-anonymity gate (k≥5 contributors) | Enforced |
| Differential privacy noise injection (ε=0.5) | Enforced |
| Organisation vs sector gap analysis | Live |
| Benchmark gap panel in CEO Dashboard | Live |
| Contribution submission endpoint | Live |
| Fully offline — zero external API calls | Confirmed |

### Current Seeded Benchmarks

| Sector | Period | Contributors | WSI Mean | Priority Review % |
|---|---|---|---|---|
| Banking | Q2 2026 | 6 | 68.1 | 8.0% |
| Oil & Gas | Q2 2026 | 5 | 72.4 | 6.2% |
| Telecommunications | Q2 2026 | 5 | 71.8 | 7.1% |
| Government / Public Sector | Q2 2026 | 7 | 65.3 | 10.4% |
| Healthcare | Q2 2026 | 5 | 69.7 | 8.8% |
| Education | Q2 2026 | 5 | 74.1 | 5.9% |

All values labelled as "seeded estimates" until client-contributed data updates them with real contributions (k≥5 per bracket).

### Architecture

```
BenchmarkEngine (benchmark_engine.py)
├── SQLite: awi_benchmarks.sqlite (WAL mode)
│   ├── Table: benchmark_snapshots    (seeded sector averages)
│   ├── Table: contributions          (submitted org data, hashed)
│   └── Table: published_benchmarks   (k-anon + DP output, read-only)
├── Gap Analysis: org metrics vs sector median/p25/p75
├── k-anonymity: enforce k≥5 before publishing contributed data
└── Differential Privacy: Laplace noise, ε=0.5, δ=1e-5
```

---

## Phase 31 Benchmark Expansion Plan

### Expansion 1 — GCC Multi-Country Benchmarks

Saudi Arabia context leads, but GCC expansion unlocks multi-market clients:

| Country | Labour Law | Saudisation Equiv | Priority Sectors |
|---|---|---|---|
| **Saudi Arabia** | Saudi Labour Law | Nitaqat | All sectors |
| **UAE** | UAE Federal Labour Law | Emiratization | Banking, Tech, Gov |
| **Qatar** | Qatar Labour Law | Qatarization | Energy, Finance, Gov |
| **Kuwait** | Kuwait Labour Law | Kuwaitization | Finance, Oil & Gas |
| **Bahrain** | Bahrain Labour Law | Bahrainization | Finance, Hospitality |
| **Oman** | Oman Labour Law | Omanization | Energy, Tourism |

**Implementation:** GCC country code added to benchmark schema. Organisation selects `country=SA` or `country=AE` when requesting comparison. Cross-country comparison report added (Phase 31C).

### Expansion 2 — Internal Department Benchmarks

For large enterprises (>2,000 employees), departments can benchmark against each other:

```
Organisation: Saudi National Bank
├── benchmark query: "How does IT compare to Finance within SNB?"
├── benchmark query: "Which department is furthest below our internal stable average?"
└── benchmark query: "Operations 3-quarter trend vs our strongest department (HR)"
```

**Implementation:** Internal benchmark table seeded from historical snapshots (Phase 30E). Minimum 3 analysis runs required before internal benchmarks activate.

### Expansion 3 — Historical Organisation vs Sector Trend

Combines Phase 30E (Historical Intelligence) with Phase 29F (Benchmark Engine):

```
Board report question: "Are we keeping pace with sector improvement?"

Output: "Saudi National Bank's Workforce Stability Index improved 4.8 points
over 6 months (68.2 → 73.0). The Saudi banking sector average improved 2.1
points over the same period (68.1 → 70.2). SNB is outperforming the sector
benchmark by +2.7 points."
```

### Expansion 4 — Saudisation / Nitaqat Benchmarks

Vision 2030 mandates Saudisation targets by sector. AWI adds:
- Saudisation % benchmark by sector and organisation size
- Nitaqat band comparison (Excellent / High / Medium / Low)
- Gap-to-target calculation for compliance planning
- Scenario simulation: "How many Saudi hires needed to reach Excellent band?"

### Expansion 5 — Benchmark Contribution Network

As AWI client base grows, benchmark quality improves. Phase 31 introduces a **privacy-preserving benchmark contribution network**:

1. Client opts in (explicit consent, per PDPL Article 7)
2. AWI aggregates noised metrics (Laplace noise, ε=0.5) before submission
3. No employee records or identifiable data transmitted
4. Contribution credited to client's "Benchmark Network" tier benefits
5. Published benchmarks updated quarterly (k≥5 per bracket)

---

## Benchmark Quality Assurance

All AWI benchmarks carry the following quality markers:

| Marker | Meaning |
|---|---|
| `status: seeded` | Estimated from public data — client contribution will improve accuracy |
| `status: contributed` | Based on k≥5 real AWI client organisations |
| `dp_noise_applied: true` | Differential privacy noise injected before output |
| `k_anonymity_floor: 5` | Minimum contributors before publishing contributed data |
| `disclosure_risk: low` | Standard DP guarantee met |

---

## Integration Points

The Benchmark Engine is wired into:

1. **CEO Intelligence Brief** — "Your Stability Index vs sector median" card
2. **Executive Dashboard** — BenchmarkGapPanel component (Phase 29)
3. **Board Report V3** — Benchmark comparison section
4. **Strategy Simulator** — "Scenario impact vs industry peers" context
5. **Decision Center** — Evidence pack includes sector benchmark position

---

## PDPL and Governance

- Contribution data is hashed before storage: `SHA-256(org_id + period + sector)` — no reverse mapping possible
- All benchmark outputs include DP noise — exact individual organisation values cannot be inferred from published benchmarks
- k-anonymity ensures no organisation's data is uniquely identifiable in any published statistic
- Opt-in only: benchmark contribution requires explicit client consent in the platform settings

---

## Next Actions (Phase 31)

1. **BENCHMARK_GCC_EXPANSION.py** — GCC country support in benchmark_engine.py
2. **INTERNAL_BENCHMARK_ENGINE.py** — Department-vs-department comparison
3. **benchmark_contribution_api.py** — Opt-in contribution submission endpoint
4. **Nitaqat integration** — Saudisation compliance benchmarks
5. **UI: Benchmark History Chart** — 12-month org vs sector trend chart on Executive Dashboard
6. **Quarterly Benchmark Update** — Automated benchmark refresh from contributions

---

*AWI Benchmark Evolution Report — Phase 30F | 2026-06-01*
