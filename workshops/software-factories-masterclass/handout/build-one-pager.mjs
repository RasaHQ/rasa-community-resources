// Renders one-pager.html to a US Letter PDF and a phone-sized PNG.
//   PLAYWRIGHT_MODULE=/path/to/playwright-core node handout/build-one-pager.mjs
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE);
const dir = fileURLToPath(new URL('.', import.meta.url));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 816, height: 1056 }, deviceScaleFactor: 1.15 });
await page.goto('file://' + dir + 'one-pager.html');
await page.pdf({ path: dir + 'rasa-travel-workshop-one-pager.pdf', width: '8.5in', height: '11in', printBackground: true, preferCSSPageSize: true });
const fits = await page.evaluate(() => document.documentElement.scrollHeight <= 1056 + 1);
await page.screenshot({ path: dir + 'one-pager-preview.png', clip: { x: 0, y: 0, width: 816, height: 1056 } });
console.log('fits one page:', fits);
await browser.close();
