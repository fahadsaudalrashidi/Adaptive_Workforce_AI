import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'
import { RiskBadge } from '../shared/RiskBadge'
import type { DepartmentRisk } from '../../types'
import { RISK_BAND_CONFIG } from '../../types'

interface DepartmentRiskHeatmapProps {
  departments: DepartmentRisk[]
}

function TrendIcon({ trend }: { trend: DepartmentRisk['trend'] }) {
  if (trend === 'improving') return <TrendingUp size={14} className="text-emerald-500" />
  if (trend === 'declining') return <TrendingDown size={14} className="text-rose-500" />
  return <Minus size={14} className="text-slate-400" />
}

export function DepartmentRiskHeatmap({ departments }: DepartmentRiskHeatmapProps) {
  const { t, isAr } = useLanguage()

  const sorted = [...departments].sort((a, b) => a.stabilityScore - b.stabilityScore)

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-700">
        <p className="section-title">{t('Department Stability Overview', 'نظرة عامة على استقرار الأقسام')}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          {t('Sorted by stability score — lowest first', 'مرتبة حسب درجة الاستقرار — الأدنى أولاً')}
        </p>
      </div>

      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {sorted.map((dept, idx) => {
          const config = RISK_BAND_CONFIG[dept.riskBand]
          const scoreWidth = `${dept.stabilityScore}%`

          return (
            <motion.div
              key={dept.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.06, duration: 0.3 }}
              className="px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors"
            >
              <div className="flex items-center gap-4">
                {/* Dept name */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200 truncate">
                      {isAr ? dept.nameAr : dept.name}
                    </p>
                    <TrendIcon trend={dept.trend} />
                  </div>

                  {/* Progress bar */}
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full rounded-full"
                        style={{ backgroundColor: config.color }}
                        initial={{ width: 0 }}
                        animate={{ width: scoreWidth }}
                        transition={{ delay: idx * 0.06 + 0.2, duration: 0.8, ease: 'easeOut' }}
                      />
                    </div>
                    <span
                      className="text-sm font-semibold tabular-nums w-10 text-right"
                      style={{ color: config.color }}
                    >
                      {dept.stabilityScore.toFixed(0)}
                    </span>
                  </div>
                </div>

                {/* Right side */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  <RiskBadge band={dept.riskBand} size="sm" />
                  <span className="text-xs text-slate-400 w-16 text-right tabular-nums">
                    {dept.employeeCount.toLocaleString()} {t('emp', 'موظف')}
                  </span>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
