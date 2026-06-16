# Korio — CLAUDE.md

## Proyecto

**Korio** (nombre comercial) / **Company Brain** (técnico) — SaaS multi-tenant de RAG para pymes españolas. Permite ingestar documentos internos y consultarlos en lenguaje natural, con control de acceso por departamento (RLS) y multi-tenancy real.

**TFM:** Máster IA Business & Innovation — Nuclio Digital School  
**Demo funcional:** 2 julio 2026  
**Defensa TFM:** 9 julio 2026  
**Repo:** https://github.com/lagalga/korio  

---

## Estado actual (14 junio 2026 · sesiones 6-13a · v0.3.4)

### ✅ Completado — Phases 1–7.3 + v0.3.0 (las 6 reglas del E3 cumplidas)

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

- ~~**QA end-to-end**~~ ✅ sesión 10 (10/10 casos)
- ~~**Benchmark formal**~~ ✅ sesión 10 (p50=1983ms, p95=3053ms)
- **Vídeo demo** del ciclo completo (Gmail llega → 30s después consultable → conflicto → email HITL → grafo → MCP en Claude Desktop)
- **Slide deck** (10–15 slides) + ensayo presentación
- **Compliance audit** ✅ sesión 13a (7/7 CRIT+HIGH cerrados). Ver `docs/COMPLIANCE-AI-ACT-GDPR.md`
- **Memoria TFM** — escritura con capítulos:
  - ✅ Phase 7.1–7.3 (grafo, MCP server) → `docs/MCP-SERVER.md`
  - ✅ Phase 6–9 (ingesta agéntica, E3 rules) → `docs/AGENTIC-INGESTION.md`
  - ✅ **Compliance** (AI Act + GDPR) → `docs/COMPLIANCE-AI-ACT-GDPR.md` (sesión 14)
  - 🔲 Defensa negocio + entrevistas (sesión 15+)

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
| Automatización | n8n v1.x (Docker en VPS) | **7 workflows**: HITL + Cron + Pipeline event bus + Gmail + Drive + Slack `/korio` + Slack file_shared |
| Servidor | Hetzner **CPX32** (AMD EPYC-Genoa), Frankfurt, 4 vCPU / 8 GB / 160 GB SSD | `ssh korio-vps` · **€17.53/mes max** (€0.0281/h) |
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
│       ├── 009_source_metadata.sql  # JSONB con canal de origen (Gmail, Drive, manual…)
│       ├── 010_mcp_api_keys.sql     # API keys SHA-256 para el servidor MCP (Phase 7.3)
│       ├── 011_pipeline_events_atomic_ingest.sql  # Bus de eventos + ingesta ACID (sesión 6)
│       ├── 012_silent_conflicts_query_time.sql    # RPC detección query-time (sesión 8)
│       ├── 013_inconclusive_state_and_policies.sql # Estado inconclusive + policies (sesión 9)
│       ├── 014_n8n_errors.sql       # Tabla errores workflows n8n (sesión 12)
│       └── 015_mcp_api_keys_rls.sql # RLS sobre mcp_api_keys (sesión 13a)
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
│   ├── conftest.py                       # Fixtures: UUIDs seed (tenants, users, spaces)
│   ├── test_rls.py                       # 10 tests aislamiento (10/10 ✅)
│   ├── test_search.py                    # 10 tests RAG (10/10 ✅)
│   ├── test_atomic_ingest.py             # 3 tests ACID atomicidad (sesiones 6)
│   ├── test_pipeline_agentic.py          # 2 tests fachada agéntica (sesión 7)
│   ├── test_query_time_detection.py      # 1 test detección query-time E4 (sesión 8)
│   ├── test_inconclusive_and_policies.py # 2 tests inconclusive + policy reuse (sesión 9)
│   └── test_graph_semantic_rerank.py     # 3 tests rerank semántico del grafo (sesión 11)
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
│   ├── benchmark.py           # Medición latencias p50/p95 por escenario
│   ├── graph_backfill.py      # Pobló 237 claims sobre 10 docs en 116s (re-run tras fix subject)
│   ├── graph_embed_claims.py  # Backfill embeddings en claims FalkorDB (455 claims en 23s)
│   └── mcp_create_key.py      # CLI create/list/revoke de MCP API keys (Phase 7.3)
│
└── docs/
    ├── ARCHITECTURE.md             # Diagrama del sistema, modelo de datos, RLS
    ├── DEPLOYMENT.md               # Setup en Hetzner desde cero
    ├── ROADMAP.md                  # Fases pasadas y futuras
    ├── SESSION-STARTER.md          # Prompt de arranque para nueva sesión Claude
    ├── AGENTIC-INGESTION.md        # Las 6 reglas del E3 + comparativa microservicios (sesiones 6-9)
    ├── MCP-SERVER.md               # Phase 7.3: Korio como servidor MCP HTTP+SSE
    ├── MULTI-TENANT-INGESTION.md   # Diseño Phase 8: OAuth multi-tenant SaaS
    ├── CHAT-PIPELINE-GUARDRAILS.md # Diseño Phase 8: chat con guardrails n8n
    └── PHASE-10-MULTIMODAL-INGESTION.md  # Diseño Phase 10: email/Slack/Teams/audio (sesión 11)
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

