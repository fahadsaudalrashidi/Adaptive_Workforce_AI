import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  ChevronRight,
  BadgeCheck,
  Bot,
  Zap,
  Clock,
  Wallet,
  MessageSquare,
  UserPlus,
  Scale,
  Flag,
  TrendingUp,
  Coins,
  CalendarClock,
  Briefcase,
  Gavel,
  Mail,
  Landmark,
  Calculator,
  HandCoins,
  LineChart,
  BookOpen,
  Package,
  Truck,
  Ship,
  Factory,
} from 'lucide-react'
import { useLanguage } from '../context/LanguageContext'
import type { NavPage } from '../types'

interface SidebarProps {
  activePage: NavPage
  onNavigate: (page: NavPage) => void
  collapsed: boolean
}

interface NavItem {
  id: NavPage
  icon: typeof LayoutDashboard
  labelEn: string
  labelAr: string
  descEn: string
  descAr: string
  badge?: 'new' | 'live'
}

interface NavGroup {
  groupEn: string
  groupAr: string
  items: NavItem[]
  secondary?: boolean
}

// Phase 40: "Executive Command" (CEO Brief, Executive Dashboard, Workforce
// Intelligence, Decision Center, Board Reports, Governance), "Data" (Data
// Intake, Intelligence Archive), and the Risk Segmentation / Scenario
// Planning / Theory Drivers items were removed — all confirmed real
// dependents of employee_risk_scoring.py and the shared upload/session
// pipeline it powered, which was removed this phase (see
// PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md Step 1 for the full trace).
// 'overview' (EnterpriseOverview.tsx) replaces both the old landing page and
// the old CEO Dashboard as the platform's default screen. Groups
// reorganized to match the platform's actual remaining scope.
const NAV_GROUPS: NavGroup[] = [
  {
    groupEn: 'Overview',
    groupAr: 'نظرة عامة',
    items: [
      {
        id: 'overview',
        icon: LayoutDashboard,
        labelEn: 'Enterprise Overview',
        labelAr: 'نظرة عامة على المؤسسة',
        descEn: 'Every module, one click away',
        descAr: 'كل وحدة على بعد نقرة واحدة',
      },
    ],
  },
  {
    groupEn: 'AI & Business Intelligence',
    groupAr: 'الذكاء الاصطناعي وذكاء الأعمال',
    items: [
      {
        id: 'aibusinessanalyst',
        icon: Bot,
        labelEn: 'AI Business Analyst',
        labelAr: 'المحلل التجاري الذكي',
        descEn: 'Ask questions · Local & offline',
        descAr: 'اطرح الأسئلة · محلي وغير متصل',
        badge: 'new',
      },
      {
        id: 'financialintelligence',
        icon: LineChart,
        labelEn: 'Financial Intelligence',
        labelAr: 'الذكاء المالي',
        descEn: 'Revenue · Expense · P&L · Cash Flow',
        descAr: 'الإيرادات · المصروفات · الأرباح والخسائر',
        badge: 'new',
      },
      {
        id: 'accountingintelligence',
        icon: BookOpen,
        labelEn: 'Accounting Intelligence',
        labelAr: 'الذكاء المحاسبي',
        descEn: 'General Ledger · Trial Balance · AR/AP Aging',
        descAr: 'دفتر الأستاذ · ميزان المراجعة · أعمار الذمم',
        badge: 'new',
      },
      {
        id: 'inventoryintelligence',
        icon: Package,
        labelEn: 'Inventory Intelligence',
        labelAr: 'ذكاء المخزون',
        descEn: 'Stock Levels · Turnover · ABC · Reorder Point',
        descAr: 'المخزون · الدوران · ABC · نقطة الطلب',
        badge: 'new',
      },
      {
        id: 'procurementintelligence',
        icon: Truck,
        labelEn: 'Procurement Intelligence',
        labelAr: 'ذكاء المشتريات',
        descEn: 'Supplier Spend · Price Trends · Cost Reduction',
        descAr: 'إنفاق الموردين · اتجاهات الأسعار · خفض التكلفة',
        badge: 'new',
      },
      {
        id: 'logisticsintelligence',
        icon: Ship,
        labelEn: 'Logistics Intelligence',
        labelAr: 'ذكاء اللوجستيات',
        descEn: 'Delivery Performance · Carrier Scoring · Returns',
        descAr: 'أداء التسليم · تقييم الناقل · المرتجعات',
        badge: 'new',
      },
      {
        id: 'operationsintelligence',
        icon: Factory,
        labelEn: 'Operations Intelligence',
        labelAr: 'ذكاء العمليات',
        descEn: 'Productivity · Utilization · Bottlenecks',
        descAr: 'الإنتاجية · الاستغلال · الاختناقات',
        badge: 'new',
      },
    ],
  },
  {
    groupEn: 'HR Analytics',
    groupAr: 'تحليلات الموارد البشرية',
    secondary: true,
    items: [
      {
        id: 'overtime',
        icon: Clock,
        labelEn: 'Overtime Cost Intelligence',
        labelAr: 'ذكاء تكلفة العمل الإضافي',
        descEn: 'Overtime spend vs. risk',
        descAr: 'إنفاق العمل الإضافي مقابل المخاطر',
        badge: 'new',
      },
      {
        id: 'payroll',
        icon: Wallet,
        labelEn: 'Payroll Movements',
        labelAr: 'حركة الرواتب',
        descEn: 'Salary movement vs. risk',
        descAr: 'حركة الراتب مقابل المخاطر',
        badge: 'new',
      },
      {
        id: 'payrollbudget',
        icon: Calculator,
        labelEn: 'Payroll Budget Planner',
        labelAr: 'مخطط ميزانية الرواتب',
        descEn: 'Planned vs. actual headcount & cost',
        descAr: 'حجم العمالة والتكلفة: المخطط مقابل الفعلي',
        badge: 'new',
      },
      {
        id: 'exitinterview',
        icon: MessageSquare,
        labelEn: 'Exit Interview Intelligence',
        labelAr: 'ذكاء مقابلات الخروج',
        descEn: 'Free-text theme analysis',
        descAr: 'تحليل مواضيع النصوص',
        badge: 'new',
      },
      {
        id: 'recruitment',
        icon: UserPlus,
        labelEn: 'Recruitment Pipeline',
        labelAr: 'مسار التوظيف',
        descEn: 'Hiring funnel · Time to hire',
        descAr: 'مسار التوظيف ووقت التعيين',
        badge: 'new',
      },
      {
        id: 'jobpatterns',
        icon: Briefcase,
        labelEn: 'Job Pattern Grouping',
        labelAr: 'تجميع الأنماط الوظيفية',
        descEn: 'Market research worksheet export',
        descAr: 'تصدير ورقة بحث السوق',
        badge: 'new',
      },
      {
        id: 'fairness',
        icon: Scale,
        labelEn: 'Fairness / Bias Audit',
        labelAr: 'تدقيق العدالة والتحيّز',
        descEn: 'Protected attributes · Disparity',
        descAr: 'الخصائص المحمية والتفاوت',
        badge: 'new',
      },
      {
        id: 'payequity',
        icon: Coins,
        labelEn: 'Pay Equity',
        labelAr: 'عدالة الأجور',
        descEn: 'Comparable-role pay gaps',
        descAr: 'فجوات الأجور للأدوار المقارنة',
        badge: 'new',
      },
      {
        id: 'nitaqat',
        icon: Flag,
        labelEn: 'Nitaqat / Saudization',
        labelAr: 'نطاقات / السعودة',
        descEn: 'Illustrative Saudization estimate',
        descAr: 'تقدير إرشادي لنسبة السعودة',
        badge: 'new',
      },
      {
        id: 'succession',
        icon: TrendingUp,
        labelEn: 'Succession Readiness',
        labelAr: 'جاهزية التعاقب الوظيفي',
        descEn: 'Constructed-heuristic readiness score',
        descAr: 'درجة جاهزية إرشادية',
        badge: 'new',
      },
      {
        id: 'contractexpiry',
        icon: CalendarClock,
        labelEn: 'Contract Expiry & Renewal',
        labelAr: 'انتهاء العقود والتجديد',
        descEn: 'Contract & Iqama expiry tiers',
        descAr: 'مستويات انتهاء العقد والإقامة',
        badge: 'new',
      },
    ],
  },
  {
    groupEn: 'Saudi Compliance & Calculators',
    groupAr: 'الامتثال السعودي والحاسبات',
    secondary: true,
    items: [
      {
        id: 'laborlaw',
        icon: Gavel,
        labelEn: 'Saudi Labor Law Calculators',
        labelAr: 'حاسبات نظام العمل السعودي',
        descEn: 'Gratuity · WPS check · Leave',
        descAr: 'المكافأة · فحص الرواتب · الإجازات',
        badge: 'new',
      },
      {
        id: 'gosi',
        icon: Landmark,
        labelEn: 'GOSI Contribution Calculator',
        labelAr: 'حاسبة اشتراكات التأمينات (GOSI)',
        descEn: 'Old/New system · Non-Saudi hazards',
        descAr: 'النظام القديم/الجديد · مخاطر غير السعوديين',
        badge: 'new',
      },
      {
        id: 'hrletters',
        icon: Mail,
        labelEn: 'HR Letter Generator',
        labelAr: 'مولّد خطابات الموارد البشرية',
        descEn: 'Salary · employment · end-of-service letters',
        descAr: 'خطابات الراتب والعمل ونهاية الخدمة',
        badge: 'new',
      },
      {
        id: 'zakat',
        icon: HandCoins,
        labelEn: 'Zakat Base Estimator',
        labelAr: 'مقدّر وعاء الزكاة',
        descEn: 'Manual balance-sheet entry · Simplified estimate',
        descAr: 'إدخال ميزانية عمومية يدوي · تقدير مبسّط',
        badge: 'new',
      },
    ],
  },
  {
    groupEn: 'Advanced',
    groupAr: 'متقدم',
    secondary: true,
    items: [
      {
        id: 'trust',
        icon: BadgeCheck,
        labelEn: 'AI Integrity',
        labelAr: 'نزاهة الذكاء الاصطناعي',
        descEn: 'Safety · Audit status',
        descAr: 'حالة السلامة والحوكمة',
      },
    ],
  },
]

