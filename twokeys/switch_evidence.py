"""Turn raw Switch room data into a verified decision.

The hands agent fetches two things with Switch's own agent operations and pipes
them in unchanged:
  participants: output of `list_participants`  -> [{id, name, type: agent|user, ...}]
  messages:     messages from `read_context`    -> [{sender|sender_id, sender_name, body|content, ...}]
The decision is read from the newest message saying `approve|deny|amend RQ-nnnn`.
Only a participant Switch reports as type "user" counts as a person.
"""
import re

from .gate import Actor

DECISION = re.compile(r"\b(approve|approved|deny|denied|amend)\b\s+(RQ-\d{4})\b(.*)", re.I | re.S)


def _get(m, *keys):
    for k in keys:
        if isinstance(m, dict) and m.get(k) is not None:
            return m[k]
    return None


def find_decision(rid, evidence):
    people = {p["id"]: p for p in evidence.get("participants", [])}
    found = None
    for m in evidence.get("messages", []):
        body = _get(m, "body", "content", "text") or ""
        if isinstance(body, dict):
            body = body.get("body", "")
        mt = DECISION.search(body)
        if not mt or mt.group(2).upper() != rid.upper():
            continue
        sid = _get(m, "sender", "sender_id", "user_id")
        p = people.get(sid)
        # Fail closed: unknown sender or Switch-posted-on-behalf messages are not a person.
        is_human = bool(p and p.get("type") == "user" and not m.get("sender_kind") and not m.get("on_behalf_of"))
        verb = mt.group(1).lower()
        verb = {"approved": "approve", "denied": "deny"}.get(verb, verb)
        found = (Actor(sid or "unknown", _get(m, "sender_name") or (p or {}).get("name", "unknown"), is_human),
                 verb, mt.group(3).strip())
    return found