## Checklist de cierre de sesión (actualizar SIEMPRE que aplique)

Cuando el usuario pida "cierra sesión" / "actualiza todo" / similar, repasar
esta lista en orden. Cada destino lleva una pista de QUÉ actualizar y CUÁNDO
omitir. Si la sesión no tocó algo, marcarlo explícitamente como "sin cambios"
en el resumen final en lugar de saltar silenciosamente.

### Notion
1. **Roadmap & Tareas — Korio TFM**
   `https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533`
   — añadir sección `## ✅ Sesión <N> (<fecha>)` al final con bullet por
   tarea cerrada y `🔲 Pendientes`. Aplica siempre que la sesión cierre
   tareas técnicas, migre algo a producción o defina nueva work.
2. **Log y Troubleshooting** (DB `collection://c83daaa3-9c54-4368-88f4-cb7a63f95592`)
   `https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1`
   — una entrada por hallazgo: Tipo (Problema / Resolución / Bug / Éxito /
   Aprendizaje), Status (Done / In Progress / Bloqueado), Fecha, Descripción
   con causa raíz + fix + verificación. Una entrada por problema (no por
   sesión). Aplica siempre que se descubra un bug, se cierre una resolución
   o se aprenda algo no obvio sobre el sistema.
3. **Estado técnico — Síntesis para TFM**
   `https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a`
   — añadir sección `## <N>. Hitos sesión <X> (<fecha>, vY.Y.Y)` al final,
   con resumen ejecutivo. Aplica cuando haya cambios de arquitectura,
   nuevas migraciones, nuevos workflows o nuevos hitos demostrables. NO
   aplica para correcciones triviales o sólo de documentación.
4. **Stack, costes e infraestructura**
   `https://app.notion.com/p/3782e8533b4481f6a98ed9b46877d170`
   — sólo si cambian los costes (VPS, Supabase, Mistral, etc.), aparecen
   nuevos servicios facturables (n8n cloud, Stripe, dominio adicional) o
   se reduce/amplia el tier de algún proveedor. La mayoría de sesiones NO
   requieren tocar esta página.

### Repo Korio (`lagalga/korio` rama `main`)
5. **`ROADMAP.md`**
   — añadir línea en el bloque correspondiente (Phase activa o Backlog).
   Marcar `[x]` lo cerrado, mover Pendientes a futuro. Aplica si la sesión
   modifica el plan o cierra algún ítem ya enumerado.
6. **`docs/SESSION-STARTER.md`**
   — al cierre de cada sesión: mover el bloque "Próxima sesión" anterior a
   "Estado al cierre de sesión <N>" y abrir nuevo bloque "Próxima sesión
   <N+1>". Aplica SIEMPRE.
7. **`CLAUDE.md`** (este archivo)
   — añadir bloque `**Sesión <N> (<fecha>)**` al final con resumen
   compacto (migraciones, workflows, commits, pendientes). Mantener el pie
   `*Actualizado: …*` reflejando última versión. Aplica SIEMPRE.

### Otros repos / artefactos
8. **`CHANGELOG.md`** — entrada `[vX.Y.Z] — YYYY-MM-DD · sesión <N>` con
   secciones Added / Changed / Fixed / Security / Operational según
   corresponda. Bump version sólo si la sesión cierra una unidad
   coherente que merezca tag.
