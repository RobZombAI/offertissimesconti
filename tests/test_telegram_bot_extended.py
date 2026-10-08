"""
Extended Test Suite: Telegram Bot Runner (bot/telegram_bot_runner.py)
Copre il 100% dei rami di esecuzione: token loader, connessione, polling,
gestione errori di rete, tutti i comandi ed eccezioni.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import bot.telegram_bot_runner as runner
from bot.telegram_bot_runner import OffertissimeScontiTelegramBot, get_bot_token

class TestTelegramBotExtended(unittest.TestCase):
    def test_get_bot_token_from_env(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token_123"}):
            self.assertEqual(get_bot_token(), "token_123")

    def test_get_bot_token_from_env_file(self):
        with patch.dict(os.environ, {}, clear=True):
            # Assicurati che legga dal file .env esistente se presente
            token = get_bot_token()
            self.assertIsInstance(token, str)

    def test_test_connection_success_and_fail(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {"ok": True, "result": {"username": "my_bot"}}
            res = bot.test_connection()
            self.assertTrue(res["ok"])

            mock_get.return_value.json.return_value = {"ok": False, "error_code": 401}
            res_fail = bot.test_connection()
            self.assertFalse(res_fail["ok"])

    def test_send_message_branches(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        with patch("requests.post") as mock_post:
            # 1. Successo
            mock_post.return_value.json.return_value = {"ok": True}
            res = bot.send_message(123, "Hello", reply_markup={"inline_keyboard": []})
            self.assertTrue(res["ok"])

            # 2. Errore API da Telegram
            mock_post.return_value.json.return_value = {"ok": False, "description": "Blocked"}
            res2 = bot.send_message(123, "Hello")
            self.assertFalse(res2["ok"])

            # 3. Eccezione di rete
            mock_post.side_effect = Exception("Connection error")
            res3 = bot.send_message(123, "Hello")
            self.assertFalse(res3["ok"])

    def test_answer_callback_query(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        with patch("requests.post") as mock_post:
            bot.answer_callback_query("cb_id_123", text="Alert!")
            mock_post.assert_called_once()

            # Con eccezione
            mock_post.side_effect = Exception("fail")
            bot.answer_callback_query("cb_id_123") # non deve sollevare errore

    def test_get_updates_success_and_exception(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "ok": True,
                "result": [{"update_id": 100, "message": {"text": "ciao", "chat": {"id": 1}}}]
            }
            updates = bot.get_updates()
            self.assertEqual(len(updates), 1)

            # Eccezione
            mock_get.side_effect = Exception("Timeout")
            empty_updates = bot.get_updates()
            self.assertEqual(empty_updates, [])

    def test_empty_message(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()
        bot.handle_message({"chat": {"id": 1}, "text": ""})
        bot.send_message.assert_not_called()

    def test_search_no_results(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()
        bot.handle_message({"chat": {"id": 1}, "text": "/cerca xxxx_prodotto_impossibile_xxxx"})
        self.assertTrue(any("Nessun prodotto trovato" in str(c) for c in bot.send_message.call_args_list))

    def test_generic_text_fallback(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()
        bot.handle_message({"chat": {"id": 1}, "text": "zzzz_nessun_risultato_zzzz"})
        self.assertTrue(any("Non ho trovato risultati" in str(c) for c in bot.send_message.call_args_list))

    def test_track_invalid_syntax_and_price(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()

        # Argomenti insufficienti
        bot.handle_message({"chat": {"id": 1}, "text": "/track SKU-1"})
        self.assertTrue(any("Formato:" in str(c) for c in bot.send_message.call_args_list))

        # Prezzo non numerico
        bot.handle_message({"chat": {"id": 1}, "text": "/track SKU-1 abc"})
        self.assertTrue(any("Prezzo non valido" in str(c) for c in bot.send_message.call_args_list))

    def test_wishlist_empty(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()
        bot.get_user_wishlist = MagicMock(return_value=[])
        bot.send_wishlist_message(99999999)
        self.assertTrue(any("vuota" in str(c) for c in bot.send_message.call_args_list))

    def test_track_callback_action(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.save_user_alert = MagicMock()
        bot.send_message = MagicMock()
        bot.answer_callback_query = MagicMock()

        cb = {
            "id": "cb_track_1",
            "data": "track_SKU-REAL-0001_12.50",
            "message": {"chat": {"id": 888}}
        }
        bot.handle_callback(cb)
        bot.save_user_alert.assert_called_with(888, "SKU-REAL-0001", 12.50)
        bot.answer_callback_query.assert_called()

    def test_run_polling_connection_failure(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.test_connection = MagicMock(return_value={"ok": False})
        # Deve terminare senza errori se la connessione fallisce
        bot.run_polling()

    def test_run_polling_one_loop_then_interrupt(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.test_connection = MagicMock(return_value={"ok": True, "result": {"username": "test_bot"}})
        
        # Simula 1 update poi interrompe il loop con un'eccezione personalizzata
        bot.get_updates = MagicMock(side_effect=[
            [{"update_id": 1, "message": {"text": "/start", "chat": {"id": 1}}}],
            [{"update_id": 2, "callback_query": {"id": "c1", "data": "menu_deals", "message": {"chat": {"id": 1}}}}],
            KeyboardInterrupt()
        ])
        bot.handle_message = MagicMock()
        bot.handle_callback = MagicMock()

        with patch("time.sleep", return_value=None):
            with self.assertRaises(KeyboardInterrupt):
                bot.run_polling()
            self.assertEqual(bot.handle_message.call_count, 1)
            self.assertEqual(bot.handle_callback.call_count, 1)

    def test_run_polling_handler_and_loop_exceptions(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.test_connection = MagicMock(return_value={"ok": True, "result": {"username": "test_bot"}})
        bot.get_updates = MagicMock(side_effect=[
            [{"update_id": 10, "message": {"text": "/test", "chat": {"id": 1}}}],
            Exception("Loop error"),
            KeyboardInterrupt()
        ])
        bot.handle_message = MagicMock(side_effect=Exception("Handler crash"))

        with patch("time.sleep", return_value=None):
            with self.assertRaises(KeyboardInterrupt):
                bot.run_polling()
            self.assertEqual(bot.handle_message.call_count, 1)

    def test_handle_callback_empty_or_malformed(self):
        bot = OffertissimeScontiTelegramBot("fake_token")
        bot.send_message = MagicMock()
        bot.answer_callback_query = MagicMock()

        # Missing cb id
        bot.handle_callback({"message": {"chat": {"id": 123}}, "data": "menu_deals"})
        bot.send_message.assert_not_called()

        # Missing chat id
        bot.handle_callback({"id": "cb1", "message": None, "data": "menu_deals"})
        bot.send_message.assert_not_called()

if __name__ == "__main__":
    unittest.main()
