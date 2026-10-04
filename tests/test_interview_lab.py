"""Interview Lab: board brief, evals, plan-90."""
from __future__ import annotations

import unittest

from app import interview_lab
from app.core import DB, connect, seed
from app.server import Store


class InterviewLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB.exists():
            seed(DB)
        from app import competitors as cmod
        c = connect(DB)
        cmod.ensure_competitors(c)
        c.close()
        cls.store = Store(DB, "local", "aq")

    def test_board_brief(self):
        payload = interview_lab.run_board_brief(self.store, None)
        self.assertEqual(payload["kind"], "board_brief")
        self.assertEqual(len(payload["sections"]), 4)
        self.assertIn("Board brief", payload["spoken"])
        self.assertGreater(payload["elapsed_ms"], 0)

    def test_evals_mostly_pass(self):
        report = interview_lab.run_evals(self.store, None)
        self.assertEqual(report["total"], 20)
        self.assertGreaterEqual(report["passed"], 17, report["results"])
        failed = [r for r in report["results"] if not r["ok"]]
        self.assertLessEqual(len(failed), 3, failed)

    def test_plan_90(self):
        plan = interview_lab.plan_90()
        self.assertEqual(len(plan["phases"]), 3)
        self.assertTrue(plan["non_goals"])

    def test_compare_governed_hit(self):
        out = interview_lab.compare_governed_cortex(self.store, "show margin percent", None)
        self.assertTrue(out["governed"]["ok"])
        self.assertEqual(out["governed"]["metric"], "margin_pct")
        self.assertFalse(out["cortex"]["ok"])  # local backend


if __name__ == "__main__":
    unittest.main()
