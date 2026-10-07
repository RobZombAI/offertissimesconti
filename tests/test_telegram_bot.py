"""
Test Suite: Telegram Bot Runner (bot/telegram_bot_runner.py)
Testa la gestione dei comandi, le query sul catalogo, la formattazione dei messaggi,
le tastiere inline, e la gestione della wishlist.
"""

import unittest
from unittest.mock import MagicMock
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from bot.telegram_bot_runner import OffertissimeScontiTelegramBot

class TestTelegramBotRunner(unittest.TestCase):
    def setUp(self):
        self.bot = OffertissimeScontiTelegramBot(token="123456:FAKE_TOKEN_FOR_TESTS")
        # Mock send_message per testare la logica interna senza rete
        self.bot.send_message = MagicMock(return_value={"ok": True})
        self.bot.answer_callback_query = MagicMock(return_value=True)

    def test_main_menu_keyboard_structure(self):
        kb = self.bot.get_main_menu_keyboard()
        self.assertIn("inline_keyboard", kb)
        buttons = [btn["text"] for row in kb["inline_keyboard"] for btn in row]
        self.assertTrue(any("Top Offerte" in b for b in buttons))
        self.assertTrue(any("Minimi Storici" in b for b in buttons))
        self.assertTrue(any("Spesa Ciclica" in b for b in buttons))
        self.assertTrue(any("I Miei Prodotti Seguiti" in b for b in buttons))

    def test_deal_keyboard_affiliate_link(self):
        sample_prod = {
            "sku_id": "SKU-TEST-01",
            "current_price": 20.0,
            "affiliate_url": "https://www.amazon.it/dp/B00TEST?tag=offertissimesconti-21"
        }
        kb = self.bot.get_deal_keyboard(sample_prod)
        self.assertIn("inline_keyboard", kb)
        buy_btn = kb["inline_keyboard"][0][0]
        self.assertIn("url", buy_btn)
        self.assertEqual(buy_btn["url"], sample_prod["affiliate_url"])

        track_btn = kb["inline_keyboard"][1][0]
        self.assertIn("callback_data", track_btn)
        self.assertTrue(track_btn["callback_data"].startswith("track_SKU-TEST-01_"))

    def test_format_deal_html(self):
        sample_prod = {
            "sku_id": "SKU-BEAU-0001",
            "title": "Florence Siero Viso Bio",
            "brand": "Florence",
            "macro_category_id": "beauty_personal_care",
            "is_cyclical": 1,
            "cycle_days": 40,
            "current_price": 9.99,
            "list_price": 15.99,
            "all_time_low": 9.99,
            "avg_price_30d": 14.00,
            "keepa_drop_percent": 28.6
        }
        html = self.bot.format_deal_html(sample_prod)
        self.assertIn("OFFERTISSIMESCONTI", html)
        self.assertIn("Florence Siero Viso Bio", html)
        self.assertIn("MINIMO STORICO ASSOLUTO", html)
        self.assertIn("€9.99", html)

    def test_handle_start_command(self):
        msg = {
            "chat": {"id": 999},
            "text": "/start",
            "from": {"first_name": "Mario"}
        }
        self.bot.handle_message(msg)
        self.bot.send_message.assert_called_once()
        args, kwargs = self.bot.send_message.call_args
        self.assertEqual(args[0], 999)
        self.assertIn("Mario", args[1])

    def test_handle_deals_command(self):
        msg = {"chat": {"id": 999}, "text": "/deals", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.assertGreater(self.bot.send_message.call_count, 1)

    def test_handle_minimi_command(self):
        msg = {"chat": {"id": 999}, "text": "/minimi", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.assertGreater(self.bot.send_message.call_count, 1)

    def test_handle_ciclici_command(self):
        msg = {"chat": {"id": 999}, "text": "/ciclici", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.assertGreater(self.bot.send_message.call_count, 1)

    def test_handle_search_command_with_results(self):
        msg = {"chat": {"id": 999}, "text": "/cerca Borbone", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.assertGreater(self.bot.send_message.call_count, 1)

    def test_handle_search_command_empty(self):
        msg = {"chat": {"id": 999}, "text": "/cerca", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.bot.send_message.assert_called_once()
        args = self.bot.send_message.call_args[0]
        self.assertIn("Inserisci cosa cercare", args[1])

    def test_handle_track_command(self):
        msg = {"chat": {"id": 999}, "text": "/track SKU-BEAU-0001 8.50", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.bot.send_message.assert_called_once()
        args = self.bot.send_message.call_args[0]
        self.assertIn("Allerta impostata con successo", args[1])

    def test_handle_wishlist_command(self):
        msg = {"chat": {"id": 999}, "text": "/wishlist", "from": {"first_name": "Mario"}}
        self.bot.handle_message(msg)
        self.assertGreater(self.bot.send_message.call_count, 0)

    def test_callbacks_navigation(self):
        for action in ["menu_deals", "menu_minimi", "menu_ciclici", "menu_wishlist", "menu_search_help"]:
            cb = {
                "id": "cb_1",
                "data": action,
                "message": {"chat": {"id": 999}}
            }
            self.bot.handle_callback(cb)
            self.bot.answer_callback_query.assert_called()

if __name__ == "__main__":
    unittest.main()
