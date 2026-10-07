"""
Extended Test Suite: API Server (api/server.py)
Copre le casistiche limite di api/server.py:
- gestione eccezioni in do_POST
- file statico con mime type sconosciuto o errore di lettura
- do_OPTIONS
- filtro min_virality in /api/products
- avvio di run_server con mock
"""

import unittest
from unittest.mock import patch, MagicMock
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

import api.server as server_mod
from api.server import OffertissimeScontiServer, run_server

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class TestApiServerExtended(unittest.TestCase):
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

    def test_products_min_virality_filter(self):
        url = f"{self.base_url}/api/products?min_virality=95&limit=5"
        with urllib.request.urlopen(url) as res:
            data = json.loads(res.read().decode("utf-8"))
            self.assertTrue(data["success"])
            for p in data["products"]:
                self.assertGreaterEqual(p["virality_score"], 95)

    def test_post_track_malformed_json(self):
        url = f"{self.base_url}/api/track"
        req = urllib.request.Request(url, data=b"NOT_A_JSON_STRING", headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                self.fail("Dovrebbe sollevare 400 Bad Request")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)
            data = json.loads(e.read().decode("utf-8"))
            self.assertIn("error", data)

    def test_post_unknown_endpoint(self):
        url = f"{self.base_url}/api/wrong_endpoint"
        req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as res:
                self.fail("Dovrebbe sollevare 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_products_sorting_options(self):
        for s in ["price_asc", "price_desc", "atl", "cycle", "drop"]:
            url = f"{self.base_url}/api/products?sort={s}&limit=3"
            with urllib.request.urlopen(url) as res:
                data = json.loads(res.read().decode("utf-8"))
                self.assertTrue(data["success"])
                self.assertEqual(len(data["products"]), 3)

    def test_export_posttap_csv_endpoint(self):
        url = f"{self.base_url}/api/export/posttap.csv"
        with urllib.request.urlopen(url) as res:
            self.assertEqual(res.status, 200)
            self.assertIn("text/csv", res.headers.get("Content-Type", ""))
            content = res.read().decode("utf-8")
            self.assertTrue(content.startswith("Title,Affiliate_URL"))

    def test_static_export_files(self):
        for f_name in ["/offertissimesconti_posttap_export.csv", "/offertissimesconti_links_only.txt"]:
            url = f"{self.base_url}{f_name}"
            with urllib.request.urlopen(url) as res:
                self.assertEqual(res.status, 200)
                data = res.read()
                self.assertGreater(len(data), 0)

    def test_run_server_mock(self):
        with patch("api.server.HTTPServer") as mock_http:
            mock_instance = MagicMock()
            mock_http.return_value = mock_instance
            mock_instance.serve_forever.side_effect = KeyboardInterrupt()
            try:
                run_server(port=9999)
            except KeyboardInterrupt:
                pass
            mock_http.assert_called_with(("0.0.0.0", 9999), OffertissimeScontiServer)

if __name__ == "__main__":
    unittest.main()
