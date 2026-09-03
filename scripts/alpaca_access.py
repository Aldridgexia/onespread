"""Read-only Alpaca discovery using the official CLI and local paper keys."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".local" / "discovery"


def credentials() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    if values.get("ALPACA_LIVE_TRADE", "false").lower() == "true":
        raise RuntimeError("Discovery requires paper mode.")
    if values.get("ALPACA_PAPER_TRADE", "true").lower() != "true":
        raise RuntimeError("Discovery requires paper mode.")
    if not all(values.get(k) for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")):
        raise RuntimeError("Complete both credentials in the local .env file.")
    env = {k: v for k, v in os.environ.items() if not k.startswith("ALPACA_")}
    env.update({k: values[k] for k in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")})
    env.update(
        ALPACA_LIVE_TRADE="false",
        ALPACA_PAPER_TRADE="true",
        ALPACA_CONFIG_DIR=str(ROOT / ".local" / "alpaca-config"),
    )
    return env


def get(path: str, params: dict | None = None, *, data: bool = False):
    """Only GET, fixed paper/data destinations, captured and redacted errors."""
    allowed = (
        "/v2/account",
        "/v2/account/configurations",
        "/v2/clock",
        "/v2/assets",
        "/v2/positions",
        "/v2/orders",
        "/v2/options/contracts",
        "/v2/stocks/snapshots",
        "/v2/stocks/quotes/latest",
        "/v1beta1/options/trades",
        "/v1beta1/options/bars",
    )
    if path not in allowed and not (
        path.startswith("/v1beta1/options/snapshots/")
        and path.rsplit("/", 1)[-1].replace(".", "").isalnum()
    ):
        raise ValueError("Endpoint is outside discovery's GET allowlist.")
    env = credentials()
    command = [str(ROOT / ".local/bin/alpaca"), "api", "GET", path, "--quiet", "--timeout", "40"]
    if params:
        command += ["--query", urlencode(params)]
    if data:
        command += ["--use-data-api"]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=160)
    if result.returncode:
        error = result.stderr
        for key in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
            error = error.replace(env[key], "[REDACTED]")
        raise RuntimeError(error.strip()[:1000])
    return json.loads(result.stdout)


def save(name: str, value):
    PRIVATE.mkdir(parents=True, exist_ok=True)
    target = PRIVATE / name
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(value, f, indent=2)
    return target


def account_summary(account):
    fields = (
        "status",
        "currency",
        "cash",
        "equity",
        "buying_power",
        "options_buying_power",
        "options_approved_level",
        "options_trading_level",
        "trading_blocked",
        "account_blocked",
        "trade_suspended_by_user",
        "created_at",
        "pattern_day_trader",
        "daytrade_count",
    )
    result = {k: account.get(k) for k in fields}
    result["account_id_suffix"] = str(account.get("id", ""))[-6:]
    result["endpoint"] = "https://paper-api.alpaca.markets"
    return result


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "account"
    if mode == "account":
        result = account_summary(get("/v2/account"))
    elif mode == "clock":
        result = get("/v2/clock")
    elif mode == "assets":
        assets = get("/v2/assets", {"status": "active", "attributes": "options_enabled"})
        save("assets.json", assets)
        result = {
            "count": len(assets),
            "tradable": sum(bool(a.get("tradable")) for a in assets),
            "sample": [
                {k: a.get(k) for k in ("symbol", "name", "exchange", "attributes")}
                for a in assets[:3]
            ],
            "selected": [
                {k: a.get(k) for k in ("symbol", "exchange", "attributes", "tradable")}
                for a in assets
                if a.get("symbol") in ("SPY", "QQQ", "IWM", "AAPL", "NVDA", "SPX", "VIX", "XSP")
            ],
        }
    elif mode == "scan":
        from discover_options import scan

        scan()
        raise SystemExit(0)
    elif mode == "history":
        from discover_options import probe_history

        probe_history()
        raise SystemExit(0)
    else:
        raise SystemExit("Use account, clock, assets, scan, or history.")
    save(mode + "_summary.json", result)
    print(json.dumps(result, indent=2))
