import pytest
from luna.watchdog_events import event


def test_watchdog_event_contains_metadata_only():
    item=event(event_type="access_denied",target_category="vault",
               reason="denied_by_policy")
    assert item["payload_included"] is False
    assert item["owner_only_destination_required"] is True
    assert item["luna_queryable"] is False
    assert item["luna_mutable"] is False


@pytest.mark.parametrize("field,value",[
    ("event_type","password: example"),
    ("target_category","/private/vault"),
    ("reason","Bearer exampletokenvalue"),
])
def test_rejects_freeform_or_secret_like_fields(field,value):
    args={"event_type":"access_denied","target_category":"vault",
          "reason":"denied_by_policy"}
    args[field]=value
    with pytest.raises(ValueError):
        event(**args)


def test_rejects_unknown_metadata_even_when_well_formed():
    with pytest.raises(ValueError):
        event(event_type="access_denied",target_category="vault",
              reason="owner_secret")
