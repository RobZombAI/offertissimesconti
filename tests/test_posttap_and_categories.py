"""
Test Suite: PostTap Export, Dynamic Sorting & Telegram Category Smart Lists
Copre le nuove funzionalità introdotte per l'export dei 3.396 link e la navigazione
a lista per categorie sia sul web server che sul bot Telegram.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from api.server import OffertissimeScontiServer
from bot.telegram_bot_runner import OffertissimeScontiTelegramBot

class TestPostTapAndCategories(unittest.TestCase):
    def setUp(self):
        self.bot = OffertissimeScontiTelegramBot(token="123456:TEST_TOKEN")
        self.bot.send_message = MagicMock(return_value={"ok": True})
        self.bot.send_document = MagicMock(return_value={"ok": True})
        self.bot.answer_callback_query = MagicMock(return_value=True)

    def test_bot_get_categories_stats(self):
        cats = self.bot.get_categories_stats()
        self.assertIsInstance(cats, list)
        self.assertEqual(len(cats), 15)
        self.assertIn("macro_category_id", cats[0])
        self.assertIn("count", cats[0])

    def test_bot_get_category_deals(self):
        deals = self.bot.get_category_deals("beauty_personal_care", limit=3)
        self.assertIsInstance(deals, list)
        self.assertGreater(len(deals), 0)
        self.assertEqual(deals[0]["macro_category_id"], "beauty_personal_care")

    def test_bot_get_categories_keyboard(self):
        kb = self.bot.get_categories_keyboard()
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        self.assertGreater(len(rows), 5)
        # Verifica presenza tasto torna indietro
        self.assertTrue(any(btn["text"].startswith("🔙") for row in rows for btn in row))

    def test_bot_send_category_smart_list(self):
        self.bot.send_category_smart_list(chat_id=12345, category_id="beauty_personal_care")
        self.assertGreater(self.bot.send_message.call_count, 1)

    def test_bot_send_category_smart_list_empty(self):
        self.bot.send_category_smart_list(chat_id=12345, category_id="non_existing_category_xyz")
        self.assertTrue(self.bot.send_message.called)

    def test_bot_send_export_document(self):
        self.bot.send_export_document(chat_id=12345)
        self.assertTrue(self.bot.send_document.called)

    def test_bot_send_export_document_fallback(self):
        self.bot.send_document = MagicMock(return_value={"ok": False})
        self.bot.send_export_document(chat_id=12345)
        self.assertTrue(self.bot.send_message.called)

    def test_bot_handle_message_categories(self):
        msg = {
            "chat": {"id": 12345},
            "text": "/categorie",
            "from": {"first_name": "TestUser"}
        }
        self.bot.handle_message(msg)
        self.assertTrue(self.bot.send_message.called)

    def test_bot_handle_message_export(self):
        msg = {
            "chat": {"id": 12345},
            "text": "/export",
            "from": {"first_name": "TestUser"}
        }
        self.bot.handle_message(msg)
        self.assertTrue(self.bot.send_document.called)

    def test_bot_handle_callback_categories(self):
        cb = {
            "id": "cb_001",
            "data": "menu_categories",
            "message": {"chat": {"id": 12345}}
        }
        self.bot.handle_callback(cb)
        self.assertTrue(self.bot.answer_callback_query.called)
        self.assertTrue(self.bot.send_message.called)

    def test_bot_handle_callback_export(self):
        cb = {
            "id": "cb_002",
            "data": "menu_export",
            "message": {"chat": {"id": 12345}}
        }
        self.bot.handle_callback(cb)
        self.assertTrue(self.bot.answer_callback_query.called)
        self.assertTrue(self.bot.send_document.called)

    def test_bot_handle_callback_main_menu(self):
        cb = {
            "id": "cb_003",
            "data": "menu_main",
            "message": {"chat": {"id": 12345}}
        }
        self.bot.handle_callback(cb)
        self.assertTrue(self.bot.answer_callback_query.called)
        self.assertTrue(self.bot.send_message.called)

    def test_bot_handle_callback_cat_selection(self):
        cb = {
            "id": "cb_004",
            "data": "cat_beauty_personal_care",
            "message": {"chat": {"id": 12345}}
        }
        self.bot.handle_callback(cb)
        self.assertTrue(self.bot.answer_callback_query.called)
        self.assertGreater(self.bot.send_message.call_count, 1)

    @patch("requests.post")
    def test_bot_send_document_network(self, mock_post):
        mock_post.return_value.json.return_value = {"ok": True}
        csv_file = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
        bot_real = OffertissimeScontiTelegramBot(token="123456:REAL")
        res = bot_real.send_document(chat_id=123, file_path=csv_file, caption="Caption test")
        self.assertTrue(res.get("ok"))

    def test_bot_send_document_file_not_found(self):
        bot_real = OffertissimeScontiTelegramBot(token="123456:REAL")
        res = bot_real.send_document(chat_id=123, file_path="non_existing_file_999.csv")
        self.assertFalse(res.get("ok"))

    @patch("requests.post")
    def test_bot_send_document_exception(self, mock_post):
        mock_post.side_effect = Exception("Network down")
        csv_file = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
        bot_real = OffertissimeScontiTelegramBot(token="123456:REAL")
        res = bot_real.send_document(chat_id=123, file_path=csv_file)
        self.assertFalse(res.get("ok"))

if __name__ == "__main__":
    unittest.main()
