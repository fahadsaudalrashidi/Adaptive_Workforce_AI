/**
 * Demo Company Data — Phase 9
 *
 * TypeScript definitions and data for 5 synthetic Saudi enterprise archetypes.
 * All data is clearly marked as synthetic and for demonstration purposes only.
 */

export interface DemoCompanyProfile {
  company_id: string
  name_en: string
  name_ar: string
  sector: string
  sector_ar: string
  employee_count: number
  saudization_pct: number
  avg_tenure_years: number
  attrition_base_rate: number
  description_en: string
  description_ar: string
  badge_color: string        // tailwind color for demo card badge
}

export interface DemoScanResult {
  company_id: string
  readiness_level: 'READY' | 'CONDITIONAL' | 'BLOCKED'
  row_count: number
  column_count: number
  feature_column_count: number
  detected_language: string
  detected_erp_style: string | null
  warnings: string[]
  blocking_reasons: string[]
}

export const DEMO_COMPANIES: DemoCompanyProfile[] = [
  {
    company_id: 'national-industrial-holdings',
    name_en: 'National Industrial Holdings Co.',
    name_ar: 'الشركة الوطنية للصناعة القابضة',
    sector: 'Heavy Industry',
    sector_ar: 'الصناعات الثقيلة',
    employee_count: 3247,
    saudization_pct: 62.4,
    avg_tenure_years: 4.8,
    attrition_base_rate: 0.18,
    description_en: 'Large industrial conglomerate with diversified manufacturing operations across the Kingdom.',
    description_ar: 'مجموعة صناعية كبرى ذات عمليات تصنيع متنوعة في أرجاء المملكة.',
    badge_color: 'blue',
  },
  {
    company_id: 'saudi-digital-services',
    name_en: 'Saudi Digital Services Group',
    name_ar: 'مجموعة الخدمات الرقمية السعودية',
    sector: 'Technology & Telecoms',
    sector_ar: 'التقنية والاتصالات',
    employee_count: 1850,
    saudization_pct: 45.1,
    avg_tenure_years: 2.9,
    attrition_base_rate: 0.28,
    description_en: 'Fast-growing technology services company serving Saudi government and private sector digital transformation.',
    description_ar: 'شركة خدمات تقنية سريعة النمو تخدم التحول الرقمي للقطاعين الحكومي والخاص في المملكة.',
    badge_color: 'purple',
  },
  {
    company_id: 'riyadh-healthcare-network',
    name_en: 'Riyadh Healthcare Network',
    name_ar: 'شبكة الرياض الصحية',
    sector: 'Healthcare',
    sector_ar: 'الرعاية الصحية',
    employee_count: 4120,
    saudization_pct: 71.3,
    avg_tenure_years: 5.6,
    attrition_base_rate: 0.14,
    description_en: 'Leading multi-specialty hospital network serving greater Riyadh with 8 facilities.',
    description_ar: 'شبكة مستشفيات متخصصة رائدة تخدم منطقة الرياض الكبرى بـ8 مرافق.',
    badge_color: 'emerald',
  },
  {
    company_id: 'gulf-retail-operations',
    name_en: 'Gulf Retail Operations Ltd.',
    name_ar: 'شركة عمليات التجزئة الخليجية',
    sector: 'Retail',
    sector_ar: 'التجزئة',
    employee_count: 6800,
    saudization_pct: 38.7,
    avg_tenure_years: 2.1,
    attrition_base_rate: 0.34,
    description_en: 'Large retail chain with 180+ outlets across Saudi Arabia and GCC.',
    description_ar: 'سلسلة تجزئة كبرى تضم أكثر من 180 منفذاً في المملكة العربية السعودية ودول الخليج.',
    badge_color: 'amber',
  },
  {
    company_id: 'public-sector-workforce-authority',
    name_en: 'Public Sector Workforce Authority',
    name_ar: 'هيئة القوى العاملة في القطاع العام',
    sector: 'Government',
    sector_ar: 'القطاع الحكومي',
    employee_count: 2350,
    saudization_pct: 94.5,
    avg_tenure_years: 8.3,
    attrition_base_rate: 0.07,
    description_en: 'Government authority responsible for national workforce policy and Saudization programs.',
    description_ar: 'جهة حكومية مسؤولة عن سياسة القوى العاملة الوطنية وبرامج السعودة.',
    badge_color: 'slate',
  },
]

export const DEMO_SCAN_RESULTS: Record<string, DemoScanResult> = {
  'national-industrial-holdings': {
    company_id: 'national-industrial-holdings',
    readiness_level: 'CONDITIONAL',
    row_count: 3247,
    column_count: 15,
    feature_column_count: 12,
    detected_language: 'en',
    detected_erp_style: null,
    warnings: [
      '67 duplicate rows detected. Consider de-duplicating before model training.',
      'Column "overtime_hours_monthly" has 8.2% null values.',
    ],
    blocking_reasons: [],
  },
  'saudi-digital-services': {
    company_id: 'saudi-digital-services',
    readiness_level: 'READY',
    row_count: 1850,
    column_count: 15,
    feature_column_count: 13,
    detected_language: 'en',
    detected_erp_style: null,
    warnings: [],
    blocking_reasons: [],
  },
  'riyadh-healthcare-network': {
    company_id: 'riyadh-healthcare-network',
    readiness_level: 'READY',
    row_count: 4120,
    column_count: 15,
    feature_column_count: 13,
    detected_language: 'en',
    detected_erp_style: null,
    warnings: [],
    blocking_reasons: [],
  },
  'gulf-retail-operations': {
    company_id: 'gulf-retail-operations',
    readiness_level: 'CONDITIONAL',
    row_count: 6800,
    column_count: 14,
    feature_column_count: 11,
    detected_language: 'en',
    detected_erp_style: null,
    warnings: [
      'High missing value rate: 12.4% of cells are null in Store Operations subset.',
      '312 duplicate rows detected.',
    ],
    blocking_reasons: [],
  },
  'public-sector-workforce-authority': {
    company_id: 'public-sector-workforce-authority',
    readiness_level: 'READY',
    row_count: 2350,
    column_count: 15,
    feature_column_count: 13,
    detected_language: 'en',
    detected_erp_style: null,
    warnings: [],
    blocking_reasons: [],
  },
}
