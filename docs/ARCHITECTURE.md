# Korio — Arquitectura del Sistema

> Company Brain · RAG híbrido vector + grafo, multi-tenant, para pymes españolas
> Estado: **Phases 1–7.3 + las 6 reglas del Entregable 3 cumplidas + Phase 9 flecos errores + Observabilidad + Corpus saneado** · v0.3.16 (29 jun 2026)

---

## Visión general

Korio es un sistema RAG (*Retrieval-Augmented Generation*) **multi-tenant** que permite a pequeñas empresas consultar en lenguaje natural el conocimiento acumulado en sus documentos internos. Aporta cuatro diferenciadores sobre un RAG vainilla:

1. **Aislamiento real por tenant y por departamento** (RLS en aplicación + Postgres).
2. **Gobernanza activa de información contradictoria** — detección semántica, auto-resolución por fecha/autoridad/policy, HITL por email con cron de escalada y estado terminal `inconclusive`.
3. **Grafo de conocimiento complementario** (FalkorDB) que rescata datos cuando la query está semánticamente reformulada (caso "35 horas semanales").
4. **Pipeline transaccional ACID** con bus de eventos `pipeline_events` que materializa las 6 reglas del Entregable 3 del Máster.

### Capas funcionales

1. **Ingesta multi-canal** — manual (UI/CLI) + automática vía n8n (Gmail, Drive, Slack file_shared con mapping `channel_id → space_id`). Cada documento lleva `source_metadata` JSONB con el contexto del canal de origen.
2. **Pipeline de procesamiento ACID** — MarkItDown → Presidio (PII whitelist) → chunking → embeddings (768d) → RPC PL/pgSQL `ingest_document_atomic` (1 sola transacción) → sync post-commit con FalkorDB → detección de conflictos.
3. **Gobernanza activa** — detección semántica (ingesta + query-time), auto-resolución por fecha/autoridad/policy reutilizable, HITL email, cron de escalada con timeout 21 días → `inconclusive`.
4. **Búsqueda RAG híbrida** — vector + grafo en paralelo con Reciprocal Rank Fusion (k=60), memoria de chat multi-turn con reformulación de query, RLS en 3 capas.
5. **Endpoints de consulta y operación** — chat web (`/ui`), grafo (`/ui/graph.html`), Swagger (`/docs`), MCP server (`/mcp/sse`), Slack `/korio`, panel admin errores n8n (`/ui/admin-errors.html`).
6. **Observabilidad en 3 capas** — LangSmith @traceable (semántica RAG, tokens/coste, UE), OTel+Jaeger (infraestructura HTTP), RAG eval LLM-as-judge (`scripts/rag_eval.py`).

> **Cobertura de este documento:** vista global y diagramas de núcleo. Para detalle por área:
>
> - **Ingesta agéntica + las 6 reglas del E3:** `docs/AGENTIC-INGESTION.md` (cap. TFM).
> - **MCP server (Phase 7.3):** `docs/MCP-SERVER.md` (cap. TFM).
> - **Compliance AI Act + GDPR:** `docs/COMPLIANCE-AI-ACT-GDPR.md` (cap. TFM).
> - **Hardening seguridad pre-demo:** `docs/AUDIT-2026-06-14.md` (anexo TFM).
> - **Diseño Phase 8 — ingesta multi-tenant configurable:** `docs/MULTI-TENANT-INGESTION.md`.
> - **Diseño Phase 8 — chat con guardrails:** `docs/CHAT-PIPELINE-GUARDRAILS.md`.
> - **Diseño Phase 10 — ingesta multimodal:** `docs/PHASE-10-MULTIMODAL-INGESTION.md`.
> - **Roadmap y estado:** `docs/ROADMAP.md`.
> - **Despliegue desde cero:** `docs/DEPLOYMENT.md`.

