from decimal import Decimal
from pathlib import Path
import json
import pytest
from luna.financial import load_directive, Opportunity, financial_snapshot, spending_decision

def test_directive_is_loaded():
    assert load_directive()["capital"]["initial_budget_usd"] == 0

def test_reject_unsafe_directive(tmp_path):
    path = tmp_path / "directive.json"
    path.write_text(json.dumps({"version": "1.0.0", "safeguards": {"no_unapproved_spending": False}}))
    with pytest.raises(ValueError):
        load_directive(path)

def test_opportunity_is_only_proposal():
    result = Opportunity("Sample", Decimal("100"), Decimal("20"), Decimal("0.5")).evaluate()
    assert result["confidence_adjusted_net"] == "30.0"
    assert result["status"] == "proposal_only"

def test_invalid_confidence():
    with pytest.raises(ValueError):
        Opportunity("X", Decimal("10"), Decimal("1"), Decimal("1.1")).evaluate()

def test_snapshot_and_spending_gate():
    assert financial_snapshot(Decimal("100"), Decimal("40"), Decimal("10"))["net"] == "60"
    assert spending_decision(Decimal("1"))["decision"] == "requires_owner_approval"
