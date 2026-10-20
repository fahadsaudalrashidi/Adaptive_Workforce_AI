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

// ── Walkthrough step definitions ───────────────────────────────────────────────

interface WalkthroughStep {
  id: number
  icon: typeof Play
  titleEn: string
  titleAr: string
  descEn: string
  descAr: string
  component: React.FC<{ onNext: () => void }>
}

// ── Step components ────────────────────────────────────────────────────────────

function StepLanding({ onNext }: { onNext: () => void }) {
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
          {t('AWI Platform Walkthrough', 'جولة منصة AWI')}
        </h2>
        <p className={`text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'This guided walkthrough illustrates the complete organization data intake-to-board-report workflow ' +
            'of the AWI Enterprise Workforce Intelligence Platform.',
            'توضح هذه الجولة الإرشادية سير العمل الكامل من استيعاب بيانات المؤسسة إلى تقرير مجلس الإدارة ' +
            'في منصة AWI لذكاء القوى العاملة المؤسسي.'
          )}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-4 max-w-md mx-auto">
        {[
          { icon: ShieldCheck, label: t('Governance-First', 'الحوكمة أولاً'), color: 'text-emerald-500' },
          { icon: WifiOff, label: t('Fully Offline', 'دون اتصال'), color: 'text-violet-500' },
          { icon: Activity, label: t('Theory-Grounded', 'مبني على النظرية'), color: 'text-blue-500' },
        ].map(({ icon: Icon, label, color }) => (
          <div key={label} className="card p-4 text-center">
            <Icon size={22} className={`${color} mx-auto mb-2`} />
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">{label}</p>
          </div>
        ))}
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2 mx-auto">
        <Play size={16} />
        {t('Begin Walkthrough', 'ابدأ الجولة')}
      </button>
    </motion.div>
  )
}

function StepUpload({ onNext }: { onNext: () => void }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-800/30 rounded-xl">
        <Upload size={18} className="text-blue-500 flex-shrink-0" />
        <p className={`text-sm text-blue-700 dark:text-blue-300 ${isAr ? 'text-right' : ''}`}>
          {t(
            'Organization Data Intake accepts CSV or Excel files. AWI auto-detects schema, language, and governance flags.',
            'استيعاب بيانات المؤسسة يقبل ملفات CSV أو Excel. تكتشف AWI تلقائياً المخطط واللغة وعلامات الحوكمة.'
          )}
        </p>
      </div>
      <div className="card p-5 space-y-3">
        {[
          t('CSV / XLSX — up to 500,000 rows', 'CSV / XLSX — حتى 500,000 صف'),
          t('Auto-detects Arabic / English column names', 'كشف تلقائي لأسماء الأعمدة بالعربية/الإنجليزية'),
          t('Governance scan runs before any analysis', 'يعمل فحص الحوكمة قبل أي تحليل'),
          t('PII and leakage columns excluded automatically', 'يتم استبعاد أعمدة البيانات الشخصية والتسريب تلقائياً'),
        ].map((item, i) => (
          <div key={i} className="flex items-center gap-3">
            <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" />
            <span className="text-sm text-slate-700 dark:text-slate-300">{item}</span>
          </div>
        ))}
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Next: Governance Scan', 'التالي: فحص الحوكمة')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepGovernance({ onNext }: { onNext: () => void }) {
  const { t } = useLanguage()
  const checks = [
    { label: t('PII Detection', 'كشف البيانات الشخصية'), result: t('Identifier columns removed', 'تمت إزالة أعمدة المعرّفات'), ok: true },
    { label: t('Proxy Leakage Scan', 'فحص التسريب الوكيل'), result: t('Tenure/experience proxies excluded', 'تم استبعاد وكلاء الخبرة'), ok: true },
    { label: t('Row Minimum', 'الحد الأدنى للصفوف'), result: t('Sufficient for 5-fold CV', 'كافٍ للتحقق المتقاطع 5-fold'), ok: true },
    { label: t('Feature Coverage', 'تغطية الميزات'), result: t('Theory constructs mapped', 'تم تعيين بنى النظرية'), ok: true },
    { label: t('Language Detection', 'كشف اللغة'), result: t('Arabic/English bilingual', 'عربي/إنجليزي ثنائي اللغة'), ok: true },
    { label: t('Employment Decision Gate', 'بوابة قرار التوظيف'), result: t('Prohibition enforced', 'تم تطبيق الحظر'), ok: true },
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
          {t('All governance checks passed — INTELLIGENCE READY', 'اجتازت جميع فحوصات الحوكمة — جاهز للذكاء')}
        </p>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Next: Workforce Intelligence', 'التالي: ذكاء القوى العاملة')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepDashboard({ onNext }: { onNext: () => void }) {
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
          {t('Workforce Risk Index Distribution', 'توزيع مؤشر مخاطر القوى العاملة')}
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
        {t('Next: Theory Intelligence', 'التالي: الذكاء النظري')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepTheory({ onNext }: { onNext: () => void }) {
  const { t, isAr } = useLanguage()
  const theories = [
    { name: 'COR', full: t('Conservation of Resources', 'نظرية الحفاظ على الموارد'), pct: 38, color: '#3b82f6' },
    { name: 'JD-R', full: t('Job Demands-Resources', 'متطلبات العمل والموارد'), pct: 29, color: '#8b5cf6' },
    { name: 'SDT', full: t('Self-Determination Theory', 'نظرية تقرير المصير'), pct: 21, color: '#ec4899' },
    { name: 'SET', full: t('Social Exchange Theory', 'نظرية التبادل الاجتماعي'), pct: 12, color: '#f59e0b' },
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <p className={`text-sm text-slate-600 dark:text-slate-400 ${isAr ? 'text-right' : ''}`}>
        {t(
          'AWI grounds every Workforce Risk Index score in validated organisational behaviour theories. ' +
          'All driver attributions are labelled as statistical associations — not causal claims.',
          'تستند AWI في كل درجة لمؤشر مخاطر القوى العاملة إلى نظريات السلوك التنظيمي المعتمدة. ' +
          'جميع إسنادات الأسباب تُصنَّف كارتباطات إحصائية — وليست ادعاءات سببية.'
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
        {t('Next: ML Validation', 'التالي: التحقق من نموذج ML')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepMLValidation({ onNext }: { onNext: () => void }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'ROC-AUC', value: '0.847', desc: t('Discrimination', 'التمييز') },
          { label: 'MCC', value: '0.494', desc: t('Classification Quality', 'جودة التصنيف') },
          { label: 'F1 Score', value: '0.707', desc: t('Harmonic Mean', 'المتوسط التوافقي') },
          { label: 'ECE', value: '0.038', desc: t('Calibration Error', 'خطأ المعايرة') },
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
            'VotingEnsemble_top3 (CatBoost + RandomForest + GradientBoosting, soft voting). ' +
            '5-fold StratifiedKFold CV. Proxy features removed. Zero leakage flags. ' +
            'Section B conservative protocol — enterprise-grade, reproducible metrics. Zero leakage flags.',
            'VotingEnsemble_top3 (CatBoost + RandomForest + GradientBoosting، تصويت ناعم). ' +
            'تحقق متقاطع 5-fold StratifiedKFold. إزالة الميزات الوكيلة. صفر علامات تسريب. ' +
            'بروتوكول القسم B المحافظ — مقاييس مؤسسية قابلة للتكرار.'
          )}
        </p>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Next: Board Intelligence', 'التالي: ذكاء مجلس الإدارة')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepBoardIntelligence({ onNext }: { onNext: () => void }) {
  const { t, isAr } = useLanguage()
  const insights = [
    t('Engineering department shows sustained concern indicators — structured assessment warranted within 90 days.', 'يُظهر قسم الهندسة مؤشرات قلق متواصلة — يستدعي إجراء تقييم منظم خلال 90 يوماً.'),
    t('Operations workforce has elevated demand-resource imbalance per JD-R signals — workload review recommended.', 'يعاني فريق العمليات من اختلال في توازن الطلب-الموارد وفق إشارات JD-R — يُوصى بمراجعة عبء العمل.'),
    t('HR and Finance departments consistently in Stable band — benchmark practices for high-risk departments.', 'أقسام الموارد البشرية والمالية في النطاق المستقر باستمرار — مرجع لأفضل الممارسات للأقسام عالية المخاطر.'),
  ]
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="card p-5">
        <p className={`text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 ${isAr ? 'text-right' : ''}`}>
          {t('Board-Level Workforce Intelligence Summary', 'ملخص ذكاء القوى العاملة لمجلس الإدارة')}
        </p>
        <p className={`text-sm text-slate-600 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'AWI Decision Center produces a bilingual board summary, Executive Priority Score, Strategic Priorities ' +
            'with financial estimates, and intervention scenario simulations — ready for CHRO presentation.',
            'يُنتج مركز قرار AWI ملخصاً ثنائي اللغة لمجلس الإدارة، ودرجة أولوية تنفيذية، وأولويات استراتيجية ' +
            'مع تقديرات مالية، ومحاكاة سيناريوهات التدخل — جاهز لعرض CHRO.'
          )}
        </p>
      </div>
      <div className="space-y-2">
        <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          {t('Sample Strategic Insights', 'نماذج من الرؤى الاستراتيجية')}
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
        {t('Next: Export Suite', 'التالي: مجموعة التصدير')} <ChevronRight size={16} />
      </button>
    </motion.div>
  )
}

