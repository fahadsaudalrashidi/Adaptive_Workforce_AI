/**
 * Zakat Base Estimator — Phase 37.
 *
 * Its own separate page with its own nav entry, placed in a new
 * "Financial Planning" area since it shares no data shape with any other
 * module — see below.
 *
 * Deliberately a MANUAL BALANCE-SHEET ENTRY FORM, not an employee-data
 * upload — the entire point of this page. Zakat is computed from
 * company-level balance-sheet figures (equity, liabilities, fixed assets),
 * not per-employee HR rows like every other module on this platform;
 * forcing it into the upload pattern used everywhere else would be a
 * category error, not a shortcut.
 *
 * This is a SIMPLIFIED TRADITIONAL approximation, NOT the actual ZATCA
 * 2024 Executive Regulations methodology — see
 * backend/core/zakat_estimator_engine.py's module docstring for the full
 * investigation and the specific list of real deductible-category
 * complexity this simplified form does not capture. That gap is
 * disclosed prominently below, not just in code comments.
 */
import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { Landmark, Calculator, RefreshCw } from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'

interface ZakatEstimateResult {
  available: boolean
  reason: string | null
  missing_fields: string[]
  zakat_base_sar: number | null
  zakat_rate: number
  estimated_zakat_liability_sar: number | null
  methodology_gap_note_en: string
  methodology_gap_note_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  sources: string[]
}

const FIELD_LABELS_EN: Record<string, string> = {
  total_equity_sar: 'Total Equity',
  long_term_liabilities_provisions_sar: 'Long-Term Liabilities / Provisions',
  net_fixed_assets_sar: 'Net Fixed Assets',
}
const FIELD_LABELS_AR: Record<string, string> = {
  total_equity_sar: 'إجمالي حقوق الملكية',
  long_term_liabilities_provisions_sar: 'الالتزامات طويلة الأجل / المخصصات',
  net_fixed_assets_sar: 'صافي الأصول الثابتة',
}

