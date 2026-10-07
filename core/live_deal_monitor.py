"""
Live Deal Monitor & Price Alert Dispatcher
Motore di monitoraggio continuo per OFFERTISSIMESCONTI.
Scansiona le variazioni di prezzo, verifica le wishlist degli utenti (user_alerts),
e invia notifiche push istantanee su Telegram quando un prezzo scende sotto il target.
"""

import os
import sys
import time
import sqlite3
import requests
import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
ENV_FILE = os.path.join(BASE_DIR, ".env")

def get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token.strip()
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()
    return ""

class LiveDealMonitor:
    def __init__(self, db_path: str = DB_PATH, bot_token: Optional[str] = None):
        self.db_path = db_path
        self.bot_token = bot_token or get_bot_token()
        self.telegram_api = f"https://api.telegram.org/bot{self.bot_token}"

    def send_telegram_alert(self, chat_id: str, text: str, keyboard: Optional[Dict] = None) -> bool:
        if not self.bot_token:
            print("⚠️ Token Telegram non configurato, impossibile inviare alert.")
            return False

        url = f"{self.telegram_api}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if keyboard:
            payload["reply_markup"] = keyboard

        try:
            res = requests.post(url, json=payload, timeout=10)
            data = res.json()
            if data.get("ok"):
                print(f"✅ Notifica inviata con successo a {chat_id}!")
                return True
            else:
                print(f"❌ Errore Telegram verso {chat_id}: {data.get('description')}")
                return False
        except Exception as e:
            print(f"❌ Eccezione nell'invio a {chat_id}: {e}")
            return False

    def send_telegram_photo(self, chat_id: str, photo_url: str, caption: str, keyboard: Optional[Dict] = None) -> bool:
        """Invia notifica con foto del prodotto o ripiega su messaggio testuale."""
        if not self.bot_token or not photo_url:
            return self.send_telegram_alert(chat_id, caption, keyboard)

        url = f"{self.telegram_api}/sendPhoto"
        truncated_caption = caption[:1020] + "..." if len(caption) > 1024 else caption
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": truncated_caption,
            "parse_mode": "HTML"
        }
        if keyboard:
            payload["reply_markup"] = keyboard

        try:
            res = requests.post(url, json=payload, timeout=12)
            data = res.json()
            if data.get("ok"):
                print(f"✅ Notifica con foto inviata con successo a {chat_id}!")
                return True
            else:
                print(f"⚠️ Invio foto fallito verso {chat_id} ({data.get('description')}). Fallback su messaggio testuale.")
                return self.send_telegram_alert(chat_id, caption, keyboard)
        except Exception as e:
            print(f"⚠️ Eccezione invio foto a {chat_id} ({e}). Fallback su messaggio testuale.")
            return self.send_telegram_alert(chat_id, caption, keyboard)

    def check_user_alerts(self) -> int:
        """
        Controlla tutti gli alert attivi in 'user_alerts'.
        Se current_price <= target_price, invia la notifica push all'utente.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Rileva colonne disponibili per compatibilità con database legacy di test
        cur.execute("PRAGMA table_info(products_catalog)")
        cols = [col[1] for col in cur.fetchall()]
        img_col = "p.image_url," if "image_url" in cols else "'' as image_url,"

        # Seleziona alert dove il prezzo attuale è sceso sotto il target dell'utente
        cur.execute(f"""
            SELECT 
                a.id as alert_id,
                a.user_id,
                a.channel,
                a.product_id,
                a.target_price,
                a.last_notified,
                p.title,
                p.current_price,
                p.list_price,
                p.all_time_low,
                p.avg_price_30d,
                p.affiliate_url,
                p.brand,
                {img_col}
                p.sku_id
            FROM user_alerts a
            JOIN products_catalog p ON a.product_id = p.sku_id
            WHERE a.active = 1 
              AND p.current_price <= a.target_price
              AND (a.last_notified IS NULL OR datetime(a.last_notified) <= datetime('now', '-6 hours'))
        """)

        alerts_to_notify = [dict(r) for r in cur.fetchall()]
        notified_count = 0

        for alert in alerts_to_notify:
            user_id = alert["user_id"]
            title = alert["title"]
            curr = alert["current_price"]
            target = alert["target_price"]
            list_p = alert["list_price"]
            atl = alert["all_time_low"]
            aff_url = alert["affiliate_url"]

            is_atl = curr <= atl
            atl_badge = "🏆 <b>NUOVO MINIMO STORICO ASSOLUTO!</b>\n" if is_atl else ""
            discount_pct = round(((list_p - curr) / list_p) * 100, 1)

            message = (
                f"🚨 <b>ALLARME PREZZO SOTTOSOGLIA!</b> ⚡\n\n"
                f"Il prodotto che stavi seguendo è appena sceso al prezzo desiderato!\n\n"
                f"📦 <b>{title}</b>\n"
                f"{atl_badge}\n"
                f"🎯 Il tuo target: <b>€{target:.2f}</b>\n"
                f"💰 <b>Prezzo Attuale: €{curr:.2f}</b> (-{discount_pct}% da listino)\n"
                f"❌ Prezzo di Listino: <s>€{list_p:.2f}</s>\n\n"
                f"⏱ <i>Attenzione: i ribassi su Amazon possono durare poche ore per esaurimento scorte!</i>"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "🛒 ACQUISTA SUBITO SU AMAZON", "url": aff_url}
                    ]
                ]
            }

            if alert["channel"] == "telegram":
                img_url = alert.get("image_url")
                if img_url:
                    success = self.send_telegram_photo(user_id, img_url, message, keyboard)
                else:
                    success = self.send_telegram_alert(user_id, message, keyboard)
                if success:
                    cur.execute("""
                        UPDATE user_alerts 
                        SET last_notified = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (alert["alert_id"],))
                    notified_count += 1

        conn.commit()
        conn.close()
        return notified_count

    def update_product_price(self, sku_id: str, new_price: float) -> bool:
        """
        Aggiorna il prezzo di un prodotto, ricalcola All-Time Low, registra lo storico
        e verifica se scattano alert per gli utenti.
        """
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("SELECT current_price, list_price, all_time_low, avg_price_30d FROM products_catalog WHERE sku_id = ?", (sku_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return False

        old_price, list_price, atl, avg30 = row
        new_atl = min(atl, new_price)
        drop_percent = round(((avg30 - new_price) / avg30) * 100, 1) if avg30 > 0 else 0

        # Aggiorna catalogo
        cur.execute("""
            UPDATE products_catalog
            SET current_price = ?,
                all_time_low = ?,
                keepa_drop_percent = ?
            WHERE sku_id = ?
        """, (new_price, new_atl, drop_percent, sku_id))

        # Registra storico
        cur.execute("""
            INSERT INTO price_history (sku_id, price)
            VALUES (?, ?)
        """, (sku_id, new_price))

        conn.commit()
        conn.close()

        print(f"🔄 Prezzo aggiornato per {sku_id}: da €{old_price:.2f} a €{new_price:.2f} (Drop: {drop_percent}%)")

        # Controlla subito se scattano alert
        self.check_user_alerts()
        return True

    def run_periodic_monitoring(self, interval_seconds: int = 60):
        print("📡 Motore Live Deal Monitor avviato.")
        print(f"⏱ Frequenza di scansione: ogni {interval_seconds} secondi.")
        while True:
            notified = self.check_user_alerts()
            if notified > 0:
                print(f"🔔 Inviati {notified} allarmi prezzo agli utenti!")
            time.sleep(interval_seconds)

if __name__ == "__main__":
    monitor = LiveDealMonitor()
    monitor.run_periodic_monitoring(interval_seconds=30)
    print(f"Allarmi inviati durante il test: {notified}")
