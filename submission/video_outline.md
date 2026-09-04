# OneSpread | Four-minute demo video

Target: 4:00, 1920×1080 landscape, MP4. Keep the synthetic-data labels visible. Use the local dashboard at `http://127.0.0.1:8765` after `make dashboard`; this walkthrough needs no keys. Record the screen and narration together. Have the six-slide PDF and public repository ready in separate tabs.

## 0:00–0:25 | The problem and the project

**Show:** Slide 1, then the dashboard overview.

**Say:** “I'm a quant developer, and I built OneSpread solo. It's a paper-only SPY options agent that records what its model saw, what it proposed, and why execution was allowed or blocked. I focused on a practical problem: by the time an AI explanation arrives, the prices behind it may already have changed.”

## 0:25–0:55 | A deliberately narrow strategy

**Show:** Slide 4 and its illustrative payoff chart.

**Say:** “OneSpread considers bull-call and bear-put debit verticals, seven to fourteen days out, with a five-point width. It allows one spread at a time and caps entry premium at three hundred dollars before costs. This chart is a hypothetical expiration payoff. It is not realized performance. The limited scope lets me inspect the entire execution path.”

## 0:55–1:35 | The proposal and independent gate

**Show:** Dashboard Replay, eligible-entry scenario. Point to evidence, model decision, and numerical checks.

**Say:** “The official Alpaca CLI supplies the real integration's market and account reads. GLM-5 runs through Featherless and proposes a candidate or WAIT using supplied evidence. It cannot call the broker. The engine validates the response and refreshes prices, context, and account state before any order. Here, the synthetic eligible-entry replay shows the evidence, proposal, and gate result together. This replay uses the real engine with a scripted model and fake broker.”

## 1:35–2:10 | The memorable failure case

**Show:** Switch to the stale-quote replay. Pause on the refusal and reason.

**Say:** “Now the quote is stale. Even if a proposal looks reasonable, the execution gate refuses it. This is a useful result: WAIT has an explicit reason. In my small hosted-model evaluation, the selected GLM configuration took about thirty-nine seconds at the median. That made a post-inference data refresh essential. The ten-case result tested integration and instruction following, not trading ability.”

## 2:10–2:50 | Follow an order to confirmed flatness

**Show:** Lifecycle replay and its ordered events. Scroll slowly enough to read entry, reconciliation, closing, and flat state.

**Say:** “The next replay follows an entry through confirmed flatness. Before a paper submission, the engine writes a durable intent. If the acknowledgement is uncertain, it reconciles broker state rather than blindly sending the order again. Subsequent cycles manage cancellation and closing limits, and completion requires a confirmed exit fill and flat account. Unexpected or partial positions require attention. These events are simulated; they do not prove a real broker fill.”

## 2:50–3:25 | Working integration and honest limits

**Show:** Slide 5, then the public repository's model/access reports and test files.

**Say:** “Alpaca read access and paid Featherless inference have succeeded. The repository includes offline tests covering risk gates and lifecycle behavior. A real paper submission and round trip remain unverified. Basic options quotes are indicative, and the momentum rule is uncalibrated. I am making no profitability claim. The current contribution is a reproducible, inspectable execution prototype.”

## 3:25–4:00 | Close with the deliverable

**Show:** Slide 6, then README quick start and the repository URL.

**Say:** “The source is public and MIT-licensed. You can run the synthetic dashboard without credentials, inspect the model evaluation, and connect your own approved paper account to the local agent. Next I would verify a monitored paper round trip, then validate executable data and research the strategy out of sample. OneSpread makes the proposal, the veto, and the order state visible in one place.”

## Recording checklist

- Keep system notifications, credentials, paper account IDs, and private journal details out of frame.
- Leave the synthetic labels readable and do not call a replay a live trade.
- Use a separate browser tab for the public repository and confirm the URL opens while signed out.
- Speak naturally; pause on the veto and lifecycle rather than reading every number.
- Check the exported MP4's audio, duration, and first/last frames before upload.
- If a real paper round trip is verified later, replace the status sentence only with its observed outcome and redacted broker evidence. Do not infer a fill from an accepted order.
