# OneSpread — hackathon prototype

Current scope: verified Alpaca paper access, option-universe discovery, Featherless model evaluation, and offline SPY vertical-spread drafts. Automated execution and a dashboard are not implemented yet.

## Credentials and tools

Enter keys only in the local `.env`; `.env.example` contains the public configuration template. `.env` and `.local/` are excluded from Git.

The official Alpaca CLI v0.0.14 was downloaded from [alpacahq/cli](https://github.com/alpacahq/cli/releases/tag/v0.0.14), checked against the release SHA-256 manifest, and installed at `.local/bin/alpaca`. It is a local tool dependency, not code generated for this project.

The discovery and evaluation scripts use the Python standard library. Run commands from this workspace.

## Read-only Alpaca discovery

```sh
python3 scripts/alpaca_access.py account
python3 scripts/alpaca_access.py clock
python3 scripts/alpaca_access.py assets
python3 scripts/alpaca_access.py scan
python3 scripts/alpaca_access.py history
```

The wrapper forces paper mode and permits only a fixed list of GET endpoints. Scan requires the asset inventory first. Historical probes use the scan's selected SPY contract and dates.

Results: [access report](output/ALPACA_ACCESS.md), [underlying universe](output/option_underlyings.csv), and [45-day contract inventory](output/option_contracts_45d.csv). Raw data are saved privately under `.local/discovery/`.

## Featherless access and evaluation

Selected model: **GLM-5 with thinking enabled**, based on ten passing synthetic cases. See the [model selection report](output/MODEL_ACCESS.md) and [tested request settings](output/selected_model_config.json). The observed 39-second median response requires a price refresh after inference.

```sh
python3 scripts/featherless_access.py inspect
python3 scripts/featherless_access.py evaluate-reasoning
```

Inspection verifies the key and retrieves model entitlements and prices. Evaluation consumes credits: ten synthetic cases per configured model, one attempt per case, with a conservative local cost estimate checked before requests. It never connects to Alpaca or executes model-proposed tool calls. The `evaluate` and `evaluate-json` modes preserve the alternative transport experiments for reproducibility.

This is a small integration and instruction-following test, not a backtest, financial forecast, or broad model-quality benchmark. Inputs and expected decisions are saved in `output/model_eval_cases.json`; results are saved by protocol in `output/` and raw responses in `.local/llm/`.

## First spread preview

```sh
python3 scripts/spread_preview.py
```

This reads saved SPY contracts and snapshots, constructs standard 100-share, five-point debit verticals at 7–14 days to expiry, and limits one-contract entry premium to $300. Entry estimates use the indicative long ask minus short bid. Expiration payoff values exclude costs and assignment/execution complications.

It writes [first_spread_preview.json](output/first_spread_preview.json), including multi-leg order drafts and the blockers that prevent their use. The preview performs no network operations and cannot submit an order. Saved after-hours data produce WAIT.

## Next implementation milestone

Connect refreshed market/account data, a current regime and event assessment, validated model output, and a deterministic execution gate. Reprice after inference, then add paper order submission, order reconciliation, exits, and a visible decision journal. Broker rejection and timeout handling must be exercised before unattended paper operation.
