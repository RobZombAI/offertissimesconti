"""
Systemic Real Amazon Image & Title Syncer
Effettua lo scraping concorrente e accurato delle pagine prodotto ufficiali di Amazon.it (/dp/{asin})
estraendo l'immagine primaria originale ad alta risoluzione (hiRes / data-old-hires / landingImage),
il titolo ufficiale e il brand, aggiornando il database SQLite, catalog.json e tutti gli export.
"""

import sqlite3
import urllib.request
import re
import html
import json
import time
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
CATALOG_JSON = os.path.join(BASE_DIR, "web", "catalog.json")
CATALOG_DATA_JSON = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.json")
CSV_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_posttap_export.csv")
CSV_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
TXT_WEB = os.path.join(BASE_DIR, "web", "offertissimesconti_posttap_links.txt")
TXT_DATA = os.path.join(BASE_DIR, "data", "offertissimesconti_links_only.txt")

HEADERS_LIST = [
    {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept-Language': 'it-IT,it;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
        'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    },
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0',
        'Accept-Language': 'it-IT,it;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
]

def fetch_real_amazon_data(asin, worker_id=0):
    """
    Scarica la pagina prodotto ufficiale Amazon ed estrae:
    - true_image: URL ad alta risoluzione da m.media-amazon.com
    - true_title: Titolo originale da #productTitle
    - true_brand: Brand ufficiale
    - is_active: Se il prodotto è attivo o 404
    """
    headers = HEADERS_LIST[worker_id % len(HEADERS_LIST)]
    url = f"https://www.amazon.it/dp/{asin}?th=1"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 404:
                return {"asin": asin, "success": False, "is_404": True, "error": "404 Not Found"}
            
            page = resp.read().decode("utf-8", errors="ignore")
            
            # 1. Titolo Ufficiale Amazon
            t_m = re.search(r'<span id="productTitle"[^>]*>(.*?)</span>', page, re.DOTALL)
            title = None
            if t_m:
                title = " ".join(html.unescape(t_m.group(1)).split())
            
            # Se è la dog page ("Spiacenti, non siamo riusciti a trovare la pagina"):
            if "spiacenti" in (title or "").lower() and "trovare" in (title or "").lower():
                return {"asin": asin, "success": False, "is_404": True, "error": "Dog Page"}
            
            # 2. Immagine Reale ad Alta Risoluzione
            candidates = []
            
            # A. colorImages hiRes
            hires = re.findall(r'"hiRes":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', page)
            candidates.extend(hires)
            
            # B. data-old-hires
            old_hires = re.findall(r'data-old-hires="(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', page)
            candidates.extend(old_hires)
            
            # C. landingImage data-a-dynamic-image
            dyn_m = re.search(r'data-a-dynamic-image="([^"]+)"', page)
            if dyn_m:
                try:
                    d = json.loads(dyn_m.group(1).replace("&quot;", '"'))
                    # ordina per risoluzione decrescente se disponibile
                    for k in d.keys():
                        if k.endswith(".jpg") and "gif" not in k and "transparent" not in k:
                            candidates.append(k)
                except Exception:
                    pass
            
            # D. colorImages large
            large = re.findall(r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', page)
            candidates.extend(large)
            
            # E. landingImage src
            src_m = re.search(r'id="landingImage"[^>]*src="(https://m\.media-amazon\.com/images/I/[^"]+\.jpg)"', page)
            if src_m:
                candidates.append(src_m.group(1))

            valid_image = None
            for c in candidates:
                if c and "media-amazon.com/images/I/" in c and not c.endswith(".gif") and "transparent" not in c:
                    # Preferisci sempre risoluzione massima (_AC_SL1500_) se possibile
                    clean_c = re.sub(r'\._AC_S[X|Y|L][0-9]+_\.jpg$', '._AC_SL1500_.jpg', c)
                    valid_image = clean_c
                    break

            # 3. Brand
            brand = None
            b_m = re.search(r'id="bylineInfo"[^>]*>(.*?)</a>', page, re.DOTALL)
            if b_m:
                b_text = html.unescape(b_m.group(1)).strip()
                b_text = re.sub(r'^(Visita lo Store di|Marca:|Brand:|Visita lo Store:)\s*', '', b_text, flags=re.IGNORECASE)
                brand = b_text.strip()
            if not brand and title:
                first_word = title.split()[0]
                if len(first_word) >= 3:
                    brand = first_word

            # 4. Prezzo reale se visibile
            price = None
            price_m = re.search(r'<span class="a-price[^"]*".*?<span class="a-offscreen">([0-9.,]+)[\s\xa0]*€</span>', page, re.DOTALL)
            if price_m:
                try:
                    p_val = float(price_m.group(1).replace(".", "").replace(",", "."))
                    if 0.5 <= p_val <= 5000.0:
                        price = p_val
                except Exception:
                    pass

            return {
                "asin": asin,
                "success": bool(valid_image),
                "title": title,
                "image_url": valid_image,
                "brand": brand,
                "price": price,
                "is_404": False
            }

    except Exception as e:
        err_msg = str(e)
        is_404 = "404" in err_msg
        return {"asin": asin, "success": False, "is_404": is_404, "error": err_msg}


def sync_all_catalog_images(max_workers=10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Recupera tutti i prodotti ordinati con priorità a quelli con immagini duplicate
    print("🔍 Analisi catalogo prodotti per individuare immagini da aggiornare...")
    cur.execute("""
        SELECT p.sku_id, p.asin, p.title, p.brand, p.image_url, 
               (SELECT COUNT(*) FROM products_catalog c2 WHERE c2.image_url = p.image_url) as dup_count
        FROM products_catalog p
        ORDER BY dup_count DESC, p.sku_id ASC
    """)
    all_products = [dict(r) for r in cur.fetchall()]
    total_count = len(all_products)
    dup_products = [p for p in all_products if p["dup_count"] > 1]
    
    print(f"📦 Totale prodotti in catalogo: {total_count}")
    print(f"⚠️ Prodotti con immagini duplicate da sanare immediatamente: {len(dup_products)}")

    # Mappa ASIN -> record
    processed = 0
    updated_count = 0
    errors_count = 0
    not_found_count = 0

    batch_updates = []

    def save_batch(batch):
        if not batch:
            return
        c = conn.cursor()
        c.executemany("""
            UPDATE products_catalog
            SET image_url = CASE WHEN ? != '' THEN ? ELSE image_url END,
                title = CASE WHEN ? != '' THEN ? ELSE title END,
                brand = CASE WHEN ? != '' THEN ? ELSE brand END
            WHERE asin = ?
        """, [(b["image_url"], b["image_url"], b["title"], b["title"], b["brand"], b["brand"], b["asin"]) for b in batch])
        conn.commit()

    print(f"\n🚀 Avvio sincronizzazione concorrente con {max_workers} thread...")
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Sottometti tutti i prodotti (duplicati per primi)
        future_to_p = {
            executor.submit(fetch_real_amazon_data, p["asin"], idx): p
            for idx, p in enumerate(all_products)
        }

        for future in as_completed(future_to_p):
            processed += 1
            orig = future_to_p[future]
            asin = orig["asin"]
            try:
                res = future.result()
                if res.get("success") and res.get("image_url"):
                    new_img = res["image_url"]
                    new_title = res.get("title") or orig["title"]
                    new_brand = res.get("brand") or orig["brand"]
                    
                    batch_updates.append({
                        "asin": asin,
                        "image_url": new_img,
                        "title": new_title,
                        "brand": new_brand
                    })
                    updated_count += 1
                    
                    if processed % 25 == 0 or processed == total_count:
                        save_batch(batch_updates)
                        batch_updates = []
                        rate = processed / (time.time() - t0)
                        eta = (total_count - processed) / rate if rate > 0 else 0
                        print(f"[{processed}/{total_count}] ({round(processed/total_count*100, 1)}%) "
                              f"Aggiornati: {updated_count} | Errori: {errors_count} | 404: {not_found_count} "
                              f"| Vel: {rate:.1f} ASIN/s | ETA: {eta/60:.1f} min")
                elif res.get("is_404"):
                    not_found_count += 1
                else:
                    errors_count += 1
            except Exception as e:
                errors_count += 1

    # Salva rimanenti
    save_batch(batch_updates)
    conn.commit()

    print(f"\n✨ Scansione completata in {round((time.time() - t0)/60, 2)} minuti!")
    print(f"📊 Risultati: {updated_count} immagini e titoli aggiornati con successo da Amazon!")

    # 2. Verifica quante immagini duplicate sono rimaste
    cur.execute("SELECT COUNT(DISTINCT image_url), COUNT(*) FROM products_catalog")
    distinct_imgs, total = cur.fetchone()
    print(f"🔍 Nuova diversità immagini: {distinct_imgs} immagini uniche su {total} prodotti!")

    # 3. Esporta su JSON, CSV e TXT
    export_all_formats(conn)
    conn.close()


def export_all_formats(conn):
    print("\n💾 Esportazione dei dati aggiornati su catalog.json, CSV e file di supporto...")
    cur = conn.cursor()
    cur.execute("SELECT * FROM products_catalog ORDER BY keepa_drop_percent DESC")
    products = [dict(r) for r in cur.fetchall()]

    # 1. web/catalog.json
    with open(CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump({"success": True, "total": len(products), "products": products}, f, indent=2, ensure_ascii=False)
    print(f"✅ Aggiornato {CATALOG_JSON} ({len(products)} prodotti)")

    # 2. data/amazon_3000_master_catalog.json
    with open(CATALOG_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"✅ Aggiornato {CATALOG_DATA_JSON}")

    # 3. CSV per PostTap
    csv_header = "Title,Affiliate_URL,ASIN,Brand,Category_ID,Category_Name,Price_EUR,List_Price_EUR,Price_ATL_EUR,Image_URL,SKU_ID\n"
    csv_lines = [csv_header]
    for p in products:
        clean_t = p['title'].replace('"', '""')
        clean_b = (p['brand'] or 'Amazon').replace('"', '""')
        line = f'"{clean_t}","{p["affiliate_url"]}","{p["asin"]}","{clean_b}","{p["macro_category_id"]}","{p["macro_category_name"]}",{p["current_price"]:.2f},{p["list_price"]:.2f},{p["all_time_low"]:.2f},"{p["image_url"]}","{p["sku_id"]}"\n'
        csv_lines.append(line)

    for path in [CSV_WEB, CSV_DATA]:
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(csv_lines)
    print(f"✅ Aggiornati {CSV_WEB} e {CSV_DATA}")

    # 4. TXT links
    for path in [TXT_WEB, TXT_DATA]:
        with open(path, "w", encoding="utf-8") as f:
            for p in products:
                f.write(f"{p['affiliate_url']}\n")
    print(f"✅ Aggiornati {TXT_WEB} e {TXT_DATA}")


if __name__ == "__main__":
    workers = 12 if len(sys.argv) < 2 else int(sys.argv[1])
    sync_all_catalog_images(max_workers=workers)
