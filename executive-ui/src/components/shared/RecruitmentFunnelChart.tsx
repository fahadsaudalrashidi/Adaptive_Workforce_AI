import { FunnelChart, Funnel, Cell, LabelList, Tooltip, ResponsiveContainer } from 'recharts'
import { categorical } from '../../styles/design-tokens'

export interface FunnelStageDatum {
  stage: string
  candidates: number
  pctOfTotal: number
}

function CustomTooltip({ active, payload }: {
  active?: boolean
  payload?: Array<{ payload: FunnelStageDatum }>
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="card p-3 shadow-elevation-2 text-xs min-w-36">
      <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">{d.stage}</p>
      <p className="text-slate-500 dark:text-slate-400">
        {d.candidates.toLocaleString()} candidates · {d.pctOfTotal.toFixed(1)}%
      </p>
    </div>
  )
}

interface RecruitmentFunnelChartProps {
  data: FunnelStageDatum[]
  /** Phase 14: `stage` currently hovered elsewhere on the page (e.g. the
   * matching table row) — dims every other funnel segment so the chart and
   * table cross-highlight, matching DepartmentBarChart's pattern. */
  highlightedKey?: string | null
  /** Phase 14: fires when the user hovers a segment directly. */
  onHoverChange?: (stage: string | null) => void
}

/**
 * Phase 11 — real funnel visualization for the recruitment pipeline's
 * stage-by-stage conversion data, replacing/augmenting the plain table.
 * The narrowing shape makes drop-off visually legible in a way a table of
 * percentages can't — this is the canonical case the design brief called
 * out specifically. The underlying table remains for exact figures.
 *
 * Phase 14 — added optional chart<->table cross-highlight (highlightedKey/
 * onHoverChange), same pairing pattern as DepartmentBarChart.
 */
export function RecruitmentFunnelChart({ data, highlightedKey, onHoverChange }: RecruitmentFunnelChartProps) {
  const chartData = data.map((d, i) => ({ ...d, fill: categorical[i % categorical.length] }))

  return (
    // dir="ltr" isolates the chart from the page's RTL context — see
    // DepartmentBarChart.tsx for the full explanation (same Recharts/RTL
    // interaction, same fix).
    <div dir="ltr" style={{ direction: 'ltr' }}>
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 52)}>
        <FunnelChart>
          <Tooltip content={<CustomTooltip />} />
          <Funnel
            dataKey="candidates"
            data={chartData}
            isAnimationActive
            animationDuration={700}
            // Recharts' Funnel onMouseEnter/onMouseLeave types are an
            // intersection of the chart-level (data, index, event) handler
            // and a native SVG MouseEventHandler, which no real function
            // signature satisfies — `any` sidesteps the mistyped overload;
            // only `.stage` off the hovered datum is actually used.
            onMouseEnter={(d: any) => onHoverChange?.(d?.stage)}
            onMouseLeave={() => onHoverChange?.(null)}
          >
            <LabelList
              position="right"
              dataKey="stage"
              style={{ fontSize: 12, fontWeight: 600, fill: '#94a3b8' }}
            />
            <LabelList
              position="center"
              dataKey="candidates"
              style={{ fontSize: 13, fontWeight: 700, fill: '#0c1120' }}
            />
            {chartData.map((d, i) => (
              <Cell
                key={i}
                fill={d.fill}
                opacity={highlightedKey && highlightedKey !== d.stage ? 0.4 : 1}
                style={{ transition: 'opacity 200ms ease' }}
              />
            ))}
          </Funnel>
        </FunnelChart>
      </ResponsiveContainer>
    </div>
  )
}
