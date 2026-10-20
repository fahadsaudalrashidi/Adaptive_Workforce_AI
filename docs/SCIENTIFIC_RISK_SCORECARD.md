# Phase 3 Scientific Risk Scorecard
## Adaptive Workforce AI — HR Attrition Prediction Platform
### Saudi HR Deployment Authorization & Academic Publication Readiness Assessment

**Assessment Date:** 2026-05-20
**Assessment Phase:** Phase 3 (Post-Phase 2 Engine Implementation, Pre-Integration)
**Audience:** Scientific Governance Board
**Purpose:** Honest evaluation of current deployed state for production authorization and academic defensibility

> **Critical Context:** Phase 2 (`theory_grounded_construct_engine.py`) exists and implements correct paper formulas but is NOT yet integrated into the ML pipeline. The ML pipeline currently runs the OLD `feature_factory.py` path. All scores reflect the **actually deployed state** unless otherwise noted.

---

## Score 1: Theory Integrity Score

**Score: 45 / 100 — HIGH CONCERN**

### What Was Assessed
This score evaluates whether the seven psychological constructs (drawn from COR, JD-R, FFM, and Mobley theory) are implemented using exact paper formulas, free from normalization distortion, and free from invented or unsupported constructs. The assessment covers both computation paths and weights the currently active path (feature_factory.py) as the operative baseline.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| Exact paper formula implementation (active path) | 25 | 5 | feature_factory.py uses wrong/invented formulas |
| No normalization applied before formula computation | 15 | 2 | _norm() called before all formulas in OLD path |
| No invented constructs present in active path | 15 | 3 | RetentionRisk, PresenteeismSignal lack theory anchors |
| Phase 2 engine formula correctness (exists, not deployed) | 20 | 16 | Exact formulas implemented; credit discounted for non-deployment |
| Evidence hierarchy enforcement (Phase 1 mapper) | 10 | 8 | Correct hierarchy present; blocked TARGET_ADJACENT |
| Construct coverage completeness (all 7 constructs) | 15 | 11 | Phase 2 covers all 7; OLD path has partial/wrong coverage |

### What Is Working
- Phase 2 `theory_grounded_construct_engine.py` implements exact paper formulas for all 7 constructs
- Phase 1 mapper enforces a documented evidence hierarchy and performs scale validation
- Phase 2 correctly blocks weak proxies and refuses leakage-flagged columns
- No normalization is applied before formula computation in the Phase 2 engine
- THEORY_COMPATIBLE_PROXY vs DIRECT_PAPER_REPLICATION distinction is encoded in Phase 2

### What Is Not Working
- The ML pipeline currently runs `feature_factory.py`, which applies `_norm()` before all construct formulas, invalidating the theoretical grounding of every output
- `feature_factory.py` contains invented constructs (RetentionRisk, PresenteeismSignal) with no peer-reviewed anchors
- The BurnoutRiskComposite formula in the OLD path does not match any published JD-R operationalization
- The SatisfactionIndex in the OLD path uses a formula inconsistent with Hackman-Oldham or Locke-derived operationalizations
- No automatic runtime flag alerts users or governance board when the OLD path is active
- Phase 2 engine exists on disk but produces zero impact on actual ML predictions

### Required for Score >= 70
- Complete Phase 3 integration: replace `feature_factory.py` as the active construct computation path with `theory_grounded_construct_engine.py`
- Add a runtime guard that raises a hard error if `feature_factory.py` is invoked for construct computation during model training or inference
- Document which published paper each formula is drawn from, with equation number and page reference, in code comments
- Remove or clearly quarantine RetentionRisk and PresenteeismSignal from the active feature set

### Required for Score >= 90
- Independent formula audit by a researcher not involved in implementation, comparing code against original papers
- Pre-registration of construct operationalizations on OSF or similar registry before Saudi data collection
- Automated unit tests asserting formula outputs match paper-reported example values (where available)
- Version-controlled construct specification document cross-referenced to code

---

## Score 2: Psychometric Reliability Score

**Score: 42 / 100 — HIGH CONCERN**

