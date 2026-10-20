/**
 * Exit Interview / Free-Text Intelligence — Phase 35.3.
 *
 * Real analysis only: uploads a free-text file to
 * POST /api/local/exit-interview-intelligence
 * (backend/core/exit_interview_intelligence_engine.py). This is a SEPARATE,
 * optional upload from the structured HR dataset — it never reuses or
 * displays raw response text; only aggregate theme counts and terms that
 * meet the backend's minimum-document-frequency privacy floor.
 */
import { useCallback, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload, MessageSquare, RefreshCw, Tag, ShieldCheck,
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

interface ThemeFrequency {
  construct: string
  theory_anchor: string
  direction: 'risk' | 'protective'
  n_responses_mentioned: number
  pct_of_responses: number
  evidence_strength: 'DIRECT' | 'STRONG_PROXY' | 'WEAK_PROXY'
}

interface ExitInterviewIntelligence {
  available: boolean
  reason: string | null
  n_responses_total: number
  n_responses_analyzed: number
  theme_frequencies: ThemeFrequency[]
  top_terms: { term: string; n_responses: number }[]
  term_extraction_method: 'tfidf' | 'word_frequency' | 'unavailable'
  narrative_en: string
  narrative_ar: string
  governance_note: string
  sources: string[]
}

interface ApiResponse {
  filename: string
  exit_interview_intelligence: ExitInterviewIntelligence
}

const UPLOAD_TIMEOUT_MS = 30_000

type ThemeSortKey = 'mentions' | 'theme'

const EVIDENCE_STYLE: Record<string, string> = {
  DIRECT: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300',
  STRONG_PROXY: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  WEAK_PROXY: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

export function ExitInterviewIntelligence() {
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

      const response = await fetch('/api/local/exit-interview-intelligence', {
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

  const eii = result?.exit_interview_intelligence
  const [hoveredTheme, setHoveredTheme] = useState<string | null>(null)

  // Phase 14 — hook called unconditionally every render (Rules of Hooks);
  // receives an empty array before a dataset is loaded.
  const { sorted: sortedThemes, sortKey, setSortKey } = useSortableTable<ThemeFrequency, ThemeSortKey>(
    eii?.theme_frequencies ?? [],
    {
      mentions: (a, b) => b.n_responses_mentioned - a.n_responses_mentioned,
      theme: (a, b) => a.construct.localeCompare(b.construct),
    },
  )

  return (
    <div className="space-y-7">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('Exit Interview Intelligence', 'ذكاء مقابلات الخروج')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t(
            'Offline theme analysis of free-text exit-interview responses — aggregate only, no raw text is ever displayed or stored.',
            'تحليل مواضيع نصوص مقابلات الخروج دون اتصال — مُجمّع فقط، لا يتم عرض أو تخزين أي نص خام.'
          )}
        </p>
      </motion.div>

      <StatusLegend />

      <StatusBanner tone="positive">
        {t(
          'This is a separate, optional upload — a .txt file (one response per line) or a .csv/.xlsx with a free-text column. Raw responses are scrubbed for PII and never returned; only aggregate theme counts (from at least 5 responses, each theme mentioned by at least 3 people) are shown.',
          'هذا تحميل منفصل واختياري — ملف .txt (استجابة واحدة لكل سطر) أو .csv/.xlsx يحتوي على عمود نصي. يتم تنقية الاستجابات الخام من البيانات الشخصية ولا يتم إرجاعها أبداً؛ تُعرض فقط أعداد المواضيع المُجمّعة.'
        )}
      </StatusBanner>

      {(status === 'idle' || status === 'error') && (
        <label className="block cursor-pointer">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.csv,.xlsx,.xls"
            onChange={handleFileSelect}
            className="hidden"
          />
          <div className="border-2 border-dashed border-slate-200 dark:border-navy-500/60 rounded-xl p-10 text-center hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-base">
            <Upload size={28} className="text-slate-300 dark:text-slate-600 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
              {t('Click to upload or drag and drop', 'انقر للتحميل أو اسحب وأفلت')}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500">
              {t('Supported: .txt, .csv, .xlsx, .xls', 'المدعوم: txt و csv و xlsx و xls')}
            </p>
          </div>
        </label>
      )}

      {status === 'loading' && (
        <>
          <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
            <RefreshCw size={12} className="animate-spin" />
            {t('Analyzing themes…', 'جارٍ تحليل المواضيع…')}
          </div>
          <SkeletonAnalysis kpiCount={3} />
        </>
      )}

      {error && (
        <StatusBanner tone="critical">{error}</StatusBanner>
      )}

      <AnimatePresence mode="wait">
        {status === 'done' && eii && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 dark:text-slate-400">{result?.filename}</span>
              <button
                onClick={reset}
                className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 flex items-center gap-1"
              >
                <RefreshCw size={12} />
                {t('Analyze another file', 'تحليل ملف آخر')}
              </button>
            </div>

            {!eii.available ? (
              <div className="card-flat p-8 text-center">
                <div className="empty-state-icon-ring mx-auto mb-4">
                  <MessageSquare size={24} className="text-navy-200" />
                </div>
                <p className="text-title text-slate-700 dark:text-slate-200 mb-2">
                  {t('Theme analysis not available', 'تحليل المواضيع غير متاح')}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto">{eii.reason}</p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                  <KPICard
                    label={t('Responses Analyzed', 'الاستجابات المُحلَّلة')}
                    value={eii.n_responses_analyzed}
                    subtitle={`${t('of', 'من')} ${eii.n_responses_total} ${t('uploaded', 'مرفوعة')}`}
                    icon={MessageSquare}
                    hero
                    animateValue
                    iconColor="text-blue-500"
                    detail={t('Raw response text is scrubbed for PII and never returned.', 'يتم تنقية نص الاستجابات الخام من البيانات الشخصية ولا يتم إرجاعها أبداً.')}
                  />
                  <KPICard
                    label={t('Themes Detected', 'المواضيع المكتشفة')}
                    value={eii.theme_frequencies.length}
                    icon={Tag}
                    iconColor="text-purple-500"
                    iconBg="bg-purple-500/10"
                    animateValue
                    detail={t('Each theme requires at least 5 responses and 3 distinct mentions to be shown.', 'يتطلب كل موضوع 5 استجابات على الأقل و3 إشارات مختلفة على الأقل ليتم عرضه.')}
                  />
                  <KPICard
                    label={t('Extraction Method', 'طريقة الاستخراج')}
                    value={eii.term_extraction_method === 'tfidf' ? 'TF-IDF' : t('Word Frequency', 'تكرار الكلمات')}
                    icon={ShieldCheck}
                    iconColor="text-emerald-500"
                    iconBg="bg-emerald-500/10"
                    detail={eii.term_extraction_method === 'tfidf'
                      ? t('Term Frequency–Inverse Document Frequency ranking.', 'ترتيب بتردد المصطلح - التردد العكسي للمستندات.')
                      : t('Simple word-frequency ranking (TF-IDF unavailable for this corpus size).', 'ترتيب بتكرار الكلمات البسيط (TF-IDF غير متاح لحجم هذه البيانات).')}
                  />
                </div>

                <div className="card p-4">
                  <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {isAr ? eii.narrative_ar : eii.narrative_en}
                  </p>
                </div>

                {eii.theme_frequencies.length > 0 && (
                  <div className="card p-5">
                    <p className="section-title mb-4">
                      {t('Theme Mentions', 'الإشارات إلى المواضيع')}
                    </p>
                    <DepartmentBarChart
                      data={eii.theme_frequencies.map(theme => ({
                        department: theme.construct,
                        value: theme.n_responses_mentioned,
                        color: theme.direction === 'risk' ? semantic.priority : semantic.stable,
                        tooltipExtra: { [t('% of responses', '% من الاستجابات')]: `${theme.pct_of_responses.toFixed(0)}%` },
                      }))}
                      valueFormatter={(v) => `${v}`}
                      highlightedKey={hoveredTheme}
                      onHoverChange={setHoveredTheme}
                    />
                  </div>
                )}

                {eii.theme_frequencies.length > 0 && (
                  <div className="card overflow-x-auto">
                    <div className="flex items-center justify-end px-4 pt-3">
                      <SortToggle<ThemeSortKey>
                        label={t('Sort:', 'ترتيب:')}
                        active={sortKey}
                        onChange={setSortKey}
                        options={[
                          { key: 'mentions', label: t('Mentions', 'الإشارات') },
                          { key: 'theme', label: t('Name', 'الاسم') },
                        ]}
                      />
                    </div>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-700 text-left">
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                            {t('Theme', 'الموضوع')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                            {t('Theory', 'النظرية')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-right">
                            {t('Mentions', 'الإشارات')}
                          </th>
                          <th className="px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide text-center">
                            {t('Evidence', 'الأدلة')}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedThemes.map((theme) => (
                          <tr
                            key={theme.construct}
                            onMouseEnter={() => setHoveredTheme(theme.construct)}
                            onMouseLeave={() => setHoveredTheme(null)}
                            className={`row-hover-card border-b border-slate-100 dark:border-slate-800 last:border-0 ${
                              hoveredTheme === theme.construct ? 'bg-slate-50 dark:bg-navy-800/40' : ''
                            }`}
                          >
                            <td className="px-4 py-2.5 font-medium text-slate-700 dark:text-slate-300">
                              {theme.construct}
                              <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full ${
                                theme.direction === 'risk'
                                  ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                  : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                              }`}>
                                {theme.direction}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-slate-500 dark:text-slate-400 text-xs">{theme.theory_anchor}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-slate-700 dark:text-slate-300">
                              {theme.n_responses_mentioned} ({theme.pct_of_responses.toFixed(0)}%)
                            </td>
                            <td className="px-4 py-2.5 text-center">
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${EVIDENCE_STYLE[theme.evidence_strength]}`}>
                                {theme.evidence_strength}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {eii.top_terms.length > 0 && (
                  <div className="card p-4">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-3">
                      {t('Most Mentioned Terms', 'الكلمات الأكثر ذكراً')}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {eii.top_terms.map(({ term, n_responses }) => (
                        <span
                          key={term}
                          className="text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                        >
                          {term} <span className="text-slate-400 dark:text-slate-500">({n_responses})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <StatusBanner tone="neutral">
                  <p className="mb-2">{eii.governance_note}</p>
                  <p className="text-[10px] uppercase tracking-wide font-semibold mb-1 opacity-80">
                    {t('Sources', 'المصادر')}
                  </p>
                  <ul className="text-[11px] opacity-70 space-y-0.5">
                    {eii.sources.map((s, i) => <li key={i}>· {s}</li>)}
                  </ul>
                </StatusBanner>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Phase 15: `caution`, not `informational` — this is a guardrail
          against a real, specific privacy mistake (uploading identifiable
          data), not a neutral methodology note. */}
      <StatusBanner tone="caution" compact>
        {t(
          'Do not upload files containing employee names or other direct identifiers.',
          'لا تحمّل ملفات تحتوي على أسماء الموظفين أو معرّفات مباشرة أخرى.'
        )}
      </StatusBanner>

      <GovernanceDisclaimer compact />
    </div>
  )
}
