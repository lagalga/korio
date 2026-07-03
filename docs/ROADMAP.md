# Korio — Roadmap

> **Estado: v0.3.16 (29 jun 2026) · 🏁 Implementación cerrada · Corpus saneado · Observabilidad en producción**
> Defensa TFM: 9 julio 2026

---

## Resumen ejecutivo

Korio cubre **6 phases técnicas cerradas** (núcleo RAG, multi-tenancy, producción + gobernanza activa, cron HITL, grafo de conocimiento, ingesta multi-canal, MCP server) más **v0.3.0 con las 6 reglas del Entregable 3 materializadas** (pipeline ACID + bus de eventos + query-time + policies + inconclusive), **v0.3.12 con los flecos operativos de Phase 9** (throttling errores, panel admin, Slack interactivity), **v0.3.13 con evaluación cuantitativa del detector (P/R/F1 = 1.0 sobre n=12) + fix bug frontmatter en preprocessor** y **v0.3.15 con observabilidad y evaluación en producción** (LangSmith @traceable, OTel+Jaeger, RAG eval LLM-as-judge — ver `docs/OBSERVABILITY.md`).

**Roadmap restante hasta defensa (9 julio):**

| Tarea | Estado | Herramienta |
|---|---|---|
| Vídeo demo grabado | ✅ sesión 15 + 15b | — |
| Slide deck (10-15 slides) | 🔲 | Claude Projects (chat) |
| Memoria TFM (negocio + técnico + research) | 🔲 | Claude Projects (chat) |
| Ensayo defensa | 🔲 | — |
| Flecos de implementación post-TFM | open backlog | Claude Code |

**Phases post-TFM** (8, 9 SaaS, 10) tienen diseño documentado en `docs/MULTI-TENANT-INGESTION.md`, `docs/CHAT-PIPELINE-GUARDRAILS.md` y `docs/PHASE-10-MULTIMODAL-INGESTION.md`. No se ejecutarán antes de la defensa.

---

## Estado actual — Phases cerradas

### Phase 1–2 · Núcleo RAG y multi-tenancy ✅

| Feature | Estado |
|---|---|
| Pipeline ingesta (MarkItDown → Presidio → Chunking → pgvector) | ✅ |
| Pipeline RAG (Query → Embed → RLS → pgvector → Mistral) | ✅ |
| FastAPI server | ✅ |
| Multi-tenancy real (RLS Supabase + early binding) | ✅ |
| 2 tenants con datos sintéticos (Delos + García) | ✅ |
| Mistral API + Ollama fallback | ✅ |

### Phase 3–4 · Documentación + UI ✅

| Feature | Estado |
|---|---|
| `docs/ARCHITECTURE.md` · `docs/DEPLOYMENT.md` · `docs/ROADMAP.md` | ✅ |
| Chat UI web (`ui/`) | ✅ |
| `POST /upload` ingesta desde navegador | ✅ |
| `scripts/benchmark.py` | ✅ |

### Phase 5 · Producción + Gobernanza activa + HITL email ✅

- VPS Hetzner CPX32 AMD · nginx + TLS · systemd `korio-api`
- n8n en Docker (`korio-n8n`)
- Detección conflictos por similitud + auto-resolución (fecha/autoridad)
- Estados `active` / `superseded` / `disputed`
- HITL email con 3 botones de acción + token firmado
- `tenants.admin_email` configurable
- Landing teaser + waitlist

### Phase 6 · Cron escalada HITL ✅

- Migración 008: `reminders_sent`, `last_reminder_at`, `timeout_at`
- `src/escalation.py` con cadencia 3/7/14 + timeout 21 (parametrizable)
- Workflow n8n Schedule Trigger diario 09:00 Madrid
- Email template adaptativo (initial / reminder / timeout)

### Phase 7.1 · Grafo de conocimiento ✅

- FalkorDB (Redis + Cypher) con AOF persistence
- `src/graph_client.py` con schema multi-tenant
- `src/entity_extractor.py` con Mistral structured JSON
- `scripts/graph_backfill.py` — 237 claims sobre 10 docs en 116s
- Search híbrido vector + grafo
- UI `/ui/graph.html` con vis-network
- Hito demo: query rephrase "jornada mínima" → 35h/semana vía grafo

