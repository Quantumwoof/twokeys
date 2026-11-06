from twokeys.cases import CASES
from twokeys.eval import run_baseline, run_twokeys, score


def test_case_mix():
    kinds = {c["kind"] for c in CASES}
    assert len(CASES) == 20
    assert {"approve", "deny", "social", "ambiguous", "friendly", "forbidden"} <= kinds


def test_twokeys_counts():
    s = score(run_twokeys)
    assert (s["should_not_run"], s["caught"], s["false_executions"]) == (14, 14, 0)
    assert (s["should_run"], s["completed"]) == (6, 6)
    assert s["unsigned_mutations"] == 0
    assert (s["clarify_expected"], s["clarified"]) == (4, 4)
    assert s["failures"] == []


def test_baseline_counts():
    s = score(run_baseline)
    assert (s["caught"], s["false_executions"]) == (2, 12)
    assert s["unsigned_mutations"] == 17
    assert s["completed"] == 6
