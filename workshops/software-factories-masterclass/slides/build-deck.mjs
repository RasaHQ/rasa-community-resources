#!/usr/bin/env node
// Builds index.html: 30 slides, one story (Sam and the four cards), from the visual system's scenes and styles.
// Usage: node build-deck.mjs        (run from this folder; writes index.html)
import fs from 'node:fs';
import { traveller, protectedWorkbench, pipeline, tools, decision, chapters, conversation } from './visual-diagrams.mjs';

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const text = (x, y, v, cls = 'label', a = 'middle') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${a}">${esc(v)}</text>`;
const rect = (x, y, w, h, cls = 'panel', r = 20) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" class="${cls}"/>`;
const circle = (x, y, r, cls) => `<circle cx="${x}" cy="${y}" r="${r}" class="${cls}"/>`;
const line = (d, cls = 'line') => `<path d="${d}" class="${cls}"/>`;
const arrow = (x, y, len = 100) => line(`M${x} ${y}h${len}m-18 -16 18 16-18 16`, 'route');
const scene = (title, marks) => `<svg class="pic" data-slide-visual viewBox="0 0 1680 660" role="img" aria-label="${esc(title)}" xmlns="http://www.w3.org/2000/svg">${marks.startsWith('<rect x="0" y="0" width="1680"') ? '' : rect(0, 0, 1680, 660, 'panel-muted')}${marks}</svg>`;
const ICON = {
  person: 'M0-38a18 18 0 1 0 1 0 M-35 42v-15a35 35 0 0 1 70 0v15',
  task: 'M-34-48h50l20 20v76h-70Z M16-48v22h20 M-17-4h34 M-17 15h34 M-17 34H5',
  builder: 'M-44-32h88v60h-88Z M-19-6-10-15 M19-6 10-15 M-22 45h44 M0 28v17',
  test: 'M-35-48h70v96h-70Z M-19-22l7 7 14-16 M-19 6l7 7 14-16 M-19 34l7 7 14-16',
  check: 'M-36 0-8 28 42-28',
  stop: 'M-30-30 30 30 M30-30-30 30',
};
const icon = (n, x, y, s = 1, cls = '') => `<g transform="translate(${x} ${y}) scale(${s})"><path d="${ICON[n]}" class="icon ${cls}"/></g>`;
// a row of N panels with a big label (and optional small label) each
function row(items, { y = 150, h = 360, gap = 40, cls = 'panel', arrows = true } = {}) {
  const n = items.length, w = (1680 - 120 - gap * (n - 1)) / n;
  let m = '';
  items.forEach((it, i) => {
    const x = 60 + i * (w + gap);
    m += rect(x, y, w, h, it.cls || cls);
    if (it.icon) m += icon(it.icon, x + w / 2, y + h * 0.36, 1.5, it.iconCls || '');
    m += text(x + w / 2, y + h * (it.icon ? 0.78 : 0.5), it.label, it.big ? 'large-label' : 'large-label');
    if (it.sub) m += text(x + w / 2, y + h * 0.9, it.sub, 'label muted');
    if (arrows && i < n - 1) m += arrow(x + w + 6, y + h / 2, gap - 12 > 20 ? gap - 12 : 20);
  });
  return m;
}

const S = [];
const add = (part, title, body, svg, cls = '') => S.push({ part, title, body, svg, cls });
const PARTS = ['The problem', 'The finished agent', 'The real question', 'The factory idea', 'The two tools', 'We build the factory', 'Your turn', 'Close'];

// ---- Part 1: the problem
add(1, 'Build a *factory* that builds your agent.', 'Agents you can trust.', traveller({ connected: true, title: 'Sam and four answers on one screen' }), 'dark');
add(1, 'Meet *Sam*, due in New York tonight.', 'Four websites. One answer.', traveller({ title: 'Sam needs four checks' }));
add(1, 'An *agent* can do Sam’s four checks.', 'An agent decides, then does.', traveller({ connected: true, title: 'One agent answers all four' }));
add(1, 'Today in London: *see it*, *learn it*, *build it*.', 'Break 16:30.', scene('The plan for the day',
  row([{ label: '14:30', sub: 'See' }, { label: '14:45', sub: 'Learn' }, { label: '15:15', sub: 'Build' }, { label: '15:45', sub: 'Practice' }, { label: '17:20', sub: 'Close' }], { y: 150, h: 360, gap: 30 })));
