/**
 * Operations Intelligence — Phase 35 (Business Intelligence Suite, Module 6,
 * final of the six originally-planned domains).
 *
 * The most abstract domain of the six: no single obvious data shape like
 * "shipments" or "inventory items." Works from a generic OPERATIONAL-UNIT-
 * PER-PERIOD record (department/branch/production-line/machine, whatever
 * the upload calls it) and detects whichever of output/hours-operated/
 * hours-available/downtime/quality/cost the data actually contains.
 *
 * Utilization is never estimated without a real hours-available (capacity)
 * column. Bottleneck flags require at least 3 periods of data per unit —
 * a unit with fewer periods still shows its raw numbers, just not the
 * confident "bottleneck" label, even if those raw numbers look worse than
 * a confidently-flagged unit's.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, RefreshCw, Zap, Gauge, AlertOctagon, ShieldCheck, TrendingDown, Wallet,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { StatusBadge } from '../components/shared/StatusBadge'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { TrendChart } from '../components/shared/TrendChart'

// ── Types (mirror backend/core/operations_intelligence_engine.py) ─────────

interface ProductivityItem { unit: string; total_output: number; total_hours_operated: number; productivity: number; n_periods: number }
interface ProductivityData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  items: ProductivityItem[]; narrative_en: string; narrative_ar: string
}
interface UtilizationItem { unit: string; total_hours_operated: number; total_hours_available: number; utilization_pct: number; n_periods: number }
interface UtilizationData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  items: UtilizationItem[]; narrative_en: string; narrative_ar: string
}
interface DowntimeUnitItem { unit: string; total_downtime_hours: number; downtime_rate_pct: number | null; n_periods: number }
interface DowntimeCauseTheme { theme: string; n_mentions: number; pct_of_reasons: number }
interface DowntimeData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  total_downtime_hours: number; by_unit: DowntimeUnitItem[]; cause_breakdown_method: string
  cause_themes: DowntimeCauseTheme[]; top_terms: { term: string; n: number }[]; min_mentions_for_theme: number
  narrative_en: string; narrative_ar: string
}
interface QualityUnitItem { unit: string; defect_rate_pct: number | null; n_periods: number }
interface QualityPeriodVariance { period: string; prior_period: string; defect_rate_prior: number; defect_rate_current: number; variance: number; variance_pct: number | null }
interface QualityData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  overall_defect_rate_pct: number | null; by_unit: QualityUnitItem[]; period_variances: QualityPeriodVariance[]
  min_periods_required: number; narrative_en: string; narrative_ar: string
}
interface BottleneckCandidate {
  unit: string; n_periods: number; sufficient_sample: boolean; utilization_pct: number | null
  downtime_rate_pct: number | null; productivity: number | null; is_bottleneck: boolean
}
interface BottleneckData {
  available: boolean; reason: string | null; min_periods_for_confidence: number
  utilization_gap_pp_threshold: number; fleet_avg_utilization_pct: number | null
  items: BottleneckCandidate[]; narrative_en: string; narrative_ar: string
}
interface CostPerUnitItem { unit: string; total_cost: number; total_output: number; cost_per_unit: number; n_periods: number }
interface CostPerUnitData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  items: CostPerUnitItem[]; narrative_en: string; narrative_ar: string
}
interface OperationsIntelligenceData {
  productivity: ProductivityData; utilization: UtilizationData; downtime: DowntimeData
  quality: QualityData; bottleneck: BottleneckData; cost_per_unit: CostPerUnitData
  disclaimer_en: string; disclaimer_ar: string; sources: string[]
}
interface ApiResponse { filename: string; row_count?: number; operations_intelligence: OperationsIntelligenceData }

const COLUMN_LABELS_EN: Record<string, string> = {
  unit: 'Operational unit — department/branch/line/machine (required)',
  period: 'Period (required for trend and bottleneck-confidence views)',
  output: 'Output / production count (required for productivity and cost-per-unit)',
  hours_operated: 'Hours operated (required for productivity and utilization)',
  hours_available: 'Hours available / capacity (required for utilization — never assumed)',
  downtime_hours: 'Downtime hours (required for downtime analysis)',
  downtime_reason: 'Downtime reason/cause (optional — enables cause breakdown)',
  defect_count: 'Defect count (required for quality analysis, unless a direct quality-score column exists)',
  quality_score: 'Defect rate / quality score — direct column (alternative to defect count)',
  cost: 'Operating cost (required for cost-per-unit-of-operation)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  unit: 'الوحدة التشغيلية (مطلوبة)', period: 'الفترة (مطلوبة)',
  output: 'الإنتاج (مطلوب)', hours_operated: 'ساعات التشغيل (مطلوبة)',
  hours_available: 'الساعات المتاحة / السعة (مطلوبة)', downtime_hours: 'ساعات التوقف (مطلوبة)',
  downtime_reason: 'سبب التوقف (اختياري)', defect_count: 'عدد العيوب (مطلوب)',
  quality_score: 'معدل العيوب / درجة الجودة (بديل)', cost: 'تكلفة التشغيل (مطلوبة)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function num(n: number, digits = 2): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
function sar(n: number): string { return `SAR ${num(n)}` }

type TabKey = 'productivity' | 'utilization' | 'downtime' | 'quality' | 'bottleneck' | 'costperunit'

export function OperationsIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('productivity')
  const [result, setResult] = useState<ApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const runUpload = useCallback(async (file: File) => {
    setStatus('loading')
    setError(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch('/api/local/operations-intelligence', {
        method: 'POST', body: formData, signal: controller.signal,
      })
      clearTimeout(timeoutId)
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${response.status})`)
      }
      const data = (await response.json()) as ApiResponse
      setResult(data)
      setStatus('done')
    } catch (err) {
      clearTimeout(timeoutId)
      const isAbort = err instanceof Error && err.name === 'AbortError'
      setError(
        isAbort
          ? t('Upload timed out after 30s. Please try again.', 'انتهت مهلة التحميل بعد 30 ثانية. يرجى المحاولة مرة أخرى.')
          : err instanceof Error ? err.message : String(err)
      )
      setStatus('error')
    }
  }, [t])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) void runUpload(file)
  }, [runUpload])

  const reset = useCallback(() => {
    setStatus('idle')
    setResult(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const ops = result?.operations_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Operations Intelligence', 'ذكاء العمليات')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Productivity, Utilization, Downtime, Quality, Bottleneck Identification, and Cost per Unit from your own operational data.',
            'الإنتاجية، معدل الاستغلال، التوقف، الجودة، تحديد الاختناقات، وتكلفة الوحدة من بيانات عملياتك الخاصة.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload an operational-unit-per-period export (Unit, Period, Output, HoursOperated, HoursAvailable, DowntimeHours, optionally DowntimeReason/DefectCount/Cost) — a department, branch, production line, or machine, whatever your data calls it. Utilization is never estimated without a real hours-available (capacity) column. A unit needs at least 3 periods of data before it can be confidently flagged as a bottleneck.',
          'حمّل بيانات تشغيلية لكل وحدة/فترة (Unit و Period و Output و HoursOperated و HoursAvailable، واختيارياً DowntimeReason/DefectCount/Cost). لا يُقدَّر معدل الاستغلال دون عمود سعة حقيقي. تحتاج الوحدة إلى 3 فترات بيانات على الأقل ليتم رصدها كاختناق بثقة.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <label className="block cursor-pointer">
          <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv,.parquet,.json" onChange={handleFileSelect} className="hidden" />
          <div className="border-2 border-dashed border-slate-200 dark:border-navy-500/60 rounded-xl p-10 text-center hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-base">
            <Upload size={28} className="text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              {t('Click to upload or drag and drop', 'انقر للتحميل أو اسحب وأفلت')}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {t('Supported: .xlsx, .xls, .csv, .parquet, .json', 'المدعوم: xlsx و xls و csv و parquet و json')}
            </p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Analyzing operations…', 'جارٍ تحليل العمليات…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && ops && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {result?.filename} · {result?.row_count?.toLocaleString()} {t('rows', 'صفوف')}
              </span>
              <button onClick={reset} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1">
                <RefreshCw size={12} />
                {t('Analyze another file', 'تحليل ملف آخر')}
              </button>
            </div>

            <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
              {([
                ['productivity', t('Productivity', 'الإنتاجية'), Zap],
                ['utilization', t('Utilization', 'معدل الاستغلال'), Gauge],
                ['downtime', t('Downtime', 'التوقف'), AlertOctagon],
                ['quality', t('Quality', 'الجودة'), ShieldCheck],
                ['bottleneck', t('Bottlenecks', 'الاختناقات'), TrendingDown],
                ['costperunit', t('Cost per Unit', 'تكلفة الوحدة'), Wallet],
              ] as [TabKey, string, typeof Zap][]).map(([key, label, Icon]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                    tab === key ? 'border-blue-500 text-blue-600 dark:text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>

            {tab === 'productivity' && <ProductivityTab data={ops.productivity} t={t} isAr={isAr} />}
            {tab === 'utilization' && <UtilizationTab data={ops.utilization} t={t} isAr={isAr} />}
            {tab === 'downtime' && <DowntimeTab data={ops.downtime} t={t} isAr={isAr} />}
            {tab === 'quality' && <QualityTab data={ops.quality} t={t} isAr={isAr} />}
            {tab === 'bottleneck' && <BottleneckTab data={ops.bottleneck} t={t} />}
            {tab === 'costperunit' && <CostPerUnitTab data={ops.cost_per_unit} t={t} isAr={isAr} />}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}

type T = (en: string, ar: string) => string

function NarrativeCard({ en, ar, isAr }: { en: string; ar: string; isAr: boolean }) {
  return <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? ar : en}</p></div>
}

// ── 1. Productivity ──────────────────────────────────────────────────────

function ProductivityTab({ data, t, isAr }: { data: ProductivityData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Zap}
        title={t('Productivity not computable from this upload', 'الإنتاجية غير قابلة للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Productivity by Unit', 'الإنتاجية حسب الوحدة')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.unit, value: i.productivity }))}
            valueFormatter={(v) => v.toFixed(2)}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Output', 'الإنتاج')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Hours Operated', 'ساعات التشغيل')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Productivity (units/hr)', 'الإنتاجية (وحدة/ساعة)')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_output, 0)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_hours_operated, 0)}</td>
                <td className="px-4 py-2.5 text-right font-mono font-semibold text-slate-700 dark:text-slate-300">{i.productivity.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 2. Utilization ────────────────────────────────────────────────────────

function UtilizationTab({ data, t, isAr }: { data: UtilizationData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Gauge}
        title={t('Utilization not computable from this upload', 'معدل الاستغلال غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Utilization by Unit', 'معدل الاستغلال حسب الوحدة')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.unit, value: i.utilization_pct, color: i.utilization_pct >= 80 ? '#059669' : i.utilization_pct >= 60 ? '#d97706' : '#dc2626' }))}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Operated', 'المُشغّل')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Available', 'المتاح')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Utilization', 'معدل الاستغلال')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_hours_operated, 0)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_hours_available, 0)}</td>
                <td className="px-4 py-2.5 text-right"><StatusBadge tone={i.utilization_pct >= 80 ? 'positive' : i.utilization_pct >= 60 ? 'caution' : 'critical'}>{i.utilization_pct.toFixed(1)}%</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 3. Downtime ───────────────────────────────────────────────────────────

function DowntimeTab({ data, t, isAr }: { data: DowntimeData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={AlertOctagon}
        title={t('Downtime analysis not computable from this upload', 'تحليل التوقف غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Downtime', 'إجمالي التوقف')} value={`${num(data.total_downtime_hours, 0)} ${t('hrs', 'ساعة')}`} icon={AlertOctagon} hero />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.by_unit.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Downtime Hours by Unit', 'ساعات التوقف حسب الوحدة')}</p>
          <DepartmentBarChart
            data={data.by_unit.map(i => ({ department: i.unit, value: i.total_downtime_hours }))}
            defaultColor="#dc2626"
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('By Unit', 'حسب الوحدة')}</div>
        <table className="w-full text-sm">
          <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Downtime Hours', 'ساعات التوقف')}</th>
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Downtime Rate', 'معدل التوقف')}</th>
          </tr></thead>
          <tbody>
            {data.by_unit.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_downtime_hours, 0)}</td>
                <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{i.downtime_rate_pct != null ? `${i.downtime_rate_pct}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.cause_themes.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Downtime Causes', 'أسباب التوقف')}</p>
          <DepartmentBarChart
            data={data.cause_themes.map(th => ({ department: th.theme, value: th.n_mentions }))}
          />
        </div>
      )}
      {data.cause_themes.length > 0 && (
        <div className="card overflow-x-auto">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
            {t(`Downtime Cause Breakdown (${data.cause_breakdown_method})`, 'تصنيف أسباب التوقف')}
          </div>
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Cause', 'السبب')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Mentions', 'الإشارات')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('% of Reasons', '% من الأسباب')}</th>
            </tr></thead>
            <tbody>
              {data.cause_themes.map((th) => (
                <tr key={th.theme} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{th.theme}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{th.n_mentions}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{th.pct_of_reasons}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.cause_breakdown_method !== 'categorical' && data.cause_themes.length > 0 && (
        <StatusBanner tone="informational" compact>
          {t(
            `Themes mentioned by fewer than ${data.min_mentions_for_theme} distinct records are suppressed — same threshold reused from Exit Interview and Logistics Returns. No raw downtime-reason text is ever shown.`,
            `يتم استبعاد الأسباب التي تُذكر في أقل من ${data.min_mentions_for_theme} سجلات.`
          )}
        </StatusBanner>
      )}
    </div>
  )
}

// ── 4. Quality ────────────────────────────────────────────────────────────

function QualityTab({ data, t, isAr }: { data: QualityData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title={t('Quality analysis not computable from this upload', 'تحليل الجودة غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        {data.overall_defect_rate_pct != null && (
          <KPICard label={t('Overall Defect Rate', 'معدل العيوب الإجمالي')} value={`${data.overall_defect_rate_pct}%`} icon={ShieldCheck} hero iconColor={data.overall_defect_rate_pct <= 2 ? 'text-emerald-500' : data.overall_defect_rate_pct <= 6 ? 'text-amber-500' : 'text-red-500'} />
        )}
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.by_unit.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Defect Rate by Unit', 'معدل العيوب حسب الوحدة')}</p>
          <DepartmentBarChart
            data={data.by_unit.map(i => ({ department: i.unit, value: i.defect_rate_pct ?? 0, color: (i.defect_rate_pct ?? 0) <= 2 ? '#059669' : (i.defect_rate_pct ?? 0) <= 6 ? '#d97706' : '#dc2626' }))}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}
      {data.period_variances.length > 1 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Defect Rate Trend', 'اتجاه معدل العيوب')}</p>
          <TrendChart
            data={data.period_variances.map(v => ({ period: v.period, defect_rate: v.defect_rate_current }))}
            series={[{ key: 'defect_rate', label: t('Defect Rate', 'معدل العيوب'), color: '#dc2626' }]}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Defect Rate', 'معدل العيوب')}</th>
          </tr></thead>
          <tbody>
            {data.by_unit.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.defect_rate_pct != null ? `${i.defect_rate_pct}%` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.period_variances.length > 0 && (
        <div className="card overflow-x-auto">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Defect Rate Trend', 'اتجاه معدل العيوب')}</div>
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Period', 'الفترة')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Prior', 'السابق')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Current', 'الحالي')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Change', 'التغيّر')}</th>
            </tr></thead>
            <tbody>
              {data.period_variances.map((v, idx) => (
                <tr key={idx} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-mono text-slate-600 dark:text-slate-400">{v.prior_period} → {v.period}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{v.defect_rate_prior}%</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{v.defect_rate_current}%</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {v.variance_pct != null ? <StatusBadge tone={v.variance_pct > 0 ? 'critical' : v.variance_pct < 0 ? 'positive' : 'neutral'}>{v.variance_pct >= 0 ? '+' : ''}{v.variance_pct.toFixed(1)}%</StatusBadge> : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── 5. Bottleneck Identification ─────────────────────────────────────────

function BottleneckTab({ data, t }: { data: BottleneckData; t: T }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={TrendingDown}
        title={t('Bottleneck identification not available', 'تحديد الاختناقات غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={{}}
        columnLabels={{}}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t(
          `A unit is only confidently flagged as a bottleneck once it has at least ${data.min_periods_for_confidence} periods of data AND its utilization sits at least ${data.utilization_gap_pp_threshold} points below the fleet average (${data.fleet_avg_utilization_pct}%, computed only from sufficient-sample units). Units below the period floor still show real numbers, just not the confident label.`,
          `تُرصد الوحدة كاختناق بثقة فقط عند توفر ${data.min_periods_for_confidence} فترات بيانات على الأقل.`
        )}
      </StatusBanner>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Periods', 'الفترات')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Utilization', 'الاستغلال')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Downtime Rate', 'معدل التوقف')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Productivity', 'الإنتاجية')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Flag', 'المؤشر')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.n_periods}{!i.sufficient_sample && <span className="text-[10px] text-amber-500 ml-1">{t('(low)', '(قليل)')}</span>}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.utilization_pct != null ? `${i.utilization_pct.toFixed(1)}%` : '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.downtime_rate_pct != null ? `${i.downtime_rate_pct}%` : '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.productivity != null ? i.productivity.toFixed(2) : '—'}</td>
                <td className="px-4 py-2.5 text-right">
                  {i.is_bottleneck ? <StatusBadge tone="critical">{t('Bottleneck', 'اختناق')}</StatusBadge> : !i.sufficient_sample ? <StatusBadge tone="neutral">{t('Insufficient data', 'بيانات غير كافية')}</StatusBadge> : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 6. Cost per Unit of Operation ────────────────────────────────────────

function CostPerUnitTab({ data, t, isAr }: { data: CostPerUnitData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Wallet}
        title={t('Cost per unit not computable from this upload', 'تكلفة الوحدة غير قابلة للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t(
          'Cost per unit of OUTPUT at the operational-unit level — distinct from Financial Intelligence\'s company-wide expense analysis, which has no concept of production output to divide by.',
          'تكلفة كل وحدة إنتاج على مستوى الوحدة التشغيلية — مختلفة عن تحليل المصروفات الشامل في الذكاء المالي.'
        )}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Cost per Unit', 'التكلفة لكل وحدة')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.unit, value: i.cost_per_unit }))}
            valueFormatter={sar}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Unit', 'الوحدة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total Cost', 'إجمالي التكلفة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Output', 'الإنتاج')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Cost / Unit', 'التكلفة/الوحدة')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.unit} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.unit}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(i.total_cost)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_output, 0)}</td>
                <td className="px-4 py-2.5 text-right font-mono font-semibold text-slate-700 dark:text-slate-300">{sar(i.cost_per_unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
