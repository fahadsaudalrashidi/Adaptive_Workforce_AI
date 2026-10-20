/**
 * Saudi Labor Law Calculators — Phase 21.
 *
 * Three related calculators grouped under one page rather than three
 * separate nav entries: End-of-Service Gratuity, WPS/Payroll Consistency,
 * and Leave Balance & Compensation share the same upload, the same strict
 * numeric-salary discipline, and the same "real legal payment, not an
 * illustrative estimate" framing — splitting them into three pages would
 * mean re-uploading the same file three times and repeating the same
 * disclaimer three times. A tab switcher keeps them visually distinct
 * while sharing one upload flow (three parallel API calls on select).
 *
 * NON-NEGOTIABLE, stated more prominently here than on any other module's
 * page: End-of-Service Gratuity and Leave Compensation are REAL legally-owed
 * amounts, not planning estimates — so unlike Overtime Cost Intelligence or
 * Sector Benchmarking elsewhere on this platform, this module NEVER
 * substitutes a benchmark or range-text-midpoint salary. If the uploaded
 * salary/years-of-service values aren't clean numbers, the honest
 * "not available" state renders instead of an approximated legal figure.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, Scale, RefreshCw, Users, Wallet, ShieldAlert, CalendarClock,
  AlertTriangle, CheckCircle2,
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
import { useEmployeeSearch } from '../hooks/useEmployeeSearch'

// ── Types ────────────────────────────────────────────────────────────────

interface GratuityCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  years_of_service: number
  monthly_wage_sar: number
  separation_type: string | null
  gratuity_full_award_sar: number
  gratuity_if_resignation_sar: number
  applicable_amount_sar: number
  applicable_scenario: string
  article_80_reduced_award_sar: number | null
}
interface DepartmentGratuityBreakdown {
  department: string
  n_employees: number
  total_full_award_sar: number
  total_if_resignation_sar: number
}
interface GratuityResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  salary_column: string | null
  years_of_service_column: string | null
  separation_type_column: string | null
  n_employees_total: number
  n_valid_computed: number
  n_excluded_invalid_salary: number
  n_excluded_invalid_years: number
  candidates: GratuityCandidate[]
  n_candidates_truncated: number
  department_breakdown: DepartmentGratuityBreakdown[]
  narrative_en: string
  narrative_ar: string
  numeric_salary_required_note_en: string
  numeric_salary_required_note_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

interface WpsMismatchCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  mismatch_type: string
  expected_sar: number
  actual_sar: number
  difference_sar: number
}
interface WpsResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  check_applicable: boolean
  basic_salary_column: string | null
  actual_salary_column: string | null
  allowances_column: string | null
  n_employees_checked: number
  n_mismatches: number
  mismatch_rate_pct: number | null
  candidates: WpsMismatchCandidate[]
  narrative_en: string
  narrative_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

interface LeaveCandidate {
  record_id_safe: string
  employee_id_raw: string | null
  department: string | null
  years_of_service: number
  cumulative_entitlement_days: number
  leave_balance_days: number | null
  monthly_wage_sar: number | null
  compensation_sar: number | null
}
interface LeaveResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  years_of_service_column: string | null
  salary_column: string | null
  leave_balance_column: string | null
  leave_taken_column: string | null
  has_real_balance_data: boolean
  n_employees_total: number
  n_valid_computed: number
  candidates: LeaveCandidate[]
  department_breakdown: { department: string; n_employees: number; total_entitlement_days: number; total_compensation_sar: number | null }[]
  narrative_en: string
  narrative_ar: string
  numeric_salary_required_note_en: string
  numeric_salary_required_note_ar: string
  disclaimer_en: string
  disclaimer_ar: string
  governance_note: string
  sources: string[]
}

const COLUMN_LABELS_EN: Record<string, string> = {
  salary: 'Exact numeric salary (required — no range-text)',
  years_of_service: 'Years of service at this company',
  separation_type: 'Separation type (optional — resignation/termination)',
  department: 'Department (optional)',
  basic_or_contract_salary: 'Contract / basic salary column',
  actual_or_total_salary: 'Actual paid / net / total salary column',
  allowances: 'Allowances (optional — enables 3-way reconciliation)',
  leave_balance: 'Leave balance (optional)',
  leave_taken: 'Leave taken (optional)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  salary: 'راتب رقمي دقيق (مطلوب — بدون نص نطاق)',
  years_of_service: 'سنوات الخدمة في هذه الشركة',
  separation_type: 'نوع الانفصال (اختياري — استقالة/إنهاء)',
  department: 'القسم (اختياري)',
  basic_or_contract_salary: 'عمود الراتب التعاقدي/الأساسي',
  actual_or_total_salary: 'عمود الراتب الفعلي/الصافي/الإجمالي',
  allowances: 'البدلات (اختياري — يُفعّل التسوية الثلاثية)',
  leave_balance: 'رصيد الإجازات (اختياري)',
  leave_taken: 'الإجازات المستخدمة (اختياري)',
}

const UPLOAD_TIMEOUT_MS = 30_000

// Gratuity, WPS, and Leave Balance are real legally-owed SAR amounts, not
// illustrative estimates — unlike other modules' K-abbreviated figures,
// these must display at the exact precision a user can verify against
// their own reference calculation, so no K-rounding here.
function sar(n: number): string {
  return `SAR ${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

type TabKey = 'gratuity' | 'wps' | 'leave'

export function SaudiLaborLawCalculators() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [tab, setTab] = useState<TabKey>('gratuity')
  const [filename, setFilename] = useState<string>('')
  const [rowCount, setRowCount] = useState<number | undefined>(undefined)
  const [gratuity, setGratuity] = useState<GratuityResult | null>(null)
  const [wps, setWps] = useState<WpsResult | null>(null)
  const [leave, setLeave] = useState<LeaveResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const runUpload = useCallback(async (file: File) => {
    setStatus('loading')
    setError(null)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)

    try {
      const endpoints = [
        '/api/local/gratuity-calculator',
        '/api/local/wps-consistency-check',
        '/api/local/leave-balance-calculator',
      ]
      const responses = await Promise.all(endpoints.map(url => {
        const formData = new FormData()
        formData.append('file', file)
        return fetch(url, { method: 'POST', body: formData, signal: controller.signal })
      }))
      clearTimeout(timeoutId)

      for (const res of responses) {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data?.detail || `Server error (${res.status})`)
        }
      }
      const [gratuityData, wpsData, leaveData] = await Promise.all(responses.map(r => r.json()))

      setFilename(gratuityData.filename)
      setRowCount(gratuityData.row_count)
      setGratuity(gratuityData.gratuity)
      setWps(wpsData.wps_consistency)
      setLeave(leaveData.leave_balance)
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
    setGratuity(null); setWps(null); setLeave(null)
    setError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Saudi Labor Law Calculators', 'حاسبات نظام العمل السعودي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'End-of-Service Gratuity, WPS/Payroll Consistency, and Leave Balance & Compensation.',
            'مكافأة نهاية الخدمة، اتساق الرواتب (نظام حماية الأجور)، ورصيد الإجازات وتعويضها.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="critical">
        <div className="flex items-start gap-2">
          <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
          <span>
            {t(
              'These figures compute REAL amounts owed under Saudi Labor Law — they are NOT illustrative planning estimates like other modules on this platform. This module NEVER substitutes a benchmark or range-text-midpoint salary for a real legal payment figure: if your salary or years-of-service column cannot be read as an exact number, the affected figures render as "not available" rather than an approximation. This is a computational aid for HR planning, not a substitute for qualified legal/HR review before any actual payment or compliance action.',
              'تحتسب هذه الأرقام مبالغ حقيقية مستحقة بموجب نظام العمل السعودي — وهي ليست تقديرات تخطيطية إرشادية كباقي وحدات هذه المنصة. لا تستبدل هذه الوحدة أبداً راتباً تقديرياً أو معيارياً بمبلغ قانوني حقيقي: إذا تعذّرت قراءة عمود الراتب أو سنوات الخدمة كرقم دقيق، تُعرض الأرقام المتأثرة كـ"غير متاحة" بدلاً من تقديرها. هذه أداة حسابية مساعدة لتخطيط الموارد البشرية، وليست بديلاً عن المراجعة القانونية المتخصصة.'
            )}
          </span>
        </div>
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
              {t('One upload computes all three calculators below.', 'تحميل واحد يحسب الحاسبات الثلاث أدناه.')}
            </p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Computing gratuity, WPS consistency, and leave figures…', 'جارٍ احتساب المكافأة واتساق الرواتب والإجازات…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && gratuity && wps && leave && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">
                {filename} · {rowCount?.toLocaleString()} {t('rows', 'صفوف')}
              </span>
              <button
                onClick={reset}
                className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1"
              >
                <RefreshCw size={12} />
                {t('Analyze another file', 'تحليل ملف آخر')}
              </button>
            </div>

            <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700">
              {([
                ['gratuity', t('End-of-Service Gratuity', 'مكافأة نهاية الخدمة'), Wallet],
                ['wps', t('WPS Consistency', 'اتساق الرواتب'), ShieldAlert],
                ['leave', t('Leave Balance', 'رصيد الإجازات'), CalendarClock],
              ] as [TabKey, string, typeof Wallet][]).map(([key, label, Icon]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    tab === key
                      ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>

            {tab === 'gratuity' && <GratuityTab data={gratuity} t={t} isAr={isAr} />}
            {tab === 'wps' && <WpsTab data={wps} t={t} isAr={isAr} />}
            {tab === 'leave' && <LeaveTab data={leave} t={t} isAr={isAr} />}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}

// ── Gratuity tab ─────────────────────────────────────────────────────────

function GratuityTab({ data, t, isAr }: { data: GratuityResult; t: (en: string, ar: string) => string; isAr: boolean }) {
  const { query, setQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    data.candidates,
    useCallback((c: GratuityCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )
  if (!data.available) {
    return (
      <EmptyState
        icon={Wallet}
        title={t('Gratuity calculation not available', 'حساب المكافأة غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>{isAr ? data.numeric_salary_required_note_ar : data.numeric_salary_required_note_en}</StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
        <KPICard label={t('Employees Computed', 'الموظفون المُحتسبون')} value={data.n_valid_computed} subtitle={t(`of ${data.n_employees_total} total`, `من ${data.n_employees_total} إجمالاً`)} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
        <KPICard label={t('Excluded (Bad Salary)', 'مستبعد (راتب غير صالح)')} value={data.n_excluded_invalid_salary} icon={AlertTriangle} iconColor="text-amber-500" iconBg="bg-amber-500/10" animateValue />
        <KPICard label={t('Total Full-Award Exposure', 'إجمالي المكافأة الكاملة')} value={sar(data.department_breakdown.reduce((s, d) => s + d.total_full_award_sar, 0))} icon={Scale} hero animateValue />
        <KPICard label={t('Separation Type', 'نوع الانفصال')} value={data.separation_type_column ?? t('Not detected', 'غير مكتشف')} icon={CheckCircle2} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" detail={t('Both scenarios shown per employee when not specified.', 'يُعرض كلا السيناريوهين لكل موظف عند عدم التحديد.')} />
      </div>
      <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? data.narrative_ar : data.narrative_en}</p></div>
      {data.candidates.some(c => c.separation_type === 'termination_for_cause_article_80') && (
        <StatusBanner tone="critical">
          {t(
            'One or more employees have an Article 80 (for-cause dismissal) separation type. The "Full Award" column is still shown as the applicable figure — it is NEVER auto-reduced by this platform. "If Article 80 Applies" shows the possible forfeiture amount (SAR 0 under 5 years of service, half the full award at 5+ years) for reference only. This provision is sourced from secondary law-firm summaries, not a directly-quoted statute excerpt like Articles 84/85, and actual forfeiture requires verified compliance with Article 80\'s specific grounds and procedure that this platform cannot confirm from a text label alone — confirm with qualified legal counsel before withholding any gratuity on this basis.',
            'لدى موظف واحد أو أكثر نوع انفصال يشير إلى المادة 80 (الفصل التأديبي). يظل عمود "المكافأة الكاملة" هو الرقم المُطبَّق — لا تُخفّضه هذه المنصة تلقائياً أبداً. يعرض عمود "حال سريان المادة 80" مبلغ الإسقاط المحتمل (صفر ريال لمن لديهم أقل من 5 سنوات خدمة، ونصف المكافأة الكاملة لمن لديهم 5 سنوات فأكثر) للمرجعية فقط. هذا الحكم مصدره ملخصات قانونية ثانوية، وليس نصاً نظامياً مقتبساً مباشرة كالمادتين 84 و85، ويتطلب الإسقاط الفعلي التحقق من استيفاء الشروط والإجراءات المحددة في المادة 80 التي لا يمكن لهذه المنصة تأكيدها من تصنيف نصي فقط — يرجى استشارة مستشار قانوني مؤهل قبل حجب أي مكافأة على هذا الأساس.'
          )}
        </StatusBanner>
      )}
      {data.candidates.length > 0 && (
        <div className="card overflow-x-auto">
          <NoIdentifierNote candidates={data.candidates} t={t} />
          <div className="flex items-center justify-end px-4 pt-3">
            <EmployeeSearchInput
              value={query}
              onChange={setQuery}
              placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
              resultCount={filteredCandidates.length}
              totalCount={data.candidates.length}
            />
          </div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'معرّف الموظف')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Years', 'السنوات')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Wage', 'الراتب')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Separation', 'الانفصال')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Full Award', 'المكافأة الكاملة')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('If Resignation', 'حال الاستقالة')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('If Article 80 Applies', 'حال سريان المادة 80')}</th>
            </tr></thead>
            <tbody>
              {filteredCandidates.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
              )}
              {filteredCandidates.map((c, i) => (
                <tr key={`${c.record_id_safe}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText></td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.years_of_service}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.monthly_wage_sar)}</td>
                  <td className="px-4 py-2.5">
                    {c.separation_type === 'resignation' ? <StatusBadge tone="caution">{t('Resignation', 'استقالة')}</StatusBadge>
                      : c.separation_type === 'termination_for_cause_article_80' ? <StatusBadge tone="critical">{t('Art. 80 (for cause)', 'المادة 80 (تأديبي)')}</StatusBadge>
                      : c.separation_type === 'employer_termination_or_end_of_contract' ? <StatusBadge tone="informational">{t('Termination', 'إنهاء')}</StatusBadge>
                      : <StatusBadge tone="neutral">{t('Unspecified', 'غير محدد')}</StatusBadge>}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{sar(c.gratuity_full_award_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.gratuity_if_resignation_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.article_80_reduced_award_sar != null ? sar(c.article_80_reduced_award_sar) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <SourcesBanner sources={data.sources} governanceNote={data.governance_note} t={t} />
    </div>
  )
}

// ── WPS tab ──────────────────────────────────────────────────────────────

function WpsTab({ data, t, isAr }: { data: WpsResult; t: (en: string, ar: string) => string; isAr: boolean }) {
  const { query, setQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    data.candidates,
    useCallback((c: WpsMismatchCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )
  if (!data.available || !data.check_applicable) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title={data.check_applicable ? t('WPS check not available', 'فحص اتساق الرواتب غير متاح') : t('WPS check not applicable to this dataset', 'فحص اتساق الرواتب غير قابل للتطبيق على هذه البيانات')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      <StatusBanner tone="informational" compact>
        {t('This checks internal consistency within your uploaded file only — it does NOT verify against live Qiwa, Mudad, or GOSI records. Confirm actual WPS compliance via those official platforms.', 'يفحص هذا اتساق البيانات داخلياً ضمن ملفك المُحمّل فقط — ولا يتحقق من سجلات قوى أو مدد أو التأمينات الاجتماعية (GOSI) الفعلية. تحقق من الامتثال الفعلي عبر تلك المنصات الرسمية.')}
      </StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Employees Checked', 'الموظفون المفحوصون')} value={data.n_employees_checked} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
        <KPICard label={t('Mismatches Found', 'حالات عدم الاتساق')} value={data.n_mismatches} subtitle={t(`${data.mismatch_rate_pct}% of checked`, `${data.mismatch_rate_pct}% من المفحوصين`)} icon={AlertTriangle} hero animateValue radialPct={data.mismatch_rate_pct ?? undefined} radialColor={data.n_mismatches > 0 ? '#dc2626' : '#059669'} />
        <KPICard label={t('Columns Compared', 'الأعمدة المُقارَنة')} value={`${data.basic_salary_column} vs ${data.actual_salary_column}`} icon={ShieldAlert} iconColor="text-amber-500" iconBg="bg-amber-500/10" />
      </div>
      <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? data.narrative_ar : data.narrative_en}</p></div>
      {data.candidates.length > 0 && (
        <div className="card overflow-x-auto">
          <NoIdentifierNote candidates={data.candidates} t={t} />
          <div className="flex items-center justify-end px-4 pt-3">
            <EmployeeSearchInput
              value={query}
              onChange={setQuery}
              placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
              resultCount={filteredCandidates.length}
              totalCount={data.candidates.length}
            />
          </div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'معرّف الموظف')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Type', 'النوع')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Expected', 'المتوقع')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Actual', 'الفعلي')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Difference', 'الفرق')}</th>
            </tr></thead>
            <tbody>
              {filteredCandidates.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
              )}
              {filteredCandidates.map((c, i) => (
                <tr key={`${c.record_id_safe}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText></td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400 text-xs">{c.mismatch_type === 'base_plus_allowances_vs_total' ? t('Base+Allowances vs Total', 'أساسي+بدلات مقابل إجمالي') : t('Contract vs Actual', 'تعاقدي مقابل فعلي')}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.expected_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{sar(c.actual_sar)}</td>
                  <td className="px-4 py-2.5 text-right font-mono font-medium text-red-600 dark:text-red-400">{c.difference_sar > 0 ? '+' : ''}{sar(c.difference_sar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <SourcesBanner sources={data.sources} governanceNote={data.governance_note} t={t} />
    </div>
  )
}

// ── Leave tab ────────────────────────────────────────────────────────────

function LeaveTab({ data, t, isAr }: { data: LeaveResult; t: (en: string, ar: string) => string; isAr: boolean }) {
  const { query, setQuery, filteredRows: filteredCandidates } = useEmployeeSearch(
    data.candidates,
    useCallback((c: LeaveCandidate) => [c.employee_id_raw, c.record_id_safe], [])
  )
  if (!data.available) {
    return (
      <EmptyState
        icon={CalendarClock}
        title={t('Leave balance calculation not available', 'حساب رصيد الإجازات غير متاح')}
        reason={data.reason ?? ''}
        checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
        columnsDetected={data.columns_detected}
        columnLabels={Object.fromEntries(Object.keys(data.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
      />
    )
  }
  return (
    <div className="space-y-5">
      {!data.has_real_balance_data && (
        <StatusBanner tone="caution" compact>
          {t('No leave-balance or leave-taken column detected — figures below are CUMULATIVE ENTITLEMENT ACCRUED since hire, not the actual remaining balance. No compensation figure is computed.', 'لم يتم اكتشاف عمود رصيد إجازات أو إجازات مستخدمة — الأرقام أدناه هي الاستحقاق التراكمي منذ التوظيف، وليست الرصيد الفعلي المتبقي. لا يُحتسب مبلغ تعويض.')}
        </StatusBanner>
      )}
      <StatusBanner tone="informational" compact>{isAr ? data.numeric_salary_required_note_ar : data.numeric_salary_required_note_en}</StatusBanner>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
        <KPICard label={t('Employees Computed', 'الموظفون المُحتسبون')} value={data.n_valid_computed} subtitle={t(`of ${data.n_employees_total} total`, `من ${data.n_employees_total} إجمالاً`)} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
        <KPICard label={t('Data Type', 'نوع البيانات')} value={data.has_real_balance_data ? t('Real Balance', 'رصيد فعلي') : t('Entitlement Only', 'استحقاق فقط')} icon={CalendarClock} hero />
        <KPICard label={t('Total Compensation Exposure', 'إجمالي التعويض')} value={sar(data.department_breakdown.reduce((s, d) => s + (d.total_compensation_sar ?? 0), 0))} icon={Wallet} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" />
      </div>
      <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? data.narrative_ar : data.narrative_en}</p></div>
      {data.candidates.length > 0 && (
        <div className="card overflow-x-auto">
          <NoIdentifierNote candidates={data.candidates} t={t} />
          <div className="flex items-center justify-end px-4 pt-3">
            <EmployeeSearchInput
              value={query}
              onChange={setQuery}
              placeholder={t('Search employee ID…', 'بحث برقم الموظف…')}
              resultCount={filteredCandidates.length}
              totalCount={data.candidates.length}
            />
          </div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'معرّف الموظف')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Years', 'السنوات')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Entitlement (days)', 'الاستحقاق (أيام)')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Balance (days)', 'الرصيد (أيام)')}</th>
              <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Compensation', 'التعويض')}</th>
            </tr></thead>
            <tbody>
              {filteredCandidates.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-xs text-slate-400 dark:text-slate-500">{t('No employees match your search.', 'لا يوجد موظفون مطابقون لبحثك.')}</td></tr>
              )}
              {filteredCandidates.map((c, i) => (
                <tr key={`${c.record_id_safe}-${i}`} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{c.employee_id_raw ?? c.record_id_safe}</LatinText></td>
                  <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{c.department ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.years_of_service}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.cumulative_entitlement_days}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{c.leave_balance_days ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right font-mono font-medium text-slate-700 dark:text-slate-300">{c.compensation_sar != null ? sar(c.compensation_sar) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <SourcesBanner sources={data.sources} governanceNote={data.governance_note} t={t} />
    </div>
  )
}

function NoIdentifierNote({ candidates, t }: { candidates: { record_id_safe: string }[]; t: (en: string, ar: string) => string }) {
  if (candidates.some(c => c.record_id_safe.startsWith('EMP-'))) return null
  return (
    <p className="px-4 pt-2 text-[11px] text-slate-400 dark:text-slate-500">
      {t('No employee identifier column detected in this upload — rows are numbered for reference only.', 'لم يتم اكتشاف عمود معرّف موظف في هذا الملف — الصفوف مُرقّمة للمرجعية فقط.')}
    </p>
  )
}

function SourcesBanner({ sources, governanceNote, t }: { sources: string[]; governanceNote: string; t: (en: string, ar: string) => string }) {
  return (
    <StatusBanner tone="neutral">
      <p className="mb-2">{governanceNote}</p>
      {sources.length > 0 && (
        <>
          <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">{t('Sources', 'المصادر')}</p>
          <ul className="text-[11px] opacity-70 space-y-0.5">{sources.map((s, i) => <li key={i}>· {s}</li>)}</ul>
        </>
      )}
    </StatusBanner>
  )
}
