"""JSON persistence so the scope and hands agents (separate processes) share one gate."""
import json
import os

from . import policy
from .gate import Actor, Gate, Request
from .sandbox import Sandbox

DEFAULT = os.environ.get("TWOKEYS_STATE", os.path.expanduser("~/.twokeys/state.json"))


def load(path=DEFAULT):
    g = Gate(ledger_path=os.path.join(os.path.dirname(path), "audit.jsonl"))
    if os.path.exists(path):
        d = json.load(open(path))
        g.sandbox = Sandbox(d["sandbox"])
        g._n = d["n"]
        for r in d["requests"]:
            req = Request(r["id"], Actor(**r["requester"]), r["text"], policy.evaluate(r["text"]), r["status"],
                          Actor(**r["approver"]) if r["approver"] else None, r["decision_note"], r["amended_value"],
                          r["evidence"], r["created"])
            g.requests[req.id] = req
    return g


def save(g, path=DEFAULT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    reqs = [dict(id=r.id, requester=vars(r.requester), text=r.text, status=r.status,
                 approver=vars(r.approver) if r.approver else None, decision_note=r.decision_note,
                 amended_value=r.amended_value, evidence=r.evidence, created=r.created) for r in g.requests.values()]
    tmp = path + ".tmp"
    json.dump({"n": g._n, "sandbox": g.sandbox.state, "requests": reqs}, open(tmp, "w"), indent=1)
    os.replace(tmp, path)
