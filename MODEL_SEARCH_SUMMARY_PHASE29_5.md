# Phase 29.5 -- Model Search Summary

**Date:** 2026-06-01  
**Models evaluated:** 14  
**Baseline AUC:** 0.8205  
**Best AUC found:** 0.8471  

## Integration Decision

**INTEGRATE -- update platform metrics with new best model**

| Criterion | Result |
|-----------|--------|
| roc_auc_improved_by_0.01 | [OK] PASS |
| mcc_not_worse_by_0.01 | [OK] PASS |
| f1_not_worse_by_0.01 | [OK] PASS |
| no_leakage_flags | [OK] PASS |

| Delta AUC | Delta MCC | Delta F1 | Leakage Flags |
|-----------|-----------|----------|----------------|
| +0.0266 | +0.0194 | +0.0100 | 0 |

## Top 10 Models by ROC-AUC

| Rank | Model | AUC | ±std | MCC | F1 | Acc |
|------|-------|-----|------|-----|----|----|
| 1 | VotingEnsemble_top3 | 0.8471 | ±0.0234 | 0.4942 | 0.7073 | 0.7523 |
| 2 | CatBoost | 0.8408 | ±0.0214 | 0.5053 | 0.7154 | 0.7574 |
| 3 | RandomForest | 0.8392 | ±0.0234 | 0.4821 | 0.7008 | 0.7464 |
| 4 | GradientBoosting | 0.8368 | ±0.0251 | 0.4693 | 0.6924 | 0.7406 |
| 5 | RandomForest_tuned | 0.8322 | ±0.0238 | 0.4912 | 0.7196 | 0.7464 |
| 6 | ExtraTrees | 0.8321 | ±0.0227 | 0.4727 | 0.6982 | 0.7414 |
| 7 | XGBoost | 0.8311 | ±0.0156 | 0.4660 | 0.6908 | 0.7381 |
| 8 | LightGBM | 0.8305 | ±0.0201 | 0.4845 | 0.7026 | 0.7473 |
| 9 | StackingClassifier_GB_RF_LR | 0.8286 | ±0.0213 | 0.4725 | 0.7128 | 0.7355 |
| 10 | HistGradientBoosting | 0.8270 | ±0.0263 | 0.4594 | 0.6860 | 0.7356 |

## Baseline (Phase 29 -- locked)

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.8205 ±0.0206 |
| MCC     | 0.4748 ±0.0376 |
| F1      | 0.6973 ±0.0250 |
| Accuracy| 74.31% |
| Model   | GradientBoosting |

## Leakage Audit -- MI Scan (top 10)

| Feature | MI Score | Flag |
|---------|----------|------|
| ID | 0.1608 | [OK] |
| Job_Opportunities | 0.0633 | [OK] |
| JobTitle | 0.0618 | [OK] |
| Training_programs_ During_last_three_years | 0.0504 | [OK] |
| Department | 0.0438 | [OK] |
| Sector | 0.0406 | [OK] |
| Rewards&Wages_Satisfaction | 0.0397 | [OK] |
| Get_ Deserved_Promotion | 0.0314 | [OK] |
| Business_Travel | 0.0290 | [OK] |
| Job_Stability | 0.0259 | [OK] |

## Leakage Audit -- Solo AUC Scan (top 10)

| Feature | Solo AUC | Flag |
|---------|----------|------|
| ID | 0.5417 | [OK] |
| Allowances | 0.5147 | [OK] |
| demand_load | 0.5080 | [OK] |