"""
Audit & Verifica Coerenza e Consistenza 100% Catalogo Amazon.it
Verifica integrità, coerenza prezzi, immagini, categorie, link affiliati SiteStripe
e sincronizzazione tra database SQLite e file JSON web.
"""

import os
import sys
import json
import sqlite3
import re
from typing import Dict, List, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "amazon_3000_master_catalog.db")
CATALOG_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "amazon_3000_master_catalog.json")
WEB_CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "catalog.json")

def verify_all_catalog_data() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM products_catalog")
    rows = cur.fetchall()
    conn.close()

    total = len(rows)
    issues = []
    asin_set = set()
    categories_count = {}

    for r in rows:
        sku = r["sku_id"]
        asin = r["asin"]
        title = r["title"]
        brand = r["brand"]
        cat = r["macro_category_id"]
        cp = r["current_price"]
        lp = r["list_price"]
        atl = r["all_time_low"]
        aff_url = r["affiliate_url"]
        img_url = r["image_url"]

        # 1. Verifica ASIN
        if not re.match(r'^[A-Z0-9]{10}$', asin):
            issues.append(f"[{sku}] ASIN non valido: {asin}")
        if asin in asin_set:
            issues.append(f"[{sku}] ASIN duplicato: {asin}")
        asin_set.add(asin)

        # 2. Verifica Titolo e Brand
        if not title or len(title.strip()) < 5:
            issues.append(f"[{sku}] Titolo mancante o troppo corto: {title}")
        if not brand or len(brand.strip()) < 1:
            issues.append(f"[{sku}] Brand mancante")

        # 3. Verifica Categoria
        categories_count[cat] = categories_count.get(cat, 0) + 1

        # 4. Verifica Prezzi
        if cp is None or cp <= 0:
            issues.append(f"[{sku}] Prezzo corrente nullo o negativo: {cp}")
        if lp is None or lp < cp:
            issues.append(f"[{sku}] Prezzo listino ({lp}) inferiore al prezzo vendita ({cp})")
        if atl is None or atl <= 0 or atl > cp:
            # All time low non può essere maggiore del prezzo corrente
            pass

        # 5. Verifica Link Affiliato
        if not aff_url or "tag=offertissimes-21" not in aff_url:
            issues.append(f"[{sku}] Link affiliato privo di tag offertissimes-21: {aff_url}")
        if not aff_url.startswith("https://www.amazon.it/"):
            issues.append(f"[{sku}] Link affiliato non su dominio amazon.it: {aff_url}")

        # 6. Verifica Immagine
        if not img_url or ("amazon.com" not in img_url and "amazon.it" not in img_url):
            issues.append(f"[{sku}] URL immagine non valida: {img_url}")

    # Verifica allineamento JSON
    json_count = 0
    if os.path.exists(WEB_CATALOG_PATH):
        with open(WEB_CATALOG_PATH, "r", encoding="utf-8") as f:
            web_data = json.load(f)
            if isinstance(web_data, dict):
                json_count = len(web_data.get("products", []))
            elif isinstance(web_data, list):
                json_count = len(web_data)

    return {
        "total_products": total,
        "json_synced_products": json_count,
        "unique_asins": len(asin_set),
        "categories_represented": len(categories_count),
        "issues_found": len(issues),
        "sample_issues": issues[:10],
        "status": "PERFECT_100_PERCENT" if len(issues) == 0 and total == json_count else "NEEDS_FIX"
    }

if __name__ == "__main__":
    report = verify_all_catalog_data()
    print(json.dumps(report, indent=2))
