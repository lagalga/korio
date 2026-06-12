# Changelog

Todos los cambios destacables de Korio se registran aquí, siguiendo el formato
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado
semántico [SemVer](https://semver.org/lang/es/).

> Korio aún está en pre-1.0 (TFM). Cambios menores tipo refactor pueden
> aparecer como `0.x.0`. La estabilidad de la API REST pública se garantizará
> al llegar a `1.0.0` (post-defensa, Phase 9 producto SaaS).

## [Unreleased]

## [0.3.1] — 2026-06-12 · sesión 10
### Added
- **Validación semántica de aristas CONTRADICTS** (`src/llm_client.py`,
  `src/graph_client.py`, `scripts/graph_backfill.py`). Nuevo método
  `LLMClient.is_semantic_contradiction(sA, pA, vA, sB, pB, vB)` — llama a
  Mistral (temp=0, max_tokens=5) para decidir SÍ/NO si dos claims son
  realmente incompatibles. `link_contradictions_between_chunks()` elimina el
  filtro CONTAINS de subject (demasiado estricto → 0 aristas) y valida
  semánticamente cada par candidato antes de crear la arista MERGE. Resultado:
  2 aristas CONTRADICTS válidas en Delos (vs 0 previas).
- **FalkorDB AOF persistence** — `REDIS_ARGS=--appendonly yes --appendfsync
  everysec --save 60 1` en `docker-compose.yml`. El grafo sobrevive reinicios
  del contenedor sin pérdida de datos.
- **`--delay / -d` en benchmark** (`scripts/benchmark.py`). Pausa configurable
  entre iteraciones para evitar rate-limit de Mistral en runs largos (ej.
  `--delay 1.5`).

### Changed
- **Threshold de búsqueda 0.4 → 0.35** (`src/search.py`, `api/server.py`).
  Mejora recall en queries abiertas sin regresiones de precisión evidentes.
- **Threshold query-time conflict 0.85 → 0.80** (`KORIO_QUERY_TIME_CONFLICT_THRESHOLD`
  en VPS `.env`). La similitud real entre chunks de versiones distintas de la
  política de vacaciones era 0.8253; con 0.85 no se detectaba.

### Fixed
- **Retry Mistral 429** en `_generate_mistral()` — backoff exponencial (1s/2s/4s),
  máximo 3 intentos. Evita errores 500 en cascada durante el benchmark.
- **Import flexible `LLMClient` en `graph_client.py`** — `try/except
  ModuleNotFoundError` permite cargar el módulo tanto desde la raíz del
  proyecto (vía `server.py`) como desde `scripts/` (que añaden `src/` al
  `sys.path` directamente).

### QA
- **QA E2E 10/10** — los 10 escenarios definidos (vectorial, grafo, multi-turn,
  RLS, disputed, query-time, MCP×2, ingesta Gmail, bus eventos) superados sin
  regresiones.
- **Benchmark formal 50/50 queries** — p50 global 1983 ms, p95 3053 ms,
  0 errores (con `--delay 1.5`).

## [0.3.0] — 2026-06-11 · sesiones 7-9
### Added
- **Workflow n8n `Korio · Pipeline event bus`** (sesión 7) consumiendo
  `KORIO_EVENT_WEBHOOK_URL`. Cada `emit()` del backend produce una ejecución
  visible con emoji + summary (`📥 Ingestor → DOCUMENT_INGESTED (op …)`).
  Activo en `n8n.korio.es`.
- **Fachada agéntica `src/agents/{base, ingestor, detector, arbitrator,
  supervisor, curator, pipeline}.py`** (sesión 7). Refleja 1:1 los 5 roles
  del Entregable 3 con documentación PEAS por agente. `Pipeline(tenant_id)
  .run_ingest(...)` es el punto de entrada de alto nivel.
- **Detección de conflictos en query-time** (sesión 8). Migración 012 con
  función `detect_silent_conflicts_among_chunks(BIGINT[], FLOAT)`. Cuando
  `/search` recupera ≥2 chunks de docs distintos con sim ≥0.85 (env
  `KORIO_QUERY_TIME_CONFLICT_THRESHOLD`), emite `CONFLICT_DETECTED` con
  `triggered_by: query_time` y avisa al usuario en la respuesta.
- **Estado terminal `inconclusive`** (sesión 9). Migración 013. Tras
  timeout HITL (21 días sin respuesta), los chunks pasan a `inconclusive`,
  excluidos del RAG hasta intervención manual. Más conservador que el
  comportamiento previo (`timeout_kept_both`). Cumple Regla 5 del E3.
- **Políticas reutilizables** (sesión 9). Tabla `policies` con
  `subject_pattern`, `decision`, `times_applied`. Cada decisión HITL del
  admin se persiste como policy reutilizable. El detector consulta
  `policies` ANTES de evaluar fecha/autoridad. Cumple Regla 4 del E3.

### Changed
- `_apply_timeout` (escalation.py) → `timeout_inconclusive` por defecto.
  Comportamiento legacy disponible con env `KORIO_TIMEOUT_KEEP_BOTH=1`.
- `ConflictReport` añade contador `policy_resolved`.
- `SearchResponse` añade `has_silent_conflict`, `silent_conflicts`,
  `query_time_threshold`. El servidor MCP también los propaga; las
  `instructions` de FastMCP instruyen a Claude Desktop a añadir un párrafo
  "⚠️ Aviso de la gobernanza:" cuando aplique.
- `version` API 0.2.0 → 0.3.0.

### Documentation
- `docs/AGENTIC-INGESTION.md` actualizado con sección "Cumplimiento de las
  6 Reglas del E3" — argumenta para defensa que las 6 están materializadas.

### Tests
- 8/8 verdes acumulados: 3 atomicidad ACID + 2 fachada agéntica + 1
  query-time E2E + 2 inconclusive/policies.

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
