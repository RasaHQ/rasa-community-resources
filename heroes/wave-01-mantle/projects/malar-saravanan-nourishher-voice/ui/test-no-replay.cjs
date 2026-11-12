const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const networking = html.slice(html.indexOf('async function postMessage('), html.indexOf('// Voice —'));

async function turn(mode) {
  const persisted = [];
  const messages = [];
  const context = {
    WEBHOOK: 'http://fixture.invalid/webhook', SENDER: 'fixture-sender', API_BASE: 'fixture',
    fetch: async (_url, options) => {
      persisted.push(JSON.parse(options.body).message); // the effect commits before the empty/failed response
      if (mode === 'network') throw new Error('connection ended after persistence');
      return { ok: mode !== 'error', status: 500, json: async () => mode === 'success' ? [{text: 'Saved.'}] : [] };
    },
    sendBtn: {disabled: false}, inputEl: {value: '', focus() {}},
    autoGrow() {}, showTyping() {}, hideTyping() {}, setStatus() {},
    addMessage: (role, text) => messages.push({role, text}), speakOn: false, speak() {},
    setTimeout: callback => callback(),
  };
  await vm.runInNewContext(networking + '; send("record item");', context);
  return {persisted, messages, context};
}
for (const mode of ['empty', 'error', 'network']) {
  test(`a committed effect followed by ${mode} outcome is never automatically replayed`, async () => {
    const result = await turn(mode);
    assert.equal(result.persisted.length, 1);
    assert.equal(result.context.sendBtn.disabled, false);
    assert.match(result.messages.filter(m => m.role === 'bot').map(m => m.text).join(' '), /check|confirm/i);
  });
}
test('a normal reply is displayed after a single submission', async () => {
  const result = await turn('success');
  assert.equal(result.persisted.length, 1);
  assert.ok(result.messages.some(m => m.role === 'bot' && m.text === 'Saved.'));
});
