"""
Resolve Last 37 with Search
OffertissimeSconti - Final 37 Resolution
"""

import os
import json
import re
import urllib.request
import urllib.parse
import sqlite3
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")

LAST_37 = [
    ('B0C7491XRN', 'Xiaomi Portable Electric Air Compressor 2'),
    ('B085TRCCT6', 'Luna Premium Smart Watch'),
    ('B0DCB9C26S', 'Hisense DHQE800BW2 Asciugatrice A Pompa Di Calore'),
    ('B0F5PXZNB6', 'Sixstarhair Ciuffetti Ciglia Finte kit'),
    ('B0CGNJ9W37', 'LAUBESS Colla Ciglia Finte Waterproof Bond and Seal Lashes'),
    ('B08RJK8863', 'Nail Store Gel UV LED Costruttore Monofasico Cover Beige'),
    ('B0D22QN9LN', 'BBQ KING Multi Pack Pitmaster Rub per Barbecue'),
    ('B0FH9XRYK7', 'Almar Preparato Gelato Soft Frozen Yogurt'),
    ('B0G4DSWK89', 'Kinder GranSorpresa Maxi Harry Potter'),
    ('B01M66R7OY', 'Prosciutto Spagnolo Pata Negra ibérico Paleta'),
    ('B09Z6W2WSD', 'Creatina Creapure Monoidrata 240 compresse'),
    ('B082MPN41T', 'Matana 120 Calici in Plastica con Glitter'),
    ('B0DF1PZSQV', 'BREOILUTLE Filtri Compatibili con Brita Maxtra'),
    ('B00TJ6YK16', 'AQUASAN 3 Cartucce Filtro Ricambio Aquacompact'),
    ('B0GXXYNBL9', 'Power Bank 10000mAh Magnetico Wireless'),
    ('B0HJB44KZS', 'Apple Watch SE GPS 40 mm Smartwatch'),
    ('B0BZ85BZNP', 'CMP T-Shirt Girocollo con Logo'),
    ('B0CSMTW5VL', 'Fisoew Maglietta sportiva da donna fitness'),
    ('B0GV4SQWC8', 'Owntop Giubbotto di Galleggiamento Adulti'),
    ('B0DK16S2XX', 'Abahub Pagaia Kayak Regolabile Alluminio'),
    ('B0BKG3BB1K', 'iZEEKER Fototrappola 36MP HD Fotocamera Caccia'),
    ('B09P4NNZH8', 'Simpeak Cintura Tattica 125cm Regolabile Nylon'),
    ('B0CGZTZWBT', 'WOLFANG Fototrappola 4K 48MP HD Fotocamera Caccia'),
    ('B00S9U2GWI', 'ALFETRAP TRAPPOLA ADESIVA PER SCARAFAGGI'),
    ('B00965GVFS', 'Tetra Goldfish Gold Colour Mangime granulare'),
    ('B0CGV9LFV8', 'Centrovete SWAT-Clear unguento 200gr'),
    ('B0HB5TSM4Y', 'Mangime per Pulcini Appena Nati'),
    ('B0BSR3W8BP', 'UGF Larve di mosca soldato essiccate Hermetia'),
    ('B094RFX5NF', 'Petsly Repellente per Gatti e Cani Anti Urina'),
    ('B07MTQ7QSG', 'Il Contadino Favino Nero Zootecnico'),
    ('B08DQRXY73', 'Zamboo Parapioggia Passeggino Universale'),
    ('B0DN1GTTQW', 'Lamicall Specchietto Retrovisore Bambini'),
    ('B0FN2XBYNV', 'YANWANG Calzini Antiscivolo per Bambini Piccoli'),
    ('B08K75WMWR', 'Parapioggia Passeggino Universale Impermeabile'),
    ('B082XYFT5K', 'Fascia Neonato Cotone Organico Traspirante'),
    ('B089YJZMP3', 'GOLDGE Bustine Corredino del Neonato Ospedale'),
    ('B0GQL7P18N', 'Momcozy S9 Pro Tiralatte Elettrico Indossabile')
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Accept-Language': 'it-IT,it;q=0.9'
}

def resolve_item(item):
    asin, query = item
    # 1. Try search by ASIN
    for q_text in [asin, query]:
        q = urllib.parse.quote(q_text)
        url = f"https://www.amazon.it/s?k={q}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=7) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                imgs = re.findall(r'https://m\.media-amazon\.com/images/I/([A-Za-z0-9\+\-\_\%]{8,25})\.(?:jpg|jpeg|png)', html)
                valid_imgs = [x for x in imgs if len(x) >= 9 and not x.startswith(('01', 'play', 'badge'))]
                if valid_imgs:
                    return asin, f"https://m.media-amazon.com/images/I/{valid_imgs[0]}._AC_SL1500_.jpg"
        except Exception:
            pass
    return asin, None

def run():
    print(f"Resolving {len(LAST_37)} items with Amazon Search...")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    resolved = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(resolve_item, LAST_37))

    for asin, img_url in results:
        if img_url:
            resolved.append((img_url, asin))

    print(f"Resolved {len(resolved)} / {len(LAST_37)} items!")
    if resolved:
        cur.executemany("UPDATE products_catalog SET image_url = ? WHERE asin = ?", resolved)
        conn.commit()

    from enrich_blank_images_with_real_amazon_photos import sync_all_exports
    sync_all_exports(conn)
    conn.close()

if __name__ == "__main__":
    run()
