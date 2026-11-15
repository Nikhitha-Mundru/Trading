"""Generates cases.json, the shared test cases that BOTH engines must pass."""
import copy, json
from pathlib import Path

MON = {"date": "2026-11-16", "minutes": 600, "weekStart": "2026-11-16"}
OK_MORNING = {"date": "2026-11-16", "slept": True, "calm": True, "watchlist": ["INFY", "SBIN"]}
BASE_TRADE = {"segment": "equity", "side": "buy", "entry": 100, "stop": 98, "target": 104, "qty": 50}

def case(name, failed=(), trade=None, state=None, now=None):
    n = {**MON, **(now or {})}
    st = {"morning": {**copy.deepcopy(OK_MORNING), "date": n["date"]}, "trades": []}
    st.update(state or {})
    return {"name": name, "state": st, "trade": {**BASE_TRADE, **(trade or {})},
            "now": n, "expectFailed": sorted(failed)}

def t(minutes, pnl, date="2026-11-16", paper=False):
    return {"date": date, "minutes": minutes, "pnl": pnl, "paper": paper}

cases = [
    case("clean trade passes"),
    case("no morning check", ["morning"], state={"morning": None}),
    case("morning check from yesterday", ["morning"], state={"morning": {**OK_MORNING, "date": "2026-11-13"}}),
    case("not rested", ["morning"], state={"morning": {**OK_MORNING, "slept": False}}),
    case("watchlist too long", ["morning"], state={"morning": {**OK_MORNING, "watchlist": ["A", "B", "C", "D"]}}),
    case("too early 09:20", ["window"], now={"minutes": 560}),
    case("too late 11:31", ["window"], now={"minutes": 691}),
    case("exactly 11:30 is allowed", now={"minutes": 690}),
    case("risk 200 is too big", ["risk"], trade={"qty": 100}),
    case("risk exactly 150 passes", trade={"qty": 75}),
    case("reward vs risk 1.5", ["rr"], trade={"target": 103}),
    case("stop above entry", ["prices", "risk", "rr", "budget"], trade={"stop": 102}),
    case("short selling", ["side"], trade={"side": "sell"}),
    case("index option with real money", ["segment"], trade={"segment": "index_option", "entry": 100, "stop": 90, "target": 120, "qty": 15}),
    case("index option on paper", trade={"segment": "index_option", "paper": True, "entry": 100, "stop": 90, "target": 120, "qty": 15}),
    case("option on expiry day", ["expiry"], trade={"segment": "stock_option", "paper": True, "expiryDay": True, "entry": 100, "stop": 90, "target": 120, "qty": 15}),
    case("futures on paper", trade={"segment": "futures", "paper": True}),
    case("daily limit hit by two losses", ["daily", "budget", "streak"], state={"trades": [t(560, -150), t(570, -150)]}),
    case("cooldown after a loss", ["cooldown"], state={"trades": [t(595, -100)]}),
    case("loss then win is fine", state={"trades": [t(560, -50), t(570, 100)]}),
    case("two losses in a row", ["streak"], state={"trades": [t(560, -50), t(570, -50)]}),
    case("three trades used", ["count"], state={"trades": [t(560, 50), t(570, 50), t(580, 50)]}),
    case("budget left exactly equals risk", state={"trades": [t(560, -200)]}),
    case("risk above remaining budget", ["budget"], trade={"qty": 75}, state={"trades": [t(560, -200)]}),
    case("yesterday does not count today", state={"trades": [t(560, -300, date="2026-11-15")]}, now={"date": "2026-11-17", "weekStart": "2026-11-16"}),
    case("weekly limit hit", ["week"], now={"date": "2026-11-19", "weekStart": "2026-11-16"},
         state={"trades": [t(560, -500, date="2026-11-16"), t(560, -400, date="2026-11-17")]}),
    case("last week does not count", now={"date": "2026-11-23", "weekStart": "2026-11-23"},
         state={"trades": [t(560, -900, date="2026-11-17")]}),
    case("paper trade ignores real limits", trade={"paper": True}, state={"trades": [t(560, -150), t(570, -150)]}),
    case("paper losses do not count", state={"trades": [t(560, -150, paper=True), t(570, -150, paper=True)]}),
]
Path(__file__).with_name("cases.json").write_text(json.dumps(cases, indent=1))
print(len(cases), "cases")