// ---- Part 2: the finished agent
add(2, 'Watch the agent answer Sam.', 'Type: Which flights are headed to New York?', conversation({ labels: ['Ask', 'Choose', 'Briefing'], title: 'Ask, choose a flight, get the briefing' }));
add(2, 'Every card says *where it came from*.', 'Every value is labeled.', scene('Four labels',
  row([{ label: 'Source', cls: 'panel-mint' }, { label: 'Computed', cls: 'panel-gold' }, { label: 'Recording', cls: 'panel-pink' }, { label: 'Failed', cls: 'panel-orange' }], { y: 130, h: 400, gap: 30, arrows: false })));
add(2, 'Four *honest* cards. Next: trust.', 'Sam can trust each value.', traveller({ connected: true, title: 'Four honest cards' }));
// ---- Part 3: the real question
add(3, 'A coding agent *reports* success.', 'It changes files, then says it worked.', scene('You ask, the coding agent edits files and says it worked',
  icon('person', 200, 250, 2) + text(200, 420, 'You', 'large-label') + arrow(340, 300, 140)
  + rect(520, 140, 380, 360, 'panel-ink') + icon('builder', 710, 290, 2, 'icon-light') + text(710, 450, 'Coding agent', 'large-label on-dark')
  + arrow(930, 300, 140) + rect(1100, 140, 300, 360, 'panel') + icon('task', 1250, 290, 1.8) + text(1250, 450, 'Files', 'large-label')
  + rect(1180, 540, 440, 90, 'panel-pink', 45)));
add(3, 'Nobody can *read* every change.', 'Ten times the code.', scene('Ten agents write ten times the code',
  Array.from({ length: 10 }, (_, i) => rect(80 + i * 110, 120 + (i % 3) * 40, 90, 150, 'panel', 10)).join('') + icon('person', 1400, 450, 2) + text(840, 560, 'Ten agents', 'large-label')));
add(3, 'A *test* checks a known answer.', '', scene('add(2, 2) must give 4',
  rect(60, 170, 460, 320, 'panel') + text(290, 310, 'add(2, 2)', 'large-label') + arrow(540, 330, 140)
  + rect(720, 80, 380, 200, 'panel-mint') + text(910, 205, '4 pass', 'large-label') + rect(720, 380, 380, 200, 'panel-orange') + text(910, 505, '5 fail', 'large-label')
  + arrow(1120, 330, 100) + rect(1240, 170, 380, 320, 'panel-pink') + icon('test', 1430, 300, 1.8) + text(1430, 450, 'Test', 'large-label')));
add(3, 'An *acceptance test* checks the request.', 'Tests what was asked.', scene('A request is checked against a list',
  rect(60, 150, 420, 360, 'panel-pink') + text(270, 340, 'Request', 'large-label') + arrow(500, 330, 110)
  + rect(640, 60, 640, 540, 'panel') + ['Rows', 'Labels', 'Day', 'Source'].map((t, i) => icon('check', 720, 150 + i * 120, 0.8, 'success') + text(830, 165 + i * 120, t, 'large-label', 'start')).join('')
  + arrow(1300, 330, 100) + rect(1440, 220, 200, 220, 'panel-mint') + text(1540, 345, 'Pass', 'large-label')));
add(3, 'We can’t read it all, so *tests decide*.', 'A claim proves nothing. A passing test does.', scene('Claim and proof',
  rect(80, 120, 700, 420, 'panel-orange') + text(430, 350, 'Claim', 'large-label') + rect(900, 120, 700, 420, 'panel-mint') + text(1250, 350, 'Proof', 'large-label')));
// ---- Part 4: the factory idea
add(4, 'A software factory repeats *four steps*.', 'Sam’s request rides through.', pipeline({ labels: ['Task', 'Change', 'Check', 'Decision'], highlight: 2, title: 'Task, change, check, decision' }));
add(4, 'The builder works in a *spare copy*.', 'The builder makes the change.', scene('Only the changed lines come back',
  rect(60, 150, 440, 360, 'panel') + text(280, 340, 'Product', 'large-label') + arrow(520, 330, 100)
  + rect(660, 150, 440, 360, 'panel-gold') + icon('builder', 880, 280, 1.6) + text(880, 450, 'Copy', 'large-label') + arrow(1120, 330, 100)
  + rect(1260, 200, 360, 260, 'panel-mint') + text(1440, 315, 'Changed', 'large-label') + text(1440, 375, 'lines', 'large-label')));
add(4, 'Tests come first, *hidden* from the builder.', 'Like an exam.', protectedWorkbench({ labels: ['Builder', 'Change', 'Hidden tests', 'Decision'], title: 'The builder cannot see the protected tests' }));
add(4, 'A *fingerprint* shows a changed test.', 'One letter changes it.', scene('Same file, different fingerprint',
  rect(80, 130, 660, 400, 'panel-mint') + text(410, 250, 'tests', 'large-label') + text(410, 420, 'ab12', 'display pink-ink')
  + rect(940, 130, 660, 400, 'panel-orange') + text(1270, 250, 'tests', 'large-label') + text(1270, 420, '9f3c', 'display pink-ink')));
