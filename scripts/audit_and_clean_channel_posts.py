"""
OffertissimeSconti - Telegram Channel Post Auditor & Cleaner
Analizza tutti i post pubblicati sul canale Telegram ufficiale (@OffertissimeSconti):
1. Verifica la validità e l'esistenza dell'ASIN su Amazon.it (evita 404 e dog page)
2. Verifica la coerenza del titolo e del prodotto
3. Verifica la presenza di prezzi anomali (< €0.50) o titoli mancanti
4. Elimina tramite API Telegram (deleteMessage) tutti i post incoerenti
5. Aggiorna channel_broadcast_log nel database SQLite
"""

import sqlite3
import urllib.request
import re
import html
import time
import requests
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
ENV_FILE = os.path.join(BASE_DIR, ".env")

def load_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

HEADERS_LIST = [
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36'},
    {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0'},
]

def check_single_post(p, worker_id=0):
    asin = p['asin']
    title = p['title'] or ''
    price = p['price_posted']
    msg_id = p['telegram_message_id']
    
    # 1. Mancanza di titolo o prezzo anomalo
    if not title or title.strip() == '' or price < 0.50:
        return {
            'post': p,
            'is_valid': False,
            'reason': f"Dati mancanti o anomali (titolo: '{title[:20]}', prezzo: €{price})"
        }
    
    # 2. Verifica su Amazon.it
    headers = HEADERS_LIST[worker_id % len(HEADERS_LIST)]
    url = f"https://www.amazon.it/dp/{asin}?th=1"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 404:
                return {'post': p, 'is_valid': False, 'reason': 'Amazon 404: Prodotto non trovato'}
            
            body = resp.read().decode('utf-8', errors='ignore')
            
            # Controllo titolo reale
            t_m = re.search(r'<span id="productTitle"[^>]*>(.*?)</span>', body, re.DOTALL)
            real_title = " ".join(html.unescape(t_m.group(1)).split()) if t_m else ""
            
            if not real_title or "spiacenti" in real_title.lower() and "trovare" in real_title.lower():
                return {'post': p, 'is_valid': False, 'reason': 'Dog page Amazon: Pagina non disponibile'}
            
            # Controllo somiglianza parole chiave tra titolo del post e titolo Amazon
            # estrai parole significative (>= 4 caratteri)
            words_post = set(w.lower() for w in re.findall(r'[a-zA-Z0-9]{4,}', title))
            words_real = set(w.lower() for w in re.findall(r'[a-zA-Z0-9]{4,}', real_title))
            common = words_post.intersection(words_real)
            
            if len(words_post) > 0 and len(common) == 0:
                return {
                    'post': p,
                    'is_valid': False,
                    'reason': f"Titolo incoerente (Post: '{title[:35]}' vs Amazon: '{real_title[:35]}')"
                }
            
            return {
                'post': p,
                'is_valid': True,
                'real_title': real_title,
                'reason': 'OK'
            }
    except Exception as e:
        err = str(e)
        if '404' in err:
            return {'post': p, 'is_valid': False, 'reason': 'Amazon 404 Not Found'}
        # Se c'è timeout temporaneo o errore di rete, ritenta una volta
        return {'post': p, 'is_valid': False, 'reason': f'Errore richiesta: {err}'}


def audit_and_clean_channel():
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    channel_id = env.get("TELEGRAM_CHANNEL_ID", "-1003838698998")
    
    if not token or not channel_id:
        print("❌ Errore: TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID mancante!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT b.id, b.telegram_message_id, b.sku_id, b.asin, b.price_posted, b.posted_at,
               p.title, p.brand, p.affiliate_url, p.image_url
        FROM channel_broadcast_log b
        LEFT JOIN products_catalog p ON b.sku_id = p.sku_id
        WHERE b.channel_id = ?
        ORDER BY b.telegram_message_id ASC
    """, (channel_id,))
    posts = [dict(r) for r in cur.fetchall()]
    total = len(posts)
    print(f"🔍 Avvio auditing concorrente su {total} post del canale Telegram...")

    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_post = {
            executor.submit(check_single_post, p, idx): p
            for idx, p in enumerate(posts)
        }
        for future in as_completed(future_to_post):
            res = future.result()
            results.append(res)
            done = len(results)
            status_icon = "✅" if res["is_valid"] else "❌"
            p = res["post"]
            print(f"[{done}/{total}] {status_icon} Msg #{p['telegram_message_id']:<3} (ASIN: {p['asin']}) -> {res['reason']}")

    valid = [r for r in results if r["is_valid"]]
    incoherent = [r for r in results if not r["is_valid"]]

    print(f"\n==========================================")
    print(f"📊 RIEPILOGO AUDITING ({round(time.time() - t0, 1)}s):")
    print(f"   Totale post analizzati: {total}")
    print(f"   ✅ Post coerenti e validi: {len(valid)}")
    print(f"   ❌ Post incoerenti da rimuovere: {len(incoherent)}")
    print(f"==========================================\n")

    if not incoherent:
        print("🎉 Nessun post incoerente trovato sul canale! Tutto pulito.")
        conn.close()
        return

    # Rimozione dei post incoerenti dal canale Telegram
    print(f"🗑️ Avvio eliminazione di {len(incoherent)} post incoerenti dal canale Telegram...")
    deleted_count = 0
    delete_failed = 0
    ids_to_purge = []

    for item in incoherent:
        p = item["post"]
        msg_id = p["telegram_message_id"]
        reason = item["reason"]
        
        del_url = f"https://api.telegram.org/bot{token}/deleteMessage"
        del_resp = requests.post(del_url, json={"chat_id": channel_id, "message_id": msg_id}, timeout=10)
        del_data = del_resp.json()
        
        if del_data.get("ok"):
            deleted_count += 1
            print(f"   🗑️ Eliminato Msg #{msg_id} (ASIN: {p['asin']}) - Motivo: {reason}")
            ids_to_purge.append(p["id"])
        else:
            desc = del_data.get("description", "Sconosciuto")
            if "message to delete not found" in desc.lower():
                print(f"   ℹ️ Msg #{msg_id} già non presente su Telegram - Motivo: {reason}")
                ids_to_purge.append(p["id"])
                deleted_count += 1
            else:
                delete_failed += 1
                print(f"   ⚠️ Impossibile eliminare Msg #{msg_id}: {desc}")
        time.sleep(0.1)

    # Rimuovi i log dei post cancellati dal database
    if ids_to_purge:
        cur.execute(f"DELETE FROM channel_broadcast_log WHERE id IN ({','.join(['?']*len(ids_to_purge))})", ids_to_purge)
        conn.commit()
        print(f"💾 Aggiornato channel_broadcast_log: rimossi {len(ids_to_purge)} record obsoleti.")

    conn.close()
    print(f"\n✨ Operazione completata: {deleted_count} post incoerenti rimossi con successo dal canale!")

if __name__ == "__main__":
    audit_and_clean_channel()
