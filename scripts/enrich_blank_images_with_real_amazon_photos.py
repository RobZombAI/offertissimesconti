"""
Enrich Amazon Master Catalog with Real High-Resolution Product Images
OffertissimeSconti - Image Pipeline

Interroga direttamente le pagine dei prodotti specifici su Amazon.it (https://www.amazon.it/dp/{asin})
ed estrae l'immagine reale ufficiale ad alta risoluzione (_AC_SL1500_.jpg) da:
1. data-old-hires
2. data-a-dynamic-image (massima risoluzione)
3. colorImages (hiRes / large)
4. landingImage / main-image / imgBlkFront
Sincronizza SQLite, JSON web, CSV e TXT.
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

OFFICIAL_ASSOCIATE_TAG = "offertissimes-21"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]

def fetch_real_amazon_image(asin: str) -> Optional[str]:
    """Interroga Amazon.it/dp/{asin} ed estrae l'immagine originale ad alta risoluzione (SL1500) della pagina specifica."""
    url = f"https://www.amazon.it/dp/{asin}"
    ua = USER_AGENTS[hash(asin) % len(USER_AGENTS)]
    headers = {
        "User-Agent": ua,
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 1. data-old-hires (Full original master photo)
        m_hires = re.search(r'data-old-hires=\"(https://[^\"]+?)\"', html)
        if m_hires:
            m_key = re.search(r'/images/I/([A-Za-z0-9\-_%+]{8,24})\.', m_hires.group(1))
            if m_key:
                return f"https://m.media-amazon.com/images/I/{m_key.group(1)}._AC_SL1500_.jpg"

        # 2. data-a-dynamic-image (JSON with resolution map)
        m_dyn = re.search(r'data-a-dynamic-image=\"(\{.+?\})\"', html)
        if m_dyn:
            dyn_str = m_dyn.group(1).replace('&quot;', '"')
            try:
                dyn_dict = json.loads(dyn_str)
                sorted_imgs = sorted(dyn_dict.items(), key=lambda x: x[1][0]*x[1][1] if isinstance(x[1], list) and len(x[1])>=2 else 0, reverse=True)
                if sorted_imgs:
                    m_key = re.search(r'/images/I/([A-Za-z0-9\-_%+]{8,24})\.', sorted_imgs[0][0])
                    if m_key:
                        return f"https://m.media-amazon.com/images/I/{m_key.group(1)}._AC_SL1500_.jpg"
            except Exception:
                pass

        # 3. colorImages JSON (hiRes o large)
        ci_m = re.search(r'\'colorImages\':\s*\{\s*\'initial\':\s*(\[\{.*?\}\])', html)
        if ci_m:
            try:
                ci_list = json.loads(ci_m.group(1))
                if ci_list:
                    raw_url = ci_list[0].get('hiRes') or ci_list[0].get('large')
                    if raw_url:
                        m_key = re.search(r'/images/I/([A-Za-z0-9\-_%+]{8,24})\.', raw_url)
                        if m_key:
                            return f"https://m.media-amazon.com/images/I/{m_key.group(1)}._AC_SL1500_.jpg"
            except Exception:
                pass

        # 4. landingImage src, main-image src, imgBlkFront src
        m_src = re.search(r'<img[^>]+(?:id=\"landingImage\"|id=\"main-image\"|id=\"imgBlkFront\")[^>]+src=\"(https://[^\"]+?)\"', html)
        if not m_src:
            m_src = re.search(r'<img[^>]+src=\"(https://[^\"]+?)\"[^>]+(?:id=\"landingImage\"|id=\"main-image\"|id=\"imgBlkFront\")', html)
        if m_src:
            m_key = re.search(r'/images/I/([A-Za-z0-9\-_%+]{8,24})\.', m_src.group(1))
            if m_key:
                return f"https://m.media-amazon.com/images/I/{m_key.group(1)}._AC_SL1500_.jpg"

        # 5. Contenitore principale imageBlock / main-image-container
        m_block = re.search(r'id=\"(?:imageBlock|main-image-container)\"[^>]*>(.*?)<div id=\"(?:productDescription|feature-bullets|centerCol|rightCol)', html, re.DOTALL)
        if m_block:
            imgs = re.findall(r'https://[^\"]+media-amazon\.com/images/I/([A-Za-z0-9\-_%+]{8,24})\.', m_block.group(1))
            if imgs:
                return f"https://m.media-amazon.com/images/I/{imgs[0]}._AC_SL1500_.jpg"

        # 6. Prima immagine prodotto valida in images/I/
        all_imgs = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\-_%+]{8,24})\.', html)
        if all_imgs:
            return f"https://m.media-amazon.com/images/I/{all_imgs[0]}._AC_SL1500_.jpg"

        return None
    except Exception:
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

def run_enrichment(max_workers: int = 30):
    print("=" * 75)
    print("🚀 RECUPERO IMMAGINI REALI DIRETTAMENTE DALLE PAGINE PRODOTTO AMAZON.IT")
    print("=" * 75)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT asin, title, image_url FROM products_catalog WHERE image_url LIKE '%images-eu%' OR image_url NOT LIKE '%_AC_SL1500_%'")
    targets = cur.fetchall()

    print(f"📦 Totale prodotti con immagini fallback o non ad alta risoluzione: {len(targets)}")
    print(f"⚡ Concorrenza: {max_workers} worker in parallelo...")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    def process_item(item):
        asin, title, old_url = item
        new_url = fetch_real_amazon_image(asin)
        if not new_url:
            time.sleep(0.4)
            new_url = fetch_real_amazon_image(asin)
        return asin, title, new_url

    batch_to_commit = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(process_item, target): target for target in targets}
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

            if done_count % 50 == 0 or done_count == len(targets):
                elapsed = time.time() - start_time
                rate = done_count / elapsed if elapsed > 0 else 0
                pct = (done_count / len(targets)) * 100
                print(f"   [{done_count}/{len(targets)} - {pct:.1f}%] Successi: {success_count} | Falliti: {fail_count} | Velocità: {rate:.1f} prod/s")

    if batch_to_commit:
        cur.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", batch_to_commit)
        conn.commit()
        batch_to_commit.clear()

    total_time = time.time() - start_time
    print(f"\n✨ Recupero immagini completato in {total_time:.1f}s!")
    print(f"   ✅ Immagini reali aggiornate da pagina Amazon: {success_count}")
    print(f"   ⚠️ Immagini non trovate: {fail_count}")

    # Sincronizzazione export
    print("\n📦 Sincronizzazione e rigenerazione file export...")
    sync_all_exports(conn)
    conn.close()
    print("\n🎉 Operazione di arricchimento immagini completata con successo!")

if __name__ == "__main__":
    workers = 30
    if len(sys.argv) > 1:
        try:
            workers = int(sys.argv[1])
        except ValueError:
            pass
    run_enrichment(max_workers=workers)
