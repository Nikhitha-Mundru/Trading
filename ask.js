// "Ask anytime": answers from your own rules, today's state and journal. No AI, no internet.
// Works in the browser (window.Ask) and in Node (require).
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory(require('./gatekeeper.js'));
  else root.Ask = factory(root.Gatekeeper);
})(typeof self !== 'undefined' ? self : this, function (G) {
  function rs(n) { return '\u20B9' + (Math.round(n * 100) / 100); }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }
  function esc(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  // ---------- glossary ----------
  var GLOSSARY = [
    { keys: ['vwap'], text: 'VWAP is the volume-weighted average price for the day: the average price paid, giving more weight to busy candles. Traders watch whether price is above or below it. VWAP Bounce waits for a dip to VWAP and a close back above it.' },
    { keys: ['opening range breakout', 'orb', 'opening range'], text: 'The opening range is the high and low of the first 15 minutes after 09:15. Opening Range Breakout (ORB) buys when a candle closes above that high, with the stop at the range low.' },
    { keys: ['gap', 'gaps'], text: 'A gap is the difference between yesterday\'s close and today\'s open. A big gap means the market is reacting to news, and prices can be jumpy.' },
    { keys: ['support', 'resistance', 'support and resistance'], text: 'Support is a price level where buying has repeatedly stopped a fall. Resistance is a level where selling has repeatedly stopped a rise. Treat them as zones, not exact lines.' },
    { keys: ['stop loss', 'stoploss', 'stop'], text: 'A stop is the price where you exit a losing trade to cap the loss. Set it before you enter, then size the position so hitting it costs no more than your per-trade limit.' },
    { keys: ['target'], text: function (r) { return 'The target is the price where you plan to take profit. Your rule needs it at least ' + r.min_reward_risk + ' times the stop distance away.'; } },
    { keys: ['r-multiple', 'r multiple', 'r-multiples'], text: 'R is the amount you risk on a trade. A trade that makes twice what you risked is +2R, and a full stop-out is -1R. Thinking in R lets you compare trades of different sizes.' },
    { keys: ['reward vs risk', 'risk reward', 'risk-reward', 'reward to risk', 'rr'], text: function (r) { return 'Reward vs risk compares the target distance to the stop distance. Your rule needs at least ' + r.min_reward_risk + ' to 1: for every \u20B91 you risk, aim for \u20B9' + r.min_reward_risk + '.'; } },
    { keys: ['position sizing', 'position size'], text: 'Position sizing decides how many shares to buy so a stop-out costs no more than your limit: quantity = rupees you can risk \u00F7 (entry price \u2212 stop price). Ask me "how many shares entry 100 stop 98".' },
    { keys: ['expectancy'], text: 'Expectancy is the average result per trade: win rate \u00D7 average win \u2212 loss rate \u00D7 average loss. Positive after costs means the setup has made money on average, but you need many trades to trust it.' },
    { keys: ['drawdown', 'max drawdown'], text: 'Drawdown is the fall from a peak in cumulative profit to a later low. Max drawdown shows the worst losing stretch.' },
    { keys: ['slippage'], text: 'Slippage is the gap between the price you planned and the price you got. It grows in fast markets and thinly traded stocks.' },
    { keys: ['stt', 'brokerage', 'charges'], text: 'Charges are brokerage, STT (securities transaction tax), exchange fees, GST and stamp duty. On small trades they take a big share of the profit, so backtests must include them.' },
    { keys: ['paper trading', 'paper trade', 'paper'], text: 'Paper trading means simulating trades at live prices with no real money, to test a setup and your discipline first.' },
    { keys: ['backtest', 'backtesting'], text: 'A backtest runs a set of rules on past data to see how they would have done. It can look better than real life, so use costs, slippage and an out-of-sample test.' },
    { keys: ['lookahead bias', 'lookahead'], text: 'Lookahead bias is when a test accidentally uses information that was not known at the time, such as entering at the same candle\'s close that created the signal.' },
    { keys: ['overfitting', 'overfit'], text: 'Overfitting is tuning a setup so closely to past data that it fails on new data. If it only works at one exact setting, be suspicious.' },
    { keys: ['out of sample', 'out-of-sample'], text: 'An out-of-sample test checks a setup on data you did not use to design it. If it only works on the design data, it is probably fitted to the past.' },
    { keys: ['expiry', 'expiry day'], text: 'Expiry is the date an option or futures contract ends. On expiry day prices swing hard and time value collapses, so your rule is no option trading on expiry day.' },
    { keys: ['lot size', 'lot', 'lots'], text: 'A lot size is the fixed quantity one futures or options contract covers, set by the exchange. It changes over time, so check the contract in your broker app. Quantity = lots \u00D7 lot size.' },
    { keys: ['margin'], text: function (r) { return 'Margin is the money your broker blocks to hold a position, a fraction of its value. Futures need far more margin than ' + rs(r.capital) + ' allows safely, which is why they are paper only.'; } },
    { keys: ['intraday'], text: function (r) { return 'Intraday means buying and selling within the same day. Your rule: everything closed by ' + r.close_all_by + '.'; } },
    { keys: ['sip', 'systematic investment plan'], text: 'A SIP (systematic investment plan) invests a fixed amount in a mutual fund on a set date each month. Yours sits outside the daily trading limits.' }
  ];
  var TERMS = [];
  GLOSSARY.forEach(function (g) { g.keys.forEach(function (k) { TERMS.push({ key: k, entry: g }); }); });
  TERMS.sort(function (a, b) { return b.key.length - a.key.length; });

  function glossaryHit(q) {
    for (var i = 0; i < TERMS.length; i++) {
      if (new RegExp('(^|[^a-z])' + esc(TERMS[i].key) + '($|[^a-z])').test(q)) return TERMS[i].entry;
    }
    return null;
  }

  // ---------- state helpers ----------
  function budget(ctx) {
    var s = G.summarize(ctx.state.trades || [], ctx.now), r = ctx.rules;
    var dayLeft = r.max_loss_per_day + s.netToday;
    return { s: s, dayLeft: dayLeft, weekLeft: r.max_loss_per_week + s.netWeek,
             cap: Math.max(0, Math.min(r.max_loss_per_trade, dayLeft)) };
  }
  // Ask the real gatekeeper about a harmless hypothetical trade, so only state-based rules can fail.
  function stateBlockers(ctx) {
    var probe = { segment: 'equity', side: 'buy', entry: 100, stop: 99, target: 102, qty: 1, paper: false };
    var res = G.evaluate(ctx.rules, ctx.state, probe, ctx.now);
    return res.results.filter(function (x) { return !x.ok; }).map(function (x) { return x.reason; });
  }
  function reasonsText(list) { return list.join(' '); }

  // ---------- intents ----------
  function canTrade(ctx) {
    var blockers = stateBlockers(ctx), b = budget(ctx);
    if (blockers.length) return 'Not now. ' + reasonsText(blockers);
    return 'Yes, as far as today goes. You have used ' + b.s.count + ' of ' + ctx.rules.max_trades_per_day + ' trades and can risk up to ' + rs(b.cap) + ' on the next one. The trade itself still has to pass the Check tab.';
  }
  function status(ctx) {
    var b = budget(ctx), r = ctx.rules;
    var open = (ctx.state.trades || []).filter(function (t) { return !t.paper && t.date === ctx.now.date && (t.pnl === null || t.pnl === undefined); }).length;
    var out = 'Today: ' + rs(b.s.netToday) + ' from ' + plural(b.s.count, 'real trade') + ' (daily limit -' + rs(r.max_loss_per_day) + '). This week: ' + rs(b.s.netWeek) + ' (limit -' + rs(r.max_loss_per_week) + ').';
    if (open) out += ' ' + plural(open, 'trade') + ' without a result count as \u20B90 until you enter it in Journal.';
    if (b.s.netToday <= -r.max_loss_per_day) out += ' Daily limit reached. Stop and close the app.';
    if (b.s.netWeek <= -r.max_loss_per_week) out += ' Weekly limit reached. No trading until Monday.';
    return out;
  }
  function risk(ctx) {
    var b = budget(ctx), blockers = stateBlockers(ctx), r = ctx.rules;
    var out = 'On the next trade you can risk up to ' + rs(b.cap) + ' (the per-trade cap is ' + rs(r.max_loss_per_trade) + '; ' + rs(Math.max(0, b.dayLeft)) + ' is left of today\'s ' + rs(r.max_loss_per_day) + ').';
    if (blockers.length) out += ' But right now: ' + reasonsText(blockers);
    return out;
  }
  function size(ctx, q) {
    var e = q.match(/entry\s*(?:at|=|:)?\s*(\d+(?:\.\d+)?)/), s = q.match(/stop\s*(?:loss)?\s*(?:at|=|:)?\s*(\d+(?:\.\d+)?)/);
    if (!e || !s) return 'To size a trade, ask like this: "how many shares entry 100 stop 98".';
    var entry = Number(e[1]), stop = Number(s[1]);
    if (stop >= entry) return 'For a long trade the stop must be below the entry. Short selling is not allowed.';
    var b = budget(ctx), per = entry - stop, qty = Math.floor(b.cap / per);
    if (qty < 1) return 'Even 1 share risks ' + rs(per) + ', more than the ' + rs(b.cap) + ' you can risk now. Use a closer stop or skip this one.';
    return 'Up to ' + plural(qty, 'share') + ': risk ' + rs(qty * per) + ' (' + rs(per) + ' a share, cap ' + rs(b.cap) + '). A target for ' + ctx.rules.min_reward_risk + ' to 1 is ' + rs(entry + ctx.rules.min_reward_risk * per) + '. For options, quantity must be whole lots.';
  }
  function time(ctx) {
    var r = ctx.rules, m = ctx.now.minutes, w0 = G.toMin(r.entry_window.start), w1 = G.toMin(r.entry_window.end), c = G.toMin(r.close_all_by);
    var out = 'It is ' + G.clock(m) + ' IST. ';
    if (m < w0) out += 'Entries open at ' + r.entry_window.start + ' (in ' + plural(w0 - m, 'minute') + ').';
    else if (m <= w1) out += 'The entry window closes at ' + r.entry_window.end + ' (in ' + plural(w1 - m, 'minute') + ').';
    else out += 'The entry window is over.';
    if (m <= c) out += ' Close every position by ' + r.close_all_by + ' (in ' + plural(c - m, 'minute') + ').';
    else out += ' The ' + r.close_all_by + ' close-out time has passed.';
    return out;
  }
  function blocked(ctx) {
    var list = (ctx.state.blocked || []).filter(function (x) { return x.date === ctx.now.date; });
    if (!list.length) return 'Nothing has been blocked today.';
    var last = list[list.length - 1];
    return 'Last block at ' + G.clock(last.minutes) + ' (' + last.segment.replace('_', ' ') + '): ' + last.reasons.join(' ') + ' Blocked checks today: ' + list.length + '.';
  }
  function statLine(label, list) {
    if (!list.length) return label + ': no results yet.';
    var wins = list.filter(function (t) { return t.pnl > 0; }).length, total = list.reduce(function (a, t) { return a + t.pnl; }, 0);
    return label + ': ' + plural(list.length, 'trade') + ', win rate ' + Math.round(wins / list.length * 100) + '%, expectancy ' + rs(total / list.length) + ' a trade, total ' + rs(total) + '.';
  }
  function stats(ctx) {
    var done = (ctx.state.trades || []).filter(function (t) { return typeof t.pnl === 'number'; });
    var out = statLine('Real money', done.filter(function (t) { return !t.paper; })) + ' ' + statLine('Paper', done.filter(function (t) { return t.paper; }));
    if (done.length < 20) out += ' Fewer than 20 results is too few to judge anything. Keep logging.';
    return out;
  }
  var TOPICS = [
    { words: /window|entry|time|early|late/, text: function (r) { return 'Entries only ' + r.entry_window.start + ' to ' + r.entry_window.end + '; everything closed by ' + r.close_all_by + '.'; } },
    { words: /loss|limit|stop|week|daily|day\b/, text: function (r) { return 'Maximum loss: ' + rs(r.max_loss_per_trade) + ' per trade, ' + rs(r.max_loss_per_day) + ' per day, ' + rs(r.max_loss_per_week) + ' per week. Hit the daily limit and you stop and close the app; hit the weekly one and you stop until Monday.'; } },
    { words: /trades|how many/, text: function (r) { return 'At most ' + r.max_trades_per_day + ' trades a day.'; } },
    { words: /reward|ratio|target|risk/, text: function (r) { return 'Reward vs risk at least ' + r.min_reward_risk + ' to 1, and risk no more than ' + rs(r.max_loss_per_trade) + ' per trade.'; } },
    { words: /cooldown|wait|streak|row|consecutive/, text: function (r) { return r.max_consecutive_losses + ' losses in a row ends the day. Wait ' + r.cooldown_minutes_after_loss + ' minutes after any loss.'; } },
    { words: /morning|sleep|slept|calm|watchlist/, text: function (r) { return 'Before trading: slept well and calm, or you do not trade. Watchlist of at most ' + r.watchlist_max + '.'; } },
    { words: /option|futures|expiry|paper|short|sell/, text: function () { return 'Options and futures are paper only. Buying only, never selling or short selling. No option trading on expiry day.'; } }
  ];
  function rules(ctx, q) {
    var hits = TOPICS.filter(function (t) { return t.words.test(q); });
    if (!hits.length) hits = TOPICS;
    return hits.map(function (t) { return t.text(ctx.rules); }).join('\n');
  }
  function help() {
    return 'I can answer from your own rules and journal. Try: "Can I trade now?", "How much can I risk?", "Today\'s P&L", "What are my rules?", "Why was I blocked?", "How am I doing?", "What is VWAP?", or "How many shares entry 100 stop 98".';
  }

  var INTENTS = [
    { id: 'can_trade', rx: [/can i (trade|take|enter|buy)|another trade|allowed to trade|should i trade|am i (allowed|done)|trade now|\bokay to\b/], run: canTrade },
    { id: 'risk', rx: [/how much (can|could|should) i risk|risk (left|now)|budget|room left|how much (is )?left/], run: risk },
    { id: 'status', rx: [/p ?& ?l|pnl|profit|how much (have i|did i) (lose|lost|make|made)|lost today|made today|today|this week|so far|loss so far/], run: status },
    { id: 'blocked', rx: [/why.*(block|stop|fail)|blocked|last check|last block/], run: blocked },
    { id: 'stats', rx: [/win rate|expectancy|how am i doing|stats|results|performance|record|journal/], run: stats },
    { id: 'time', rx: [/what time|time now|how long|time left|minutes left|when (do|does|should|must).*(close|stop|end|exit)|cut-?off|window close/], run: time },
    { id: 'rules', rx: [/\brules?\b|limit|allowed|maximum|\bmax\b|window|cooldown|expiry|options?\b|futures|reward|ratio|morning|watchlist|streak|in a row|how many trades|paper/], run: rules }
  ];

  function answer(question, ctx) {
    var q = String(question || '').toLowerCase().replace(/[?!]+/g, ' ').replace(/\s+/g, ' ').trim();
    if (!q) return { intent: 'help', text: help() };
    if (/shares|quantity|qty|position size|how many (lots|units)/.test(q) && /entry|stop/.test(q)) return { intent: 'size', text: size(ctx, q) };
    var term = glossaryHit(q), ruleWords = /\b(my|rule|rules|limit|allowed|today|now)\b/.test(q);
    var explain = /what('s| is| are)|define|meaning|mean\b|explain|tell me about/.test(q);
    if (term && !ruleWords && (explain || q.split(' ').length <= 3)) {
      return { intent: 'glossary', text: typeof term.text === 'function' ? term.text(ctx.rules) : term.text };
    }
    var best = null, bestScore = 0;
    INTENTS.forEach(function (it) {
      var score = it.rx.reduce(function (a, rx) { return a + (rx.test(q) ? 1 : 0); }, 0);
      if (score > bestScore) { best = it; bestScore = score; }
    });
    if (best) return { intent: best.id, text: best.run(ctx, q) };
    if (term) return { intent: 'glossary', text: typeof term.text === 'function' ? term.text(ctx.rules) : term.text };
    return { intent: 'help', text: help() };
  }

  return { answer: answer, glossary: GLOSSARY };
});