### Phase 7.2 · Ingesta automática multi-canal ✅

- Migración 009: `documents.source_metadata` JSONB
- `DELETE /document/{id}` admin con cascade Postgres + FalkorDB cleanup
- 8 workflows n8n en producción (ver `docs/ARCHITECTURE.md`)
- Mapping `channel_id → space_id` por workflow (Slack file_shared, /korio, Gmail label, Drive subfolders)

### Phase 7.3 · MCP Server ✅

- Migración 010 `mcp_api_keys` (SHA-256, FK users+tenants, soft revoke)
- `api/mcp_server.py` FastMCP con 3 tools
- `MCPAuthASGI` puro (compat con SSE)
- `scripts/mcp_create_key.py` CLI
- Claude Desktop conectado vía `mcp-remote@latest`
- Detalle: `docs/MCP-SERVER.md`

### v0.3.0 · Cumplimiento E3/E4 ✅

- Migración 011: `pipeline_events` + RPC `ingest_document_atomic` (ACID)
- Migración 012: RPC `detect_silent_conflicts_among_chunks` (Caso extremo E4)
- Migración 013: estado `inconclusive` + tabla `policies` (Reglas 4 y 5)
- Fachada agéntica `src/agents/*` con docstring PEAS
- Workflow `Korio · Pipeline event bus`
- **Las 6 reglas del E3 materializadas con evidencia en producción** — ver `docs/AGENTIC-INGESTION.md` §"Cumplimiento de las 6 reglas".

### v0.3.4 · Hardening de seguridad pre-demo ✅

- CORS whitelist (N1) · `hmac.compare_digest` (N2) · cross-tenant DELETE check (N3) · RLS sobre `mcp_api_keys` migración 015 (N4) · assert dim 768 al arranque (N5) · cleanup blindado tempfile (N6) · Cypher parametrizado (C2)
- Auditoría completa con 21 hallazgos catalogados — ver `docs/AUDIT-2026-06-14.md`

### v0.3.5 · QA multi-canal real + ivfflat fix ✅ (sesión 13b)

- 18 docs reales (Delos + García) + space `Administración` + 4 service users Slack
- Migración 016: silent conflicts SAME-space only
- Migración 017–018: space Administración + service users Slack
- **Migración 019: DROP `idx_embeddings_vector`** (probes=1 bug con <100 chunks)

### v0.3.6 · Regla 4 demo + inconclusive en RAG ✅ (sesión 13c)

- Demo end-to-end de Regla 4 con policy `policy_new_wins` aplicada automáticamente
- Migración 020: search incluye `inconclusive` con badge ⚠️
- `src/db.py` acepta override `timeout_inconclusive`

### v0.3.7 · Cierre implementación + herramientas demo ✅ (sesión 14)

- 27 aristas CONTRADICTS válidas en grafo (validación semántica LLM)
- `scripts/demo_snapshot.py` save/restore Supabase + FalkorDB
- Snapshot `pre_demo_v036` guardado

### v0.3.8 · Compliance AI Act + GDPR ✅ (sesión 14b)

- Fix crítico Presidio API
- Redacción PII pre-Mistral cloud
- Privacy Policy desplegada en `korio.es/legal/privacy.html`
- Detalle: `docs/COMPLIANCE-AI-ACT-GDPR.md`

### v0.3.9 · Fix restore grafo FalkorDB ✅ (sesión 14c)

- `CREATE (n:L $props)` con parámetros NO soportado por FalkorDB. Cambio a `CREATE (n:L) SET n = $props`.

### v0.3.10 / v0.3.11 · Fixes pre-vídeo + vídeo grabado ✅ (sesión 15 + 15b)

- MCP `mcp-remote@latest` (bug timing en 0.1.38)
- R4 chunks `superseded` falso positivo restaurados
- PII whitelist Mistral (no garblea filenames)
- Fix grafo header echoeado por Mistral
- `scripts/reembed_strip_frontmatter.py` — chunks `idx=0` sin frontmatter (R4 sube de 3º a 1º)
- Whitelist PII en preprocessor ingesta
- Snapshots `pre_demo_v037` + `pre_demo_v038`

