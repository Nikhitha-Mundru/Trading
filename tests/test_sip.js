// Run with: node tests/test_sip.js
const assert = require('assert');
const Sip = require('../sip.js');
let n = 0;
function test(name, fn) { try { fn(); n++; } catch (e) { console.log('FAIL', name, '\n  ', e.message); process.exitCode = 1; } }
const near = (a, b, tol) => assert.ok(Math.abs(a - b) <= (tol || 1e-6), a + ' is not near ' + b);
const sip = (over) => Object.assign({ id: 'a', name: 'Index fund', amount: 1000, day: 5, start: '2026-01' }, over);

// ---- cash flows ----
test('schedule: one installment a month, only dates already passed', () => {
  assert.deepStrictEqual(Sip.schedule(sip(), '2026-03-10').map(f => f.date), ['2026-01-05', '2026-02-05', '2026-03-05']);
  assert.deepStrictEqual(Sip.schedule(sip(), '2026-03-04').map(f => f.date), ['2026-01-05', '2026-02-05']);
  assert.strictEqual(Sip.schedule(sip({ start: '2026-12' }), '2026-11-16').length, 0);
});
test('schedule: step-up after every 12 installments', () => {
  const f = Sip.schedule(sip({ start: '2025-01', stepUp: 10 }), '2026-02-10');
  assert.strictEqual(f.length, 14);
  assert.deepStrictEqual([f[0].amount, f[11].amount, f[12].amount, f[13].amount], [1000, 1000, 1100, 1100]);
  near(f.reduce((a, x) => a + x.amount, 0), 14200);
});
test('schedule: skipped months are left out', () => {
  assert.deepStrictEqual(Sip.schedule(sip({ skipped: ['2026-02'] }), '2026-03-10').map(f => f.date), ['2026-01-05', '2026-03-05']);
});
test('schedule: pasted transactions win and stop at the as-of date', () => {
  const flows = [{ date: '2025-01-05', amount: 500 }, { date: '2025-02-05', amount: 700 }, { date: '2025-03-05', amount: 900 }];
  assert.deepStrictEqual(Sip.schedule(sip({ flows }), '2025-02-20').map(f => f.amount), [500, 700]);
});

// ---- XIRR by hand ----
test('xirr: one payment, one year, 10%', () => near(Sip.xirr([{ date: '2025-01-01', amount: 1000 }], 1100, '2026-01-01'), 0.10));
test('xirr: two payments solved exactly (x*x + x = 2.31 gives 10%)', () => {
  near(Sip.xirr([{ date: '2025-01-01', amount: 1000 }, { date: '2026-01-01', amount: 1000 }], 2310, '2027-01-01'), 0.10);
});
test('xirr: a loss is negative', () => near(Sip.xirr([{ date: '2025-01-01', amount: 1000 }], 900, '2026-01-01'), -0.10));
test('xirr: total loss and unusable inputs', () => {
  assert.strictEqual(Sip.xirr([{ date: '2025-01-01', amount: 1000 }], 0, '2026-01-01'), -1);
  assert.strictEqual(Sip.xirr([], 100, '2026-01-01'), null);
  assert.strictEqual(Sip.xirr([{ date: '2026-01-01', amount: 1000 }], 1100, '2026-01-01'), null); // no time has passed
});
test('xirr: a withdrawal (negative amount) is handled', () => {
  const flows = [{ date: '2025-01-01', amount: 1000 }, { date: '2026-01-01', amount: -550 }];
  // 1000 in, 550 out after a year, 550 left after two: 1000x^2 - 550x - 550 = 0 with x = 1 + rate
  near(Sip.xirr(flows, 550, '2027-01-01'), (550 + Math.sqrt(550 * 550 + 4 * 1000 * 550)) / 2000 - 1, 1e-9);
});

