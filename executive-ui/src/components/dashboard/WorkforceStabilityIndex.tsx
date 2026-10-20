import { motion } from 'framer-motion'
import { useLanguage } from '../../context/LanguageContext'
import { ProgressRing } from '../shared/ProgressRing'
import { status } from '../../styles/design-tokens'

interface WorkforceStabilityIndexProps {
  score: number
  trend: number
}

// Phase 15 — collapsed from a 4-tier scale (which included an orange
// "concern" step not part of the canonical 5-tone status system, see
// design-tokens.ts) down to the 3 tones that actually apply to a
// higher-is-better score: positive/caution/critical. Orange is no longer
// used as an implicit 4th severity level here.
function getScoreColor(score: number): string {
  if (score >= 65) return status.positive
  if (score >= 45) return status.caution
  return status.critical
}

function getScoreLabel(score: number, isAr: boolean): string {
  if (score >= 80) return isAr ? 'مستقر جداً' : 'Highly Stable'
  if (score >= 65) return isAr ? 'مستقر' : 'Stable'
  if (score >= 45) return isAr ? 'مراقبة مطلوبة' : 'Monitor'
  return isAr ? 'مراجعة مطلوبة' : 'Review Required'
}

export function WorkforceStabilityIndex({ score, trend }: WorkforceStabilityIndexProps) {
  const { t, isAr } = useLanguage()
  const color = getScoreColor(score)

  return (
    <div className="card p-6 flex flex-col items-center">
      <p className="section-title mb-6">
        {t('Workforce Stability Index', 'مؤشر الاستقرار الوظيفي')}
      </p>

      {/* Phase 15: now the shared ProgressRing (was a third, independently
          hand-rolled SVG ring with its own stroke width — see PHASE_15
          report §4) so this gauge shares the exact same proportions as
          every other ring on the platform. */}
      <ProgressRing value={score} color={color} size={160} showPercentSign={false} centerSub={t('/ 100', '/ 100')} />

      {/* Status label */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0, duration: 0.4 }}
        className="mt-4 flex flex-col items-center gap-2"
      >
        <span
          className="text-sm font-semibold"
          style={{ color }}
        >
          {getScoreLabel(score, isAr)}
        </span>

        {trend !== 0 && (
          <div className="flex items-center gap-1.5">
            <span
              className={`text-xs font-medium ${trend >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}
            >
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)} pts
            </span>
            <span className="text-xs text-slate-400">
              {t('vs 6 months ago', 'مقارنة بـ 6 أشهر')}
            </span>
          </div>
        )}
      </motion.div>

      {/* Scale labels */}
      <div className="mt-4 w-full flex justify-between text-xs text-slate-400">
        <span>{t('Critical', 'حرج')}</span>
        <span>{t('Excellent', 'ممتاز')}</span>
      </div>
      <div className="w-full h-1.5 rounded-full mt-1 overflow-hidden bg-gradient-to-r from-red-500 via-amber-400 via-emerald-400 to-emerald-500" />
    </div>
  )
}
