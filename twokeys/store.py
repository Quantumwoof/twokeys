"""JSON persistence so the scope and hands agents (separate processes) share one gate."""
import json
import os
import re

from . import policy
from .gate import Actor, Gate, Request
from .sandbox import Sandbox

HOME_FALLBACK = os.path.expanduser("~/.twokeys/state.json")
# Live Codex/Switch sandboxes treat $HOME as a read-only filesystem (EROFS) but
# can write under /tmp. A single well-known path here keeps both agents in sync.
LIVE_FALLBACK = "/tmp/twokeys-shared/state.json"
FALLBACK = LIVE_FALLBACK

# Codex often sets TWOKEYS_STATE=/tmp/tmpXXXX/state.json (mkdtemp-style) and cds
# out of the agent directory, which used to split Scope and Hands.
_INVENTED_TMP = re.compile(r"^/tmp/tmp[A-Za-z0-9_]+/state\.json$")


def _as_live_switch_agent():
    """True when this process is one of the live Switch TwoKeys agents."""
    parts = [os.getcwd(), os.environ.get("PWD") or "", os.path.abspath(__file__)]
    blob = " ".join(parts)
    return any(marker in blob for marker in ("-twokeys-scope", "-twokeys-hands", "payments-twokeys", "/.switch/agents/"))


def _isolated():
    return bool(os.environ.get("TWOKEYS_ISOLATED"))


def resolve(path=None):
    """Turn a CLI/env path into an absolute file path.

    Live Switch templates left `{state_file}` unexpanded, so agents invented
    *different* tempfiles and Hands could not see a request Scope had just
    opened. Home (`~/.twokeys`) is also unwritable inside the agent sandbox.
    Live traffic therefore shares /tmp/twokeys-shared/state.json. Tests and
    `twokeys demo` opt out with TWOKEYS_ISOLATED or a non-live path.
    """
    if not _isolated() and _as_live_switch_agent():
        return os.path.abspath(LIVE_FALLBACK)
    raw = HOME_FALLBACK if path is None else path
    raw = os.path.expanduser(str(raw or ""))
    if not raw or "{" in raw or "}" in raw:
        raw = HOME_FALLBACK if _isolated() else LIVE_FALLBACK
    raw = os.path.abspath(raw)
    if _isolated():
        return raw
    if raw == os.path.abspath(HOME_FALLBACK) or _INVENTED_TMP.match(raw):
        return os.path.abspath(LIVE_FALLBACK)
    return raw


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
    try:
        json.dump({"n": g._n, "sandbox": g.sandbox.state, "requests": reqs}, open(tmp, "w"), indent=1)
        os.replace(tmp, path)
    except OSError as e:
        if getattr(e, "errno", None) in {30, 13} and path != os.path.abspath(LIVE_FALLBACK):
            return save(g, LIVE_FALLBACK)
        raise
