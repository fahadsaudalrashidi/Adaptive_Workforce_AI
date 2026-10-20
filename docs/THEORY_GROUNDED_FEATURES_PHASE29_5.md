# Phase 29.5 -- Theory-Grounded Feature Engineering

**Date:** 2026-06-01  
**Status:** All features reviewed for leakage -- CLEARED

## Engineered Features

| Feature | Theory | Sources | Leakage Risk |
|---------|--------|---------|--------------|
| `demand_load` | JD-R Demands | OverTime × 2 + BusinessTravel binary | Low |

## Proxy Exclusion Compliance

None of the engineered features derive from:
- Years_Experience or any tenure-duration column
- Post-event outcome columns
- PII or identifier columns

All engineered features represent **pre-event attitudinal or behavioral indicators**
grounded in validated organizational behavior theory.

## References

- Hobfoll, S.E. (1989). COR Theory -- Conservation of Resources
- Demerouti, E. et al. (2001). JD-R Model
- Hackman, J.R. & Oldham, G.R. (1976). Work Design
- Mobley, W.H. (1977). Employee Turnover Process
- Adams, J.S. (1965). Equity Theory