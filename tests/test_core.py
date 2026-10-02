"""Unit tests for synthetic seed, metrics, and assistant routers."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core import METRICS, interpret_metric, match_faq, metric_sql, seed
from app import demo_auth


class SeedTests(unittest.TestCase):
    def test_seed_and_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "t.db"
            result = seed(db, dealers=10, skus=40)
            self.assertGreater(result["current_facts"], 0)
            self.assertGreaterEqual(result["quarantined"], 0)
            from app.core import connect

            c = connect(db)
            try:
                dealers = c.execute("SELECT COUNT(*) FROM dealers").fetchone()[0]
                products = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
                facts = c.execute("SELECT COUNT(*) FROM silver_facts").fetchone()[0]
                gold = c.execute("SELECT COUNT(*) FROM gold_channel_family").fetchone()[0]
                monthly = c.execute("SELECT COUNT(*) FROM silver_monthly").fetchone()[0]
                vendors = c.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
                reps = c.execute("SELECT COUNT(*) FROM salespeople").fetchone()[0]
                territories = c.execute("SELECT COUNT(*) FROM territories").fetchone()[0]
                vk = c.execute("SELECT COUNT(*) FROM silver_vendor_kpi").fetchone()[0]
                sample = c.execute(
                    "SELECT cost_cents, vendor_id, safety_stock FROM products LIMIT 1"
                ).fetchone()
                fact = c.execute("SELECT rep_id, cost_cents FROM silver_facts LIMIT 1").fetchone()
            finally:
                c.close()
            self.assertEqual(dealers, 10)
            self.assertEqual(products, 40)
            self.assertGreater(facts, 0)
            self.assertGreater(gold, 0)
            self.assertGreater(monthly, 0)
            self.assertEqual(vendors, 12)
            self.assertEqual(reps, 20)
            self.assertEqual(territories, 8)
            self.assertEqual(vk, 12)
            self.assertIsNotNone(sample["cost_cents"])
            self.assertIsNotNone(sample["vendor_id"])
            self.assertIsNotNone(fact["rep_id"])
            sql, params = metric_sql("by_channel", "DLR-0001")
            self.assertIn("dealer_id=?", sql)
            self.assertEqual(params, ["DLR-0001"])

    def test_deep_metrics_execute(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "t.db"
            seed(db, dealers=8, skus=30)
            from app.core import connect

            c = connect(db)
            try:
                for name in (
                    "margin_pct",
                    "price_realization",
                    "low_margin_skus",
                    "margin_waterfall",
                    "reorder_candidates",
                    "days_of_cover",
                    "units_by_month",
                    "seasonal_index",
                    "yoy_family",
                    "lead_vs_peak",
                    "territory_perf",
                    "territory_coverage",
                    "whitespace",
                    "plan_vs_season",
                    "rep_leaderboard",
                    "rep_grade",
                    "vendor_otif",
                    "vendor_scorecard",
                ):
                    sql, params = metric_sql(name, "DLR-0001")
                    rows = list(c.execute(sql, params))
                    self.assertIsInstance(rows, list, msg=name)
                    sql_all, params_all = metric_sql(name, None)
                    rows_all = list(c.execute(sql_all, params_all))
                    self.assertIsInstance(rows_all, list, msg=f"{name}/all")
            finally:
                c.close()
            self.assertIn("margin_pct", METRICS)
            self.assertIn("vendor_scorecard", METRICS)


class AssistantTests(unittest.TestCase):
    def test_metric_router(self):
        self.assertEqual(interpret_metric("show sales by channel"), "by_channel")
        self.assertEqual(interpret_metric("show margin percent"), "margin_pct")
        self.assertEqual(interpret_metric("show rep grades"), "rep_grade")
        self.assertEqual(interpret_metric("show vendor scorecard"), "vendor_scorecard")
        self.assertEqual(interpret_metric("show seasonality"), "seasonal_index")
        with self.assertRaises(ValueError):
            interpret_metric("forecast next quarter invent numbers")

    def test_faq_and_auth(self):
        self.assertIsNotNone(match_faq("what is open box inventory"))
        self.assertIsNone(demo_auth.authenticate("dlr-0001", "wrong"))
        sess = demo_auth.authenticate("dlr-0001", "vc-demo")
        self.assertEqual(sess["dealer"], "DLR-0001")
        cookie = demo_auth.issue_cookie(sess)
        parsed = demo_auth.parse_cookie(cookie.split(",")[0] if False else f"vc_demo={cookie.split('=',1)[1].split(';')[0]}")
        self.assertEqual(parsed["username"], "dlr-0001")


if __name__ == "__main__":
    unittest.main()