### What Was Assessed
This score evaluates whether the scales feeding into construct computation are validated, directionally consistent, and psychometrically appropriate for the population and dataset in use. It covers internal consistency, construct validity, and scale-level appropriateness for both the IBM HR training dataset and anticipated Saudi HR deployment data.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| WLB directionality verified for BurnoutRisk formula | 15 | 3 | Direction unverified; risk of inverted burnout signal |
| PerformanceRating floor effect addressed | 10 | 1 | IBM HR values only 3–4; massive range compression, unmitigated |
| JobInvolvement vs EmployeeEngagement conflation avoided | 10 | 5 | Partial: Phase 1 maps both, but conflation risk unresolved |
| Cronbach alpha validation for Saudi survey scales | 20 | 0 | No internal consistency validation present |
| Factor analysis for Saudi population construct validity | 20 | 0 | No confirmatory or exploratory factor analysis performed |
| Distribution shape validation present | 10 | 7 | Phase 1 scale validation checks distribution shape |
| Response scale anchor documentation | 15 | 8 | IBM HR scale anchors documented; Saudi anchors unverified |

### What Is Working
- Phase 1 mapper performs distribution shape validation for scale inputs
- Scale validation thresholds are calibrated for SAR salary values
- IBM HR scale anchors are known and partially documented
- Arabic/bilingual column mapping is implemented, supporting bilingual scale handling

### What Is Not Working
- Work-life balance (WLB) item direction in the BurnoutRisk formula has not been empirically verified; if the item is reverse-keyed and not corrected, BurnoutRisk outputs are directionally inverted
- PerformanceRating in IBM HR has a catastrophic floor effect (only values 3 and 4 present out of a nominal 1–5 scale), rendering it statistically unusable as a continuous predictor without transformation
- No Cronbach alpha has been computed for any scale composite used in construct computation, for either IBM HR or Saudi data
- No factor analysis has been conducted to confirm that items load onto intended constructs for a Saudi population
- JobInvolvement and EmployeeEngagement are psychometrically distinct constructs (Schaufeli et al., 2002) and conflating them in Saudi survey instruments would invalidate EngagementScore
- Scale validation in Phase 1 tests distribution shape only, which detects outliers but does not assess internal consistency or construct validity

### Required for Score >= 70
- Empirically verify WLB item polarity in the active dataset and apply reverse-scoring if necessary before BurnoutRisk computation
- Apply a documented transformation or binning strategy to PerformanceRating to mitigate floor effects, or exclude it from construct formulas with explicit justification
- Compute Cronbach alpha (target alpha >= 0.70) for each multi-item scale used in construct computation
- Document the distinction between JobInvolvement and EmployeeEngagement in the column mapping specification

### Required for Score >= 90
- Conduct confirmatory factor analysis (CFA) on Saudi pilot data to verify construct structure before full deployment
- Publish internal consistency statistics (alpha, omega) as supplementary material in any academic submission
- Establish measurement invariance across Saudi government and private sector subgroups using multi-group CFA
- Independent psychometrician review of all scale operationalizations

---

## Score 3: Leakage Safety Score

**Score: 58 / 100 — CONDITIONAL**

### What Was Assessed
This score evaluates the platform's defenses against data leakage, including proxy leakage, identifier memorization, target-adjacent feature inclusion, and temporal leakage from non-sequential train/test splitting. Both the detection infrastructure and residual leakage risks in the active computation path are assessed.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| Automated leakage detection infrastructure | 20 | 16 | 14-check LeakageDetector is robust |
| TARGET_ADJACENT evidence blocked in Phase 1 mapper | 10 | 9 | Correctly blocks in Phase 1 |
| Phase 2 engine refuses leakage-flagged columns | 10 | 9 | Correctly refuses in Phase 2 |
| AUC governance caps enforced | 10 | 8 | 0.65 CRITICAL cap, 0.75 two-HIGH cap — well-designed |
| RetentionRisk excluded from active feature set | 15 | 2 | RetentionRisk computed and included as feature in OLD path |
| EmployeeStabilityRisk borderline status addressed | 10 | 4 | Named construct is borderline; no formal ruling documented |
| Temporal validation (time-based split) implemented | 15 | 0 | Random split used; no temporal guard exists |
| Absence/behavioral withdrawal features flagged | 10 | 5 | Partial recognition; no formal pre-exit behavioral screen |

