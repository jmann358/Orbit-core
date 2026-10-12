"""Pre-persistence chat screening; no quarantine service or secret retention.

A positive match is blocked before storage, model context and task routing.
No vault exists here: users must remove sensitive fields and resubmit.
"""
from luna.sensitivity_policy import classify


def screen(text):
    result = classify(text)
    blocked = result["sensitive"]
    return {
        "decision": "block_until_owner_broker" if blocked else "allow",
        "categories": result["categories"],
        "luna_may_receive": not blocked,
        "normal_persistence_allowed": not blocked,
        "payload_retained": False,
        "broker_operational": False,
        "vault_write_performed": False,
        "comprehensive_pii_screening": False,
    }
