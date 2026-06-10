# Korio — CLAUDE.md

## Proyecto

**Korio** (nombre comercial) / **Company Brain** (técnico) — SaaS multi-tenant de RAG para pymes españolas. Permite ingestar documentos internos y consultarlos en lenguaje natural, con control de acceso por departamento (RLS) y multi-tenancy real.

**TFM:** Máster IA Business & Innovation — Nuclio Digital School  
**Demo funcional:** 2 julio 2026  
**Defensa TFM:** 9 julio 2026  
**Repo:** https://github.com/lagalga/korio  

---

## Estado actual (10 junio 2026 · tarde · sesión 3)

### ✅ Completado — Phases 1–7.2 CERRADAS

**Phases 1–4** — pipeline ingesta, RAG vectorial, multi-tenancy con RLS, docs técnicos, chat UI con upload, benchmark script.

**Phase 5** — producción en korio.es, gobernanza activa (auto-resolución + HITL email), landing teaser.

**Phase 6** — cron de escalada HITL (recordatorios 3/7/14 días + auto-cierre a 21 días). Workflow n8n Schedule Trigger diario 09:00 Madrid. Migración 008.

**Phase 7.1** — grafo de conocimiento con FalkorDB vivo, sync en tiempo real, 3 puntos de acceso desde la UI. Hito TFM: la query "¿Cuántas horas semanales mínimas?" que el RAG vectorial puro no encontraba ahora responde "más de 35 horas/semana" en ~1s vía grafo. Banner ⚠️ del chat con link al grafo.

**Phase 7.2** — ingesta automática multi-canal en producción:
- **Migración 009**: `documents.source_metadata` (JSONB) + índice parcial por `via`. Registra el canal de origen.
- **`ingest_document()`** acepta `source_metadata: Optional[dict]` y lo persiste; `/upload` lo acepta como Form field JSON string.
- **`DELETE /document/{id}`** (admin) — borra Postgres en cascada + limpia FalkorDB. Auth con `APIKeyHeader` X-Korio-Admin-Key (botón Authorize visible en Swagger).
- **Fix crítico de gobernanza**: webhook HITL ahora protegido con Basic Auth (`HITL_USER_REDACTED` / `HITL_PASS_REDACTED`); `conflict_detector.py` y `escalation.py` parcheados para enviar credenciales via `HITL_WEBHOOK_USER` + `HITL_WEBHOOK_PASS` del `.env`.
- **3 workflows nuevos** en `n8n.korio.es`:
  - **Gmail → /upload (Delos RRHH)**: vigila label `korio/ingesta` en `contacto@lagalga.es` cada 5 min, ingiere adjuntos PDF/DOCX, marca leído + aplica label `korio/procesado`.
  - **Drive → /upload (Delos RRHH)**: vigila carpeta `Clínica Delos / input` (`1rlBEmkqLHvidWEPv64LaMpzBh9bMDGF4`) cada 5 min.
  - **Slack /korio → /search (Delos admin)**: slash command → ACK ephemeral → POST /search → reply en thread con respuesta + fuentes con %relevancia + link a korio.es.
- **UI polish**: filenames de fuentes ya no se truncan; eliminado marcador `[grafo]` confuso de las respuestas.
- **Documento de diseño** `docs/MULTI-TENANT-INGESTION.md` — Phase 8 post-TFM (OAuth multi-tenant, vault de tokens, ingestion_rules, onboarding UX). Sirve como capítulo de la memoria TFM "Arquitectura objetivo SaaS post-defensa".

### 🔲 Pendiente antes del 2 julio (demo) + 9 julio (defensa)

- **QA end-to-end**: 10+ queries en ambos tenants
- **Benchmark formal** de latencias (`scripts/benchmark.py`) — métricas p50/p95
- **Vídeo demo** del ciclo completo (Gmail llega → 30s después consultable → conflicto → email HITL → grafo)
- **Slide deck** (10–15 slides) + ensayo presentación
- **Memoria TFM** — escritura completa con capítulos Phase 8 (`MULTI-TENANT-INGESTION.md`) y guardrails (`CHAT-PIPELINE-GUARDRAILS.md`)
- **Memoria de chat** (sesión 4 en curso): query reformulation con LLM para multi-turn
- **Fix CONTRADICTS falsos positivos**: validar par claim_a/claim_b antes de crear arista (mejora calidad demo grafo)

### 🔲 Phase 7.3 — MCP Server (post-demo, opcional para defensa)

Exponer Korio como servidor MCP para Claude Desktop, ChatGPT, n8n:
- `search_knowledge_base(query, user_id, tenant_id)`
- `ingest_document(file_url, tenant_id, space_id)`
- `list_pending_conflicts(tenant_id)`
- `list_spaces(user_id)`
- Stack probable: FastAPI MCP endpoint (mantiene Python)

