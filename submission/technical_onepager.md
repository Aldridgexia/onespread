# OneSpread | Technical brief

**Purpose.** An auditable paper-only SPY debit-spread agent. The prototype tests execution discipline around LLM proposals; its strategy has no demonstrated alpha.

**Strategy.** Bull-call or bear-put debit verticals, 7–14 DTE, five-point width, standard 100-share multiplier, one contract per leg, maximum $300 entry premium excluding costs. The engine permits one active spread and at most one entry attempt per New York date. A 5/20-bar IEX momentum classification is an uncalibrated demonstration rule.

**AI logic.** GLM-5 on Featherless receives selected candidates and supplied public market/news evidence, then returns a candidate or WAIT with evidence IDs. Strict local parsing validates its final JSON. The model has no broker tools. Its prose cannot override sizing, risk constraints, or exit logic. Ten synthetic integration cases passed in the selected configuration; the 39.16-second median latency motivates refreshed data after inference. The engine prompt differs from that evaluation prompt.

**Independent execution checks.** Refresh context, quotes, and account state after inference. Reject changed direction/news, missing or old evidence, future quotes, decisions older than two minutes, debit deterioration above $0.10, ineligible exposure/account state, and calendar gaps. Reviewed calendar coverage expires after 24 hours; entries abstain within 30 minutes of listed events and in the session's final hour.

**Order lifecycle.** The official Alpaca CLI handles reads, alpaca-py validates request structure, and HTTPX sends mutations only to Alpaca's paper endpoint. SQLite records a unique intent before the request. Uncertain acknowledgements remain unresolved until reconciliation. Cancel pending orders after 120 seconds and await confirmation. Closing limits can trigger at +30%/-25% indicative credit thresholds, two hours held, or 30 minutes before session close. Both the exit fill and account flatness must be confirmed. Limits may not fill; partial fills, unexpected positions, assignments, and failed exits require an operator.

**Infrastructure.** Python 3.12, uv lockfile, Ruff, ty, and offline pytest checks. A process lock prevents concurrent local runners. The agent must remain running to manage lifecycle state. A separate loopback, read-only dashboard exposes an allowlist of files and journal results. The hosted static demo contains synthetic replay data only. Credentials, downloaded tools, calendars, and journals stay outside Git.

**Verified versus pending.** Alpaca reads and paid model inference have succeeded. Three synthetic replays exercise the real engine using a scripted model and fake broker. Actual paper submission, fills, and a broker round trip remain unverified; no orders have been submitted during development. Indicative options data cannot establish executable prices. The premium cap excludes costs and is not a guarantee against assignment or operational outcomes.

**Source and evidence.** [Repository](https://github.com/Aldridgexia/onespread) · [Model evaluation](../output/MODEL_ACCESS.md) · [Alpaca access](../output/ALPACA_ACCESS.md) · [Engine](../onespread/engine.py) · [Risk and lifecycle tests](../tests/test_engine.py).
