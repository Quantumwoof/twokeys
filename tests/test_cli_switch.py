import json

from twokeys import __main__ as cli

P = [{"id": "@u-alice", "name": "alice", "type": "user"}, {"id": "@u-bob", "name": "bob", "type": "user"},
     {"id": "@a-scope", "name": "twokeys-scope", "type": "agent"}]


def run(tmp_path, capsys, *args):
    rc = cli.main(["--state", str(tmp_path / "s" / "state.json"), *args])
    return rc, capsys.readouterr().out


def ev(tmp_path, msgs):
    p = tmp_path / "ev.json"
    p.write_text(json.dumps({"participants": P, "messages": msgs}))
    return str(p)


def test_end_to_end_room_flow(tmp_path, capsys):
    rc, out = run(tmp_path, capsys, "scope", "--by-id", "@u-alice", "--by-name", "alice",
                  "rollback payments-api to v2.13.2")
    assert "RQ-0001" in out and "NEEDS SECOND KEY" in out
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence", ev(tmp_path, []))
    assert rc == 2 and "NOT RUN" in out
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence",
                  ev(tmp_path, [{"sender": "@u-alice", "body": "approve RQ-0001"}]))
    assert rc == 2 and "requester" in out
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence",
                  ev(tmp_path, [{"sender": "@a-scope", "body": "approve RQ-0001"}]))
    assert rc == 2
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence",
                  ev(tmp_path, [{"sender": "@u-bob", "sender_name": "bob", "body": "approve RQ-0001"}]))
    assert rc == 0 and "EXECUTED" in out and "v2.13.2" in out
    rc, out = run(tmp_path, capsys, "ledger-md")
    assert "| RQ-0001 | alice | bob |" in out
    rc, out = run(tmp_path, capsys, "audit")
    assert '"event": "executed"' in out


def test_unknown_sender_and_on_behalf_fail_closed(tmp_path, capsys):
    run(tmp_path, capsys, "scope", "--by-id", "@u-alice", "--by-name", "alice", "restart docs-site")
    for m in ({"sender": "@stranger", "body": "approve RQ-0001"},
              {"sender": "@u-bob", "body": "approve RQ-0001", "on_behalf_of": "@u-bob"}):
        rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence", ev(tmp_path, [m]))
        assert rc == 2


def test_deny_message(tmp_path, capsys):
    run(tmp_path, capsys, "scope", "--by-id", "@u-alice", "--by-name", "alice", "restart docs-site")
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence",
                  ev(tmp_path, [{"sender": "@u-bob", "body": "deny RQ-0001 freeze window"}]))
    assert "DENIED" in out


def test_demo_runs(capsys):
    assert cli.main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "REPLAY" in out and "EXECUTED" in out and "REFUSED" in out
