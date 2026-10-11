"""Pre-Luna sensitive intake gate.

Until an independent owner-only quarantine broker exists, sensitive-looking payloads
are blocked before normal chat persistence or model context. This module does not
store, hash, preview, or forward the payload.
"""
from luna.sensitivity_policy import classify

def screen(text):
    result=classify(text)
    if result["sensitive"]:
        return {
            "decision":"block_until_owner_broker",
            "categories":list(result["categories"]),
            "luna_may_receive":False,
            "normal_persistence_allowed":False,
            "payload_retained":False,
            "broker_operational":False,
            "vault_write_performed":False,
        }
    return {
        "decision":"allow",
        "categories":[],
        "luna_may_receive":True,
        "normal_persistence_allowed":True,
        "payload_retained":False,
        "broker_operational":False,
        "vault_write_performed":False,
    }
