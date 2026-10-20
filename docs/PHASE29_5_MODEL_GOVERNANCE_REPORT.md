# Phase 29.5 -- Model Governance Report

**Date:** 2026-06-01  
**Standard:** HR Analytics Model Risk Framework  
**Reviewer roles:** ML Scientist + Model Risk Officer + Leakage Auditor

---

## 1. Data Governance

- PII columns removed: []
- Proxy/tenure columns removed: ['Years_Experience', 'Years_experience_lastorganization']
- Near-constant columns removed: []
- Static exclude columns removed: []

## 2. Leakage Audit Summary

- MI scan high-MI flags (>0.25): 0
- All proxy keywords enforced programmatically: YES
- PII exclusion enforced programmatically: YES
- No synthetic labels used: YES
- No post-event outcome columns in features: YES

## 3. Theory-Grounded Features

- Features engineered: 1
- All reviewed individually: YES
- None derived from proxy/tenure columns: YES

## 4. Model Search Summary

- Models evaluated: 14
- CV method: 5-fold StratifiedKFold
- Threshold: 0.5
- Random state: 42

## 5. Integration Decision

**INTEGRATE -- update platform metrics with new best model**

- Delta AUC: +0.0266  (need ≥ +0.01)
- Delta MCC: +0.0194  (need ≥ -0.01)
- Delta F1:  +0.0100  (need ≥ -0.01)
- Leakage flags: 0  (need = 0)

## 6. Absolute Rules Compliance

| Rule | Status |
|------|--------|
| No metric inflation | [OK] Conservative CV used throughout |
| No proxy leakage reintroduced | [OK] Programmatic exclusion enforced |
| No PII or ID columns | [OK] Enforced by column scanner |
| No target leakage / synthetic labels | [OK] Only real binary target used |
| No overfitting | [OK] OOF CV, not test-set metric cherry-picking |
| Full-feature metrics not used as platform | [OK] Conservative proxy-free metrics only |
| Platform metrics only updated if thresholds pass | [OK] Acceptance gate enforced |

## 7. Limitations

- Model search uses conservative hyperparameter ranges to avoid overfit
- Dataset size n=1,191 limits ensemble diversity gains
- Calibration comparison uses 3-fold inner CV due to dataset size
- All metrics are statistical estimates subject to CV variance

---

*This report was generated automatically by phase29_5_model_search.py.*  
*All findings are statistical model metrics only -- not employment decisions.*