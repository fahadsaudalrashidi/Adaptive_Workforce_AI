# Phase 11B — Visual QA (Overlap Bug) and Design Polish

Status: **Bug found, root-caused, fixed, and verified via actual screenshot
inspection (not code review alone) across all 6 usages, LTR and RTL. Design
pushed further per the honest self-critique below. Zero backend
regressions.**

---

## 1. The overlap bug — found, root-caused, fixed

### What was wrong

Every horizontal bar chart and the recruitment funnel chart
(`DepartmentBarChart.tsx`, `RecruitmentFunnelChart.tsx` — used across
**6 of the 7 feature pages**: Overtime, Nitaqat, Succession, Fairness,
Payroll, Recruitment) broke severely in Arabic/RTL mode: the bars rendered
on top of their own axis labels, leaving only the first 1-2 letters of each
department/attribute name visible (e.g. "Finance" → "F", "Engineering" →
"E"), with value labels also clipped against the bar edge. This was found
by actually opening the Arabic pages and looking at the screenshots — the
zero-console-errors check from Phase 11's own verification would never have
caught it, since this is a pure layout/geometry bug, not a JS error.

Screenshot evidence of the original bug (pre-fix, part of this session's
verification sweep): `scratchpad/sweep/nitaqat_ar.png` shows the Nitaqat
department chart with row labels truncated to "O", "S", "In", "F", "H",
"L", "M" — Operations/Sales/Information Technology/Finance/Human
Resources/Legal/Marketing, all clipped under their own bars.

### Root cause

`DepartmentBarChart.tsx:73` (pre-fix) — the Recharts `<ResponsiveContainer>`
had no direction isolation, so it inherited `dir="rtl"` from
`<html dir="rtl">`, which `LanguageContext.tsx` sets on every language
toggle. Recharts' internal geometry — Y-axis category-label positioning,
bar `x`/`width` calculation, `LabelList` placement — assumes LTR and was
never designed to run under an inherited RTL text-direction context. The
practical effect: labels and bar rectangles ended up computed for
overlapping screen positions. This is a known class of bug with Recharts
(and most SVG-based charting libraries) in RTL applications; the
established fix — and the one applied here — is that **charts stay LTR
internally in RTL apps** (only the surrounding page chrome mirrors), which
is also what Bloomberg Arabic, Qiwa, and most enterprise Arabic dashboards
do for numeric visualizations.

Same root cause, same fix needed, in `RecruitmentFunnelChart.tsx` (stage
labels via `LabelList position="right"`) and defensively in
`RadialKPI.tsx` (circular/symmetric, so not visibly broken, but isolated
for consistency rather than relying on that symmetry continuing to save it).

### The fix

Wrapped each chart's `<ResponsiveContainer>` in a `dir="ltr"` /
`style={{direction:'ltr'}}` div, isolating it from the page's direction
regardless of language:

- `DepartmentBarChart.tsx:88`
- `RecruitmentFunnelChart.tsx:40`
- `RadialKPI.tsx:30`

This is a single fix at the shared-component level — it resolved the bug
everywhere those 3 components are used, without touching any of the 7 page
files.

### Verification — actually screenshotted and inspected, not assumed

Per the explicit instruction not to declare this fixed from code review
alone, every one of the 6 chart usages was re-screenshotted in Arabic mode
after the fix and visually inspected:

| Location | Screenshot | Result |
|---|---|---|
| Succession — dept bar chart | `sweep/fix_succession_ar.png` | Finance/Engineering/Sales/Operations fully readable, no overlap |
| Nitaqat — dept bar chart | `sweep/fix_nitaqat_ar.png` | All 9 departments readable, gold top-band bar intact |
| Overtime — dept bar chart | `sweep/fix_overtime_ar.png` | Sales/Engineering/Operations/Finance/HR readable |
| Fairness — attribute bar chart | `sweep/fix_fairness_ar.png` | Age/Gender readable, red/orange risk colors intact |
| Payroll — dept bar chart | `sweep/fix_payroll_ar.png` | Sales/Operations/Finance/Engineering readable |
| Recruitment — funnel chart | `sweep/fix_recruitment_funnel_ar.png` | Applied/Screening/Interview/Offer/Hired stage labels all clear beside the funnel |

All 6 also re-confirmed in the LTR/English direction (`sweep/
zoom_succession_table_en.png`, `sweep/zoom_succession_chart_en.png`) to
make sure the fix didn't regress the already-working English layout — it
didn't; LTR was rendering correctly before and after, since `dir="ltr"`
matches what the page already inherited in English mode.

**Also checked and confirmed NOT overlapping** (part of the same sweep,
ruling out other candidate bug locations named in the brief): the
Succession Readiness table's "Stuck"/"Low Fairness" flag badges
(`zoom_succession_table_en.png` / `_ar.png` — each column reserves its own
grid space via the `<table>` element's native column layout, never
absolute-positioned over other cells, so this was not a second instance of
the bug), the EmptyState requirement-chip grid, and the KPI card row
across all 7 pages.

---

