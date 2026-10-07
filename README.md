# ⚡ OFFERTISSIMESCONTI – Piattaforma Ufficiale

Ecosistema completo per solopreneur: **Sito Web Live**, **API REST**, **Bot Telegram Interattivo** e **Motore Keepa-Style** per il tracciamento di oltre **3.380 prodotti** ciclici e virali su Amazon.

---

## 📁 Struttura del Progetto

```
modest-hawking/
├── api/
│   └── server.py                   # Server Web integrato (serve sia il frontend su '/' che le REST API)
├── bot/
│   ├── telegram_bot_runner.py      # Bot Telegram Ufficiale di Produzione (comandi, tastiere inline, alert)
│   └── telegram_deal_bot.py        # Simulatore e formattatore post per canali broadcast
├── core/
│   └── price_engine.py             # Motore Keepa-style (calcolo all-time-low, medie 30/90gg, trigger notifiche)
├── data/
│   ├── amazon_3000_master_catalog.db   # Database SQLite con 3.380 prodotti indicizzati su 15 categorie
│   ├── amazon_3000_master_catalog.json # Export JSON completo del catalogo
│   ├── amazon_3000_master_catalog.csv  # Export CSV compatibile con Excel/Pandas
│   └── tracker_test.db                 # Database persistente delle wishlist utenti
├── web/
│   ├── index.html                  # Homepage professionale responsive per approvazione Amazon Associates
│   ├── style.css                   # Design system moderno con badge e grafici sparkline
│   └── app.js                      # Client interattivo con ricerca live e modal alert
├── scripts/
│   └── build_3000_market_database.py # Script di rigenerazione del catalogo
├── .env.example                    # Template di configurazione per Token Telegram e Tag Affiliato
└── README.md
```

---

## 🚀 1. Avviare il Sito Web & REST API
Il server locale è attivo su:
👉 **[http://localhost:8000](http://localhost:8000)**

Se devi riavviarlo:
```bash
python3 api/server.py
```

---

## 🤖 2. Avviare il Bot Telegram Live

1. Apri Telegram sul tuo smartphone o PC e cerca **`@BotFather`**
2. Invia `/newbot`
3. Scegli il nome: `OffertissimeSconti | Radar Minimi Storici`
4. Scegli lo username: ad esempio `offertissimesconti_radar_bot`
5. Copia il token HTTP API che ti restituisce BotFather (es. `123456789:ABCdef...`)
6. Avvia il bot passando il token:
```bash
python3 bot/telegram_bot_runner.py <IL_TUO_TOKEN>
```
*Oppure salvalo nel file `.env` come `TELEGRAM_BOT_TOKEN=...` ed esegui semplicemente:*
```bash
python3 bot/telegram_bot_runner.py
```

Il bot risponderà immediatamente a:
- `/start` $\rightarrow$ Menu principale con pulsanti inline
- `/deals` $\rightarrow$ Top sconti record del momento
- `/minimi` $\rightarrow$ Prodotti al minimo storico assoluto
- `/ciclici` $\rightarrow$ Spesa ciclica e consumabili (caffè, integratori, detersivi)
- `/cerca <nome>` $\rightarrow$ Ricerca libera su oltre 3.380 prodotti nel database
- `/track <sku> <prezzo>` $\rightarrow$ Impostazione allerta personale

---

## 🌐 3. Pubblicare il Sito Online Gratis (per Amazon Associates)

Per avere un URL pubblico gratuito da fornire ad Amazon:
- **Netlify Drop**: trascina la cartella `web/` su [app.netlify.com/drop](https://app.netlify.com/drop).
- **Vercel**: carica il progetto per ottenere `offertissimesconti.vercel.app`.
