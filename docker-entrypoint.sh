#!/usr/bin/env bash
# ==============================================================================
# OFFERTISSIMESCONTI - Production Docker Entrypoint & Process Manager
# ==============================================================================
set -e

MODE="${1:-all}"

echo "========================================================"
echo "🚀 AVVIO OFFERTISSIMESCONTI - Server di Produzione"
echo "🕒 Data/Ora: $(date -u)"
echo "⚙️ Modalità: $MODE"
echo "========================================================"

case "$MODE" in
  api)
    echo "🌐 Avvio API Server & Web Frontend sulla porta $PORT..."
    exec python api/server.py
    ;;
  monitor)
    echo "🔥 Avvio Radar Live Deal Monitor 24/7..."
    exec python core/live_deal_monitor.py
    ;;
  bot)
    echo "🤖 Avvio Bot Telegram Interattivo..."
    exec python bot/telegram_bot_runner.py
    ;;
  broadcaster)
    echo "📢 Avvio Canale Telegram Broadcaster Automatico..."
    exec python bot/telegram_channel_broadcaster.py --interval "${BROADCAST_INTERVAL:-600}"
    ;;
  all)
    echo "🌟 Avvio Orchestrato di Tutti i 4 Servizi in Modalità All-in-One..."

    # Array per tenere traccia dei PID dei processi figli
    pids=()

    # Trap per terminazione pulita su SIGTERM / SIGINT
    cleanup() {
      echo ""
      echo "🛑 Segnale di arresto ricevuto. Terminazione pulita di tutti i processi..."
      for pid in "${pids[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
          kill -TERM "$pid" 2>/dev/null || true
        fi
      done
      wait
      echo "✅ Tutti i servizi arrestati correttamente."
      exit 0
    }
    trap cleanup SIGTERM SIGINT

    # 1. API Server & Web Frontend
    echo "▶️ [1/4] Avvio API Server..."
    python api/server.py &
    pids+=($!)

    # 2. Live Deal Monitor
    echo "▶️ [2/4] Avvio Live Deal Monitor..."
    python core/live_deal_monitor.py &
    pids+=($!)

    # 3. Telegram Interactive Bot (se il token è configurato)
    if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
      echo "▶️ [3/4] Avvio Bot Telegram Interattivo..."
      python bot/telegram_bot_runner.py &
      pids+=($!)
    else
      echo "⚠️ [3/4] TELEGRAM_BOT_TOKEN non impostato: Bot Interattivo in pausa."
    fi

    # 4. Telegram Channel Broadcaster (se token e canale sono configurati)
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHANNEL_ID" ]; then
      echo "▶️ [4/4] Avvio Telegram Channel Broadcaster..."
      python bot/telegram_channel_broadcaster.py --interval "${BROADCAST_INTERVAL:-600}" &
      pids+=($!)
    else
      echo "⚠️ [4/4] TELEGRAM_CHANNEL_ID non impostato: Channel Broadcaster in pausa."
    fi

    echo "========================================================"
    echo "✅ TUTTI I SERVIZI SONO ATTIVI E OPERATIVI H24!"
    echo "========================================================"

    # Attende i processi figli. Se uno crasha in modo critico, esce per consentire a Docker di riavviare il container
    wait -n "${pids[@]}"
    ;;
  *)
    exec "$@"
    ;;
esac
