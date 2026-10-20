import { useLanguage } from '../../context/LanguageContext'
import { status } from '../../styles/design-tokens'

/**
 * Phase 15 — fixed color -> meaning key, shown once near the top of a page
 * so an executive doesn't have to memorize what each of the 5 canonical
 * status tones (design-tokens.ts `status`) means. Deliberately small and
 * unobtrusive (a single inline row, not a boxed card) — a legend that
 * competes for attention with the content it's explaining defeats its own
 * purpose.
 */
export function StatusLegend() {
  const { t } = useLanguage()
  const items: { tone: keyof typeof status; label: string }[] = [
    { tone: 'critical', label: t('Critical', 'حرج') },
    { tone: 'caution', label: t('Caution', 'تنبيه') },
    { tone: 'positive', label: t('Positive', 'إيجابي') },
    { tone: 'informational', label: t('Informational', 'معلوماتي') },
    { tone: 'neutral', label: t('Neutral', 'محايد') },
  ]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400 dark:text-slate-500">
      <span className="uppercase tracking-wide font-semibold text-slate-400 dark:text-slate-500">
        {t('Color key:', 'مفتاح الألوان:')}
      </span>
      {items.map(({ tone, label }) => (
        <span key={tone} className="inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: status[tone] }} />
          {label}
        </span>
      ))}
    </div>
  )
}
