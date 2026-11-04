"""Deterministic USD accounting for manually imported, complete event histories.

This module records historical events only. It has no network or execution code.
Daily time-weighted returns use an explicit end-of-day external-flow convention;
they are estimates when deposits/withdrawals occur intraday. An explicit calendar
of benchmark observations is required. Non-calendar event dates are rejected
rather than silently moved to another day. Raw (not split-adjusted) closes are
required; stock splits are separate events. Currency conversion and tax-basis
accounting are outside this initial module's scope.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
EVENT_COLUMNS = ("id", "date", "account", "type", "symbol", "quantity", "price", "amount", "fee", "transfer_id")
PRICE_COLUMNS = ("date", "symbol", "close", "source", "as_of")
BENCHMARK_COLUMNS = ("date", "total_return_index", "source", "as_of")
KINDS = frozenset({"DEPOSIT", "WITHDRAWAL", "BUY", "SELL", "DIVIDEND", "INTEREST", "FEE", "TRANSFER_IN", "TRANSFER_OUT", "SPLIT"})


class DataQualityError(ValueError):
    """Safe, contextual error messages do not contain imported row contents."""


@dataclass(frozen=True)
class Event:
    id: str
    date: date
    account: str
    type: str
    symbol: str = ""
    quantity: Decimal = ZERO
    price: Decimal = ZERO
    amount: Decimal = ZERO
    fee: Decimal = ZERO
    transfer_id: str = ""


@dataclass(frozen=True)
class Price:
    date: date
    symbol: str
    close: Decimal
    source: str
    as_of: datetime


@dataclass(frozen=True)
class BenchmarkPoint:
    date: date
    total_return_index: Decimal
    source: str
    as_of: datetime


def _number(value: str, *, blank_zero: bool = False) -> Decimal:
    if value == "" and blank_zero:
        return ZERO
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise DataQualityError("Invalid decimal value.") from None
    if not result.is_finite() or result < 0 or result.adjusted() > 20 or result.as_tuple().exponent < -18:
        raise DataQualityError("Decimal must be finite, nonnegative, and within supported precision.")
    return result


def _date(value: str) -> date:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise DataQualityError("Invalid ISO calendar date.") from None


def _timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise DataQualityError("Invalid source timestamp.") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise DataQualityError("Source timestamps require an explicit time zone.")
    return result.astimezone(timezone.utc)


def _rows(path: str | Path, columns: tuple[str, ...]) -> Iterable[tuple[int, dict[str, str]]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or tuple(reader.fieldnames) != columns:
            raise DataQualityError("CSV header does not match the documented normalized schema.")
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise DataQualityError(f"Malformed CSV row at line {line}.")
            yield line, {key: value.strip() for key, value in row.items()}


def _validate_event(event: Event) -> None:
    if not event.id or len(event.id) > 128:
        raise DataQualityError("Every event requires a bounded stable identifier.")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", event.account):
        raise DataQualityError("Account must be an opaque lower-case alias, not an account number.")
    if event.type not in KINDS:
        raise DataQualityError("Unsupported event type; explicit normalization is required.")
    for value in (event.quantity, event.price, event.amount, event.fee):
        if not isinstance(value, Decimal):
            raise DataQualityError("Event amounts must use Decimal values.")
        _number(str(value))
    if event.symbol and not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", event.symbol):
        raise DataQualityError("Invalid security symbol.")
    if event.type in {"BUY", "SELL"}:
        if not event.symbol or event.quantity <= 0 or event.price <= 0 or event.amount != event.quantity * event.price:
            raise DataQualityError("Trade requires a symbol, positive quantity/price, and an exact quantity-times-price amount.")
    elif event.type == "SPLIT":
        if not event.symbol or event.quantity <= 0 or any((event.price, event.amount, event.fee)):
            raise DataQualityError("Split requires a positive share multiplier and zero dollar fields.")
    else:
        if event.quantity or event.price or event.fee or event.amount <= 0:
            raise DataQualityError("Cash event requires a positive amount and zero quantity, price, and fee fields.")
        if event.symbol and event.type != "DIVIDEND":
            raise DataQualityError("Only dividend cash events may include a symbol.")
    if event.type.startswith("TRANSFER_"):
        if not event.transfer_id:
            raise DataQualityError("Internal transfers require a pairing identifier.")
    elif event.transfer_id:
        raise DataQualityError("Transfer identifiers are only valid on transfer events.")


def _validate_events(events: list[Event]) -> None:
    if not events:
        raise DataQualityError("A complete nonempty event history is required.")
    identifiers: set[str] = set()
    transfers: dict[str, list[Event]] = {}
    last_date: date | None = None
    for event in events:
        _validate_event(event)
        if event.id in identifiers:
            raise DataQualityError("Duplicate event identifier; import rejected without partial application.")
        identifiers.add(event.id)
        if last_date is not None and event.date < last_date:
            raise DataQualityError("Events must be in chronological order; same-day order is preserved.")
        last_date = event.date
        if event.transfer_id:
            transfers.setdefault(event.transfer_id, []).append(event)
    for pair in transfers.values():
        if (len(pair) != 2 or {event.type for event in pair} != {"TRANSFER_IN", "TRANSFER_OUT"}
                or pair[0].date != pair[1].date or pair[0].amount != pair[1].amount
                or pair[0].account == pair[1].account):
            raise DataQualityError("Internal cash transfers must pair exactly on date and amount across two different accounts.")


def load_events(path: str | Path) -> list[Event]:
    """Read normalized ledger rows atomically; duplicate IDs are rejected."""
    events = []
    for line, row in _rows(path, EVENT_COLUMNS):
        try:
            events.append(Event(row["id"], _date(row["date"]), row["account"], row["type"], row["symbol"],
                                *(_number(row[key], blank_zero=True) for key in ("quantity", "price", "amount", "fee")), row["transfer_id"]))
        except DataQualityError as exc:
            raise DataQualityError(f"Event CSV line {line}: {exc}") from None
    _validate_events(events)
    return events


def load_prices(path: str | Path) -> dict[tuple[date, str], Price]:
    prices = {}
    for line, row in _rows(path, PRICE_COLUMNS):
        try:
            point = Price(_date(row["date"]), row["symbol"], _number(row["close"]), row["source"], _timestamp(row["as_of"]))
            if point.close <= 0 or not point.source or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", point.symbol):
                raise DataQualityError("Price requires a positive raw close, valid symbol, and source.")
            key = (point.date, point.symbol)
            if key in prices:
                raise DataQualityError("Duplicate price observation.")
            prices[key] = point
        except DataQualityError as exc:
            raise DataQualityError(f"Price CSV line {line}: {exc}") from None
    if not prices:
        raise DataQualityError("Price history is empty.")
    return prices


def load_benchmark(path: str | Path) -> dict[date, BenchmarkPoint]:
    points = {}
    for line, row in _rows(path, BENCHMARK_COLUMNS):
        try:
            point = BenchmarkPoint(_date(row["date"]), _number(row["total_return_index"]), row["source"], _timestamp(row["as_of"]))
            if point.total_return_index <= 0 or not point.source:
                raise DataQualityError("Benchmark requires a positive total-return index and source.")
            if point.date in points:
                raise DataQualityError("Duplicate benchmark observation.")
            points[point.date] = point
        except DataQualityError as exc:
            raise DataQualityError(f"Benchmark CSV line {line}: {exc}") from None
    if not points:
        raise DataQualityError("Benchmark history is empty.")
    return points


def _fmt(value: Decimal, places: int = 6) -> str:
    return format(value.quantize(Decimal(1).scaleb(-places)), "f")


def _money(value: Decimal) -> str:
    return _fmt(value, 2)


def _flow(event: Event, combined: bool) -> Decimal:
    if event.type == "DEPOSIT" or (not combined and event.type == "TRANSFER_IN"):
        return event.amount
    if event.type == "WITHDRAWAL" or (not combined and event.type == "TRANSFER_OUT"):
        return -event.amount
    return ZERO


def _apply(event: Event, cash: dict[str, Decimal], shares: dict[str, dict[str, Decimal]]) -> None:
    account = event.account
    if event.type in {"DEPOSIT", "TRANSFER_IN", "DIVIDEND", "INTEREST"}:
        cash[account] += event.amount
    elif event.type in {"WITHDRAWAL", "TRANSFER_OUT", "FEE"}:
        cash[account] -= event.amount
    elif event.type == "BUY":
        cash[account] -= event.amount + event.fee
        shares[account][event.symbol] = shares[account].get(event.symbol, ZERO) + event.quantity
    elif event.type == "SELL":
        shares[account][event.symbol] = shares[account].get(event.symbol, ZERO) - event.quantity
        cash[account] += event.amount - event.fee
    elif event.type == "SPLIT":
        if shares[account].get(event.symbol, ZERO) <= 0:
            raise DataQualityError("Split has no existing position.")
        shares[account][event.symbol] *= event.quantity
    if cash[account] < 0 or any(quantity < 0 for quantity in shares[account].values()):
        raise DataQualityError("Ledger creates negative cash or shares; check missing history, event ordering, or unsupported leverage.")


def _period_factor(previous: Decimal, current: Decimal, flow: Decimal) -> Decimal:
    if previous > 0:
        factor = (current - flow) / previous
    elif flow > 0:
        # A new funded segment begins at zero; first funding is treated as opening capital.
        factor = current / flow
    elif current == 0 and flow == 0:
        factor = ONE
    else:
        raise DataQualityError("Return cannot be computed from a zero-valued opening period.")
    if factor < 0:
        raise DataQualityError("End-of-day flow convention produces an invalid return; intraday valuations are required.")
    return factor


def analyze(events: list[Event], prices: dict[tuple[date, str], Price], benchmark: dict[date, BenchmarkPoint], *,
            as_of: datetime, history_complete: bool = False, max_age_days: int = 4) -> dict:
    """Return JSON-safe combined/account analytics, or fail closed on bad data.

    `history_complete=True` is an explicit caller attestation that the event history
    starts at account inception with zero balances. It is not automatically proven
    by a syntactically valid CSV. Reconcile final balances against a statement.
    `as_of` is the evaluation instant, never automatically advanced to make sample
    data appear fresh. max_age_days is calendar age of latest valuation, not a
    market-calendar guarantee. Source timestamps must be timezone-aware.
    """
    if history_complete is not True:
        raise DataQualityError("Incomplete or unconfirmed history: performance is unavailable until inception history is attested and reconciled.")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DataQualityError("Analysis timestamp requires an explicit time zone.")
    if not isinstance(max_age_days, int) or not 0 <= max_age_days <= 7:
        raise DataQualityError("Freshness threshold must be between zero and seven calendar days.")
    _validate_events(events)
    as_of = as_of.astimezone(timezone.utc)
    today = as_of.date()
    if any(event.date > today for event in events):
        raise DataQualityError("Future ledger events cannot be included in historical analysis.")
    calendar = sorted(day for day in benchmark if events[0].date <= day <= today)
    if not calendar or calendar[0] != events[0].date:
        raise DataQualityError("Benchmark calendar must cover the first event date.")
    if (today - calendar[-1]).days > max_age_days:
        raise DataQualityError("Latest valuation is stale; refresh observations before producing a current briefing.")
    if any(event.date not in calendar for event in events):
        raise DataQualityError("An event is outside the supplied valuation calendar; explicit observations are required.")
    for key, point in prices.items():
        if key != (point.date, point.symbol) or _number(str(point.close)) <= 0:
            raise DataQualityError("Invalid price observation key or value.")
    for key, point in benchmark.items():
        if key != point.date or _number(str(point.total_return_index)) <= 0:
            raise DataQualityError("Invalid benchmark observation key or value.")
    for point in list(prices.values()) + list(benchmark.values()):
        if point.as_of.tzinfo is None or point.as_of.utcoffset() is None or point.as_of > as_of or point.as_of.date() < point.date:
            raise DataQualityError("Source timestamp is invalid, future-dated, or precedes the observation date.")
        if not point.source:
            raise DataQualityError("Observation provenance is missing.")
    accounts = sorted({event.account for event in events})
    cash = {account: ZERO for account in accounts}
    shares: dict[str, dict[str, Decimal]] = {account: {} for account in accounts}
    previous = {account: ZERO for account in [*accounts, "__combined__"]}
    wealth = {account: ONE for account in previous}
    peaks = dict(wealth)
    drawdowns = {account: ZERO for account in previous}
    contributions = {account: ZERO for account in previous}
    events_by_date = {day: [] for day in calendar}
    for event in events:
        events_by_date[event.date].append(event)
    timeline = []
    account_timeline = {account: [] for account in accounts}
    benchmark_units = ZERO
    used_sources: dict[tuple[str, str], dict] = {}
    first_index = benchmark[calendar[0]].total_return_index

    with localcontext() as context:
        context.prec = 40
        for day in calendar:
            daily_flow = {account: ZERO for account in previous}
            for event in events_by_date[day]:
                _apply(event, cash, shares)
                daily_flow[event.account] += _flow(event, False)
                daily_flow["__combined__"] += _flow(event, True)
            values = {}
            for account in accounts:
                holdings_value = ZERO
                for symbol, quantity in shares[account].items():
                    if quantity == 0:
                        continue
                    point = prices.get((day, symbol))
                    if point is None or point.close <= 0:
                        raise DataQualityError("Missing or invalid held-security close on a valuation date; no forward-fill is permitted.")
                    holdings_value += quantity * point.close
                    used_sources[(point.source, point.as_of.isoformat())] = {"source": point.source, "as_of": point.as_of.isoformat()}
                values[account] = cash[account] + holdings_value
            values["__combined__"] = sum(values.values(), ZERO)
            for account in previous:
                factor = _period_factor(previous[account], values[account], daily_flow[account])
                wealth[account] *= factor
                peaks[account] = max(peaks[account], wealth[account])
                if peaks[account] > 0:
                    drawdowns[account] = min(drawdowns[account], wealth[account] / peaks[account] - ONE)
                contributions[account] += daily_flow[account]
                previous[account] = values[account]
                if account != "__combined__":
                    account_timeline[account].append({"date": day.isoformat(), "equity": _money(values[account]), "net_flow": _money(daily_flow[account]), "twr_pct": _fmt((wealth[account] - ONE) * HUNDRED)})
            point = benchmark[day]
            benchmark_units += daily_flow["__combined__"] / point.total_return_index
            if benchmark_units < 0:
                raise DataQualityError("Withdrawals exceed the hypothetical benchmark balance; a matched comparison is unavailable.")
            benchmark_value = benchmark_units * point.total_return_index
            used_sources[(point.source, point.as_of.isoformat())] = {"source": point.source, "as_of": point.as_of.isoformat()}
            timeline.append({"date": day.isoformat(), "equity": _money(values["__combined__"]), "net_flow": _money(daily_flow["__combined__"]),
                             "cumulative_contributions": _money(contributions["__combined__"]), "twr_pct": _fmt((wealth["__combined__"] - ONE) * HUNDRED),
                             "benchmark_equity": _money(benchmark_value), "benchmark_return_pct": _fmt((point.total_return_index / first_index - ONE) * HUNDRED)})

        last = calendar[-1]
        total = previous["__combined__"]
        combined_quantities: dict[str, Decimal] = {}
        account_results = []

        def holdings_for(quantities: dict[str, Decimal], equity: Decimal) -> list[dict]:
            output = []
            for symbol, quantity in quantities.items():
                if quantity <= 0:
                    continue
                point = prices[(last, symbol)]
                value = quantity * point.close
                output.append({"symbol": symbol, "quantity": _fmt(quantity, 12), "price": _fmt(point.close), "market_value": _money(value),
                               "weight_pct": _fmt(value / equity * HUNDRED) if equity else "0.000000", "price_date": last.isoformat(),
                               "source": point.source, "as_of": point.as_of.isoformat()})
            return sorted(output, key=lambda item: Decimal(item["market_value"]), reverse=True)

        for account in accounts:
            value = previous[account]
            for symbol, quantity in shares[account].items():
                combined_quantities[symbol] = combined_quantities.get(symbol, ZERO) + quantity
            account_results.append({"id": account, "equity": _money(value), "cash": _money(cash[account]), "positions_value": _money(value - cash[account]),
                                    "net_contributions": _money(contributions[account]), "gain": _money(value - contributions[account]),
                                    "twr_pct": _fmt((wealth[account] - ONE) * HUNDRED), "max_drawdown_pct": _fmt(drawdowns[account] * HUNDRED),
                                    "holdings": holdings_for(shares[account], value), "timeline": account_timeline[account]})
        total_cash = sum(cash.values(), ZERO)
        return {
            "schema_version": "1.0", "as_of": as_of.isoformat(), "valuation_date": last.isoformat(), "history_start": calendar[0].isoformat(), "currency": "USD",
            "summary": {"equity": _money(total), "cash": _money(total_cash), "positions_value": _money(total - total_cash),
                        "net_contributions": _money(contributions["__combined__"]), "gain": _money(total - contributions["__combined__"]),
                        "twr_pct": _fmt((wealth["__combined__"] - ONE) * HUNDRED), "benchmark_twr_pct": timeline[-1]["benchmark_return_pct"],
                        "benchmark_equity": _money(benchmark_value), "benchmark_excess_value": _money(total - benchmark_value),
                        "max_drawdown_pct": _fmt(drawdowns["__combined__"] * HUNDRED), "xirr_pct": None},
            "holdings": holdings_for(combined_quantities, total), "accounts": account_results, "timeline": timeline,
            "quality": {"status": "fresh", "valuation_age_days": (today - last).days, "history_attested_complete": True,
                        "broker_reconciled": False, "provenance_status": "declared_not_independently_verified", "warnings": ["History completeness is a caller attestation, not broker verification.",
                                                                  "Returns use an end-of-day external-flow convention; intraday cash flows can affect accuracy.",
                                                                  "The supplied benchmark defines the observation calendar; exchange-calendar completeness is not independently certified.",
                                                                  "XIRR is unavailable in this MVP; short periods are not annualized."]},
            "methodology": {"prices": "Raw closes; splits applied as explicit share-multiplier events.",
                            "twr": "Estimated daily time-weighted return: (ending value - external end-of-day flow) / previous ending value. Initial funding of a zero-value segment is treated as opening capital.",
                            "benchmark": "Hypothetical units bought/sold at each external-flow date using a supplied total-return index. Internal transfers cancel at combined level. No taxes or trading costs deducted from the benchmark.",
                            "drawdown": "Largest decline in the flow-adjusted return index, expressed as a negative percentage.",
                            "net_contributions": "Net external flows; per-account figures include paired internal transfers. Not an IRA tax-year contribution calculation.",
                            "taxes": "Pre-tax performance. No tax-lot, realized-gain, wash-sale, or IRA eligibility certification."},
            "sources": sorted(used_sources.values(), key=lambda item: (item["as_of"], item["source"])),
            "reconciliation": {"event_count": len(events), "account_count": len(accounts), "position_count": len([q for q in combined_quantities.values() if q > 0]),
                               "status": "statement_comparison_required"},
        }


def reconcile(analysis: dict, statement: dict, *, cash_tolerance: Decimal = Decimal("0.01"),
              quantity_tolerance: Decimal = Decimal("0.00000001")) -> dict:
    """Compare final account cash/shares with a separately obtained statement.

    Statement shape: {"valuation_date": "YYYY-MM-DD", "accounts": [
      {"id": "taxable", "cash": "123.45", "holdings": [
        {"symbol": "NOVA", "quantity": "2.5"}]}]}.

    Input remains local; no broker connection is used. A match verifies only the
    supplied endpoints, not completeness of all historical cash flows. The
    function returns a result without mutating the analytical report. Callers
    should store the statement's origin and checksum in their private store.
    """
    if cash_tolerance < 0 or quantity_tolerance < 0:
        raise DataQualityError("Reconciliation tolerances must be nonnegative.")
    if not isinstance(statement, dict) or statement.get("valuation_date") != analysis.get("valuation_date"):
        raise DataQualityError("Statement and analytical valuation dates must agree.")
    rows = statement.get("accounts")
    if not isinstance(rows, list):
        raise DataQualityError("Statement accounts must be a list.")
    actual = {row["id"]: row for row in analysis["accounts"]}
    expected = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in expected:
            raise DataQualityError("Statement account aliases must be unique.")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,30}", row["id"]):
            raise DataQualityError("Statement account must be an opaque alias.")
        if not isinstance(row.get("cash"), str) or not isinstance(row.get("holdings"), list):
            raise DataQualityError("Statement cash must be a decimal string and holdings a list.")
        cash = _number(row["cash"])
        holdings = {}
        for holding in row["holdings"]:
            if (not isinstance(holding, dict) or not isinstance(holding.get("symbol"), str)
                    or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,15}", holding["symbol"])
                    or holding["symbol"] in holdings or not isinstance(holding.get("quantity"), str)):
                raise DataQualityError("Statement holding symbols must be valid and unique, with decimal-string quantities.")
            holdings[holding["symbol"]] = _number(holding["quantity"])
        expected[row["id"]] = {"cash": cash, "holdings": holdings}
    discrepancies = []
    for account in sorted(set(actual) | set(expected)):
        if account not in actual or account not in expected:
            discrepancies.append({"account": account, "field": "account_coverage"})
            continue
        if abs(Decimal(actual[account]["cash"]) - expected[account]["cash"]) > cash_tolerance:
            discrepancies.append({"account": account, "field": "cash"})
        shares = {row["symbol"]: Decimal(row["quantity"]) for row in actual[account]["holdings"]}
        for symbol in sorted(set(shares) | set(expected[account]["holdings"])):
            if abs(shares.get(symbol, ZERO) - expected[account]["holdings"].get(symbol, ZERO)) > quantity_tolerance:
                discrepancies.append({"account": account, "field": "quantity", "symbol": symbol})
    return {"status": "matched" if not discrepancies else "mismatch", "valuation_date": analysis["valuation_date"],
            "discrepancies": discrepancies, "account_count": len(rows),
            "scope": "Cash and share endpoint comparison only; statement authenticity and historical completeness require independent checks."}
