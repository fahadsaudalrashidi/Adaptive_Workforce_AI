import { chromium } from './executive-ui/node_modules/playwright/index.mjs';
import { resolve } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setViewportSize({ width: 1414, height: 1000 });

const htmlPath = resolve(__dirname, 'PROOF_AWI_Board_Briefing.html');
await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
await page.waitForTimeout(1500);

const slides = await page.locator('.slide').all();
console.log('Slides found:', slides.length);

for (let i = 0; i < slides.length; i++) {
  const slide = slides[i];
  await slide.scrollIntoViewIfNeeded();
  await page.waitForTimeout(200);
  const num = String(i + 1).padStart(2, '0');
  await slide.screenshot({ path: `SCREENSHOTS/phase33_slide_${num}.png` });
  console.log(`Captured slide ${i + 1}`);
}

await browser.close();
console.log('Done — all slides captured.');
