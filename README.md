![Korio - Company Brain](https://github.com/lagalga/korio/blob/main/ui/assets/img/logo.png)
# Korio — Company Brain

> SaaS multi-tenant de RAG para pymes españolas, con **gobernanza activa** del conocimiento y **grafo de conocimiento** complementario.
> TFM · Máster IA Business & Innovation · Nuclio Digital School

Korio permite a una organización consultar en lenguaje natural el conocimiento acumulado en sus documentos internos (PDFs, Word, Excel, Markdown), con:

- **Aislamiento real** entre clientes (multi-tenancy con RLS de Supabase + early binding en aplicación).
- **Aislamiento por departamento** dentro de cada cliente (un médico no ve documentos del departamento Legal).
- **Detección automática de contradicciones** entre documentos al ingestar (auto-resolución por autoridad/fecha, HITL via email para casos ambiguos, cron de escalada con auto-cierre).
- **Grafo de conocimiento** en FalkorDB con entidades + claims atómicos extraídos por LLM. Search híbrido vector + grafo rescata datos cuando la query está semánticamente reformulada respecto al texto fuente.
- **Ingesta automática multi-canal** vía n8n: Gmail (label vigilada), Drive (carpeta vigilada), Slack (`/korio` para consultar **+** subida automática de PDF/DOCX al canal vigilado). Cada documento lleva `source_metadata` (JSONB) con el contexto del canal de origen.

**Estado:** Phases 1–7.3 + rerank semántico + hardening seguridad + panel admin errores · **v0.3.14** · Producción en [korio.es](https://korio.es) · Demo TFM 2 julio 2026 · Defensa 9 julio 2026

> **Sesión 17c · 23 jun 2026 (v0.3.14):** fixes encadenados pre-grabación vídeo: restore snapshot limpiaba policies, umbral conflicto 0.78→0.80, promoción doc-level tras ≥2 aprobaciones HITL (`promote_to_document_replacement`), nginx `proxy_read_timeout` 120→300s.
> **Sesión 16 · 18 jun 2026 (v0.3.12):** throttling anti-spam errores n8n (1 DM en error 1/10/20…), panel `/ui/admin-errors.html` + endpoints admin, botón "Marcar reviewed" en Slack con verificación de firma, workflow Slack file_shared: duplicado → DM thread (no errorWorkflow).
> **Sesión 13a · 14 jun 2026 (v0.3.4):** auditoría completa (21 hallazgos) + 7 fixes seguridad bloqueantes: CORS whitelist, `hmac.compare_digest`, tenant check DELETE, RLS `mcp_api_keys`, assert dim 768, tempfile cleanup, Cypher parametrizado.
> **Benchmark (sesión 10 · 12 jun 2026):** p50 global 1983 ms · p95 3053 ms · 50/50 queries sin errores · QA E2E 10/10 ✅

---

## ⚠️ Aviso de uso

Korio es un **TFM académico** publicado como portfolio. El código se distribuye bajo **Business Source License 1.1** (ver [LICENSE](LICENSE)) — source-available; uso interno, académico, evaluación y no comercial libres. Ofrecer Korio (o un derivado) como **SaaS multi-tenant de RAG / knowledge management a terceros** requiere licencia comercial del autor hasta el 25 de junio de 2030, fecha en la que el código convierte automáticamente a **Apache 2.0**.

- **Endpoints `/search`, `/ingest`, `/upload`, `/waitlist` NO tienen autenticación ni rate-limit** en la instancia de demo (`korio.es`). Diseño intencional para la demo del TFM; OAuth multi-tenant + rate-limit están planificados en **Phase 8** (post-defensa). NO desplegar la rama `main` tal cual en producción real sin cerrar esos endpoints.
- Datos en `data-synthetic/` son **ficticios**. Nombres, DNIs, NIFs y direcciones NO corresponden a personas reales (se usan formatos válidos para test, e.g. DNI `12345678Z`).
- Dependencia **`pymupdf` está bajo licencia AGPL-3.0**. Uso académico/personal sin restricción; integración en producto comercial cerrado requiere licencia comercial de Artifex o sustituir la dependencia.
- Procesamiento de prompts vía Mistral API (`la Plateforme`) — por defecto Mistral **no entrena** con datos de clientes de pago, ver [política Mistral](https://mistral.ai/terms/). Detalles en `landing/legal/privacy.html`.

---

## URLs en producción

| URL | Servicio |
|---|---|
| [korio.es](https://korio.es) | Landing teaser de la marca |
| [korio.es/ui](https://korio.es/ui) | App de chat (RAG + ingesta + gobernanza) |
| [korio.es/ui/graph.html](https://korio.es/ui/graph.html) | **Visualización del grafo de conocimiento** |
| [korio.es/docs](https://korio.es/docs) | Swagger UI (FastAPI) con Authorize para endpoints admin |
| [korio.es/mcp/sse](https://korio.es/mcp/sse) | **Servidor MCP HTTP+SSE (Phase 7.3)** — 3 tools (`search_knowledge_base`, `list_pending_conflicts`, `list_spaces`), auth `X-Korio-MCP-Key` |
| [n8n.korio.es](https://n8n.korio.es) | Editor de workflows (**8 activos**: Pipeline event bus + HITL + Cron + Gmail + Drive + Slack `/korio` + Slack file_shared + Gestión de errores) |

---

## Quickstart (desarrollo local)

### Requisitos

- Python 3.12+
- Docker + Docker Compose
- Cuenta Supabase (Pro, Frankfurt)
- API key de Mistral AI

### 1. Clonar y configurar

```bash
git clone https://github.com/lagalga/korio.git
cd korio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Modelo spaCy (necesario para Presidio en español)
python -m spacy download es_core_news_lg

cp .env.example .env
# Editar .env con credenciales Supabase, Mistral, HITL_WEBHOOK_URL, etc.
```

### 2. Levantar Ollama

```bash
docker compose up -d ollama
docker exec korio-ollama ollama pull nomic-embed-text
docker exec korio-ollama ollama pull mistral:7b-instruct-q4_K_M
```

### 3. Schema en Supabase

En el SQL Editor de Supabase, ejecutar en orden todas las migraciones:

```
supabase/migrations/001_initial_schema.sql
supabase/migrations/002_search_function.sql
supabase/migrations/003_fix_vector_dims.sql
supabase/migrations/004_conflict_reviews.sql                  ← Gobernanza activa
supabase/migrations/005_search_with_disputed.sql              ← Search incluye 'disputed'
supabase/migrations/006_tenant_admin_email.sql                ← admin_email por tenant
supabase/migrations/007_waitlist.sql                          ← Landing waitlist
supabase/migrations/008_escalation_tracking.sql               ← Cron de escalada HITL
supabase/migrations/009_source_metadata.sql                   ← JSONB canal de origen
supabase/migrations/010_mcp_api_keys.sql                      ← API keys MCP (Phase 7.3)
supabase/migrations/011_pipeline_events_atomic_ingest.sql     ← Bus de eventos + ingesta ACID
supabase/migrations/012_silent_conflicts_query_time.sql       ← Detección query-time
supabase/migrations/013_inconclusive_state_and_policies.sql   ← Estado inconclusive + policies
supabase/migrations/014_n8n_errors.sql                        ← Tabla errores workflows n8n
supabase/migrations/015_mcp_api_keys_rls.sql                  ← RLS sobre mcp_api_keys
supabase/migrations/016_silent_conflicts_same_space.sql       ← Fix cross-space falsos positivos
supabase/migrations/017_delos_admin_space.sql                 ← Space Administración Delos
supabase/migrations/018_slack_service_users.sql               ← 4 service users Slack (RLS canal)
supabase/migrations/019_drop_ivfflat_index.sql                ← Drop índice ivfflat (bug probes)
supabase/migrations/020_search_includes_inconclusive.sql      ← Search incluye 'inconclusive'
```

### 3b. Grafo de conocimiento (opcional pero recomendado)

```bash
# FalkorDB en docker-compose
docker compose up -d falkordb

# Activar el grafo en .env
echo "KORIO_GRAPH_ENABLED=1" >> .env

# Backfill (procesa todos los chunks existentes con Mistral, ~10s por chunk)
python scripts/graph_backfill.py
```

### 4. Tests

```bash
python -m pytest tests/ -v
# Esperado: 20/20 ✅
```

### 5. Levantar API

```bash
python -m uvicorn api.server:app --reload --port 8000

# Landing:  http://localhost:8000/
# App chat: http://localhost:8000/ui
# Swagger:  http://localhost:8000/docs
```

### 6. Ingestar un documento

```bash
python src/ingest.py data-synthetic/delos_politica_rrhh.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001
```

### 7. Hacer una query

```bash
python src/search.py "¿Cuántos días de vacaciones tienen los empleados?" \
  --user-id a2000000-0000-0000-0000-000000000001 \
  --tenant-id a0000000-0000-0000-0000-000000000001
```

---

## Arquitectura

### Pipeline RAG con gobernanza

```
INGESTA DE DOCUMENTO
    ▼
[POST /upload]
    │
    ├── 1. MarkItDown ─────────► PDF/DOCX/XLSX → Markdown
    ├── 2. Presidio ───────────► Detecta + pseudoanonimiza PII (español)
    ├── 3. Chunking ───────────► RecursiveCharacterTextSplitter (500 tok/50 overlap)
    ├── 4. Embeddings ─────────► nomic-embed-text (768 dims, Ollama)
    ├── 5. Persist ────────────► Supabase pgvector + content_hash dedup
    └── 6. ⚖️ Conflict detect ─► busca chunks similares (>0.78) en el mismo space
                                  ├── auto_new_wins:      existente → superseded
                                  ├── auto_existing_wins: nuevo → superseded
                                  └── pending:            crea conflict_review + email HITL


CONSULTA DEL USUARIO
    ▼
[POST /search]
    │
    ├── 1. Embed query ────────► nomic-embed-text (768 dims, ~0.8s)
    ├── 2. RLS early binding ──► user → spaces → documents permitidos
    ├── 3. Vector search ──────► pgvector cosine (chunks active OR disputed)
    ├── 4. Context assembly ───► chunks + filename + flag de disputa
    └── 5. LLM generation ─────► Mistral API (~2.5s, instrucción especial si hay disputa)
    │
    ▼
RESPUESTA + CITAS (filename real) + BANNER ⚠️ si hay chunks disputed
```

### RLS en dos capas

- **Aplicación** (`db.py`): early binding obtiene `space_ids` del usuario y filtra `document_ids` ANTES del vector search.
- **PostgreSQL** (`migrations/001`): políticas RLS de Supabase enforces el mismo aislamiento a nivel de BD.

Un usuario de Despacho García nunca puede ver datos de Clínica Delos. Un médico no puede ver documentos del departamento Legal.

### Gobernanza activa (Phase 5)

Cuando se ingesta un documento que solapa semánticamente con otro:

| Criterio | Resolución |
|---|---|
| Diferencia de fecha > 30 días | ⚡ Auto: el más reciente prevalece |
| Diferencia de autoridad ≥ 3 puntos | ⚡ Auto: mayor autoridad prevalece |
| Sin criterio claro | ⏳ HITL: email al admin con los 2 chunks + 3 botones de acción |

Los chunks "perdedores" pasan a `superseded` y dejan de aparecer en búsquedas. Los chunks en disputa (HITL pendiente) sí aparecen, con flag visual de contradicción.

### Cron de escalada HITL (Phase 6)

Los conflictos sin resolver reciben recordatorios automáticos por email:

| Día | Acción |
|---|---|
| 0 | Email inicial al detectar el conflicto |
| 3 | Recordatorio Nº 1 |
| 7 | Recordatorio Nº 2 |
| 14 | Recordatorio Nº 3 urgente |
| 21 | Auto-cierre como `timeout_inconclusive` (ambos chunks siguen incluidos en RAG con badge ⚠️ + aviso en respuesta, hasta revisión manual) |

Disparado por workflow n8n Schedule Trigger diario a las 09:00 Madrid que llama a `POST /escalate-reviews`. Cadencia parametrizable vía `.env`.

### Grafo de conocimiento (Phase 7.1)

El RAG vectorial puro depende de la similitud semántica entre query y texto fuente. Cuando la query se rephrasea, la recuperación cae. Para mitigarlo, Korio extrae **entidades + claims atómicos** de cada chunk con Mistral y los almacena en FalkorDB:

```
[empleados asalariados de tiempo completo] -- jornada_minima --> [35 horas/semana]
```

En tiempo de consulta, el search híbrido lanza en paralelo el vector search y una consulta al grafo por keywords del predicate. El LLM recibe ambos contextos.

**Ejemplo real**: la query *"¿Cuántas horas semanales mínimas exige la política?"* devolvía *"No encuentro información"* con vector-puro porque el texto fuente dice *"rige para empleados que trabajan más de 35 horas"* (umbral de aplicabilidad, no jornada mínima). Con el grafo activado, responde correctamente *"más de 35 horas a la semana"* en ~1s.

Schema del grafo: nodos `Document → Chunk → Entity / Claim` con aristas `CONTAINS / MENTIONS / HAS_CLAIM / ABOUT_ENTITY / CONTRADICTS`. Multi-tenant por `tenant_id` en todos los nodos + filtro por `allowed_space_ids` en las queries (RLS-equivalente en grafo).

Visualización interactiva en [`korio.es/ui/graph.html`](https://korio.es/ui/graph.html) con vis-network.

### Observabilidad y evaluación (Phase 8 / sesión 18)

Tres capas complementarias, todas con degradado **no-op seguro** (sin la dependencia o sin la env activa, el sistema funciona idéntico):

1. **LangSmith `@traceable`** (capa semántica) — instrumenta el pipeline RAG sin LangChain (`src/observability.py`): spans `rag-search → ollama-embed / graph-retrieval / mistral-generate` con tokens y coste por llamada LLM. Región **UE** → trazas residentes en territorio europeo (GDPR).
2. **OpenTelemetry + Jaeger** (capa de infraestructura) — `api/otel.py` instrumenta FastAPI + `requests` (Mistral/Ollama/Supabase) y exporta OTLP a Jaeger **self-hosted** en el VPS. Waterfall de latencia por endpoint.
3. **RAG eval LLM-as-judge** — `scripts/rag_eval.py` puntúa relevance / faithfulness / correctness / retrieval-hit sobre `scripts/eval_set.json`, reutilizando `search()` + Mistral. Complementa el benchmark de latencia con una red de seguridad de **calidad**.

Activación vía `.env`: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT` (EU), `KORIO_OTEL_ENABLED`. Detalle y decisiones en [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

---

## Stack

| Componente | Tecnología | Notas |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama | **768 dims — fijo** |
| Vector store | pgvector en Supabase | RLS nativo, Frankfurt (GDPR) |
| **Graph store** | **FalkorDB** (Redis 8.6.3 + Cypher) | docker-compose, solo localhost (127.0.0.1:6379) |
| LLM generación | Mistral API `mistral-small-latest` | ~3s latencia, temp 0.2 |
| LLM extracción claims | Mistral API (structured JSON, temp 0.0) | en `entity_extractor.py` |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` | offline en VPS |
| Backend API | FastAPI + Uvicorn, Python 3.12 | systemd service |
| PII detection | Presidio + spaCy `es_core_news_lg` | configurado en español, whitelist PII real |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Doc parsing | PyMuPDF + MarkItDown `[pdf,docx,xlsx,pptx]` | PyMuPDF para texto, MarkItDown para conversión |
| Automatización | n8n **v2.27.4** (Docker en VPS) | **8 workflows**: HITL + Cron + Pipeline event bus + Gmail + Drive + Slack `/korio` + Slack file_shared + Gestión errores |
| Visualización grafo | **vis-network 9.1.9** (CDN) | barnesHut física, canvas render |
| Servidor | Hetzner **CPX32** (AMD EPYC-Genoa), Frankfurt | 4 vCPU / 8 GB / 160 GB SSD · Ubuntu 26.04 LTS · **€17.53/mes max** |
| Reverse proxy | nginx + Let's Encrypt (certbot) | renovación automática, proxy_read_timeout 300s |
| Observabilidad (RAG) | **LangSmith** `@traceable` | trazas semánticas del pipeline RAG, tokens/coste, región UE (GDPR) |
| Observabilidad (HTTP) | **OpenTelemetry + Jaeger** | trazas de infraestructura self-hosted (OTLP), waterfall de latencia por endpoint |
| Evaluación de calidad | **RAG eval** LLM-as-judge (`scripts/rag_eval.py`) | relevance / faithfulness / correctness / retrieval-hit |

> Detalle completo en [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md). Toda la
> instrumentación degrada a no-op si la dependencia o la env no están activas.

---

## Datos de prueba

### Tenant 1: Clínica Delos

```
tenant_id: a0000000-0000-0000-0000-000000000001

Espacios:
  RRHH    → a1000000-0000-0000-0000-000000000001
  Médico  → a1000000-0000-0000-0000-000000000002
  Legal   → a1000000-0000-0000-0000-000000000003

Usuarios:
  admin   → a1000000-0000-0000-0000-000000000001  (todos los espacios)
  doctor  → a2000000-0000-0000-0000-000000000001  (RRHH + Médico)
  staff   → a3000000-0000-0000-0000-000000000001  (solo RRHH)
```

### Tenant 2: Despacho Legal García

```
tenant_id: b0000000-0000-0000-0000-000000000002

Espacios:
  Casos   → b1000000-0000-0000-0000-000000000001
  Fiscal  → b1000000-0000-0000-0000-000000000002

Usuarios:
  admin   → b1000000-0000-0000-0000-000000000002  (Casos + Fiscal)
  lawyer  → b2000000-0000-0000-0000-000000000002  (solo Casos)
```

---

## Tests

```bash
python -m pytest tests/ -v    # 31/31 ✅ (~25s)

# Por suite:
# test_rls.py                        10/10 ✅  RLS multi-tenant
# test_search.py                     10/10 ✅  RAG vectorial
# test_atomic_ingest.py               3/3  ✅  Transaccionalidad ACID (incluye rollback demostrado)
# test_pipeline_agentic.py            2/2  ✅  Fachada agéntica (5 roles del Entregable 3)
# test_query_time_detection.py        1/1  ✅  Caso extremo E4: conflictos silenciosos query-time
# test_inconclusive_and_policies.py   2/2  ✅  Estado inconclusive + política reutilizable
# test_graph_semantic_rerank.py       3/3  ✅  Rerank semántico del grafo (RRF lexical + semantic)
```

---

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Sistema, modelo de datos, RLS
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Setup en Hetzner desde cero
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Fases pasadas + futuras
- [`docs/AGENTIC-INGESTION.md`](docs/AGENTIC-INGESTION.md) — Pipeline ACID + 6 reglas Entregable 3 + comparativa E4 vs Korio
- [`docs/MCP-SERVER.md`](docs/MCP-SERVER.md) — Phase 7.3: arquitectura MCP HTTP+SSE, Claude Desktop
- [`docs/MULTI-TENANT-INGESTION.md`](docs/MULTI-TENANT-INGESTION.md) — Diseño Phase 8: OAuth multi-tenant configurable
- [`docs/CHAT-PIPELINE-GUARDRAILS.md`](docs/CHAT-PIPELINE-GUARDRAILS.md) — Diseño Phase 8: guardrails n8n + Lakera/Presidio
- [`docs/COMPLIANCE-AI-ACT-GDPR.md`](docs/COMPLIANCE-AI-ACT-GDPR.md) — AI Act + GDPR: clasificación de riesgo, medidas técnicas, Privacy Policy
- [`docs/AUDIT-2026-06-14.md`](docs/AUDIT-2026-06-14.md) — Auditoría seguridad: 21 hallazgos, 7 cerrados, 14 diferidos
- [`docs/PHASE-10-MULTIMODAL-INGESTION.md`](docs/PHASE-10-MULTIMODAL-INGESTION.md) — Diseño Phase 10: email body, Slack/Teams threads, audio
- [`CLAUDE.md`](CLAUDE.md) — Memoria del proyecto para Claude Code

---

## Métricas (24 junio 2026)

| Métrica | Valor |
|---|---|
| Versión | **v0.3.14** (23 junio 2026, sesión 17c) |
| Tests | **31/31 ✅** (20 RLS+RAG + 8 agéntica/ACID + 3 rerank semántico grafo) |
| Benchmark formal (sesión 10) | p50 1983 ms · p95 3053 ms · 50/50 sin errores |
| Latencia RAG vector-puro | ~1.0–3.3s |
| Latencia RAG híbrido (vector + grafo) | ~1.0s |
| Latencia embedding | ~0.8s |
| Latencia detección query-time | ~0.1s adicional (RPC SQL par a par) |
| Umbral conflicto silencioso (query-time) | 0.80 (configurable `KORIO_QUERY_TIME_CONFLICT_THRESHOLD`) |
| Docs en producción | **20** (13 Delos + 5 García + 2 RRHH en conflicto) |
| Chunks en producción | **74** activos |
| Nodos grafo | **1130** · Aristas: **1818** (incl. 27 CONTRADICTS) |
| Phases completadas | 1 · 2 · 3 · 4 · 5 · 6 · 7.1 · 7.2 · 7.3 + Phase 9 parcial (errores n8n) |
| Migraciones SQL aplicadas | **20** (úl: `020_search_includes_inconclusive.sql`) |
| Workflows n8n activos | **8** (v2.27.4) |
| MCP server | korio.es/mcp/sse — Claude Desktop conectado |
| Producción | korio.es + grafo en vivo · snapshot `pre_demo_v038` disponible |
| Auditoría seguridad | 21 hallazgos · 7 cerrados · 14 diferidos a Phase 8/9 (`docs/AUDIT-2026-06-14.md`) |

---

## Estructura del proyecto

```
korio/
├── api/
│   ├── server.py             # FastAPI: /search, /ingest, /upload, /review,
│   │                         #          /waitlist, /escalate-reviews,
│   │                         #          /graph/*, /health, DELETE /document/{id}
│   │                         #          /mcp/* (sub-app SSE con MCPAuthASGI)
│   └── mcp_server.py         # FastMCP: 3 tools (Phase 7.3)
├── src/
│   ├── search.py             # RAG híbrido vector + grafo + detección query-time (Step 2.5)
│   ├── ingest.py             # Pipeline ACID: IO → dedupe → RPC atómico → grafo → conflictos
│   ├── conflict_detector.py  # Detección + auto-resolución + policies + HITL
│   ├── escalation.py         # Cron HITL: recordatorios + timeout → inconclusive (sigue en RAG con aviso)
│   ├── policies.py           # Políticas reutilizables (Regla 4 del E3)
│   ├── graph_client.py       # Wrapper FalkorDB multi-tenant (Phase 7.1)
│   ├── entity_extractor.py   # Mistral structured JSON (Phase 7.1)
│   ├── embedder.py           # Wrapper Ollama nomic-embed-text
│   ├── chunker.py            # RecursiveTextSplitter
│   ├── preprocessor.py       # MarkItDown + Presidio (es_core_news_lg)
│   ├── llm_client.py         # Mistral API + Ollama fallback + prompt RAG
│   ├── db.py                 # Supabase client + RLS + conflict_reviews
│   └── agents/               # Fachada agéntica (Phase 7.2+ / E3)
│       ├── base.py           #   BaseAgent con PEAS docstring
│       ├── ingestor.py       #   Rol Ingestor
│       ├── detector.py       #   Rol Detector
│       ├── arbitrator.py     #   Rol Árbitro
│       ├── supervisor.py     #   Rol Supervisor HITL
│       ├── curator.py        #   Rol Curador
│       ├── pipeline.py       #   Orquestador Pipeline(tenant_id).run_ingest()
│       └── events.py         #   emit() → pipeline_events + webhook async n8n
├── landing/                  # Landing teaser de korio.es
├── tests/
│   ├── test_rls.py                      # 10/10 ✅ RLS multi-tenant
│   ├── test_search.py                   # 10/10 ✅ RAG vectorial
│   ├── test_atomic_ingest.py            #  3/3  ✅ Transaccionalidad ACID
│   ├── test_pipeline_agentic.py         #  2/2  ✅ Fachada agéntica
│   ├── test_query_time_detection.py     #  1/1  ✅ Caso extremo E4
│   └── test_inconclusive_and_policies.py #  2/2  ✅ inconclusive + policy reuse
├── ui/
│   ├── index.html            # App chat
│   ├── graph.html            # Visualización grafo (vis-network)
│   ├── admin-errors.html     # Panel admin errores n8n (Phase 9)
│   ├── css/styles.css
│   └── js/main.js
├── supabase/migrations/      # 20 migraciones SQL (001–020)
├── docs/                     # ARCHITECTURE, DEPLOYMENT, ROADMAP, AGENTIC-INGESTION,
│                             # MCP-SERVER, MULTI-TENANT-INGESTION, CHAT-PIPELINE-GUARDRAILS,
│                             # COMPLIANCE-AI-ACT-GDPR, AUDIT-2026-06-14, PHASE-10-MULTIMODAL-INGESTION
├── deploy/                   # systemd, nginx, setup.sh, refresh-landing.sh
├── scripts/
│   ├── benchmark.py               # Latencias p50/p95 por escenario
│   ├── graph_backfill.py          # Pobla el grafo con todos los chunks existentes
│   ├── graph_embed_claims.py      # Backfill embeddings en claims FalkorDB
│   ├── mcp_create_key.py          # CLI create/list/revoke de MCP API keys
│   ├── demo_snapshot.py           # Save/restore estado completo para grabación demo
│   └── reembed_strip_frontmatter.py  # Re-embebido sin frontmatter YAML
└── data-synthetic/           # Documentos de prueba (en .gitignore)
```

---

## Memoria TFM

La memoria se redacta en un **Claude Chat Project separado** (para no mezclar el contexto de implementación con el de escritura académica). Este README es el punto de referencia técnica para ese proyecto.

- **Google Doc:** https://docs.google.com/document/d/1RN53jKdePExVhgR2AHE8sGQCbwSSJ1rnH57giQtKhok/edit
- **Plantilla:** Nuclio Digital School — 7 capítulos + anexos
- **Estado a 11 junio 2026:** Capítulos 1–3 completos, 4–7 pendientes

| Capítulo | Contenido | Estado |
|---|---|---|
| 1. Introducción | Caso de negocio + objetivos + KPIs | ✅ Completo |
| 2. Contexto | Sector, benchmarking (Glean, Guru, Hyper, Monora…) | ✅ Completo |
| 3. Metodología | Enfoque, stack, proyecciones ROI | ✅ Completo |
| 4. Desarrollo y resultados | Prototipo funcional + casos de uso | 🔲 Pendiente |
| 5. Conclusiones | Hallazgos, limitaciones, líneas futuras | 🔲 Pendiente |
| 6. Bibliografía | 24 referencias [F01–F24b] | ✅ Base completa |
| 7. Anexos | Materiales complementarios | 🔲 Pendiente |

Los docs técnicos en `docs/` son la base de los capítulos pendientes:
`AGENTIC-INGESTION.md` → cap. 4.1 · `MCP-SERVER.md` → cap. 4.2 · `MULTI-TENANT-INGESTION.md` + `CHAT-PIPELINE-GUARDRAILS.md` → cap. 5.5

---

## Licencia

Código liberado bajo **Business Source License 1.1** — ver [LICENSE](LICENSE).
Copyright © 2026 Heriberto Noguera.

**Qué puedes hacer libremente:**
- Leer, clonar, modificar, redistribuir el código.
- Usarlo internamente en tu organización (incluidas afiliadas).
- Uso académico, investigación, evaluación, uso personal.
- Cualquier uso no comercial.

**Qué requiere licencia comercial del autor:**
- Ofrecer Korio (o un derivado) como **SaaS multi-tenant de RAG, knowledge management o gobernanza documental a terceros** antes del 25 de junio de 2030.

**Change Date:** 25 de junio de 2030 → el código convierte automáticamente a **Apache License 2.0** sin restricciones.

Contexto académico: TFM del Máster IA Business & Innovation (Nuclio Digital School). El carácter académico no afecta a los términos de la licencia.

**Dependencias con licencia distinta:**
- `pymupdf` — AGPL-3.0. Uso académico/personal libre; integración en producto comercial cerrado requiere licencia comercial de Artifex o sustituir la dependencia.

Para licencias comerciales: contacto@lagalga.es

## Autor

**Heriberto Noguera** · [@lagalga](https://github.com/lagalga) · contacto@lagalga.es
