"""Validated domain objects and deterministic risk policy."""

import hashlib
from datetime import date, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Literal, Self
from zoneinfo import ZoneInfo

from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

NY = ZoneInfo("America/New_York")
CENT = Decimal("0.01")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Quote(Record):
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)
    timestamp: AwareDatetime

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.ask < self.bid:
            raise ValueError("Crossed quote")
        return self

    def fresh(self, now: datetime) -> bool:
        return 0 <= (now - self.timestamp).total_seconds() <= 60


class Greeks(Record):
    delta: float = Field(ge=-1, le=1)
    gamma: float
    theta: float
    vega: float
    rho: float


class Contract(Record):
    symbol: str
    root: Literal["SPY"]
    underlying: Literal["SPY"]
    kind: Literal["call", "put"]
    expiry: date
    strike: Decimal = Field(gt=0)
    multiplier: Literal[100]
    tradable: Literal[True]
    quote: Quote
    greeks: Greeks
    iv: float = Field(gt=0)


class Spread(Record):
    long: Contract
    short: Contract

    @model_validator(mode="after")
    def vertical(self) -> Self:
        long, short = self.long, self.short
        width = short.strike - long.strike if long.kind == "call" else long.strike - short.strike
        if long.kind != short.kind or long.expiry != short.expiry or width != 5:
            raise ValueError("Only five-point debit verticals are allowed")
        # Verify OCC identity against metadata, including the unadjusted SPY root.
        for leg in (long, short):
            expected = f"SPY{leg.expiry:%y%m%d}{leg.kind[0].upper()}{int(leg.strike * 1000):08d}"
            if leg.symbol != expected or leg.strike * 1000 != int(leg.strike * 1000):
                raise ValueError("Contract metadata does not match OCC symbol")
        return self

    @property
    def id(self) -> str:
        return hashlib.sha256(f"{self.long.symbol}:{self.short.symbol}".encode()).hexdigest()[:16]

    @property
    def kind(self) -> str:
        return "bull_call" if self.long.kind == "call" else "bear_put"

    @property
    def debit(self) -> Decimal:
        return (self.long.quote.ask - self.short.quote.bid).quantize(CENT, rounding=ROUND_CEILING)

    @property
    def credit(self) -> Decimal:
        return (self.long.quote.bid - self.short.quote.ask).quantize(CENT, rounding=ROUND_FLOOR)

    def quote_blockers(self, now: datetime) -> list[str]:
        if not all(leg.quote.fresh(now) for leg in (self.long, self.short)):
            return ["stale_or_future_option_quote"]
        if abs((self.long.quote.timestamp - self.short.quote.timestamp).total_seconds()) > 10:
            return ["unsynchronized_option_quotes"]
        return []

    def entry_blockers(self, now: datetime) -> list[str]:
        reasons = self.quote_blockers(now)
        if not 7 <= (self.long.expiry - now.astimezone(NY).date()).days <= 14:
            reasons.append("expiry_outside_7_to_14_days")
        if not Decimal(0) < self.debit < 5 or self.debit * 100 > 300:
            reasons.append("debit_exceeds_policy")
        if not 0.40 <= abs(self.long.greeks.delta) <= 0.65:
            reasons.append("long_delta_outside_policy")
        return reasons

    def order(self, client_id: str, *, closing: bool = False) -> dict:
        # SDK specifies positive net debit and negative net credit for MLeg limits.
        payload = {
            "client_order_id": client_id,
            "order_class": "mleg",
            "qty": "1",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": str(-self.credit if closing else self.debit),
            "legs": [
                {
                    "symbol": self.long.symbol,
                    "ratio_qty": "1",
                    "side": "sell" if closing else "buy",
                    "position_intent": "sell_to_close" if closing else "buy_to_open",
                },
                {
                    "symbol": self.short.symbol,
                    "ratio_qty": "1",
                    "side": "buy" if closing else "sell",
                    "position_intent": "buy_to_close" if closing else "sell_to_open",
                },
            ],
        }
        # The SDK's before-validator expects already-constructed leg request objects.
        LimitOrderRequest.model_validate(
            {**payload, "legs": [OptionLegRequest.model_validate(leg) for leg in payload["legs"]]}
        )
        return payload


class BrokerState(Record):
    timestamp: AwareDatetime
    is_open: bool
    next_close: AwareDatetime
    active: bool
    blocked: bool
    options_level: int
    buying_power: Decimal = Field(ge=0)
    positions: dict[str, Decimal]
    open_order_ids: list[str]

    def entry_blockers(self, now: datetime) -> list[str]:
        reasons = []
        if not 0 <= (now - self.timestamp).total_seconds() <= 30:
            reasons.append("broker_state_requires_refresh")
        if not self.is_open:
            reasons.append("market_closed")
        if (self.next_close - now).total_seconds() <= 3600:
            reasons.append("no_entry_in_final_hour")
        if not self.active or self.blocked or self.options_level < 3:
            reasons.append("account_not_eligible")
        if self.positions or self.open_order_ids:
            reasons.append("existing_exposure_or_pending_order")
        return reasons


class Decision(Record):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    action: Literal["propose", "wait"]
    candidate_id: str | None
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=1, max_length=600)
    invalidation: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.action == "propose") != (self.candidate_id is not None):
            raise ValueError("Action and candidate ID disagree")
        return self


class Event(Record):
    timestamp: AwareDatetime
    title: str
    source: str


class Calendar(Record):
    """Operator-reviewed macro calendar. News alone cannot establish event absence."""

    reviewed_at: AwareDatetime
    coverage_start: AwareDatetime
    coverage_end: AwareDatetime
    sources: list[str] = Field(min_length=1)
    events: list[Event]

    def blockers(self, now: datetime) -> list[str]:
        if not self.coverage_start <= now <= self.coverage_end:
            return ["event_calendar_outside_coverage"]
        if not 0 <= (now - self.reviewed_at).total_seconds() <= 86400:
            return ["event_calendar_review_expired"]
        if any(abs((event.timestamp - now).total_seconds()) <= 1800 for event in self.events):
            return ["major_event_within_30_minutes"]
        return []
