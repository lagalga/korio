# Korio — Guía de despliegue en producción

> Setup completo desde cero en Hetzner **CPX32** (AMD EPYC-Genoa) · Frankfurt

---

## Requisitos previos

| Servicio | Plan | Coste | Notas |
|---|---|---|---|
| Hetzner VPS **CPX32** | Hourly/Monthly | **€17.53/mes max** (€0.0281/h) | Frankfurt · AMD EPYC-Genoa · 4 vCPU / 8 GB / 160 GB SSD |
| Supabase | Pro | $25/mes | Frankfurt (eu-central-1) — GDPR |
| Mistral AI | Pay-per-use | ~€0.002/query | `mistral-small-latest` |
| Dominio (opcional) | — | — | Para HTTPS en producción |

**Tiempo estimado:** 45–60 minutos para un setup limpio.

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
# Añadir alias en ~/.ssh/config
Host korio-vps
  HostName <IP_DEL_SERVIDOR>
  User root
  IdentityFile ~/.ssh/id_ed25519

# Conectar
ssh korio-vps
```

### 1.3 Setup inicial del servidor

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar dependencias base
apt install -y git curl wget python3 python3-pip python3-venv \
               build-essential libpq-dev

# Instalar Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Verificar
docker --version
```

---

## 2. Clonar repositorio y configurar entorno

```bash
# Clonar repo
git clone https://github.com/lagalga/korio.git
cd korio

# Crear entorno virtual Python
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Descargar modelo spaCy (necesario para Presidio)
python -m spacy download es_core_news_lg
```

---

## 3. Variables de entorno

```bash
cp .env.example .env
nano .env
```

Contenido de `.env`:

```env
# Supabase
SUPABASE_URL=https://<PROJECT_ID>.supabase.co
SUPABASE_ANON_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>

# Ollama (en este mismo VPS)
OLLAMA_HOST=http://localhost:11434

# Mistral API
MISTRAL_API_KEY=<tu_api_key>

# Gobernanza HITL
HITL_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-hitl
HITL_WEBHOOK_USER=<basic_auth_user>
HITL_WEBHOOK_PASS=<basic_auth_pass>
KORIO_BASE_URL=https://korio.es
KORIO_ADMIN_API_KEY=<random_token_para_endpoints_admin>
ESCALATION_REMINDER_DAYS=3,7,14
ESCALATION_TIMEOUT_DAYS=21

# Grafo de conocimiento (FalkorDB)
KORIO_GRAPH_ENABLED=1
FALKORDB_HOST=127.0.0.1
FALKORDB_PORT=6379
KORIO_GRAPH_NAME=korio

# n8n.korio.es (opcional, para crear workflows vía API REST)
N8N_KORIO_API_KEY=<n8n_api_key>
N8N_KORIO_BASE_URL=https://n8n.korio.es

# Postgres local (opcional, solo para dev)
POSTGRES_PASSWORD=korio
```

---

## 4. Levantar Ollama con Docker

```bash
# Arrancar servicios (solo Ollama para producción)
docker compose up -d ollama

# Esperar a que el healthcheck pase
docker compose ps

# Descargar modelos
docker exec korio-ollama ollama pull nomic-embed-text
docker exec korio-ollama ollama pull mistral:7b-instruct-q4_K_M

# Verificar modelos instalados
docker exec korio-ollama ollama list
```

> **Nota:** El modelo `nomic-embed-text` (~274MB) es el primero que hay que descargar. Es CRÍTICO para el funcionamiento del sistema (768 dims, nunca cambiar).

---

## 5. Schema de Supabase

