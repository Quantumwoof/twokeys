"""Deterministic scope + policy engine. Models may chat; this decides."""
import re
from dataclasses import dataclass, field
from typing import Optional

from .catalog import lookup
from .sandbox import SEED

# Outcomes
NEEDS_APPROVAL = "needs_approval"   # second human must sign off before hands runs
AUTO_OK = "auto_ok"                 # read-only, runs without sign-off
FORBIDDEN = "forbidden"             # never runs from chat
CLARIFY = "clarify"                 # ask the requester a question first

BYPASS = re.compile(
    r"skip (the )?(approval|sign-?off|review)|no (need for|need to wait for) (approval|sign-?off)|"
    r"without (approval|sign-?off|review)|bypass|don'?t wait for|i approve (it|this|my own)|"
    r"(already|pre-?)approved|approve it yourself|just do it|override (the )?(gate|policy)",
    re.I,
)
DESTRUCTIVE = re.compile(r"\b(drop|delete|truncate|wipe|purge|destroy)\b", re.I)


@dataclass
class Action:
    kind: str
    service: str
    target: Optional[str] = None
    value: Optional[int] = None

    def describe(self):
        k, s, t, v = self.kind, self.service, self.target, self.value
        return {
            "status": f"read status of {s}",
            "rollback": f"roll back {s} to {t}",
            "deploy": f"deploy {t} to {s}",
            "flag": f"set flag {t} on {s} to {v}%",
            "rotate": f"rotate secret {t} on {s}",
            "replay": f"replay {v} dead-lettered events on {s}",
            "restart": f"rolling restart of {s}",
            "scale": f"scale {s} to {v} replicas",
        }.get(k, f"{k} {s}")


@dataclass
class Verdict:
    outcome: str
    risk: str  # none | low | medium | high | critical
    restated: str
    reasons: list = field(default_factory=list)
    action: Optional[Action] = None
    proposal: Optional[str] = None
    question: Optional[str] = None


def _parse_action(text, svc):
    t = text.lower()
    state = SEED[svc.name]
    ver = re.search(r"\b(v\d+(?:\.\d+)*|pg-[\d.]+)\b", t)
    pct = re.search(r"(\d{1,3})\s*%", t)
    num = re.search(r"\b(\d+)\b", t)
    if re.search(r"\b(status|version|what'?s running|health)\b", t) and not re.search(r"rollback|roll back|deploy|set|enable", t):
        return Action("status", svc.name), None
    if re.search(r"roll ?back|revert", t):
        if not ver:
            return None, f"Roll {svc.name} back to which version? Known: {', '.join(state['history'][:-1])}."
        return Action("rollback", svc.name, ver.group(1)), None
    if re.search(r"\bdeploy|ship|release\b", t):
        if not ver:
            return None, f"Deploy which version of {svc.name}?"
        return Action("deploy", svc.name, ver.group(1)), None
    if re.search(r"\bflag|enable|disable|turn (on|off)|rollout\b", t):
        names = list(state["flags"]) 
        flag = next((f for f in names if f in t), None)
        if not flag:
            return None, f"Which flag on {svc.name}? Known: {', '.join(names) or 'none'}."
        if re.search(r"disable|turn off", t):
            return Action("flag", svc.name, flag, 0), None
        if not pct:
            return None, f"What percentage of traffic should {flag} go to?"
        return Action("flag", svc.name, flag, int(pct.group(1))), None
    if re.search(r"\brotate\b", t):
        secrets = list(state["secrets"])
        sec = next((s for s in secrets if s.replace("_", " ") in t.replace("_", " ")), None)
        if not sec and len(secrets) == 1 and "secret" in t:
            sec = secrets[0]
        if not sec:
            return None, f"Which secret on {svc.name}? Known: {', '.join(secrets) or 'none'}."
        return Action("rotate", svc.name, sec), None
    if re.search(r"\breplay\b", t):
        n = num.group(1) if num else None
        return Action("replay", svc.name, None, int(n) if n else state.get("dlq", 0)), None
    if re.search(r"\brestart|bounce\b", t):
        return Action("restart", svc.name), None
    if re.search(r"\bscale\b", t):
        if not num:
            return None, f"Scale {svc.name} to how many replicas?"
        return Action("scale", svc.name, None, int(num.group(1))), None
    return None, "I couldn't map that to a known action (rollback, deploy, flag, rotate, replay, restart, scale, status)."


def evaluate(text: str) -> Verdict:
    """Restate, scope, and classify one chat request. Pure and deterministic."""
    reasons = []
    services = lookup(text)
    if len(services) != 1:
        q = ("Which service? " + ", ".join(s.name for s in services)) if services else \
            "Which service do you mean? I only act on services in the catalog."
        return Verdict(CLARIFY, "unknown", f"Unscoped request: {text.strip()}", ["target service is ambiguous or unknown"], question=q)
    svc = services[0]

    if DESTRUCTIVE.search(text):
        reasons.append(f"destructive verb against {svc.name}" + (" (no-touch service)" if svc.no_touch else ""))
        return Verdict(FORBIDDEN, "critical", f"Destructive request against {svc.name}", reasons,
                       proposal="Destructive data operations are not run from chat. Open a change ticket with the data owner "
                                f"({svc.owner}).")

    action, question = _parse_action(text, svc)
    if action is None:
        return Verdict(CLARIFY, "unknown", f"Request against {svc.name}, action unclear", ["missing parameter"], question=question)

    restated = action.describe()
    if BYPASS.search(text):
        reasons.append("request asks to skip or self-supply the second sign-off")
        return Verdict(FORBIDDEN, "critical", restated, reasons, action=action,
                       proposal="Dual control cannot be waived from chat. Re-post the request without the bypass and a "
                                "second person will be asked to sign off.")

    if action.kind == "status":
        return Verdict(AUTO_OK, "none", restated, ["read-only"], action=action)

    if svc.no_touch and action.kind not in ("restart",):
        return Verdict(FORBIDDEN, "critical", restated, [f"{svc.name} is no-touch from chat"], action=action,
                       proposal=f"Contact {svc.owner}; changes to {svc.name} go through its own change board.")

    if action.kind in ("rollback", "deploy") and action.target not in SEED[svc.name]["history"]:
        return Verdict(CLARIFY, "unknown", restated, ["version not in release history"],
                       question=f"{action.target} isn't in {svc.name}'s release history "
                                f"({', '.join(SEED[svc.name]['history'])}). Which one did you mean?")
    if action.kind == "flag" and not 0 <= action.value <= 100:
        return Verdict(CLARIFY, "unknown", restated, ["percentage out of range"], question="Percentage must be 0-100.")

    risk = {"payments": "high", "pii": "high", "none": "low"}[svc.data_class]
    if action.kind in ("rotate",) and svc.data_class != "none":
        risk = "critical"
    proposal = f"Smallest safe action: {restated} (sandbox)."
    if action.kind == "flag" and action.value > 25 and svc.data_class != "none":
        current = SEED[svc.name]["flags"].get(action.target, 0)
        proposal = (f"Smallest safe action: ramp {action.target} from {current}% to 25% first, watch error rate, "
                    f"then {action.value}%. Approver may amend.")
    if action.kind == "replay":
        proposal = f"Smallest safe action: replay {min(action.value, 10)} events as a canary, then the rest."
    reasons.append(f"data class {svc.data_class}; owner {svc.owner}")
    if svc.dual_control:
        reasons.append("catalog requires dual control")
    else:
        reasons.append("mutating action: TwoKeys always asks a second human")
    return Verdict(NEEDS_APPROVAL, risk, restated, reasons, action=action, proposal=proposal)
