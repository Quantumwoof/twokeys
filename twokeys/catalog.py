"""Seeded service catalog. Fictional company "Acme Pay"; no real systems."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Service:
    name: str
    owner: str
    data_class: str  # "payments" | "pii" | "none"
    dual_control: bool
    no_touch: bool = False  # destructive actions are never allowed from chat
    aliases: tuple = field(default_factory=tuple)


CATALOG = {
    s.name: s
    for s in [
        Service("payments-api", "@payments-oncall", "payments", True, aliases=("payments", "payment api")),
        Service("ledger-db", "@ledger-team", "payments", True, no_touch=True, aliases=("ledger",)),
        Service("checkout-web", "@web-team", "pii", True, aliases=("checkout",)),
        Service("webhooks-gw", "@integrations", "payments", True, aliases=("webhooks", "webhook gateway")),
        Service("kyc-service", "@identity", "pii", True, no_touch=True, aliases=("kyc",)),
        Service("status-page", "@sre", "none", False, aliases=("status",)),
        Service("docs-site", "@devrel", "none", False, aliases=("docs",)),
    ]
}


def lookup(text: str):
    """Return the list of services a free-text mention could refer to."""
    t = text.lower()
    hits = [s for s in CATALOG.values() if s.name in t]
    if hits:
        return hits
    return [s for s in CATALOG.values() if any(a in t for a in s.aliases)]
