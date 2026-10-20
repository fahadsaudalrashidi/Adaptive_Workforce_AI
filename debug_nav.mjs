import { chromium } from './executive-ui/node_modules/playwright/index.mjs';
import { execSync, spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { writeFileSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS = resolve(__dirname, 'SCREENSHOTS');

const srv = spawn('py', ['-m', 'http.server', '7791', '--directory', resolve(__dirname, 'executive-ui/dist')], { stdio: 'ignore' });
await new Promise(r => setTimeout(r, 2500));
console.log('Static server on :7791');

const mockRisk = {
  scoredAt: new Date().toISOString(),
  filename: 'test_corp_200_employees',
  datasetHash: 'a1b2c3d4',
  totalEmployeeRecords: 200,
  page: 1, pageSize: 200, matchedConstructCount: 4,
  averageRiskScore: 54.2, averageStabilityScore: 68.1,
  riskBandCounts: { 'Stable': 94, 'Monitoring': 62, 'Strategic Concern': 28, 'Priority Review': 16 },
  executiveSummary: 'Workforce analysis identified 44 employees in elevated risk bands.',
  governanceStatus: 'PDPL-Compliant | No PII in outputs | Local processing only',
  scoringWarnings: [],
  employeeRiskTable: [],
  departmentSummary: [
    { group_field: 'Department', group_value: 'Engineering', employee_count: 40, average_risk_score: 72.3, average_stability_score: 41.2, priority_review_count: 8, strategic_concern_count: 12, monitoring_count: 10, stable_count: 10, top_risk_drivers: ['OverTime'], top_protective_drivers: [], governance_notes: [] },
  ],
  specialtySummary: [],
  employeeScoringAvailable: true,
  simulationResult: {
    available: false, reason: 'Insufficient data',
    scenarios: [], baseline: { avg_risk_score: 54.2, avg_stability_score: 68.1, at_risk_count: 44, priority_review_count: 16 },
    recommended_strategy: null,
  },
  decisionIntelligence: {
    available: true, executive_priority_score: 72, decision_readiness_level: 'medium',
    board_summary_en: '44 employees in elevated risk bands.', strategic_priorities: [],
    top_decision_questions: [], limitations: [],
  },
  storytelling: {
    available: true, reason: null,
    board_narrative: {
      audience: 'board', audience_ar: 'مجلس الإدارة',
      headline_en: '44 employees require board-level attention',
      headline_ar: '44 موظفاً يستوجبون انتباه المجلس',
      opening_en: 'Workforce analysis reveals risk concentration.',
      opening_ar: 'يكشف تحليل القوى العاملة عن تركيز المخاطر.',
      key_finding_en: 'Priority Review band contains 16 employees.',
      key_finding_ar: 'تحتوي نطاق المراجعة الأولوية على 16 موظفاً.',
      risk_signal_en: 'Financial exposure: SAR 5.3M',
      risk_signal_ar: 'التعرض المالي: SAR 5.3M',
      recommended_action_en: 'Authorize HR review programme.',
      recommended_action_ar: 'تفويض برنامج مراجعة الموارد البشرية.',
      closing_en: 'Board decision required.',
      closing_ar: 'القرار المطلوب من المجلس.',
      governance_note: 'Statistical associations only.',
    },
    ceo_narrative: null, chro_narrative: null, gov_narrative: null,
    narrative_context: { at_risk: 44, exposure: 5280000, savings: 1848000 },
    governance_notes: ['PDPL-Compliant'],
    computed_at: new Date().toISOString(),
  },
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

const consoleLogs = [];
page.on('console', msg => {
  consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
});

// Step 1: Load app and inject localStorage
await page.goto('http://127.0.0.1:7791/', { waitUntil: 'load', timeout: 15000 });
await page.waitForTimeout(1000);

await page.evaluate(({ data, ver }) => {
  localStorage.setItem('awi-employee-risk-ver', String(ver));
  localStorage.setItem('awi-employee-risk-v1', JSON.stringify(data));
}, { data: mockRisk, ver: 27 });

await page.reload({ waitUntil: 'networkidle', timeout: 20000 });
await page.waitForTimeout(3000);

console.log('\n-- After reload, all buttons:');
const btnsAfterReload = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('button')).map(b => ({
    text: b.textContent?.trim().slice(0, 60),
    testid: b.getAttribute('data-testid'),
    disabled: b.disabled
  }));
});
btnsAfterReload.forEach(b => console.log(' ', JSON.stringify(b)));

// Step 2: Click Board Reports nav
console.log('\n-- Clicking Board Reports nav...');
const navClicked = await page.evaluate(() => {
  const allBtns = Array.from(document.querySelectorAll('button'));
  const boardBtn = allBtns.find(b => (b.textContent || '').toLowerCase().includes('board report'));
  if (boardBtn) {
    boardBtn.click();
    return boardBtn.textContent?.trim().slice(0, 50);
  }
  return 'NOT FOUND';
});
console.log('Nav clicked:', navClicked);

// Wait for React re-render
await page.waitForTimeout(3000);

console.log('\n-- After nav click, all buttons with testids:');
const btnsAfterNav = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('button')).map(b => ({
    text: b.textContent?.trim().slice(0, 60),
    testid: b.getAttribute('data-testid'),
    disabled: b.disabled
  }));
});
btnsAfterNav.forEach(b => console.log(' ', JSON.stringify(b)));

// Try waitForSelector with longer timeout
console.log('\n-- Waiting for generate-pdf-btn (up to 8s)...');
try {
  await page.waitForSelector('[data-testid="generate-pdf-btn"]', { timeout: 8000 });
  console.log('PDF button FOUND by waitForSelector!');
} catch (e) {
  console.log('PDF button NOT found within 8s:', e.message);
}

// Dump page content around main area
const pageInfo = await page.evaluate(() => {
  const main = document.querySelector('main') || document.querySelector('[class*="content"]') || document.body;
  return {
    title: document.title,
    bodyText: document.body.innerText?.slice(0, 500),
    errors: Array.from(document.querySelectorAll('[class*="error"]')).map(e => e.textContent?.trim().slice(0, 100)),
    h1: Array.from(document.querySelectorAll('h1')).map(h => h.textContent?.trim()),
  };
});
console.log('\n-- Page info after nav:', JSON.stringify(pageInfo, null, 2));

// Check console errors
console.log('\n-- Console logs (errors only):', consoleLogs.filter(l => l.includes('[error]')).slice(0, 10));

await page.screenshot({ path: `${SCREENSHOTS}/debug_after_nav.png` });
console.log('Screenshot: debug_after_nav.png');

srv.kill();
await browser.close();
