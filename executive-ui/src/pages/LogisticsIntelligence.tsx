/**
 * Logistics Intelligence — Phase 34 (Business Intelligence Suite, Module 5).
 *
 * Shipment/delivery-level data — related to Procurement Intelligence's
 * delivery-performance item (Phase 33) but a genuinely different focus:
 * Procurement measures whether a SUPPLIER delivered inbound goods on time;
 * this page measures the platform owner's own OUTBOUND shipping
 * performance to their customers, carrier reliability, and returns.
 *
 * Carrier/route performance scoring is explicitly labeled a CONSTRUCTED
 * HEURISTIC, never a validated/certified carrier rating — same framing as
 * Procurement's supplier score and Succession Readiness's readiness score.
 * Returns theme extraction never surfaces raw return-reason text — only
 * aggregate counts for themes mentioned by at least 3 distinct shipments.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, RefreshCw, Package, Clock, Wallet, Truck, AlertTriangle, RotateCcw,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { StatusBadge } from '../components/shared/StatusBadge'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { CompositionChart } from '../components/shared/CompositionChart'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { TrendChart } from '../components/shared/TrendChart'

// ── Types (mirror backend/core/logistics_intelligence_engine.py) ──────────

interface StatusCount { status: string; n: number; pct: number }
interface ShipmentStatusData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  n_shipments_total: number; n_unclassified: number; status_counts: StatusCount[]
  narrative_en: string; narrative_ar: string
}
interface DeliveryTimeData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  n_with_complete_dates: number; n_on_time: number; on_time_pct: number
  avg_delivery_days: number | null; narrative_en: string; narrative_ar: string
}
interface CarrierCost { carrier: string; total_cost: number; avg_cost: number; n_shipments: number }
interface CostPeriodVariance {
  period: string; prior_period: string; total_cost_prior: number; total_cost_current: number
  cost_variance: number; cost_variance_pct: number | null
}
interface ShippingCostData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  total_cost: number; avg_cost_per_shipment: number; n_shipments_costed: number
  by_carrier: CarrierCost[]; period_variances: CostPeriodVariance[]; min_periods_required: number
  narrative_en: string; narrative_ar: string
}
interface CarrierPerformanceItem {
  carrier: string; delivery_component: number | null; cost_component: number | null
  composite_score: number | null; components_used: string[]; avg_cost: number | null; n_shipments: number
}
interface RoutePerformanceItem { route: string; on_time_pct: number | null; avg_cost: number | null; n_shipments: number }
interface CarrierRouteData {
  available: boolean; reason: string | null; is_validated_instrument: boolean; confidence: string
  n_carriers_excluded_no_data: number; carrier_items: CarrierPerformanceItem[]; route_items: RoutePerformanceItem[]
  narrative_en: string; narrative_ar: string; disclaimer_en: string; disclaimer_ar: string
}
interface DelayGroupStat { group_type: string; group: string; n_late: number; avg_days_late: number; is_concentration_flagged: boolean }
interface DelayAnalysisData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  min_late_for_flag: number; n_late_total: number; has_delay_cause_data: boolean
  by_carrier: DelayGroupStat[]; by_route: DelayGroupStat[]; by_carrier_route: DelayGroupStat[]
  narrative_en: string; narrative_ar: string
}
interface ReturnThemeFrequency { theme: string; n_shipments_mentioned: number; pct_of_reasons_provided: number }
interface ReturnsAnalysisData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  n_shipments_total: number; n_returned: number; return_rate_pct: number; n_reasons_provided: number
  min_mentions_for_theme: number; theme_frequencies: ReturnThemeFrequency[]
  top_terms: { term: string; n_shipments: number }[]; term_extraction_method: string
  narrative_en: string; narrative_ar: string; governance_note: string
}
interface LogisticsIntelligenceData {
  shipment_status: ShipmentStatusData; delivery_time: DeliveryTimeData; shipping_cost: ShippingCostData
  carrier_route_performance: CarrierRouteData; delay_analysis: DelayAnalysisData; returns_analysis: ReturnsAnalysisData
  disclaimer_en: string; disclaimer_ar: string; sources: string[]
}
interface ApiResponse { filename: string; row_count?: number; logistics_intelligence: LogisticsIntelligenceData }

const COLUMN_LABELS_EN: Record<string, string> = {
  shipment_id: 'Shipment/order ID (optional)', carrier: 'Carrier (required for carrier-level views)',
  route: 'Route / origin-destination (optional)', ship_date: 'Ship date (required for cost-trend view)',
  expected_delivery_date: 'Expected delivery date (required for on-time/delay views)',
  actual_delivery_date: 'Actual delivery date (required for on-time/delay views)',
  status: 'Status (required for the shipment status overview)', cost: 'Shipping cost (required for cost views)',
  return_flag: 'Return flag (optional — alternative to a Returned status value)',
  return_reason: 'Return reason — free text (optional)',
  delay_reason: 'Delay reason/cause (optional, not yet used in Phase 1)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  shipment_id: 'رقم الشحنة/الطلب (اختياري)', carrier: 'شركة الشحن (مطلوبة لعروض مستوى الناقل)',
  route: 'المسار (اختياري)', ship_date: 'تاريخ الشحن (مطلوب لعرض اتجاه التكلفة)',
  expected_delivery_date: 'تاريخ التسليم المتوقع (مطلوب)', actual_delivery_date: 'تاريخ التسليم الفعلي (مطلوب)',
  status: 'الحالة (مطلوبة)', cost: 'تكلفة الشحن (مطلوبة)',
  return_flag: 'مؤشر الإرجاع (اختياري)',
  return_reason: 'سبب الإرجاع (اختياري)',
  delay_reason: 'سبب التأخير (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function num(n: number, digits = 2): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}
function sar(n: number): string { return `SAR ${num(n)}` }

type TabKey = 'status' | 'delivery' | 'cost' | 'carrier' | 'delay' | 'returns'

const STATUS_TONE: Record<string, 'positive' | 'informational' | 'caution' | 'critical'> = {
  delivered: 'positive', in_transit: 'informational', delayed: 'caution', returned: 'critical',
}

export function LogisticsIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('status')
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
      const response = await fetch('/api/local/logistics-intelligence', {
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

  const log = result?.logistics_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Logistics Intelligence', 'ذكاء اللوجستيات')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Shipment Status, Delivery Time, Shipping Cost, Carrier/Route Performance, Delay Analysis, and Returns from your own shipment data.',
            'حالة الشحنات، وقت التسليم، تكلفة الشحن، أداء الناقل/المسار، تحليل التأخير، والمرتجعات من بيانات شحناتك.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a shipment export (Carrier, Route, ShipDate, ExpectedDeliveryDate, ActualDeliveryDate, Status, Cost, optionally ReturnReason) — your own OUTBOUND delivery data, distinct from Procurement\'s inbound supplier deliveries. Carrier scores are a constructed heuristic, never a certified rating. No raw return-reason text is ever surfaced — only aggregate themes mentioned by 3+ shipments.',
          'حمّل ملف شحنات (Carrier و Route و ShipDate وتواريخ التسليم و Status و Cost، واختيارياً ReturnReason) — بيانات تسليمك الصادرة الخاصة. درجات شركات الشحن معيار داخلي مُركّب وليست تقييماً معتمداً. لا يُعرض أي نص خام لسبب الإرجاع.'
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
            {t('Analyzing shipments…', 'جارٍ تحليل الشحنات…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && log && (
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
                ['status', t('Status Overview', 'نظرة عامة'), Package],
                ['delivery', t('Delivery Time', 'وقت التسليم'), Clock],
                ['cost', t('Shipping Cost', 'تكلفة الشحن'), Wallet],
                ['carrier', t('Carrier & Route', 'الناقل والمسار'), Truck],
                ['delay', t('Delay Analysis', 'تحليل التأخير'), AlertTriangle],
                ['returns', t('Returns', 'المرتجعات'), RotateCcw],
              ] as [TabKey, string, typeof Package][]).map(([key, label, Icon]) => (
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

            {tab === 'status' && <StatusTab data={log.shipment_status} t={t} isAr={isAr} />}
            {tab === 'delivery' && <DeliveryTab data={log.delivery_time} t={t} isAr={isAr} />}
            {tab === 'cost' && <CostTab data={log.shipping_cost} t={t} isAr={isAr} />}
            {tab === 'carrier' && <CarrierTab data={log.carrier_route_performance} t={t} isAr={isAr} />}
            {tab === 'delay' && <DelayTab data={log.delay_analysis} t={t} isAr={isAr} />}
            {tab === 'returns' && <ReturnsTab data={log.returns_analysis} t={t} isAr={isAr} />}
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

// ── 1. Shipment Status Overview ─────────────────────────────────────────

function StatusTab({ data, t, isAr }: { data: ShipmentStatusData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Package}
        title={t('Shipment status data not detected', 'لم يتم اكتشاف بيانات حالة الشحنات')}
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
        <KPICard label={t('Total Shipments', 'إجمالي الشحنات')} value={data.n_shipments_total} icon={Package} hero />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.status_counts.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Shipment Status Distribution', 'توزيع حالة الشحنات')}</p>
          <CompositionChart
            data={data.status_counts.map(c => ({
              label: c.status.replace('_', ' '),
              value: c.n,
              color: c.status === 'delivered' ? '#059669' : c.status === 'in_transit' ? '#3b82f6' : c.status === 'delayed' ? '#d97706' : c.status === 'returned' ? '#dc2626' : undefined,
            }))}
          />
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {data.status_counts.map((c) => (
          <div key={c.status} className="card p-3 text-center">
            <StatusBadge tone={STATUS_TONE[c.status] ?? 'neutral'}>{c.status.replace('_', ' ')}</StatusBadge>
            <p className="text-lg font-mono font-semibold text-slate-700 dark:text-slate-300 mt-2">{c.n}</p>
            <p className="text-[11px] text-slate-400">{c.pct}%</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── 2. Delivery Time ─────────────────────────────────────────────────────

function DeliveryTab({ data, t, isAr }: { data: DeliveryTimeData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Clock}
        title={t('Delivery time not computable from this upload', 'وقت التسليم غير قابل للاحتساب من هذا الملف')}
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
        <KPICard label={t('On-Time Rate', 'نسبة الالتزام بالموعد')} value={`${data.on_time_pct}%`} icon={Clock} hero radialPct={data.on_time_pct} radialColor={data.on_time_pct >= 80 ? '#059669' : data.on_time_pct >= 50 ? '#d97706' : '#dc2626'} />
        <KPICard label={t('On Time', 'في الموعد')} value={`${data.n_on_time} / ${data.n_with_complete_dates}`} icon={Package} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        {data.avg_delivery_days != null && (
          <KPICard label={t('Avg Delivery Time', 'متوسط وقت التسليم')} value={`${data.avg_delivery_days} ${t('days', 'يوماً')}`} icon={Clock} iconColor="text-slate-500" iconBg="bg-slate-500/10" />
        )}
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
    </div>
  )
}

// ── 3. Shipping Cost ──────────────────────────────────────────────────────

function CostTab({ data, t, isAr }: { data: ShippingCostData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Wallet}
        title={t('Shipping cost not computable from this upload', 'تكلفة الشحن غير قابلة للاحتساب من هذا الملف')}
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
        <KPICard label={t('Total Cost', 'إجمالي التكلفة')} value={sar(data.total_cost)} icon={Wallet} hero />
        <KPICard label={t('Avg Cost / Shipment', 'متوسط التكلفة/شحنة')} value={sar(data.avg_cost_per_shipment)} icon={Wallet} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('Shipments Costed', 'الشحنات المُسعّرة')} value={data.n_shipments_costed} icon={Package} iconColor="text-slate-500" iconBg="bg-slate-500/10" />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.by_carrier.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Cost by Carrier', 'التكلفة حسب الناقل')}</p>
          <DepartmentBarChart
            data={data.by_carrier.map(c => ({ department: c.carrier, value: c.total_cost, tooltipExtra: { [t('Shipments', 'الشحنات')]: c.n_shipments } }))}
            valueFormatter={sar}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Carrier', 'الناقل')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total Cost', 'إجمالي التكلفة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Cost', 'متوسط التكلفة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Shipments', 'الشحنات')}</th>
          </tr></thead>
          <tbody>
            {data.by_carrier.map((c) => (
              <tr key={c.carrier} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{c.carrier}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(c.total_cost)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.avg_cost)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.n_shipments}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.period_variances.length > 0 && (
        <div className="card overflow-x-auto">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Monthly Cost Trend', 'اتجاه التكلفة الشهري')}</div>
          {data.period_variances.length > 1 && (
            <div className="p-4">
              <TrendChart
                data={data.period_variances.map(v => ({ period: v.period, cost: v.total_cost_current }))}
                series={[{ key: 'cost', label: t('Total Cost', 'إجمالي التكلفة'), color: '#3b82f6' }]}
                valueFormatter={sar}
              />
            </div>
          )}
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
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{sar(v.total_cost_prior)}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{sar(v.total_cost_current)}</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {v.cost_variance_pct != null ? <StatusBadge tone={v.cost_variance_pct > 0 ? 'critical' : v.cost_variance_pct < 0 ? 'positive' : 'neutral'}>{v.cost_variance_pct >= 0 ? '+' : ''}{v.cost_variance_pct.toFixed(1)}%</StatusBadge> : '—'}
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

// ── 4. Carrier & Route Performance ──────────────────────────────────────

function CarrierTab({ data, t, isAr }: { data: CarrierRouteData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Truck}
        title={t('Carrier/route performance not available', 'أداء الناقل/المسار غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={{}}
        columnLabels={{}}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="caution">{isAr ? data.disclaimer_ar : data.disclaimer_en}</StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.carrier_items.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Carrier Composite Score', 'الدرجة المُركّبة للناقل')}</p>
          <DepartmentBarChart
            data={data.carrier_items.map(i => ({ department: i.carrier, value: i.composite_score ?? 0, color: (i.composite_score ?? 0) >= 70 ? '#059669' : (i.composite_score ?? 0) >= 40 ? '#d97706' : '#dc2626' }))}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Carrier Composite Score', 'الدرجة المُركّبة للناقل')}</div>
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Carrier', 'الناقل')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('On-Time', 'الالتزام')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Cost', 'متوسط التكلفة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Composite', 'المُركّبة')}</th>
          </tr></thead>
          <tbody>
            {data.carrier_items.map((i) => (
              <tr key={i.carrier} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.carrier}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.delivery_component != null ? `${i.delivery_component}%` : '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.avg_cost != null ? sar(i.avg_cost) : '—'}</td>
                <td className="px-4 py-2.5 text-right"><StatusBadge tone={(i.composite_score ?? 0) >= 70 ? 'positive' : (i.composite_score ?? 0) >= 40 ? 'caution' : 'critical'}>{i.composite_score?.toFixed(1)}</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Route Breakdown', 'تفصيل المسارات')}</div>
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-100 dark:border-slate-800 text-left">
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Route', 'المسار')}</th>
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('On-Time', 'الالتزام')}</th>
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Cost', 'متوسط التكلفة')}</th>
            <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Shipments', 'الشحنات')}</th>
          </tr></thead>
          <tbody>
            {data.route_items.map((r) => (
              <tr key={r.route} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{r.route}</td>
                <td className="px-4 py-2 text-right font-mono">{r.on_time_pct != null ? <StatusBadge tone={r.on_time_pct >= 80 ? 'positive' : r.on_time_pct >= 50 ? 'caution' : 'critical'}>{r.on_time_pct.toFixed(1)}%</StatusBadge> : '—'}</td>
                <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{r.avg_cost != null ? sar(r.avg_cost) : '—'}</td>
                <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{r.n_shipments}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 5. Delay Analysis ─────────────────────────────────────────────────────

function DelayTab({ data, t, isAr }: { data: DelayAnalysisData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title={t('Delay analysis not computable from this upload', 'تحليل التأخير غير قابل للاحتساب من هذا الملف')}
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
          `A carrier/route combination is flagged as a delay "concentration" only once it has at least ${data.min_late_for_flag} late shipments — below that floor, raw counts are still shown but never labeled a pattern.`,
          `يُصنَّف تركّز التأخير فقط عند وجود ${data.min_late_for_flag} شحنات متأخرة على الأقل.`
        )}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('By Carrier × Route', 'حسب الناقل × المسار')}</div>
        {data.by_carrier_route.length === 0 ? <p className="text-xs text-slate-400 px-4 py-3">{t('No late shipments.', 'لا توجد شحنات متأخرة.')}</p> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Carrier · Route', 'الناقل · المسار')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Late Shipments', 'الشحنات المتأخرة')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Days Late', 'متوسط أيام التأخير')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Flag', 'المؤشر')}</th>
            </tr></thead>
            <tbody>
              {data.by_carrier_route.map((s, idx) => (
                <tr key={idx} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{s.group}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{s.n_late}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{s.avg_days_late}</td>
                  <td className="px-4 py-2 text-right">{s.is_concentration_flagged ? <StatusBadge tone="critical">{t('Concentration', 'تركّز')}</StatusBadge> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

// ── 6. Returns Analysis ────────────────────────────────────────────────

function ReturnsTab({ data, t, isAr }: { data: ReturnsAnalysisData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={RotateCcw}
        title={t('Returns analysis not available', 'تحليل المرتجعات غير متاح')}
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
        <KPICard label={t('Return Rate', 'نسبة الإرجاع')} value={`${data.return_rate_pct}%`} icon={RotateCcw} hero />
        <KPICard label={t('Returned Shipments', 'الشحنات المرتجعة')} value={data.n_returned} icon={Package} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('Reasons Provided', 'الأسباب المتوفرة')} value={data.n_reasons_provided} icon={Package} iconColor="text-slate-500" iconBg="bg-slate-500/10" />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.theme_frequencies.length > 0 && (
        <StatusBanner tone="informational" compact>
          {t(
            `Themes mentioned by fewer than ${data.min_mentions_for_theme} distinct shipments are suppressed — same threshold as Exit Interview Intelligence. No raw return-reason text is ever shown.`,
            `يتم استبعاد المواضيع التي تُذكر في أقل من ${data.min_mentions_for_theme} شحنات — نفس معيار ذكاء مقابلات الخروج.`
          )}
        </StatusBanner>
      )}
      {data.theme_frequencies.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Return Themes', 'مواضيع الإرجاع')}</p>
          <DepartmentBarChart
            data={data.theme_frequencies.map(th => ({ department: th.theme, value: th.n_shipments_mentioned }))}
          />
        </div>
      )}
      {data.theme_frequencies.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Theme', 'الموضوع')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Shipments', 'الشحنات')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('% of Reasons', '% من الأسباب')}</th>
            </tr></thead>
            <tbody>
              {data.theme_frequencies.map((th) => (
                <tr key={th.theme} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{th.theme}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{th.n_shipments_mentioned}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{th.pct_of_reasons_provided}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.top_terms.length > 0 && (
        <div className="card p-4">
          <p className="text-[11px] text-slate-400 uppercase tracking-wide font-semibold mb-2">{t(`Top terms (${data.term_extraction_method})`, 'أهم المصطلحات')}</p>
          <div className="flex flex-wrap gap-2">
            {data.top_terms.map((tm) => (
              <span key={tm.term} className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">{tm.term} <span className="text-slate-400">({tm.n_shipments})</span></span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
