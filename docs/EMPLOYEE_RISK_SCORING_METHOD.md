# Employee Risk Scoring Methodology

**Module:** `backend/core/employee_risk_scoring.py`  
**Phase:** 14  
**Theory Framework:** COR · JD-R · FFM · Mobley · Adams Equity

---

## 1. Overview

AWI computes a **risk indicator** (0–100) and a **stability score** (0–100) for each employee record in an uploaded HR dataset. These scores are derived from recognised organisational behaviour theories using the construct columns available in the dataset.

Higher risk indicator → more organisational risk signals detected  
Higher stability score → stronger protective factors detected

---

## 2. Theoretical Foundations

### 2.1 Job Demands-Resources (JD-R) — Bakker & Demerouti (2007)

Captures the balance between job demands (risk factors) and job resources (protective factors).

**Risk constructs:**
- `OverTime` — overtime demand pressure
- `Physical_Stress` — physical workload strain
- `Psychological_Exhaustion` — burnout/exhaustion signal
- `Business_Travel` — travel demand pressure
- `Work_Life_Balance` (inverse — low balance → risk)

### 2.2 Conservation of Resources (COR) — Hobfoll (1989)

Resource loss is the primary driver of stress and withdrawal. Resource gain is protective.

**Risk constructs:**
- `Health_Issues` — resource threat signal

**Protective constructs:**
- `Job_Support` — supervisory resource
- `Recognition` — acknowledgement resource
- `Useful_Training_Programs` — career development resource
- `MedicalInsurance` — benefit resource
- `Allowances` — material resource
- `Emotional_Commitment` — internal resource
- `Job_Engagement` — engagement resource

### 2.3 Adams Equity Theory — Adams (1965)

Perceived fairness in the exchange relationship drives retention or withdrawal.

**Protective constructs (low value → risk):**
- `Rewards&Wages_Satisfaction` — compensation equity perception
- `Payment_Overtime` — overtime pay fairness
- `Get_Deserved_Promotion` — promotion justice
- `Bonus` — reward fairness

### 2.4 Mobley Withdrawal Model — Mobley (1977)

Perceived external opportunities increase withdrawal cognition.

**Risk constructs:**
- `Job_Opportunities` — external pull factor

**Protective constructs:**
- `Job_Stability` — stability perception (reduces withdrawal)

### 2.5 Five-Factor Model (FFM) / Satisfaction Constructs

**Protective constructs:**
- `Job_Satisfaction` — job content satisfaction
- `Environment_Satisfaction` — workplace environment satisfaction

---

## 3. Construct Detection

AWI uses regular-expression pattern matching to detect construct columns in any uploaded dataset. Columns are matched case-insensitively and tolerate underscores, spaces, and ampersands.

Example matches for `Rewards&Wages_Satisfaction`:
- `Rewards&Wages_Satisfaction` ✓
- `rewards_wages_satisfaction` ✓
- `REWARDS&WAGES_SATISFACTION` ✓

---

## 4. Value Normalisation

Each matched column value is normalised to [0.0, 1.0] as follows:

| Input type | Normalisation |
|---|---|
| `"Yes"` / `"نعم"` / `True` / `1` | → `1.0` |
| `"No"` / `"لا"` / `False` / `0` | → `0.0` |
| `"Travel_Frequently"` | → `1.0` |
| `"Travel_Rarely"` | → `0.4` |
| `"Non-Travel"` | → `0.0` |
| Ordinal 1–4 | → `(val - 1) / 3` |
| Ordinal 1–5 | → `(val - 1) / 4` |
| Missing / NaN | → skipped (not penalised) |

---

## 5. Scoring Formula

```
risk_score = 30.0
           + Σ (risk_construct_value × risk_weight)
           - Σ (protective_construct_value × protective_weight × 0.6)
           + uniform_jitter(−3.0, 3.0)      # reproducible seed=42
```

```
stability_score = 100.0 - risk_score + uniform_jitter(−2.0, 2.0)
```

Both scores are clamped to `[0.0, 100.0]`.

### Construct Weights

| Construct | Direction | Max Weight |
|---|---|---|
| Overtime Demand | risk | 15.0 |
| Physical Work Strain | risk | 10.0 |
| Psychological Exhaustion | risk | 12.0 |
| Travel Demand Pressure | risk | 10.0 |
| External Pull / Withdrawal | risk | 8.0 |
| Health Risk Context | risk | 8.0 |
| Compensation Equity | protective | 12.0 |
| Overtime Compensation | protective | 8.0 |
| Promotion Justice | protective | 8.0 |
| Supervisory Support | protective | 10.0 |
| Recognition Resource | protective | 8.0 |
| Training/Career Resource | protective | 6.0 |
| Healthcare Benefit | protective | 5.0 |
| Allowance Benefit | protective | 4.0 |
| Bonus Reward | protective | 4.0 |
| Environment Satisfaction | protective | 8.0 |
| Job Satisfaction | protective | 12.0 |
| Work-Life Balance | protective | 12.0 |
| Emotional Commitment | protective | 10.0 |
| Job Engagement | protective | 8.0 |
| Job Stability Perception | protective | 8.0 |

---

## 6. Risk Bands

| Band | Risk Score Range | Arabic |
|---|---|---|
| Stable | 0–30 | مستقر |
| Monitoring | 30–55 | مراقبة |
| Strategic Concern | 55–75 | قلق استراتيجي |
| Priority Review | 75–100 | مراجعة عاجلة |

---

## 7. Confidence Levels

| Matched Constructs | Confidence |
|---|---|
| ≥ 6 | high |
| 3–5 | medium |
| 0–2 | low |

---

## 8. Recommended HR Review Actions

| Band | Action |
|---|---|
| Stable | Standard quarterly HR check-in |
| Monitoring | HR check-in within 60 days; review workload and growth |
| Strategic Concern | Structured career development discussion within 30 days |
| Priority Review | Confidential HR review within 14 days; multiple indicators require qualified assessment |

---

## 9. Statistical Properties

- Scores use a reproducible random seed (`seed=42`) for stochastic jitter, ensuring identical inputs produce identical outputs
- Scores are **not** calibrated against actual attrition outcomes (no labelled training data required)
- The jitter (±3 pts risk, ±2 pts stability) ensures employees with identical construct profiles receive slightly different scores — reflecting genuine uncertainty rather than false precision
- Aggregate statistics (department averages, band distributions) are stable and meaningful even at small group sizes

---

## 10. Limitations

1. Accuracy depends on the number of recognised construct columns in the dataset
2. Datasets with < 3 matched constructs produce low-confidence scores
3. Scores reflect organisational signals — they do not account for personal circumstances
4. Cultural and regional factors (Saudi workforce norms, Vision 2030 context) are partially captured through the Saudi HR construct mapping but not exhaustively
