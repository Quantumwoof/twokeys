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



def test_live_read_context_tree_and_mismatched_ids(tmp_path, capsys):
    """Switch list_participants uses UUIDs; read_context nests root/replies and
    names senders as @switch-mattermost-...-bob:localhost. That is what broke
    the first live rehearsal: bob's approve was in evidence and still unseen."""
    people = [
        {"id": "00723657-e8e2-4b94-a61f-726bea139615", "name": "payments-twokeys-scope", "type": "agent"},
        {"id": "d79c4fc0-71fd-459d-a54c-6f5408b4cff9", "name": "user", "type": "user"},
        {"id": "d05df1bb-5d8b-4b97-b325-9f2c8edc92e4", "name": "bob", "type": "user"},
    ]
    messages = [{
        "root": {
            "sender": "@switch-mattermost-b69379a6-48c8-4492-9fb6-98f44632e4a4-user:localhost",
            "sender_name": "user",
            "body": "@payments-twokeys-scope rollback payments-api to v2.13.2",
        },
        "replies": [
            {
                "sender": "@switch-agent-70e98deb:localhost",
                "sender_name": "payments-twokeys-scope",
                "body": "**RQ-0001 · NEEDS SECOND KEY** approve RQ-0001",
            },
            {
                "sender": "@switch-mattermost-b69379a6-48c8-4492-9fb6-98f44632e4a4-bob:localhost",
                "sender_name": "bob",
                "body": "approve RQ-0001",
            },
        ],
    }]
    evpath = ev(tmp_path, messages)
    # overwrite with live participant ids
    import json as _json
    _json.dump({"participants": people, "messages": messages}, open(evpath, "w"))
    rc, out = run(tmp_path, capsys, "scope", "--by-id", "d79c4fc0-71fd-459d-a54c-6f5408b4cff9",
                  "--by-name", "user", "rollback payments-api to v2.13.2")
    assert "RQ-0001" in out and "NEEDS SECOND KEY" in out
    rc, out = run(tmp_path, capsys, "execute", "RQ-0001", "--evidence", evpath)
    assert rc == 0 and "EXECUTED" in out and "v2.13.2" in out and "bob" in out


def test_placeholder_state_path_falls_back(tmp_path, monkeypatch, capsys):
    from twokeys import store
    assert "{" not in store.resolve("{state_file}")
    assert store.resolve("{state_file}").endswith("twokeys-shared/state.json")
    assert store.resolve("~/.twokeys/state.json").endswith("twokeys-shared/state.json")


def test_live_agent_cwd_shares_canonical_state(tmp_path, monkeypatch):
    from twokeys import store
    monkeypatch.delenv("TWOKEYS_ISOLATED", raising=False)
    monkeypatch.chdir(tmp_path)
    invented = str(tmp_path / "tmpXYZ" / "state.json")
    assert store.resolve(invented) == invented or store.resolve("{state_file}").endswith("twokeys-shared/state.json")
    agent = tmp_path / "payments-twokeys-hands"
    agent.mkdir()
    monkeypatch.chdir(agent)
    assert store.resolve(invented) == store.resolve("{state_file}")
    assert store.resolve(invented).endswith("twokeys-shared/state.json")


def test_invented_tmp_state_shares_canonical_file(tmp_path, monkeypatch):
    from twokeys import store
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TWOKEYS_ISOLATED", raising=False)
    invented = "/tmp/tmpu27uap71/state.json"
    assert store.resolve(invented) == store.resolve("{state_file}")
    assert store.resolve(invented).endswith("twokeys-shared/state.json")
    monkeypatch.setenv("TWOKEYS_ISOLATED", "1")
    assert store.resolve(invented) == invented
