/**
 * Financial Intelligence — Phase 30 (Business Intelligence Suite, Phase 1).
 *
 * The platform's first non-HR domain: analyzes an uploaded transaction-level
 * or general-ledger dataset (NOT an employee roster) into six views —
 * Revenue, Expense, P&L, Cash Flow, Financial Ratios, and Variance — fed by
 * a single upload and a single analysis call, since all six are different
 * presentations of the same underlying transaction data rather than
 * independent calculators (unlike the Saudi Labor Law Calculators page,
 * which genuinely runs three separate calculators over the same file).
 *
 * NON-NEGOTIABLE: every figure traces to the uploaded data's own
 * categorization — no external benchmark, industry ratio, or forecast.
 * Cash Flow is explicitly labeled NET TRANSACTION MOVEMENT, not a real
 * cash-flow statement (see the backend module's docstring for why). Ratios
 * that require balance-sheet data (current ratio, debt-to-equity, ROA,
 * ROE) are explicitly listed as unavailable, never estimated.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, LineChart, RefreshCw, Users, TrendingUp, TrendingDown, Scale,
  Wallet, Percent, ArrowLeftRight, AlertTriangle,
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

// ── Types ────────────────────────────────────────────────────────────────

interface PeriodFigure {
  period: string
  total_revenue_sar: number
  total_expense_sar: number
  net_sar: number
  n_transactions: number
}
interface CategoryFigure {
  category: string
  signal_type: string
  total_sar: number
  n_transactions: number
  share_pct: number
}
interface DepartmentExpenseFigure {
  department: string
  total_expense_sar: number
  n_transactions: number
}
interface PeriodVariance {
  period: string
  prior_period: string
  revenue_variance_sar: number | null
  revenue_variance_pct: number | null
  expense_variance_sar: number | null
  expense_variance_pct: number | null
  net_variance_sar: number | null
  net_variance_pct: number | null
}
interface FinancialRatios {
  expense_to_revenue_ratio: number | null
  top_expense_category: string | null
  top_expense_category_share_pct: number | null
  top_revenue_category: string | null
  top_revenue_category_share_pct: number | null
  unavailable_ratios_note_en: string
  unavailable_ratios_note_ar: string
}
interface FinancialIntelligenceData {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  transaction_date_column: string | null
  account_category_column: string | null
  amount_column: string | null
  type_column: string | null
  cost_center_column: string | null
  classification_method: string | null
  n_transactions_total: number
  n_transactions_classified: number
  n_excluded_invalid_amount: number
  n_excluded_unclassified: number
  has_period_trend: boolean
  total_revenue_sar: number | null
  total_expense_sar: number | null
  net_pnl_sar: number | null
  period_figures: PeriodFigure[]
  revenue_by_category: CategoryFigure[]
  expense_by_category: CategoryFigure[]
  expense_by_department: DepartmentExpenseFigure[]
  department_normalization_notes: string[]
  period_variances: PeriodVariance[]
  ratios: FinancialRatios | null
  cash_flow_available: boolean
  cash_flow_disclaimer_en: string
  cash_flow_disclaimer_ar: string
  narrative_en: string
  narrative_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}
interface ApiResponse {
  filename: string
  row_count?: number
  financial_intelligence: FinancialIntelligenceData
}

const COLUMN_LABELS_EN: Record<string, string> = {
  transaction_date: 'Transaction/entry date (optional — enables period trends)',
  account_category: 'Account/category name (optional — enables category breakdown)',
  amount: 'Transaction amount (required — must be numeric)',
  type: 'Transaction type / revenue-expense indicator (optional — improves accuracy)',
  cost_center: 'Department / cost center (optional — enables department rollup)',
  description: 'Description / vendor (optional — reserved for future analysis)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  transaction_date: 'تاريخ المعاملة (اختياري — يُفعّل الاتجاهات الزمنية)',
  account_category: 'اسم الحساب/الفئة (اختياري — يُفعّل التصنيف حسب الفئة)',
  amount: 'مبلغ المعاملة (مطلوب — يجب أن يكون رقماً)',
  type: 'نوع المعاملة (اختياري — يُحسّن الدقة)',
  cost_center: 'القسم / مركز التكلفة (اختياري)',
  description: 'الوصف / المورد (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function sar(n: number): string {
  return `SAR ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

type TabKey = 'revenue' | 'expense' | 'pnl' | 'cashflow' | 'ratios' | 'variance'

export function FinancialIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('revenue')
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
      const response = await fetch('/api/local/financial-intelligence', {
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

  const fi = result?.financial_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Financial Intelligence', 'الذكاء المالي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Revenue, Expense, P&L, Cash Flow, Ratios, and Variance from your own transaction data.',
            'الإيرادات والمصروفات والأرباح والخسائر والتدفق النقدي والنسب والتباين من بيانات معاملاتك.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a transaction-level or general-ledger export (e.g. TransactionDate, Account, Amount, Type, Department) — NOT an employee roster. Every figure is computed only from your own data\'s own categorization; no external benchmark, industry ratio, or forecast is used anywhere on this page. This is a computational planning aid, not a certified financial statement — qualified accounting/finance review is required before any filing or decision.',
          'حمّل ملف معاملات أو دفتر أستاذ عام (مثال: TransactionDate و Account و Amount و Type و Department) — وليس قائمة موظفين. تُحسب كل الأرقام من تصنيف بياناتك الخاصة فقط؛ لا يُستخدم أي معيار خارجي أو نسبة صناعية أو توقّع في هذه الصفحة. هذه أداة تخطيط حسابية مساعدة، وليست قائمة مالية معتمدة — تلزم مراجعة محاسبية/مالية متخصصة قبل أي إقرار أو قرار.'
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
            {t('Analyzing transactions…', 'جارٍ تحليل المعاملات…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && fi && (
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

            {!fi.available ? (
              <EmptyState
                icon={LineChart}
                title={t('Financial data not detected in this upload', 'لم يتم اكتشاف بيانات مالية في هذا الملف')}
                reason={fi.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={fi.columns_detected}
                columnLabels={Object.fromEntries(Object.keys(fi.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
              />
            ) : (
              <>
                <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700 overflow-x-auto">
                  {([
                    ['revenue', t('Revenue', 'الإيرادات'), TrendingUp],
                    ['expense', t('Expense', 'المصروفات'), TrendingDown],
                    ['pnl', t('P&L', 'الأرباح والخسائر'), Scale],
                    ['cashflow', t('Cash Flow', 'التدفق النقدي'), Wallet],
                    ['ratios', t('Ratios', 'النسب'), Percent],
                    ['variance', t('Variance', 'التباين'), ArrowLeftRight],
                  ] as [TabKey, string, typeof TrendingUp][]).map(([key, label, Icon]) => (
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

                {tab === 'revenue' && <RevenueTab fi={fi} t={t} isAr={isAr} />}
                {tab === 'expense' && <ExpenseTab fi={fi} t={t} isAr={isAr} />}
                {tab === 'pnl' && <PnlTab fi={fi} t={t} isAr={isAr} />}
                {tab === 'cashflow' && <CashFlowTab fi={fi} t={t} isAr={isAr} />}
                {tab === 'ratios' && <RatiosTab fi={fi} t={t} isAr={isAr} />}
                {tab === 'variance' && <VarianceTab fi={fi} t={t} isAr={isAr} />}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}

type TabProps = { fi: FinancialIntelligenceData; t: (en: string, ar: string) => string; isAr: boolean }

function NarrativeCard({ fi, isAr }: { fi: FinancialIntelligenceData; isAr: boolean }) {
  return <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? fi.narrative_ar : fi.narrative_en}</p></div>
}

function CategoryTable({
  rows, t, highlightedKey, onHoverChange,
}: {
  rows: CategoryFigure[]
  t: (en: string, ar: string) => string
  highlightedKey?: string | null
  onHoverChange?: (category: string | null) => void
}) {
  if (rows.length === 0) return null
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Category', 'الفئة')}</th>
          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total', 'الإجمالي')}</th>
          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Share', 'الحصة')}</th>
          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Transactions', 'المعاملات')}</th>
        </tr></thead>
        <tbody>
          {rows.map((c, i) => (
            <tr
              key={`${c.category}-${i}`}
              onMouseEnter={() => onHoverChange?.(c.category)}
              onMouseLeave={() => onHoverChange?.(null)}
              className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${highlightedKey === c.category ? 'bg-slate-50 dark:bg-navy-800/40' : ''}`}
            >
              <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{c.category}</td>
              <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(c.total_sar)}</td>
              <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.share_pct.toFixed(1)}%</td>
              <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{c.n_transactions}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RevenueTab({ fi, t, isAr }: TabProps) {
  const [hovered, setHovered] = useState<string | null>(null)
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Revenue', 'إجمالي الإيرادات')} value={sar(fi.total_revenue_sar ?? 0)} icon={TrendingUp} hero iconColor="text-emerald-500" />
        <KPICard label={t('Transactions Classified', 'المعاملات المصنّفة')} value={fi.n_transactions_classified} subtitle={t(`of ${fi.n_transactions_total} total`, `من ${fi.n_transactions_total} إجمالاً`)} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('Top Revenue Category', 'أعلى فئة إيراد')} value={fi.ratios?.top_revenue_category ?? '—'} subtitle={fi.ratios?.top_revenue_category_share_pct != null ? `${fi.ratios.top_revenue_category_share_pct.toFixed(1)}%` : undefined} icon={Percent} iconColor="text-amber-500" iconBg="bg-amber-500/10" />
      </div>
      <NarrativeCard fi={fi} isAr={isAr} />
      {!fi.has_period_trend && (
        <StatusBanner tone="caution" compact>{t('No transaction-date column detected — totals shown only, no period trend.', 'لم يتم اكتشاف عمود تاريخ — إجماليات فقط دون اتجاه زمني.')}</StatusBanner>
      )}
      {fi.revenue_by_category.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Revenue by Category', 'الإيرادات حسب الفئة')}</p>
          <CompositionChart
            data={fi.revenue_by_category.map(c => ({ label: c.category, value: c.total_sar }))}
            valueFormatter={sar}
            highlightedKey={hovered}
            onHoverChange={setHovered}
          />
        </div>
      )}
      <CategoryTable rows={fi.revenue_by_category} t={t} highlightedKey={hovered} onHoverChange={setHovered} />
    </div>
  )
}

function ExpenseTab({ fi, t, isAr }: TabProps) {
  const [hoveredCategory, setHoveredCategory] = useState<string | null>(null)
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Expense', 'إجمالي المصروفات')} value={sar(fi.total_expense_sar ?? 0)} icon={TrendingDown} hero iconColor="text-red-500" />
        <KPICard label={t('Top Expense Category', 'أعلى فئة مصروف')} value={fi.ratios?.top_expense_category ?? '—'} subtitle={fi.ratios?.top_expense_category_share_pct != null ? `${fi.ratios.top_expense_category_share_pct.toFixed(1)}%` : undefined} icon={Percent} iconColor="text-amber-500" iconBg="bg-amber-500/10" />
        <KPICard label={t('Departments', 'الأقسام')} value={fi.expense_by_department.length} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" detail={t('Reused from department_normalizer.py — same as every HR module.', 'مُعاد استخدامه من department_normalizer.py.')} />
      </div>
      <NarrativeCard fi={fi} isAr={isAr} />
      {fi.expense_by_category.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Expense by Category', 'المصروفات حسب الفئة')}</p>
          <CompositionChart
            data={fi.expense_by_category.map(c => ({ label: c.category, value: c.total_sar }))}
            valueFormatter={sar}
            highlightedKey={hoveredCategory}
            onHoverChange={setHoveredCategory}
          />
        </div>
      )}
      <CategoryTable rows={fi.expense_by_category} t={t} highlightedKey={hoveredCategory} onHoverChange={setHoveredCategory} />
      {fi.expense_by_department.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Expense by Department', 'المصروفات حسب القسم')}</p>
          <DepartmentBarChart
            data={fi.expense_by_department.map(d => ({ department: d.department, value: d.total_expense_sar, tooltipExtra: { [t('Transactions', 'المعاملات')]: d.n_transactions } }))}
            valueFormatter={sar}
            defaultColor="#dc2626"
            highlightedKey={hoveredDept}
            onHoverChange={setHoveredDept}
          />
        </div>
      )}
      {fi.expense_by_department.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total Expense', 'إجمالي المصروف')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Transactions', 'المعاملات')}</th>
            </tr></thead>
            <tbody>
              {fi.expense_by_department.map((d, i) => (
                <tr
                  key={`${d.department}-${i}`}
                  onMouseEnter={() => setHoveredDept(d.department)}
                  onMouseLeave={() => setHoveredDept(null)}
                  className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${hoveredDept === d.department ? 'bg-slate-50 dark:bg-navy-800/40' : ''}`}
                >
                  <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{d.department}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(d.total_expense_sar)}</td>
                  <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_transactions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {fi.department_normalization_notes.length > 0 && (
        <StatusBanner tone="informational" compact>
          <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
          <ul className="space-y-0.5 mt-1">{fi.department_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}</ul>
        </StatusBanner>
      )}
    </div>
  )
}

function PnlTab({ fi, t }: TabProps) {
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t('Derived from your uploaded data\'s own revenue/expense categorization — not a certified financial statement.', 'مُشتقة من تصنيف بياناتك الخاصة للإيرادات/المصروفات — وليست قائمة مالية معتمدة.')}
      </StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Revenue', 'إجمالي الإيرادات')} value={sar(fi.total_revenue_sar ?? 0)} icon={TrendingUp} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" />
        <KPICard label={t('Total Expense', 'إجمالي المصروفات')} value={sar(fi.total_expense_sar ?? 0)} icon={TrendingDown} iconColor="text-red-500" iconBg="bg-red-500/10" />
        <KPICard label={t('Net P&L', 'صافي الربح/الخسارة')} value={sar(fi.net_pnl_sar ?? 0)} icon={Scale} hero radialColor={(fi.net_pnl_sar ?? 0) >= 0 ? '#059669' : '#dc2626'} />
      </div>
      {fi.has_period_trend && fi.period_figures.length > 1 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Revenue, Expense & Net by Period', 'الإيرادات والمصروفات والصافي حسب الفترة')}</p>
          <TrendChart
            data={fi.period_figures.map(p => ({ period: p.period, revenue: p.total_revenue_sar, expense: p.total_expense_sar, net: p.net_sar }))}
            series={[
              { key: 'revenue', label: t('Revenue', 'الإيرادات'), color: '#059669' },
              { key: 'expense', label: t('Expense', 'المصروفات'), color: '#dc2626' },
              { key: 'net', label: t('Net', 'الصافي'), color: '#3b82f6' },
            ]}
            valueFormatter={sar}
          />
        </div>
      )}
      {fi.has_period_trend && fi.period_figures.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Period', 'الفترة')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Revenue', 'الإيرادات')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Expense', 'المصروفات')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Net', 'الصافي')}</th>
            </tr></thead>
            <tbody>
              {fi.period_figures.map((p) => (
                <tr key={p.period} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-slate-700 dark:text-slate-300">{p.period}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(p.total_revenue_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(p.total_expense_sar)}</td>
                  <td className={`px-4 py-2.5 text-right font-mono font-medium ${p.net_sar >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>{sar(p.net_sar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CashFlowTab({ fi, t, isAr }: TabProps) {
  return (
    <div className="space-y-5">
      <StatusBanner tone="caution">
        <div className="flex items-start gap-2">
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          <span>{isAr ? fi.cash_flow_disclaimer_ar : fi.cash_flow_disclaimer_en}</span>
        </div>
      </StatusBanner>
      {!fi.cash_flow_available ? (
        <StatusBanner tone="neutral">{t('No transaction-date column detected — net movement by period cannot be shown.', 'لم يتم اكتشاف عمود تاريخ — لا يمكن عرض صافي الحركة حسب الفترة.')}</StatusBanner>
      ) : (
        <>
        {fi.period_figures.length > 1 && (
          <div className="card p-5">
            <p className="section-title mb-4">{t('Inflow / Outflow / Net Movement by Period', 'التدفق الداخل/الخارج/صافي الحركة حسب الفترة')}</p>
            <TrendChart
              data={fi.period_figures.map(p => ({ period: p.period, inflow: p.total_revenue_sar, outflow: p.total_expense_sar, net: p.net_sar }))}
              series={[
                { key: 'inflow', label: t('Inflow', 'التدفق الداخل'), color: '#059669' },
                { key: 'outflow', label: t('Outflow', 'التدفق الخارج'), color: '#dc2626' },
                { key: 'net', label: t('Net Movement', 'صافي الحركة'), color: '#3b82f6' },
              ]}
              valueFormatter={sar}
            />
          </div>
        )}
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Period', 'الفترة')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Inflow', 'التدفق الداخل')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Outflow', 'التدفق الخارج')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Net Movement', 'صافي الحركة')}</th>
            </tr></thead>
            <tbody>
              {fi.period_figures.map((p) => (
                <tr key={p.period} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-slate-700 dark:text-slate-300">{p.period}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-emerald-600 dark:text-emerald-400">+{sar(p.total_revenue_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-red-600 dark:text-red-400">-{sar(p.total_expense_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{sar(p.net_sar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  )
}

function RatiosTab({ fi, t, isAr }: TabProps) {
  const r = fi.ratios
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Expense-to-Revenue Ratio', 'نسبة المصروفات إلى الإيرادات')} value={r?.expense_to_revenue_ratio != null ? r.expense_to_revenue_ratio.toFixed(3) : '—'} icon={Percent} hero />
        <KPICard
          label={t('Top Expense Concentration', 'أعلى تركّز مصروف')}
          value={r?.top_expense_category_share_pct != null ? `${r.top_expense_category_share_pct.toFixed(1)}%` : '—'}
          subtitle={r?.top_expense_category ?? undefined}
          icon={TrendingDown}
          radialPct={r?.top_expense_category_share_pct ?? undefined}
          radialColor="#dc2626"
        />
        <KPICard
          label={t('Top Revenue Concentration', 'أعلى تركّز إيراد')}
          value={r?.top_revenue_category_share_pct != null ? `${r.top_revenue_category_share_pct.toFixed(1)}%` : '—'}
          subtitle={r?.top_revenue_category ?? undefined}
          icon={TrendingUp}
          radialPct={r?.top_revenue_category_share_pct ?? undefined}
          radialColor="#059669"
        />
      </div>
      <StatusBanner tone="neutral">
        <p className="font-semibold mb-1">{t('Ratios not available from this upload', 'نسب غير متاحة من هذا الملف')}</p>
        <p>{isAr ? r?.unavailable_ratios_note_ar : r?.unavailable_ratios_note_en}</p>
      </StatusBanner>
    </div>
  )
}

function VarianceTab({ fi, t }: TabProps) {
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t('Period-over-period variance, reusing the exact Planned-vs-Actual variance shape already established in the Payroll Budget Planner — applied here to period movement (revenue - expense) since this upload has no budget/planned figure.', 'تباين من فترة لأخرى، بنفس صيغة التباين (المخطط مقابل الفعلي) المُستخدمة في مخطط ميزانية الرواتب.')}
      </StatusBanner>
      {fi.period_variances.length === 0 ? (
        <StatusBanner tone="neutral">{t('At least 2 periods are required to compute variance.', 'يتطلب احتساب التباين فترتين على الأقل.')}</StatusBanner>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Period', 'الفترة')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Revenue Δ', 'تغيّر الإيراد')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Expense Δ', 'تغيّر المصروف')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Net Δ', 'تغيّر الصافي')}</th>
            </tr></thead>
            <tbody>
              {fi.period_variances.map((v) => (
                <tr key={v.period} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 text-slate-700 dark:text-slate-300">
                    <div className="font-mono">{v.period}</div>
                    <div className="text-[11px] text-slate-400">{t('vs', 'مقابل')} {v.prior_period}</div>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {v.revenue_variance_sar != null ? <StatusBadge tone={v.revenue_variance_sar >= 0 ? 'positive' : 'critical'}>{v.revenue_variance_sar >= 0 ? '+' : ''}{v.revenue_variance_pct?.toFixed(1)}%</StatusBadge> : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {v.expense_variance_sar != null ? <StatusBadge tone={v.expense_variance_sar <= 0 ? 'positive' : 'caution'}>{v.expense_variance_sar >= 0 ? '+' : ''}{v.expense_variance_pct?.toFixed(1)}%</StatusBadge> : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">
                    {v.net_variance_sar != null ? `${v.net_variance_sar >= 0 ? '+' : ''}${sar(v.net_variance_sar)}` : '—'}
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
