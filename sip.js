// Mutual fund SIP analysis. Works only from numbers you type in: no prices fetched, no reminders, no AI.
// Separate from the trading rules on purpose: SIPs sit outside the daily limits.
// Works in the browser (window.Sip) and in Node (require).
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Sip = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function parts(s) { var a = s.split('-'); return { y: Number(a[0]), m: Number(a[1]), d: Number(a[2] || 1) }; }
  function monthKey(date) { return date.slice(0, 7); }
  function monthIndex(key) { var p = parts(key + '-01'); return p.y * 12 + p.m - 1; }
  function keyFromIndex(i) { return Math.floor(i / 12) + '-' + pad(i % 12 + 1); }
  function dayNumber(s) { var p = parts(s); return Math.round(Date.UTC(p.y, p.m - 1, p.d) / 86400000); }
  function dueDate(sip, key) { return key + '-' + pad(sip.day); }
  function shortDate(s) { var p = parts(s); return p.d + ' ' + MONTHS[p.m - 1]; }
  function monthLabel(key) { var p = parts(key + '-01'); return MONTHS[p.m - 1] + ' ' + p.y; }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function rs(n) { return (n < 0 ? '-' : '') + '\u20B9' + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 }); }
  function pct1(n) { return (Math.round(n * 10) / 10) + '%'; }

  // ---------- input parsing ----------
  function validate(sip) {
    if (!sip.name || !String(sip.name).trim()) return 'Give the SIP a name.';
    var hasFlows = sip.flows && sip.flows.length;
    if (!(typeof sip.amount === 'number' && isFinite(sip.amount) && sip.amount > 0)) return 'Amount must be more than zero.';
    if (!(Number.isInteger(sip.day) && sip.day >= 1 && sip.day <= 28)) return 'Pick a day from 1 to 28, so every month has it.';
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(sip.start || '')) return 'Pick the month you started.';
    if (!hasFlows && sip.stepUp !== undefined && !(typeof sip.stepUp === 'number' && sip.stepUp >= 0 && sip.stepUp <= 100)) return 'Step-up must be between 0 and 100 percent a year.';
    return '';
  }

  // "2025-03, 2025-04" -> { months: [...], bad: [...] }
  function parseSkipped(text) {
    var months = [], bad = [];
    String(text || '').split(/[\s,;]+/).filter(Boolean).forEach(function (t) { (/^\d{4}-(0[1-9]|1[0-2])$/.test(t) ? months : bad).push(t); });
    return { months: months, bad: bad };
  }

  // One transaction per line: "2025-01-05, 2000", "05-01-2025 2,000", "05/01/2025;2000". Negative = money taken out.
  function parseFlows(text) {
    var flows = [], bad = 0;
    String(text || '').split(/\r?\n/).forEach(function (line) {
      line = line.trim();
      if (!line) return;
      var m = line.match(/^(\d{4}-\d{2}-\d{2}|\d{2}[-\/]\d{2}[-\/]\d{4})[\s,;]+(?:\u20B9|rs\.?)?\s*(-?[\d,]+(?:\.\d+)?)\s*$/i);
      if (!m) { bad++; return; }
      var d = m[1], date = /^\d{4}/.test(d) ? d : d.slice(6, 10) + '-' + d.slice(3, 5) + '-' + d.slice(0, 2);
      var amount = Number(m[2].replace(/,/g, ''));
      if (!isFinite(amount) || amount === 0 || isNaN(Date.parse(date))) { bad++; return; }
      flows.push({ date: date, amount: amount });
    });
    flows.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    return { flows: flows, bad: bad };
  }

  // ---------- cash flows ----------
  // Pasted transactions win. Otherwise: one installment on `day` of every month from `start`,
  // minus skipped months, with the amount stepping up every 12 installments.
  function schedule(sip, asOf) {
    if (sip.flows && sip.flows.length) return sip.flows.filter(function (f) { return f.date <= asOf; });
    var skipped = {}, out = [], step = (sip.stepUp || 0) / 100;
    (sip.skipped || []).forEach(function (m) { skipped[m] = true; });
    var s = monthIndex(sip.start), e = monthIndex(monthKey(asOf));
    for (var i = s; i <= e; i++) {
      var key = keyFromIndex(i), date = dueDate(sip, key);
      if (date > asOf) break;
      if (skipped[key]) continue;
      out.push({ date: date, amount: Math.round(sip.amount * Math.pow(1 + step, Math.floor((i - s) / 12)) * 100) / 100 });
    }
    return out;
  }
  function sum(flows) { return flows.reduce(function (a, f) { return a + f.amount; }, 0); }
  function monthlyNow(sip, asOf) { var f = schedule(sip, asOf); return f.length ? f[f.length - 1].amount : sip.amount; }

  // ---------- maths ----------
  // XIRR: the yearly rate that makes all your payments plus today's value net to zero, using actual dates.
  function solveXirr(pts) {
    var times = pts.map(function (p) { return p.t; }), t0 = Math.min.apply(null, times), tEnd = Math.max.apply(null, times);
    if (tEnd <= t0) return null;
    function npv(r) { return pts.reduce(function (s, p) { return s + p.a / Math.pow(1 + r, (p.t - t0) / 365); }, 0); }
    var lo = -0.9999, hi = 10, flo = npv(lo), fhi = npv(hi);
    if (!isFinite(flo) || !isFinite(fhi) || flo * fhi > 0) return null;
    for (var i = 0; i < 200; i++) {
      var mid = (lo + hi) / 2, fm = npv(mid);
      if ((fm > 0) === (flo > 0)) { lo = mid; flo = fm; } else hi = mid;
    }
    return (lo + hi) / 2;
  }
  function xirr(flows, value, asOf) {
    if (!flows.length) return null;
    var invested = sum(flows);
    if (value <= 0) return invested > 0 ? -1 : null;
    var pts = flows.map(function (f) { return { t: dayNumber(f.date), a: -f.amount }; });
    pts.push({ t: dayNumber(asOf), a: value });
    return solveXirr(pts);
  }

  // What the same payments, on the same dates, would be worth at a fixed yearly rate.
  function benchmark(flows, asOf, rate) {
    var t1 = dayNumber(asOf);
    return flows.reduce(function (s, f) { return s + f.amount * Math.pow(1 + rate, (t1 - dayNumber(f.date)) / 365); }, 0);
  }

  // Extra value if a cheaper plan added `diff` (e.g. 0.008) to your yearly return on the same payments.
  function costDrag(flows, asOf, rate, diff) { return benchmark(flows, asOf, rate + diff) - benchmark(flows, asOf, rate); }

  // Months with no payment between your first and last payment. A gap check, not a nag.
  function consistency(flows) {
    if (!flows.length) return { months: 0, paid: 0, missed: [], longestGap: 0 };
    var have = {};
    flows.forEach(function (f) { if (f.amount > 0) have[monthKey(f.date)] = true; });
    var keys = Object.keys(have).sort();
    if (!keys.length) return { months: 0, paid: 0, missed: [], longestGap: 0 };
    var s = monthIndex(keys[0]), e = monthIndex(keys[keys.length - 1]), missed = [], run = 0, longest = 0;
    for (var i = s; i <= e; i++) {
      var k = keyFromIndex(i);
      if (have[k]) run = 0; else { missed.push(k); run++; if (run > longest) longest = run; }
    }
    return { months: e - s + 1, paid: keys.length, missed: missed, longestGap: longest };
  }

  // Monthly compounding; each installment goes in at the start of its month. An assumption, not a forecast.
  function project(value, monthly, years, rate, stepUp) {
    var mr = Math.pow(1 + rate, 1 / 12) - 1, v = value, added = 0, amt = monthly;
    for (var m = 0; m < years * 12; m++) {
      if (m > 0 && m % 12 === 0) amt = amt * (1 + stepUp);
      v = (v + amt) * (1 + mr); added += amt;
    }
    return { value: v, added: added };
  }

  // ---------- analysis ----------
  function latestSnapshot(sipId, snapshots) {
    var best = null;
    (snapshots || []).forEach(function (s) { if (s.sipId === sipId && (!best || s.date >= best.date)) best = s; });
    return best;
  }

  function analyze(sip, snapshots, opts) {
    opts = opts || {};
    var snap = latestSnapshot(sip.id, snapshots);
    if (!snap) return { value: null };
    var asOf = snap.date, flows = schedule(sip, asOf), invested = sum(flows);
    var years = flows.length ? (dayNumber(asOf) - dayNumber(flows[0].date)) / 365 : 0;
    var x = xirr(flows, snap.value, asOf), rate = opts.benchmarkRate === undefined ? 0.07 : opts.benchmarkRate;
    var bench = benchmark(flows, asOf, rate);
    return { value: snap.value, asOf: asOf, flows: flows, installments: flows.length, invested: invested,
             gain: snap.value - invested, pct: invested > 0 ? (snap.value - invested) / invested * 100 : null,
             xirr: x, years: years, benchRate: rate, benchValue: bench, aheadBy: snap.value - bench,
             directDiff: opts.directDiff || null,
             drag: opts.directDiff && x !== null ? costDrag(flows, asOf, x, opts.directDiff) : null,
             consistency: consistency(flows) };
  }

  function projections(sip, a, opts) {
    opts = opts || {};
    var monthly = monthlyNow(sip, a.asOf), years = opts.years || 10, step = opts.stepUp || 0;
    return (opts.rates || [0.08, 0.10, 0.12]).map(function (r) {
      var p = project(a.value, monthly, years, r, step);
      return { rate: r, years: years, value: p.value, added: p.added, totalInvested: a.invested + p.added };
    });
  }

  // Plain-language lines, used by both the SIP tab and the Ask tab.
  function lines(a) {
    if (a.value === null) return ['No value entered yet. Type today\'s value from your fund app to see the analysis.'];
    var out = [];
    out.push('Invested ' + rs(a.invested) + ' over ' + plural(a.installments, 'installment') + '.');
    out.push('Value ' + rs(a.value) + ' on ' + shortDate(a.asOf) + ': gain ' + rs(a.gain) + (a.pct === null ? '' : ' (' + pct1(a.pct) + ')') + '.');
    out.push(a.xirr === null ? 'XIRR could not be worked out from these numbers.'
      : 'XIRR, your yearly return counting when each payment went in: ' + pct1(a.xirr * 100) + ' a year.' + (a.years < 1 ? ' Under a year of data, so treat it as rough.' : ''));
    out.push('The same payments at ' + pct1(a.benchRate * 100) + ' a year would be worth ' + rs(a.benchValue) + '. You are ' + (a.aheadBy >= 0 ? 'ahead by ' : 'behind by ') + rs(Math.abs(a.aheadBy)) + '.');
    if (a.drag !== null) out.push('If a direct plan saved ' + pct1(a.directDiff * 100) + ' a year, you would have about ' + rs(a.drag) + ' more.');
    var c = a.consistency;
    if (c.months) out.push('Paid in ' + c.paid + ' of ' + plural(c.months, 'month') + (c.missed.length ? '. No payment in: ' + c.missed.slice(0, 6).map(monthLabel).join(', ') + (c.missed.length > 6 ? ' and more' : '') : ', no gaps') + '.');
    return out;
  }

  // Reads the file the PC tool makes. Checks every field and says what it skipped, so a bad file cannot sneak in.
  function importData(text, newId) {
    var out = { sips: [], snapshots: [], warnings: [], errors: [] }, data;
    try { data = JSON.parse(text); } catch (e) { out.errors.push('That is not valid JSON. Paste the whole file the PC tool made, or choose the file.'); return out; }
    if (!data || data.version !== 1 || !Array.isArray(data.sips)) { out.errors.push('This is not a SIP import file (expected version 1 from the PC tool).'); return out; }
    (data.warnings || []).forEach(function (w) { out.warnings.push(String(w)); });
    var isDate = function (d) { return typeof d === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(d) && !isNaN(Date.parse(d)); };
    data.sips.forEach(function (raw, i) {
      raw = raw || {};
      var label = raw.name ? String(raw.name) : 'SIP ' + (i + 1), flows = [], bad = 0;
      (Array.isArray(raw.flows) ? raw.flows : []).forEach(function (f) {
        if (f && isDate(f.date) && typeof f.amount === 'number' && isFinite(f.amount) && f.amount !== 0) flows.push({ date: f.date, amount: f.amount }); else bad++;
      });
      flows.sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
      var sip = { id: newId(), name: String(raw.name || '').trim(), amount: Number(raw.amount), day: Number(raw.day),
                  start: flows.length ? flows[0].date.slice(0, 7) : raw.start, stepUp: Number(raw.stepUp || 0),
                  skipped: Array.isArray(raw.skipped) ? raw.skipped.filter(function (m) { return /^\d{4}-(0[1-9]|1[0-2])$/.test(m); }) : [] };
      if (flows.length) sip.flows = flows;
      var err = validate(sip);
      if (err) { out.errors.push(label + ': ' + err); return; }
      if (bad) out.warnings.push(label + ': ' + bad + ' transaction ' + (bad === 1 ? 'line was' : 'lines were') + ' invalid and skipped.');
      out.sips.push(sip);
      var v = raw.value;
      if (v && isDate(v.date) && typeof v.value === 'number' && isFinite(v.value) && v.value >= 0) out.snapshots.push({ sipId: sip.id, date: v.date, value: v.value });
      else out.warnings.push(label + ': no current value in the file. Type it in on its card.');
    });
    if (!out.sips.length && !out.errors.length) out.errors.push('The file has no SIPs in it.');
    return out;
  }

  // Running total of money put in, month by month, across all the flows given.
  function cumulativeByMonth(flows, asOf) {
    if (!flows.length) return [];
    var sorted = flows.slice().sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
    var s = monthIndex(monthKey(sorted[0].date)), e = monthIndex(monthKey(asOf)), out = [], total = 0, k = 0;
    for (var i = s; i <= e; i++) {
      var key = keyFromIndex(i), added = 0;
      while (k < sorted.length && monthKey(sorted[k].date) === key) { added += sorted[k].amount; k++; }
      total += added; out.push({ month: key, added: added, invested: total });
    }
    return out;
  }

  // All SIPs together. Only SIPs with a saved value are counted, so invested and value compare like for like.
  function portfolio(sips, snapshots, opts) {
    opts = opts || {};
    var items = [], missing = [];
    sips.forEach(function (s) { var a = analyze(s, snapshots, opts); if (a.value === null) missing.push(s.name); else items.push({ sip: s, a: a }); });
    if (!items.length) return { count: 0, value: null, missing: missing };
    var invested = 0, value = 0, bench = 0, pts = [], allFlows = [], asOfs = [];
    items.forEach(function (it) {
      invested += it.a.invested; value += it.a.value; bench += it.a.benchValue; asOfs.push(it.a.asOf);
      it.a.flows.forEach(function (f) { pts.push({ t: dayNumber(f.date), a: -f.amount }); allFlows.push(f); });
      pts.push({ t: dayNumber(it.a.asOf), a: it.a.value });
    });
    asOfs.sort();
    var latest = asOfs[asOfs.length - 1], earliest = asOfs[0];
    var firstDate = allFlows.length ? allFlows.map(function (f) { return f.date; }).sort()[0] : null;
    var x = !allFlows.length ? null : value <= 0 ? (invested > 0 ? -1 : null) : solveXirr(pts);
    var rows = items.map(function (it) {
      return { name: it.sip.name, invested: it.a.invested, value: it.a.value, gain: it.a.gain, pct: it.a.pct, xirr: it.a.xirr,
               share: value > 0 ? it.a.value / value * 100 : null };
    });
    var ranked = rows.filter(function (r) { return r.xirr !== null; }).sort(function (a, b) { return b.xirr - a.xirr; });
    return { count: items.length, value: value, invested: invested, gain: value - invested,
             pct: invested > 0 ? (value - invested) / invested * 100 : null, xirr: x,
             years: firstDate ? (dayNumber(latest) - dayNumber(firstDate)) / 365 : 0,
             asOf: latest, staleDays: dayNumber(latest) - dayNumber(earliest),
             benchRate: items[0].a.benchRate, benchValue: bench, aheadBy: value - bench,
             rows: rows, best: ranked.length > 1 ? ranked[0] : null, worst: ranked.length > 1 ? ranked[ranked.length - 1] : null,
             largest: rows.length > 1 ? rows.slice().sort(function (a, b) { return b.value - a.value; })[0] : null,
             missing: missing, cumulative: cumulativeByMonth(allFlows, latest) };
  }

  // Compact rupees for chart labels: 12.5L, 1.25Cr.
  function short(n) {
    var a = Math.abs(n), sign = n < 0 ? '-' : '';
    function t(x) { return String(Math.round(x * 100) / 100); }
    if (a >= 1e7) return sign + '\u20B9' + t(a / 1e7) + 'Cr';
    if (a >= 1e5) return sign + '\u20B9' + t(a / 1e5) + 'L';
    return rs(n);
  }

  function brief(name, a) {
    if (a.value === null) return name + ': no value entered yet.';
    return name + ': gain ' + rs(a.gain) + (a.pct === null ? '' : ' (' + pct1(a.pct) + ')') + (a.xirr === null ? '' : ', XIRR ' + pct1(a.xirr * 100)) + '.';
  }

  function portfolioLines(p) {
    if (p.value === null) return [p.missing.length ? 'Type today\'s value on a SIP card to see all your SIPs together.' : 'No SIP added yet.'];
    var out = [];
    out.push('Right now your SIPs together are ' + (p.aheadBy >= 0 ? 'ahead of' : 'behind') + ' a ' + pct1(p.benchRate * 100) + ' a year benchmark by ' + rs(Math.abs(p.aheadBy)) + '.');
    out.push('All SIPs together (' + plural(p.count, 'fund') + '): invested ' + rs(p.invested) + ', value ' + rs(p.value) + ', gain ' + rs(p.gain) + (p.pct === null ? '' : ' (' + pct1(p.pct) + ')') + '.');
    out.push(p.xirr === null ? 'Combined XIRR could not be worked out.'
      : 'Combined XIRR: ' + pct1(p.xirr * 100) + ' a year.' + (p.years < 1 ? ' Under a year of data, so treat it as rough.' : ''));
    if (p.best) out.push('Strongest: ' + p.best.name + ' (XIRR ' + pct1(p.best.xirr * 100) + '). Weakest: ' + p.worst.name + ' (XIRR ' + pct1(p.worst.xirr * 100) + ').');
    if (p.largest) out.push('Largest holding: ' + p.largest.name + ', ' + pct1(p.largest.share) + ' of the total value.');
    if (p.missing.length) out.push('Not counted yet (no value entered): ' + p.missing.join(', ') + '.');
    if (p.staleDays > 31) out.push('Your saved values are up to ' + plural(p.staleDays, 'day') + ' apart. Save fresh values for a cleaner picture.');
    return out;
  }

  // One row per saved value, with XIRR as it stood on that date.
  function growthLog(sip, snapshots) {
    return (snapshots || []).filter(function (s) { return s.sipId === sip.id; })
      .sort(function (a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; })
      .map(function (s) {
        var flows = schedule(sip, s.date), invested = sum(flows);
        return { date: s.date, invested: invested, value: s.value, gain: s.value - invested,
                 pct: invested > 0 ? (s.value - invested) / invested * 100 : null, xirr: xirr(flows, s.value, s.date) };
      });
  }

  return { validate: validate, parseFlows: parseFlows, parseSkipped: parseSkipped, schedule: schedule, monthlyNow: monthlyNow,
           xirr: xirr, benchmark: benchmark, costDrag: costDrag, consistency: consistency, project: project,
           analyze: analyze, projections: projections, lines: lines, growthLog: growthLog,
           importData: importData, portfolio: portfolio, portfolioLines: portfolioLines, cumulativeByMonth: cumulativeByMonth, short: short, brief: brief,
           monthKey: monthKey, monthLabel: monthLabel, shortDate: shortDate, rs: rs, pct1: pct1 };
});
