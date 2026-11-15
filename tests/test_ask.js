// Run with: node tests/test_ask.js
const fs = require('fs'), path = require('path'), assert = require('assert');
const Ask = require('../ask.js');
const rules = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'rules.json'), 'utf8'));
const now = { date: '2026-11-16', minutes: 600, weekStart: '2026-11-16' };
const morning = { date: '2026-11-16', slept: true, calm: true, watchlist: ['INFY'] };
const t = (minutes, pnl, extra) => Object.assign({ date: '2026-11-16', minutes, pnl, paper: false }, extra);
const ctx = (over) => Object.assign({ rules, now, state: { morning, trades: [], blocked: [] } }, over);
let n = 0;
function test(name, fn) { try { fn(); n++; } catch (e) { console.log('FAIL', name, '\n  ', e.message); process.exitCode = 1; } }
const ask = (q, c) => Ask.answer(q, c || ctx());

test('status shows loss and limits', () => {
  const r = ask('how much have I lost today?', ctx({ state: { morning, trades: [t(560, -100)], blocked: [] } }));
  assert.strictEqual(r.intent, 'status'); assert.ok(r.text.includes('\u20B9-100') && r.text.includes('1 real trade') && r.text.includes('-\u20B9300'));
});
test('status notes trades without results', () => {
  const r = ask("today's p&l", ctx({ state: { morning, trades: [t(560, null)], blocked: [] } }));
  assert.ok(r.text.includes('without a result'));
});
test('status flags the daily limit', () => {
  const r = ask('p&l today', ctx({ state: { morning, trades: [t(540, -150), t(560, -150)], blocked: [] } }));
  assert.ok(r.text.includes('Daily limit reached'));
});
test('can I trade now: yes', () => {
  const r = ask('Can I trade now?', ctx({ state: { morning, trades: [t(560, -100)], blocked: [] } }));
  assert.strictEqual(r.intent, 'can_trade'); assert.ok(r.text.startsWith('Yes') && r.text.includes('\u20B9150') && r.text.includes('1 of 3'));
});
test('can I trade now: cooldown', () => {
  const r = ask('can I take another trade', ctx({ state: { morning, trades: [t(595, -100)], blocked: [] } }));
  assert.ok(r.text.startsWith('Not now') && r.text.includes('Wait 10 more minutes'));
});
test('can I trade now: no morning check', () => {
  const r = ask('can i trade', ctx({ state: { morning: null, trades: [], blocked: [] } }));
  assert.ok(r.text.startsWith('Not now') && r.text.includes('morning check'));
});
test('can I trade now: outside window', () => {
  const r = ask('can I trade now', ctx({ now: Object.assign({}, now, { minutes: 16 * 60 + 10 }) }));
  assert.ok(r.text.startsWith('Not now') && r.text.includes('16:10'));
});
test('risk shrinks as the day budget shrinks', () => {
  const r = ask('how much can I risk', ctx({ state: { morning, trades: [t(540, -250)], blocked: [] } }));
  assert.strictEqual(r.intent, 'risk'); assert.ok(r.text.includes('up to \u20B950'));
});
test('size: 150 / 2 = 75 shares and a 2 to 1 target', () => {
  const r = ask('how many shares entry 100 stop 98');
  assert.strictEqual(r.intent, 'size'); assert.ok(r.text.includes('75 shares') && r.text.includes('\u20B9104'));
});
test('size respects what is left today', () => {
  const r = ask('how many shares entry 100 stop 98', ctx({ state: { morning, trades: [t(540, -250)], blocked: [] } }));
  assert.ok(r.text.includes('25 shares'));
});
test('size rejects a stop above entry and too-wide stops', () => {
  assert.ok(ask('quantity entry 100 stop 102').text.includes('below the entry'));
  assert.ok(ask('shares entry 1000 stop 800').text.includes('Even 1 share'));
});
test('size without numbers explains the format', () => {
  assert.strictEqual(ask('shares entry').intent, 'size');
  assert.ok(ask('shares entry').text.includes('how many shares entry 100 stop 98'));
});
test('glossary: vwap and r-multiple', () => {
  assert.ok(ask('what is vwap?').text.includes('volume-weighted'));
  assert.strictEqual(ask('what does r-multiple mean').intent, 'glossary');
  assert.ok(ask('VWAP').text.includes('volume-weighted'));
});
test('glossary uses your rules.json numbers', () => {
  const r2 = Object.assign({}, rules, { min_reward_risk: 3 });
  assert.ok(ask('what is reward vs risk', ctx({ rules: r2 })).text.includes('at least 3 to 1'));
});
test('rules questions beat the glossary', () => {
  const r = ask('what is the expiry rule');
  assert.strictEqual(r.intent, 'rules'); assert.ok(r.text.includes('expiry day'));
});
test('rules: full list and single topic', () => {
  const all = ask('what are my rules?').text;
  assert.ok(all.includes('\u20B9150') && all.includes('09:30') && all.includes('paper only'));
  const win = ask('what is the entry window').text;
  assert.ok(win.includes('09:30 to 11:30') && !win.includes('\u20B9900'));
});
test('rules follow rules.json changes', () => {
  const r2 = Object.assign({}, rules, { max_loss_per_trade: 100 });
  assert.ok(ask('what is my max loss', ctx({ rules: r2 })).text.includes('\u20B9100 per trade'));
});
test('blocked: last reason, and none', () => {
  const b = [{ date: '2026-11-16', minutes: 590, segment: 'index_option', reasons: ['index_option is paper only.'] }];
  const r = ask('why was I blocked?', ctx({ state: { morning, trades: [], blocked: b } }));
  assert.ok(r.text.includes('09:50') && r.text.includes('paper only') && r.text.includes('1.'));
  assert.ok(ask('why was i blocked').text.includes('Nothing has been blocked'));
});
test('stats by hand', () => {
  const trades = [t(540, 100), t(560, -50), t(580, 100, { paper: true })];
  const r = ask('how am I doing?', ctx({ state: { morning, trades, blocked: [] } }));
  assert.ok(r.text.includes('Real money: 2 trades, win rate 50%, expectancy \u20B925 a trade, total \u20B950') && r.text.includes('Paper: 1 trade,') && r.text.includes('Fewer than 20'));
});
test('time: minutes left', () => {
  const r = ask('how long until the window closes');
  assert.strictEqual(r.intent, 'time'); assert.ok(r.text.includes('10:00 IST') && r.text.includes('90 minutes') && r.text.includes('105 minutes'));
});
test('unknown and empty questions get help, not nonsense', () => {
  assert.strictEqual(ask('tell me a joke about bananas').intent, 'help');
  assert.strictEqual(ask('').intent, 'help');
  assert.ok(ask(null).text.includes('Can I trade now'));
});
test('works with an empty state', () => {
  const empty = ctx({ state: {} });
  ['can i trade now', 'p&l today', 'how am i doing', 'why was i blocked', 'how much can i risk'].forEach(q => ask(q, empty));
});

