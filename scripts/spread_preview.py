"""Build SPY vertical drafts from saved data. No network and no order submission."""

import hashlib
import json
import math
import re
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / ".local" / "discovery"
REQUIRED_GREEKS = ("delta", "gamma", "theta", "vega", "rho")


def timestamp(value):
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", value).replace("Z", "+00:00"))


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def preview():
    discovery = json.loads((DATA / "discovery_summary.json").read_text())
    account = json.loads((DATA / "account_summary.json").read_text())
    contracts = json.loads((DATA / "SPY_contracts.json").read_text())
    snapshots = json.loads((DATA / "SPY_snapshots.json").read_text())
    now = datetime.now(timezone.utc)
    asof_date = date.fromisoformat(discovery["clock"]["timestamp"][:10])
    lookup = {(c["type"], c["expiration_date"], Decimal(c["strike_price"])): c for c in contracts}
    candidates: list[dict[str, Any]] = []
    for long in contracts:
        dte = (date.fromisoformat(long["expiration_date"]) - asof_date).days
        if not 7 <= dte <= 14:
            continue
        strike = Decimal(long["strike_price"])
        short_strike = strike + (Decimal(5) if long["type"] == "call" else Decimal(-5))
        short = lookup.get((long["type"], long["expiration_date"], short_strike))
        if not short or any(
            not c["tradable"]
            or str(c["size"]) != "100"
            or c.get("root_symbol") != "SPY"
            or c.get("underlying_symbol") != "SPY"
            for c in (long, short)
        ):
            continue
        legs = [snapshots.get(c["symbol"], {}) for c in (long, short)]
        if any(not number(s.get("impliedVolatility")) or s["impliedVolatility"] <= 0 for s in legs):
            continue
        if any(
            not all(number((s.get("greeks") or {}).get(k)) for k in REQUIRED_GREEKS) for s in legs
        ):
            continue
        if not 0.40 <= abs(legs[0]["greeks"]["delta"]) <= 0.65:
            continue
        quotes = [s.get("latestQuote") or {} for s in legs]
        if any(
            not (
                number(q.get("bp"))
                and number(q.get("ap"))
                and q["ap"] >= q["bp"] > 0
                and q.get("t")
            )
            for q in quotes
        ):
            continue
        quote_times = [timestamp(q["t"]) for q in quotes]
        if abs((quote_times[0] - quote_times[1]).total_seconds()) > 10:
            continue
        # Conservative indicative entry estimate: buy ask, sell bid; never a fill assumption.
        debit = (Decimal(str(quotes[0]["ap"])) - Decimal(str(quotes[1]["bp"]))).quantize(
            Decimal(".01"), rounding=ROUND_CEILING
        )
        if not Decimal(0) < debit < Decimal(5) or debit * 100 > 300:
            continue
        kind = "bull_call" if long["type"] == "call" else "bear_put"
        digest = hashlib.sha256(
            (long["symbol"] + short["symbol"] + quotes[0]["t"]).encode()
        ).hexdigest()[:20]
        ages = [(now - t).total_seconds() for t in quote_times]
        blockers = []
        if not discovery["clock"]["is_open"]:
            blockers.append("market_closed_in_saved_clock")
        if (now - timestamp(discovery["clock"]["timestamp"])).total_seconds() > 60:
            blockers.append("saved_clock_requires_refresh")
        if any(age < 0 or age > 60 for age in ages):
            blockers.append("option_quotes_require_refresh")
        if discovery["positions_count"] or discovery["open_orders_count"]:
            blockers.append("existing_exposure_or_pending_order")
        if float(account["options_buying_power"]) < float(debit * 100):
            blockers.append("insufficient_options_buying_power")
        blockers += [
            "saved_account_state_requires_refresh",
            "no_current_regime_or_event_assessment",
        ]
        payload = {
            "order_class": "mleg",
            "qty": "1",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": str(debit),
            "client_order_id": "preview-" + digest,
            "legs": [
                {
                    "symbol": long["symbol"],
                    "ratio_qty": "1",
                    "side": "buy",
                    "position_intent": "buy_to_open",
                },
                {
                    "symbol": short["symbol"],
                    "ratio_qty": "1",
                    "side": "sell",
                    "position_intent": "sell_to_open",
                },
            ],
        }
        candidates.append(
            {
                "id": digest,
                "kind": kind,
                "expiration": long["expiration_date"],
                "dte_at_snapshot": dte,
                "long_strike": str(strike),
                "short_strike": str(short_strike),
                "net_debit": str(debit),
                "premium_usd": str(debit * 100),
                "expiration_max_profit_before_costs_usd": str((5 - debit) * 100),
                "greeks_per_share": {
                    k: round(legs[0]["greeks"][k] - legs[1]["greeks"][k], 6)
                    for k in REQUIRED_GREEKS
                },
                "quote_timestamps": [q["t"] for q in quotes],
                "blockers": blockers,
                "selection_distance": abs(abs(legs[0]["greeks"]["delta"]) - 0.5)
                + abs(dte - 9) * 0.02,
                "order_draft": payload,
            }
        )
    candidates.sort(key=lambda c: c["selection_distance"])
    chosen = [
        next(c for c in candidates if c["kind"] == kind)
        for kind in ("bull_call", "bear_put")
        if any(c["kind"] == kind for c in candidates)
    ]
    result = {
        "generated_at": now.isoformat(),
        "mode": "offline_preview",
        "decision": "WAIT",
        "reason": "Saved after-hours data cannot authorize an order; refresh market/account state and assess regime first.",
        "feed": "indicative",
        "mathematically_eligible_drafts": len(candidates),
        "examples": chosen,
        "order_submission_enabled": False,
        "note": "Expiration payoff calculations exclude fees and execution/assignment complications. These drafts are not live trade recommendations.",
    }
    output = ROOT / "output" / "first_spread_preview.json"
    output.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "decision": result["decision"],
                "draft_count": len(candidates),
                "examples": [
                    {
                        k: c[k]
                        for k in (
                            "kind",
                            "expiration",
                            "long_strike",
                            "short_strike",
                            "premium_usd",
                            "blockers",
                        )
                    }
                    for c in chosen
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    preview()
