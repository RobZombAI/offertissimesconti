"""
Test Suite: Telegram Deal Bot Simulator (bot/telegram_deal_bot.py)
Copre tutte le funzioni del simulatore bot e la formattazione Keepa.
"""

import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from bot.telegram_deal_bot import TelegramMasterDealBot

class TestTelegramDealBot(unittest.TestCase):
    def setUp(self):
        self.bot = TelegramMasterDealBot()

    def test_format_deal_post_standard(self):
        sample = {
            "title": "Caffè Borbone Cialde",
            "macro_category_id": "grocery_coffee",
            "brand": "Borbone",
            "is_cyclical": 1,
            "cycle_days": 30,
            "virality_score": 95,
            "keepa_drop_percent": 25.0,
            "current_price": 18.00,
            "list_price": 24.00,
            "all_time_low": 17.50,
            "avg_price_30d": 22.00,
            "affiliate_url": "https://www.amazon.it/dp/B073XVK2V1?tag=offertissimes-21",
            "sku_id": "SKU-COFF-0001"
        }
        post = self.bot.format_deal_post(sample)
        self.assertIn("OFFERTISSIMESCONTI", post)
        self.assertIn("CICLICO", post)
        self.assertIn("Borbone", post)
        self.assertIn("€18.00", post)

    def test_format_deal_post_atl(self):
        sample_atl = {
            "title": "Finish Pastiglie",
            "macro_category_id": "cleaning_household",
            "brand": "Finish",
            "is_cyclical": 0,
            "cycle_days": 90,
            "virality_score": 88,
            "keepa_drop_percent": 30.0,
            "current_price": 15.00,
            "list_price": 25.00,
            "all_time_low": 15.00, # ATL raggiunto
            "avg_price_30d": 20.00,
            "affiliate_url": "https://www.amazon.it/dp/B08N582H3N?tag=offertissimes-21",
            "sku_id": "SKU-CLEAN-0001"
        }
        post = self.bot.format_deal_post(sample_atl)
        self.assertIn("MINIMO STORICO ASSOLUTO", post)
        self.assertIn("VIRALE / TREND", post)

    def test_get_top_deals_with_category(self):
        deals = self.bot.get_top_deals(category="beauty_personal_care", limit=2)
        self.assertLessEqual(len(deals), 2)
        for d in deals:
            self.assertEqual(d["macro_category_id"], "beauty_personal_care")

    def test_get_top_deals_only_cyclical(self):
        deals = self.bot.get_top_deals(only_cyclical=True, limit=3)
        self.assertGreater(len(deals), 0)
        for d in deals:
            self.assertEqual(d["is_cyclical"], 1)

    def test_get_top_deals_only_non_cyclical(self):
        deals = self.bot.get_top_deals(only_cyclical=False, limit=3)
        self.assertGreater(len(deals), 0)
        for d in deals:
            self.assertEqual(d["is_cyclical"], 0)

    def test_search_product(self):
        top_deal = self.bot.get_top_deals(limit=1)
        query = top_deal[0]["brand"] if top_deal and top_deal[0]["brand"] else "Samsung"
        results = self.bot.search_product(query, limit=3)
        self.assertGreater(len(results), 0)

if __name__ == "__main__":
    unittest.main()
