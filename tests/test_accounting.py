"""Independent arithmetic and adversarial import tests; all data are synthetic."""
import csv
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from investment_research.accounting import (BenchmarkPoint, DataQualityError, Event, Price,
                                          analyze, load_benchmark, load_events, load_prices, reconcile)

D1 = date(2026, 11, 2)
D2 = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)
STAMP1 = datetime(2026, 11, 2, 21, tzinfo=timezone.utc)
STAMP2 = datetime(2026, 11, 3, 21, tzinfo=timezone.utc)


def event(identifier, day, kind, *, account="taxable", symbol="", quantity="0", price="0", amount="0", fee="0", transfer_id=""):
    return Event(identifier, day, account, kind, symbol, D(quantity), D(price), D(amount), D(fee), transfer_id)


def observations(first="10", second="11", index1="100", index2="110"):
    return ({(D1, "NOVA"): Price(D1, "NOVA", D(first), "synthetic", STAMP1),
             (D2, "NOVA"): Price(D2, "NOVA", D(second), "synthetic", STAMP2)},
            {D1: BenchmarkPoint(D1, D(index1), "synthetic", STAMP1), D2: BenchmarkPoint(D2, D(index2), "synthetic", STAMP2)})


class AccountingTests(unittest.TestCase):
    def analyze(self, events, **kwargs):
        prices, benchmark = observations(**kwargs)
        return analyze(events, prices, benchmark, as_of=NOW, history_complete=True)

    def initial_position(self):
        return [event("deposit", D1, "DEPOSIT", amount="100"),
                event("buy", D1, "BUY", symbol="NOVA", quantity="10", price="10", amount="100")]

    def test_deposit_is_not_profit_and_benchmark_matches_cash_dates(self):
        result = self.analyze(self.initial_position() + [event("later", D2, "DEPOSIT", amount="100")])
        self.assertEqual(result["summary"]["equity"], "210.00")
        self.assertEqual(result["summary"]["net_contributions"], "200.00")
        self.assertEqual(result["summary"]["gain"], "10.00")
        self.assertEqual(result["summary"]["twr_pct"], "10.000000")
        self.assertEqual(result["summary"]["benchmark_equity"], "210.00")
        self.assertEqual(result["summary"]["benchmark_excess_value"], "0.00")

    def test_internal_transfers_cancel_combined_external_flows(self):
        events = [event("a", D1, "DEPOSIT", amount="100"),
                  event("b", D2, "TRANSFER_OUT", amount="40", transfer_id="paired"),
                  event("c", D2, "TRANSFER_IN", account="roth", amount="40", transfer_id="paired")]
        result = self.analyze(events)
        self.assertEqual(result["summary"]["equity"], "100.00")
        self.assertEqual(result["summary"]["gain"], "0.00")
        self.assertEqual(result["summary"]["net_contributions"], "100.00")
        self.assertEqual(result["summary"]["twr_pct"], "0.000000")
        self.assertEqual({x["id"]: x["net_contributions"] for x in result["accounts"]}, {"roth": "40.00", "taxable": "60.00"})

    def test_dividend_is_return_not_external_contribution(self):
        result = self.analyze(self.initial_position() + [event("dividend", D2, "DIVIDEND", symbol="NOVA", amount="2")], second="10", index2="100")
        self.assertEqual(result["summary"]["equity"], "102.00")
        self.assertEqual(result["summary"]["twr_pct"], "2.000000")
        self.assertEqual(result["summary"]["net_contributions"], "100.00")

    def test_fractional_sales_and_fees_preserve_cash(self):
        events = [event("a", D1, "DEPOSIT", amount="100"),
                  event("b", D1, "BUY", symbol="NOVA", quantity="2.5", price="10", amount="25", fee="1"),
                  event("c", D2, "SELL", symbol="NOVA", quantity="1.25", price="12", amount="15", fee="0.5")]
        result = self.analyze(events, second="12")
        self.assertEqual(result["summary"]["cash"], "88.50")
        self.assertEqual(result["summary"]["positions_value"], "15.00")
        self.assertEqual(result["summary"]["equity"], "103.50")
        self.assertEqual(result["summary"]["gain"], "3.50")

    def test_split_with_raw_closes_has_no_invented_gain(self):
        result = self.analyze(self.initial_position() + [event("split", D2, "SPLIT", symbol="NOVA", quantity="2")], second="5", index2="100")
        self.assertEqual(result["summary"]["equity"], "100.00")
        self.assertEqual(result["summary"]["twr_pct"], "0.000000")
        self.assertEqual(result["holdings"][0]["quantity"], "20.000000000000")

    def test_withdrawals_do_not_manufacture_drawdown(self):
        events = [event("a", D1, "DEPOSIT", amount="100"), event("b", D2, "WITHDRAWAL", amount="90")]
        result = self.analyze(events, index2="100")
        self.assertEqual(result["summary"]["max_drawdown_pct"], "0.000000")
        self.assertEqual(result["summary"]["gain"], "0.00")

    def test_market_drawdown_is_flow_adjusted(self):
        result = self.analyze(self.initial_position() + [event("deposit2", D2, "DEPOSIT", amount="1000")], second="8")
        self.assertEqual(result["summary"]["equity"], "1080.00")
        self.assertEqual(result["summary"]["max_drawdown_pct"], "-20.000000")

    def test_duplicate_events_rejected(self):
        events = self.initial_position()
        with self.assertRaisesRegex(DataQualityError, "Duplicate"):
            self.analyze([*events, events[-1]])

    def test_unpaired_transfer_rejected(self):
        with self.assertRaisesRegex(DataQualityError, "pair exactly"):
            self.analyze([event("a", D1, "DEPOSIT", amount="100"), event("b", D2, "TRANSFER_OUT", amount="40", transfer_id="missing")])

    def test_unfunded_trade_rejected(self):
        with self.assertRaisesRegex(DataQualityError, "negative cash"):
            self.analyze([event("a", D1, "BUY", symbol="NOVA", quantity="1", price="10", amount="10")])

    def test_oversell_rejected(self):
        with self.assertRaisesRegex(DataQualityError, "negative cash or shares"):
            self.analyze(self.initial_position() + [event("sale", D2, "SELL", symbol="NOVA", quantity="11", price="11", amount="121")])

    def test_partial_history_rejected(self):
        prices, benchmark = observations()
        with self.assertRaisesRegex(DataQualityError, "Incomplete"):
            analyze(self.initial_position(), prices, benchmark, as_of=NOW)

    def test_missing_price_rejected(self):
        prices, benchmark = observations()
        del prices[(D2, "NOVA")]
        with self.assertRaisesRegex(DataQualityError, "Missing"):
            analyze(self.initial_position(), prices, benchmark, as_of=NOW, history_complete=True)

    def test_stale_valuation_rejected(self):
        prices, benchmark = observations()
        with self.assertRaisesRegex(DataQualityError, "stale"):
            analyze(self.initial_position(), prices, benchmark, as_of=datetime(2026, 11, 10, tzinfo=timezone.utc), history_complete=True)

    def test_future_source_timestamp_rejected(self):
        prices, benchmark = observations()
        prices[(D2, "NOVA")] = replace(prices[(D2, "NOVA")], as_of=datetime(2026, 11, 4, tzinfo=timezone.utc))
        with self.assertRaisesRegex(DataQualityError, "Source timestamp"):
            analyze(self.initial_position(), prices, benchmark, as_of=NOW, history_complete=True)

    def test_nonfinite_and_negative_amounts_rejected(self):
        for value in ["NaN", "Infinity", "-1"]:
            with self.subTest(value=value), self.assertRaises(DataQualityError):
                self.analyze([event("a", D1, "DEPOSIT", amount=value)])

    def test_account_numbers_rejected(self):
        with self.assertRaisesRegex(DataQualityError, "opaque"):
            self.analyze([event("a", D1, "DEPOSIT", account="123456789", amount="100")])

    def test_trade_amount_mismatch_rejected(self):
        events = self.initial_position()
        events[-1] = replace(events[-1], amount=D("99"))
        with self.assertRaisesRegex(DataQualityError, "quantity-times-price"):
            self.analyze(events)

    def test_sample_reconciles_to_independent_totals(self):
        samples = Path(__file__).resolve().parents[1] / "samples"
        result = analyze(load_events(samples / "transactions.csv"), load_prices(samples / "prices.csv"), load_benchmark(samples / "benchmark.csv"), as_of=NOW, history_complete=True)
        self.assertEqual(result["summary"]["net_contributions"], "5750.00")
        self.assertEqual(result["summary"]["cash"], "1677.00")
        self.assertEqual(result["summary"]["positions_value"], "4329.00")
        self.assertEqual(result["summary"]["equity"], "6006.00")
        self.assertEqual(result["summary"]["gain"], "256.00")
        self.assertEqual(result["summary"]["benchmark_twr_pct"], "1.500000")
        self.assertIsNone(result["summary"]["xirr_pct"])
        self.assertFalse(result["quality"]["broker_reconciled"])

    def test_csv_parser_rejects_duplicate_rows_without_values_in_error(self):
        samples = Path(__file__).resolve().parents[1] / "samples"
        original = (samples / "transactions.csv").read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.csv"
            path.write_text(original + original.splitlines()[-1] + "\n")
            with self.assertRaisesRegex(DataQualityError, "Duplicate") as caught:
                load_events(path)
            self.assertNotIn("demo-016", str(caught.exception))

    def test_noncalendar_event_is_not_silently_moved(self):
        with self.assertRaisesRegex(DataQualityError, "outside the supplied"):
            prices, benchmark = observations()
            events = [event("a", D1, "DEPOSIT", amount="100"), event("b", date(2026, 11, 4), "DEPOSIT", amount="100")]
            analyze(events, prices, benchmark, as_of=datetime(2026, 11, 4, 22, tzinfo=timezone.utc), history_complete=True)

    def test_statement_reconciliation_matches_cash_and_quantities(self):
        result = self.analyze(self.initial_position())
        statement = {"valuation_date": "2026-11-03", "accounts": [{"id": "taxable", "cash": "0", "holdings": [{"symbol": "NOVA", "quantity": "10"}]}]}
        self.assertEqual(reconcile(result, statement)["status"], "matched")
        self.assertFalse(result["quality"]["broker_reconciled"])

    def test_statement_reconciliation_detects_mismatch_and_missing_accounts(self):
        result = self.analyze(self.initial_position())
        statement = {"valuation_date": "2026-11-03", "accounts": [{"id": "taxable", "cash": "1", "holdings": [{"symbol": "NOVA", "quantity": "9"}]}]}
        discrepancy = reconcile(result, statement)
        self.assertEqual(discrepancy["status"], "mismatch")
        self.assertEqual(len(discrepancy["discrepancies"]), 2)
        self.assertEqual(reconcile(result, {"valuation_date": "2026-11-03", "accounts": []})["status"], "mismatch")

    def test_statement_dates_must_match(self):
        with self.assertRaisesRegex(DataQualityError, "dates must agree"):
            reconcile(self.analyze(self.initial_position()), {"valuation_date": "2026-11-02", "accounts": []})

    def test_nonfinite_direct_price_rejected(self):
        prices, benchmark = observations()
        prices[(D2, "NOVA")] = replace(prices[(D2, "NOVA")], close=D("NaN"))
        with self.assertRaises(DataQualityError):
            analyze(self.initial_position(), prices, benchmark, as_of=NOW, history_complete=True)


if __name__ == "__main__":
    unittest.main()