En [supabase.com](https://supabase.com), ir a **SQL Editor** y ejecutar las migraciones en orden:

```bash
# Orden de ejecución (9 migraciones):
# 1. supabase/migrations/001_initial_schema.sql     — schema + RLS + seed
# 2. supabase/migrations/002_search_function.sql    — search_embeddings(vector(768))
# 3. supabase/migrations/003_fix_vector_dims.sql    — 384 → 768 dims
# 4. supabase/migrations/004_conflict_reviews.sql   — gobernanza activa
# 5. supabase/migrations/005_search_with_disputed.sql
# 6. supabase/migrations/006_tenant_admin_email.sql
# 7. supabase/migrations/007_waitlist.sql           — landing
# 8. supabase/migrations/008_escalation_tracking.sql — cron HITL
# 9. supabase/migrations/009_source_metadata.sql    — canal de origen en ingesta
#
# IMPORTANTE tras aplicar cualquier migración:
#   NOTIFY pgrst, 'reload schema';
# (PostgREST cachea el schema; sin esto las nuevas columnas no son visibles)
```

### Verificar que el schema está correcto

```sql
-- Debe devolver 'vector(768)'
SELECT pg_typeof(embedding) FROM embeddings LIMIT 1;

-- Debe listar las tablas principales
SELECT tablename FROM pg_tables WHERE schemaname = 'public'
ORDER BY tablename;
-- Resultado esperado: audit_log, documents, embeddings, spaces, tenants, user_spaces, users
```

### Habilitar RLS en Supabase

Las políticas RLS se crean en `001_initial_schema.sql`. Verificar:

```sql
-- Debe devolver true para todas las tablas
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public';
```

---

## 6. Levantar la API

### Modo desarrollo (con hot-reload)

```bash
source .venv/bin/activate
python -m uvicorn api.server:app --reload --host 0.0.0.0 --port 8000
```

### Modo producción (proceso systemd)

Crear `/etc/systemd/system/korio-api.service`:

```ini
[Unit]
Description=Korio API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/korio
Environment="PATH=/root/korio/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/root/korio/.venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 2
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
```

---

## 7. Verificar el sistema

### Health check

```bash
curl http://localhost:8000/health
# Respuesta esperada:
# {"status": "ok", "services": {"supabase": "ok", "embedder": "ok", "llm": "ok (mistral/mistral-small-latest)"}}
```

### Test de ingesta

```bash
source .venv/bin/activate
python src/ingest.py data-synthetic/delos_politica_rrhh.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001
# Esperado: "✓ Ingestados X chunks"
```

### Test de búsqueda

```bash
python src/search.py "¿Cuántos días de vacaciones tienen los empleados?" \
  --user-id a2000000-0000-0000-0000-000000000001 \
  --tenant-id a0000000-0000-0000-0000-000000000001
```

### Tests automáticos

```bash
source .venv/bin/activate
python -m pytest tests/ -v
# Esperado: 20/20 tests ✅ (~20s)
```

---

## 8. Ingestar datos sintéticos de prueba

Para tener el sistema completo con ambos tenants:

```bash
source .venv/bin/activate

# Tenant: Clínica Delos
python src/ingest.py data-synthetic/delos_politica_rrhh.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001

python src/ingest.py data-synthetic/delos_protocolo_admision.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000002

python src/ingest.py data-synthetic/delos_acta_junta_directiva.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000003

# Tenant: Despacho García
python src/ingest.py data-synthetic/garcia_caso_laboral.md \
  --tenant-id b0000000-0000-0000-0000-000000000002 \
  --space-id b1000000-0000-0000-0000-000000000001

python src/ingest.py data-synthetic/garcia_dictamen_fiscal.md \
  --tenant-id b0000000-0000-0000-0000-000000000002 \
  --space-id b1000000-0000-0000-0000-000000000002

python src/ingest.py data-synthetic/garcia_protocolo_clientes.md \
  --tenant-id b0000000-0000-0000-0000-000000000002 \
  --space-id b1000000-0000-0000-0000-000000000001
```

---

## 9. Firewall (opcional para producción)

```bash
# Instalar ufw
apt install -y ufw

# Reglas básicas
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 8000/tcp    # API Korio
# ufw allow 443/tcp   # HTTPS si tienes dominio + nginx

ufw enable
ufw status
```

---

## Comandos de mantenimiento

```bash
# Ver logs de la API
journalctl -u korio-api -f

# Reiniciar API
systemctl restart korio-api

# Ver logs de Ollama
docker logs korio-ollama --tail 50

# Verificar modelos Ollama
docker exec korio-ollama ollama list

# Ver espacio en disco
df -h

# Ver uso de RAM
free -h
```

---

## Troubleshooting

### Error: "vector dimension mismatch"
```
El schema tiene vector(384) pero el modelo genera 768 dims.
Solución: ejecutar supabase/migrations/003_fix_vector_dims.sql
```

### Error: "Ollama connection refused"
```bash
# Verificar que el contenedor está corriendo
docker ps | grep ollama
# Si no está: docker compose up -d ollama
```

### Error: "Supabase connection failed"
```bash
# Verificar variables de entorno
grep SUPABASE .env
# Verificar conectividad
curl https://<PROJECT_ID>.supabase.co/rest/v1/tenants \
  -H "apikey: <anon_key>"
```

### Tests fallando por RLS
```
Verificar que en conftest.py los UUIDs de tenants/users/spaces
coinciden con los datos seed de Supabase.
Los datos seed se crean en 001_initial_schema.sql.
```

---

*Actualizado: junio 2026*
