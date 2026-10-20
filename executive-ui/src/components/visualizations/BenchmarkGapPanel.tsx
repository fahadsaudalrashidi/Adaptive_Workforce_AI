/**
 * BenchmarkGapPanel — Phase 29F
 * Visualises sector benchmark comparison gaps for AWI indices.
 * Horizontal bar chart: org value vs sector mean, per metric.
 * Governance: k-anonymity ≥5, DP noise ε=0.5 applied server-side.
 */
import { useState } from 'react'
import { useLanguage } from '../../context/LanguageContext'

interface BenchmarkGap {
  metric:      string
  label_en:    string
  label_ar?:   string
  org_value:   number
  sector_mean: number
  gap:         number
  gap_pct:     number
  direction:   string
  significance: 'strength' | 'gap' | 'critical_gap' | 'neutral'
}

interface BenchmarkComparison {
  available:       boolean
  reason?:         string | null
  sector:          string
  sector_label?:   string
  employee_range?: string
  period?:         string
  n_contributors?: number
  gaps:            BenchmarkGap[]
  /** Phase 16 honesty fix: every sector benchmark currently in the database
   * is a seeded internal placeholder (see benchmark_engine.py's
   * `_SEED_BENCHMARKS`), not an aggregate of real client contributions,
   * despite the displayed `n_contributors` count. Drives which disclosure
   * text renders below — never the "k-anonymity enforced" framing for
   * seeded data, since there's no real cross-org data to protect yet. */
  benchmark?: { is_seeded?: boolean } | null
  governance_note?: string
}

interface Props {
  comparison: BenchmarkComparison | null | undefined
  onRequestComparison?: (sector: string) => void
}

const SECTORS = [
  { value: 'banking',    label_en: 'Banking',           label_ar: 'البنوك' },
  { value: 'oil_gas',   label_en: 'Oil & Gas',          label_ar: 'النفط والغاز' },
  { value: 'telecom',   label_en: 'Telecom',            label_ar: 'الاتصالات' },
  { value: 'government',label_en: 'Government',         label_ar: 'الجهات الحكومية' },
  { value: 'retail_fmcg',label_en: 'Retail / FMCG',    label_ar: 'التجزئة' },
  { value: 'healthcare', label_en: 'Healthcare',        label_ar: 'الرعاية الصحية' },
]

function sigColor(sig: string): string {
  if (sig === 'strength')    return '#10b981'
  if (sig === 'critical_gap') return '#ef4444'
  if (sig === 'gap')         return '#f59e0b'
  return '#94a3b8'
}

function sigLabel(sig: string, isAr: boolean): string {
  if (isAr) {
    if (sig === 'strength')    return '▲ أعلى من القطاع'
    if (sig === 'critical_gap') return '▼ فجوة حرجة'
    if (sig === 'gap')         return '▼ دون القطاع'
    return '≈ في مستوى القطاع'
  }
  if (sig === 'strength')    return '▲ Above sector'
  if (sig === 'critical_gap') return '▼ Critical gap'
  if (sig === 'gap')         return '▼ Below sector'
  return '≈ At sector level'
}

