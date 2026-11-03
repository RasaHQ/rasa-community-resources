// Renders one-pager.html to a US Letter PDF and a phone-sized PNG.
// Brand assets and the licensed STK Bureau fonts are staged from outside this repository and are never committed:
//   BRAND_ROOT=/path/to/rasahq/brand  FONT_DIR="/path/to/STK-Fonts"  PLAYWRIGHT_MODULE=/path/to/playwright-core \
//   node handout/build-one-pager.mjs
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdtempSync, mkdirSync, copyFileSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE);
const dir = fileURLToPath(new URL('.', import.meta.url));
const { BRAND_ROOT, FONT_DIR } = process.env;
const stage = mkdtempSync(join(tmpdir(), 'one-pager-'));
mkdirSync(join(stage, 'assets'));
const assets = {
  'rasa-logo-horizontal-ink.svg': join(BRAND_ROOT, 'assets/logos/digital/rasa-logo-horizontal-ink.svg'),
  'soundwave-light.webp': join(BRAND_ROOT, 'assets/patterns/primary/web/soundwave-01-light.webp'),
  'serif-regular.woff2': join(FONT_DIR, 'Bureau Serif/woff2/STKBureauSerif-Regular.woff2'),
  'serif-italic.woff2': join(FONT_DIR, 'Bureau Serif/woff2/STKBureauSerif-Italic.woff2'),
  'sans-regular.woff2': join(FONT_DIR, 'Bureau Sans/woff2/STKBureauSans-Regular.woff2'),
  'sans-medium.woff2': join(FONT_DIR, 'Bureau Sans/woff2/STKBureauSans-Medium.woff2'),
  'sans-semibold.woff2': join(FONT_DIR, 'Bureau Sans/woff2/STKBureauSans-SemiBold.woff2'),
  'mono-regular.woff2': join(FONT_DIR, 'Bureau Sans Mono/woff2/STKBureauSansMono-Regular.woff2'),
};
for (const [name, from] of Object.entries(assets)) copyFileSync(from, join(stage, 'assets', name));
const qr = readFileSync(dir + 'qr.svg', 'utf8').trim();
writeFileSync(join(stage, 'one-pager.html'), readFileSync(dir + 'one-pager.html', 'utf8').replace('<!--QR-->', qr));
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 816, height: 1056 }, deviceScaleFactor: 1.15 });
await page.goto('file://' + join(stage, 'one-pager.html'));
await page.evaluate(() => document.fonts.ready);
const families = await page.evaluate(() => [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family + ' ' + f.weight + ' ' + f.style));
await page.pdf({ path: dir + 'rasa-travel-workshop-one-pager.pdf', width: '8.5in', height: '11in', printBackground: true, preferCSSPageSize: true });
const clear = await page.evaluate(() => document.querySelector('.band').getBoundingClientRect().top - document.querySelector('.join').getBoundingClientRect().bottom);
const fits = clear >= 8;
await page.screenshot({ path: dir + 'one-pager-preview.png', clip: { x: 0, y: 0, width: 816, height: 1056 } });
console.log('fits one page:', fits, '| space between the Join bar and the pattern band (px):', Math.round(clear), '| fonts loaded:', families.join('; '));
await browser.close();
