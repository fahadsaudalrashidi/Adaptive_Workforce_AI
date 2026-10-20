import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { useCountUp } from '../../hooks/useCountUp'
import { ProgressRing } from './ProgressRing'
import { motion as motionTokens } from '../../styles/design-tokens'

interface KPICardProps {
  label: string
  labelAr?: string
  value: string | number
  unit?: string
  trend?: number
  trendLabel?: string
  icon: LucideIcon
  iconColor?: string
  iconBg?: string
  subtitle?: string
  delay?: number
  highlight?: boolean
  /** Phase 11: elevate to the top of the card hierarchy (deeper surface,
   * stronger shadow, gold top accent) for the page's single most important
   * number — not every KPI, just the headline one(s). */
  hero?: boolean
  /** Phase 11: animate numeric values counting up on mount/update, instead
   * of a static number. Parses the leading/trailing non-numeric parts of
   * `value` (e.g. "SAR " prefix, "%" suffix) and preserves them exactly —
   * only the digits animate. Silently no-ops if `value` isn't parseable as
   * a number (e.g. "High Green", "—"). */
  animateValue?: boolean
  /** Phase 11: 0-100 — renders a radial gauge in place of the icon badge,
   * for percentage-based KPIs (Saudization %, overtime prevalence, etc.). */
  radialPct?: number
  radialColor?: string
  /** Phase 14: one extra line of supporting context revealed on hover only
   * — the platform-wide version of the pattern introduced for the CEO
   * Dashboard's StatChip in Phase 13. Never shifts the card's own layout
   * (absolutely positioned via .hover-detail-panel). */
  detail?: string
}

const NUMERIC_PATTERN = /^([^\d-]*)(-?[\d,]+\.?\d*)(.*)$/

function AnimatedValue({ raw }: { raw: string }) {
  const match = raw.match(NUMERIC_PATTERN)
  if (!match) return <>{raw}</>

  const [, prefix, numStr, suffix] = match
  const numeric = parseFloat(numStr.replace(/,/g, ''))
  if (!Number.isFinite(numeric)) return <>{raw}</>

  const decimals = numStr.includes('.') ? numStr.split('.')[1].length : 0
  const animated = useCountUp(numeric)
  const formatted = animated.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })

  return <>{prefix}{formatted}{suffix}</>
}

export function KPICard({
  label,
  value,
  unit,
  trend,
  trendLabel,
  icon: Icon,
  iconColor = 'text-blue-500',
  iconBg = 'bg-blue-500/10',
  subtitle,
  delay = 0,
  highlight = false,
  hero = false,
  animateValue = false,
  radialPct,
  radialColor = '#3b82f6',
  detail,
}: KPICardProps) {
  const trendPositive = trend !== undefined && trend >= 0
  const trendNeutral = trend === 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: motionTokens.slow, ease: motionTokens.easeExecutive }}
      className={`
        relative group
        ${hero ? 'card-hero card-hero-glow p-6 hover:shadow-glow-gold' : 'card p-5'} card-interactive
        ${highlight ? 'ring-1 ring-blue-500/30 dark:ring-blue-500/20' : ''}
      `}
    >
      {hero && <span className="card-hero-accent" aria-hidden="true" />}
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className={hero ? 'metric-label text-navy-200' : 'metric-label truncate'}>{label}</p>
          <div className={hero ? 'mt-3 flex items-baseline gap-1.5' : 'mt-2 flex items-baseline gap-1.5'}>
            <span className={hero ? 'text-display tabular-nums text-white tracking-tight' : 'value-display'}>
              {animateValue && typeof value === 'string' ? <AnimatedValue raw={value} /> : value}
            </span>
            {unit && (
              <span className="text-sm text-slate-500 dark:text-slate-400">{unit}</span>
            )}
          </div>
          {subtitle && (
            <p className={hero ? 'mt-2 text-xs text-navy-200' : 'mt-1.5 text-xs text-slate-500 dark:text-slate-400'}>{subtitle}</p>
          )}
          {trend !== undefined && (
            <div className="mt-2 flex items-center gap-1.5">
              <span
                className={`text-xs font-medium ${
                  trendNeutral
                    ? 'text-slate-500'
                    : trendPositive
                    ? 'text-emerald-500'
                    : 'text-rose-500'
                }`}
              >
                {trendNeutral ? '→' : trendPositive ? '↑' : '↓'}
                {' '}
                {Math.abs(trend).toFixed(1)}
                {trendLabel && ` ${trendLabel}`}
              </span>
              <span className="text-xs text-slate-400">vs prior period</span>
            </div>
          )}
        </div>

        {radialPct !== undefined ? (
          <ProgressRing value={radialPct} color={radialColor} size={hero ? 108 : 88} />
        ) : (
          <div className={`${hero ? 'p-3 rounded-2xl' : 'p-2.5 rounded-xl'} ${iconBg} flex-shrink-0`}>
            <Icon size={hero ? 24 : 20} className={iconColor} />
          </div>
        )}
      </div>

      {detail && (
        <div className="hover-detail-panel left-3 right-3 top-full mt-1.5">
          {detail}
        </div>
      )}
    </motion.div>
  )
}