## 2. Honest self-critique against the "legendary Fortune 500" bar

**Phase 11 as shipped: genuinely conservative, and that conservatism is
exactly why it read as "primitive."** Re-examining the Phase 11 report's
own language — "gold accent layered on top... not a full re-skin," a 3px
top accent bar, flat single-color bars, the same `p-5`/`gap-4`/`space-y-6`
spacing rhythm as before, a flat `bg-navy-900` with no atmosphere — the
honest assessment is that Phase 11 added new colors and a few new shapes
onto the *same* layout skeleton, rather than committing to a visibly
different tier of polish. A hero KPI card with an 88px gauge and a 3px
top line, sitting in the same-density grid as every other card, does not
read as "the headline number" at a glance — it reads as "a KPI card that
happens to have a small circle in it."

### Gaps identified (the 4 the brief flagged, self-assessed):

1. **Flatness despite elevation tokens — confirmed real.** The 3-tier
   elevation system existed but the *visual delta* between tiers was too
   small to register without close inspection. Fixed in this phase (§3).
2. **Whitespace/breathing room — confirmed real.** `gap-4`/`space-y-6`
   throughout read as a dense internal tool, not an executive surface.
   Fixed in this phase (§3).
3. **Chart polish — partially real.** The custom tooltips and theme-aware
   colors from Phase 11 were genuinely more polished than Recharts
   defaults, but flat single-color bars still looked closer to a
   default/library output than a designed one. Fixed in this phase (§3).
4. **Moments of delight — partially real.** `useCountUp` and hover states
   existed and worked, but neither is visible in a static screenshot, and
   more importantly neither was paired with any other signal (glow, scale,
   color shift) that would make the "important number" moment land. Fixed
   in this phase (§3, hero glow + hover glow).

### What was done about each (this phase, §3 in detail below):
- Hero KPI cards: bigger radial gauge (88→108px), ambient gold radial-glow
  background fill (not just a top line), thicker glowing top accent
  (`box-shadow` bloom, not flat), bigger padding, `hover:shadow-glow-gold`.
- Page-level ambient background: two low-opacity radial gradients (blue
  top-left, gold top-right), fixed behind all content — the Linear/Stripe
  "atmosphere" convention, applied once at the layout level so every page
  inherits it.
- Bar charts: gradient fills (per-color `<linearGradient>` defs) replacing
  flat single-tone bars.
- Spacing: `space-y-6`→`space-y-7`, KPI grid `gap-4`→`gap-5`, header
  `text-2xl font-bold` (1.5rem)→`text-headline` (1.875rem, bold, tighter
  letter-spacing — the named scale from Phase 11's own `tailwind.config.js`
  that went unused until now) across all 7 pages.

### Honest rating

**Does it now clear "legendary Fortune 500 / modern Tableau-Power-BI"?**
Closer, and the specific complaint (flat, same-as-before, "بدائي") is
directly addressed — the hero cards now have real visual weight, the bars
have real depth, the page has real atmosphere instead of flat navy, and
the spacing no longer reads as a cramped internal tool. I would call this
a genuine, visible step up, confirmable in the before/after screenshots in
§4.

Where I'd still stop short of calling it "legendary": the **main
CEO Brief / Executive Dashboard landing** — the actual first-impression
surface a Fortune 500 board member would see — still shows a bare "No
Workforce Data / Upload Data" empty state in every screenshot taken this
session, because populating it requires wiring a full employee-risk
dataset through `DataUpload.tsx`'s different upload flow, which is out of
this phase's scope (both Phase 11 and 11B focused on the 7 analysis
pages). A genuinely "legendary" verdict should be judged with that
dashboard actually populated and reviewed, not just its empty state. I'm
stating this directly rather than claiming full coverage I don't have
evidence for.

---

## 3. Design pushed further — what changed and where

| File | Change |
|---|---|
| `src/index.css` | `.ambient-glow` (page-level radial gradient atmosphere, dark mode only); `.card-hero-glow` (gold radial wash inside hero cards); `.card-hero-accent` thickened 3px→4px with a glow `box-shadow`; `.card-hero` shadow bumped `elevation-2`→`elevation-3` |
| `src/layout/AppLayout.tsx` | `<main>` gets `.ambient-glow`; content padding `p-6`→`p-6 md:p-8` |
| `src/components/shared/KPICard.tsx` | Hero variant: `card-hero-glow`, `p-6`, `hover:shadow-glow-gold`, bigger icon/gauge (`108px`/`24px` vs `88px`/`20px`), bigger icon badge padding, label no longer truncated on hero (wraps instead — see the truncation-caused-by-the-bigger-gauge fix below) |
| `src/components/shared/RadialKPI.tsx`, `DepartmentBarChart.tsx`, `RecruitmentFunnelChart.tsx` | `dir="ltr"` isolation (the bug fix, §1) |
| `src/components/shared/DepartmentBarChart.tsx` | Per-color `<linearGradient>` defs, bars filled via `url(#...)` instead of flat hex |
| All 7 feature pages | `space-y-6`→`space-y-7`; `text-2xl font-bold`→`text-headline`; KPI grid `gap-4`→`gap-5` |

