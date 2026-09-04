# Submission fields

## Project title

OneSpread

## Tagline

AI-assisted options decisions with an independent execution gate.

## Short description

OneSpread evaluates SPY debit spreads with GLM-5, refreshes market evidence after inference, and applies deterministic risk checks before paper execution. A durable journal and replay dashboard explain entries, vetoes, and order state. Broker fills remain unverified.

## Project description

### The problem

An options trading agent can produce a convincing explanation while using prices that have already changed. It can also lose track of whether an order was accepted after a timeout. For a quant developer, those execution failures matter before any claim about alpha.

### What I built

OneSpread is a solo-built, paper-only SPY options agent with a read-only decision dashboard. It focuses on one bull-call or bear-put debit vertical at a time: five-point strike width, 7–14 days to expiry, one contract per leg, and at most $300 entry premium before costs. The narrow strategy scope makes the execution path inspectable.

The official Alpaca CLI supplies account, market, options, and news reads. A simple 5/20-bar momentum classification and supplied news evidence inform GLM-5, served through Featherless. The model proposes an eligible candidate or WAIT and cites evidence IDs. It has no direct broker tools. Code validates its output and refreshes context, quotes, and account state before allowing an order.

The execution gate rejects stale quotes, invalid selections, changed context, excessive debit deterioration, existing exposure, and uncovered event-calendar periods. Paper mode records an order intent before making a single multi-leg request. Subsequent cycles reconcile broker state, manage cancellation and closing limits, and require confirmation of flatness. Uncertain acknowledgements are reconciled instead of blindly resubmitted.

### Why AI is useful here

The model connects a proposed spread to the supplied regime and news evidence in a readable decision record. It can abstain. Numerical constraints, sizing, calendar rules, and order state remain in deterministic code. In a small synthetic integration evaluation, the selected GLM-5 configuration passed 10 of 10 cases, with a 39.16-second median response. That latency motivated the post-inference refresh. These results describe one hosted configuration and test prompt; they are not a reliability or trading-performance benchmark.

### What the demo proves

The dashboard includes three clearly labeled synthetic replays: eligible entry, a stale-quote veto, and an entry-to-flat lifecycle. These use the actual engine with a scripted model and fake broker, making its decision and reconciliation behavior reproducible without credentials. A separate local view displays the real agent's private journal.

Alpaca read access and Featherless inference have been exercised. Paper submission, fills, and a real broker round trip remain unverified. Basic options quotes are indicative, and the momentum rule is uncalibrated. No backtest, profitability, or production-readiness claim is made.

### Who it is for and what comes next

The initial audience is quant developers evaluating AI-assisted execution workflows. The product hypothesis is that inspectable evidence, explicit vetoes, and recoverable order state make experiments easier to audit. Next comes a monitored paper round trip, followed by execution-data validation and out-of-sample strategy research. The current deliverable is an auditable prototype, with MIT-licensed source and a reproducible local demo.

## Technologies and tags

Alpaca Trading API; official Alpaca CLI; alpaca-py; Featherless; GLM-5; Python; Pydantic; SQLite; HTTPX; uv; Ruff; ty; pytest; HTML/CSS/JavaScript; options; AI agents; paper trading.

## Repository

https://github.com/Aldridgexia/onespread

## Demo

https://onespread-options-lab.alxia-biz.chatgpt.site/

Organizer-facing note: the hosted demo is a synthetic replay interface; real Alpaca/Featherless decision cycles run locally. Arrange judge access before entering this URL in the submission form.