export function BenchmarkGapPanel({ comparison, onRequestComparison }: Props) {
  const { t, isAr } = useLanguage()
  const [selectedSector, setSelectedSector] = useState('banking')

  if (!comparison || !comparison.available) {
    return (
      <div className="space-y-3">
        <p className="text-xs text-slate-400">
          {t(
            'Select a sector to compare your workforce indices against Saudi sector benchmarks.',
            'اختر قطاعاً لمقارنة مؤشرات القوى العاملة لديك بمعايير القطاع السعودي.'
          )}
        </p>
        <div className="flex flex-wrap gap-2">
          {SECTORS.map(s => (
            <button
              key={s.value}
              onClick={() => {
                setSelectedSector(s.value)
                onRequestComparison?.(s.value)
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                selectedSector === s.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {isAr ? s.label_ar : s.label_en}
            </button>
          ))}
        </div>
        {comparison?.reason && (
          <p className="text-xs text-slate-500 italic">{comparison.reason}</p>
        )}
      </div>
    )
  }

  const sectorLabel = comparison.sector_label || comparison.sector
  const gaps = comparison.gaps || []
  const isSeeded = comparison.benchmark?.is_seeded !== false // default true: treat unknown as seeded, never overclaim

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <span className="px-2 py-1 rounded bg-blue-900/30 text-blue-400 font-semibold">
          {isAr ? 'القطاع' : 'Sector'}: {sectorLabel}
        </span>
        {comparison.period && (
          <span className="px-2 py-1 rounded bg-slate-700 text-slate-400">
            {comparison.period}
          </span>
        )}
        {isSeeded ? (
          <span className="px-2 py-1 rounded bg-slate-700 text-slate-400">
            {t('Illustrative sector reference', 'مرجع قطاعي إرشادي')}
          </span>
        ) : comparison.n_contributors != null && (
          <span className="px-2 py-1 rounded bg-slate-700 text-slate-400">
            ≥{comparison.n_contributors} {t('organisations', 'منظمة')}
          </span>
        )}
      </div>

      {/* Gap bars */}
      <div className="space-y-3">
        {gaps.map((gap, idx) => {
          const maxVal = Math.max(gap.org_value, gap.sector_mean, 1)
          const orgPct  = (gap.org_value  / maxVal) * 100
          const secPct  = (gap.sector_mean / maxVal) * 100
          const color   = sigColor(gap.significance)
          const label   = isAr && gap.label_ar ? gap.label_ar : gap.label_en

          return (
            <div key={idx} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-300">{label}</span>
                <span className="text-xs font-semibold" style={{ color }}>
                  {sigLabel(gap.significance, isAr)}
                </span>
              </div>
              {/* Org bar */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-blue-400 w-16 text-right shrink-0">
                  {t('Org', 'المنظمة')}
                </span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    style={{ width: `${orgPct.toFixed(1)}%` }}
                  />
                </div>
                <span className="text-xs tabular-nums text-slate-300 w-10 text-right">
                  {gap.org_value.toFixed(1)}
                </span>
              </div>
              {/* Sector bar */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 w-16 text-right shrink-0">
                  {t('Sector', 'القطاع')}
                </span>
                <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-slate-500 transition-all duration-500"
                    style={{ width: `${secPct.toFixed(1)}%` }}
                  />
                </div>
                <span className="text-xs tabular-nums text-slate-500 w-10 text-right">
                  {gap.sector_mean.toFixed(1)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {gaps.length === 0 && (
        <p className="text-xs text-slate-500 italic">
          {t('No gap data available for this comparison.', 'لا توجد بيانات فجوات لهذه المقارنة.')}
        </p>
      )}

      <p className="text-xs text-slate-500 italic pt-1">
        {isSeeded
          ? t(
              'This sector reference is this platform\'s own internal illustrative estimate — not yet backed by real client contributions. Differential-privacy noise and k-anonymity gating are real safeguards that will apply once genuine organisations contribute, but they currently protect a seeded placeholder, not real cross-organisation data. Treat as directional only.',
              'هذا المرجع القطاعي تقدير إرشادي داخلي من هذه المنصة — وليس مدعوماً بعد بمساهمات فعلية من عملاء حقيقيين. ضوضاء الخصوصية التفاضلية وإخفاء الهوية آليات حماية فعلية ستُطبَّق فور مساهمة منظمات حقيقية، لكنها حالياً تحمي بيانات نموذجية وليست بيانات حقيقية عبر المنظمات. يُعامل كمؤشر اتجاهي فقط.'
            )
          : t(
              'Benchmark values include differential privacy noise (ε=0.5). k-anonymity ≥5 enforced. Statistical comparison only.',
              'قيم المعيار تتضمن ضوضاء الخصوصية التفاضلية (ε=0.5). يُطبّق مبدأ إخفاء الهوية k≥5. مقارنة إحصائية فقط.'
            )}
      </p>
    </div>
  )
}
