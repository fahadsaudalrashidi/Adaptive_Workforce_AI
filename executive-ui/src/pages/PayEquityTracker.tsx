/**
 * Pay Equity Analysis — Phase 17.
 *
 * Real analysis only: uploads a file to POST /api/local/pay-equity
 * (backend/core/pay_equity_engine.py) and renders whatever the backend
 * actually computed. Narrower and more specific than Fairness/Bias Audit
 * (which looks at OUTCOME rates like attrition risk): this asks whether
 * people in comparable roles (same job level and/or department) are paid
 * comparably across protected-attribute groups — reusing ethical_ai.py's
 * minimum-group-size floor, high-cardinality bucketing guard, and
 * significance-testing discipline (see pay_equity_engine.py's module
 * docstring). A gap that fails the significance test is shown as such,
 * never silently dropped or presented as confirmed.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Coins, RefreshCw, Users, TrendingDown, Ban,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { SortToggle } from '../components/shared/SortToggle'
import { StatusBadge } from '../components/shared/StatusBadge'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { useSortableTable } from '../hooks/useSortableTable'

interface PayGapComparison {
  cohort_label_en: string
  cohort_label_ar: string
  comparability_basis: string
  protected_attribute: string
  protected_attribute_type: string
  was_bucketed: boolean
  higher_paid_group: string
  lower_paid_group: string
  higher_paid_group_n: number
  lower_paid_group_n: number
  higher_paid_group_mean_sar: number
  lower_paid_group_mean_sar: number
  pay_gap_pct: number
  p_value: number | null
  statistically_significant: boolean | null
  interpretation_en: string
  interpretation_ar: string
}

interface PayEquity {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  salary_column: string | null
  protected_attributes_used: string[]
  comparability_factors_used: string[]
  n_employees_total: number
  n_comparisons_computed: number
  n_comparisons_suppressed_small_sample: number
  comparisons: PayGapComparison[]
  n_significant_gaps: number
  narrative_en: string
  narrative_ar: string
  granularity_notes: string[]
  department_normalization_notes: string[]
  pay_equity_confidence: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  pay_equity: PayEquity
}

const UPLOAD_TIMEOUT_MS = 30_000

const COLUMN_LABELS_EN: Record<string, string> = {
  salary_or_compensation: 'Salary / compensation (e.g. MonthlyIncome)',
  protected_attribute: 'A protected attribute (Gender, Nationality, or Age)',
  job_level: 'Job level / career grade (optional — enables role-level comparison)',
  department: 'Department (optional — enables department-level comparison)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  salary_or_compensation: 'الراتب / التعويض (مثال: MonthlyIncome)',
  protected_attribute: 'خاصية محمية (الجنس أو الجنسية أو العمر)',
  job_level: 'المستوى الوظيفي (اختياري — يفعّل المقارنة حسب المستوى)',
  department: 'القسم (اختياري — يفعّل المقارنة حسب القسم)',
}

type SortKey = 'gap' | 'significance' | 'cohort'

function sar(n: number): string {
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

export function PayEquityTracker() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
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

      const response = await fetch('/api/local/pay-equity', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
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

  const pe = result?.pay_equity
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []

  // Phase 17 — hook called unconditionally every render (Rules of Hooks);
  // receives an empty array before a dataset is loaded.
  const { sorted: sortedComparisons, sortKey, setSortKey } = useSortableTable<PayGapComparison, SortKey>(
    pe?.comparisons ?? [],
    {
      gap: (a, b) => b.pay_gap_pct - a.pay_gap_pct,
      significance: (a, b) => Number(b.statistically_significant) - Number(a.statistically_significant),
      cohort: (a, b) => a.cohort_label_en.localeCompare(b.cohort_label_en),
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Pay Equity Analysis', 'تحليل عدالة الأجور')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Statistical pay-gap indicator within comparable roles — a narrower, more specific analysis than Fairness/Bias Audit.',
            'مؤشر إحصائي لفجوة الأجور ضمن أدوار قابلة للمقارنة — تحليل أكثر تحديداً من تدقيق العدالة والتحيّز.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Statistical pay-gap indicator for internal HR review — NOT a legal pay-equity certification or audit. Gaps are only computed within comparable groups (same job level and/or department), gated by a minimum-group-size floor (n≥20 per group) and statistical-significance testing (p<0.05). A confirmed, significant gap is a signal to investigate, not proof of unlawful discrimination — qualified HR and legal review is required before any compensation action.',
          'مؤشر إحصائي لفجوة الأجور لأغراض المراجعة الداخلية للموارد البشرية — وليس شهادة أو تدقيقاً قانونياً. تُحتسب الفجوات فقط ضمن مجموعات قابلة للمقارنة (نفس المستوى الوظيفي و/أو القسم)، بحد أدنى ٢٠ موظفاً لكل مجموعة واختبار دلالة إحصائية (p<0.05). الفجوة المؤكدة ذات الدلالة هي إشارة للتحقيق، وليست دليلاً على تمييز غير قانوني — تلزم مراجعة متخصصي الموارد البشرية والقانون قبل أي إجراء متعلق بالتعويضات.'
        )}
      </StatusBanner>

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with a salary/compensation column (e.g. MonthlyIncome), a protected attribute (Gender, Nationality, or Age), and at least one comparability factor (JobLevel and/or Department) to compute real pay-gap comparisons. Missing any of these, this page honestly says so instead of fabricating a gap.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود راتب/تعويض (مثال: MonthlyIncome)، وخاصية محمية (الجنس أو الجنسية أو العمر)، وعامل مقارنة واحد على الأقل (المستوى الوظيفي و/أو القسم) لحساب مقارنات فجوة الأجور الفعلية. في حال غياب أي منها، تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال فجوة.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <label className="block cursor-pointer">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.parquet,.json"
            onChange={handleFileSelect}
            className="hidden"
          />
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
            {t('Analyzing pay equity…', 'جارٍ تحليل عدالة الأجور…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && pe && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {result?.filename} · {result?.row_count?.toLocaleString()} {t('rows', 'صفوف')}
              </span>
              <button
                onClick={reset}
                className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1"
              >
                <RefreshCw size={12} />
                {t('Analyze another file', 'تحليل ملف آخر')}
              </button>
            </div>

            {duplicateWarnings.length > 0 && (
              <StatusBanner tone="caution" compact>
                <ul className="space-y-0.5">
                  {duplicateWarnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </StatusBanner>
            )}

            {!pe.available ? (
              <EmptyState
                icon={Coins}
                title={t('Pay equity data not detected in this upload', 'لم يتم اكتشاف بيانات عدالة الأجور في هذا الملف')}
                reason={pe.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={pe.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(pe.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Employees Analyzed', 'الموظفون المُحلَّلون')}
                    value={pe.n_employees_total.toLocaleString()}
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `Comparability factors used: ${pe.comparability_factors_used.join(', ') || 'none'}.`,
                      `عوامل المقارنة المستخدمة: ${pe.comparability_factors_used.join('، ') || 'لا يوجد'}.`
                    )}
                  />
                  <KPICard
                    label={t('Significant Pay Gaps', 'فجوات أجور ذات دلالة')}
                    value={pe.n_significant_gaps}
                    subtitle={t(`of ${pe.n_comparisons_computed} comparisons`, `من ${pe.n_comparisons_computed} مقارنة`)}
                    icon={TrendingDown}
                    hero
                    animateValue
                    radialPct={pe.n_comparisons_computed > 0 ? (100 * pe.n_significant_gaps / pe.n_comparisons_computed) : undefined}
                    radialColor={pe.n_significant_gaps > 0 ? '#dc2626' : '#059669'}
                    detail={t('Statistically significant at p<0.05 — a signal to investigate, not proof of discrimination.', 'ذو دلالة إحصائية عند p<0.05 — إشارة للتحقيق، وليست دليلاً على تمييز.')}
                  />
                  <KPICard
                    label={t('Comparisons Computed', 'المقارنات المحتسبة')}
                    value={pe.n_comparisons_computed}
                    icon={Coins}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    animateValue
                    detail={t(
                      `Protected attributes tested: ${pe.protected_attributes_used.join(', ') || 'none'}.`,
                      `الخصائص المحمية المُختبرة: ${pe.protected_attributes_used.join('، ') || 'لا يوجد'}.`
                    )}
                  />
                  <KPICard
                    label={t('Suppressed (Small Sample)', 'مستبعد (عينة صغيرة)')}
                    value={pe.n_comparisons_suppressed_small_sample}
                    subtitle={t('n<20 in a group', 'أقل من ٢٠ في مجموعة')}
                    icon={Ban}
                    iconColor="text-slate-400"
                    iconBg="bg-slate-500/10"
                    animateValue
                    detail={t('Never reported on too few people — the same discipline as Fairness/Bias Audit.', 'لا يُبلَّغ عن نتيجة لعدد قليل جداً من الأشخاص — نفس انضباط تدقيق العدالة والتحيّز.')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? pe.narrative_ar : pe.narrative_en}
                  </p>
                </div>

                {pe.comparisons.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Pay Gap by Cohort', 'فجوة الأجور حسب المجموعة')}</p>
                    <DepartmentBarChart
                      data={pe.comparisons.map(c => ({
                        department: isAr ? c.cohort_label_ar : c.cohort_label_en,
                        value: c.pay_gap_pct,
                        color: c.statistically_significant ? '#dc2626' : '#64748b',
                      }))}
                      valueFormatter={(v) => `${v.toFixed(1)}%`}
                    />
                  </div>
                )}

                {pe.comparisons.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<SortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'gap', label: t('Gap %', 'الفجوة %') },
                          { key: 'significance', label: t('Significance', 'الدلالة') },
                          { key: 'cohort', label: t('Cohort', 'المجموعة') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Cohort', 'المجموعة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Comparison', 'المقارنة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Gap', 'الفجوة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('p-value', 'قيمة p')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Significance', 'الدلالة')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedComparisons.map((c, i) => (
                          <tr key={`${c.cohort_label_en}-${c.protected_attribute}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 align-top">
                            <td className="px-4 py-2.5">
                              <div className="font-medium text-slate-700 dark:text-slate-300">
                                {isAr ? c.cohort_label_ar : c.cohort_label_en}
                              </div>
                              <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5 max-w-sm">
                                {isAr ? c.interpretation_ar : c.interpretation_en}
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">
                              <div>{c.protected_attribute} {c.was_bucketed && <span className="text-[10px] text-slate-400">({t('bucketed', 'مُقسّم')})</span>}</div>
                              <div className="text-[11px] mt-0.5">
                                {c.lower_paid_group} ({c.lower_paid_group_n}, {sar(c.lower_paid_group_mean_sar)}) {t('vs', 'مقابل')} {c.higher_paid_group} ({c.higher_paid_group_n}, {sar(c.higher_paid_group_mean_sar)})
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">
                              {c.pay_gap_pct.toFixed(1)}%
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                              {c.p_value != null ? c.p_value.toFixed(4) : '—'}
                            </td>
                            <td className="px-4 py-2.5 text-center">
                              {c.statistically_significant === true ? (
                                <StatusBadge tone="critical">{t('Significant', 'ذو دلالة')}</StatusBadge>
                              ) : c.statistically_significant === false ? (
                                <StatusBadge tone="neutral">{t('Not Significant', 'غير ذي دلالة')}</StatusBadge>
                              ) : (
                                <StatusBadge tone="neutral">{t('Unknown', 'غير معروف')}</StatusBadge>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {pe.comparisons.length === 0 && (
                  <StatusBanner tone="neutral">
                    {t(
                      'No comparable-role cohort in this dataset had at least two protected-attribute groups with 20+ employees each — no pay comparison could be computed without relying on too-small samples.',
                      'لم تحتوِ أي مجموعة أدوار قابلة للمقارنة في هذه البيانات على خاصيتين محميتين بحجم ٢٠ موظفاً على الأقل لكل منهما — تعذّر احتساب أي مقارنة أجور دون الاعتماد على عينات صغيرة جداً.'
                    )}
                  </StatusBanner>
                )}

                {pe.granularity_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Data granularity notes', 'ملاحظات دقة البيانات')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {pe.granularity_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {pe.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {pe.department_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{pe.governance_note}</p>
                  {pe.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {pe.sources.map((s, i) => <li key={i}>· {s}</li>)}
                      </ul>
                    </>
                  )}
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