### What Is Working
- The 14-check `LeakageDetector` covers proxy keywords, ID memorization, target correlation, and multiple other leakage vectors — this is a genuine engineering strength
- Phase 1 mapper correctly identifies and blocks TARGET_ADJACENT evidence category
- Phase 2 engine refuses to compute constructs using leakage-flagged columns
- AUC caps (0.65 for CRITICAL flags, 0.75 for 2+ HIGH flags) provide governance-level enforcement
- `LeakageReport.summary` discloses flag counts and categories

### What Is Not Working
- `feature_factory.py` (the active path) computes `RetentionRisk` — a construct semantically adjacent to the attrition target — and adds it as a model feature, creating near-certain label leakage
- `EmployeeStabilityRisk` is a borderline target-adjacent construct; no formal classification decision has been documented in the governance record
- Train/test splitting uses random sampling, which violates temporal ordering. Employees who left later in the observation period may have behavioral signals (absence, engagement decline) in the training set that predict their own attrition in the test set
- Absence features and `PresenteeismSignal` may capture behavioral withdrawal occurring in the weeks before resignation — without a temporal cutoff window, these features leak future attrition signals into the training data
- No minimum time gap is enforced between the feature observation window and the attrition event label

### Required for Score >= 70
- Remove `RetentionRisk` from the active feature set and document the exclusion decision in the governance log
- Implement time-based train/test splitting (earliest N% of hire cohort as training, remainder as test) or leave-one-period-out cross-validation
- Formally classify `EmployeeStabilityRisk` as either safe or target-adjacent in the governance record with justification
- Apply a minimum 90-day lag between the feature observation window and the attrition event label for behavioral features

### Required for Score >= 90
- Conduct a full temporal leakage audit using survival analysis framing, verifying no feature is computed from data post-dating the prediction point
- Pre-register the leakage detection protocol and AUC governance thresholds before Saudi data collection
- Implement automated rejection of training runs that do not use temporal splitting

---

## Score 4: Saudi Transferability Score

**Score: 38 / 100 — HIGH CONCERN**

### What Was Assessed
This score evaluates the platform's readiness for deployment in Saudi Arabian organizational contexts. It covers domain shift from the IBM HR training dataset, cultural measurement validity, sector-specific dynamics unique to the Saudi labor market, and the applicability of Western-validated psychological theories to Saudi employees.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| Training data matches Saudi HR population | 20 | 1 | IBM HR is US synthetic, 1,470 employees — maximum domain shift |
| Saudi construct validity studies cited | 15 | 0 | No Saudi-specific validation literature referenced |
| Cultural measurement invariance verified | 15 | 0 | Arabic synonyms implemented but invariance unverified |
| Government vs private sector distinction handled | 15 | 2 | Conflation unaddressed; attrition dynamics are fundamentally different |
| Vision 2030 labor market dynamics modeled | 10 | 0 | Not modeled; Saudization quotas and nationalization effects ignored |
| Salary in SAR handled correctly | 5 | 5 | Scale validation threshold correctly calibrated for SAR |
| Arabic/bilingual column mapping implemented | 10 | 8 | Implemented and functional |
| Saudi naming conventions handled | 10 | 8 | Handled appropriately |

### What Is Working
- SAR salary scale validation thresholds are correctly set
- Arabic and bilingual column mapping is implemented
- Saudi naming conventions in HR data are handled
- The architecture is designed to accept Saudi HR data inputs

