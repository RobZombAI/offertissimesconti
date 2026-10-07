"""
Test Suite: Live Deal Monitor & Alert Dispatcher (core/live_deal_monitor.py)
Testa la logica di calcolo dei ribassi, dispatch delle notifiche,
aggiornamento dei prezzi nel database e gestione dello storico.
"""

import unittest
import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.live_deal_monitor import LiveDealMonitor

TEST_DB = os.path.join(BASE_DIR, "data", "test_deal_monitor.db")

class TestLiveDealMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Crea database di test isolato
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        conn = sqlite3.connect(TEST_DB)
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
            CREATE TABLE price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id TEXT,
                price REAL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Inserisci prodotto di test
        cur.execute("""
            INSERT INTO products_catalog VALUES (
                'SKU-TEST-A', 'B00TEST001', 'Prodotto Test Siero', 'BrandTest',
                'beauty_personal_care', 15.00, 25.00, 14.00, 20.00,
                'https://www.amazon.it/dp/B00TEST001?tag=offertissimes-21', 25.0
            )
        """)
        # Alert: utente vuole comprare a <= 12.00 (ora a 15.00, quindi non deve scattare)
        cur.execute("""
            INSERT INTO user_alerts (user_id, channel, product_id, target_price)
            VALUES ('test_chat_99', 'telegram', 'SKU-TEST-A', 12.00)
        """)
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_alert_not_triggered_if_above_target(self):
        monitor = LiveDealMonitor(db_path=TEST_DB, bot_token="fake_token")
        notified = monitor.check_user_alerts()
        self.assertEqual(notified, 0, "L'alert non deve scattare se il prezzo è sopra il target")

    def test_update_product_price_and_trigger(self):
        monitor = LiveDealMonitor(db_path=TEST_DB, bot_token="fake_token")
        # Aggiorna il prezzo a 10.50 (sotto la soglia di 12.00)
        updated = monitor.update_product_price("SKU-TEST-A", 10.50)
        self.assertTrue(updated)

        conn = sqlite3.connect(TEST_DB)
        cur = conn.cursor()
        cur.execute("SELECT current_price, all_time_low FROM products_catalog WHERE sku_id = 'SKU-TEST-A'")
        curr, atl = cur.fetchone()
        self.assertEqual(curr, 10.50)
        self.assertEqual(atl, 10.50) # nuovo all time low!

        # Verifica inserimento in price_history
        cur.execute("SELECT COUNT(*) FROM price_history WHERE sku_id = 'SKU-TEST-A'")
        self.assertGreater(cur.fetchone()[0], 0)
        conn.close()

    def test_update_nonexistent_product(self):
        monitor = LiveDealMonitor(db_path=TEST_DB, bot_token="fake_token")
        updated = monitor.update_product_price("SKU-FANTASMA", 5.0)
        self.assertFalse(updated)

    def test_send_telegram_alert_without_token(self):
        monitor = LiveDealMonitor(db_path=TEST_DB, bot_token="")
        sent = monitor.send_telegram_alert("12345", "Test")
        self.assertFalse(sent)

if __name__ == "__main__":
    unittest.main()
