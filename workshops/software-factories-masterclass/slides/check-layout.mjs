#!/usr/bin/env node
// No runtime dependency is added to the offline deck. Supply an installed
// playwright-core path with --playwright when running this development gate.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(name);
  if (i < 0) return fallback;
  if (!args[i + 1] || args[i + 1].startsWith('--')) throw Error(`Missing ${name} value`);
  return args[i + 1];
};
const source = path.resolve(arg('--deck', path.join(here, 'index.html')));
const output = path.resolve(arg('--out', path.join(process.cwd(), 'slide-layout-evidence')));
const captureSteps = args.includes('--capture-steps');
const require = createRequire(import.meta.url);
const { chromium } = require(arg('--playwright', 'playwright-core'));
const sourceBytes = await fs.readFile(source);
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const localStylesheets = [];
for (const match of sourceBytes.toString().matchAll(/<link\b[^>]*>/gi)) {
  const rel = match[0].match(/\brel\s*=\s*["']([^"']+)["']/i)?.[1] || '';
  if (!rel.toLowerCase().split(/\s+/).includes('stylesheet')) continue;
  const href = match[0].match(/\bhref\s*=\s*["']([^"']+)["']/i)?.[1];
  if (!href) throw Error('Stylesheet link lacks href');
  const url = new URL(href, pathToFileURL(source));
  if (url.protocol !== 'file:') continue; // Rendering rejects network requests.
  const filename = fileURLToPath(url);
  if (localStylesheets.some(s => s.path === filename)) continue;
  const bytes = await fs.readFile(filename);
  localStylesheets.push({ path: filename, url: url.href, bytes: bytes.length, sha256: sha256(bytes) });
}
const boundFiles = new Set([source, ...localStylesheets.map(s => s.path)]);
await fs.mkdir(output, { recursive: true });
const report = {
  createdAt: new Date().toISOString(),
  source, sourceSha256: sha256(sourceBytes),
  localStylesheets,
  gateSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
  policy: { maximumSlides: 30, maximumBodyWords: 12, marginRatio: 0.06,
    titlePxAt1920: 64, bodyPxAt1920: 36, labelPxAt1920: 28,
    minimumVisualAreaRatio: 0.5, minimumVisualAreaAppliesFromAspect: 1.7, viewports: [[1920, 1080], [1512, 982], [1440, 900], [1280, 800], [1280, 720]],
    words: 'All visible instructional text including diagram labels and links; excludes title and persistent breadcrumb/navigation only.',
    visualArea: 'Bounding union of visible diagram marks or image, clipped to slide. Empty SVG containers do not count.',
    limitations: 'Geometry cannot judge pedagogic meaning or illustration quality. Independent visual and read-aloud review remain required.' },
  failures: [], slides: [],
};
const browser = await chromium.launch({ headless: true });
try {
  for (const [width, height] of report.policy.viewports) {
    const page = await browser.newPage({ viewport: { width, height }, reducedMotion: 'reduce' });
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    // Documentation anchors may point online; rendering the deck must not.
    await page.route('**/*', route => {
      if (/^https?:/.test(route.request().url())) {
        errors.push(`Network request: ${route.request().url()}`);
        return route.abort();
      }
      if (route.request().url().startsWith('file:') && !boundFiles.has(fileURLToPath(route.request().url()))) {
        errors.push(`Unbound local asset: ${route.request().url()}`);
        return route.abort();
      }
      return route.continue();
    });
    await page.goto(pathToFileURL(source).href, { waitUntil: 'load' });
    await page.evaluate(async () => { await document.fonts.ready; });
    const count = await page.locator('.slide').count();
    const slideIds = await page.locator('.slide').evaluateAll(slides => slides.map(s => s.id));
    if (new Set(slideIds).size !== count || slideIds.some(id => !id)) report.failures.push(`${width}: every slide needs a unique id`);
    if (!count || count > 30) report.failures.push(`${width}: slide count ${count}, expected 1..30`);
    await page.keyboard.press('Home');
    for (let index = 0; index < count; index++) {
      if (index) await page.keyboard.press('ArrowRight');
      const revealFrames = [];
      const captureStep = async step => {
        const filename = `slide-${String(index + 1).padStart(2, '0')}-step-${String(step).padStart(2, '0')}-${width}x${height}.png`;
        const png = await page.screenshot({ path: path.join(output, filename), animations: 'disabled' });
        revealFrames.push({ step, screenshot: filename, screenshotSha256: sha256(png) });
      };
      // A teaching diagram may reveal several stages before ArrowRight moves
      // to the next slide. Exercise those stages through the real controls,
      // then measure the fully revealed composition, not the previous slide.
      const revealSteps = await page.evaluate(() => {
        const slide = [...document.querySelectorAll('.slide')].find(s => getComputedStyle(s).display !== 'none');
        return Math.max(0, ...[...(slide?.querySelectorAll('.step[data-s]') || [])].map(s => Number(s.dataset.s) || 0));
      });
      if (revealSteps > 40) throw Error(`Unbounded reveal sequence: ${revealSteps}`);
      if (captureSteps && revealSteps) await captureStep(0);
      for (let step = 0; step < revealSteps; step++) {
        await page.keyboard.press('ArrowRight');
        if (captureSteps) await captureStep(step + 1);
      }
      await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
      const metrics = await page.evaluate(({ width, height }) => {
        const visible = el => {
          const s = getComputedStyle(el), r = el.getBoundingClientRect();
          return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) !== 0 && r.width > 0 && r.height > 0;
        };
        const slides = [...document.querySelectorAll('.slide')].filter(visible);
        if (slides.length !== 1) return { failures: [`Expected one visible slide, found ${slides.length}`] };
        const slide = slides[0], bounds = slide.getBoundingClientRect();
        const scale = width / 1920, failures = [], text = [], words = [];
        const safe = { left: width * .06, right: width * .94, top: height * .06, bottom: height * .94 };
        const rect = r => ({ x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom });
        const outside = r => r.x < safe.left - 1 || r.right > safe.right + 1 || r.y < safe.top - 1 || r.bottom > safe.bottom + 1;
        const factor = el => {
          if (el instanceof SVGGraphicsElement) {
            const m = el.getScreenCTM(); return m ? Math.hypot(m.a, m.b) : 1;
          }
          let k = 1;
          for (let p = el; p; p = p.parentElement) {
            const s = getComputedStyle(p);
            if (s.transform !== 'none') { const m = new DOMMatrix(s.transform); k *= Math.hypot(m.a, m.b); }
            const zoom = Number(s.zoom); if (Number.isFinite(zoom) && zoom > 0) k *= zoom;
          }
          return k;
        };
        // Include fixed deck chrome: a footer or logo outside .slide must not
        // escape the typography and safe-area checks.
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode, el = node.parentElement;
          if (!el || !node.textContent.trim() || !visible(el) || el.closest('script,style,defs,title,desc')) continue;
          const globalChrome = !slide.contains(el);
          const label = globalChrome || Boolean(el.closest('svg,nav,[data-text-role="label"],[data-slide-chrome]'));
          const title = Boolean(el.closest('h1'));
          const s = getComputedStyle(el), actualPx = parseFloat(s.fontSize) * factor(el);
          const minimumPx = (title ? 64 : label ? 28 : 36) * scale;
          const value = node.textContent.trim();
          if (!globalChrome && !title && !el.closest('nav,[data-slide-chrome]')) words.push(...(value.match(/[\p{L}\p{N}]+(?:[’'/:.-][\p{L}\p{N}]+)*/gu) || []));
          if (actualPx + .25 < minimumPx) failures.push(`Small ${title ? 'title' : label ? 'label' : 'body'}: ${actualPx.toFixed(1)}px < ${minimumPx.toFixed(1)}px: ${value}`);
          const range = document.createRange();
          const first = node.textContent.search(/\S/), last = node.textContent.trimEnd().length;
          range.setStart(node, first); range.setEnd(node, last);
          const boxes = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0).map(rect);
          for (const r of boxes) {
            if (outside(r)) failures.push(`Text outside 6% safe area: ${value}`);
            text.push({ value, rect: r, role: title ? 'title' : label ? 'label' : 'body', actualPx,
              inVisual: Boolean(el.closest('.scene,svg.pic,[data-slide-visual]')) });
          }
        }
        if (words.length > 12) failures.push(`Body words ${words.length} > 12`);
        if (slide.querySelector('ul,ol,li')) failures.push('Bullet/list markup is not allowed');
        for (let a = 0; a < text.length; a++) for (let b = a + 1; b < text.length; b++) {
          const x = text[a].rect, y = text[b].rect;
          const iw = Math.min(x.right, y.right) - Math.max(x.x, y.x), ih = Math.min(x.bottom, y.bottom) - Math.max(x.y, y.y);
          if (iw > 2 && ih > 2 && iw * ih > .12 * Math.min(x.width * x.height, y.width * y.height)) failures.push(`Overlapping text: ${text[a].value} / ${text[b].value}`);
        }
        const visuals = [...slide.querySelectorAll('svg.pic,svg[data-slide-visual],[data-slide-visual],img:not(.logo)')].filter(visible).map(el => {
          let marks;
          if (el instanceof SVGSVGElement) marks = [...el.querySelectorAll('rect,circle,ellipse,path,line,polyline,polygon,text,use,image')].filter(m => !m.closest('defs,clipPath,mask') && visible(m)).map(m => m.getBoundingClientRect());
          else marks = [el.getBoundingClientRect()];
          if (!marks.length) return { areaRatio: 0 };
          const left = Math.max(bounds.left, Math.min(...marks.map(m => m.left)));
          const right = Math.min(bounds.right, Math.max(...marks.map(m => m.right)));
          const top = Math.max(bounds.top, Math.min(...marks.map(m => m.top)));
          const bottom = Math.min(bounds.bottom, Math.max(...marks.map(m => m.bottom)));
          const box = { x: left, y: top, right, bottom, width: right - left, height: bottom - top };
          if (outside(box)) failures.push('Picture outside 6% safe area');
          return { areaRatio: Math.max(0, box.width) * Math.max(0, box.height) / (width * height), rect: box };
        });
        const visualAreaRatio = Math.max(0, ...visuals.map(v => v.areaRatio));
        for (const t of text.filter(t => !t.inVisual)) for (const v of visuals.filter(v => v.rect)) {
          const x = t.rect, y = v.rect;
          const iw = Math.min(x.right, y.right) - Math.max(x.x, y.x), ih = Math.min(x.bottom, y.bottom) - Math.max(x.y, y.y);
          if (iw > 2 && ih > 2 && iw * ih > .12 * x.width * x.height) failures.push(`Text overlaps picture: ${t.value}`);
        }
        if (width / height >= 1.7 && visualAreaRatio < .5 - .001) failures.push(`Picture area ${(visualAreaRatio * 100).toFixed(1)}% < 50%`);
        if (document.documentElement.scrollWidth > width + 1 || document.documentElement.scrollHeight > height + 1 || bounds.left < -1 || bounds.top < -1 || bounds.right > width + 1 || bounds.bottom > height + 1) failures.push('Slide or document overflows viewport');
        if (slide.scrollWidth > slide.clientWidth + 1 || slide.scrollHeight > slide.clientHeight + 1) failures.push('Slide content overflows its own box');
        for (const image of document.querySelectorAll('img,svg.logo, .logo-corner')) {
          if (!visible(image)) continue;
          if (outside(image.getBoundingClientRect())) failures.push('Image or logo outside 6% safe area');
          if (image instanceof HTMLImageElement && (!image.complete || !image.naturalWidth)) failures.push('Image did not load');
        }
        const fontFaces = [...document.fonts].map(f => ({ family: f.family, status: f.status }));
        if (fontFaces.some(f => f.status === 'error')) failures.push('An embedded font failed to load');
        const contentRects = [...text.map(t => t.rect), ...visuals.filter(v => v.rect).map(v => v.rect)];
        const marginsPx = { left: Math.min(...contentRects.map(r => r.x)),
          right: width - Math.max(...contentRects.map(r => r.right)),
          top: Math.min(...contentRects.map(r => r.y)),
          bottom: height - Math.max(...contentRects.map(r => r.bottom)) };
        const marginsFraction = { left: marginsPx.left / width, right: marginsPx.right / width,
          top: marginsPx.top / height, bottom: marginsPx.bottom / height };
        const minimumFontPx = Object.fromEntries(['title', 'body', 'label'].map(role => {
          const values = text.filter(t => t.role === role).map(t => t.actualPx);
          return [role, values.length ? Math.min(...values) : null];
        }));
        const overflowPx = { documentX: Math.max(0, document.documentElement.scrollWidth - width),
          documentY: Math.max(0, document.documentElement.scrollHeight - height),
          slideX: Math.max(0, slide.scrollWidth - slide.clientWidth),
          slideY: Math.max(0, slide.scrollHeight - slide.clientHeight) };
        const overlapFindings = failures.filter(f => f.startsWith('Overlapping text') || f.startsWith('Text overlaps picture'));
        return { id: slide.id, title: slide.querySelector('h1')?.textContent, bodyWords: words.length,
          visualAreaRatio, minimumFontPx, marginsPx, marginsFraction, overflowPx, overlapFindings,
          text, visuals, fontFaces, failures: [...new Set(failures)] };
      }, { width, height });
      if (metrics.id !== slideIds[index]) metrics.failures.push(`Navigation showed ${metrics.id}, expected ${slideIds[index]}`);
      const filename = `slide-${String(index + 1).padStart(2, '0')}-${width}x${height}.png`;
      await page.screenshot({ path: path.join(output, filename), animations: 'disabled' });
      const screenshot = await fs.readFile(path.join(output, filename));
      report.slides.push({ index: index + 1, width, height, revealSteps, revealFrames, ...metrics, screenshot: filename, screenshotSha256: sha256(screenshot) });
    }
    report.failures.push(...errors.map(e => `${width}: ${e}`));
    await page.close();
  }
} catch (error) {
  report.failures.push(String(error.stack || error));
} finally {
  await browser.close();
  if (sha256(await fs.readFile(source)) !== report.sourceSha256) report.failures.push('Deck source changed during gate');
  for (const stylesheet of localStylesheets) {
    try {
      if (sha256(await fs.readFile(stylesheet.path)) !== stylesheet.sha256) report.failures.push(`Stylesheet changed during gate: ${stylesheet.path}`);
    } catch { report.failures.push(`Stylesheet unavailable after gate: ${stylesheet.path}`); }
  }
  report.failedSlides = report.slides.filter(s => s.failures.length).length;
  report.passed = !report.failures.length && !report.failedSlides;
  await fs.writeFile(path.join(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ passed: report.passed, rendered: report.slides.length, failedSlides: report.failedSlides, failures: report.failures, report: path.join(output, 'report.json') }, null, 2));
  if (!report.passed) process.exitCode = 1;
}
