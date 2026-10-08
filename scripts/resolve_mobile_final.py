"""
Resolve Mobile Final
OffertissimeSconti - Mobile User Agent Pass for Final Products
"""

import os
import json
import re
import urllib.request
import urllib.error
import sqlite3
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT asin, title, macro_category_id FROM products_catalog WHERE image_url LIKE '%images-eu%'")
rows = c.fetchall()

# Filter down to the ~36 that are blank
blank_asins = []
for asin, title, cat in rows:
    old_url = f"https://images-eu.ssl-images-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_SX500_.jpg"
    try:
        req = urllib.request.Request(old_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2) as r:
            if len(r.read()) <= 100:
                blank_asins.append((asin, title, cat))
    except Exception:
        blank_asins.append((asin, title, cat))

print(f"Total blank items to resolve: {len(blank_asins)}")

headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Accept-Language': 'it-IT,it;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def resolve_mobile(item):
    asin, title, cat = item
    url = f"https://www.amazon.it/dp/{asin}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=7) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            imgs = re.findall(r'<img[^>]+src=\"(https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]+)\.(?:jpg|png|jpeg))\"', html)
            for full_url, h in imgs:
                if len(h) >= 9 and not h.startswith(('01', 'play', 'badge', 'nav')):
                    return asin, f"https://m.media-amazon.com/images/I/{h}._AC_SL1500_.jpg", 'ok'
            
            # fallback regex
            all_h = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', html[:300000])
            filtered = [x for x in all_h if len(x) >= 9 and not x.startswith(('01', 'play', 'badge', 'nav'))]
            if filtered:
                return asin, f"https://m.media-amazon.com/images/I/{filtered[0]}._AC_SL1500_.jpg", 'regex'
            return asin, None, 'no_img'
    except urllib.error.HTTPError as e:
        return asin, None, f'http_{e.code}'
    except Exception as e:
        return asin, None, f'err_{e}'

with ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(resolve_mobile, blank_asins))

resolved = []
unresolved = []
for asin, img, status in results:
    if img:
        resolved.append((img, asin))
    else:
        unresolved.append((asin, status))

print(f"Mobile resolution: {len(resolved)} resolved, {len(unresolved)} unresolved")
if unresolved:
    print("Unresolved list:", unresolved)

if resolved:
    c.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", resolved)
    conn.commit()

from enrich_blank_images_with_real_amazon_photos import sync_all_exports
sync_all_exports(conn)
conn.close()