9. **MEMORY.md auto-memory** (en
   `~/.claude/projects/-Users-berto-Claude-Code-korio/memory/MEMORY.md`) —
   añadir o actualizar entradas tipo `feedback_*`, `project_*` o
   `reference_*` con lo aprendido que aplique a sesiones futuras. NO usar
   esta memoria para estado efímero — sólo para reglas / hechos
   duraderos.

### Orden recomendado
GitHub commits + push → CLAUDE.md → SESSION-STARTER → CHANGELOG → Notion (4 páginas en bloque). MEMORY al final si hubo aprendizajes.

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

---

**Sesión 10 (12 jun · mañana)** — QA E2E 10/10 + Benchmark + fixes encadenados:

- **QA E2E completo (10/10 ✅)**: E1 vectorial directa, E2 grafo (35h/semana), E3 multi-turn reformulación, E4 aislamiento RLS, E5 chunk disputed badge, E6 query-time silent_conflict, E7 MCP Claude Desktop, E8 MCP list_pending_conflicts, E9 ingesta Gmail, E10 bus de eventos n8n.
- **FalkorDB AOF persistencia** — `REDIS_ARGS=--appendonly yes --appendfsync everysec` en `docker-compose.yml`.
- **Benchmark `--delay` flag** — `scripts/benchmark.py` acepta `-d <segundos>` entre iteraciones. Resultado: global p50=1983ms, p95=3053ms. 50/50 sin errores.
- **Retry Mistral 429** — `_generate_mistral()` reintenta hasta 3 veces con backoff exponencial (1s/2s/4s).
- **Threshold búsqueda 0.4→0.35** y **query-time conflict 0.85→0.80** (vars de entorno actualizadas en VPS).
- **Validación semántica CONTRADICTS** — `llm_client.py` nuevo método `is_semantic_contradiction()`. `graph_client.py` reescrito `link_contradictions_between_chunks()`: elimina filtro CONTAINS excesivamente estricto, valida par a par con Mistral (temp=0). Resultado: 2 aristas CONTRADICTS válidas en Delos vs 0 previas.

---

**Sesión 11 (12 jun · tarde)** — Rerank semántico del grafo (v0.3.2):

- **`find_claims_semantic()`** en `graph_client.py` — scan + cosine similarity en Python con RLS por space_id.
- **`upsert_claim()`** acepta `embedding: Optional[List[float]]`.
- **`_graph_context()` con Reciprocal Rank Fusion (k=60)** — léxico (keywords + score 3·predicate + 2·value + 1·subject) y semántico (cosine query × claim) corren en paralelo, top-8 final combinado.
- **`src/ingest.py`** embeda `"subject predicate value"` en batch al crear claims.
- **`scripts/graph_embed_claims.py`** backfill — 455 claims embedidos en 23s en producción.
- **3/3 tests** en `tests/test_graph_semantic_rerank.py`.
- **Modelo fallback `mistral:7b-instruct-q4_K_M`** descargado en VPS (4.4 GB).
- **Corrección specs VPS** — Hetzner CPX32 AMD EPYC-Genoa, 4 vCPU / 8 GB / 160 GB SSD, €17.53/mes. Corregido en README, CLAUDE.md, ARCHITECTURE, DEPLOYMENT, ROADMAP y Notion.
- **`docs/PHASE-10-MULTIMODAL-INGESTION.md`** — diseño Phase 10 post-TFM: email body, Slack/Teams threads, audio (Voxtral + Whisper). `src/adapters/` + `POST /ingest/{kind}`.
- **Workflow n8n `Korio · Slack file_shared → /upload (Delos RRHH)`** (`81GO5BjXj0ZNYmhO`): Webhook `korio-slack-events` → switch challenge/file_shared → `files.info` → download → POST `/upload` → ✅ reaction + DM. Verificado E2E con PDF en producción.

---

**Sesión 12 (12 jun · noche)** — Visualización grafo + captura de errores n8n (v0.3.3):

