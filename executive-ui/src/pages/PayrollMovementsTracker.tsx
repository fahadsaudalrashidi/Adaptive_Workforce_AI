/**
 * Payroll Movements Tracker — Phase 35.2.
 *
 * Real analysis only: uploads a file to POST /api/local/payroll-movements
 * (backend/core/payroll_movement_tracker.py) and renders whatever the
 * backend actually computed. No demo/hardcoded data. Most snapshot HR
 * datasets will return `data_mode: "unavailable"` or `"cross_sectional_snapshot"`
 * rather than `"longitudinal"` — the page renders each mode honestly,
 * including explaining what unlocks full period-over-period tracking.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, TrendingUp, AlertTriangle, RefreshCw, Layers, Camera,
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

interface DepartmentPayrollMovement {
  department: string
  n_employees: number
  avg_hike_pct: number
  avg_risk_score_above_median_hike: number | null
  avg_risk_score_below_median_hike: number | null
}

interface PayrollMovements {
  available: boolean
  reason: string | null
  data_mode: 'longitudinal' | 'cross_sectional_snapshot' | 'unavailable'
  n_employees_total: number
  org_avg_hike_pct: number | null
  n_periods_detected: number | null
  department_breakdown: DepartmentPayrollMovement[]
  comparison_note_en: string
  comparison_note_ar: string
  limitation_note_en: string
  limitation_note_ar: string
  governance_note: string
  sources: string[]
  department_normalization_notes: string[]
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  payroll_movements: PayrollMovements
}

const UPLOAD_TIMEOUT_MS = 30_000

type DeptSortKey = 'name' | 'movement' | 'employees'

const MODE_CONFIG = {
  longitudinal: {
    icon: Layers,
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    labelEn: 'Longitudinal — real period-over-period history',
    labelAr: 'طولي — سجل فعلي بين الفترات',
  },
  cross_sectional_snapshot: {
    icon: Camera,
    color: 'text-amber-500',
    bg: 'bg-amber-500/10',
    labelEn: 'Snapshot proxy — single point in time',
    labelAr: 'مؤشر لحظي — نقطة زمنية واحدة',
  },
  unavailable: {
    icon: AlertTriangle,
    color: 'text-slate-400',
    bg: 'bg-slate-500/10',
    labelEn: 'Not available for this dataset',
    labelAr: 'غير متاح لهذه البيانات',
  },
} as const

export function PayrollMovementsTracker() {
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

      const response = await fetch('/api/local/payroll-movements', {
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

  const pm = result?.payroll_movements
  const modeCfg = pm ? MODE_CONFIG[pm.data_mode] : null
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)

  // Phase 14 — hook called unconditionally every render (Rules of Hooks);
  // receives an empty array before a dataset is loaded.
  const { sorted: sortedDepartments, sortKey, setSortKey } = useSortableTable<DepartmentPayrollMovement, DeptSortKey>(
    pm?.department_breakdown ?? [],
    {
      name: (a, b) => a.department.localeCompare(b.department),
      movement: (a, b) => b.avg_hike_pct - a.avg_hike_pct,
      employees: (a, b) => b.n_employees - a.n_employees,
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Payroll Movements Tracker', 'متتبع حركة الرواتب')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Real salary-movement analysis, compared descriptively against attrition risk.',
            'تحليل حركة الرواتب الفعلي، مقارنةً وصفياً بمخاطر الاستنزاف.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Most HR exports are a single snapshot. This page honestly reports whichever mode your data supports — a full period-over-period history, a single-point salary-hike indicator, or neither — rather than fabricating a trend.',
          'معظم بيانات الموارد البشرية هي لقطة واحدة. تعرض هذه الصفحة بصدق الوضع الذي تدعمه بياناتك — سجل كامل بين الفترات، أو مؤشر لحظي، أو لا شيء — دون افتعال اتجاه وهمي.'
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
            {t('Analyzing payroll movement…', 'جارٍ تحليل حركة الرواتب…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && pm && modeCfg && (
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

            {/* Mode banner — always shown, honest about data shape */}
            <div className={`flex items-center gap-3 p-4 rounded-xl ${modeCfg.bg}`}>
              <modeCfg.icon size={20} className={modeCfg.color} />
              <p className={`text-sm font-semibold ${modeCfg.color}`}>
                {isAr ? modeCfg.labelAr : modeCfg.labelEn}
              </p>
            </div>

            {!pm.available ? (
              <div className="card-flat p-8 text-center">
                <div className="empty-state-icon-ring mx-auto mb-4">
                  <TrendingUp size={24} className="text-navy-200" />
                </div>
                <p className="text-title text-slate-700 dark:text-slate-200 mb-2">
                  {pm.reason}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                  {isAr ? pm.limitation_note_ar : pm.limitation_note_en}
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                  <KPICard
                    label={t('Average Movement', 'متوسط الحركة')}
                    value={pm.org_avg_hike_pct != null ? `${pm.org_avg_hike_pct >= 0 ? '+' : ''}${pm.org_avg_hike_pct.toFixed(1)}%` : '—'}
                    icon={TrendingUp}
                    hero
                    animateValue
                    iconColor={pm.org_avg_hike_pct != null && pm.org_avg_hike_pct >= 0 ? 'text-emerald-500' : 'text-red-500'}
                    detail={isAr ? modeCfg.labelAr : modeCfg.labelEn}
                  />
                  <KPICard
                    label={t('Employees Covered', 'الموظفون المشمولون')}
                    value={pm.n_employees_total.toLocaleString()}
                    icon={Layers}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    animateValue
                    detail={t(
                      `Spread across ${pm.department_breakdown.length} department(s).`,
                      `موزعون على ${pm.department_breakdown.length} قسم.`
                    )}
                  />
                  <KPICard
                    label={t('Periods Detected', 'الفترات المكتشفة')}
                    value={pm.n_periods_detected ?? '—'}
                    subtitle={pm.data_mode === 'cross_sectional_snapshot'
                      ? t('Single snapshot only', 'لقطة واحدة فقط')
                      : undefined}
                    icon={Camera}
                    iconColor="text-amber-500"
                    iconBg="bg-amber-500/10"
                    animateValue
                    detail={isAr ? pm.limitation_note_ar : pm.limitation_note_en}
                  />
                </div>

                {pm.data_mode === 'cross_sectional_snapshot' && (
                  <StatusBanner tone="caution" compact>
                    {isAr ? pm.limitation_note_ar : pm.limitation_note_en}
                  </StatusBanner>
                )}

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? pm.comparison_note_ar : pm.comparison_note_en}
                  </p>
                </div>

                {pm.department_breakdown.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">
                      {t('Average Movement by Department', 'متوسط الحركة حسب القسم')}
                    </p>
                    <DepartmentBarChart
                      data={pm.department_breakdown.map(d => ({
                        department: d.department,
                        value: d.avg_hike_pct,
                        color: d.avg_hike_pct >= 0 ? semantic.stable : semantic.priority,
                        tooltipExtra: { [t('Employees', 'الموظفون')]: d.n_employees },
                      }))}
                      valueFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      highlightedKey={hoveredDept}
                      onHoverChange={setHoveredDept}
                    />
                  </div>
                )}

                {pm.department_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<DeptSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'movement', label: t('Movement', 'الحركة') },
                          { key: 'employees', label: t('Employees', 'الموظفون') },
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
                            {t('Employees', 'الموظفون')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                            {t('Avg Movement', 'متوسط الحركة')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                            {t('Risk (above-median hike)', 'المخاطر (زيادة أعلى من المتوسط)')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                            {t('Risk (below-median hike)', 'المخاطر (زيادة أقل من المتوسط)')}
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
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_employees}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">
                              {d.avg_hike_pct >= 0 ? '+' : ''}{d.avg_hike_pct.toFixed(1)}%
                            </td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">
                              {d.avg_risk_score_above_median_hike != null ? d.avg_risk_score_above_median_hike.toFixed(0) : '—'}
                            </td>
                            <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">
                              {d.avg_risk_score_below_median_hike != null ? d.avg_risk_score_below_median_hike.toFixed(0) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Department name normalization disclosure — Bug fix: "Sales"/
                    "مبيعات" and "Finance"/"finance" are now merged into one
                    department row instead of being double-counted; every
                    merge (or unmerged near-duplicate flagged for review) is
                    disclosed here, never applied silently. */}
                {pm.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">
                      {t('Department names normalized', 'تم توحيد أسماء الأقسام')}
                    </p>
                    <ul className="space-y-0.5 mt-1">
                      {pm.department_normalization_notes.map((note, i) => (
                        <li key={i}>· {note}</li>
                      ))}
                    </ul>
                  </StatusBanner>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{pm.governance_note}</p>
                  {pm.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {pm.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
