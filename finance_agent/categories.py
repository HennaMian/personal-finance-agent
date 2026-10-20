from __future__ import annotations

import re
from typing import Iterable

from .models import Transaction


CATEGORIES = (
    "Income",
    "Food",
    "Transportation",
    "Shopping",
    "Entertainment",
    "Healthcare",
    "Home",
    "Health",
    "Insurance",
    "Utilities",
    "Housing",
    "Transfers",
    "Cash",
    "Other",
)


def categorization_prompt(transactions: Iterable[Transaction]) -> str:
    rows = [
        {
            "id": item.id,
            "date": item.date.isoformat(),
            "description": item.description,
            "amount": float(item.amount),
        }
        for item in transactions
    ]
    return (
        "Categorize each transaction. Return ONLY a JSON object mapping every id "
        "to one allowed category. Do not calculate totals. "
        f"Allowed categories: {list(CATEGORIES)}. Transactions: {rows}"
    )


def clean_json_object(text: str) -> dict[str, object] | None:
    """Decode a JSON object, tolerating a fenced response but no invented syntax."""
    import json

    candidate = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def apply_categories(transactions: list[Transaction], response: str) -> dict[str, object]:
    """Apply only allow-listed model labels; invalid/missing values become Other."""
    parsed = clean_json_object(response) or {}
    accepted = 0
    rejected: list[str] = []
    for item in transactions:
        if item.category:
            continue
        proposed = parsed.get(item.id)
        if isinstance(proposed, str) and proposed in CATEGORIES:
            item.category = proposed
            accepted += 1
        else:
            item.category = "Other"
            rejected.append(item.id)
    return {"accepted": accepted, "rejected_to_other": rejected}
