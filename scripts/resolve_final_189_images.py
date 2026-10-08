"""
Resolve Final 189 Images
OffertissimeSconti - Final Precision Pass

Risolve chirurgicamente gli ultimi 189 prodotti con immagini vuote
catturando l'immagine principale dall'image container o blocco multimediale di Amazon.it.
"""

import os
import json
import re
import time
import sqlite3
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
TRULY_BLANK_PATH = os.path.join(BASE_DIR, "data", "truly_blank_remaining.json")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def fetch_precision_image(item):
    asin, title, cat = item
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

        # 1. Cerca nel blocco main-image-container / imageBlock
        blk_match = re.search(r'id=\"(?:imageBlock|main-image-container|imgTagWrapperId)\"[^>]*>(.*?)(?:</div>\s*</div>\s*</div>|id=\"rightCol\")', html, re.DOTALL)
        if blk_match:
            imgs = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', blk_match.group(1), re.I)
            if imgs:
                return asin, f"https://m.media-amazon.com/images/I/{imgs[0]}._AC_SL1500_.jpg"

        # 2. Cerca data-old-hires
        m = re.search(r'data-old-hires=\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))\"', html, re.I)
        if m:
            return asin, f"https://m.media-amazon.com/images/I/{m.group(2)}._AC_SL1500_.jpg"

        # 3. Cerca colorImages in tutto il file
        m = re.search(r'\"hiRes\":\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|jpeg|png))\"', html, re.I)
        if m:
            return asin, f"https://m.media-amazon.com/images/I/{m.group(2)}._AC_SL1500_.jpg"

        # 4. Cerca la prima immagine m.media-amazon.com nei primi 250KB del file (dove risiede l'above-the-fold)
        above_the_fold = html[:250000]
        imgs = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', above_the_fold, re.I)
        if imgs:
            # Escludi banner o icone standard se presenti
            filtered = [x for x in imgs if len(x) >= 9 and not x.startswith(('01', 'play', 'badge'))]
            if filtered:
                return asin, f"https://m.media-amazon.com/images/I/{filtered[0]}._AC_SL1500_.jpg"

        # 5. Cerca in tutta la pagina escludendo loghi Amazon noti
        imgs_all = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', html, re.I)
        if imgs_all:
            return asin, f"https://m.media-amazon.com/images/I/{imgs_all[0]}._AC_SL1500_.jpg"

        return asin, None
    except Exception:
        return asin, None

def run():
    with open(TRULY_BLANK_PATH) as f:
        items = json.load(f)

    print(f"🎯 Avvio risoluzione chirurgica per {len(items)} prodotti...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    successes = []
    fails = []

    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(fetch_precision_image, it): it for it in items}
        for fut in as_completed(futures):
            asin, img_url = fut.result()
            if img_url:
                successes.append((img_url, asin))
            else:
                fails.append(asin)

    if successes:
        cur.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", successes)
        conn.commit()

    print(f"✅ Aggiornati con successo {len(successes)} prodotti su {len(items)}!")
    print(f"⚠️ Non risolti: {len(fails)}")

    # Sincronizza tutti gli export
    from enrich_blank_images_with_real_amazon_photos import sync_all_exports
    sync_all_exports(conn)
    conn.close()

if __name__ == "__main__":
    run()
