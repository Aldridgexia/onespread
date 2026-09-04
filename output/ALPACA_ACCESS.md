# Alpaca access and option universe

Verified September 2, 2026, approximately 10:31–10:36 p.m. America/New_York, using the official Alpaca CLI v0.0.14 and the dedicated paper account. All remote operations were GET requests. No orders, account changes, or subscription changes were made.

## Account

| Item | Observed value |
| --- | --- |
| Trading destination | `https://paper-api.alpaca.markets` |
| Account ID suffix | `4ca097` |
| Status | ACTIVE |
| Created | September 1, 2026 |
| Cash / equity | $100,000 / $100,000 |
| Options buying power | $100,000 |
| General buying power | $400,000; distinct from options buying power |
| Options approved / trading level | 3 / 3 |
| Account / trading blocks | None reported |
| Positions / open orders | 0 / 0 |
| Market clock | Closed; next regular open September 3 at 9:30 a.m. ET |

Level 3 enables supported spreads. Account enablement does not establish that every proposed order will be accepted; no execution was attempted.

## Available underlying universe

The active-assets query with `attributes=options_enabled` returned **6,301 assets**, all in class `us_equity`, all carrying the returned `has_options` flag. **6,173 underlying assets were marked tradable**. These flags are a discovery starting point; they do not guarantee current tradable contracts or usable quotes for every underlying.

Exchange counts: NASDAQ 2,614; NYSE 1,777; ARCA 1,239; BATS 455; AMEX 90; OTC 126.

The full returned underlying list is generated locally as `output/option_underlyings.csv` and excluded from Git. This was an equity/ETF asset discovery, not an exhaustive test of index-option support.

## Five-underlying contract inventory

Explicit inclusive expiration window: **September 3 through October 18, 2026**. Every contract page was consumed. Counts include all strikes, both calls and puts, for the five named underlyings, rather than the full market's option contracts.

| Underlying | Contracts | Calls | Puts | Expirations | First expiry |
| --- | ---: | ---: | ---: | ---: | --- |
| SPY | 5,160 | 2,580 | 2,580 | 15 | September 3 |
| QQQ | 5,162 | 2,581 | 2,581 | 15 | September 3 |
| IWM | 2,908 | 1,454 | 1,454 | 15 | September 3 |
| AAPL | 1,268 | 634 | 634 | 10 | September 4 |
| NVDA | 1,330 | 665 | 665 | 10 | September 4 |
| Total | 15,828 | 7,914 | 7,914 | — | — |

All 15,828 returned contracts were marked tradable, American style, size 100. The last expiry returned in this window was October 16. Dates and counts are a snapshot of the catalogue, not a guarantee of future listings.

The full contract inventory is generated locally as `output/option_contracts_45d.csv` and excluded from Git.

## Actual market-data coverage

Underlying reference prices came from IEX daily bars. Option snapshots explicitly used `feed=indicative`, with strikes within ±10% of those reference prices and the same expiration window. Every snapshot page was consumed.

| Underlying | Reference price | Contracts sampled / snapshots | Positive two-sided quotes | Positive IV and all 5 Greeks |
| --- | ---: | ---: | ---: | ---: |
| SPY | 765.13 | 3,098 / 3,098 | 2,965 | 2,800 (90.4%) |
| QQQ | 709.32 | 2,874 / 2,874 | 2,717 | 2,589 (90.1%) |
| IWM | 294.01 | 1,532 / 1,532 | 1,417 | 1,315 (85.8%) |
| AAPL | 325.03 | 342 / 342 | 342 | 330 (96.5%) |
| NVDA | 224.435 | 250 / 250 | 250 | 227 (90.8%) |

All 8,096 snapshots contained a latest-quote object. A positive two-sided quote requires `ask >= bid > 0`; it does not establish executable liquidity. Greek coverage checks delta, gamma, theta, vega and rho for finite numerical values. Zero is permitted for a Greek; missing values are not treated as zero. A total of 835 snapshots lacked the full positive-IV/Greek set.

Quotes were dated September 2, generally near 4 p.m. ET; the earliest sampled QQQ quote was approximately 3:35 p.m. ET. Because this scan ran after market close, these are prior-session snapshots. Latest-trade timestamps were much older for some contracts, including a SPY contract last traded in September 2025. Snapshot presence alone is therefore not a freshness check.

Open interest was present for 10,875 of the 15,828 contracts. All populated open-interest dates were **August 31**, and 4,953 contracts had no open-interest value. Preserve the date and missingness explicitly.

Alpaca documents the Basic indicative feed as modified quote data and derived trades delayed by 15 minutes. Indicative quote spreads and paper fills should not be presented as evidence of executable market prices or strategy profitability. [Feed documentation](https://docs.alpaca.markets/us/docs/historical-option-data)

## Entitlements and historical data

- **Indicative option chain:** verified for all five sampled underlyings.
- **IEX underlying snapshots:** verified for all five.
- **Latest OPRA snapshot:** HTTP 403, specifically `OPRA agreement is not signed`. This identifies the observed rejection; it does not prove signing the agreement alone would grant real-time OPRA under Basic. No agreement was accepted or plan upgraded.
- **Historical minute bars:** verified for `SPY260903C00765000`, requesting September 1–2 and retrieving five recent one-minute bars.
- **Historical trades:** verified for the same contract/date window, retrieving five recent trades.
- Historical requests were made without a feed parameter. The historical-trades endpoint rejected `feed=indicative`; retrying without that parameter succeeded. This is historical access, not proof of latest OPRA access.
- Streaming, long-horizon historical completeness, index options, and actual order execution were not tested.

## Practical implication for the hackathon

The account and available data support building the paper demo now. SPY is a reasonable first underlying to narrow the implementation around, based on the verified catalogue and snapshot coverage. Contract selection should enforce quote timestamps, positive quotes, available IV/Greeks, known contract size, and explicit treatment of dated/missing open interest. Recheck data during the next market session before making an automated paper decision.

## Local setup and refresh

Paper credentials remain in the Git-ignored `.env`. The checksum-verified official CLI binary is installed at `.local/bin/alpaca`. The discovery wrapper loads the keys into the child process environment, forces paper routing, permits only allowlisted GET endpoints, and redacts credential values from reported CLI errors. Raw responses and machine-readable summaries are under `.local/discovery/`, which is also ignored by Git.

From this workspace, run:

```sh
python3 scripts/alpaca_access.py account
python3 scripts/alpaca_access.py clock
python3 scripts/alpaca_access.py assets
python3 scripts/alpaca_access.py scan
python3 scripts/alpaca_access.py history
```

The CSV files and private summaries refresh when these commands run; this narrative records the initial scan. The local CLI installation is documented by the [official release](https://github.com/alpacahq/cli/releases/tag/v0.0.14).

API references: [contract filters and pagination](https://docs.alpaca.markets/us/reference/get-options-contracts), [option snapshots](https://docs.alpaca.markets/us/reference/optionchain), [options enablement](https://docs.alpaca.markets/us/docs/options-trading).
