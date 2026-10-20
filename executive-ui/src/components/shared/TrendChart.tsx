import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { useTheme } from '../../context/ThemeContext'
import { chartTheme, categorical } from '../../styles/design-tokens'

export interface TrendSeries {
  /** Recharts dataKey — must match a numeric key on every point in `data`. */
  key: string
  label: string
  color?: string
}

interface TrendChartProps {
  /** Each point must carry `period` plus one numeric field per series' `key`. */
  data: Array<Record<string, string | number>>
  series: TrendSeries[]
  valueFormatter?: (v: number) => string
  height?: number
}

function CustomTooltip({ active, payload, label, valueFormatter }: {
  active?: boolean
  payload?: Array<{ dataKey: string; value: number; color: string; name: string }>
  label?: string
  valueFormatter: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="card p-3 shadow-elevation-2 text-xs min-w-40">
      <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 mt-0.5">
          <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full" style={{ background: p.color }} />
            {p.name}
          </span>
          <span className="font-semibold tabular-nums" style={{ color: p.color }}>{valueFormatter(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * Phase 41 — real time-series trend chart (period-over-period), for the
 * data shapes explicitly called out as needing a line/area treatment:
 * Financial Intelligence's P&L/Cash Flow periods, Logistics/Operations'
 * cost/quality period variances, Procurement's per-item price trend. Not
 * used anywhere the backend only returns a snapshot or a period *count* —
 * only where a real array of period-indexed points exists (see
 * PHASE_41_PLATFORM_VISUALIZATION_UPGRADE_REPORT.md's per-module notes for
 * where this was deliberately withheld, e.g. Payroll Movements).
 */
export function TrendChart({ data, series, valueFormatter, height = 240 }: TrendChartProps) {
  const { isDark } = useTheme()
  const theme = chartTheme(isDark)
  const fmt = valueFormatter ?? ((v: number) => v.toLocaleString())

  return (
    <div dir="ltr" style={{ direction: 'ltr' }}>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <defs>
            {series.map((s, i) => {
              const color = s.color ?? categorical[i % categorical.length]
              return (
                <linearGradient key={s.key} id={`trend-grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              )
            })}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={theme.grid} vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 11, fill: theme.text }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fontSize: 10, fill: theme.text }} tickLine={false} axisLine={false} width={48} />
          <Tooltip content={<CustomTooltip valueFormatter={fmt} />} cursor={{ stroke: theme.grid }} />
          {series.length > 1 && (
            <Legend
              verticalAlign="top" height={28}
              wrapperStyle={{ fontSize: 12, color: theme.text }}
            />
          )}
          {series.map((s, i) => {
            const color = s.color ?? categorical[i % categorical.length]
            return (
              <Area
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={color}
                strokeWidth={2}
                fill={`url(#trend-grad-${s.key})`}
                dot={{ r: 3, fill: color, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
                isAnimationActive
                animationDuration={700}
              />
            )
          })}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
