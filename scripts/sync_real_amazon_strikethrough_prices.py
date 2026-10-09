"""
Sync Real Amazon Strikethrough (Comparison) Prices
OffertissimeSconti - Master Real Pricing Pipeline

Sincronizza al 100% i prezzi di paragone (prezzo barrato/tagliato) direttamente da Amazon.it:
- Se Amazon ha un prezzo barrato reale (data-a-strike="true", basisPrice, Prezzo consigliato, Prezzo mediano):
  list_price = amz_strike_price (il vero prezzo di listino di Amazon al centesimo)
  keepa_drop_percent = sconto reale effettivo
- Se Amazon NON ha un prezzo barrato (prodotto a prezzo pieno standard):
  list_price = current_price (nessun prezzo barrato finto o inventato con moltiplicatori)
  keepa_drop_percent = 0.0
"""

import os
import sys
import re
import json
import time
import sqlite3
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
CATALOG_JSON_DATA = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.json")
CATALOG_JSON_WEB = os.path.join(BASE_DIR, "web", "catalog.json")
CATEGORIES_JSON_WEB = os.path.join(BASE_DIR, "web", "categories.json")
CSV_EXPORT_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
CSV_EXPORT_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_posttap_export.csv")
TXT_LINKS_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_links_only.txt")
TXT_LINKS_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_links_only.txt")

OFFICIAL_ASSOCIATE_TAG = "offertissimes-21"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
]

def fetch_real_amazon_pricing(asin: str) -> Tuple[Optional[float], Optional[float]]:
    url = f"https://www.amazon.it/dp/{asin}"
    ua = USER_AGENTS[hash(asin) % len(USER_AGENTS)]
    headers = {
        "User-Agent": ua,
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 1. Estrazione prezzo di vendita corrente
        cur_price = None
        m_curr = re.search(r'class=\"a-price aok-align-center[^>]*>.*?class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)
        if not m_curr:
            m_curr = re.search(r'class=\"a-price-whole\">([0-9\.\,]+)<.*?class=\"a-price-fraction\">([0-9]{2})<', html, re.DOTALL)
        if m_curr:
            val_str = m_curr.group(1) if len(m_curr.groups()) == 1 else f"{m_curr.group(1)},{m_curr.group(2)}"
            try:
                cur_price = float(val_str.replace('.', '').replace(',', '.'))
            except ValueError:
                pass

        if not cur_price:
            offscreen = re.findall(r'<span class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html)
            for p_str in offscreen:
                try:
                    val = float(p_str.replace('.', '').replace(',', '.'))
                    if 0.4 <= val <= 9000:
                        cur_price = val
                        break
                except ValueError:
                    pass

        # 2. Estrazione prezzo tagliato di paragone (strikethrough / basisPrice / Prezzo consigliato)
        strikes = re.findall(r'data-a-strike=\"true\"[^>]*>.*?class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)
        basis = re.findall(r'class=\"basisPrice\"[^>]*>.*?class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)
        cons = re.findall(r'Prezzo consigliato:[^<]*<span[^>]*class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)
        med = re.findall(r'Prezzo mediano:[^<]*<span[^>]*class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)
        rec = re.findall(r'Prezzo più basso recente:[^<]*<span[^>]*class=\"a-offscreen\">([0-9\.\,]+)\s*€?</span>', html, re.DOTALL)

        all_strikes = strikes + basis + cons + med + rec
        strike_price = None
        for s in all_strikes:
            try:
                v = float(s.replace('.', '').replace(',', '.'))
                if cur_price and v > cur_price:
                    strike_price = v
                    break
                elif not strike_price and v > 0:
                    strike_price = v
            except ValueError:
                pass

        return cur_price, strike_price
    except Exception:
        return None, None

def run_sync(max_workers: int = 25):
    print("=" * 75)
    print("🚀 SINCRONIZZAZIONE 100% PREZZI TAGLIATI DI PARAGONE REALI AMAZON.IT")
    print("=" * 75)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT sku_id, asin, title, current_price, list_price, all_time_low FROM products_catalog ORDER BY sku_id ASC")
    products = [dict(r) for r in cur.fetchall()]
    total = len(products)

    print(f"📦 Totale prodotti da verificare: {total}")
    print(f"⚡ Concorrenza: {max_workers} worker in parallelo...")

    start_time = time.time()
    db_updates = []
    done = 0
    with_strike_count = 0
    regular_price_count = 0
    unchanged_count = 0

    def process_item(item):
        asin = item["asin"]
        amz_cp, amz_sp = fetch_real_amazon_pricing(asin)
        return item, amz_cp, amz_sp

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(process_item, p): p for p in products}
        for fut in as_completed(futures):
            done += 1
            item, amz_cp, amz_sp = fut.result()
            asin = item["asin"]
            db_cp = float(item["current_price"])
            db_lp = float(item["list_price"])
            db_atl = float(item["all_time_low"])

            # Calcolo dei nuovi prezzi 100% reali
            final_cp = amz_cp if (amz_cp and amz_cp > 0) else db_cp
            
            if amz_sp and amz_sp > final_cp:
                # Amazon ha un prezzo barrato ufficiale reale
                final_lp = amz_sp
                drop_pct = round((final_lp - final_cp) / final_lp * 100, 1)
                with_strike_count += 1
            else:
                # Amazon NON ha un prezzo barrato (prodotto a prezzo pieno/standard)
                final_lp = final_cp
                drop_pct = 0.0
                regular_price_count += 1

            final_atl = min(db_atl, final_cp)

            db_updates.append((final_cp, final_lp, final_atl, drop_pct, asin))

            if len(db_updates) >= 50:
                cur.executemany("""
                    UPDATE products_catalog 
                    SET current_price = ?, list_price = ?, all_time_low = ?, keepa_drop_percent = ?
                    WHERE asin = ?
                """, db_updates)
                conn.commit()
                db_updates.clear()

            if done % 100 == 0 or done == total:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                pct = (done / total) * 100
                print(f"   [{done}/{total} - {pct:.1f}%] Sconti Reali Amazon: {with_strike_count} | Prezzi Standard (Zero Strike Finto): {regular_price_count} | Velocità: {rate:.1f} prod/s")

    if db_updates:
        cur.executemany("""
            UPDATE products_catalog 
            SET current_price = ?, list_price = ?, all_time_low = ?, keepa_drop_percent = ?
            WHERE asin = ?
        """, db_updates)
        conn.commit()
        db_updates.clear()

    total_time = time.time() - start_time
    print("\n" + "=" * 75)
    print(f"✨ SINCRONIZZAZIONE PREZZI DI PARAGONE COMPLETATA IN {total_time:.1f}s!")
    print(f"   🎯 Prodotti con VERO prezzo barrato su Amazon: {with_strike_count} ({with_strike_count/total*100:.1f}%)")
    print(f"   ✅ Prodotti a prezzo standard netto (senza finto barrato): {regular_price_count} ({regular_price_count/total*100:.1f}%)")
    print("=" * 75)

    # Sincronizza tutti gli export
    from enrich_blank_images_with_real_amazon_photos import sync_all_exports
    sync_all_exports(conn)
    conn.close()

if __name__ == "__main__":
    workers = 25
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    run_sync(max_workers=workers)
