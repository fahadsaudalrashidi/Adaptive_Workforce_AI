import type { ReactNode } from 'react'
import type { StatusTone } from '../../styles/design-tokens'

interface StatusBadgeProps {
  tone: StatusTone
  children: ReactNode
  className?: string
}

/**
 * Phase 15 — the ONE small pill/badge component every status tag across
 * the platform should render through (readiness tiers, Nitaqat bands,
 * fairness risk levels, "Stuck"/"Low Fairness" flags, grade badges).
 * Replaces the ~6 near-identical ad hoc badge-color maps that had drifted
 * to similar amber/orange shades with no shared meaning. Same 5 tones as
 * StatusBanner — see design-tokens.ts `status` for the fixed mapping.
 */
const TONE_CLASSES: Record<StatusTone, string> = {
  critical:       'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  caution:        'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  informational:  'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  positive:       'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  neutral:        'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

export function StatusBadge({ tone, children, className = '' }: StatusBadgeProps) {
  return (
    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TONE_CLASSES[tone]} ${className}`}>
      {children}
    </span>
  )
}
