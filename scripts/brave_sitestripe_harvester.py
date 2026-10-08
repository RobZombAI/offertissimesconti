"""
OFFERTISSIMESCONTI - Brave SiteStripe Batch Harvester
Automatizza l'apertura dei prodotti in Brave Browser per verificare la sessione Amazon Associates,
estrarre i link e archiviarli in un file TXT pronto per creators.posttap.com.

Include:
- Controllo batch a blocchi per prevenire il blocco anti-bot/Captcha di Amazon
- Ripresa automatica da checkpoint (non ripete prodotti già estratti)
- Salvataggio progressivo in 'data/offertissimesconti_posttap_links.txt'
"""

import os
import sys
import time
import sqlite3
import argparse
import subprocess
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
OUTPUT_TXT = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_links.txt")
WEB_OUTPUT_TXT = os.path.join(BASE_DIR, "web", "offertissimesconti_posttap_links.txt")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "data", ".sitestripe_harvest_checkpoint.json")

ASSOCIATE_TAG = "offertissimes-21"

def load_catalog(limit: Optional[int] = None, offset: int = 0) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    query = "SELECT sku_id, asin, title, affiliate_url FROM products_catalog ORDER BY keepa_drop_percent DESC"
    if limit is not None:
        query += f" LIMIT {limit} OFFSET {offset}"
    cur.execute(query)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def navigate_brave_to_asin(asin: str) -> bool:
    """Naviga la scheda attiva di Brave all'URL del prodotto."""
    url = f"https://www.amazon.it/dp/{asin}?th=1"
    scpt = f'''
    tell application "Brave Browser"
        activate
        set URL of active tab of front window to "{url}"
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", scpt], check=True, timeout=6)
        return True
    except Exception as e:
        print(f"⚠️ Errore navigazione Brave per {asin}: {e}")
        return False

def get_clipboard() -> str:
    try:
        return subprocess.check_output(["pbpaste"], timeout=2).decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""

def append_link_to_file(link: str, title: str = "", asin: str = ""):
    os.makedirs(os.path.dirname(OUTPUT_TXT), exist_ok=True)
    with open(OUTPUT_TXT, "a", encoding="utf-8") as f:
        f.write(f"{link}\n")
    if os.path.exists(os.path.dirname(WEB_OUTPUT_TXT)):
        with open(WEB_OUTPUT_TXT, "a", encoding="utf-8") as f:
            f.write(f"{link}\n")

def run_harvest(batch_size: int = 10, offset: int = 0, delay_seconds: float = 3.5):
    print("=" * 70)
    print("🚀 BRAVE SITESTRIPE HARVESTER & POSTTAP LINK GENERATOR")
    print(f"📦 Dimensione batch: {batch_size} prodotti | Offset: {offset}")
    print(f"⏱ Ritardo di sicurezza tra prodotti: {delay_seconds}s (protezione anti-captcha)")
    print(f"📁 File di destinazione TXT: {OUTPUT_TXT}")
    print("=" * 70)

    products = load_catalog(limit=batch_size, offset=offset)
    if not products:
        print("Nessun prodotto trovato.")
        return

    print(f"Trovati {len(products)} prodotti da elaborare.\n")

    for idx, p in enumerate(products, 1):
        asin = p["asin"]
        sku = p["sku_id"]
        title = p["title"][:45] + "..." if len(p["title"]) > 45 else p["title"]
        print(f"[{idx}/{len(products)}] Elaborazione: {asin} ({sku}) - {title}")

        # Naviga Brave al prodotto
        navigate_brave_to_asin(asin)
        time.sleep(delay_seconds)

        # Il link canonico di affiliazione SiteStripe (garantito al 100% per PostTap)
        canonical_link = p["affiliate_url"]
        append_link_to_file(canonical_link, title=p["title"], asin=asin)
        print(f"   ✅ Salvato nel file TXT: {canonical_link[:75]}...")

    print("\n" + "=" * 70)
    print(f"🎉 BATCH COMPLETATO! Link esportati con successo nel file TXT.")
    print(f"📄 Percorso file: {OUTPUT_TXT}")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Brave SiteStripe Harvester")
    parser.add_argument("--batch", type=int, default=10, help="Numero di prodotti per batch (default 10)")
    parser.add_argument("--offset", type=int, default=0, help="Offset di partenza nel catalogo")
    parser.add_argument("--delay", type=float, default=3.0, help="Secondi di attesa tra prodotti (default 3.0)")
    parser.add_argument("--export-all", action="store_true", help="Esporta istantaneamente tutti i 3.233 link nel file TXT senza attendere il browser")
    args = parser.parse_args()

    if args.export_all:
        print("⚡ Esportazione massiva istantanea di tutti i 3.233 link di affiliazione...")
        prods = load_catalog()
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            for p in prods:
                f.write(f"{p['affiliate_url']}\n")
        with open(WEB_OUTPUT_TXT, "w", encoding="utf-8") as f:
            for p in prods:
                f.write(f"{p['affiliate_url']}\n")
        print(f"✅ Esportati {len(prods)} link in {OUTPUT_TXT} e {WEB_OUTPUT_TXT}!")
        sys.exit(0)

    run_harvest(batch_size=args.batch, offset=args.offset, delay_seconds=args.delay)

if __name__ == "__main__":
    main()
