# OneSpread — hackathon prototype

SPY debit spreads with timestamped AI explanations, deterministic risk checks, and a durable paper-order journal. The backend supports dry runs, opt-in paper entry, reconciliation, cancellation, and exits. A read-only dashboard displays the local journal and three synthetic replay scenarios. No broker order has been submitted during development.

## Development

Python 3.12 is pinned in `.python-version`; uv manages `.venv` and the committed `uv.lock`.

```sh
uv sync --locked
make check                  # Ruff lint + formatting, ty, and offline risk/lifecycle tests
make format                 # Ruff fixes and formatting
uv run python -m onespread  # One read-only decision cycle
```

Dependencies: `alpaca-py` (official SDK order validation), `httpx` (bounded inference and paper-order transport), `pydantic` (data/decision validation), and `python-dotenv`. Development tools: Ruff, ty, pytest. Git tracks source, configuration, lockfile, and sanitized reports; credentials, downloaded binaries, journals, and generated market-data CSVs are ignored. A private Sites source repository supports the hosted demo; a public GitHub submission repository is still needed.

## Dashboard and replay

```sh
make dashboard            # http://127.0.0.1:8765
make build                # Synthetic-only static demo in dist/
uv run python -m onespread.smoke  # One paid GLM inference using synthetic inputs
```

The local dashboard has Replay and Local journal views. It never imports the broker clients and exposes no trading controls. The local endpoint binds only to loopback, serves an explicit file allowlist, and reads SQLite without write access. Refreshing the view does not run the trading agent.

The hosted demo bundles only four static files and synthetic replay data. It cannot reach the local journal or Alpaca. Replay scenarios exercise the real risk engine with a scripted model and fake broker: eligible entry, a stale-quote veto, and entry through confirmed flatness. The payoff chart is a theoretical expiration payoff, not realized performance. Optional page tools can select a replay scenario and read its visible decision; they cannot trade.

## Credentials and tools

Enter keys only in the local `.env`; `.env.example` contains the public configuration template. `.env` and `.local/` are excluded from Git.

