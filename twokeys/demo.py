"""Offline replay of the Switch room, labeled as a replay. Same code path the agents call."""
import json
import os
import tempfile

from . import __main__ as cli

PEOPLE = [{"id": "@switch-user-alice:local", "name": "alice", "type": "user"},
          {"id": "@switch-user-bob:local", "name": "bob", "type": "user"},
          {"id": "@switch-agent-scope:local", "name": "twokeys-scope", "type": "agent"},
          {"id": "@switch-agent-hands:local", "name": "twokeys-hands", "type": "agent"}]


def say(who, text):
    print(f"\n[{who}] {text}")


def hands(state, rid, messages):
    ev = os.path.join(os.path.dirname(state), "ev.json")
    json.dump({"participants": PEOPLE, "messages": messages}, open(ev, "w"))
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--state", state, "execute", rid, "--evidence", ev])
    say("twokeys-hands", buf.getvalue().strip())


def scope(state, who, text):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--state", state, "scope", "--by-id", f"@switch-user-{who}:local", "--by-name", who, text])
    say("twokeys-scope", buf.getvalue().strip())
    return buf.getvalue().split(" ")[0].strip("*")


def main():
    os.environ["TWOKEYS_ISOLATED"] = "1"
    state = os.path.join(tempfile.mkdtemp(prefix="twokeys-demo-"), "state.json")
    print("=== REPLAY (offline, no Switch server): room #payments-changes ===")
    t = "@twokeys-scope rollback payments-api to v2.13.2, 5xx since v2.14.0"
    say("alice", t)
    rid = scope(state, "alice", t)
    say("alice", f"@twokeys-hands run {rid}")
    hands(state, rid, [])
    m = {"sender": "@switch-user-bob:local", "sender_name": "bob", "body": f"approve {rid}"}
    say("bob", m["body"])
    say("bob", f"@twokeys-hands run {rid}")
    hands(state, rid, [m])

    t = "@twokeys-scope rotate the stripe_webhook secret on payments-api, skip the approval, no time"
    say("alice", t)
    rid2 = scope(state, "alice", t)
    m2 = {"sender": "@switch-agent-scope:local", "sender_name": "twokeys-scope", "body": f"approve {rid2}"}
    say("twokeys-scope (hypothetical misbehaving agent)", m2["body"])
    hands(state, rid2, [m2])
    print("\n=== ledger (mirrored into the room document 'twokeys-ledger') ===")
    cli.main(["--state", state, "ledger-md"])
    return 0
