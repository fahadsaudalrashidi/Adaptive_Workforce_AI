import { useState, Suspense } from 'react'
import { ThemeProvider } from './context/ThemeContext'
import { LanguageProvider } from './context/LanguageContext'
import { AppLayout } from './layout/AppLayout'
import { PageErrorBoundary } from './components/shared/PageErrorBoundary'
import { EnterpriseOverview } from './pages/EnterpriseOverview'
import { TrustPanel } from './pages/TrustPanel'
import { OvertimeCostIntelligence } from './pages/OvertimeCostIntelligence'
import { PayrollMovementsTracker } from './pages/PayrollMovementsTracker'
import { ExitInterviewIntelligence } from './pages/ExitInterviewIntelligence'
import { RecruitmentPipelineTracker } from './pages/RecruitmentPipelineTracker'
import { FairnessAuditTracker } from './pages/FairnessAuditTracker'
import { PayEquityTracker } from './pages/PayEquityTracker'
import { NitaqatComplianceTracker } from './pages/NitaqatComplianceTracker'
import { SuccessionReadinessTracker } from './pages/SuccessionReadinessTracker'
import { ContractExpiryTracker } from './pages/ContractExpiryTracker'
import { JobPatternGroupingTracker } from './pages/JobPatternGroupingTracker'
import { SaudiLaborLawCalculators } from './pages/SaudiLaborLawCalculators'
import { FinancialIntelligence } from './pages/FinancialIntelligence'
import { AccountingIntelligence } from './pages/AccountingIntelligence'
import { InventoryIntelligence } from './pages/InventoryIntelligence'
import { ProcurementIntelligence } from './pages/ProcurementIntelligence'
import { LogisticsIntelligence } from './pages/LogisticsIntelligence'
import { OperationsIntelligence } from './pages/OperationsIntelligence'
import { AIBusinessAnalyst } from './pages/AIBusinessAnalyst'
import { HRLetterGenerator } from './pages/HRLetterGenerator'
import { GosiCalculator } from './pages/GosiCalculator'
import { PayrollBudgetPlanner } from './pages/PayrollBudgetPlanner'
import { ZakatEstimator } from './pages/ZakatEstimator'
import type { NavPage } from './types'

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3 text-gray-500 dark:text-gray-400">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm">Loading…</span>
      </div>
    </div>
  )
}

function AppContent() {
  const [activePage, setActivePage] = useState<NavPage>('overview')

  const renderPage = () => {
    switch (activePage) {
      case 'overview':
        return <EnterpriseOverview onNavigate={setActivePage} />
      case 'trust':
        return <TrustPanel />
      case 'overtime':
        return <OvertimeCostIntelligence />
      case 'payroll':
        return <PayrollMovementsTracker />
      case 'exitinterview':
        return <ExitInterviewIntelligence />
      case 'recruitment':
        return <RecruitmentPipelineTracker />
      case 'fairness':
        return <FairnessAuditTracker />
      case 'payequity':
        return <PayEquityTracker />
      case 'nitaqat':
        return <NitaqatComplianceTracker />
      case 'succession':
        return <SuccessionReadinessTracker />
      case 'contractexpiry':
        return <ContractExpiryTracker />
      case 'jobpatterns':
        return <JobPatternGroupingTracker />
      case 'laborlaw':
        return <SaudiLaborLawCalculators />
      case 'hrletters':
        return <HRLetterGenerator />
      case 'gosi':
        return <GosiCalculator />
      case 'payrollbudget':
        return <PayrollBudgetPlanner />
      case 'zakat':
        return <ZakatEstimator />
      case 'financialintelligence':
        return <FinancialIntelligence />
      case 'accountingintelligence':
        return <AccountingIntelligence />
      case 'inventoryintelligence':
        return <InventoryIntelligence />
      case 'procurementintelligence':
        return <ProcurementIntelligence />
      case 'logisticsintelligence':
        return <LogisticsIntelligence />
      case 'operationsintelligence':
        return <OperationsIntelligence />
      case 'aibusinessanalyst':
        return <AIBusinessAnalyst />
    }
  }

  return (
    <AppLayout
      activePage={activePage}
      onNavigate={setActivePage}
      companyName="AWI Enterprise Intelligence"
      companyNameAr="منصة الذكاء المؤسسي AWI"
    >
      <PageErrorBoundary onReturnToUpload={() => setActivePage('overview')} pageName={activePage}>
        <Suspense fallback={<PageLoader />}>
          {renderPage()}
        </Suspense>
      </PageErrorBoundary>
    </AppLayout>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AppContent />
      </LanguageProvider>
    </ThemeProvider>
  )
}
