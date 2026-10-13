"""Read-only financial planning core. No financial accounts, payments or spending."""
from __future__ import annotations
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

DIRECTIVE = Path(__file__).resolve().parents[1] / "docs" / "FINANCIAL_DIRECTIVE_V1.json"

def load_directive(path: Path = DIRECTIVE) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != "1.0.0":
        raise ValueError("Unsupported financial directive version")
    if data.get("safeguards", {}).get("no_unapproved_spending") is not True:
        raise ValueError("Missing mandatory spending restriction")
    return data

@dataclass(frozen=True)
class Opportunity:
    name: str
    estimated_revenue: Decimal
    estimated_cost: Decimal
    confidence: Decimal
    notes: str = ""

    def evaluate(self) -> dict[str, str]:
        if not self.name.strip():
            raise ValueError("Opportunity name required")
        if self.estimated_revenue < 0 or self.estimated_cost < 0:
            raise ValueError("Negative estimates are invalid")
        if not Decimal("0") <= self.confidence <= Decimal("1"):
            raise ValueError("Confidence must be between 0 and 1")
        expected_revenue = self.estimated_revenue * self.confidence
        expected_net = expected_revenue - self.estimated_cost
        return {
            "name": self.name,
            "estimated_net": str(self.estimated_revenue - self.estimated_cost),
            "confidence_adjusted_net": str(expected_net),
            "status": "proposal_only",
            "notes": self.notes,
        }

def financial_snapshot(revenue: Decimal, expenses: Decimal, reserve: Decimal) -> dict[str, str]:
    if min(revenue, expenses, reserve) < 0:
        raise ValueError("Amounts must not be negative")
    net = revenue - expenses
    return {"revenue": str(revenue), "expenses": str(expenses),
            "net": str(net), "reserve": str(reserve),
            "owner_payout": "not_authorized",
            "spending_authority": "none"}

def spending_decision(amount: Decimal) -> dict[str, str]:
    """Every spending request stays pending until separately authorized."""
    if amount < 0:
        raise ValueError("Amount must not be negative")
    return {"amount": str(amount), "decision": "requires_owner_approval"}
