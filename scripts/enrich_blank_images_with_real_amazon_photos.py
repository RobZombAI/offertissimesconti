"""
Enrich Blank Images with Real Amazon Photos
OffertissimeSconti - Master Image Resolution Engine

Identifica tutti i prodotti con immagini vuote/corrotte (GIF 1x1 da 43 byte o legacy images-eu)
ed estrae via streaming multithread la VERA immagine originale Amazon CDN ad alta definizione (SL1500)
senza MAI toccare titoli, prezzi, ASIN o link affiliati.
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
CATALOG_JSON_DATA = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.json")
CATALOG_JSON_WEB = os.path.join(BASE_DIR, "web", "catalog.json")
CATEGORIES_JSON_WEB = os.path.join(BASE_DIR, "web", "categories.json")
CSV_EXPORT_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
CSV_EXPORT_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_posttap_export.csv")
TXT_LINKS_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_links_only.txt")
TXT_LINKS_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_links_only.txt")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

def check_image_is_blank(url: str) -> bool:
    """Verifica se un URL immagine è vuoto o restituisce la GIF trasparente 1x1 di 43 byte."""
    if not url or not url.strip():
        return True
    if url.endswith(".gif"):
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            cl = int(resp.headers.get("Content-Length", 0))
            if cl > 0 and cl <= 100:
                return True
            if cl > 100:
                return False
    except Exception:
        pass

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read(200)
            return len(data) <= 100
    except Exception:
        return True

def fetch_real_amazon_image(asin: str) -> Optional[str]:
    """Interroga Amazon.it/dp/{asin} ed estrae l'hash dell'immagine originale ad alta risoluzione."""
    url = f"https://www.amazon.it/dp/{asin}"
    ua = USER_AGENTS[hash(asin) % len(USER_AGENTS)]
    headers = {
        "User-Agent": ua,
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Sec-Ch-Ua": '"Chromium";v="123", "Not:A-Brand";v="8"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"'
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 1. Selettore principale: landingImage data-a-dynamic-image
        m = re.search(r'id=\"landingImage\"[^>]+data-a-dynamic-image=\"\{&quot;(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))', html, re.I)
        if m:
            img_hash = m.group(2)
            return f"https://m.media-amazon.com/images/I/{img_hash}._AC_SL1500_.jpg"

        # 2. Selettore generico: data-a-dynamic-image
        m = re.search(r'data-a-dynamic-image=\"\{&quot;(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))', html, re.I)
        if m:
            img_hash = m.group(2)
            return f"https://m.media-amazon.com/images/I/{img_hash}._AC_SL1500_.jpg"

        # 3. Selettore JSON colorImages: hiRes
        m = re.search(r'\"hiRes\":\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))\"', html, re.I)
        if m:
            img_hash = m.group(2)
            return f"https://m.media-amazon.com/images/I/{img_hash}._AC_SL1500_.jpg"

        # 4. Selettore JSON colorImages: large
        m = re.search(r'\"large\":\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))\"', html, re.I)
        if m:
            img_hash = m.group(2)
            return f"https://m.media-amazon.com/images/I/{img_hash}._AC_SL1500_.jpg"

        # 5. Fallback imgBlkFront per libri o categorie speciali
        m = re.search(r'id=\"imgBlkFront\"[^>]+src=\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))', html, re.I)
        if m:
            img_hash = m.group(2)
            return f"https://m.media-amazon.com/images/I/{img_hash}._AC_SL1500_.jpg"

        # 6. Fallback regex su immagini nel blocco principale
        all_imgs = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', html, re.I)
        if all_imgs:
            return f"https://m.media-amazon.com/images/I/{all_imgs[0]}._AC_SL1500_.jpg"

        return None
    except Exception as e:
        return None

def sync_all_exports(conn):
    """Rigenera tutti i file JSON, CSV e TXT sincronizzati con SQLite."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM products_catalog ORDER BY keepa_drop_percent DESC")
    all_products = [dict(r) for r in cur.fetchall()]

    print(f"🔄 Sincronizzazione esportazioni per {len(all_products)} prodotti...")

    # 1. JSON Master Catalog
    with open(CATALOG_JSON_DATA, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)

    # 2. Web Catalog JSON
    web_catalog_payload = {
        "success": True,
        "total": len(all_products),
        "products": all_products
    }
    with open(CATALOG_JSON_WEB, "w", encoding="utf-8") as f:
        json.dump(web_catalog_payload, f, indent=2, ensure_ascii=False)

    # 3. Categories JSON
    cur.execute("""
        SELECT 
            macro_category_id,
            macro_category_name,
            COUNT(*) as total_skus,
            ROUND(AVG(keepa_drop_percent), 1) as avg_drop
        FROM products_catalog
        GROUP BY macro_category_id, macro_category_name
        ORDER BY total_skus DESC
    """)
    cats = [dict(r) for r in cur.fetchall()]
    cat_payload = {
        "success": True,
        "categories": cats,
        "total": len(cats)
    }
    with open(CATEGORIES_JSON_WEB, "w", encoding="utf-8") as f:
        json.dump(cat_payload, f, indent=2, ensure_ascii=False)

    # 4. PostTap CSV
    import csv
    csv_fields = [
        "Title", "Affiliate_URL", "Price_EUR", "Original_Price_EUR",
        "Discount_Percent", "Category", "Brand", "ASIN", "Image_URL"
    ]
    for csv_path in [CSV_EXPORT_DATA, CSV_EXPORT_WEB]:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(csv_fields)
            for p in all_products:
                writer.writerow([
                    p["title"],
                    p["affiliate_url"],
                    f"{p['current_price']:.2f}",
                    f"{p['list_price']:.2f}",
                    p["keepa_drop_percent"],
                    p["macro_category_name"],
                    p["brand"],
                    p["asin"],
                    p["image_url"]
                ])

    # 5. TXT Links
    for txt_path in [TXT_LINKS_DATA, TXT_LINKS_WEB]:
        with open(txt_path, "w", encoding="utf-8") as f:
            for p in all_products:
                f.write(f"{p['affiliate_url']}\n")

    print("✅ Tutte le esportazioni sono sincronizzate al 100%!")

