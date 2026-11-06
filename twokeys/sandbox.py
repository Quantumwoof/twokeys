"""In-memory sandbox standing in for production. Never touches real systems."""
import copy

SEED = {
    "payments-api": {"version": "v2.14.0", "history": ["v2.12.0", "v2.13.1", "v2.13.2", "v2.14.0"],
                     "flags": {"retry_v2": 0}, "secrets": {"stripe_webhook": "gen-7"}, "replicas": 6},
    "ledger-db": {"version": "pg-15.4", "history": ["pg-15.4"], "flags": {}, "secrets": {"db_password": "gen-3"}, "replicas": 3},
    "checkout-web": {"version": "v5.2.0", "history": ["v5.1.3", "v5.2.0"], "flags": {"checkout_v2": 5},
                     "secrets": {}, "replicas": 8},
    "webhooks-gw": {"version": "v1.9.1", "history": ["v1.9.0", "v1.9.1"], "flags": {},
                    "secrets": {"webhook_signing": "gen-12"}, "replicas": 4, "dlq": 37},
    "kyc-service": {"version": "v3.0.2", "history": ["v3.0.2"], "flags": {}, "secrets": {}, "replicas": 2},
    "status-page": {"version": "v0.8.0", "history": ["v0.7.9", "v0.8.0"], "flags": {"banner": 0}, "secrets": {}, "replicas": 1},
    "docs-site": {"version": "v12", "history": ["v11", "v12"], "flags": {}, "secrets": {}, "replicas": 1},
}


class Sandbox:
    def __init__(self, state=None):
        self.state = copy.deepcopy(state or SEED)

    def snapshot(self, service):
        s = copy.deepcopy(self.state[service])
        # Never echo secret material, only its generation label.
        return s

    def apply(self, action):
        svc = self.state[action.service]
        before = self.snapshot(action.service)
        k = action.kind
        if k == "status":
            pass
        elif k in ("rollback", "deploy"):
            if action.target not in svc["history"]:
                raise ValueError(f"{action.target} not in release history of {action.service}")
            svc["version"] = action.target
        elif k == "flag":
            svc["flags"][action.target] = action.value
        elif k == "rotate":
            gen = int(svc["secrets"][action.target].split("-")[1]) + 1
            svc["secrets"][action.target] = f"gen-{gen}"
        elif k == "replay":
            n = min(action.value, svc.get("dlq", 0))
            svc["dlq"] = svc.get("dlq", 0) - n
        elif k == "restart":
            pass
        elif k == "scale":
            svc["replicas"] = action.value
        else:
            raise ValueError(f"sandbox refuses unknown action {k}")
        return before, self.snapshot(action.service)
