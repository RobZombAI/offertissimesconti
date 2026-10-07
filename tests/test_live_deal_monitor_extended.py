"""
Extended Test Suite: Live Deal Monitor (core/live_deal_monitor.py)
Copre il 100% dei rami di esecuzione: token loader, notifiche Telegram,
errori di rete, periodic monitoring loop.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.live_deal_monitor import LiveDealMonitor, get_bot_token

class TestLiveDealMonitorExtended(unittest.TestCase):
    def test_get_bot_token(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "sample_token"}):
            self.assertEqual(get_bot_token(), "sample_token")

    def test_send_telegram_alert_api_error(self):
        monitor = LiveDealMonitor(bot_token="token_xyz")
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"ok": False, "description": "Chat not found"}
            res = monitor.send_telegram_alert("999", "Hello", keyboard={"inline_keyboard": []})
            self.assertFalse(res)

    def test_send_telegram_alert_exception(self):
        monitor = LiveDealMonitor(bot_token="token_xyz")
        with patch("requests.post", side_effect=Exception("Network down")):
            res = monitor.send_telegram_alert("999", "Hello")
            self.assertFalse(res)

    def test_check_user_alerts_success_branch(self):
        import tempfile
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
                INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                VALUES ('user_mock_success', 'telegram', 'SKU-TEST-SUCCESS', 500.0)
            """)
            cur.execute("""
                INSERT INTO products_catalog VALUES (
                    'SKU-TEST-SUCCESS', 'B00SUCCESS', 'Prodotto Successo', 'Brand', 'beauty_personal_care',
                    10.0, 20.0, 10.0, 15.0, 'https://www.amazon.it/dp/B00SUCCESS?tag=offertissimesconti-21', 33.3
                )
            """)
            conn.commit()
            conn.close()

            monitor = LiveDealMonitor(db_path=tmp.name, bot_token="token_xyz")
            monitor.send_telegram_alert = MagicMock(return_value=True)
            notified = monitor.check_user_alerts()
            self.assertGreaterEqual(notified, 1)

    def test_run_periodic_monitoring_interrupted(self):
        monitor = LiveDealMonitor(bot_token="token_xyz")
        monitor.check_user_alerts = MagicMock(return_value=1)
        with patch("time.sleep", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                monitor.run_periodic_monitoring(interval_seconds=1)
            monitor.check_user_alerts.assert_called_once()
