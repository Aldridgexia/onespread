# Dashboard milestone

- A read-only local journal dashboard and a static synthetic replay share the same interface.
- Replay runs through the actual engine with a scripted model and fake broker: eligible entry, stale-quote veto, and entry → hold → exit → flat confirmation.
- 22 offline tests pass, including replay outcomes, read-only journal access, filtering internal identifiers, and avoiding database creation for an empty journal. Ruff and ty pass.
- The local root and journal endpoint respond successfully. Requests for `.env` return 404; POST requests are unsupported. The server binds to loopback only.
- The production bundle is a fixed allowlist of four files. It contains no keys, local journal, account state, or raw market data. Hosted replay is not connected to Alpaca.
- JavaScript syntax checked with Node. The local preview was opened. Browser visual/interaction QA was not requested and was not performed. The two optional WebMCP tools were advertised in the browser; tool invocation was not verified because the available browser documentation did not expose a call interface.

## Production prompt smoke test

The initial request returned Markdown-fenced JSON and failed validation. The prompt now explicitly requires raw JSON without backticks or surrounding text. One subsequent request passed strict parsing and evidence-ID validation in 51.57 seconds. See `production_prompt_smoke.json`.

The model's prose remains advisory: the smoke response suggested a 50% loss threshold and a prior swing low absent from its inputs. Neither can change the implemented exits (+30% / −25%, two hours, or session cutoff). This is evidence for retaining deterministic execution rules, and a prompt-quality limitation to address in the next open-session rehearsal. A passing syntax check does not establish grounded reasoning or a profitable policy. No new broker orders were submitted.

## Calendar

Primary release calendars reviewed for September 4, 08:00–11:00 ET; the configuration includes the 08:30 Employment Situation release. See `CALENDAR_REVIEW.md` for scope and sources. Recheck before paper operation.

## Remaining

Open-session production inference and a real Alpaca paper entry/exit lifecycle remain unverified. Public judge access, a public GitHub repository/license, video, and slides remain submission work.