// ---- benchmark, cost, consistency, projection ----
test('benchmark: same payments at a fixed rate', () => {
  near(Sip.benchmark([{ date: '2025-01-01', amount: 1000 }], '2026-01-01', 0.07), 1070);
  near(Sip.benchmark([{ date: '2025-01-01', amount: 1000 }, { date: '2026-01-01', amount: 1000 }], '2026-01-01', 0.07), 2070);
});
test('cost drag: 1% a year on 1000 for a year at 10%', () => near(Sip.costDrag([{ date: '2025-01-01', amount: 1000 }], '2026-01-01', 0.10, 0.01), 10));
test('consistency: gaps between first and last payment only', () => {
  const c = Sip.consistency([{ date: '2026-01-05', amount: 1 }, { date: '2026-02-05', amount: 1 }, { date: '2026-05-05', amount: 1 }]);
  assert.deepStrictEqual([c.months, c.paid, c.missed, c.longestGap], [5, 3, ['2026-03', '2026-04'], 2]);
  assert.deepStrictEqual(Sip.consistency([]).missed, []);
});
test('project: no growth just adds the installments, step-up raises them yearly', () => {
  near(Sip.project(0, 1000, 1, 0, 0).value, 12000);
  near(Sip.project(0, 1000, 2, 0, 0.10).added, 25200);
});
test('project: 12% for a year by the annuity formula', () => {
  const mr = Math.pow(1.12, 1 / 12) - 1;
  near(Sip.project(0, 1000, 1, 0.12, 0).value, 1000 * (1 + mr) * (Math.pow(1 + mr, 12) - 1) / mr, 1e-6);
  near(Sip.project(5000, 0, 1, 0.12, 0).value, 5600, 1e-6); // a lump sum just grows at the yearly rate
});

// ---- analyze and wording ----
test('analyze by hand: 13 installments, a small loss', () => {
  const s = sip({ day: 1, start: '2025-01' });
  const a = Sip.analyze(s, [{ sipId: 'a', date: '2026-01-01', value: 12600 }]);
  assert.strictEqual(a.installments, 13); near(a.invested, 13000); near(a.gain, -400); near(a.pct, -400 / 13000 * 100);
  assert.ok(a.xirr < 0 && a.aheadBy < 0);
});
test('analyze: latest value wins; none means no analysis', () => {
  const s = sip({ day: 1, start: '2025-01' });
  const a = Sip.analyze(s, [{ sipId: 'a', date: '2025-06-01', value: 1 }, { sipId: 'a', date: '2025-12-31', value: 13000 }]);
  assert.strictEqual(a.value, 13000); assert.strictEqual(a.installments, 12);
  assert.strictEqual(Sip.analyze(s, []).value, null);
  assert.strictEqual(Sip.analyze(s, [{ sipId: 'other', date: '2025-12-31', value: 5 }]).value, null);
});
test('analyze: benchmark and direct-plan options flow through', () => {
  const s = sip({ day: 1, start: '2025-01' }), snaps = [{ sipId: 'a', date: '2025-12-31', value: 13000 }];
  const a = Sip.analyze(s, snaps, { benchmarkRate: 0.0, directDiff: 0.01 });
  near(a.benchValue, 12000); near(a.aheadBy, 1000); assert.ok(a.drag > 0);
  assert.strictEqual(Sip.analyze(s, snaps).drag, null);
});
test('lines: plain wording, rough warning under a year, no-value message', () => {
  const s = sip({ day: 1, start: '2025-01' });
  const l = Sip.lines(Sip.analyze(s, [{ sipId: 'a', date: '2025-12-31', value: 13000 }]));
  assert.ok(l[0] === 'Invested \u20B912,000 over 12 installments.');
  assert.ok(l[1].startsWith('Value \u20B913,000 on 31 Dec: gain \u20B91,000 (8.3%).'));
  assert.ok(l[2].includes('XIRR') && l[2].includes('Under a year'));
  assert.ok(l[3].includes('at 7% a year') && l[3].includes('ahead by'));
  assert.ok(l[l.length - 1].includes('Paid in 12 of 12 months, no gaps'));
  assert.ok(Sip.lines({ value: null })[0].includes('No value entered'));
});
test('projections: three assumed rates, longer is bigger', () => {
  const s = sip({ day: 1, start: '2025-01' }), a = Sip.analyze(s, [{ sipId: 'a', date: '2025-12-31', value: 13000 }]);
  const p = Sip.projections(s, a, { years: 10 });
  assert.deepStrictEqual(p.map(x => x.rate), [0.08, 0.10, 0.12]);
  assert.ok(p[0].value < p[1].value && p[1].value < p[2].value);
  near(p[0].added, 120000); near(p[0].totalInvested, 132000);
});
test('growth log: one row per saved value with xirr at that date', () => {
  const s = sip({ day: 1, start: '2025-01' });
  const log = Sip.growthLog(s, [{ sipId: 'a', date: '2025-12-31', value: 13000 }, { sipId: 'a', date: '2025-06-30', value: 6100 }]);
  assert.deepStrictEqual(log.map(r => [r.date, r.invested, r.value]), [['2025-06-30', 6000, 6100], ['2025-12-31', 12000, 13000]]);
  assert.ok(log[0].xirr !== null && log[1].xirr !== null);
});

