from research.review import by_hour, infer_rules, parse, report, stop_rule_attempts

SAMPLE = '''TRADES
date,time,segment,paper,entry,stop,target,qty,risk,pnl
2026-11-16,09:40,equity,false,100,98,104,50,100,-100
2026-11-16,10:20,equity,false,200,196,208,25,100,150
2026-11-17,09:45,equity,true,100,98,104,50,100,
2026-11-17,10:15,index_option,true,100,90,120,15,150,300

BLOCKED
date,time,segment,rules,reasons
2026-11-16,09:20,equity,window,"It is 09:20. Entries are allowed only 09:30 to 11:30."
2026-11-16,10:25,equity,cooldown;count,"Wait 3 more minutes after your last loss. | All 3 trades used today."
'''


def test_parse_reads_both_sections_and_quoted_reasons():
    trades, blocked = parse(SAMPLE)
    assert len(trades) == 4 and len(blocked) == 2
    assert list(trades["paper"]) == [False, False, True, True]
    assert blocked["rule_list"][1] == ["cooldown", "count"]
    assert "|" in blocked["reasons"][1]


def test_results_and_missing_by_hand():
    text = report(SAMPLE)
    assert "4 (2 real, 2 paper)" in text and "1 have no result" in text
    assert "Real money: 2 trades, win rate 50%, expectancy 25.0 per trade, total 50.0" in text
    assert "Paper: 1 trades" in text and "total 300.0" in text


def test_by_hour_buckets():
    trades, _ = parse(SAMPLE)
    done = trades[trades["pnl"].notna()]
    assert by_hour(done) == {"09": {"trades": 1, "total": -100.0}, "10": {"trades": 2, "total": 450.0}}


def test_stop_rule_attempts_counts_only_stop_rules():
    _, blocked = parse(SAMPLE)
    assert stop_rule_attempts(blocked) == 1  # the window block is not a stop rule; cooldown/count is
    assert "ran 1 checks after a stop rule" in report(SAMPLE)


def test_old_exports_without_rule_ids_are_inferred_from_text():
    old = '''BLOCKED
date,time,segment,reasons
2026-11-16,10:00,equity,"Daily limit reached (-300). Stop and close the app. | Wait 4 more minutes after your last loss."
'''
    _, blocked = parse(old)
    assert blocked["rule_list"][0] == ["daily", "cooldown"]
    assert infer_rules("Risk ₹150 is more than the ₹100 left today.") == ["budget"]
    assert infer_rules("Risk is ₹200; limit is ₹150.") == ["risk"]


def test_empty_inputs_do_not_crash():
    assert "no data" in report("")
    assert "Nothing was blocked" in report("TRADES\ndate,time,segment,paper,entry,stop,target,qty,risk,pnl\n2026-11-16,10:00,equity,false,100,98,104,50,100,100\n")


def test_advice_points_at_the_top_blocking_rule():
    text = "BLOCKED\ndate,time,segment,rules,reasons\n" + "\n".join(
        f'2026-11-16,1{i}:00,equity,window,"x"' for i in range(3))
    assert "time window" in report(text)


def test_a_day_where_everything_was_blocked():
    text = 'BLOCKED\ndate,time,segment,rules,reasons\n2026-11-16,10:00,equity,morning,"Do the morning check first."\n'
    out = report(text)
    assert "2026-11-16" in out and "No trades logged" in out and "morning check: 1" in out