function sar(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `SAR ${(n / 1_000_000).toFixed(2)}M`
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

export function ZakatEstimator() {
  const { t, isAr } = useLanguage()
  const [totalEquity, setTotalEquity] = useState('')
  const [ltLiabilities, setLtLiabilities] = useState('')
  const [netFixedAssets, setNetFixedAssets] = useState('')
  const [otherDeductions, setOtherDeductions] = useState('')
  const [result, setResult] = useState<ZakatEstimateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const compute = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload: Record<string, number | null> = {
        total_equity_sar: totalEquity.trim() === '' ? null : parseFloat(totalEquity),
        long_term_liabilities_provisions_sar: ltLiabilities.trim() === '' ? null : parseFloat(ltLiabilities),
        net_fixed_assets_sar: netFixedAssets.trim() === '' ? null : parseFloat(netFixedAssets),
        other_deductions_sar: otherDeductions.trim() === '' ? 0 : parseFloat(otherDeductions),
      }
      const res = await fetch('/api/local/zakat-estimator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      const data = await res.json()
      setResult(data.zakat_estimate)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [totalEquity, ltLiabilities, netFixedAssets, otherDeductions])

  const reset = useCallback(() => {
    setTotalEquity(''); setLtLiabilities(''); setNetFixedAssets(''); setOtherDeductions('')
    setResult(null); setError(null)
  }, [])

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Zakat Base Estimator', 'مقدّر وعاء الزكاة')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t('A simplified planning estimate from manually-entered balance-sheet figures — not an employee data upload.', 'تقدير تخطيطي مبسّط من أرقام ميزانية عمومية تُدخل يدوياً — وليس تحميل بيانات موظفين.')}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="critical">
        <p className="font-medium mb-1">
          {t('This is a SIMPLIFIED TRADITIONAL approximation, NOT the actual ZATCA 2024 Bylaws methodology.', 'هذا تقدير مبسّط تقليدي، وليس منهجية لوائح هيئة الزكاة والضريبة والجمارك (زاتكا) الفعلية لعام 2024.')}
        </p>
        <p>
          {t(
            'The real ZATCA methodology nets specific categories of current/non-current assets against liabilities, applies a minimum/maximum base comparison based on book-vs-adjusted net profit, and recognizes over a dozen individually-defined deductible asset categories (qualifying investments, employee housing assets, statutory deposits, deferred tax assets, right-of-use assets, and more) that this simplified 4-field form does not collect. This tool CANNOT be used to prepare an actual ZATCA filing — engage a qualified zakat/tax professional for that.',
            'تُقاصّ منهجية هيئة الزكاة والضريبة والجمارك (زاتكا) الفعلية فئات محددة من الأصول المتداولة وغير المتداولة مقابل الالتزامات، وتطبّق مقارنة بين الحد الأدنى والأقصى للوعاء استناداً إلى صافي الربح الدفتري مقابل المعدَّل، وتعترف بأكثر من اثنتي عشرة فئة أصول قابلة للخصم مُعرَّفة فردياً (كالاستثمارات المؤهلة، وأصول سكن الموظفين، والودائع النظامية، وأصول الضريبة المؤجلة، وأصول حق الاستخدام، وغيرها) لا تجمعها هذه الأداة المكوّنة من 4 حقول. لا يمكن استخدام هذه الأداة لإعداد إقرار زكوي فعلي — يرجى الاستعانة بمحاسب زكاة/ضرائب مؤهل لذلك.'
          )}
        </p>
      </StatusBanner>

      <div className="card p-6 space-y-4">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {t('Balance Sheet Figures (SAR)', 'أرقام الميزانية العمومية (ريال سعودي)')}
        </p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">{t('Total Equity (required)', 'إجمالي حقوق الملكية (مطلوب)')}</label>
            <input type="number" value={totalEquity} onChange={e => setTotalEquity(e.target.value)} placeholder="0.00"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">{t('Long-Term Liabilities / Provisions (required)', 'الالتزامات طويلة الأجل / المخصصات (مطلوب)')}</label>
            <input type="number" value={ltLiabilities} onChange={e => setLtLiabilities(e.target.value)} placeholder="0.00"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">{t('Net Fixed Assets (required)', 'صافي الأصول الثابتة (مطلوب)')}</label>
            <input type="number" value={netFixedAssets} onChange={e => setNetFixedAssets(e.target.value)} placeholder="0.00"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 dark:text-slate-400 mb-1">{t('Other Deductions (optional, defaults to 0)', 'خصومات أخرى (اختياري، الافتراضي 0)')}</label>
            <input type="number" value={otherDeductions} onChange={e => setOtherDeductions(e.target.value)} placeholder="0.00"
              className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
          </div>
        </div>
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={compute}
            disabled={loading}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? <RefreshCw size={14} className="animate-spin" /> : <Calculator size={14} />}
            {t('Estimate Zakat Base', 'تقدير وعاء الزكاة')}
          </button>
          {result && (
            <button onClick={reset} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1">
              <RefreshCw size={12} />{t('Reset', 'إعادة تعيين')}
            </button>
          )}
        </div>
      </div>

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      {result && !result.available && (
        <StatusBanner tone="caution">
          <p className="font-medium mb-1">{t('Cannot compute — required field(s) missing', 'تعذّر الاحتساب — حقل/حقول مطلوبة مفقودة')}</p>
          <p className="text-xs">{result.reason}</p>
          <ul className="text-xs mt-1 list-disc ms-4">
            {result.missing_fields.map(f => <li key={f}>{isAr ? FIELD_LABELS_AR[f] : FIELD_LABELS_EN[f]}</li>)}
          </ul>
        </StatusBanner>
      )}

      {result && result.available && result.zakat_base_sar != null && result.estimated_zakat_liability_sar != null && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <KPICard label={t('Estimated Zakat Base', 'وعاء الزكاة المقدَّر')} value={sar(result.zakat_base_sar)} icon={Landmark} hero animateValue />
            <KPICard label={t(`Estimated Liability (${(result.zakat_rate * 100).toFixed(1)}%)`, `الالتزام المقدَّر (${(result.zakat_rate * 100).toFixed(1)}%)`)} value={sar(result.estimated_zakat_liability_sar)} icon={Calculator} iconColor="text-red-500" iconBg="bg-red-500/10" animateValue />
          </div>

          <StatusBanner tone="caution">{isAr ? result.methodology_gap_note_ar : result.methodology_gap_note_en}</StatusBanner>
          <StatusBanner tone="informational">{isAr ? result.disclaimer_ar : result.disclaimer_en}</StatusBanner>

          <StatusBanner tone="neutral">
            <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">{t('Sources', 'المصادر')}</p>
            <ul className="text-[11px] opacity-70 space-y-0.5">{result.sources.map((s, i) => <li key={i}>· {s}</li>)}</ul>
          </StatusBanner>
        </motion.div>
      )}

      <GovernanceDisclaimer compact />
    </div>
  )
}
