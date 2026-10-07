"""
Price Engine & Deal Tracker (Keepa-Style Core)
Modello di monitoraggio prezzi, calcolo minimi storici e dispatch degli alert di ribasso.
"""

import json
import sqlite3
import datetime
from typing import Dict, List, Optional, Tuple

class KeepaStylePriceEngine:
    def __init__(self, db_path: str = "deals_tracker.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Tabella Prodotti
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    asin TEXT UNIQUE,
                    name TEXT,
                    category TEXT,
                    brand TEXT,
                    cycle_days INTEGER,
                    virality_score INTEGER,
                    current_price REAL,
                    list_price REAL,
                    all_time_low REAL,
                    affiliate_tag TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Tabella Storico Prezzi (Keepa-like time series)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT,
                    price REAL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
            """)
            # Tabella Alert Utenti (Wishlist con soglia di prezzo desiderata)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    channel TEXT, -- 'telegram', 'app_push', 'web'
                    product_id TEXT,
                    target_price REAL,
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
            """)
            conn.commit()

    def seed_from_json(self, json_path: str):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for p in data.get("sample_products", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO products (
                        id, asin, name, category, brand, cycle_days,
                        virality_score, current_price, list_price, all_time_low, affiliate_tag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["id"], p["asin"], p["name"], p["category"], p["brand"],
                    p["cycle_days"], p["virality_score"], p["current_price"],
                    p["list_price"], p["all_time_low"], "dealtracker-21"
                ))
                # Seed iniziale dello storico
                cursor.execute("""
                    INSERT INTO price_history (product_id, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (p["id"], p["avg_price_30d"], (datetime.datetime.now() - datetime.timedelta(days=15)).isoformat()))
                cursor.execute("""
                    INSERT INTO price_history (product_id, price, recorded_at)
                    VALUES (?, ?, ?)
                """, (p["id"], p["current_price"], datetime.datetime.now().isoformat()))
            conn.commit()

    def add_user_alert(self, user_id: str, channel: str, product_id: str, target_price: float):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                VALUES (?, ?, ?, ?)
            """, (user_id, channel, product_id, target_price))
            conn.commit()

    def record_price_update(self, product_id: str, new_price: float) -> List[Dict]:
        """
        Registra un nuovo prezzo e genera notifiche se:
        1. Il prezzo tocca o batte il Minimo Storico (All-Time Low)
        2. Il prezzo scende sotto la soglia impostata dagli utenti nella Wishlist
        """
        notifications = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, all_time_low, current_price, affiliate_tag, asin FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if not row:
                return []

            name, atl, old_price, tag, asin = row
            is_new_atl = new_price < atl

            # Aggiorna storico
            cursor.execute("INSERT INTO price_history (product_id, price) VALUES (?, ?)", (product_id, new_price))
            
            # Aggiorna all_time_low se battuto
            updated_atl = min(atl, new_price)
            cursor.execute("""
                UPDATE products 
                SET current_price = ?, all_time_low = ?
                WHERE id = ?
            """, (new_price, updated_atl, product_id))

            # Recupera allarmi attivi per gli utenti
            cursor.execute("""
                SELECT id, user_id, channel, target_price 
                FROM user_alerts 
                WHERE product_id = ? AND active = 1 AND target_price >= ?
            """, (product_id, new_price))
            alerts = cursor.fetchall()

            affiliate_link = f"https://www.amazon.it/dp/{asin}?tag={tag}"

            for alert_id, user_id, channel, target_price in alerts:
                notifications.append({
                    "user_id": user_id,
                    "channel": channel,
                    "product_name": name,
                    "old_price": old_price,
                    "new_price": new_price,
                    "target_price": target_price,
                    "is_all_time_low": is_new_atl,
                    "affiliate_link": affiliate_link,
                    "discount_percent": round(((old_price - new_price) / old_price) * 100, 1) if old_price > new_price else 0
                })

            conn.commit()

        return notifications

    def get_top_deals(self) -> List[Dict]:
        """Restituisce le offerte con il maggior ribasso rispetto al prezzo di listino o all'ATL."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, category, current_price, list_price, all_time_low, asin, affiliate_tag
                FROM products
                ORDER BY ((list_price - current_price) / list_price) DESC
                LIMIT 10
            """)
            rows = cursor.fetchall()
            deals = []
            for r in rows:
                discount = round(((r[4] - r[3]) / r[4]) * 100, 1)
                deals.append({
                    "id": r[0],
                    "name": r[1],
                    "category": r[2],
                    "current_price": r[3],
                    "list_price": r[4],
                    "all_time_low": r[5],
                    "discount_percent": discount,
                    "affiliate_link": f"https://www.amazon.it/dp/{r[6]}?tag={r[7]}"
                })
            return deals

if __name__ == "__main__":
    engine = KeepaStylePriceEngine("data/tracker_test.db")
    engine.seed_from_json("data/categories_and_products.json")
    print("Database popolato con successo.")

    # Simula un utente Telegram che imposta un alert su Pampers Progressi (attualmente a €49.90, vuole €42.00)
    engine.add_user_alert(user_id="tg_987654", channel="telegram", product_id="SKU-BABY-001", target_price=42.00)
    print("Alert aggiunto per utente tg_987654 su SKU-BABY-001 a soglia €42.00")

    # Simula un drop di prezzo improvviso su Amazon a €39.90 (Minimo Storico!)
    alerts_triggered = engine.record_price_update(product_id="SKU-BABY-001", new_price=39.90)
    print(f"\nAllarmi scattati ({len(alerts_triggered)}):")
    for a in alerts_triggered:
        print(f"-> A {a['user_id']} ({a['channel']}): {a['product_name']} sceso a €{a['new_price']}! Link: {a['affiliate_link']}")
