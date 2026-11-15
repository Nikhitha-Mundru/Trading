// Run with: node tests/test_gatekeeper.js
const fs = require('fs'), path = require('path');
const G = require('../gatekeeper.js');
const rules = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'rules.json'), 'utf8'));
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json'), 'utf8'));
let bad = 0;
for (const c of cases) {
  const res = G.evaluate(rules, c.state, c.trade, c.now);
  const failed = res.results.filter(r => !r.ok).map(r => r.id).sort();
  const ok = JSON.stringify(failed) === JSON.stringify(c.expectFailed) && res.pass === (c.expectFailed.length === 0);
  if (!ok) { bad++; console.log('FAIL', c.name, 'got', failed, 'want', c.expectFailed); }
}
console.log(bad ? bad + ' failed' : 'all ' + cases.length + ' cases pass');
process.exit(bad ? 1 : 0);
