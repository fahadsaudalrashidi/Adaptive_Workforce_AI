# Temporal Validation Governance Audit

**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Phase:** 4 — Scientific Governance Integration  
**Document type:** Governance Audit — Temporal Leakage Prevention  
**File:** `backend/core/temporal_validation_guard.py`  
**Audit date:** 2026-05-20  
**Status:** Enforced in production pipeline

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Why Temporal Leakage Is the Most Common Silent Failure in HR ML](#2-why-temporal-leakage-is-the-most-common-silent-failure-in-hr-ml)
3. [The Five Categories of Temporal HR Data](#3-the-five-categories-of-temporal-hr-data)
4. [Finding Type Matrix](#4-finding-type-matrix)
5. [Exit Date Column Taxonomy](#5-exit-date-column-taxonomy)
6. [Hire Date Governance](#6-hire-date-governance)
7. [Split Strategy Decision Tree](#7-split-strategy-decision-tree)
8. [SMOTE Governance](#8-smote-governance)
9. [Preprocessing-Before-Split Governance](#9-preprocessing-before-split-governance)
10. [Integration Point: Guard Position in main.py](#10-integration-point-guard-position-in-mainpy)
11. [Test Coverage](#11-test-coverage)
12. [Known Limitations](#12-known-limitations)
13. [Appendix: TemporalValidationReport Field Reference](#13-appendix-temporalvalidationreport-field-reference)

---

## 1. Executive Summary

The `TemporalValidationGuard` is a Phase 4 governance component that runs a mandatory scan of every dataset before feature engineering begins. It detects four failure modes that collectively invalidate model metrics without raising any Python exception or framework error:

1. **Exit date leakage** — including a post-outcome date (resignation date, termination date, offboarding date) as a model feature. The model learns a trivially perfect signal: employees who have already left have an exit date; employees who have not do not. AUC reaches 0.99 or higher. The feature is meaningless in production.

2. **Unsafe random split** — splitting rows at random when temporal columns are present. A randomly-assigned test row may precede a training row chronologically, allowing the model to learn future states. This is particularly dangerous in longitudinal HR datasets spanning multiple survey periods.

3. **SMOTE before split** — applying synthetic minority oversampling to the full dataset before train/test partition. Synthetic rows generated from real test-set neighbors contaminate the test set. Reported AUC is inflated by an unknown amount. The contamination cannot be removed retroactively.

4. **Preprocessing before split** — fitting a scaler, imputer, or encoder on the entire dataset before splitting. The test set statistics (mean, standard deviation, quantile anchors) leak into training. The model sees a slightly different distribution at inference time than was measured during evaluation.

All four failure modes are silent. No framework raises a warning. The pipeline completes successfully. The metrics look excellent. The production model underperforms because it was evaluated under conditions that cannot exist in deployment.

The guard is invoked in `backend/api/main.py` **before** `factory.engineer()` and returns a `TemporalValidationReport`. It does not modify data, block training, or raise exceptions. The caller decides the action. For any CRITICAL finding, the pipeline logs a warning and the finding is recorded in the audit trail.

---

## 2. Why Temporal Leakage Is the Most Common Silent Failure in HR ML

HR datasets are unusual among tabular ML datasets because they record the lifecycle of an event — employment — that has a natural start, middle, and end. Every column in an HR export is anchored to a specific moment in time:

- The employee's **hire date** is a past anchor.
- The employee's **performance rating** reflects a specific review period.
- The employee's **attrition outcome** (the target variable) is a future event relative to the features.

When this structure is ignored during modeling, the model receives information about the future while being evaluated on whether it can predict the future. The result is a model that appears to generalize but does not.

**The three mechanisms of temporal leakage in HR:**

**Mechanism 1: Direct outcome encoding.** An exit date column is included as a feature. The date only exists for employees who left. For employees who stayed, the field is null. The model learns: `if exit_date is not null: predict attrition`. AUC becomes 0.99+. The feature is useless in deployment because the exit date does not exist for active employees at prediction time.

**Mechanism 2: Distributional contamination.** A scaler fitted on the full dataset computes the mean salary as SAR 14,250. In reality, the training-set mean is SAR 13,900 and the test-set mean is SAR 15,100. By using the combined mean, the scaler shifts both distributions toward each other, making the model appear more stable than it is. In production, the scaler is re-fitted on whatever data is available, producing a different shift. Performance degrades.

**Mechanism 3: Chronological ordering violations.** In a dataset spanning three annual survey waves (2021, 2022, 2023), a random 80/20 split places 20% of 2021 rows in the test set and 20% of 2023 rows in training. The model can learn patterns that incorporate 2023 behaviors to predict 2021 attrition. This produces optimistic evaluation results that do not replicate when the model is deployed to score the 2024 wave.

The `TemporalValidationGuard` catches all three mechanisms via name-based pattern matching, dtype detection, and configuration flag inspection.

---

## 3. The Five Categories of Temporal HR Data

| Category | Risk Level | Description | Guard Response |
|---|---|---|---|
| **EXIT_DATE** | CRITICAL / HIGH | Post-outcome dates that only exist after an employee leaves (resignation date, termination date, last working day, separation date, offboarding date). Including these as features causes direct target leakage. | CRITICAL if in `feature_names`; HIGH if only in `df.columns`. Random split marked UNSAFE. `time_based` strategy required. |
| **HIRE_DATE** | MEDIUM | Employment start dates that can proxy tenure but are not inherently leakage unless used without a fixed snapshot anchor. Raw hire dates encode the employee's age-at-hire and may carry temporal ordering signals in longitudinal data. | MEDIUM finding. Random split allowed cautiously if no exit/generic date columns are present. Recommendation: derive tenure as `(snapshot_date - hire_date).days / 365`. |
| **GENERIC_DATE** | MEDIUM / HIGH | Any column whose name or dtype indicates date or time information: columns ending in `_date`, `_dt`, `_time`, `_month`, `_year`; columns with `datetime64` dtype detected by dtype sniffing. | MEDIUM if name-matched; HIGH if dtype-detected and in `feature_names`. Random split marked UNSAFE. `time_based` strategy recommended. |
| **SNAPSHOT** | INFO | Data collection anchors: `survey_date`, `snapshot_date`, `as_of_date`, `report_date`, `extraction_date`. Safe when all rows share a single snapshot date; dangerous when rows span multiple periods. | INFO finding only. No split strategy change unless combined with other categories. Recommendation: verify all training rows share one snapshot date. |
| **PREPROCESSING_LEAK** | MEDIUM | Column names that contain `_scaled`, `_imputed`, `_encoded`, `_norm`, `_normalised`, `_std`, `_zscore`, indicating a transformation was applied to the full dataset before splitting. | MEDIUM finding. Column is flagged but not blocked (ModelInputContract handles blocking). Recommendation: move all transformers inside CV folds. |

---

## 4. Finding Type Matrix

| Finding Type | Severity | Blocks Training? | Trigger Condition | Recommendation |
|---|---|---|---|---|
| `EXIT_DATE` | CRITICAL | No — guard does not block | Column name matches any exit date pattern AND column is in `feature_names` | Remove from feature set immediately. Use only to define the train/test split boundary. |
| `EXIT_DATE` | HIGH | No | Column name matches exit date pattern AND column is in `df.columns` only (not in features) | Verify the column is not inadvertently entering features through downstream merges. |
| `HIRE_DATE` | MEDIUM | No | Column name matches hire/start date pattern | Replace with derived tenure feature anchored to a fixed snapshot date. |
| `GENERIC_DATE` | MEDIUM | No | Column name contains `_date`, `_dt`, `_time`, `_month`, `_year`, `snapshot_`, `period`, `fiscal_` | Convert to derived duration or cyclical feature. Review split strategy. |
| `GENERIC_DATE` | HIGH | No | Column has `datetime64` dtype (dtype sniff) AND is in `feature_names` | Extract duration features. Use time-based split. |
| `SNAPSHOT` | INFO | No | Column name matches snapshot/report date pattern | Verify single snapshot date per training cohort. |
| `PREPROCESSING_LEAK` | MEDIUM | No | Column in `feature_names` has `_scaled`, `_imputed`, `_encoded`, `_norm`, `_normalised`, `_std`, `_zscore` in name | Move all transformers inside CV folds or after train/test split. |
| `SMOTE_BEFORE_SPLIT` | CRITICAL | No | `smote_before_split=True` passed to `validate()` | Apply SMOTE inside imbalanced-learn Pipeline, inside CV folds only. Test set must never contain SMOTE rows. |
| `PREPROCESSING_BEFORE_SPLIT` | CRITICAL | No | `preprocessing_before_split=True` passed to `validate()` | Fit transformers on training fold only. Apply (do not refit) on test fold. |

**Important:** The guard returns findings and sets `has_temporal_risk`; it does not raise exceptions or stop training. Responsibility for acting on findings rests with the calling code in `main.py`. All findings are logged and included in the `TemporalValidationReport`.

---

## 5. Exit Date Column Taxonomy

The guard maintains an explicit list of post-outcome date patterns. A column is classified as `EXIT_DATE` if any of the following substrings appear in its lowercased name:

```
exit_date          exitdate
resignation_date   resignationdate    resigned_date
last_day           lastday
last_working_day   lastworkingday
offboarding_date   offboardingdate
termination_date   terminationdate
end_date           enddate
final_status_date
departure_date     deparaturedate
separation_date    separationdate
leave_date         leavedate
employment_end     employmentend
```

**Why these are always leakage:**

Each of these fields is populated only after the outcome has occurred. For an active employee being scored for attrition risk, none of these fields will have a value — because the employee has not yet left. A model trained on a dataset where this column exists for some rows and is null for others learns a trivially perfect rule. It will assign near-zero attrition probability to any active employee at inference time, regardless of their actual risk factors, because no exit date exists.

**The only legitimate use of exit date columns** is to define the chronological boundary of the train/test split. For example: employees with `exit_date < 2023-01-01` form the training cohort; employees active as of `2023-01-01` form the evaluation cohort. The exit date is used to construct the split, not as a model input.

**Column naming note:** The guard detects both underscore-separated (`exit_date`) and concatenated (`exitdate`) forms. It also detects partial matches (`resignation_date` matches because `resignation_date` is in the pattern list). A column named `reason_for_resignation` would not match this list but would be caught by `PROXY_LEAKAGE_KEYWORDS` in `ModelInputContract`.

---

## 6. Hire Date Governance

### When hire date derivation is CORRECT

Tenure is a legitimate feature. The correct derivation is:

```python
tenure_years = (snapshot_date - hire_date).days / 365.25
```

Where `snapshot_date` is the **same fixed date for all training rows** — typically the date of the data extract or the end of the reporting period. This derivation is correct because:

- All employees are measured relative to the same point in time.
- The resulting feature is a scalar (years of tenure) with no temporal ordering information.
- The feature will have the same meaning at inference time as it did at training time.

### When hire date derivation is INCORRECT

Hire date derivation is incorrect when:

1. **`snapshot_date` varies across rows.** If each row records its own `snapshot_date` (e.g., the survey date for that individual), tenure is calculated differently for each employee. Employees in the same dataset are measured at different calendar times, and the training/test split may inadvertently place future observations in training.

2. **The raw hire date is used directly as a numeric feature.** Most ML frameworks encode dates as Unix timestamps or ordinal integers. A hire date of 2019-03-15 encoded as an integer encodes temporal ordering. If employee 1 was hired before employee 2, the model can learn directional patterns based on cohort effects that may not hold in the future.

3. **Hire date is used without controlling for dataset-wide time span.** In a dataset collected over five years, a hire date of 2015 and a hire date of 2020 carry very different meanings depending on when the data was collected.

### Guard behavior for hire dates

The guard raises a MEDIUM finding for any column matching hire date patterns. Random split is still allowed (with caution) if no exit date or generic date columns are present. The recommended strategy becomes `stratified_time`. The governance note reads:

> HIRE DATE COLUMNS: [list]. Convert to tenure duration features anchored to a fixed snapshot date before use.

---

## 7. Split Strategy Decision Tree

The guard produces a `SplitSafetyAssessment` with three fields: `random_split_safe`, `reason`, and `recommended_strategy`.

```
START
  │
  ├─ EXIT date columns detected?
  │       YES → random_split_safe = False
  │              recommended_strategy = "time_based"
  │              reason: "Post-outcome date columns present. Temporal ordering violated."
  │
  ├─ GENERIC date columns detected (but no exit columns)?
  │       YES → random_split_safe = False
  │              recommended_strategy = "time_based"
  │              reason: "Date columns detected. Random split may violate ordering."
  │
  ├─ HIRE date columns present ONLY (no exit, no generic date)?
  │       YES → random_split_safe = True (cautious)
  │              recommended_strategy = "stratified_time"
  │              reason: "Hire date present but no exit/generic dates. Random split acceptable
  │                        if all rows share one snapshot date; otherwise use time-based."
  │
  └─ No temporal columns detected
          → random_split_safe = True
             recommended_strategy = "random"
             reason: "No temporal columns detected. Random split is acceptable."
```

**Strategy definitions:**

- **`random`** — Standard train/test split using `sklearn.model_selection.train_test_split` with shuffle. Appropriate when no temporal columns are present and the dataset is a single cross-sectional snapshot.

- **`stratified_time`** — Split that preserves the distribution of the temporal variable across folds. Appropriate when hire dates are present but all rows share a single data collection snapshot. Implemented via stratified sampling on a time-period bucket.

- **`time_based`** — Chronological split where all training observations precede all test observations. Appropriate when exit dates or generic date columns are present. In HR attrition: all employees who left before date X are training; all employees active after date X are test. Implemented via `sklearn.model_selection.TimeSeriesSplit` or a manual date-based filter.

---

## 8. SMOTE Governance

### Why SMOTE before split invalidates all metrics

SMOTE (Synthetic Minority Oversampling Technique) generates synthetic training samples by interpolating between real minority-class observations in feature space. When SMOTE is applied to the **full dataset** before the train/test split, the following contamination occurs:

1. SMOTE generates synthetic minority-class rows by interpolating between **real test-set rows** and other minority rows.
2. The synthetic rows are distributed across training and test sets by the subsequent random split.
3. The test set now contains rows that are linear combinations of other rows already in training.
4. The model can effectively memorize these synthetic test rows by learning the interpolation manifold.
5. AUC is inflated. The magnitude of inflation depends on the minority class ratio and the SMOTE interpolation distance.

**Example inflation scenario:**

```
True AUC (correctly applied SMOTE):   0.74
AUC with SMOTE before split:          0.83

Difference: +9 AUC points
All metrics computed on this pipeline are invalid.
```

The contamination cannot be detected after the fact. If SMOTE was applied before the split, the only remediation is to re-run the entire pipeline.

### Correct SMOTE governance

SMOTE must be applied **inside cross-validation folds only**, using an `imbalanced-learn` Pipeline:

```python
from imblearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

pipeline = Pipeline([
    ("smote", SMOTE(random_state=42, sampling_strategy="auto")),
    ("model", RandomForestClassifier()),
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="roc_auc")
# SMOTE runs inside each fold. The held-out fold is never resampled.
```

**The test set must never contain SMOTE-generated rows.** The final held-out test set (the 20% not used in CV) must be evaluated against the model fitted on SMOTE-augmented training folds, with no SMOTE applied to the test set itself.

### Guard behavior

The guard raises an unconditional CRITICAL finding when `smote_before_split=True`:

```
column_name: "SMOTE_PIPELINE"
finding_type: "SMOTE_BEFORE_SPLIT"
severity: "CRITICAL"
reason: "SMOTE is being applied BEFORE train/test split. This leaks synthetic minority
         samples into the test set, causing AUC inflation and invalid evaluation metrics."
recommendation: "Apply SMOTE INSIDE cross-validation folds only, using an
                 imbalanced-learn Pipeline."
```

---

## 9. Preprocessing-Before-Split Governance

### What pre-split preprocessing leaks

When a scaler (e.g., `StandardScaler`, `MinMaxScaler`) or imputer (e.g., `SimpleImputer`) is fitted on the full dataset before splitting:

| Statistic leaked | Effect |
|---|---|
| **Mean (per feature)** | Training mean is pulled toward test-set mean. The model assumes a slightly different distribution than it will encounter in production. |
| **Standard deviation** | Scaling factors computed on full data compress or expand features relative to what a training-only fit would produce. |
| **Quantiles (median imputer, quantile scaler)** | Quantile anchors derived from test-set distribution are used to transform training data. |
| **Category frequencies (OrdinalEncoder, TargetEncoder)** | Categories that only appear in the test set get encodings derived from their test-set frequency, which is future information. |

**The magnitude of contamination** depends on how different the training and test distributions are. For large datasets with stable distributions, the contamination is small but non-zero. For small HR datasets (n < 500) or datasets with significant temporal trends, the contamination can shift AUC by 2–5 points.

### Correct preprocessing governance

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
    ("model", RandomForestClassifier()),
])

pipeline.fit(X_train, y_train)      # Scaler fitted on training fold ONLY
y_pred = pipeline.predict(X_test)  # Scaler applied (not refitted) on test fold
```

The key constraint: `.fit()` is called only on `X_train`. The `.transform()` applied to `X_test` uses statistics computed from `X_train` only.

### Guard behavior

The guard raises an unconditional CRITICAL finding when `preprocessing_before_split=True`:

```
column_name: "PREPROCESSING_PIPELINE"
finding_type: "PREPROCESSING_BEFORE_SPLIT"
severity: "CRITICAL"
reason: "Scaling, imputation, or encoding applied to the full dataset BEFORE train/test
         split. This leaks test set statistics (mean, std, quantiles) into training,
         inflating performance metrics."
recommendation: "Fit all transformers on training fold ONLY. Use sklearn Pipeline or
                 ColumnTransformer inside CV."
```

---

## 10. Integration Point: Guard Position in main.py

The `TemporalValidationGuard` is called in `backend/api/main.py` within the `analyse` endpoint, **after** the DataHealer and Theory Engine have run but **before** `factory.engineer()`:

```python
# backend/api/main.py  (lines 231–244 — Phase 4 integration)

# ── Temporal validation ─────────────────────────────────────────────────────
_temp_guard = TemporalValidationGuard()
_temp_report = _temp_guard.validate(
    feature_names=[c for c in df_theory.columns if c != target],
    df=df_theory,
    target_col=target,
)
if not _temp_report.random_split_safe:
    logger.warning("TemporalValidationGuard: %s", _temp_report.summary)

df_eng, manifest = _factory.engineer(
    df_theory, sem_map, decision.dataset_type, target,
)
```

**Why this position matters:**

- The guard runs on `df_theory` — the DataFrame after theory-grounded constructs have been added by `compute_constructs()`. This means the guard also scans for any temporal leakage introduced by construct computation, not just raw columns.
- The guard runs before `factory.engineer()`, ensuring that the feature engineering step does not inherit columns that carry temporal leakage.
- The guard does not modify `df_theory`. It only produces a report. The `_factory.engineer()` call proceeds regardless of findings. The finding is recorded in the log for audit purposes.
- After `factory.engineer()`, the `ModelInputContract` performs a second validation layer that blocks legacy and leakage-flagged features from entering the ML model. The temporal guard and the model input contract are complementary, not redundant.

**Pipeline order in `analyse` endpoint:**

```
1. DataHealer.fit_transform()          — data cleaning
2. TheoryAwareColumnMapper.map()       — Phase 1 column mapping
3. compute_constructs()                — Phase 2 construct computation
4. TemporalValidationGuard.validate()  — THIS DOCUMENT (Phase 4)
5. FeatureFactory.engineer()           — feature engineering
6. ModelInputContract.validate()       — feature set governance
7. MLRouter.train()                    — model training
```

---

## 11. Test Coverage

The Phase 4 integration test suite (`tests/test_phase4_integration.py`) includes 11 tests dedicated to `TemporalValidationGuard`, grouped in `TestTemporalValidationGuard`. The tests are listed below with a description of what each verifies:

| # | Test name | What it verifies |
|---|---|---|
| 1 | `test_exit_date_column_detected` | An `exit_date` column in `feature_names` appears in `report.exit_date_columns` and `report.has_temporal_risk` is True. |
| 2 | `test_random_split_unsafe_with_exit_dates` | When `termination_date` is in features, `report.random_split_safe` is False and recommended strategy is `"time_based"`. |
| 3 | `test_random_split_safe_for_clean_features` | A clean feature set (Age, MonthlyIncome, JobLevel, etc.) with no date columns produces `random_split_safe=True`. |
| 4 | `test_smote_before_split_is_critical` | When `smote_before_split=True`, at least one CRITICAL finding exists and exactly one `SMOTE_BEFORE_SPLIT` finding is present. |
| 5 | `test_preprocessing_before_split_is_critical` | When `preprocessing_before_split=True`, at least one CRITICAL finding exists and exactly one `PREPROCESSING_BEFORE_SPLIT` finding is present. |
| 6 | `test_hire_date_generates_medium_finding` | `hire_date` in features produces a HIRE_DATE finding with severity MEDIUM and the column appears in `report.hire_date_columns`. |
| 7 | `test_last_working_day_is_exit_date` | `last_working_day` is correctly classified as an exit date and `random_split_safe` is False. |
| 8 | `test_resignation_date_is_exit_date` | `resignation_date` is correctly classified as an exit date and appears in `report.exit_date_columns`. |
| 9 | `test_convenience_function` | `validate_temporal_safety()` wrapper returns a report with `random_split_safe=True` for a clean feature set. |
| 10 | `test_is_random_split_safe_helper` | The `TemporalValidationGuard.is_random_split_safe()` helper returns True for a clean feature set. |
| 11 | `test_get_exit_date_columns_helper` | `get_exit_date_columns()` correctly identifies `exit_date` and `termination_date` but not `Age` or `MonthlyIncome` from a mixed list. |

All 11 tests pass in the Phase 4 suite. The full test suite (243 tests across 10 files) passes with zero failures.

---

## 12. Known Limitations

The `TemporalValidationGuard` is a static analysis tool. It has the following documented limitations:

### 12.1 Name-based detection only

The guard matches column names against pattern lists. A date column named `snapshot_q3_2023` would be detected (matches `_q3` via `_year` pattern, and `snapshot_` explicitly). However, a date column named `survey_wave` or `cohort_identifier` would not be detected, because neither name matches any pattern in the four pattern lists.

**Consequence:** Custom enterprise column naming conventions may use non-standard date identifiers that bypass detection.

**Mitigation:** The ModelInputContract provides a second layer of governance via `PROXY_LEAKAGE_KEYWORDS`. HR data engineers should review the pattern lists and extend them to match their organization's naming conventions.

### 12.2 Datetime dtype sniffing only for pandas types

The guard calls `df.select_dtypes(include=["datetime", "datetime64"])` to detect datetime columns by dtype. This works for columns that are loaded as `datetime64[ns]` by pandas. It does not detect:

- Date columns stored as strings (e.g., `"2023-03-15"` in an object-dtype column)
- Date columns stored as integers (Unix timestamps, Excel serial dates)
- Date columns stored as floats (fractional Unix timestamps)

**Consequence:** A date column stored as a string or integer will not be detected by the dtype sniff path. It may still be detected by the name-based path if the column name matches a pattern.

**Mitigation:** The DataHealer (`backend/core/data_healer.py`) attempts to parse and recast string date columns as `datetime64` before the guard runs. If the DataHealer successfully parses a string date column, it will be detected by the guard's dtype sniff path.

### 12.3 Cannot detect in-memory operations

The guard cannot detect:

- SMOTE or preprocessing applied before the `validate()` call in Python code that does not set `smote_before_split=True` or `preprocessing_before_split=True`.
- Leakage introduced by feature engineering functions that read from external data sources.
- Leakage introduced by feature interactions computed before the guard call but after data loading.

**Consequence:** If a caller applies SMOTE before calling `validate()` but does not set `smote_before_split=True`, the guard will not detect it.

**Mitigation:** The `smote_before_split` and `preprocessing_before_split` flags are caller-declared. The audit trail produced by the ModelInputContract includes the scientific feature mode and the list of disabled constructs, providing a partial audit of the preprocessing sequence.

### 12.4 Guard does not block — it advises

The guard never raises an exception, sets a flag that stops training, or modifies the DataFrame. It is a reporting tool. If the calling code in `main.py` ignores the findings, the model trains with the leaking features.

**Current behavior in main.py:** A WARNING is logged if `random_split_safe=False`. The pipeline proceeds. No HTTP error is returned to the API caller.

**Recommended enhancement:** For CRITICAL findings (exit date in features), the API should return a 422 Unprocessable Entity response rather than proceeding with training. This enhancement is tracked as a governance gap.

---

## 13. Appendix: TemporalValidationReport Field Reference

```python
@dataclass
class TemporalValidationReport:
    has_temporal_risk: bool          # True if any CRITICAL/HIGH finding or exit date present
    random_split_safe: bool          # True if random split is acceptable
    n_critical: int                  # Count of CRITICAL findings
    n_high: int                      # Count of HIGH findings
    n_medium: int                    # Count of MEDIUM findings
    n_info: int                      # Count of INFO findings
    findings: List[TemporalFinding]  # Full finding list
    split_assessment: SplitSafetyAssessment
    preprocessing_leak_columns: List[str]
    exit_date_columns: List[str]
    hire_date_columns: List[str]
    generic_date_columns: List[str]
    snapshot_columns: List[str]
    summary: str                     # Human-readable one-line summary
    governance_notes: List[str]      # Detailed governance notes for audit log

@dataclass
class SplitSafetyAssessment:
    random_split_safe: bool
    reason: str
    recommended_strategy: str        # "random" / "time_based" / "stratified_time"
    temporal_columns_detected: List[str]
    exit_columns_detected: List[str]
    hire_columns_detected: List[str]

@dataclass
class TemporalFinding:
    column_name: str
    finding_type: str   # EXIT_DATE / HIRE_DATE / GENERIC_DATE / SNAPSHOT /
                        # PREPROCESSING_LEAK / SMOTE_BEFORE_SPLIT /
                        # PREPROCESSING_BEFORE_SPLIT
    severity: str       # CRITICAL / HIGH / MEDIUM / INFO
    reason: str
    recommendation: str
```

---

*This document is part of the Phase 4 Scientific Governance Audit for the Adaptive Workforce Intelligence Engine v2.5.1. It covers only the temporal validation component. For the full scientific traceability chain, see `SCIENTIFIC_TRACEABILITY_AUDIT.md`.*
