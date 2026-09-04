"""Durable order intents, conservative reconciliation, and one bounded decision cycle."""

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from onespread.domain import NY, BrokerState, Calendar, Decision, Spread

Json = dict[str, Any]


class Broker(Protocol):
    def state(self) -> BrokerState: ...
    def candidates(self, now: datetime) -> list[Spread]: ...
    def refresh(self, spread: Spread) -> Spread: ...
    def evidence(self, now: datetime) -> Json: ...
    def submit(self, payload: Json) -> Json: ...
    def lookup(self, client_id: str) -> Json | None: ...
    def cancel(self, order_id: str) -> None: ...


class Model(Protocol):
    def decide(self, facts: Json) -> Decision: ...


class Journal:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY, day TEXT UNIQUE NOT NULL, active INTEGER NOT NULL,
                phase TEXT NOT NULL, spread TEXT NOT NULL, entry_id TEXT NOT NULL,
                exit_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_trade ON trades(active) WHERE active=1;
        """)

    def record(self, report: Json, now: datetime) -> Json:
        value = {"timestamp": now.isoformat(), **report}
        with self.db:
            self.db.execute(
                "INSERT INTO events(timestamp,payload) VALUES (?,?)",
                (now.isoformat(), json.dumps(value)),
            )
        return value

    def active(self) -> Json | None:
        row = self.db.execute("SELECT * FROM trades WHERE active=1").fetchone()
        return dict(row) if row else None

    def attempted_today(self, now: datetime) -> bool:
        return (
            self.db.execute(
                "SELECT 1 FROM trades WHERE day=?", (str(now.astimezone(NY).date()),)
            ).fetchone()
            is not None
        )

    def reserve(self, spread: Spread, now: datetime) -> str:
        cid = "os-" + uuid4().hex[:24]
        with self.db:
            self.db.execute(
                "INSERT INTO trades VALUES (?,?,1,?,?,?,NULL,?,?)",
                (
                    cid,
                    str(now.astimezone(NY).date()),
                    "entry_unknown",
                    spread.model_dump_json(),
                    cid,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return cid

    def update(
        self,
        trade_id: str,
        phase: str,
        now: datetime,
        *,
        active: bool = True,
        exit_id: str | None = None,
    ) -> None:
        with self.db:
            self.db.execute(
                "UPDATE trades SET phase=?,active=?,updated_at=?,exit_id=COALESCE(?,exit_id) WHERE id=?",
                (phase, int(active), now.isoformat(), exit_id, trade_id),
            )


class Engine:
    def __init__(
        self,
        broker: Broker,
        model: Model,
        journal: Journal,
        *,
        calendar: Calendar | None = None,
        execute: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.broker, self.model, self.journal = broker, model, journal
        self.calendar, self.execute, self.clock = calendar, execute, clock

    def report(self, action: str, reasons: list[str], **details: Any) -> Json:
        return self.journal.record(
            {
                "action": action,
                "reasons": reasons,
                "mode": "paper" if self.execute else "dry_run",
                "feed": "indicative",
                **details,
            },
            self.clock(),
        )

    def calendar_blockers(self) -> list[str]:
        return self.calendar.blockers(self.clock()) if self.calendar else ["event_calendar_missing"]

    def run(self) -> Json:
        # Every exception is a recorded no-new-entry result. Never log exception bodies or secrets.
        try:
            active = self.journal.active()
            if active:
                return self.manage(active)
            return self.entry()
        except Exception as error:
            return self.report("WAIT", ["cycle_failed_closed"], error_type=type(error).__name__)

    def entry(self) -> Json:
        state = self.broker.state()
        blockers = state.entry_blockers(self.clock())
        if self.journal.attempted_today(self.clock()):
            blockers.append("daily_entry_attempt_limit")
        if self.execute:
            blockers += self.calendar_blockers()
        if blockers:
            return self.report("WAIT", blockers)
        candidates = self.broker.candidates(self.clock())
        if not candidates:
            return self.report("WAIT", ["no_fresh_eligible_spread"])
        facts = self.broker.evidence(self.clock())
        facts["candidates"] = [
            {
                "id": s.id,
                "kind": s.kind,
                "debit": str(s.debit),
                "premium_usd": str(s.debit * 100),
                "expiry": str(s.long.expiry),
            }
            for s in candidates
        ]
        facts["calendar_status"] = self.calendar_blockers() or ["reviewed_and_clear"]
        decision = self.model.decide(facts)
        detail = {"decision": decision.model_dump(), "evidence": facts}
        if decision.action == "wait":
            return self.report("WAIT", ["model_abstained"], **detail)
        chosen = next((s for s in candidates if s.id == decision.candidate_id), None)
        expected = {"bullish": "bull_call", "bearish": "bear_put"}.get(facts["regime"])
        if chosen is None or chosen.kind != expected:
            return self.report("WAIT", ["invalid_model_selection"], **detail)
        # Recheck public context and reprice AFTER inference. Never reuse its quoted order price.
        refreshed_facts = self.broker.evidence(self.clock())
        old_news = {(e["id"], e["timestamp"]) for e in facts["evidence"] if e["id"] != "regime"}
        new_news = {
            (e["id"], e["timestamp"]) for e in refreshed_facts["evidence"] if e["id"] != "regime"
        }
        if refreshed_facts["regime"] != facts["regime"] or new_news != old_news:
            return self.report("WAIT", ["context_changed_during_inference"], **detail)
        refreshed = self.broker.refresh(chosen)
        state = self.broker.state()
        now = self.clock()
        blockers = state.entry_blockers(now) + refreshed.entry_blockers(now)
        if (now - datetime.fromisoformat(facts["asof"])).total_seconds() > 120:
            blockers.append("decision_expired")
        if refreshed.debit > chosen.debit + Decimal("0.10"):
            blockers.append("price_moved_more_than_10_cents")
        if state.buying_power < refreshed.debit * 100:
            blockers.append("insufficient_options_buying_power")
        calendar_blockers = self.calendar_blockers()
        if blockers or calendar_blockers:
            return self.report(
                "WAIT",
                blockers + calendar_blockers,
                refreshed_premium_usd=str(refreshed.debit * 100),
                **detail,
            )
        if not self.execute:
            return self.report(
                "DRY_RUN_PROPOSAL",
                ["paper_execution_not_enabled"],
                order_draft=refreshed.order("dry-run-" + chosen.id),
                **detail,
            )
        # Commit intent before touching the network. A crash or timeout leaves a blocking record.
        cid = self.journal.reserve(refreshed, now)
        self.journal.record({"action": "ENTRY_INTENT", "client_order_id": cid, **detail}, now)
        acknowledgement = self.broker.submit(refreshed.order(cid))
        if acknowledgement.get("client_order_id") != cid:
            raise ValueError("Order acknowledgement identity mismatch")
        self.journal.update(cid, "entry_pending", self.clock())
        return self.report("ENTRY_SUBMITTED", ["await_broker_fill"], client_order_id=cid)

    def manage(self, trade: Json) -> Json:
        now = self.clock()
        closing = trade["exit_id"] is not None
        cid = trade["exit_id"] if closing else trade["entry_id"]
        order = self.broker.lookup(cid)
        if order is None:
            # 404 is not evidence that a timed-out POST was never accepted. Never re-POST.
            return self.report("ATTENTION", ["order_acceptance_unresolved"], client_order_id=cid)
        if order.get("client_order_id") != cid:
            raise ValueError("Reconciliation identity mismatch")
        status = order["status"]
        state = self.broker.state()
        filled = Decimal(order["filled_qty"])
        terminal = status in {"canceled", "expired", "rejected"}
        if terminal and filled == 0 and not closing:
            if state.positions or state.open_order_ids:
                return self.report("ATTENTION", ["unexpected_exposure_after_terminal_entry"])
            self.journal.update(trade["id"], status, now, active=False)
            return self.report("ENTRY_ENDED", [status])
        if closing and status == "filled" and filled == 1:
            if state.positions or state.open_order_ids:
                return self.report("ATTENTION", ["exit_fill_requires_flat_account_confirmation"])
            self.journal.update(trade["id"], "closed", now, active=False)
            return self.report("CLOSED", ["exit_filled_and_account_flat"])
        if status != "filled":
            if terminal or filled != 0:
                return self.report("ATTENTION", ["partial_or_terminal_order_requires_review"])
            age = (now - datetime.fromisoformat(trade["updated_at"])).total_seconds()
            if age >= 120 and "cancel_requested" not in trade["phase"]:
                if not self.execute:
                    return self.report("DRY_RUN_CANCEL", ["order_older_than_120_seconds"])
                # Mark before DELETE; even a lost response remains in reconciliation.
                self.journal.update(trade["id"], "cancel_requested", now)
                self.broker.cancel(order["id"])
                return self.report("CANCEL_REQUESTED", ["await_broker_cancellation"])
            return self.report("PENDING", [status])
        if filled != 1:
            return self.report("ATTENTION", ["unexpected_fill_quantity"])
        if closing:
            return self.report("ATTENTION", ["unresolved_exit"])
        original = Spread.model_validate_json(trade["spread"])
        expected_positions = {original.long.symbol: Decimal(1), original.short.symbol: Decimal(-1)}
        if state.positions != expected_positions or state.open_order_ids:
            return self.report("ATTENTION", ["account_does_not_match_owned_spread"])
        if not state.is_open or not 0 <= (now - state.timestamp).total_seconds() <= 30:
            return self.report("ATTENTION", ["cannot_exit_with_closed_or_stale_market"])
        spread = self.broker.refresh(original)
        state = self.broker.state()
        now = self.clock()
        if (
            state.positions != expected_positions
            or state.open_order_ids
            or not state.is_open
            or not 0 <= (now - state.timestamp).total_seconds() <= 30
        ):
            return self.report("ATTENTION", ["account_changed_before_exit"])
        blockers = spread.quote_blockers(self.clock())
        if blockers:
            return self.report("ATTENTION", blockers)
        entry_price = Decimal(order["filled_avg_price"])
        held = (
            now - datetime.fromisoformat(order["filled_at"].replace("Z", "+00:00"))
        ).total_seconds()
        should_exit = (
            (state.next_close - now).total_seconds() <= 1800
            or held >= 7200
            or spread.credit >= entry_price * Decimal("1.30")
            or spread.credit <= entry_price * Decimal("0.75")
        )
        if not should_exit:
            return self.report(
                "HOLD", ["exit_threshold_not_reached"], indicative_exit_credit=str(spread.credit)
            )
        if not Decimal(0) < spread.credit <= 5:
            return self.report("ATTENTION", ["no_positive_executable_credit_estimate"])
        if not self.execute:
            return self.report(
                "DRY_RUN_EXIT",
                ["exit_threshold_reached"],
                order_draft=spread.order("dry-exit", closing=True),
            )
        exit_id = "os-exit-" + uuid4().hex[:24]
        self.journal.update(trade["id"], "exit_unknown", self.clock(), exit_id=exit_id)
        ack = self.broker.submit(spread.order(exit_id, closing=True))
        if ack.get("client_order_id") != exit_id:
            raise ValueError("Exit acknowledgement identity mismatch")
        self.journal.update(trade["id"], "exit_pending", self.clock())
        return self.report("EXIT_SUBMITTED", ["await_broker_fill"], client_order_id=exit_id)
