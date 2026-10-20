/**
 * Synthetic Saudi enterprise demo data.
 * ALL DATA IS SYNTHETIC — no real employees, no real identifiers.
 * For demonstration and evaluation purposes only.
 *
 * GOVERNANCE DISCLAIMER: This synthetic dataset is designed to demonstrate
 * probabilistic workforce stability indicators. It does not represent any
 * real organization or individual.
 */

import type {
  WorkforceMetrics,
  DepartmentRisk,
  TrendPoint,
  TheoryContribution,
  CalibrationMetrics,
  GovernanceStatus,
} from '../types'

// ── Departments ───────────────────────────────────────────────────────────────

const departments: DepartmentRisk[] = [
  {
    id: 'it',
    name: 'Information Technology',
    nameAr: 'تقنية المعلومات',
    riskBand: 'monitoring',
    stabilityScore: 68.4,
    employeeCount: 423,
    trend: 'stable',
    trendValue: -0.8,
    corScore: 0.72,
    jdrScore: 0.81,
    ffmScore: 0.65,
  },
  {
    id: 'finance',
    name: 'Finance & Accounting',
    nameAr: 'المالية والمحاسبة',
    riskBand: 'stable',
    stabilityScore: 82.1,
    employeeCount: 312,
    trend: 'improving',
    trendValue: 2.3,
    corScore: 0.83,
    jdrScore: 0.79,
    ffmScore: 0.81,
  },
  {
    id: 'ops',
    name: 'Operations',
    nameAr: 'العمليات التشغيلية',
    riskBand: 'strategic_concern',
    stabilityScore: 54.7,
    employeeCount: 847,
    trend: 'declining',
    trendValue: -4.1,
    corScore: 0.51,
    jdrScore: 0.48,
    ffmScore: 0.58,
  },
  {
    id: 'hr',
    name: 'Human Resources',
    nameAr: 'الموارد البشرية',
    riskBand: 'stable',
    stabilityScore: 87.3,
    employeeCount: 156,
    trend: 'improving',
    trendValue: 1.7,
    corScore: 0.89,
    jdrScore: 0.84,
    ffmScore: 0.85,
  },
  {
    id: 'sales',
    name: 'Sales & Marketing',
    nameAr: 'المبيعات والتسويق',
    riskBand: 'monitoring',
    stabilityScore: 71.2,
    employeeCount: 489,
    trend: 'stable',
    trendValue: 0.4,
    corScore: 0.68,
    jdrScore: 0.74,
    ffmScore: 0.71,
  },
  {
    id: 'eng',
    name: 'Engineering & Production',
    nameAr: 'الهندسة والإنتاج',
    riskBand: 'priority_review',
    stabilityScore: 41.8,
    employeeCount: 634,
    trend: 'declining',
    trendValue: -6.2,
    corScore: 0.39,
    jdrScore: 0.41,
    ffmScore: 0.44,
  },
  {
    id: 'rd',
    name: 'Research & Development',
    nameAr: 'التطوير والبحث',
    riskBand: 'stable',
    stabilityScore: 79.6,
    employeeCount: 218,
    trend: 'improving',
    trendValue: 3.1,
    corScore: 0.82,
    jdrScore: 0.77,
    ffmScore: 0.79,
  },
  {
    id: 'exec',
    name: 'Executive Management',
    nameAr: 'الإدارة التنفيذية',
    riskBand: 'stable',
    stabilityScore: 91.2,
    employeeCount: 168,
    trend: 'stable',
    trendValue: 0.2,
    corScore: 0.93,
    jdrScore: 0.89,
    ffmScore: 0.91,
  },
]

// ── Historical Trend (12 months) ──────────────────────────────────────────────

