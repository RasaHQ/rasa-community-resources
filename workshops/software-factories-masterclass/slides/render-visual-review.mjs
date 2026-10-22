#!/usr/bin/env node
// Component review only. The finished deck's story and wording live in build-deck.mjs.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as diagrams from './visual-diagrams.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const i = process.argv.indexOf('--out');
const output = path.resolve(i < 0 ? 'visual-system-review' : process.argv[i + 1]);
const seed = await fs.readFile(path.join(here, 'index.html'), 'utf8');
const fonts = [...seed.matchAll(/@font-face\{[^}]+\}/g)].map(m => m[0]).join('\n');
if (!fonts || /font-family\s*:\s*['"]?STK/i.test(fonts)) throw Error('Expected the existing embedded OFL fallback faces only');
const css = await fs.readFile(path.join(here, 'visual-system.css'), 'utf8');
const samples = [
  ['A traveller needs four answers, all at once.', diagrams.traveller()],
  ['One agent brings those answers together.', diagrams.traveller({ connected: true })],
  ['The factory checks a change before it reaches your product.', diagrams.pipeline()],
  ['The builder cannot change the tests that judge its work.', diagrams.protectedWorkbench()],
  ['One tool runs the agent; the other builds changes.', diagrams.tools()],
  ['A wrong change differs from a check that could not run.', diagrams.decision()],
  ['Build your factory one chapter at a time.', diagrams.chapters()],
  ['Start with a question, then choose a flight.', diagrams.conversation()],
  ['Follow one story from a traveller to your own factory.', diagrams.roadmap()],
  ['Several capabilities support one running agent.', diagrams.capabilityHub()],
];
const escape = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
let html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rasa masterclass visual system — review draft</title><!-- Component review. OFL font licences accompany this file in FONT-LICENSES.txt. --><style>${fonts}\n${css}</style></head><body>`;
samples.forEach(([title, svg], n) => {
  html += `<section class="slide ${n ? '' : 'on'}" id="s${n + 1}"><nav class="crumb" aria-label="Where you are"><span>Visual system / review draft</span><span>${n + 1} of ${samples.length}</span></nav><h1>${escape(title)}</h1><div class="scene">${svg}</div></section>`;
});
html += `<script>
const slides=[...document.querySelectorAll('.slide')];let current=0;
function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('on',i===current));history.replaceState(null,'','#'+(current+1))}
document.addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}if(e.key==='Home'){e.preventDefault();show(0)}if(e.key==='End'){e.preventDefault();show(slides.length-1)}});
addEventListener('hashchange',()=>show(Number(location.hash.slice(1))-1||0));show(Number(location.hash.slice(1))-1||0);
</script></body></html>`;
await fs.mkdir(output, { recursive: true });
await fs.writeFile(path.join(output, 'index.html'), html);
await fs.copyFile(path.join(here, 'FONT-LICENSES.txt'), path.join(output, 'FONT-LICENSES.txt'));
console.log(`Component review: ${samples.length} scenes in ${path.join(output, 'index.html')}`);
