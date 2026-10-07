"""
Test Suite: Database & Catalog Data Integrity
Verifica la correttezza, completezza e validità di tutti i 3.380+ prodotti
presenti in amazon_3000_master_catalog.db.
"""

import unittest
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "amazon_3000_master_catalog.db")

class TestDatabaseIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = sqlite3.connect(DB_PATH)
        cls.conn.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_database_exists_and_connected(self):
        self.assertTrue(os.path.exists(DB_PATH), "Il database SQLite non esiste")

    def test_minimum_catalog_size(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products_catalog")
        count = cur.fetchone()[0]
        self.assertGreaterEqual(count, 3000, f"Il catalogo deve contenere almeno 3000 prodotti (trovati: {count})")

    def test_all_15_macro_categories_present(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT macro_category_id FROM products_catalog")
        cats = [r[0] for r in cur.fetchall()]
        expected_cats = [
            "beauty_personal_care", "health_supplements", "grocery_coffee",
            "cleaning_household", "baby_care", "pet_supplies",
            "electronics_gadgets", "home_kitchen", "diy_tools_garden",
            "automotive", "sports_fitness_gear", "office_stationery",
            "apparel_basics", "toys_hobbies", "books_planners"
        ]
        for ec in expected_cats:
            self.assertIn(ec, cats, f"Categoria mancante nel catalogo: {ec}")

    def test_no_null_or_empty_critical_fields(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT sku_id, asin, title, brand, current_price, list_price, affiliate_url
            FROM products_catalog
            WHERE sku_id IS NULL OR asin IS NULL OR title IS NULL OR brand IS NULL 
               OR current_price IS NULL OR list_price IS NULL OR affiliate_url IS NULL
               OR title = '' OR asin = '' OR brand = ''
        """)
        bad_rows = cur.fetchall()
        self.assertEqual(len(bad_rows), 0, f"Trovati prodotti con campi critici nulli o vuoti: {len(bad_rows)}")

    def test_price_sanity_checks(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT sku_id, current_price, list_price, all_time_low, avg_price_30d
            FROM products_catalog
            WHERE current_price <= 0 OR list_price <= 0 OR all_time_low <= 0
        """)
        invalid_prices = cur.fetchall()
        self.assertEqual(len(invalid_prices), 0, f"Trovati prezzi negativi o zero: {len(invalid_prices)}")

    def test_affiliate_tag_and_amazon_urls(self):
        cur = self.conn.cursor()
        cur.execute("SELECT sku_id, affiliate_url FROM products_catalog")
        rows = cur.fetchall()
        for r in rows:
            url = r["affiliate_url"]
            self.assertTrue(url.startswith("https://www.amazon.it/"), f"URL non conforme ad Amazon.it: {url}")
            self.assertIn("tag=offertissimes-21", url, f"Tag affiliato errato o mancante: {url}")

    def test_cyclical_ratio_balance(self):
        cur = self.conn.cursor()
        cur.execute("SELECT SUM(is_cyclical), COUNT(*) FROM products_catalog")
        cyclical, total = cur.fetchone()
        ratio = cyclical / total
        self.assertGreaterEqual(ratio, 0.50, f"I prodotti ciclici devono essere almeno il 50% (trovato: {ratio:.1%})")
        self.assertLessEqual(ratio, 0.80, f"I prodotti ciclici non devono superare l'80% (trovato: {ratio:.1%})")

    def test_user_alerts_table_structure(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_alerts'")
        self.assertIsNotNone(cur.fetchone(), "Tabella user_alerts mancante nel database master")

    def test_price_history_table_structure(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'")
        self.assertIsNotNone(cur.fetchone(), "Tabella price_history mancante nel database master")

if __name__ == "__main__":
    unittest.main()
