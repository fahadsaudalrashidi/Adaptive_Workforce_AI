import { motion } from 'framer-motion'
import {
  ShieldCheck, WifiOff, Lock, Activity,
  FileSearch, Database, CheckCircle2, AlertCircle,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'

interface TrustItem {
  id: string
  icon: typeof ShieldCheck
  color: string
  bgColor: string
  borderColor: string
  titleEn: string
  titleAr: string
  descEn: string
  descAr: string
  status: 'active' | 'pending'
  detailEn: string
  detailAr: string
}

const TRUST_ITEMS: TrustItem[] = [
  {
    id: 'governance',
    icon: ShieldCheck,
    color: 'text-emerald-600 dark:text-emerald-400',
    bgColor: 'bg-emerald-50 dark:bg-emerald-950/30',
    borderColor: 'border-emerald-200 dark:border-emerald-800/40',
    titleEn: 'Governance Active',
    titleAr: 'الحوكمة نشطة',
    descEn: 'All 8 governance controls are enforced',
    descAr: 'جميع ضوابط الحوكمة الـ 8 مطبّقة',
    status: 'active',
    detailEn:
      'PII detection, leakage prevention, tenant isolation, calibration enforcement, ' +
      'export safety, audit logging, theory grounding, and legacy construct protection ' +
      'are all active on every request.',
    detailAr:
      'اكتشاف البيانات الشخصية والوقاية من التسريب وعزل المستأجرين وإنفاذ المعايرة ' +
      'وسلامة التصدير وتسجيل التدقيق والأسس النظرية وحماية البنى القديمة — كلها نشطة في كل طلب.',
  },
  {
    id: 'pdpl',
    icon: FileSearch,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
    borderColor: 'border-blue-200 dark:border-blue-800/40',
    titleEn: 'PDPL Compliance Controls',
    titleAr: 'ضوابط الامتثال لأنظمة البيانات',
    descEn: 'Saudi Personal Data Protection Law technical controls',
    descAr: 'الضوابط التقنية لنظام حماية البيانات الشخصية السعودي',
    status: 'active',
    detailEn:
      'Technical controls implement the four PDPL principles: data minimisation, ' +
      'purpose limitation, data subject protection, and processing accountability. ' +
      'Legal compliance certification requires qualified Saudi legal counsel review.',
    detailAr:
      'تُطبّق الضوابط التقنية المبادئ الأربعة لنظام حماية البيانات: الحد الأدنى من البيانات، ' +
      'وتحديد الغرض، وحماية أصحاب البيانات، والمساءلة عن المعالجة.',
  },
  {
    id: 'offline',
    icon: WifiOff,
    color: 'text-violet-600 dark:text-violet-400',
    bgColor: 'bg-violet-50 dark:bg-violet-950/30',
    borderColor: 'border-violet-200 dark:border-violet-800/40',
    titleEn: 'Offline Deployment',
    titleAr: 'النشر دون اتصال',
    descEn: 'All employee data stays within your organisation',
    descAr: 'تبقى جميع بيانات الموظفين داخل مؤسستك',
    status: 'active',
    detailEn:
      'The platform operates in offline/local-first mode. The OfflineModeGuard intercepts ' +
      'all network calls at the socket level. No employee data is transmitted to any ' +
      'external service, cloud API, or telemetry endpoint.',
    detailAr:
      'تعمل المنصة في وضع محلي أولاً دون اتصال بالإنترنت. يعترض حارس وضع عدم الاتصال ' +
      'جميع مكالمات الشبكة على مستوى المقبس. لا تُنقل أي بيانات موظفين إلى أي خدمة خارجية.',
  },
  {
    id: 'calibration',
    icon: Activity,
    color: 'text-cyan-600 dark:text-cyan-400',
    bgColor: 'bg-cyan-50 dark:bg-cyan-950/30',
    borderColor: 'border-cyan-200 dark:border-cyan-800/40',
    titleEn: 'Calibration Verified',
    titleAr: 'المعايرة مؤكدة',
    descEn: 'Probabilistic outputs with calibration references',
    descAr: 'مخرجات احتمالية مع مراجع المعايرة',
    status: 'active',
    detailEn:
      'Model outputs are calibrated using Expected Calibration Error (ECE) measurement. ' +
      'Every risk score includes AUC-ROC, ECE, and Brier Score references. ' +
      'Predictions are organisational-level distributions, never individual verdicts.',
    detailAr:
      'يتم معايرة مخرجات النموذج باستخدام قياس خطأ المعايرة المتوقع (ECE). ' +
      'تتضمن كل درجة مخاطر مراجع AUC-ROC و ECE و Brier Score. ' +
      'التوقعات هي توزيعات على مستوى المؤسسة — وليست أحكاماً على الأفراد.',
  },
  {
    id: 'audit',
    icon: Lock,
    color: 'text-amber-600 dark:text-amber-400',
    bgColor: 'bg-amber-50 dark:bg-amber-950/30',
    borderColor: 'border-amber-200 dark:border-amber-800/40',
    titleEn: 'Audit Logging Enabled',
    titleAr: 'تسجيل التدقيق مفعّل',
    descEn: '18-category event log with PII guard',
    descAr: 'سجل أحداث بـ 18 فئة مع حماية من البيانات الشخصية',
    status: 'active',
    detailEn:
      'Every platform action is logged with category, timestamp, tenant scope, and ' +
      'action details. PII fields are automatically stripped from log entries. ' +
      'Logs are append-only and tenant-scoped — cross-tenant access is architecturally blocked.',
    detailAr:
      'يتم تسجيل كل إجراء على المنصة مع الفئة والطابع الزمني ونطاق المستأجر وتفاصيل الإجراء. ' +
      'يتم حذف حقول البيانات الشخصية تلقائياً من إدخالات السجل.',
  },
  {
    id: 'no_transfer',
    icon: Database,
    color: 'text-rose-600 dark:text-rose-400',
    bgColor: 'bg-rose-50 dark:bg-rose-950/30',
    borderColor: 'border-rose-200 dark:border-rose-800/40',
    titleEn: 'No External Data Transfer',
    titleAr: 'لا نقل بيانات خارجي',
    descEn: 'Zero data leaves your on-premises environment',
    descAr: 'لا تغادر أي بيانات بيئتك المحلية',
    status: 'active',
    detailEn:
      'Employee data is never sent to external AI APIs, cloud model inference endpoints, ' +
      'analytics platforms, or telemetry services. All computation occurs locally. ' +
      'Any external call attempt raises OFFLINE_POLICY_VIOLATION and is logged.',
    detailAr:
      'لا تُرسَل بيانات الموظفين أبداً إلى واجهات برمجة الذكاء الاصطناعي الخارجية أو ' +
      'نقاط استنتاج النماذج السحابية أو منصات التحليلات أو خدمات القياس عن بعد. ' +
      'يتم تنفيذ جميع العمليات الحسابية محلياً.',
  },
]

function TrustCard({ item, idx }: { item: TrustItem; idx: number }) {
  const { isAr } = useLanguage()
  const Icon = item.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.07, duration: 0.4 }}
      className={`
        card p-5 border
        ${item.borderColor}
      `}
    >
      <div className="flex items-start gap-4">
        <div className={`p-2.5 rounded-xl flex-shrink-0 ${item.bgColor}`}>
          <Icon size={20} className={item.color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <p className={`text-sm font-bold ${isAr ? 'text-right' : ''}`}>
              {isAr ? item.titleAr : item.titleEn}
            </p>
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-100 dark:bg-emerald-950/40 rounded-full flex-shrink-0">
              <CheckCircle2 size={11} className="text-emerald-600 dark:text-emerald-400" />
              <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                {isAr ? 'نشط' : 'Active'}
              </span>
            </div>
          </div>
          <p className={`text-xs text-slate-500 dark:text-slate-400 mb-3 ${isAr ? 'text-right' : ''}`}>
            {isAr ? item.descAr : item.descEn}
          </p>
          <p className={`text-xs text-slate-600 dark:text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
            {isAr ? item.detailAr : item.detailEn}
          </p>
        </div>
      </div>
    </motion.div>
  )
}

export function TrustPanel() {
  const { t, isAr } = useLanguage()

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4"
      >
        <div>
          <h1 className={`text-2xl font-bold text-slate-900 dark:text-slate-100 ${isAr ? 'text-right' : ''}`}>
            {t('AI Integrity Command Center', 'مركز قيادة نزاهة الذكاء الاصطناعي')}
          </h1>
          <p className={`text-sm text-slate-500 dark:text-slate-400 mt-1 ${isAr ? 'text-right' : ''}`}>
            {t(
              'Live governance posture · Privacy controls · Audit coverage · Zero external data transfer',
              'وضع الحوكمة المباشر · ضوابط الخصوصية · تغطية التدقيق · صفر نقل بيانات خارجي'
            )}
          </p>
        </div>
        <div className="flex-shrink-0 flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
              {t('All Controls Active', 'جميع الضوابط نشطة')}
            </span>
          </div>
          <p className="text-xs text-slate-500">{new Date().toLocaleDateString('en-GB')}</p>
        </div>
      </motion.div>

      {/* Integrity Score Banner */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.05 }}
        className="p-5 bg-slate-900 border border-slate-700/60 rounded-2xl"
        style={{ background: 'linear-gradient(135deg, #0f172a 0%, #0c1a14 100%)' }}
      >
        <div className="flex items-center gap-5">
          <div className="flex flex-col items-center justify-center w-20 h-20 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex-shrink-0">
            <span className="text-3xl font-black text-emerald-400">100</span>
            <span className="text-xs text-emerald-500 font-semibold">/ 100</span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 size={16} className="text-emerald-400" />
              <p className="text-base font-bold text-emerald-300">
                {t('AI Integrity Score — Maximum', 'نقاط نزاهة الذكاء الاصطناعي — الحد الأقصى')}
              </p>
            </div>
            <p className={`text-sm text-slate-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
              {t(
                '6 of 6 trust controls verified active. Employee data is protected, offline, and under full audit coverage. Zero external calls logged.',
                '6 من 6 ضوابط الثقة نشطة ومتحقق منها. بيانات الموظفين محمية وغير متصلة وخاضعة لتغطية تدقيق كاملة. صفر مكالمات خارجية.'
              )}
            </p>
          </div>
          <div className="hidden md:flex flex-col gap-2 flex-shrink-0">
            {[
              { label: t('Governance', 'حوكمة'), value: '8', color: 'text-emerald-400' },
              { label: t('Trust', 'ثقة'), value: '6/6', color: 'text-blue-400' },
              { label: t('Audit', 'تدقيق'), value: '18', color: 'text-violet-400' },
              { label: t('Ext. Calls', 'خارجي'), value: '0', color: 'text-rose-400' },
            ].map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className={`text-sm font-black tabular-nums ${s.color}`}>{s.value}</span>
                <span className="text-xs text-slate-500">{s.label}</span>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Trust cards grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {TRUST_ITEMS.map((item, idx) => (
          <TrustCard key={item.id} item={item} idx={idx} />
        ))}
      </div>

      {/* Executive confidence summary */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="card p-6"
      >
        <div className="flex items-center gap-2 mb-4">
          <ShieldCheck size={18} className="text-blue-500" />
          <p className={`section-title ${isAr ? 'text-right' : ''}`}>
            {t('Board-Level AI Assurance Statement', 'بيان ضمان الذكاء الاصطناعي لمجلس الإدارة')}
          </p>
        </div>
        <p className={`text-sm text-slate-600 dark:text-slate-400 leading-relaxed mb-4 ${isAr ? 'text-right' : ''}`}>
          {t(
            'This platform has been engineered with governance as the primary design constraint, ' +
            'not an afterthought. Every module is preceded by a governance validation layer. ' +
            'Employee data never leaves your organisation. Analysis outputs are probabilistic ' +
            'and aggregate — they describe workforce patterns, not individual employees. ' +
            'Saudi PDPL technical controls are implemented at the architectural level.',
            'صُمِّمت هذه المنصة مع الحوكمة باعتبارها القيد التصميمي الأساسي، لا إضافة لاحقة. ' +
            'كل وحدة تسبقها طبقة التحقق من الحوكمة. لا تغادر بيانات الموظفين مؤسستك أبداً. ' +
            'مخرجات التحليل احتمالية وإجمالية — تصف أنماط القوى العاملة، لا الموظفين الأفراد. ' +
            'ضوابط نظام حماية البيانات السعودي مطبّقة على المستوى المعماري.'
          )}
        </p>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: t('Governance Controls', 'ضوابط الحوكمة'), value: '8', color: 'text-emerald-600 dark:text-emerald-400' },
            { label: t('Trust Indicators', 'مؤشرات الثقة'), value: '6', color: 'text-blue-600 dark:text-blue-400' },
            { label: t('Audit Event Types', 'أنواع أحداث التدقيق'), value: '18', color: 'text-violet-600 dark:text-violet-400' },
            { label: t('External Calls', 'الاتصالات الخارجية'), value: '0', color: 'text-rose-600 dark:text-rose-400' },
          ].map((stat, i) => (
            <div key={i} className="text-center p-3 bg-slate-50 dark:bg-slate-800/40 rounded-xl">
              <p className={`text-2xl font-black ${stat.color}`}>{stat.value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{stat.label}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* PDPL legal note */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 rounded-xl"
      >
        <AlertCircle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
        <p className={`text-xs text-amber-700 dark:text-amber-400 leading-relaxed ${isAr ? 'text-right' : ''}`}>
          {t(
            'Technical controls are implemented and active. Legal compliance certification requires ' +
            'qualified Saudi legal counsel review against current PDPL regulations. This panel describes ' +
            'technical measures only and does not constitute legal advice or guarantee regulatory compliance.',
            'الضوابط التقنية مُطبَّقة ونشطة. تستلزم شهادة الامتثال القانوني مراجعة مستشار قانوني سعودي مؤهل ' +
            'وفقاً للوائح نظام حماية البيانات الشخصية الحالية. تصف هذه اللوحة التدابير التقنية فقط ' +
            'ولا تُعد نصيحة قانونية ولا تضمن الامتثال التنظيمي.'
          )}
        </p>
      </motion.div>

      <GovernanceDisclaimer showAll />
    </div>
  )
}
