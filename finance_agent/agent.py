from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .calculations import build_summary, compute_totals, find_flags
from .categories import apply_categories, categorization_prompt, clean_json_object
from .llm import LLMClient
from .models import Transaction


@dataclass
class AgentState:
    transactions: list[Transaction]
    ingestion: dict[str, object]
    totals: dict[str, float] | None = None
    by_category: dict[str, float] | None = None
    observations: list[dict[str, object]] = field(default_factory=list)
    report_written: bool = False


class FinanceAgent:
    TOOLS = ("categorize_transactions", "compute_totals", "write_report")

    def __init__(self, llm: LLMClient, max_steps: int = 6):
        self.llm = llm
        self.max_steps = max_steps

    def _decision_prompt(self, state: AgentState) -> str:
        missing = sum(item.category is None for item in state.transactions)
        snapshot = {
            "missing_categories": missing,
            "totals_computed": state.totals is not None,
            "report_written": state.report_written,
            "last_observation": state.observations[-1] if state.observations else None,
        }
        return (
            "You are controlling a finance agent. Pick exactly one next tool based on state and the latest "
            "observation. Order is normally categorize_transactions, compute_totals, write_report, but recover "
            "from tool errors. Return ONLY JSON like {\"tool\": \"compute_totals\", \"arguments\": {}}. "
            f"Available tools: {list(self.TOOLS)}. State: {json.dumps(snapshot)}"
        )

    def _dispatch(self, tool: str, state: AgentState, output: Path) -> dict[str, object]:
        if tool == "categorize_transactions":
            missing = [item for item in state.transactions if not item.category]
            if not missing:
                return {"tool": tool, "status": "ok", "detail": "nothing to categorize"}
            response = self.llm.complete(categorization_prompt(missing), "categorization")
            result = apply_categories(state.transactions, response)
            return {"tool": tool, "status": "ok", **result}
        if tool == "compute_totals":
            # A premature computation is rejected so the controller can observe
            # the failed precondition and choose categorization next.
            if any(item.category is None for item in state.transactions):
                return {"tool": tool, "status": "error", "detail": "missing categories remain"}
            state.totals, state.by_category = compute_totals(state.transactions)
            return {"tool": tool, "status": "ok", "detail": "deterministic totals computed"}
        if tool == "write_report":
            if state.totals is None or state.by_category is None:
                return {"tool": tool, "status": "error", "detail": "totals not computed"}
            report = {
                "totals": state.totals,
                "by_category": state.by_category,
                "flagged": find_flags(state.transactions),
                "transactions": [item.public_dict() for item in state.transactions],
                "summary": build_summary(state.totals, state.by_category),
                "metadata": {
                    "ingestion": state.ingestion,
                    "agent_steps": state.observations + [{"tool": tool, "status": "ok"}],
                },
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            state.report_written = True
            return {"tool": tool, "status": "ok", "detail": str(output)}
        return {"tool": tool, "status": "error", "detail": "unknown tool"}

    def run(self, state: AgentState, output: Path) -> AgentState:
        for _ in range(self.max_steps):
            try:
                raw = self.llm.complete(self._decision_prompt(state), "orchestration")
                decision = clean_json_object(raw)
                tool = decision.get("tool") if decision else None
                if tool not in self.TOOLS:
                    state.observations.append(
                        {"tool": "controller", "status": "error", "detail": "invalid model decision"}
                    )
                    continue
                observation = self._dispatch(str(tool), state, output)
                state.observations.append(observation)
                if state.report_written:
                    return state
            except Exception as exc:  # model/provider failures are recoverable
                state.observations.append(
                    {"tool": "controller", "status": "error", "detail": type(exc).__name__}
                )

        # Bounded deterministic fallback: no missing label or model failure can
        # prevent a structurally valid report.
        for item in state.transactions:
            if not item.category:
                item.category = "Other"
        if state.totals is None:
            state.totals, state.by_category = compute_totals(state.transactions)
        state.observations.append({"tool": "fallback", "status": "ok", "detail": "step limit reached"})
        self._dispatch("write_report", state, output)
        return state
