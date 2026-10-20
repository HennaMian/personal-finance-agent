from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from .models import Transaction


CENT = Decimal("0.01")
RATE = Decimal("0.0001")


def _money(value: Decimal) -> float:
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))


def compute_totals(transactions: list[Transaction]) -> tuple[dict[str, float], dict[str, float]]:
    """Compute all report numbers without accepting any model-provided number."""
    income = Decimal("0")
    expenses = Decimal("0")
    category_totals: defaultdict[str, Decimal] = defaultdict(Decimal)

    for item in transactions:
        category = item.category or "Other"
        if category == "Transfers" or item.amount == 0:
            continue
        if item.amount > 0:
            if category == "Income":
                income += item.amount
                category_totals[category] += item.amount
            else:
                # Positive non-income values are refunds and reduce that category.
                expenses -= item.amount
                category_totals[category] -= item.amount
        else:
            spend = -item.amount
            expenses += spend
            category_totals[category] += spend

    net = income - expenses
    savings_rate = (net / income) if income else Decimal("0")
    totals = {
        "income": _money(income),
        "expenses": _money(expenses),
        "net": _money(net),
        "savings_rate": float(savings_rate.quantize(RATE, rounding=ROUND_HALF_UP)),
    }
    by_category = {name: _money(value) for name, value in sorted(category_totals.items())}
    return totals, by_category


def find_flags(transactions: list[Transaction]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    seen: dict[tuple[str, Decimal], Transaction] = {}
    for item in transactions:
        normalized = " ".join(item.description.upper().split())
        key = (normalized, item.amount)
        if key in seen:
            first = seen[key]
            flags.append(
                {
                    "description": item.description,
                    "reason": f"possible duplicate of {first.date.isoformat()} with the same merchant and amount",
                }
            )
        else:
            seen[key] = item
        if item.amount == 0:
            flags.append({"description": item.description, "reason": "zero-amount pending authorization excluded from totals"})
    return flags


def build_summary(totals: dict[str, float], by_category: dict[str, float]) -> str:
    spending = [(name, value) for name, value in by_category.items() if name != "Income"]
    top_name, top_value = max(spending, key=lambda pair: pair[1], default=("None", 0.0))
    return (
        f"Income was ${totals['income']:,.2f} and net expenses were ${totals['expenses']:,.2f}, "
        f"leaving ${totals['net']:,.2f} net ({totals['savings_rate']:.1%} savings rate). "
        f"The largest spending category was {top_name} at ${top_value:,.2f}."
    )