const sipOf = { id: 'a', name: 'Nifty index fund', amount: 1000, day: 1, start: '2025-01' };
const sipCtx = (over) => ctx({ sipData: Object.assign({ sips: [sipOf], snapshots: [] }, over || {}) });
test('sip: not set up yet', () => {
  assert.ok(ask('how is my sip doing').text.includes('No SIP is set up'));
});
test('sip: set up but no value yet asks for the value', () => {
  const r = ask('how is my SIP doing?', sipCtx());
  assert.strictEqual(r.intent, 'sip'); assert.ok(r.text.includes('Nifty index fund') && r.text.includes('Type today'));
});
test('sip: analysis with value', () => {
  const r = ask('what is my sip xirr', sipCtx({ snapshots: [{ sipId: 'a', date: '2025-12-31', value: 13000 }] }));
  assert.strictEqual(r.intent, 'sip');
  assert.ok(r.text.includes('Invested \u20B912,000 over 12 installments') && r.text.includes('gain \u20B91,000 (8.3%)') && r.text.includes('XIRR') && r.text.includes('ahead by'));
});
test('sip: the definition still comes from the glossary', () => {
  assert.strictEqual(ask('what is a sip').intent, 'glossary');
});
test('sip questions do not disturb trading answers', () => {
  assert.strictEqual(ask('can i trade now', sipCtx()).intent, 'can_trade');
});
test('sip: several SIPs give the whole picture first, then one line each', () => {
  const sips = [sipOf, { id: 'b', name: 'Flexi cap', amount: 500, day: 1, start: '2025-07' }];
  const snaps = [{ sipId: 'a', date: '2025-12-31', value: 13000 }, { sipId: 'b', date: '2025-12-31', value: 3100 }];
  const r = ask('how are all my sips doing', sipCtx({ sips, snapshots: snaps }));
  assert.strictEqual(r.intent, 'sip');
  const lines = r.text.split('\n');
  assert.ok(lines[0].startsWith('Right now your SIPs together are'));
  assert.ok(r.text.includes('All SIPs together (2 funds): invested \u20B915,000, value \u20B916,100') && r.text.includes('Combined XIRR'));
  assert.ok(r.text.includes('Nifty index fund: gain \u20B91,000') && r.text.includes('Flexi cap: gain \u20B9100'));
});
test('sip: several SIPs, one without a value, says so', () => {
  const sips = [sipOf, { id: 'b', name: 'Flexi cap', amount: 500, day: 1, start: '2025-07' }];
  const r = ask('how is my sip doing', sipCtx({ sips, snapshots: [{ sipId: 'a', date: '2025-12-31', value: 13000 }] }));
  assert.ok(r.text.includes('Not counted yet (no value entered): Flexi cap') && r.text.includes('Flexi cap: no value entered yet.'));
});
console.log(process.exitCode ? 'some tests failed' : 'all ' + n + ' ask tests pass');