```
USUARIO (web chat · Slack /korio · Claude Desktop vía MCP · n8n)
  │
  │  POST /search · /upload · /ingest · /review · /escalate-reviews
  │  GET  /admin/errors · /graph/{contradictions,entity,subgraph}
  │  SSE  /mcp/sse  (Model Context Protocol)
  ▼
┌──────────────────────────────────────────────────────────────────┐
│            FastAPI (api/server.py · v0.3.16)                     │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Sub-apps montados:                                         │  │
│  │   /ui            → chat web                                │  │
│  │   /ui/graph.html → visualización del grafo (vis-network)   │  │
│  │   /ui/admin-errors.html → panel admin errores n8n          │  │
│  │   /mcp/*         → FastMCP SSE (MCPAuthASGI middleware)    │  │
│  │   /legal/*       → privacy policy                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   PIPELINE         PIPELINE          GOBERNANZA + GRAFO
   BÚSQUEDA         INGESTA           (sync en vivo + cron)
```

---

## Pipeline de búsqueda (RAG híbrido)

```
search.py · v0.3.16
  │
  │ 1. Reformulación query (LLM) si hay historial multi-turn
  │    src/llm_client.reformulate_query()
  │
  │ 2. Embed query — Ollama nomic-embed-text · 768d · ~0.8s
  │
  │ 3. RLS early binding (db.py)
  │    user_id → user_spaces → allowed_doc_ids
  │
  │ 4. Búsqueda vectorial — pgvector cosine
  │    RPC search_embeddings(query_vec, threshold=0.35, allowed_docs)
  │    Incluye chunks active + disputed + inconclusive con flag
  │
  │ 5. Step 2.5: detección query-time de conflictos silentes
  │    RPC detect_silent_conflicts_among_chunks(ids, threshold=0.80)
  │    Si hay pares ≥0.80 misma space → has_silent_conflict=true
  │
  │ 6. Búsqueda paralela en grafo (FalkorDB)
  │    src/graph_client.find_claims_by_predicate() + find_claims_semantic()
  │    Reciprocal Rank Fusion k=60 → top-8 claims
  │
  │ 7. LLM generación — Mistral API (fallback Ollama local)
  │    Prompt con CONTEXTO unificado (chunks + grafo)
  │    PII redaction pre-Mistral (KORIO_REDACT_MISTRAL=1)
  │
  │ 8. Audit log + emisión eventos pipeline_events
  ▼
SearchResponse {answer, sources, has_silent_conflict, graph_contributed, …}
```

**Latencia p50 actual**: 1983 ms / p95 3053 ms (benchmark.py 50 iter, sesión 10).

---

## Pipeline de ingesta (ACID + bus de eventos)

```
ingest_document(file_path, tenant_id, space_id, source_metadata)
  │
  │ operation_id = new_operation_id()   ← UUID que correlaciona todo el ciclo
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│  FASE 1 — IO externa (sin transacción SQL)                  │
│    preprocessor.py  · MarkItDown + Presidio (whitelist PII) │
│    chunker.py       · 500 tok / 50 overlap                  │
│    embedder.py      · Ollama nomic-embed-text · 768d        │
│    entity_extractor · Mistral structured JSON               │
│      └─ embed batch "subject predicate value" para claims   │
│                                                              │
│  FASE 2 — Dedupe (SELECT)                                   │
│    content_hash existe? → raise DuplicateDocumentError      │
│                                                              │
│  FASE 3 — Escritura ACID (1 sola llamada de red)            │
│    RPC ingest_document_atomic(p_doc, p_chunks, op_id, agent)│
│      INSERT documents                                        │
│      INSERT embeddings × N                                   │
│      INSERT pipeline_events(DOCUMENT_INGESTED)               │
│    Si cualquier paso falla → TODO se revierte               │
│                                                              │
│  FASE 4 — Post-commit: grafo (best-effort + cola retry)     │
│    graph_client.sync(claims con embeddings)                  │
│    emit GRAPH_SYNCED | GRAPH_SYNC_FAILED + graph_sync_queue │
│                                                              │
│  FASE 5 — Post-commit: detección de conflictos              │
│    conflict_detector.detect_and_resolve(...)                 │
│    Orden de aplicación:                                     │
│      0) is_chunk_contradiction() LLM  ← filtra falsos pos.  │
│      1) find_applicable_policy()      ← Regla 4 del E3      │
│      2) _decide_by_authority()                              │
│      3) _decide_by_date()                                   │
│      4) → conflict_reviews pending + webhook HITL email     │
│    emit CONFLICT_DETECTED | DOCUMENT_CLEARED                 │
│                                                              │
│  CIERRE — emit CORPUS_UPDATED                                │
└──────────────────────────────────────────────────────────────┘
```

