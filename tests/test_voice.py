"""Unit tests for speakable briefs and Cortex SQL safety (no network)."""
from __future__ import annotations

import unittest

from app import voice


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
