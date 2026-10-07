"""
Telegram Deal Bot per Catalogo 3.000+ Prodotti Amazon
Supporta comandi interattivi per tutte le 15 categorie, filtri ciclici/virali,
ricerca istantanea su oltre 3.000 ASIN e alert di minimo storico in stile Keepa.
"""

import sqlite3
import os
import json
from typing import Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "amazon_3000_master_catalog.db")

class TelegramMasterDealBot:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def format_deal_post(self, prod: Dict) -> str:
        """Formatta un'offerta per Telegram in stile Keepa con grafici testuali e badge."""
        cyclical_badge = "🔄 CICLICO (RIACQUISTO)" if prod["is_cyclical"] else "⚡ VIRALE / TREND"
        drop_pct = prod["keepa_drop_percent"]
        is_atl = prod["current_price"] <= prod["all_time_low"]
        atl_badge = "\n🏆 *MINIMO STORICO ASSOLUTO!*" if is_atl else ""

        post = (
            f"🔥 *OFFERTISSIMESCONTI* | Sconto del *{drop_pct}%* | {cyclical_badge}\n\n"
            f"📦 *{prod['title']}*\n"
            f"🏷 Categoria: #{prod['macro_category_id']} • {prod['brand']}\n"
            f"⭐ Virality Score: {prod['virality_score']}/100{atl_badge}\n\n"
            f"💰 Prezzo Attuale: *€{prod['current_price']:.2f}*\n"
            f"❌ Prezzo di Listino: ~€{prod['list_price']:.2f}~\n"
            f"📉 Minimo Storico: €{prod['all_time_low']:.2f}\n"
            f"📊 Media 30 Giorni: €{prod['avg_price_30d']:.2f}\n\n"
            f"📈 *Trend Prezzo Keepa*:\n"
            f"`[Media: €{prod['avg_price_30d']:.2f} ===📉===> Oggi: €{prod['current_price']:.2f}]`\n"
            f"🔄 _Ciclo consigliato di riacquisto: ogni {prod['cycle_days']} giorni_\n\n"
            f"👉 [CLICCA QUI PER ACQUISTARE SU AMAZON]({prod['affiliate_url']})\n\n"
            f"🔔 _Per monitorare questo articolo: /track {prod['sku_id']} <prezzo>_"
        )
        return post

    def get_top_deals(self, category: Optional[str] = None, only_cyclical: Optional[bool] = None, limit: int = 5) -> List[Dict]:
        """Estrae le offerte con i ribassi percentuali maggiori."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        conditions = []
        params = []
        if category:
            conditions.append("macro_category_id = ?")
            params.append(category)
        if only_cyclical is not None:
            conditions.append("is_cyclical = ?")
            params.append(1 if only_cyclical else 0)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""
            SELECT * FROM products_catalog
            {where_clause}
            ORDER BY keepa_drop_percent DESC
            LIMIT ?
        """
        params.append(limit)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def search_product(self, query: str, limit: int = 5) -> List[Dict]:
        """Cerca nel catalogo per parola chiave o brand."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        term = f"%{query}%"
        cur.execute("""
            SELECT * FROM products_catalog
            WHERE title LIKE ? OR brand LIKE ? OR sub_category_name LIKE ?
            ORDER BY virality_score DESC
            LIMIT ?
        """, (term, term, term, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

if __name__ == "__main__":
    bot = TelegramMasterDealBot()
    print("--- SIMULAZIONE: TOP 2 OFFERTE CICLICHE RECORD ---")
    cyclical_deals = bot.get_top_deals(only_cyclical=True, limit=2)
    for d in cyclical_deals:
        print(bot.format_deal_post(d))
        print("-" * 50)

    print("\n--- SIMULAZIONE: RICERCA 'COSRX' NEL CATALOGO ---")
    results = bot.search_product("COSRX", limit=2)
    for r in results:
        print(f"Trovato: {r['title']} | Prezzo: €{r['current_price']} | Drop: -{r['keepa_drop_percent']}%")
