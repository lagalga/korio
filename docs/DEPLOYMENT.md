# Korio — Guía de despliegue en producción

> Setup completo desde cero en Hetzner **CPX32** (AMD EPYC-Genoa) · Frankfurt
> Estado: v0.3.16 · 20 migraciones · FalkorDB + n8n + Ollama + Jaeger dockerizados

---

## Requisitos previos

| Servicio | Plan | Coste | Notas |
|---|---|---|---|
| Hetzner VPS **CPX32** | Hourly/Monthly | **€17.53/mes max** (€0.0281/h) | Frankfurt · AMD EPYC-Genoa · 4 vCPU / 8 GB / 160 GB SSD |
| Supabase | Pro | $25/mes | Frankfurt (eu-central-1) — GDPR |
| Mistral AI | Pay-per-use | ~€0.002/query | `mistral-small-latest` |
| Dominio | — | — | Requerido para TLS + nginx + Slack webhooks |

**Tiempo estimado:** 60–90 minutos para un setup limpio.

---

## 1. Configurar Hetzner VPS

### 1.1 Crear servidor

En [console.hetzner.com](https://console.hetzner.com):
- **Tipo:** **CPX32** (AMD EPYC-Genoa, 4 vCPU, 8 GB RAM, 160 GB SSD)
- **Imagen:** Ubuntu 24.04 LTS
- **Ubicación:** Falkenstein o Nuremberg (EU — GDPR)
- **SSH Key:** añadir tu clave pública
- **Nombre:** `korio-vps`

### 1.2 Acceso SSH

```bash
# ~/.ssh/config
Host korio-vps
  HostName <IP_DEL_SERVIDOR>
  User root
  IdentityFile ~/.ssh/id_ed25519

ssh korio-vps
```

### 1.3 Setup inicial del servidor

```bash
apt update && apt upgrade -y
apt install -y git curl wget python3 python3-pip python3-venv \
               build-essential libpq-dev nginx certbot python3-certbot-nginx

# Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
docker --version
```

---

## 2. Clonar repositorio y configurar entorno

```bash
cd /root
git clone https://github.com/lagalga/korio.git
cd korio

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python -m spacy download es_core_news_lg
```

---

## 3. Variables de entorno

```bash
cp .env.example .env
nano .env
```

`.env` completo (v0.3.16):

```env
# ─── Supabase ─────────────────────────────────────────────
SUPABASE_URL=https://<PROJECT_ID>.supabase.co
SUPABASE_ANON_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>

# ─── Ollama (mismo VPS) ───────────────────────────────────
OLLAMA_HOST=http://localhost:11434

# ─── LLM (Mistral cloud + Ollama fallback) ────────────────
MISTRAL_API_KEY=<tu_api_key>
KORIO_REDACT_MISTRAL=1                       # PII whitelist pre-envío (Presidio)

# ─── Búsqueda ─────────────────────────────────────────────
KORIO_SEARCH_THRESHOLD=0.35                  # Cosine min (sesión 10)
KORIO_QUERY_TIME_CONFLICT_ENABLED=1
KORIO_QUERY_TIME_CONFLICT_THRESHOLD=0.80     # Caso extremo E4
KORIO_DISPUTED_BANNER_MIN_SIM=0.6            # UI banner solo si supera (sesión 12)

# ─── Gobernanza HITL ──────────────────────────────────────
HITL_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-hitl
HITL_WEBHOOK_USER=<basic_auth_user>          # Webhook protegido Basic Auth
HITL_WEBHOOK_PASS=<basic_auth_pass>
KORIO_BASE_URL=https://korio.es
KORIO_ADMIN_API_KEY=<random_token>           # Auth para endpoints /admin/*
KORIO_ADMIN_TENANT_ID=<uuid>                 # Defensa en profundidad DELETE /document
ESCALATION_REMINDER_DAYS=3,7,14
ESCALATION_TIMEOUT_DAYS=21

# ─── Grafo de conocimiento (FalkorDB) ─────────────────────
KORIO_GRAPH_ENABLED=1
FALKORDB_HOST=127.0.0.1
FALKORDB_PORT=6379
KORIO_GRAPH_NAME=korio

# ─── Pipeline event bus ───────────────────────────────────
KORIO_EVENT_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-events

# ─── Seguridad / Hardening (sesión 13a + 16b) ─────────────
KORIO_ENV=prod
KORIO_EXTRA_CORS_ORIGINS=                    # opcional, coma-separado
SLACK_SIGNING_SECRET=<de api.slack.com>      # Verificación firma /admin/errors/slack-action

# ─── n8n.korio.es (gestión de workflows vía API REST) ─────
N8N_KORIO_API_KEY=<api_key>
N8N_KORIO_BASE_URL=https://n8n.korio.es

# ─── Observabilidad (sesión 18) ───────────────────────────
# LangSmith — trazas RAG semánticas. Cuenta UE: el endpoint EU es OBLIGATORIO
# (el US devuelve 403 en el ingest). Usar Service Key (lsv2_sk_).
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<lsv2_sk_...>
LANGCHAIN_PROJECT=korio
LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com
# OTel → Jaeger (trazas HTTP self-hosted). No-op si KORIO_OTEL_ENABLED != 1.
KORIO_OTEL_ENABLED=1
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=korio-api

# ─── Detector de conflictos (sesión 19) ──────────────────
KORIO_CONFLICT_SEMANTIC_VALIDATION=1             # Validación semántica LLM antes de declarar conflict
```

---

## 4. Docker compose: Ollama + FalkorDB + n8n

Verifica `docker-compose.yml` (en el repo):
- **`korio-ollama`** → modelos `nomic-embed-text` (768d) + `mistral:7b-instruct-q4_K_M` (fallback)
- **`korio-falkordb`** → Redis 8.6.3 con módulo grafo, **AOF persistence** (`appendonly yes appendfsync everysec`)
- **`korio-n8n`** → n8n v1.x
- **`korio-jaeger`** → Jaeger all-in-one (OTLP). UI `127.0.0.1:16686` (vía túnel SSH), receptor OTLP `127.0.0.1:4317`. Solo si usas OTel.

Si el `docker-compose.yml` del repo no incluye Jaeger, añade:

```yaml
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: korio-jaeger
    environment:
      - COLLECTOR_OTLP_ENABLED=true
    ports:
      - "127.0.0.1:16686:16686"   # UI (solo localhost, túnel SSH)
      - "127.0.0.1:4317:4317"     # OTLP gRPC
    restart: unless-stopped
```

```bash
docker compose up -d
docker compose ps     # los 3 contenedores en running

# Descargar modelos Ollama (la primera vez)
docker exec korio-ollama ollama pull nomic-embed-text
docker exec korio-ollama ollama pull mistral:7b-instruct-q4_K_M
docker exec korio-ollama ollama list

# Verificar FalkorDB
docker exec korio-falkordb redis-cli PING

# Verificar n8n
curl -sI http://localhost:5678 | head -1
```

> El modelo `nomic-embed-text` (~274MB · 768 dims · INMUTABLE) es crítico. Cambiarlo requiere re-ingestar TODA la BD.

---

## 5. Schema de Supabase

20 migraciones en `supabase/migrations/`. Ejecutar en orden desde el SQL Editor de [supabase.com](https://supabase.com):

| # | Fichero | Propósito |
|---|---|---|
| 001 | `001_initial_schema.sql` | Schema base + RLS + seed |
| 002 | `002_search_function.sql` | RPC `search_embeddings(vector(768), …)` |
| 003 | `003_fix_vector_dims.sql` | Corrección 384 → 768 |
| 004 | `004_conflict_reviews.sql` | Gobernanza activa |
| 005 | `005_search_with_disputed.sql` | Incluye chunks `disputed` |
| 006 | `006_tenant_admin_email.sql` | Email HITL configurable por tenant |
| 007 | `007_waitlist.sql` | Landing teaser |
| 008 | `008_escalation_tracking.sql` | Cron HITL escalada |
| 009 | `009_source_metadata.sql` | `documents.source_metadata` JSONB |
| 010 | `010_mcp_api_keys.sql` | API keys MCP server (SHA-256) |
| 011 | `011_pipeline_events_atomic_ingest.sql` | Bus eventos + RPC ACID |
| 012 | `012_silent_conflicts_query_time.sql` | Caso extremo E4 |
| 013 | `013_inconclusive_state_and_policies.sql` | Estado + policies reutilizables |
| 014 | `014_n8n_errors.sql` | Captura errores workflows |
| 015 | `015_mcp_api_keys_rls.sql` | RLS sobre `mcp_api_keys` |
| 016 | `016_silent_conflicts_same_space.sql` | Fix false positives cross-space |
| 017 | `017_admin_space.sql` | Space `Administración` |
| 018 | `018_slack_service_users.sql` | Service users multi-canal Slack |
| 019 | `019_drop_ivfflat_index.sql` | DROP `idx_embeddings_vector` (probes=1 bug) |
| 020 | `020_inconclusive_in_search.sql` | RPC incluye `inconclusive` con badge ⚠️ |

```sql
-- IMPORTANTE tras cada migración:
NOTIFY pgrst, 'reload schema';
```

### Verificar schema

```sql
-- Vector dim correcta
SELECT pg_typeof(embedding) FROM embeddings LIMIT 1;   -- vector(768)

-- Tablas esperadas
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;
-- audit_log, conflict_reviews, documents, embeddings, graph_sync_queue,
-- mcp_api_keys, n8n_errors, pipeline_events, policies, spaces, tenants,
-- user_spaces, users, waitlist

-- RLS habilitado
SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
```

---

## 6. nginx + TLS

`/etc/nginx/sites-available/korio.es`:

```nginx
server {
    listen 80;
    server_name korio.es;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name korio.es;

    ssl_certificate     /etc/letsencrypt/live/korio.es/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/korio.es/privkey.pem;

    # Buffering OFF para SSE del MCP server
    proxy_buffering off;
    proxy_read_timeout 86400;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Idem para n8n.korio.es → http://127.0.0.1:5678
```

```bash
ln -s /etc/nginx/sites-available/korio.es /etc/nginx/sites-enabled/
certbot --nginx -d korio.es -d n8n.korio.es
systemctl reload nginx
```

---

## 7. FastAPI como systemd service

`/etc/systemd/system/korio-api.service`:

```ini
[Unit]
Description=Korio API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/korio
EnvironmentFile=/root/korio/.env
Environment="PATH=/root/korio/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
# IMPORTANTE: --workers 1 mientras las sesiones SSE de MCP sean in-memory por proceso
ExecStart=/root/korio/.venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable korio-api
systemctl start korio-api
systemctl status korio-api
journalctl -u korio-api -f
```

---

## 8. Verificación

### Health check

```bash
curl https://korio.es/health
# {"status":"ok","services":{"supabase":"ok","embedder":"ok","llm":"ok (mistral_api/...)"}}
```

### Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
# 31/31 verdes (~30s)
```

### Endpoints clave

| URL | Propósito |
|---|---|
| `https://korio.es/` | Landing teaser |
| `https://korio.es/ui` | Chat web |
| `https://korio.es/ui/graph.html` | Visualización grafo |
| `https://korio.es/ui/admin-errors.html` | Panel admin errores n8n |
| `https://korio.es/docs` | Swagger (botón Authorize) |
| `https://korio.es/mcp/sse` | MCP server (Phase 7.3) |
| `https://korio.es/legal/privacy.html` | Privacy Policy GDPR |
| `https://n8n.korio.es` | Editor n8n (8 workflows) |

---

## 9. Operaciones recurrentes

### Crear MCP API key

```bash
ssh korio-vps
cd /root/korio && source .venv/bin/activate
python scripts/mcp_create_key.py create \
  --user-id <uuid> --tenant-id <uuid> --name "Claude Desktop"
# Plaintext mostrado UNA sola vez. Prefijo korio_
```

### Disparar cron HITL manualmente

```bash
curl -X POST https://korio.es/escalate-reviews \
  -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY"
```

### Listar / marcar reviewed errores n8n

UI: `https://korio.es/ui/admin-errors.html` (pega admin key).
CLI:
```bash
curl -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY" \
  "https://korio.es/admin/errors?only_unreviewed=true&limit=20"
curl -X POST -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY" \
  "https://korio.es/admin/errors/<id>/review"
```

### Snapshot / restore demo

```bash
python scripts/demo_snapshot.py list
python scripts/demo_snapshot.py save --name pre_demo_v039
python scripts/demo_snapshot.py restore --name pre_demo_v038 -y
systemctl restart korio-api
```

### Borrar documento (admin)

```bash
curl -X DELETE https://korio.es/document/<doc_id> \
  -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY"
# Postgres cascade + FalkorDB cleanup
```

---

## 10. Firewall

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
# Puertos internos (8000 FastAPI, 5678 n8n, 6379 FalkorDB, 11434 Ollama) NO se exponen
ufw enable
ufw status
```

---

## 11. Configuración Slack (post-deploy)

### Slack app "Korio-Delos"

1. https://api.slack.com/apps → app de Korio.
2. **OAuth & Permissions** → Bot Token Scopes:
   `chat:write, commands, files:read, reactions:write, app_mentions:read`
3. **Slash Commands** → `/korio` con Request URL `https://n8n.korio.es/webhook/korio-slack`
4. **Event Subscriptions** → ON · Request URL `https://n8n.korio.es/webhook/korio-slack-events` · Bot events: `file_shared`
5. **Interactivity & Shortcuts** → ON · Request URL `https://korio.es/admin/errors/slack-action`
6. **Basic Information** → copiar `Signing Secret` → añadir a `.env` como `SLACK_SIGNING_SECRET` + `systemctl restart korio-api`
7. **Install / Reinstall to Workspace**
8. `/invite @Korio-Delos` en canales relevantes

---

## Comandos de mantenimiento

```bash
# Logs en vivo
journalctl -u korio-api -f
docker logs korio-ollama --tail 50
docker logs korio-falkordb --tail 50
docker logs korio-n8n --tail 50

# Reiniciar API
systemctl restart korio-api

# Estado contenedores
docker ps --format '{{.Names}}\t{{.Status}}'

# Espacio disco / RAM
df -h
free -h
docker system df    # uso de Docker
```

---

## Troubleshooting

### `vector dimension mismatch`
Schema con `vector(384)` pero el modelo genera 768. Ejecutar migración `003_fix_vector_dims.sql`.

### `Ollama connection refused`
```bash
docker ps | grep ollama
docker compose up -d ollama
```

### `Supabase connection failed`
Verificar `.env` + `curl https://<PROJECT>.supabase.co/rest/v1/tenants -H "apikey: $ANON"`.

### RPC `search_embeddings` devuelve 0 con datos en BD
Sesión 13b — el índice `ivfflat lists=100` con `probes=1` y <100 chunks dispersos saltaba matches. Migración 019 dropea el índice. Reintroducir solo con >1000 chunks (HNSW preferido).

### MCP SSE rompe con `Unexpected message http.response.start`
`BaseHTTPMiddleware` bufferea el stream. Usar `MCPAuthASGI` puro (ya implementado).

### `mcp-remote` cliente alucina respuestas sin llamar al tool
Bug timing en `mcp-remote@0.1.38`. Upgrade a `@latest` en `claude_desktop_config.json`.

### n8n API PUT workflow devuelve 400 "additional properties"
La API rechaza campos como `binaryMode`, `timeSavedMode`, `availableInMCP`. Filtrar `settings` a whitelist: `executionOrder, saveDataErrorExecution, saveDataSuccessExecution, saveManualExecutions, saveExecutionProgress, executionTimeout, errorWorkflow, timezone, callerPolicy, callerIds`.

### n8n API activate devuelve 400 "Cannot activate an archived workflow"
Llamar primero `POST /workflows/{id}/unarchive`.

---

*Actualizado: 29 junio 2026 · v0.3.16 · sesión 19. 20 migraciones · 8 workflows · observabilidad en producción.*
