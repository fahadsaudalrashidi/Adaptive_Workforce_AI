import type { RiskBand } from '../../types'
import { RISK_BAND_CONFIG } from '../../types'
import { useLanguage } from '../../context/LanguageContext'

interface RiskBadgeProps {
  band: RiskBand
  size?: 'sm' | 'md' | 'lg'
  showDot?: boolean
}

export function RiskBadge({ band, size = 'md', showDot = true }: RiskBadgeProps) {
  const { isAr } = useLanguage()
  const config = RISK_BAND_CONFIG[band]

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  }

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full font-medium border
        ${config.bgClass} ${config.textClass} ${config.borderClass}
        ${sizeClasses[size]}
      `}
    >
      {showDot && (
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: config.color }}
        />
      )}
      {isAr ? config.labelAr : config.label}
    </span>
  )
}

interface RiskLegendProps {
  compact?: boolean
}

export function RiskLegend({ compact = false }: RiskLegendProps) {
  const { t } = useLanguage()
  const bands: RiskBand[] = ['stable', 'monitoring', 'strategic_concern', 'priority_review']

  if (compact) {
    return (
      <div className="flex flex-wrap gap-2">
        {bands.map(b => (
          <RiskBadge key={b} band={b} size="sm" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="section-title mb-3">{t('Risk Bands', 'مستويات المخاطر')}</p>
      {bands.map(b => {
        const config = RISK_BAND_CONFIG[b]
        return (
          <div key={b} className="flex items-start gap-2.5">
            <RiskBadge band={b} size="sm" />
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">
              {config.description}
            </p>
          </div>
        )
      })}
    </div>
  )
}