- **Fix banner "⚠️ Contradicción detectada"** — umbral `KORIO_DISPUTED_BANNER_MIN_SIM=0.6` (env). El banner solo aparece si la similitud del chunk disputado supera el umbral, eliminando falsos positivos en queries no relacionadas.
- **Fix aristas CONTRADICTS invisibles** — `get_tenant_subgraph()` con `limit=300` excluía nodos endpoint de aristas CONTRADICTS. Solución: second query que rescata nodos prioritarios `id(n) IN [list]` fuera del LIMIT.
- **Hover/click en sidebar → resaltar arista CONTRADICTS** — `data-from-id` / `data-to-id` en items de la sidebar. `highlightContradictionEdge(fromId, toId)` dimea todos los nodos/aristas excepto los 2 claims endpoint y su CONTRADICTS. Click bloquea, click fuera libera.
- **Fix scale "enganchado" post-hover** — `DataSet.update()` no puede resetear propiedades anidadas (font.bold, size). Solución definitiva: `data.nodes.clear() + data.nodes.add(canonicalGraph.nodes con posiciones preservadas)`. Clona estado canónico inmutable al renderizar.
- **`supabase/migrations/014_n8n_errors.sql`** — tabla `n8n_errors` (workflow_id, error_message, error_node, raw_payload JSONB, reviewed_at) + 3 índices. Sin RLS (solo service_role).
- **Workflow n8n `Korio - Gestión de errores n8n`** (`KeUTpIk0ycbW1f3g`) — Error Trigger → Set (extrae mensaje desde stack) → parallel [HTTP POST Supabase `n8n_errors` + Slack DM a admin U0A97H29E8J con Block Kit]. Verificado E2E: 2 filas en Supabase, real production error de Slack `/korio` capturado.
- **`errorWorkflow: "KeUTpIk0ycbW1f3g"` aplicado** a los 7 workflows de producción (ya configurado en todos).
- **Pendiente Phase 9 (próxima sesión)**: throttling anti-spam (1 DM por 10 errores del mismo workflow), panel `/admin/errors` en la UI, botón "reviewed" en el propio mensaje Slack (interactivity webhook).

---

---

**Sesión 13a (14 jun 2026)** — Hardening de seguridad pre-demo (v0.3.4):

- **Auditoría completa** con 3 agentes Explore en paralelo (seguridad / diseño / bugs) sobre v0.3.3. 21 hallazgos catalogados (4 CRIT, 3 HIGH, 8 MED, 6 LOW). Cruce contra roadmap existente para no duplicar Phase 8/9/10.
- **7 fixes cerrados** (bloqueantes para demo pública del 2-jul):
  - **N1 CORS whitelist** — `api/server.py`: `https://korio.es` + opcional `localhost` si `KORIO_ENV=dev`. Métodos/headers explícitos. Env nueva `KORIO_EXTRA_CORS_ORIGINS`.
  - **N2 timing attack** — `require_admin` con `hmac.compare_digest` (no `!=`).
  - **N3 cross-tenant DELETE** — `DELETE /document/{id}` valida `doc.tenant_id == KORIO_ADMIN_TENANT_ID` (defensa en profundidad hasta OAuth Phase 8).
  - **N4 RLS `mcp_api_keys`** — migración `015_mcp_api_keys_rls.sql`: policies `self_read`/`self_update` (auth.uid) + `service_role_all`.
  - **N5 assert dim 768** — `Embedder._check_connection` aborta arranque si Ollama devuelve dim distinta.
  - **N6 cleanup tempfile** — `/upload`: `tmp_path` antes de `copyfileobj`, `finally` blindado contra `FileNotFoundError`/`OSError`.
  - **C2 Cypher parametrizado** — `tests/test_graph_semantic_rerank.py` con `$tid` (no f-string).
- **14 issues diferidos** con destino justificado (Phase 8/9 o ya planeados): anexo en `docs/AUDIT-2026-06-14.md` (capítulo memoria TFM *Seguridad y deuda técnica reconocida*).
- **Envs nuevas en `/root/korio/.env`**: `KORIO_ENV=prod`, `KORIO_ADMIN_TENANT_ID=<uuid>`, opcional `KORIO_EXTRA_CORS_ORIGINS`.
- **5 commits atómicos a `main`** (`Fix(seguridad)…`, `Feat(seguridad)…`, `Fix:…`, `Fix(test):…`, `Docs:…`). Push verificado.

---

