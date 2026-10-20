/**
 * Job Pattern Grouping & Market Research Export — Phase 19.
 *
 * Real analysis only: uploads a file to POST /api/local/job-pattern-grouping
 * (backend/core/job_pattern_grouping_engine.py) and renders whatever the
 * backend actually computed, then can export the same result to
 * POST /api/local/job-pattern-grouping/export for a downloadable .xlsx
 * worksheet.
 *
 * NON-NEGOTIABLE, stated up front on this page (not just in the export):
 * this tool does NOT search the internet, contact any job board, or call
 * any AI service itself — it only groups and summarizes the user's own
 * uploaded data, entirely on this machine. Zero data leaves the machine.
 * The exported worksheet is something the user takes to an external source
 * of their own choosing to research current market salary ranges.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Briefcase, RefreshCw, Users, Layers, Download, ShieldOff,
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

interface JobPattern {
  pattern_id: string
  job_title: string
  job_level: string | null
  department: string | null
  experience_bucket: string | null
  experience_range_label: string | null
  academic_qualification: string | null
  employee_count: number
  n_with_valid_salary: number
  avg_salary_sar: number | null
  median_salary_sar: number | null
  salary_min_sar: number | null
  salary_max_sar: number | null
  salary_suppressed: boolean
}

interface JobPatternGrouping {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  job_title_column: string | null
  job_level_column: string | null
  department_column: string | null
  experience_column: string | null
  salary_column: string | null
  academic_degree_column: string | null
  education_field_column: string | null
  grouping_dimensions_used: string[]
  n_employees_total: number
  n_employees_grouped: number
  n_patterns: number
  n_patterns_truncated: number
  patterns: JobPattern[]
  title_normalization_notes: string[]
  department_normalization_notes: string[]
  degree_normalization_notes: string[]
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
  data_quality_warnings?: string[]
  job_pattern_grouping: JobPatternGrouping
}

const UPLOAD_TIMEOUT_MS = 30_000

const COLUMN_LABELS_EN: Record<string, string> = {
  job_title: 'Job title (e.g. JobTitle, JobRole, Position)',
  job_level: 'Job level (optional — refines grouping)',
  department: 'Department (optional — refines grouping)',
  experience: 'Tenure / years of experience (optional — refines grouping)',
  salary: 'Salary / compensation (optional — enables salary columns)',
  academic_degree: 'Academic qualification (optional — e.g. Academic_degree, refines grouping)',
  education_field: 'Field of study / major (optional — combines with qualification when both present)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  job_title: 'المسمى الوظيفي (مثال: JobTitle أو JobRole)',
  job_level: 'المستوى الوظيفي (اختياري — يُحسّن التجميع)',
  department: 'القسم (اختياري — يُحسّن التجميع)',
  experience: 'سنوات الخبرة (اختياري — يُحسّن التجميع)',
  salary: 'الراتب / التعويض (اختياري — يُفعّل أعمدة الراتب)',
  academic_degree: 'المؤهل العلمي (اختياري — مثال: Academic_degree، يُحسّن التجميع)',
  education_field: 'التخصص الأكاديمي (اختياري — يُدمج مع المؤهل عند توفر كليهما)',
}

type SortKey = 'count' | 'salary' | 'title'

function sar(n: number): string {
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(1)}K`
  return `SAR ${n.toFixed(0)}`
}

export function JobPatternGroupingTracker() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<ApiResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const runUpload = useCallback(async (file: File) => {
    setStatus('loading')
    setError(null)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/local/job-pattern-grouping', {
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

  const handleExport = useCallback(async () => {
    if (!result?.job_pattern_grouping?.available) return
    setExporting(true)
    try {
      const res = await fetch('/api/local/job-pattern-grouping/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_pattern_grouping: result.job_pattern_grouping }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Export failed (${res.status})`)
      }
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'Job_Pattern_Market_Research_Worksheet.xlsx'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setExporting(false)
    }
  }, [result])

  const jp = result?.job_pattern_grouping
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []

  const { sorted: sortedPatterns, sortKey, setSortKey } = useSortableTable<JobPattern, SortKey>(
    jp?.patterns ?? [],
    {
      count: (a, b) => b.employee_count - a.employee_count,
      salary: (a, b) => (b.avg_salary_sar ?? -1) - (a.avg_salary_sar ?? -1),
      title: (a, b) => a.job_title.localeCompare(b.job_title),
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Job Pattern Grouping & Market Research Export', 'تجميع أنماط الوظائف وتصدير بحث السوق')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Groups your own employees into job patterns and exports a worksheet for you to research externally.',
            'يُجمّع موظفيك في أنماط وظيفية ويُصدّر ورقة عمل لتبحث عنها خارجياً.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        <div className="flex items-start gap-2">
          <ShieldOff size={16} className="flex-shrink-0 mt-0.5" />
          <span>
            {t(
              'This tool does NOT search the internet, contact any job board, or call any AI service itself — it only groups and summarizes your own uploaded data, entirely on this machine. Zero data leaves your machine. Take the exported worksheet to a source of your choosing (a recruiter, a job board, or an AI assistant) to research current market salary ranges yourself.',
              'لا تبحث هذه الأداة في الإنترنت، ولا تتصل بأي موقع وظائف، ولا تستدعي أي خدمة ذكاء اصطناعي بنفسها — فهي فقط تُجمّع وتُلخّص بياناتك المُحمّلة، بالكامل على هذا الجهاز. لا تغادر أي بيانات جهازك. خذ ورقة العمل المُصدَّرة إلى مصدر من اختيارك (مسؤول توظيف، أو موقع وظائف، أو مساعد ذكاء اصطناعي) لتبحث عن نطاقات الرواتب الحالية في السوق بنفسك.'
            )}
          </span>
        </div>
      </StatusBanner>

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with a job-title column (e.g. JobTitle or JobRole) to compute real job patterns. Job level, department, experience, and salary columns each independently refine the result when present — missing any of them, this page honestly says so instead of fabricating a pattern.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود مسمى وظيفي (مثال: JobTitle أو JobRole) لحساب أنماط وظيفية فعلية. تُحسّن أعمدة المستوى الوظيفي والقسم والخبرة والراتب النتيجة كل على حدة عند توفرها — في حال غياب أي منها، تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال نمط.'
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
            {t('Grouping job patterns…', 'جارٍ تجميع الأنماط الوظيفية…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && jp && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {result?.filename} · {result?.row_count?.toLocaleString()} {t('rows', 'صفوف')}
              </span>
              <div className="flex items-center gap-3">
                {jp.available && (
                  <button
                    onClick={handleExport}
                    disabled={exporting}
                    className="text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors"
                  >
                    {exporting ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                    {t('Download Market Research Worksheet', 'تحميل ورقة بحث السوق')}
                  </button>
                )}
                <button
                  onClick={reset}
                  className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1"
                >
                  <RefreshCw size={12} />
                  {t('Analyze another file', 'تحليل ملف آخر')}
                </button>
              </div>
            </div>

            {duplicateWarnings.length > 0 && (
              <StatusBanner tone="caution" compact>
                <ul className="space-y-0.5">
                  {duplicateWarnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </StatusBanner>
            )}

            {!jp.available ? (
              <EmptyState
                icon={Briefcase}
                title={t('Job pattern data not detected in this upload', 'لم يتم اكتشاف بيانات أنماط وظيفية في هذا الملف')}
                reason={jp.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={jp.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(jp.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                  <KPICard
                    label={t('Employees Grouped', 'الموظفون المُجمَّعون')}
                    value={jp.n_employees_grouped.toLocaleString()}
                    subtitle={t(`of ${jp.n_employees_total} total`, `من ${jp.n_employees_total} إجمالاً`)}
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                  />
                  <KPICard
                    label={t('Job Patterns', 'الأنماط الوظيفية')}
                    value={jp.n_patterns}
                    icon={Layers}
                    hero
                    animateValue
                    detail={t(
                      `Grouped using: ${jp.grouping_dimensions_used.join(', ')}.`,
                      `تم التجميع باستخدام: ${jp.grouping_dimensions_used.join('، ')}.`
                    )}
                  />
                  <KPICard
                    label={t('Salary Column', 'عمود الراتب')}
                    value={jp.salary_column ?? t('Not detected', 'غير مكتشف')}
                    icon={Briefcase}
                    iconColor="text-emerald-500"
                    iconBg="bg-emerald-500/10"
                    detail={t('Patterns with under 3 employees have salary figures suppressed.', 'الأنماط التي تضم أقل من 3 موظفين تُخفى فيها أرقام الراتب.')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? jp.narrative_ar : jp.narrative_en}
                  </p>
                </div>

                {jp.patterns.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Employee Count by Job Pattern', 'عدد الموظفين حسب النمط الوظيفي')}</p>
                    <DepartmentBarChart
                      data={jp.patterns.map(p => ({ department: p.job_title, value: p.employee_count }))}
                    />
                  </div>
                )}

                {jp.patterns.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<SortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'count', label: t('Count', 'العدد') },
                          { key: 'salary', label: t('Avg Salary', 'متوسط الراتب') },
                          { key: 'title', label: t('Title', 'المسمى') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Job Title', 'المسمى الوظيفي')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Qualification', 'المؤهل')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Experience', 'الخبرة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Count', 'العدد')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Salary', 'متوسط الراتب')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedPatterns.map((p) => (
                          <tr key={p.pattern_id} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 align-top">
                            <td className="px-4 py-2.5">
                              <div className="font-medium text-slate-700 dark:text-slate-300">{p.job_title}</div>
                              {p.job_level && <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">{p.job_level}</div>}
                            </td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{p.department ?? '—'}</td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{p.academic_qualification ?? '—'}</td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{p.experience_range_label ?? '—'}</td>
                            <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">
                              {p.employee_count}
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                              {p.salary_suppressed ? (
                                <StatusBadge tone="neutral">{t('Suppressed (n<3)', 'مخفي (n<3)')}</StatusBadge>
                              ) : p.avg_salary_sar != null ? (
                                sar(p.avg_salary_sar)
                              ) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {jp.n_patterns_truncated > 0 && (
                  <StatusBanner tone="informational" compact>
                    {t(
                      `${jp.n_patterns_truncated} additional smaller pattern(s) not shown on screen — the full list is included in the exported worksheet.`,
                      `${jp.n_patterns_truncated} نمطاً إضافياً أصغر لم يُعرض على الشاشة — القائمة الكاملة مضمّنة في ورقة العمل المُصدَّرة.`
                    )}
                  </StatusBanner>
                )}

                {jp.title_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Job titles normalized', 'تم توحيد المسميات الوظيفية')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {jp.title_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {jp.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {jp.department_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {jp.degree_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Academic qualifications normalized', 'تم توحيد المؤهلات العلمية')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {jp.degree_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{jp.governance_note}</p>
                  {jp.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {jp.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
