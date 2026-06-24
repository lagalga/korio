# Korio — Roadmap

> **Estado: v0.3.13 (22 jun 2026) · 🏁 Implementación cerrada · Evaluación cuantitativa + fix frontmatter aplicado**
> Defensa TFM: 9 julio 2026

---

## Resumen ejecutivo

Korio cubre **6 phases técnicas cerradas** (núcleo RAG, multi-tenancy, producción + gobernanza activa, cron HITL, grafo de conocimiento, ingesta multi-canal, MCP server) más **v0.3.0 con las 6 reglas del Entregable 3 materializadas** (pipeline ACID + bus de eventos + query-time + policies + inconclusive), **v0.3.12 con los flecos operativos de Phase 9** (throttling errores, panel admin, Slack interactivity) y **v0.3.13 con evaluación cuantitativa del detector (P/R/F1 = 1.0 sobre n=12) + fix bug frontmatter en preprocessor**.

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
| Validación semántica LLM en detector de ingesta | Reduce falsos positivos G1↔G2 (docs estilo similar) | 3-4h |
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

### Phase 8 · Mitigaciones a limitaciones detectadas

Diseños completos en `docs/`:

| Bloque | Esfuerzo | Doc fuente |
|---|---|---|
| **Ingesta multi-tenant configurable** (OAuth + vault tokens + onboarding UI) | ~6 semanas + verificación Google CASA | `docs/MULTI-TENANT-INGESTION.md` |
| **Chat pipeline con guardrails** (n8n + Lakera/Rebuff + Presidio egress + rate limit) | ~2 semanas | `docs/CHAT-PIPELINE-GUARDRAILS.md` |
| Reranker cross-encoder | +20-30% calidad en queries rephrasadas | 6-8h |
| Query expansion con LLM antes del embed | Más cobertura | 4-6h |
| MCP Server OAuth 2.1 + rate limit + `mcp_audit_log` con PII-redaction | Producto-real | ~2 semanas |
| MCP Streamable HTTP stateless o sticky sessions nginx (multi-worker) | Escala MCP | 3-5 días |
| Bias audit embeddings RRHH/Legal (AI Act Art. 15) | Compliance | 1 semana — ver `docs/COMPLIANCE-AI-ACT-GDPR.md` |
| DPA formal con Mistral | Compliance | bloqueado por proveedor |
| Endpoints `/export/{tenant_id}` (RGPD Art. 20) y `/subject-access/{user_id}` (Art. 15) | Compliance | 3-4 días |

Hallazgos diferidos de la auditoría 13a (14 issues) — ver `docs/AUDIT-2026-06-14.md`.

### Phase 9 · Producto SaaS

| Feature | Descripción |
|---|---|
| Matriz de autoridad configurable en onboarding | UI para `authority_weight` por space y source_type |
| Panel admin de conflictos en `/ui/admin/conflicts` | Alternativa visual al email |
| Auth real | Supabase Auth (email/password, Google OAuth) |
| Billing | Stripe por tenant/mes |
| Conectores nativos configurables | Drive, Slack, Notion, Gmail con OAuth multi-tenant (ver Phase 8) |
| API keys por tenant | Para integrar Korio desde otras apps |
| Límites de plan | Chunks máximos, queries/mes, usuarios |
| Persistencia de chat por usuario | Conversaciones multi-sesión cross-device |
| Reflejo de chat Slack ↔ chat web | Identidad compartida, conversaciones cross-canal |
| ROPA + admin dashboard audit-log | Compliance (`docs/COMPLIANCE-AI-ACT-GDPR.md`) |

Ya cerrados de Phase 9 dentro del TFM (flecos operativos):

- ✅ Throttling Slack DM errores n8n (s16a)
- ✅ Panel `/admin/errors` UI + endpoints (s16b)
- ✅ Botón Slack "Marcar reviewed" (s16b · firma HMAC + anti-replay)
- ✅ Slack file_shared duplicate → DM thread (s16c)

### Phase 10 · Ingesta multimodal + escala

Diseño completo en `docs/PHASE-10-MULTIMODAL-INGESTION.md`:

- Email body adapter (parsing local, sin LLM)
- Slack/Teams thread adapter (reaction `📥 korio` ingiere thread completa)
- Audio adapter ASR (Voxtral API → Whisper local cuando volumen >100 min/mes)
- `src/adapters/` con interfaz común + 4 nuevos workflows n8n + 3 botones upload UI

Escala y GPU:

| Mejora | Impacto | Coste |
|---|---|---|
| GPU en Hetzner (GEX44) | Embed ~0.1s · LLM ~1s | ~€65/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

---

## Métricas y stack (sesión 17b, v0.3.13)

| Categoría | Valor |
|---|---|
| Tests | **28/28 verdes** + 3 skipped (~32s) |
| Migraciones aplicadas | 20 |
| Workflows n8n activos | 8 |
| Documentos en producción | 22 (Delos 20 + García 5 tras restore) |
| Aristas CONTRADICTS en grafo | 27 (13 resueltas + 14 pendientes) |
| Benchmark p50 / p95 | **1983 ms / 3053 ms** (50/50 sin errores, sesión 10) |
| **Detector P/R/F1 (n=12 eval corpus)** | **1.000 / 1.000 / 1.000** sobre ground truth declarado |
| Snapshots demo | `pre_demo_v038` (20 docs, 74 chunks, 1130 nodos, 1818 aristas) · `pre_eval_20260622` (baseline post-eval) |
| Endpoints admin | `/admin/errors`, `/admin/errors/{id}/review`, `/admin/errors/slack-action` (s16b) |
| Compliance | Privacy Policy + PII redaction Mistral + whitelist Presidio (s14b) + frontmatter strip (s17b) |

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
| `docs/DEPLOYMENT.md` | Operativo: cómo redeployar desde cero |
| `docs/SESSION-STARTER.md` | Operativo: estado de cierre por sesión + plan siguiente |
| `docs/ROADMAP.md` (este fichero) | Operativo: visión global + backlog |

---

*Actualizado: 22 junio 2026 · v0.3.13 · sesiones 17 + 17b. 🏁 Implementación cerrada + evaluación cuantitativa cerrada + fix frontmatter aplicado. Próximo: maquetar slides, grabar vídeo demo (3 escenas), memoria TFM en Claude Projects, banco Q&A, ensayos cronometrados.*
