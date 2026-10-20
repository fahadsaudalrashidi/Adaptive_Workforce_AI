import { chromium } from './executive-ui/node_modules/playwright/index.mjs';
import { resolve } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setViewportSize({ width: 1280, height: 900 });

const htmlPath = resolve(__dirname, 'PROOF_AWI_Board_Report_V3.html');
await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
await page.waitForTimeout(1500);

await page.screenshot({ path: 'SCREENSHOTS/phase33_pdf_board_report_v3.png', fullPage: false });
console.log('PDF Board Report V3 screenshot captured.');

// Scroll to show a mid-section
await page.evaluate(() => window.scrollTo(0, 1200));
await page.waitForTimeout(300);
await page.screenshot({ path: 'SCREENSHOTS/phase33_pdf_board_report_v3_mid.png', fullPage: false });
console.log('PDF Board Report V3 mid-page screenshot captured.');

await browser.close();