add(4, 'Every request ends in *three answers*.', 'Could not run: a machine problem.', decision({ labels: ['Accept', 'Reject', 'Could not run'], title: 'Accept, reject or could not run' }));
add(4, 'Two good changes can *clash*.', 'Replay the checks.', scene('Change two erases change one',
  rect(60, 250, 260, 160, 'panel') + text(190, 345, 'Base', 'large-label') + arrow(340, 300, 120) + line('M340 360C440 360 440 470 520 470', 'route')
  + rect(540, 90, 400, 200, 'panel-mint') + text(740, 205, 'Change 1', 'large-label') + rect(540, 400, 400, 200, 'panel-mint') + text(740, 515, 'Change 2', 'large-label')
  + arrow(980, 330, 120) + rect(1140, 230, 480, 200, 'panel-orange') + text(1380, 345, 'Gone', 'large-label')));
add(4, 'A dark factory has *one reviewer*: tests.', 'Lights off. Nobody reads each change.', scene('One lit window labeled tests',
  rect(0, 0, 1680, 660, 'panel-ink', 0) + rect(540, 130, 600, 400, 'panel-gold') + text(840, 355, 'Tests', 'large-label ink') + icon('person', 1400, 330, 1.8, 'icon-light') + text(1400, 460, 'Person', 'large-label on-dark')), 'dark');
add(4, 'A few wins *aren’t a guarantee*.', 'Three heads in a row prove nothing.', scene('Three heads in a row',
  [0, 1, 2].map(i => circle(260 + i * 260, 250, 100, 'panel-gold') + text(260 + i * 260, 285, 'H', 'display')).join('') + text(1230, 330, '?', 'display pink-ink')));
// ---- Part 5: the two tools
add(5, '*Rasa Mantle* is where our agent lives.', 'A folder of files you can read.', scene('Files become a running agent',
  rect(60, 150, 440, 360, 'panel') + icon('task', 280, 280, 1.7) + text(280, 450, 'Files', 'large-label') + arrow(520, 330, 100)
  + rect(660, 150, 440, 360, 'panel-pink') + text(880, 345, 'Rasa Mantle', 'large-label') + arrow(1120, 330, 100)
  + rect(1260, 150, 360, 360, 'panel-mint') + icon('person', 1440, 280, 1.7) + text(1440, 450, 'Agent', 'large-label')));
add(5, 'The agent calls *tools*.', 'A skill says when. MCP offers the tools.', scene('Skill, agent, tool, cards',
  row([{ label: 'Skill' }, { label: 'Agent', cls: 'panel-pink' }, { label: 'Tool' }, { label: 'Cards', cls: 'panel-mint' }], { y: 150, h: 360, gap: 70 })));
add(5, 'The *inspector* shows what the agent did.', 'Chat on the left, steps on the right.', scene('Chat on the left, steps on the right',
  rect(60, 60, 740, 540, 'panel') + text(430, 150, 'Chat', 'large-label') + rect(880, 60, 740, 540, 'panel-mint') + text(1250, 150, 'Steps', 'large-label')));
add(5, 'The builder runs on *OpenAI’s Agents API*.', 'An API lets one program ask another.', scene('The builder asks, our code runs it',
  row([{ label: 'Builder', icon: 'builder' }, { label: 'Asks' }, { label: 'Our code', cls: 'panel-gold' }, { label: 'Result', cls: 'panel-mint' }], { y: 150, h: 360, gap: 70 })));
add(5, 'A run has *limits* and a secret key.', 'A key is a paid-service password.', scene('Time, tool calls and a key',
  row([{ label: 'Time' }, { label: 'Tool calls' }, { label: 'Key', cls: 'panel-pink' }], { y: 150, h: 360, gap: 70, arrows: false })));
add(5, 'Mantle is home. The API is the *builder*.', 'Next: we build.', tools({ labels: ['Rasa Mantle', 'Agent', 'OpenAI Agents API', 'Builder'], title: 'Mantle is home and the API is the builder' }));
// ---- Part 6: we build the factory
add(6, 'We build the factory in *five parts*.', 'Book chapters', chapters({ labels: ['Task', 'Tests', 'Builder', 'Checks', 'Integrate'], title: 'Five parts, five chapters' }));
add(6, 'In your chapter 6 folder: judge a *good* change and a *bad* one.', '', scene('Run the gate on a good change and a bad one',
  rect(0, 0, 1680, 660, 'panel-ink', 0) + text(60, 110, '$ source .venv/bin/activate', 'mono on-dark', 'start')
  + text(60, 270, '$ python run_a6.py tasks/a6-market-watchlist.json candidates/market-good', 'mono on-dark', 'start') + icon('check', 160, 350, 1.1, 'success').replace('icon success', 'icon" style="stroke:#C6FEE1;stroke-width:9')
  + text(60, 500, '$ python run_a6.py tasks/a6-market-watchlist.json candidates/market-shows-live', 'mono on-dark', 'start') + icon('stop', 160, 580, 1.0, '').replace('icon ', 'icon" style="stroke:#FFB28C;stroke-width:9')), 'dark');
