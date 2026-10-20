/**
 * Nitaqat / Saudization Compliance — Phase 7.
 *
 * Real analysis only: uploads a file to POST /api/local/nitaqat-compliance
 * (backend/core/nitaqat_compliance_engine.py) and renders whatever the
 * backend actually computed.
 *
 * NON-NEGOTIABLE: this page NEVER claims to replicate the official HRSD/
 * Qiwa Nitaqat Mutawar calculation — the real per-sector logarithmic
 * formula's coefficients are not publicly available (see
 * NITAQAT_COMPLIANCE_INVESTIGATION.md). Every result renders a persistent
 * "Illustrative estimate — not an official Nitaqat/HRSD determination"
 * banner, unconditionally, whenever any band/percentage is shown.
 */
import { Fragment, useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Users, RefreshCw, Flag, ChevronDown, ShieldAlert,
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
import { useSortableTable } from '../hooks/useSortableTable'
import { nitaqatBandColor, motion as motionTokens } from '../styles/design-tokens'

interface DepartmentSaudizationBreakdown {
  department: string
  n_total: number
  n_saudi: number
  n_non_saudi: number
  saudization_pct: number
  band: string
}

interface NitaqatCompliance {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_total: number
  n_saudi: number
  n_non_saudi: number
  n_excluded_missing: number
  saudization_pct: number | null
  band: string | null
  is_small_establishment: boolean
  department_breakdown: DepartmentSaudizationBreakdown[]
  department_normalization_notes: string[]
  band_thresholds_used: Record<string, number>
  is_official_calculation: boolean
  calculation_confidence: string
  narrative_en: string
  narrative_ar: string
  governance_note: string
  disclaimer_en: string
  disclaimer_ar: string
  sources: string[]
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  nitaqat_compliance: NitaqatCompliance
}

const COLUMN_LABELS_EN: Record<string, string> = {
  nationality_or_saudi_status: 'Nationality / Saudi status (e.g. Nationality, IsSaudi)',
  department_or_sector: 'Department / economic activity (optional, for a breakdown)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  nationality_or_saudi_status: 'الجنسية / الحالة السعودية (مثال: Nationality أو IsSaudi)',
  department_or_sector: 'القسم / النشاط الاقتصادي (اختياري، لعرض تفصيلي)',
}

const BAND_COLOR: Record<string, string> = {
  Platinum: 'text-slate-300',
  'High Green': 'text-emerald-500',
  'Mid Green': 'text-emerald-400',
  'Low Green': 'text-emerald-300',
  Green: 'text-emerald-400',
  Red: 'text-red-500',
}
const BAND_BADGE: Record<string, string> = {
  Platinum: 'bg-slate-200 text-slate-800 dark:bg-slate-300 dark:text-slate-900',
  'High Green': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  'Mid Green': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  'Low Green': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  Green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  Red: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
}

const UPLOAD_TIMEOUT_MS = 30_000

type DeptSortKey = 'name' | 'saudization' | 'total'

export function NitaqatComplianceTracker() {
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

      const response = await fetch('/api/local/nitaqat-compliance', {
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

  const nc = result?.nitaqat_compliance
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []
  const [hoveredDept, setHoveredDept] = useState<string | null>(null)
  const [expandedDept, setExpandedDept] = useState<string | null>(null)

  // Phase 14 — hook called unconditionally every render (Rules of Hooks);
  // receives an empty array before a dataset is loaded.
  const { sorted: sortedDepartments, sortKey, setSortKey } = useSortableTable<DepartmentSaudizationBreakdown, DeptSortKey>(
    nc?.department_breakdown ?? [],
    {
      name: (a, b) => a.department.localeCompare(b.department),
      saudization: (a, b) => b.saudization_pct - a.saudization_pct,
      total: (a, b) => b.n_total - a.n_total,
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Nitaqat / Saudization Compliance', 'الامتثال لنطاقات / السعودة')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Illustrative Saudization percentage and band estimate — for HR planning, not an official determination.',
            'تقدير إرشادي لنسبة السعودة والمستوى — لأغراض التخطيط، وليس تصنيفاً رسمياً.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      {/* Persistent, unconditional illustrative-estimate banner. Phase 15:
          moved from `caution`(amber)/ShieldAlert to `informational` — this
          disclosure is ALWAYS shown regardless of findings (constant, not
          risk-dependent), so it must read as quiet methodology context,
          not as an alarming situational flag. Text is unchanged
          word-for-word; only the visual tone changed. */}
      <StatusBanner tone="informational">
        <span className="font-medium">
          {t(
            'Illustrative estimate — NOT an official Nitaqat/HRSD determination. The real Nitaqat Mutawar calculation uses a per-sector logarithmic formula HRSD has not published in any accessible public source. Verify actual status via Qiwa (qiwa.sa) before any hiring, visa, or compliance decision.',
            'تقدير إرشادي — وليس تصنيفاً رسمياً من نطاقات أو وزارة الموارد البشرية والتنمية الاجتماعية. الحساب الفعلي يعتمد على معادلة خاصة بكل نشاط اقتصادي لم تُنشر. يرجى التحقق عبر منصة قوى (qiwa.sa) قبل اتخاذ أي قرار.'
          )}
          {' '}
          {/* Phase 17 — additive, per live regulatory research: since
              2026-04-15, official Nitaqat counting also requires Qiwa
              contract-authentication status (MHRSD announcement; Saudi
              Gazette; Erickson Immigration Group — see
              nitaqat_compliance_engine.py's NITAQAT_QIWA_CONTRACT_NOTE_EN
              for full source citations). This platform only ever sees a
              nationality/Saudi-status column, never Qiwa contract status. */}
          {t(
            'This estimate is based on nationality data only. Since April 2026, official Nitaqat counting also requires Qiwa contract authentication status, which this platform cannot verify — actual counted headcount may differ from this estimate.',
            'يعتمد هذا التقدير على بيانات الجنسية فقط. اعتباراً من أبريل 2026، يتطلب الاحتساب الرسمي لنطاقات أيضاً حالة توثيق العقد عبر منصة قوى، وهو أمر لا يمكن لهذه المنصة التحقق منه — قد يختلف العدد الفعلي المُحتسب عن هذا التقدير.'
          )}
        </span>
      </StatusBanner>

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with a nationality/Saudi-status column to compute an illustrative Saudization estimate. Most HR exports have no nationality column — this page honestly says so instead of fabricating a percentage.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود الجنسية/الحالة السعودية لحساب تقدير إرشادي لنسبة السعودة. معظم بيانات الموارد البشرية لا تحتوي على عمود جنسية — تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال نسبة.'
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
            {t('Estimating Saudization compliance…', 'جارٍ تقدير الامتثال للسعودة…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && nc && (
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

            {!nc.available ? (
              <EmptyState
                icon={Users}
                title={t('Nationality data not detected in this upload', 'لم يتم اكتشاف بيانات الجنسية في هذا الملف')}
                reason={nc.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={nc.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(nc.columns_detected).map(k => [k, COLUMN_LABELS_EN[k] ? t(COLUMN_LABELS_EN[k], COLUMN_LABELS_AR[k]) : k])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Total Classified', 'إجمالي المصنّفين')}
                    value={nc.n_total.toLocaleString()}
                    subtitle={nc.n_excluded_missing > 0 ? `${nc.n_excluded_missing} ${t('excluded (missing)', 'مستبعد (مفقود)')}` : undefined}
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `Spread across ${nc.department_breakdown.length} department(s).`,
                      `موزعون على ${nc.department_breakdown.length} قسم.`
                    )}
                  />
                  <KPICard
                    label={t('Saudi Nationals', 'المواطنون السعوديون')}
                    value={nc.n_saudi.toLocaleString()}
                    subtitle={`${nc.n_non_saudi} ${t('non-Saudi', 'غير سعودي')}`}
                    icon={Flag}
                    iconColor="text-emerald-500"
                    iconBg="bg-emerald-500/10"
                    animateValue
                    detail={t('From an explicit nationality/Saudi-status column in your upload.', 'من عمود صريح للجنسية/الحالة السعودية في ملفك.')}
                  />
                  <KPICard
                    label={t('Saudization %', 'نسبة السعودة')}
                    value={nc.saudization_pct != null ? `${nc.saudization_pct.toFixed(1)}%` : '—'}
                    icon={Users}
                    hero
                    animateValue
                    radialPct={nc.saudization_pct ?? undefined}
                    radialColor={nc.band ? (nitaqatBandColor[nc.band] ?? '#3b82f6') : '#3b82f6'}
                    detail={t('Illustrative estimate — verify actual status via Qiwa before any decision.', 'تقدير إرشادي — يرجى التحقق من الحالة الفعلية عبر قوى قبل اتخاذ أي قرار.')}
                  />
                  <KPICard
                    label={t('Illustrative Band', 'المستوى الإرشادي')}
                    value={nc.band ?? '—'}
                    subtitle={nc.is_small_establishment ? t('Small establishment rule', 'قاعدة المنشأة الصغيرة') : undefined}
                    icon={ShieldAlert}
                    iconColor={nc.band ? (BAND_COLOR[nc.band] ?? 'text-slate-400') : 'text-slate-400'}
                    iconBg="bg-slate-500/10"
                    detail={t("This tool's own constructed thresholds, not an official HRSD source.", 'حدود من تصميم هذه الأداة، وليست من مصدر رسمي.')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? nc.narrative_ar : nc.narrative_en}
                  </p>
                </div>

                {nc.department_breakdown.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">
                      {t('Saudization % by Department', 'نسبة السعودة حسب القسم')}
                    </p>
                    <DepartmentBarChart
                      data={nc.department_breakdown.map(d => ({
                        department: d.department,
                        value: d.saudization_pct,
                        color: nitaqatBandColor[d.band] ?? '#3b82f6',
                        tooltipExtra: { [t('Band', 'المستوى')]: d.band, [t('Total', 'الإجمالي')]: d.n_total },
                      }))}
                      valueFormatter={(v) => `${v.toFixed(1)}%`}
                      highlightedKey={hoveredDept}
                      onHoverChange={setHoveredDept}
                    />
                  </div>
                )}

                {nc.department_breakdown.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<DeptSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'saudization', label: t('Saudization %', 'نسبة السعودة') },
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
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Saudi', 'سعودي')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Saudization %', 'نسبة السعودة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Band', 'المستوى')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedDepartments.map((d) => {
                          const isExpanded = expandedDept === d.department
                          return (
                            <Fragment key={d.department}>
                              <tr
                                onClick={() => setExpandedDept(isExpanded ? null : d.department)}
                                onMouseEnter={() => setHoveredDept(d.department)}
                                onMouseLeave={() => setHoveredDept(null)}
                                className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 cursor-pointer ${
                                  hoveredDept === d.department ? 'bg-slate-50 dark:bg-navy-800/40' : ''
                                }`}
                              >
                                <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                                  <span className="inline-flex items-center gap-1.5">
                                    <ChevronDown
                                      size={12}
                                      className={`text-slate-400 transition-transform duration-base ease-executive ${isExpanded ? 'rotate-180' : ''}`}
                                    />
                                    {d.department}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_total}</td>
                                <td className="px-4 py-2.5 text-right text-slate-600 dark:text-slate-400">{d.n_saudi}</td>
                                <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{d.saudization_pct.toFixed(1)}%</td>
                                <td className="px-4 py-2.5 text-center">
                                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${BAND_BADGE[d.band] ?? 'bg-slate-100 text-slate-600'}`}>
                                    {d.band}
                                  </span>
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
                                    <td colSpan={5} className="px-4 pb-3 pt-0 bg-slate-50/70 dark:bg-navy-800/30">
                                      <div className="ps-5 max-w-sm">
                                        <div dir="ltr" style={{ direction: 'ltr' }} className="flex w-full h-2 rounded-full overflow-hidden bg-slate-200 dark:bg-navy-800">
                                          <div
                                            className="h-2 bg-emerald-500"
                                            style={{ width: `${d.n_total > 0 ? (d.n_saudi / d.n_total) * 100 : 0}%` }}
                                          />
                                          <div
                                            className="h-2 bg-slate-400 dark:bg-navy-400"
                                            style={{ width: `${d.n_total > 0 ? (d.n_non_saudi / d.n_total) * 100 : 0}%` }}
                                          />
                                        </div>
                                        <div className="flex items-center gap-4 mt-1.5 text-xs">
                                          <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                                            <span className="w-2 h-2 rounded-full bg-emerald-500" />
                                            {t('Saudi', 'سعودي')}: {d.n_saudi} ({d.n_total > 0 ? ((d.n_saudi / d.n_total) * 100).toFixed(0) : 0}%)
                                          </span>
                                          <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                                            <span className="w-2 h-2 rounded-full bg-slate-400 dark:bg-navy-400" />
                                            {t('Non-Saudi', 'غير سعودي')}: {d.n_non_saudi} ({d.n_total > 0 ? ((d.n_non_saudi / d.n_total) * 100).toFixed(0) : 0}%)
                                          </span>
                                        </div>
                                      </div>
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

                {nc.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {nc.department_normalization_notes.map((note, i) => <li key={i}>· {note}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Illustrative disclaimer — rendered a second time, in full,
                    alongside the results (not just the top banner), and the
                    band thresholds used are shown so the heuristic is fully
                    transparent, never a black box. Phase 15: moved to
                    `informational` — same reasoning as the top banner, this
                    is a constant methodology disclosure, not a situational
                    risk flag. */}
                <StatusBanner tone="informational">
                  <p className="mb-2">{nc.disclaimer_en}</p>
                  <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                    {t('Illustrative band thresholds used (this tool\'s own construction, not an HRSD source)', 'الحدود الإرشادية للمستويات المستخدمة (بناء هذه الأداة، وليست من مصدر رسمي)')}
                  </p>
                  <p className="text-[11px] opacity-70">
                    {Object.entries(nc.band_thresholds_used)
                      .sort((a, b) => b[1] - a[1])
                      .map(([band, pct]) => `${band} ≥ ${pct}%`)
                      .join('  ·  ')}
                  </p>
                </StatusBanner>

                <StatusBanner tone="neutral">
                  <p className="mb-2">{nc.governance_note}</p>
                  {nc.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {nc.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
