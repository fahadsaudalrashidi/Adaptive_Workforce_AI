import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { motion } from 'framer-motion'
import { useLanguage } from '../../context/LanguageContext'
import type { TheoryContribution } from '../../types'

interface ConstructContributionChartProps {
  theories: TheoryContribution[]
}

interface CustomLabelProps {
  cx: number
  cy: number
  midAngle: number
  innerRadius: number
  outerRadius: number
  percent: number
}

function CustomLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: CustomLabelProps) {
  const RADIAN = Math.PI / 180
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + radius * Math.cos(-midAngle * RADIAN)
  const y = cy + radius * Math.sin(-midAngle * RADIAN)

  if (percent < 0.08) return null

  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

export function ConstructContributionChart({ theories }: ConstructContributionChartProps) {
  const { t, isAr } = useLanguage()

  const data = theories.map(th => ({
    name: th.shortName,
    fullName: isAr ? th.theoryAr : th.theory,
    value: th.contribution,
    color: th.color,
  }))

  return (
    <div className="card p-5">
      <p className="section-title mb-1">
        {t('Theory Construct Contributions', 'مساهمات البنى النظرية')}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
        {t('Relative influence of validated organizational behavior theories', 'التأثير النسبي للنظريات السلوكية التنظيمية المعتمدة')}
      </p>

      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            outerRadius={80}
            innerRadius={40}
            dataKey="value"
            labelLine={false}
            label={CustomLabel}
          >
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.color} strokeWidth={0} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number, name: string) => [`${value.toFixed(1)}%`, name]}
            contentStyle={{
              backgroundColor: 'var(--tooltip-bg, #1e293b)',
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '12px',
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="space-y-2 mt-2">
        {theories.map((th, idx) => (
          <motion.div
            key={th.shortName}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.08, duration: 0.3 }}
            className="flex items-center gap-2.5"
          >
            <span
              className="w-2.5 h-2.5 rounded-full flex-shrink-0"
              style={{ backgroundColor: th.color }}
            />
            <span className="text-xs text-slate-600 dark:text-slate-400 flex-1 truncate">
              {th.shortName} — {isAr ? th.theoryAr : th.theory}
            </span>
            <span className="text-xs font-semibold tabular-nums" style={{ color: th.color }}>
              {th.contribution.toFixed(1)}%
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
