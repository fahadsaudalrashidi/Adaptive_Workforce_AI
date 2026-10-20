import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, ShieldAlert, Info, CheckCircle2 } from 'lucide-react'
import type { ReactNode } from 'react'
import type { StatusTone } from '../../styles/design-tokens'

interface StatusBannerProps {
  /** One of the 5 canonical tones (design-tokens.ts `status`). Pick by
   * actual meaning, not visual habit — `informational` for anything that
   * is ALWAYS present regardless of findings (governance/methodology
   * notes), `caution`/`critical` only for genuinely situational risk. */
  tone: StatusTone
  icon?: LucideIcon
  children: ReactNode
  /** Smaller inline variant for secondary notices (data-quality warnings,
   * normalization notes) vs. the full-weight page-level banner. */
  compact?: boolean
}

/**
 * Phase 15 — the ONE banner component every page-level alert/disclosure
 * box should render through, replacing the ad hoc `bg-X-50 border-X-200`
 * divs duplicated across all 8 pages. Exists to fix two confirmed real
 * problems from screenshot review:
 *
 * 1. Color collision — amber/orange had become the default for almost
 *    everything (disclaimer banners, risk flags alike), so nothing read
 *    as more urgent than anything else. Each tone here maps to exactly
 *    one meaning (see `status` in design-tokens.ts) and nothing else.
 * 2. Two same-looking banners stacking with no visual differentiation —
 *    `critical` gets a visibly heavier structural treatment (thicker
 *    border, left accent bar, bolder icon/text) than `informational`
 *    (deliberately quiet: thin border, muted icon, no bold text), so a
 *    real urgent flag and a routine disclosure never blur into one
 *    undifferentiated block even when stacked back-to-back.
 */
const TONE_CONFIG: Record<StatusTone, { icon: LucideIcon; box: string; icon_: string; text: string }> = {
  critical: {
    icon: ShieldAlert,
    box: 'bg-red-50 dark:bg-red-950/30 border border-red-300 dark:border-red-700/50 border-s-4 border-s-red-500 dark:border-s-red-500',
    icon_: 'text-red-600 dark:text-red-400',
    text: 'text-red-800 dark:text-red-300 font-medium',
  },
  caution: {
    icon: AlertTriangle,
    box: 'bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40',
    icon_: 'text-amber-500',
    text: 'text-amber-700 dark:text-amber-400',
  },
  informational: {
    icon: Info,
    box: 'bg-slate-50 dark:bg-navy-800/30 border border-slate-200 dark:border-navy-600/40',
    icon_: 'text-slate-400 dark:text-navy-300',
    text: 'text-slate-600 dark:text-navy-200',
  },
  positive: {
    icon: CheckCircle2,
    box: 'bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40',
    icon_: 'text-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-400',
  },
  neutral: {
    icon: Info,
    box: 'bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700',
    icon_: 'text-slate-400',
    text: 'text-slate-500 dark:text-slate-400',
  },
}

export function StatusBanner({ tone, icon, children, compact = false }: StatusBannerProps) {
  const cfg = TONE_CONFIG[tone]
  const Icon = icon ?? cfg.icon
  return (
    <div className={`flex items-start gap-3 ${compact ? 'p-3' : 'p-4'} rounded-xl ${cfg.box}`}>
      <Icon size={tone === 'critical' ? 18 : 16} className={`${cfg.icon_} flex-shrink-0 mt-0.5`} />
      <div className={`text-xs ${cfg.text}`}>{children}</div>
    </div>
  )
}