// ---- parsing and validation ----
test('parseFlows: formats, thousands separators, bad lines', () => {
  const r = Sip.parseFlows('Date,Amount\n2025-01-05, 2000\n05-02-2025 2,000\n05/03/2025;\u20B92500.50\n2025-04-05,-300\nnonsense\n\n');
  assert.deepStrictEqual(r.flows.map(f => [f.date, f.amount]), [['2025-01-05', 2000], ['2025-02-05', 2000], ['2025-03-05', 2500.5], ['2025-04-05', -300]]);
  assert.strictEqual(r.bad, 2); // the header and "nonsense"
  assert.strictEqual(Sip.parseFlows('').flows.length, 0);
});
test('parseFlows sorts by date', () => assert.deepStrictEqual(Sip.parseFlows('2025-03-05,1\n2025-01-05,2').flows.map(f => f.date), ['2025-01-05', '2025-03-05']));
test('parseSkipped', () => assert.deepStrictEqual(Sip.parseSkipped('2025-03, 2025-04; oops 2025-13'), { months: ['2025-03', '2025-04'], bad: ['oops', '2025-13'] }));
test('validate', () => {
  assert.strictEqual(Sip.validate(sip()), '');
  assert.strictEqual(Sip.validate(sip({ start: '2019-04', stepUp: 10 })), ''); // an existing SIP started years ago is fine
  ['name', 'amount', 'day', 'start'].forEach(k => assert.ok(Sip.validate(sip({ [k]: k === 'amount' || k === 'day' ? 0 : '' }))));
  assert.ok(Sip.validate(sip({ day: 29 }))); assert.ok(Sip.validate(sip({ stepUp: -1 }))); assert.ok(Sip.validate(sip({ stepUp: 101 })));
});
test('money formatting uses Indian grouping and signs', () => {
  assert.strictEqual(Sip.rs(1234567), '\u20B912,34,567'); assert.strictEqual(Sip.rs(-400), '-\u20B9400');
});

