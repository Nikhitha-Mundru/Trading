"""Run a setup over every CSV in data/.

    python -m research.run_backtest orb
    python -m research.run_backtest vwap --slippage 0.001
"""
import argparse

from gatekeeper import load_rules
from research.backtest import metrics, run_backtest, split_design_test, warnings_for
from research.common import ROOT, load_all
from research.setups import SETUPS


def show(label, m):
    print(f"{label:<12} trades {m['trades']:>3}  win rate {m['win_rate']:.0%}  "
          f"expectancy {m['expectancy']:>7} per trade  total {m['total']:>8}  "
          f"max drawdown {m['max_drawdown']:>7}  avg R {m['avg_r']}  charges {m['charges']}")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("setup", choices=sorted(SETUPS))
    p.add_argument("--slippage", type=float, default=0.0005, help="per side, as a fraction (0.0005 = 0.05%%)")
    p.add_argument("--leverage", type=float, default=1.0, help="1 = cash only; intraday margin is higher but riskier")
    args = p.parse_args(argv)

    data = load_all()
    if not data:
        print("No CSV files in data/. Run: python -m research.fetch_data INFY SBIN ITC")
        return 1
    rules = load_rules()
    trades, blocked = run_backtest(data, SETUPS[args.setup], rules, args.slippage, args.leverage)
    dates = sorted({d for df in data.values() for d in df["date"].unique()})
    design, test = split_design_test(trades, dates)

    print(f"Setup {args.setup}: {len(dates)} days, {len(data)} symbols, {len(blocked)} signals blocked by rules")
    show("All", metrics(trades)); show("Design 70%", metrics(design)); show("Test 30%", metrics(test))
    for w in warnings_for(metrics(design), metrics(test)):
        print("WARNING:", w)
    out = ROOT / "research" / "output"
    out.mkdir(exist_ok=True)
    trades.to_csv(out / f"trades_{args.setup}.csv", index=False)
    print(f"Trade list saved to research/output/trades_{args.setup}.csv. Check 3 trades by hand against a chart.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
