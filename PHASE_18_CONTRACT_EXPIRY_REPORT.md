# Phase 18 — Contract Expiry & Renewal Monitoring

New, standalone module: employment-contract and Iqama (Saudi residency permit) expiry
tracking, with two route-layer cross-links to Succession Readiness and Nitaqat. This is
a genuinely new domain for the platform — the first module in this session to track a
lifecycle/compliance *date* rather than a workforce metric.

## 1. Column-detection patterns (contract-end-date and Iqama-expiry, confirmed separate)

**Deviation from the literal brief, disclosed up front.** The brief named
`theory_aware_column_mapper.py` and `saudi_schema_intelligence.py` as the fuzzy-detection
pattern to reuse. Both were checked and rejected, consistent with this session's established
practice of verifying instructions against codebase reality rather than following them
blindly:

- `theory_aware_column_mapper.py` — grepped for its public surface; it is built around
  `ConstructDefinition`/`ConstructMapping`/`TheoryAwareColumnMapper` for **Likert-scale
  survey constructs** with confidence scoring. Not a fit for a single date column.
- `saudi_schema_intelligence.py` — `SaudiSchemaIntelligenceEngine.analyse_schema` exists
  but is dead code relative to the live product: grepped the backend and found it
  referenced only in a placeholder string in
  [`backend/api/enterprise_routes.py:399`](backend/api/enterprise_routes.py#L399)
  (`"In production, this endpoint invokes SaudiSchemaIntelligenceEngine.analyse()..."`),
  never actually called. This corroborates `nitaqat_compliance_engine.py`'s own module
  docstring (lines 90-96), which independently reached and documented the same conclusion
  in Phase 7.

Instead, `contract_expiry_engine.py` reuses the local-regex `_find_column(df, pattern)`
convention already live in every Phase 5-17 engine (succession, overtime, nitaqat, pay
equity) — see the engine's module docstring,
[`backend/core/contract_expiry_engine.py:10-23`](backend/core/contract_expiry_engine.py#L10-L23),
for the full citation trail.

**Two independent regex patterns, two independent parsing passes** —
[`backend/core/contract_expiry_engine.py:78-94`](backend/core/contract_expiry_engine.py#L78-L94):

```python
_CONTRACT_END_PATTERNS = re.compile(
    r"\b(contract[_\s]?end[_\s]?date|contract[_\s]?expiry|contract[_\s]?expiration|"
    r"contractenddate|contract[_\s]?termination[_\s]?date|"
    r"تاريخ[_\s]?انتهاء[_\s]?العقد|نهاية[_\s]?العقد)\b", re.I)

_IQAMA_EXPIRY_PATTERNS = re.compile(
    r"\b(iqama[_\s]?expiry|iqama[_\s]?expiration|iqamaexpirydate|iqama[_\s]?end[_\s]?date|"
    r"visa[_\s]?expiry|visa[_\s]?expiration|visaexpirydate|"
    r"residency[_\s]?permit[_\s]?expiry|residency[_\s]?expiry|"
    r"انتهاء[_\s]?الإقامة|تاريخ[_\s]?انتهاء[_\s]?الإقامة|انتهاء[_\s]?التأشيرة)\b", re.I)
```

The two patterns share no keyword, so a column literally named just `ExpiryDate` (no
distinguishing word) matches **neither** — a deliberate safe-failure: the engine refuses
to guess which entity type an ambiguous column represents, rather than assigning it to
one signal arbitrarily. This mirrors the "refuse rather than guess" discipline already
established by `nitaqat_compliance_engine.get_saudi_status_by_record_id`.

`analyze_contract_expiry()` ([line 368](backend/core/contract_expiry_engine.py#L368))
detects both columns independently (`contract_col`, `iqama_col`), and — when both are
present — runs `_parse_signal()` ([line 301](backend/core/contract_expiry_engine.py#L301))
twice, once per column, producing two separate tier-count dicts
(`contract_tier_counts`, `iqama_tier_counts`) and never averaging or merging the two.
Confirmed live in the browser (§5) and by test
(`test_messy_fixture_contract_and_iqama_are_not_conflated`,
[`tests/test_contract_expiry_engine.py:183`](tests/test_contract_expiry_engine.py#L183)):
employee EMP001 in the synthetic fixture has `ContractEndDate=2026-09-15` and
`IqamaExpiry=2026-08-25` — two different dates, two different day-counts, two separate
candidate rows.

## 2. Urgency-tier boundaries chosen and why

[`backend/core/contract_expiry_engine.py:206-215`](backend/core/contract_expiry_engine.py#L206-L215):

```python
def _tier_for_days(days: int) -> str:
    if days < 0:  return "overdue"
    if days <= 30: return "critical_0_30"
    if days <= 60: return "urgent_31_60"
    if days <= 90: return "upcoming_61_90"
    return "monitored_90_plus"
```

Five tiers: **overdue/expired, ≤30 days, 31-60 days, 61-90 days, 90+ days** — the exact
boundaries the brief itself suggested, chosen because they line up with standard HR/visa
renewal planning practice (a 90-day outer horizon to start planning, a 30-day inner
horizon where action is genuinely urgent).

**Explicitly disclosed as an unverified planning heuristic, not a researched regulatory
finding.** The module docstring
([lines 32-43](backend/core/contract_expiry_engine.py#L32-L43)) draws a direct contrast
with Phase 17's Qiwa contract-authentication finding, which *was* independently verified
via live web research — this phase performed no equivalent regulatory research for the
30/60/90-day boundaries. The disclaimer text
(`CONTRACT_EXPIRY_DISCLAIMER_EN`, [line 136](backend/core/contract_expiry_engine.py#L136))
states this directly: *"not a legally mandated renewal timeline... Actual Iqama/visa
renewal deadlines, grace periods, and penalties are governed by real Saudi immigration
regulations this platform does not verify per-employee."* This disclaimer renders
unconditionally on every `available: true` response (verified live in §5).

Tier-boundary math is hand-verified independent of any calendar date in
`test_tier_boundaries_hand_computed`
([`tests/test_contract_expiry_engine.py:66`](tests/test_contract_expiry_engine.py#L66)) —
asserts every boundary transition (`-1→overdue`, `0/30→critical_0_30`,
`31/60→urgent_31_60`, `61/90→upcoming_61_90`, `91→monitored_90_plus`).

## 3. Cross-link implementations (Phase 8 decoupled-engine / route-layer-join pattern)

**Join surface**: `get_expiry_signals_by_record_id(df)`
([`backend/core/contract_expiry_engine.py:522`](backend/core/contract_expiry_engine.py#L522))
returns `{record_id_safe: {"contract_days_remaining": int|None, "iqama_days_remaining":
int|None}}`, or `None` when no cross-link is possible. It:

- Refuses (`return None`) when no real named ID column exists (`EmployeeID`,
  `employee_id`, `EmpID`, `emp_id`) — never falls back to a positional index, for the
  identical reason `get_saudi_status_by_record_id` refuses: a positional fallback
  computed over this module's valid-row subset would not reliably match another module's
  positional fallback over a *different* valid-row subset.
- Uses the exact same one-way hash scheme as every other cross-link-participating engine
  this session: `"EMP-" + sha256(str(raw_id))[:6].upper()` — reproduced independently by
  `employee_risk_scoring._make_record_id()`, `succession_readiness_engine.py`, and
  `nitaqat_compliance_engine.get_saudi_status_by_record_id`.
- Never imports `succession_readiness_engine.py` or `nitaqat_compliance_engine.py`, and
  neither of those imports `contract_expiry_engine.py` back — confirmed by inspection of
  all three files' import blocks. The route layer, which already imports all three
  engines independently, is the only place that combines them — exactly the Phase 8
  precedent at
  [`backend/api/local_analysis_routes.py:2042-2205`](backend/api/local_analysis_routes.py#L2042-L2205)
  (the `/succession-readiness` route's `saudi_pipeline_cross_link` construction).

**New route**: `/api/local/contract-expiry`
([`backend/api/local_analysis_routes.py:2216-2454`](backend/api/local_analysis_routes.py#L2216-L2454)).
Same ingestion pipeline as every other module (normalize → governance scan → analyze →
serialize), then two independent joins:

- **Succession cross-link** ([lines 2333-2371](backend/api/local_analysis_routes.py#L2333-L2371)):
  intersects `readiness_result.high_readiness_record_ids` with `signals_map`, flagging an
  employee if `min(contract_days_remaining, iqama_days_remaining)` (soonest of *either*
  non-null signal) is `<= CROSS_LINK_HORIZON_DAYS` (90). Soonest-of-either was chosen
  deliberately: a leadership-critical employee could become unreachable via *either*
  boundary, not just contract end.
- **Nitaqat cross-link** ([lines 2373-2411](backend/api/local_analysis_routes.py#L2373-L2411)):
  intersects non-Saudi IDs from `get_saudi_status_by_record_id` with `signals_map`, but
  uses **only** `iqama_days_remaining` (never `contract_days_remaining`) — Nitaqat/
  Saudization is specifically about legal work-authorization status, not the employment
  relationship's end date, so mixing in contract-end would conflate two different
  compliance questions.

Both cross-links: refuse (`available: false` with a stated reason) when the upload lacks
either a named ID column or the relevant signal — never a silent/guessed join. Both
verified live end-to-end in §5 with real computed counts (not placeholders).

## 4. Test results

`tests/test_contract_expiry_engine.py` — **25/25 passed**:

```
$ python -m pytest tests/test_contract_expiry_engine.py -v
...
25 passed in 0.56s
```

Coverage:
- **Tier-boundary math** (1 test) — hand-computed, calendar-independent.
- **"Not detected" against every real HR-shaped fixture in this repo** (7 tests, one per
  file): `test_employee_data.csv`, `messy_test_data.csv`, `messy_recruitment_data.csv`,
  `succession_test_data.csv`, `nitaqat_test_data.csv`,
  `nitaqat_realistic_multidept_test_data.csv`, `pay_equity_realistic_test_data.csv`,
  `payroll_longitudinal_test_data.csv` — none of the fixtures built across this entire
  session track contract or Iqama/visa expiry, confirming the honest-degradation path is
  the expected, common case. (`MODEL_SEARCH_RESULTS_PHASE29_5.csv` was checked and
  excluded — it's ML training-run metrics, not HR data. A file named
  `Original_Dataset_of_Employee_Attrition` does not exist in this repo, despite being
  named in the phase brief; only tangentially-related files exist
  (`saudi_attrition_normalizer.py`, `hr_attrition_page.py`) — noted here for the record.)
- **Two-genuinely-separate-signals** (4 tests) — messy synthetic fixture
  (`contract_expiry_test_data.csv`, built for this phase) confirms `ContractEndDate` and
  `IqamaExpiry` are detected as two distinct columns, never conflated per-employee,
  department rollup present.
- **Messy-data discipline** (built into the fixture above): mixed date formats (ISO
  `YYYY-MM-DD` and an alternate `DD-Mon-YYYY` form), one clearly-invalid string
  (`"not-a-real-date"`), one blank/missing value. **A genuine finding surfaced here**: two
  rows using the alternate `15-Mar-2027`/`20-Sep-2026` format were *also* excluded as
  unparseable, even though that format parses fine in isolation — `pandas.to_datetime()`
  infers a single format from the majority of a column and applies it across all rows
  (documented pandas behavior), so a minority-format value can be silently excluded
  rather than parsed. This fails safe (excluded + disclosed via
  `date_quality_warnings`, matching the "never guess" principle) but is a real
  limitation of the `pd.to_datetime(errors="coerce")` discipline this module inherited
  from `recruitment_pipeline_engine.py` — worth flagging for anyone uploading genuinely
  mixed-format date columns. Total: 4 invalid dates disclosed exactly (2 contract, 2
  Iqama), matching hand-verification.
- **Exact tiering on dynamically-built data** (2 tests) — dates built as
  `datetime.now() + timedelta(days=N)` offsets (calendar-drift-safe, will not go stale),
  confirming all 5 tiers compute correctly and the `monitored_90_plus` tier is
  aggregate-only (not surfaced as an individual row).
- **`get_expiry_signals_by_record_id` join-surface** (6 tests) — refuses with no ID
  column, refuses with no expiry column, refuses on empty DataFrame, reproduces the exact
  hash scheme, excludes rows with a missing ID, and returns both signals independently
  on the messy fixture.
- **Both cross-link scenarios** (3 tests) — synthetic fixtures built to isolate each
  scenario: a high-readiness-tier employee with a soon-expiring contract is flagged while
  a high-readiness employee with a far-out contract is not; a non-Saudi employee with a
  soon-expiring Iqama is flagged while a Saudi employee is correctly excluded; and the
  join correctly refuses when the upload lacks a shared named ID column.

## Full regression suite

Before and after this phase's changes:

```
$ python -m pytest tests/ -q
40 failed, 1395 passed, 1 skipped, 205 warnings in 52-54s
```

1395 passed = the ~1370 pre-existing passing baseline + 25 new Phase 18 tests. The same
40 pre-existing, unrelated failures as prior phases (all in
`tests/test_phase29_extended.py::TestCEODashboardVisualisations` and
`tests/test_phase30_1_security.py` — bcrypt/auth-manager environment issues predating
this phase) — **zero regressions**.

## 5. Live browser verification

Backend restarted (`python backend/api/main.py` — no auto-reload, confirmed in Phase 17)
to pick up the new route; frontend (`npm run dev`) restarted after adding the page/nav
entry. `npx tsc --noEmit` passed with zero errors before verification.

**Environment note** (not a code defect): this machine had a stale, unowned TCP listener
occupying `127.0.0.1:8000` (`Get-Process`/`Get-CimInstance` confirmed no process actually
owns it — an orphaned Windows kernel socket entry, likely left behind by an earlier
session's forced process kill). This silently shadowed the freshly-restarted backend for
any client connecting via `localhost`/`127.0.0.1`, including Vite's dev proxy. Verified
the real backend was healthy and serving the new route via its `0.0.0.0` binding
(`192.168.100.2:8000` → `405 Method Not Allowed` on GET, confirming the route exists and
only accepts POST); temporarily pointed `vite.config.ts`'s proxy at that address for this
verification session, then reverted it back to `localhost:8000` immediately after — no
net change to committed config. Flagging this so a future session isn't puzzled by a
"route not found" symptom that isn't caused by the route.

**Screenshot 1 — page loaded, nav entry live**: "Contract Expiry & Renewal" appears in
the sidebar directly below "Succession Readiness" (the cross-link-adjacent placement the
brief requested), disclaimer and column-requirement banners render correctly, bilingual
toggle present.

**Screenshot 2 — honest "not detected" against real data**: uploaded the real
`test_employee_data.csv` (200 rows, already in this repo). Result: "Contract/Iqama expiry
data not detected in this upload," reason text matches the engine's `unavailable_result`
exactly, both `contract_end_date` and `iqama_or_visa_expiry` checklist chips render
unchecked (only `department` is checked, since that column happens to exist in this
fixture) — no fabricated dates, matching every other module's established honest-
degradation pattern.

**Screenshot 3 — both cross-link scenarios, real computed numbers**: uploaded
`contract_expiry_test_data.csv` (the synthetic fixture built for this phase, 10 rows,
carrying `ContractEndDate`, `IqamaExpiry`, `PerformanceRating`, `YearsAtCompany`, and
`Nationality` in one file so a single upload drives all three engines, matching the "same
upload" precedent Phase 8 established). Rendered live:
- KPIs: 10 employees, 5/8 contract records urgent-or-overdue (63%), 6/8 Iqama records
  urgent-or-overdue, 4 invalid dates excluded.
- **Succession Readiness Cross-Link** (green, available): *"Of 3 employees in the 'High
  Readiness' tier, 3 have a contract or Iqama/visa expiry within 90 days..."*
- **Nitaqat Iqama Compliance Cross-Link** (amber, available): *"Of 6 employees recorded
  as non-Saudi, 4 have an Iqama/visa expiry within 90 days..."*
- Candidate table below (scrolled into view): 10 individually-tiered rows with real
  department, signal type (Contract vs. Iqama/Visa shown separately per employee),
  expiry date, days remaining, and color-coded urgency badges (red=overdue/critical,
  amber=urgent). Date-quality warnings ("2 row(s) had an unparseable contract-end-date
  value...", "2 row(s)... Iqama/visa-expiry...") and the sources/governance footer render
  correctly.

Zero console errors or page errors captured across the full flow (`page.on('console')`
and `page.on('pageerror')` both empty).

## Files changed

- `backend/core/contract_expiry_engine.py` (new, ~619 lines)
- `tests/test_contract_expiry_engine.py` (new, 25 tests)
- `contract_expiry_test_data.csv` (new fixture, repo root)
- `backend/api/local_analysis_routes.py` (+6 lines import, +239 lines route)
- `executive-ui/src/pages/ContractExpiryTracker.tsx` (new)
- `executive-ui/src/types/index.ts` (+1 NavPage variant: `contractexpiry`)
- `executive-ui/src/App.tsx` (+2 lines: import + route case)
- `executive-ui/src/layout/Sidebar.tsx` (+1 icon import, +1 nav item, placed directly
  after Succession Readiness)
