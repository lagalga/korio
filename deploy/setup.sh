#!/bin/bash
# deploy/setup.sh — Setup inicial del VPS (ejecutar como root desde /root/korio)
# Uso: bash deploy/setup.sh

set -e
REPO_DIR=/root/korio
BRANCH=claude/nifty-booth-0c25a5

echo "=== Korio VPS Setup ==="

# 1. Asegurarse de estar en el directorio correcto
cd "$REPO_DIR"

# 2. Actualizar código
echo "[1/6] Actualizando código del repositorio..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

# 3. Python venv + dependencias
echo "[2/6] Configurando entorno Python..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# 4. Modelo spaCy (solo si no está instalado)
echo "[3/6] Verificando modelo spaCy..."
if ! .venv/bin/python -c "import spacy; spacy.load('es_core_news_lg')" 2>/dev/null; then
    .venv/bin/python -m spacy download es_core_news_lg
fi

# 5. Nginx
echo "[4/6] Configurando nginx..."
cp deploy/nginx/korio.es.conf    /etc/nginx/sites-available/korio.es
cp deploy/nginx/n8n.korio.es.conf /etc/nginx/sites-available/n8n.korio.es
ln -sf /etc/nginx/sites-available/korio.es       /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/n8n.korio.es   /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 6. Systemd para FastAPI
echo "[5/6] Instalando servicio systemd korio-api..."
cp deploy/korio-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable korio-api
systemctl restart korio-api

# 7. Docker (n8n)
echo "[6/6] Arrancando n8n con Docker Compose..."
docker compose up -d n8n

echo ""
echo "=== Setup completado ==="
echo "  FastAPI:  http://127.0.0.1:8000/health"
echo "  n8n:      http://127.0.0.1:5678"
echo "  nginx:    $(systemctl is-active nginx)"
echo ""
echo "Siguiente paso — SSL (después de apuntar DNS):"
echo "  certbot --nginx -d korio.es -d www.korio.es -d n8n.korio.es"