const trends: TrendPoint[] = [
  { month: 'Jun 2024', monthAr: 'يونيو 2024', stabilityIndex: 71.2, stableCount: 1801, monitoringCount: 941, concernCount: 398, priorityCount: 107 },
  { month: 'Jul 2024', monthAr: 'يوليو 2024', stabilityIndex: 69.8, stableCount: 1768, monitoringCount: 967, concernCount: 412, priorityCount: 100 },
  { month: 'Aug 2024', monthAr: 'أغسطس 2024', stabilityIndex: 68.4, stableCount: 1742, monitoringCount: 988, concernCount: 431, priorityCount: 86 },
  { month: 'Sep 2024', monthAr: 'سبتمبر 2024', stabilityIndex: 70.1, stableCount: 1779, monitoringCount: 954, concernCount: 418, priorityCount: 96 },
  { month: 'Oct 2024', monthAr: 'أكتوبر 2024', stabilityIndex: 72.3, stableCount: 1821, monitoringCount: 931, concernCount: 387, priorityCount: 108 },
  { month: 'Nov 2024', monthAr: 'نوفمبر 2024', stabilityIndex: 71.8, stableCount: 1813, monitoringCount: 943, concernCount: 374, priorityCount: 117 },
  { month: 'Dec 2024', monthAr: 'ديسمبر 2024', stabilityIndex: 70.4, stableCount: 1788, monitoringCount: 962, concernCount: 389, priorityCount: 108 },
  { month: 'Jan 2025', monthAr: 'يناير 2025', stabilityIndex: 72.9, stableCount: 1842, monitoringCount: 921, concernCount: 371, priorityCount: 113 },
  { month: 'Feb 2025', monthAr: 'فبراير 2025', stabilityIndex: 74.1, stableCount: 1871, monitoringCount: 908, concernCount: 362, priorityCount: 106 },
  { month: 'Mar 2025', monthAr: 'مارس 2025', stabilityIndex: 73.7, stableCount: 1862, monitoringCount: 916, concernCount: 357, priorityCount: 112 },
  { month: 'Apr 2025', monthAr: 'أبريل 2025', stabilityIndex: 75.2, stableCount: 1891, monitoringCount: 904, concernCount: 344, priorityCount: 108 },
  { month: 'May 2025', monthAr: 'مايو 2025', stabilityIndex: 74.3, stableCount: 1877, monitoringCount: 909, concernCount: 357, priorityCount: 104 },
]

// ── Theory Contributions ──────────────────────────────────────────────────────

const theoryContributions: TheoryContribution[] = [
  {
    theory: 'Conservation of Resources Theory',
    theoryAr: 'نظرية الحفاظ على الموارد',
    shortName: 'COR',
    contribution: 31.2,
    color: '#3b82f6',
    citation: 'Hobfoll, S.E. (1989). Journal of Applied Psychology',
    constructs: [
      { name: 'BurnoutRisk', nameAr: 'مخاطر الإرهاق', weight: 0.38, description: 'Resource depletion indicator' },
      { name: 'SatisfactionIndex', nameAr: 'مؤشر الرضا', weight: 0.34, description: 'Conservation equilibrium' },
      { name: 'EngagementScore', nameAr: 'درجة الانخراط', weight: 0.28, description: 'Resource investment signal' },
    ],
  },
  {
    theory: 'Job Demands-Resources Model',
    theoryAr: 'نموذج متطلبات الوظيفة والموارد',
    shortName: 'JD-R',
    contribution: 28.7,
    color: '#06b6d4',
    citation: 'Bakker & Demerouti (2007). Journal of Managerial Psychology',
    constructs: [
      { name: 'CareerProgression', nameAr: 'التطور الوظيفي', weight: 0.42, description: 'Growth resource availability' },
      { name: 'SalaryGrowth', nameAr: 'نمو الراتب', weight: 0.35, description: 'Financial resource trajectory' },
      { name: 'TenureRatio', nameAr: 'نسبة مدة الخدمة', weight: 0.23, description: 'Organizational embeddedness' },
    ],
  },
  {
    theory: 'Five Factor Model',
    theoryAr: 'نموذج الخمسة عوامل',
    shortName: 'FFM',
    contribution: 19.4,
    color: '#8b5cf6',
    citation: 'McCrae & Costa (1987). Journal of Personality and Social Psychology',
    constructs: [
      { name: 'IncomePerLevel', nameAr: 'الدخل لكل مستوى', weight: 0.51, description: 'Relative income satisfaction proxy' },
      { name: 'EngagementScore', nameAr: 'درجة الانخراط', weight: 0.49, description: 'Conscientiousness behavioral signal' },
    ],
  },
  {
    theory: 'Mobley Turnover Process',
    theoryAr: 'نموذج موبلي للدوران الوظيفي',
    shortName: 'Mobley',
    contribution: 14.8,
    color: '#f59e0b',
    citation: 'Mobley, W.H. (1977). Journal of Applied Psychology',
    constructs: [
      { name: 'SatisfactionIndex', nameAr: 'مؤشر الرضا', weight: 0.55, description: 'Job evaluation dissatisfaction signal' },
      { name: 'TenureRatio', nameAr: 'نسبة مدة الخدمة', weight: 0.45, description: 'Search behavior proxy' },
    ],
  },
  {
    theory: 'Adams Equity Theory',
    theoryAr: 'نظرية العدالة لأدامز',
    shortName: 'Equity',
    contribution: 5.9,
    color: '#10b981',
    citation: 'Adams, J.S. (1963). Journal of Abnormal and Social Psychology',
    constructs: [
      { name: 'IncomePerLevel', nameAr: 'الدخل لكل مستوى', weight: 0.62, description: 'Input-outcome ratio equity signal' },
      { name: 'CareerProgression', nameAr: 'التطور الوظيفي', weight: 0.38, description: 'Comparative advancement equity' },
    ],
  },
]

