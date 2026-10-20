import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from 'recharts'
import { useTheme } from '../../context/ThemeContext'
import { useLanguage } from '../../context/LanguageContext'
import type { TrendPoint } from '../../types'

interface RetentionTrendsProps {
  data: TrendPoint[]
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ value: number; name: string; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  const { t } = useLanguage()
  if (!active || !payload?.length) return null

  return (
    <div className="card p-3 shadow-xl text-xs min-w-36">
      <p className="font-semibold text-slate-700 dark:text-slate-300 mb-2">{label}</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center justify-between gap-4 py-0.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-slate-500 dark:text-slate-400 capitalize">{p.name}</span>
          </div>
          <span className="font-semibold tabular-nums" style={{ color: p.color }}>
            {p.value.toFixed(1)}
            {p.name === t('Stability', 'الاستقرار') ? '' : ''}
          </span>
        </div>
      ))}
    </div>
  )
}

export function RetentionTrends({ data }: RetentionTrendsProps) {
  const { isDark } = useTheme()
  const { t, isAr } = useLanguage()

  const chartData = data.map(d => ({
    month: isAr ? d.monthAr : d.month,
    [t('Stability', 'الاستقرار')]: d.stabilityIndex,
  }))

  const gridColor = isDark ? '#334155' : '#e2e8f0'
  const textColor = isDark ? '#94a3b8' : '#64748b'

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <p className="section-title">
            {t('Stability Index — 12 Month Trend', 'مؤشر الاستقرار — اتجاه 12 شهراً')}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {t('Probabilistic workforce stability score over time', 'درجة الاستقرار الوظيفي الاحتمالي عبر الزمن')}
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800/50">
          <span className="text-xs font-medium text-blue-700 dark:text-blue-400">
            {t('12 months', '12 شهراً')}
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="stabilityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis
            dataKey="month"
            tick={{ fontSize: 10, fill: textColor }}
            tickLine={false}
            axisLine={false}
            interval={1}
          />
          <YAxis
            domain={[60, 85]}
            tick={{ fontSize: 10, fill: textColor }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={70} stroke="#d97706" strokeDasharray="4 4" strokeOpacity={0.6} />
          <Area
            type="monotone"
            dataKey={t('Stability', 'الاستقرار')}
            stroke="#3b82f6"
            strokeWidth={2.5}
            fill="url(#stabilityGradient)"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0, fill: '#3b82f6' }}
          />
        </AreaChart>
      </ResponsiveContainer>

      <p className="text-xs text-slate-400 mt-3 text-center">
        {t(
          'Dashed line: monitoring threshold (70.0). Values above threshold indicate stable organizational patterns.',
          'الخط المتقطع: عتبة المراقبة (70.0). القيم فوق العتبة تشير إلى أنماط تنظيمية مستقرة.'
        )}
      </p>
    </div>
  )
}