### What Is Not Working
- The model is trained exclusively on IBM HR Analytics data (US-origin, synthetic, 1,470 employees). Applying this model to Saudi employees constitutes a domain shift of the highest severity — different organizational cultures, regulatory environments, labor market structures, and workforce demographics
- None of the seven construct theories (COR, JD-R, FFM, Mobley) have been validated with Saudi employee populations in the referenced evidence base; all validation studies originate from Western samples
- Arabic synonym support enables column name matching but does not establish that the underlying constructs are measured equivalently in Arabic-language survey instruments
- Government sector attrition in Saudi Arabia is governed by civil service regulations, pension incentives, and Saudization mandates that have no equivalent in IBM HR data; private sector attrition is driven by Vision 2030 opportunity shifts — these are categorically different phenomena
- Vision 2030 labor market dynamics (rapid nationalization, new sector growth, female workforce participation changes) are not captured in any construct or feature
- No minimum Saudi sample size gate exists to prevent deployment on datasets too small for reliable inference

### Required for Score >= 70
- Collect a pilot Saudi HR dataset (minimum 500 employees, both sectors) and conduct descriptive validity checks before any model deployment
- Cite and incorporate at least one Saudi-specific organizational behavior study into the construct validity documentation
- Add a hard deployment gate requiring at least N Saudi HR records (recommend N >= 300) before inference is permitted
- Formally separate government and private sector employees into distinct model pipelines or add sector as a mandatory stratification variable

### Required for Score >= 90
- Conduct full cross-cultural measurement invariance testing (configural, metric, scalar) comparing IBM HR constructs against Saudi pilot data
- Commission or cite peer-reviewed construct validity studies for COR, JD-R, and Mobley theory in Gulf Cooperation Council (GCC) organizational contexts
- Re-train or fine-tune the model on Saudi HR data before any production deployment
- Model Vision 2030 labor market effects explicitly, either as covariates or as a separate risk factor module

---

## Score 5: Construct Defensibility Score

**Score: 35 / 100 — HIGH CONCERN**

### What Was Assessed
This score evaluates whether each of the seven psychological constructs can be defended before an academic audience and in peer review, given the operationalizations actually active in the deployed ML pipeline. Phase 2 engine construct defensibility is assessed separately and noted for comparison, but the current deployed state drives the primary score.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| SatisfactionIndex defensible in active path | 12 | 2 | OLD formula is incorrect; Phase 2 version is defensible |
| BurnoutRisk defensible in active path | 12 | 2 | OLD formula deviates from JD-R; WLB direction unverified even in Phase 2 |
| EngagementScore defensible in active path | 12 | 3 | Phase 2 version defensible; OLD path conflates constructs |
| TenureRatio defensible | 10 | 8 | Defensible in both paths; straightforward ratio |
| IncomePerLevel defensible | 10 | 6 | Ordinal-to-interval denominator assumption requires documentation |
| CareerProgression defensible | 12 | 9 | Defensible in Phase 2; less clear in OLD path |
| SalaryGrowth defensible | 10 | 7 | Defensible if PercentSalaryHike is confirmed as percentage |
| RetentionRisk excluded (invented construct) | 12 | 1 | Computed and included in OLD path; no theory anchor |
| PresenteeismSignal excluded (no anchor) | 10 | 1 | Active in OLD path; no peer-reviewed theory anchor |

### What Is Working
- Phase 2 `SatisfactionIndex`: directly grounded in published satisfaction theory, defensible
- Phase 2 `EngagementScore`: grounded in Schaufeli/Bakker JD-R engagement operationalization, defensible
- Phase 2 `TenureRatio`: straightforward ratio, broadly defensible across frameworks
- Phase 2 `CareerProgression`: defensible with documented assumptions
- Phase 2 `SalaryGrowth`: defensible provided PercentSalaryHike is confirmed as a percentage point value

### What Is Not Working
- `BurnoutRiskComposite` in `feature_factory.py` uses a formula not traceable to any published JD-R operationalization — academically indefensible in its current form
- `SatisfactionIndex` in `feature_factory.py` uses a formula inconsistent with Hackman-Oldham or Locke-derived operationalizations — indefensible
- `RetentionRisk` is an invented construct with no peer-reviewed anchor; its inclusion as a model feature is not academically defensible and constitutes potential leakage
- `PresenteeismSignal` has no documented theory anchor in the COR, JD-R, FFM, or Mobley frameworks — its construct validity cannot be defended
- `IncomePerLevel` uses JobLevel as an ordinal denominator while treating the result as interval-scale — this interval assumption must be explicitly justified or the construct must be reformulated
- The currently active ML pipeline runs all seven constructs through the indefensible OLD path