The official Alpaca CLI v0.0.14 was downloaded from [alpacahq/cli](https://github.com/alpacahq/cli/releases/tag/v0.0.14), checked against the release SHA-256 manifest, and installed at `.local/bin/alpaca`. It is a local tool dependency, not code generated for this project.

Every decision cycle uses the official CLI for broker/account and market-data reads. The SDK validates multi-leg order structure. Mutations use a fixed paper API destination with no automatic retries, allowing the journal to handle uncertain outcomes explicitly. Run commands from this workspace; a fresh checkout also needs the verified official CLI installed at `.local/bin/alpaca` from the release above for its operating system and architecture.

## Read-only Alpaca discovery

```sh
uv run python scripts/alpaca_access.py account
uv run python scripts/alpaca_access.py clock
uv run python scripts/alpaca_access.py assets
uv run python scripts/alpaca_access.py scan
uv run python scripts/alpaca_access.py history
```

The wrapper forces paper mode and permits only a fixed list of GET endpoints. Scan requires the asset inventory first. Historical probes use the scan's selected SPY contract and dates.

Results: [access report](output/ALPACA_ACCESS.md), [underlying universe](output/option_underlyings.csv), and [45-day contract inventory](output/option_contracts_45d.csv). Raw data are saved privately under `.local/discovery/`.

## Featherless access and evaluation

Selected model: **GLM-5 with thinking enabled**, based on ten passing synthetic cases. See the [model selection report](output/MODEL_ACCESS.md) and [tested request settings](output/selected_model_config.json). The observed 39-second median response requires a price refresh after inference.

```sh
uv run python scripts/featherless_access.py inspect
uv run python scripts/featherless_access.py evaluate-reasoning
```

Inspection verifies the key and retrieves model entitlements and prices. Evaluation consumes credits: ten synthetic cases per configured model, one attempt per case, with a conservative local cost estimate checked before requests. It never connects to Alpaca or executes model-proposed tool calls. The `evaluate` and `evaluate-json` modes preserve the alternative transport experiments for reproducibility.

This is a small integration and instruction-following test, not a backtest, financial forecast, or broad model-quality benchmark. Inputs and expected decisions are saved in `output/model_eval_cases.json`; results are saved by protocol in `output/` and raw responses in `.local/llm/`.

## First spread preview

```sh
uv run python scripts/spread_preview.py
```

This reads saved SPY contracts and snapshots, constructs standard 100-share, five-point debit verticals at 7–14 days to expiry, and limits one-contract entry premium to $300. Entry estimates use the indicative long ask minus short bid. Expiration payoff values exclude costs and assignment/execution complications.

It writes [first_spread_preview.json](output/first_spread_preview.json), including multi-leg order drafts and the blockers that prevent their use. The preview performs no network operations and cannot submit an order. Saved after-hours data produce WAIT.

## Decision and execution loop

1. Read the paper account, market clock, positions, and pending orders. Stop on an ineligible account, closed session, exposure, or final-hour entry window.
2. Build up to two bull-call and two bear-put candidates from current SPY metadata and indicative quotes. Require standard 100-share contracts, five-point width, 7–14 DTE, complete Greeks, long absolute delta 0.40–0.65, and at most $300 premium for one spread.
3. Compute a simple 5/20-bar momentum classification from current-session IEX bars, and retrieve up to 20 recent SPY-tagged news headlines. GLM-5 can propose one candidate or WAIT and must cite supplied evidence. These thresholds are uncalibrated demonstration rules, not a measured trading edge.
4. Refresh context, quotes, and account state after inference. Reject changed direction/news, stale or future quotes, decisions older than two minutes, and debit deterioration greater than ten cents. A reviewed event calendar must cover the decision time; abstain within 30 minutes before or after an event.
5. Dry runs record a draft. Paper mode first commits a unique order intent, then sends a single multi-leg limit order. One active spread and at most one entry attempt per New York date are enforced. A lost acknowledgement remains unresolved until broker reconciliation; no blind resubmission.
6. Reconcile on subsequent cycles. Cancel orders still pending after 120 seconds and wait for broker confirmation. Owned, fully filled spreads trigger a closing limit at +30%/-25% indicative credit thresholds, two hours held, or 30 minutes before the broker's session close. Credit exits use a negative net limit price. Confirm both the exit fill and a flat account before completing the trade.

```sh
# Up to 60 read-only cycles, 60 seconds between cycles:
uv run python -m onespread --cycles 60 --interval 60

# Enables actual PAPER submissions/cancellations; requires reviewed calendar coverage:
uv run python -m onespread --paper --cycles 60 --interval 60
```

The process must stay running to manage orders and exits. A single cycle is not an unattended trading service. No live endpoint is configurable. Current option quotes are indicative, not OPRA executable prices; paper fills cannot establish real-market execution quality. Limit orders may remain unfilled. Partial fills, unmatched positions, assignments, non-positive exit-credit estimates, and terminal failed exits require operator attention. The app never liquidates unfamiliar positions. The $300 cap is entry premium, excluding fees; it is not a guarantee against every assignment or operational outcome.

## Calendar and journal

Place a reviewed calendar in `.local/onespread/calendar.json`. Its fields are `reviewed_at`, `coverage_start`, `coverage_end` (timezone-aware timestamps), `sources` (nonempty list of source URLs), and `events` (objects with `timestamp`, `title`, and `source`). Reviews expire after 24 hours. Include scheduled market-moving releases throughout the coverage interval. Empty event lists are appropriate only after checking the sources. Missing coverage blocks entries.

A bounded review is prepared for September 4, 2026, 08:00–11:00 ET, including the 08:30 Employment Situation release. See [calendar review](output/CALENDAR_REVIEW.md) for sources and limitations; recheck before an open-session rehearsal. This configuration does not itself turn on paper execution.

The private SQLite journal at `.local/onespread/journal.sqlite3` records decisions, supplied public evidence, intents, and lifecycle state. `.local/onespread/latest.json` is the latest result. Do not delete the journal while a paper order or position may exist: it is the ownership/reconciliation record. A process lock prevents two local runners acting simultaneously.

Next milestone: exercise the new prompt against open-session data, verify a complete paper execution lifecycle, and complete the public repository, short demo video, slides, and submission. The hosted Sites demo starts private; judge access must be arranged before submission.
