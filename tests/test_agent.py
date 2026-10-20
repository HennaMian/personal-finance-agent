import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from finance_agent.agent import AgentState, FinanceAgent
from finance_agent.categories import apply_categories
from finance_agent.parser import load_and_reconcile


class GarbageClient:
    def complete(self, prompt: str, purpose: str) -> str:
        return "this is not JSON and is not a tool call"


class AgentFailureTests(unittest.TestCase):
    def test_off_list_category_is_rejected(self):
        rows, _ = load_and_reconcile(Path("sample_data"))
        target = next(row for row in rows if row.category is None)
        result = apply_categories([target], json.dumps({target.id: "Crypto Moonshots"}))
        self.assertEqual(target.category, "Other")
        self.assertEqual(result["rejected_to_other"], [target.id])

    def test_step_limit_fallback_writes_report_after_bad_model_output(self):
        rows, metadata = load_and_reconcile(Path("sample_data"))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            state = FinanceAgent(GarbageClient(), max_steps=2).run(AgentState(rows, metadata), output)
            report = json.loads(output.read_text())
        self.assertTrue(state.report_written)
        self.assertIn("fallback", [step["tool"] for step in state.observations])
        self.assertEqual(set(report), {"totals", "by_category", "flagged", "transactions", "summary", "metadata"})
        self.assertTrue(all(item["category"] for item in report["transactions"]))

    def test_committed_replay_runs_end_to_end(self):
        from finance_agent.llm import ReplayClient

        rows, metadata = load_and_reconcile(Path("sample_data"))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            state = FinanceAgent(ReplayClient(Path("recordings/submission-run.json"))).run(
                AgentState(rows, metadata), output
            )
            report = json.loads(output.read_text())
        self.assertTrue(state.report_written)
        self.assertGreater(report["totals"]["income"], 0)
        self.assertEqual(report["transactions"][0]["date"], "2024-01-01")


if __name__ == "__main__":
    unittest.main()
