/**
 * Accounting Intelligence — Phase 31 (Business Intelligence Suite, Module 2).
 *
 * Covers only the items that genuinely require true double-entry data
 * (separate Debit/Credit columns, and — for Balance Sheet — an Asset/
 * Liability/Equity classification) or a wholly different upload shape
 * (invoice-level AR/AP data) — everything Phase 30's Financial Intelligence
 * page (Revenue/Expense/P&L/Cash Flow/Ratios/Variance from a plain
 * transaction list) already covers is deliberately NOT rebuilt here. See
 * backend/core/accounting_intelligence_engine.py's module docstring for the
 * full non-overlap reasoning.
 *
 * UNLIKE Financial Intelligence's single top-level `available` flag, each of
 * the 5 sections here (General Ledger, Trial Balance, Balance Sheet, AR/AP
 * Aging, Journal Anomalies) has its OWN independent `available` flag — a
 * plain GL export legitimately supports the first three but not AR/AP Aging,
 * for example. Every tab renders its own honest "not detected" state rather
 * than gating the whole page on one upload-wide check.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, RefreshCw, BookOpen, Scale, Building2, Clock, ShieldAlert,
  AlertTriangle, CheckCircle2, XCircle, Copy,
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

// ── Types (mirror backend/core/accounting_intelligence_engine.py) ─────────

interface LedgerTransaction { date: string | null; description: string | null; debit_sar: number | null; credit_sar: number | null }
interface LedgerAccountSummary {
  account: string; account_type: string | null; total_debit_sar: number; total_credit_sar: number
  net_sar: number; n_transactions: number; n_transactions_shown: number; transactions: LedgerTransaction[]
}
interface GeneralLedgerData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  n_transactions_total: number; n_accounts: number; accounts: LedgerAccountSummary[]
  narrative_en: string; narrative_ar: string
}
interface TrialBalanceLine { account: string; total_debit_sar: number; total_credit_sar: number }
interface TrialBalanceData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  lines: TrialBalanceLine[]; total_debit_sar: number | null; total_credit_sar: number | null
  difference_sar: number | null; is_balanced: boolean | null; tolerance_sar: number
  narrative_en: string; narrative_ar: string
}
interface BalanceSheetLine { account: string; balance_sar: number }
interface BalanceSheetData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  assets: BalanceSheetLine[]; liabilities: BalanceSheetLine[]; equity: BalanceSheetLine[]
  net_income_current_period_sar: number | null
  total_assets_sar: number | null; total_liabilities_sar: number | null
  total_equity_reported_sar: number | null; total_equity_including_net_income_sar: number | null
  identity_difference_sar: number | null; is_balanced: boolean | null; n_accounts_unclassified: number
  narrative_en: string; narrative_ar: string
}
interface AgingBucketData { bucket: string; total_sar: number; n_invoices: number }
interface OpenInvoiceData {
  direction: string; party: string; invoice_number: string | null; due_date: string
  amount_sar: number; days_overdue: number; bucket: string
}
interface ARAPAgingData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  as_of_date: string | null; n_open_invoices: number; n_excluded_paid: number
  n_excluded_unclassified_status: number; total_outstanding_sar: number | null
  buckets: AgingBucketData[]; invoices: OpenInvoiceData[]
  narrative_en: string; narrative_ar: string
}
interface AmountAnomalyData {
  account: string; date: string | null; description: string | null; amount_sar: number
  account_q1_sar: number; account_q3_sar: number; fence_low_sar: number; fence_high_sar: number
}
interface DuplicateCandidateData {
  account: string; date: string; amount_sar: number
  description_a: string | null; description_b: string | null
  description_similarity: number | null; confidence: string
}
interface JournalAnomalyData {
  available: boolean; reason: string | null; columns_detected: Record<string, boolean>
  min_sample_size: number; n_accounts_checked: number; n_accounts_suppressed_small_sample: number
  amount_anomalies: AmountAnomalyData[]; duplicate_candidates: DuplicateCandidateData[]
  narrative_en: string; narrative_ar: string
}
interface AccountingIntelligenceData {
  general_ledger: GeneralLedgerData; trial_balance: TrialBalanceData; balance_sheet: BalanceSheetData
  ar_ap_aging: ARAPAgingData; journal_anomalies: JournalAnomalyData
  disclaimer_en: string; disclaimer_ar: string; sources: string[]
}
interface ApiResponse { filename: string; row_count?: number; accounting_intelligence: AccountingIntelligenceData }

const GL_COLUMN_LABELS_EN: Record<string, string> = {
  account: 'Account name (required)', debit: 'Debit amount — separate column (required)',
  credit: 'Credit amount — separate column (required)', date: 'Entry/transaction date (optional)',
  description: 'Description / memo (optional)',
}
const GL_COLUMN_LABELS_AR: Record<string, string> = {
  account: 'اسم الحساب (مطلوب)', debit: 'عمود المدين المنفصل (مطلوب)',
  credit: 'عمود الدائن المنفصل (مطلوب)', date: 'تاريخ القيد (اختياري)', description: 'الوصف (اختياري)',
}
const BS_COLUMN_LABELS_EN: Record<string, string> = {
  account: 'Account name (required)', account_type: 'Account type — Asset/Liability/Equity classification (required)',
  debit: 'Debit amount (required)', credit: 'Credit amount (required)',
}
const BS_COLUMN_LABELS_AR: Record<string, string> = {
  account: 'اسم الحساب (مطلوب)', account_type: 'نوع الحساب — أصول/خصوم/حقوق ملكية (مطلوب)',
  debit: 'المدين (مطلوب)', credit: 'الدائن (مطلوب)',
}
const AGING_COLUMN_LABELS_EN: Record<string, string> = {
  party: 'Customer / vendor name (required)', due_date: 'Due date (required)',
  status: 'Paid / outstanding status (required)', amount: 'Invoice amount — via debit or credit (required)',
}
const AGING_COLUMN_LABELS_AR: Record<string, string> = {
  party: 'اسم العميل / المورد (مطلوب)', due_date: 'تاريخ الاستحقاق (مطلوب)',
  status: 'حالة السداد (مطلوب)', amount: 'مبلغ الفاتورة (مطلوب)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function sar(n: number): string {
  return `SAR ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

type TabKey = 'gl' | 'tb' | 'bs' | 'aging' | 'anomalies'

export function AccountingIntelligence() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('gl')
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
      const response = await fetch('/api/local/accounting-intelligence', {
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

  const ai = result?.accounting_intelligence

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Accounting Intelligence', 'الذكاء المحاسبي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'General Ledger, Trial Balance, Balance Sheet, AR/AP Aging, and Journal Anomaly Detection from your own double-entry data.',
            'دفتر الأستاذ العام وميزان المراجعة والميزانية العمومية وأعمار الذمم وكشف الشذوذ في القيود من بيانات القيد المزدوج الخاصة بك.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a double-entry journal/ledger export (e.g. Account, AccountType, Debit, Credit, Description, Party, DueDate, PaidStatus) — a genuinely different shape from Financial Intelligence\'s plain transaction list. Each section below has its own independent detection: a file may support some sections and not others. Not a certified financial statement — qualified accounting review is required before any filing or decision.',
          'حمّل ملف قيود محاسبية بنظام القيد المزدوج (مثال: Account و AccountType و Debit و Credit و Description و Party و DueDate و PaidStatus) — شكل مختلف تماماً عن قائمة معاملات الذكاء المالي. لكل قسم أدناه اكتشاف مستقل خاص به. هذه ليست قائمة مالية معتمدة — تلزم مراجعة محاسبية متخصصة قبل أي إقرار أو قرار.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500 dark:text-slate-400">
              {t('AR/AP aging as-of date (optional, defaults to today)', 'تاريخ مرجعي لأعمار الذمم (اختياري، الافتراضي اليوم)')}
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
            {t('Analyzing ledger…', 'جارٍ تحليل دفتر الأستاذ…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && ai && (
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
                ['gl', t('General Ledger', 'دفتر الأستاذ'), BookOpen],
                ['tb', t('Trial Balance', 'ميزان المراجعة'), Scale],
                ['bs', t('Balance Sheet', 'الميزانية العمومية'), Building2],
                ['aging', t('AR/AP Aging', 'أعمار الذمم'), Clock],
                ['anomalies', t('Anomalies & Duplicates', 'الشذوذ والتكرار'), ShieldAlert],
              ] as [TabKey, string, typeof BookOpen][]).map(([key, label, Icon]) => (
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

            {tab === 'gl' && <GeneralLedgerTab data={ai.general_ledger} t={t} isAr={isAr} />}
            {tab === 'tb' && <TrialBalanceTab data={ai.trial_balance} t={t} isAr={isAr} />}
            {tab === 'bs' && <BalanceSheetTab data={ai.balance_sheet} t={t} isAr={isAr} />}
            {tab === 'aging' && <AgingTab data={ai.ar_ap_aging} t={t} isAr={isAr} />}
            {tab === 'anomalies' && <AnomaliesTab data={ai.journal_anomalies} t={t} isAr={isAr} />}
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

// ── 1. General Ledger ────────────────────────────────────────────────────

function GeneralLedgerTab({ data, t, isAr }: { data: GeneralLedgerData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={BookOpen}
        title={t('General ledger data not detected', 'لم يتم اكتشاف بيانات دفتر الأستاذ')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? GL_COLUMN_LABELS_AR[k] : GL_COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  const [hoveredAccount, setHoveredAccount] = useState<string | null>(null)
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Journal Lines', 'قيود اليومية')} value={data.n_transactions_total} icon={BookOpen} hero />
        <KPICard label={t('Accounts', 'الحسابات')} value={data.n_accounts} icon={Building2} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.accounts.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Net Position by Account', 'الصافي حسب الحساب')}</p>
          <DepartmentBarChart
            data={data.accounts.map(acc => ({ department: acc.account, value: acc.net_sar, color: acc.net_sar >= 0 ? '#059669' : '#dc2626' }))}
            valueFormatter={sar}
            highlightedKey={hoveredAccount}
            onHoverChange={setHoveredAccount}
          />
        </div>
      )}
      <div className="space-y-3">
        {data.accounts.map((acc) => (
          <details
            key={acc.account}
            className={`card overflow-hidden transition-colors ${hoveredAccount === acc.account ? 'ring-1 ring-blue-500/40' : ''}`}
            onMouseEnter={() => setHoveredAccount(acc.account)}
            onMouseLeave={() => setHoveredAccount(null)}
          >
            <summary className="px-4 py-3 cursor-pointer flex items-center justify-between text-sm">
              <span className="font-medium text-slate-700 dark:text-slate-300">{acc.account}{acc.account_type ? <span className="ml-2 text-[10px] uppercase tracking-wide text-slate-400">{acc.account_type}</span> : null}</span>
              <span className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400 font-mono">
                <span>{t('Dr', 'مدين')} {sar(acc.total_debit_sar)}</span>
                <span>{t('Cr', 'دائن')} {sar(acc.total_credit_sar)}</span>
                <span className={acc.net_sar >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>{t('Net', 'الصافي')} {sar(acc.net_sar)}</span>
                <span>{acc.n_transactions} {t('lines', 'قيود')}</span>
              </span>
            </summary>
            <table className="w-full text-sm border-t border-slate-200 dark:border-slate-700">
              <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Date', 'التاريخ')}</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Description', 'الوصف')}</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Debit', 'مدين')}</th>
                <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Credit', 'دائن')}</th>
              </tr></thead>
              <tbody>
                {acc.transactions.map((txn, i) => (
                  <tr key={i} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <td className="px-4 py-2 font-mono text-slate-600 dark:text-slate-400">{txn.date ?? '—'}</td>
                    <td className="px-4 py-2 text-slate-600 dark:text-slate-400">{txn.description ?? '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-slate-700 dark:text-slate-300">{txn.debit_sar != null ? sar(txn.debit_sar) : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-slate-700 dark:text-slate-300">{txn.credit_sar != null ? sar(txn.credit_sar) : '—'}</td>
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

// ── 2. Trial Balance ─────────────────────────────────────────────────────

function TrialBalanceTab({ data, t, isAr }: { data: TrialBalanceData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Scale}
        title={t('Trial balance not computable from this upload', 'ميزان المراجعة غير قابل للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? GL_COLUMN_LABELS_AR[k] : GL_COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone={data.is_balanced ? 'positive' : 'critical'}>
        <div className="flex items-start gap-2">
          {data.is_balanced ? <CheckCircle2 size={16} className="flex-shrink-0 mt-0.5" /> : <XCircle size={16} className="flex-shrink-0 mt-0.5" />}
          <span>{isAr ? data.narrative_ar : data.narrative_en}</span>
        </div>
      </StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Debit', 'إجمالي المدين')} value={sar(data.total_debit_sar ?? 0)} icon={Scale} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('Total Credit', 'إجمالي الدائن')} value={sar(data.total_credit_sar ?? 0)} icon={Scale} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('Difference', 'الفارق')} value={sar(Math.abs(data.difference_sar ?? 0))} icon={data.is_balanced ? CheckCircle2 : AlertTriangle} hero radialColor={data.is_balanced ? '#059669' : '#dc2626'} />
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Account', 'الحساب')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Debit', 'مدين')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Credit', 'دائن')}</th>
          </tr></thead>
          <tbody>
            {data.lines.map((l) => (
              <tr key={l.account} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{l.account}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{l.total_debit_sar > 0 ? sar(l.total_debit_sar) : '—'}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{l.total_credit_sar > 0 ? sar(l.total_credit_sar) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 3. Balance Sheet ─────────────────────────────────────────────────────

function BSLineTable({ rows, t }: { rows: BalanceSheetLine[]; t: T }) {
  if (rows.length === 0) return <p className="text-xs text-slate-400 px-1">{t('None', 'لا يوجد')}</p>
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map((l) => (
          <tr key={l.account} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
            <td className="px-4 py-2 text-slate-700 dark:text-slate-300">{l.account}</td>
            <td className="px-4 py-2 text-right font-mono text-slate-700 dark:text-slate-300">{sar(l.balance_sar)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function BalanceSheetTab({ data, t, isAr }: { data: BalanceSheetData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Building2}
        title={t('Balance sheet not computable from this upload', 'الميزانية العمومية غير قابلة للاحتساب من هذا الملف')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? BS_COLUMN_LABELS_AR[k] : BS_COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone={data.is_balanced ? 'positive' : 'critical'}>
        <div className="flex items-start gap-2">
          {data.is_balanced ? <CheckCircle2 size={16} className="flex-shrink-0 mt-0.5" /> : <XCircle size={16} className="flex-shrink-0 mt-0.5" />}
          <span>{isAr ? data.narrative_ar : data.narrative_en}</span>
        </div>
      </StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
        <KPICard label={t('Total Assets', 'إجمالي الأصول')} value={sar(data.total_assets_sar ?? 0)} icon={Building2} hero iconColor="text-blue-500" />
        <KPICard label={t('Total Liabilities', 'إجمالي الخصوم')} value={sar(data.total_liabilities_sar ?? 0)} icon={Building2} iconColor="text-red-500" iconBg="bg-red-500/10" />
        <KPICard label={t('Equity (Reported)', 'حقوق الملكية (المُبلّغة)')} value={sar(data.total_equity_reported_sar ?? 0)} icon={Building2} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" />
        <KPICard label={t('Net Income (Unclosed)', 'صافي الدخل (غير مُقفل)')} value={sar(data.net_income_current_period_sar ?? 0)} icon={Building2} radialColor={(data.net_income_current_period_sar ?? 0) >= 0 ? '#059669' : '#dc2626'} />
      </div>
      {(data.total_assets_sar ?? 0) > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Balance Sheet Composition', 'تركيبة الميزانية العمومية')}</p>
          <CompositionChart
            data={[
              { label: t('Assets', 'الأصول'), value: data.total_assets_sar ?? 0, color: '#3b82f6' },
              { label: t('Liabilities', 'الخصوم'), value: data.total_liabilities_sar ?? 0, color: '#dc2626' },
              { label: t('Equity', 'حقوق الملكية'), value: data.total_equity_reported_sar ?? 0, color: '#059669' },
            ].filter(d => d.value > 0)}
            valueFormatter={sar}
          />
        </div>
      )}
      <div className="grid md:grid-cols-3 gap-5">
        <div className="card">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Assets', 'الأصول')}</div>
          <BSLineTable rows={data.assets} t={t} />
        </div>
        <div className="card">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Liabilities', 'الخصوم')}</div>
          <BSLineTable rows={data.liabilities} t={t} />
        </div>
        <div className="card">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Equity', 'حقوق الملكية')}</div>
          <BSLineTable rows={data.equity} t={t} />
        </div>
      </div>
    </div>
  )
}

// ── 4. AR/AP Aging ────────────────────────────────────────────────────────

const BUCKET_TONE: Record<string, 'positive' | 'informational' | 'caution' | 'critical'> = {
  current: 'positive', '1-30': 'informational', '31-60': 'caution', '61-90': 'caution', '90+': 'critical',
}

function AgingTab({ data, t, isAr }: { data: ARAPAgingData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={Clock}
        title={t('AR/AP invoice-level data not detected', 'لم يتم اكتشاف بيانات فواتير الذمم المدينة/الدائنة')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? AGING_COLUMN_LABELS_AR[k] : AGING_COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Total Outstanding', 'إجمالي المستحق')} value={sar(data.total_outstanding_sar ?? 0)} icon={Clock} hero iconColor="text-amber-500" />
        <KPICard label={t('Open Invoices', 'الفواتير المفتوحة')} value={data.n_open_invoices} icon={Clock} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
        <KPICard label={t('As Of', 'حتى تاريخ')} value={data.as_of_date ?? '—'} icon={Clock} iconColor="text-slate-500" iconBg="bg-slate-500/10" subtitle={t(`${data.n_excluded_paid} paid item(s) excluded`, `${data.n_excluded_paid} بنداً مدفوعاً مستبعداً`)} />
      </div>
      <NarrativeCard en={data.narrative_en} ar={data.narrative_ar} isAr={isAr} />
      {data.buckets.length > 0 && (
        <div className="card p-5">
          <p className="section-title mb-4">{t('Outstanding by Aging Bucket', 'المستحق حسب فئة العمر')}</p>
          <DepartmentBarChart
            data={data.buckets.map(b => ({
              department: b.bucket,
              value: b.total_sar,
              color: b.bucket === 'current' ? '#059669' : b.bucket === '1-30' ? '#3b82f6' : b.bucket === '90+' ? '#dc2626' : '#d97706',
              tooltipExtra: { [t('Invoices', 'الفواتير')]: b.n_invoices },
            }))}
            valueFormatter={sar}
            sortByValue={false}
            height={200}
          />
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {data.buckets.map((b) => (
          <div key={b.bucket} className="card p-3 text-center">
            <StatusBadge tone={BUCKET_TONE[b.bucket] ?? 'neutral'}>{b.bucket}</StatusBadge>
            <p className="text-sm font-mono font-semibold text-slate-700 dark:text-slate-300 mt-2">{sar(b.total_sar)}</p>
            <p className="text-[11px] text-slate-400">{b.n_invoices} {t('invoice(s)', 'فاتورة')}</p>
          </div>
        ))}
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Party', 'الطرف')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Direction', 'الاتجاه')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Due Date', 'تاريخ الاستحقاق')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Amount', 'المبلغ')}</th>
            <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Bucket', 'الفئة')}</th>
          </tr></thead>
          <tbody>
            {data.invoices.map((inv, i) => (
              <tr key={i} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{inv.party}{inv.invoice_number ? <span className="ml-2 text-[11px] text-slate-400 font-mono">{inv.invoice_number}</span> : null}</td>
                <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400 uppercase text-xs">{inv.direction}</td>
                <td className="px-4 py-2.5 font-mono text-slate-600 dark:text-slate-400">{inv.due_date}</td>
                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{sar(inv.amount_sar)}</td>
                <td className="px-4 py-2.5 text-right"><StatusBadge tone={BUCKET_TONE[inv.bucket] ?? 'neutral'}>{inv.bucket}</StatusBadge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── 5. Journal Anomalies & Duplicates ───────────────────────────────────

function AnomaliesTab({ data, t, isAr }: { data: JournalAnomalyData; t: T; isAr: boolean }) {
  if (!data.available) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title={t('Journal anomaly detection not available', 'كشف الشذوذ في القيود غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? GL_COLUMN_LABELS_AR[k] : GL_COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t(
          `Statistical outliers use IQR fences per account, only for accounts with at least ${data.min_sample_size} transactions — ${data.n_accounts_checked} account(s) checked, ${data.n_accounts_suppressed_small_sample} suppressed for too few transactions.`,
          `تُستخدم أسيجة IQR الإحصائية لكل حساب، فقط للحسابات التي تحتوي على ${data.min_sample_size} معاملات على الأقل — تم فحص ${data.n_accounts_checked} حساباً واستبعاد ${data.n_accounts_suppressed_small_sample} لقلة المعاملات.`
        )}
      </StatusBanner>
      <div className="grid grid-cols-2 gap-5">
        <KPICard label={t('Amount Anomalies', 'قيم شاذة')} value={data.amount_anomalies.length} icon={AlertTriangle} hero iconColor="text-amber-500" />
        <KPICard label={t('Duplicate Candidates', 'حالات تكرار محتملة')} value={data.duplicate_candidates.length} icon={Copy} iconColor="text-blue-500" iconBg="bg-blue-500/10" />
      </div>

      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {t('Amount Anomalies (unusual relative to this account\'s own history)', 'قيم شاذة (غير معتادة مقارنة بتاريخ الحساب نفسه)')}
        </div>
        {data.amount_anomalies.length === 0 ? (
          <p className="text-xs text-slate-400 px-4 py-3">{t('None detected.', 'لم يتم اكتشاف أي شذوذ.')}</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Account', 'الحساب')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Date', 'التاريخ')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Description', 'الوصف')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Amount', 'المبلغ')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Normal Range', 'النطاق المعتاد')}</th>
            </tr></thead>
            <tbody>
              {data.amount_anomalies.map((a, i) => (
                <tr key={i} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{a.account}</td>
                  <td className="px-4 py-2 font-mono text-slate-600 dark:text-slate-400">{a.date ?? '—'}</td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-400">{a.description ?? '—'}</td>
                  <td className="px-4 py-2 text-right font-mono font-semibold text-amber-600 dark:text-amber-400">{sar(a.amount_sar)}</td>
                  <td className="px-4 py-2 text-right font-mono text-[11px] text-slate-400">{sar(a.fence_low_sar < 0 ? 0 : a.fence_low_sar)} – {sar(a.fence_high_sar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card overflow-x-auto">
        <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
          {t('Duplicate Candidates (matched on date + account + amount)', 'حالات تكرار محتملة (تطابق التاريخ والحساب والمبلغ)')}
        </div>
        {data.duplicate_candidates.length === 0 ? (
          <p className="text-xs text-slate-400 px-4 py-3">{t('None detected.', 'لم يتم اكتشاف أي تكرار.')}</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="text-left border-b border-slate-100 dark:border-slate-800">
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Account', 'الحساب')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Date', 'التاريخ')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Amount', 'المبلغ')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Descriptions', 'الأوصاف')}</th>
              <th className="px-4 py-2 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Confidence', 'مستوى الثقة')}</th>
            </tr></thead>
            <tbody>
              {data.duplicate_candidates.map((d, i) => (
                <tr key={i} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-300">{d.account}</td>
                  <td className="px-4 py-2 font-mono text-slate-600 dark:text-slate-400">{d.date}</td>
                  <td className="px-4 py-2 text-right font-mono text-slate-700 dark:text-slate-300">{sar(d.amount_sar)}</td>
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400 text-[12px]">
                    <div>{d.description_a ?? '—'}</div>
                    {d.description_b !== d.description_a && <div className="text-slate-400">{d.description_b ?? '—'}</div>}
                  </td>
                  <td className="px-4 py-2 text-right"><StatusBadge tone={d.confidence === 'high' ? 'critical' : 'caution'}>{d.confidence === 'high' ? t('High', 'عالية') : t('Review', 'للمراجعة')}</StatusBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