---

## Stack tecnológico

| Componente | Tecnología | Notas |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama en VPS | **768 dims — FIJO, no cambiar nunca** |
| Vector store | pgvector en Supabase (Frankfurt) | RLS nativo, GDPR |
| Graph store | FalkorDB (Redis 8.6.3 + módulo grafo) | Cypher, multi-tenant por propiedad |
| LLM generación | Mistral API `mistral-small-latest` | ~3s latencia |
| LLM extracción | Mistral API `mistral-small-latest` (temp 0.0) | Structured JSON |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` en VPS | ~25s CPU, offline |
| Backend API | FastAPI + Uvicorn, Python 3.12 | Swagger en `/docs` con Authorize |
| PII detection | Presidio + spaCy `es_core_news_lg` | Antes de ingestar |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Conversión docs | MarkItDown | PDF/DOCX/XLSX → Markdown |
| Automatización | n8n v1.x (Docker en VPS) | **5 workflows**: HITL + Cron + Gmail + Drive + Slack |
| Servidor | Hetzner CX32, Frankfurt, 4vCPU/8GB | `ssh korio-vps` |
| Base de datos | Supabase Pro, Frankfurt | `pkurvkdmoulfqnngjsjr.supabase.co` |

---

## Infraestructura

```
SSH:        ssh korio-vps   (alias en ~/.ssh/config → 167.233.72.42)
Supabase:   https://pkurvkdmoulfqnngjsjr.supabase.co
Ollama VPS: http://167.233.72.42:11434
Docker:     docker exec korio-ollama ollama list

URLs públicas:
  https://korio.es              → Landing teaser
  https://korio.es/ui           → App de chat
  https://korio.es/ui/graph.html → Visualización del grafo de conocimiento
  https://korio.es/docs         → Swagger UI (con botón Authorize para endpoints admin)
  https://n8n.korio.es          → n8n editor (5 workflows: HITL + Cron + Gmail + Drive + Slack)
```

### VPS — comandos útiles
```bash
ssh korio-vps
docker ps                                       # ver contenedores
docker exec korio-ollama ollama list            # modelos cargados
docker exec korio-falkordb redis-cli PING       # ping grafo
docker logs korio-ollama --tail 50              # logs Ollama
docker logs korio-n8n --tail 50                 # logs n8n
docker logs korio-falkordb --tail 50            # logs FalkorDB

systemctl status korio-api                  # FastAPI service
systemctl restart korio-api                 # reiniciar FastAPI
journalctl -u korio-api -f                  # logs FastAPI en tiempo real
curl https://korio.es/health                # health check producción

# Disparar cron escalada manualmente (el daily corre a las 09:00 Madrid)
curl -X POST https://korio.es/escalate-reviews \
  -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY" \
  -d '{}'

# Inspeccionar el grafo desde el host
.venv/bin/python -c "
from src.graph_client import get_graph_client
gc = get_graph_client()
print(gc.get_contradictions(tenant_id='a0000000-0000-0000-0000-000000000001',
                            allowed_space_ids=['a1000000-0000-0000-0000-000000000001']))
"
```

### Variables de entorno clave (en `/root/korio/.env`)

```
# Embeddings + Vector store
SUPABASE_URL=https://pkurvkdmoulfqnngjsjr.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_ANON_KEY=...

# LLM
MISTRAL_API_KEY=...

# Gobernanza
HITL_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-hitl
HITL_WEBHOOK_USER=HITL_USER_REDACTED                  # basic auth del webhook HITL
HITL_WEBHOOK_PASS=HITL_PASS_REDACTED
KORIO_BASE_URL=https://korio.es
KORIO_ADMIN_API_KEY=...                  # para /escalate-reviews y DELETE /document/{id}
ESCALATION_REMINDER_DAYS=3,7,14
ESCALATION_TIMEOUT_DAYS=21

# Grafo de conocimiento
KORIO_GRAPH_ENABLED=1
FALKORDB_HOST=127.0.0.1
FALKORDB_PORT=6379
KORIO_GRAPH_NAME=korio

