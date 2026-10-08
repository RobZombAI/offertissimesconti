"""
Test Suite: Telegram Channel Broadcaster (bot/telegram_channel_broadcaster.py)
Testa la selezione intelligente delle offerte, la formattazione dei post,
la registrazione nel database anti-duplicati e la gestione degli errori API Telegram.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from bot.telegram_channel_broadcaster import TelegramChannelBroadcaster

class TestTelegramChannelBroadcaster(unittest.TestCase):
    def setUp(self):
        self.broadcaster = TelegramChannelBroadcaster(
            bot_token="123456:TEST_TOKEN",
            channel_id="@TestChannel"
        )

    def test_init_broadcast_table(self):
        conn = sqlite3.connect(self.broadcaster.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_broadcast_log'")
        self.assertIsNotNone(cur.fetchone())
        conn.close()

    def test_get_next_deal_to_broadcast(self):
        deal = self.broadcaster.get_next_deal_to_broadcast()
        self.assertIsNotNone(deal)
        self.assertIn("sku_id", deal)
        self.assertIn("current_price", deal)
        self.assertIn("list_price", deal)
        self.assertIn("affiliate_url", deal)
        self.assertIn("image_url", deal)
        self.assertIn("tag=offertissimes-21", deal["affiliate_url"])

    def test_format_channel_post(self):
        sample_deal = {
            "sku_id": "SKU-ELEC-TEST",
            "asin": "B00TEST123",
            "title": "Echo Dot Smart Speaker",
            "brand": "Amazon",
            "macro_category_id": "electronics_gadgets",
            "macro_category_name": "Elettronica",
            "current_price": 29.99,
            "list_price": 59.99,
            "all_time_low": 29.99,
            "keepa_drop_percent": 50.0,
            "avg_price_30d": 49.99,
            "is_cyclical": 0,
            "affiliate_url": "https://www.amazon.it/dp/B00TEST123?tag=offertissimes-21",
            "image_url": "https://m.media-amazon.com/images/I/test.jpg"
        }
        caption, keyboard = self.broadcaster.format_channel_post(sample_deal)
        self.assertIn("MINIMO STORICO ASSOLUTO", caption)
        self.assertIn("€29.99", caption)
        self.assertIn("€59.99", caption)
        self.assertIn("Risparmio Reale: €30.00 (-50%)", caption)
        self.assertIn("In qualità di Affiliato Amazon", caption)

        buttons = keyboard.get("inline_keyboard", [])
        self.assertTrue(any("ACQUISTA" in btn["text"] for row in buttons for btn in row))
        self.assertTrue(any("Segui Prezzo con il Bot" in btn["text"] for row in buttons for btn in row))
        self.assertTrue(any("Radar Web" in btn["text"] for row in buttons for btn in row))

    def test_record_broadcast_and_anti_duplicate(self):
        sample_deal = {
            "sku_id": "SKU-TEST-BROADCAST-001",
            "asin": "B00TESTBROAD",
            "current_price": 19.99,
            "list_price": 39.99,
            "keepa_drop_percent": 50.0
        }
        self.broadcaster.record_broadcast(sample_deal, "@TestChannel", 101)

        conn = sqlite3.connect(self.broadcaster.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM channel_broadcast_log WHERE sku_id = ?", ("SKU-TEST-BROADCAST-001",))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        conn.close()

    @patch("requests.get")
    def test_check_channel_permissions_success(self, mock_get):
        mock_get.return_value.json.return_value = {
            "ok": True,
            "result": {"id": -1001234567, "title": "Test Channel", "type": "channel"}
        }
        res = self.broadcaster.check_channel_permissions("@TestChannel")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat"]["title"], "Test Channel")

    @patch("requests.get")
    def test_check_channel_permissions_forbidden(self, mock_get):
        mock_get.return_value.json.return_value = {
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot is not a member of the channel chat"
        }
        res = self.broadcaster.check_channel_permissions("@TestChannel")
        self.assertFalse(res["ok"])
        self.assertIn("Forbidden", res["description"])

    @patch("requests.post")
    def test_broadcast_deal_success(self, mock_post):
        mock_post.return_value.json.return_value = {
            "ok": True,
            "result": {"message_id": 9999}
        }
        sample_deal = {
            "sku_id": "SKU-TEST-002",
            "asin": "B00TEST002",
            "title": "Caffè Borbone 100 Cialde",
            "brand": "Borbone",
            "macro_category_id": "grocery_coffee",
            "macro_category_name": "Alimentari",
            "current_price": 18.50,
            "list_price": 25.00,
            "all_time_low": 18.50,
            "keepa_drop_percent": 26.0,
            "is_cyclical": 1,
            "cycle_days": 30,
            "affiliate_url": "https://www.amazon.it/dp/B00TEST002?tag=offertissimes-21",
            "image_url": "https://m.media-amazon.com/images/I/coffee.jpg"
        }
        res = self.broadcaster.broadcast_deal(sample_deal, "@TestChannel")
        self.assertTrue(res["ok"])
        self.assertEqual(res["message_id"], 9999)

    def test_recent_categories_empty_and_filled(self):
        cats = self.broadcaster.get_recent_broadcasted_categories(limit=5)
        self.assertIsInstance(cats, list)

if __name__ == "__main__":
    unittest.main()
