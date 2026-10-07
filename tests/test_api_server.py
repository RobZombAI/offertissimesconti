"""
Test Suite: REST API & Web Server (api/server.py)
Testa in modo esaustivo tutti gli endpoint REST, routing file statici,
parametri di ricerca, paginazione, CORS, gestione errori 404 e POST /api/track.
"""

import unittest
import json
import urllib.request
import urllib.parse
import urllib.error
import threading
import time
import socket
from http.server import HTTPServer
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from api.server import OffertissimeScontiServer

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class TestApiServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = get_free_port()
        cls.server = HTTPServer(("127.0.0.1", cls.port), OffertissimeScontiServer)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _fetch(self, path: str, method: str = "GET", data: dict = None, headers: dict = None):
        url = f"{self.base_url}{path}"
        req_headers = headers or {}
        req_data = None
        if data is not None:
            req_data = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                body = response.read().decode("utf-8")
                resp_headers = dict(response.info())
                return status, body, resp_headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8"), dict(e.headers)

    def test_root_index_html(self):
        status, body, headers = self._fetch("/")
        self.assertEqual(status, 200)
        self.assertIn("OffertissimeSconti", body)
        self.assertIn("text/html", headers.get("Content-Type", ""))

    def test_static_css(self):
        status, body, headers = self._fetch("/style.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers.get("Content-Type", ""))
        self.assertIn("OFFERTISSIMESCONTI", body)

    def test_static_js(self):
        status, body, headers = self._fetch("/app.js")
        self.assertEqual(status, 200)
        self.assertIn("OFFERTISSIMESCONTI", body)

    def test_options_cors(self):
        status, body, headers = self._fetch("/api/products", method="OPTIONS")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_api_health(self):
        status, body, _ = self._fetch("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("brand"), "OFFERTISSIMESCONTI")

    def test_api_stats(self):
        status, body, _ = self._fetch("/api/stats")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        stats = data.get("stats", {})
        self.assertGreaterEqual(stats.get("total_products", 0), 3000)
        self.assertGreaterEqual(stats.get("total_cyclical", 0), 1000)

    def test_api_categories(self):
        status, body, _ = self._fetch("/api/categories")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        cats = data.get("categories", [])
        self.assertEqual(len(cats), 15)
        for cat in cats:
            self.assertIn("macro_category_id", cat)
            self.assertIn("macro_category_name", cat)
            self.assertGreater(cat["total_skus"], 0)

    def test_api_deals(self):
        status, body, _ = self._fetch("/api/deals?limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        deals = data.get("deals", [])
        self.assertLessEqual(len(deals), 5)
        self.assertGreater(len(deals), 0)

    def test_api_products_default_pagination(self):
        status, body, _ = self._fetch("/api/products")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("limit"), 24)
        self.assertEqual(len(data.get("products", [])), 24)

    def test_api_products_category_filter(self):
        status, body, _ = self._fetch("/api/products?category=beauty_personal_care&limit=10")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        for p in data["products"]:
            self.assertEqual(p["macro_category_id"], "beauty_personal_care")

    def test_api_products_cyclical_filter(self):
        status, body, _ = self._fetch("/api/products?cyclical=1&limit=10")
        self.assertEqual(status, 200)
        data = json.loads(body)
        for p in data["products"]:
            self.assertEqual(p["is_cyclical"], 1)

    def test_api_products_min_drop_filter(self):
        status, body, _ = self._fetch("/api/products?min_drop=20&limit=10")
        self.assertEqual(status, 200)
        data = json.loads(body)
        for p in data["products"]:
            self.assertGreaterEqual(p["keepa_drop_percent"], 20)

    def test_api_products_search(self):
        status, body, _ = self._fetch("/api/products?search=Borbone&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertGreater(len(data["products"]), 0)
        for p in data["products"]:
            matches = ("Borbone" in p["title"]) or ("Borbone" in p["brand"]) or ("Borbone" in p["sub_category_name"])
            self.assertTrue(matches)

    def test_api_track_success(self):
        payload = {
            "product_id": "SKU-TEST-001",
            "target_price": 19.99,
            "user_id": "test_user_unit",
            "channel": "telegram"
        }
        status, body, _ = self._fetch("/api/track", method="POST", data=payload)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))

    def test_api_track_invalid_payload(self):
        # Manca product_id
        payload = {"target_price": 10.0}
        status, body, _ = self._fetch("/api/track", method="POST", data=payload)
        self.assertEqual(status, 400)

        # Prezzo negativo
        payload2 = {"product_id": "SKU-1", "target_price": -5}
        status2, body2, _ = self._fetch("/api/track", method="POST", data=payload2)
        self.assertEqual(status2, 400)

    def test_404_not_found(self):
        status, body, _ = self._fetch("/api/rotta_inesistente")
        self.assertEqual(status, 404)
        data = json.loads(body)
        self.assertIn("error", data)

    def test_static_404(self):
        # File statico inesistente
        status, _, _ = self._fetch("/file_fantasma.xyz")
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()
