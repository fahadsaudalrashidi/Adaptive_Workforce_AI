/**
 * Inventory Intelligence — Phase 32 (Business Intelligence Suite, Module 3).
 *
 * A fourth genuinely distinct data shape for this platform: item-level
 * stock/transaction data (SKU, quantity, unit cost, movement history) — not
 * an employee roster, not Phase 30's plain financial transaction list, and
 * not Phase 31's double-entry GL export. Fully separate page, fully
 * separate engine.
 *
 * UNLIKE Financial Intelligence's single top-level `available` flag (and
 * LIKE Accounting Intelligence's per-section flags), each of the 6 sections
 * here has its OWN independent `available` flag — a pure point-in-time
 * snapshot (no movement history) only supports Stock Levels and ABC
 * Analysis; the other four (Turnover, Stock Aging, Reorder Point/Safety
 * Stock, Overstock/Stockout Risk) all require real transaction history and
 * honestly degrade without it — same discipline this session already
 * established for Payroll Movements' snapshot-vs-longitudinal distinction.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, RefreshCw, Package, Repeat, Clock, PieChart, Target, AlertOctagon,
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

// ── Types (mirror backend/core/inventory_intelligence_engine.py) ──────────

interface StockLevelItem {
  sku: string; item_name: string | null; category: string | null
  current_stock: number; current_stock_source: string
  total_received: number | null; total_issued: number | null; last_movement_date: string | null
}
interface StockLevelsData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  has_movement_history: boolean; n_items: number; items: StockLevelItem[]
  narrative_en: string; narrative_ar: string
}
interface TurnoverItem {
  sku: string; item_name: string | null; total_issued: number
  avg_units_on_hand: number; avg_inventory_value: number | null; turnover_ratio: number | null
}
interface TurnoverData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  formula_used: string | null; items: TurnoverItem[]
  narrative_en: string; narrative_ar: string
}
interface StockAgingItem {
  sku: string; item_name: string | null; days_since_last_movement: number; tier: string
  current_stock: number | null; value_on_hand: number | null
}
interface StockAgingData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  as_of_date: string | null; tier_counts: Record<string, number>; items: StockAgingItem[]
  narrative_en: string; narrative_ar: string
}
interface ABCItem { sku: string; item_name: string | null; value_on_hand: number; cumulative_pct_before: number; tier: string }
interface ABCData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  total_value: number | null; tier_counts: Record<string, number>; tier_value_pct: Record<string, number>
  items: ABCItem[]; narrative_en: string; narrative_ar: string
}
interface ReorderItem {
  sku: string; item_name: string | null; formula_used: string; current_stock: number
  avg_daily_demand: number; lead_time_days: number | null; demand_std: number | null
  safety_stock: number | null; reorder_point: number | null; days_of_supply: number | null
  stockout_risk: boolean; overstock: boolean
}
interface ReorderData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  z_service_level: number; stockout_days_threshold: number; overstock_days_threshold: number
  overstock_multiple: number; items: ReorderItem[]; narrative_en: string; narrative_ar: string
}
interface OverstockStockoutData {
  available: boolean; reason: string | null; n_stockout_risk: number; n_overstock: number
  stockout_items: ReorderItem[]; overstock_items: ReorderItem[]
  narrative_en: string; narrative_ar: string
}
interface InventoryIntelligenceData {
  stock_levels: StockLevelsData; turnover: TurnoverData; stock_aging: StockAgingData
  abc_analysis: ABCData; reorder_points: ReorderData; overstock_stockout: OverstockStockoutData
  disclaimer_en: string; disclaimer_ar: string; sources: string[]
}
interface ApiResponse { filename: string; row_count?: number; inventory_intelligence: InventoryIntelligenceData }

const COLUMN_LABELS_EN: Record<string, string> = {
  sku: 'SKU / item code (required)', item_name: 'Item name (optional)', category: 'Category (optional)',
  quantity_on_hand: 'Quantity on hand (snapshot; optional if movement history is present)',
  unit_cost: 'Unit cost (required for value-based views)',
  transaction_date: 'Transaction/movement date (required for movement-dependent views)',
  transaction_type: 'Transaction type — Receipt/Issue (required for movement-dependent views)',
  quantity_moved: 'Quantity moved (required for movement-dependent views)',
  lead_time_days: 'Lead time in days (optional — enables the full reorder-point formula)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  sku: 'رمز الصنف (مطلوب)', item_name: 'اسم الصنف (اختياري)', category: 'الفئة (اختياري)',
  quantity_on_hand: 'الكمية المتوفرة (لقطة؛ اختياري إذا وُجد سجل حركة)',
  unit_cost: 'تكلفة الوحدة (مطلوبة للعروض المعتمدة على القيمة)',
  transaction_date: 'تاريخ الحركة (مطلوب للعروض المعتمدة على الحركة)',
  transaction_type: 'نوع الحركة — استلام/صرف (مطلوب للعروض المعتمدة على الحركة)',
  quantity_moved: 'الكمية المتحركة (مطلوبة للعروض المعتمدة على الحركة)',
  lead_time_days: 'مدة التوريد بالأيام (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function num(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
function sar(n: number): string {
  return `SAR ${num(n)}`
}

type TabKey = 'levels' | 'turnover' | 'aging' | 'abc' | 'reorder' | 'overstock'

const TIER_TONE: Record<string, 'positive' | 'informational' | 'caution' | 'critical'> = {
  active: 'positive', watch: 'informational', slow_moving: 'caution', dead_stock: 'critical',
  A: 'critical', B: 'caution', C: 'informational',
}

export function InventoryIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('levels')
  const [result, setResult] = useState<ApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [asOfDate, setAsOfDate] = useState<string>('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const runUpload = useCallback(async (file: File) => {
    setStatus('loading')
    setError(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (asOfDate) formData.append('as_of_date', asOfDate)
      const response = await fetch('/api/local/inventory-intelligence', {
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
  }, [t, asOfDate])

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

  const inv = result?.inventory_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Inventory Intelligence', 'ذكاء المخزون')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Stock Levels, Turnover, Aging/Dead Stock, ABC Analysis, Reorder Point & Safety Stock, and Overstock/Stockout Risk from your own inventory data.',
            'مستويات المخزون، معدل الدوران، التقادم، تحليل ABC، نقطة إعادة الطلب ومخزون الأمان، ومخاطر التكدس والنفاد من بيانات مخزونك.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload an inventory snapshot (SKU, QuantityOnHand, UnitCost) or a movement/transaction log (SKU, TransactionDate, TransactionType, QuantityMoved, UnitCost) — a genuinely different shape from the financial and accounting modules. Each section below has its own independent detection: a snapshot alone supports Stock Levels and ABC Analysis only. Not a certified stock valuation — operations review is required before any purchasing or stocking decision.',
          'حمّل لقطة مخزون (SKU و QuantityOnHand و UnitCost) أو سجل حركة/معاملات (SKU و TransactionDate و TransactionType و QuantityMoved و UnitCost). لكل قسم أدناه اكتشاف مستقل: اللقطة وحدها تُفعّل مستويات المخزون وتحليل ABC فقط. هذه ليست تقييماً معتمداً للمخزون — تلزم مراجعة العمليات قبل أي قرار شراء أو تخزين.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500 dark:text-slate-400">
              {t('Aging / reorder-point as-of date (optional, defaults to today)', 'تاريخ مرجعي للتقادم ونقطة الطلب (اختياري، الافتراضي اليوم)')}
            </label>
            <input
              type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)}
              className="text-xs px-2 py-1 rounded border border-slate-200 dark:border-navy-500/60 bg-transparent text-slate-600 dark:text-slate-300"
            />
          </div>
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
        </div>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Analyzing inventory…', 'جارٍ تحليل المخزون…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && inv && (
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
                ['levels', t('Stock Levels', 'مستويات المخزون'), Package],
                ['turnover', t('Turnover', 'معدل الدوران'), Repeat],
                ['aging', t('Stock Aging', 'تقادم المخزون'), Clock],
                ['abc', t('ABC Analysis', 'تحليل ABC'), PieChart],
                ['reorder', t('Reorder Point', 'نقطة إعادة الطلب'), Target],
                ['overstock', t('Overstock & Stockout', 'التكدس والنفاد'), AlertOctagon],
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

            {tab === 'levels' && <StockLevelsTab data={inv.stock_levels} t={t} isAr={isAr} />}
            {tab === 'turnover' && <TurnoverTab data={inv.turnover} t={t} isAr={isAr} />}
            {tab === 'aging' && <AgingTab data={inv.stock_aging} t={t} isAr={isAr} />}
            {tab === 'abc' && <ABCTab data={inv.abc_analysis} t={t} isAr={isAr} />}
            {tab === 'reorder' && <ReorderTab data={inv.reorder_points} t={t} isAr={isAr} />}
            {tab === 'overstock' && <OverstockTab data={inv.overstock_stockout} t={t} />}
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

// ── 1. Stock Levels ──────────────────────────────────────────────────────

function StockLevelsTab({ data, t, isAr }: { data: StockLevelsData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Package}
        title={t('Stock level data not detected', 'لم يتم اكتشاف بيانات مستوى المخزون')}
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
        <KPICard label={t('Items', 'الأصناف')} value={data.n_items} icon={Package} hero />
        <KPICard
          label={t('Movement History', 'سجل الحركة')}
          value={data.has_movement_history ? t('Available', 'متوفر') : t('Snapshot only', 'لقطة فقط')}
          icon={Clock} iconColor={data.has_movement_history ? 'text-emerald-500' : 'text-amber-500'}
          iconBg={data.has_movement_history ? 'bg-emerald-500/10' : 'bg-amber-500/10'}
        />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {!data.has_movement_history && (
        <StatusBanner tone="caution" compact>
          {t('Only a point-in-time snapshot is available — no in/out movement trend can be shown.', 'تتوفر لقطة لحظية فقط — لا يمكن عرض اتجاه حركة.')}
        </StatusBanner>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('SKU', 'الرمز')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Category', 'الفئة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Current Stock', 'المخزون الحالي')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Source', 'المصدر')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Last Movement', 'آخر حركة')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.sku}{i.item_name ? <div className="text-[11px] text-slate-400 font-normal">{i.item_name}</div> : null}</td>
                <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{i.category ?? '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{num(i.current_stock)}</td>
                <td className="px-4 py-2.5 text-[11px] text-slate-400 uppercase">{i.current_stock_source === 'snapshot_column' ? t('snapshot', 'لقطة') : t('derived', 'مُشتق')}</td>
                <td className="px-4 py-2.5 font-mono text-slate-600 dark:text-slate-400">{i.last_movement_date ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 2. Turnover ───────────────────────────────────────────────────────────

function TurnoverTab({ data, t, isAr }: { data: TurnoverData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Repeat}
        title={t('Inventory turnover not computable from this upload', 'معدل دوران المخزون غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  const isValueFormula = data.formula_used === 'cogs_over_avg_inventory_value'
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {isValueFormula
          ? t('Formula: cost of goods issued ÷ average inventory value (unit cost detected).', 'الصيغة: تكلفة البضاعة المصروفة ÷ متوسط قيمة المخزون.')
          : t('Formula: units issued ÷ average units on hand (no unit-cost column detected — a different, non-interchangeable formula).', 'الصيغة: الوحدات المصروفة ÷ متوسط الوحدات المتوفرة (لا يوجد عمود تكلفة).')}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('SKU', 'الرمز')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Issued', 'المصروف')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Units on Hand', 'متوسط الوحدات')}</th>
            {isValueFormula && <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Inventory Value', 'متوسط قيمة المخزون')}</th>}
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Turnover Ratio', 'معدل الدوران')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.total_issued)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{num(i.avg_units_on_hand)}</td>
                {isValueFormula && <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.avg_inventory_value != null ? sar(i.avg_inventory_value) : '—'}</td>}
                <td className="px-4 py-2.5 text-right font-mono font-semibold text-slate-700 dark:text-slate-300">{i.turnover_ratio != null ? i.turnover_ratio.toFixed(3) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 3. Stock Aging / Dead Stock ─────────────────────────────────────────

function AgingTab({ data, t, isAr }: { data: StockAgingData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Clock}
        title={t('Stock aging not computable from this upload', 'تقادم المخزون غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  const TIER_ORDER = ['active', 'watch', 'slow_moving', 'dead_stock'] as const
  return (
    <div className="space-y-5">
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {TIER_ORDER.some(tier => (data.tier_counts[tier] ?? 0) > 0) && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Items by Aging Tier', 'الأصناف حسب مستوى التقادم')}</p>
          <DepartmentBarChart
            data={TIER_ORDER.map(tier => ({ department: tier.replace('_', ' '), value: data.tier_counts[tier] ?? 0, color: tier === 'active' ? '#059669' : tier === 'watch' ? '#3b82f6' : tier === 'dead_stock' ? '#dc2626' : '#d97706' }))}
            sortByValue={false}
            height={200}
          />
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(['active', 'watch', 'slow_moving', 'dead_stock'] as const).map((tier) => (
          <div key={tier} className="card p-3 text-center">
            <StatusBadge tone={TIER_TONE[tier]}>{tier.replace('_', ' ')}</StatusBadge>
            <p className="text-lg font-mono font-semibold text-slate-700 dark:text-slate-300 mt-2">{data.tier_counts[tier] ?? 0}</p>
          </div>
        ))}
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('SKU', 'الرمز')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Days Since Movement', 'أيام منذ آخر حركة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Tier', 'المستوى')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Value on Hand', 'القيمة المتوفرة')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.days_since_last_movement}</td>
                <td className="px-4 py-2.5"><StatusBadge tone={TIER_TONE[i.tier]}>{i.tier.replace('_', ' ')}</StatusBadge></td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.value_on_hand != null ? sar(i.value_on_hand) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 4. ABC Analysis ──────────────────────────────────────────────────────

function ABCTab({ data, t, isAr }: { data: ABCData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={PieChart}
        title={t('ABC analysis not computable from this upload', 'تحليل ABC غير قابل للاحتساب من هذا الملف')}
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
        {t('Standard 80/15/5 cumulative-value convention (A/B/C), computed from real quantity × unit cost.', 'معيار 80/15/5 التراكمي القياسي (A/B/C)، محسوب من الكمية الفعلية × تكلفة الوحدة.')}
      </StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
        <KPICard label={t('Total Value', 'إجمالي القيمة')} value={sar(data.total_value ?? 0)} icon={PieChart} hero />
        {(['A', 'B', 'C'] as const).map((tier) => (
          <KPICard key={tier} label={t(`Tier ${tier}`, `فئة ${tier}`)} value={data.tier_counts[tier] ?? 0} subtitle={`${data.tier_value_pct[tier] ?? 0}% ${t('of value', 'من القيمة')}`} icon={PieChart} iconColor={tier === 'A' ? 'text-red-500' : tier === 'B' ? 'text-amber-500' : 'text-blue-500'} iconBg={tier === 'A' ? 'bg-red-500/10' : tier === 'B' ? 'bg-amber-500/10' : 'bg-blue-500/10'} />
        ))}
      </div>
      {(['A', 'B', 'C'] as const).some(tier => (data.tier_value_pct[tier] ?? 0) > 0) && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Value Concentration by Tier', 'تركّز القيمة حسب الفئة')}</p>
          <CompositionChart
            data={(['A', 'B', 'C'] as const).map(tier => ({
              label: t(`Tier ${tier}`, `فئة ${tier}`),
              value: data.tier_value_pct[tier] ?? 0,
              color: tier === 'A' ? '#dc2626' : tier === 'B' ? '#d97706' : '#3b82f6',
            })).filter(d => d.value > 0)}
            valueFormatter={(v) => `${v}%`}
          />
        </div>
      )}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('SKU', 'الرمز')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Value on Hand', 'القيمة المتوفرة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Cum. % Before', 'التراكمي % قبل')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Tier', 'الفئة')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(i.value_on_hand)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-500 dark:text-slate-400">{i.cumulative_pct_before.toFixed(1)}%</td>
                <td className="px-4 py-2.5"><StatusBadge tone={TIER_TONE[i.tier]}>{i.tier}</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 5. Reorder Point & Safety Stock ─────────────────────────────────────

function ReorderTab({ data, t, isAr }: { data: ReorderData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Target}
        title={t('Reorder point not computable from this upload', 'نقطة إعادة الطلب غير قابلة للاحتساب من هذا الملف')}
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
          `Items with a real lead-time value use the full formula (Safety Stock = Z×σ×√LeadTime, Z=${data.z_service_level}). Items without lead time fall back to a simpler average-demand days-of-supply estimate — never a fabricated lead-time assumption.`,
          `الأصناف التي لديها مدة توريد حقيقية تستخدم الصيغة الكاملة. الأصناف بدون مدة توريد تستخدم تقدير أيام التغطية المبسّط.`
        )}
      </StatusBanner>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('SKU', 'الرمز')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Current Stock', 'المخزون الحالي')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Formula', 'الصيغة')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Safety Stock / Reorder Point', 'مخزون الأمان / نقطة الطلب')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Days of Supply', 'أيام التغطية')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Flags', 'المؤشرات')}</th>
          </tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{num(i.current_stock)}</td>
                <td className="px-4 py-2.5 text-[11px] text-slate-400 uppercase">{i.formula_used === 'lead_time_variability' ? t('lead-time formula', 'صيغة مدة التوريد') : t('days-of-supply fallback', 'تقدير مبسّط')}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                  {i.formula_used === 'lead_time_variability' ? `${num(i.safety_stock ?? 0)} / ${num(i.reorder_point ?? 0)}` : '—'}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{i.days_of_supply != null ? i.days_of_supply.toFixed(1) : '—'}</td>
                <td className="px-4 py-2.5 text-right">
                  {i.stockout_risk && <StatusBadge tone="critical" className="mr-1">{t('Stockout', 'نفاد')}</StatusBadge>}
                  {i.overstock && <StatusBadge tone="caution">{t('Overstock', 'تكدس')}</StatusBadge>}
                  {!i.stockout_risk && !i.overstock && '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 6. Overstock & Stockout Risk ────────────────────────────────────────

function OverstockTab({ data, t }: { data: OverstockStockoutData; t: T }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={AlertOctagon}
        title={t('Overstock / stockout risk not available', 'مخاطر التكدس/النفاد غير متاحة')}
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
        {t('These flags reuse the Reorder Point tab\'s own computed figures directly — not a separate calculation.', 'تُعيد هذه المؤشرات استخدام أرقام تبويب نقطة إعادة الطلب مباشرة — دون حساب منفصل.')}
      </StatusBanner>
      <div className="grid grid-cols-2 gap-5">
        <KPICard label={t('Stockout Risk', 'خطر النفاد')} value={data.n_stockout_risk} icon={AlertOctagon} hero iconColor="text-red-500" />
        <KPICard label={t('Overstocked', 'مخزون زائد')} value={data.n_overstock} icon={AlertOctagon} iconColor="text-amber-500" iconBg="bg-amber-500/10" />
      </div>
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Stockout Risk Items', 'أصناف معرضة لخطر النفاد')}</div>
        {data.stockout_items.length === 0 ? <p className="text-xs text-slate-400 px-4 py-3">{t('None.', 'لا يوجد.')}</p> : (
          <table className="w-full text-sm">
            <tbody>
              {data.stockout_items.map((i) => (
                <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{t('stock', 'المخزون')} {num(i.current_stock)}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{i.formula_used === 'lead_time_variability' ? `${t('safety stock', 'مخزون الأمان')} ${num(i.safety_stock ?? 0)}` : `${(i.days_of_supply ?? 0).toFixed(1)} ${t('days supply', 'أيام تغطية')}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Overstocked Items', 'أصناف بمخزون زائد')}</div>
        {data.overstock_items.length === 0 ? <p className="text-xs text-slate-400 px-4 py-3">{t('None.', 'لا يوجد.')}</p> : (
          <table className="w-full text-sm">
            <tbody>
              {data.overstock_items.map((i) => (
                <tr key={i.sku} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{i.sku}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{t('stock', 'المخزون')} {num(i.current_stock)}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-600 dark:text-slate-400">{i.formula_used === 'lead_time_variability' ? `${t('reorder point', 'نقطة الطلب')} ${num(i.reorder_point ?? 0)}` : `${(i.days_of_supply ?? 0).toFixed(1)} ${t('days supply', 'أيام تغطية')}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
