from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Transaction:
    id: str
    date: date
    description: str
    amount: Decimal
    category: str | None
    source: str
    raw: dict[str, str] = field(repr=False, default_factory=dict)

    def public_dict(self) -> dict[str, object]:
        return {
            "source_id": self.id,
            "source": self.source,
            "date": self.date.isoformat(),
            "description": self.description,
            "amount": float(self.amount),
            "category": self.category or "Other",
        }
