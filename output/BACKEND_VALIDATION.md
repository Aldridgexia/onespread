# Backend milestone validation

Verified September 3, 2026, evening America/New_York (September 4 UTC).

- Python 3.12.9; uv-managed environment and lockfile.
- Installed alpaca-py 0.44.0, Ruff 0.16.6, ty 0.0.78, pytest 9.1.1.
- Ruff lint, Ruff formatting check, ty, and all 19 offline tests pass.
- Tests cover calls/puts, signed credit exits, the contract multiplier, stale/future quotes, repricing and account changes during inference, closed markets, missing calendar coverage, persistent uncertain submissions, full entry/exit reconciliation, rejection, partial fills, cancellation acknowledgement, malformed decisions, and paper-only configuration.
- Read-only actual-account cycle returned `WAIT: market_closed`.
- Separate access probes returned 3 news articles, 5 IEX bars, and 2 option snapshots. The current chain scan completed with zero eligible fresh spreads after hours.
- No Alpaca orders were submitted or canceled. No new inference requests were needed for the closed-market check.

## Not yet verified

The new production prompt has not been exercised on an open-session snapshot; previous GLM evaluations used a different synthetic policy prompt. Broker acceptance, fills, cancellation, and closing orders are tested with a fake broker, not verified against real paper orders. The news sample is not a complete macro calendar; reviewed calendar coverage has not been supplied. There is no validated return forecast or backtested edge.

The SDK emits an upstream `websockets.legacy` deprecation warning during import; no test failures occur. It does not affect the HTTP transports used here.

## Remaining submission work

Review event-calendar coverage, rehearse the new loop during an open session, build the decision/order dashboard, verify a complete paper-order lifecycle, and prepare the public repository, demo, video, and slides. Limit-order exits are attempts, not guaranteed flatness. The process must remain running to manage its orders.
