# Judge-level self-review (written 6 Nov 2026)

## Against the four Switch criteria

**Use of Switch: strong, with one honest gap.** Switch is in the critical path. The decision only counts as Switch reports it (participant `type`, `sender`, `on_behalf_of`, `read_context`), and the ledger is a Switch room document. The template uses agents, room, bridge, exclusive roles, room doc, instructions and kickoff, and it passes Switch's own `lint_template` (run against the cloned `sandbox-quantum/switch` core). *Gap:* the Codex hands agent relays the Switch evidence to the gate, so the identity check trusts that relay. A native protocol client would close this. *Gap:* Switch Tasks/Decisions are not used, because the protocol docs mark tasks "present but not ready for use".

**Technical execution: strong offline, unproven live.** It has a zero-dependency package, 29 tests (policy, gate, eval counts asserted, CLI end-to-end, template lint) and CI. *Not yet shown:* a live run on Switch + Mattermost. The template has never been run by a real Console, and Codex's exact use of `read_context` output (field names) is handled tolerantly (`body|content|text`, `sender|sender_id|user_id`) but has not been observed.

**Creativity and impact: good.** It targets a regulated, professional user with a cited control (NIST CM-3(1), AC-5), and it is clearly not the landing-page incident bot. It is a control layer usable by any agent. A risk is that judges may see "approval bot" as simple; the counter is the social-engineering cases and the Switch-identity verification.

**Presentation: good on paper.** The README follows the rubric (Problem / Solution / Users / Why different / Results / Limits / How Switch is used / How to run / Demo / Judging map), with a mermaid diagram and eval table. Whether it lands depends on the video.

## Against the winners playbook
- [x] Professional, high-stakes user in one sentence
- [x] Real cited source with fetched URLs (csf.tools NIST CM-3, AC-5; CSRC landing page)
- [x] Before → after tagline, under 20 words
- [x] Seeded eval with counts and a baseline (14/14 vs 2/14; 0 vs 12 false executions)
- [x] Sponsor tech in the critical path, steps named
- [x] Fail-closed / human-in-the-loop as the feature
- [x] Limits after results
- [ ] Live public URL: not applicable (local Switch). The repo plus video stand in.
- [ ] Video recorded with live Switch

## Still to do for the parent (in order)
1. Push the repo public (done if the report says so) and add the video link to the README and SUBMISSION.
2. Start Docker (see the report for the commands on this box), install Switch Console, choose a local server with Mattermost.
3. Run the template and create the second Mattermost user. Do one rehearsal; if `twokeys` isn't on the agents' path, check that Console cloned `repo:` into each agent directory.
4. Record per `docs/DEMO_SCRIPT.md`. If a step breaks live, fix the instructions, not the gate.
5. Submit on the WeMakeDevs form before **Sat 7 Nov, 7:29 PM WAT**.

Weakest spots if judged today: no live footage yet; the Codex-relayed evidence; the regex parser.
