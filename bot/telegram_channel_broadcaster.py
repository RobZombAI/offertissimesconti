"""
OFFERTISSIMESCONTI - Telegram Channel Broadcaster (Produzione)
Modulo di pubblicazione automatica programmata sul Canale Telegram ufficiale.
Invia ogni 10 minuti (configurabile) la migliore offerta attiva reale del catalogo:
- Rileva sconti record, minimi storici assoluti e virali
- Foto ad alta risoluzione del prodotto
- Layout accattivante con calcolo risparmio in € e %
- Pulsanti inline per acquisto diretto con affiliazione verificata (tag=offertissimes-21)
- Deep-linking integrato per tracciamento 1-tap sul bot (@offertissimesconti_radar_bot)
- Registro anti-duplicati su SQLite (channel_broadcast_log)
"""

import os
import sys
import time
import sqlite3
import requests
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
ENV_FILE = os.path.join(BASE_DIR, ".env")

def load_env() -> Dict[str, str]:
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

class TelegramChannelBroadcaster:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
        db_path: str = DB_PATH
    ):
        env = load_env()
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN") or env.get("TELEGRAM_BOT_TOKEN", "")
        self.channel_id = channel_id or os.environ.get("TELEGRAM_CHANNEL_ID") or env.get("TELEGRAM_CHANNEL_ID", "-1003838698998")
        self.db_path = db_path
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.init_broadcast_table()

    def init_broadcast_table(self):
        """Inizializza la tabella SQLite per tracciare i post inviati ed evitare duplicati."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS channel_broadcast_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku_id TEXT NOT NULL,
                    asin TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    price_posted REAL NOT NULL,
                    list_price REAL,
                    drop_percent REAL,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id INTEGER,
                    FOREIGN KEY(sku_id) REFERENCES products_catalog(sku_id)
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_sku ON channel_broadcast_log(sku_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_posted_at ON channel_broadcast_log(posted_at DESC);")
            conn.commit()

    def check_channel_permissions(self, channel_id: Optional[str] = None) -> Dict:
        """Verifica se il bot ha accesso al canale e i diritti di invio."""
        target = channel_id or self.channel_id
        if not self.bot_token or not target:
            return {"ok": False, "description": "Token o Channel ID mancante"}

        url = f"{self.api_url}/getChat"
        try:
            res = requests.get(url, params={"chat_id": target}, timeout=10)
            data = res.json()
            if not data.get("ok"):
                return data

            chat = data.get("result", {})
            return {"ok": True, "chat": chat}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def get_recent_broadcasted_categories(self, limit: int = 3) -> List[str]:
        """Recupera le macro_categorie dei post più recenti per alternare i reparti."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT p.macro_category_id
                FROM channel_broadcast_log b
                JOIN products_catalog p ON b.sku_id = p.sku_id
                ORDER BY b.posted_at DESC
                LIMIT ?
            """, (limit,))
            return [row[0] for row in cur.fetchall()]

    def get_next_deal_to_broadcast(self, cooldown_hours: int = 48) -> Optional[Dict]:
        """
        Seleziona la migliore offerta attiva non ancora inviata di recente:
        - Priorità 1: Minimi storici assoluti con forte sconto reale
        - Priorità 2: Top drop percent (> 25%) con virality score elevato
        - Rotazione intelligente per evitare di postare la stessa categoria di fila
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        recent_cats = self.get_recent_broadcasted_categories(limit=2)

        # Cerca offerte escludendo quelle trasmesse di recente nel periodo di cooldown
        cur.execute(f"""
            SELECT p.*,
                   (p.list_price - p.current_price) AS savings_eur,
                   CASE WHEN p.current_price <= p.all_time_low * 1.01 THEN 1 ELSE 0 END AS is_atl,
                   CASE WHEN ph.sku_id IS NOT NULL THEN 1 ELSE 0 END AS is_fresh_drop
            FROM products_catalog p
            LEFT JOIN (
                SELECT sku_id, MAX(posted_at) as last_posted
                FROM channel_broadcast_log
                WHERE datetime(posted_at) >= datetime('now', '-{cooldown_hours} hours')
                GROUP BY sku_id
            ) recent ON p.sku_id = recent.sku_id
            LEFT JOIN (
                SELECT DISTINCT sku_id
                FROM price_history
                WHERE datetime(recorded_at) >= datetime('now', '-24 hours')
            ) ph ON p.sku_id = ph.sku_id
            WHERE recent.sku_id IS NULL
              AND p.current_price > 0
              AND p.list_price > p.current_price
              AND (p.keepa_drop_percent >= 15 OR p.current_price <= p.all_time_low * 1.02)
              AND p.image_url IS NOT NULL AND p.image_url != ''
              AND p.affiliate_url IS NOT NULL AND p.affiliate_url != ''
            ORDER BY 
                is_fresh_drop DESC,
                is_atl DESC,
                p.keepa_drop_percent DESC,
                p.virality_score DESC
            LIMIT 50
        """)

        candidates = [dict(r) for r in cur.fetchall()]
        conn.close()

        if not candidates:
            # Se tutti i prodotti sono stati trasmessi nel cooldown, riduci a 12 ore
            if cooldown_hours > 12:
                return self.get_next_deal_to_broadcast(cooldown_hours=12)
            return None

        # Preferisci un candidato di una categoria diversa da quelle inviate appena prima
        for cand in candidates:
            if cand["macro_category_id"] not in recent_cats:
                return cand

        # Fallback sul primo miglior candidato
        return candidates[0]

    def format_channel_post(self, deal: Dict) -> Tuple[str, Dict]:
        """
        Formatta il post per il canale Telegram:
        - Layout accattivante, pulito, ad alta conversione
        - Pulsanti inline per Amazon, Bot e Sito Web
        """
        title = deal["title"]
        brand = deal.get("brand", "Amazon")
        cat_name = deal.get("macro_category_name", "Offerte")
        curr_price = deal["current_price"]
        list_price = deal["list_price"]
        atl = deal["all_time_low"]
        drop = deal["keepa_drop_percent"]
        savings = list_price - curr_price
        is_atl = curr_price <= (atl * 1.01)
        is_cyclical = deal.get("is_cyclical", 0)

        is_fresh = bool(deal.get("is_fresh_drop"))
        if is_fresh:
            badge_header = f"⚡ <b>NUOVO CALO DI PREZZO REALE RILEVATO!</b> (-{drop:.0f}%)"
        else:
            badge_header = f"📉 <b>CALO DI PREZZO REALE AMAZON (-{drop:.0f}%)!</b>"
        cyclical_line = f"🔄 <i>Consumabile: ciclo riacquisto ~{deal.get('cycle_days', 30)}gg</i>\n" if is_cyclical else ""

        html = (
            f"{badge_header}\n"
            f"🏷 <b>{cat_name}</b> • {brand}\n\n"
            f"📦 <b>{title}</b>\n\n"
            f"{cyclical_line}"
            f"💰 <b>Prezzo Offerta: €{curr_price:.2f}</b>\n"
            f"❌ Prezzo Consigliato: <s>€{list_price:.2f}</s>\n"
            f"💸 <b>Risparmio Reale: €{savings:.2f} (-{drop:.0f}%)</b>\n\n"
            f"📊 <code>[Media 30gg: €{deal.get('avg_price_30d', list_price):.2f} ──📉── Oggi: €{curr_price:.2f}]</code>\n\n"
            f"⚡ <i>Offerta a tempo, scorte limitate. In qualità di Affiliato Amazon io ricevo un guadagno dagli acquisti idonei.</i>"
        )

        aff_url = deal["affiliate_url"]
        sku_id = deal["sku_id"]
        bot_track_url = f"https://t.me/offertissimesconti_radar_bot?start=track_{sku_id}"
        web_radar_url = "https://robzombai.github.io/offertissimesconti/"

        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🛒 ACQUISTA SUBITO SU AMAZON", "url": aff_url}
                ],
                [
                    {"text": "🔔 Segui Prezzo con il Bot", "url": bot_track_url},
                    {"text": "🌐 Radar Web Completo", "url": web_radar_url}
                ]
            ]
        }

        return html, keyboard

    def broadcast_deal(self, deal: Dict, channel_id: Optional[str] = None) -> Dict:
        """Invia l'offerta sul Canale Telegram e ne registra l'esito nel database."""
        target = channel_id or self.channel_id
        if not self.bot_token or not target:
            return {"ok": False, "error": "Token Telegram o Canale non configurato"}

        caption, keyboard = self.format_channel_post(deal)
        photo_url = (deal.get("image_url") or "").strip()
        if not photo_url or photo_url.endswith(".gif"):
            photo_url = "https://robzombai.github.io/offertissimesconti/images/logo.jpg"

        # Invia con foto se disponibile
        url = f"{self.api_url}/sendPhoto"
        truncated_caption = caption[:1020] + "..." if len(caption) > 1024 else caption
        payload = {
            "chat_id": target,
            "photo": photo_url,
            "caption": truncated_caption,
            "parse_mode": "HTML",
            "reply_markup": keyboard
        }

        try:
            res = requests.post(url, json=payload, timeout=15)
            data = res.json()
            if not data.get("ok"):
                # Fallback su messaggio di testo
                url_msg = f"{self.api_url}/sendMessage"
                res_msg = requests.post(url_msg, json={
                    "chat_id": target,
                    "text": caption,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard,
                    "disable_web_page_preview": False
                }, timeout=15)
                data = res_msg.json()

            if data.get("ok"):
                msg_id = data.get("result", {}).get("message_id")
                # Registra nel database per evitare duplicati
                self.record_broadcast(deal, target, msg_id)
                print(f"📢 [CANALE TELEGRAM] Offerta pubblicata con successo: {deal['title'][:50]}... (€{deal['current_price']:.2f})")
                return {"ok": True, "message_id": msg_id, "deal": deal}
            else:
                err_desc = data.get("description", "Errore sconosciuto")
                print(f"❌ Errore invio al canale {target}: {err_desc}")
                return {"ok": False, "description": err_desc}
        except Exception as e:
            print(f"❌ Eccezione durante la pubblicazione al canale {target}: {e}")
            return {"ok": False, "error": str(e)}

    def record_broadcast(self, deal: Dict, channel_id: str, message_id: Optional[int]):
        """Salva il post nel log per lo storico e l'anti-ripetizione."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO channel_broadcast_log (
                    sku_id, asin, channel_id, price_posted, list_price, drop_percent, telegram_message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                deal["sku_id"],
                deal["asin"],
                channel_id,
                deal["current_price"],
                deal["list_price"],
                deal["keepa_drop_percent"],
                message_id
            ))
            conn.commit()

    def run_broadcast_cycle(self) -> Dict:
        """Esegue un singolo ciclo di selezione e pubblicazione."""
        deal = self.get_next_deal_to_broadcast()
        if not deal:
            print("ℹ️ Nessuna nuova offerta qualificata trovata in questo momento.")
            return {"ok": False, "reason": "no_deal_available"}

        return self.broadcast_deal(deal)

    def populate_channel(self, count: int = 5, sleep_seconds: float = 2.5) -> List[Dict]:
        """
        Carica un lotto iniziale di offerte tra le migliori attualmente presenti nel catalogo,
        alternando le categorie e inviandole al canale con una breve pausa per rispettare
        i rate limit di Telegram.
        """
        published = []
        print(f"📦 Avvio caricamento iniziale di {count} offerte presenti sul canale {self.channel_id}...")
        for i in range(count):
            deal = self.get_next_deal_to_broadcast()
            if not deal:
                print(f"ℹ️ Nessun'altra offerta qualificata disponibile (inviate {len(published)}).")
                break
            res = self.broadcast_deal(deal)
            if res.get("ok"):
                published.append(deal)
                print(f"   [{i+1}/{count}] Pubblicato: {deal['title'][:40]}... (€{deal['current_price']:.2f})")
            else:
                print(f"   [{i+1}/{count}] Errore invio: {res}")
            if i < count - 1:
                time.sleep(sleep_seconds)
        print(f"✅ Caricamento completato: {len(published)} offerte pubblicate con successo!")
        return published

    def run_continuous_broadcaster(self, interval_seconds: int = 600):
        """
        Ciclo principale: pubblica una nuova offerta ogni 10 minuti (default 600s).
        Se il bot non è ancora amministratore del canale, attende senza crashare.
        """
        print("=" * 65)
        print("📢 OFFERTISSIMESCONTI - TELEGRAM CHANNEL BROADCASTER ATTIVO")
        print(f"🎯 Canale di destinazione: {self.channel_id}")
        print(f"⏱ Frequenza pubblicazione: ogni {interval_seconds // 60} minuti ({interval_seconds}s)")
        print(f"🤖 Bot associato: @offertissimesconti_radar_bot")
        print("=" * 65)

        loop_count = 0
        while True:
            try:
                loop_count += 1
                env_curr = load_env()
                if env_curr.get("TELEGRAM_CHANNEL_ID"):
                    self.channel_id = env_curr["TELEGRAM_CHANNEL_ID"]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{now_str}] 🔄 Ciclo #{loop_count}: Verifica nuove offerte per il canale...")

                # Verifica se il bot può postare sul canale
                perm_check = self.check_channel_permissions()
                if not perm_check.get("ok"):
                    desc = perm_check.get("description", "")
                    print(f"⚠️ In attesa di autorizzazione sul canale {self.channel_id}:")
                    print(f"   Dettaglio Telegram API: {desc}")
                    print(f"   💡 Promemoria: Assicurati di aver aggiunto @offertissimesconti_radar_bot come Amministratore nel canale {self.channel_id} con permesso 'Pubblica Messaggi'.")
                else:
                    res = self.run_broadcast_cycle()
                    if res.get("ok"):
                        print(f"✅ Offerta pubblicata con successo. Prossimo aggiornamento tra {interval_seconds // 60} minuti.")
                    elif not res.get("ok") and "not a member" in str(res.get("description", "")).lower():
                        print(f"⚠️ Aggiungi @offertissimesconti_radar_bot come Amministratore nel canale {self.channel_id}.")
                    else:
                        print(f"ℹ️ Nessuna nuova offerta da pubblicare in questo ciclo ({res.get('reason', res)}). Prossimo controllo tra {interval_seconds // 60} minuti.")

            except KeyboardInterrupt:
                print("\n🛑 Broadcaster arrestato dall'utente.")
                break
            except Exception as e:
                print(f"❌ Eccezione nel loop del broadcaster: {e}")

            time.sleep(interval_seconds)

def main():
    parser = argparse.ArgumentParser(description="OffertissimeSconti Telegram Channel Broadcaster")
    parser.add_argument("--once", action="store_true", help="Pubblica una singola offerta e termina")
    parser.add_argument("--populate", type=int, default=0, help="Carica subito N offerte presenti sul canale prima di avviare il loop o terminare")
    parser.add_argument("--interval", type=int, default=600, help="Intervallo di pubblicazione in secondi (default 600 = 10 min)")
    parser.add_argument("--channel", type=str, default=None, help="Canale di destinazione Telegram (es. @Offertissimesconti o -100...)")
    parser.add_argument("--test-channel", action="store_true", help="Verifica permessi del bot sul canale e termina")
    parser.add_argument("--dry-run", action="store_true", help="Seleziona e formatta la prossima offerta senza inviarla a Telegram")
    args = parser.parse_args()

    broadcaster = TelegramChannelBroadcaster(channel_id=args.channel)

    if args.test_channel:
        res = broadcaster.check_channel_permissions()
        print("Risultato verifica canale:", res)
        sys.exit(0 if res.get("ok") else 1)

    if args.dry_run:
        deal = broadcaster.get_next_deal_to_broadcast()
        if deal:
            caption, kb = broadcaster.format_channel_post(deal)
            print("\n--- ANTEPRIMA PROSSIMA OFFERTA SELEZIONATA ---")
            print(f"Prodotto: {deal['title']}")
            print(f"Prezzo: €{deal['current_price']} (Listino: €{deal['list_price']}, Sconto: -{deal['keepa_drop_percent']}%)")
            print(f"Immagine: {deal['image_url']}")
            print(f"Affiliate URL: {deal['affiliate_url']}")
            print("\n--- TESTO FORMATTATO TELEGRAM ---")
            print(caption)
            print("\n--- PULSANTI INLINE ---")
            print(kb)
        else:
            print("Nessuna offerta trovata.")
        sys.exit(0)

    if args.populate > 0:
        broadcaster.populate_channel(count=args.populate)
        if args.once:
            sys.exit(0)

    if args.once:
        res = broadcaster.run_broadcast_cycle()
        print("Risultato invio:", res)
        sys.exit(0 if res.get("ok") else 1)

    broadcaster.run_continuous_broadcaster(interval_seconds=args.interval)

if __name__ == "__main__":
    main()