# n8n (para que Claude pueda crear workflows directos sin pasar por lagalga)
N8N_KORIO_API_KEY=...
N8N_KORIO_BASE_URL=https://n8n.korio.es
```

---

## Estructura del proyecto

```
korio/
├── CLAUDE.md                    # Este fichero (memoria del proyecto)
├── README.md
├── .env                         # Credenciales reales (no en git)
├── .env.example                 # Template
├── docker-compose.yml           # Ollama + n8n en VPS
├── requirements.txt
│
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql   # Schema + RLS + seed data
│       ├── 002_search_function.sql  # search_embeddings(vector(768))
│       ├── 003_fix_vector_dims.sql  # Corrección 384→768 dims
│       ├── 004_conflict_reviews.sql # Gobernanza activa
│       ├── 005_search_with_disputed.sql
│       ├── 006_tenant_admin_email.sql
│       ├── 007_waitlist.sql
│       ├── 008_escalation_tracking.sql
│       └── 009_source_metadata.sql  # JSONB con canal de origen (Gmail, Drive, manual…)
│
├── src/
│   ├── ingest.py             # Pipeline ingesta: doc → chunks → pgvector + grafo
│   ├── search.py             # RAG híbrido vector + grafo
│   ├── embedder.py           # Wrapper Ollama nomic-embed-text, 768 dims
│   ├── chunker.py            # RecursiveTextSplitter
│   ├── preprocessor.py       # MarkItDown + Presidio
│   ├── llm_client.py         # Mistral API + Ollama fallback
│   ├── db.py                 # Supabase client, RLS early binding, audit log
│   ├── conflict_detector.py  # Gobernanza activa al nivel de chunk
│   ├── escalation.py         # Cron HITL: recordatorios + auto-timeout
│   ├── graph_client.py       # Wrapper FalkorDB con RLS multi-tenant
│   ├── entity_extractor.py   # Mistral structured JSON → entidades + claims
│   └── utils.py
│
├── api/
│   ├── __init__.py
│   └── server.py        # FastAPI: /search, /ingest, /upload, /review,
│                        #          /escalate-reviews, /waitlist,
│                        #          /graph/contradictions, /graph/entity/{name},
│                        #          /graph/subgraph, /health,
│                        #          DELETE /document/{id} (admin)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # Fixtures: UUIDs seed (tenants, users, spaces)
│   ├── test_rls.py      # 10 tests aislamiento (10/10 ✅)
│   └── test_search.py   # 10 tests RAG (10/10 ✅)
│
├── data-synthetic/      # Documentos de prueba (en .gitignore)
│   ├── delos_politica_rrhh.md
│   ├── delos_protocolo_admision.md
│   ├── delos_acta_junta_directiva.md
│   ├── garcia_caso_laboral.md
│   ├── garcia_dictamen_fiscal.md
│   └── garcia_protocolo_clientes.md
│
├── ui/                  # Chat UI web + visualización grafo
│   ├── index.html
│   ├── graph.html       # vis-network 9.1.9 + panel contradicciones
│   ├── css/styles.css
│   └── js/main.js
│
├── landing/             # Landing teaser estático en /
│
├── scripts/
│   ├── benchmark.py     # Medición latencias p50/p95 por escenario
│   └── graph_backfill.py # Pobló 233 claims sobre 9 docs en 107s
│
└── docs/
    ├── ARCHITECTURE.md           # Diagrama del sistema, modelo de datos, RLS
    ├── DEPLOYMENT.md             # Setup en Hetzner desde cero
    ├── ROADMAP.md                # Fases pasadas y futuras
    ├── SESSION-STARTER.md        # Prompt de arranque para nueva sesión Claude
    └── MULTI-TENANT-INGESTION.md # Diseño Phase 8: OAuth multi-tenant SaaS
```

---

## Entorno de desarrollo

```bash
# Activar venv (siempre antes de ejecutar)
cd "/Users/berto/Claude Code/korio"
source .venv/bin/activate

# Tests
python -m pytest tests/test_rls.py -v        # RLS (10 tests, ~1s)
python -m pytest tests/test_search.py -v     # RAG (10 tests, ~20s)
python -m pytest tests/ -v                   # Todos (20/20)

# Ingesta
python src/ingest.py data-synthetic/FILE.md \
  --tenant-id <uuid> --space-id <uuid>

# Búsqueda
python src/search.py "¿pregunta?" --user-id <uuid> --tenant-id <uuid>

# Servidor FastAPI (arrancar desde el directorio del proyecto/worktree)
python -m uvicorn api.server:app --reload --port 8000
# Swagger: http://localhost:8000/docs
# UI:      http://localhost:8000/ui

# UI (servidor estático alternativo, sin FastAPI)
python -m http.server 3000 --directory ui

# Benchmark de latencias (requiere servidor en :8000)
python scripts/benchmark.py                     # 5 iter por escenario
python scripts/benchmark.py -n 10 -o out.json  # 10 iter + JSON
```

---

## Datos de prueba (Supabase — producción real)

### Tenant 1: Clínica Delos
```
tenant_id:  a0000000-0000-0000-0000-000000000001

