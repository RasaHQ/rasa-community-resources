// Rasa visual primitives, separate from the deck's story and wording.
// Each scene has an accessible title. Its labels count toward the 12-word limit.
const escape = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const text = (x, y, value, cls = 'label', anchor = 'start') => `<text x="${x}" y="${y}" class="${cls}" text-anchor="${anchor}">${escape(value)}</text>`;
const rect = (x, y, w, h, cls = 'panel', r = 20) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" class="${cls}"/>`;
const circle = (x, y, r, cls) => `<circle cx="${x}" cy="${y}" r="${r}" class="${cls}"/>`;
const line = (d, cls = 'line') => `<path d="${d}" class="${cls}"/>`;
const arrow = (x, y, length = 100) => line(`M${x} ${y}h${length}m-18 -16 18 16-18 16`, 'route');
const scene = (title, marks) => `<svg class="pic" data-slide-visual viewBox="0 0 1680 660" role="img" aria-label="${escape(title)}" xmlns="http://www.w3.org/2000/svg">${marks}</svg>`;
const icons = {
  flight: 'M-48 4 48-30 15 12-5 18-20 42-25 15Z M-25 15 48-30',
  weather: 'M-38 18h72a25 25 0 0 0-3-50 34 34 0 0 0-64 10 21 21 0 0 0-5 40 M-20 38l-9 15 M5 38l-9 15 M30 38l-9 15',
  timing: 'M0-48a48 48 0 1 0 1 0 M0-30v32l23 14',
  money: 'M-48-30h96v60h-96Z M0-16a16 16 0 1 0 0 32 16 16 0 1 0 0-32 M-34 0h1 M33 0h1',
  person: 'M0-38a18 18 0 1 0 1 0 M-35 42v-15a35 35 0 0 1 70 0v15',
  task: 'M-34-48h50l20 20v76h-70Z M16-48v22h20 M-17-4h34 M-17 15h34 M-17 34H5',
  builder: 'M-44-32h88v60h-88Z M-19-6-10-15 M19-6 10-15 M-22 45h44 M0 28v17',
  test: 'M-35-48h70v96h-70Z M-19-22l7 7 14-16 M-19 6l7 7 14-16 M-19 34l7 7 14-16',
  check: 'M-36 0-8 28 42-28',
  stop: 'M-30-30 30 30 M30-30-30 30',
  book: 'M0-30q-40-24-70-8v90q35-16 70 6 35-22 70-6v-90q-30-16-70 8v88',
};
const icon = (name, x, y, scale = 1, cls = '') => `<g transform="translate(${x} ${y}) scale(${scale})"><path d="${icons[name] || icons.task}" class="icon ${cls}"/></g>`;

/** Four equal domains, one focal traveller; connected=true shows one response. */
export function traveller({ labels = ['Flight', 'Weather', 'Timing', 'Money'], connected = false, title = 'A traveller and four sources' } = {}) {
  let marks = rect(0, 0, 1680, 660, 'panel-muted');
  const positions = [[210, 40], [1120, 40], [210, 370], [1120, 370]];
  positions.forEach(([x, y], i) => {
    if (connected) marks += line(`M${x < 840 ? x + 350 : x} ${y + 125}C840 ${y + 125} 840 ${y + 125} 840 330`, 'route');
    marks += rect(x, y, 350, 250, i === 3 && connected ? 'panel-gold' : 'panel');
    marks += icon(['flight', 'weather', 'timing', 'money'][i], x + 175, y + 90, 1.15);
    marks += text(x + 175, y + 204, labels[i], 'large-label', 'middle');
  });
  // Keep every connector behind the focal traveller, as in the brand's
  // connected-skills composition. Lines never cross the portrait.
  marks += circle(840, 330, 154, connected ? 'panel-ink' : 'panel-pink');
  marks += icon('person', 840, 322, 1.7, connected ? 'icon-light' : '');
  return scene(title, marks);
}

