"""Schema-only contract for the future owner-only quarantine service.

No encryption, storage, decryption, or payload handling is implemented here.
"""
import re

RECEIPT=re.compile(r"^q_[A-Za-z0-9_-]{16,80}$")
STATUSES=frozenset({"quarantined","preserved","deleted","released_sanitized","expired"})
OWNER_ACTIONS=frozenset({"preserve","delete","release_sanitized","create_rule"})
SOURCE_KINDS=frozenset({"chat","document","connector","tool_output","manual"})

def luna_receipt(receipt_id,status="quarantined"):
    if not isinstance(receipt_id,str) or not RECEIPT.fullmatch(receipt_id):
        raise ValueError("Invalid opaque quarantine receipt")
    if status not in STATUSES:
        raise ValueError("Invalid quarantine status")
    return {
        "schema_version":1,
        "receipt_id":receipt_id,
        "status":status,
        "payload_included":False,
        "preview_included":False,
        "fingerprint_included":False,
        "decryption_available":False,
        "owner_review_required":status=="quarantined",
    }

def owner_record(receipt_id,categories,source_kind):
    if not isinstance(receipt_id,str) or not RECEIPT.fullmatch(receipt_id):
        raise ValueError("Invalid opaque quarantine receipt")
    if source_kind not in SOURCE_KINDS:
        raise ValueError("Invalid source kind")
    if not isinstance(categories,(list,tuple)) or not categories:
        raise ValueError("At least one category is required")
    clean=[]
    for category in categories:
        if not isinstance(category,str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}",category):
            raise ValueError("Invalid category token")
        clean.append(category)
    return {
        "schema_version":1,
        "receipt_id":receipt_id,
        "categories":sorted(set(clean)),
        "source_kind":source_kind,
        "allowed_owner_actions":sorted(OWNER_ACTIONS),
        "payload_included":False,
        "credential_fingerprint_included":False,
        "luna_queryable":False,
        "luna_mutable":False,
    }
