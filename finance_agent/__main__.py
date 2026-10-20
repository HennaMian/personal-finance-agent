from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import AgentState, FinanceAgent
from .llm import OllamaClient, RecordingClient, ReplayClient
from .parser import load_and_reconcile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a monthly report from four finance CSV exports")
    parser.add_argument("--data", type=Path, required=True, help="directory containing the four CSV files")
    parser.add_argument("--out", type=Path, required=True, help="report JSON path")
    parser.add_argument("--replay", type=Path, help="replay a committed LLM recording (offline)")
    parser.add_argument("--record", type=Path, default=Path("recordings/ollama-run.json"))
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model for a live run")
    parser.add_argument("--max-steps", type=int, default=6)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        transactions, ingestion = load_and_reconcile(args.data)
        if args.replay:
            client = ReplayClient(args.replay)
        else:
            client = RecordingClient(OllamaClient(args.model), args.record, "ollama", args.model)
        state = FinanceAgent(client, max_steps=args.max_steps).run(
            AgentState(transactions=transactions, ingestion=ingestion), args.out
        )
        mode = f"replay {args.replay}" if args.replay else f"live Ollama ({args.model})"
        print(f"Wrote {args.out} with {len(state.transactions)} transactions using {mode}.")
        return 0
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"finance-agent: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