### Required for Score >= 70
- Activate Phase 2 engine for all construct computation (minimum required action)
- Document the specific paper, equation number, and page for each construct formula in a citable construct specification
- Remove RetentionRisk and PresenteeismSignal from the active feature set entirely
- Add a note in the IncomePerLevel computation documenting the ordinal-to-interval assumption and its limitations

### Required for Score >= 90
- All seven constructs pass independent expert review against original source papers
- Pre-register construct operationalizations before Saudi data is collected
- Resolve the IncomePerLevel ordinal denominator issue through reformulation or formal justification
- Confirm PercentSalaryHike is a percentage value via data dictionary audit and add an assertion in code

---

## Score 6: Scientific Honesty Score

**Score: 62 / 100 — CONDITIONAL**

### What Was Assessed
This score evaluates whether the platform accurately and transparently represents its own limitations, uncertainties, and methodological caveats — both internally in the codebase and externally to end users, governance stakeholders, and potential academic reviewers. It covers uncertainty quantification, disclosure of proxy use, and communication of domain transfer risks.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| Governance notes in ConstructResult | 10 | 9 | governance_notes field present and populated |
| LeakageReport.summary discloses flags | 10 | 9 | Summary disclosure present |
| THEORY_COMPATIBLE_PROXY vs DIRECT_PAPER_REPLICATION distinction | 10 | 9 | Distinction is encoded and meaningful |
| Confidence never reaches 1.00 | 8 | 7 | Confirmed; confidence is bounded |
| Proxy penalties disclosed | 8 | 7 | Disclosed in audit output |
| audit_summary in ConstructActivationReport | 9 | 8 | Present and informative |
| End-user dashboard surfaces limitations | 15 | 3 | Dashboard/UI status unknown; assumed absent until verified |
| Model calibration honesty displayed | 10 | 3 | Unknown if calibration uncertainty is shown to users |
| Warning when OLD path is active | 10 | 0 | No disclosure when feature_factory.py runs wrong formulas |
| Domain mismatch warning for Saudi deployment | 10 | 0 | No warning when IBM HR constructs applied to Saudi data |
| Confidence interval / prediction interval shown | 8 | 5 | Partial; construct-level confidence exists but prediction intervals unclear |

### What Is Working
- `ConstructResult.governance_notes` is populated with meaningful caveats at the construct level
- `LeakageReport.summary` discloses the number and category of flags detected
- The THEORY_COMPATIBLE_PROXY vs DIRECT_PAPER_REPLICATION distinction is a genuine contribution to scientific honesty and should be highlighted in any academic submission
- Model confidence is bounded below 1.00, avoiding false certainty
- Proxy penalties are disclosed in audit outputs
- `ConstructActivationReport.audit_summary` provides a traceable record of which constructs were activated and why

### What Is Not Working
- There is no runtime warning or governance flag raised when `feature_factory.py` (wrong formulas) is the active computation path — the system runs silently in a state it knows to be scientifically weaker
- There is no warning when the model trained on IBM HR data is applied to Saudi HR data — domain mismatch of this magnitude warrants an explicit deployment-blocking alert
- Dashboard and end-user UI disclosure status is unknown; if limitations are not surfaced to HR practitioners making decisions based on model output, the scientific honesty record is incomplete
- Model calibration honesty (i.e., whether predicted attrition probabilities are reliable as probabilities, not just rankings) is not verified or displayed
- No disclosure mechanism exists to inform downstream users that PerformanceRating has a floor effect in the training data

### Required for Score >= 70
- Add a runtime warning (logged and surfaced to governance) whenever `feature_factory.py` is invoked for construct computation
- Add an explicit domain mismatch warning that is displayed whenever a model trained on IBM HR data is run on non-IBM data (specifically Saudi HR data)
- Audit the dashboard/UI to confirm that at minimum the leakage flag count, confidence level, and construct path (OLD vs Phase 2) are visible to end users
- Document that all confidence scores represent relative model certainty, not calibrated probabilities

