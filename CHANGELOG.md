# Changelog

Todos los cambios destacables de Korio se registran aquí, siguiendo el formato
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y versionado
semántico [SemVer](https://semver.org/lang/es/).

> Korio aún está en pre-1.0 (TFM). Cambios menores tipo refactor pueden
> aparecer como `0.x.0`. La estabilidad de la API REST pública se garantizará
> al llegar a `1.0.0` (post-defensa, Phase 9 producto SaaS).

## [Unreleased]

## [0.3.11] — 2026-06-18 · sesión 15-15b (Vídeo demo + fixes)

### Added
- **`scripts/reembed_strip_frontmatter.py`** — re-embebe chunks `idx=0` quitando
  frontmatter YAML (title/author/role/date) que diluía el embedding semántico.
  R4 (jornada laboral mínima) pasa de 3º (sim 0.607) a 1º (0.632) en query del guion.
- **Snapshot `pre_demo_v037`** y **`pre_demo_v038`** — 20 docs, 74 chunks,
  1130 nodos, 1818 aristas. v038 incluye chunks re-embebidos sin frontmatter.

### Fixed
- **`src/llm_client.py:_redact_for_mistral`** — whitelist `_PII_ENTITY_TYPES`
  (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, NRP, CREDIT_CARD, IBAN_CODE,
  MEDICAL_LICENSE, ES_NIF, ES_NIE…). Antes redactaba ORG/LOC/MISC →
  `[R4_<REDACTED>]` en citas. Ahora `[R4_convenio-colectivo-sanitario-resumen.md]`.
- **`src/preprocessor.py:anonymize_pii`** — misma whitelist en ingesta. Antes
  generaba chunks con `Dpto. <REDACTED> Recursos Humanos`, `Camisola <REDACTED>`
  visible en preview email HITL. Docs nuevos limpios.
- **`src/search.py:_graph_context`** — eliminado header literal
  `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]` que Mistral echoeba en respuestas.
- **R4 chunks `superseded` → `active`** — falso positivo detector (35h asalariados
  vs 35h médicos residentes, distinto subject). Restaurados ids 185, 186.

### Operational
- **Vídeo demo grabado** (3 actos) durante sesión 15-15b.
- **MCP `mcp-remote@latest`** en Claude Desktop config (antes `0.1.38` con timing bug).
- **Reset post-grabación**: snapshot v038 restaurado + R2 + L3 borrados para
  permitir re-ingesta natural por Gmail/Drive en próxima toma.
- **Aprendizaje Phase 9**: chunker debe excluir frontmatter YAML del texto a embebir.

## [0.3.7] — 2026-06-16 · sesión 14 (Cierre implementación + herramientas demo)

### Added
- **`scripts/demo_snapshot.py`** — save/restore del estado de datos (Supabase +
  FalkorDB) para la grabación del vídeo demo. Snapshot `pre_demo_v036` guardado
  con 18 docs, 63 chunks, 925 nodos grafo, 1475 aristas.
- **27 aristas CONTRADICTS** en grafo de conocimiento: 13 (par resuelto 242↔240) +
  14 (par pendiente 243↔241). Claims manuales insertados para chunk 241 tras fallo
  persistente del LLM (JSON truncado por Mistral).

### Fixed
- **Test `test_busqueda_sin_contexto`** — ajustado para RAG híbrido: el grafo puede
  aportar contexto marginal con keywords genéricas. Solo verifica `chunks_used == 0`.
- **31/31 tests verdes** (antes 30/31 por el test de arriba).

### Operational
- **Implementación cerrada** — a partir de esta versión, sesiones de contenido
  (vídeo demo sesión 15, slide deck sesión 16, memoria TFM en Claude Projects).

## [0.3.6] — 2026-06-16 · sesión 13c (Regla 4 demo + inconclusive en RAR)

### Added
- **Migración 020** — `search_embeddings` RPC incluye `chunk_status = 'inconclusive'`
  en el filtro. Chunks con timeout HITL ahora visibles en el RAG como información
  complementaria con aviso de contradicción pendiente.

### Changed
- **`src/search.py`** — `inconclusive` tratado igual que `disputed`: badge ⚠️ +
  aviso en la respuesta al usuario.
- **`src/db.py`** — `resolve_conflict_review()` acepta `timeout_inconclusive`
  además de `pending`. El admin puede overridear decisiones de timeout.
- **`src/preprocessor.py`** — PyMuPDF (`pymupdf.open()`) como extractor
  principal de PDFs. Mejor calidad que MarkItDown/pdfminer para texto pegado.
- **18 docs demo** expandidos a 550-950 palabras para mayor riqueza semántica.

### Verified
- **Regla 4 (políticas reutilizables)** demostrada en producción: admin resuelve
  R6↔R7 → policy `policy_new_wins` creada → re-ingesta R6+R7 → chunk auto-resuelto
  por policy sin HITL. `times_applied=1`. Las 6 reglas del E3 cerradas con
  evidencia de producción.

## [0.3.5] — 2026-06-15 · sesión 13b (multi-canal real + ivfflat fix + extractor version_ts)

### Added
- **`src/version_extractor.py`** — extracción de `version_ts` desde el documento
  (filename + content) con jerarquía de 6 heurísticas: fecha textual
  día+mes+año, ISO, año aislado en filename, marcador `vN`, léxico
  "actualizada/nueva/revisada", año aislado en content. Antes el detector de
  conflictos siempre comparaba `datetime.now()`, lo que rompía la
  auto-resolución por fecha tras un reset.
- **`data-synthetic/demo-tfm/R6+R7`** — par de docs sin fecha extraíble
  (normativa de uniformes RRHH v1/v2) para activar el caso HITL → `inconclusive`
  (regla 5 del E3).
- **`data-synthetic/demo-tfm/G1-G5`** — 5 docs ficticios del Despacho García
  con casuística propia: dictámenes IRPF 2023↔2025 auto-resueltos por fecha,
  casos laborales/mercantiles, protocolo onboarding.
- **Migración 017** — space `Administración` (id `...004`) en el tenant Delos +
  grant al admin user.
- **Migración 018** — 4 service users Slack (`slack_{rrhh,medico,legal,admin}@delos`)
  con scope por `user_spaces`. El workflow `/korio` mapea `channel_id` →
  service user_id → el RLS del backend hace el resto.

### Changed
- **Workflow Slack `file_shared`** parametrizado. Multi-canal real:
  `#clinica-delos-{rrhh,medico,legal,admin}` → mapping `channel_id → space_id`.
- **Workflow Drive** refactorizado a 4 `googleDriveTrigger` paralelos, uno por
  subcarpeta `input/{rrhh,medico,legal,admin}`. Mapping `parents[0] → space_id`.
- **Workflow Gmail** filtro cambiado a label-based (no `unread`). Idempotencia
  vía `korio/procesado`. Más robusto: el usuario puede abrir el correo en
  Gmail sin romper el pipeline.
- **Workflow `/korio` search** mapea `channel_id` al service user del canal →
  RLS del backend filtra automáticamente por el space del departamento.

### Fixed
- **Migración 016 — `detect_silent_conflicts_among_chunks` solo same-space**.
  Cross-space producía falsos positivos cuando chunks cortos de departamentos
  distintos quedaban próximos en el espacio vectorial (R4 RRHH ↔ M3 Médico
  con sim 0.85). Cross-space no tiene caso funcional en Korio.
- **Migración 019 — DROP `idx_embeddings_vector`** (ivfflat `lists=100`).
  Causa raíz del bug "RPC search devuelve 0 matches tras reset": con 19
  chunks dispersos en 100 listas, `ivfflat.probes=1` solo recorría una →
  encontraba self-match exacto pero ignoraba todos los vecinos. Sin índice el
  planner usa seq scan, trivial con decenas de chunks. Reintroducir en
  Phase 9 con `lists=ceil(sqrt(N))` o HNSW cuando el volumen lo justifique.

### Operational
- 18 docs en producción (13 Delos + 5 García). 5 auto-resoluciones limpias.
  R6/R7 → `inconclusive` (regla 5 demostrada).
- 6 entradas nuevas en Notion troubleshooting.

## [0.3.4] — 2026-06-14 · sesión 13a (hardening de seguridad pre-demo)
### Security
- **N1 — CORS whitelist** (`api/server.py`). Sustituye `allow_origins=["*"]`
  por whitelist explícita (`https://korio.es`, opcional `localhost` si
  `KORIO_ENV=dev`). Métodos y headers explícitos. Nueva env
  `KORIO_EXTRA_CORS_ORIGINS` (lista coma-separada).
- **N2 — `hmac.compare_digest` en admin key** (`api/server.py` `require_admin`).
  Sustituye comparación `!=` por constant-time para evitar timing attacks que
  permitirían descubrir `KORIO_ADMIN_API_KEY` byte a byte.
- **N3 — Tenant check en `DELETE /document/{id}`** (`api/server.py`). Valida
  `doc.tenant_id == KORIO_ADMIN_TENANT_ID` antes de borrar. Defensa en
  profundidad mientras llega OAuth (Phase 8). Si la env no está seteada,
  comportamiento previo (compat atrás).
- **N4 — RLS sobre `mcp_api_keys`** (`supabase/migrations/015_mcp_api_keys_rls.sql`).
  Policies `mcp_keys_self_read` y `mcp_keys_self_update` filtran por
  `user_id = auth.uid()`. Policy `mcp_keys_service_role_all` mantiene acceso
  al backend.

### Changed
- **N5 — Assert dim 768 en arranque del Embedder** (`src/embedder.py`).
  `_check_connection()` hace embedding de prueba y aborta arranque si la
  dimensionalidad no coincide. Defensa contra cambios silenciosos del modelo
  en Ollama (cambiar a 384 corrompería el vector store).
- **N6 — Cleanup blindado de tempfile en `/upload`** (`api/server.py`).
  `tmp_path` se asigna antes de `copyfileobj` (garantiza que `finally` siempre
  pueda limpiarlo). `os.unlink` envuelto en `try/except FileNotFoundError/OSError`
  con log warning, no rompe el request.

### Fixed
- **C2 — Cypher parametrizado en test**
  (`tests/test_graph_semantic_rerank.py`). Sustituye f-strings con `tenant_id`
  en `MATCH/DELETE` de cleanup por parámetros `$tid` del driver FalkorDB.

### Docs
- **`docs/AUDIT-2026-06-14.md`** — anexo de auditoría (21 hallazgos: 4 CRIT,
  3 HIGH, 8 MED, 6 LOW). Mapea cada hallazgo a su destino: cerrado (N1-N6,
  C2), diferido a Phase 8/9, ya planeado en roadmap previo, o aceptado
  consciente. Capítulo memoria TFM *Seguridad y deuda técnica reconocida*.

### Verified in production
- `curl -i -H "Origin: https://evil.test" https://korio.es/health` no devuelve
  `Access-Control-Allow-Origin: *`.
- Admin key inválida → `HTTP 401`.
- `/health` → `status: ok` (3/3 servicios).
- Log de arranque: `✓ Ollama conexión OK (nomic-embed-text, 768 dims)`.

## [0.3.3] — 2026-06-12 · sesión 12 (grafo UI + captura de errores n8n)
### Added
- **Grafo UI: hover/click en sidebar resalta arista CONTRADICTS**
  (`ui/graph.html`, `ui/js/main.js`). `data-from-id`/`data-to-id` en items
  de la sidebar; `highlightContradictionEdge(fromId, toId)` dimea todos los
  nodos/aristas excepto los 2 claims endpoint y su arista. Click bloquea
  highlight, click fuera libera.
- **Captura de errores n8n** (`supabase/migrations/014_n8n_errors.sql`).
  Tabla `n8n_errors` (workflow_id, error_message, error_node, raw_payload
  JSONB, reviewed_at) + 3 índices. Sin RLS (solo service_role).
- **Workflow `Korio - Gestión de errores n8n`** (`KeUTpIk0ycbW1f3g`) —
  Error Trigger → Set (extrae mensaje desde stack) → \[HTTP POST Supabase
  `n8n_errors` + Slack DM al admin con Block Kit\]. `errorWorkflow`
  aplicado a los 7 workflows de producción.

### Fixed
- **Banner disputed calibrado** (`src/search.py`). Nuevo umbral
  `KORIO_DISPUTED_BANNER_MIN_SIM=0.6` (env): el banner ⚠️ solo aparece si la
  similitud del chunk en disputa supera el umbral. Elimina falsos positivos
  en queries no relacionadas.
- **Aristas CONTRADICTS invisibles en el grafo UI** (`src/graph_client.py`
  `get_tenant_subgraph()`). Antes el `LIMIT 300` podía excluir nodos endpoint
  de aristas CONTRADICTS. Solución: query secundaria `id(n) IN [list]`
  rescata los nodos prioritarios fuera del LIMIT.
- **Scale "enganchado" tras hover en el grafo**. `DataSet.update()` no puede
  resetear propiedades anidadas (font.bold, size). Solución definitiva:
  `data.nodes.clear() + data.nodes.add(canonicalGraph.nodes con posiciones
  preservadas)`. Clona estado canónico inmutable al renderizar.

### Verified in production
- 2 filas reales en `n8n_errors` (error `channel_not_found` del workflow
  Slack `/korio` capturado).
- 8 workflows n8n activos.

## [0.3.2] — 2026-06-12 · sesión 11 (cierre de programación)
### Added
- **Rerank semántico del grafo de conocimiento** — Phase 8 cerrada.
  `src/graph_client.py` añade `find_claims_semantic(tenant_id,
  query_embedding, allowed_space_ids, top_k)` que scan + cosine similarity
  sobre los Claims con embedding guardado. `upsert_claim()` acepta
  `embedding: Optional[List[float]]`. `src/ingest.py` embeda el texto
  `"subject predicate value"` en batch al ingestar. `src/search.py`
  `_graph_context()` ejecuta léxico + semántico en paralelo y combina
  rankings con **Reciprocal Rank Fusion** (k=60), top-8 final.
  Coste query-time: cero llamadas extra (reutiliza el embedding de la
  query). Habilita queries muy rephrasadas como *"¿cuánto se trabaja a la
  semana como mínimo?"* que el léxico no atrapaba pero el grafo aporta
  "35 horas" sin problema.
- **`scripts/graph_embed_claims.py`** — backfill one-shot batch=16.
  Ejecutado en producción: **455 claims embedidos en 23 s** (~20 claims/s).
- **`tests/test_graph_semantic_rerank.py`** — 3 tests (ordering por cosine,
  RLS, claims sin embedding). **3/3 verdes en VPS**.
- **Modelo fallback LLM en Ollama VPS** — `mistral:7b-instruct-q4_K_M`
  descargado (4.4 GB). Activado automáticamente por `LLMClient` cuando
  `MISTRAL_API_KEY` no está disponible. Blinda contra rate-limit Mistral.

### Verified in production
- Query del hito TFM *"¿cuántas horas semanales mínimas exige la política?"*
  → respuesta correcta con `graph_contributed=true` en 1772 ms.
- Query MUY rephrasada *"¿cuánto se trabaja a la semana como mínimo?"*
  (sin "política" ni "jornada") → respuesta correcta con citas en 1384 ms.

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
