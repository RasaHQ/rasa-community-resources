#!/usr/bin/env node
// sow: software-factories-masterclass-SOW-02
// Deliberately broken fixtures prove that the slide gate rejects each failure.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const here = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(option('--out', 'slide-layout-controls'));
const playwright = option('--playwright', 'playwright-core');
const original = `<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%}
.slide{display:none;position:absolute;inset:0;background:#FAF6F0}.slide.on{display:block}
nav{position:absolute;top:6.5vh;left:6.5vw;font:1.666667vw/1.2 monospace}
h1{position:absolute;top:13vh;left:6.5vw;margin:0;font:4.166667vw/1.1 Georgia}
.scene{position:absolute;left:6.25vw;top:31.481481vh;width:87.5vw;height:61.111111vh}
svg{width:100%;height:100%}text{font:36px Arial}
</style></head><body><section id="s1" class="slide on"><nav>Part 1 / Example</nav>
<h1>One clear idea belongs on each slide.</h1><div class="scene">
<svg class="pic" viewBox="0 0 1680 660" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Test scene">
<rect width="1680" height="660" fill="#EDE8E0"/><rect x="60" y="60" width="700" height="540" fill="#FCE7EF"/>
<text x="100" y="200">Example</text></svg></div></section></body></html>`;
const style = (html, css) => html.replace('</style>', `${css}</style>`);
const cases = [
  { id: 'good', mutate: h => h, expects: null },
  { id: 'small-title', mutate: h => style(h, 'h1{font-size:20px}'), expects: 'Small title' },
  { id: 'small-label', mutate: h => style(h, 'text{font-size:12px}'), expects: 'Small label' },
  { id: 'thin-margin', mutate: h => style(h, 'nav{left:0}'), expects: 'safe area' },
  { id: 'overflow', mutate: h => style(h, '.scene{top:95vh}'), expects: 'overflows' },
  { id: 'empty-visual', mutate: h => h.replace(/(<svg[^>]+>)[\s\S]*?<\/svg>/, '$1</svg>'), expects: 'Picture area' },
  { id: 'tiny-visual', mutate: h => style(h, '.scene{width:10vw;height:10vh}'), expects: 'Picture area' },
  { id: 'excess-words', mutate: h => h.replace('</svg>', '<text x="100" y="600">one two three four five six seven eight nine ten eleven twelve thirteen</text></svg>'), expects: 'Body words' },
  { id: 'overlapping-labels', mutate: h => h.replace('</svg>', '<text x="100" y="200">Overlap</text></svg>'), expects: 'Overlapping text' },
  { id: 'picture-overlap', mutate: h => style(h, 'h1{top:40vh}'), expects: 'Text overlaps picture' },
  { id: 'bullet-list', mutate: h => h.replace('</section>', '<ul><li>Example</li></ul></section>'), expects: 'Bullet/list' },
  { id: 'global-chrome', mutate: h => h.replace('</body>', '<div style="position:fixed;left:0;top:0;font-size:8px">Footer</div></body>'), expects: 'Small label' },
  { id: 'navigation', mutate: h => h.replace('</body>', '<section class="slide" id="s2"><h1>Second slide</h1></section></body>'), expects: 'Navigation showed', slides: 2 },
];
await fs.mkdir(output, { recursive: true });
const results = [];
for (const c of cases) {
  const dir = path.join(output, c.id);
  await fs.mkdir(dir, { recursive: true });
  const deck = path.join(dir, 'index.html');
  await fs.writeFile(deck, c.mutate(original));
  const run = spawnSync(process.execPath, [path.join(here, 'check-layout.mjs'), '--playwright', playwright, '--deck', deck, '--out', dir], { encoding: 'utf8', timeout: 30000 });
  let report;
  try { report = JSON.parse(await fs.readFile(path.join(dir, 'report.json'), 'utf8')); }
  catch { results.push({ id: c.id, passed: false, error: run.error?.message || run.stderr || run.stdout }); continue; }
  const expectedViews = 2 * (c.slides || 1);
  const passed = c.expects
    ? run.status === 1 && report.slides.length === expectedViews && report.slides.filter(s => s.failures.some(f => f.includes(c.expects))).length >= 2
    : run.status === 0 && report.passed && report.slides.length === expectedViews;
  results.push({ id: c.id, passed, expected: c.expects || 'PASS', exit: run.status,
    rendered: report.slides.length, report: path.join(dir, 'report.json') });
  console.log(`${c.id}: ${passed ? 'PASS' : 'FAIL'}`);
}
await fs.writeFile(path.join(output, 'results.json'), JSON.stringify(results, null, 2) + '\n');
if (results.some(r => !r.passed)) process.exitCode = 1;
