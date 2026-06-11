# Korio — CLAUDE.md

## Proyecto

**Korio** (nombre comercial) / **Company Brain** (técnico) — SaaS multi-tenant de RAG para pymes españolas. Permite ingestar documentos internos y consultarlos en lenguaje natural, con control de acceso por departamento (RLS) y multi-tenancy real.

**TFM:** Máster IA Business & Innovation — Nuclio Digital School  
**Demo funcional:** 2 julio 2026  
**Defensa TFM:** 9 julio 2026  
**Repo:** https://github.com/lagalga/korio  

---

## Estado actual (11 junio 2026 · sesiones 6-9 · v0.3.0)

### ✅ Completado — Phases 1–7.3 + v0.3.0 (las 6 reglas del E3 cumplidas)

**Phases 1–4** — pipeline ingesta, RAG vectorial, multi-tenancy con RLS, docs técnicos, chat UI con upload, benchmark script.

**Phase 5** — producción en korio.es, gobernanza activa (auto-resolución + HITL email), landing teaser.

**Phase 6** — cron de escalada HITL (recordatorios 3/7/14 días + auto-cierre a 21 días). Workflow n8n Schedule Trigger diario 09:00 Madrid. Migración 008.

**Phase 7.1** — grafo de conocimiento con FalkorDB vivo, sync en tiempo real, 3 puntos de acceso desde la UI. Hito TFM: la query "¿Cuántas horas semanales mínimas?" que el RAG vectorial puro no encontraba ahora responde "más de 35 horas/semana" en ~1s vía grafo. Banner ⚠️ del chat con link al grafo.

**Phase 7.2** — ingesta automática multi-canal en producción:
- **Migración 009**: `documents.source_metadata` (JSONB) + índice parcial por `via`. Registra el canal de origen.
- **`ingest_document()`** acepta `source_metadata: Optional[dict]` y lo persiste; `/upload` lo acepta como Form field JSON string.
- **`DELETE /document/{id}`** (admin) — borra Postgres en cascada + limpia FalkorDB. Auth con `APIKeyHeader` X-Korio-Admin-Key (botón Authorize visible en Swagger).
- **Fix crítico de gobernanza**: webhook HITL ahora protegido con Basic Auth (`B3rt0` / `13-K0rio-14!`); `conflict_detector.py` y `escalation.py` parcheados para enviar credenciales via `HITL_WEBHOOK_USER` + `HITL_WEBHOOK_PASS` del `.env`.
- **3 workflows nuevos** en `n8n.korio.es`:
  - **Gmail → /upload (Delos RRHH)**: vigila label `korio/ingesta` en `contacto@lagalga.es` cada 5 min, ingiere adjuntos PDF/DOCX, marca leído + aplica label `korio/procesado`.
  - **Drive → /upload (Delos RRHH)**: vigila carpeta `Clínica Delos / input` (`1rlBEmkqLHvidWEPv64LaMpzBh9bMDGF4`) cada 5 min.
  - **Slack /korio → /search (Delos admin)**: slash command → ACK ephemeral → POST /search → reply en thread con respuesta + fuentes con %relevancia + link a korio.es.
- **UI polish**: filenames de fuentes ya no se truncan; eliminado marcador `[grafo]` confuso de las respuestas.
- **Documento de diseño** `docs/MULTI-TENANT-INGESTION.md` — Phase 8 post-TFM (OAuth multi-tenant, vault de tokens, ingestion_rules, onboarding UX). Sirve como capítulo de la memoria TFM "Arquitectura objetivo SaaS post-defensa".

**Sesión 4 (10 jun · tarde)** — memoria de chat + fix CONTRADICTS:
- **Memoria de chat multi-turn**: `state.conversation` guarda últimos 6 turnos en el frontend. `search.py` reformula la query como autónoma vía LLM (`reformulate_query`) antes del embedding. Latencia +1s. Solo se guardan turnos con `has_context=true`. Respuesta expone `original_query`, `embedded_query`, `query_reformulated`.
- **Fix CONTRADICTS falsos positivos en el grafo**: Cypher exige `subject` igual o substring containment, en `link_contradictions_between_chunks` (live) y `scripts/graph_backfill.py` (batch).
- **Documento de seguridad** `docs/CHAT-PIPELINE-GUARDRAILS.md` — Phase 8 con n8n + Lakera/Rebuff (ingress) + Presidio (egress) + rate limit.

