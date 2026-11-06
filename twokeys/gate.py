"""The two-key state machine and audit ledger.

A request moves: proposed -> approved|denied -> executed|refused.
`execute` is the only path to the sandbox and it fails closed.
"""
import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from . import policy
from .sandbox import Sandbox


class GateRefused(Exception):
    pass


@dataclass
class Actor:
    id: str            # Switch participant id, e.g. @switch-user-ab12:switch
    name: str
    is_human: bool


@dataclass
class Request:
    id: str
    requester: Actor
    text: str
    verdict: policy.Verdict
    status: str = "proposed"
    approver: Optional[Actor] = None
    decision_note: str = ""
    amended_value: Optional[int] = None
    evidence: dict = field(default_factory=dict)
    created: float = field(default_factory=time.time)


class Gate:
    def __init__(self, sandbox=None, ledger_path=None, clock=time.time):
        self.sandbox = sandbox or Sandbox()
        self.requests = {}
        self.audit = []
        self.ledger_path = ledger_path
        self.clock = clock
        self._n = 0

    # -- audit -----------------------------------------------------------
    def _log(self, event, req, **extra):
        line = {"ts": round(self.clock(), 3), "event": event, "request_id": req.id,
                "requester": req.requester.name, "approver": req.approver.name if req.approver else None,
                "proposed": req.verdict.restated, "outcome": req.verdict.outcome, "risk": req.verdict.risk, **extra}
        self.audit.append(line)
        if self.ledger_path:
            import os
            os.makedirs(os.path.dirname(self.ledger_path) or ".", exist_ok=True)
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(line) + "\n")
        return line

    # -- steps -----------------------------------------------------------
    def submit(self, requester: Actor, text: str) -> Request:
        self._n += 1
        rid = f"RQ-{self._n:04d}"
        req = Request(rid, requester, text, policy.evaluate(text))
        if req.verdict.outcome == policy.FORBIDDEN:
            req.status = "refused"
        elif req.verdict.outcome == policy.CLARIFY:
            req.status = "needs_clarification"
        self.requests[rid] = req
        self._log("submitted", req)
        if req.verdict.outcome == policy.AUTO_OK:
            self._run(req, executor="twokeys-hands")
        return req

    def decide(self, rid: str, actor: Actor, decision: str, note: str = "") -> Request:
        req = self.requests.get(rid)
        if req is None:
            raise GateRefused(f"unknown request {rid}")
        if req.status != "proposed":
            raise GateRefused(f"{rid} is {req.status}; only proposed requests take a decision")
        if not actor.is_human:
            self._log("decision_rejected", req, by=actor.name, reason="agents cannot sign off")
            raise GateRefused("agents cannot sign off; a person must")
        if actor.id == req.requester.id:
            self._log("decision_rejected", req, by=actor.name, reason="requester cannot approve own request")
            raise GateRefused("the requester cannot be the second key")
        if decision == "deny":
            req.status, req.approver, req.decision_note = "denied", actor, note
            self._log("denied", req, note=note)
            return req
        if decision == "amend":
            m = re.search(r"(\d{1,3})", note)
            if not (req.verdict.action and req.verdict.action.kind in ("flag", "replay", "scale") and m):
                raise GateRefused("amend supports a new number for flag / replay / scale requests")
            req.amended_value = int(m.group(1))
            decision = "approve"
        if decision != "approve":
            raise GateRefused(f"unknown decision {decision}")
        req.status, req.approver, req.decision_note = "approved", actor, note
        self._log("approved", req, note=note, amended_value=req.amended_value)
        return req

    def execute(self, rid: str, executor: str = "twokeys-hands") -> Request:
        """Fail closed: runs only an approved request with a distinct human approver."""
        req = self.requests.get(rid)
        if req is None:
            raise GateRefused(f"unknown request {rid}")
        ok = (req.status == "approved" and req.verdict.outcome == policy.NEEDS_APPROVAL and req.approver is not None
              and req.approver.is_human and req.approver.id != req.requester.id)
        if not ok:
            self._log("execution_refused", req, executor=executor, status=req.status)
            raise GateRefused(f"{rid} has no valid second-person approval (status {req.status}); nothing ran")
        return self._run(req, executor)

    def _run(self, req, executor):
        act = req.verdict.action
        if req.amended_value is not None:
            act = policy.Action(act.kind, act.service, act.target, req.amended_value)
        before, after = self.sandbox.apply(act)
        req.status = "executed"
        req.evidence = {"ran": act.describe(), "before": before, "after": after}
        self._log("executed", req, executor=executor, ran=act.describe())
        return req
