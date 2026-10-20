/**
 * RiskMatrix — Phase 29 Extended.
 *
 * 5×5 Likelihood × Impact heat-map with department dots overlaid.
 * Each cell is colour-coded: green (1–3) → amber (4–9) → red (10–25).
 * Governance footer included.
 */

interface DeptPoint {
  name:       string
  likelihood: number   // 1–5
  impact:     number   // 1–5
}

interface Props {
  departments: DeptPoint[]
  size?:       number
}


function cellColor(l: number, i: number): string {
  const score = l * i
  if (score <= 3)  return '#15803d'
  if (score <= 6)  return '#ca8a04'
  if (score <= 9)  return '#ea580c'
  return '#991b1b'
}


export function RiskMatrix({ departments, size = 300 }: Props) {
  const padding   = 40
  const cellSize  = (size - padding) / 5
  const dotR      = 7

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} aria-label="Risk Matrix">
        {/* Y-axis label */}
        <text
          x={10} y={size / 2} textAnchor="middle"
          transform={`rotate(-90, 10, ${size / 2})`}
          fill="#94a3b8" fontSize={9} fontFamily="system-ui"
        >
          LIKELIHOOD →
        </text>

        {/* X-axis label */}
        <text
          x={padding + (size - padding) / 2} y={size - 2}
          textAnchor="middle"
          fill="#94a3b8" fontSize={9} fontFamily="system-ui"
        >
          IMPACT →
        </text>

        {/* Grid cells */}
        {Array.from({ length: 5 }, (_, row) =>
          Array.from({ length: 5 }, (_, col) => {
            const l = 5 - row   // likelihood: top=5, bottom=1
            const i = col + 1   // impact: left=1, right=5
            const x = padding + col * cellSize
            const y = row * cellSize
            return (
              <g key={`${row}-${col}`}>
                <rect
                  x={x} y={y} width={cellSize} height={cellSize}
                  fill={cellColor(l, i)} stroke="#0f172a" strokeWidth={1}
                  opacity={0.7}
                />
                <text
                  x={x + cellSize / 2} y={y + cellSize / 2 + 4}
                  textAnchor="middle" fill="rgba(255,255,255,0.5)"
                  fontSize={9} fontFamily="system-ui"
                >
                  {l * i}
                </text>
              </g>
            )
          })
        )}

        {/* Y-axis tick labels */}
        {Array.from({ length: 5 }, (_, row) => {
          const l = 5 - row
          return (
            <text
              key={row}
              x={padding - 4}
              y={row * cellSize + cellSize / 2 + 4}
              textAnchor="end"
              fill="#64748b" fontSize={8} fontFamily="system-ui"
            >
              {l}
            </text>
          )
        })}

        {/* X-axis tick labels */}
        {Array.from({ length: 5 }, (_, col) => (
          <text
            key={col}
            x={padding + col * cellSize + cellSize / 2}
            y={5 * cellSize + 12}
            textAnchor="middle"
            fill="#64748b" fontSize={8} fontFamily="system-ui"
          >
            {col + 1}
          </text>
        ))}

        {/* Department dots */}
        {departments.map((dept, idx) => {
          const l = Math.max(1, Math.min(5, Math.round(dept.likelihood)))
          const i = Math.max(1, Math.min(5, Math.round(dept.impact)))
          const cx = padding + (i - 1) * cellSize + cellSize / 2
          const cy = (5 - l) * cellSize + cellSize / 2
          const hue = l * i >= 10 ? '#fca5a5' : l * i >= 5 ? '#fde68a' : '#bbf7d0'
          return (
            <g key={idx}>
              <circle cx={cx} cy={cy} r={dotR} fill={hue} stroke="#0f172a" strokeWidth={1.5} opacity={0.9} />
              <title>{dept.name} (L={l}, I={i}, Score={l * i})</title>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="flex items-center gap-3 text-[10px] text-slate-400">
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-green-700 inline-block" />Low</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-amber-600 inline-block" />Medium</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-700 inline-block" />High</span>
        <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-red-950 inline-block" />Critical</span>
      </div>

      <p className="text-[9px] text-slate-600 text-center max-w-[280px]">
        Statistical risk indicators. Not deterministic predictions. Qualified HR review required.
      </p>
    </div>
  )
}
