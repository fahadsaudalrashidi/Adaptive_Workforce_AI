# Screenshot Checklist
## Adaptive Workforce AI — v1.0.0-enterprise-local

Use this checklist to capture all screenshots needed for academic submission, enterprise demo, and presentation decks.

**Setup:** System running, Saudi dataset uploaded and analysed. Capture in both light and dark mode where noted.

---

## Required Screenshots

### 1. Data Upload Page

**Page:** Upload (initial state, before data)
**Capture:**
- [ ] Full page — empty upload state with drag-and-drop zone visible
- [ ] File selection dialog (optional)
- [ ] Upload in progress (optional, if capturable)

**Notes:** Shows the local-only, no-cloud design principle.

---

### 2. Executive Dashboard — Full View

**Page:** Executive Dashboard
**Capture:**
- [ ] Top KPI row (total employees, avg risk %, risk band counts)
- [ ] Risk band distribution chart
- [ ] Executive Priority Score + Decision Readiness Level card
- [ ] ML Validation card (Section B metrics visible: AUC 0.82, MCC 0.47)
- [ ] Full dashboard scroll (all cards visible)

**Notes:** Capture in light mode for formal presentation. Include Arabic toggle screenshot if audience is Arabic-speaking.

---

### 3. ML Validation Card — Detail

**Page:** Executive Dashboard → ML Validation section
**Capture:**
- [ ] Both sections visible (or scrolled to Section B)
- [ ] Conservative metrics highlighted: AUC 0.8471, MCC 0.4942, F1 0.7073 (VotingEnsemble — Phase 29.5)
- [ ] Feature importance bar chart (top features: Job_Opportunities first)
- [ ] Governance notes visible

**Notes:** This screenshot is the most important for academic submission — proves conservative validation.

---

### 4. Employee Risk Dashboard — Table

**Page:** Employee Risk Dashboard
**Capture:**
- [ ] Full employee table visible (first 10–20 rows)
- [ ] Risk band badges visible (Stable / Monitoring / Strategic Concern / Priority Review)
- [ ] Risk and stability scores visible
- [ ] Filter/sort controls visible
- [ ] Drill-down expanded for one high-risk employee (showing top drivers)

**Notes:** Blur or redact actual employee names/IDs for public screenshots.

---

### 5. Risk Segmentation

**Page:** Risk Segmentation
**Capture:**
- [ ] Department comparison chart
- [ ] Risk distribution by department
- [ ] Top risk drivers per department

---

### 6. Theory Explainability

**Page:** Theory Explainability
**Capture:**
- [ ] Theory framework cards (COR, JD-R, SDT, SET, OCT, SIT all visible)
- [ ] Driver attribution for one theory expanded
- [ ] Bilingual driver explanation (EN + AR side by side if possible)

---

### 7. Strategy Simulator

**Page:** Strategy Simulator
**Capture:**
- [ ] Baseline metrics (avg risk, at-risk count)
- [ ] Scenario list (all scenarios visible or top 3)
- [ ] One scenario expanded (showing estimated risk reduction, affected departments, confidence)
- [ ] Recommended strategy section

**Notes:** Highlight the "Improve Internal Job Opportunities" scenario as the top-impact scenario linked to the #1 ML feature.

---

### 8. Decision Center — Full View

**Page:** Decision Center
**Capture:**
- [ ] Board summary (EN version visible)
- [ ] Executive Priority Score badge
- [ ] Decision Readiness badge
- [ ] Strategic priorities list (urgency and confidence badges visible)
- [ ] One strategic priority expanded (showing recommended next step + confidence reason)
- [ ] Decision questions section (one expanded with answer and evidence)
- [ ] Department decision briefs section
- [ ] Evidence pack section (collapsed/expanded)
- [ ] Arabic version of board summary (language toggled)

**Notes:** This is the primary board presentation screenshot. Capture clean with no partial loads.

---

### 9. Governance Panel

**Page:** Governance Panel
**Capture:**
- [ ] Full governance panel visible
- [ ] ML exclusions section (PII removed, identifier removed, proxy removed)
- [ ] Governance warnings listed
- [ ] Employment decision prohibition statement visible
- [ ] Statistical associations disclaimer visible

**Notes:** This screenshot is critical for regulatory and legal audience presentations.

---

### 10. Executive Reports

**Page:** Executive Reports
**Capture:**
- [ ] Reports page overview
- [ ] ML Validation section visible
- [ ] Simulation section visible
- [ ] Decision Intelligence section visible
- [ ] CSV export buttons visible
- [ ] Governance disclaimer row at bottom

---

### 11. Analysis History

**Page:** Analysis History
**Capture:**
- [ ] List of past analysis sessions
- [ ] Session metadata visible (date, dataset name, employee count)
- [ ] Load session button
- [ ] Delete session option

---

### 12. Final Release Terminal Output

**Capture the terminal output of all 4 validations:**

```
py -m pytest tests/ -q
```
- [ ] Last 5 lines showing: `712 passed, 1 skipped, 174 warnings`

```
py scripts/final_release_check.py
```
- [ ] Full output showing 7/7 PASS

```
py scripts/run_saudi_ml_validation.py
```
- [ ] Section B header and metrics table
- [ ] Line: `ML VALIDATION COMPLETE — available=True`

```
cd executive-ui && npx vite build
```
- [ ] Bundle output showing all chunks
- [ ] Final line: `built in X.XXs`

---

## Optional — Comparison Screenshots

### ML Section A vs Section B

- [ ] Section A results (AUC 1.0 — with proxy leakage warning visible)
- [ ] Section B results (AUC 0.82 — conservative)
- [ ] Side-by-side comparison (use slide layout)

**Caption:** "Section A shows inflated metrics due to tenure proxy leakage. Section B shows the conservative, academically valid result after proxy removal."

### Language Toggle (EN ↔ AR)

- [ ] Executive Dashboard in English
- [ ] Executive Dashboard in Arabic
- [ ] Decision Center board summary in Arabic

### Dark Mode

- [ ] Executive Dashboard dark mode
- [ ] Decision Center dark mode

---

## Screenshot Naming Convention

```
[page]_[section]_[mode]_[language].png

Examples:
  dashboard_kpi_row_light_en.png
  decision_center_board_summary_light_ar.png
  ml_validation_section_b_light_en.png
  terminal_pytest_results.png
  terminal_final_release_check.png
  terminal_saudi_ml_validation.png
  terminal_vite_build.png
```

---

## Presentation Deck Priority Order

For a 10-slide academic or executive presentation:

| Slide | Screenshot |
|---|---|
| 1 | Upload page (problem setup) |
| 2 | Executive Dashboard — KPI overview |
| 3 | ML Validation — Section A vs B comparison |
| 4 | ML Validation — Section B conservative metrics |
| 5 | Decision Center — board summary + strategic priorities |
| 6 | Strategy Simulator — scenario impact |
| 7 | Theory Explainability — driver attribution |
| 8 | Governance Panel — exclusions + disclaimers |
| 9 | Employee Risk Table (redacted) |
| 10 | Terminal — all 4 validation outputs |
