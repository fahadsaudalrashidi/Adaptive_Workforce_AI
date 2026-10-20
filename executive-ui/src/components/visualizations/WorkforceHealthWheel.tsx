/**
 * WorkforceHealthWheel — Phase 29G
 * Segmented donut chart showing 4 risk band proportions.
 * SVG arc segments, no external library.
 */

interface Segment {
  label:  string
  count:  number
  color:  string
  pct:    number
}

interface Props {
  riskBandCounts: Record<string, number>
  totalEmployees: number
  size?: number
}


function describeDonutArc(cx: number, cy: number, outer: number, inner: number, startDeg: number, endDeg: number): string {
  const toRad = (d: number) => (d * Math.PI) / 180
  const x1o = cx + outer * Math.cos(toRad(startDeg - 90))
  const y1o = cy + outer * Math.sin(toRad(startDeg - 90))
  const x2o = cx + outer * Math.cos(toRad(endDeg - 90))
  const y2o = cy + outer * Math.sin(toRad(endDeg - 90))
  const x1i = cx + inner * Math.cos(toRad(endDeg - 90))
  const y1i = cy + inner * Math.sin(toRad(endDeg - 90))
  const x2i = cx + inner * Math.cos(toRad(startDeg - 90))
  const y2i = cy + inner * Math.sin(toRad(startDeg - 90))
  const large = endDeg - startDeg > 180 ? 1 : 0
  return [
    `M ${x1o} ${y1o}`,
    `A ${outer} ${outer} 0 ${large} 1 ${x2o} ${y2o}`,
    `L ${x1i} ${y1i}`,
    `A ${inner} ${inner} 0 ${large} 0 ${x2i} ${y2i}`,
    'Z',
  ].join(' ')
}

export function WorkforceHealthWheel({ riskBandCounts, totalEmployees, size = 200 }: Props) {
  const cx = size / 2
  const cy = size / 2
  const outer = size * 0.44
  const inner = size * 0.26

  const bands: { key: string; label: string; color: string; glow: string }[] = [
    { key: 'Stable',           label: 'Stable',    color: '#10b981', glow: '#10b98144' },
    { key: 'Monitoring',       label: 'Monitor',   color: '#f59e0b', glow: '#f59e0b44' },
    { key: 'Strategic Concern',label: 'Concern',   color: '#f97316', glow: '#f9731644' },
    { key: 'Priority Review',  label: 'Priority',  color: '#ef4444', glow: '#ef444444' },
  ]

  const segments: Segment[] = bands.map(b => {
    const count = riskBandCounts[b.key] ?? riskBandCounts[b.key.toLowerCase().replace(' ', '_')] ?? 0
    return { label: b.label, count, color: b.color, pct: totalEmployees > 0 ? count / totalEmployees : 0 }
  })

  // Build arc angles
  let cursor = 0
  const arcs = segments.map(seg => {
    const start = cursor
    const sweep = seg.pct * 360
    cursor += sweep
    return { ...seg, start, end: start + sweep }
  })

  const stableCount = riskBandCounts['Stable'] ?? 0
  const stablePct = totalEmployees > 0 ? Math.round(stableCount / totalEmployees * 100) : 0

  return (
    <div className="flex flex-col items-center gap-3">
      <svg width={size} height={size} className="overflow-visible">
        <defs>
          {arcs.map((_seg, i) => (
            <filter key={i} id={`glow-${i}`}>
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          ))}
        </defs>

        {arcs.map((seg, i) => {
          if (seg.pct < 0.005) return null
          const gap = 1.5
          return (
            <path
              key={i}
              d={describeDonutArc(cx, cy, outer, inner, seg.start + gap / 2, seg.end - gap / 2)}
              fill={seg.color}
              opacity={0.85}
            />
          )
        })}

        {/* Centre text */}
        <text x={cx} y={cy - 8} textAnchor="middle" className="fill-white" fontSize="20" fontWeight="bold">
          {stablePct}%
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="fill-slate-400" fontSize="9">
          Stable
        </text>
        <text x={cx} y={cy + 22} textAnchor="middle" className="fill-slate-400" fontSize="9">
          {totalEmployees.toLocaleString()} total
        </text>
      </svg>

      {/* Legend */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {arcs.map((seg, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: seg.color }} />
            <span className="text-slate-400">{seg.label}</span>
            <span className="text-slate-200 font-semibold ml-auto">{seg.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
