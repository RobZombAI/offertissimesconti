"""
OFFERTISSIMESCONTI - Telegram Bot Ufficiale (Produzione)
Motore di polling nativo per Telegram Bot API (richiede solo 'requests').
Gestisce comandi (/start, /deals, /minimi, /ciclici, /cerca, /track),
pulsanti interattivi inline, e invio notifiche automatiche di minimi storici.
"""

import os
import sys
import time
import sqlite3
import requests
import json
import re
from typing import Dict, List, Optional

# Assicura flush immediato dei log
sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
TRACKER_DB = os.path.join(BASE_DIR, "data", "tracker_test.db")
ENV_FILE = os.path.join(BASE_DIR, ".env")

def get_bot_token() -> str:
    # 1. Da variabile d'ambiente
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()

    # 2. Da file .env
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()

    return ""

class OffertissimeScontiTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0

    def test_connection(self) -> Dict:
        """Verifica la validità del token interrogando getMe."""
        url = f"{self.api_url}/getMe"
        res = requests.get(url, timeout=10)
        return res.json()

    def send_message(self, chat_id: int, text: str, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML") -> Dict:
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        try:
            res = requests.post(url, json=payload, timeout=10)
            res_data = res.json()
            if not res_data.get("ok"):
                print(f"❌ Errore Telegram API verso chat {chat_id}: {res_data.get('description')}")
            else:
                print(f"✅ Messaggio inviato con successo a chat {chat_id}")
            return res_data
        except Exception as e:
            print(f"❌ Errore invio messaggio a {chat_id}: {e}")
            return {"ok": False, "error": str(e)}

    def send_photo(self, chat_id: int, photo_url: str, caption: Optional[str] = None, reply_markup: Optional[Dict] = None, parse_mode: str = "HTML") -> Dict:
        """Invia una foto reale del prodotto con didascalia e pulsanti inline."""
        if not photo_url:
            return self.send_message(chat_id, caption or "", reply_markup=reply_markup, parse_mode=parse_mode)

        url = f"{self.api_url}/sendPhoto"
        # Limite caption Telegram è 1024 caratteri
        truncated_caption = caption[:1020] + "..." if caption and len(caption) > 1024 else caption
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "parse_mode": parse_mode
        }
        if truncated_caption:
            payload["caption"] = truncated_caption
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            res = requests.post(url, json=payload, timeout=12)
            res_data = res.json()
            if not res_data.get("ok"):
                print(f"⚠️ Invio foto fallito verso chat {chat_id} ({res_data.get('description')}). Fallback su messaggio testuale.")
                return self.send_message(chat_id, caption or "", reply_markup=reply_markup, parse_mode=parse_mode)
            print(f"✅ Foto inviata con successo a chat {chat_id}")
            return res_data
        except Exception as e:
            print(f"⚠️ Errore invio foto verso chat {chat_id} ({e}). Fallback su messaggio testuale.")
            return self.send_message(chat_id, caption or "", reply_markup=reply_markup, parse_mode=parse_mode)

    def send_document(self, chat_id: int, file_path: str, caption: Optional[str] = None) -> Dict:
        url = f"{self.api_url}/sendDocument"
        if not os.path.exists(file_path):
            return {"ok": False, "error": f"File non trovato: {file_path}"}
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": chat_id}
                if caption:
                    data["caption"] = caption
                    data["parse_mode"] = "HTML"
                res = requests.post(url, data=data, files=files, timeout=30)
                res_data = res.json()
                if res_data.get("ok"):
                    print(f"✅ Documento inviato con successo a {chat_id}")
                else:
                    print(f"❌ Errore invio documento a {chat_id}: {res_data.get('description')}")
                return res_data
        except Exception as e:
            print(f"❌ Errore invio documento a {chat_id}: {e}")
            return {"ok": False, "error": str(e)}

    def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None):
        url = f"{self.api_url}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            pass

    def get_updates(self) -> List[Dict]:
        url = f"{self.api_url}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 20
        }
        try:
            res = requests.get(url, params=params, timeout=25)
            data = res.json()
            if data.get("ok"):
                return data.get("result", [])
        except Exception as e:
            print(f"Polling timeout o connessione persa: {e}")
        return []

    # --- Query sul Database Master ---
    def get_deals(self, filter_type: str = "deals", limit: int = 3) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        if filter_type == "minimi":
            cur.execute("""
                SELECT * FROM products_catalog
                WHERE current_price <= all_time_low * 1.01
                ORDER BY keepa_drop_percent DESC
                LIMIT ?
            """, (limit,))
        elif filter_type == "ciclici":
            cur.execute("""
                SELECT * FROM products_catalog
                WHERE is_cyclical = 1
                ORDER BY keepa_drop_percent DESC
                LIMIT ?
            """, (limit,))
        else: # top deals generali
            cur.execute("""
                SELECT * FROM products_catalog
                ORDER BY keepa_drop_percent DESC
                LIMIT ?
            """, (limit,))

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_categories_stats(self) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                macro_category_id,
                macro_category_name,
                COUNT(*) as count,
                ROUND(AVG(keepa_drop_percent), 1) as avg_drop
            FROM products_catalog
            GROUP BY macro_category_id, macro_category_name
            ORDER BY count DESC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_category_deals(self, category_id: str, limit: int = 5) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM products_catalog
            WHERE macro_category_id = ?
            ORDER BY keepa_drop_percent DESC
            LIMIT ?
        """, (category_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def search_products(self, query: str, limit: int = 3) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        term = f"%{query}%"
        cur.execute("""
            SELECT * FROM products_catalog
            WHERE title LIKE ? OR brand LIKE ? OR sub_category_name LIKE ?
            ORDER BY keepa_drop_percent DESC
            LIMIT ?
        """, (term, term, term, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def save_user_alert(self, user_id: str, sku_id: str, target_price: float):
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                VALUES (?, 'telegram', ?, ?)
            """, (str(user_id), sku_id, target_price))
            conn.commit()

    def get_user_wishlist(self, user_id: str) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                a.id as alert_id,
                a.product_id,
                a.target_price,
                a.created_at,
                p.title,
                p.current_price,
                p.all_time_low,
                p.affiliate_url,
                p.keepa_drop_percent
            FROM user_alerts a
            JOIN products_catalog p ON a.product_id = p.sku_id
            WHERE a.user_id = ? AND a.active = 1
            ORDER BY a.created_at DESC
        """, (str(user_id),))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # --- Formattazione Messaggi ---
    def format_deal_html(self, p: Dict) -> str:
        drop = p["keepa_drop_percent"]
        is_atl = p["current_price"] <= p["all_time_low"]
        atl_badge = "🏆 <b>MINIMO STORICO ASSOLUTO!</b>\n" if is_atl else ""
        cyclical_badge = f"🔄 <i>Consumabile: ciclo riacquisto ~{p['cycle_days']}gg</i>\n" if p["is_cyclical"] else "⚡ <i>Trend Virale</i>\n"

        html = (
            f"🔥 <b>OFFERTISSIMESCONTI</b> | Sconto Reale: <b>-{drop}%</b>\n\n"
            f"📦 <b>{p['title']}</b>\n"
            f"🏷 Categoria: #{p['macro_category_id']} • <b>{p['brand']}</b>\n"
            f"{atl_badge}"
            f"{cyclical_badge}\n"
            f"💰 Prezzo Attuale: <b>€{p['current_price']:.2f}</b>\n"
            f"❌ Prezzo di Listino: <s>€{p['list_price']:.2f}</s>\n"
            f"📉 Minimo Storico: <b>€{p['all_time_low']:.2f}</b>\n"
            f"📊 Media 30 Giorni Radar: €{p['avg_price_30d']:.2f}\n\n"
            f"📈 <code>[Media: €{p['avg_price_30d']:.2f} ──📉── Oggi: €{p['current_price']:.2f}]</code>\n"
        )
        return html

    def get_deal_keyboard(self, p: Dict) -> Dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "🛒 Acquista su Amazon", "url": p["affiliate_url"]}
                ],
                [
                    {"text": f"🔔 Traccia a -15% (€{(p['current_price']*0.85):.2f})", "callback_data": f"track_{p['sku_id']}_{(p['current_price']*0.85):.2f}"}
                ]
            ]
        }

    def send_deal(self, chat_id: int, p: Dict):
        """Invia un'offerta completa con foto reale, anteprima dettagliata e pulsanti inline."""
        caption = self.format_deal_html(p)
        kb = self.get_deal_keyboard(p)
        photo_url = p.get("image_url")
        if photo_url:
            self.send_photo(chat_id, photo_url, caption=caption, reply_markup=kb)
        else:
            self.send_message(chat_id, caption, reply_markup=kb)

    def get_categories_keyboard(self) -> Dict:
        emojis = {
            "beauty_personal_care": "🧴", "health_supplements": "💊",
            "electronics_gadgets": "📱", "home_kitchen": "🏠",
            "cleaning_household": "🧼", "pet_supplies": "🐾",
            "grocery_coffee": "☕", "sports_fitness_gear": "🏋️",
            "baby_care": "👶", "diy_tools_garden": "🛠️",
            "office_stationery": "📎", "automotive": "🚗",
            "apparel_basics": "👕", "toys_hobbies": "🎮",
            "books_planners": "📚"
        }
        cats = self.get_categories_stats()
        rows = []
        curr_row = []
        for c in cats:
            cid = c["macro_category_id"]
            ico = emojis.get(cid, "🏷")
            short_name = c["macro_category_name"].split()[0]
            if len(short_name) < 4:
                short_name = c["macro_category_name"][:14]
            label = f"{ico} {short_name} ({c['count']})"
            curr_row.append({"text": label, "callback_data": f"cat_{cid}"})
            if len(curr_row) == 2:
                rows.append(curr_row)
                curr_row = []
        if curr_row:
            rows.append(curr_row)
        rows.append([{"text": "🔙 Torna al Menu Principale", "callback_data": "menu_main"}])
        return {"inline_keyboard": rows}

    def send_category_smart_list(self, chat_id: int, category_id: str):
        products = self.get_category_deals(category_id, limit=3)
        if not products:
            self.send_message(chat_id, "Nessun prodotto trovato in questa categoria.", reply_markup=self.get_main_menu_keyboard())
            return

        cat_name = products[0]["macro_category_name"]
        header = (
            f"📂 <b>LISTA SMART: {cat_name.upper()}</b>\n"
            f"📊 <i>Top sconti verificati con media storica del Radar a 90 giorni:</i>\n"
        )
        self.send_message(chat_id, header)

        for p in products:
            self.send_deal(chat_id, p)

        more_kb = {
            "inline_keyboard": [
                [
                    {"text": "📂 Altre Categorie", "callback_data": "menu_categories"},
                    {"text": "🔙 Menu Principale", "callback_data": "menu_main"}
                ]
            ]
        }
        self.send_message(chat_id, "💡 <i>Vuoi esplorare altri dipartimenti o impostare allarmi?</i>", reply_markup=more_kb)

    def send_export_document(self, chat_id: int):
        csv_path = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
        caption = (
            "📥 <b>EXPORT COMPLETO LINK AFFILIAZIONE (PostTap & Creator)</b>\n\n"
            "Ecco il file CSV con tutti i <b>3.396 prodotti</b> dell'indagine:\n"
            "• Titoli, brand, categorie e ASIN\n"
            "• Prezzi attuali, listino e minimi storici verificati\n"
            "• Tutti i link diretti con tag: <code>offertissimes-21</code>\n\n"
            "Pronto per il caricamento su PostTap o fogli Excel/Sheets!\n"
            "🌐 Link web: https://robzombai.github.io/offertissimesconti/offertissimesconti_posttap_export.csv"
        )
        res = self.send_document(chat_id, csv_path, caption=caption)
        if not res.get("ok"):
            self.send_message(chat_id, caption, reply_markup=self.get_main_menu_keyboard())

    def get_main_menu_keyboard(self) -> Dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "🔥 Top Offerte Oggi", "callback_data": "menu_deals"},
                    {"text": "🏆 Minimi Storici", "callback_data": "menu_minimi"}
                ],
                [
                    {"text": "📂 Esplora per Categoria", "callback_data": "menu_categories"},
                    {"text": "🔄 Spesa Ciclica", "callback_data": "menu_ciclici"}
                ],
                [
                    {"text": "📋 I Miei Prodotti Seguiti", "callback_data": "menu_wishlist"},
                    {"text": "📥 Scarica Link PostTap", "callback_data": "menu_export"}
                ],
                [
                    {"text": "🔍 Come Cercare", "callback_data": "menu_search_help"}
                ]
            ]
        }

    # --- Dispatcher Comandi & Eventi ---
    def handle_message(self, msg: Dict):
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()
        first_name = msg.get("from", {}).get("first_name", "Utente")

        print(f"📩 Ricevuto messaggio da {first_name} ({chat_id}): '{text}'")

        if not text:
            return

        if text.startswith("/start"):
            welcome_text = (
                f"👋 Ciao <b>{first_name}</b>, benvenuto su <b>OFFERTISSIMESCONTI</b>! ⚡\n\n"
                f"Siamo il tuo radar intelligente per gli acquisti su Amazon. "
                f"Monitoriamo oltre <b>3.380 prodotti reali</b> ed eliminiamo i finti sconti grazie al nostro algoritmo di tracciamento continuo dei minimi storici.\n\n"
                f"💡 <b>Cosa puoi fare:</b>\n"
                f"• Clicca i pulsanti in basso per esplorare le offerte del momento\n"
                f"• Clicca su <b>📋 I Miei Prodotti Seguiti</b> per vedere i tuoi alert attivi\n"
                f"• Digita <code>/cerca &lt;prodotto&gt;</code> (es. <i>/cerca Borbone</i> oppure <i>/cerca creatina</i>)\n"
                f"• Invia direttamente il nome di un articolo per cercarlo subito!"
            )
            self.send_message(chat_id, welcome_text, reply_markup=self.get_main_menu_keyboard())

        elif text.startswith("/wishlist") or text.startswith("/allarmi") or text.startswith("/miei"):
            self.send_wishlist_message(chat_id)

        elif text.startswith("/categorie") or text.startswith("/reparti"):
            self.send_message(chat_id, "📂 <b>SELEZIONA UNA CATEGORIA:</b>\nScegli un dipartimento per visualizzare la lista intelligente delle migliori offerte attive:", reply_markup=self.get_categories_keyboard())

        elif text.startswith("/export") or text.startswith("/posttap") or text.startswith("/csv"):
            self.send_export_document(chat_id)

        elif text.startswith("/deals") or text.startswith("/offerte"):
            self.send_deals_list(chat_id, "deals")

        elif text.startswith("/minimi"):
            self.send_deals_list(chat_id, "minimi")

        elif text.startswith("/ciclici"):
            self.send_deals_list(chat_id, "ciclici")

        elif text.startswith("/cerca"):
            query = text.replace("/cerca", "").strip()
            if not query:
                self.send_message(chat_id, "⚠️ Inserisci cosa cercare. Esempio: <code>/cerca Borbone</code> oppure <code>/cerca siero</code>")
                return

            results = self.search_products(query, limit=3)
            if not results:
                self.send_message(chat_id, f"🔍 Nessun prodotto trovato per '<b>{query}</b>'. Prova con un termine più generico.")
            else:
                self.send_message(chat_id, f"🔎 Ecco i risultati migliori per '<b>{query}</b>':")
                for p in results:
                    self.send_deal(chat_id, p)

        elif text.startswith("/track"):
            parts = text.split()
            if len(parts) < 3:
                self.send_message(chat_id, "⚠️ Formato: <code>/track &lt;SKU_ID&gt; &lt;PREZZO_DESIDERATO&gt;</code>\nEsempio: <code>/track SKU-BEAU-0001 12.50</code>")
                return
            sku_id = parts[1]
            try:
                target_price = float(parts[2].replace(",", "."))
                self.save_user_alert(chat_id, sku_id, target_price)
                self.send_message(chat_id, f"✅ <b>Allerta impostata con successo!</b>\nTi invierò una notifica istantanea appena il prodotto <code>{sku_id}</code> scenderà sotto <b>€{target_price:.2f}</b>.")
            except ValueError:
                self.send_message(chat_id, "⚠️ Prezzo non valido. Inserisci un numero valido (es. 19.90).")

        elif "amazon.it" in text or "amzn.to" in text or re.match(r'^[A-Z0-9]{10}$', text.strip()):
            asin = self.extract_asin(text)
            if asin:
                self.handle_asin_lookup(chat_id, asin)
            else:
                self.send_message(chat_id, "⚠️ Impossibile estrarre l'ASIN da questo link Amazon. Verifica l'URL.")

        else:
            # Ricerca generica di default
            results = self.search_products(text, limit=2)
            if results:
                self.send_message(chat_id, f"🔎 Ho cercato '<b>{text}</b>' per te nel catalogo:")
                for p in results:
                    self.send_deal(chat_id, p)
            else:
                self.send_message(chat_id, f"Non ho trovato risultati per '<b>{text}</b>'. Prova con comandi come <code>/deals</code> o <code>/minimi</code>.", reply_markup=self.get_main_menu_keyboard())

    def extract_asin(self, text: str) -> Optional[str]:
        clean = text.strip()
        if re.match(r'^[A-Z0-9]{10}$', clean):
            return clean
        m = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', text)
        if m:
            return m.group(1)
        if "amzn.to/" in text:
            short_url_match = re.search(r'https?://amzn\.to/[A-Za-z0-9]+', text)
            if short_url_match:
                try:
                    r = requests.get(short_url_match.group(0), timeout=5, allow_redirects=True)
                    m2 = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', r.url)
                    if m2:
                        return m2.group(1)
                except Exception:
                    pass
        return None

    def handle_asin_lookup(self, chat_id: int, asin: str):
        affiliate_url = f"https://www.amazon.it/dp/{asin}?tag=offertissimes-21"
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM products_catalog WHERE asin = ?", (asin,))
        p = cur.fetchone()
        conn.close()

        if p:
            p_dict = dict(p)
            header = "⚡ <b>PRODOTTO MONITORATO RILEVATO!</b>\nEcco il link affiliato con <b>Deeplinking Amazon App attivo</b>:\n\n"
            card_html = header + self.format_deal_html(p_dict)
            photo_url = p_dict.get("image_url")
            kb = self.get_deal_keyboard(p_dict)
            if photo_url:
                self.send_photo(chat_id, photo_url, caption=card_html, reply_markup=kb)
            else:
                self.send_message(chat_id, card_html, reply_markup=kb)
        else:
            text = (
                f"🔗 <b>LINK AFFILIATO GENERATO CON SUCCESSO!</b>\n\n"
                f"📦 <b>ASIN Rilevato:</b> <code>{asin}</code>\n"
                f"🏷 <b>Tracking ID:</b> <code>offertissimes-21</code>\n"
                f"📲 <b>Deeplinking App:</b> ✅ ATTIVO (apre subito l'app Amazon)\n\n"
                f"👉 <b>Tuo Link Diretto:</b>\n<code>{affiliate_url}</code>\n\n"
                f"💡 <i>Puoi copiare questo link e condividerlo sui social, canali o PostTap per ricevere le commissioni su ogni acquisto idoneo.</i>"
            )
            kb = {
                "inline_keyboard": [
                    [{"text": "🛒 Apri su Amazon (App Deeplink)", "url": affiliate_url}]
                ]
            }
            self.send_message(chat_id, text, reply_markup=kb)

    def handle_callback(self, cb: Dict):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")

        print(f"🔘 Callback premuto da {chat_id}: {data}")

        if data == "menu_deals":
            self.answer_callback_query(cb_id, "Caricamento offerte...")
            self.send_deals_list(chat_id, "deals")
        elif data == "menu_minimi":
            self.answer_callback_query(cb_id, "Caricamento minimi storici...")
            self.send_deals_list(chat_id, "minimi")
        elif data == "menu_categories":
            self.answer_callback_query(cb_id, "Caricamento categorie...")
            self.send_message(chat_id, "📂 <b>SELEZIONA UNA CATEGORIA:</b>\nScegli un dipartimento per visualizzare la lista intelligente delle migliori offerte attive:", reply_markup=self.get_categories_keyboard())
        elif data == "menu_export":
            self.answer_callback_query(cb_id, "Invio export PostTap...")
            self.send_export_document(chat_id)
        elif data == "menu_main":
            self.answer_callback_query(cb_id)
            self.send_message(chat_id, "⚡ <b>Menu Principale OFFERTISSIMESCONTI</b>", reply_markup=self.get_main_menu_keyboard())
        elif data.startswith("cat_"):
            cat_id = data.replace("cat_", "")
            self.answer_callback_query(cb_id, "Caricamento offerte categoria...")
            self.send_category_smart_list(chat_id, cat_id)
        elif data == "menu_ciclici":
            self.answer_callback_query(cb_id, "Caricamento spesa ciclica...")
            self.send_deals_list(chat_id, "ciclici")
        elif data == "menu_search_help":
            self.answer_callback_query(cb_id)
            self.send_message(chat_id, "🔍 <b>Come cercare un prodotto:</b>\nScrivi semplicemente il nome dell'articolo nella chat (es. <code>caffè</code>, <code>proteine</code>, <code>Finish</code>) oppure usa <code>/cerca &lt;nome&gt;</code>.")
        elif data == "menu_wishlist":
            self.answer_callback_query(cb_id, "Caricamento lista...")
            self.send_wishlist_message(chat_id)
        elif data.startswith("track_"):
            parts = data.split("_")
            if len(parts) == 3:
                sku_id = parts[1]
                target_price = float(parts[2])
                self.save_user_alert(chat_id, sku_id, target_price)
                self.answer_callback_query(cb_id, f"Allerta salvata a €{target_price:.2f}!")
                self.send_message(chat_id, f"🔔 <b>Allerta registrata!</b> Ti avviseremo appena <code>{sku_id}</code> scende sotto <b>€{target_price:.2f}</b>.")
            else:
                self.answer_callback_query(cb_id)
        else:
            self.answer_callback_query(cb_id)

    def send_wishlist_message(self, chat_id: int):
        wishlist = self.get_user_wishlist(str(chat_id))
        if not wishlist:
            self.send_message(
                chat_id,
                "📋 <b>La tua lista prodotti seguiti è vuota!</b>\n\n"
                "Per iniziare a seguire un articolo, clicca su <i>'🔔 Traccia a -15%'</i> "
                "sotto qualsiasi prodotto, oppure usa il comando:\n"
                "<code>/track &lt;SKU_ID&gt; &lt;PREZZO&gt;</code>.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return

        self.send_message(chat_id, f"📋 <b>I TUOI PRODOTTI SEGUITI ({len(wishlist)}):</b>\n\nEcco lo stato attuale dei prodotti che stai monitorando:\n")
        for item in wishlist:
            is_reached = item["current_price"] <= item["target_price"]
            status_text = "🎉 <b>PREZZO RAGGIUNTO!</b>" if is_reached else "⏳ <i>In monitoraggio attivo...</i>"
            text = (
                f"📦 <b>{item['title']}</b>\n"
                f"🎯 Tuo Target: <b>€{item['target_price']:.2f}</b>\n"
                f"💰 Prezzo Attuale: <b>€{item['current_price']:.2f}</b> (-{item['keepa_drop_percent']}%)\n"
                f"📉 Minimo Storico: €{item['all_time_low']:.2f}\n"
                f"📊 Stato: {status_text}\n"
            )
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🛒 Acquista su Amazon", "url": item["affiliate_url"]}
                    ]
                ]
            }
            self.send_message(chat_id, text, reply_markup=keyboard)

    def send_deals_list(self, chat_id: int, filter_type: str):
        deals = self.get_deals(filter_type, limit=3)
        title_map = {
            "deals": "🔥 <b>TOP SCONTI RECORD DEL MOMENTO:</b>",
            "minimi": "🏆 <b>PRODOTTI AL MINIMO STORICO ASSOLUTO:</b>",
            "ciclici": "🔄 <b>CONSUMABILI & SPESA CICLICA IN SCONTO:</b>"
        }
        self.send_message(chat_id, title_map.get(filter_type, "Ecco le offerte:"))
        for d in deals:
            self.send_deal(chat_id, d)

    def run_polling(self):
        info = self.test_connection()
        if not info.get("ok"):
            print("❌ Errore: Token non valido o impossibile connettersi a Telegram API:")
            print(info)
            return

        bot_username = info["result"]["username"]
        print(f"✅ Bot Telegram avviato con successo!")
        print(f"🤖 Nome Bot: @{bot_username}")
        print("📡 In ascolto per nuovi messaggi (premi CTRL+C per arrestare)...")

        while True:
            updates = self.get_updates()
            for u in updates:
                self.last_update_id = u["update_id"]
                if "message" in u:
                    self.handle_message(u["message"])
                elif "callback_query" in u:
                    self.handle_callback(u["callback_query"])
            time.sleep(1)

if __name__ == "__main__":
    token = get_bot_token()
    if not token and len(sys.argv) > 1:
        token = sys.argv[1].strip()

    if not token:
        print("\n⚠️ ATTENZIONE: Nessun Token Telegram fornito!")
        print("Per avviare il bot, passa il token da riga di comando o salvalo nel file .env:")
        print("Esempio: python3 bot/telegram_bot_runner.py 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ\n")
        sys.exit(1)

    bot = OffertissimeScontiTelegramBot(token)
    bot.run_polling()
