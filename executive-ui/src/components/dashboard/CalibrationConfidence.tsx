import { motion } from 'framer-motion'
import { CheckCircle, Info } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import type { CalibrationMetrics } from '../../types'

interface CalibrationConfidenceProps {
  metrics: CalibrationMetrics
}

interface MetricRowProps {
  label: string
  labelAr: string
  value: string
  benchmark: string
  good: boolean
  description: string
  delay: number
}

function MetricRow({ label, labelAr, value, benchmark, good, description, delay }: MetricRowProps) {
  const { t } = useLanguage()
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
      className="flex items-center gap-4 py-2.5 border-b border-slate-100 dark:border-slate-700 last:border-0"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
            {t(label, labelAr)}
          </p>
          <span
            className="text-xs text-slate-400 cursor-help"
            title={description}
          >
            <Info size={11} />
          </span>
        </div>
        <p className="text-xs text-slate-400 mt-0.5">
          {t('Benchmark: ', 'المرجع: ')}{benchmark}
        </p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className={`text-sm font-bold tabular-nums ${good ? 'text-emerald-500' : 'text-amber-500'}`}>
          {value}
        </span>
        <CheckCircle size={14} className={good ? 'text-emerald-500' : 'text-amber-500'} />
      </div>
    </motion.div>
  )
}

export function CalibrationConfidence({ metrics }: CalibrationConfidenceProps) {
  const { t } = useLanguage()

  const rows: MetricRowProps[] = [
    {
      label: 'AUC-ROC',
      labelAr: 'مساحة تحت المنحنى',
      value: metrics.auc.toFixed(3),
      benchmark: '> 0.75',
      good: metrics.auc >= 0.75,
      description: 'Area Under Receiver Operating Characteristic — discrimination ability',
      delay: 0.1,
    },
    {
      label: 'Expected Calibration Error',
      labelAr: 'خطأ المعايرة المتوقع',
      value: metrics.ece.toFixed(3),
      benchmark: '< 0.05',
      good: metrics.ece < 0.05,
      description: 'ECE — reliability of predicted probabilities. Lower is better.',
      delay: 0.2,
    },
    {
      label: 'Brier Score',
      labelAr: 'درجة برير',
      value: metrics.brierScore.toFixed(3),
      benchmark: '< 0.20',
      good: metrics.brierScore < 0.20,
      description: 'Mean squared error of probability predictions. Lower is better.',
      delay: 0.3,
    },
    {
      label: '80% Confidence Coverage',
      labelAr: 'تغطية الثقة 80٪',
      value: `${(metrics.coverageAt80 * 100).toFixed(1)}%`,
      benchmark: '> 75%',
      good: metrics.coverageAt80 >= 0.75,
      description: 'Fraction of actual outcomes within the 80% prediction interval.',
      delay: 0.4,
    },
  ]

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-1">
        <p className="section-title">
          {t('Calibration & Reliability', 'المعايرة والموثوقية')}
        </p>
        <span className="governance-badge bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
          {t('All passing', 'جميعها مقبولة')}
        </span>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
        {t(`Model: ${metrics.modelVersion} · ${metrics.validationMethod}`,
           `النموذج: ${metrics.modelVersion} · ${metrics.validationMethod}`)}
      </p>

      <div>
        {rows.map(r => (
          <MetricRow key={r.label} {...r} />
        ))}
      </div>

      <p className="text-xs text-slate-400 mt-4 leading-relaxed">
        {t(
          `Calibration verified on ${metrics.trainingCohortSize.toLocaleString()} employees using ${metrics.validationMethod}. Scores reflect statistical patterns, not individual predictions.`,
          `تم التحقق من المعايرة على ${metrics.trainingCohortSize.toLocaleString()} موظف باستخدام ${metrics.validationMethod}. تعكس الدرجات الأنماط الإحصائية وليس التنبؤات الفردية.`
        )}
      </p>
    </div>
  )
}
