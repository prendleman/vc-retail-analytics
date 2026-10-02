"""API-level assistant behavior tests against a temporary DB."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from app.core import seed
from app.server import Handler, Store
from http.server import ThreadingHTTPServer


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls._tmp.name) / "api.db"
        seed(cls.db, dealers=8, skus=30)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.httpd.dealer = None
        cls.httpd.store = Store(cls.db, "local", "aq_vc_reader")
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls._tmp.cleanup()

    def _json(self, method, path, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = None if body is None else json.dumps(body).encode()
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        conn.request(method, path, body=payload, headers=hdrs)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
        conn.close()
        return resp.status, data, resp.getheader("Set-Cookie")

    def test_today_escalate_and_proposed_metric(self):
        status, login, cookie = self._json("POST", "/api/login", {"username": "operator", "password": "vc-demo"})
        self.assertEqual(status, 200)
        cookie_hdr = cookie.split(";")[0]
        st, today, _ = self._json(
            "POST",
            "/api/ask",
            {"question": "where is my order ABC", "mode": "today"},
            {"Cookie": cookie_hdr},
        )
        self.assertEqual(st, 200)
        self.assertEqual(today["kind"], "escalate")
        st, prop, _ = self._json(
            "POST",
            "/api/ask",
            {"question": "show sales by family", "mode": "proposed"},
            {"Cookie": cookie_hdr},
        )
        self.assertEqual(st, 200)
        self.assertEqual(prop["kind"], "metric")
        self.assertEqual(prop["metric"], "by_family")
        self.assertIn("trace", prop)

    def test_dealer_escape_denied(self):
        status, login, cookie = self._json("POST", "/api/login", {"username": "dlr-0001", "password": "vc-demo"})
        self.assertEqual(status, 200)
        cookie_hdr = cookie.split(";")[0]
        st, data, _ = self._json("GET", "/api/summary?dealer=DLR-0002", headers={"Cookie": cookie_hdr})
        # GET with headers helper — fix call
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/summary?dealer=DLR-0002", headers={"Cookie": cookie_hdr})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 403)
        self.assertIn("denied", body["error"].lower())


if __name__ == "__main__":
    unittest.main()