Spaces:
  RRHH:    a1000000-0000-0000-0000-000000000001
  Médico:  a1000000-0000-0000-0000-000000000002
  Legal:   a1000000-0000-0000-0000-000000000003

Users:
  admin:   a1000000-0000-0000-0000-000000000001  (RRHH + Médico + Legal)
  doctor:  a2000000-0000-0000-0000-000000000001  (RRHH + Médico)
  staff:   a3000000-0000-0000-0000-000000000001  (solo RRHH)
```

### Tenant 2: Despacho Legal García
```
tenant_id:  b0000000-0000-0000-0000-000000000002

Spaces:
  Casos:   b1000000-0000-0000-0000-000000000001
  Fiscal:  b1000000-0000-0000-0000-000000000002

Users:
  admin:   b1000000-0000-0000-0000-000000000002  (Casos + Fiscal)
  lawyer:  b2000000-0000-0000-0000-000000000002  (solo Casos)
```

---

## RLS — CRÍTICO

El early binding es el corazón del sistema. Nunca saltarlo:

1. `db.py` obtiene `space_ids` del usuario ANTES del vector search
2. Filtra `document_ids` permitidos para esos spaces
3. El vector search usa `WHERE document_id = ANY(allowed_doc_ids)`
4. Doble capa: aplicación + políticas RLS de Supabase

**Si falla RLS, todo el modelo de seguridad se colapsa.**

---

## Modelos — FIJOS para el TFM

| Modelo | Uso | Dimensiones |
|--------|-----|-------------|
| `nomic-embed-text` | Embeddings ingesta + query | **768 dims — INMUTABLE** |
| `mistral-small-latest` | Generación (Mistral API) | temp 0.2 |
| `mistral:7b-instruct-q4_K_M` | Fallback Ollama | temp 0.2 |

**Cambiar el modelo de embeddings requiere re-ingestar TODOS los documentos.**

---

## Convenciones de código

- **Comentarios y docs:** ESPAÑOL
- **Código (variables, funciones, clases):** INGLÉS
- **Indentación:** 2 espacios (pero Python usa 4 por convención, respetar)
- **Type hints:** siempre en funciones Python
- **Docstrings:** en español
- **Commits:** `Feat: título en inglés` + descripción en español

---

## Métricas reales (10 junio 2026)

- Latencia RAG vector puro: **~1.0–3.3s** (p50 manual, pendiente benchmark.py formal)
- Latencia RAG híbrido vector + grafo: **~1.0s** (caso PCA jornada mínima)
- Latencia embedding query (Ollama CPU): **~0.8s**
- Latencia HITL email E2E: **~1s**
- Tiempo backfill grafo (9 docs → 233 claims): **107s**
- Tests completos (20): **~20s**
- Datos en producción: 9+ docs (varía con ingesta automática), 29+ chunks, 158 entidades, 233 claims, 3 contradicciones

---

## Notion — Páginas clave del proyecto

| Página | URL | Uso |
|--------|-----|-----|
| Estado técnico (síntesis TFM) | https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a | Fuente de verdad técnica para Claude Chat |
| Historial de Desarrollo | dentro de Log y Troubleshooting | 12 entradas con fechas y hitos reales |
| Roadmap & Tareas | https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533 | Checklist phases |
| Company Brain proceso completo | https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6 | Descripción funcional |
| Stack, costes e infraestructura | https://app.notion.com/p/3782e8533b4481f6a98ed9b46877d170 | Detalle costes |

---

## Reglas

1. Responder siempre en **español**
2. RLS verificado desde el día 1 — nunca saltarlo
3. Modelo embeddings `nomic-embed-text` **768 dims** — nunca cambiar
4. No agregar dependencias sin consultar
5. Documentar decisiones en Notion después de cada sesión
6. Commits atómicos con mensaje claro
7. **n8n: la instancia de Korio es `n8n.korio.es`, NO `n8n.lagalga.es`**. El `n8n-mcp` de Claude Code apunta a lagalga; los workflows hay que exportar/importar a korio O usar `N8N_KORIO_API_KEY` del `.env` del VPS contra la API REST de korio.
8. **Webhook HITL protegido con Basic Auth**: cualquier llamada desde backend debe ir con `HITL_WEBHOOK_USER` + `HITL_WEBHOOK_PASS`.

---

*Actualizado: 10 junio 2026 (tarde · sesión 3) — Phase 7.2 CERRADA · ingesta automática multi-canal (Gmail + Drive + Slack) en producción con `source_metadata`; endpoint admin `DELETE /document/{id}`; doc de diseño Phase 8 para memoria TFM.*
