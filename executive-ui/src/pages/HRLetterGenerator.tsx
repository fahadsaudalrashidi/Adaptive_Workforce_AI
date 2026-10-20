/**
 * Automated HR Letter Generator — Phase 36.
 *
 * Deliberately different from every other module on this platform: its
 * entire purpose is to produce real, NAMED, official Word documents
 * (Salary Certificate, Employment Certificate, and a real-computed
 * End-of-Service Settlement letter cross-linked to the Saudi Labor Law
 * Calculators' gratuity engine) — so this page shows real employee names,
 * unlike every anonymized/aggregate view elsewhere. Warning/disciplinary
 * and termination letters are intentionally NOT offered (see the excluded-
 * letter-types note rendered below the upload, and
 * backend/core/hr_letter_generator.py's module docstring for the full
 * reasoning).
 *
 * The upload is kept in React state and RE-SENT with every generate call
 * (single or bulk) — this backend is stateless/no-persistence-by-default,
 * so there is no server-side session to reference an employee by later.
 */
import { useCallback, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, FileText, RefreshCw, Users, AlertTriangle, CheckCircle2,
  Wallet, Briefcase, Scale, Download, Globe2,
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

// ── Types ────────────────────────────────────────────────────────────────

interface EmployeeLetterRecord {
  employee_id: string
  name: string
  job_title: string
  department: string
  hire_date_display: string
  salary_sar: number | null
  salary_raw_display: string | null
  end_of_service_available: boolean
}

interface HrLettersEmployeeResult {
  available: boolean
  reason: string | null
  columns_detected: Record<string, boolean>
  n_total_rows: number
  n_usable: number
  n_excluded_missing_required: number
  n_excluded_invalid_salary: number
  employees: EmployeeLetterRecord[]
  narrative_en: string
  narrative_ar: string
  excluded_letter_types_note_en: string
  excluded_letter_types_note_ar: string
  governance_note: string
}

type LetterType = 'salary_certificate' | 'employment_certificate' | 'end_of_service_settlement'

const COLUMN_LABELS_EN: Record<string, string> = {
  name: 'Employee name',
  employee_id: 'Employee ID',
  job_title: 'Job title',
  department: 'Department',
  hire_date: 'Hire / start date',
  salary: 'Monthly salary (required for Salary Certificate only)',
}
const COLUMN_LABELS_AR: Record<string, string> = {
  name: 'اسم الموظف',
  employee_id: 'الرقم الوظيفي',
  job_title: 'المسمى الوظيفي',
  department: 'القسم',
  hire_date: 'تاريخ التعيين',
  salary: 'الراتب الشهري (مطلوب فقط لخطاب تعريف الراتب)',
}

const LETTER_TYPE_META: Record<LetterType, { icon: typeof FileText; labelEn: string; labelAr: string }> = {
  salary_certificate: { icon: Wallet, labelEn: 'Salary Certificate', labelAr: 'خطاب تعريف بالراتب' },
  employment_certificate: { icon: Briefcase, labelEn: 'Employment Certificate', labelAr: 'خطاب تعريف بالعمل' },
  end_of_service_settlement: { icon: Scale, labelEn: 'End-of-Service Settlement', labelAr: 'تسوية نهاية الخدمة' },
}

const UPLOAD_TIMEOUT_MS = 30_000
const GENERATE_TIMEOUT_MS = 60_000

function sar(n: number): string {
  return `SAR ${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

function letterAvailableFor(letterType: LetterType, emp: EmployeeLetterRecord): boolean {
  if (letterType === 'salary_certificate') return emp.salary_sar != null
  if (letterType === 'end_of_service_settlement') return emp.end_of_service_available
  return true
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback
  const match = /filename="?([^";]+)"?/.exec(header)
  return match ? match[1] : fallback
}

export function HRLetterGenerator() {
  const { t, isAr } = useLanguage()
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [file, setFile] = useState<File | null>(null)
  const [filename, setFilename] = useState<string>('')
  const [rowCount, setRowCount] = useState<number | undefined>(undefined)
  const [employeeData, setEmployeeData] = useState<HrLettersEmployeeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [letterType, setLetterType] = useState<LetterType>('salary_certificate')
  const [language, setLanguage] = useState<'en' | 'ar'>('en')
  const [companyName, setCompanyName] = useState('')
  const [companyAddress, setCompanyAddress] = useState('')
  const [signatoryName, setSignatoryName] = useState('')
  const [signatoryTitle, setSignatoryTitle] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [generating, setGenerating] = useState<string | null>(null)  // employee_id being generated, or 'bulk'
  const [genError, setGenError] = useState<string | null>(null)
  const [bulkSummary, setBulkSummary] = useState<{ n_generated: number; n_skipped: number; items: { employee_id: string; name: string; generated: boolean; reason: string | null }[] } | null>(null)

  const companyReady = companyName.trim() && companyAddress.trim() && signatoryName.trim() && signatoryTitle.trim()

  // UX safety net only, not validation of truthfulness (see Priority 2 in
  // PHASE_26 report) — obvious placeholder text (e.g. "a", "xx") flows
  // directly into an official-looking document, so a light, non-blocking
  // nudge helps catch accidental test input before generating.
  const shortFieldWarnings = useMemo(() => {
    const fields: [string, string][] = [
      [t('Company name', 'اسم الشركة'), companyName],
      [t('Company address', 'عنوان الشركة'), companyAddress],
      [t('Signatory name', 'اسم المفوّض'), signatoryName],
      [t('Signatory title', 'المسمى الوظيفي للمفوّض'), signatoryTitle],
    ]
    return fields.filter(([, value]) => value.trim().length > 0 && value.trim().length <= 2).map(([label]) => label)
  }, [companyName, companyAddress, signatoryName, signatoryTitle, t])

  const runUpload = useCallback(async (f: File) => {
    setStatus('loading')
    setError(null)
    setBulkSummary(null)
    setGenError(null)

    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS)
    try {
      const formData = new FormData()
      formData.append('file', f)
      const res = await fetch('/api/local/hr-letters/employees', { method: 'POST', body: formData, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      const data = await res.json()
      setFile(f)
      setFilename(data.filename)
      setRowCount(data.row_count)
      setEmployeeData(data.hr_letters)
      setSelected(new Set())
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
    const f = e.target.files?.[0]
    if (f) void runUpload(f)
  }, [runUpload])

  const reset = useCallback(() => {
    setStatus('idle')
    setFile(null)
    setEmployeeData(null)
    setError(null)
    setBulkSummary(null)
    setGenError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }, [])

  const eligibleForType = useMemo(
    () => employeeData?.employees.filter(e => letterAvailableFor(letterType, e)) ?? [],
    [employeeData, letterType]
  )

  const toggleEmployee = useCallback((id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleSelectAllEligible = useCallback(() => {
    setSelected(prev => {
      const allSelected = eligibleForType.length > 0 && eligibleForType.every(e => prev.has(e.employee_id))
      if (allSelected) return new Set()
      return new Set(eligibleForType.map(e => e.employee_id))
    })
  }, [eligibleForType])

  const generateSingle = useCallback(async (emp: EmployeeLetterRecord) => {
    if (!file || !companyReady) return
    setGenerating(emp.employee_id)
    setGenError(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), GENERATE_TIMEOUT_MS)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('employee_id', emp.employee_id)
      formData.append('letter_type', letterType)
      formData.append('language', language)
      formData.append('company_name', companyName)
      formData.append('company_address', companyAddress)
      formData.append('signatory_name', signatoryName)
      formData.append('signatory_title', signatoryTitle)
      const res = await fetch('/api/local/hr-letters/generate-single', { method: 'POST', body: formData, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      const blob = await res.blob()
      const name = filenameFromContentDisposition(res.headers.get('content-disposition'), `${letterType}_${emp.employee_id}.docx`)
      downloadBlob(blob, name)
    } catch (err) {
      const isAbort = err instanceof Error && err.name === 'AbortError'
      setGenError(isAbort ? t('Letter generation timed out.', 'انتهت مهلة إنشاء الخطاب.') : err instanceof Error ? err.message : String(err))
    } finally {
      setGenerating(null)
    }
  }, [file, companyReady, letterType, language, companyName, companyAddress, signatoryName, signatoryTitle, t])

  const generateBulk = useCallback(async () => {
    if (!file || !companyReady || selected.size === 0) return
    setGenerating('bulk')
    setGenError(null)
    setBulkSummary(null)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), GENERATE_TIMEOUT_MS)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('employee_ids', JSON.stringify(Array.from(selected)))
      formData.append('letter_type', letterType)
      formData.append('language', language)
      formData.append('company_name', companyName)
      formData.append('company_address', companyAddress)
      formData.append('signatory_name', signatoryName)
      formData.append('signatory_title', signatoryTitle)
      const res = await fetch('/api/local/hr-letters/generate-bulk', { method: 'POST', body: formData, signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || `Server error (${res.status})`)
      }
      const summaryHeader = res.headers.get('x-hr-letters-summary')
      if (summaryHeader) {
        try {
          const decoded = JSON.parse(atob(summaryHeader))
          setBulkSummary(decoded)
        } catch { /* non-fatal — zip still downloads */ }
      }
      const blob = await res.blob()
      const name = filenameFromContentDisposition(res.headers.get('content-disposition'), `HR_Letters_${letterType}.zip`)
      downloadBlob(blob, name)
    } catch (err) {
      const isAbort = err instanceof Error && err.name === 'AbortError'
      setGenError(isAbort ? t('Bulk generation timed out.', 'انتهت مهلة الإنشاء المجمّع.') : err instanceof Error ? err.message : String(err))
    } finally {
      setGenerating(null)
    }
  }, [file, companyReady, selected, letterType, language, companyName, companyAddress, signatoryName, signatoryTitle])

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Automated HR Letter Generator', 'مولّد خطابات الموارد البشرية الآلي')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Salary Certificate, Employment Certificate, and a real-computed End-of-Service Settlement letter — single or bulk (mail-merge).',
            'خطاب تعريف بالراتب، خطاب تعريف بالعمل، وخطاب تسوية نهاية خدمة برقم محتسب فعلياً — فردي أو مجمّع.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="critical" icon={AlertTriangle}>
        {t(
          'Every letter generated here is a DRAFT that requires human review and an authorized signature before official use. This platform includes real employee names in these documents by necessity — unlike every other module — because that is the entire point of an official letter. It cannot verify that you are authorized to issue official company correspondence.',
          'كل خطاب يُنشأ هنا هو مسودة تتطلب مراجعة بشرية وتوقيعاً من جهة مخوّلة قبل الاستخدام الرسمي. تتضمن هذه الوثائق أسماء موظفين حقيقية بالضرورة — بخلاف كل وحدة أخرى في هذه المنصة — لأن ذلك هو صميم أي خطاب رسمي. لا يمكن لهذه المنصة التحقق من أنك مخوّل بإصدار مراسلات رسمية باسم الشركة.'
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
              {t('Needs Name, Employee ID, Job Title, Department, and Hire Date columns.', 'يتطلب أعمدة الاسم والرقم الوظيفي والمسمى الوظيفي والقسم وتاريخ التعيين.')}
            </p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Reading employee records…', 'جارٍ قراءة سجلات الموظفين…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && <StatusBanner tone="critical">{error}</StatusBanner>}

      <AnimatePresence mode="wait">
        {status === 'done' && employeeData && (
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
                {t('Use another file', 'استخدام ملف آخر')}
              </button>
            </div>

            {!employeeData.available ? (
              <EmptyState
                icon={FileText}
                title={t('No usable employee records found', 'لم يتم العثور على سجلات موظفين قابلة للاستخدام')}
                reason={employeeData.reason ?? ''}
                checklistLabel={t('Columns that would activate this feature', 'الأعمدة التي تُفعّل هذه الميزة')}
                columnsDetected={employeeData.columns_detected}
                columnLabels={Object.fromEntries(Object.keys(employeeData.columns_detected).map(k => [k, isAr ? COLUMN_LABELS_AR[k] : COLUMN_LABELS_EN[k]]))}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                  <KPICard label={t('Usable Employees', 'الموظفون القابلون للاستخدام')} value={employeeData.n_usable} subtitle={t(`of ${employeeData.n_total_rows} total`, `من ${employeeData.n_total_rows} إجمالاً`)} icon={Users} iconColor="text-blue-500" iconBg="bg-blue-500/10" animateValue />
                  <KPICard label={t('Excluded (Missing Field)', 'مستبعد (حقل مفقود)')} value={employeeData.n_excluded_missing_required} icon={AlertTriangle} iconColor="text-amber-500" iconBg="bg-amber-500/10" animateValue />
                  <KPICard label={t('Eligible for Selected Letter', 'مؤهل للخطاب المحدد')} value={eligibleForType.length} icon={CheckCircle2} iconColor="text-emerald-500" iconBg="bg-emerald-500/10" animateValue />
                  <KPICard label={t('Selected for Bulk', 'محدد للإنشاء المجمّع')} value={selected.size} icon={FileText} hero />
                </div>

                <div className="card p-4"><p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{isAr ? employeeData.narrative_ar : employeeData.narrative_en}</p></div>

                <StatusBanner tone="neutral">
                  {isAr ? employeeData.excluded_letter_types_note_ar : employeeData.excluded_letter_types_note_en}
                </StatusBanner>

                {/* Letter type + language + company details */}
                <div className="card p-5 space-y-5">
                  <div>
                    <p className="text-[10px] uppercase tracking-wide font-semibold text-slate-400 dark:text-slate-500 mb-2">{t('Letter Type', 'نوع الخطاب')}</p>
                    <div className="flex flex-wrap gap-2">
                      {(Object.keys(LETTER_TYPE_META) as LetterType[]).map(lt => {
                        const meta = LETTER_TYPE_META[lt]
                        const Icon = meta.icon
                        return (
                          <button
                            key={lt}
                            onClick={() => { setLetterType(lt); setSelected(new Set()); setBulkSummary(null) }}
                            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border transition-colors ${
                              letterType === lt
                                ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'
                                : 'border-slate-200 dark:border-navy-600/50 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                            }`}
                          >
                            <Icon size={14} />
                            {isAr ? meta.labelAr : meta.labelEn}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] uppercase tracking-wide font-semibold text-slate-400 dark:text-slate-500 mb-2 flex items-center gap-1.5">
                      <Globe2 size={12} />
                      {t('Document Language', 'لغة الوثيقة')}
                    </p>
                    <div className="flex gap-2">
                      <button onClick={() => setLanguage('en')} className={`px-3.5 py-1.5 rounded-lg text-sm border ${language === 'en' ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300' : 'border-slate-200 dark:border-navy-600/50 text-slate-500'}`}>English</button>
                      <button onClick={() => setLanguage('ar')} className={`px-3.5 py-1.5 rounded-lg text-sm border ${language === 'ar' ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300' : 'border-slate-200 dark:border-navy-600/50 text-slate-500'}`}>العربية</button>
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] uppercase tracking-wide font-semibold text-slate-400 dark:text-slate-500 mb-2">
                      {t('Company Details (used on the letterhead — not assumed or fabricated)', 'بيانات الشركة (تُستخدم في ترويسة الخطاب — لا تُفترض أو تُختلق)')}
                    </p>
                    <div className="grid sm:grid-cols-2 gap-3">
                      <input value={companyName} onChange={e => setCompanyName(e.target.value)} placeholder={t('Company name', 'اسم الشركة')} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
                      <input value={companyAddress} onChange={e => setCompanyAddress(e.target.value)} placeholder={t('Company address', 'عنوان الشركة')} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
                      <input value={signatoryName} onChange={e => setSignatoryName(e.target.value)} placeholder={t('Authorized signatory name', 'اسم المفوّض بالتوقيع')} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
                      <input value={signatoryTitle} onChange={e => setSignatoryTitle(e.target.value)} placeholder={t('Signatory title', 'المسمى الوظيفي للمفوّض')} className="w-full px-3 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400" />
                    </div>
                    {!companyReady && (
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">{t('Fill in all four company fields to enable generation.', 'يرجى تعبئة جميع حقول الشركة الأربعة لتفعيل الإنشاء.')}</p>
                    )}
                    {shortFieldWarnings.length > 0 && (
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-2 flex items-start gap-1">
                        <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
                        {t(
                          `${shortFieldWarnings.join(', ')} look${shortFieldWarnings.length === 1 ? 's' : ''} unusually short — this flows directly into an official-looking document, so double-check it's not placeholder text before generating.`,
                          `الحقول التالية تبدو قصيرة بشكل غير معتاد: ${shortFieldWarnings.join('، ')} — يظهر هذا مباشرة في وثيقة رسمية المظهر، يرجى التأكد من أنها ليست نصاً تجريبياً قبل الإنشاء.`
                        )}
                      </p>
                    )}
                  </div>
                </div>

                {genError && <StatusBanner tone="critical">{genError}</StatusBanner>}

                {bulkSummary && (
                  <StatusBanner tone={bulkSummary.n_skipped > 0 ? 'caution' : 'positive'}>
                    <p className="mb-1 font-medium">
                      {t(`Bulk generation complete: ${bulkSummary.n_generated} generated, ${bulkSummary.n_skipped} skipped.`, `اكتمل الإنشاء المجمّع: تم إنشاء ${bulkSummary.n_generated} وتخطي ${bulkSummary.n_skipped}.`)}
                    </p>
                    {bulkSummary.items.filter(i => !i.generated).map(i => (
                      <p key={i.employee_id} className="text-xs opacity-80">{i.name} ({i.employee_id}): {i.reason}</p>
                    ))}
                  </StatusBanner>
                )}

                {/* Employee table */}
                <div className="card overflow-x-auto">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
                    <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={eligibleForType.length > 0 && eligibleForType.every(e => selected.has(e.employee_id))}
                        onChange={toggleSelectAllEligible}
                        disabled={eligibleForType.length === 0}
                      />
                      {t('Select all eligible', 'تحديد الكل المؤهل')}
                    </label>
                    <button
                      onClick={generateBulk}
                      disabled={!companyReady || selected.size === 0 || generating !== null}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      {generating === 'bulk' ? <RefreshCw size={14} className="animate-spin" /> : <Download size={14} />}
                      {t(`Generate Selected (${selected.size})`, `إنشاء المحدد (${selected.size})`)}
                    </button>
                  </div>
                  <table className="w-full text-sm">
                    <thead><tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                      <th className="px-4 py-2.5"></th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Name', 'الاسم')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Employee ID', 'الرقم الوظيفي')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Job Title', 'المسمى الوظيفي')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Department', 'القسم')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">{t('Salary', 'الراتب')}</th>
                      <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t('Eligibility', 'الأهلية')}</th>
                      <th className="px-4 py-2.5"></th>
                    </tr></thead>
                    <tbody>
                      {employeeData.employees.map(emp => {
                        const eligible = letterAvailableFor(letterType, emp)
                        return (
                          <tr key={emp.employee_id} className="row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <td className="px-4 py-2.5">
                              <input
                                type="checkbox"
                                checked={selected.has(emp.employee_id)}
                                disabled={!eligible}
                                onChange={() => toggleEmployee(emp.employee_id)}
                              />
                            </td>
                            <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">{emp.name}</td>
                            <td className="px-4 py-2.5 font-mono text-xs text-slate-500 dark:text-slate-400"><LatinText>{emp.employee_id}</LatinText></td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{emp.job_title}</td>
                            <td className="px-4 py-2.5 text-slate-600 dark:text-slate-400">{emp.department}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{emp.salary_sar != null ? sar(emp.salary_sar) : '—'}</td>
                            <td className="px-4 py-2.5">
                              {eligible
                                ? <StatusBadge tone="positive">{t('Eligible', 'مؤهل')}</StatusBadge>
                                : <StatusBadge tone="neutral">{t('Not available', 'غير متاح')}</StatusBadge>}
                            </td>
                            <td className="px-4 py-2.5">
                              <button
                                onClick={() => generateSingle(emp)}
                                disabled={!eligible || !companyReady || generating !== null}
                                className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-30 disabled:cursor-not-allowed"
                              >
                                {generating === emp.employee_id ? <RefreshCw size={12} className="animate-spin" /> : <Download size={12} />}
                                {t('Generate', 'إنشاء')}
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                <StatusBanner tone="neutral">{employeeData.governance_note}</StatusBanner>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <GovernanceDisclaimer compact />
    </div>
  )
}
