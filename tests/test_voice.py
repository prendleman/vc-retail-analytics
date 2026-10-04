"""Unit tests for speakable briefs, Cortex SQL safety, and spoken metric routing."""
from __future__ import annotations

import unittest

from app import voice
from app.core import interpret_metric, resolve_metric


class VoiceSpeakableTests(unittest.TestCase):
    def test_margin_pct(self):
        text = voice.speakable_metric(
            "margin_pct",
            [{"channel": "Trade", "margin_pct": 42.1}, {"channel": "Consumer", "margin_pct": 51.0}],
        )
        self.assertIn("Trade", text)
        self.assertIn("42.1 percent", text)

    def test_by_channel_money(self):
        text = voice.speakable_metric(
            "by_channel",
            [{"channel": "Trade", "net_sales": 346_000_000}, {"channel": "Consumer", "net_sales": 200_000_000}],
        )
        self.assertIn("million", text)
        self.assertIn("Trade", text)

    def test_empty(self):
        text = voice.speakable_metric("portfolio", [])
        self.assertIn("no rows", text)

    def test_portfolio_brief(self):
        text = voice.speakable_portfolio_brief(
            {"dealers": 1500, "skus": 20000, "units_sold": 3_000_000, "net_sales": 750_000_000, "margin": 350_000_000},
            [{"channel": "Trade", "net_sales": 400_000_000, "margin_pct": 43.0}],
            [{"sku_id": "SKU-9", "units_sold": 5}],
        )
        self.assertIn("1,500 accounts", text)
        self.assertIn("Trade", text)
        self.assertIn("SKU-9", text)


class ResolveMetricTests(unittest.TestCase):
    def test_exact_unchanged(self):
        self.assertEqual(interpret_metric("show margin percent"), "margin_pct")
        self.assertEqual(resolve_metric("show margin percent"), "margin_pct")

    def test_spoken_aliases(self):
        self.assertEqual(resolve_metric("what's our margin by channel?"), "margin_pct")
        self.assertEqual(resolve_metric("Please show me sales by channel"), "by_channel")
        self.assertEqual(resolve_metric("past due POs"), "po_past_due")
        self.assertEqual(resolve_metric("MRP exceptions please"), "mrp_exceptions")

    def test_unknown_still_raises(self):
        with self.assertRaises(ValueError):
            resolve_metric("what is the weather in houston")


class CortexSqlSafetyTests(unittest.TestCase):
    def test_select_ok(self):
        sql = voice.safe_select_sql("SELECT channel, SUM(net_sales) FROM gold GROUP BY 1")
        self.assertTrue(sql.lower().startswith("select"))

    def test_with_ok(self):
        sql = voice.safe_select_sql("WITH t AS (SELECT 1 AS x) SELECT * FROM t")
        self.assertIn("WITH", sql.upper())

    def test_rejects_delete(self):
        with self.assertRaises(ValueError):
            voice.safe_select_sql("DELETE FROM dealers")

    def test_rejects_multi(self):
        with self.assertRaises(ValueError):
            voice.safe_select_sql("SELECT 1; SELECT 2")


if __name__ == "__main__":
    unittest.main()