/** A spatially separated workbench and protected acceptance, not a box chain. */
export function protectedWorkbench({ labels = ['Builder', 'Change', 'Hidden tests', 'Decision'], title = 'The builder cannot edit the protected tests' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  m += rect(45, 45, 905, 570, 'panel');
  m += rect(90, 95, 320, 450, 'panel-pink');
  m += icon('builder', 250, 260, 2) + text(250, 460, labels[0], 'large-label', 'middle');
  m += arrow(435, 315, 90);
  m += rect(555, 175, 310, 300, 'panel-ink') + icon('task', 710, 280, 1.35, 'icon-light');
  m += text(710, 415, labels[1], 'large-label on-dark', 'middle');
  m += line('M1000 40v580', 'route');
  m += rect(1050, 45, 585, 570, 'panel-mint');
  m += icon('test', 1195, 230, 1.7) + text(1342, 410, labels[2], 'large-label', 'middle');
  m += icon('check', 1490, 230, 1.3, 'success') + text(1342, 535, labels[3], 'label', 'middle');
  return scene(title, m);
}

/** A clear forward sequence with an optional visibly refused branch. */
export function pipeline({ labels = ['Request', 'Build', 'Check', 'Integrate'], highlight = 2, title = 'The factory checks each change before integration' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  labels.forEach((label, i) => {
    const x = 40 + i * 420;
    m += rect(x, 88, 340, 485, i === highlight ? 'panel-pink' : i === 3 ? 'panel-mint' : 'panel');
    m += text(x + 36, 157, String(i + 1).padStart(2, '0'), 'mono muted');
    m += icon(['task', 'builder', 'test', 'check'][i], x + 170, 320, 1.8);
    m += text(x + 170, 505, label, 'large-label', 'middle');
    if (i < labels.length - 1) m += arrow(x + 350, 330, 60);
  });
  return scene(title, m);
}

/** Two complementary tools around a single product, not two competing stacks. */
export function tools({ labels = ['Rasa Mantle', 'Agent', 'OpenAI Agents API', 'Builder'], title = 'One tool runs the agent, the other builds changes' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  m += rect(40, 40, 750, 580, 'panel-ink') + rect(890, 40, 750, 580, 'panel-pink');
  m += text(95, 135, labels[0], 'large-label on-dark') + text(945, 135, labels[2], 'large-label');
  m += icon('person', 415, 330, 2.3, 'icon-light') + icon('builder', 1265, 330, 2.3);
  m += text(415, 540, labels[1], 'large-label on-dark', 'middle') + text(1265, 540, labels[3], 'large-label', 'middle');
  // The builder supplies a change to the agent, so the arrow points left.
  m += line('M890 330H790m18-16-18 16 18 16', 'route');
  return scene(title, m);
}

export function decision({ labels = ['Accept', 'Reject', 'Could not run'], title = 'A decision distinguishes failure from inability to run' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  labels.forEach((label, i) => {
    const x = 40 + i * 560;
    m += rect(x, 45, 480, 570, ['panel-mint', 'panel-orange', 'panel'][i]);
    m += icon(['check', 'stop', 'timing'][i], x + 240, 270, 2);
    m += text(x + 240, 510, label, 'large-label', 'middle');
  });
  return scene(title, m);
}

export function chapters({ labels = ['Task', 'Tests', 'Builder', 'Checks', 'Integrate'], title = 'Build the factory one chapter at a time' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  labels.forEach((label, i) => {
    const x = 40 + i * 325, y = 160 - i * 25;
    m += rect(x, y, 300, 450, i === labels.length - 1 ? 'panel-pink' : 'panel');
    m += line(`M${x + 22} ${y}v450`, 'route');
    m += text(x + 58, y + 95, String(i + 3).padStart(2, '0'), 'display');
    m += icon('book', x + 150, y + 240, .8);
    m += text(x + 150, y + 380, label, 'label', 'middle');
  });
  return scene(title, m);
}

/** One running story: ask, select a real result, then get the briefing. */
export function conversation({ labels = ['Ask', 'Choose', 'Briefing'], title = 'Start with a question, not a known flight number' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  m += rect(45, 45, 630, 570, 'panel-ink');
  m += circle(155, 155, 58, 'panel-pink') + icon('person', 155, 155, .85);
  m += rect(245, 100, 360, 110, 'panel-pink') + text(425, 170, labels[0], 'large-label', 'middle');
  m += line('M280 255h285M280 290h225M280 325h265', 'line');
  m += rect(110, 400, 495, 140, 'panel-pink') + icon('check', 175, 470, .75);
  m += text(370, 486, labels[1], 'large-label', 'middle');
  m += arrow(700, 330, 140);
  m += rect(875, 45, 760, 570, 'panel');
  m += text(930, 122, labels[2], 'large-label');
  ['flight', 'weather', 'timing', 'money'].forEach((name, i) => {
    const x = 930 + (i % 2) * 330, y = 165 + Math.floor(i / 2) * 210;
    m += rect(x, y, 290, 175, i === 3 ? 'panel-gold' : 'panel-muted');
    m += icon(name, x + 145, y + 85, 1.05);
  });
  return scene(title, m);
}

/** A reusable eight-part orientation; times and directions are content-owned. */
export function roadmap({ labels = ['Problem', 'Agent', 'Question', 'Factory', 'Tools', 'Build', 'Practice', 'Close'], active = 0, title = 'Follow one story from a traveller to your own factory' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  m += line('M205 180H1475V480H205', 'route');
  labels.forEach((label, i) => {
    const row = i < 4 ? 0 : 1, col = row ? 7 - i : i;
    const x = 40 + col * 420, y = 35 + row * 330;
    m += rect(x, y, 340, 260, i === active ? 'panel-pink' : 'panel');
    m += circle(x + 55, y + 60, 12, i === active ? 'panel-ink' : 'panel-muted');
    m += text(x + 170, y + 175, label, 'large-label', 'middle');
  });
  return scene(title, m);
}

/** A hub of capabilities. The content owner supplies verified feature names. */
export function capabilityHub({ center = 'Agent', labels = ['Skills', 'Flows', 'Tools', 'Responses', 'Voice', 'Testing'], title = 'Capabilities connect to one running agent' } = {}) {
  let m = rect(0, 0, 1680, 660, 'panel-muted');
  const positions = [[45, 35], [45, 245], [45, 455], [1195, 35], [1195, 245], [1195, 455]];
  positions.forEach(([x, y], i) => {
    m += line(`M${x < 840 ? x + 440 : x} ${y + 85}C840 ${y + 85} 840 ${y + 85} 840 330`, 'route');
    m += rect(x, y, 440, 170, i === 0 ? 'panel-pink' : 'panel');
    m += text(x + 220, y + 100, labels[i], 'large-label', 'middle');
  });
  m += circle(840, 330, 190, 'panel-ink') + icon('person', 840, 280, 1.5, 'icon-light');
  m += text(840, 440, center, 'large-label on-dark', 'middle');
  return scene(title, m);
}

export { scene, text, rect, icon, line, arrow };