### Required for Score >= 90
- Conduct and report model calibration analysis (Brier score, calibration curves) before academic submission
- Implement a mandatory pre-deployment disclosure screen for HR practitioners summarizing known limitations
- Add a domain shift severity score that is displayed at inference time
- Submit the governance notes and audit trail format as a methodological contribution in any publication

---

## Score 7: External Validity Readiness Score

**Score: 32 / 100 — HIGH CONCERN**

### What Was Assessed
This score evaluates whether the platform is ready to produce valid, generalizable predictions in a real Saudi organizational environment. It covers temporal validity, sample representativeness, local construct validation, measurement integrity for Arabic-language instruments, sector heterogeneity, and minimum data quality gates required before deployment.

### Scoring Evidence

| Criterion | Weight | Earned | Notes |
|-----------|--------|--------|-------|
| Temporal validation (time-based split) implemented | 20 | 0 | Random split used throughout; no temporal guard |
| Saudi-specific training or validation data present | 20 | 0 | IBM HR only; no Saudi data in the validation chain |
| Local construct validity confirmation | 15 | 0 | No Saudi CFA or construct validity study |
| Cronbach alpha for Arabic survey scales | 10 | 0 | Not performed |
| Public/private sector separation implemented | 10 | 1 | Not implemented; attrition dynamics conflated |
| Minimum sample size gate implemented | 10 | 0 | No gate exists |
| Architecture for Saudi HR data handling | 5 | 5 | Architecture is present and functional |
| Arabic/bilingual column mapping | 5 | 5 | Implemented |
| Governance and leakage detection | 5 | 4 | Present; leakage detection is a genuine strength |
| Phase 2 construct engine with proxy labeling | 5 | 4 | Exists; not yet deployed |

### What Is Working
- The technical architecture for ingesting and processing Saudi HR data exists and is functional
- Arabic and bilingual column mapping handles non-English field names
- The governance and leakage detection infrastructure is among the strongest elements of the platform
- The Phase 2 construct engine provides a theoretically sound computation path ready for integration
- SAR-calibrated salary validation is in place

### What Is Not Working
- Temporal validation is absent: the random train/test split does not respect the time-ordering of employee records, meaning the model may train on future-dated behavioral signals relative to its test set labels
- No Saudi-specific data exists anywhere in the training or validation pipeline; the model's claimed external validity for Saudi HR contexts is entirely unverified
- No local confirmatory factor analysis, no construct validity study, and no psychometric analysis of any Arabic-language survey instrument has been performed
- Government sector and private sector employees are treated identically, despite fundamentally different attrition mechanisms, retention incentives, and regulatory environments in Saudi Arabia
- There is no minimum sample size gate — the system could be deployed on a dataset of 50 employees and produce confidence-weighted predictions without any statistical basis
- Without temporal splitting, survival bias in the IBM HR training data cannot be assessed or corrected

### Required for Score >= 70
- Implement time-based train/test splitting as a hard requirement before any model training run
- Establish and enforce a minimum sample size gate (recommended: N >= 300, with a warning at N < 500)
- Collect or license at minimum a Saudi HR pilot dataset and conduct descriptive validity checks
- Add a sector (government vs private) variable as a mandatory stratification factor in all analyses

### Required for Score >= 90
- Achieve validated construct measurement in Saudi pilot data via CFA before production deployment
- Retrain the model on Saudi HR data, or document clearly that the IBM HR trained model is a research prototype only and not for production inference on Saudi populations
- Publish external validity results (ideally prospective validation) in peer-reviewed venue before claiming deployment readiness
- Implement prospective monitoring with quarterly recalibration once deployed

---

## Overall Platform Scientific Readiness

### Weighted Score Summary

| Score | Domain | Weight | Raw Score | Weighted |
|-------|--------|--------|-----------|---------|
| 1 | Theory Integrity | 20% | 45 | 9.0 |
| 2 | Psychometric Reliability | 15% | 42 | 6.3 |
| 3 | Leakage Safety | 15% | 58 | 8.7 |
| 4 | Saudi Transferability | 20% | 38 | 7.6 |
| 5 | Construct Defensibility | 15% | 35 | 5.25 |
| 6 | Scientific Honesty | 8% | 62 | 4.96 |
| 7 | External Validity Readiness | 7% | 32 | 2.24 |
| **TOTAL** | | **100%** | | **44.1 / 100** |

