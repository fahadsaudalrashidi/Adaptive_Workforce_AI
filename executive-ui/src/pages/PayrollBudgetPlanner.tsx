/**
 * Payroll Budget — Planned vs. Actual — Phase 37.
 *
 * Its own separate page with its own nav entry, placed near Overtime Cost
 * Intelligence (the concept this module extends to full payroll).
 *
 * Input design: planned/budgeted figures are entered MANUALLY, per real
 * department, rather than via a second uploaded planning file — see
 * backend/core/payroll_budget_engine.py's module docstring for the full
 * reasoning (a second file would force a fuzzy department-name-matching
 * step this platform's other cross-links explicitly refuse to risk). The
 * flow is therefore two steps against the SAME re-uploaded file: (1)
 * upload to see the real actual department list, (2) fill in planned
 * headcount/avg salary per department (keyed by the exact labels this
 * page already showed you) and recompute.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Wallet, RefreshCw, Users, TrendingUp, TrendingDown, Calculator,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'

interface DepartmentVariance {
  department: string
  actual_present: boolean
  planned_submitted: boolean
  actual_headcount: number
  actual_avg_salary_sar: number | null
  actual_total_payroll_sar: number | null
  planned_headcount: number | null
  planned_avg_salary_sar: number | null
  planned_total_payroll_sar: number | null
  headcount_variance: number | null
  headcount_variance_pct: number | null
  payroll_cost_variance_sar: number | null
  payroll_cost_variance_pct: number | null
}
interface PayrollBudgetResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_employees_total: number
  n_valid_salary: number
  n_excluded_invalid_salary: number
  department_variances: DepartmentVariance[]
  company_actual_headcount: number
  company_actual_total_payroll_sar: number
  company_planned_headcount: number | null
  company_planned_total_payroll_sar: number | null
  company_headcount_variance: number | null
  company_headcount_variance_pct: number | null
  company_payroll_cost_variance_sar: number | null
  company_payroll_cost_variance_pct: number | null
  departments_missing_planned_budget: string[]
  narrative_en: string
  narrative_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
}

const COLUMN_LABELS_EN: Record<string, string> = {
  salary: 'Exact numeric salary (required — no range-text)',
  department: 'Department (required)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  salary: 'راتب رقمي دقيق (مطلوب — بدون نص نطاق)',
  department: 'القسم (مطلوب)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function sar(n: number): string {
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

export function PayrollBudgetPlanner() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [file, setFile] = useState<File | null>(null)
  const [filename, setFilename] = useState('')
  const [rowCount, setRowCount] = useState<number | undefined>(undefined)
  const [result, setResult] = useState<PayrollBudgetResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [plannedInputs, setPlannedInputs] = useState<Record<string, { headcount: string; avgSalary: string }>>({})
  const [computing, setComputing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchVariance = useCallback(async (f: File, plannedBudgets: string) => {
    const formData = new FormData()
    formData.append('file', f)
    formData.append('planned_budgets', plannedBudgets)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)
    try {
      const res = await fetch('/api/local/payroll-budget-variance', { method: 'POST', body: formData, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      return await res.json()
    } catch (err) {
      clearTimeout(timeoutId)
      throw err
    }
  }, [])

  const runUpload = useCallback(async (f: File) => {
    setStatus('loading')
    setError(null)
    try {
      const data = await fetchVariance(f, '{}')
      setFile(f)
      setFilename(data.filename)
      setRowCount(data.row_count)
      setResult(data.payroll_budget)
      if (data.payroll_budget?.available) {
        const init: Record<string, { headcount: string; avgSalary: string }> = {}
        for (const d of data.payroll_budget.department_variances) {
          init[d.department] = { headcount: '', avgSalary: '' }
        }
        setPlannedInputs(init)
      }
      setStatus('done')
    } catch (err) {
      const isAbort = err instanceof Error && err.name === 'AbortError'
      setError(isAbort ? t('Upload timed out after 30s. Please try again.', 'انتهت مهلة التحميل بعد 30 ثانية. يرجى المحاولة مرة أخرى.') : err instanceof Error ? err.message : String(err))
      setStatus('error')
    }
  }, [fetchVariance, t])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) void runUpload(f)
  }, [runUpload])

  const reset = useCallback(() => {
    setStatus('idle')
    setFile(null)
    setResult(null)
    setError(null)
    setPlannedInputs({})
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const computeVariance = useCallback(async () => {
    if (!file) return
    setComputing(true)
    setError(null)
    try {
      const planned: Record<string, { planned_headcount: number; planned_avg_salary_sar: number }> = {}
      for (const [dept, v] of Object.entries(plannedInputs)) {
        const hc = parseFloat(v.headcount)
        const sal = parseFloat(v.avgSalary)
        if (!Number.isNaN(hc) && !Number.isNaN(sal) && hc >= 0 && sal >= 0) {
          planned[dept] = { planned_headcount: Math.round(hc), planned_avg_salary_sar: sal }
        }
      }
      const data = await fetchVariance(file, JSON.stringify(planned))
      setResult(data.payroll_budget)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setComputing(false)
    }
  }, [file, plannedInputs, fetchVariance])

  const hasAnyPlanEntered = Object.values(plannedInputs).some(v => v.headcount.trim() && v.avgSalary.trim())

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Payroll Budget — Planned vs. Actual', 'ميزانية الرواتب — المخطط مقابل الفعلي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t('Real actual headcount and payroll cost per department, compared against a budget you enter.', 'حجم العمالة وتكلفة الرواتب الفعلية الحقيقية لكل قسم، مقارنة بميزانية تُدخلها.')}
        </p>
      </motion.div>

      <StatusLegend />

      {(status === 'idle' || status === 'error') && (
        <label className="block cursor-pointer">
          <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv,.parquet,.json" onChange={handleFileSelect} className="hidden" />
          <div className="border-2 border-dashed border-slate-200 dark:border-navy-500/60 rounded-xl p-10 text-center hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-base">
            <Upload size={28} className="text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t('Click to upload or drag and drop', 'انقر للتحميل أو اسحب وأفلت')}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500">{t('Needs a numeric salary column and a department column.', 'يتطلب عمود راتب رقمي وعمود قسم.')}</p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Computing actual payroll per department…', 'جارٍ احتساب الرواتب الفعلية لكل قسم…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && result && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">{filename} · {rowCount?.toLocaleString()} {t('rows', 'صفوف')}</span>
              <button onClick={reset} className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1">
                <RefreshCw size={12} />{t('Analyze another file', 'تحليل ملف آخر')}
              </button>
            </div>

            {!result.available ? (
              <EmptyState
                icon={Wallet}
                title={t('Payroll budget comparison not available', 'مقارنة ميزانية الرواتب غير متاحة')}
                reason={result.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={result.columns_detected}
                columnLabels={Object.fromEntries(Object.keys(result.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
              />
            ) : (
              <>
                <StatusBanner tone="informational" compact>{isAr ? result.disclaimer_ar : result.disclaimer_en}</StatusBanner>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard label={t('Actual Headcount', 'حجم العمالة الفعلي')} value={result.company_actual_headcount} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
                  <KPICard label={t('Actual Payroll', 'الرواتب الفعلية')} value={sar(result.company_actual_total_payroll_sar)} icon={Wallet} hero animateValue />
                  <KPICard
                    label={t('Headcount Variance', 'فرق حجم العمالة')}
                    value={result.company_headcount_variance != null ? `${result.company_headcount_variance > 0 ? '+' : ''}${result.company_headcount_variance}` : t('No plan entered', 'لم تُدخل ميزانية')}
                    icon={result.company_headcount_variance != null && result.company_headcount_variance > 0 ? TrendingUp : TrendingDown}
                    iconColor={result.company_headcount_variance != null && result.company_headcount_variance > 0 ? 'text-amber-500' : 'text-emerald-500'}
                    iconBg={result.company_headcount_variance != null && result.company_headcount_variance > 0 ? 'bg-amber-500/10' : 'bg-emerald-500/10'}
                  />
                  <KPICard
                    label={t('Payroll Cost Variance', 'فرق تكلفة الرواتب')}
                    value={result.company_payroll_cost_variance_sar != null ? `${result.company_payroll_cost_variance_sar > 0 ? '+' : ''}${sar(result.company_payroll_cost_variance_sar)}` : t('No plan entered', 'لم تُدخل ميزانية')}
                    subtitle={result.company_payroll_cost_variance_pct != null ? `${result.company_payroll_cost_variance_pct > 0 ? '+' : ''}${result.company_payroll_cost_variance_pct}%` : undefined}
                    icon={Calculator}
                    iconColor={result.company_payroll_cost_variance_sar != null && result.company_payroll_cost_variance_sar > 0 ? 'text-red-500' : 'text-emerald-500'}
                    iconBg={result.company_payroll_cost_variance_sar != null && result.company_payroll_cost_variance_sar > 0 ? 'bg-red-500/10' : 'bg-emerald-500/10'}
                  />
                </div>

                <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? result.narrative_ar : result.narrative_en}</p></div>

                {result.department_variances.some(d => d.payroll_cost_variance_sar != null) && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Payroll Cost Variance by Department', 'فرق تكلفة الرواتب حسب القسم')}</p>
                    <DepartmentBarChart
                      data={result.department_variances
                        .filter(d => d.payroll_cost_variance_sar != null)
                        .map(d => ({ department: d.department, value: d.payroll_cost_variance_sar as number, color: (d.payroll_cost_variance_sar as number) > 0 ? '#dc2626' : '#059669' }))}
                      valueFormatter={(v) => `${v > 0 ? '+' : ''}${sar(v)}`}
                    />
                  </div>
                )}

                <div className="card overflow-x-auto">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Enter Planned Budget Per Department', 'أدخل الميزانية المخططة لكل قسم')}</p>
                    <button
                      onClick={computeVariance}
                      disabled={!hasAnyPlanEntered || computing}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {computing ? <RefreshCw size={14} className="animate-spin" /> : <Calculator size={14} />}
                      {t('Compute Variance', 'احتساب الفروقات')}
                    </button>
                  </div>
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Actual Headcount', 'الحجم الفعلي')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Actual Avg Salary', 'متوسط الراتب الفعلي')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Planned Headcount', 'حجم العمالة المخطط')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Planned Avg Salary (SAR)', 'متوسط الراتب المخطط (ريال)')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('HC Variance', 'فرق العمالة')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Cost Variance', 'فرق التكلفة')}</th>
                    </tr></thead>
                    <tbody>
                      {result.department_variances.map(d => (
                        <tr key={d.department} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                          <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{d.department}{!d.actual_present && <span className="ms-1 text-[10px] text-amber-500">({t('no actual data', 'لا بيانات فعلية')})</span>}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{d.actual_headcount}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{d.actual_avg_salary_sar != null ? sar(d.actual_avg_salary_sar) : '—'}</td>
                          <td className="px-4 py-2.5">
                            <input
                              type="number" min="0" placeholder="0"
                              value={plannedInputs[d.department]?.headcount ?? ''}
                              onChange={e => setPlannedInputs(prev => ({ ...prev, [d.department]: { ...(prev[d.department] ?? { headcount: '', avgSalary: '' }), headcount: e.target.value } }))}
                              className="w-24 px-2 py-1 text-sm rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400"
                            />
                          </td>
                          <td className="px-4 py-2.5">
                            <input
                              type="number" min="0" placeholder="0"
                              value={plannedInputs[d.department]?.avgSalary ?? ''}
                              onChange={e => setPlannedInputs(prev => ({ ...prev, [d.department]: { ...(prev[d.department] ?? { headcount: '', avgSalary: '' }), avgSalary: e.target.value } }))}
                              className="w-28 px-2 py-1 text-sm rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400"
                            />
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono">
                            {d.headcount_variance != null ? <span className={d.headcount_variance > 0 ? 'text-amber-600 dark:text-amber-400' : d.headcount_variance < 0 ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500'}>{d.headcount_variance > 0 ? '+' : ''}{d.headcount_variance}</span> : <span className="text-slate-400">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono">
                            {d.payroll_cost_variance_sar != null ? <span className={d.payroll_cost_variance_sar > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}>{d.payroll_cost_variance_sar > 0 ? '+' : ''}{sar(d.payroll_cost_variance_sar)}</span> : <span className="text-slate-400">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <StatusBanner tone="neutral">{result.governance_note}</StatusBanner>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}
