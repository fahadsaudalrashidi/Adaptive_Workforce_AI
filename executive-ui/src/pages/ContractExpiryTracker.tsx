/**
 * Contract Expiry & Renewal Monitoring — Phase 18.
 *
 * Real analysis only: uploads a file to POST /api/local/contract-expiry
 * (backend/core/contract_expiry_engine.py) and renders whatever the backend
 * actually computed. A genuinely new domain for this platform (contract/
 * Iqama lifecycle tracking): ContractEndDate and IqamaExpiry are two
 * distinct signals, detected and tiered independently, never merged.
 *
 * Two cross-links, computed at the route layer on the SAME upload (this
 * page never combines them itself — see local_analysis_routes.py's
 * /contract-expiry route):
 *   - Succession: high-readiness employee with contract OR Iqama expiring
 *     within the cross-link horizon.
 *   - Nitaqat: non-Saudi employee with Iqama expiring within the horizon
 *     (Iqama only — a direct legal work-authorization signal).
 *
 * NON-NEGOTIABLE: this page NEVER claims to be legal or immigration advice.
 * Urgency tiers are this platform's own illustrative planning heuristic —
 * see contract_expiry_engine.py's module docstring.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, CalendarClock, RefreshCw, Users, AlertOctagon, Flag, ShieldAlert,
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
import { LatinText } from '../components/shared/LatinText'
import { EmployeeSearchInput } from '../components/shared/EmployeeSearchInput'
import { DepartmentBarChart } from '../components/shared/DepartmentBarChart'
import { useSortableTable } from '../hooks/useSortableTable'
import { useEmployeeSearch } from '../hooks/useEmployeeSearch'
import type { StatusTone } from '../styles/design-tokens'

interface ExpiryCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  signal_type: 'contract' | 'iqama'
  expiry_date: string
  days_remaining: number
  urgency_tier: string
  urgency_tier_label_en: string
  urgency_tier_label_ar: string
}

interface DepartmentExpiryBreakdown {
  department: string
  signal_type: 'contract' | 'iqama'
  n_total: number
  n_overdue: number
  n_critical_0_30: number
  n_urgent_31_60: number
}

interface ContractExpiry {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  contract_end_column: string | null
  iqama_expiry_column: string | null
  n_employees_total: number
  n_contract_records_valid: number
  n_iqama_records_valid: number
  n_invalid_dates_excluded: number
  date_quality_warnings: string[]
  contract_tier_counts: Record<string, number>
  iqama_tier_counts: Record<string, number>
  tier_labels_en: Record<string, string>
  tier_labels_ar: Record<string, string>
  candidates: ExpiryCandidate[]
  department_breakdown: DepartmentExpiryBreakdown[]
  department_normalization_notes: string[]
  narrative_en: string
  narrative_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

interface SuccessionCrossLink {
  available: boolean
  reason?: string
  n_high_readiness_with_expiring_signal?: number
  n_high_readiness_total?: number
  horizon_days?: number
  narrative_en?: string
  narrative_ar?: string
}

interface NitaqatCrossLink {
  available: boolean
  reason?: string
  n_non_saudi_with_expiring_iqama?: number
  n_non_saudi_total?: number
  horizon_days?: number
  narrative_en?: string
  narrative_ar?: string
}

interface ApiResponse {
  filename: string
  row_count?: number
  data_quality_warnings?: string[]
  contract_expiry: ContractExpiry
  succession_cross_link?: SuccessionCrossLink
  nitaqat_cross_link?: NitaqatCrossLink
}

const UPLOAD_TIMEOUT_MS = 30_000

const COLUMN_LABELS_EN: Record<string, string> = {
  contract_end_date: 'Contract end date (e.g. ContractEndDate, ContractExpiry)',
  iqama_or_visa_expiry: 'Iqama / visa expiry date (e.g. IqamaExpiry, VisaExpiryDate)',
  department: 'Department (optional — enables department-level rollup)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  contract_end_date: 'تاريخ انتهاء العقد (مثال: ContractEndDate)',
  iqama_or_visa_expiry: 'تاريخ انتهاء الإقامة / التأشيرة (مثال: IqamaExpiry)',
  department: 'القسم (اختياري — يفعّل التجميع حسب القسم)',
}

const TIER_TONE: Record<string, StatusTone> = {
  overdue: 'critical',
  critical_0_30: 'critical',
  urgent_31_60: 'caution',
  upcoming_61_90: 'informational',
  monitored_90_plus: 'neutral',
}

type SortKey = 'urgency' | 'department' | 'signal'

export function ContractExpiryTracker() {
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

      const response = await fetch('/api/local/contract-expiry', {
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

  const ce = result?.contract_expiry
  const successionCrossLink = result?.succession_cross_link
  const nitaqatCrossLink = result?.nitaqat_cross_link
  const duplicateWarnings = result?.data_quality_warnings?.filter(w => w.includes('duplicate row')) ?? []

  const TIER_ORDER = ['overdue', 'critical_0_30', 'urgent_31_60', 'upcoming_61_90', 'monitored_90_plus']
  const { sorted: sortedCandidates, sortKey, setSortKey } = useSortableTable<ExpiryCandidate, SortKey>(
    ce?.candidates ?? [],
    {
      urgency: (a, b) => TIER_ORDER.indexOf(a.urgency_tier) - TIER_ORDER.indexOf(b.urgency_tier) || a.days_remaining - b.days_remaining,
      department: (a, b) => (a.department ?? '').localeCompare(b.department ?? ''),
      signal: (a, b) => a.signal_type.localeCompare(b.signal_type),
    },
  )
  const { query: candidateSearchQuery, setQuery: setCandidateSearchQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    sortedCandidates,
    useCallback((c: ExpiryCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Contract Expiry & Renewal Monitoring', 'متابعة انتهاء العقود والتجديد')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Contract-end-date and Iqama/visa-expiry tracking, with urgency tiers and cross-links to Succession Readiness and Nitaqat.',
            'متابعة تواريخ انتهاء العقود والإقامة/التأشيرة، مع مستويات إلحاح وروابط مع جاهزية التعاقب ونطاقات.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="informational">
        {ce?.disclaimer_en ?? t(
          'Contract/Iqama expiry tracking is a planning aid based on the expiry dates present in your uploaded data — it is NOT legal or immigration advice. The urgency tiers (≤30 / 31-60 / 61-90 / 90+ days) are this platform\'s own illustrative planning heuristic, not a legally mandated renewal timeline. Qualified HR and legal review is required before any renewal, compliance, or employment action.',
          'متابعة انتهاء العقود/الإقامات أداة إرشادية للتخطيط استناداً إلى تواريخ الانتهاء الموجودة في بياناتك المُحمّلة — وليست استشارة قانونية أو استشارة هجرة. مستويات الإلحاح هي معيار إرشادي داخلي من تصميم هذه المنصة، وليست جدولاً زمنياً قانونياً مُلزماً. تلزم مراجعة متخصصي الموارد البشرية والقانون قبل أي إجراء متعلق بالتجديد أو الامتثال أو التوظيف.'
        )}
      </StatusBanner>

      <StatusBanner tone="informational">
        {t(
          'Upload a workforce dataset with a contract-end-date column (e.g. ContractEndDate) and/or an Iqama/visa-expiry column (e.g. IqamaExpiry) to compute real urgency tiers. These are tracked as two separate signals, never merged. Missing both, this page honestly says so instead of fabricating an expiry date.',
          'حمّل بيانات القوى العاملة التي تحتوي على عمود تاريخ انتهاء العقد (مثال: ContractEndDate) و/أو عمود انتهاء الإقامة/التأشيرة (مثال: IqamaExpiry) لحساب مستويات إلحاح فعلية. تُتابَع هاتان الإشارتان بشكل منفصل ولا تُدمجان أبداً. في حال غياب كليهما، تعرض هذه الصفحة ذلك بصدق بدلاً من افتعال تاريخ انتهاء.'
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
            {t('Analyzing contract & Iqama expiry…', 'جارٍ تحليل انتهاء العقود والإقامات…')}
          </div>
          <SkeletonAnalysis kpiCount={4} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && ce && (
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

            {!ce.available ? (
              <EmptyState
                icon={CalendarClock}
                title={t('Contract/Iqama expiry data not detected in this upload', 'لم يتم اكتشاف بيانات انتهاء العقد/الإقامة في هذا الملف')}
                reason={ce.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={ce.columns_detected}
                columnLabels={Object.fromEntries(
                  Object.keys(ce.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]])
                )}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard
                    label={t('Employees in Upload', 'الموظفون في الملف')}
                    value={ce.n_employees_total.toLocaleString()}
                    icon={Users}
                    iconColor="text-blue-500"
                    iconBg="bg-blue-500/10"
                    animateValue
                    detail={t(
                      `Contract column: ${ce.contract_end_column ?? '—'}. Iqama column: ${ce.iqama_expiry_column ?? '—'}.`,
                      `عمود العقد: ${ce.contract_end_column ?? '—'}. عمود الإقامة: ${ce.iqama_expiry_column ?? '—'}.`
                    )}
                  />
                  <KPICard
                    label={t('Contract: Urgent or Overdue', 'العقد: عاجل أو متأخر')}
                    value={(ce.contract_tier_counts.overdue ?? 0) + (ce.contract_tier_counts.critical_0_30 ?? 0) + (ce.contract_tier_counts.urgent_31_60 ?? 0)}
                    subtitle={t(`of ${ce.n_contract_records_valid} tracked`, `من ${ce.n_contract_records_valid} مُتابَع`)}
                    icon={AlertOctagon}
                    hero
                    animateValue
                    radialPct={ce.n_contract_records_valid > 0 ? (100 * ((ce.contract_tier_counts.overdue ?? 0) + (ce.contract_tier_counts.critical_0_30 ?? 0) + (ce.contract_tier_counts.urgent_31_60 ?? 0)) / ce.n_contract_records_valid) : undefined}
                    radialColor="#dc2626"
                    detail={t('Within 60 days (urgent or overdue) — ≤30/31-60/61-90/90+ day tiers.', 'ضمن 60 يوماً (عاجل أو متأخر) — مستويات ≤30/31-60/61-90/90+ يوماً.')}
                  />
                  <KPICard
                    label={t('Iqama/Visa: Urgent or Overdue', 'الإقامة/التأشيرة: عاجل أو متأخر')}
                    value={(ce.iqama_tier_counts.overdue ?? 0) + (ce.iqama_tier_counts.critical_0_30 ?? 0) + (ce.iqama_tier_counts.urgent_31_60 ?? 0)}
                    subtitle={t(`of ${ce.n_iqama_records_valid} tracked`, `من ${ce.n_iqama_records_valid} مُتابَع`)}
                    icon={ShieldAlert}
                    iconColor="text-amber-500"
                    iconBg="bg-amber-500/10"
                    animateValue
                    detail={t('A separate signal from contract end — legal work-authorization, not employment-relationship end.', 'إشارة منفصلة عن انتهاء العقد — تصريح العمل القانوني، وليس نهاية علاقة التوظيف.')}
                  />
                  <KPICard
                    label={t('Invalid Dates Excluded', 'تواريخ غير صالحة مستبعدة')}
                    value={ce.n_invalid_dates_excluded}
                    subtitle={t('excluded, not guessed', 'مستبعدة وليست مفترضة')}
                    icon={CalendarClock}
                    iconColor="text-slate-400"
                    iconBg="bg-slate-500/10"
                    animateValue
                    detail={t('Unparseable date values are excluded from tiering and disclosed — never guessed.', 'تُستبعد قيم التاريخ غير القابلة للقراءة من التصنيف ويُفصح عنها — لا تُخمَّن أبداً.')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? ce.narrative_ar : ce.narrative_en}
                  </p>
                </div>

                {ce.n_contract_records_valid > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Contract Expiry by Urgency Tier', 'انتهاء العقود حسب مستوى الإلحاح')}</p>
                    <DepartmentBarChart
                      data={TIER_ORDER.map(tier => ({
                        department: isAr ? ce.tier_labels_ar[tier] : ce.tier_labels_en[tier],
                        value: ce.contract_tier_counts[tier] ?? 0,
                        color: (TIER_TONE[tier] === 'critical' ? '#dc2626' : TIER_TONE[tier] === 'caution' ? '#d97706' : TIER_TONE[tier] === 'informational' ? '#3b82f6' : '#64748b'),
                      }))}
                      sortByValue={false}
                      height={200}
                    />
                  </div>
                )}

                {ce.n_iqama_records_valid > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">{t('Iqama/Visa Expiry by Urgency Tier', 'انتهاء الإقامة/التأشيرة حسب مستوى الإلحاح')}</p>
                    <DepartmentBarChart
                      data={TIER_ORDER.map(tier => ({
                        department: isAr ? ce.tier_labels_ar[tier] : ce.tier_labels_en[tier],
                        value: ce.iqama_tier_counts[tier] ?? 0,
                        color: (TIER_TONE[tier] === 'critical' ? '#dc2626' : TIER_TONE[tier] === 'caution' ? '#d97706' : TIER_TONE[tier] === 'informational' ? '#3b82f6' : '#64748b'),
                      }))}
                      sortByValue={false}
                      height={200}
                    />
                  </div>
                )}

                {successionCrossLink && (
                  <div className={`p-4 rounded-xl border ${successionCrossLink.available ? 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800/40' : 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <Flag size={14} className={successionCrossLink.available ? 'text-emerald-500' : 'text-slate-400'} />
                      <p className={`text-xs font-semibold ${successionCrossLink.available ? 'text-emerald-700 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400'}`}>
                        {t('Succession Readiness Cross-Link', 'الربط مع جاهزية التعاقب')}
                      </p>
                    </div>
                    {successionCrossLink.available ? (
                      <p className="text-xs text-emerald-700 dark:text-emerald-400">{isAr ? successionCrossLink.narrative_ar : successionCrossLink.narrative_en}</p>
                    ) : (
                      <p className="text-xs text-slate-500 dark:text-slate-400">{successionCrossLink.reason}</p>
                    )}
                  </div>
                )}

                {nitaqatCrossLink && (
                  <div className={`p-4 rounded-xl border ${nitaqatCrossLink.available ? 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800/40' : 'bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <ShieldAlert size={14} className={nitaqatCrossLink.available ? 'text-amber-500' : 'text-slate-400'} />
                      <p className={`text-xs font-semibold ${nitaqatCrossLink.available ? 'text-amber-700 dark:text-amber-400' : 'text-slate-500 dark:text-slate-400'}`}>
                        {t('Nitaqat Iqama Compliance Cross-Link', 'الربط مع امتثال الإقامة (نطاقات)')}
                      </p>
                    </div>
                    {nitaqatCrossLink.available ? (
                      <p className="text-xs text-amber-700 dark:text-amber-400">{isAr ? nitaqatCrossLink.narrative_ar : nitaqatCrossLink.narrative_en}</p>
                    ) : (
                      <p className="text-xs text-slate-500 dark:text-slate-400">{nitaqatCrossLink.reason}</p>
                    )}
                  </div>
                )}

                {ce.candidates.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-between px-4 pt-3 flex-wrap gap-2">
                      <EmployeeSearchInput
                        value={candidateSearchQuery}
                        onChange={setCandidateSearchQuery}
                        placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
                        resultCount={filteredCandidates.length}
                        totalCount={sortedCandidates.length}
                      />
                      <SortToggle<SortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'urgency', label: t('Urgency', 'الإلحاح') },
                          { key: 'department', label: t('Department', 'القسم') },
                          { key: 'signal', label: t('Signal', 'الإشارة') },
                        ]}
                      />
                    </div>
                    {!ce.candidates.some(c => c.record_id_safe.startsWith('EMP-')) && (
                      <p className="px-4 pt-2 text-[11px] text-slate-400 dark:text-slate-500">
                        {t('No employee identifier column detected in this upload — rows are numbered for reference only.', 'لم يتم اكتشاف عمود معرّف موظف في هذا الملف — الصفوف مُرقّمة للمرجعية فقط.')}
                      </p>
                    )}
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'معرّف الموظف')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Signal', 'الإشارة')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Expiry Date', 'تاريخ الانتهاء')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Days Remaining', 'الأيام المتبقية')}</th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">{t('Urgency', 'الإلحاح')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredCandidates.length === 0 && (
                          <tr><td colSpan={6} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
                        )}
                        {filteredCandidates.map((c, i) => (
                          <tr key={`${c.record_id_safe}-${c.signal_type}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 align-top">
                            <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText></td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">
                              {c.signal_type === 'contract' ? t('Contract', 'العقد') : t('Iqama/Visa', 'الإقامة/التأشيرة')}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-slate-600 dark:text-slate-400">{c.expiry_date}</td>
                            <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">
                              {c.days_remaining}
                            </td>
                            <td className="px-4 py-2.5 text-center">
                              <StatusBadge tone={TIER_TONE[c.urgency_tier] ?? 'neutral'}>
                                {isAr ? c.urgency_tier_label_ar : c.urgency_tier_label_en}
                              </StatusBadge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {ce.date_quality_warnings.length > 0 && (
                  <StatusBanner tone="caution" compact>
                    <ul className="space-y-0.5">
                      {ce.date_quality_warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                {ce.department_normalization_notes.length > 0 && (
                  <StatusBanner tone="informational" compact>
                    <p className="font-semibold">{t('Department names normalized', 'تم توحيد أسماء الأقسام')}</p>
                    <ul className="space-y-0.5 mt-1">
                      {ce.department_normalization_notes.map((n, i) => <li key={i}>· {n}</li>)}
                    </ul>
                  </StatusBanner>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{ce.governance_note}</p>
                  {ce.sources.length > 0 && (
                    <>
                      <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                        {t('Sources', 'المصادر')}
                      </p>
                      <ul className="text-[11px] opacity-70 space-y-0.5">
                        {ce.sources.map((s, i) => <li key={i}>· {s}</li>)}
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
