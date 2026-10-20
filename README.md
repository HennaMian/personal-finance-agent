# Personal Finance Agent

A small tool-using agent that turns four overlapping, messy CSV exports into a reproducible monthly report. The model chooses the next tool and supplies missing semantic categories; ordinary Python owns parsing, reconciliation, validation, arithmetic, and report serialization.

## Run it

Requires Python 3.10+ and has no third-party runtime dependencies.

```bash
python3 -m finance_agent \
  --data sample_data \
  --out report.json \
  --replay recordings/submission-run.json
```

The committed recording makes this command fully offline. It produces `report.json` with 48 canonical transactions from 69 raw input rows. Run the offline test suite with:

```bash
python3 -m unittest discover -v
```

To demonstrate recovery from bad model output without changing code:

```bash
python3 -m finance_agent --data sample_data --out failure-report.json \
  --replay recordings/failure-demo.json --max-steps 2
```

That recording returns prose and then an unknown tool. The bounded fallback still exits successfully and writes a structurally valid report, with unresolved labels safely set to `Other`.

For a live run, install [Ollama](https://ollama.com/), start it, pull `qwen2.5:7b`, and omit `--replay`:

```bash
ollama pull qwen2.5:7b
python3 -m finance_agent --data sample_data --out report.json \
  --model qwen2.5:7b --record recordings/ollama-run.json
```

The live client requests temperature 0. Every response is appended to the recording after it is received. No API key is used or stored. Approximate development time: 3 hours.

## Design

The loop exposes three tools: `categorize_transactions`, `compute_totals`, and `write_report`. At each step, the controller receives compact state plus the prior observation and returns the next tool call. The dispatcher checks the tool name and preconditions, returns an observation, and stops after six steps. This makes it an agent rather than a fixed prompt chain: the model chooses an action, sees success or failure, and chooses again.

Model output is untrusted. A category response must decode to a JSON object, refer to transaction IDs, and use the fixed allow-list. Missing or off-list labels become `Other`. A malformed controller response consumes a bounded step and becomes an error observation. If the model or provider keeps failing, the step-limit fallback labels unresolved rows `Other`, computes totals, and writes the report. `tests/test_agent.py` demonstrates this with a client that returns garbage on every call.

The hard boundary is in `finance_agent/calculations.py`: it accepts normalized transactions, not model totals, and uses `Decimal` until JSON serialization. The summary is deterministic too, so every displayed number comes from the same computed totals.

## Data rules

- All four named files are required and read. Dates accept `YYYY-M-D` and `MM/DD/YYYY`, then serialize as `YYYY-MM-DD`; amounts use `Decimal`.
- The exports overlap. Reconciliation precedence is bank statement, uncategorized/card feed, clean expenses, then income. A later cross-file row is removed only when amount matches, posting dates are within one day, and the descriptions share a meaningful merchant token. An explicit label from a lower-priority clean export can enrich the retained row.
- Rows within the same file are never deduplicated. That keeps the two identical-looking Whole Foods charges in the ledger and flags the later one for human review.
- `Transfers` do not count as income or expense. A zero-dollar pending authorization is retained for auditability, excluded from totals, and flagged.
- Positive `Income` rows count as income. Other positive rows are refunds and reduce expenses in their category. Negative non-transfer rows are expenses. `net = income - expenses`; `savings_rate = net / income` (or zero when income is zero).
- No fuzzy/semantic deduplication is attempted beyond the narrow rule above. False merging is more damaging than leaving a possible duplicate visible.

## AI usage and decisions

I used OpenAI ChatGPT/Codex to help scaffold the package, propose tests, and review failure cases. Its categorization and tool-choice responses for the development run are saved in `recordings/submission-run.json`. I reviewed the category mapping and kept ambiguous Venmo and unknown-merchant rows as `Other` rather than inventing intent.

I rewrote the first-pass architecture around a standard-library-only client and deterministic `Decimal` calculations, narrowed deduplication to an explainable three-part rule, and made the fallback produce a complete report instead of aborting. The following decisions are mine and are explicit in code: the LLM/code boundary, the three tool contracts, category allow-list, source precedence, transfer/refund/pending treatment, and bounded failure behavior.

I deliberately did not build a UI, database, broad fuzzy matching, or a categorization benchmark. I chose one optional extra: conservative duplicate/anomaly flags. With two more hours, I would add property-based reconciliation tests and recording schema/version validation; I would still skip a UI because it does not improve the evaluated agent boundary.

## Walkthrough notes

- Run the committed replay and explain the three-step choose/observe loop in `FinanceAgent.run`.
- Trace `WHOLEFDS MKT #10452` from mixed-source ingestion through its recorded `Food` label to the category total and duplicate flag.
- Open `compute_totals` and show that its inputs contain labels but no model-produced arithmetic.
- Swap in the test `GarbageClient` (or run that test) to show the two failed decisions, step limit, `Other` fallback, and valid report.
- Close with the narrow reconciliation trade-off, what AI-generated work was changed, and the two-hour extension plan above.