export function Sidebar({ activePage, onNavigate, collapsed }: SidebarProps) {
  const { t, isAr } = useLanguage()

  let globalIdx = 0

  return (
    <aside
      className={`
        flex flex-col h-full bg-slate-950 border-r border-slate-800/80
        transition-all duration-300 ease-in-out
        ${collapsed ? 'w-16' : 'w-64'}
      `}
    >
      {/* Logo */}
      <div className={`flex items-center gap-3 border-b border-slate-800/80 ${collapsed ? 'px-3 py-4 justify-center' : 'px-4 py-4'}`}>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/20">
          <Zap size={14} className="text-white" />
        </div>
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            <p className="text-white text-sm font-bold leading-tight tracking-tight">AWI</p>
            <p className="text-slate-500 text-xs tracking-wide">
              {t('Enterprise Intelligence Platform', 'منصة الذكاء المؤسسي')}
            </p>
          </motion.div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto space-y-4">
        {NAV_GROUPS.map((group, groupIdx) => {
          const isFirstSecondary = group.secondary && !NAV_GROUPS[groupIdx - 1]?.secondary
          return (
            <div key={group.groupEn}>
              {/* Divider before first secondary group */}
              {isFirstSecondary && !collapsed && (
                <div className="flex items-center gap-2 px-3 mb-3 mt-1">
                  <div className="flex-1 h-px bg-slate-800/80" />
                  <p className="text-[8px] font-bold uppercase tracking-widest text-slate-700">
                    {t('Advanced', 'متقدم')}
                  </p>
                  <div className="flex-1 h-px bg-slate-800/80" />
                </div>
              )}
              {isFirstSecondary && collapsed && (
                <div className="h-px bg-slate-800/80 mx-2 mb-2" />
              )}

              {!collapsed && (
                <div className="flex items-center gap-2 px-3 mb-1.5">
                  <p className={`font-semibold uppercase tracking-widest ${group.secondary ? 'text-[9px] text-slate-700' : 'text-[10px] text-slate-600'}`}>
                    {isAr ? group.groupAr : group.groupEn}
                  </p>
                  <div className="flex-1 h-px bg-slate-800" />
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const idx = globalIdx++
                  const Icon = item.icon
                  const isActive = activePage === item.id
                  const label = isAr ? item.labelAr : item.labelEn
                  const desc = isAr ? item.descAr : item.descEn
                  const isSecondary = group.secondary === true

                  return (
                    <motion.button
                      key={item.id}
                      onClick={() => onNavigate(item.id)}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04, duration: 0.25 }}
                      className={`
                        w-full flex items-center gap-3 px-3 rounded-lg text-sm transition-all duration-150 relative
                        ${isSecondary ? 'py-1.5' : 'py-2'}
                        ${isActive
                          ? 'bg-blue-600/15 text-blue-300'
                          : isSecondary
                            ? 'text-slate-600 hover:text-slate-300 hover:bg-slate-800/40'
                            : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800/50'
                        }
                        ${collapsed ? 'justify-center' : ''}
                      `}
                      title={collapsed ? label : undefined}
                    >
                      {/* Active left accent bar */}
                      {isActive && !collapsed && (
                        <motion.div
                          layoutId="sidebar-active-bar"
                          className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full bg-blue-400"
                        />
                      )}

                      <Icon
                        size={isSecondary ? 14 : 16}
                        className={`flex-shrink-0 ${isActive ? 'text-blue-400' : ''}`}
                      />

                      {!collapsed && (
                        <div className={`flex-1 text-left ${isAr ? 'text-right' : ''} min-w-0`}>
                          <p className={`font-semibold leading-tight ${isSecondary ? 'text-[11.5px]' : 'text-[12.5px]'} ${isActive ? 'text-blue-300' : ''}`}>
                            {label}
                          </p>
                          <p className={`text-slate-600 mt-0.5 truncate ${isSecondary ? 'text-[9.5px]' : 'text-[10.5px]'}`}>{desc}</p>
                        </div>
                      )}

                      {!collapsed && isActive && (
                        <ChevronRight size={12} className="flex-shrink-0 text-blue-500" />
                      )}
                    </motion.button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </nav>

      {/* Footer — Phase 40: was a per-dataset "LIVE ANALYSIS"/"NO DATASET" badge
          tied to AnalysisContext, which was removed along with its only two
          writers (DataUpload.tsx, AnalysisHistory.tsx). Replaced with a
          static platform-status footer — each module manages its own upload
          independently, so there is no single "current dataset" to report here. */}
      {!collapsed && (
        <div className="px-3 py-3 border-t border-slate-800/80">
          <div className="bg-slate-800/40 border border-slate-700/40 rounded-lg px-3 py-2.5">
            <div className="flex items-center justify-center gap-1.5 mb-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <p className="text-slate-400 text-xs font-semibold tracking-wide">
                {t('LOCAL & OFFLINE', 'محلي وغير متصل')}
              </p>
            </div>
            <p className="text-slate-600 text-xs text-center mt-0.5">
              {t('Each module uploads its own data', 'كل وحدة تحمّل بياناتها الخاصة')}
            </p>
          </div>
        </div>
      )}
    </aside>
  )
}