function StepExport({ onNext }: { onNext: () => void }) {
  const { t, isAr } = useLanguage()
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[
          { type: t('Board Report PDF', 'تقرير مجلس الإدارة PDF'), pages: '12', icon: BarChart3, desc: t('McKinsey-grade narrative deck', 'تقرير تحليلي من فئة McKinsey') },
          { type: t('McKinsey Slide Deck', 'عرض شرائح McKinsey'), pages: '11', icon: FileText, desc: t('Print-ready A4 landscape', 'جاهز للطباعة A4 أفقي') },
          { type: t('Governance Report', 'تقرير الحوكمة'), pages: '7', icon: ShieldCheck, desc: t('PDPL compliance audit', 'تدقيق امتثال PDPL') },
          { type: t('Data Export CSV', 'تصدير البيانات CSV'), pages: '—', icon: Activity, desc: t('Full risk table + scores', 'جدول المخاطر الكامل + الدرجات') },
        ].map(({ type, pages, icon: Icon, desc }) => (
          <div key={type} className="card p-4 flex items-center gap-3">
            <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
              <Icon size={16} className="text-blue-500" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{type}</p>
              <p className="text-xs text-slate-400">{pages !== '—' ? `${pages} ${t('pages', 'صفحات')} · ` : ''}{desc}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="p-3 bg-slate-50 dark:bg-slate-800/40 rounded-lg">
        <p className={`text-xs text-slate-500 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'All exports include mandatory governance disclaimers, statistical-associations-only warnings, ' +
            'and PDPL compliance notes. Export audit trail logged per session.',
            'تتضمن جميع الصادرات إخلاءات المسؤولية الإلزامية، وتحذيرات الارتباطات الإحصائية فقط، ' +
            'وملاحظات الامتثال لـ PDPL. يتم تسجيل مسار تدقيق الصادرات لكل جلسة.'
          )}
        </p>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2">
        {t('Complete Walkthrough', 'إتمام الجولة')} <CheckCircle2 size={16} />
      </button>
    </motion.div>
  )
}

function StepComplete({ onNext }: { onNext: () => void }) {
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
          {t('Platform Overview Complete', 'اكتمل نظرة عامة المنصة')}
        </h2>
        <p className={`text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'You have reviewed the complete AWI workflow: governance scanning, ' +
            'theory-grounded workforce intelligence, conservative ML validation, ' +
            'board-level decision intelligence, and compliant export suite.',
            'لقد اطلعتم على سير عمل AWI الكامل: فحص الحوكمة، ' +
            'وذكاء القوى العاملة المبني على النظرية، والتحقق المحافظ من نموذج ML، ' +
            'وذكاء قرار مجلس الإدارة، ومجموعة التصدير المتوافقة.'
          )}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3 max-w-sm mx-auto">
        <div className="card p-4 text-center">
          <p className="text-2xl font-black text-blue-600">1,014</p>
          <p className="text-xs text-slate-500 mt-1">{t('Validated Tests', 'اختبارات معتمدة')}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-2xl font-black text-emerald-600">0.847</p>
          <p className="text-xs text-slate-500 mt-1">{t('Conservative AUC', 'AUC محافظ')}</p>
        </div>
      </div>
      <button onClick={onNext} className="btn-primary flex items-center gap-2 mx-auto">
        {t('Restart Walkthrough', 'إعادة الجولة')} <Play size={16} />
      </button>
    </motion.div>
  )
}

