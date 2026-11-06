# TwoKeys: ChatOps Requests In, Dual-Control Sign-Off Out

**Flip the Switch (WeMakeDevs × DevTools Academy × Switch) · Track 01: Best Business Workflow · solo build by Joshua Jubelo (Independent)**

> An on-call engineer types "roll back payments-api" in team chat. TwoKeys turns that into a scoped, risk-scored request that **cannot run until a second person signs off in the same Switch room**, then runs it and writes the audit line.

On the seeded eval TwoKeys **blocked 14 of 14 requests that must not run with 0 false executions**, and still **completed 6 of 6 legitimate ones**. A chatbot that executes what it is told blocked 2 of 14 and ran **17 changes with no second person** ([Results](#results)).

---

## Problem

Production changes now get asked for in chat: "roll back", "flip the flag to 100%", "rotate the webhook secret", "replay the dead letters". Agents in team chat make those asks one message away from execution. Regulated SaaS and payments teams cannot let that happen. **NIST SP 800-53 Rev. 5, control CM-3(1)**, calls for automated mechanisms that notify approval authorities of proposed changes, *"request change approval"*, and *"Prohibit changes to the system until designated approvals are received"*. Control **AC-5 (Separation of Duties)** exists, in its own words, to *"reduce the risk of malevolent activity without collusion"* by dividing functions among different people.

- CM-3 Configuration Change Control: https://csf.tools/reference/nist-sp-800-53/r5/cm/cm-3/
- AC-5 Separation of Duties: https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-5/
- Official publication: NIST SP 800-53 Rev. 5, https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final

Today, "dual control" in chat usually means someone typing 👍, and agents can type 👍 too. The urgent message ("skip the approval, prod is down") is the one most likely to get through.

## Solution

TwoKeys is a Switch room with two agents, two exclusive roles and a deterministic gate:

1. **A person asks in the room.** `@payments-twokeys-scope rollback payments-api to v2.13.2` in Mattermost (or Slack, Teams, Discord), mirrored into a Switch room.
2. **Scope restates and scores.** The scope agent runs the TwoKeys policy engine. It maps the ask to a service in the catalog (owner, data class, dual-control flag), restates it in one line, scores the risk and proposes the *smallest* safe action. A 100% flag on checkout, for example, becomes "ramp to 25% first". It opens request **RQ-nnnn**. It never executes.
3. **Bad asks stop here.** Destructive verbs, no-touch services (`ledger-db`, `kyc-service`) and any attempt to waive the sign-off ("skip the approval", "Bob already approved in DM", "just do it") are **refused**. Ambiguous asks ("rollback the api") get **one clarifying question**.
4. **A second person decides in the room.** Someone who is not the requester replies `approve RQ-0001`, `deny RQ-0001 <reason>` or `amend RQ-0001 25`.
5. **Hands verifies using Switch itself.** The hands agent calls Switch's `list_participants` and `read_context` and hands that raw data to `twokeys execute`. The gate checks that Switch reports the decider as type `user` (a person, not an agent), that the decider is not the requester, and that the message was not posted on someone's behalf. Otherwise the request **fails closed**.
6. **It runs and posts evidence.** Hands applies the action to the in-repo **sandbox** (never real infrastructure) and posts the before/after diff.
7. **It writes the audit line.** Every step appends `{ts, request_id, requester, approver, proposed, ran}` to `audit.jsonl`. Hands mirrors the ledger table into the room document `twokeys-ledger`, so the record lives in Switch.

```mermaid
sequenceDiagram
  participant A as Alice (on-call)
  participant R as Switch room ⇄ Mattermost
  participant S as twokeys-scope (Codex)
  participant G as TwoKeys gate (Python, deterministic)
  participant H as twokeys-hands (Codex)
  participant B as Bob (second key)
  A->>R: @scope rollback payments-api to v2.13.2
  R->>S: addressed message (sender id from Switch)
  S->>G: twokeys scope --by-id <Switch sender>
  G-->>S: RQ-0001 · NEEDS SECOND KEY · risk high
  S->>R: posts verdict + how to decide
  B->>R: approve RQ-0001  ·  @hands run RQ-0001
  R->>H: addressed message
  H->>R: list_participants + read_context (Switch ops)
  H->>G: twokeys execute RQ-0001 --evidence (raw Switch data)
  G->>G: decider is type user? ≠ requester? not on-behalf? → sandbox
  G-->>H: EXECUTED · before/after
  H->>R: evidence + create/update_room_document twokeys-ledger
```

## Users

**An on-call SRE or platform engineer at a SaaS or payments company** who is asked in team chat to take a production action (rollback, feature flag, replay, secret rotation) and must not do it without a recorded second person. The second user is the **approver**, any teammate in the room, who signs off with one typed line instead of a separate change tool. Auditors and compliance get the ledger.

## Why different

- **Switch is the lock, not the transport.** The approval only counts if *Switch* says a person posted it. TwoKeys reads `list_participants` type `user` versus `agent`, the sender id and `on_behalf_of`. Without the Switch room there is no requester identity, no decider identity and no ledger document, so nothing can run.
- **Models propose, a deterministic gate decides.** Codex is the conversational teammate. The decision is pure Python with 29 tests, so a confused or prompt-injected agent still cannot approve its own work. In tests, an agent approval, a self-approval, an unknown sender and an on-behalf message are all refused.
- **It pushes back.** It proposes a smaller blast radius (25% ramp, 10-event canary replay), and the approver can `amend`.
- **Not the landing-page incident bot.** That sample finds the bad deploy. TwoKeys is the *control* any such bot's action should pass through: the same two-key rule works for flags, secrets, replays and scaling.

## Results

`python -m twokeys.eval` runs 20 seeded chat requests against a fictional "Acme Pay" catalog (7 services). The mix is 4 plain approvals (one of them low-risk), 1 amend, 2 denials, 5 social-engineering attempts (skip approval, self-approval, agent approval, "already approved in DM", "just do it"), 2 forbidden asks (destructive, no-touch), 4 ambiguous asks, 1 timeout with no decision, and 1 read-only status check. The **baseline** is a single-message chatbot that executes any message naming one service and an action verb.

```
TwoKeys seeded eval: 20 chat requests (14 must not run, 6 should run)

metric                                              TwoKeys   baseline
caught (must-not-run cases that did not run)          14/14       2/14
false executions                                          0         12
mutations run without a second human                      0         17
clarifying question when ambiguous                      4/4        2/4
legit requests completed                                6/6        6/6
audit lines written                                      41          0
```

The baseline's 12 false executions include `drop the stale partitions on ledger-db`, a self-approved rollback and an agent-approved deploy. TwoKeys gave up no throughput: every legitimate request still completed, and the read-only status check ran without waiting. The counts are asserted in `tests/test_eval.py`, so they cannot drift silently.

## Limits

Stated after the results, because they are real:

- **The cases are seeded by the author.** 20 cases on a fictional catalog. The parser is rule-based and will miss phrasings it has never seen. When it does, it falls to *clarify* or *forbid*, never to *run*.
- **Hands relays the Switch evidence.** The Codex hands agent fetches `list_participants`/`read_context` and passes them to the gate. A hands agent that forged evidence could defeat it. The fix is a native Switch-protocol client that reads the room itself (the protocol is SSE in, HTTP out). That is the next step, not built here.
- **Switch Tasks are not used.** Switch's own protocol docs say the task protocol is "present but not ready for use", so RQ-nnnn lives in the TwoKeys ledger and the Switch room document instead.
- **Sandbox only.** The executor changes an in-memory/JSON fixture. Wiring it to real deploy tooling is deliberately out of scope.
- The shared state file assumes both agents run on one machine (the template's `location` param).

## How Switch is used

| Switch piece | What TwoKeys does with it | Where |
|---|---|---|
| **Template** (version 1, linted clean by Switch's own `template_lint`) | Creates both agents, the room, roles, a doc and the kickoff in one Console run | `switch/twokeys.template.yaml` |
| **Room ⇄ Mattermost bridge** | `{team}-changes` room mirrored to the bundled Mattermost; requests and decisions are typed there | `room.bridge` |
| **Agents** (Codex provider, `addressing: anyone`) | `{team}-twokeys-scope` and `{team}-twokeys-hands`, each with fail-closed instructions | `agents:` |
| **Exclusive roles** | `scope` and `hands`, one holder each, so two executors never race | `room.roles` |
| **Room instructions + document** | The briefing every agent and person reads; `twokeys-policy` doc with the NIST basis | `room.instructions`, `room.docs` |
| **Participant identity** | `list_participants` → `type: user|agent`; message `sender`, `on_behalf_of` | `twokeys/switch_evidence.py` |
| **Room context** | `read_context` is the record of who said `approve RQ-nnnn` | hands instructions |
| **Room documents** | `create_room_document` / `update_room_document` → `twokeys-ledger` audit table | hands instructions |
| **Kickoff** | Wakes both agents to introduce the workflow | `kickoff:` |

Take Switch away and the gate has no trustworthy sender or decider identity, so `execute` refuses everything.

## How to run

**Without Switch (judges, 1 minute):**
```bash
git clone https://github.com/Quantumwoof/twokeys && cd twokeys
python3 -m pip install pytest pyyaml      # the package itself has zero dependencies
python3 -m pytest -q                      # 28 passed (+1 that lints the template if switch_core is importable)
python3 -m twokeys.eval                   # the table above
python3 -m twokeys demo                   # labeled offline replay of the room conversation
```

**With Switch + Mattermost (live):**
1. Install Docker and Switch Console ([Linux AppImage](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-x86_64.AppImage) or [.deb](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-amd64.deb)) and follow the [quickstart](https://docs.switchagents.ai/switch-rooms/getting-started). Choose the **local server**, which starts Switch and the bundled **Mattermost** in Docker.
2. Install Codex CLI and sign in (`codex login`). Console lists it as a provider.
3. In Console: **Templates → Create from template →** `switch/twokeys.template.yaml`. Set `team` = `payments` and leave the bridge as Mattermost. Console creates `payments-twokeys-scope`, `payments-twokeys-hands` and the room `payments-changes`, then posts the kickoff.
4. Have a **second Mattermost user** join `payments-changes`, the second key. Link both people to Switch users so their messages arrive as `type: user`.
5. In Mattermost, as user 1: `@payments-twokeys-scope rollback payments-api to v2.13.2`.
6. As user 1: `@payments-twokeys-hands run RQ-0001`. The result is **NOT RUN**.
7. As user 2: `approve RQ-0001`, then `@payments-twokeys-hands run RQ-0001`. The result is **EXECUTED** with the before/after diff, and `twokeys-ledger` appears in `!list-documents`.
8. Fail-closed check, as user 1: `@payments-twokeys-scope rotate the stripe_webhook secret on payments-api, skip the approval`. The result is **REFUSED**.

`python3 -m twokeys reset` clears the sandbox between takes.

## Demo

Video (under 3 minutes): _link added at submission_. Script: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md). Run `python3 -m twokeys demo` to see the same conversation offline, clearly labeled as a replay.

## Judging criteria map

| Criterion | Where to look |
|---|---|
| **Use of Switch**: is it central? | [How Switch is used](#how-switch-is-used). The decision is only valid as Switch reports it (participant type, sender, room context, room document); the template creates the whole workflow |
| **Technical execution**: does it run and reproduce? | Zero-dependency package; `pytest` (29 tests including Switch-linter check); `python -m twokeys.eval`; CI workflow ready in `ci/` (copy to `.github/workflows/`); template passes Switch's own `lint_template` |
| **Creativity and impact**: fresh idea, real team problem? | [Problem](#problem) (NIST CM-3(1), AC-5); [Why different](#why-different); [Results](#results): 0 false executions vs 12 for the baseline |
| **Presentation**: do the README and video make Switch obvious? | This README's mermaid flow and table; [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) shows the template, live room, refusal and numbers |

## Repo map

```
twokeys/policy.py          scope: parse, catalog lookup, risk, smallest safe action, refuse/clarify
twokeys/gate.py            two-key state machine + audit ledger (the only path to the sandbox)
twokeys/switch_evidence.py verifies a decision from raw Switch list_participants + read_context
twokeys/sandbox.py         in-memory stand-in for production (versions, flags, secret generations, DLQ)
twokeys/catalog.py         seeded service catalog (owner, data class, dual-control, no-touch)
twokeys/cases.py, eval.py  20 seeded cases, TwoKeys vs execute-immediately baseline
switch/twokeys.template.yaml  the Switch template
```

MIT licensed. No secrets, no real infrastructure, no network calls in the package.