// ── Calibration ───────────────────────────────────────────────────────────────

const calibration: CalibrationMetrics = {
  auc: 0.783,
  ece: 0.041,
  brierScore: 0.162,
  coverageAt80: 0.761,
  calibrationDate: '2025-05-01',
  modelVersion: 'v3.2.1',
  trainingCohortSize: 3247,
  validationMethod: 'Temporal holdout (6-month forward window)',
}

// ── Governance Status ─────────────────────────────────────────────────────────

const governance: GovernanceStatus = {
  pdplCompliance: {
    label: 'PDPL Compliance',
    labelAr: 'الامتثال للأنظمة',
    status: 'active',
    description: 'Saudi Personal Data Protection Law (Royal Decree M/19) controls active',
    lastVerified: '2025-05-20',
  },
  tenantIsolation: {
    label: 'Tenant Isolation',
    labelAr: 'عزل المستأجرين',
    status: 'active',
    description: 'Structural namespace isolation — cross-tenant access architecturally prevented',
    lastVerified: '2025-05-20',
  },
  leakageProtection: {
    label: 'Leakage Protection',
    labelAr: 'حماية من التسريب',
    status: 'active',
    description: 'Target leakage detection active across all feature engineering stages',
    lastVerified: '2025-05-20',
  },
  auditTrail: {
    label: 'Audit Trail',
    labelAr: 'مسار التدقيق',
    status: 'active',
    description: '18-event audit logging with PII protection and immutable records',
    lastVerified: '2025-05-20',
  },
  exportSafety: {
    label: 'Export Safety',
    labelAr: 'أمان التصدير',
    status: 'active',
    description: 'PII removed, disclaimers attached, language validated before every export',
    lastVerified: '2025-05-20',
  },
  calibrationActive: {
    label: 'Calibration',
    labelAr: 'المعايرة',
    status: 'active',
    description: 'ECE 0.041 — probability scores are reliable indicators, not overconfident claims',
    lastVerified: '2025-05-01',
  },
  theoryGrounded: {
    label: 'Theory-Grounded',
    labelAr: 'مستند نظرياً',
    status: 'active',
    description: 'COR, JD-R, FFM, Mobley, and Adams Equity Theory constructs active',
    lastVerified: '2025-05-20',
  },
  legacyConstructsFree: {
    label: 'Legacy-Construct Free',
    labelAr: 'خالٍ من البنى القديمة',
    status: 'active',
    description: 'No attendance proxies, PDS columns, or unvalidated heuristics in use',
    lastVerified: '2025-05-20',
  },
}

// ── Full Demo Dataset ─────────────────────────────────────────────────────────

