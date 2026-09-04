from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from onespread.adapters import Settings
from onespread.domain import BrokerState, Calendar, Contract, Decision, Spread
from onespread.engine import Engine, Journal

NOW = datetime(2026, 9, 3, 15, 0, tzinfo=UTC)


def make_spread(*, debit: str = "2.00", age: int = 5, kind: str = "call") -> Spread:
    legs = []
    for strike, bid, ask in [
        (765, "3.00", str(Decimal(debit) + 1)),
        (770 if kind == "call" else 760, "1.00", "1.10"),
    ]:
        legs.append(
            Contract.model_validate(
                {
                    "symbol": f"SPY260911{kind[0].upper()}{strike * 1000:08d}",
                    "root": "SPY",
                    "underlying": "SPY",
                    "kind": kind,
                    "expiry": "2026-09-11",
                    "strike": strike,
                    "multiplier": 100,
                    "tradable": True,
                    "quote": {"bid": bid, "ask": ask, "timestamp": NOW - timedelta(seconds=age)},
                    "greeks": {
                        "delta": 0.5 if kind == "call" else -0.5,
                        "gamma": 0.01,
                        "vega": 0.1,
                        "theta": -0.1,
                        "rho": 0.01,
                    },
                    "iv": 0.2,
                }
            )
        )
    return Spread(long=legs[0], short=legs[1])


def state(**changes: Any) -> BrokerState:
    return BrokerState.model_validate(
        {
            "timestamp": NOW,
            "is_open": True,
            "next_close": NOW + timedelta(hours=5),
            "active": True,
            "blocked": False,
            "options_level": 3,
            "buying_power": "100000",
            "positions": {},
            "open_order_ids": [],
            **changes,
        }
    )


class FakeBroker:
    def __init__(self) -> None:
        self.spread = make_spread()
        self.current = state()
        self.submissions: list[dict] = []
        self.orders: dict[str, dict] = {}
        self.time_out = False
        self.cancelled: list[str] = []

    def state(self) -> BrokerState:
        return self.current

    def candidates(self, now: datetime) -> list[Spread]:
        return [make_spread()]

    def refresh(self, spread: Spread) -> Spread:
        return self.spread

    def evidence(self, now: datetime) -> dict:
        return {
            "asof": NOW.isoformat(),
            "regime": "bullish",
            "evidence": [{"id": "regime", "timestamp": NOW.isoformat()}],
        }

    def submit(self, payload: dict) -> dict:
        self.submissions.append(payload)
        if self.time_out:
            raise TimeoutError("Simulated lost response")
        return {"client_order_id": payload["client_order_id"]}

    def lookup(self, client_id: str) -> dict | None:
        return self.orders.get(client_id)

    def cancel(self, order_id: str) -> None:
        self.cancelled.append(order_id)


class FakeModel:
    def __init__(self, broker: FakeBroker) -> None:
        self.broker = broker
        self.calls = 0
        self.after_inference: Any = lambda: None

    def decide(self, facts: dict) -> Decision:
        self.calls += 1
        self.after_inference()
        return Decision(
            action="propose",
            candidate_id=make_spread().id,
            evidence_ids=["regime"],
            reason="Fixture momentum",
            invalidation="Momentum changes",
        )


@pytest.fixture
def setup(tmp_path: Path) -> tuple[Engine, FakeBroker, FakeModel]:
    broker = FakeBroker()
    model = FakeModel(broker)
    calendar = Calendar(
        reviewed_at=NOW,
        coverage_start=NOW - timedelta(hours=1),
        coverage_end=NOW + timedelta(hours=6),
        sources=["synthetic fixture"],
        events=[],
    )
    return (
        Engine(
            broker, model, Journal(tmp_path / "journal.db"), calendar=calendar, clock=lambda: NOW
        ),
        broker,
        model,
    )


@pytest.mark.parametrize("kind", ["call", "put"])
def test_call_and_put_debits_and_credit_sign(kind: str) -> None:
    spread = make_spread(kind=kind)
    assert spread.debit * 100 == 200
    assert not spread.entry_blockers(NOW)
    exit_order = spread.order("exit-fixture", closing=True)
    assert Decimal(exit_order["limit_price"]) == Decimal("-1.90")
    assert [leg["position_intent"] for leg in exit_order["legs"]] == [
        "sell_to_close",
        "buy_to_close",
    ]


@pytest.mark.parametrize("age", [61, -1])
def test_stale_and_future_quotes(age: int) -> None:
    assert "stale_or_future_option_quote" in make_spread(age=age).entry_blockers(NOW)


def test_multiplier_budget_and_metadata() -> None:
    assert "debit_exceeds_policy" in make_spread(debit="3.01").entry_blockers(NOW)
    values = make_spread().long.model_dump()
    values["multiplier"] = 10
    with pytest.raises(ValidationError):
        Contract.model_validate(values)
    values = make_spread().model_dump()
    values["short"]["expiry"] = "2026-09-18"
    with pytest.raises(ValidationError):
        Spread.model_validate(values)


