"""TwoKeys CLI, called by the Switch agents (and usable by hand).

  python -m twokeys scope --by-id ID --by-name NAME "request text"
  python -m twokeys execute RQ-0001 --evidence evidence.json   (hands agent only)
  python -m twokeys show RQ-0001 | audit | ledger-md | demo | reset
"""
import argparse
import json
import sys

from . import policy, store
from .gate import Actor, GateRefused
from .switch_evidence import find_decision


def fmt_scope(req):
    v = req.verdict
    head = {policy.NEEDS_APPROVAL: "NEEDS SECOND KEY", policy.AUTO_OK: "READ-ONLY, RAN",
            policy.FORBIDDEN: "REFUSED", policy.CLARIFY: "NEED DETAIL"}[v.outcome]
    lines = [f"**{req.id} · {head} · risk {v.risk}**", f"Ask: {v.restated} (from {req.requester.name})"]
    lines += [f"Why: {'; '.join(v.reasons)}"] if v.reasons else []
    if v.proposal:
        lines.append(v.proposal)
    if v.question:
        lines.append(f"Question for {req.requester.name}: {v.question}")
    if v.outcome == policy.NEEDS_APPROVAL:
        lines.append(f"A second person (not {req.requester.name}, not an agent) replies `approve {req.id}`, "
                     f"`deny {req.id} <reason>` or `amend {req.id} <number>`. Nothing runs until then.")
    if req.status == "executed":
        lines.append("Result: " + json.dumps(req.evidence["after"]))
    return "\n".join(lines)


def fmt_exec(req):
    e = req.evidence
    keys = [k for k in e["after"] if e["before"].get(k) != e["after"][k]] or ["version"]
    e = dict(e, before={k: e["before"].get(k) for k in keys}, after={k: e["after"][k] for k in keys})
    return (f"**{req.id} · EXECUTED in sandbox** · {e['ran']}\nRequested by {req.requester.name}, "
            f"approved by {req.approver.name}{' (amended)' if req.amended_value is not None else ''}\n"
            f"Before: {json.dumps(e['before'])}\nAfter:  {json.dumps(e['after'])}")


def ledger_md(g):
    rows = ["| request | requester | approver | proposed | status |", "|---|---|---|---|---|"]
    for r in g.requests.values():
        rows.append(f"| {r.id} | {r.requester.name} | {r.approver.name if r.approver else '-'} | "
                    f"{r.verdict.restated} | {r.status} |")
    return "\n".join(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="twokeys")
    ap.add_argument("--state", default=store.DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scope"); s.add_argument("--by-id", required=True); s.add_argument("--by-name", required=True)
    s.add_argument("text", nargs="+")
    e = sub.add_parser("execute"); e.add_argument("rid"); e.add_argument("--evidence", required=True)
    sh = sub.add_parser("show"); sh.add_argument("rid")
    for n in ("audit", "ledger-md", "demo", "reset"):
        sub.add_parser(n)
    a = ap.parse_args(argv)

    if a.cmd == "demo":
        from .demo import main as demo
        return demo()
    if a.cmd == "reset":
        import os, shutil
        d = os.path.dirname(a.state)
        shutil.rmtree(d, ignore_errors=True)
        print("state cleared:", d)
        return 0
    g = store.load(a.state)
    if a.cmd == "scope":
        # The requester is whoever Switch says posted the message; agents can't request on a person's behalf here.
        req = g.submit(Actor(a.by_id, a.by_name, True), " ".join(a.text))
        store.save(g, a.state)
        print(fmt_scope(req))
        return 0
    if a.cmd == "execute":
        ev = json.load(sys.stdin if a.evidence == "-" else open(a.evidence))
        found = find_decision(a.rid, ev)
        if not found:
            try:
                g.execute(a.rid)
            except GateRefused as x:
                store.save(g, a.state)
                print(f"**{a.rid} · NOT RUN** · {x}. No decision message from a person found in the room.")
                return 2
            return 2
        actor, verb, note = found
        try:
            req = g.decide(a.rid, actor, verb, note)
            if req.status == "denied":
                store.save(g, a.state)
                print(f"**{a.rid} · DENIED by {actor.name}** · {note or 'no reason given'}. Nothing ran.")
                return 0
            req = g.execute(a.rid, executor="twokeys-hands")
        except GateRefused as x:
            try:
                g.execute(a.rid)
            except GateRefused:
                pass
            store.save(g, a.state)
            print(f"**{a.rid} · NOT RUN** · {x}.")
            return 2
        store.save(g, a.state)
        print(fmt_exec(req))
        return 0
    if a.cmd == "show":
        r = g.requests.get(a.rid)
        print(fmt_scope(r) if r else f"unknown {a.rid}")
        return 0 if r else 1
    if a.cmd == "audit":
        import os
        p = g.ledger_path
        if p and os.path.exists(p):
            print(open(p).read(), end="")
        return 0
    if a.cmd == "ledger-md":
        print(ledger_md(g))
        return 0


if __name__ == "__main__":
    sys.exit(main())
