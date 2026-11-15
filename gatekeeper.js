// Gatekeeper rules engine (JavaScript). Mirrors gatekeeper.py exactly.
// Works in the browser (window.Gatekeeper) and in Node (require).
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Gatekeeper = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  function toMin(hhmm) {
    var p = hhmm.split(':');
    return Number(p[0]) * 60 + Number(p[1]);
  }
  function clock(minutes) {
    var h = Math.floor(minutes / 60), m = minutes % 60;
    return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
  }
  function rupees(n) {
    return '\u20B9' + (Math.round(n * 100) / 100);
  }

  // Real-money trades only; paper trades never count toward the limits.
  function summarize(trades, now) {
    var real = trades.filter(function (t) { return !t.paper; });
    var today = real.filter(function (t) { return t.date === now.date; });
    var week = real.filter(function (t) { return t.date >= now.weekStart && t.date <= now.date; });
    var sum = function (list) { return list.reduce(function (a, t) { return a + (t.pnl || 0); }, 0); };
    var streak = 0;
    for (var i = today.length - 1; i >= 0; i--) {
      if ((today[i].pnl || 0) < 0) streak++; else break;
    }
    var lastLoss = null;
    today.forEach(function (t) { if ((t.pnl || 0) < 0) lastLoss = t.minutes; });
    return { netToday: sum(today), netWeek: sum(week), count: today.length, streak: streak, lastLossMinutes: lastLoss };
  }

  function evaluate(rules, state, trade, now) {
    var out = [];
    function add(id, label, ok, reason) { out.push({ id: id, label: label, ok: ok, reason: reason }); }
    var paper = trade.paper === true;
    var s = summarize(state.trades || [], now);

    // 1. Morning check
    var m = state.morning;
    var mOk = !!(m && m.date === now.date && m.slept && m.calm && (m.watchlist || []).length <= rules.watchlist_max);
    var mWhy = 'Morning check passed.';
    if (!m || m.date !== now.date) mWhy = 'Do the morning check first.';
    else if (!m.slept || !m.calm) mWhy = 'You said you are not rested and calm. No trading today.';
    else if ((m.watchlist || []).length > rules.watchlist_max) mWhy = 'Watchlist has more than ' + rules.watchlist_max + ' names.';
    add('morning', 'Morning check', mOk, mWhy);

    // 2. Entry window
    var w0 = toMin(rules.entry_window.start), w1 = toMin(rules.entry_window.end);
    var wOk = now.minutes >= w0 && now.minutes <= w1;
    add('window', 'Entry window', wOk, wOk
      ? 'It is ' + clock(now.minutes) + ', inside ' + rules.entry_window.start + ' to ' + rules.entry_window.end + '.'
      : 'It is ' + clock(now.minutes) + '. Entries are allowed only ' + rules.entry_window.start + ' to ' + rules.entry_window.end + '.');

    // 3. Segment
    var seg = trade.segment, segOk, segWhy;
    if (rules.real_money_segments.indexOf(seg) >= 0) { segOk = true; segWhy = 'Real money allowed for ' + seg + '.'; }
    else if (rules.paper_only_segments.indexOf(seg) >= 0) {
      segOk = paper;
      segWhy = paper ? seg + ' is paper only, and this is a paper trade.' : seg + ' is paper only. Log it as a paper trade.';
    } else { segOk = false; segWhy = 'Unknown segment: ' + seg + '.'; }
    add('segment', 'Segment', segOk, segWhy);

    // 4. Side (buying only; no short selling)
    add('side', 'Buy only', trade.side === 'buy', trade.side === 'buy' ? 'Long trade.' : 'Short selling and selling options are not allowed.');

    // 5. Prices make sense
    var e = trade.entry, st = trade.stop, tg = trade.target, q = trade.qty;
    var nums = [e, st, tg, q].every(function (x) { return typeof x === 'number' && isFinite(x) && x > 0; });
    var geoOk = nums && Math.floor(q) === q && st < e && e < tg;
    add('prices', 'Prices and quantity', geoOk, geoOk ? 'Stop is below entry and target is above it.' : 'Need whole quantity and stop < entry < target.');
    var risk = geoOk ? (e - st) * q : null;
    var reward = geoOk ? (tg - e) * q : null;

    // 6. Risk per trade
    var rOk = geoOk && risk <= rules.max_loss_per_trade + 1e-9;
    add('risk', 'Risk per trade', rOk, !geoOk ? 'Fix the prices first.' : 'Risk is ' + rupees(risk) + '; limit is ' + rupees(rules.max_loss_per_trade) + '.');

    // 7. Reward vs risk
    var rrOk = geoOk && reward / risk >= rules.min_reward_risk - 1e-9;
    add('rr', 'Reward vs risk', rrOk, !geoOk ? 'Fix the prices first.' : 'Reward vs risk is ' + (Math.round(reward / risk * 100) / 100) + ' to 1; need at least ' + rules.min_reward_risk + ' to 1.');

    // 8-13. Real-money limits (skipped for paper trades)
    var skip = 'Paper trade: real-money limits do not apply.';
    var dOk = paper || s.netToday > -rules.max_loss_per_day;
    add('daily', 'Daily loss limit', dOk, paper ? skip : dOk ? 'Today is ' + rupees(s.netToday) + '; limit is -' + rupees(rules.max_loss_per_day) + '.' : 'Daily limit reached (' + rupees(s.netToday) + '). Stop and close the app.');

    var bOk = paper || (geoOk && risk <= rules.max_loss_per_day + s.netToday + 1e-9);
    add('budget', 'Fits remaining daily budget', bOk, paper ? skip : !geoOk ? 'Fix the prices first.' : bOk ? 'Risk fits what is left of today\'s budget.' : 'Risk ' + rupees(risk) + ' is more than the ' + rupees(Math.max(0, rules.max_loss_per_day + s.netToday)) + ' left today.');

    var wkOk = paper || s.netWeek > -rules.max_loss_per_week;
    add('week', 'Weekly loss limit', wkOk, paper ? skip : wkOk ? 'This week is ' + rupees(s.netWeek) + '; limit is -' + rupees(rules.max_loss_per_week) + '.' : 'Weekly limit reached (' + rupees(s.netWeek) + '). No trading until Monday.');

    var cOk = paper || s.count < rules.max_trades_per_day;
    add('count', 'Trades per day', cOk, paper ? skip : cOk ? s.count + ' of ' + rules.max_trades_per_day + ' trades used today.' : 'All ' + rules.max_trades_per_day + ' trades used today.');

    var stOk = paper || s.streak < rules.max_consecutive_losses;
    add('streak', 'Losses in a row', stOk, paper ? skip : stOk ? s.streak + ' losses in a row.' : s.streak + ' losses in a row. Done for the day.');

    var wait = s.lastLossMinutes === null ? 0 : rules.cooldown_minutes_after_loss - (now.minutes - s.lastLossMinutes);
    var cdOk = paper || wait <= 0;
    add('cooldown', 'Wait after a loss', cdOk, paper ? skip : cdOk ? 'No cooldown running.' : 'Wait ' + wait + ' more minutes after your last loss.');

    // 14. Options: not on expiry day
    var isOpt = rules.option_segments.indexOf(seg) >= 0;
    var xOk = !(isOpt && trade.expiryDay === true);
    add('expiry', 'Expiry day', xOk, xOk ? (isOpt ? 'Not an expiry day.' : 'Not an option.') : 'No option trading on expiry day.');

    return {
      pass: out.every(function (r) { return r.ok; }),
      results: out, risk: risk, reward: reward,
      rr: geoOk ? reward / risk : null, summary: s
    };
  }

  return { evaluate: evaluate, summarize: summarize, toMin: toMin, clock: clock };
});
