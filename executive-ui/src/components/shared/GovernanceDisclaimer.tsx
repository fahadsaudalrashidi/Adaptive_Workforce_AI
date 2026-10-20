import { useState } from 'react'
import { AlertCircle, ChevronDown, ChevronUp, Shield } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { StatusBanner } from './StatusBanner'

const GOVERNANCE_DISCLAIMER =
  'GOVERNANCE DISCLAIMER: This output is produced by an AI-assisted workforce analytics platform. ' +
  'Risk indicators are probabilistic and do not represent determinations of individual employee ' +
  'intent or behavior. All HR decisions based on this output require qualified HR professional review.'

const CONFIDENCE_WARNING =
  'CONFIDENCE WARNING: Platform intelligence carries inherent uncertainty. Workforce risk indices ' +
  'should be interpreted as statistical patterns in organizational data, not as predictions about ' +
  'specific individuals. Confidence intervals for individual-level assessments are wide.'

const PDPL_NOTE =
  'PDPL COMPLIANCE NOTE: This platform processes employee data subject to Saudi Personal Data ' +
  'Protection Law (PDPL, Royal Decree M/19). Data subjects must be notified of automated ' +
  'processing. This note does not constitute legal advice or PDPL compliance certification.'

interface GovernanceDisclaimerProps {
  compact?: boolean
  showAll?: boolean
}

export function GovernanceDisclaimer({ compact = false, showAll = false }: GovernanceDisclaimerProps) {
  const [expanded, setExpanded] = useState(showAll)
  const { t } = useLanguage()

  if (compact) {
    // Phase 15 — real-screenshot review: this is the single most-repeated
    // banner in the entire app (rendered on literally every page) and was
    // amber/AlertCircle — the same visual weight as a genuine situational
    // risk warning, even though this text never changes and carries no
    // finding-specific urgency. Moved to `informational`, the same fix
    // applied to every other constant disclosure banner this phase.
    return (
      <StatusBanner tone="informational" compact>
        {t(
          'All risk indicators are probabilistic. HR professional review required before any decision.',
          'جميع مؤشرات المخاطر احتمالية. مراجعة متخصص موارد بشرية مطلوبة قبل اتخاذ أي قرار.'
        )}
      </StatusBanner>
    )
  }

  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-100/50 dark:hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Shield size={16} className="text-blue-500 flex-shrink-0" />
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {t('Governance & Compliance Notices', 'إشعارات الحوكمة والامتثال')}
          </span>
          <span className="governance-badge bg-blue-50 dark:bg-blue-950/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/50">
            {t('3 active', '3 نشطة')}
          </span>
        </div>
        {expanded ? (
          <ChevronUp size={16} className="text-slate-400" />
        ) : (
          <ChevronDown size={16} className="text-slate-400" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-slate-200 dark:border-slate-700 pt-3">
          {[
            {
              // Phase 15: was amber — this notice is constant/always-on,
              // not a situational risk flag, so it now matches the
              // `informational` tone used everywhere else on the platform
              // for standing disclosures.
              icon: AlertCircle,
              color: 'text-slate-400 dark:text-navy-300',
              bg: 'bg-slate-50 dark:bg-navy-800/30 border-slate-200 dark:border-navy-600/40',
              label: t('Governance Disclaimer', 'إخلاء المسؤولية التنظيمية'),
              text: GOVERNANCE_DISCLAIMER,
            },
            {
              icon: AlertCircle,
              color: 'text-blue-500',
              bg: 'bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800/40',
              label: t('Confidence Warning', 'تحذير الثقة'),
              text: CONFIDENCE_WARNING,
            },
            {
              icon: Shield,
              color: 'text-emerald-500',
              bg: 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/40',
              label: t('PDPL Review Note', 'ملاحظة مراجعة أنظمة حماية البيانات'),
              text: PDPL_NOTE,
            },
          ].map(({ icon: Icon, color, bg, label, text }, i) => (
            <div key={i} className={`rounded-lg border p-3 ${bg}`}>
              <div className="flex items-start gap-2">
                <Icon size={14} className={`${color} mt-0.5 flex-shrink-0`} />
                <div>
                  <p className={`text-xs font-semibold ${color} mb-1`}>{label}</p>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{text}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