**Sesión 5 (11 jun · mañana)** — Phase 7.3 + 4 fixes encadenados del RAG híbrido:

**Phase 7.3 — MCP Server** ✅ EN PRODUCCIÓN:
- **Migración 010**: tabla `mcp_api_keys` (key_hash SHA-256, user_id, tenant_id, name, last_used_at, revoked_at). FK a `users` y `tenants`.
- **`api/mcp_server.py`**: FastMCP con 3 tools — `search_knowledge_base`, `list_pending_conflicts`, `list_spaces`. Identidad propagada vía `ContextVar` desde el header `X-Korio-MCP-Key`. Reaprovecha el early binding de RLS del backend sin duplicar nada.
- **`api/server.py`**: middleware ASGI puro `MCPAuthASGI` que envuelve solo el sub-app `/mcp`. NO se usa `@app.middleware("http")` porque `BaseHTTPMiddleware` bufferea la respuesta y rompe SSE.
- **Transport security**: `TransportSecuritySettings` con `allowed_hosts=[korio.es,...]` para que el anti-DNS-rebinding del SDK MCP acepte el Host de nginx.
- **`scripts/mcp_create_key.py`**: CLI create/list/revoke. Plaintext mostrado UNA sola vez. Prefijo `korio_`.
- **Doc** `docs/MCP-SERVER.md` — capítulo memoria TFM con arquitectura, conexión a Claude Desktop (vía `mcp-remote` por npx, requiere Node 20+), limitaciones y Phase 8 (OAuth 2.1, rate limit, audit log).
- **Decisiones críticas del despliegue** documentadas: 1 worker uvicorn (las sesiones SSE son in-memory por proceso); en Phase 8 → streamable_http_app stateless o sticky sessions en nginx.

**Fix encadenado del RAG cuando el grafo debía aportar** (caso TFM `"35 horas semanales mínimas"`):

1. **Fix SSE + middleware** — `BaseHTTPMiddleware` rompía streams SSE con `AssertionError: Unexpected message: http.response.start, content-length=0`. Sustituido por `MCPAuthASGI` puro.
2. **Fix citación de fuentes** — docstring + `instructions` del MCP server obligan al modelo cliente a citar siempre los `filename` y avisar de `is_disputed`.
3. **Fix `list_spaces` -32602** — FastMCP requiere ≥1 parámetro declarado para validar `arguments:{}`. Añadido `include_inactive: bool = False` (no usado, placeholder Phase 8).
4. **Fix grafo ignorado por el LLM** — el bloque `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]` se prepend-eaba al `user_prompt` **fuera** del bloque `CONTEXTO:`. El system_prompt obliga a "RESPONDER ÚNICAMENTE con información del CONTEXTO" → Mistral, literal, lo descartaba. Solución: `build_rag_prompt(graph_context=...)` lo inyecta DENTRO del CONTEXTO; system_prompt declara explícitamente que ambas fuentes (chunks + grafo) son válidas.
5. **Fix retrieval del grafo saturado por subject genérico** — `find_claims_by_predicate` con `LIMIT 20` se llenaba con matches por subject "política vacaciones" (keyword "política") y los claims con value "35 horas/semana" caían fuera. LIMIT subido a 50 + rerank en Python: `score = 3·predicate_match + 2·value_match + 1·subject_match` por cada keyword. Los claims informativos suben al top-8.

Resultado verificado en producción y vía Claude Desktop:
- `"¿cuántas horas semanales mínimas exige la política de RRHH?"` → *"La política de RRHH exige una jornada mínima de 35 horas semanales para los empleados asalariados [pca_politica_vacaciones_actualizada.md]"* con `graph_contributed: True` y latencia ~1.3s.
- Citación de fuentes ✅ con marcadores ✅/⚠️ por estado disputed.
- Aviso explícito de contradicciones pendientes en respuestas que tocan chunks `disputed`.

### 🔲 Pendiente antes del 2 julio (demo) + 9 julio (defensa)