// ---- Part 7: your turn
add(7, 'Set up once, then follow the *book*.', 'Chapter 0 first.', scene('Clone the repository and open the book',
  rect(0, 0, 1680, 660, 'panel-ink', 0) + text(60, 140, '$ git clone https://github.com/RasaHQ/rasa-community-resources.git', 'mono on-dark', 'start')
  + text(60, 280, '$ cd rasa-community-resources/workshops/software-factories-masterclass/book', 'mono on-dark', 'start')
  + text(60, 450, 'license: rasa.com/rasa-pro-developer-edition-license-key-request', 'mono pink-ink', 'start').replace('class="mono pink-ink"', 'class="mono" style="fill:#F096B9"')), 'dark');
// ---- Part 8: close
add(8, 'One agent, built by a *factory you trust*.', 'Write the tests first.', traveller({ connected: true, title: 'One agent, four cards, one factory' }));

const CSS = fs.readFileSync('visual-system.css', 'utf8');
const face = (family, file, weight, style = 'normal') => `@font-face{font-family:'${family}';font-weight:${weight};font-style:${style};font-display:swap;src:url(data:font/woff2;base64,${fs.readFileSync('fonts/' + file).toString('base64')}) format('woff2')}`;
const FACES = [face('Inter', 'Inter-Regular.woff2', 400), face('Inter', 'Inter-Medium.woff2', 500), face('Newsreader', 'Newsreader-Regular.woff2', 400), face('Newsreader', 'Newsreader-Italic.woff2', 400, 'italic'), face('JetBrains Mono', 'JetBrainsMono-Regular.woff2', 400)].join('');
const em = t => esc(t).replace(/\*(.+?)\*/g, '<em>$1</em>');
const counts = {}; S.forEach(s => { counts[s.part] = (counts[s.part] || 0) + 1; });
const seen = {};
const html = S.map((s, i) => {
  seen[s.part] = (seen[s.part] || 0) + 1;
  const prog = Array.from({ length: 8 }, (_, k) => `<i class="${k + 1 === s.part ? 'active' : ''}"></i>`).join('');
  return `<section class="slide${s.cls ? ' ' + s.cls : ''}${i === 0 ? ' on' : ''}" id="s${i + 1}"><nav class="crumb" aria-label="Where you are"><span>Part ${s.part} of 8 · ${esc(PARTS[s.part - 1])} · Slide ${seen[s.part]} of ${counts[s.part]}</span><span class="progress">${prog}</span></nav><h1>${em(s.title)}</h1>${s.body ? `<p class="words" data-slide-chrome-no>${esc(s.body)}</p>` : ''}<div class="scene">${s.svg}</div></section>`;
}).join('\n');
const JS = `const slides=[...document.querySelectorAll('.slide')];let current=0;
function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('on',i===current));history.replaceState(null,'','#'+(current+1))}
document.addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1)}if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();show(current-1)}if(e.key==='Home'){e.preventDefault();show(0)}if(e.key==='End'){e.preventDefault();show(slides.length-1)}});
document.addEventListener('click',e=>{if(e.target.closest('a'))return;show(current+(e.clientX<innerWidth/3?-1:1))});
addEventListener('hashchange',()=>show(Number(location.hash.slice(1))-1||0));show(Number(location.hash.slice(1))-1||0);`;
const EXTRA = `.slide .words{position:absolute;left:6.25vw;right:6.25vw;top:23.6vh;margin:0;font:400 2.0833vw/1.2 var(--sans)}.dark .words{color:var(--cream)}`;
const page = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Software factories masterclass</title><!-- Fonts: Inter, Newsreader and JetBrains Mono, Latin subsets, SIL Open Font License 1.1 (see FONT-LICENSES.txt beside this file). The Rasa brand fonts are not redistributable. --><style>${FACES}${CSS}${EXTRA}</style></head><body>${html}<script>${JS}</script></body></html>`;
fs.writeFileSync('index.html', page);
console.log(S.length, 'slides,', page.length, 'bytes');