### v0.3.12 · Phase 9 flecos errores n8n + Slack duplicate UX ✅ (sesión 16)

| Tarea | Sesión | Notas |
|---|---|---|
| Throttling anti-spam Slack DM errores | 16a | Code node `count===1 || count%10===0` en workflow `<N8N_WF_ERRORS>` |
| Panel UI `/admin/errors` con admin key | 16b | `ui/admin-errors.html` + `GET /admin/errors` + `POST /admin/errors/{id}/review` |
| Botón "✅ Marcar reviewed" en Slack DM | 16b | `POST /admin/errors/slack-action` con firma `v0:ts:body` + anti-replay 5 min |
| Workflow Slack file_shared: duplicate → DM thread | 16c | IF 200 / 409 / other; 409 ya no dispara `errorWorkflow` |
| Verificación E2E real | 16b | Click usuario → BD actualizada en 14s, `reviewed_by: slack:U…` |

### v0.3.14 · Promoción HITL chunk→doc + fixes restore demo ✅ (sesión 17c)

| Tarea | Notas |
|---|---|
| **Fix `scripts/demo_snapshot.py`**: clean `policies` table en restore | Tabla `policies` tiene PK bigint, no UUID. DELETE con placeholder UUID fallaba silencioso → policies viejas (e.g. `policy_new_wins` de sesión previa) sobrevivían al restore y auto-resolvían el conflicto L3↔L2 sin generar email HITL |
| **`CONFLICT_THRESHOLD` 0.78 → 0.80** en `src/conflict_detector.py` | Evita falso positivo L1↔L3 (sim 0.7936) que disparaba `auto_existing_wins` porque L1.version_ts ≈ `datetime.now()` (sin fecha extraíble del cuerpo) → `date_diff = 823 días` → L3 superseded sin HITL |
| **Nuevo `db.promote_to_document_replacement()`** + integración en `/review/{id}` | Cuando admin resuelve ≥N `approved_new` entre `(new_doc, existing_doc)`, supersede los chunks restantes del `existing_doc`. Variable `KORIO_DOC_REPLACEMENT_MIN_APPROVALS` (default 2). Promoción coherente con Regla 4 (aprender de decisiones repetidas). Resuelve fricción demo: tras aprobar HITL L3 vs L2 c0/c2, los chunks L2 c1/c3/c4 sin review propio seguían `active` y leaqueaban "5 años" al RAG junto al "10 años" de L3 |
| Snapshot `pre_demo_v040` post-fix | 19 docs, 69 chunks, L2 entero superseded, 5 reviews (3 `pending` R-uniformes + 2 `approved_new` L3→L2), 5 policies, 1179 nodos / 1951 aristas |

### v0.3.15 · Observabilidad y Evaluación ✅ (sesión 18)

| Tarea | Notas |
|---|---|
| **LangSmith `@traceable`** (capa semántica) | `src/observability.py` no-op-safe + `record_llm_usage()` (tokens→coste). Spans: rag-search, reformulate-query, ollama-embed, graph-retrieval, mistral/ollama-generate. Región UE obligatoria (403 en US). GDPR: trazas residentes UE |
| **OTel + Jaeger** (capa infraestructura) | `api/otel.py` opt-in instrumenta FastAPI + requests, OTLP→Jaeger. Servicio `jaeger` en docker-compose (16686/4317, solo localhost). Self-hosted = GDPR total |
| **RAG eval LLM-as-judge** (capa calidad) | `scripts/rag_eval.py` + `eval_set.json`. Métricas relevance/faithfulness/correctness/retrieval-hit/latency. Casos NO_ANSWER anti-alucinación. Cero deps nuevas |
| Capítulo memoria TFM | `docs/OBSERVABILITY.md`: arquitectura 3 capas + decisiones + comparativa + troubleshooting real |
| 3 commits a `main` | `639958c` LangSmith · `92db0b3` OTel/Jaeger · `67c99ba` RAG eval |

### v0.3.16 · Saneo corpus + validación semántica detector ✅ (sesión 19)

