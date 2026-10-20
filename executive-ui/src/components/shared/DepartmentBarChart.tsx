import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell, LabelList,
} from 'recharts'
import { useTheme } from '../../context/ThemeContext'
import { chartTheme } from '../../styles/design-tokens'

/** Stable, DOM-safe gradient id derived from a hex color, so bars sharing
 * a color (e.g. every "Mid Green" department) share one <linearGradient>
 * def instead of duplicating one per bar. */
function gradientIdFor(color: string): string {
  return `bar-grad-${color.replace('#', '')}`
}

export interface DepartmentBarDatum {
  department: string
  value: number
  /** Optional per-bar color override (e.g. band/tier color) — falls back
   * to the chart's default brand color when omitted. */
  color?: string
  /** Extra fields shown in the tooltip, e.g. { Total: 30, Saudi: 21 } */
  tooltipExtra?: Record<string, string | number>
}

interface DepartmentBarChartProps {
  data: DepartmentBarDatum[]
  valueSuffix?: string
  valueFormatter?: (v: number) => string
  height?: number
  defaultColor?: string
  /** Phase 41: when false, preserves the caller's input order instead of
   * sorting descending by value — for ordered-stage data (AR/AP aging
   * buckets, contract/Iqama urgency tiers) where the category sequence
   * itself is the meaningful signal, not the value ranking. Defaults to
   * true (the original Phase 11 sorted-ranked-comparison behaviour). */
  sortByValue?: boolean
  /** Phase 14: `department` name currently hovered elsewhere on the page
   * (e.g. the matching table row) — dims every other bar so the two views
   * of the same data cross-highlight, matching the legend<->river pattern
   * from Phase 13's WorkforceCompositionRiver. Controlled from outside;
   * omit for the original Phase 11 behaviour (no dimming). */
  highlightedKey?: string | null
  /** Phase 14: fires when the user hovers a bar directly, so a parent can
   * highlight the matching table row — the other half of the cross-
   * highlight pairing. */
  onHoverChange?: (department: string | null) => void
}

function CustomTooltip({ active, payload }: {
  active?: boolean
  payload?: Array<{ payload: DepartmentBarDatum & { formattedValue: string } }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="card p-3 shadow-elevation-2 text-xs min-w-40">
      <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{d.department}</p>
      <div className="flex items-center justify-between gap-4">
        <span className="text-slate-500 dark:text-slate-400">Value</span>
        <span className="font-semibold tabular-nums" style={{ color: d.color }}>{d.formattedValue}</span>
      </div>
      {d.tooltipExtra && Object.entries(d.tooltipExtra).map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-4 mt-0.5">
          <span className="text-slate-500 dark:text-slate-400">{k}</span>
          <span className="text-slate-600 dark:text-slate-300 tabular-nums">{v}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * Phase 11 — horizontal bar chart for department/category comparisons,
 * replacing plain tables (used across Overtime, Nitaqat, Succession,
 * Fairness). Sorted descending by value, with per-bar color coding
 * (band/tier/risk color) carried through visually instead of only in a
 * table-cell badge. Always rendered ALONGSIDE the existing data table
 * (additive, not a replacement) — the table remains for exact figures and
 * screen-reader/print access; the chart is for at-a-glance comparison.
 */
export function DepartmentBarChart({
  data,
  valueSuffix = '',
  valueFormatter,
  height,
  defaultColor = '#3b82f6',
  sortByValue = true,
  highlightedKey,
  onHoverChange,
}: DepartmentBarChartProps) {
  const { isDark } = useTheme()
  const theme = chartTheme(isDark)

  const sorted = sortByValue ? [...data].sort((a, b) => b.value - a.value) : data
  const fmt = valueFormatter ?? ((v: number) => `${v}${valueSuffix}`)
  const chartData = sorted.map(d => ({ ...d, formattedValue: fmt(d.value) }))
  const chartHeight = height ?? Math.max(160, sorted.length * 38)
  const uniqueColors = Array.from(new Set(chartData.map(d => d.color ?? defaultColor)))
  // Longer formatted values (e.g. "SAR 48,600.00" vs "42%") need more room
  // for the end-of-bar LabelList or they clip against the container edge —
  // confirmed via screenshot once currency-formatted charts were added
  // (Financial/Accounting/Logistics/Operations), which this component
  // never rendered before. ~6.2px/char at this font size, floored at the
  // original fixed 36px so short labels are unaffected.
  const longestLabel = Math.max(0, ...chartData.map(d => d.formattedValue.length))
  const rightMargin = Math.max(36, longestLabel * 6.2 + 12)

  return (
    // dir="ltr" is deliberate and load-bearing, not decorative: Recharts'
    // internal axis-label and bar-geometry math assumes LTR and breaks
    // under an inherited dir="rtl" (bars render on top of / overlapping
    // the Y-axis category labels — confirmed via screenshot in Arabic
    // mode). Charts stay LTR internally in RTL apps as standard practice
    // (only the surrounding page chrome mirrors) — this isolates the
    // chart from whatever direction the page around it is in.
    <div dir="ltr" style={{ direction: 'ltr' }}>
      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 4, right: rightMargin, left: 4, bottom: 4 }}
          barCategoryGap={10}
        >
          <defs>
            {uniqueColors.map(color => (
              <linearGradient key={color} id={gradientIdFor(color)} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={color} stopOpacity={0.75} />
                <stop offset="100%" stopColor={color} stopOpacity={1} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.grid} horizontal={false} />
          <XAxis type="number" tick={{ fontSize: 10, fill: theme.text }} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="department"
            width={120}
            tick={{ fontSize: 11, fill: theme.text, fontWeight: 500 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: isDark ? 'rgba(76,93,138,0.12)' : 'rgba(148,163,184,0.12)' }} />
          <Bar
            dataKey="value"
            radius={[0, 6, 6, 0]}
            maxBarSize={22}
            isAnimationActive
            animationDuration={600}
            onMouseEnter={(d: DepartmentBarDatum) => onHoverChange?.(d.department)}
            onMouseLeave={() => onHoverChange?.(null)}
          >
            {chartData.map((d, i) => (
              <Cell
                key={i}
                fill={`url(#${gradientIdFor(d.color ?? defaultColor)})`}
                opacity={highlightedKey && highlightedKey !== d.department ? 0.4 : 1}
                style={{ transition: 'opacity 200ms ease' }}
              />
            ))}
            <LabelList
              dataKey="formattedValue"
              position="right"
              style={{ fontSize: 11, fill: theme.text, fontWeight: 600 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