**Platform Composite Score: 44 / 100 — HIGH CONCERN**

---

### Traffic-Light Dashboard

| Domain | Score | Status |
|--------|-------|--------|
| Theory Integrity | 45 | RED |
| Psychometric Reliability | 42 | RED |
| Leakage Safety | 58 | AMBER |
| Saudi Transferability | 38 | RED |
| Construct Defensibility | 35 | RED |
| Scientific Honesty | 62 | AMBER |
| External Validity Readiness | 32 | RED |
| **Platform Composite** | **44** | **RED** |

**RED** = Score < 50 — Not deployable without major fixes
**AMBER** = Score 50–69 — Conditional — specific mitigations required
**GREEN** = Score >= 70 — Acceptable with documented limitations

---

### Deployment Verdict

> **NOT READY FOR PRODUCTION**

The platform scores 44/100 on the composite scientific readiness index. Five of seven assessment domains are in RED status. The platform contains genuine engineering strengths — particularly the leakage detection infrastructure, the Phase 2 construct engine, and the Arabic/bilingual data handling — but none of these strengths are currently active in the deployed ML pipeline, which runs the scientifically indefensible OLD `feature_factory.py` path.

**This platform must not be used to inform real HR decisions about Saudi employees in its current state.**

---

### Exact Conditions That Must Be Met Before Production Deployment

The following conditions are **mandatory and non-negotiable** for any production deployment. All must be satisfied before the governance board issues a deployment authorization.

**Tier 1 — Blocking (Must Complete Before Any Deployment):**

1. **Phase 3 Integration**: `theory_grounded_construct_engine.py` must replace `feature_factory.py` as the active construct computation path in the ML pipeline. The OLD path must be disabled for production use with a hard runtime guard.

2. **Temporal Splitting**: All model training and evaluation must use time-based train/test splits. Random splitting is prohibited for production models.

3. **RetentionRisk Removal**: The `RetentionRisk` construct must be removed from the active feature set and the exclusion documented in the governance log.

4. **Saudi Pilot Data**: A minimum validated Saudi HR dataset (N >= 300, both government and private sector represented) must be used for at minimum descriptive validity checks before any inference on Saudi employees.

5. **Minimum Sample Size Gate**: A hard deployment gate must reject inference requests on datasets with N < 300 employees.

6. **WLB Directionality Verification**: The Work-Life Balance item polarity must be empirically verified and reverse-scoring applied if necessary before any BurnoutRisk computation.

**Tier 2 — Required for Academic Publication:**

7. **Cronbach Alpha Reporting**: Internal consistency (alpha >= 0.70) must be computed and reported for all multi-item scales.

8. **Formula Audit**: An independent researcher must audit every construct formula against the source paper equation before submission.

9. **Domain Mismatch Disclosure**: Any publication must explicitly disclose that the model was trained on US synthetic IBM HR data and validated on Saudi data, with quantified domain shift assessment.

10. **Sector Stratification**: Government and private sector employees must be analyzed separately, with separate validity evidence for each sector.

**Tier 3 — Required for Full Scientific Defensibility:**

11. **Confirmatory Factor Analysis**: CFA on Saudi pilot data confirming construct structure before full-scale deployment.

12. **Calibration Analysis**: Brier score and calibration curves computed and reported.

13. **Prospective Validation**: At minimum one prospective validation cohort with a 6-month follow-up before claims of predictive validity in Saudi contexts.

14. **Pre-registration**: Construct operationalizations and analysis plan pre-registered on OSF or equivalent before Saudi data collection begins.

---

*This scorecard was produced for internal governance review. It reflects the current deployed system state as of Phase 3 assessment. Scores should be re-evaluated after each major integration milestone. The conservative scoring approach (rounding down under uncertainty) is intentional — the cost of overestimating scientific readiness in an HR deployment affecting employee livelihoods is higher than the cost of additional validation work.*
