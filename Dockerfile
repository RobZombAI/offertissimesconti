# ==============================================================================
# OFFERTISSIMESCONTI - Dockerfile di Produzione Enterprise
# Immagine snella, sicura e multi-servizio (API, Deal Monitor, Telegram Bot, Broadcaster)
# ==============================================================================

FROM python:3.13-slim

# Evita buffering dell'output Python e generazione file bytecode non necessari
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Installa pacchetti di sistema minimi per SSL e salute del container
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia l'intera struttura del progetto
COPY api/ ./api/
COPY bot/ ./bot/
COPY core/ ./core/
COPY data/ ./data/
COPY web/ ./web/
COPY scripts/ ./scripts/
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Crea utente di sistema non-root per massima sicurezza
RUN chmod +x /app/docker-entrypoint.sh && \
    useradd -u 1001 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck HTTP per monitorare la salute dell'API server
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/stats || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["all"]
