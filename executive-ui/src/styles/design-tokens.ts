/**
 * Phase 11 design tokens — the JS-side counterpart to the Tailwind config
 * extension in tailwind.config.js. Tailwind classes can't be read by chart
 * libraries (Recharts needs real hex/rgba strings for fills, strokes,
 * gradients), so anything a chart or inline style needs lives here, kept
 * in sync with tailwind.config.js by hand (no build-time codegen — this
 * codebase has no existing token-sync tooling, and adding one would be a
 * disproportionate build-pipeline change for this phase).
 *
 * See DESIGN_SYSTEM.md for the full rationale.
 */

export const navy = {
  950: '#080b16',
  900: '#0c1120',
  800: '#111830',
  700: '#182242',
  600: '#212f56',
  500: '#2e3f70',
  400: '#4c5d8a',
  300: '#7788ab',
  200: '#a9b4cc',
  100: '#d7dce8',
} as const

export const gold = {
  50:  '#fdf8ec',
  100: '#faedc4',
  200: '#f3d888',
  300: '#eabf4f',
  400: '#d4af37',
  500: '#b8932c',
  600: '#967322',
  700: '#74581c',
} as const

/** Functional blue accent — unchanged from the platform's existing usage,
 * kept here only so chart components have one canonical source instead of
 * re-declaring '#3b82f6' per file. */
export const brand = {
  400: '#60a5fa',
  500: '#3b82f6',
  600: '#2563eb',
} as const

/** Semantic risk/status colors — same values as tailwind.config.js's
 * `risk` token, and the same greens/ambers/reds already used ad hoc across
 * Nitaqat band badges, Fairness risk levels, etc. Centralising here so new
 * chart components pick the SAME hex a badge would render, rather than an
 * approximate one. */
export const semantic = {
  stable:   '#059669', // emerald-600
  monitor:  '#d97706', // amber-600
  concern:  '#ea580c', // orange-600
  priority: '#dc2626', // red-600
  info:     '#3b82f6', // blue-500
} as const

/**
 * Phase 15 — the ONE canonical status/tone system for badges, banners, and
 * alerts platform-wide, added in direct response to real-screenshot
 * feedback: orange/amber had become the default color for almost
 * everything (disclaimer banners, "Decision Readiness" badges, "Strategic
 * Concern" tags all landed on similar amber/orange shades), so nothing
 * stood out as genuinely urgent versus routine.
 *
 * Five tones, each with ONE fixed meaning — never mixed or substituted:
 *   - critical      — genuinely urgent/actionable risk. Used sparingly.
 *   - caution       — moderate/watch-list. Used sparingly, never as a
 *                      fallback/default for "don't know what else to use."
 *   - informational — governance/methodology/PDPL notes that are ALWAYS
 *                      present regardless of findings (constant, not
 *                      risk-dependent) — must read as quiet, not alarming.
 *   - positive       — good/stable/favorable.
 *   - neutral        — purely descriptive, no risk connotation.
 *
 * `semantic` above (stable/monitor/concern/priority) remains the 4-tier
 * RISK-BAND color scale used by WorkforceCompositionRiver and similar
 * population-distribution visuals — a different concept (a continuous
 * risk gradient across a population) from this fixed 5-tone UI-status
 * system, so it is kept separate rather than collapsed into it.
 */
export const status = {
  critical:       '#dc2626', // red-600
  caution:        '#d97706', // amber-600
  informational:  '#3b82f6', // blue-500
  positive:       '#059669', // emerald-600
  neutral:        '#64748b', // slate-500
} as const

export type StatusTone = keyof typeof status

/** Ordered categorical palette for multi-series charts (department
 * comparisons, etc.) — navy-family + gold, so charts read as part of the
 * same system rather than a generic default Recharts palette. */
export const categorical = [
  '#3b82f6', // brand blue
  '#d4af37', // gold
  '#059669', // emerald
  '#8b5cf6', // violet
  '#0ea5e9', // sky
  '#d97706', // amber
  '#ec4899', // pink
  '#14b8a6', // teal
  '#f97316', // orange
] as const

/** Nitaqat band -> color, matching the badge colors already established in
 * NitaqatComplianceTracker.tsx's BAND_COLOR map, for the new department
 * bar chart to stay visually consistent with the existing table badges. */
export const nitaqatBandColor: Record<string, string> = {
  Platinum:      gold[400],
  'High Green':  '#10b981',
  'Mid Green':   '#34d399',
  'Low Green':   '#6ee7b7',
  Green:         '#10b981',
  Red:           semantic.priority,
}

/** Succession readiness tier -> color, matching
 * SuccessionReadinessTracker.tsx's TIER_BADGE map. */
export const readinessTierColor: Record<string, string> = {
  'High Readiness':     '#10b981',
  'Emerging Readiness': brand[500],
  Developing:            navy[300],
}

export const motion = {
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
  easeExecutive: [0.16, 1, 0.3, 1] as [number, number, number, number],
} as const

/** Theme-aware chart grid/text colors, mirroring the pattern already used
 * in components/dashboard/RetentionTrends.tsx. */
export function chartTheme(isDark: boolean) {
  return {
    grid: isDark ? navy[600] : '#e2e8f0',
    text: isDark ? navy[300] : '#64748b',
    tooltipBg: isDark ? navy[800] : '#ffffff',
  }
}
