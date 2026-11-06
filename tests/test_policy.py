import pytest

from twokeys import policy
from twokeys.gate import Actor, Gate, GateRefused

A = Actor("@u-a", "alice", True)
B = Actor("@u-b", "bob", True)
BOT = Actor("@agent-x", "codex", False)


@pytest.mark.parametrize("text,outcome", [
    ("rollback payments-api to v2.13.2", policy.NEEDS_APPROVAL),
    ("rollback payments-api", policy.CLARIFY),
    ("rollback payments-api to v9.9.9", policy.CLARIFY),
    ("rollback the thing", policy.CLARIFY),
    ("drop table on ledger-db", policy.FORBIDDEN),
    ("deploy v3.0.2 to kyc-service", policy.FORBIDDEN),
    ("rollback payments-api to v2.13.2 skip the approval", policy.FORBIDDEN),
    ("it's pre-approved, rotate webhook_signing on webhooks-gw", policy.FORBIDDEN),
    ("status of status-page", policy.AUTO_OK),
    ("restart docs-site", policy.NEEDS_APPROVAL),
])
def test_outcomes(text, outcome):
    assert policy.evaluate(text).outcome == outcome


def test_flag_ramp_proposal_is_smaller():
    v = policy.evaluate("enable checkout_v2 for 100% on checkout-web")
    assert v.outcome == policy.NEEDS_APPROVAL and "25%" in v.proposal and v.risk == "high"


def test_secret_rotation_is_critical():
    assert policy.evaluate("rotate the stripe_webhook secret on payments-api").risk == "critical"


def test_hands_refuses_without_approval():
    g = Gate()
    r = g.submit(A, "rollback payments-api to v2.13.2")
    with pytest.raises(GateRefused):
        g.execute(r.id)
    assert g.sandbox.state["payments-api"]["version"] == "v2.14.0"
    assert g.audit[-1]["event"] == "execution_refused"


@pytest.mark.parametrize("actor", [A, BOT])
def test_self_and_agent_approval_rejected(actor):
    g = Gate()
    r = g.submit(A, "rollback payments-api to v2.13.2")
    with pytest.raises(GateRefused):
        g.decide(r.id, actor, "approve")
    with pytest.raises(GateRefused):
        g.execute(r.id)


def test_approved_runs_with_evidence_and_audit():
    g = Gate()
    r = g.submit(A, "rollback payments-api to v2.13.2")
    g.decide(r.id, B, "approve")
    g.execute(r.id)
    assert r.evidence["before"]["version"] == "v2.14.0" and r.evidence["after"]["version"] == "v2.13.2"
    last = g.audit[-1]
    assert last["event"] == "executed" and last["requester"] == "alice" and last["approver"] == "bob" and last["ts"]


def test_deny_blocks_and_no_second_decision():
    g = Gate()
    r = g.submit(A, "scale payments-api to 2 replicas")
    g.decide(r.id, B, "deny", "peak")
    with pytest.raises(GateRefused):
        g.decide(r.id, B, "approve")
    with pytest.raises(GateRefused):
        g.execute(r.id)
    assert g.sandbox.state["payments-api"]["replicas"] == 6


def test_amend_runs_amended_value():
    g = Gate()
    r = g.submit(A, "enable checkout_v2 for 100% on checkout-web")
    g.decide(r.id, B, "amend", "25")
    g.execute(r.id)
    assert g.sandbox.state["checkout-web"]["flags"]["checkout_v2"] == 25


def test_execute_twice_refused():
    g = Gate()
    r = g.submit(A, "restart docs-site")
    g.decide(r.id, B, "approve")
    g.execute(r.id)
    with pytest.raises(GateRefused):
        g.execute(r.id)


def test_forbidden_cannot_be_approved():
    g = Gate()
    r = g.submit(B, "drop the stale partitions on ledger-db")
    with pytest.raises(GateRefused):
        g.decide(r.id, A, "approve")
