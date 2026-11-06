"""Mock policy tests only; no credentials, personal records, or financial actions."""
import copy
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from investment_research.gateway import MockReadGateway

NOW = datetime(2026, 11, 5, 18, tzinfo=timezone.utc)
STAMP = "2026-11-05T16:00:00+00:00"


def transaction(identifier="fixture-event-1"):
    return {"fixture_id": identifier, "occurred_at": "2026-11-04T15:00:00+00:00", "kind": "BUY",
            "symbol": "NOVA", "quantity": "2", "amount": "-100", "fee": "0"}


def transaction_args(**changes):
    return {"account_alias": "taxable", "start_date": "2026-11-01", "end_date": "2026-11-05",
            "page": 1, "page_size": 100, **changes}


class FixtureUpstream:
    """In-memory fixtures intentionally provide no network or generic adapter."""

    def __init__(self):
        common = {"as_of": STAMP, "currency": "USD", "complete": True}
        self.responses = {
            "read_accounts": {**common, "accounts": [{"alias": "taxable", "type": "taxable"}, {"alias": "roth", "type": "roth_ira"}]},
            "read_balances": {**common, "account_alias": "taxable", "cash": "25.50", "positions_value": "100", "equity": "125.50"},
            "read_holdings": {**common, "account_alias": "taxable", "total_market_value": "100",
                              "holdings": [{"symbol": "NOVA", "quantity": "2", "price": "50", "market_value": "100", "price_as_of": STAMP}]},
            "read_transactions": {**common, "account_alias": "taxable", "start_date": "2026-11-01", "end_date": "2026-11-05",
                                  "page": 1, "page_size": 100, "total_count": 1, "transactions": [transaction()]},
        }
        self.calls = []
        self.failure = None

    def _fixture(self, operation, *args):
        self.calls.append((operation, args))
        if self.failure:
            raise self.failure
        return copy.deepcopy(self.responses[operation])

    def read_accounts(self):
        return self._fixture("read_accounts")

    def read_balances(self, alias):
        return self._fixture("read_balances", alias)

    def read_holdings(self, alias):
        return self._fixture("read_holdings", alias)

    def read_transactions(self, alias, start, end, page, page_size):
        return self._fixture("read_transactions", alias, start, end, page, page_size)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.upstream = FixtureUpstream()
        self.gateway = MockReadGateway(self.upstream, account_aliases=frozenset({"taxable", "roth"}), clock=lambda: NOW)

    def blocked(self, result, code):
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["data"])
        self.assertIsNone(result["as_of"])
        self.assertEqual(result["readiness"], "blocked")
        self.assertFalse(result["can_recommend"])
        self.assertIn(code, {blocker["code"] for blocker in result["blockers"]})

    def test_four_reads_use_only_typed_fixture_methods_and_remain_unverified(self):
        for operation, args in [("read_accounts", {}), ("read_balances", {"account_alias": "taxable"}),
                                ("read_holdings", {"account_alias": "taxable"}), ("read_transactions", transaction_args())]:
            with self.subTest(operation=operation):
                result = self.gateway.execute(operation, args)
                self.assertEqual(result["status"], "available")
                self.assertEqual(result["mode"], "mock")
                self.assertTrue(result["synthetic"])
                self.assertEqual(result["readiness"], "blocked")
                self.assertFalse(result["can_recommend"])
                self.assertEqual(result["authentication"], "not_implemented")
                self.assertEqual(result["independent_isolation"], "not_implemented")
                self.assertEqual(result["broker_read_only_authorization"], "not_verified")
                self.assertEqual(result["provenance"], "unverified_synthetic_fixture")
                self.assertEqual(result["financial_action_capabilities"], [])
                self.assertEqual(result["as_of"], STAMP)
                self.assertEqual(result["checked_at"], NOW.isoformat())
        self.assertEqual([name for name, _ in self.upstream.calls], ["read_accounts", "read_balances", "read_holdings", "read_transactions"])
        self.assertEqual(self.upstream.calls[-1][1], ("taxable", date(2026, 11, 1), date(2026, 11, 5), 1, 100))

    def test_orders_transfers_admin_dynamic_tools_and_raw_requests_never_reach_upstream(self):
        for operation in ["buy", "sell", "orders", "submit_order", "cancel_order", "exercise", "deposit", "withdraw", "transfer",
                          "write", "admin", "configure", "register_tool", "tools/call", "request", "GET", "POST",
                          "https://example.invalid/read", "Read_accounts", "read_accounts ", None, ["read_accounts"],
                          {"method": "tools/call", "params": {"name": "read_accounts"}}]:
            with self.subTest(operation=operation):
                self.blocked(self.gateway.execute(operation, {}), "REQUEST_DENIED")
        self.assertEqual(self.upstream.calls, [])

    def test_extra_nested_malformed_or_scope_arguments_are_denied_before_adapter(self):
        cases = [None, [], "taxable", {"account_alias": ["taxable"]}, {"account_alias": {"alias": "taxable"}},
                 {"account_alias": "foreign"}, {"account_alias": "taxable", "url": "https://example.invalid"},
                 {"account_alias": "taxable", "headers": {}}, {"account_alias": "taxable", "method": "GET"},
                 {"account_alias": "taxable", "tool": "read_holdings"}, {"account_alias": "taxable", "arguments": {}},
                 {"account_alias": "taxable", "account_aliases": ["foreign"]}, {"account_alias": "taxable", "verified": True},
                 {"account_alias": "taxable", "synthetic": False}, {"account_alias": "taxable", "as_of": NOW.isoformat()}]
        for args in cases:
            with self.subTest(args=args):
                self.blocked(self.gateway.execute("read_balances", args), "REQUEST_DENIED")
        self.blocked(self.gateway.execute("read_accounts", {"account_alias": "taxable"}), "REQUEST_DENIED")
        self.assertEqual(self.upstream.calls, [])

    def test_scope_requires_fixed_nonempty_valid_aliases(self):
        for aliases in [set(["taxable"]), frozenset(), frozenset({"123456"}), frozenset({"taxable", 1})]:
            with self.subTest(aliases=aliases), self.assertRaises(ValueError):
                MockReadGateway(self.upstream, account_aliases=aliases)

    def test_transaction_argument_bounds_and_types_prevent_unbounded_reads(self):
        cases = [{"page": 0}, {"page": 1001}, {"page": True}, {"page": "1"}, {"page_size": 0}, {"page_size": 101},
                 {"page_size": 1.0}, {"start_date": "2020-01-01"}, {"end_date": "2026-11-06"},
                 {"start_date": "2026-11-05", "end_date": "2026-11-04"}, {"start_date": "2026-02-30"},
                 {"start_date": "20261101"}, {"start_date": date(2026, 11, 1)}, {"page": {"next": 1}}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.blocked(self.gateway.execute("read_transactions", transaction_args(**changes)), "REQUEST_DENIED")
        self.assertEqual(self.upstream.calls, [])

    def test_unknown_secret_and_account_identifier_fields_are_never_returned(self):
        for field in ["access_token", "refresh_token", "authorization", "account_number", "raw_response", "verified", "permissions"]:
            with self.subTest(field=field):
                self.upstream.responses["read_balances"][field] = "fixture-sensitive-marker"
                result = self.gateway.execute("read_balances", {"account_alias": "taxable"})
                self.blocked(result, "FIXTURE_INVALID")
                self.assertNotIn("fixture-sensitive-marker", json.dumps(result))
                self.assertNotIn(field, json.dumps(result["data"]))
                del self.upstream.responses["read_balances"][field]
        self.upstream.responses["read_holdings"]["holdings"][0]["token"] = "fixture-sensitive-marker"
        self.blocked(self.gateway.execute("read_holdings", {"account_alias": "taxable"}), "FIXTURE_INVALID")
        self.upstream.responses["read_accounts"]["accounts"][0]["account_number"] = "fixture-sensitive-marker"
        self.blocked(self.gateway.execute("read_accounts", {}), "FIXTURE_INVALID")

    def test_foreign_response_alias_and_account_list_cannot_expand_scope(self):
        self.upstream.responses["read_balances"]["account_alias"] = "roth"
        self.blocked(self.gateway.execute("read_balances", {"account_alias": "taxable"}), "FIXTURE_INVALID")
        self.upstream.responses["read_accounts"]["accounts"].append({"alias": "foreign", "type": "taxable"})
        self.blocked(self.gateway.execute("read_accounts", {}), "FIXTURE_INVALID")

    def test_missing_or_duplicate_accounts_are_not_complete(self):
        self.upstream.responses["read_accounts"]["accounts"].pop()
        self.blocked(self.gateway.execute("read_accounts", {}), "FIXTURE_INCOMPLETE")
        self.upstream.responses["read_accounts"]["accounts"] *= 2
        self.blocked(self.gateway.execute("read_accounts", {}), "FIXTURE_INVALID")

    def test_stale_future_naive_and_invalid_timestamps_are_blocked_without_retiming(self):
        for stamp, code in [((NOW - timedelta(hours=97)).isoformat(), "FIXTURE_STALE"),
                            ((NOW + timedelta(seconds=1)).isoformat(), "FIXTURE_STALE"),
                            ("2026-11-05T16:00:00", "FIXTURE_INVALID"), ("not-a-time", "FIXTURE_INVALID")]:
            with self.subTest(stamp=stamp):
                self.upstream.responses["read_balances"]["as_of"] = stamp
                self.blocked(self.gateway.execute("read_balances", {"account_alias": "taxable"}), code)

    def test_nonfinite_wrong_type_and_unbounded_amounts_rejected(self):
        for value in ["NaN", "Infinity", "-Infinity", "1e3", "1000000000001", "0.1234567890123", "-1", 1, True, 1.5, None, {}]:
            with self.subTest(value=value):
                self.upstream.responses["read_balances"]["cash"] = value
                self.blocked(self.gateway.execute("read_balances", {"account_alias": "taxable"}), "FIXTURE_INVALID")

    def test_tampered_balances_currency_and_incomplete_flags_rejected(self):
        for key, value, code in [("equity", "126.50", "FIXTURE_INVALID"), ("currency", "EUR", "FIXTURE_INVALID"),
                                 ("complete", False, "FIXTURE_INCOMPLETE"), ("complete", "true", "FIXTURE_INCOMPLETE")]:
            with self.subTest(key=key):
                saved = self.upstream.responses["read_balances"][key]
                self.upstream.responses["read_balances"][key] = value
                self.blocked(self.gateway.execute("read_balances", {"account_alias": "taxable"}), code)
                self.upstream.responses["read_balances"][key] = saved

    def test_holdings_arithmetic_duplicate_marks_and_stale_quotes_rejected(self):
        original = copy.deepcopy(self.upstream.responses["read_holdings"])
        for field, value, code in [("market_value", "110", "FIXTURE_INVALID"), ("quantity", "0", "FIXTURE_INVALID"),
                                   ("price_as_of", (NOW - timedelta(days=5)).isoformat(), "FIXTURE_STALE"),
                                   ("price_as_of", "2026-11-05T17:00:00+00:00", "FIXTURE_STALE")]:
            with self.subTest(field=field):
                self.upstream.responses["read_holdings"] = copy.deepcopy(original)
                self.upstream.responses["read_holdings"]["holdings"][0][field] = value
                self.blocked(self.gateway.execute("read_holdings", {"account_alias": "taxable"}), code)
        self.upstream.responses["read_holdings"] = copy.deepcopy(original)
        self.upstream.responses["read_holdings"]["holdings"] *= 2
        self.blocked(self.gateway.execute("read_holdings", {"account_alias": "taxable"}), "FIXTURE_INVALID")
        self.upstream.responses["read_holdings"] = copy.deepcopy(original)
        self.upstream.responses["read_holdings"]["total_market_value"] = "101"
        self.blocked(self.gateway.execute("read_holdings", {"account_alias": "taxable"}), "FIXTURE_INVALID")

    def test_paginated_results_explicitly_partial_never_claim_complete_history(self):
        raw = self.upstream.responses["read_transactions"]
        raw.update(page_size=2, total_count=3, transactions=[transaction(), transaction("fixture-event-2")])
        result = self.gateway.execute("read_transactions", transaction_args(page_size=2))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["readiness"], "blocked")
        self.assertFalse(result["data"]["complete"])
        self.assertFalse(result["data"]["history_complete"])
        self.assertEqual(result["data"]["pagination"], {"page": 1, "page_size": 2, "total_count": 3, "total_pages": 2, "has_more": True, "window_complete": False})
        raw.update(page=2, transactions=[transaction("fixture-event-3")])
        result = self.gateway.execute("read_transactions", transaction_args(page=2, page_size=2))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["data"]["pagination"]["has_more"])
        self.assertFalse(result["data"]["pagination"]["window_complete"])
        self.assertFalse(result["can_recommend"])

    def test_transaction_page_binding_missing_rows_and_overstated_totals_blocked(self):
        original = copy.deepcopy(self.upstream.responses["read_transactions"])
        for field, value, code in [("page", 2, "FIXTURE_INVALID"), ("page_size", 20, "FIXTURE_INVALID"),
                                   ("start_date", "2026-10-01", "FIXTURE_INVALID"), ("total_count", 100001, "FIXTURE_INVALID"),
                                   ("total_count", 2, "FIXTURE_INCOMPLETE"), ("transactions", [], "FIXTURE_INCOMPLETE")]:
            with self.subTest(field=field):
                self.upstream.responses["read_transactions"] = copy.deepcopy(original)
                self.upstream.responses["read_transactions"][field] = value
                self.blocked(self.gateway.execute("read_transactions", transaction_args()), code)

    def test_transaction_timestamps_unknown_fields_and_duplicate_ids_rejected(self):
        raw = self.upstream.responses["read_transactions"]
        for stamp in ["2026-10-31T15:00:00+00:00", "2026-11-05T17:00:00+00:00"]:
            raw["transactions"][0]["occurred_at"] = stamp
            self.blocked(self.gateway.execute("read_transactions", transaction_args()), "FIXTURE_INVALID")
        raw["transactions"] = [transaction(), transaction()]
        raw["total_count"] = 2
        self.blocked(self.gateway.execute("read_transactions", transaction_args()), "FIXTURE_INVALID")
        raw.update(total_count=1, transactions=[{**transaction(), "secret": "fixture-sensitive-marker"}])
        result = self.gateway.execute("read_transactions", transaction_args())
        self.blocked(result, "FIXTURE_INVALID")
        self.assertNotIn("fixture-sensitive-marker", json.dumps(result))

    def test_old_snapshot_cannot_assert_a_transaction_window_through_today(self):
        self.upstream.responses["read_transactions"]["as_of"] = "2026-11-04T16:00:00+00:00"
        self.blocked(self.gateway.execute("read_transactions", transaction_args()), "FIXTURE_INCOMPLETE")

    def test_fixture_exception_details_are_masked_and_nothing_is_logged(self):
        self.upstream.failure = RuntimeError("fixture-sensitive-marker /private/fixture access_token=fixture-secret")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = self.gateway.execute("read_balances", {"account_alias": "taxable"})
        self.blocked(result, "UPSTREAM_UNAVAILABLE")
        self.assertNotIn("fixture-sensitive-marker", json.dumps(result))
        self.assertNotIn("/private/fixture", json.dumps(result))
        self.assertNotIn("fixture-secret", json.dumps(result))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_nested_wrong_response_shapes_fail_closed(self):
        for response in [None, [], {"access_token": "fixture-sensitive-marker"}]:
            self.upstream.responses["read_balances"] = response
            result = self.gateway.execute("read_balances", {"account_alias": "taxable"})
            self.blocked(result, "FIXTURE_INVALID")
            self.assertNotIn("fixture-sensitive-marker", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