// ── Step registry ──────────────────────────────────────────────────────────────

const WALKTHROUGH_STEPS: WalkthroughStep[] = [
  {
    id: 0, icon: Sparkles,
    titleEn: 'Welcome',            titleAr: 'الترحيب',
    descEn: 'AWI Overview',        descAr: 'نظرة عامة',
    component: StepLanding,
  },
  {
    id: 1, icon: Upload,
    titleEn: 'Data Intake',        titleAr: 'استيعاب البيانات',
    descEn: 'Organization data',   descAr: 'بيانات المؤسسة',
    component: StepUpload,
  },
  {
    id: 2, icon: ShieldCheck,
    titleEn: 'Governance Scan',    titleAr: 'فحص الحوكمة',
    descEn: 'PII & compliance',    descAr: 'بيانات شخصية وامتثال',
    component: StepGovernance,
  },
  {
    id: 3, icon: BarChart3,
    titleEn: 'Workforce Intel',    titleAr: 'ذكاء القوى العاملة',
    descEn: 'Risk dashboard',      descAr: 'لوحة المخاطر',
    component: StepDashboard,
  },
  {
    id: 4, icon: Brain,
    titleEn: 'Theory Insights',    titleAr: 'رؤى نظرية',
    descEn: 'COR/JD-R/SDT/SET',   descAr: 'COR/JD-R/SDT/SET',
    component: StepTheory,
  },
  {
    id: 5, icon: Activity,
    titleEn: 'ML Validation',      titleAr: 'تحقق نموذج ML',
    descEn: 'Conservative metrics',descAr: 'مقاييس محافظة',
    component: StepMLValidation,
  },
  {
    id: 6, icon: Users,
    titleEn: 'Board Intelligence', titleAr: 'ذكاء المجلس',
    descEn: 'Decision center',     descAr: 'مركز القرار',
    component: StepBoardIntelligence,
  },
  {
    id: 7, icon: Download,
    titleEn: 'Export Suite',       titleAr: 'مجموعة التصدير',
    descEn: 'PDF, PPTX, CSV',     descAr: 'PDF, PPTX, CSV',
    component: StepExport,
  },
  {
    id: 8, icon: CheckCircle2,
    titleEn: 'Complete',           titleAr: 'مكتمل',
    descEn: 'Overview finished',   descAr: 'انتهت الجولة',
    component: StepComplete,
  },
]

