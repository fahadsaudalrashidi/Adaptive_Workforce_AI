import { motion } from 'framer-motion'
import { CheckCircle2 } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  reason: string
  checklistLabel: string
  /** key -> whether this column/signal was detected */
  columnsDetected: Record<string, boolean>
  /** key -> display label (already language-resolved by the caller via t()) */
  columnLabels: Record<string, string>
}

/**
 * Phase 11 — premium treatment for this platform's honest "data not
 * detected" states (Payroll Movements, Recruitment Pipeline, Fairness
 * Audit, Nitaqat, Succession Readiness all have one). Functionally
 * identical to the plain boxes it replaces — same reason text, same
 * columns-detected data, word-for-word — just presented as a considered
 * empty state (icon ring, requirement-chip grid) instead of looking like
 * an error message, since this honesty is a genuine platform strength.
 */
export function EmptyState({
  icon: Icon,
  title,
  reason,
  checklistLabel,
  columnsDetected,
  columnLabels,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="card-flat p-8 text-center"
    >
      <div className="empty-state-icon-ring mx-auto mb-4">
        <Icon size={24} className="text-navy-200" />
      </div>
      <p className="text-title text-slate-700 dark:text-slate-200 mb-2">{title}</p>
      <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-6">{reason}</p>

      <p className="text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wide font-semibold mb-3">
        {checklistLabel}
      </p>
      <div className="grid sm:grid-cols-2 gap-2 max-w-xl mx-auto text-left rtl:text-right">
        {Object.entries(columnsDetected).map(([key, present]) => (
          <div
            key={key}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs transition-colors duration-base ${
              present
                ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/40'
                : 'bg-transparent border-slate-200 dark:border-navy-600/50'
            }`}
          >
            {present ? (
              <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" />
            ) : (
              <span className="w-[14px] h-[14px] rounded-full border border-slate-300 dark:border-navy-400 flex-shrink-0" />
            )}
            <span className={present ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'}>
              {columnLabels[key] ?? key}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  )
}
