import { motion } from 'framer-motion'
import { useCountUp } from '../../hooks/useCountUp'
import { motion as motionTokens } from '../../styles/design-tokens'

interface ProgressRingProps {
  /** 0-100 */
  value: number
  /** Ring color — semantic, chosen by the caller based on domain meaning
   * (e.g. nitaqatBandColor[band], readinessTierColor[tier], a `status`
   * token). Not hardcoded here: whether "high" is good or bad varies per
   * metric (Saudization % vs. overtime prevalence %), and only the caller
   * knows which — this component only owns the shared geometry. */
  color: string
  size?: number
  /** Phase 15: hero variant — larger center digits + a soft glow, for the
   * single most important gauge on a page (e.g. CEO Dashboard's WSI). The
   * stroke-width RATIO is identical to the non-hero ring — only size/glow/
   * type scale change, so every ring on the platform shares one
   * proportion rule regardless of which page it's on. */
  hero?: boolean
  /** Default center label is `{value}%`; set false for raw 0-100 scores
   * that aren't percentages (e.g. a stability index score). */
  showPercentSign?: boolean
  /** Optional second line under the main number (e.g. "Grade B"). */
  centerSub?: string
  trackColor?: string
}

/**
 * Phase 15 — the ONE ring/gauge component every circular progress
 * indicator on the platform renders through. Before this phase there were
 * three independent implementations with three different stroke-width
 * ratios and two different rendering approaches (a Recharts
 * RadialBarChart in the old RadialKPI, and two hand-rolled SVG circles in
 * CEODashboard's HeroGauge and WorkforceStabilityIndex) — confirmed via
 * real screenshots to read as visually inconsistent (thin ring here,
 * thick ring there, teal vs. light blue with no shared meaning). All
 * three now delegate to this one component: same stroke-to-size ratio,
 * same rounded end-caps, same animation curve, same track color, on every
 * page.
 */
const STROKE_RATIO = 0.09

export function ProgressRing({
  value, color, size = 88, hero = false, showPercentSign = true, centerSub, trackColor,
}: ProgressRingProps) {
  const clamped = Math.max(0, Math.min(100, value))
  const animated = useCountUp(clamped)
  const stroke = Math.round(size * STROKE_RATIO)
  const r = size / 2 - stroke / 2 - 1
  const circumference = 2 * Math.PI * r
  const arc = (clamped / 100) * circumference

  return (
    // dir="ltr": the ring's geometry (rotation, arc direction) is
    // symmetric-independent of text direction, but isolating it
    // defensively matches every other Recharts/SVG visual on the platform
    // (see DepartmentBarChart.tsx) rather than relying on symmetry alone.
    <div className="relative flex-shrink-0" dir="ltr" style={{ width: size, height: size, direction: 'ltr' }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={trackColor ?? 'rgba(76,93,138,0.25)'} strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - arc }}
          transition={{ duration: motionTokens.slow, ease: motionTokens.easeExecutive }}
          style={hero ? { filter: `drop-shadow(0 0 14px ${color}99)` } : undefined}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={hero ? 'font-black tabular-nums text-white leading-none' : 'font-bold tabular-nums leading-none'}
          style={{
            fontSize: hero ? size * 0.24 : size * 0.19,
            color: hero ? undefined : color,
            letterSpacing: hero ? '-0.02em' : undefined,
          }}
        >
          {animated.toFixed(0)}{showPercentSign ? '%' : ''}
        </span>
        {centerSub && (
          <span
            className={hero ? 'text-sm font-bold mt-1' : 'text-[10px] font-semibold mt-0.5'}
            style={{ color }}
          >
            {centerSub}
          </span>
        )}
      </div>
    </div>
  )
}
