/**
 * Succession Planning / Internal Mobility Readiness — Phase 8.
 *
 * Real analysis only: uploads a file to POST /api/local/succession-readiness
 * (backend/core/succession_readiness_engine.py) and renders whatever the
 * backend actually computed.
 *
 * NON-NEGOTIABLE: this page NEVER claims to be a validated psychometric or
 * vendor-benchmarked succession-planning instrument. The inputs (performance
 * rating, tenure) are real data from the upload, but the formula combining
 * them into a single readiness score is this platform's own constructed
 * heuristic — every result renders a persistent "constructed heuristic, not
 * a validated instrument" banner, unconditionally, whenever any readiness
 * figure is shown. See succession_readiness_engine.py's module docstring
 * for why the dead, uncomputable CareerProgression/TenureRatio constructs
 * were not reused (SUCCESSION_READINESS_INVESTIGATION.md).
 */
import { Fragment, useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, TrendingUp, RefreshCw, AlertTriangle, Users,
  Award, Flag, ChevronDown,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { EmptyState } from '../components/shared/EmptyState'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { SortToggle } from '../components/shared/SortToggle'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { LatinText } from '../components/shared/LatinText'
import { useSortableTable } from '../hooks/useSortableTable'
import { useEmployeeSearch } from '../hooks/useEmployeeSearch'
import { EmployeeSearchInput } from '../components/shared/EmployeeSearchInput'
import { readinessTierColor, motion as motionTokens } from '../styles/design-tokens'

interface ReadinessCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  performance_percentile: number
  tenure_years: number
  readiness_score: number
  readiness_tier: string
  is_stuck_high_performer: boolean
  high_readiness_low_fairness_flag: boolean
}

interface DepartmentReadinessBreakdown {
  department: string
  n_total: number
  n_high_readiness: number
  avg_readiness_score: number
}

interface SuccessionReadiness {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_total: number
  n_high_readiness: number
  n_stuck_high_performers: number
  n_high_readiness_low_fairness: number
  avg_readiness_score: number | null
  top_candidates: ReadinessCandidate[]
  high_readiness_record_ids: string[]
  department_breakdown: DepartmentReadinessBreakdown[]
  department_normalization_notes: string[]
  formula_description_en: string
  formula_description_ar: string
  is_validated_instrument: boolean
  calculation_confidence: string
  narrative_en: string
  narrative_ar: string
  governance_note: string
  disclaimer_en: string
  disclaimer_ar: string
  sources: string[]
}

interface SaudiPipelineCrossLink {
  available: boolean
  reason?: string
  n_high_readiness_saudi?: number
  n_high_readiness_total?: number
  narrative_en?: string
  narrative_ar?: string
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  succession_readiness: SuccessionReadiness
  saudi_pipeline_cross_link?: SaudiPipelineCrossLink
}

const COLUMN_LABELS_EN: Record<string, string> = {
  performance_rating: 'Performance rating (e.g. PerformanceRating)',
  tenure_years: 'Tenure / years at company (e.g. YearsAtCompany)',
  job_level: "Job level / career grade (optional — enables the 'stuck high performer' signal)",
  promotion_fairness: 'Promotion fairness/justice perception (optional — enables the readiness + low-fairness cross-reference)',
  department_or_sector: 'Department (optional, for a per-department breakdown)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  performance_rating: 'تقييم الأداء (مثال: PerformanceRating)',
  tenure_years: 'مدة الخدمة / سنوات العمل (مثال: YearsAtCompany)',
  job_level: 'المستوى الوظيفي (اختياري — يفعّل مؤشر "التوقف عند مستوى وظيفي")',
  promotion_fairness: 'إدراك عدالة الترقية (اختياري — يفعّل مقارنة الجاهزية مع تدني إدراك العدالة)',
  department_or_sector: 'القسم (اختياري، لعرض تفصيلي حسب القسم)',
}

