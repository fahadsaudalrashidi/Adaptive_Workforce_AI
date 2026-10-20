import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { useTheme } from '../../context/ThemeContext'
import { chartTheme, categorical } from '../../styles/design-tokens'

export interface CompositionDatum {
  label: string
  value: number
  /** Optional per-slice color override — falls back to the categorical
   * palette by index, same convention as RecruitmentFunnelChart. */
  color?: string
}

interface CompositionChartProps {
  data: CompositionDatum[]
  valueFormatter?: (v: number) => string
  height?: number
  /** Phase 41: `label` currently hovered elsewhere on the page (e.g. a
   * matching table row) — dims every other slice, same cross-highlight
   * pairing as DepartmentBarChart/RecruitmentFunnelChart. */
  highlightedKey?: string | null
  onHoverChange?: (label: string | null) => void
}

function CustomTooltip({ active, payload }: {
  active?: boolean
  payload?: Array<{ payload: CompositionDatum & { formattedValue: string; pct: string } }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="card p-3 shadow-elevation-2 text-xs min-w-36">
      <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">{d.label}</p>
      <p className="text-slate-500 dark:text-slate-400">{d.formattedValue} · {d.pct}%</p>
    </div>
  )
}

/**
 * Phase 41 — donut composition chart for small-N proportional breakdowns
 * (revenue/expense by category, balance-sheet composition, ABC inventory
 * tiers, shipment status distribution). One fixed convention platform-wide
 * (donut, not a mix of pie/stacked-bar) so every "this adds up to 100%"
 * view reads the same way regardless of domain. Always rendered ALONGSIDE
 * the existing table — same additive discipline as DepartmentBarChart.
 */
export function CompositionChart({
  data, valueFormatter, height = 240, highlightedKey, onHoverChange,
}: CompositionChartProps) {
  const { isDark } = useTheme()
  const theme = chartTheme(isDark)
  const total = data.reduce((s, d) => s + d.value, 0)
  const fmt = valueFormatter ?? ((v: number) => v.toLocaleString())
  const chartData = data.map((d, i) => ({
    ...d,
    color: d.color ?? categorical[i % categorical.length],
    formattedValue: fmt(d.value),
    pct: total > 0 ? ((d.value / total) * 100).toFixed(1) : '0.0',
  }))

  return (
    <div dir="ltr" style={{ direction: 'ltr' }}>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="middle" align="right" layout="vertical"
            wrapperStyle={{ fontSize: 12, color: theme.text }}
            formatter={(value: string) => <span style={{ color: theme.text }}>{value}</span>}
          />
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="label"
            cx="35%"
            cy="50%"
            innerRadius="55%"
            outerRadius="85%"
            paddingAngle={2}
            isAnimationActive
            animationDuration={600}
            onMouseEnter={(d: CompositionDatum) => onHoverChange?.(d.label)}
            onMouseLeave={() => onHoverChange?.(null)}
          >
            {chartData.map((d, i) => (
              <Cell
                key={i}
                fill={d.color}
                opacity={highlightedKey && highlightedKey !== d.label ? 0.35 : 1}
                style={{ transition: 'opacity 200ms ease' }}
              />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