Las 6 reglas del Entregable 3 están materializadas en producción — ver tabla en `docs/AGENTIC-INGESTION.md` §"Cumplimiento de las 6 reglas".

---

## Modelo de datos (Supabase / PostgreSQL + pgvector)

### Tablas core

```sql
tenants          -- empresa cliente (multi-tenancy)
spaces           -- departamento / área de conocimiento
users            -- usuario de la plataforma
user_spaces      -- control de acceso (qué espacios ve cada usuario)
documents        -- documento ingestado (+ source_metadata JSONB · status)
embeddings       -- chunk + vector(768) + chunk_status
                 -- chunk_status ∈ {active, superseded, disputed, inconclusive}
audit_log        -- trazabilidad de queries
waitlist         -- landing teaser leads
```

### Tablas de gobernanza y observabilidad

```sql
conflict_reviews          -- chunks en conflicto + HITL email + escalada
                          -- (reminders_sent, last_reminder_at, timeout_at)
policies                  -- decisiones HITL persistidas como policy reutilizable
                          -- (subject_pattern, decision, times_applied)
pipeline_events           -- bus de eventos · operation_id + event_type + payload
                          -- (DOCUMENT_INGESTED, CONFLICT_DETECTED, GRAPH_SYNCED…)
graph_sync_queue          -- cola retry post-commit FalkorDB
mcp_api_keys              -- SHA-256 + FK users+tenants + soft revoke (Phase 7.3)
n8n_errors                -- errores capturados de workflows (sesión 12+16)
                          -- (reviewed_at, reviewed_by, notes)
```

### Función RPC clave

```sql
-- supabase/migrations/002_search_function.sql + 005 (disputed) + 020 (inconclusive)
CREATE FUNCTION search_embeddings(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  allowed_doc_ids uuid[]
) RETURNS TABLE (id, content, similarity, document_id, chunk_status) ...
```

20 migraciones aplicadas en producción (`supabase/migrations/001…020`).

---

## RLS — Modelo de seguridad

Aislamiento triple: **aplicación** (early binding), **PostgreSQL** (políticas RLS), **FalkorDB** (filtro por `tenant_id` + `allowed_space_ids` en cada query Cypher).

```
query("¿vacaciones?", user_id="doctor-uuid", tenant_id="delos")
  │
  ├─ 1. App: SELECT space_id FROM user_spaces WHERE user_id = ?
  │         → [space_rrhh, space_medico]
  │
  ├─ 2. App: SELECT id FROM documents
  │         WHERE tenant_id = ? AND space_id IN (?, ?)
  │         → [doc-001, doc-003, doc-005]
  │
  ├─ 3. pgvector RPC: WHERE document_id = ANY(allowed_doc_ids)
  │
  ├─ 4. FalkorDB: MATCH (c:Claim {tenant_id: $tid})
  │               WHERE c.space_id IN $allowed_space_ids
  │
  └─ resultado: solo documentos del doctor; nunca Legal ni cross-tenant
```

**Por qué triple capa**: el RLS de Supabase es backstop; el early binding en aplicación es la primera línea y permite construir el contexto RAG sin depender de policies en el hot path. FalkorDB no tiene RLS nativo — replicamos el patrón a nivel de query.

