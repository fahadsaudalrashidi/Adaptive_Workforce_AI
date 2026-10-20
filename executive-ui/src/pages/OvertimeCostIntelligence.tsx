/**
 * Overtime & Workforce Cost Intelligence — Phase 35.1.
 *
 * Real analysis only: uploads a file to POST /api/local/overtime-cost-intelligence
 * (backend/core/overtime_cost_intelligence_engine.py) and renders whatever the
 * backend actually computed. No demo/hardcoded data — if a dataset has no
 * overtime-related column, the page shows the backend's real `available: false`
 * message rather than fabricating a chart.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Clock, DollarSign, AlertTriangle, CheckCircle,
  RefreshCw,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { KPICard } from '../components/shared/KPICard'
import { SkeletonAnalysis } from '../components/shared/SkeletonAnalysis'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { SortToggle } from '../components/shared/SortToggle'
import { StatusBanner } from '../components/shared/StatusBanner'
import { StatusLegend } from '../components/shared/StatusLegend'
import { useSortableTable } from '../hooks/useSortableTable'
import { semantic } from '../styles/design-tokens'

interface DepartmentOvertimeCost {
  department: string
  n_employees: number
  n_overtime_employees: number
  overtime_prevalence_pct: number
  monthly_overtime_cost_sar: number
  annual_overtime_cost_sar: number
  average_risk_score: number | null
  elevated_overtime_and_risk: boolean
}

interface OvertimeCostIntelligence {
  available: boolean
  reason: string | null
  hours_source: 'observed' | 'assumed' | 'unavailable'
  wage_source: 'observed' | 'estimated' | 'unavailable'
  n_employees_total: number
  n_overtime_employees: number
  overtime_prevalence_pct: number
  org_monthly_overtime_cost_sar: number
  org_annual_overtime_cost_sar: number
  department_breakdown: DepartmentOvertimeCost[]
  elevated_risk_departments: string[]
  narrative_en: string
  narrative_ar: string
  governance_note: string
  sources: string[]
  department_normalization_notes: string[]
  salary_benchmark_confidence: 'observed' | 'gastat_official_2018' | 'uncalibrated_generic_estimate' | 'unavailable'
  employment_sector_used: string | null
}

interface ApiResponse {
  filename: string
  row_count?: number
  governance_scan_passed?: boolean
  pii_columns_detected?: string[]
  leakage_columns_detected?: string[]
  data_quality_warnings?: string[]
  overtime_cost_intelligence: OvertimeCostIntelligence
}

const UPLOAD_TIMEOUT_MS = 30_000

type DeptSortKey = 'name' | 'overtime' | 'cost' | 'risk'

function sar(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `SAR ${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `SAR ${(n / 1_000).toFixed(0)}K`
  return `SAR ${n.toFixed(0)}`
}

function benchmarkConfidenceLabel(
  confidence: OvertimeCostIntelligence['salary_benchmark_confidence'],
  t: (en: string, ar: string) => string,
): { text: string; color: string } {
  switch (confidence) {
    case 'observed':
      return { text: t('Observed (from your data)', 'ملاحظ (من بياناتك)'), color: 'text-emerald-600 dark:text-emerald-400' }
    case 'gastat_official_2018':
      return { text: t('GASTAT Official 2018', 'الهيئة العامة للإحصاء الرسمي 2018'), color: 'text-blue-600 dark:text-blue-400' }
    case 'uncalibrated_generic_estimate':
      return { text: t('Uncalibrated generic estimate', 'تقدير عام غير معاير'), color: 'text-amber-600 dark:text-amber-400' }
    default:
      return { text: t('Unavailable', 'غير متاح'), color: 'text-slate-400' }
  }
}

export function OvertimeCostIntelligence() {
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

      const response = await fetch('/api/local/overtime-cost-intelligence', {
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

  const oci = result?.overtime_cost_intelligence
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)

  // Phase 14 — hook is called unconditionally every render (Rules of
  // Hooks); it just receives an empty array before a dataset is loaded,
  // which useSortableTable's own useMemo handles fine.
  const { sorted: sortedDepartments, sortKey, setSortKey } = useSortableTable<DepartmentOvertimeCost, DeptSortKey>(
    oci?.department_breakdown ?? [],
    {
      name: (a, b) => a.department.localeCompare(b.department),
      overtime: (a, b) => b.overtime_prevalence_pct - a.overtime_prevalence_pct,
      cost: (a, b) => b.monthly_overtime_cost_sar - a.monthly_overtime_cost_sar,
      risk: (a, b) => (b.average_risk_score ?? -1) - (a.average_risk_score ?? -1),
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Overtime & Workforce Cost Intelligence', 'ذكاء تكلفة العمل الإضافي والقوى العاملة')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Real overtime financial exposure by department, cross-referenced against attrition risk.',
            'التعرض المالي الفعلي للعمل الإضافي حسب القسم، مقارنة بمخاطر الاستنزاف.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with an overtime column (hours or yes/no) to compute real cost exposure. This is a separate, dedicated analysis — it does not reuse a previously uploaded file.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود للعمل الإضافي (ساعات أو نعم/لا) لحساب التعرض المالي الفعلي. هذا تحليل منفصل ومخصص — لا يعيد استخدام ملفاً محملاً مسبقاً.'
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
            {t('Analyzing overtime cost…', 'جارٍ تحليل تكلفة العمل الإضافي…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && oci && (
          <motion.div
            key="results"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-5"
          >
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

            {/* Data quality disclosure — includes the duplicate-row removal
                notice (e.g. "1 duplicate row(s) removed... matched by
                'EmployeeID'"), surfaced here rather than applied silently. */}
            {result?.data_quality_warnings && result.data_quality_warnings.filter(w => w.includes('duplicate row')).length > 0 && (
              <StatusBanner tone="caution" compact>
                <ul className="space-y-0.5">
                  {result.data_quality_warnings.filter(w => w.includes('duplicate row')).map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </StatusBanner>
            )}

            {!oci.available ? (
              <div className="card-flat p-8 text-center">
                <div className="empty-state-icon-ring mx-auto mb-4">
                  <Clock size={24} className="text-navy-200" />
                </div>
                <p className="text-title text-slate-700 dark:text-slate-200 mb-2">
                  {t('Overtime analysis not available for this dataset', 'تحليل العمل الإضافي غير متاح لهذه البيانات')}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                  {oci.reason}
                </p>
              </div>
            ) : (
              <>
                {/* KPI row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Overtime Prevalence', 'انتشار العمل الإضافي')}
                    value={`${oci.overtime_prevalence_pct.toFixed(0)}%`}
                    subtitle={`${oci.n_overtime_employees} / ${oci.n_employees_total} ${t('employees', 'موظف')}`}
                    icon={Clock}
                    hero
                    animateValue
                    radialPct={oci.overtime_prevalence_pct}
                    radialColor={semantic.monitor}
                    detail={oci.hours_source === 'observed'
                      ? t('Hours are directly observed in the uploaded data.', 'الساعات مرصودة مباشرة في البيانات المحملة.')
                      : t('Hours estimated from a yes/no overtime flag (no hours column found).', 'الساعات مُقدّرة من مؤشر نعم/لا للعمل الإضافي (لا يوجد عمود ساعات).')}
                  />
                  <KPICard
                    label={t('Monthly Overtime Cost', 'التكلفة الشهرية للعمل الإضافي')}
                    value={sar(oci.org_monthly_overtime_cost_sar)}
                    subtitle={oci.wage_source === 'observed'
                      ? t('From observed salary data', 'من بيانات الراتب الفعلية')
                      : t('Estimated salary basis', 'أساس راتب تقديري')}
                    // Phase 15: was TrendingUp (a trend icon) on a plain
                    // financial figure with no trend meaning — this page's
                    // OTHER financial KPI below had the same mismatch
                    // (Building2, an org/department icon). Both now use
                    // the fixed financial icon (DollarSign) matching the
                    // CEO Dashboard's "Financial Exposure" chip.
                    icon={DollarSign}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `${benchmarkConfidenceLabel(oci.salary_benchmark_confidence, t).text} salary benchmark${oci.employment_sector_used ? ` · ${oci.employment_sector_used} sector` : ''}.`,
                      `معيار راتب: ${benchmarkConfidenceLabel(oci.salary_benchmark_confidence, t).text}${oci.employment_sector_used ? ` · قطاع ${oci.employment_sector_used}` : ''}.`
                    )}
                  />
                  <KPICard
                    label={t('Annual Overtime Exposure', 'التعرض السنوي للعمل الإضافي')}
                    value={sar(oci.org_annual_overtime_cost_sar)}
                    icon={DollarSign}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    highlight
                    animateValue
                    detail={t('Monthly overtime cost projected across 12 months.', 'التكلفة الشهرية للعمل الإضافي مُسقطة على 12 شهراً.')}
                  />
                  <KPICard
                    label={t('Departments Flagged', 'الأقسام المُعلّمة')}
                    value={oci.elevated_risk_departments.length}
                    subtitle={t('High overtime + high risk', 'عمل إضافي مرتفع + مخاطر مرتفعة')}
                    icon={AlertTriangle}
                    iconColor={oci.elevated_risk_departments.length > 0 ? 'text-red-500' : 'text-emerald-500'}
                    iconBg={oci.elevated_risk_departments.length > 0 ? 'bg-red-500/10' : 'bg-emerald-500/10'}
                    animateValue
                    detail={oci.elevated_risk_departments.length > 0
                      ? oci.elevated_risk_departments.join(', ')
                      : t('No department shows both elevated overtime and elevated risk.', 'لا يوجد قسم يظهر فيه عمل إضافي مرتفع ومخاطر مرتفعة معاً.')}
                  />
                </div>

                {/* Data source transparency */}
                {(oci.hours_source === 'assumed' || oci.wage_source === 'estimated') && (
                  <StatusBanner tone="neutral" compact>
                    {oci.hours_source === 'assumed' && t(
                      'Hours estimated from a yes/no overtime flag (no hours column found). ',
                      'الساعات مُقدّرة من مؤشر نعم/لا للعمل الإضافي (لا يوجد عمود ساعات). '
                    )}
                    {oci.wage_source === 'estimated' && t(
                      'Salary estimated from sector benchmarks (no salary column found).',
                      'الراتب مُقدّر من معايير القطاع (لا يوجد عمود راتب).'
                    )}
                  </StatusBanner>
                )}

                {/* Salary benchmark confidence — Phase 4 sector benchmarking,
                    surfaced here since Overtime Cost Intelligence is the only
                    live page that consumes financial_intelligence_engine.py's
                    salary model. Always shown, not just when estimated, so the
                    "observed" case is equally visible. */}
                <div className="flex items-center gap-2 p-3 bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-lg">
                  <span className="text-[10px] text-slate-400 dark:text-slate-500 uppercase tracking-wide font-semibold">
                    {t('Salary Benchmark', 'معيار الراتب')}
                  </span>
                  <span className={`text-xs font-semibold ${benchmarkConfidenceLabel(oci.salary_benchmark_confidence, t).color}`}>
                    {benchmarkConfidenceLabel(oci.salary_benchmark_confidence, t).text}
                  </span>
                  {oci.employment_sector_used && (
                    <span className="text-[11px] text-slate-400 dark:text-slate-500">
                      ({t('sector', 'قطاع')}: {oci.employment_sector_used})
                    </span>
                  )}
                </div>

                {/* Narrative */}
                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? oci.narrative_ar : oci.narrative_en}
                  </p>
                </div>

                {/* Department comparison chart */}
                <div className="card p-5">
                  <p className="section-title mb-4">
                    {t('Overtime Prevalence by Department', 'انتشار العمل الإضافي حسب القسم')}
                  </p>
                  <DepartmentBarChart
                    data={oci.department_breakdown.map(d => ({
                      department: d.department,
                      value: d.overtime_prevalence_pct,
                      color: d.elevated_overtime_and_risk ? semantic.priority : semantic.monitor,
                      tooltipExtra: { [t('Monthly Cost', 'التكلفة الشهرية')]: sar(d.monthly_overtime_cost_sar) },
                    }))}
                    valueFormatter={(v) => `${v.toFixed(0)}%`}
                    highlightedKey={hoveredDept}
                    onHoverChange={setHoveredDept}
                  />
                </div>

                {/* Department table — live client-side sort (useSortableTable),
                    row-hover cross-highlighted with the bar chart above via
                    shared hoveredDept state. */}
                <div className="card overflow-x-auto">
                  <div className="flex items-center justify-end px-4 pt-3">
                    <SortToggle<DeptSortKey>
                      label={t('Sort:', 'ترتيب:')}
                      active={sortKey}
                      onChange={setSortKey}
                      options={[
                        { key: 'overtime', label: t('Overtime %', 'نسبة العمل الإضافي') },
                        { key: 'cost', label: t('Cost', 'التكلفة') },
                        { key: 'risk', label: t('Risk', 'المخاطر') },
                        { key: 'name', label: t('Name', 'الاسم') },
                      ]}
                    />
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                          {t('Department', 'القسم')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('Overtime %', 'نسبة العمل الإضافي')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('Monthly Cost', 'التكلفة الشهرية')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                          {t('Avg Risk', 'متوسط المخاطر')}
                        </th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">
                          {t('Flag', 'إشارة')}
                        </th>
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
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">
                            {d.overtime_prevalence_pct.toFixed(0)}% ({d.n_overtime_employees}/{d.n_employees})
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">
                            {sar(d.monthly_overtime_cost_sar)}
                          </td>
                          <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">
                            {d.average_risk_score != null ? d.average_risk_score.toFixed(0) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-center">
                            {d.elevated_overtime_and_risk ? (
                              <AlertTriangle size={14} className="text-red-500 inline" />
                            ) : (
                              <CheckCircle size={14} className="text-slate-300 dark:text-slate-600 inline" />
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Department name normalization disclosure — Bug fix: "Sales"/
                    "مبيعات" and "Finance"/"finance" are now merged into one
                    department row instead of being double-counted; every
                    merge (or unmerged near-duplicate flagged for review) is
                    disclosed here, never applied silently. */}
                {oci.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">
                      {t('Department names normalized', 'تم توحيد أسماء الأقسام')}
                    </p>
                    <ul className="space-y-0.5 mt-1">
                      {oci.department_normalization_notes.map((note, i) => (
                        <li key={i}>· {note}</li>
                      ))}
                    </ul>
                  </StatusBanner>
                )}

                {/* Governance + sources */}
                <StatusBanner tone="neutral">
                  <p className="mb-2">{oci.governance_note}</p>
                  <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                    {t('Sources', 'المصادر')}
                  </p>
                  <ul className="text-[11px] opacity-70 space-y-0.5">
                    {oci.sources.map((s, i) => <li key={i}>· {s}</li>)}
                  </ul>
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