- **QA end-to-end**: 10+ queries en ambos tenants vía `korio.es/ui` + Claude Desktop con MCP
- **Benchmark formal** de latencias (`scripts/benchmark.py`) — métricas p50/p95 + comparar con MCP
- **Vídeo demo** del ciclo completo (Gmail llega → 30s después consultable → conflicto → email HITL → grafo → MCP en Claude Desktop)
- **Slide deck** (10–15 slides) + ensayo presentación
- **Memoria TFM** — escritura completa con capítulos Phase 8 (`MULTI-TENANT-INGESTION.md`, `CHAT-PIPELINE-GUARDRAILS.md`) y Phase 7.3 (`MCP-SERVER.md`)
- ~~**Memoria de chat**~~ ✅ sesión 4
- ~~**Fix CONTRADICTS falsos positivos**~~ ✅ sesión 4
- ~~**Phase 7.3 MCP Server**~~ ✅ sesión 5

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
HITL_WEBHOOK_USER=B3rt0                  # basic auth del webhook HITL
HITL_WEBHOOK_PASS=13-K0rio-14!
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
│       ├── 009_source_metadata.sql  # JSONB con canal de origen (Gmail, Drive, manual…)
│       └── 010_mcp_api_keys.sql     # API keys SHA-256 para el servidor MCP (Phase 7.3)
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
│   ├── server.py        # FastAPI: /search, /ingest, /upload, /review,
│   │                    #          /escalate-reviews, /waitlist,
│   │                    #          /graph/contradictions, /graph/entity/{name},
│   │                    #          /graph/subgraph, /health,
│   │                    #          DELETE /document/{id} (admin)
│   │                    #          /mcp/* (sub-app SSE con auth ASGI, Phase 7.3)
│   └── mcp_server.py    # FastMCP: search_knowledge_base, list_pending_conflicts,
│                        #          list_spaces (Phase 7.3)
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
│   ├── benchmark.py        # Medición latencias p50/p95 por escenario
│   ├── graph_backfill.py   # Pobló 237 claims sobre 10 docs en 116s (re-run tras fix subject)
│   └── mcp_create_key.py   # CLI create/list/revoke de MCP API keys (Phase 7.3)
│
└── docs/
    ├── ARCHITECTURE.md             # Diagrama del sistema, modelo de datos, RLS
    ├── DEPLOYMENT.md               # Setup en Hetzner desde cero
    ├── ROADMAP.md                  # Fases pasadas y futuras
    ├── SESSION-STARTER.md          # Prompt de arranque para nueva sesión Claude
    ├── MCP-SERVER.md               # Phase 7.3: Korio como servidor MCP HTTP+SSE
    ├── MULTI-TENANT-INGESTION.md   # Diseño Phase 8: OAuth multi-tenant SaaS
    └── CHAT-PIPELINE-GUARDRAILS.md # Diseño Phase 8: chat con guardrails n8n
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

**Sesión 6 (11 jun · tarde)** — Korio v0.2.0: ingesta agéntica + transaccionalidad ACID:

- **Migración 011**: tabla `pipeline_events` (bus de eventos del pipeline multi-agente con `operation_id` UUID que correlaciona el ciclo), tabla `graph_sync_queue` (retry post-commit con FalkorDB), función PL/pgSQL `ingest_document_atomic(p_doc, p_chunks, p_operation_id, p_source_agent)` que escribe documento + chunks + evento `DOCUMENT_INGESTED` en **una sola transacción**.
- **`src/agents/events.py`**: `emit(event_type, source_agent, tenant_id, operation_id, document_id?, payload?)` con doble efecto: INSERT síncrono en `pipeline_events` (audit) + POST best-effort a webhook n8n (observabilidad en vivo, `KORIO_EVENT_WEBHOOK_URL`). Enums `EventType` (9 tipos) y `Agent` (6 roles). `new_operation_id()`, `trace(operation_id)`.
- **Refactor `src/ingest.py` en 5 fases claras**: IO externa (preprocess + chunking + embeddings, todo en memoria) → dedupe (SELECT) → RPC atómico (1 sola escritura) → sync FalkorDB post-commit con cola de retry → detección de conflictos. Cada fase emite eventos al bus.
- **Tests `tests/test_atomic_ingest.py`**: 3/3 verdes incluyendo `test_rpc_atomico_rollback_si_falla_mid_transaction` que fuerza fallo a mitad con vector de dimensión incorrecta y verifica que NADA queda persistido (documento, chunks ni evento DOCUMENT_INGESTED).
- **`api/server.py` version `0.2.0`** + `CHANGELOG.md` siguiendo Keep a Changelog.
- **Doc `docs/AGENTIC-INGESTION.md`** — capítulo memoria TFM "Cierre del feedback del Entregable 4 (transaccionalidad SQL) + comparativa con el sistema multiagéntico del E3/E4". Justifica la decisión de roles-lógicos-en-proceso vs microservicios (LangFlow) con tabla cuantitativa de latencias.