def test_dry_run_does_not_reserve_or_submit(setup: tuple) -> None:
    engine, broker, _ = setup
    assert engine.run()["action"] == "DRY_RUN_PROPOSAL"
    assert not broker.submissions and not engine.journal.active()


@pytest.mark.parametrize(
    "change,reason",
    [
        ("quote", "stale_or_future_option_quote"),
        ("price", "price_moved_more_than_10_cents"),
        ("position", "existing_exposure_or_pending_order"),
    ],
)
def test_inference_cannot_bypass_refresh(setup: tuple, change: str, reason: str) -> None:
    engine, broker, model = setup

    def mutate() -> None:
        if change == "quote":
            broker.spread = make_spread(age=61)
        elif change == "price":
            broker.spread = make_spread(debit="2.50")
        else:
            broker.current = state(positions={"SPY": "1"})

    model.after_inference = mutate
    engine.execute = True
    assert reason in engine.run()["reasons"]
    assert not broker.submissions


def test_missing_calendar_blocks_entry(setup: tuple) -> None:
    engine, broker, _ = setup
    engine.calendar = None
    engine.execute = True
    assert "event_calendar_missing" in engine.run()["reasons"]
    assert not broker.submissions


def test_closed_market_does_not_spend_model_credit(setup: tuple) -> None:
    engine, broker, model = setup
    broker.current = state(is_open=False)
    assert "market_closed" in engine.run()["reasons"]
    assert model.calls == 0


def test_timeout_survives_restart_without_duplicate_post(setup: tuple) -> None:
    engine, broker, model = setup
    engine.execute = True
    broker.time_out = True
    assert engine.run()["action"] == "WAIT"
    assert engine.journal.active()["phase"] == "entry_unknown"
    restarted = Engine(broker, model, engine.journal, execute=True, clock=lambda: NOW)
    for _ in range(3):
        assert restarted.run()["action"] == "ATTENTION"
    assert len(broker.submissions) == 1


def test_full_owned_spread_lifecycle_and_daily_limit(setup: tuple) -> None:
    engine, broker, _ = setup
    engine.execute = True
    assert engine.run()["action"] == "ENTRY_SUBMITTED"
    trade = engine.journal.active()
    cid = trade["entry_id"]
    broker.orders[cid] = {
        "id": "entry-broker-id",
        "client_order_id": cid,
        "status": "filled",
        "filled_qty": "1",
        "filled_avg_price": "2.00",
        "filled_at": (NOW - timedelta(hours=2)).isoformat(),
    }
    broker.current = state(
        positions={broker.spread.long.symbol: "1", broker.spread.short.symbol: "-1"}
    )
    assert engine.run()["action"] == "EXIT_SUBMITTED"
    exit_id = engine.journal.active()["exit_id"]
    broker.orders[exit_id] = {"client_order_id": exit_id, "status": "filled", "filled_qty": "1"}
    assert engine.run()["action"] == "ATTENTION"  # Fill alone does not establish flatness.
    broker.current = state()
    assert engine.run()["action"] == "CLOSED"
    assert "daily_entry_attempt_limit" in engine.run()["reasons"]
    assert len(broker.submissions) == 2


def test_rejection_and_partial_fill_fail_closed(setup: tuple) -> None:
    engine, broker, _ = setup
    engine.execute = True
    engine.run()
    cid = engine.journal.active()["entry_id"]
    broker.orders[cid] = {"client_order_id": cid, "status": "canceled", "filled_qty": "0.5"}
    assert engine.run()["action"] == "ATTENTION"
    assert engine.journal.active()
    broker.orders[cid]["filled_qty"] = "0"
    broker.orders[cid]["status"] = "rejected"
    assert engine.run()["action"] == "ENTRY_ENDED"
    assert "daily_entry_attempt_limit" in engine.run()["reasons"]


def test_cancel_acknowledgement_does_not_unlock_entry(setup: tuple) -> None:
    engine, broker, _ = setup
    engine.execute = True
    engine.run()
    cid = engine.journal.active()["entry_id"]
    broker.orders[cid] = {
        "id": "broker-id",
        "client_order_id": cid,
        "status": "new",
        "filled_qty": "0",
    }
    engine.clock = lambda: NOW + timedelta(seconds=121)
    assert engine.run()["action"] == "CANCEL_REQUESTED"
    assert engine.run()["action"] == "PENDING"
    assert len(broker.cancelled) == 1 and len(broker.submissions) == 1


@pytest.mark.parametrize(
    "body",
    [
        '{"action":"wait"}',
        '"action":"wait"}',
        '{"action":"wait","candidate_id":"invented","evidence_ids":["regime"],"reason":"x","invalidation":"x"}',
    ],
)
def test_malformed_model_output_is_rejected(body: str) -> None:
    with pytest.raises(ValidationError):
        Decision.model_validate_json(body)


def test_live_configuration_rejected(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("ALPACA_LIVE_TRADE=true\nALPACA_API_KEY=fake\nALPACA_SECRET_KEY=fake\n")
    with pytest.raises(ValueError, match="paper mode"):
        Settings(env)