### A bug I introduced and caught during this same polish pass

Enlarging the hero radial gauge from 88px to 108px shrank the label
column enough that "High Readiness" truncated to "HIGH READINE…" on
Succession's hero card (caught via the same screenshot-and-look discipline
used for the overlap bug, not assumed away). Fixed by removing `truncate`
on the hero label path so it wraps to two lines instead
(`KPICard.tsx`) — re-screenshotted and confirmed clean in both English
(`polish/succession_en.png`) and Arabic (`polish/succession_ar.png`).

---

## 4. Before/after screenshots (post-polish, full page, EN + AR)

All in `scratchpad/polish/*.png`, described in detail below since they
can't be attached inline:

**`nitaqat_en.png`** — Header now bold headline-scale type. Hero
"Saudization %" card: visible gold glow bleeding from the top-right corner
of the card, thick glowing gold top edge, 108px gauge showing "61%" in
green, big white "61.4%" value. Department bar chart below: 9 bars, each
with a visible left-to-right gradient (not flat), Operations bar in gold
(Platinum band), rest in graduated greens, all labels fully legible.

**`nitaqat_ar.png`** — Same content, fully mirrored: sidebar right,
hero card's gauge now sits to the left of its number (correct RTL flex
order), gold glow still anchored correctly, department names ("Operations,"
"Sales," "Information Technology," etc.) fully legible beside their bars
— this is the exact location the overlap bug lived in, now confirmed clean.

**`succession_en.png`** — Hero "High Readiness" card: label wraps
cleanly to two lines ("HIGH / READINESS") after the truncation fix, gauge
shows "17%", value "10" in bold white, "avg score: 41.8" subtitle below.
Non-hero cards ("Employees Evaluated," "Stuck High Performers," "High
Readiness + Low F...") sit at a visibly quieter weight beside it — the
elevation hierarchy the Phase 11 self-critique found too subtle now reads
clearly in a side-by-side glance.

**`succession_ar.png`** — Same layout mirrored; "جاهزية عالية" (High
Readiness) label fits on one line in Arabic without truncating; readiness
table below shows "متوقف" (Stuck) / "عدالة متدنية" (Low Fairness) flag
badges each in their own column, no overlap with employee ID, department,
or tier columns.

**`recruitment_en.png`** / **`recruitment_ar.png`** — Hero "Hired" card
with the same glow/gauge treatment; funnel chart below (English: Applied
55 → Screening 38 → Interview 28 → Offer 16 → Hired 8, labels to the right
of each band; Arabic: same funnel, same stage labels, correctly positioned
beside the shape rather than overlapping it) — the funnel is the other
component that had the RTL bug, now confirmed fixed in the actual funnel
shape, not just the bar charts.

All six screenshots show real, unmodified computed data identical to
values already verified in Phases 8–10 (58 employees / 10 high-readiness /
41.8 avg score for Succession; 220 rows / 135 Saudi / 61.4% for Nitaqat;
55 candidates / 8 hired / 14.5% for Recruitment) — the visual work did not
touch, and did not risk, any figure.

---

## 5. Regression verification

```
py -m pytest tests/ -q
39 failed, 1354 passed, 1 skipped
```

Identical to the Phase 11 baseline — the same pre-existing, unrelated
`passlib`/bcrypt gap (unchanged since Phase 5), zero change in count.
**Zero backend files touched this phase** (Phase 11B was frontend-only,
same as Phase 11).

`npx tsc --noEmit`: clean after every edit this phase (checked
incrementally, not just once at the end).

Console errors: `[]` (empty) across the entire verification sweep — 18
page views (7 pages × EN/AR + dashboard + CEO Brief), the 6 targeted
chart-fix screenshots, and the 6 post-polish screenshots. No error was
introduced by the `dir="ltr"` isolation, the gradient defs, or the ambient
background.

---

## 6. Files changed

| File | Change |
|---|---|
| `executive-ui/src/components/shared/DepartmentBarChart.tsx` | RTL bug fix (`dir="ltr"` wrapper) + gradient-fill bars |
| `executive-ui/src/components/shared/RecruitmentFunnelChart.tsx` | RTL bug fix (`dir="ltr"` wrapper) |
| `executive-ui/src/components/shared/RadialKPI.tsx` | RTL isolation (defensive) |
| `executive-ui/src/components/shared/KPICard.tsx` | Hero variant strengthened; truncation-regression fix |
| `executive-ui/src/index.css` | `.ambient-glow`, `.card-hero-glow`, thickened `.card-hero-accent` |
| `executive-ui/src/layout/AppLayout.tsx` | Ambient background wiring, more generous padding |
| All 7 feature pages (`Nitaqat/Succession/Overtime/Payroll/Recruitment/Fairness/ExitInterview`) | Spacing rhythm + header type scale |

No backend files touched. No governance/disclosure/disclaimer text content
changed (word-for-word identical in every screenshot).