// ── Main Platform Walkthrough page ─────────────────────────────────────────────

export function PlatformWalkthrough() {
  const { t, isAr } = useLanguage()
  const [currentStep, setCurrentStep] = useState(0)

  const step = WALKTHROUGH_STEPS[currentStep]
  const StepComponent = step.component
  const progress = ((currentStep) / (WALKTHROUGH_STEPS.length - 1)) * 100

  const handleNext = () => {
    if (currentStep < WALKTHROUGH_STEPS.length - 1) {
      setCurrentStep(s => s + 1)
    } else {
      setCurrentStep(0)
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
            {t('AWI Platform Walkthrough', 'جولة منصة AWI')}
          </h1>
        </div>
        <p className={`text-sm text-slate-500 dark:text-slate-400 ${isAr ? 'text-right' : ''}`}>
          {t(
            'Guided 9-step platform overview — AWI Enterprise Workforce Intelligence',
            'جولة إرشادية من 9 خطوات — AWI لذكاء القوى العاملة المؤسسي'
          )}
        </p>
      </motion.div>

      {/* Progress bar */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {t('Step', 'الخطوة')} {currentStep + 1} / {WALKTHROUGH_STEPS.length}
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
        {WALKTHROUGH_STEPS.slice(1, -1).map(s => {
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
            <StepComponent onNext={handleNext} />
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      {currentStep > 0 && currentStep < WALKTHROUGH_STEPS.length - 1 && (
        <div className="flex items-center gap-3">
          <button
            onClick={handlePrev}
            className="btn-ghost border border-slate-200 dark:border-slate-700 flex items-center gap-2 text-sm"
          >
            <ChevronLeft size={15} />
            {t('Back', 'رجوع')}
          </button>
        </div>
      )}

      <GovernanceDisclaimer compact />
    </div>
  )
}
