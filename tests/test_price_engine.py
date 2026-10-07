"""
Test Suite: Price Engine (core/price_engine.py)
Testa la gestione del database, il calcolo dei ribassi,
All-Time Low e il recupero delle top offerte.
"""

import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from core.price_engine import KeepaStylePriceEngine

ENGINE_TEST_DB = os.path.join(BASE_DIR, "data", "test_engine_unit.db")
SEED_JSON = os.path.join(BASE_DIR, "data", "categories_and_products.json")

class TestPriceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.path.exists(ENGINE_TEST_DB):
            os.remove(ENGINE_TEST_DB)
        cls.engine = KeepaStylePriceEngine(ENGINE_TEST_DB)
        cls.engine.seed_from_json(SEED_JSON)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(ENGINE_TEST_DB):
            os.remove(ENGINE_TEST_DB)

    def test_seed_populated(self):
        top_deals = self.engine.get_top_deals()
        self.assertGreater(len(top_deals), 0)
        first_deal = top_deals[0]
        self.assertIn("discount_percent", first_deal)
        self.assertIn("affiliate_link", first_deal)

    def test_add_alert_and_trigger(self):
        # Aggiunge alert per SKU-BABY-001 a 35.00
        self.engine.add_user_alert("test_usr", "telegram", "SKU-BABY-001", 35.00)

        # Trigger calo di prezzo a 32.00 (minore di 35.00)
        notifications = self.engine.record_price_update("SKU-BABY-001", 32.00)
        self.assertEqual(len(notifications), 1)
        notif = notifications[0]
        self.assertEqual(notif["user_id"], "test_usr")
        self.assertEqual(notif["new_price"], 32.00)
        self.assertTrue(notif["is_all_time_low"])

    def test_record_price_update_nonexistent_product(self):
        notifications = self.engine.record_price_update("SKU-INVENTATO-999", 10.00)
        self.assertEqual(len(notifications), 0)

if __name__ == "__main__":
    unittest.main()
