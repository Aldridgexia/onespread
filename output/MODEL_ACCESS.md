# Featherless access and model selection

Completed September 2, 2026, approximately 11:36 p.m. ET (September 3 at 03:36 UTC).

**Selected: `zai-org/GLM-5` on Featherless, with thinking enabled and locally validated JSON output.** The primary model in `.env` and `.env.example` has been updated. Exact tested request settings are in [selected_model_config.json](selected_model_config.json).

## Verified access

The authenticated plan request succeeded. Both `zai-org/GLM-5` and `deepseek-ai/DeepSeek-V4-Flash` were active, ungated, available on the account's plan, and listed as supporting tool use. Actual inference requests succeeded for both. The plan endpoint did not expose a credit balance, so remaining credit was not independently verified.

Credentials were loaded from the local Git-ignored `.env`; only the Featherless key was sent to `api.featherless.ai`. The inference tests used synthetic market/account values. Alpaca credentials and account records were not sent to the models, and no proposed tool call was executed.

## Ten-case evaluation

Each configuration used one attempt per model per case. The same synthetic cases and policy were used for both models, alternating which model ran first. The cases cover:

1. Valid bullish selection.
2. Valid bearish selection.
3. Neutral-regime abstention.
4. Stale quotes.
5. Missing required Greeks.
6. Correct contract-multiplier arithmetic under a $300 premium cap.
7. An imminent major event.
8. Instruction injection embedded in untrusted article text.
9. An already-pending entry order.
10. An ineligible top-ranked candidate with a valid alternative.

Passing requires strict parsing and field validation, the expected action/candidate, supplied evidence IDs, and at least one relevant evidence reference. Reasoning fields were never accepted as the final decision. Malformed JSON was not repaired.

| Tested configuration | DeepSeek-V4-Flash | GLM-5 |
| --- | ---: | ---: |
| Forced function call, thinking disabled | 7/10 | 0/10 |
| JSON-object response mode, thinking disabled | 0/10 | 0/10 |
| JSON requested in prompt, thinking enabled, no forced response format | 3/10 | **10/10** |

The first test exposed empty function arguments: two DeepSeek responses and every GLM response lacked usable arguments. DeepSeek also made one incorrect candidate decision in that test. In the second configuration, DeepSeek omitted the opening JSON brace, while GLM placed its answer in a reasoning field and left the content field empty. With thinking enabled, GLM produced valid final JSON for all ten cases; seven DeepSeek responses still failed strict parsing.

These are observations about these hosted configurations. They do not establish whether a failure originates in model generation, chat templates, or provider response processing, and do not establish that the underlying DeepSeek model is generally inferior.

## Final configuration measurements

| Metric | DeepSeek-V4-Flash | GLM-5 |
| --- | ---: | ---: |
| Complete passing cases | 3/10 | 10/10 |
| Strictly valid structured outputs | 3/10 | 10/10 |
| Correct action/candidate decisions | 3/10 | 10/10 |
| Valid evidence-ID references | 3/10 | 10/10 |
| Median request duration | 4.19 seconds | 39.16 seconds |
| Maximum request duration | 35.84 seconds | 52.77 seconds |
| Input tokens | 7,224 | 6,982 |
| Output tokens, including reported reasoning usage | 5,462 | 6,330 |
| Estimated token cost | $0.00254 | $0.02657 |

Durations measure receipt of the complete response; DeepSeek's latency numbers include responses that were unusable. GLM's cost above covers the final ten requests only.

Across all three configurations, 60 inference requests reported **47,365 input tokens and 16,242 output tokens**, for an estimated **$0.05399** at the retrieved per-token prices. This is a usage-based estimate, not an independently reconciled billing balance.

The final configuration uses `temperature=0`, `max_tokens=2048`, and `chat_template_kwargs={"enable_thinking": true}`. It requests a JSON object through the prompt, parses `message.content`, and validates the result in local code. It does not use the forced tool-call or JSON-object response-format settings that failed these checks.

## Implication for the build

Use GLM-5 as the initial model for a decision cycle measured in minutes. Refresh prices and account state after inference; the 39-second median response time is material relative to a 60-second quote-age threshold. Invalid output or a timeout must result in abstention, and every proposed order must pass independent numerical and account checks.

This is a small integration and instruction-following test, not a statistical backtest, an alpha study, or evidence of production reliability. Evidence-ID checks do not constitute a comprehensive factuality evaluation. Do not deploy the synthetic test prompt as the production market-decision prompt.

## First SPY draft pipeline

The offline preview constructed 47 SPY debit-vertical drafts meeting its structural, Greek/IV, quote-shape, DTE, and premium filters. Two representative drafts from the saved September 2 data are:

| Structure | Expiry | Long / short strike | Indicative premium estimate |
| --- | --- | --- | ---: |
| Bull call | September 11 | 766 / 771 | $257 |
| Bear put | September 11 | 766 / 761 | $181 |

These are historical illustrations, not current trade recommendations. The preview returns **WAIT** because the saved clock is closed/stale, quotes and account state need refreshing, and there is no current regime/event assessment. This refusal is deterministic; the actual saved market snapshot was not submitted to the LLM. Both order drafts remain offline and order submission is disabled.

The next implementation step is the fresh-data decision loop and independent execution gate, followed by paper order lifecycle/reconciliation and the decision dashboard.

## Artifacts

- [Synthetic cases, schema, and test policy](model_eval_cases.json)
- [Forced function-call results](model_eval_results.json)
- [Non-thinking JSON results](model_eval_results_json.json)
- [Thinking-enabled JSON results](model_eval_results_reasoning-json.json)
- [Selected request settings](selected_model_config.json)
- [Offline spread drafts and blockers](first_spread_preview.json)

Raw responses and model entitlement metadata remain in `.local/llm/`. Provider documentation: [API setup](https://featherless.ai/docs/quickstart-guide), [model metadata](https://featherless.ai/docs/api-reference-models), [thinking controls](https://featherless.ai/docs/chat-template-kwargs).
