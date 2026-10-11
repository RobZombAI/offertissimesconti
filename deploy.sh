#!/usr/bin/env bash
# ==============================================================================
# OFFERTISSIMESCONTI - One-Click Production Deploy Script
# Esegui questo script sul server per aggiornare all'ultima versione di master
# ==============================================================================
set -e

echo "🚀 [1/3] Scaricamento aggiornamenti da Git (master)..."
git pull origin master

echo "📦 [2/3] Ricompilazione e riavvio container Docker..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d --build
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d --build
else
    echo "⚠️ Docker non rilevato. Riavvio manuale dei processi Python..."
    # Fallback se non si usa Docker
    pkill -f "api/server.py" || true
    pkill -f "live_deal_monitor.py" || true
    pkill -f "telegram_bot_runner.py" || true
    pkill -f "telegram_channel_broadcaster.py" || true
    nohup python3 api/server.py > /tmp/api.log 2>&1 &
    nohup python3 core/live_deal_monitor.py > /tmp/monitor.log 2>&1 &
    nohup python3 bot/telegram_bot_runner.py > /tmp/bot.log 2>&1 &
    nohup python3 bot/telegram_channel_broadcaster.py --interval 600 > /tmp/broadcaster.log 2>&1 &
fi

echo "✨ [3/3] Verifica stato del server..."
sleep 3
if command -v curl &> /dev/null; then
    curl -s http://localhost:8000/api/stats || true
    echo ""
fi

echo "=========================================================="
echo "🎉 DEPLOY DI PRODUZIONE COMPLETATO CON SUCCESSO!"
echo "=========================================================="