// ---- all SIPs together ----
const A = sip({ id: 'A', name: 'Fund A', day: 1, start: '2025-01' });           // 12 x 1000 by 2025-12-31
const B = sip({ id: 'B', name: 'Fund B', day: 1, start: '2025-07', amount: 500 }); // 6 x 500
const snapA = { sipId: 'A', date: '2025-12-31', value: 13000 }, snapB = { sipId: 'B', date: '2025-12-31', value: 3100 };
test('portfolio: totals add up by hand', () => {
  const p = Sip.portfolio([A, B], [snapA, snapB]);
  assert.deepStrictEqual([p.count, p.invested, p.value, p.gain], [2, 15000, 16100, 1100]);
  near(p.pct, 1100 / 15000 * 100);
});
test('portfolio: combined XIRR equals XIRR of the merged payments', () => {
  const p = Sip.portfolio([A, B], [snapA, snapB]);
  const merged = Sip.schedule(A, '2025-12-31').concat(Sip.schedule(B, '2025-12-31'));
  near(p.xirr, Sip.xirr(merged, 16100, '2025-12-31'), 1e-9);
});
test('portfolio: one SIP matches its own analysis', () => {
  const p = Sip.portfolio([A], [snapA]), a = Sip.analyze(A, [snapA]);
  near(p.xirr, a.xirr, 1e-9); near(p.value, a.value); assert.strictEqual(p.best, null);
});
test('portfolio: a SIP with no value is listed, not counted', () => {
  const p = Sip.portfolio([A, B], [snapA]);
  assert.deepStrictEqual([p.count, p.invested, p.missing], [1, 12000, ['Fund B']]);
  assert.ok(Sip.portfolioLines(p).some(l => l.includes('Not counted yet') && l.includes('Fund B')));
  assert.strictEqual(Sip.portfolio([A], []).value, null);
  assert.ok(Sip.portfolioLines(Sip.portfolio([A], []))[0].includes('Type today'));
  assert.ok(Sip.portfolioLines(Sip.portfolio([], []))[0].includes('No SIP added yet'));
});
test('portfolio: benchmark is the sum of each fund against the same rate', () => {
  const p = Sip.portfolio([A, B], [snapA, snapB], { benchmarkRate: 0 });
  near(p.benchValue, 15000); near(p.aheadBy, 1100);
  const q = Sip.portfolio([A, B], [snapA, snapB]);
  near(q.benchValue, Sip.analyze(A, [snapA]).benchValue + Sip.analyze(B, [snapB]).benchValue);
});
test('portfolio: strongest, weakest, largest, stale values', () => {
  const p = Sip.portfolio([A, B], [snapA, { sipId: 'B', date: '2025-11-15', value: 2400 }]);
  assert.strictEqual(p.best.name, 'Fund A'); assert.strictEqual(p.worst.name, 'Fund B'); assert.strictEqual(p.largest.name, 'Fund A');
  assert.strictEqual(p.staleDays, 46);
  const l = Sip.portfolioLines(p);
  assert.ok(l.some(x => x.startsWith('Strongest: Fund A')) && l.some(x => x.includes('46 days apart')) && l.some(x => x.startsWith('Largest holding: Fund A')));
});
test('portfolio lines: verdict first, then totals and XIRR', () => {
  const l = Sip.portfolioLines(Sip.portfolio([A, B], [snapA, snapB]));
  assert.ok(l[0].startsWith('Right now your SIPs together are') && l[0].includes('7% a year benchmark'));
  assert.ok(l[1].startsWith('All SIPs together (2 funds): invested \u20B915,000, value \u20B916,100, gain \u20B91,100 (7.3%)'));
  assert.ok(l[2].startsWith('Combined XIRR') && l[2].includes('Under a year'));
});
test('cumulative by month fills quiet months and keeps a running total', () => {
  const c = Sip.cumulativeByMonth([{ date: '2026-01-05', amount: 1000 }, { date: '2026-02-05', amount: 1000 }, { date: '2026-04-05', amount: 500 }], '2026-04-30');
  assert.deepStrictEqual(c.map(r => [r.month, r.added, r.invested]), [['2026-01', 1000, 1000], ['2026-02', 1000, 2000], ['2026-03', 0, 2000], ['2026-04', 500, 2500]]);
  assert.deepStrictEqual(Sip.cumulativeByMonth([], '2026-01-01'), []);
  const p = Sip.portfolio([A, B], [snapA, snapB]);
  assert.strictEqual(p.cumulative[p.cumulative.length - 1].invested, 15000); assert.strictEqual(p.cumulative[0].month, '2025-01');
});
test('short money labels and brief lines', () => {
  assert.strictEqual(Sip.short(28000), '\u20B928,000'); assert.strictEqual(Sip.short(250000), '\u20B92.5L'); assert.strictEqual(Sip.short(12500000), '\u20B91.25Cr');
  assert.ok(Sip.brief('Fund A', Sip.analyze(A, [snapA])).startsWith('Fund A: gain \u20B91,000 (8.3%), XIRR'));
  assert.strictEqual(Sip.brief('Fund A', { value: null }), 'Fund A: no value entered yet.');
});

