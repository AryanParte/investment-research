"""Mock-only policy kernel for an internal scheduled collector facade.

This is not an authenticated gateway, live proxy, broker wire protocol, or proof
of independent isolation. It contains no transport, credentials, adapter, or
production enablement. Injected fixture methods are a local testing contract.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Callable, Protocol


class MockReadUpstream(Protocol):
    """Separate fixture reads; intentionally no generic call or request method.

    Fixture timestamps describe captured data, not the current evaluation time.
    For transactions, input `complete` asserts only that the one requested page
    is fully populated. The kernel separately marks multi-page windows partial;
    no page ever establishes complete inception history.
    """

    def read_accounts(self) -> dict: ...
    def read_balances(self, account_alias: str) -> dict: ...
    def read_holdings(self, account_alias: str) -> dict: ...
    def read_transactions(self, account_alias: str, start_date: date, end_date: date,
                          page: int, page_size: int) -> dict: ...


OPERATIONS = frozenset({"read_accounts", "read_balances", "read_holdings", "read_transactions"})
MAX_AGE = timedelta(hours=96)
MAX_PAGE_SIZE = 100
MAX_PAGES = 1000
MAX_HOLDINGS = 500
MESSAGES = {
    "REQUEST_DENIED": "This request is outside the fixed mock read contract.",
    "FIXTURE_INVALID": "The fixture failed its allowed-field or consistency checks.",
    "FIXTURE_STALE": "The fixture timestamp is stale or in the future.",
    "FIXTURE_INCOMPLETE": "The fixture does not contain the required complete response.",
    "UPSTREAM_UNAVAILABLE": "The injected fixture read did not complete.",
}


class _Blocked(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(MESSAGES[code])


def _keys(value: object, expected: set[str], code: str = "FIXTURE_INVALID") -> dict:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != expected:
        raise _Blocked(code)
    return value


def _alias(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,23}", value):
        raise _Blocked("FIXTURE_INVALID")
    return value


def _integer(value: object, minimum: int, maximum: int, code: str = "FIXTURE_INVALID") -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _Blocked(code)
    return value


def _number(value: object, *, signed: bool = False) -> Decimal:
    # No floats, exponents, NaN, Infinity, or arbitrarily large precision.
    if type(value) is not str or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,12})?", value):
        raise _Blocked("FIXTURE_INVALID")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise _Blocked("FIXTURE_INVALID") from None
    if not result.is_finite() or abs(result) > Decimal("1000000000000") or (not signed and result < 0):
        raise _Blocked("FIXTURE_INVALID")
    return result


def _date(value: object, code: str = "FIXTURE_INVALID") -> date:
    if type(value) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise _Blocked(code)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _Blocked(code) from None


def _time(value: object) -> datetime:
    if type(value) is not str or len(value) > 40:
        raise _Blocked("FIXTURE_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise _Blocked("FIXTURE_INVALID") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise _Blocked("FIXTURE_INVALID")
    return result.astimezone(timezone.utc)


def _symbol(value: object) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,14}", value):
        raise _Blocked("FIXTURE_INVALID")
    return value


class MockReadGateway:
    """Deny-by-default validation over injected synthetic fixture methods.

    account_aliases is configured by the trusted test harness, never by request
    arguments. This class does not authenticate that harness or enforce process
    isolation. A separately controlled production implementation remains absent.
    """

    def __init__(self, upstream: MockReadUpstream, *, account_aliases: frozenset[str],
                 clock: Callable[[], datetime] | None = None):
        if type(account_aliases) is not frozenset or not 1 <= len(account_aliases) <= 20:
            raise ValueError("A fixed nonempty fixture account scope is required")
        try:
            for alias in account_aliases:
                _alias(alias)
        except _Blocked:
            raise ValueError("Invalid fixture account scope") from None
        self._upstream = upstream
        self._account_aliases = account_aliases
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _arguments(self, operation: object, arguments: object, now: datetime) -> dict:
        if type(operation) is not str or operation not in OPERATIONS:
            raise _Blocked("REQUEST_DENIED")
        expected = set() if operation == "read_accounts" else {"account_alias"}
        if operation == "read_transactions":
            expected |= {"start_date", "end_date", "page", "page_size"}
        values = _keys(arguments, expected, "REQUEST_DENIED").copy()
        if "account_alias" in values and (type(values["account_alias"]) is not str or values["account_alias"] not in self._account_aliases):
            raise _Blocked("REQUEST_DENIED")
        if operation == "read_transactions":
            start = _date(values["start_date"], "REQUEST_DENIED")
            end = _date(values["end_date"], "REQUEST_DENIED")
            if start > end or end > now.date() or (end - start).days > 366:
                raise _Blocked("REQUEST_DENIED")
            values.update(start_date=start, end_date=end)
            _integer(values["page"], 1, MAX_PAGES, "REQUEST_DENIED")
            _integer(values["page_size"], 1, MAX_PAGE_SIZE, "REQUEST_DENIED")
        return values

    def _read_fixture(self, operation: str, args: dict) -> dict:
        # Explicit branches, not getattr/call/HTTP/MCP passthrough.
        try:
            if operation == "read_accounts":
                return self._upstream.read_accounts()
            if operation == "read_balances":
                return self._upstream.read_balances(args["account_alias"])
            if operation == "read_holdings":
                return self._upstream.read_holdings(args["account_alias"])
            if operation == "read_transactions":
                return self._upstream.read_transactions(args["account_alias"], args["start_date"], args["end_date"], args["page"], args["page_size"])
        except Exception:
            raise _Blocked("UPSTREAM_UNAVAILABLE") from None
        raise _Blocked("REQUEST_DENIED")

    def _validate(self, operation: str, raw: object, args: dict, now: datetime) -> dict:
        fields = {"as_of", "currency", "complete"}
        fields |= ({"accounts"} if operation == "read_accounts" else {"account_alias"})
        fields |= {"read_accounts": set(), "read_balances": {"cash", "positions_value", "equity"},
                   "read_holdings": {"holdings", "total_market_value"},
                   "read_transactions": {"start_date", "end_date", "page", "page_size", "total_count", "transactions"}}[operation]
        data = _keys(raw, fields)
        as_of = _time(data["as_of"])
        if as_of > now or now - as_of > MAX_AGE:
            raise _Blocked("FIXTURE_STALE")
        if data["currency"] != "USD":
            raise _Blocked("FIXTURE_INVALID")
        if data["complete"] is not True:
            raise _Blocked("FIXTURE_INCOMPLETE")
        clean = {"as_of": as_of.isoformat(), "currency": "USD", "complete": True}
        if operation != "read_accounts":
            if type(data["account_alias"]) is not str or data["account_alias"] != args["account_alias"]:
                raise _Blocked("FIXTURE_INVALID")
            clean["account_alias"] = data["account_alias"]
        if operation == "read_accounts":
            rows = data["accounts"]
            if type(rows) is not list or len(rows) > 20:
                raise _Blocked("FIXTURE_INVALID")
            accounts, seen = [], set()
            for row in rows:
                row = _keys(row, {"alias", "type"})
                alias = _alias(row["alias"])
                if alias not in self._account_aliases or alias in seen or row["type"] not in ("taxable", "roth_ira", "traditional_ira"):
                    raise _Blocked("FIXTURE_INVALID")
                seen.add(alias)
                accounts.append({"alias": alias, "type": row["type"]})
            if seen != self._account_aliases:
                raise _Blocked("FIXTURE_INCOMPLETE")
            clean["accounts"] = accounts
        elif operation == "read_balances":
            values = {field: _number(data[field]) for field in ("cash", "positions_value", "equity")}
            if abs(values["cash"] + values["positions_value"] - values["equity"]) > Decimal("0.01"):
                raise _Blocked("FIXTURE_INVALID")
            clean.update({field: str(value) for field, value in values.items()})
        elif operation == "read_holdings":
            rows = data["holdings"]
            if type(rows) is not list or len(rows) > MAX_HOLDINGS:
                raise _Blocked("FIXTURE_INVALID")
            holdings, seen, total = [], set(), Decimal(0)
            for row in rows:
                row = _keys(row, {"symbol", "quantity", "price", "market_value", "price_as_of"})
                symbol = _symbol(row["symbol"])
                values = {field: _number(row[field]) for field in ("quantity", "price", "market_value")}
                marked = _time(row["price_as_of"])
                if (symbol in seen or values["quantity"] <= 0 or values["price"] <= 0
                        or abs(values["quantity"] * values["price"] - values["market_value"]) > Decimal("0.01")):
                    raise _Blocked("FIXTURE_INVALID")
                if marked > as_of or now - marked > MAX_AGE:
                    raise _Blocked("FIXTURE_STALE")
                seen.add(symbol)
                total += values["market_value"]
                holdings.append({"symbol": symbol, "price_as_of": marked.isoformat(), **{key: str(value) for key, value in values.items()}})
            if abs(total - _number(data["total_market_value"])) > Decimal("0.01"):
                raise _Blocked("FIXTURE_INVALID")
            clean.update(holdings=holdings, total_market_value=str(total))
        else:
            clean.update(self._transactions(data, args, as_of))
        return clean

    def _transactions(self, data: dict, args: dict, as_of: datetime) -> dict:
        if args["end_date"] > as_of.date():
            raise _Blocked("FIXTURE_INCOMPLETE")
        for field in ("start_date", "end_date"):
            if _date(data[field]) != args[field]:
                raise _Blocked("FIXTURE_INVALID")
        for field, maximum in (("page", MAX_PAGES), ("page_size", MAX_PAGE_SIZE)):
            if _integer(data[field], 1, maximum) != args[field]:
                raise _Blocked("FIXTURE_INVALID")
        total = _integer(data["total_count"], 0, MAX_PAGES * MAX_PAGE_SIZE)
        pages = max(1, (total + args["page_size"] - 1) // args["page_size"])
        if pages > MAX_PAGES or args["page"] > pages:
            raise _Blocked("FIXTURE_INVALID")
        rows = data["transactions"]
        expected = min(args["page_size"], max(0, total - (args["page"] - 1) * args["page_size"]))
        if type(rows) is not list or len(rows) != expected:
            raise _Blocked("FIXTURE_INCOMPLETE")
        transactions, seen = [], set()
        kinds = {"BUY", "SELL", "DIVIDEND", "INTEREST", "FEE", "DEPOSIT", "WITHDRAWAL", "TRANSFER_IN", "TRANSFER_OUT"}
        for row in rows:
            row = _keys(row, {"fixture_id", "occurred_at", "kind", "symbol", "quantity", "amount", "fee"})
            identifier = row["fixture_id"]
            if type(identifier) is not str or not re.fullmatch(r"fixture-[a-z0-9_-]{1,48}", identifier) or identifier in seen:
                raise _Blocked("FIXTURE_INVALID")
            seen.add(identifier)
            occurred = _time(row["occurred_at"])
            if not args["start_date"] <= occurred.date() <= args["end_date"] or occurred > as_of:
                raise _Blocked("FIXTURE_INVALID")
            if type(row["kind"]) is not str or row["kind"] not in kinds:
                raise _Blocked("FIXTURE_INVALID")
            symbol = None if row["symbol"] is None else _symbol(row["symbol"])
            quantity, amount, fee = _number(row["quantity"]), _number(row["amount"], signed=True), _number(row["fee"])
            if row["kind"] in {"BUY", "SELL"} and (symbol is None or quantity <= 0):
                raise _Blocked("FIXTURE_INVALID")
            transactions.append({"fixture_id": identifier, "occurred_at": occurred.isoformat(), "kind": row["kind"],
                                 "symbol": symbol, "quantity": str(quantity), "amount": str(amount), "fee": str(fee)})
        return {"start_date": args["start_date"].isoformat(), "end_date": args["end_date"].isoformat(),
                "transactions": transactions, "complete": pages == 1,
                "pagination": {"page": args["page"], "page_size": args["page_size"], "total_count": total,
                               "total_pages": pages, "has_more": args["page"] < pages, "window_complete": pages == 1},
                "history_complete": False}

    def execute(self, operation: object, arguments: object) -> dict:
        """Fixture policy evaluation only; no production authority is conferred."""
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Fixture clock must return an aware datetime")
        now = now.astimezone(timezone.utc)
        result = {"mode": "mock", "synthetic": True, "readiness": "blocked", "can_recommend": False,
                  "authentication": "not_implemented", "independent_isolation": "not_implemented",
                  "broker_read_only_authorization": "not_verified", "provenance": "unverified_synthetic_fixture",
                  "checked_at": now.isoformat(), "as_of": None, "status": "unavailable", "data": None,
                  "financial_action_capabilities": [], "blockers": [{"code": "MOCK_ONLY", "message": "No production adapter, authentication, or independently controlled isolation is implemented."}]}
        try:
            args = self._arguments(operation, arguments, now)
            raw = self._read_fixture(operation, args)
            clean = self._validate(operation, raw, args, now)
            result.update(status="available" if clean["complete"] else "partial", as_of=clean["as_of"], data=clean)
        except _Blocked as exc:
            result["blockers"].append({"code": exc.code, "message": MESSAGES[exc.code]})
        except Exception:
            # Deliberately suppress raw fixture values, exception text, and tokens.
            result["blockers"].append({"code": "FIXTURE_INVALID", "message": MESSAGES["FIXTURE_INVALID"]})
        return result
