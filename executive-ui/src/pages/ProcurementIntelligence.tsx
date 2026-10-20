/**
 * Procurement Intelligence — Phase 33 (Business Intelligence Suite, Module 4).
 *
 * Purchase-order/supplier-level data — related to Inventory Intelligence
 * (Phase 32, which tracks stock ON HAND) but distinct: this page tracks the
 * BUYING PROCESS and supplier relationships that replenish it. Fully
 * separate engine, fully separate page.
 *
 * Each of the 6 sections has its own independent `available` flag, same
 * pattern as Accounting/Inventory Intelligence. Supplier Performance
 * Scoring is explicitly labeled a CONSTRUCTED HEURISTIC, not a validated
 * instrument (same framing as Succession Readiness) — never presented as
 * an objective/certified supplier rating. Cost-reduction flags compare
 * only the upload's own multi-supplier prices — no external market-price
 * benchmark is used anywhere on this page.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, RefreshCw, Building2, Tag, TrendingUp, Truck, Award, Lightbulb,
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

// ── Types (mirror backend/core/procurement_intelligence_engine.py) ────────

interface CategorySpend { category: string; total_spend: number; n_pos: number }
interface SupplierSpendItem { supplier: string; total_spend: number; n_pos: number; category_breakdown: CategorySpend[] }
interface SupplierSpendData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  total_spend_all_suppliers: number | null; items: SupplierSpendItem[]
  narrative_en: string; narrative_ar: string
}
interface POPricePoint { date: string | null; unit_price: number; quantity: number | null }
interface ItemPriceHistory {
  supplier: string; sku: string; item_name: string | null; n_pos: number
  avg_price: number; min_price: number; max_price: number; price_points: POPricePoint[]
}
interface POPriceData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  items: ItemPriceHistory[]; narrative_en: string; narrative_ar: string
}
interface PricePeriodVariance {
  period: string; prior_period: string; avg_price_prior: number; avg_price_current: number
  price_variance: number; price_variance_pct: number | null
}
interface PriceTrendItem {
  supplier: string; sku: string; item_name: string | null; n_pos: number; n_periods: number
  overall_change_pct: number | null; period_variances: PricePeriodVariance[]
}
interface PriceTrendData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  min_periods_required: number; min_pos_required: number; n_pairs_suppressed_insufficient_sample: number
  items: PriceTrendItem[]; narrative_en: string; narrative_ar: string
}
interface SupplierDeliveryItem { supplier: string; n_pos_with_delivery_data: number; n_on_time: number; on_time_pct: number }
interface DeliveryData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  n_suppliers_without_delivery_data: number; suppliers_without_delivery_data: string[]
  items: SupplierDeliveryItem[]; narrative_en: string; narrative_ar: string
}
interface SupplierPerformanceItem {
  supplier: string; delivery_component: number | null; price_trend_component: number | null
  composite_score: number; components_used: string[]
}
interface PerformanceData {
  available: boolean; reason: string | null; is_validated_instrument: boolean; confidence: string
  n_suppliers_excluded_no_data: number; items: SupplierPerformanceItem[]
  narrative_en: string; narrative_ar: string; disclaimer_en: string; disclaimer_ar: string
}
interface CostReductionOpportunity {
  sku: string; item_name: string | null; cheapest_supplier: string; cheapest_avg_price: number; cheapest_n_pos: number
  priciest_supplier: string; priciest_avg_price: number; priciest_n_pos: number; price_diff_pct: number
}
interface CostReductionData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  threshold_pct: number; items: CostReductionOpportunity[]; narrative_en: string; narrative_ar: string
}
interface ProcurementIntelligenceData {
  supplier_spend: SupplierSpendData; po_price_analysis: POPriceData; price_trend: PriceTrendData
  delivery_performance: DeliveryData; supplier_performance: PerformanceData; cost_reduction: CostReductionData
  disclaimer_en: string; disclaimer_ar: string; sources: string[]
}
interface ApiResponse { filename: string; row_count?: number; procurement_intelligence: ProcurementIntelligenceData }

const COLUMN_LABELS_EN: Record<string, string> = {
  supplier: 'Supplier name/ID (required)', sku: 'SKU / item code (required)', item_name: 'Item name (optional)',
  category: 'Category (optional)', po_date: 'PO/order date (required for price-trend and delivery views)',
  unit_price: 'Unit price (required, unless a direct total-spend column exists)',
  quantity: 'Quantity (required, unless a direct total-spend column exists)',
  total_spend: 'Total spend (optional direct column)',
  expected_delivery_date: 'Expected delivery date (optional)', actual_delivery_date: 'Actual delivery date (optional)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  supplier: 'اسم/رمز المورد (مطلوب)', sku: 'رمز الصنف (مطلوب)', item_name: 'اسم الصنف (اختياري)',
  category: 'الفئة (اختياري)', po_date: 'تاريخ الطلب (مطلوب لعروض الاتجاه والتسليم)',
  unit_price: 'سعر الوحدة (مطلوب ما لم يوجد عمود إجمالي مباشر)',
  quantity: 'الكمية (مطلوبة ما لم يوجد عمود إجمالي مباشر)', total_spend: 'إجمالي الإنفاق (عمود مباشر اختياري)',
  expected_delivery_date: 'تاريخ التسليم المتوقع (اختياري)', actual_delivery_date: 'تاريخ التسليم الفعلي (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function num(n: number, digits = 2): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
function sar(n: number): string { return `SAR ${num(n)}` }

type TabKey = 'spend' | 'price' | 'trend' | 'delivery' | 'score' | 'costreduction'

export function ProcurementIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('spend')
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
      const response = await fetch('/api/local/procurement-intelligence', {
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

  const proc = result?.procurement_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Procurement Intelligence', 'ذكاء المشتريات')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Supplier Spend, Price Analysis, Price Trends, Delivery Performance, Supplier Scoring, and Cost-Reduction Opportunities from your own purchase-order data.',
            'إنفاق الموردين، تحليل الأسعار، اتجاهات الأسعار، أداء التسليم، تقييم الموردين، وفرص خفض التكلفة من بيانات أوامر الشراء الخاصة بك.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a purchase-order export (SupplierName, SKU, PODate, UnitPrice, Quantity, optionally ExpectedDeliveryDate/ActualDeliveryDate) — related to but distinct from Inventory Intelligence (which tracks stock on hand, not the buying process). Cost-reduction flags and price trends compare only your own uploaded purchase history — no external market-price benchmark is used anywhere on this page.',
          'حمّل ملف أوامر شراء (SupplierName و SKU و PODate و UnitPrice و Quantity، واختيارياً تواريخ التسليم المتوقعة/الفعلية) — مرتبط بذكاء المخزون لكنه مختلف عنه. تقارن مؤشرات خفض التكلفة واتجاهات الأسعار بيانات مشترياتك الخاصة فقط — لا يُستخدم أي معيار سوقي خارجي في هذه الصفحة.'
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
            {t('Analyzing purchase orders…', 'جارٍ تحليل أوامر الشراء…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && proc && (
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
                ['spend', t('Supplier Spend', 'إنفاق الموردين'), Building2],
                ['price', t('PO & Price', 'أوامر الشراء والأسعار'), Tag],
                ['trend', t('Price Trend', 'اتجاه الأسعار'), TrendingUp],
                ['delivery', t('Delivery', 'التسليم'), Truck],
                ['score', t('Supplier Score', 'تقييم المورد'), Award],
                ['costreduction', t('Cost Reduction', 'خفض التكلفة'), Lightbulb],
              ] as [TabKey, string, typeof Building2][]).map(([key, label, Icon]) => (
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

            {tab === 'spend' && <SpendTab data={proc.supplier_spend} t={t} isAr={isAr} />}
            {tab === 'price' && <PriceTab data={proc.po_price_analysis} t={t} isAr={isAr} />}
            {tab === 'trend' && <TrendTab data={proc.price_trend} t={t} isAr={isAr} />}
            {tab === 'delivery' && <DeliveryTab data={proc.delivery_performance} t={t} isAr={isAr} />}
            {tab === 'score' && <ScoreTab data={proc.supplier_performance} t={t} isAr={isAr} />}
            {tab === 'costreduction' && <CostReductionTab data={proc.cost_reduction} t={t} isAr={isAr} />}
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

// ── 1. Supplier Spend ────────────────────────────────────────────────────

function SpendTab({ data, t, isAr }: { data: SupplierSpendData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Building2}
        title={t('Supplier spend data not detected', 'لم يتم اكتشاف بيانات إنفاق الموردين')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  const [hoveredSupplier, setHoveredSupplier] = useState<string | null>(null)
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Spend', 'إجمالي الإنفاق')} value={sar(data.total_spend_all_suppliers ?? 0)} icon={Building2} hero />
        <KPICard label={t('Suppliers', 'الموردون')} value={data.items.length} icon={Building2} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Spend by Supplier', 'الإنفاق حسب المورد')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.supplier, value: i.total_spend, tooltipExtra: { [t('POs', 'أوامر')]: i.n_pos } }))}
            valueFormatter={sar}
            highlightedKey={hoveredSupplier}
            onHoverChange={setHoveredSupplier}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Supplier', 'المورد')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total Spend', 'إجمالي الإنفاق')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('POs', 'أوامر الشراء')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Categories', 'الفئات')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr
                key={i.supplier}
                onMouseEnter={() => setHoveredSupplier(i.supplier)}
                onMouseLeave={() => setHoveredSupplier(null)}
                className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${hoveredSupplier === i.supplier ? 'bg-slate-50 dark:bg-navy-800/40' : ''}`}
              >
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.supplier}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(i.total_spend)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.n_pos}</td>
                <td className="px-4 py-2.5 text-[11px] text-slate-500 dark:text-slate-400">{i.category_breakdown.map(c => `${c.category} (${sar(c.total_spend)})`).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 2. PO & Price Analysis ────────────────────────────────────────────────

function PriceTab({ data, t, isAr }: { data: POPriceData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Tag}
        title={t('Price history not computable from this upload', 'تاريخ الأسعار غير قابل للاحتساب من هذا الملف')}
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
      <div className="space-y-3">
        {data.items.map((i) => (
          <details key={`${i.supplier}-${i.sku}`} className="card overflow-hidden">
            <summary className="px-4 py-3 cursor-pointer flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">{i.sku} <span className="text-[11px] text-slate-400 font-normal">· {i.supplier}</span></span>
              <span className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400 font-mono">
                <span>{t('Avg', 'المتوسط')} {sar(i.avg_price)}</span>
                <span>{t('Range', 'النطاق')} {num(i.min_price, 4)}–{num(i.max_price, 4)}</span>
                <span>{i.n_pos} {t('POs', 'أوامر')}</span>
              </span>
            </summary>
            <table className="w-full text-sm border-t border-slate-200 dark:border-slate-700">
              <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Date', 'التاريخ')}</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Unit Price', 'سعر الوحدة')}</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Quantity', 'الكمية')}</th>
              </tr></thead>
              <tbody>
                {i.price_points.map((p, idx) => (
                  <tr key={idx} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <td className="px-4 py-2 font-mono text-slate-600 dark:text-slate-400">{p.date ?? '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-slate-700 dark:text-slate-300">{num(p.unit_price, 4)}</td>
                    <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{p.quantity != null ? num(p.quantity, 0) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ))}
      </div>
    </div>
  )
}

// ── 3. Price Trend ─────────────────────────────────────────────────────────

function TrendTab({ data, t, isAr }: { data: PriceTrendData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={TrendingUp}
        title={t('Price trend not computable from this upload', 'اتجاه الأسعار غير قابل للاحتساب من هذا الملف')}
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
          `Trends require at least ${data.min_periods_required} periods and ${data.min_pos_required} purchase orders per supplier-item pair — ${data.n_pairs_suppressed_insufficient_sample} pair(s) had too little history and were suppressed, never guessed.`,
          `يتطلب احتساب الاتجاه ${data.min_periods_required} فترات على الأقل و ${data.min_pos_required} أوامر شراء — تم استبعاد ${data.n_pairs_suppressed_insufficient_sample} زوجاً لقلة البيانات.`
        )}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      <div className="space-y-3">
        {data.items.map((i) => (
          <div key={`${i.supplier}-${i.sku}`} className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{i.sku} <span className="text-[11px] text-slate-400 font-normal">· {i.supplier}</span></span>
              {i.overall_change_pct != null && (
                <StatusBadge tone={i.overall_change_pct > 0 ? 'critical' : i.overall_change_pct < 0 ? 'positive' : 'neutral'}>
                  {i.overall_change_pct >= 0 ? '+' : ''}{i.overall_change_pct.toFixed(2)}% {t('over', 'خلال')} {i.n_periods} {t('periods', 'فترات')}
                </StatusBadge>
              )}
            </div>
            {i.period_variances.length > 1 && (
              <div className="mb-3">
                <TrendChart
                  data={i.period_variances.map(v => ({ period: v.period, avg_price: v.avg_price_current }))}
                  series={[{ key: 'avg_price', label: t('Avg Price', 'متوسط السعر'), color: '#3b82f6' }]}
                  valueFormatter={(v) => num(v, 2)}
                  height={140}
                />
              </div>
            )}
            <table className="w-full text-sm">
              <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
                <th className="py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Period', 'الفترة')}</th>
                <th className="py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Prior Avg', 'المتوسط السابق')}</th>
                <th className="py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Current Avg', 'المتوسط الحالي')}</th>
                <th className="py-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Change', 'التغيّر')}</th>
              </tr></thead>
              <tbody>
                {i.period_variances.map((v, idx) => (
                  <tr key={idx} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <td className="py-1.5 font-mono text-slate-600 dark:text-slate-400">{v.prior_period} → {v.period}</td>
                    <td className="py-1.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(v.avg_price_prior, 4)}</td>
                    <td className="py-1.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(v.avg_price_current, 4)}</td>
                    <td className="py-1.5 text-right font-mono">
                      {v.price_variance_pct != null ? <StatusBadge tone={v.price_variance_pct > 0 ? 'critical' : v.price_variance_pct < 0 ? 'positive' : 'neutral'}>{v.price_variance_pct >= 0 ? '+' : ''}{v.price_variance_pct.toFixed(1)}%</StatusBadge> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── 4. Delivery Performance ────────────────────────────────────────────────

function DeliveryTab({ data, t, isAr }: { data: DeliveryData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Truck}
        title={t('Delivery performance not available', 'أداء التسليم غير متاح')}
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
      {data.suppliers_without_delivery_data.length > 0 && (
        <StatusBanner tone="caution" compact>
          {t('No delivery-date data at all for: ', 'لا تتوفر بيانات تسليم إطلاقاً لـ: ') + data.suppliers_without_delivery_data.join(', ')}
        </StatusBanner>
      )}
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('On-Time Delivery by Supplier', 'الالتزام بالتسليم حسب المورد')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.supplier, value: i.on_time_pct, color: i.on_time_pct >= 80 ? '#059669' : i.on_time_pct >= 50 ? '#d97706' : '#dc2626' }))}
            valueFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Supplier', 'المورد')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('POs Tracked', 'الأوامر المتتبعة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('On-Time', 'في الموعد')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('On-Time %', 'نسبة الالتزام')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.supplier} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.supplier}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.n_pos_with_delivery_data}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.n_on_time}</td>
                <td className="px-4 py-2.5 text-right"><StatusBadge tone={i.on_time_pct >= 80 ? 'positive' : i.on_time_pct >= 50 ? 'caution' : 'critical'}>{i.on_time_pct.toFixed(1)}%</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 5. Supplier Performance Score ───────────────────────────────────────

function ScoreTab({ data, t, isAr }: { data: PerformanceData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Award}
        title={t('Supplier performance scoring not available', 'تقييم أداء الموردين غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={{}}
        columnLabels={{}}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="caution">
        {isAr ? data.disclaimer_ar : data.disclaimer_en}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Composite Score by Supplier', 'الدرجة المُركّبة حسب المورد')}</p>
          <DepartmentBarChart
            data={data.items.map(i => ({ department: i.supplier, value: i.composite_score, color: i.composite_score >= 70 ? '#059669' : i.composite_score >= 40 ? '#d97706' : '#dc2626' }))}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Supplier', 'المورد')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Delivery', 'التسليم')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Price Trend', 'اتجاه السعر')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Composite Score', 'الدرجة المُركّبة')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.supplier} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.supplier}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.delivery_component != null ? i.delivery_component.toFixed(1) : '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.price_trend_component != null ? i.price_trend_component.toFixed(1) : '—'}</td>
                <td className="px-4 py-2.5 text-right"><StatusBadge tone={i.composite_score >= 70 ? 'positive' : i.composite_score >= 40 ? 'caution' : 'critical'}>{i.composite_score.toFixed(1)}</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.n_suppliers_excluded_no_data > 0 && (
        <StatusBanner tone="neutral" compact>
          {t(`${data.n_suppliers_excluded_no_data} supplier(s) excluded — no delivery or price-trend data available to score.`, `تم استبعاد ${data.n_suppliers_excluded_no_data} مورداً لعدم توفر بيانات كافية للتقييم.`)}
        </StatusBanner>
      )}
    </div>
  )
}

// ── 6. Cost-Reduction Opportunities ────────────────────────────────────────

function CostReductionTab({ data, t, isAr }: { data: CostReductionData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Lightbulb}
        title={t('Cost-reduction flagging not available', 'رصد فرص خفض التكلفة غير متاح')}
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
        {t(`Flags items sourced from 2+ suppliers with a price spread of ${data.threshold_pct}% or more — computed only from your own purchase history, no external market comparison.`, `يرصد الأصناف التي يزيد فارق سعرها بين الموردين عن ${data.threshold_pct}%.`)}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.items.length === 0 ? (
        <StatusBanner tone="neutral">{t('No cost-reduction opportunities found above the threshold.', 'لم يتم رصد فرص خفض تكلفة تتجاوز الحد.')}</StatusBanner>
      ) : (
        <div className="space-y-3">
          {data.items.map((i) => (
            <div key={i.sku} className="card p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{i.sku}{i.item_name ? <span className="text-[11px] text-slate-400 font-normal"> · {i.item_name}</span> : null}</span>
                <StatusBadge tone="caution">+{i.price_diff_pct.toFixed(1)}%</StatusBadge>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/20 p-3">
                  <p className="text-[11px] text-emerald-600 dark:text-emerald-400 uppercase tracking-wide font-semibold">{t('Cheapest', 'الأرخص')}</p>
                  <p className="font-medium text-slate-700 dark:text-slate-300 mt-1">{i.cheapest_supplier}</p>
                  <p className="font-mono text-slate-600 dark:text-slate-400">{sar(i.cheapest_avg_price)} <span className="text-[11px]">({i.cheapest_n_pos} {t('POs', 'أوامر')})</span></p>
                </div>
                <div className="rounded-lg bg-red-50 dark:bg-red-950/20 p-3">
                  <p className="text-[11px] text-red-600 dark:text-red-400 uppercase tracking-wide font-semibold">{t('Priciest', 'الأغلى')}</p>
                  <p className="font-medium text-slate-700 dark:text-slate-300 mt-1">{i.priciest_supplier}</p>
                  <p className="font-mono text-slate-600 dark:text-slate-400">{sar(i.priciest_avg_price)} <span className="text-[11px]">({i.priciest_n_pos} {t('POs', 'أوامر')})</span></p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
