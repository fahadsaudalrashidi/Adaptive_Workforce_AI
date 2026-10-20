// ── Risk Band ────────────────────────────────────────────────────────────────

export type RiskBand = 'stable' | 'monitoring' | 'strategic_concern' | 'priority_review'

export interface RiskBandConfig {
  label: string
  labelAr: string
  color: string
  bgClass: string
  textClass: string
  borderClass: string
  description: string
}

export const RISK_BAND_CONFIG: Record<RiskBand, RiskBandConfig> = {
  stable: {
    label: 'Stable',
    labelAr: 'مستقر',
    color: '#059669',
    bgClass: 'bg-emerald-500/10',
    textClass: 'text-emerald-400',
    borderClass: 'border-emerald-500/30',
    description: 'Workforce indicators within expected range',
  },
  monitoring: {
    label: 'Monitoring',
    labelAr: 'مراقبة',
    color: '#d97706',
    bgClass: 'bg-amber-500/10',
    textClass: 'text-amber-400',
    borderClass: 'border-amber-500/30',
    description: 'Elevated indicators — proactive attention recommended',
  },
  strategic_concern: {
    label: 'Strategic Concern',
    labelAr: 'قلق استراتيجي',
    color: '#ea580c',
    bgClass: 'bg-orange-500/10',
    textClass: 'text-orange-400',
    borderClass: 'border-orange-500/30',
    description: 'Sustained elevation — strategic review warranted',
  },
  priority_review: {
    label: 'Priority Review',
    labelAr: 'مراجعة عاجلة',
    color: '#dc2626',
    bgClass: 'bg-red-500/10',
    textClass: 'text-red-400',
    borderClass: 'border-red-500/30',
    description: 'Critical indicators — qualified HR review required',
  },
}

// ── Department ───────────────────────────────────────────────────────────────

export interface DepartmentRisk {
  id: string
  name: string
  nameAr: string
  riskBand: RiskBand
  stabilityScore: number
  employeeCount: number
  trend: 'improving' | 'stable' | 'declining'
  trendValue: number
  corScore: number
  jdrScore: number
  ffmScore: number
}

// ── Theory Constructs ─────────────────────────────────────────────────────────

export interface TheoryContribution {
  theory: string
  theoryAr: string
  shortName: string
  contribution: number
  constructs: ConstructDetail[]
  citation: string
  color: string
}

export interface ConstructDetail {
  name: string
  nameAr: string
  weight: number
  description: string
}

// ── Trend Data ────────────────────────────────────────────────────────────────

export interface TrendPoint {
  month: string
  monthAr: string
  stabilityIndex: number
  stableCount: number
  monitoringCount: number
  concernCount: number
  priorityCount: number
}

// ── Calibration ───────────────────────────────────────────────────────────────

export interface CalibrationMetrics {
  auc: number
  ece: number
  brierScore: number
  coverageAt80: number
  calibrationDate: string
  modelVersion: string
  trainingCohortSize: number
  validationMethod: string
}

// ── Governance Status ─────────────────────────────────────────────────────────

export interface GovernanceStatusItem {
  label: string
  labelAr: string
  status: 'active' | 'warning' | 'inactive'
  description: string
  lastVerified: string
}

export interface GovernanceStatus {
  pdplCompliance: GovernanceStatusItem
  tenantIsolation: GovernanceStatusItem
  leakageProtection: GovernanceStatusItem
  auditTrail: GovernanceStatusItem
  exportSafety: GovernanceStatusItem
  calibrationActive: GovernanceStatusItem
  theoryGrounded: GovernanceStatusItem
  legacyConstructsFree: GovernanceStatusItem
}

// ── Workforce Summary ─────────────────────────────────────────────────────────

export interface WorkforceMetrics {
  tenantId: string
  companyName: string
  companyNameAr: string
  industry: string
  location: string
  reportDate: string
  totalEmployees: number
  stabilityIndex: number
  riskBands: Record<RiskBand, number>
  departments: DepartmentRisk[]
  trends: TrendPoint[]
  theoryContributions: TheoryContribution[]
  calibration: CalibrationMetrics
  governance: GovernanceStatus
  executiveSummary: string
  executiveSummaryAr: string
  strategicInsights: string[]
  strategicInsightsAr: string[]
}

// ── Export Package ────────────────────────────────────────────────────────────

export interface ExportPackage {
  data: WorkforceMetrics
  governanceDisclaimer: string
  confidenceWarning: string
  pdplNote: string
  exportedAt: string
  exportType: string
}

// ── UI State ──────────────────────────────────────────────────────────────────

export type Language = 'en' | 'ar'
export type Theme = 'dark' | 'light'
// Phase 40: 'ceo' | 'dashboard' | 'segmentation' | 'theory' | 'governance' |
// 'reports' | 'upload' | 'employees' | 'history' | 'simulation' | 'decision' |
// 'executive-report-preview' removed — all confirmed dependents of
// employee_risk_scoring.py and its shared upload/session pipeline, removed
// this phase. 'overview' (EnterpriseOverview.tsx) is the new default page.
export type NavPage = 'overview' | 'trust' | 'overtime' | 'payroll' | 'exitinterview' | 'recruitment' | 'fairness' | 'payequity' | 'nitaqat' | 'succession' | 'contractexpiry' | 'jobpatterns' | 'laborlaw' | 'hrletters' | 'gosi' | 'payrollbudget' | 'zakat' | 'financialintelligence' | 'accountingintelligence' | 'inventoryintelligence' | 'procurementintelligence' | 'logisticsintelligence' | 'operationsintelligence' | 'aibusinessanalyst'
