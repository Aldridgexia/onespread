"""One paid inference against synthetic data; no Alpaca client or order submission."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from onespread.adapters import Featherless, Settings
from onespread.replay import ASOF, ReplayBroker, spread_at


def main() -> None:
    spread = spread_at(ASOF)
    facts = ReplayBroker().evidence(ASOF)
    facts["candidates"] = [
        {
            "id": spread.id,
            "kind": spread.kind,
            "debit": str(spread.debit),
            "premium_usd": str(spread.debit * 100),
            "expiry": str(spread.long.expiry),
        }
    ]
    facts["calendar_status"] = ["synthetic_fixture_clear"]
    started = time.monotonic()
    result: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "model": "zai-org/GLM-5",
        "input": "Synthetic fixture, not market observations",
        "broker_orders": 0,
    }
    try:
        result["decision"] = Featherless(Settings()).decide(facts).model_dump()
        result["valid"] = True
    except Exception as error:
        result.update(valid=False, error_type=type(error).__name__)
    result["seconds"] = round(time.monotonic() - started, 2)
    path = Path(__file__).resolve().parents[1] / "output/production_prompt_smoke.json"
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