const TIER_BADGE: Record<string, string> = {
  'High Readiness': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  'Emerging Readiness': 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  Developing: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

const UPLOAD_TIMEOUT_MS = 30_000

type CandidateSortKey = 'readiness' | 'tenure' | 'department'
type DeptSortKey = 'name' | 'total' | 'highReadiness' | 'avgScore'

export function SuccessionReadinessTracker() {
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

      const response = await fetch('/api/local/succession-readiness', {
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

  const sr = result?.succession_readiness
  const crossLink = result?.saudi_pipeline_cross_link
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []
  const [expandedCandidate, setExpandedCandidate] = useState<string | null>(null)
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)

  // Phase 14 — both hooks called unconditionally every render (Rules of
  // Hooks); each receives an empty array before a dataset is loaded.
  const { sorted: sortedCandidates, sortKey: candidateSortKey, setSortKey: setCandidateSortKey } = useSortableTable<ReadinessCandidate, CandidateSortKey>(
    sr?.top_candidates ?? [],
    {
      readiness: (a, b) => b.readiness_score - a.readiness_score,
      tenure: (a, b) => b.tenure_years - a.tenure_years,
      department: (a, b) => (a.department ?? '').localeCompare(b.department ?? ''),
    },
  )
  const { query: candidateSearchQuery, setQuery: setCandidateSearchQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    sortedCandidates,
    useCallback((c: ReadinessCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )
  const { sorted: sortedDepartments, sortKey: deptSortKey, setSortKey: setDeptSortKey } = useSortableTable<DepartmentReadinessBreakdown, DeptSortKey>(
    sr?.department_breakdown ?? [],
    {
      name: (a, b) => a.department.localeCompare(b.department),
      total: (a, b) => b.n_total - a.n_total,
      highReadiness: (a, b) => b.n_high_readiness - a.n_high_readiness,
      avgScore: (a, b) => b.avg_readiness_score - a.avg_readiness_score,
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Succession / Internal Mobility Readiness', 'جاهزية التعاقب الوظيفي / التنقل الداخلي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Constructed-heuristic readiness score from real performance and tenure data — a discussion starting point, not a validated instrument.',
            'درجة جاهزية إرشادية من بيانات أداء ومدة خدمة حقيقية — نقطة انطلاق للنقاش، وليست أداة معتمدة.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      {/* Persistent, unconditional constructed-heuristic banner. Phase 15:
          moved from `caution`(amber)/ShieldAlert to `informational` — same
          reasoning as Nitaqat's equivalent banner: this disclosure is
          ALWAYS shown regardless of findings, so it must read as quiet
          methodology context rather than competing visually with genuine
          situational risk flags. Text unchanged word-for-word. */}
      <StatusBanner tone="informational">
        <span className="font-medium">
          {t(
            'Constructed heuristic — NOT a validated psychometric or vendor-benchmarked succession-planning instrument. The inputs (performance rating, tenure) are real data from your upload, but the formula combining them into a single readiness score is this platform\'s own construction. Use as a discussion starting point for HR/talent review, never as the sole basis for promotion or succession decisions.',
            'أداة إرشادية من تصميم هذه المنصة — وليست أداة نفسية معتمدة أو مقاسة مقابل معيار صناعي. المدخلات (تقييم الأداء، مدة الخدمة) بيانات حقيقية، لكن صيغة دمجها في درجة واحدة هي بناء داخلي لهذه المنصة. تُستخدم كنقطة انطلاق للنقاش، وليست الأساس الوحيد لأي قرار ترقية.'
          )}
        </span>
      </StatusBanner>

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with a performance-rating and a tenure column to compute a readiness estimate. If both are missing, this page honestly says so instead of fabricating a score.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود تقييم الأداء وعمود مدة الخدمة لحساب تقدير الجاهزية. إذا كان أي منهما مفقوداً، تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال درجة.'
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
            {t('Estimating succession readiness…', 'جارٍ تقدير جاهزية التعاقب الوظيفي…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && sr && (
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

            {!sr.available ? (
              <EmptyState
                icon={TrendingUp}
                title={t('Performance/tenure data not detected in this upload', 'لم يتم اكتشاف بيانات الأداء/مدة الخدمة في هذا الملف')}
                reason={sr.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={sr.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(sr.columns_detected).map(k => [k, COLUMN_LABELS_EN[k] ? t(COLUMN_LABELS_EN[k], COLUMN_LABELS_AR[k]) : k])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Employees Evaluated', 'الموظفون المُقيَّمون')}
                    value={sr.n_total.toLocaleString()}
                    // Phase 15: was TrendingUp (a growth/trend icon) on a
                    // plain headcount metric with no trend meaning —
                    // confirmed via screenshot review as the exact "icon
                    // doesn't match content" problem. Users is the fixed
                    // headcount icon used platform-wide (Recruitment's
                    // Total Candidates, Nitaqat's Total Classified).
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `Spread across ${sr.department_breakdown.length} department(s).`,
                      `موزعون على ${sr.department_breakdown.length} قسم.`
                    )}
                  />
                  <KPICard
                    label={t('High Readiness', 'جاهزية عالية')}
                    value={sr.n_high_readiness.toLocaleString()}
                    subtitle={sr.avg_readiness_score != null ? `${t('avg score', 'متوسط الدرجة')}: ${sr.avg_readiness_score.toFixed(1)}` : undefined}
                    icon={Award}
                    hero
                    animateValue
                    radialPct={sr.n_total > 0 ? (100 * sr.n_high_readiness / sr.n_total) : undefined}
                    radialColor={readinessTierColor['High Readiness']}
                    detail={t('Constructed heuristic from performance + tenure — not a validated instrument.', 'أداة إرشادية من الأداء ومدة الخدمة — وليست أداة معتمدة.')}
                  />
                  <KPICard
                    label={t('Stuck High Performers', 'أداء عالٍ متوقف عند مستواه')}
                    value={sr.columns_detected.job_level ? sr.n_stuck_high_performers.toLocaleString() : '—'}
                    subtitle={!sr.columns_detected.job_level ? t('needs JobLevel', 'يتطلب المستوى الوظيفي') : undefined}
                    icon={AlertTriangle}
                    iconColor="text-amber-500"
                    iconBg="bg-amber-500/10"
                    animateValue
                    detail={sr.columns_detected.job_level
                      ? t('High performance percentile with no job-level advancement.', 'أداء مرتفع دون تقدم في المستوى الوظيفي.')
                      : t('Add a job-level column to enable this signal.', 'أضف عمود المستوى الوظيفي لتفعيل هذا المؤشر.')}
                  />
                  <KPICard
                    label={t('High Readiness + Low Fairness', 'جاهزية عالية + عدالة متدنية')}
                    value={sr.columns_detected.promotion_fairness ? sr.n_high_readiness_low_fairness.toLocaleString() : '—'}
                    subtitle={!sr.columns_detected.promotion_fairness ? t('needs PromotionFairness', 'يتطلب عمود عدالة الترقية') : undefined}
                    icon={Flag}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    animateValue
                    detail={sr.columns_detected.promotion_fairness
                      ? t('High readiness candidates who also perceive promotion as unfair — a retention risk.', 'مرشحون بجاهزية عالية يدركون الترقية كغير عادلة — مخاطرة استبقاء.')
                      : t('Add a promotion-fairness column to enable this signal.', 'أضف عمود عدالة الترقية لتفعيل هذا المؤشر.')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? sr.narrative_ar : sr.narrative_en}
                  </p>
                </div>

                {crossLink && (
                  <div className={`p-4 rounded-xl border ${crossLink.available ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/40' : 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <Flag size={14} className={crossLink.available ? 'text-emerald-500' : 'text-slate-400'} />
                      <p className={`text-xs font-semibold ${crossLink.available ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'}`}>
                        {t('Nitaqat Saudi Leadership Pipeline Cross-Link', 'الربط مع خط القيادة السعودي (نطاقات)')}
                      </p>
                    </div>
                    {crossLink.available ? (
                      <p className="text-xs text-emerald-700 dark:text-emerald-400">{isAr ? crossLink.narrative_ar : crossLink.narrative_en}</p>
                    ) : (
                      <p className="text-xs text-slate-500 dark:text-slate-400">{crossLink.reason}</p>
                    )}
                  </div>
                )}

                {sr.top_candidates.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-between px-4 pt-3 flex-wrap gap-2">
                      <EmployeeSearchInput
                        value={candidateSearchQuery}
                        onChange={setCandidateSearchQuery}
                        placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
                        resultCount={filteredCandidates.length}
                        totalCount={sortedCandidates.length}
                      />
                      <SortToggle<CandidateSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={candidateSortKey}
                        onChange={setCandidateSortKey}
                        options={[
                          { key: 'readiness', label: t('Score', 'الدرجة') },
                          { key: 'tenure', label: t('Tenure', 'مدة الخدمة') },
                          { key: 'department', label: t('Department', 'القسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee', 'الموظف')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Tenure (yrs)', 'مدة الخدمة (سنوات)')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Readiness Score', 'درجة الجاهزية')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Tier', 'المستوى')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Flags', 'مؤشرات')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCandidates.length === 0 && (
                          <tr><td colSpan={6} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
                        )}
                        {filteredCandidates.map((c) => {
                          const isExpanded = expandedCandidate === c.record_id_safe
                          const hasSignals = c.is_stuck_high_performer || c.high_readiness_low_fairness_flag
                          return (
                            <Fragment key={c.record_id_safe}>
                              <tr
                                onClick={() => setExpandedCandidate(isExpanded ? null : c.record_id_safe)}
                                className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 cursor-pointer"
                              >
                                <td className="px-4 py-2.5 font-mono text-xs text-slate-600 dark:text-slate-400">
                                  <span className="inline-flex items-center gap-1.5">
                                    <ChevronDown
                                      size={12}
                                      className={`text-slate-400 transition-transform duration-base ease-executive ${isExpanded ? 'rotate-180' : ''}`}
                                    />
                                    <LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText>
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                                <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{c.tenure_years.toFixed(1)}</td>
                                <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{c.readiness_score.toFixed(1)}</td>
                                <td className="px-4 py-2.5 text-center">
                                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${TIER_BADGE[c.readiness_tier] ?? 'bg-slate-100 text-slate-600'}`}>
                                    {c.readiness_tier}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-center space-x-1">
                                  {c.is_stuck_high_performer && (
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                                      {t('Stuck', 'متوقف')}
                                    </span>
                                  )}
                                  {c.high_readiness_low_fairness_flag && (
                                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
                                      {t('Low Fairness', 'عدالة متدنية')}
                                    </span>
                                  )}
                                </td>
                              </tr>
                              <AnimatePresence>
                                {isExpanded && (
                                  <motion.tr
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: motionTokens.base, ease: motionTokens.easeExecutive }}
                                    className="border-b border-slate-100 dark:border-slate-800 last:border-0"
                                  >
                                    <td colSpan={6} className="px-4 pb-3 pt-0 bg-slate-50/70 dark:bg-navy-800/30">
                                      {hasSignals ? (
                                        <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1 ps-5">
                                          {c.is_stuck_high_performer && (
                                            <li>
                                              <span className="font-semibold text-amber-700 dark:text-amber-400">{t('Stuck signal', 'مؤشر التوقف')}:</span>{' '}
                                              {t('high performance percentile with no job-level advancement.', 'أداء مرتفع دون تقدم في المستوى الوظيفي.')}
                                            </li>
                                          )}
                                          {c.high_readiness_low_fairness_flag && (
                                            <li>
                                              <span className="font-semibold text-purple-700 dark:text-purple-400">{t('Low fairness signal', 'مؤشر تدني العدالة')}:</span>{' '}
                                              {t('high readiness score combined with low promotion-fairness perception.', 'درجة جاهزية عالية مع إدراك متدنٍ لعدالة الترقية.')}
                                            </li>
                                          )}
                                        </ul>
                                      ) : (
                                        <p className="text-xs text-slate-400 dark:text-slate-500 ps-5">
                                          {t('No stuck-performer or low-fairness signal detected for this candidate.', 'لم يتم رصد مؤشر توقف أو تدني عدالة لهذا المرشح.')}
                                        </p>
                                      )}
                                    </td>
                                  </motion.tr>
                                )}
                              </AnimatePresence>
                            </Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {sr.department_breakdown.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">
                      {t('Average Readiness Score by Department', 'متوسط درجة الجاهزية حسب القسم')}
                    </p>
                    <DepartmentBarChart
                      data={sr.department_breakdown.map(d => ({
                        department: d.department,
                        value: d.avg_readiness_score,
                        color: d.avg_readiness_score >= 70 ? readinessTierColor['High Readiness']
                          : d.avg_readiness_score >= 40 ? readinessTierColor['Emerging Readiness']
                          : readinessTierColor['Developing'],
                        tooltipExtra: { [t('Total', 'الإجمالي')]: d.n_total, [t('High Readiness', 'جاهزية عالية')]: d.n_high_readiness },
                      }))}
                      valueFormatter={(v) => v.toFixed(1)}
                      highlightedKey={hoveredDept}
                      onHoverChange={setHoveredDept}
                    />
                  </div>
                )}

                {sr.department_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<DeptSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={deptSortKey}
                        onChange={setDeptSortKey}
                        options={[
                          { key: 'avgScore', label: t('Score', 'الدرجة') },
                          { key: 'highReadiness', label: t('High Readiness', 'جاهزية عالية') },
                          { key: 'total', label: t('Total', 'الإجمالي') },
                          { key: 'name', label: t('Name', 'الاسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Total', 'الإجمالي')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('High Readiness', 'جاهزية عالية')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Avg Score', 'متوسط الدرجة')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedDepartments.map((d) => (
                          <tr
                            key={d.department}
                            onMouseEnter={() => setHoveredDept(d.department)}
                            onMouseLeave={() => setHoveredDept(null)}
                            className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${
                              hoveredDept === d.department ? 'bg-slate-50 dark:bg-navy-800/40' : ''
                            }`}
                          >
                            <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{d.department}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_total}</td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_high_readiness}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{d.avg_readiness_score.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {sr.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {sr.department_normalization_notes.map((note, i) => <li key={i}>· {note}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Heuristic disclaimer — rendered a second time, in full,
                    alongside the results (not just the top banner), and the
                    formula itself is shown so the heuristic is fully
                    transparent, never a black box. Phase 15: moved to
                    `informational` for the same reason as the top banner. */}
                <StatusBanner tone="informational">
                  <p className="mb-2">{sr.disclaimer_en}</p>
                  <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                    {t("Formula used (this tool's own construction, not a validated instrument)", 'الصيغة المستخدمة (بناء هذه الأداة، وليست أداة معتمدة)')}
                  </p>
                  <p className="text-[11px] opacity-70">{sr.formula_description_en}</p>
                </StatusBanner>

                <StatusBanner tone="neutral">
                  <p className="mb-2">{sr.governance_note}</p>
                  {sr.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {sr.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