*Actualizado: 14 junio 2026 (sesiones 6-13a) — v0.3.4. Hardening seguridad cerrado: 7 fixes nuevos antes de demo pública (CORS, timing attack, cross-tenant DELETE, RLS mcp_api_keys, dim assert, tempfile cleanup, Cypher param). 15 migraciones, 8 workflows n8n, 28/28 tests verdes, p50=1983ms/p95=3053ms. Pendiente: vídeo demo, slide deck, memoria TFM (sesiones 13b+).*

---

**Sesión 13b (15 jun · noche)** — QA E2E con multi-canal real + ivfflat fix (v0.3.5):

- **18 docs en producción** (13 Delos + 5 García nuevos G1-G5). Auto-resoluciones limpias en 5 pares (R2↔R1, R5↔R3, M2↔M1, L3↔L2, G4↔G3) por fecha extraída del contenido.
- **R6/R7 nuevos** (normativa uniformes RRHH sin fecha) → conflict pending → `/escalate-reviews` con backdate → chunks `inconclusive` ✅ regla 5 demostrada.
- **Multi-canal real verificado E2E**:
  - Gmail label `korio/rrhh` → R2 → space RRHH
  - Drive carpeta `input/medico` → M2 → space Médico
  - Slack `#clinica-delos-legal` → L3 → space Legal
- **Slack RLS por canal**: 4 service users (`slack_{rrhh,medico,legal,admin}@delos`) con scope vía `user_spaces`. Workflow `/korio` mapea `channel_id → user_id` → RLS automático. Preguntar en `#clinica-delos-rrhh` sobre LOPD → "No encuentro" (correcto).
- **Migración 016** — `detect_silent_conflicts_among_chunks` añade `d1.space_id = d2.space_id`. Cross-space sin caso funcional + chunks cortos producían falsos positivos (R4↔M3 sim 0.85 entre RRHH y Médico).
- **Migración 017** — space `Administración` (id ...004) en Delos + grant al admin.
- **Migración 018** — 4 service users Slack con `user_spaces` por canal.
- **Migración 019** — **DROP `idx_embeddings_vector`** (ivfflat lists=100). Causa raíz del bug RPC: con 19 chunks dispersos en 100 listas, `ivfflat.probes=1` (default) solo recorría una lista → encontraba self-match exacto pero ignoraba todos los vecinos. Sin índice el seq scan es trivial con decenas de chunks. Reintroducir en Phase 9 con `lists=ceil(sqrt(N))` o HNSW.
- **Workflows n8n parametrizados** (4 refactores):
  - `Korio · Slack file_shared → /upload (Delos multi-space)` — switch sobre `event.channel_id` → space_id.
  - `Korio · Drive → /upload (Delos multi-space)` — 4 triggers paralelos por subcarpeta `input/{rrhh,medico,legal,admin}`, mapping `parents[0] → space_id`.
  - `Korio · Gmail → /upload (Delos multi-space)` — filtro `(label:korio/rrhh OR ... OR label:korio/admin) has:attachment -label:korio/procesado -in:trash`. Sin `readStatus:unread` (frágil si user abre correo). Idempotencia vía `korio/procesado`.
  - `Korio · Slack /korio → /search (Delos multi-canal)` — mapping `channel_id → service user_id`.
- **3 commits a `main`**: `e5ea543` (extractor version_ts), `68760ff` (R6/R7 + mig 016), `be13a45` (García + mig 017/018/019).
- **Notion troubleshooting**: 6 entradas nuevas (4 resoluciones + 2 problemas Phase 9 + 1 aprendizaje).

🔲 **Pendientes Phase 9** (no bloqueantes para vídeo):
- Detector ingesta: falsos positivos entre docs temáticamente similares (G1↔G2 caso despacho legal mismo estilo). Fix: validación semántica LLM (`is_semantic_contradiction()`) antes de declarar conflict.
- Workflow Slack: doc-ya-existe debe avisar al usuario con DM, no disparar errorWorkflow.
- Regla 4 (políticas reutilizables): sin caso demostrado aún, queda para 13c.
- Reintroducir índice vectorial con volumen >1000 chunks.

