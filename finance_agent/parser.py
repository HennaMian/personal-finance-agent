from __future__ import annotations

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .models import Transaction


FILES = ("bank_statement.csv", "transactions_uncategorized.csv", "expenses.csv", "income.csv")


def parse_date(value: str):
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported date: {value!r}")


def _default_category(filename: str, row: dict[str, str]) -> str | None:
    explicit = (row.get("Category") or "").strip()
    if explicit:
        return explicit
    if filename == "income.csv":
        return "Income"
    if filename == "bank_statement.csv":
        # The bank export has no semantic labels. Credits are safely income only
        # when they are not transfers/refunds; debits must still be categorized.
        desc = row["Description"].upper()
        if row.get("Type") == "Credit" and "REFUND" not in desc and "TRANSFER" not in desc:
            return "Income"
    return None


def load_file(path: Path) -> list[Transaction]:
    transactions: list[Transaction] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"Date", "Description", "Amount"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path.name}: missing required columns {sorted(required)}")
        for line, row in enumerate(reader, start=2):
            try:
                amount = Decimal(row["Amount"].strip()).quantize(Decimal("0.01"))
            except (InvalidOperation, AttributeError) as exc:
                raise ValueError(f"{path.name}:{line}: invalid amount") from exc
            transactions.append(
                Transaction(
                    id=f"{path.stem}:{line}",
                    date=parse_date(row["Date"]),
                    description=" ".join(row["Description"].split()),
                    amount=amount,
                    category=_default_category(path.name, row),
                    source=path.name,
                    raw=row,
                )
            )
    return transactions


def _merchant_tokens(description: str) -> set[str]:
    ignored = {"PAYMENT", "PURCHASE", "DEPOSIT", "FEE", "STORE", "SUBSCRIPTION"}
    tokens = set(re.findall(r"[A-Z]{3,}", description.upper()))
    return tokens - ignored


def _overlaps(candidate: Transaction, existing: Transaction) -> bool:
    if candidate.amount != existing.amount or abs((candidate.date - existing.date).days) > 1:
        return False
    left, right = _merchant_tokens(candidate.description), _merchant_tokens(existing.description)
    if not left or not right:
        return False
    # A shared meaningful merchant token handles posting-date drift and mild
    # bank noise ("Freelance Work" vs "Freelance Payment").
    return bool(left & right)


def load_and_reconcile(data_dir: Path) -> tuple[list[Transaction], dict[str, object]]:
    """Load every file, then make a canonical ledger with documented precedence.

    Bank rows win, then uncategorized/card rows, then clean expenses and income.
    A later row is an overlap only when amount matches, dates are within one day,
    and a meaningful merchant token matches. Rows inside the same file are never
    collapsed, preserving the deliberate repeated Whole Foods charge.
    """
    missing = [name for name in FILES if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing required files: {', '.join(missing)}")

    loaded = {name: load_file(data_dir / name) for name in FILES}
    ledger: list[Transaction] = []
    dropped: list[dict[str, str]] = []
    for filename in FILES:
        prior_sources = [item for item in ledger if item.source != filename]
        for candidate in loaded[filename]:
            match = next((item for item in prior_sources if _overlaps(candidate, item)), None)
            if match:
                # Retain an explicit category from a lower-priority clean export.
                if not match.category and candidate.category:
                    match.category = candidate.category
                dropped.append({"dropped": candidate.id, "kept": match.id})
            else:
                ledger.append(candidate)
    ledger.sort(key=lambda item: (item.date, item.source, item.id))
    return ledger, {
        "raw_rows": sum(len(items) for items in loaded.values()),
        "canonical_rows": len(ledger),
        "overlaps_removed": len(dropped),
        "overlap_examples": dropped[:5],
    }
