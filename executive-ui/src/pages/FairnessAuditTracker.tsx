/**
 * Fairness / Bias Audit — Phase 6.
 *
 * Real analysis only: uploads a file to POST /api/local/fairness-audit
 * (backend/core/ethical_ai.py) and renders whatever the backend actually
 * computed. Fixed a confirmed bug (ETHICAL_AI_ENGINE_INVESTIGATION.md §5b)
 * where a continuous attribute (Age) produced a fabricated 428,600,000x
 * "CRITICAL" disparity ratio — this page only ever shows bucketed,
 * minimum-group-size-floored, real numbers. If no protected attribute
 * (gender, age, nationality, etc.) is detected, this page says so honestly
 * instead of hiding the section or fabricating a result.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Scale, AlertTriangle, CheckCircle2, RefreshCw, ShieldAlert, Users2,
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

interface ProtectedAttribute {
  column_name: string
  attribute_type: string
  detection_confidence: number
  value_counts: Record<string, number>
  representation_warning: boolean
}

interface FairnessMetric {
  metric_name: string
  attribute_column: string
  score: number
  disparity_ratio: number
  risk_level: 'critical' | 'high' | 'medium' | 'low' | 'acceptable'
  group_rates: Record<string, number>
  interpretation: string
  recommendation: string
  was_bucketed: boolean
  n_groups_excluded_small_sample: number
  p_value: number | null
  statistically_significant: boolean | null
}

interface BiasAudit {
  protected_attributes: ProtectedAttribute[]
  fairness_metrics: FairnessMetric[]
  overall_risk_level: string
  bias_detected: boolean
  audit_summary: string
  recommendations: string[]
  ethical_disclaimer: string
  audit_passed: boolean
  granularity_notes: string[]
}

interface ConfidenceGovernance {
  prediction_type: string
  raw_confidence: number
  governed_confidence: number
  display_allowed: boolean
  suppression_reason: string
  confidence_band: 'High' | 'Moderate' | 'Low' | 'Unreliable'
  caveats: string[]
  requires_human_review: boolean
}

interface EthicalReport {
  bias_audit: BiasAudit
  governance: ConfidenceGovernance[]
  overall_ethical_status: 'Pass' | 'Conditional' | 'Fail'
  blocking_issues: string[]
  advisory_warnings: string[]
  ethical_clearance_text: string
  requires_expert_review: boolean
}

interface ApiResponse {
  filename: string
  row_count?: number
  ethical_report: EthicalReport
}

const UPLOAD_TIMEOUT_MS = 30_000

type MetricSortKey = 'disparity' | 'attribute'
type AttributeSortKey = 'name' | 'confidence'

const RISK_COLOR: Record<string, string> = {
  critical: 'text-red-500',
  high: 'text-orange-500',
  medium: 'text-amber-500',
  low: 'text-blue-500',
  acceptable: 'text-emerald-500',
}

const RISK_BADGE: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  medium: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  low: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  acceptable: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
}

const RISK_HEX: Record<string, string> = {
  critical: semantic.priority,
  high: '#ea580c',
  medium: semantic.monitor,
  low: semantic.info,
  acceptable: semantic.stable,
}

const STATUS_CONFIG = {
  Pass: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
  Conditional: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-500/10' },
  Fail: { icon: ShieldAlert, color: 'text-red-500', bg: 'bg-red-500/10' },
} as const

export function FairnessAuditTracker() {
  const { t } = useLanguage()
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

      const response = await fetch('/api/local/fairness-audit', {
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

  const er = result?.ethical_report
  const ba = er?.bias_audit
  const statusCfg = er ? STATUS_CONFIG[er.overall_ethical_status] : null
  const [hoveredAttribute, setHoveredAttribute] = useState<string | null>(null)

  // Phase 14 — both hooks called unconditionally every render (Rules of
  // Hooks); each receives an empty array before a dataset is loaded.
  const { sorted: sortedMetrics, sortKey: metricSortKey, setSortKey: setMetricSortKey } = useSortableTable<FairnessMetric, MetricSortKey>(
    ba?.fairness_metrics ?? [],
    {
      disparity: (a, b) => b.disparity_ratio - a.disparity_ratio,
      attribute: (a, b) => a.attribute_column.localeCompare(b.attribute_column),
    },
  )
  const { sorted: sortedAttributes, sortKey: attrSortKey, setSortKey: setAttrSortKey } = useSortableTable<ProtectedAttribute, AttributeSortKey>(
    ba?.protected_attributes ?? [],
    {
      name: (a, b) => a.column_name.localeCompare(b.column_name),
      confidence: (a, b) => b.detection_confidence - a.detection_confidence,
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Fairness / Bias Audit', 'تدقيق العدالة والتحيّز')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Real statistical fairness audit across protected attributes, cross-referenced against prediction confidence governance.',
            'تدقيق إحصائي فعلي للعدالة عبر الخصائص المحمية، مقارنةً بحوكمة موثوقية التنبؤات.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset to check for statistical disparity across protected attributes (gender, age, nationality, etc.). If none are detected, this page says so honestly rather than fabricating a result.',
          'حمّل بيانات القوى العاملة للتحقق من التفاوت الإحصائي عبر الخصائص المحمية (الجنس، العمر، الجنسية، إلخ). إن لم يتم اكتشاف أي منها، تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال نتيجة.'
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
            {t('Running fairness audit…', 'جارٍ تشغيل تدقيق العدالة…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && er && ba && statusCfg && (
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

            {/* Ethical clearance banner — always shown */}
            <div className={`flex items-center gap-3 p-4 rounded-xl ${statusCfg.bg}`}>
              <statusCfg.icon size={20} className={statusCfg.color} />
              <p className={`text-sm font-semibold ${statusCfg.color}`}>
                {er.ethical_clearance_text}
              </p>
            </div>

            {ba.protected_attributes.length === 0 ? (
              /* Honest not-applicable state — no protected attributes detected */
              <div className="card-flat p-8 text-center">
                <div className="empty-state-icon-ring mx-auto mb-4">
                  <Users2 size={24} className="text-navy-200" />
                </div>
                <p className="text-title text-slate-700 dark:text-slate-200 mb-2">
                  {t('No protected attributes detected in this upload', 'لم يتم اكتشاف خصائص محمية في هذا الملف')}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">
                  {ba.audit_summary}
                </p>
                <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-3 max-w-md mx-auto">
                  {t(
                    'Columns that would activate this feature: gender, age, nationality/ethnicity, religion, disability, marital status.',
                    'الأعمدة التي تُفعّل هذه الميزة: الجنس، العمر، الجنسية/العرق، الدين، الإعاقة، الحالة الاجتماعية.'
                  )}
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Protected Attributes', 'الخصائص المحمية')}
                    value={ba.protected_attributes.length}
                    icon={Users2}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={ba.protected_attributes.map(a => a.column_name).join(', ')}
                  />
                  <KPICard
                    label={t('Fairness Metrics Computed', 'مقاييس العدالة المحسوبة')}
                    value={ba.fairness_metrics.length}
                    icon={Scale}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    animateValue
                    detail={t(
                      `${ba.fairness_metrics.filter(m => m.statistically_significant).length} statistically significant.`,
                      `${ba.fairness_metrics.filter(m => m.statistically_significant).length} ذو دلالة إحصائية.`
                    )}
                  />
                  <KPICard
                    label={t('Overall Risk Level', 'مستوى المخاطر الإجمالي')}
                    value={ba.overall_risk_level.toUpperCase()}
                    icon={ShieldAlert}
                    // Phase 15: this page had no hero KPI card at all — the
                    // one page out of the 7 without a single "most
                    // important number" treatment (every other feature
                    // page has exactly one `hero` card). This is the
                    // bottom-line finding of the whole audit, so it gets
                    // the same elevated treatment every sibling page's
                    // headline metric already has.
                    hero
                    iconColor={RISK_COLOR[ba.overall_risk_level] ?? 'text-slate-400'}
                    iconBg="bg-slate-500/10"
                    detail={t('Bucketed and minimum-group-size-floored — never a raw continuous-attribute ratio.', 'مُقسّم ومحكوم بحد أدنى لحجم المجموعة — وليس نسبة خام لخاصية مستمرة.')}
                  />
                  <KPICard
                    label={t('Audit Passed', 'اجتاز التدقيق')}
                    value={ba.audit_passed ? t('Yes', 'نعم') : t('No', 'لا')}
                    icon={ba.audit_passed ? CheckCircle2 : AlertTriangle}
                    iconColor={ba.audit_passed ? 'text-emerald-500' : 'text-red-500'}
                    iconBg={ba.audit_passed ? 'bg-emerald-500/10' : 'bg-red-500/10'}
                    detail={er.blocking_issues.length > 0
                      ? t(`${er.blocking_issues.length} blocking issue(s) found.`, `تم العثور على ${er.blocking_issues.length} مشكلة معيقة.`)
                      : t('No blocking issues found.', 'لم يتم العثور على مشاكل معيقة.')}
                  />
                </div>

                {/* Blocking issues — always includes the non-significance
                    caveat inline when a "critical"/"high" risk level was
                    NOT statistically significant, never an unqualified
                    alarm (see ethical_ai.py generate_ethical_report).
                    Phase 15: this is the ONE genuinely `critical` banner on
                    this page — it now gets the heavier left-border
                    treatment (StatusBanner) so it reads as structurally
                    more urgent than the `caution` advisory banner right
                    below it, not just a different shade of the same box. */}
                {er.blocking_issues.length > 0 && (
                  <StatusBanner tone="critical" compact>
                    <ul className="space-y-1.5">
                      {er.blocking_issues.map((b, i) => <li key={i}>{b}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {er.advisory_warnings.length > 0 && (
                  <StatusBanner tone="caution" compact>
                    <ul className="space-y-1.5">
                      {er.advisory_warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Disparity comparison chart */}
                {ba.fairness_metrics.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">
                      {t('Disparity Ratio by Attribute', 'نسبة التفاوت حسب الخاصية')}
                    </p>
                    <DepartmentBarChart
                      data={ba.fairness_metrics.map(m => ({
                        department: m.attribute_column,
                        value: m.disparity_ratio,
                        color: RISK_HEX[m.risk_level] ?? '#3b82f6',
                        tooltipExtra: {
                          [t('Risk', 'المخاطر')]: m.risk_level.toUpperCase(),
                          [t('Significant?', 'ذو دلالة؟')]: m.statistically_significant ? t('Yes', 'نعم') : t('No', 'لا'),
                        },
                      }))}
                      valueFormatter={(v) => `${v.toFixed(2)}x`}
                      highlightedKey={hoveredAttribute}
                      onHoverChange={setHoveredAttribute}
                    />
                  </div>
                )}

                {/* Fairness metrics table */}
                {ba.fairness_metrics.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<MetricSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={metricSortKey}
                        onChange={setMetricSortKey}
                        options={[
                          { key: 'disparity', label: t('Disparity', 'التفاوت') },
                          { key: 'attribute', label: t('Name', 'الاسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Attribute', 'الخاصية')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Disparity', 'التفاوت')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Risk', 'المخاطر')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Significant?', 'ذو دلالة؟')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Bucketed', 'مُقسّم')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedMetrics.map((m) => (
                          <tr
                            key={m.attribute_column}
                            onMouseEnter={() => setHoveredAttribute(m.attribute_column)}
                            onMouseLeave={() => setHoveredAttribute(null)}
                            className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 align-top ${
                              hoveredAttribute === m.attribute_column ? 'bg-slate-50 dark:bg-navy-800/40' : ''
                            }`}
                          >
                            <td className="px-4 py-2.5">
                              <div className="font-medium text-slate-700 dark:text-slate-300">{m.attribute_column}</div>
                              <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5 max-w-md">{m.interpretation}</div>
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">{m.disparity_ratio.toFixed(2)}x</td>
                            <td className="px-4 py-2.5 text-center">
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${RISK_BADGE[m.risk_level] ?? 'bg-slate-100 text-slate-600'}`}>
                                {m.risk_level}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-center text-xs">
                              {m.statistically_significant === null ? '—' : m.statistically_significant
                                ? <span className="text-red-500 font-semibold">{t('Yes', 'نعم')} (p={m.p_value?.toFixed(3)})</span>
                                : <span className="text-slate-400">{t('No', 'لا')} (p={m.p_value?.toFixed(3)})</span>}
                            </td>
                            <td className="px-4 py-2.5 text-center text-xs text-slate-500 dark:text-slate-400">
                              {m.was_bucketed ? t('Yes', 'نعم') : t('No', 'لا')}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Protected attributes detected */}
                <div className="card overflow-x-auto">
                  <div className="flex items-center justify-between px-4 pt-4 flex-wrap gap-2">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                      {t('Protected Attributes Detected', 'الخصائص المحمية المكتشفة')}
                    </p>
                    <SortToggle<AttributeSortKey>
                      label={t('Sort:', 'ترتيب:')}
                      active={attrSortKey}
                      onChange={setAttrSortKey}
                      options={[
                        { key: 'confidence', label: t('Confidence', 'الثقة') },
                        { key: 'name', label: t('Name', 'الاسم') },
                      ]}
                    />
                  </div>
                  <table className="w-full text-sm mt-2">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Column', 'العمود')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Type', 'النوع')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Confidence', 'الثقة')}</th>
                        <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Small Group?', 'مجموعة صغيرة؟')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedAttributes.map((a) => (
                        <tr key={a.column_name} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                          <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{a.column_name}</td>
                          <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400 capitalize">{a.attribute_type}</td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{(a.detection_confidence * 100).toFixed(0)}%</td>
                          <td className="px-4 py-2.5 text-center">
                            {a.representation_warning
                              ? <AlertTriangle size={14} className="text-amber-500 inline" />
                              : <CheckCircle2 size={14} className="text-slate-300 dark:text-slate-600 inline" />}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Granularity/bucketing/exclusion disclosure — never silent */}
                {ba.granularity_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Data granularity notes', 'ملاحظات دقة البيانات')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {ba.granularity_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {/* Confidence governance */}
                {er.governance.length > 0 && (
                  <div className="card p-4 space-y-3">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">
                      {t('Prediction Confidence Governance', 'حوكمة موثوقية التنبؤ')}
                    </p>
                    {er.governance.map((g, i) => (
                      <div key={i} className="flex flex-wrap items-center gap-3 text-xs">
                        <span className="px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-medium">
                          {g.prediction_type}
                        </span>
                        <span className={`px-2 py-1 rounded font-semibold ${
                          g.confidence_band === 'High' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                          : g.confidence_band === 'Moderate' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                          : g.confidence_band === 'Low' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {g.confidence_band} ({(g.governed_confidence * 100).toFixed(0)}%)
                        </span>
                        {!g.display_allowed && (
                          <span className="text-red-600 dark:text-red-400">{g.suppression_reason}</span>
                        )}
                        {g.caveats.map((c, ci) => (
                          <span key={ci} className="text-slate-500 dark:text-slate-400">{c}</span>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* Ethical disclaimer — always rendered, never dropped */}
                <StatusBanner tone="neutral">{ba.ethical_disclaimer}</StatusBanner>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}