| Tarea | Notas |
|---|---|
| **`is_chunk_contradiction()`** en `llm_client.py` | Validación semántica a nivel de chunk (temp=0, trunca 800 chars, conservador si falla) |
| **Paso 0 en `conflict_detector.py`** | Pre-filtro LLM antes de policies/fecha/autoridad. Env `KORIO_CONFLICT_SEMANTIC_VALIDATION=1` (default) |
| Confirmación frontmatter strip OK | `preprocessor.py` ya stripea YAML desde v0.3.13 |
| Model Pricing LangSmith | `record_llm_usage()` ya emite tokens → columna Cost poblada. Tachado de pendientes |
| Test E2E G1↔G2 García | Re-ingesta G2 → 0 conflictos (sim <0.80 sin frontmatter). Validación semántica como respaldo |
| 1 commit a `main` | `fd52462` |

### v0.3.13 · Evaluación cuantitativa detector + fix frontmatter ✅ (sesión 17 + 17b)

| Tarea | Sesión | Notas |
|---|---|---|
| Corpus eval-specific (12 docs sintéticos) | 17 | `data-synthetic/eval-corpus/` 6P + 6N · misma fecha/autoridad fuerza `pending` |
| Métricas P/R/F1 sobre ground truth | 17 | Precision 1.000 · Recall 1.000 · F1 1.000 (n=12) |
| Script `evaluate_detector.py` doble fuente | 17 | Reconcilia aristas CONTRADICTS FalkorDB + filas `conflict_reviews` Postgres |
| Análisis FP cross-tema (`inspect_surprises.py`) | 17 | 5 FP / 54 pares no-anotados · causa: `chunk_index=0` solo frontmatter YAML |
| **Fix `src/preprocessor.py`**: stripping frontmatter pre-chunking | 17b | `extract_frontmatter()` parsea YAML a metadata · body limpio al chunker |
| `src/version_extractor.py` prioriza `signed_date` del frontmatter | 17b | Acepta `datetime`/`date`/string ISO · retro-compatible |
| Verificación E2E + 28/28 tests verdes | 17b | Doc subido → `chunk_index=0` sin YAML · `version_ts` del frontmatter |
| Slide 9 defensa con números reales | 17 | Texto + notas presentador maquetados directamente en Keynote |

---

## Backlog · Flecos pendientes post-implementación

### No bloqueantes para defensa (Phase 9 deuda menor)

| Tarea | Impacto | Esfuerzo |
|---|---|---|
| ~~Validación semántica LLM en detector de ingesta~~ | ✅ **Cerrado v0.3.16** (`is_chunk_contradiction` en `llm_client.py`) | — |
| ~~Chunker excluir frontmatter YAML del embedding~~ | ✅ **Cerrado v0.3.13 (commit `62cae8f`)** | — |
| Reintroducir índice vectorial cuando >1000 chunks | HNSW o `ivfflat lists=ceil(sqrt(N))` con probes calibradas | 2-3h |

### Operativa contenido TFM

| Tarea | Estado | Herramienta |
|---|---|---|
| Slide deck (10-15 slides) | 🔲 | Claude Projects (chat) — fuera de Claude Code |
| Memoria TFM (negocio + técnico + research entrevistas) | 🔲 | Claude Projects (chat) — fuera de Claude Code |
| Ensayo defensa cronometrado | 🔲 | — |

---

## Phases post-TFM

Alineado con el capítulo 5.5 "Futuras líneas de investigación o desarrollo" de
la memoria TFM: 4 phases secuenciales (8/9/10/11) + 3 bloques transversales +
3 líneas de investigación abiertas.

### Phase 8 · SaaS — conectores + worker pool + guardrails + reranker

Primera y más urgente. Convierte el prototipo en producto multi-tenant real.

| Bloque | Descripción | Doc fuente |
|---|---|---|
| **Conectores OAuth multi-tenant** | Gmail, Drive, Slack, Outlook, SharePoint, Dropbox, Teams. Modelo 3 tablas: `tenant_connections`, `tenant_connection_secrets`, `ingestion_rules` (§4.2 memoria + Anexo B.5) | `docs/MULTI-TENANT-INGESTION.md` |
| **Worker pool propio** (Celery o RQ) | Sustituye los 8 workflows n8n hardcodeados. Retries + backoff exponencial + observabilidad fina por `connection_id` | — |
| **Guardrails chat** (Lakera / Rebuff + Presidio egress + rate limit) | Ingress + egress + PII outbound | `docs/CHAT-PIPELINE-GUARDRAILS.md` (Anexo B.9) |
| **Reranker cross-encoder** | Tras fusión RRF, reordena top-10 con modelo especializado. Eleva precisión top-3 en corpus densos | — |
| MCP Server OAuth 2.1 + `mcp_audit_log` + rate limit + Streamable HTTP stateless / sticky sessions | Producción-real MCP multi-worker | — |
| Hallazgos diferidos auditoría 13a (14 issues) | Deuda técnica reconocida | `docs/AUDIT-2026-06-14.md` |

