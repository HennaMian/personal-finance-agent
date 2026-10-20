from pathlib import Path
import unittest

from finance_agent.parser import load_and_reconcile, parse_date


class ParserTests(unittest.TestCase):
    def test_mixed_dates_are_normalized(self):
        self.assertEqual(parse_date("2024-1-6").isoformat(), "2024-01-06")
        self.assertEqual(parse_date("01/03/2024").isoformat(), "2024-01-03")

    def test_all_four_files_are_loaded_and_overlaps_are_reconciled(self):
        rows, metadata = load_and_reconcile(Path("sample_data"))
        self.assertEqual(metadata["raw_rows"], 69)
        self.assertEqual(metadata["canonical_rows"], 48)
        self.assertEqual(metadata["overlaps_removed"], 21)
        whole_foods = [row for row in rows if row.description == "WHOLEFDS MKT #10452"]
        self.assertEqual(len(whole_foods), 2, "same-file duplicate-looking rows remain visible")


if __name__ == "__main__":
    unittest.main()
