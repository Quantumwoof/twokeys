# WeMakeDevs Flip the Switch: submission draft

Note: the WeMakeDevs page lists the requirements as a public repo, a demo video, and a README that shows how Switch is used. Check the live submit form for any extra fields before submitting.

- **Project name:** TwoKeys
- **Tagline:** ChatOps Requests In, Dual-Control Sign-Off Out
- **Track:** Track 01: Best Business Workflow
- **Team:** Joshua Jubelo (solo) · Independent · GitHub Quantumwoof
- **Repo:** https://github.com/Quantumwoof/twokeys  _(confirm it is public)_
- **Demo video:** _<YouTube/Loom link, under 3 min>_

## Short description (about 60 words)
TwoKeys turns production requests in team chat (rollbacks, flag changes, secret rotations, replays) into dual-control changes inside a Switch room. A scope agent restates the ask, scores its risk and opens RQ-nnnn. Nothing runs until a *different person* approves in the room. The hands agent verifies that approval from Switch's own participant data, runs it in a sandbox and writes the audit ledger.

## Longer description
On-call engineers get asked to change production from chat, and agents now make that a one-message action. NIST SP 800-53 CM-3(1) says to "prohibit changes to the system until designated approvals are received". TwoKeys enforces that in Switch. One template creates two Codex agents (scope, hands), a Mattermost-bridged room with exclusive `scope`/`hands` roles, and a policy document. A deterministic Python gate decides; the models only propose. Approvals count only if Switch reports the decider as a user (not an agent), who is not the requester and is not speaking on someone's behalf. On 20 seeded requests TwoKeys blocked 14/14 with 0 false executions and completed 6/6. A bot that executes immediately ran 12 requests it should have refused and made 17 changes with no second person.

## How Switch is used
Template → agents + room + roles + room doc + kickoff; Mattermost bridge; `list_participants` and `read_context` as the source of truth for who asked and who approved; `create_room_document`/`update_room_document` for the `twokeys-ledger` audit table. Without Switch the gate has no trusted identities and refuses everything.

## Built with
Switch (rooms, Console, templates, agent operations), Mattermost, Codex CLI, Python 3 (standard library only), pytest.

## How to run
```
git clone https://github.com/Quantumwoof/twokeys && cd twokeys
pip install pytest pyyaml && pytest -q && python -m twokeys.eval && python -m twokeys demo
```
Live: Switch Console → Templates → `switch/twokeys.template.yaml` (see the README, "How to run").