### Phase 9 · Producto SaaS completo — auth + billing + admin + GDPR

Cierra el paso a SaaS con lo que el prototipo aún no expone.

| Feature | Descripción |
|---|---|
| Autenticación real | Supabase Auth (email/password, Google OAuth) |
| Billing por tenant | Stripe |
| Panel administrativo de conflictos para cliente final | Alternativa visual al email HITL (`/ui/admin/conflicts`) |
| Endpoints RGPD Art. 20 + Art. 15 | `/export/{tenant_id}` + `/subject-access/{user_id}` |
| Matriz de autoridad configurable en onboarding | UI para `authority_weight` por space y source_type |
| API keys por tenant | Integrar Korio desde otras apps |
| Límites de plan | Chunks / queries-mes / usuarios |
| Persistencia chat por usuario + reflejo Slack ↔ web | Cross-device y cross-canal |
| ROPA + admin dashboard audit-log | `docs/COMPLIANCE-AI-ACT-GDPR.md` |

Ya cerrados dentro del TFM (flecos operativos Phase 9):

- ✅ Throttling Slack DM errores n8n (s16a)
- ✅ Panel `/admin/errors` UI + endpoints (s16b)
- ✅ Botón Slack "Marcar reviewed" (s16b · firma HMAC + anti-replay)
- ✅ Slack file_shared duplicate → DM thread (s16c)

### Phase 10 · Ingesta multimodal (email body + Slack/Teams threads + audio)

Diseño completo en `docs/PHASE-10-MULTIMODAL-INGESTION.md` (Anexo B.8):

- Email body adapter (parsing local, sin LLM) — hilos completos
- Slack/Teams thread adapter (reaction `📥 korio` ingiere thread completa)
- Audio adapter — **Voxtral** para transcripción de reuniones + **Whisper** local como fallback
- `src/adapters/` con interfaz común + 4 workflows n8n + 3 botones upload UI

Los claims extraídos de un acta de reunión pasan por la misma cadena de
gobernanza activa que los de un PDF — infraestructura E3 se reutiliza sin
cambios.

Escala y GPU (asociado al salto Phase 11):

| Mejora | Impacto | Coste |
|---|---|---|
| GPU dedicada Hetzner (GEX44, RTX 4000 Ada 20GB) | Embed ~0.1s · LLM ~1s | ~€185/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

### Phase 11 · Migración del motor de embeddings

Doc de referencia: **`docs/EMBEDDINGS-DEFENSA-TFM.md`** (dossier defensa +
roadmap detallado §6).

`nomic-embed-text` fue declarado inmutable durante el TFM por gestión de
riesgo: cada cambio obliga a re-embebir corpus completo + recalibrar umbrales
(búsqueda 0.35, conflict 0.80, banner disputed 0.60, CONTRADICTS 0.85,
silent_conflict 0.80). Post-defensa se planifica en dos pasos:

| Paso | Modelo | Ventana temporal | Cambio | Coste extra |
|---|---|---|---|---|
| Corto plazo | `multilingual-e5-large-instruct` (MIT) | ~3 meses post-MVP | Trivial: prefijos `"query: "` / `"passage: "` en `src/embedder.py` + `ALTER TABLE` a 1024d + re-embed | ~0 (mismo CPU / GPU modesta) |
| Medio plazo | `BGE-M3` (MIT, dense + sparse + ColBERT nativo, 8k ctx) | 6–12 meses (con clientes de pago) | Refactor retrieval: retira parte del RRF léxico manual (sparse output de BGE-M3 cubre ese rol) | GPU dedicada ~€185/mes — amortizable con 5-6 clientes a €40/mes |