Pendiente sesión 7 (Phase 8 candidatos): detección query-time, estado `inconclusive` post-timeout, políticas reutilizables, refactor `src/agents/{ingestor,detector,…}.py`, workflow n8n `korio:event-bus`.

---

**Sesiones 7-8-9 (11 jun · tarde-noche)** — v0.3.0 cierre del mapeo E3/E4:

**Sesión 7 — observabilidad y fachada agéntica**:
- **Workflow n8n `Korio · Pipeline event bus`** (id `ymewhJheuvUgUCyt`) en `n8n.korio.es`. `KORIO_EVENT_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-events` en `/root/korio/.env`. Cada evento del backend dispara una ejecución visible con emoji + summary.
- **`src/agents/{base, ingestor, detector, arbitrator, supervisor, curator, pipeline}.py`** — fachada que refleja 1:1 los 5 roles del E3 con documentación PEAS por agente. `Pipeline(tenant_id).run_ingest()` es el entry point de alto nivel.

**Sesión 8 — detección query-time (Caso extremo del E4)**:
- **Migración 012** — RPC `detect_silent_conflicts_among_chunks(BIGINT[], FLOAT)` calcula similitud par a par dentro de Postgres (una sola query, O(N²/2) sobre N=chunks recuperados, pequeño).
- **`src/search.py` Step 2.5** — tras la búsqueda vectorial, llama al RPC. Si hay pares ≥0.85 entre docs distintos, emite `CONFLICT_DETECTED` con `triggered_by: query_time` + añade aviso al system_prompt + `silent_conflicts[]` al response.
- **`api/mcp_server.py`** — instructions actualizadas para que Claude Desktop muestre "⚠️ Aviso de la gobernanza:" cuando `has_silent_conflict=true`.
- Env vars: `KORIO_QUERY_TIME_CONFLICT_ENABLED=1`, `KORIO_QUERY_TIME_CONFLICT_THRESHOLD=0.85`.

**Sesión 9 — Reglas 4 y 5 del E3**:
- **Migración 013** — estado terminal `inconclusive` en `chunk_status` + nueva tabla `policies` (subject_pattern, decision, source_review_id, times_applied, last_applied_at, active).
- **`src/policies.py`** — `find_applicable_policy()` y `save_policy_from_review()`. Cada decisión HITL del admin se persiste como policy reutilizable que el Detector consulta antes de evaluar fecha/autoridad.
- **`src/escalation.py`** — `_apply_timeout` ahora marca chunks como `inconclusive` (excluidos del RAG hasta intervención manual) en lugar de devolver ambos a `active`. Legacy disponible con `KORIO_TIMEOUT_KEEP_BOTH=1`.
- **`src/conflict_detector.py`** — `ConflictReport.policy_resolved`. Logs distinguen `📚 Policy` vs `⚡ Auto`.
- **`api/server.py`** — `/review/{id}` persiste la policy automáticamente tras action HITL.

**Tests sesiones 6-9** (8/8 verdes acumulados):
- 3 atomicidad ACID (test_atomic_ingest.py)
- 2 fachada agéntica + Pipeline (test_pipeline_agentic.py)
- 1 query-time E2E reproduciendo el Caso extremo del E4 (test_query_time_detection.py)
- 2 inconclusive + policy reuse (test_inconclusive_and_policies.py)

**Las 6 reglas del E3 están materializadas en producción** (tabla detallada en `docs/AGENTIC-INGESTION.md` §"Cumplimiento de las 6 reglas del Entregable 3").

---

*Actualizado: 11 junio 2026 (sesiones 6-9) — v0.3.0. Korio cierra el feedback del profesor (transaccionalidad ACID), el Caso extremo del E4 (detección query-time), y las 6 reglas del E3 (`inconclusive` + `policies`). 8/8 tests verdes. Suite agéntica observable en n8n.korio.es. Pendiente para defensa: QA E2E, benchmark, vídeo demo, slides, memoria TFM.*
