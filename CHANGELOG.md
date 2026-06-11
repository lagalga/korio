# Changelog

Todos los cambios destacables de Korio se registran aquí, siguiendo el formato
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado
semántico [SemVer](https://semver.org/lang/es/).

> Korio aún está en pre-1.0 (TFM). Cambios menores tipo refactor pueden
> aparecer como `0.x.0`. La estabilidad de la API REST pública se garantizará
> al llegar a `1.0.0` (post-defensa, Phase 9 producto SaaS).

## [Unreleased]

## [0.2.0] — 2026-06-11 · sesión 6
### Added
- **Bus de eventos del pipeline multi-agente** (`pipeline_events`, migración 011).
  Cada transición lógica (`Ingestor → Detector → Arbitrator → Supervisor → Curator`)
  emite un evento con `operation_id` UUID que correlaciona todo el ciclo.
- **`src/agents/events.py`** con `emit()`, `new_operation_id()`, `trace()` y enums
  `EventType` + `Agent`. INSERT a `pipeline_events` síncrono + webhook a n8n
  best-effort (env `KORIO_EVENT_WEBHOOK_URL`).
- **`graph_sync_queue`** — cola de retry para sync con FalkorDB post-commit.
  El corpus Postgres queda siempre consistente; el grafo eventualmente
  alcanza el mismo estado vía n8n worker.
- **`tests/test_atomic_ingest.py`** con 3 tests verdes (happy path,
  deduplicación, rollback ACID del RPC ante fallo a mitad).

### Changed
- **Pipeline de ingesta es ACID** (responde al feedback del profesor del Entregable 4
  del TFM). Toda la escritura — `documents` + `embeddings` + evento
  `DOCUMENT_INGESTED` — sucede en una sola transacción PL/pgSQL vía
  `ingest_document_atomic` (migración 011). Si cualquier paso falla, todo se
  revierte. Las llamadas a APIs externas (Ollama, Mistral) se hacen ANTES de
  invocar la función, así no atan conexiones de la pool ni pueden corromper
  el estado.
- `src/ingest.py` reorganizado en 5 fases claras: IO externa → dedupe → RPC
  atómico → sync grafo post-commit (con cola) → detección de conflictos.
- `ingest_document()` ahora devuelve `operation_id` en el dict de resultado
  para trazabilidad end-to-end.

### Documentation
- `docs/AGENTIC-INGESTION.md` — capítulo memoria TFM: cierre del feedback del
  profesor + comparativa con el sistema multiagéntico del Entregable 3/4
  (microservicios en LangFlow vs roles lógicos en Python).

## [0.1.0] — 2026-06-11 · sesiones 1-5
### Added
- **Phases 1-2** — pipeline RAG vectorial con multi-tenancy real (RLS Supabase
  + early binding en aplicación), 2 tenants sintéticos (Clínica Delos + Despacho
  García), 20/20 tests verdes.
- **Phase 3** — documentación técnica (ARCHITECTURE, DEPLOYMENT, ROADMAP).
- **Phase 4** — chat UI web vanilla con upload, selector tenant/usuario, toggle
  fuentes, markdown. `scripts/benchmark.py`.
- **Phase 5** — producción en `korio.es` (Hetzner CX32), gobernanza activa
  con tres estados de chunk (`active` / `superseded` / `disputed`), HITL email
  vía n8n con botones de acción. Landing teaser con waitlist.
- **Phase 6** — cron de escalada HITL (recordatorios 3/7/14 días + auto-cierre
  21 días). Workflow n8n Schedule Trigger diario 09:00 Madrid.
- **Phase 7.1** — grafo de conocimiento con FalkorDB, sync en tiempo real, 3
  puntos de acceso desde la UI. Hito TFM "¿cuántas horas semanales mínimas?"
  resuelto vía claims `subject → predicate → value`.
- **Phase 7.2** — ingesta automática multi-canal: workflows n8n para
  Gmail/Drive/Slack con `source_metadata` JSONB en `documents`. Endpoint admin
  `DELETE /document/{id}` con cascada Postgres + FalkorDB.
- **Phase 7.3 — MCP Server** (`korio.es/mcp/sse`): FastMCP con 3 tools
  (`search_knowledge_base`, `list_pending_conflicts`, `list_spaces`), auth
  por API key `X-Korio-MCP-Key` (SHA-256 en `mcp_api_keys`, migración 010),
  middleware ASGI puro compatible con SSE, cliente Claude Desktop vía
  `mcp-remote` (Node 20+).
- **Memoria de chat multi-turn** — `state.conversation` en frontend, query
  reformulation vía LLM antes del embedding.

### Fixed
- `BaseHTTPMiddleware` rompe streams SSE. Sustituido por middleware ASGI puro
  `MCPAuthASGI` envolviendo solo el sub-app `/mcp`.
- Anti-DNS-rebinding del SDK MCP: añadido `TransportSecuritySettings` con
  `allowed_hosts=[korio.es, www.korio.es, 127.0.0.1, localhost]`.
- `list_spaces` -32602: añadido parámetro `include_inactive` dummy para que
  FastMCP serialice schema con ≥1 param.
- Grafo ignorado por el LLM: el bloque `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]`
  se inyectaba FUERA del `CONTEXTO:`. Ahora `build_rag_prompt(graph_context=...)`
  lo mete DENTRO; system_prompt declara que chunks + grafo son válidos.
- Retrieval del grafo saturado por subject genérico: `find_claims_by_predicate`
  LIMIT 20 → 50 + rerank en Python `score = 3·predicate + 2·value + 1·subject`
  por keyword.
- CONTRADICTS falsos positivos en el grafo: Cypher exige `subject` igual o
  substring containment.