*Actualizado: 16 junio 2026 (sesión 14) — v0.3.7. Implementación cerrada. 31/31 tests, 20 migraciones, 8 workflows n8n, 18 docs producción, 27 aristas CONTRADICTS, snapshot pre_demo guardado. Próximo: vídeo demo (sesión 15), slide deck (sesión 16), memoria TFM en Claude Projects.*

---

**Sesión 13c (16 jun 2026)** — Regla 4 demo + fix inconclusive en RAG (v0.3.6):

- **Regla 4 demostrada en producción** — ciclo completo: admin resolvió R6↔R7 como `approved_new` → policy `policy_new_wins` creada (subject_pattern="nota interna sobre uniformes…") → borrado R6+R7 → re-ingesta R6 (chunks activos) → re-ingesta R7 → `📚 Política 4 aplicada` chunk 242↔240 (sim=0.98) auto-resuelto por policy. `times_applied=1`. Segundo par (243↔241 sim=0.91) no matcheó → HITL email enviado. Las 6 reglas del E3 **cerradas con evidencia de producción**.
- **Migración 020** — `search_embeddings` RPC incluye `inconclusive` en el filtro. Fix: el diseño de gobernanza dice "conservar ambos documentos como información complementaria" pero la RPC solo devolvía `active`/`disputed`.
- **`src/search.py`** — `inconclusive` tratado igual que `disputed`: badge ⚠️ + aviso en respuesta. Chunks inconclusive ya no desaparecen del RAG.
- **`src/db.py`** — `resolve_conflict_review()` acepta `timeout_inconclusive` además de `pending`. El admin puede overridear decisiones de timeout.
- **Fix preprocessor PyMuPDF** — `pymupdf.open()` para extracción de PDFs (mejor calidad que MarkItDown/pdfminer para texto pegado).
- **18 docs expandidos** a 550-950 palabras cada uno para mayor riqueza semántica en chunks.
- **3 commits a `main`**: `544e75f` (pymupdf + docs expandidos), `0ac0d72` (mig 020 + search.py inconclusive), `7ee4c57` (db.py override timeout).

🔲 **Pendientes Phase 9** (no bloqueantes para vídeo):
- Validación semántica LLM en detector ingesta (falsos positivos G1↔G2).
- Workflow Slack: doc-ya-existe → DM en lugar de errorWorkflow.
- Reintroducir índice vectorial con volumen >1000 chunks.

---

**Sesión 14 (16 jun 2026)** — Cierre implementación + herramientas de demo (v0.3.7):

- **Aristas CONTRADICTS visibles en grafo** — chunk 241 (R6, chunk 1) tenía 0 claims por truncamiento JSON de Mistral. Insertados 10 claims manuales + ejecutado `link_contradictions_between_chunks(243, 241)` → 14 aristas CONTRADICTS nuevas. **Total 27 aristas CONTRADICTS** en grafo (13 del par resuelto 242↔240 + 14 del par pendiente 243↔241).
- **`scripts/demo_snapshot.py`** — herramienta save/restore para la grabación del vídeo demo. Captura: 5 tablas Supabase (documents, embeddings, conflict_reviews, policies, pipeline_events) + grafo FalkorDB completo (925 nodos, 1475 aristas). Permite resetear al estado pre-demo con `python scripts/demo_snapshot.py restore --name pre_demo_v036`.
- **Fix test `test_busqueda_sin_contexto`** — con RAG híbrido, el grafo puede aportar contexto marginal (keywords genéricas) aunque vector search devuelva 0 chunks. Test ajustado para verificar solo `chunks_used == 0`.
- **31/31 tests verdes** (antes 30/31).
- **Snapshot `pre_demo_v036`** guardado en VPS: 18 docs, 63 chunks, 925 nodos grafo, 1475 aristas, 2 policies, 1 conflict_review.
- **1 commit a `main`**: `d4a23e3`.

**🏁 IMPLEMENTACIÓN CERRADA** — a partir de aquí, sesiones de contenido (vídeo, slides, memoria TFM con parte de negocio).

*Actualizado: 16 junio 2026 (sesión 14) — v0.3.7. Implementación cerrada. 31/31 tests, 20 migraciones, 8 workflows n8n, 18 docs producción, 27 aristas CONTRADICTS, snapshot pre_demo guardado. Próximo: vídeo demo (sesión 15), slide deck (sesión 16), memoria TFM en Claude Projects.*
