"""Seeded evaluation: TwoKeys vs a single-message chatbot that executes at once.

Run: python -m twokeys.eval   (add --json for machine-readable output)
"""
import json
import re
import sys

from . import policy
from .cases import CASES
from .catalog import lookup
from .gate import Gate, GateRefused

VERB = re.compile(r"roll ?back|revert|deploy|ship|enable|disable|flag|rotate|replay|restart|bounce|scale|drop|delete|status", re.I)


def run_twokeys(case):
    g = Gate()
    req = g.submit(case["by"], case["text"])
    for actor, decision, note in case["decisions"]:
        try:
            g.decide(req.id, actor, decision, note)
        except GateRefused:
            pass
    if req.status not in ("executed", "refused", "needs_clarification"):
        try:
            g.execute(req.id)
        except GateRefused:
            pass
    asked = req.verdict.outcome == policy.CLARIFY
    return {"executed": req.status == "executed", "asked": asked, "signed": req.approver is not None and req.status == "executed",
            "audit_lines": len(g.audit)}


def run_baseline(case):
    """Executes immediately on any message naming one service and an action verb."""
    parseable = len(lookup(case["text"])) == 1 and bool(VERB.search(case["text"]))
    return {"executed": parseable, "asked": not parseable, "signed": False, "audit_lines": 0}


def score(runner):
    s = dict(cases=len(CASES), should_not_run=0, caught=0, false_executions=0, should_run=0, completed=0,
             unsigned_mutations=0, clarify_expected=0, clarified=0, audit_lines=0, failures=[])
    for c in CASES:
        r = runner(c)
        s["audit_lines"] += r["audit_lines"]
        if c["expect"] in ("block", "clarify"):
            s["should_not_run"] += 1
            if r["executed"]:
                s["false_executions"] += 1
                s["failures"].append(c["id"])
            else:
                s["caught"] += 1
            if c["expect"] == "clarify":
                s["clarify_expected"] += 1
                s["clarified"] += int(r["asked"] and not r["executed"])
        else:
            s["should_run"] += 1
            if r["executed"]:
                s["completed"] += 1
            else:
                s["failures"].append(c["id"])
        if r["executed"] and c["expect"] != "auto" and not r["signed"]:
            s["unsigned_mutations"] += 1
    return s


def main(argv=None):
    argv = argv or sys.argv[1:]
    tk, bl = score(run_twokeys), score(run_baseline)
    if "--json" in argv:
        print(json.dumps({"twokeys": tk, "baseline": bl}, indent=2))
        return 0
    print(f"TwoKeys seeded eval: {tk['cases']} chat requests "
          f"({tk['should_not_run']} must not run, {tk['should_run']} should run)\n")
    rows = [("caught (must-not-run cases that did not run)", "caught", "should_not_run"),
            ("false executions", "false_executions", None),
            ("mutations run without a second human", "unsigned_mutations", None),
            ("clarifying question when ambiguous", "clarified", "clarify_expected"),
            ("legit requests completed", "completed", "should_run"),
            ("audit lines written", "audit_lines", None)]
    print(f"{'metric':48} {'TwoKeys':>10} {'baseline':>10}")
    for label, k, d in rows:
        f = (lambda s: f"{s[k]}/{s[d]}") if d else (lambda s: str(s[k]))
        print(f"{label:48} {f(tk):>10} {f(bl):>10}")
    print("\nbaseline = single-message chatbot that executes any parseable command immediately")
    if tk["failures"]:
        print("TwoKeys failures:", ", ".join(tk["failures"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
