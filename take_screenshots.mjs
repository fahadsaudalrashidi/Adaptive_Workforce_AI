import { chromium } from './executive-ui/node_modules/playwright/index.mjs';
import { mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, 'SCREENSHOTS');
mkdirSync(OUT, { recursive: true });

const BASE = 'http://localhost:5173';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx     = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page    = await ctx.newPage();

  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 15000 });

  // Helper: screenshot
  const shot = async (name) => {
    const p = join(OUT, `${name}.png`);
    await page.screenshot({ path: p, fullPage: false });
    console.log(`  SAVED: ${name}.png`);
    return p;
  };

  // Helper: click sidebar nav item by text
  const nav = async (text) => {
    const el = page.getByText(text, { exact: false }).first();
    if (await el.isVisible({ timeout: 3000 }).catch(() => false)) {
      await el.click();
      await page.waitForTimeout(800);
    }
  };

  console.log('[1] Landing / Upload page...');
  await shot('01_upload_page');

  console.log('[2] CEO Brief...');
  await nav('CEO Brief');
  await page.waitForTimeout(600);
  await shot('02_ceo_brief_empty');

  console.log('[3] Executive Dashboard...');
  await nav('Executive Dashboard');
  await page.waitForTimeout(600);
  await shot('03_executive_dashboard_empty');

  console.log('[4] Board Reports...');
  await nav('Board Reports');
  await page.waitForTimeout(600);
  await shot('04_board_reports_empty');

  console.log('[5] Decision Center...');
  await nav('Decision');
  await page.waitForTimeout(600);
  await shot('05_decision_center_empty');

  // Navigate to CEO Brief and capture layout
  console.log('[6] CEO Brief layout...');
  await nav('CEO Brief');
  await page.waitForTimeout(600);
  await shot('06_ceo_brief_layout');

  // Board Reports layout
  console.log('[7] Board Reports layout...');
  await nav('Board Reports');
  await page.waitForTimeout(600);
  await shot('07_board_reports_layout');

  // HTML slide deck screenshot (open the PROOF file)
  console.log('[8] HTML Slide Deck (proof file)...');
  const htmlPath = join(__dirname, 'PROOF_AWI_Board_Briefing.html').replace(/\\/g, '/');
  await page.goto(`file:///${htmlPath}`, { waitUntil: 'load', timeout: 10000 });
  await page.waitForTimeout(800);
  await shot('08_html_slide_deck_cover');

  // Scroll down to see more slides
  await page.evaluate(() => window.scrollTo(0, 500));
  await page.waitForTimeout(400);
  await shot('09_html_slide_deck_page2');

  await page.evaluate(() => window.scrollTo(0, 1100));
  await page.waitForTimeout(400);
  await shot('10_html_slide_deck_page3');

  await browser.close();

  console.log('');
  console.log('==============================================');
  console.log('SCREENSHOTS COMPLETE');
  console.log(`Output directory: ${OUT}`);
  console.log('==============================================');
})().catch(e => {
  console.error('Screenshot error:', e.message);
  process.exit(1);
});
