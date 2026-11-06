"""JSON persistence so the scope and hands agents (separate processes) share one gate."""
import json
import os

from . import policy
from .gate import Actor, Gate, Request
from .sandbox import Sandbox

FALLBACK = os.path.expanduser("~/.twokeys/state.json")


def _as_live_switch_agent():
    """Scope and Hands run with cwd under ~/.switch/agents/.../*-twokeys-*."""
    cwd = os.getcwd()
    return any(marker in cwd for marker in ("-twokeys-scope", "-twokeys-hands", "payments-twokeys"))


def resolve(path=None):
    """Turn a CLI/env path into an absolute file path.

    Live Switch templates left `{state_file}` unexpanded in agent instructions,
    which made agents invent tempfiles — and invent *different* ones, so Hands
    could not see a request Scope had just opened. When we are one of those
    agents, always use the shared fallback. Tests and `twokeys demo` pass an
    explicit --state from another directory and are unchanged.
    """
    if _as_live_switch_agent():
        return os.path.abspath(FALLBACK)
    raw = FALLBACK if path is None else path
    raw = os.path.expanduser(str(raw or ""))
    if not raw or "{" in raw or "}" in raw:
        raw = FALLBACK
    return os.path.abspath(raw)


DEFAULT = resolve(os.environ.get("TWOKEYS_STATE"))


def load(path=DEFAULT):
    path = resolve(path)
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
    path = resolve(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    reqs = [dict(id=r.id, requester=vars(r.requester), text=r.text, status=r.status,
                 approver=vars(r.approver) if r.approver else None, decision_note=r.decision_note,
                 amended_value=r.amended_value, evidence=r.evidence, created=r.created) for r in g.requests.values()]
    tmp = path + ".tmp"
    json.dump({"n": g._n, "sandbox": g.sandbox.state, "requests": reqs}, open(tmp, "w"), indent=1)
    os.replace(tmp, path)