// ---- importing the PC tool's file ----
const fs = require('fs'), path = require('path');
const mkId = () => { let k = 0; return () => 'imp' + (++k); };
const sample = fs.readFileSync(path.join(__dirname, 'sip_import_sample.json'), 'utf8');
test('import: the file the PC tool really makes loads cleanly', () => {
  const r = Sip.importData(sample, mkId());
  assert.deepStrictEqual(r.errors, []);
  assert.deepStrictEqual(r.sips.map(s => s.name), ['Nifty 50 Index Fund - Direct Plan - Growth', 'Example Small Cap Fund - Direct Plan - Growth']);
  const a = r.sips[0];
  assert.deepStrictEqual([a.amount, a.day, a.start, a.flows.length], [2000, 5, '2025-01', 3]);
  assert.deepStrictEqual(r.snapshots, [{ sipId: a.id, date: '2026-11-14', value: 13529 }]); // the second fund had no value
  assert.ok(r.warnings.some(w => w.includes('no current value in the file')));
  assert.ok(r.warnings.some(w => w.includes('left out 1 switch line')));
});
test('import: imported SIPs go straight into the analysis', () => {
  const r = Sip.importData(sample, mkId());
  const a = Sip.analyze(r.sips[0], r.snapshots);
  near(a.invested, 6500); near(a.value, 13529); assert.ok(a.xirr > 0 && a.installments === 3);
  assert.deepStrictEqual(Sip.portfolio(r.sips, r.snapshots).missing, ['Example Small Cap Fund - Direct Plan - Growth']);
});
test('import: not JSON, wrong shape, empty', () => {
  assert.ok(Sip.importData('hello', mkId()).errors[0].includes('not valid JSON'));
  assert.ok(Sip.importData('{"version":2,"sips":[]}', mkId()).errors[0].includes('not a SIP import file'));
  assert.ok(Sip.importData('[]', mkId()).errors[0].includes('not a SIP import file'));
  assert.ok(Sip.importData('{"version":1,"sips":[]}', mkId()).errors[0].includes('no SIPs'));
});
test('import: a bad SIP is reported and the good one still loads', () => {
  const file = { version: 1, sips: [{ name: '', amount: 1000, day: 5, start: '2025-01' }, { name: 'Good', amount: 1000, day: 5, start: '2025-01', value: { date: '2025-12-31', value: 5 } }] };
  const r = Sip.importData(JSON.stringify(file), mkId());
  assert.strictEqual(r.sips.length, 1); assert.ok(r.errors[0].startsWith('SIP 1:'));
});
test('import: bad transaction lines and bad values are skipped with a warning, start follows the first transaction', () => {
  const file = { version: 1, sips: [{ name: 'F', amount: 1000, day: 5, start: '2020-01', flows: [{ date: '2025-03-05', amount: 1000 }, { date: 'nope', amount: 5 }, { date: '2025-01-05', amount: 'x' }, { date: '2025-01-05', amount: 1000 }], value: { date: '2025-13-40', value: 3 } }] };
  const r = Sip.importData(JSON.stringify(file), mkId());
  assert.deepStrictEqual(r.sips[0].flows.map(f => f.date), ['2025-01-05', '2025-03-05']); assert.strictEqual(r.sips[0].start, '2025-01');
  assert.ok(r.warnings.some(w => w.includes('2 transaction lines were invalid')) && r.warnings.some(w => w.includes('no current value')));
  assert.strictEqual(r.snapshots.length, 0);
});
test('import: ids are unique per SIP and snapshots point at them', () => {
  const r = Sip.importData(sample, mkId());
  assert.notStrictEqual(r.sips[0].id, r.sips[1].id); assert.strictEqual(r.snapshots[0].sipId, r.sips[0].id);
});
console.log(process.exitCode ? 'some tests failed' : 'all ' + n + ' sip tests pass');
