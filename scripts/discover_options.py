"""Inventory contract metadata and measure snapshot coverage; never sends orders."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import csv
import json
import statistics

from alpaca_access import get, save, ROOT, PRIVATE

SYMBOLS = ("SPY", "QQQ", "IWM", "AAPL", "NVDA")


def pages(path, params, field, *, data=False):
    collected = {} if field == "snapshots" else []
    tokens = set()
    for _ in range(40):
        response = get(path, params, data=data)
        batch = response.get(field) or ({} if isinstance(collected, dict) else [])
        if isinstance(collected, dict):
            collected.update(batch)
        else:
            collected.extend(batch)
        token = response.get("next_page_token")
        if not token:
            return collected
        if token in tokens:
            raise RuntimeError("Repeated pagination token; inventory is incomplete.")
        tokens.add(token)
        params = dict(params, page_token=token)
    raise RuntimeError("Pagination safety limit reached; inventory is incomplete.")


def finite_number(value):
    import math
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def inspect_symbol(symbol, start, end, stock):
    params = {"expiration_date_gte": start, "expiration_date_lte": end}
    contracts = pages("/v2/options/contracts", dict(params, underlying_symbols=symbol,
                      status="active", limit=10000), "option_contracts")
    save(f"{symbol}_contracts.json", contracts)
    price = (stock.get("dailyBar") or {}).get("c") or (stock.get("latestTrade") or {}).get("p")
    if not price:
        raise RuntimeError(f"No underlying reference price for {symbol}.")
    low, high = round(price * .9, 2), round(price * 1.1, 2)
    snapshots = pages(f"/v1beta1/options/snapshots/{symbol}", dict(params, feed="indicative",
                      strike_price_gte=low, strike_price_lte=high, limit=1000),
                      "snapshots", data=True)
    save(f"{symbol}_snapshots.json", snapshots)
    expected = [c for c in contracts if low <= float(c["strike_price"]) <= high]
    quote_count = iv_count = greek_count = two_sided = 0
    quote_times, trade_times, spreads = [], [], []
    greek_fields = Counter()
    for snap in snapshots.values():
        quote, trade, greeks = snap.get("latestQuote") or {}, snap.get("latestTrade") or {}, snap.get("greeks") or {}
        quote_count += bool(quote)
        if quote.get("t"):
            quote_times.append(quote["t"])
        if trade.get("t"):
            trade_times.append(trade["t"])
        iv = snap.get("impliedVolatility")
        iv_count += finite_number(iv) and iv > 0
        fields = ("delta", "gamma", "theta", "vega", "rho")
        greek_count += all(finite_number(greeks.get(k)) for k in fields)
        for k in fields:
            greek_fields[k] += finite_number(greeks.get(k))
        bid, ask = quote.get("bp"), quote.get("ap")
        if finite_number(bid) and finite_number(ask) and ask >= bid > 0:
            two_sided += 1
            spreads.append(2 * (ask-bid)/(ask+bid))
    summary = {
        "symbol": symbol, "reference_price": price, "reference_bar": stock.get("dailyBar"),
        "strike_band": [low, high], "contracts": len(contracts),
        "tradable_contracts": sum(bool(c.get("tradable")) for c in contracts),
        "types": dict(Counter(c.get("type") for c in contracts)),
        "styles": dict(Counter(c.get("style") for c in contracts)),
        "sizes": dict(Counter(str(c.get("size")) for c in contracts)),
        "expirations": dict(sorted(Counter(c["expiration_date"] for c in contracts).items())),
        "open_interest_present": sum(c.get("open_interest") is not None for c in contracts),
        "open_interest_dates": dict(Counter(c.get("open_interest_date") for c in contracts)),
        "near_money_contracts": len(expected), "snapshots": len(snapshots),
        "near_money_contracts_with_snapshot": sum(c["symbol"] in snapshots for c in expected),
        "quotes": quote_count, "positive_two_sided_quotes": two_sided,
        "positive_iv": iv_count, "all_five_greeks": greek_count, "greek_fields": dict(greek_fields),
        "quote_timestamp_range": [min(quote_times), max(quote_times)] if quote_times else None,
        "trade_timestamp_range": [min(trade_times), max(trade_times)] if trade_times else None,
        "median_indicative_relative_spread": statistics.median(spreads) if spreads else None,
        "example_snapshot": next(iter(snapshots.items()), None),
    }
    print(json.dumps({k: summary[k] for k in ("symbol", "contracts", "snapshots", "positive_iv", "all_five_greeks", "quote_timestamp_range")}), flush=True)
    return summary


def write_csv(path, rows, fields):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def scan():
    clock = get("/v2/clock")
    save("clock_summary.json", clock)
    start = date.fromisoformat((clock["timestamp"] if clock["is_open"] else clock["next_open"])[:10])
    end = start + timedelta(days=45)
    stock_snapshots = get("/v2/stocks/snapshots", {"symbols": ",".join(SYMBOLS), "feed": "iex"}, data=True)
    save("stock_snapshots_iex.json", stock_snapshots)
    summary = {"captured_at": datetime.now(timezone.utc).isoformat(), "clock": clock,
               "expiration_gte": str(start), "expiration_lte": str(end), "days": 45,
               "stock_feed": "iex", "option_feed": "indicative", "symbols": {}, "errors": {}}
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {pool.submit(inspect_symbol, s, str(start), str(end), stock_snapshots.get(s, {})): s for s in SYMBOLS}
        for task in as_completed(tasks):
            symbol = tasks[task]
            try:
                summary["symbols"][symbol] = task.result()
            except Exception as error:
                summary["errors"][symbol] = str(error)
                print(f"{symbol}: {error}", flush=True)
    summary["positions_count"] = len(get("/v2/positions"))
    summary["open_orders_count"] = len(get("/v2/orders", {"status": "open", "limit": 500}))
    summary["account_configuration"] = get("/v2/account/configurations")
    # A read-only entitlement check; no purchase or subscription change.
    try:
        get("/v1beta1/options/snapshots/SPY", {"feed": "opra", "limit": 1,
                                              "expiration_date_gte": str(start)}, data=True)
        summary["opra_latest_access"] = "request succeeded"
    except Exception as error:
        summary["opra_latest_access"] = str(error)
    save("discovery_summary.json", summary)
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    assets = json.loads((PRIVATE / "assets.json").read_text())
    write_csv(output / "option_underlyings.csv", sorted(assets, key=lambda a: a["symbol"]),
              ["symbol", "name", "exchange", "class", "tradable", "attributes"])
    contracts = []
    for symbol in summary["symbols"]:
        contracts.extend(json.loads((PRIVATE / f"{symbol}_contracts.json").read_text()))
    write_csv(output / "option_contracts_45d.csv", sorted(contracts, key=lambda c: c["symbol"]),
              ["symbol", "underlying_symbol", "root_symbol", "expiration_date", "type", "style",
               "strike_price", "size", "tradable", "open_interest", "open_interest_date", "close_price", "close_price_date"])
    print(json.dumps({"window": [str(start), str(end)], "errors": summary["errors"],
                      "positions": summary["positions_count"], "open_orders": summary["open_orders_count"],
                      "opra_latest_access": summary["opra_latest_access"]}, indent=2), flush=True)


def probe_history():
    summary = json.loads((PRIVATE / "discovery_summary.json").read_text())
    contracts = json.loads((PRIVATE / "SPY_contracts.json").read_text())
    spot = summary["symbols"]["SPY"]["reference_price"]
    calls = [c for c in contracts if c["type"] == "call"]
    sample = min(calls, key=lambda c: (c["expiration_date"], abs(float(c["strike_price"])-spot)))
    clock_date = date.fromisoformat(summary["clock"]["timestamp"][:10])
    start = (clock_date - timedelta(days=1)).isoformat() + "T00:00:00Z"
    end = clock_date.isoformat() + "T23:59:59Z"
    result = {"symbol": sample["symbol"], "start": start, "end": end,
              "note": "Historical endpoints queried without a feed parameter; this tests historical access, not real-time OPRA entitlement."}
    prior_path = PRIVATE / "history_probe.json"
    prior = json.loads(prior_path.read_text()) if prior_path.exists() else {}
    for name, path, extra in [
        ("bars", "/v1beta1/options/bars", {"timeframe": "1Min"}),
        ("trades", "/v1beta1/options/trades", {}),
    ]:
        if (name == "bars" and all(prior.get(k) == result[k] for k in ("symbol", "start", "end"))
                and prior.get("bars", {}).get("success")):
            result["bars"] = prior["bars"]
            continue
        try:
            response = get(path, dict(symbols=sample["symbol"], start=start, end=end,
                                     limit=5, sort="desc", **extra), data=True)
            save(f"historical_{name}_sample.json", response)
            rows = (response.get(name) or {}).get(sample["symbol"], [])
            result[name] = {"success": True, "sample_rows": len(rows),
                            "timestamps": [row.get("t") for row in rows]}
        except Exception as error:
            result[name] = {"success": False, "error": str(error)}
    save("history_probe.json", result)
    print(json.dumps(result, indent=2))
