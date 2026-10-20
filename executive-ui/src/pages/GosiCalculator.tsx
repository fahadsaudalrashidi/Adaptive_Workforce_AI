/**
 * GOSI Contribution Calculator — Phase 37.
 *
 * Its own separate page with its own nav entry — NOT bundled into the
 * Saudi Labor Law Calculators tabbed page. That earlier bundling pattern
 * made features feel cramped/hard to discover; this module gets a clear,
 * standalone entry point instead.
 *
 * Computes REAL government social-insurance contribution amounts for the
 * current published rate period (see backend/core/gosi_calculator_engine.py's
 * module docstring for full sourcing) — not an illustrative estimate. When
 * no GOSI system/tier column is detected, BOTH Old System and New System
 * figures are shown for every Saudi employee rather than guessing.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Landmark, RefreshCw, Users, AlertTriangle, Globe2,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { StatusBadge } from '../components/shared/StatusBadge'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { LatinText } from '../components/shared/LatinText'
import { EmployeeSearchInput } from '../components/shared/EmployeeSearchInput'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { useEmployeeSearch } from '../hooks/useEmployeeSearch'

interface GosiCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  is_saudi: boolean
  subject_wage_sar: number
  subject_wage_capped: boolean
  old_system_total_sar: number | null
  new_system_total_sar: number | null
  applicable_system: string
  applicable_employee_sar: number
  applicable_employer_sar: number
  applicable_total_sar: number
}
interface DepartmentGosiBreakdown {
  department: string
  n_employees: number
  total_employee_contribution_sar: number
  total_employer_contribution_sar: number
  total_contribution_sar: number
}
interface GosiResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_employees_total: number
  n_valid_computed: number
  n_excluded_invalid_salary: number
  n_excluded_unclassifiable_nationality: number
  housing_allowance_understated_note: string | null
  candidates: GosiCandidate[]
  department_breakdown: DepartmentGosiBreakdown[]
  narrative_en: string
  narrative_ar: string
  numeric_salary_required_note_en: string
  numeric_salary_required_note_ar: string
  effective_period: string
  wage_cap_sar: number
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

const COLUMN_LABELS_EN: Record<string, string> = {
  salary: 'Exact numeric salary (required — no range-text)',
  nationality: 'Nationality / Saudi status (required)',
  housing_allowance: 'Housing allowance (optional — improves accuracy)',
  gosi_system_tier: 'GOSI system/tier (optional — shows both if absent)',
  department: 'Department (optional)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  salary: 'راتب رقمي دقيق (مطلوب — بدون نص نطاق)',
  nationality: 'الجنسية / الحالة السعودية (مطلوب)',
  housing_allowance: 'بدل السكن (اختياري — يحسّن الدقة)',
  gosi_system_tier: 'نظام/فئة التأمينات (اختياري — يُعرض كلاهما عند غيابه)',
  department: 'القسم (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

function sar(n: number): string {
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

export function GosiCalculator() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [filename, setFilename] = useState<string>('')
  const [rowCount, setRowCount] = useState<number | undefined>(undefined)
  const [result, setResult] = useState<GosiResult | null>(null)
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
      const res = await fetch('/api/local/gosi-calculator', { method: 'POST', body: formData, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      const data = await res.json()
      setFilename(data.filename)
      setRowCount(data.row_count)
      setResult(data.gosi)
      setStatus('done')
    } catch (err) {
      clearTimeout(timeoutId)
      const isAbort = err instanceof Error && err.name === 'AbortError'
      setError(isAbort ? t('Upload timed out after 30s. Please try again.', 'انتهت مهلة التحميل بعد 30 ثانية. يرجى المحاولة مرة أخرى.') : err instanceof Error ? err.message : String(err))
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

  const allCandidates = result?.candidates ?? []
  const { query, setQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    allCandidates,
    useCallback((c: GosiCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('GOSI Contribution Calculator', 'حاسبة اشتراكات التأمينات الاجتماعية (GOSI)')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Real social-insurance contribution amounts per employee and department — Old System, New System, and non-Saudi occupational hazards.',
            'مبالغ اشتراكات التأمينات الاجتماعية الحقيقية لكل موظف وقسم — النظام القديم والجديد ومخاطر العمل لغير السعوديين.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="critical" icon={AlertTriangle}>
        {t(
          'These figures compute REAL government contribution amounts for the current published rate period — they are NOT illustrative planning estimates. GOSI New System rates rise every July on a fixed schedule; reconfirm the currently applicable rate directly via GOSI/Ta\'meenati before relying on this for any actual payroll or compliance action, especially outside the stated effective period.',
          'تحتسب هذه الأرقام مبالغ اشتراكات حكومية حقيقية لفترة المعدلات المنشورة حالياً — وهي ليست تقديرات تخطيطية إرشادية. ترتفع معدلات النظام الجديد كل يوليو وفق جدول ثابت؛ يرجى التحقق من المعدل الحالي مباشرة عبر التأمينات الاجتماعية (تأميناتي) قبل الاعتماد على هذا الرقم في أي إجراء فعلي للرواتب أو الامتثال، خصوصاً خارج الفترة المذكورة.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <label className="block cursor-pointer">
          <input ref={fileInputRef} type="file" accept=".xlsx,.xls,.csv,.parquet,.json" onChange={handleFileSelect} className="hidden" />
          <div className="border-2 border-dashed border-slate-200 dark:border-navy-500/60 rounded-xl p-10 text-center hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-base">
            <Upload size={28} className="text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">{t('Click to upload or drag and drop', 'انقر للتحميل أو اسحب وأفلت')}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500">{t('Needs a numeric salary column and a nationality column.', 'يتطلب عمود راتب رقمي وعمود جنسية.')}</p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Computing GOSI contributions…', 'جارٍ احتساب اشتراكات التأمينات…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
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
                icon={Landmark}
                title={t('GOSI calculation not available', 'حساب التأمينات غير متاح')}
                reason={result.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={result.columns_detected}
                columnLabels={Object.fromEntries(Object.keys(result.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
              />
            ) : (
              <>
                <StatusBanner tone="informational" compact>
                  {t(`Effective period: ${result.effective_period}. Contribution base capped at SAR ${result.wage_cap_sar.toLocaleString()}/month.`, `الفترة الفعلية: ${result.effective_period}. سقف وعاء الاشتراك ${result.wage_cap_sar.toLocaleString()} ريال/شهرياً.`)}
                </StatusBanner>
                {result.housing_allowance_understated_note && (
                  <StatusBanner tone="caution" compact>{result.housing_allowance_understated_note}</StatusBanner>
                )}

                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard label={t('Employees Computed', 'الموظفون المُحتسبون')} value={result.n_valid_computed} subtitle={t(`of ${result.n_employees_total} total`, `من ${result.n_employees_total} إجمالاً`)} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
                  <KPICard label={t('Excluded (Bad Salary)', 'مستبعد (راتب غير صالح)')} value={result.n_excluded_invalid_salary} icon={AlertTriangle} iconColor="text-amber-500" iconBg="bg-amber-500/10" animateValue />
                  <KPICard label={t('Total Contribution', 'إجمالي الاشتراكات')} value={sar(result.department_breakdown.reduce((s, d) => s + d.total_contribution_sar, 0))} icon={Landmark} hero animateValue />
                  <KPICard label={t('Saudi / Non-Saudi', 'سعودي / غير سعودي')} value={`${result.candidates.filter(c => c.is_saudi).length} / ${result.candidates.filter(c => !c.is_saudi).length}`} icon={Globe2} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" />
                </div>

                <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? result.narrative_ar : result.narrative_en}</p></div>

                {result.department_breakdown.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Total Contribution by Department', 'إجمالي الاشتراكات حسب القسم')}</p>
                    <DepartmentBarChart
                      data={result.department_breakdown.map(d => ({ department: d.department, value: d.total_contribution_sar, tooltipExtra: { [t('Employees', 'الموظفون')]: d.n_employees } }))}
                      valueFormatter={sar}
                    />
                  </div>
                )}

                {result.department_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department Breakdown', 'التوزيع حسب القسم')}</p>
                    </div>
                    <table className="w-full text-sm">
                      <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Employees', 'الموظفون')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Employee Share', 'حصة الموظف')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Employer Share', 'حصة صاحب العمل')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total', 'الإجمالي')}</th>
                      </tr></thead>
                      <tbody>
                        {result.department_breakdown.map(d => (
                          <tr key={d.department} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{d.department}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{d.n_employees}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(d.total_employee_contribution_sar)}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(d.total_employer_contribution_sar)}</td>
                            <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{sar(d.total_contribution_sar)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {result.candidates.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                      <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee-Level Detail', 'التفاصيل على مستوى الموظف')}</p>
                      <EmployeeSearchInput
                        value={query}
                        onChange={setQuery}
                        placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
                        resultCount={filteredCandidates.length}
                        totalCount={allCandidates.length}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'معرّف الموظف')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Status', 'الحالة')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('System', 'النظام')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Subject Wage', 'الوعاء')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Applicable Total', 'الإجمالي المُطبَّق')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Old System', 'النظام القديم')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('New System', 'النظام الجديد')}</th>
                      </tr></thead>
                      <tbody>
                        {filteredCandidates.length === 0 && (
                          <tr><td colSpan={8} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
                        )}
                        {filteredCandidates.map((c, i) => (
                          <tr key={`${c.record_id_safe}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText></td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                            <td className="px-4 py-2.5">{c.is_saudi ? <StatusBadge tone="informational">{t('Saudi', 'سعودي')}</StatusBadge> : <StatusBadge tone="neutral">{t('Non-Saudi', 'غير سعودي')}</StatusBadge>}</td>
                            <td className="px-4 py-2.5">
                              {c.applicable_system === 'unspecified_both_shown'
                                ? <StatusBadge tone="caution">{t('Both shown', 'كلاهما')}</StatusBadge>
                                : c.applicable_system === 'non_saudi'
                                ? <StatusBadge tone="neutral">—</StatusBadge>
                                : <StatusBadge tone="positive">{c.applicable_system === 'old' ? t('Old', 'قديم') : t('New', 'جديد')}</StatusBadge>}
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.subject_wage_sar)}{c.subject_wage_capped && <span className="ms-1 text-amber-500" title={t('Capped at wage ceiling', 'مُسقّف عند الحد الأقصى')}>*</span>}</td>
                            <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{sar(c.applicable_total_sar)}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.old_system_total_sar != null ? sar(c.old_system_total_sar) : '—'}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.new_system_total_sar != null ? sar(c.new_system_total_sar) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{result.governance_note}</p>
                  <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">{t('Sources', 'المصادر')}</p>
                  <ul className="text-[11px] opacity-70 space-y-0.5">{result.sources.map((s, i) => <li key={i}>· {s}</li>)}</ul>
                </StatusBanner>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}
