/**
 * Recruitment Pipeline Status Tracker — Phase 5.
 *
 * Real analysis only: uploads a file to POST /api/local/recruitment-pipeline
 * (backend/core/recruitment_pipeline_engine.py) and renders whatever the
 * backend actually computed. This platform's other modules are all
 * retention/attrition-focused (who might LEAVE) — this page covers hiring
 * (who is being brought IN), a genuinely new domain. Most datasets used
 * elsewhere on this platform are structured HR *employee* data with no
 * candidate/hiring-stage columns at all, so this page will usually show the
 * honest "not detected" state below — never a fabricated funnel.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Users, TrendingDown, CheckCircle2, RefreshCw, AlertTriangle,
  Clock, Building2, Radio,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { RecruitmentFunnelChart } from '../components/shared/RecruitmentFunnelChart'
import { SortToggle } from '../components/shared/SortToggle'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { useSortableTable } from '../hooks/useSortableTable'
import { semantic } from '../styles/design-tokens'

interface StageFunnelCount {
  stage: string
  n_candidates: number
  pct_of_total: number
  conversion_from_previous_pct: number | null
}

interface DepartmentPipelineBreakdown {
  department: string
  n_candidates: number
  n_hired: number
  hire_rate_pct: number
}

interface SourceChannelBreakdown {
  source: string
  n_candidates: number
  n_hired: number
  hire_rate_pct: number
}

interface RejectionThemeFrequency {
  construct: string
  n_responses_mentioned: number
  pct_of_responses: number
}

interface RejectionReasonThemes {
  available: boolean
  n_responses_analyzed: number
  theme_frequencies: RejectionThemeFrequency[]
  top_terms: { term: string; n_responses: number }[]
}

interface RecruitmentPipeline {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_candidates_total: number
  current_stage_distribution: StageFunnelCount[]
  department_breakdown: DepartmentPipelineBreakdown[]
  source_breakdown: SourceChannelBreakdown[]
  biggest_dropoff_stage: string | null
  n_rejected: number
  rejection_rate_pct: number | null
  avg_time_to_hire_days: number | null
  n_time_to_hire_computed: number
  invalid_date_sequences_excluded: number
  date_quality_warnings: string[]
  department_normalization_notes: string[]
  stage_normalization_notes: string[]
  rejection_reason_themes: RejectionReasonThemes | null
  cost_per_hire_sar: number | null
  cost_per_hire_confidence: 'observed' | 'uncalibrated_generic_estimate' | null
  narrative_en: string
  narrative_ar: string
  governance_note: string
  sources: string[]
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  recruitment_pipeline: RecruitmentPipeline
}

const COLUMN_LABELS_EN: Record<string, string> = {
  candidate_id: 'Candidate/applicant ID',
  stage: 'Pipeline stage (Applied/Screening/Interview/Offer/Hired/Rejected)',
  application_date: 'Application date',
  offer_date: 'Offer date',
  hire_date: 'Hire/start date',
  rejection_date: 'Rejection date',
  source: 'Source/channel',
  rejection_reason: 'Rejection reason',
  department_or_role: 'Department/role applied for',
  recruitment_cost: 'Recruitment cost / cost per hire',
}

const COLUMN_LABELS_AR: Record<string, string> = {
  candidate_id: 'معرّف المرشح',
  stage: 'مرحلة المسار (تقديم/فرز/مقابلة/عرض/تعيين/رفض)',
  application_date: 'تاريخ التقديم',
  offer_date: 'تاريخ العرض',
  hire_date: 'تاريخ التوظيف',
  rejection_date: 'تاريخ الرفض',
  source: 'المصدر/القناة',
  rejection_reason: 'سبب الرفض',
  department_or_role: 'القسم/الوظيفة المتقدم لها',
  recruitment_cost: 'تكلفة التوظيف',
}

const UPLOAD_TIMEOUT_MS = 30_000

type FunnelSortKey = 'candidates' | 'pct' | 'conversion'
type DeptSortKey = 'department' | 'candidates' | 'hired' | 'rate'
type SourceSortKey = 'source' | 'candidates' | 'hired' | 'rate'

function sar(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `SAR ${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(0)}K`
  return `SAR ${n.toFixed(0)}`
}

export function RecruitmentPipelineTracker() {
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

      const response = await fetch('/api/local/recruitment-pipeline', {
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

  const rp = result?.recruitment_pipeline
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []
  const [hoveredStage, setHoveredStage] = useState<string | null>(null)

  // Phase 14 — all three hooks are called unconditionally every render
  // (Rules of Hooks); each just receives an empty array before a dataset
  // is loaded, which useSortableTable's own useMemo handles fine.
  const { sorted: sortedStages, sortKey: stageSortKey, setSortKey: setStageSortKey } = useSortableTable<StageFunnelCount, FunnelSortKey>(
    rp?.current_stage_distribution ?? [],
    {
      candidates: (a, b) => b.n_candidates - a.n_candidates,
      pct: (a, b) => b.pct_of_total - a.pct_of_total,
      conversion: (a, b) => (b.conversion_from_previous_pct ?? -1) - (a.conversion_from_previous_pct ?? -1),
    },
  )
  const { sorted: sortedDepartments, sortKey: deptSortKey, setSortKey: setDeptSortKey } = useSortableTable<DepartmentPipelineBreakdown, DeptSortKey>(
    rp?.department_breakdown ?? [],
    {
      department: (a, b) => a.department.localeCompare(b.department),
      candidates: (a, b) => b.n_candidates - a.n_candidates,
      hired: (a, b) => b.n_hired - a.n_hired,
      rate: (a, b) => b.hire_rate_pct - a.hire_rate_pct,
    },
  )
  const { sorted: sortedSources, sortKey: sourceSortKey, setSortKey: setSourceSortKey } = useSortableTable<SourceChannelBreakdown, SourceSortKey>(
    rp?.source_breakdown ?? [],
    {
      source: (a, b) => a.source.localeCompare(b.source),
      candidates: (a, b) => b.n_candidates - a.n_candidates,
      hired: (a, b) => b.n_hired - a.n_hired,
      rate: (a, b) => b.hire_rate_pct - a.hire_rate_pct,
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Recruitment Pipeline Status Tracker', 'متتبع حالة مسار التوظيف')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Real hiring-funnel analysis — who is being brought in, not who might leave.',
            'تحليل مسار التوظيف الفعلي — من يتم استقطابهم، وليس من قد يغادر.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a dataset with candidate/applicant records (a pipeline-stage column at minimum) to compute a real hiring funnel. Most HR employee exports have no recruitment columns at all — this page honestly says so instead of fabricating a funnel.',
          'حمّل بيانات مرشحين/متقدمين (عمود مرحلة المسار كحد أدنى) لحساب مسار توظيف فعلي. معظم بيانات الموظفين لا تحتوي على أعمدة توظيف إطلاقاً — تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال مسار وهمي.'
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
            {t('Analyzing recruitment pipeline…', 'جارٍ تحليل مسار التوظيف…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && rp && (
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

            {/* Duplicate-row disclosure — same pipeline-level dedup as every
                other module (see PHASE_4_CORRECTIONS_REPORT.md §2). */}
            {duplicateWarnings.length > 0 && (
              <StatusBanner tone="caution" compact>
                <ul className="space-y-0.5">
                  {duplicateWarnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </StatusBanner>
            )}

            {!rp.available ? (
              <EmptyState
                icon={AlertTriangle}
                title={t('Recruitment pipeline data not detected in this upload', 'لم يتم اكتشاف بيانات مسار التوظيف في هذا الملف')}
                reason={rp.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={rp.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(rp.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Total Candidates', 'إجمالي المرشحين')}
                    value={rp.n_candidates_total.toLocaleString()}
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `Spread across ${rp.department_breakdown.length} department(s) and ${rp.source_breakdown.length} source(s).`,
                      `موزعون على ${rp.department_breakdown.length} قسم و ${rp.source_breakdown.length} مصدر.`
                    )}
                  />
                  <KPICard
                    label={t('Hired', 'تم التعيين')}
                    value={(rp.current_stage_distribution.find(s => s.stage === 'Hired')?.n_candidates ?? 0).toLocaleString()}
                    subtitle={`${rp.current_stage_distribution.find(s => s.stage === 'Hired')?.pct_of_total.toFixed(0) ?? 0}% ${t('of total', 'من الإجمالي')}`}
                    icon={CheckCircle2}
                    hero
                    animateValue
                    radialPct={rp.current_stage_distribution.find(s => s.stage === 'Hired')?.pct_of_total}
                    radialColor={semantic.stable}
                    detail={rp.cost_per_hire_sar != null
                      ? t(`Cost per hire: ${sar(rp.cost_per_hire_sar)} (${rp.cost_per_hire_confidence === 'observed' ? 'observed' : 'estimated'}).`, `تكلفة التوظيف: ${sar(rp.cost_per_hire_sar)} (${rp.cost_per_hire_confidence === 'observed' ? 'ملاحظ' : 'تقديري'}).`)
                      : t('Cost-per-hire data not available in this dataset.', 'بيانات تكلفة التوظيف غير متوفرة في هذه البيانات.')}
                  />
                  <KPICard
                    label={t('Biggest Drop-off', 'أكبر تسرّب')}
                    value={rp.biggest_dropoff_stage ?? '—'}
                    icon={TrendingDown}
                    iconColor="text-red-500"
                    iconBg="bg-red-500/10"
                    detail={(() => {
                      const s = rp.current_stage_distribution.find(x => x.stage === rp.biggest_dropoff_stage)
                      return s?.conversion_from_previous_pct != null
                        ? t(`Only ${s.conversion_from_previous_pct.toFixed(0)}% converted from the previous stage.`, `تحوّل ${s.conversion_from_previous_pct.toFixed(0)}% فقط من المرحلة السابقة.`)
                        : t('Conversion rate not computable for this stage.', 'معدل التحويل غير قابل للحساب لهذه المرحلة.')
                    })()}
                  />
                  <KPICard
                    label={t('Avg Time to Hire', 'متوسط زمن التوظيف')}
                    value={rp.avg_time_to_hire_days != null ? `${rp.avg_time_to_hire_days.toFixed(0)}d` : '—'}
                    subtitle={rp.avg_time_to_hire_days != null ? `${rp.n_time_to_hire_computed} ${t('hires', 'تعيينات')}` : undefined}
                    icon={Clock}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    detail={rp.invalid_date_sequences_excluded > 0
                      ? t(`${rp.invalid_date_sequences_excluded} record(s) excluded for invalid date sequences.`, `تم استبعاد ${rp.invalid_date_sequences_excluded} سجل بسبب تسلسل تواريخ غير صالح.`)
                      : t('All date sequences in this dataset were valid.', 'جميع تسلسلات التواريخ في هذه البيانات كانت صالحة.')}
                  />
                </div>

                {/* Date-quality disclosure — invalid hire/rejection-before-
                    application sequences excluded, never silently negative. */}
                {rp.date_quality_warnings.length > 0 && (
                  <StatusBanner tone="caution" compact>
                    <ul className="space-y-0.5">
                      {rp.date_quality_warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Cost per hire — reuses financial_intelligence_engine.py,
                    never a new formula (see module docstring). */}
                {rp.cost_per_hire_sar != null && (
                  <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-lg">
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wide font-semibold">
                      {t('Cost Per Hire', 'تكلفة التوظيف')}
                    </span>
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{sar(rp.cost_per_hire_sar)}</span>
                    <span className={`text-xs font-semibold ${rp.cost_per_hire_confidence === 'observed' ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}`}>
                      {rp.cost_per_hire_confidence === 'observed'
                        ? t('Observed (from your data)', 'ملاحظ (من بياناتك)')
                        : t('Uncalibrated generic estimate', 'تقدير عام غير معاير')}
                    </span>
                  </div>
                )}

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? rp.narrative_ar : rp.narrative_en}
                  </p>
                </div>

                {/* Funnel visualization — the canonical case for a real
                    funnel chart over a table: the narrowing shape makes
                    stage-by-stage drop-off immediately legible. */}
                <div className="card p-5">
                  <p className="section-title mb-2">
                    {t('Hiring Funnel', 'مسار التوظيف')}
                  </p>
                  <RecruitmentFunnelChart
                    data={rp.current_stage_distribution.map(s => ({
                      stage: s.stage,
                      candidates: s.n_candidates,
                      pctOfTotal: s.pct_of_total,
                    }))}
                    highlightedKey={hoveredStage}
                    onHoverChange={setHoveredStage}
                  />
                </div>

                {/* Funnel table — live client-side sort (useSortableTable);
                    default order preserves the natural stage sequence.
                    Rows cross-highlight with the funnel chart above via
                    shared hoveredStage state. */}
                <div className="card overflow-x-auto">
                  <div className="flex items-center justify-end px-4 pt-3">
                    <SortToggle<FunnelSortKey>
                      label={t('Sort:', 'ترتيب:')}
                      active={stageSortKey}
                      onChange={setStageSortKey}
                      options={[
                        { key: 'candidates', label: t('Candidates', 'المرشحون') },
                        { key: 'pct', label: t('% of Total', '% من الإجمالي') },
                        { key: 'conversion', label: t('Conversion', 'التحويل') },
                      ]}
                    />
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                          {t('Stage', 'المرحلة')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('Candidates', 'المرشحون')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('% of Total', '% من الإجمالي')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('Conversion', 'التحويل')}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedStages.map((s) => (
                        <tr
                          key={s.stage}
                          onMouseEnter={() => setHoveredStage(s.stage)}
                          onMouseLeave={() => setHoveredStage(null)}
                          className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${
                            s.stage === rp.biggest_dropoff_stage ? 'bg-red-50/50 dark:bg-red-950/10' : ''
                          } ${hoveredStage === s.stage ? 'bg-slate-50 dark:bg-navy-800/40' : ''}`}
                        >
                          <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                            {s.stage}
                            {s.stage === rp.biggest_dropoff_stage && (
                              <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                                {t('biggest drop-off', 'أكبر تسرّب')}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{s.n_candidates}</td>
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{s.pct_of_total.toFixed(1)}%</td>
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">
                            {s.conversion_from_previous_pct != null ? `${s.conversion_from_previous_pct.toFixed(1)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                      <tr className="bg-slate-50 dark:bg-slate-800/40">
                        <td className="px-4 py-2.5 font-medium text-slate-500 dark:text-slate-400">{t('Rejected', 'مرفوض')}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-slate-500 dark:text-slate-400">{rp.n_rejected}</td>
                        <td className="px-4 py-2.5 text-right text-slate-500 dark:text-slate-400">
                          {rp.rejection_rate_pct != null ? `${rp.rejection_rate_pct.toFixed(1)}%` : '—'}
                        </td>
                        <td className="px-4 py-2.5" />
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Stage name normalization disclosure */}
                {rp.stage_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Pipeline stage names normalized', 'تم توحيد أسماء مراحل المسار')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {rp.stage_normalization_notes.map((note, i) => <li key={i}>· {note}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Department breakdown */}
                {rp.department_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-between px-4 pt-4 flex-wrap gap-2">
                      <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Building2 size={13} /> {t('By Department / Role', 'حسب القسم / الوظيفة')}
                      </p>
                      <SortToggle<DeptSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={deptSortKey}
                        onChange={setDeptSortKey}
                        options={[
                          { key: 'candidates', label: t('Candidates', 'المرشحون') },
                          { key: 'hired', label: t('Hired', 'تم التعيين') },
                          { key: 'rate', label: t('Rate', 'المعدل') },
                          { key: 'department', label: t('Name', 'الاسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm mt-2">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Candidates', 'المرشحون')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Hired', 'تم التعيين')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Hire Rate', 'معدل التعيين')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedDepartments.map((d) => (
                          <tr key={d.department} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{d.department}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_candidates}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_hired}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{d.hire_rate_pct.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Department name normalization disclosure */}
                {rp.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {rp.department_normalization_notes.map((note, i) => <li key={i}>· {note}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Source/channel breakdown */}
                {rp.source_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-between px-4 pt-4 flex-wrap gap-2">
                      <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Radio size={13} /> {t('By Source / Channel', 'حسب المصدر / القناة')}
                      </p>
                      <SortToggle<SourceSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sourceSortKey}
                        onChange={setSourceSortKey}
                        options={[
                          { key: 'candidates', label: t('Candidates', 'المرشحون') },
                          { key: 'hired', label: t('Hired', 'تم التعيين') },
                          { key: 'rate', label: t('Rate', 'المعدل') },
                          { key: 'source', label: t('Name', 'الاسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm mt-2">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Source', 'المصدر')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Candidates', 'المرشحون')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Hired', 'تم التعيين')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Hire Rate', 'معدل التعيين')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedSources.map((s) => (
                          <tr key={s.source} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{s.source}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{s.n_candidates}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{s.n_hired}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{s.hire_rate_pct.toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Rejection-reason themes — reuses exit_interview_intelligence_engine.py */}
                {rp.rejection_reason_themes?.available && (
                  <div className="card p-4">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-3">
                      {t('Rejection-Reason Themes', 'مواضيع أسباب الرفض')}
                      <span className="ml-2 font-normal normal-case text-slate-400">
                        ({rp.rejection_reason_themes.n_responses_analyzed} {t('responses analyzed', 'استجابة تم تحليلها')})
                      </span>
                    </p>
                    {rp.rejection_reason_themes.theme_frequencies.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {rp.rejection_reason_themes.theme_frequencies.map((th) => (
                          <span key={th.construct} className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                            {th.construct} <span className="text-slate-400 dark:text-slate-500">({th.n_responses_mentioned})</span>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 dark:text-slate-500">
                        {t('No recognised theme was mentioned by enough respondents.', 'لم يُذكر أي موضوع معروف من قبل عدد كافٍ من المستجيبين.')}
                      </p>
                    )}
                  </div>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{rp.governance_note}</p>
                  {rp.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {rp.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
