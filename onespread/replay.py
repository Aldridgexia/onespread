"""Deterministic, network-free demonstrations through the real risk/lifecycle engine."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from onespread.domain import BrokerState, Calendar, Contract, Decision, Spread
from onespread.engine import Engine, Journal

ASOF = datetime(2026, 9, 4, 14, 0, tzinfo=UTC)


def spread_at(now: datetime, *, stale: bool = False) -> Spread:
    legs = []
    for strike, bid, ask, delta in [(765, "3.00", "3.10", 0.52), (770, "1.10", "1.20", 0.34)]:
        legs.append(
            Contract.model_validate(
                {
                    "symbol": f"SPY260911C{strike * 1000:08d}",
                    "root": "SPY",
                    "underlying": "SPY",
                    "kind": "call",
                    "expiry": "2026-09-11",
                    "strike": strike,
                    "multiplier": 100,
                    "tradable": True,
                    "quote": {
                        "bid": bid,
                        "ask": ask,
                        "timestamp": now - timedelta(seconds=90 if stale else 3),
                    },
                    "greeks": {
                        "delta": delta,
                        "gamma": 0.018,
                        "theta": -0.14,
                        "vega": 0.27,
                        "rho": 0.06,
                    },
                    "iv": 0.19,
                }
            )
        )
    return Spread(long=legs[0], short=legs[1])


class ReplayBroker:
    """A fake broker, deliberately with no credential or network dependency."""

    def __init__(self) -> None:
        self.now = ASOF
        self.stale = False
        self.positions: dict[str, Decimal] = {}
        self.orders: dict[str, dict[str, Any]] = {}

    def state(self) -> BrokerState:
        return BrokerState(
            timestamp=self.now,
            is_open=True,
            next_close=ASOF + timedelta(hours=6),
            active=True,
            blocked=False,
            options_level=3,
            buying_power=Decimal(100000),
            positions=self.positions,
            open_order_ids=[],
        )

    def candidates(self, now: datetime) -> list[Spread]:
        return [spread_at(now)]

    def refresh(self, spread: Spread) -> Spread:
        return spread_at(self.now, stale=self.stale)

    def evidence(self, now: datetime) -> dict[str, Any]:
        return {
            "asof": now.isoformat(),
            "regime": "bullish",
            "synthetic": True,
            "evidence": [
                {
                    "id": "regime",
                    "timestamp": now.isoformat(),
                    "source": "Synthetic momentum fixture",
                    "return_5_bars": 0.0008,
                    "return_20_bars": 0.0017,
                    "note": "Illustrative inputs; not historical observations or an alpha claim.",
                }
            ],
            "news_scope": "No actual headlines in this deterministic replay.",
        }

    def submit(self, payload: dict) -> dict:
        cid = payload["client_order_id"]
        self.orders[cid] = {"client_order_id": cid, "status": "new", "filled_qty": "0"}
        return self.orders[cid]

    def lookup(self, client_id: str) -> dict | None:
        return self.orders.get(client_id)

    def cancel(self, order_id: str) -> None:
        raise RuntimeError("This fixture does not simulate cancellation")


class ScriptedModel:
    def decide(self, facts: dict) -> Decision:
        return Decision(
            action="propose",
            candidate_id=facts["candidates"][0]["id"],
            evidence_ids=["regime"],
            reason="The supplied 5-bar and 20-bar momentum agree. Propose the eligible bull call spread, subject to fresh quotes and account checks.",
            invalidation="Wait if direction changes, quotes age past 60 seconds, or entry debit deteriorates by more than $0.10.",
        )


def generate_replay() -> dict:
    scenarios = []
    for name, title in [
        ("entry", "Eligible entry"),
        ("veto", "Stale quote veto"),
        ("exit", "Entry to exit"),
    ]:
        with TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "replay.sqlite3")
            broker = ReplayBroker()
            calendar = Calendar(
                reviewed_at=ASOF,
                coverage_start=ASOF - timedelta(hours=1),
                coverage_end=ASOF + timedelta(hours=7),
                sources=["Synthetic fixture calendar"],
                events=[],
            )
            engine = Engine(
                broker,
                ScriptedModel(),
                journal,
                calendar=calendar,
                execute=name == "exit",
                clock=lambda: broker.now,
            )
            broker.stale = name == "veto"
            engine.run()
            if name == "exit":
                trade = journal.active()
                assert trade is not None
                cid = trade["entry_id"]
                spread = spread_at(broker.now)
                broker.orders[cid].update(
                    status="filled",
                    filled_qty="1",
                    filled_avg_price="2.00",
                    filled_at=broker.now.isoformat(),
                )
                broker.positions = {
                    spread.long.symbol: Decimal(1),
                    spread.short.symbol: Decimal(-1),
                }
                engine.run()
                broker.now += timedelta(hours=2)
                engine.run()
                active = journal.active()
                assert active is not None
                exit_id = active["exit_id"]
                broker.orders[exit_id].update(status="filled", filled_qty="1")
                broker.positions = {}
                engine.run()
            events = [
                json.loads(r[0])
                for r in journal.db.execute("SELECT payload FROM events ORDER BY seq")
            ]
            # Do not mislabel this as actual paper execution or actual GLM output.
            for event in events:
                event["mode"] = "replay"
                event["synthetic"] = True
                event.pop("client_order_id", None)
                if "order_draft" in event:
                    event["order_draft"].pop("client_order_id", None)
            scenarios.append(
                {
                    "id": name,
                    "title": title,
                    "events": events,
                    "spread": spread_at(ASOF).model_dump(mode="json"),
                }
            )
            journal.db.close()
    return {
        "source": "replay",
        "model_source": "Scripted decision; real risk engine",
        "generated_at": datetime.now(UTC).isoformat(),
        "scenarios": scenarios,
        "notice": "Synthetic quotes, scripted model decisions, and simulated fills. No broker orders or actual performance.",
    }


if __name__ == "__main__":
    print(json.dumps(generate_replay(), indent=2))