def run_enrichment(max_workers: int = 15):
    print("=" * 70)
    print("🚀 AVVIO ARRICCHIMENTO IMMAGINI AMAZON - MODALITÀ SISTEMICA")
    print("=" * 70)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT asin, title, image_url FROM products_catalog")
    all_rows = cur.fetchall()

    print(f"📦 Totale prodotti nel catalogo: {len(all_rows)}")

    # Fase 1: Identificazione dei prodotti con immagini vuote o images-eu
    print("\n🔍 Fase 1: Scansione rapida per identificare immagini vuote (GIF 43 byte o rotte)...")
    
    blank_targets = []
    with ThreadPoolExecutor(max_workers=30) as ex:
        futures = {ex.submit(check_image_is_blank, row[2]): row for row in all_rows}
        for fut in as_completed(futures):
            row = futures[fut]
            try:
                if fut.result():
                    blank_targets.append(row)
            except Exception:
                blank_targets.append(row)

    print(f"🎯 Prodotti rilevati con immagine vuota o logo: {len(blank_targets)} su {len(all_rows)}")

    # Fase 2: Estrazione delle vere immagini da Amazon.it
    print(f"\n⚡ Fase 2: Recupero immagini reali ad alta risoluzione via Amazon CDN con {max_workers} worker...")
    
    success_count = 0
    fail_count = 0
    start_time = time.time()

    def process_item(item):
        asin, title, old_url = item
        new_url = fetch_real_amazon_image(asin)
        return asin, title, new_url

    batch_to_commit = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(process_item, target): target for target in blank_targets}
        done_count = 0
        for fut in as_completed(futures):
            done_count += 1
            asin, title, new_url = fut.result()
            if new_url:
                success_count += 1
                batch_to_commit.append((new_url, asin))
            else:
                fail_count += 1

            if len(batch_to_commit) >= 25:
                cur.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", batch_to_commit)
                conn.commit()
                batch_to_commit.clear()

            if done_count % 50 == 0 or done_count == len(blank_targets):
                elapsed = time.time() - start_time
                rate = done_count / elapsed if elapsed > 0 else 0
                pct = (done_count / len(blank_targets)) * 100
                print(f"   [{done_count}/{len(blank_targets)} - {pct:.1f}%] Successi: {success_count} | Falliti: {fail_count} | Velocità: {rate:.1f} prod/s")

    if batch_to_commit:
        cur.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", batch_to_commit)
        conn.commit()
        batch_to_commit.clear()

    total_time = time.time() - start_time
    print(f"\n✨ Fase 2 completata in {total_time:.1f}s!")
    print(f"   ✅ Immagini reali aggiornate: {success_count}")
    print(f"   ⚠️ Immagini non trovate: {fail_count}")

    # Fase 3: Sincronizzazione export
    print("\n📦 Fase 3: Sincronizzazione e rigenerazione file export...")
    sync_all_exports(conn)
    conn.close()
    print("\n🎉 Operazione di arricchimento immagini completata con successo!")

if __name__ == "__main__":
    workers = 15
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    run_enrichment(max_workers=workers)
