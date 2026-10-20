/**
 * Enterprise Overview — Phase 40 landing page.
 *
 * Replaces both DataUpload.tsx (the old shared-upload landing page) and
 * CEODashboard.tsx (the old hero-metric page) as the platform's default
 * screen, now that employee_risk_scoring.py and the whole "one shared
 * dataset -> aggregated executive brief" pipeline behind both of them has
 * been removed (Phase 40).
 *
 * Deliberately NOT a fabricated cross-module metrics dashboard: every
 * surviving module (the 6 BI domains, every HR/compliance tracker, AI
 * Business Analyst) already has its own independent file upload and its own
 * dedicated backend endpoint — confirmed via real import/route tracing, not
 * assumption (see PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md Step 1). There
 * is no shared analyzed dataset left to pull a real headline number from
 * without re-introducing exactly the kind of invented figure this session
 * has consistently refused to ship elsewhere. Instead this is an honest
 * navigation hub: one real, functioning module per card, each linking
 * straight to its own upload flow.
 */
import { motion } from 'framer-motion'
import {
  Bot, LineChart, BookOpen, Package, Truck, Ship, Factory,
  Clock, Wallet, Calculator, MessageSquare, UserPlus, Briefcase,
  Scale, Coins, Flag, TrendingUp, CalendarClock, Gavel, Landmark,
  Mail, HandCoins, ArrowRight,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import { GovernanceDisclaimer } from '../components/shared/GovernanceDisclaimer'
import type { NavPage } from '../types'

interface ModuleCard {
  id: NavPage
  icon: typeof Bot
  titleEn: string
  titleAr: string
  descEn: string
  descAr: string
}

interface ModuleSection {
  labelEn: string
  labelAr: string
  cards: ModuleCard[]
}

const SECTIONS: ModuleSection[] = [
  {
    labelEn: 'AI & Business Intelligence',
    labelAr: 'الذكاء الاصطناعي وذكاء الأعمال',
    cards: [
      { id: 'aibusinessanalyst', icon: Bot, titleEn: 'AI Business Analyst', titleAr: 'المحلل التجاري الذكي', descEn: 'Ask questions over your data — local & offline', descAr: 'اطرح أسئلة على بياناتك — محلي وغير متصل' },
      { id: 'financialintelligence', icon: LineChart, titleEn: 'Financial Intelligence', titleAr: 'الذكاء المالي', descEn: 'Revenue, expense, P&L, cash flow', descAr: 'الإيرادات والمصروفات والأرباح والتدفق النقدي' },
      { id: 'accountingintelligence', icon: BookOpen, titleEn: 'Accounting Intelligence', titleAr: 'الذكاء المحاسبي', descEn: 'General ledger, trial balance, AR/AP aging', descAr: 'دفتر الأستاذ وميزان المراجعة وأعمار الذمم' },
      { id: 'inventoryintelligence', icon: Package, titleEn: 'Inventory Intelligence', titleAr: 'ذكاء المخزون', descEn: 'Stock levels, turnover, ABC, reorder point', descAr: 'المخزون والدوران وتصنيف ABC ونقطة الطلب' },
      { id: 'procurementintelligence', icon: Truck, titleEn: 'Procurement Intelligence', titleAr: 'ذكاء المشتريات', descEn: 'Supplier spend, price trends, cost reduction', descAr: 'إنفاق الموردين واتجاهات الأسعار وخفض التكلفة' },
      { id: 'logisticsintelligence', icon: Ship, titleEn: 'Logistics Intelligence', titleAr: 'ذكاء اللوجستيات', descEn: 'Delivery performance, carrier scoring, returns', descAr: 'أداء التسليم وتقييم الناقل والمرتجعات' },
      { id: 'operationsintelligence', icon: Factory, titleEn: 'Operations Intelligence', titleAr: 'ذكاء العمليات', descEn: 'Productivity, utilization, bottlenecks', descAr: 'الإنتاجية والاستغلال والاختناقات' },
    ],
  },
  {
    labelEn: 'HR Analytics',
    labelAr: 'تحليلات الموارد البشرية',
    cards: [
      { id: 'overtime', icon: Clock, titleEn: 'Overtime Cost Intelligence', titleAr: 'ذكاء تكلفة العمل الإضافي', descEn: 'Overtime spend by department', descAr: 'إنفاق العمل الإضافي حسب القسم' },
      { id: 'payroll', icon: Wallet, titleEn: 'Payroll Movements', titleAr: 'حركة الرواتب', descEn: 'Salary movement tracking', descAr: 'تتبع حركة الرواتب' },
      { id: 'payrollbudget', icon: Calculator, titleEn: 'Payroll Budget Planner', titleAr: 'مخطط ميزانية الرواتب', descEn: 'Planned vs. actual headcount & cost', descAr: 'المخطط مقابل الفعلي للعمالة والتكلفة' },
      { id: 'exitinterview', icon: MessageSquare, titleEn: 'Exit Interview Intelligence', titleAr: 'ذكاء مقابلات الخروج', descEn: 'Free-text theme analysis', descAr: 'تحليل مواضيع النصوص' },
      { id: 'recruitment', icon: UserPlus, titleEn: 'Recruitment Pipeline', titleAr: 'مسار التوظيف', descEn: 'Hiring funnel, time to hire', descAr: 'مسار التوظيف ووقت التعيين' },
      { id: 'jobpatterns', icon: Briefcase, titleEn: 'Job Pattern Grouping', titleAr: 'تجميع الأنماط الوظيفية', descEn: 'Market research worksheet export', descAr: 'تصدير ورقة بحث السوق' },
      { id: 'fairness', icon: Scale, titleEn: 'Fairness / Bias Audit', titleAr: 'تدقيق العدالة والتحيّز', descEn: 'Protected attributes, disparity', descAr: 'الخصائص المحمية والتفاوت' },
      { id: 'payequity', icon: Coins, titleEn: 'Pay Equity', titleAr: 'عدالة الأجور', descEn: 'Comparable-role pay gaps', descAr: 'فجوات الأجور للأدوار المقارنة' },
      { id: 'nitaqat', icon: Flag, titleEn: 'Nitaqat / Saudization', titleAr: 'نطاقات / السعودة', descEn: 'Illustrative Saudization estimate', descAr: 'تقدير إرشادي لنسبة السعودة' },
      { id: 'succession', icon: TrendingUp, titleEn: 'Succession Readiness', titleAr: 'جاهزية التعاقب الوظيفي', descEn: 'Constructed-heuristic readiness score', descAr: 'درجة جاهزية إرشادية' },
      { id: 'contractexpiry', icon: CalendarClock, titleEn: 'Contract Expiry & Renewal', titleAr: 'انتهاء العقود والتجديد', descEn: 'Contract & Iqama expiry tiers', descAr: 'مستويات انتهاء العقد والإقامة' },
    ],
  },
  {
    labelEn: 'Saudi Compliance & Calculators',
    labelAr: 'الامتثال السعودي والحاسبات',
    cards: [
      { id: 'laborlaw', icon: Gavel, titleEn: 'Saudi Labor Law Calculators', titleAr: 'حاسبات نظام العمل السعودي', descEn: 'Gratuity, WPS check, leave', descAr: 'المكافأة وفحص الرواتب والإجازات' },
      { id: 'gosi', icon: Landmark, titleEn: 'GOSI Contribution Calculator', titleAr: 'حاسبة اشتراكات التأمينات', descEn: 'Old/New system, non-Saudi rates', descAr: 'النظام القديم/الجديد ومعدلات غير السعوديين' },
      { id: 'hrletters', icon: Mail, titleEn: 'HR Letter Generator', titleAr: 'مولّد خطابات الموارد البشرية', descEn: 'Salary, employment, end-of-service letters', descAr: 'خطابات الراتب والعمل ونهاية الخدمة' },
      { id: 'zakat', icon: HandCoins, titleEn: 'Zakat Base Estimator', titleAr: 'مقدّر وعاء الزكاة', descEn: 'Manual balance-sheet entry, simplified estimate', descAr: 'إدخال ميزانية عمومية يدوي وتقدير مبسّط' },
    ],
  },
]

interface EnterpriseOverviewProps {
  onNavigate: (page: NavPage) => void
}

export function EnterpriseOverview({ onNavigate }: EnterpriseOverviewProps) {
  const { t, isAr } = useLanguage()

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-headline text-slate-900 dark:text-white">
          {t('AWI Enterprise Intelligence Platform', 'منصة الذكاء المؤسسي AWI')}
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">
          {t(
            'Every module below is independent — upload your own file directly inside the module you need. There is no shared platform-wide dataset; each analysis runs on the data you give that specific module.',
            'كل وحدة أدناه مستقلة — حمّل ملفك مباشرة داخل الوحدة التي تحتاجها. لا توجد بيانات مشتركة على مستوى المنصة؛ يعمل كل تحليل على البيانات التي تمنحها لتلك الوحدة تحديداً.'
          )}
        </p>
      </motion.div>

      {SECTIONS.map((section) => (
        <div key={section.labelEn}>
          <p className="section-title mb-3">{t(section.labelEn, section.labelAr)}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {section.cards.map((card) => {
              const Icon = card.icon
              return (
                <button
                  key={card.id}
                  onClick={() => onNavigate(card.id)}
                  className="card p-4 text-left rtl:text-right hover:border-blue-300 dark:hover:border-blue-700 transition-colors duration-base group"
                >
                  <div className="flex items-start justify-between">
                    <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                      <Icon size={18} className="text-blue-500" />
                    </div>
                    <ArrowRight
                      size={14}
                      className={`text-slate-300 dark:text-slate-600 group-hover:text-blue-500 transition-colors mt-1 ${isAr ? 'rotate-180' : ''}`}
                    />
                  </div>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 mt-3">
                    {isAr ? card.titleAr : card.titleEn}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                    {isAr ? card.descAr : card.descEn}
                  </p>
                </button>
              )
            })}
          </div>
        </div>
      ))}

      <GovernanceDisclaimer compact />
    </div>
  )
}