export const DEMO_WORKFORCE_METRICS: WorkforceMetrics = {
  tenantId: 'demo-national-industrial',
  companyName: 'National Industrial Holdings',
  companyNameAr: 'الشركة الوطنية للصناعة',
  industry: 'Industrial Manufacturing',
  location: 'Riyadh, Kingdom of Saudi Arabia',
  reportDate: '2025-05-20',
  totalEmployees: 3247,
  stabilityIndex: 74.3,
  riskBands: {
    stable: 1877,
    monitoring: 909,
    strategic_concern: 357,
    priority_review: 104,
  },
  departments,
  trends,
  theoryContributions,
  calibration,
  governance,
  executiveSummary:
    'The workforce stability index currently stands at 74.3 out of 100, reflecting moderate-to-good ' +
    'organizational resilience across most departments. Engineering & Production exhibits elevated ' +
    'stability concern indicators warranting qualified HR review. Operations shows a sustained ' +
    'declining trend that should be addressed through targeted retention strategy. Finance, HR, and ' +
    'R&D departments demonstrate strong stability profiles. All risk indicators are probabilistic — ' +
    'qualified HR professional review is required before any workforce decisions.',
  executiveSummaryAr:
    'يبلغ مؤشر الاستقرار الوظيفي حالياً 74.3 من أصل 100، مما يعكس مرونة تنظيمية معتدلة إلى جيدة ' +
    'في معظم الأقسام. تُظهر قسم الهندسة والإنتاج مؤشرات ارتفاع تستوجب مراجعة متخصصي الموارد البشرية. ' +
    'يسجل قسم العمليات اتجاهاً تراجعياً مستمراً يستلزم استراتيجية استبقاء موجهة. تتمتع أقسام المالية ' +
    'والموارد البشرية والبحث والتطوير بملامح استقرار قوية. جميع المؤشرات احتمالية — تتطلب مراجعة ' +
    'متخصص موارد بشرية مؤهل قبل اتخاذ أي قرارات تتعلق بالقوى العاملة.',
  strategicInsights: [
    'Engineering & Production stability indicators have declined 6.2 points over 90 days — ' +
      'JD-R model signals elevated job demands relative to available resources.',
    'Operations department trend reversal may require compensation equity review — ' +
      'Adams Equity Theory constructs show input-outcome imbalance signals.',
    'R&D and Finance departments show improving trajectories consistent with recent ' +
      'career progression investments — COR resource-gain cycles active.',
    'Overall stability index has improved 3.1 points since January 2025, ' +
      'consistent with positive organizational interventions in H1 2025.',
    'Model calibration (ECE 0.041) indicates risk scores are reliable for departmental ' +
      'planning — individual-level certainty remains probabilistic.',
  ],
  strategicInsightsAr: [
    'انخفضت مؤشرات استقرار الهندسة والإنتاج بمقدار 6.2 نقطة خلال 90 يوماً — ' +
      'يشير نموذج JD-R إلى ارتفاع متطلبات العمل مقارنةً بالموارد المتاحة.',
    'قد تستدعي عكسة اتجاه قسم العمليات مراجعة عدالة التعويضات — ' +
      'تُظهر بنى نظرية أدامز للعدالة إشارات اختلال في موازين المدخلات والمخرجات.',
    'تُسجل أقسام البحث والتطوير والمالية مسارات تحسن متوافقة مع الاستثمارات الأخيرة ' +
      'في التطوير المهني — دورات اكتساب الموارد وفق نظرية COR نشطة.',
    'تحسن المؤشر الإجمالي للاستقرار بمقدار 3.1 نقطة منذ يناير 2025، ' +
      'يتسق مع التدخلات التنظيمية الإيجابية في النصف الأول من عام 2025.',
    'تشير معايرة النموذج (ECE 0.041) إلى موثوقية درجات المخاطر للتخطيط القسمي — ' +
      'تبقى درجة اليقين على مستوى الأفراد احتمالية.',
  ],
}

export const GOVERNANCE_DISCLAIMER =
  'GOVERNANCE DISCLAIMER: This output is produced by an AI-assisted workforce analytics system. ' +
  'Risk indicators are probabilistic and do not represent determinations of individual employee ' +
  'intent or behavior. All HR decisions based on this output require qualified HR professional review.'

export const CONFIDENCE_WARNING =
  'CONFIDENCE WARNING: Model predictions carry inherent uncertainty. Risk scores should be ' +
  'interpreted as statistical patterns in organizational data, not as predictions about specific ' +
  'individuals. Confidence intervals for individual-level predictions are wide.'

export const PDPL_NOTE =
  'PDPL REVIEW NOTE: This platform processes employee data subject to Saudi Personal Data ' +
  'Protection Law (PDPL, Royal Decree M/19). Data subjects must be notified of automated ' +
  'processing. This note does not constitute legal advice or PDPL compliance certification.'
