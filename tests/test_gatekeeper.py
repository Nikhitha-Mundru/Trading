
import json, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gatekeeper import evaluate, load_rules  # noqa: E402

RULES = load_rules(ROOT / "rules.json")
CASES = json.loads((Path(__file__).parent / "cases.json").read_text())


@pytest.mark.parametrize("c", CASES, ids=[c["name"] for c in CASES])
def test_case(c):
    res = evaluate(RULES, c["state"], c["trade"], c["now"])
    failed = sorted(r["id"] for r in res["results"] if not r["ok"])
    assert failed == c["expectFailed"]
    assert res["pass"] == (not c["expectFailed"])