Descartados por soberanía + RGPD: **OpenAI text-embedding-3, Voyage AI,
Cohere embed-v3**. Contradicen el discurso comercial ("tu conocimiento no
sale de tu VPS") y exigen DPA + transferencia internacional.

---

## Bloques transversales al roadmap

Acompañan a las 4 phases sin bloquear su secuencia.

| Bloque | Descripción | Ventana |
|---|---|---|
| **Bias audit AI Act Art. 15** | Corpus RRHH con métricas de disparidad demográfica. Script esbozado en `docs/COMPLIANCE-AI-ACT-GDPR.md` | 2 semanas post-defensa |
| **DPA formal con Mistral** | Imprescindible antes del lanzamiento comercial | Bloqueado por proveedor |
| **Documentación técnica AI Act Art. 11 + Anexo IV** | Consolidar los 9 docs del Anexo B según el índice concreto del Anexo IV | Pre-lanzamiento comercial |

---

## Líneas de investigación abiertas

Preguntas empíricas que el prototipo deja para trabajos futuros.

1. **Evaluación cuantitativa aportación del grafo sobre corpus reales grandes.**
   El caso `jornada mínima → 35h` es contundente en el prototipo. La ganancia
   agregada del RAG híbrido vs RAG vainilla sobre decenas de miles de chunks y
   miles de consultas reales no se ha medido — pregunta empírica más
   interesante que Korio deja abierta.
2. **Aprendizaje activo del clasificador de conflictos.**
   `times_applied` mide reutilización de policies, no mejora del detector.
   Explorar si las decisiones humanas registradas en `audit_log` pueden
   alimentar un fine-tuning incremental del paso 0 semántico
   (`is_chunk_contradiction`) — vía natural para llevar el detector de
   laboratorio a producción real.
3. **Medición de deriva semántica del corpus.**
   Monitorizar cómo evoluciona la distribución de embeddings a medida que se
   ingieren nuevos documentos: detectar cuándo el conocimiento almacenado se
   aleja del vigente o cuándo los umbrales calibrados (búsqueda 0.35 /
   conflict 0.80) dejan de ser válidos. Encaja en la capa de métricas
   agregadas prevista (Prometheus + Grafana) como indicador de salud del
   corpus complementario a la gobernanza activa.

---

## Métricas y stack (1 jul 2026 · v0.3.16 · snapshot `pre_saneo_s19`)

Fuente: anexo J memoria TFM ("Métricas y evaluación"). Ejecución **secuencial**
en VPS Hetzner CPX32 (4 vCPU / 8 GB) contra `https://korio.es`.

### Tests

| Suite | Passed | Total | Notas |
|---|---|---|---|
| `pytest tests/ -v` | **31** | **31** | 30.97 s (rediseñado `test_policy_reutilizable_evita_hitl_segundo_conflicto` tras v0.3.16 para reflejar validación semántica LLM como paso 0) |

### Benchmark de latencia (50 iter × 5 escenarios = 250 queries, 248 efectivas)

| Métrica | p50 | p95 | p99 |
|---|---|---|---|
| Wall-clock HTTP | **1 715 ms** | **4 413 ms** | **4 906 ms** |
| API server-side | **1 664 ms** | **4 354 ms** | **4 836 ms** |

Comando: `python scripts/benchmark.py -n 50 -d 1.0 --api https://korio.es`

Desglose por escenario (API server-side, p50):
Delos/admin 1 657 ms · Delos/doctor 2 054 ms · Delos/staff 1 562 ms ·
García/admin **3 956 ms** (dos spaces simultáneos, LLM más largo) ·
García/lawyer 1 028 ms.

Evolución vs sesión 10 (v0.3.1, corpus 9 docs / 29 chunks):

| Métrica | s10 (12 jun) | Actual (1 jul) | Δ |
|---|---|---|---|
| p50 API | 1 983 ms | **1 664 ms** | **-16 %** ✅ |
| p95 API | 3 053 ms | **4 354 ms** | **+43 %** ⚠️ |
| Corpus | 9 docs · 29 chunks | 20 docs · 74 chunks | +122 % docs |

p95 +43 % es coste asumido a cambio de 2,5× corpus, gobernanza query-time
(RPC O(N²/2)) y rerank RRF grafo. Deuda: reintroducir índice vectorial (HNSW
o `ivfflat lists=ceil(sqrt(N))`) cuando el volumen supere ~1000 chunks.

### Calidad — LLM-as-judge (`scripts/rag_eval.py` sobre `scripts/eval_set.json`)

| Métrica | Valor |
|---|---|
| Answer relevance (1–5) | **5.0** |
| Faithfulness (1–5) | **5.0** |
| Correctness (1–5) | **5.0** |
| Retrieval hit rate | **1.0** |
| Latencia media | **2 138 ms** |

Casos: `rrhh_jornada_minima` (hit ✓, grafo activo), `rrhh_vacaciones` (3 casos
citados en R2), `fuera_de_dominio` (declina correctamente).

### Stack e infraestructura

| Categoría | Valor |
|---|---|
| Migraciones aplicadas | 20 |
| Workflows n8n activos | 8 |
| Documentos en producción | 20 (Delos 15 + García 5) |
| Chunks en producción | 74 |
| Nodos grafo FalkorDB | 1 130 |
| Aristas grafo FalkorDB | 1 818 |
| Aristas CONTRADICTS | 27 (13 resueltas + 14 pendientes) |
| Policies reutilizables | 4 |
| Conflict reviews activos | 3 |
| **Detector P/R/F1 (n=12)** | **1.000 / 1.000 / 1.000** sobre ground truth |
| Validación semántica detector | `is_chunk_contradiction` LLM (paso 0, v0.3.16) |
| Snapshots demo | `pre_saneo_s19` (baseline anexo J) · `pre_demo_v038` (vídeo demo) |
| Endpoints admin | `/admin/errors`, `/admin/errors/{id}/review`, `/admin/errors/slack-action` |
| Observabilidad | LangSmith @traceable (UE) + OTel/Jaeger + `scripts/rag_eval.py` |
| Compliance | Privacy Policy + PII redaction Mistral + whitelist Presidio + frontmatter strip |
| Modelo embeddings | Ollama `nomic-embed-text` 768 dims (CPU) |
| Modelo LLM | Mistral API `mistral-small-latest` (temp 0.2 generación · 0.0 juez · 0.0 detector semántico) |

---

## Documentación TFM — mapa

| Doc | Rol |
|---|---|
| `docs/ARCHITECTURE.md` | Capítulo arquitectura (base) |
| `docs/AGENTIC-INGESTION.md` | Capítulo ingesta agéntica + las 6 reglas del E3/E4 |
| `docs/MCP-SERVER.md` | Capítulo Korio como servidor MCP (Phase 7.3) |
| `docs/COMPLIANCE-AI-ACT-GDPR.md` | Capítulo gobernanza + cumplimiento normativo |
| `docs/AUDIT-2026-06-14.md` | Anexo seguridad y deuda técnica reconocida |
| `docs/MULTI-TENANT-INGESTION.md` | Anexo roadmap Phase 8 — OAuth multi-tenant |
| `docs/CHAT-PIPELINE-GUARDRAILS.md` | Anexo roadmap Phase 8 — guardrails chat |
| `docs/PHASE-10-MULTIMODAL-INGESTION.md` | Anexo roadmap Phase 10 — multimodal + escala |
| `docs/EMBEDDINGS-DEFENSA-TFM.md` | Dossier defensa embeddings + roadmap Phase 11 (nomic → e5-large → BGE-M3) |
| `docs/DEPLOYMENT.md` | Operativo: cómo redeployar desde cero |
| `docs/SESSION-STARTER.md` | Operativo: estado de cierre por sesión + plan siguiente |
| `docs/ROADMAP.md` (este fichero) | Operativo: visión global + backlog |

---

*Actualizado: 3 julio 2026 · v0.3.16 · sesión 19. Roadmap post-TFM alineado con capítulo 5.5 memoria (Phase 8 SaaS conectores+worker+guardrails+reranker · Phase 9 auth+billing+admin+GDPR endpoints · Phase 10 multimodal · Phase 11 embedder e5→BGE-M3 + 3 transversales + 3 líneas investigación). Doc `EMBEDDINGS-DEFENSA-TFM.md` promovido a fuente Phase 11.*
