import { chromium } from './executive-ui/node_modules/playwright/index.mjs';
import { resolve } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setViewportSize({ width: 1280, height: 900 });

// Screenshot 1: Board Report V3 HTML (the new PDF source)
const htmlPath = resolve(__dirname, 'SCREENSHOTS/phase33_1_board_report_v3.html');
await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
await page.waitForTimeout(1200);

await page.screenshot({ path: 'SCREENSHOTS/phase33_1_board_report_top.png', fullPage: false });
console.log('Board Report V3 — top screenshot captured.');

await page.evaluate(() => window.scrollTo(0, 1400));
await page.waitForTimeout(300);
await page.screenshot({ path: 'SCREENSHOTS/phase33_1_board_report_mid.png', fullPage: false });
console.log('Board Report V3 — mid-page screenshot captured.');

await page.evaluate(() => window.scrollTo(0, 3200));
await page.waitForTimeout(300);
await page.screenshot({ path: 'SCREENSHOTS/phase33_1_board_report_bottom.png', fullPage: false });
console.log('Board Report V3 — bottom screenshot captured.');

await browser.close();
console.log('All Phase 33.1 screenshots complete.');
