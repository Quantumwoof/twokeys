"""Turn raw Switch room data into a verified decision.

The hands agent fetches two things with Switch's own agent operations and pipes
them in unchanged:
  participants: output of `list_participants`  -> [{id, name, type: agent|user, ...}]
  messages:     messages from `read_context`    -> either a flat list of
                {sender|sender_id, sender_name, body|content, ...} or the live
                Switch shape [{root: {...}, replies: [...]}, ...]
The decision is read from the newest message saying `approve|deny|amend RQ-nnnn`.
Only a participant Switch reports as type "user" counts as a person.
Participant `id` is often a UUID, while message `sender` is a Switch address
such as `@switch-mattermost-<id>-bob:localhost`; we also match on `sender_name`.
"""
import re

from .gate import Actor

DECISION = re.compile(r"\b(approve|approved|deny|denied|amend)\b\s+(RQ-\d{4})\b(.*)", re.I | re.S)


def _get(m, *keys):
    for k in keys:
        if isinstance(m, dict) and m.get(k) is not None:
            return m[k]
    return None


def _iter_messages(items):
    """Yield individual message dicts from a flat list or read_context threads."""
    if items is None:
        return
    if isinstance(items, dict):
        # Wrapper from dumping the whole read_context payload.
        if "messages" in items and "body" not in items and "content" not in items and "text" not in items:
            if "root" not in items:
                yield from _iter_messages(items.get("messages"))
                return
        if "root" in items:
            yield from _iter_messages(items.get("root"))
            yield from _iter_messages(items.get("replies") or [])
            return
        yield items
        return
    if isinstance(items, list):
        for it in items:
            yield from _iter_messages(it)


def _person(people, m):
    """Resolve a message sender to a list_participants row, or None."""
    sid = _get(m, "sender", "sender_id", "user_id")
    sname = (_get(m, "sender_name") or "").strip()
    by_id = {p["id"]: p for p in people if p.get("id")}
    by_name = {}
    for p in people:
        n = (p.get("name") or "").strip().lower()
        if n and n not in by_name:
            by_name[n] = p
    if sid and sid in by_id:
        return by_id[sid], sid
    if sname and sname.lower() in by_name:
        p = by_name[sname.lower()]
        return p, sid or p.get("id")
    if sid:
        sl = str(sid).lower()
        for p in people:
            n = (p.get("name") or "").strip()
            if not n:
                continue
            nl = n.lower()
            if sl.endswith(f"-{nl}:localhost") or sl.endswith(f"-{nl}") or f"-{nl}:" in sl:
                return p, sid
    return None, sid


def find_decision(rid, evidence):
    people = evidence.get("participants") or []
    found = None
    found_human = False
    for m in _iter_messages(evidence.get("messages")):
        if not isinstance(m, dict):
            continue
        body = _get(m, "body", "content", "text") or ""
        if isinstance(body, dict):
            body = body.get("body", "")
        mt = DECISION.search(str(body))
        if not mt or mt.group(2).upper() != rid.upper():
            continue
        p, sid = _person(people, m)
        # Fail closed: unknown sender or Switch-posted-on-behalf messages are not a person.
        is_human = bool(p and p.get("type") == "user" and not m.get("sender_kind") and not m.get("on_behalf_of"))
        verb = mt.group(1).lower()
        verb = {"approved": "approve", "denied": "deny"}.get(verb, verb)
        actor_id = (p or {}).get("id") or sid or "unknown"
        actor_name = _get(m, "sender_name") or (p or {}).get("name") or "unknown"
        candidate = (Actor(actor_id, actor_name, is_human), verb, mt.group(3).strip())
        # Newest person wins. An agent's own help text also contains
        # "approve RQ-nnnn" and must not overwrite a later (or earlier) human sign-off.
        if is_human or not found_human:
            found = candidate
            found_human = found_human or is_human
    return found
