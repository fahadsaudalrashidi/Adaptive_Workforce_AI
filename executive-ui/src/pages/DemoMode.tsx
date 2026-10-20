import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, ChevronRight, ChevronLeft, CheckCircle2,
  Upload, ShieldCheck, BarChart3, Users, Brain,
  Activity, FileText, Download, Sparkles,
  WifiOff,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import { DEMO_COMPANIES } from '../data/demoCompanies'
import type { DemoCompanyProfile } from '../data/demoCompanies'

// ── Demo step definitions ──────────────────────────────────────────────────────

interface DemoStep {
  id: number
  icon: typeof Play
  titleEn: string
  titleAr: string
  descEn: string
  descAr: string
  component: React.FC<{ onNext: () => void; selectedCompany?: DemoCompanyProfile | null }>
}

// ── Step components ────────────────────────────────────────────────────────────

function StepLanding({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center py-8 space-y-6"
    >
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-500 shadow-xl mx-auto">
        <Sparkles size={36} className="text-white" />
      </div>
      <div>
        <h2 className={`text-2xl font-black text-slate-900 dark:text-slate-100 mb-2 ${isAr ? 'text-right' : ''}`}>
          {t('Welcome to the Enterprise Demo', 'مرحباً بكم في العرض المؤسسي')}
        </h2>
        <p className={`text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'This guided demonstration walks through the complete upload-to-report workflow ' +
            'using synthetic Saudi enterprise data. No real employee data is used.',
            'يستعرض هذا العرض التوجيهي سير العمل الكامل من التحميل إلى التقرير ' +
            'باستخدام بيانات مؤسسية سعودية اصطناعية. لا تُستخدم بيانات موظفين حقيقية.'
          )}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-4 max-w-md mx-auto">
        {[
          { icon: ShieldCheck, label: t('Governance-First', 'الحوكمة أولاً'), color: 'text-emerald-500' },
          { icon: WifiOff, label: t('Fully Offline', 'دون اتصال'), color: 'text-violet-500' },
          { icon: Activity, label: t('AI-Powered', 'مدعوم بالذكاء الاصطناعي'), color: 'text-blue-500' },
        ].map(({ icon: Icon, label, color }) => (
          <div key={label} className="card p-4 text-center">
            <Icon size={22} className={`${color} mx-auto mb-2`} />
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">{label}</p>
          </div>
        ))}
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2 mx-auto">
        <Play size={16} />
        {t('Start Demo', 'ابدأ العرض')}
      </button>
    </motion.div>
  )
}

function StepUpload({
  onNext,
  selectedCompany,
}: {
  onNext: () => void
  selectedCompany?: DemoCompanyProfile | null
}) {
  const { t, isAr } = useLanguage()
  const [chosen, setChosen] = useState<DemoCompanyProfile | null>(selectedCompany ?? null)

  const badgeColors: Record<string, string> = {
    blue:   'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    purple: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    emerald:'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    amber:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    slate:  'bg-slate-100 text-slate-700 dark:bg-slate-900/30 dark:text-slate-400',
  }

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-800/30 rounded-xl">
        <Upload size={18} className="text-blue-500 flex-shrink-0" />
        <p className={`text-sm text-blue-700 dark:text-blue-300 ${isAr ? 'text-right' : ''}`}>
          {t(
            'Select a synthetic Saudi enterprise dataset to begin the demonstration.',
            'اختر مجموعة بيانات مؤسسية سعودية اصطناعية لبدء العرض التوضيحي.'
          )}
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {DEMO_COMPANIES.map(profile => (
          <motion.button
            key={profile.company_id}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => setChosen(profile)}
            className={`card p-4 text-left transition-all ${
              chosen?.company_id === profile.company_id
                ? 'ring-2 ring-blue-500 border-blue-300 dark:border-blue-700'
                : 'hover:border-slate-300 dark:hover:border-slate-600'
            }`}
          >
            <div className="flex items-start justify-between mb-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeColors[profile.badge_color] ?? badgeColors.slate}`}>
                {isAr ? profile.sector_ar : profile.sector}
              </span>
              {chosen?.company_id === profile.company_id && (
                <CheckCircle2 size={16} className="text-blue-500" />
              )}
            </div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1">
              {isAr ? profile.name_ar : profile.name_en}
            </p>
            <div className="flex gap-4 text-xs text-slate-400 mt-2">
              <span>{profile.employee_count.toLocaleString()} {t('employees', 'موظف')}</span>
              <span>{profile.saudization_pct}% {t('Saudi', 'سعودي')}</span>
            </div>
          </motion.button>
        ))}
      </div>
      <button
        onClick={onNext}
        disabled={!chosen}
        className="btn-primary flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {t('Continue with', 'المتابعة مع')} {chosen ? (isAr ? chosen.name_ar : chosen.name_en) : t('selected company', 'الشركة المختارة')}
        <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepGovernance({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t } = useLanguage()
  const checks = [
    { label: t('PII Detection', 'كشف البيانات الشخصية'), result: t('No PII columns detected', 'لا أعمدة بيانات شخصية'), ok: true },
    { label: t('Leakage Scan', 'فحص التسريب'), result: t('No temporal leakage columns', 'لا أعمدة تسريب زمني'), ok: true },
    { label: t('Row Minimum', 'الحد الأدنى للصفوف'), result: t('Sufficient rows for analysis', 'صفوف كافية للتحليل'), ok: true },
    { label: t('Feature Coverage', 'تغطية الميزات'), result: t('32 feature columns detected', '32 عموداً للميزات'), ok: true },
    { label: t('Language Detection', 'كشف اللغة'), result: t('Arabic/English mixed', 'عربي/إنجليزي مختلط'), ok: true },
    { label: t('Schema Quality', 'جودة المخطط'), result: t('HR behavioral schema confirmed', 'مخطط السلوك البشري مؤكد'), ok: true },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="card p-5 space-y-3">
        {checks.map((check, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center gap-3"
          >
            <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0" />
            <div className="flex-1 flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{check.label}</span>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">{check.result}</span>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="p-4 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40 rounded-xl text-center">
        <CheckCircle2 size={28} className="text-emerald-500 mx-auto mb-2" />
        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-400">
          {t('All governance checks passed — READY', 'اجتازت جميع فحوصات الحوكمة — جاهز')}
        </p>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Proceed to Analysis', 'المتابعة للتحليل')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepSchema({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  const cols = [
    { name: 'job_satisfaction',        theory: 'COR',    type: t('Ordinal', 'ترتيبي') },
    { name: 'emotional_commitment',     theory: 'COR',    type: t('Ordinal', 'ترتيبي') },
    { name: 'psychological_exhaustion', theory: 'COR',    type: t('Ordinal', 'ترتيبي') },
    { name: 'get_deserved_promotion',   theory: 'JD-R',   type: t('Binary', 'ثنائي') },
    { name: 'monthly_salary_range',     theory: 'JD-R',   type: t('Range text', 'نص نطاقي') },
    { name: 'job_opportunities',        theory: 'Mobley', type: t('Ordinal', 'ترتيبي') },
    { name: 'payment_overtime',         theory: 'Adams',  type: t('Binary', 'ثنائي') },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <p className={`text-sm text-slate-600 dark:text-slate-400 ${isAr ? 'text-right' : ''}`}>
        {t(
          '35 columns identified and mapped to HR theory constructs.',
          '35 عموداً تم تحديدها ورسمها لبنى النظرية البشرية.'
        )}
      </p>
      <div className="card overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-800 dark:bg-slate-900 text-slate-300">
            <tr>
              <th className="text-left p-3 font-semibold">{t('Column', 'العمود')}</th>
              <th className="text-left p-3 font-semibold">{t('Theory', 'النظرية')}</th>
              <th className="text-left p-3 font-semibold">{t('Type', 'النوع')}</th>
            </tr>
          </thead>
          <tbody>
            {cols.map((col, i) => (
              <motion.tr
                key={col.name}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.07 }}
                className="border-b border-slate-100 dark:border-slate-700"
              >
                <td className="p-3 font-mono text-blue-600 dark:text-blue-400">{col.name}</td>
                <td className="p-3">
                  <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded-full font-medium">
                    {col.theory}
                  </span>
                </td>
                <td className="p-3 text-slate-500 dark:text-slate-400">{col.type}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('View Workforce Dashboard', 'عرض لوحة القوى العاملة')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepDashboard({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t } = useLanguage()
  const bands = [
    { label: t('Stable', 'مستقر'), count: 1847, color: 'bg-emerald-500', pct: '56.9%' },
    { label: t('Monitoring', 'مراقبة'), count: 892, color: 'bg-amber-500', pct: '27.5%' },
    { label: t('Strategic Concern', 'قلق استراتيجي'), count: 384, color: 'bg-orange-500', pct: '11.8%' },
    { label: t('Priority Review', 'مراجعة عاجلة'), count: 124, color: 'bg-red-500', pct: '3.8%' },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: t('Total Employees', 'إجمالي الموظفين'), value: '3,247', color: 'text-slate-800 dark:text-slate-200' },
          { label: t('Stability Index', 'مؤشر الاستقرار'), value: '72.4', color: 'text-blue-600 dark:text-blue-400' },
          { label: t('Stable Workforce', 'القوى العاملة المستقرة'), value: '56.9%', color: 'text-emerald-600 dark:text-emerald-400' },
          { label: t('Priority Review', 'مراجعة عاجلة'), value: '124', color: 'text-red-600 dark:text-red-400' },
        ].map(kpi => (
          <div key={kpi.label} className="card p-4 text-center">
            <p className={`text-2xl font-black ${kpi.color}`}>{kpi.value}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{kpi.label}</p>
          </div>
        ))}
      </div>
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-3 uppercase tracking-wider">
          {t('Risk Band Distribution', 'توزيع نطاقات المخاطر')}
        </p>
        <div className="space-y-2.5">
          {bands.map(band => (
            <div key={band.label} className="flex items-center gap-3">
              <span className="text-xs text-slate-600 dark:text-slate-400 w-32 flex-shrink-0">{band.label}</span>
              <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
                <motion.div
                  className={`h-full rounded-full ${band.color}`}
                  initial={{ width: 0 }}
                  animate={{ width: band.pct }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
              </div>
              <span className="text-xs font-bold text-slate-700 dark:text-slate-300 w-16 text-right tabular-nums">
                {band.count.toLocaleString()} ({band.pct})
              </span>
            </div>
          ))}
        </div>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('View Department Risk', 'عرض مخاطر الأقسام')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepDepartments({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t } = useLanguage()
  const depts = [
    { name: t('Operations', 'العمليات'),         score: 58.2, band: t('Monitoring', 'مراقبة'), color: 'text-amber-500' },
    { name: t('Information Technology', 'تقنية المعلومات'), score: 68.4, band: t('Monitoring', 'مراقبة'), color: 'text-amber-500' },
    { name: t('Human Resources', 'الموارد البشرية'), score: 81.2, band: t('Stable', 'مستقر'),    color: 'text-emerald-500' },
    { name: t('Finance', 'المالية'),              score: 75.6, band: t('Stable', 'مستقر'),    color: 'text-emerald-500' },
    { name: t('Engineering', 'الهندسة'),          score: 44.1, band: t('Strategic Concern', 'قلق استراتيجي'), color: 'text-orange-500' },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-800 dark:bg-slate-900 text-slate-300">
            <tr>
              <th className="text-left p-3 font-semibold">{t('Department', 'القسم')}</th>
              <th className="text-left p-3 font-semibold">{t('Stability Score', 'نقاط الاستقرار')}</th>
              <th className="text-left p-3 font-semibold">{t('Risk Band', 'نطاق المخاطر')}</th>
            </tr>
          </thead>
          <tbody>
            {depts.map((d, i) => (
              <motion.tr
                key={d.name}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                className="border-b border-slate-100 dark:border-slate-700"
              >
                <td className="p-3 font-medium text-slate-800 dark:text-slate-200">{d.name}</td>
                <td className="p-3 font-bold tabular-nums" style={{ color: d.score < 60 ? '#ea580c' : d.score < 75 ? '#d97706' : '#059669' }}>
                  {d.score}
                </td>
                <td className={`p-3 text-xs font-semibold ${d.color}`}>{d.band}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Explain Theory Contributions', 'شرح مساهمات النظرية')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepTheory({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  const theories = [
    { name: 'COR', full: t('Conservation of Resources', 'نظرية الحفاظ على الموارد'), pct: 38, color: '#3b82f6' },
    { name: 'JD-R', full: t('Job Demands-Resources', 'متطلبات العمل والموارد'), pct: 29, color: '#8b5cf6' },
    { name: 'Mobley', full: t('Turnover Decision Process', 'عملية قرار دوران العمل'), pct: 21, color: '#ec4899' },
    { name: 'Adams', full: t('Equity Theory', 'نظرية العدالة'), pct: 12, color: '#f59e0b' },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <p className={`text-sm text-slate-600 dark:text-slate-400 ${isAr ? 'text-right' : ''}`}>
        {t(
          'Risk scores are grounded in four validated organisational behaviour theories. ' +
          'All construct mappings from this Saudi dataset are labelled as PROXY.',
          'تستند درجات المخاطر إلى أربع نظريات سلوك تنظيمي معتمدة. ' +
          'جميع تعيينات البناء من مجموعة البيانات السعودية هذه مُصنَّفة كـ PROXY.'
        )}
      </p>
      <div className="space-y-3">
        {theories.map((th, i) => (
          <motion.div
            key={th.name}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="text-sm font-bold" style={{ color: th.color }}>{th.name}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400 ml-2">— {th.full}</span>
              </div>
              <span className="text-sm font-black text-slate-700 dark:text-slate-300">{th.pct}%</span>
            </div>
            <div className="bg-slate-100 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: th.color }}
                initial={{ width: 0 }}
                animate={{ width: `${th.pct}%` }}
                transition={{ duration: 0.9, delay: i * 0.1 + 0.3, ease: 'easeOut' }}
              />
            </div>
          </motion.div>
        ))}
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('View Calibration Panel', 'عرض لوحة المعايرة')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepCalibration({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'AUC-ROC', value: '0.847', desc: t('Discrimination', 'التمييز') },
          { label: 'ECE', value: '0.043', desc: t('Calibration Error', 'خطأ المعايرة') },
          { label: t('Brier Score', 'نقاط بريير'), value: '0.182', desc: t('Accuracy', 'الدقة') },
          { label: t('Coverage 80%', 'تغطية 80%'), value: '81.3%', desc: t('Confidence Interval', 'فترة الثقة') },
        ].map(metric => (
          <div key={metric.label} className="card p-4 text-center">
            <p className="text-xl font-black text-blue-600 dark:text-blue-400">{metric.value}</p>
            <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-1">{metric.label}</p>
            <p className="text-xs text-slate-400 mt-0.5">{metric.desc}</p>
          </div>
        ))}
      </div>
      <div className="card p-4">
        <p className={`text-sm text-slate-600 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'The model is calibrated with ECE of 0.043, indicating that predicted probabilities ' +
            'closely match observed event rates. All risk scores are probabilistic distributions ' +
            'at the departmental level — not individual employee assessments.',
            'تم معايرة النموذج بخطأ ECE يبلغ 0.043، مما يشير إلى أن الاحتمالات المتوقعة ' +
            'تتطابق بشكل وثيق مع معدلات الأحداث المرصودة. جميع درجات المخاطر هي توزيعات احتمالية ' +
            'على مستوى الأقسام — وليست تقييمات لموظفين أفراد.'
          )}
        </p>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('View Executive Summary', 'عرض الملخص التنفيذي')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepSummary({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  const insights = [
    t('Engineering department shows sustained concern indicators — structured assessment warranted within 90 days.', 'يُظهر قسم الهندسة مؤشرات قلق متواصلة — يستدعي إجراء تقييم منظم خلال 90 يوماً.'),
    t('Operations workforce has elevated demand-resource imbalance per JD-R proxy signals — workload review recommended.', 'يعاني فريق العمليات من اختلال في توازن الطلب-الموارد وفق إشارات JD-R الوكيلة — يُوصى بمراجعة عبء العمل.'),
    t('HR and Finance departments consistently in Stable band — benchmark practices for high-risk departments.', 'أقسام الموارد البشرية والمالية في النطاق المستقر باستمرار — مرجع لأفضل الممارسات للأقسام عالية المخاطر.'),
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="card p-5">
        <p className={`text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 ${isAr ? 'text-right' : ''}`}>
          {t('Board-Level Summary', 'ملخص مجلس الإدارة')}
        </p>
        <p className={`text-sm text-slate-600 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'National Industrial Holdings demonstrates a stable workforce foundation with 56.9% of employees ' +
            'in the Stable risk band. The Engineering department requires structured attention. ' +
            'Compensation equity indicators (Adams proxy) are within acceptable range organisation-wide.',
            'تُظهر الشركة الوطنية للصناعة القابضة أساساً متيناً للقوى العاملة مع 56.9% من الموظفين ' +
            'في نطاق المخاطر المستقر. يتطلب قسم الهندسة اهتماماً منظماً. ' +
            'مؤشرات عدالة التعويض (Adams proxy) ضمن النطاق المقبول على مستوى المؤسسة.'
          )}
        </p>
      </div>
      <div className="space-y-2">
        <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          {t('Strategic Insights', 'الرؤى الاستراتيجية')}
        </p>
        {insights.map((insight, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex gap-3 p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg"
          >
            <span className="w-5 h-5 flex-shrink-0 bg-blue-600 text-white text-xs font-bold rounded-full flex items-center justify-center">
              {i + 1}
            </span>
            <p className={`text-xs text-slate-600 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
              {insight}
            </p>
          </motion.div>
        ))}
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Export PDF Report', 'تصدير تقرير PDF')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepExport({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  const [exported, setExported] = useState(false)

  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          { type: t('Executive Summary', 'الملخص التنفيذي'), pages: '5', icon: BarChart3 },
          { type: t('Governance Report', 'تقرير الحوكمة'), pages: '7', icon: ShieldCheck },
          { type: t('Board Briefing', 'إحاطة مجلس الإدارة'), pages: '2', icon: FileText },
          { type: t('Data Readiness Audit', 'تدقيق جاهزية البيانات'), pages: '3', icon: Activity },
        ].map(({ type, pages, icon: Icon }) => (
          <div key={type} className="card p-4 flex items-center gap-3">
            <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
              <Icon size={16} className="text-blue-500" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{type}</p>
              <p className="text-xs text-slate-400">{pages} {t('pages', 'صفحات')} · PDF</p>
            </div>
          </div>
        ))}
      </div>

      {!exported ? (
        <button
          onClick={() => { setExported(true); window.print() }}
          className="btn-primary flex items-center gap-2"
        >
          <Download size={16} />
          {t('Export Executive PDF (Demo)', 'تصدير PDF التنفيذي (عرض تجريبي)')}
        </button>
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex items-center gap-3 p-4 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40 rounded-xl"
        >
          <CheckCircle2 size={20} className="text-emerald-500" />
          <p className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
            {t('Export initiated — mandatory disclaimers included', 'بدأ التصدير — تم تضمين إخلاء المسؤولية الإلزامي')}
          </p>
        </motion.div>
      )}

      <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg">
        <p className={`text-xs text-slate-500 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'All PDF exports include 3 mandatory disclaimers: probabilistic analysis only, ' +
            'governance controls active, and offline deployment mode.',
            'تتضمن جميع صادرات PDF 3 إخلاءات مسؤولية إلزامية: التحليل الاحتمالي فقط، ' +
            'وضوابط الحوكمة النشطة، ووضع النشر دون اتصال.'
          )}
        </p>
      </div>

      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Complete Demo', 'إتمام العرض')} <CheckCircle2 size={16} />
      </button>
    </motion.div>
  )
}

function StepComplete({ onNext }: { onNext: () => void; selectedCompany?: DemoCompanyProfile | null }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="text-center py-8 space-y-6"
    >
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 shadow-xl mx-auto">
        <CheckCircle2 size={40} className="text-white" />
      </div>
      <div>
        <h2 className={`text-2xl font-black text-slate-900 dark:text-slate-100 mb-2 ${isAr ? 'text-right' : ''}`}>
          {t('Demo Complete', 'اكتمل العرض')}
        </h2>
        <p className={`text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'You have seen the complete upload-to-report workflow: governance scanning, ' +
            'dataset classification, theory-grounded analysis, calibrated risk scoring, ' +
            'and compliant PDF export.',
            'لقد اطلعتم على سير العمل الكامل من التحميل إلى التقرير: فحص الحوكمة، ' +
            'وتصنيف مجموعة البيانات، والتحليل المبني على النظرية، وتسجيل المخاطر المعاير، ' +
            'وتصدير PDF المتوافق.'
          )}
        </p>
      </div>
      <button
        onClick={onNext}
        className="btn-primary flex items-center gap-2 mx-auto"
      >
        {t('Restart Demo', 'إعادة تشغيل العرض')} <Play size={16} />
      </button>
    </motion.div>
  )
}

// ── Demo step registry ─────────────────────────────────────────────────────────

const DEMO_STEPS: DemoStep[] = [
  {
    id: 0, icon: Sparkles,
    titleEn: 'Welcome',          titleAr: 'الترحيب',
    descEn: 'Introduction',      descAr: 'مقدمة',
    component: StepLanding,
  },
  {
    id: 1, icon: Upload,
    titleEn: 'Upload Dataset',   titleAr: 'تحميل البيانات',
    descEn: 'Select enterprise', descAr: 'اختيار المؤسسة',
    component: StepUpload,
  },
  {
    id: 2, icon: ShieldCheck,
    titleEn: 'Governance Scan',  titleAr: 'فحص الحوكمة',
    descEn: 'PII & leakage',     descAr: 'PII والتسريب',
    component: StepGovernance,
  },
  {
    id: 3, icon: Brain,
    titleEn: 'Schema Intel',     titleAr: 'ذكاء المخطط',
    descEn: 'Column mapping',    descAr: 'تعيين الأعمدة',
    component: StepSchema,
  },
  {
    id: 4, icon: BarChart3,
    titleEn: 'Workforce Intel',  titleAr: 'ذكاء القوى العاملة',
    descEn: 'Risk dashboard',    descAr: 'لوحة المخاطر',
    component: StepDashboard,
  },
  {
    id: 5, icon: Users,
    titleEn: 'Dept Risk',        titleAr: 'مخاطر الأقسام',
    descEn: 'Department view',   descAr: 'عرض الأقسام',
    component: StepDepartments,
  },
  {
    id: 6, icon: Brain,
    titleEn: 'Theory Insights',  titleAr: 'رؤى نظرية',
    descEn: 'COR/JD-R/Mobley',   descAr: 'COR/JD-R/Mobley',
    component: StepTheory,
  },
  {
    id: 7, icon: Activity,
    titleEn: 'Calibration',      titleAr: 'المعايرة',
    descEn: 'Model reliability', descAr: 'موثوقية النموذج',
    component: StepCalibration,
  },
  {
    id: 8, icon: FileText,
    titleEn: 'Exec Summary',     titleAr: 'الملخص التنفيذي',
    descEn: 'Board briefing',    descAr: 'إحاطة المجلس',
    component: StepSummary,
  },
  {
    id: 9, icon: Download,
    titleEn: 'PDF Export',       titleAr: 'تصدير PDF',
    descEn: 'Report generation', descAr: 'إنشاء التقارير',
    component: StepExport,
  },
  {
    id: 10, icon: CheckCircle2,
    titleEn: 'Complete',         titleAr: 'مكتمل',
    descEn: 'Demo finished',     descAr: 'انتهى العرض',
    component: StepComplete,
  },
]

// ── Main Demo Mode page ────────────────────────────────────────────────────────

export function DemoMode() {
  const { t, isAr } = useLanguage()
  const [currentStep, setCurrentStep] = useState(0)
  const [selectedCompany, setSelectedCompany] = useState<DemoCompanyProfile | null>(null)

  const step = DEMO_STEPS[currentStep]
  const StepComponent = step.component
  const progress = ((currentStep) / (DEMO_STEPS.length - 1)) * 100

  const handleNext = () => {
    if (currentStep < DEMO_STEPS.length - 1) {
      setCurrentStep(s => s + 1)
    } else {
      setCurrentStep(0)
      setSelectedCompany(null)
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) setCurrentStep(s => s - 1)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3 mb-1">
          <div className="p-1.5 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
            <Play size={16} className="text-blue-500" />
          </div>
          <h1 className={`text-2xl font-bold text-slate-900 dark:text-slate-100 ${isAr ? 'text-right' : ''}`}>
            {t('Enterprise Demo Mode', 'وضع العرض المؤسسي')}
          </h1>
        </div>
        <p className={`text-sm text-slate-500 dark:text-slate-400 ${isAr ? 'text-right' : ''}`}>
          {t(
            'Guided 10-step workflow — synthetic Saudi enterprise data only',
            'سير عمل موجّه من 10 خطوات — بيانات مؤسسية سعودية اصطناعية فقط'
          )}
        </p>
      </motion.div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {t('Step', 'الخطوة')} {currentStep + 1} / {DEMO_STEPS.length}
          </span>
          <span className="text-xs font-semibold text-blue-600 dark:text-blue-400">
            {isAr ? step.titleAr : step.titleEn}
          </span>
        </div>
        <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 rounded-full"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.4 }}
          />
        </div>
      </div>

      {/* Step pills */}
      <div className="flex gap-1.5 flex-wrap">
        {DEMO_STEPS.slice(1, -1).map(s => {
          const Icon = s.icon
          const done = currentStep > s.id
          const active = currentStep === s.id
          return (
            <button
              key={s.id}
              onClick={() => setCurrentStep(s.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                done
                  ? 'bg-emerald-100 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400'
                  : active
                  ? 'bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 ring-1 ring-blue-400 dark:ring-blue-600'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500'
              }`}
            >
              {done ? <CheckCircle2 size={11} /> : <Icon size={11} />}
              <span className="hidden sm:inline">{isAr ? s.titleAr : s.titleEn}</span>
            </button>
          )
        })}
      </div>

      {/* Step content card */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-5 pb-4 border-b border-slate-100 dark:border-slate-700">
          <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
            {(() => { const Icon = step.icon; return <Icon size={18} className="text-blue-500" /> })()}
          </div>
          <div>
            <p className="text-base font-bold text-slate-900 dark:text-slate-100">
              {isAr ? step.titleAr : step.titleEn}
            </p>
            <p className="text-xs text-slate-400">{isAr ? step.descAr : step.descEn}</p>
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={currentStep}>
            <StepComponent
              onNext={handleNext}
              selectedCompany={selectedCompany}
            />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      {currentStep > 0 && currentStep < DEMO_STEPS.length - 1 && (
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrev}
            className="btn-ghost border border-slate-200 dark:border-slate-700 flex items-center gap-2 text-sm"
          >
            <ChevronLeft size={15} />
            {t('Back', 'رجوع')}
          </button>
          <span className="text-xs text-slate-400 flex-1 text-center">
            {t('Demo uses synthetic data only', 'العرض يستخدم بيانات اصطناعية فقط')}
          </span>
        </div>
      )}

      <GovernanceDisclaimer compact />
    </div>
  )
}