**Hardening adicional (sesión 13a)**: CORS whitelist, `hmac.compare_digest` en admin keys, tenant check en `DELETE /document`, RLS sobre `mcp_api_keys` (migración 015), assert dim 768 al arranque del embedder. Ver `docs/AUDIT-2026-06-14.md`.

---

## Tenants de prueba

### Clínica Delos (`a0000000-0000-0000-0000-000000000001`)

| Usuario | Espacios visibles |
|---|---|
| admin | RRHH + Médico + Legal + Administración |
| doctor | RRHH + Médico |
| staff | solo RRHH |
| slack_rrhh@delos | solo RRHH (service user para canal Slack) |
| slack_medico@delos | solo Médico |
| slack_legal@delos | solo Legal |
| slack_admin@delos | RRHH + Médico + Legal + Administración |

### Despacho Legal García (`b0000000-0000-0000-0000-000000000002`)

| Usuario | Espacios visibles |
|---|---|
| admin | Casos + Fiscal |
| lawyer | solo Casos |

---

## Stack tecnológico

| Componente | Tecnología | Decisión |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama | 768d INMUTABLE, multilingüe, self-hosted |
| Vector store | pgvector en Supabase Pro (Frankfurt) | RLS nativo, GDPR EU |
| Graph store | **FalkorDB** (Redis 8.6.3 + módulo grafo) | Cypher, multi-tenant por propiedad, AOF persistence |
| LLM generación | Mistral API `mistral-small-latest` | ~2.5s, calidad en español, EU |
| LLM extracción | Mistral API `mistral-small-latest` (temp 0.0) | Structured JSON output |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` | ~25s CPU, offline, sin coste marginal |
| Backend API | FastAPI + Uvicorn (Python 3.12) | Async, Swagger en `/docs` |
| MCP framework | `mcp` SDK + `FastMCP` (Anthropic) | Phase 7.3 — transporte HTTP+SSE |
| PII detection | Presidio + spaCy `es_core_news_lg` | Whitelist por entity_type (PERSON, EMAIL, IBAN…) |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Conversión docs | MarkItDown + PyMuPDF | PDF/DOCX/XLSX/HTML → Markdown |
| Automatización | **n8n** v1.x en Docker (`korio-n8n`) | 8 workflows en producción |
| Servidor VPS | Hetzner **CPX32** AMD EPYC-Genoa, Falkenstein/Nuremberg | 4 vCPU / 8 GB / 160 GB SSD · **€17.53/mes max** |

### 8 workflows n8n.korio.es

| # | Workflow | Trigger | Acción |
|---|---|---|---|
| 1 | HITL email | Webhook | Email con 3 botones de resolución HITL |
| 2 | Cron escalada | Schedule daily 09:00 Madrid | POST `/escalate-reviews` |
| 3 | Pipeline event bus | Webhook | Visualización de cada evento del pipeline |
| 4 | Gmail → /upload multi-space | Gmail Trigger label-based | POST `/upload` con channel→space mapping |
| 5 | Drive → /upload multi-space | 4 Drive Triggers (rrhh/medico/legal/admin) | POST `/upload` |
| 6 | Slack /korio → /search | Slash command | ACK + POST `/search` + thread reply |
| 7 | Slack file_shared → /upload | Events API (file_shared) | POST `/upload` · IF 200/409/other |
| 8 | Gestión errores n8n | Error Trigger | Supabase + throttling + Slack DM con botón reviewed |

Cada workflow productivo lleva `errorWorkflow: <N8N_WF_ERRORS>` para captura automática.

---

## Latencias reales (sesión 10, benchmark formal)

| Operación | Mediana | Notas |
|---|---|---|
| Embedding query (Ollama CPU) | ~0.8s | Hetzner CPX32 AMD |
| Vector search pgvector | <0.1s | sin índice ivfflat tras migración 019 (>1000 chunks → reintroducir HNSW) |
| Graph rerank semántico | ~0.05s | RRF k=60 sobre 455 claims embebidos |
| LLM generation Mistral API | ~2.5s | `mistral-small-latest`, retry 429 con backoff |
| **Total RAG end-to-end p50** | **1983 ms** | benchmark formal 50/50 sin errores |
| **Total RAG end-to-end p95** | **3053 ms** | |
| HITL email E2E | ~1s | Workflow n8n |
| Ingesta documento (~6 chunks) | ~6s | embed + ACID INSERT + grafo |

---

## Diagrama de despliegue

```
┌─── Cliente ─────────────────────────────────────────────────────┐
│  Browser / curl / Slack workspace / Claude Desktop (MCP) / n8n  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─── Hetzner CPX32 AMD (Frankfurt) ──────────────────────────────┐
│                                                                  │
│  nginx (TLS Let's Encrypt) ──► korio.es · n8n.korio.es          │
│                                                                  │
│  ┌────────────────────────────┐  ┌──────────────────────────┐   │
│  │ FastAPI + Uvicorn :8000    │  │ docker compose:           │   │
│  │ (systemd: korio-api)       │  │  - korio-ollama :11434    │   │
│  │   ├─ /search · /upload     │  │     nomic-embed-text      │   │
│  │   ├─ /mcp/sse (FastMCP)    │  │     mistral:7b fallback   │   │
│  │   ├─ /admin/errors*        │  │  - korio-falkordb :6379   │   │
│  │   ├─ /escalate-reviews     │  │     AOF everysec          │   │
│  │   ├─ /graph/*              │  │  - korio-n8n :5678        │   │
│  │   └─ /ui · /legal          │  │     8 workflows           │   │
│  │   (OTel → Jaeger :4317)    │  │  - korio-jaeger :16686    │   │
│  └────────────────────────────┘  └──────────────────────────┘   │
│  Trazas RAG → LangSmith (cloud UE) · Trazas HTTP → Jaeger (local)│
└──────────────────────────┬──────────────────────────────────────┘
                           │ Supabase REST API + pgvector
                           ▼
┌─── Supabase Pro (Frankfurt) ──────────────────────────────────┐
│  PostgreSQL + pgvector + RLS policies                          │
│  20 migraciones aplicadas                                      │
│  Tablas: tenants, spaces, users, documents, embeddings,        │
│           audit_log, conflict_reviews, policies,               │
│           pipeline_events, graph_sync_queue, mcp_api_keys,     │
│           n8n_errors, waitlist                                 │
└────────────────────────────────────────────────────────────────┘
                           │ Mistral API
                           ▼
┌─── Mistral AI (cloud · EU) ───────────────────────────────────┐
│  mistral-small-latest · generación + extracción structured JSON│
│  (PII redaction pre-envío con whitelist Presidio)              │
└────────────────────────────────────────────────────────────────┘
```

---

## Observabilidad y evaluación (sesión 18)

Tres capas complementarias, todas **no-op safe** (sin la dependencia o sin la env
activa, el sistema funciona idéntico). Detalle en [`OBSERVABILITY.md`](OBSERVABILITY.md).

| Capa | Tecnología | Qué traza / mide | Hosting |
|---|---|---|---|
| Semántica | **LangSmith** `@traceable` (`src/observability.py`) | árbol `rag-search → ollama-embed / graph-retrieval / mistral-generate`, tokens y coste por llamada LLM | cloud **UE** (GDPR) |
| Infraestructura | **OTel + Jaeger** (`api/otel.py`) | request FastAPI + llamadas `requests` salientes (Mistral/Ollama/Supabase), waterfall de latencia | **self-hosted** VPS |
| Calidad | **RAG eval** LLM-as-judge (`scripts/rag_eval.py`) | relevance / faithfulness / correctness / retrieval-hit sobre `eval_set.json` | local (on-demand) |

**Decisión clave**: LangSmith instrumenta el pipeline RAG **sin LangChain** (Korio
no lo usa para orquestar) vía `@traceable`. OTel exporta OTLP a Jaeger en el propio
VPS → trazas de infraestructura sin salir del servidor. La eval reutiliza `search()`
+ Mistral sin dependencias nuevas (no RAGAS). Activación vía `.env`:
`LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT` (EU obligatorio), `KORIO_OTEL_ENABLED`.

---

## Módulos del código fuente

### Backend

| Fichero | Responsabilidad |
|---|---|
| `api/server.py` | FastAPI con todos los endpoints + middleware MCPAuthASGI |
| `api/mcp_server.py` | FastMCP con 3 tools (search_knowledge_base, list_pending_conflicts, list_spaces) |
| `src/search.py` | Orquestador del pipeline RAG híbrido + reformulación + query-time conflicts |
| `src/ingest.py` | Pipeline de ingesta en 5 fases con RPC ACID |
| `src/embedder.py` | Wrapper Ollama nomic-embed-text + assert dim 768 al arranque |
| `src/chunker.py` | `RecursiveCharacterTextSplitter` |
| `src/preprocessor.py` | MarkItDown + Presidio con whitelist PII |
| `src/llm_client.py` | Mistral API + fallback Ollama + retry 429 + PII redaction |
| `src/db.py` | Supabase client, RLS early binding, audit log |
| `src/conflict_detector.py` | Detección + auto-resolución (policy → autoridad → fecha) |
| `src/escalation.py` | Cron HITL: recordatorios + auto-timeout → `inconclusive` |
| `src/graph_client.py` | Wrapper FalkorDB con RLS multi-tenant + RRF |
| `src/entity_extractor.py` | Mistral structured JSON → entities + claims |
| `src/policies.py` | `find_applicable_policy()` + `save_policy_from_review()` |
| `src/version_extractor.py` | Extrae `version_ts` de filename + contenido (6 heurísticas) |
| `src/agents/{ingestor,detector,arbitrator,supervisor,curator,pipeline}.py` | Fachada agéntica con docstring PEAS (refleja roles E3) |
| `src/agents/events.py` | `emit()` → INSERT pipeline_events + webhook n8n best-effort |

### Tests

| Fichero | Cobertura |
|---|---|
| `tests/test_rls.py` | 10 tests aislamiento RLS multi-tenant/space |
| `tests/test_search.py` | 10 tests RAG + memoria + disputed |
| `tests/test_atomic_ingest.py` | 3 tests ACID incluyendo rollback demostrado |
| `tests/test_pipeline_agentic.py` | 2 tests fachada agéntica + Pipeline |
| `tests/test_query_time_detection.py` | 1 test E2E del Caso extremo del E4 |
| `tests/test_inconclusive_and_policies.py` | 2 tests reglas 4 y 5 del E3 |
| `tests/test_graph_semantic_rerank.py` | 3 tests RRF + RLS + fallback |
| **Total** | **31/31 verdes** (~30s) |

### Scripts operativos

| Script | Uso |
|---|---|
| `scripts/benchmark.py` | Medición p50/p95 con `--delay` configurable |
| `scripts/graph_backfill.py` | Pobló 237 claims sobre 10 docs en 116s |
| `scripts/graph_embed_claims.py` | Embed 455 claims FalkorDB en 23s |
| `scripts/mcp_create_key.py` | Create/list/revoke API keys MCP (plaintext una sola vez) |
| `scripts/demo_snapshot.py` | Save/restore Supabase + FalkorDB para grabación demo |
| `scripts/reembed_strip_frontmatter.py` | Re-embed chunks sin frontmatter YAML (deuda Phase 9) |

---

*Actualizado: 29 junio 2026 · v0.3.16 · sesión 19. Phases 1–7.3 + Phase 9 flecos + observabilidad + corpus saneado. 20 migraciones · 8 workflows · 31/31 tests · p50=1983ms.*
