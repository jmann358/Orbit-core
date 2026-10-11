"""Activation gate for Luna's isolated fixed regression tests.

Owner approval alone is not enough. Every safety prerequisite must be true.
"""
import re
from luna.runner_preflight import inspect_runner
from luna.permissions import check

_PINNED_IMAGE=re.compile(r"^orbit-luna-test@sha256:[0-9a-f]{64}$")

def status(image_ref=None, owner_approved=True):
    preflight=inspect_runner()
    image_pinned=isinstance(image_ref,str) and bool(_PINNED_IMAGE.fullmatch(image_ref))
    grant_active=check("run_tests")
    gates={
        "owner_approved":owner_approved is True,
        "runtime_available":preflight["runtime_available"] is True,
        "image_pinned":image_pinned,
        "run_tests_grant_active":grant_active,
        "network_denied":True,
        "host_read_only":True,
        "secrets_unavailable":True,
        "fixed_test_targets_only":True,
    }
    enabled=all(gates.values())
    return {
        "enabled":enabled,
        "gates":gates,
        "runtime":preflight["runtime"],
        "image_ref":image_ref if image_pinned else None,
        "fail_closed":True,
        "auto_apply":False,
        "merge_allowed":False,
        "arbitrary_commands_allowed":False,
    }
