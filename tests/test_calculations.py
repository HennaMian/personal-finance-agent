from datetime import date
from decimal import Decimal
import unittest

from finance_agent.calculations import compute_totals
from finance_agent.models import Transaction


def tx(identifier: str, amount: str, category: str) -> Transaction:
    return Transaction(identifier, date(2024, 1, 1), identifier, Decimal(amount), category, "test.csv")


class CalculationTests(unittest.TestCase):
    def test_income_expense_refund_and_transfer_rules(self):
        totals, categories = compute_totals(
            [
                tx("pay", "100.00", "Income"),
                tx("food", "-30.00", "Food"),
                tx("refund", "5.00", "Food"),
                tx("transfer", "-40.00", "Transfers"),
                tx("pending", "-0.00", "Shopping"),
            ]
        )
        self.assertEqual(totals, {"income": 100.0, "expenses": 25.0, "net": 75.0, "savings_rate": 0.75})
        self.assertEqual(categories, {"Food": 25.0, "Income": 100.0})


if __name__ == "__main__":
    unittest.main()
