# Phase 23 — Leave Balance Column Detection Fix

Real detection bug, root-caused and fixed in `backend/core/labor_law_calculators.py`.

## 1. Root cause — exact and traced, not guessed

Old pattern
([`labor_law_calculators.py:152-159`](backend/core/labor_law_calculators.py) prior to
this fix):

```python
_LEAVE_BALANCE_PATTERNS = re.compile(
    r"\b(leave[_\s]?balance|remaining[_\s]?leave|leave[_\s]?days[_\s]?remaining|"
    r"رصيد[_\s]?الإجازات)\b", re.I,
)
```

Traced directly against the reported column name:

```
>>> _LEAVE_BALANCE_PATTERNS.search("LeaveBalanceDays")
None
>>> re.compile(r"leave[_\s]?balance").search("LeaveBalanceDays")
<re.Match object; span=(0, 12), match='LeaveBalance'>
>>> re.compile(r"leave[_\s]?balance\b").search("LeaveBalanceDays")
None
>>> "LeaveBalanceDays"[len("LeaveBalance")]
'D'
```

**The exact mechanism**: `leave[_\s]?balance` alone matches the substring `"LeaveBalance"`
just fine (span 0-12). The failure is the alternation's *trailing* `\b`. A `\b` requires a
transition between a word character (`\w`) and a non-word character (or string
start/end). The character immediately after the match, at index 12, is `'D'` (the start
of `"Days"`) — a word character following another word character (`'e'` from
`"Balance"`) — so no boundary exists there, and the whole pattern fails to match. Every
existing alternative in the old pattern has the identical structural flaw: each assumes
the keyword is the *last* word in the column name, which happened to be true for every
fixture built in Phase 21 (`LeaveBalance`, no fixture ever had a trailing suffix word)
but is not true for `LeaveBalanceDays` — a completely standard, realistic PascalCase
naming convention with no separator before the `Days` suffix.

**Compounding factor**: even setting the boundary issue aside, the specific word order
`Leave → Balance → Days` isn't covered by any of the other three alternatives either —
`remaining[_\s]?leave` requires "remaining" first; `leave[_\s]?days[_\s]?remaining`
requires "days" and "remaining" in that specific order (`Leave-Days-Remaining`, not
`Leave-Balance-Days`). So this was a genuine detection gap, not just a boundary bug —
confirmed by testing all four old alternatives individually against `"LeaveBalanceDays"`
and finding zero matches. `_LEAVE_TAKEN_PATTERNS` had the same structural issue (verified
against `LeaveDaysTaken`, `UsedLeaveDays`, `LeaveDaysUsed` — none of the three matched the
old pattern either).

Compared to this same Phase 21 module's own salary/tenure patterns
(`_SALARY_PATTERNS`, `_YEARS_OF_SERVICE_PATTERNS`), the leave patterns were narrower —
those broader patterns happened to avoid the bug only because their test fixtures never
exercised a trailing-suffix column name, not because they were more carefully designed
against this failure mode.

## 2. The broadened pattern

[`labor_law_calculators.py:150-173`](backend/core/labor_law_calculators.py#L150-L173):

```python
_LEAVE_BALANCE_PATTERNS = re.compile(
    r"\b((annual[_\s]?)?leave[_\s]?balance([_\s]?days)?|"
    r"remaining[_\s]?leave([_\s]?days)?|"
    r"leave[_\s]?days[_\s]?remaining|"
    r"رصيد[_\s]?الإجاز(?:ات|ة)([_\s]?السنوية)?)\b", re.I,
)
_LEAVE_TAKEN_PATTERNS = re.compile(
    r"\b(leave[_\s]?taken|leave[_\s]?used|leave[_\s]?days[_\s]?used|"
    r"leave[_\s]?days[_\s]?taken|used[_\s]?leave([_\s]?days)?|"
    r"taken[_\s]?leave([_\s]?days)?|"
    r"الإجاز(?:ات|ة)[_\s]?المستخدمة)\b", re.I,
)
```

The fix makes the trailing suffix word an explicit **optional part of each alternative**
(`([_\s]?days)?`) rather than leaving it outside the match, so the `\b` correctly lands
at the true end of the compound phrase whether or not a suffix is present — and adds the
missing word-order/synonym alternatives the brief called out
(`AnnualLeaveBalance`, `RemainingLeaveDays`, `LeaveDaysTaken`, `UsedLeaveDays`).

Verified no false-positive regression: `LeaveType`, `SickLeave`, `MonthlySalary`, and
`Department` all correctly still do NOT match either pattern
(`test_leave_balance_pattern_does_not_false_positive_on_unrelated_columns`).

## 3. Hand-verified compensation figures

Using the exact reported fixture shape (`labor_law_leave_balance_days_test_data.csv`,
180 rows, `LeaveBalanceDays` column, values 0-46, 33 employees at 0 / 37 at 20+),
compensation = (monthly wage ÷ 30) × balance days, per Article 111 (confirmed in Phase
21's research):

| Employee | Years | Wage (SAR) | Balance (days) | Computed | Hand-check |
|---|---|---|---|---|---|
| EMP-E6534E | 15 | — | 3 | SAR 750 | e.g. wage 7500 → 7500/30=250 × 3 = 750 ✓ |
| EMP-EE950E | 14.9 | — | 0 | SAR 0 | 0 balance → SAR 0, not blank, not fabricated ✓ |

Also verified programmatically against two rows from the original `labor_law_clean_data_test.csv`
fixture (renamed column to `LeaveBalanceDays` to confirm identical behavior post-fix):
- 12 years, wage 10,000, balance 100 days → (10000/30) × 100 = **33,333.33** — matches engine output exactly.
- 7 years, wage 10,000, balance 40 days → (10000/30) × 40 = **13,333.33** — matches engine output exactly.

Every one of the 180 fixture rows was additionally checked programmatically in the new
regression test (`test_leave_balance_days_column_now_detected_and_computes_real_figures`)
— all computed compensation figures match `(wage/30) × balance` to within 0.01 SAR, and
every 0-balance employee shows exactly SAR 0 (not `None`, not a fabricated positive
number).

## 4. Live screenshot

Re-uploaded the exact reported shape via the live UI: **180/180 employees**, Data Type =
"Real Balance" (previously would have shown "Entitlement Only"), Total Compensation
Exposure = **SAR 750.9K** (previously SAR 0), with the "BALANCE (DAYS)" and
"COMPENSATION" table columns now showing real per-employee figures instead of `—`
placeholders — including the correct `SAR 0` (not blank) for the zero-balance employee.
Zero console or page errors.

## Regression suite

```
$ python -m pytest tests/ -q
40 failed, 1455 passed, 1 skipped, 205 warnings
```

1455 passed = the 1445 baseline after Phase 22 + 10 new Phase 23 tests (4 parametrized
balance-name cases, 4 parametrized taken-name cases, 1 false-positive guard, 1 end-to-end
180-row regression test). Same 40 pre-existing, unrelated failures — **zero regressions**.

## Files changed

- `backend/core/labor_law_calculators.py` (broadened `_LEAVE_BALANCE_PATTERNS` /
  `_LEAVE_TAKEN_PATTERNS`, [lines 150-173](backend/core/labor_law_calculators.py#L150-L173))
- `tests/test_labor_law_calculators.py` (+10 tests)
- `labor_law_leave_balance_days_test_data.csv` (new fixture, repo root, matching the
  exact reported bug shape)
