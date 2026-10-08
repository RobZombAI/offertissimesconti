"""
Coverage Booster Suite
Testa chirurgicamente i rami rimanenti per raggiungere il 98%+ di coverage:
- server.py: do_OPTIONS, mime_type sconosciuto, eccezione 500 in statico
- live_deal_monitor.py: get_bot_token vuoto, canale non-telegram, notifica già inviata
- telegram_bot_runner.py: get_bot_token vuoto, callback menu_search_help, ricerca generica
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import tempfile
import sqlite3
import urllib.request
import urllib.error
import threading
import time
import socket
from http.server import HTTPServer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import api.server as server_mod
from api.server import OffertissimeScontiServer
import core.live_deal_monitor as ldm_mod
from core.live_deal_monitor import LiveDealMonitor
import bot.telegram_bot_runner as tbr_mod
from bot.telegram_bot_runner import OffertissimeScontiTelegramBot

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

class TestCoverageBooster(unittest.TestCase):
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

    # --- 1. api/server.py ---
    def test_options_method_directly(self):
        url = f"{self.base_url}/"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)

    def test_serve_static_unknown_mime_and_ioerror(self):
        web_dir = os.path.join(BASE_DIR, "web")
        dummy_file = os.path.join(web_dir, "test_dummy_no_extension")
        with open(dummy_file, "w") as f:
            f.write("content")

        try:
            handler = OffertissimeScontiServer.__new__(OffertissimeScontiServer)
            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()
            handler.wfile = MagicMock()
            handler.send_error = MagicMock()

            # Test unknown mime (file without extension -> guess_type returns None)
            handler._serve_static(dummy_file)
            handler.send_response.assert_called_with(200)
            handler.send_header.assert_any_call("Content-Type", "application/octet-stream")

            # Test IO error
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                handler._serve_static(dummy_file)
                handler.send_error.assert_called_with(500, "Errore server: Permission denied")

            # Test BrokenPipe in _serve_static and exception in send_error
            handler.wfile.write.side_effect = BrokenPipeError("Pipe broken")
            handler._serve_static(dummy_file)

            handler.wfile.write.side_effect = Exception("Write error")
            handler.send_error.side_effect = Exception("Cannot send error")
            handler._serve_static(dummy_file)

            # Test BrokenPipe in _send_json
            handler.wfile.write.side_effect = BrokenPipeError("Broken pipe")
            handler._send_json(200, {"ok": True})

            # Test nonexistent static file
            handler.send_error.side_effect = None
            handler._serve_static("/nonexistent/file/path/test.html")
            handler.send_error.assert_called_with(404, "File non trovato")
        finally:
            if os.path.exists(dummy_file):
                os.remove(dummy_file)

    # --- 2. core/live_deal_monitor.py ---
    def test_ldm_get_bot_token_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.exists", return_value=False):
                self.assertEqual(ldm_mod.get_bot_token(), "")

    def test_ldm_non_telegram_channel_alert(self):
        # Database temporaneo per testare canale email
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE products_catalog (
                    sku_id TEXT PRIMARY KEY,
                    asin TEXT,
                    title TEXT,
                    brand TEXT,
                    macro_category_id TEXT,
                    current_price REAL,
                    list_price REAL,
                    all_time_low REAL,
                    avg_price_30d REAL,
                    affiliate_url TEXT,
                    keepa_drop_percent REAL
                )
            """)
            cur.execute("""
                CREATE TABLE user_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    channel TEXT,
                    product_id TEXT,
                    target_price REAL,
                    active INTEGER DEFAULT 1,
                    last_notified TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                INSERT INTO products_catalog VALUES (
                    'SKU-TEST-EMAIL', 'B00EMAIL', 'Prodotto Email', 'Brand',
                    'beauty', 10.0, 20.0, 10.0, 15.0, 'https://amazon.it', 30.0
                )
            """)
            # Alert con canale email (non telegram)
            cur.execute("""
                INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                VALUES ('user@email.com', 'email', 'SKU-TEST-EMAIL', 12.0)
            """)
            conn.commit()
            conn.close()

            monitor = LiveDealMonitor(db_path=tmp.name, bot_token="fake")
            notified = monitor.check_user_alerts()
            self.assertEqual(notified, 0) # Non invia a telegram per canale email

    # --- 3. bot/telegram_bot_runner.py ---
    def test_tbr_get_bot_token_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.exists", return_value=False):
                self.assertEqual(tbr_mod.get_bot_token(), "")

    def test_tbr_generic_search_fallback(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_message = MagicMock()
        bot.get_deal_keyboard = MagicMock(return_value={})
        bot.format_deal_html = MagicMock(return_value="HTML")

        # Cerca testo generico che trova risultati (es. Borbone)
        bot.handle_message({"chat": {"id": 1}, "text": "Borbone"})
        self.assertTrue(bot.send_message.called)

    def test_tbr_callback_menu_search_help(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_message = MagicMock()
        bot.answer_callback_query = MagicMock()

        cb = {
            "id": "cb_help",
            "data": "menu_search_help",
            "message": {"chat": {"id": 1}}
        }
        bot.handle_callback(cb)
        bot.answer_callback_query.assert_called_with("cb_help")
        bot.send_message.assert_called()

    def test_tbr_callback_unknown(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.answer_callback_query = MagicMock()

        cb = {
            "id": "cb_unk",
            "data": "unknown_action_xyz",
            "message": {"chat": {"id": 1}}
        }
        bot.handle_callback(cb)
        bot.answer_callback_query.assert_called_with("cb_unk")

    def test_ldm_send_alert_branches(self):
        # 1. No token
        ldm_no_token = LiveDealMonitor(bot_token="")
        self.assertFalse(ldm_no_token.send_telegram_alert("123", "Test"))

        # 2. Success with token
        ldm_with_token = LiveDealMonitor(bot_token="fake_tok")
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            res = ldm_with_token.send_telegram_alert("123", "Test")
            self.assertTrue(res)

    def test_tbr_extra_branches(self):
        bot = OffertissimeScontiTelegramBot("fake")

        # send_document failure responses
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=b"data")):
                with patch("requests.post") as mock_post:
                    mock_post.return_value.json.return_value = {"ok": False, "description": "Too large"}
                    res = bot.send_document(123, "file.csv")
                    self.assertFalse(res.get("ok"))

                    mock_post.side_effect = Exception("Network error")
                    res = bot.send_document(123, "file.csv")
                    self.assertFalse(res.get("ok"))

        # extract_asin amzn.to exception
        with patch("requests.get", side_effect=Exception("Timeout")):
            asin = bot.extract_asin("Guarda qui https://amzn.to/abc12345")
            self.assertIsNone(asin)

        # callback track with invalid format
        bot.answer_callback_query = MagicMock()
        cb = {
            "id": "cb_track_inv",
            "data": "track_only_one_part",
            "message": {"chat": {"id": 1}}
        }
        bot.handle_callback(cb)
        bot.answer_callback_query.assert_called_with("cb_track_inv")

    def test_tbr_send_photo_branches(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_message = MagicMock(return_value={"ok": True})

        # 1. empty photo_url
        res1 = bot.send_photo(123, "", caption="No photo")
        bot.send_message.assert_called_with(123, "No photo", reply_markup=None, parse_mode="HTML")

        # 2. caption > 1024 chars and success
        long_caption = "A" * 1030
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            res2 = bot.send_photo(123, "https://example.com/img.jpg", caption=long_caption, reply_markup={"inline_keyboard": []})
            self.assertTrue(res2["ok"])

            # 3. API error
            mock_post.return_value.json.return_value = {"ok": False, "description": "Failed to get photo"}
            res3 = bot.send_photo(123, "https://example.com/img.jpg", caption="Caption")
            bot.send_message.assert_called_with(123, "Caption", reply_markup=None, parse_mode="HTML")

            # 4. Exception
            mock_post.side_effect = Exception("Network timeout")
            res4 = bot.send_photo(123, "https://example.com/img.jpg", caption="Caption Err")
            bot.send_message.assert_called_with(123, "Caption Err", reply_markup=None, parse_mode="HTML")

    def test_tbr_send_deal_branches(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_photo = MagicMock(return_value={"ok": True})
        bot.send_message = MagicMock(return_value={"ok": True})

        # Deal with image_url
        p_with_img = {
            "sku_id": "SKU-IMG-1", "title": "Prod Img", "brand": "Brand",
            "macro_category_id": "beauty", "is_cyclical": 1, "cycle_days": 30,
            "current_price": 10.0, "list_price": 20.0, "all_time_low": 10.0,
            "avg_price_30d": 15.0, "keepa_drop_percent": 33.3,
            "affiliate_url": "https://amazon.it", "image_url": "https://example.com/pic.jpg"
        }
        bot.send_deal(123, p_with_img)
        bot.send_photo.assert_called_once()

        # Deal without image_url
        p_without_img = dict(p_with_img)
        p_without_img["image_url"] = ""
        bot.send_deal(123, p_without_img)
        bot.send_message.assert_called_once()

    def test_tbr_handle_asin_lookup_branches(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_photo = MagicMock(return_value={"ok": True})
        bot.send_message = MagicMock(return_value={"ok": True})

        # 1. Existing ASIN (e.g. B00PBX3L7K)
        bot.handle_asin_lookup(123, "B00PBX3L7K")
        self.assertTrue(bot.send_photo.called or bot.send_message.called)

        # 2. Non-existent ASIN
        bot.handle_asin_lookup(123, "B999999999")
        bot.send_message.assert_called()

    def test_ldm_send_telegram_photo_branches(self):
        # 1. No token
        ldm_no_token = LiveDealMonitor(bot_token="")
        self.assertFalse(ldm_no_token.send_telegram_photo("123", "https://img.jpg", "caption"))

        # 2. No photo_url
        ldm = LiveDealMonitor(bot_token="fake_token")
        ldm.send_telegram_alert = MagicMock(return_value=True)
        res_no_img = ldm.send_telegram_photo("123", "", "caption")
        self.assertTrue(res_no_img)

        # 3. caption > 1024 and success
        long_caption = "B" * 1030
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": True}
            res_ok = ldm.send_telegram_photo("123", "https://img.jpg", long_caption, keyboard={"inline_keyboard": []})
            self.assertTrue(res_ok)

            # 4. API error -> fallback
            mock_post.return_value.json.return_value = {"ok": False, "description": "Cannot download photo"}
            res_err = ldm.send_telegram_photo("123", "https://img.jpg", "caption")
            self.assertTrue(res_err) # fallback to send_telegram_alert which returns True

            # 5. Exception -> fallback
            mock_post.side_effect = Exception("Connection timeout")
            res_exc = ldm.send_telegram_photo("123", "https://img.jpg", "caption")
            self.assertTrue(res_exc)

    def test_ldm_check_user_alerts_with_photo(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE products_catalog (
                    sku_id TEXT PRIMARY KEY,
                    asin TEXT,
                    title TEXT,
                    brand TEXT,
                    macro_category_id TEXT,
                    current_price REAL,
                    list_price REAL,
                    all_time_low REAL,
                    avg_price_30d REAL,
                    affiliate_url TEXT,
                    keepa_drop_percent REAL,
                    image_url TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE user_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    channel TEXT,
                    product_id TEXT,
                    target_price REAL,
                    active INTEGER DEFAULT 1,
                    last_notified TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                INSERT INTO products_catalog VALUES (
                    'SKU-PHOTO-1', 'B00PHOTO1', 'Prodotto Foto', 'Brand',
                    'beauty', 10.0, 20.0, 10.0, 15.0, 'https://amazon.it', 30.0,
                    'https://m.media-amazon.com/images/I/photo.jpg'
                )
            """)
            cur.execute("""
                INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                VALUES ('user_tg_1', 'telegram', 'SKU-PHOTO-1', 12.0)
            """)
            conn.commit()
            conn.close()

            monitor = LiveDealMonitor(db_path=tmp.name, bot_token="fake_token")
            monitor.send_telegram_photo = MagicMock(return_value=True)
            notified = monitor.check_user_alerts()
            self.assertEqual(notified, 1)
            monitor.send_telegram_photo.assert_called_once()

    def test_tbr_send_wishlist_non_empty(self):
        bot = OffertissimeScontiTelegramBot("fake")
        bot.send_message = MagicMock()
        mock_wish = [
            {
                "title": "Prod 1",
                "current_price": 10.0,
                "target_price": 12.0,
                "keepa_drop_percent": 20.0,
                "all_time_low": 9.0,
                "affiliate_url": "https://amazon.it"
            },
            {
                "title": "Prod 2",
                "current_price": 25.0,
                "target_price": 20.0,
                "keepa_drop_percent": 10.0,
                "all_time_low": 18.0,
                "affiliate_url": "https://amazon.it"
            }
        ]
        bot.get_user_wishlist = MagicMock(return_value=mock_wish)
        bot.send_wishlist_message(123)
        self.assertGreater(bot.send_message.call_count, 1)

if __name__ == "__main__":
    unittest.main()
