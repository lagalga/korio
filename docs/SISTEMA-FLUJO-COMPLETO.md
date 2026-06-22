# Korio — Flujo completo del sistema (Ingesta · Retrieval · Eventos)

> Documento de referencia para la memoria TFM y el Pitch Deck.
> Estado: v0.3.12 (18 jun 2026) · Phases 1–7.3 cerradas + Phase 9 flecos.
> **Versión exhaustiva** (sin simplificaciones) + **versión reducida** al final (para diagramas).

---

## FASE 1 — INGESTA Y GOBERNANZA

### 1.1 Fuentes de entrada (estado actual + roadmap)

#### Implementadas (Phases 7.2 / TFM)
| Canal | Trigger | Espacio destino |
|---|---|---|
| Upload manual UI (`/ui`) | Multipart `POST /upload` | `space_id` del usuario |
| **Gmail** (label `korio/ingesta`) | n8n Gmail Trigger | Adjuntos → space configurado |
| **Google Drive** (4 subcarpetas) | n8n Drive Trigger × 4 | Subfolders rrhh/medico/legal/admin → space |
| **Slack `file_shared`** | n8n Event Subscriptions | `channel_id → space_id` mapping en Code node |
| **Slack `/korio`** | Slash command | Solo consulta (`/search`), no ingesta |
| CLI (`python src/ingest.py FILE`) | Manual back-office | `--tenant-id` `--space-id` por argumento |

#### Planificadas — Phase 8 (post-TFM)
- Conectores OAuth multi-tenant configurables: Outlook, SharePoint, Dropbox, Teams
- Tabla `tenant_connections` + `ingestion_rules` + `ingestion_cursors` en Supabase
- Onboarding UI para que el admin del tenant conecte sus propias cuentas sin código

#### Planificadas — Phase 10 (post-TFM)
- **Email body** (no solo adjuntos): parsing `text/plain`/`text/html` → Markdown estructurado con thread completa
- **Hilos Slack / Teams**: reaction `📥 korio` → ingiere thread completa al momento
- **Audio** (MP3/WAV/OGG/M4A): Voxtral API (Mistral) → fallback Whisper local (faster-whisper)
- Adapter interface común: `src/adapters/{email,slack,teams,audio}_adapter.py`

**Metadata capturada en cada documento:**
```jsonc
{
  "tenant_id": "uuid",
  "space_id": "uuid",
  "source_metadata": {            // JSONB en documents
    "via": "gmail | gdrive | slack_file | upload | cli",
    "thread_id": "...",           // email/Slack
    "channel_id": "...",          // Slack
    "drive_folder_id": "...",     // Drive
    "original_filename": "...",
    "from": "...",
    "participants": ["..."]
  },
  "content_hash": "SHA-256",      // para deduplicación
  "status": "active | superseded | archived"
}
```

---

### 1.2 Preprocesado y conversión a Markdown

**Librería principal:** `MarkItDown` (Microsoft) + `PyMuPDF`

| Formato de entrada | Herramienta | Output |
|---|---|---|
| PDF (texto nativo) | `PyMuPDF` / `MarkItDown` | Markdown |
| PDF (imagen/escaneado) | `MarkItDown` + OCR interno | Markdown |
| DOCX / XLSX / PPTX | `MarkItDown` | Markdown |
| HTML | `MarkItDown` | Markdown limpio |
| Email adjuntos (MSG/EML) | `email` stdlib | Body + adjuntos separados |
| TXT / MD | Directo | Sin transformación |
| **Audio** *(Phase 10)* | Voxtral API → fallback Whisper local | Transcript Markdown con timestamps |
| **Email body** *(Phase 10)* | `email` + `BeautifulSoup` | Markdown con hilo completo |
| **Slack/Teams thread** *(Phase 10)* | API + adapter | Markdown por mensaje, cronológico |

**Módulo:** `src/preprocessor.py`

**Notas importantes:**
- Whisper / Voxtral / VLM **no están implementados** en v0.3.12 — Phase 10 post-TFM.
- El frontmatter YAML generado automáticamente en algunos formatos se excluye del embedding desde v0.3.11 (`scripts/reembed_strip_frontmatter.py`).

---

### 1.3 Detección y pseudoanonimización de PII (Presidio)

**Librería:** `Microsoft Presidio` + `spaCy es_core_news_lg`

**Tipos detectados (whitelist configurable):**
- `PERSON` (nombres propios)
- `EMAIL_ADDRESS`
- `PHONE_NUMBER`
- `IBAN_CODE`
- `LOCATION` (opcional, según tenant)
- `ES_NIF`, `ES_NIE` (regex custom)
- `CREDIT_CARD`

**Modos de operación en Korio:**
1. **Pre-ingesta** (`src/preprocessor.py`): redacción en el texto antes de chunking. Usa whitelist configurable por tenant (algunos nombres de empresa deben preservarse).
2. **Pre-LLM** (`src/llm_client.py`): segunda pasada antes de enviar contexto a Mistral cloud (`KORIO_REDACT_MISTRAL=1`). Evita que datos sensibles salgan al proveedor externo.

**Output por chunk:**
```jsonc
{
  "content_anonymized": "El paciente [PERSON] tiene IBAN [IBAN_CODE]...",
  "pii_detected": [
    { "type": "PERSON", "start": 12, "end": 24, "action": "REPLACED" },
    { "type": "IBAN_CODE", "start": 31, "end": 51, "action": "REPLACED" }
  ]
}
```

**Módulo:** `src/preprocessor.py` (Fase 1 pipeline + whitelist) · `src/llm_client.py` (pre-LLM)

---

### 1.4 Chunking

**Librería:** `LangChain RecursiveCharacterTextSplitter`

| Parámetro | Valor |
|---|---|
| Chunk size | 500 tokens |
| Overlap | 50 tokens |
| Separadores | `\n\n` → `\n` → ` ` → carácter |

**Módulo:** `src/chunker.py`

**Output por chunk:**
```jsonc
{
  "chunk_index": 0,
  "content": "Texto de hasta 500 tokens...",
  "token_count": 487,
  "document_id": "uuid",
  "tenant_id": "uuid",
  "space_id": "uuid"
}
```

---

### 1.5 Embeddings

**Modelo:** `nomic-embed-text` vía **Ollama local en el VPS** (768 dimensiones, self-hosted)

| Parámetro | Valor |
|---|---|
| Dimensiones | 768 (INMUTABLE — assert al arranque del embedder) |
| Latencia por batch | ~0.8s en Hetzner CPX32 AMD |
| Idiomas | Multilingüe (ES/EN/otras) |
| Forma de uso | `POST http://localhost:11434/api/embeddings` |

**También embebido:** entidades y claims para el grafo. `entity_extractor.py` genera triples `"sujeto predicado valor"` que se pasan por el mismo modelo → vectores comparables con query embedding en RRF.

**No se usa ningún embedding cloud en producción.** Toda inferencia de embedding es local.

**Módulo:** `src/embedder.py`

---

### 1.6 Escritura ACID (Vector Store)

**Tecnología:** Supabase Pro (Frankfurt) — PostgreSQL + `pgvector`

#### Función RPC atómica

```sql
-- supabase/migrations/011_pipeline_events.sql
CREATE FUNCTION ingest_document_atomic(
  p_doc         JSONB,
  p_chunks      JSONB,
  p_operation_id UUID,
  p_source_agent TEXT
) RETURNS JSONB LANGUAGE plpgsql AS $$ ... $$;
```

Un solo `rpc()` HTTP ejecuta en **1 transacción PL/pgSQL**:
1. `INSERT INTO documents (...)` — fila maestra con metadata + status + source_metadata
2. `INSERT INTO embeddings (content, embedding vector(768), chunk_status, ...) × N` — chunks + vectores
3. `INSERT INTO pipeline_events (DOCUMENT_INGESTED, operation_id, ...)` — primer evento del bus

Si cualquier paso lanza excepción → **rollback automático** de los 3. Test demostrado: `test_rpc_atomico_rollback_si_falla_mid_transaction` (chunk con vector de dimensión incorrecta → documentos sin fila, embeddings vacíos, pipeline_events sin evento).

#### Esquema de tablas principales

```sql
-- Tablas core
tenants          -- empresa cliente
spaces           -- departamento / área
users            -- usuario
user_spaces      -- control acceso (qué spaces ve cada user)
documents        -- documento ingestado (+ source_metadata JSONB + status)
embeddings       -- chunk + vector(768)
                 -- chunk_status ∈ {active, superseded, disputed, inconclusive}
audit_log        -- trazabilidad de queries de usuario

-- Gobernanza y observabilidad
conflict_reviews     -- chunks en conflicto + estado HITL + escalada
                     -- (reminders_sent, last_reminder_at, timeout_at)
policies             -- decisiones HITL persistidas como policy reutilizable
                     -- (subject_pattern, decision, times_applied)
pipeline_events      -- bus de eventos (operation_id + event_type + payload)
graph_sync_queue     -- cola retry post-commit FalkorDB
mcp_api_keys         -- SHA-256 + FK users+tenants + soft revoke
n8n_errors           -- errores capturados de workflows n8n
                     -- (reviewed_at, reviewed_by, notes)
```

#### RLS — 3 capas de seguridad

```
query(user_id="doctor", tenant_id="delos")
  │
  ├─ 1. App early binding (src/db.py):
  │      SELECT space_id FROM user_spaces WHERE user_id = ?
  │      → [space_rrhh, space_medico]
  │      SELECT id FROM documents WHERE tenant_id = ? AND space_id IN (?,?)
  │      → [doc-001, doc-003, doc-005]
  │
  ├─ 2. PostgreSQL RLS (policies en Supabase):
  │      Backstop — incluso si app falla, Postgres rechaza filas de otro tenant
  │
  └─ 3. FalkorDB: MATCH (c:Claim {tenant_id: $tid})
                  WHERE c.space_id IN $allowed_space_ids
```

20 migraciones aplicadas en producción (`supabase/migrations/001…020`).

---

### 1.7 Sync al Graph Store (post-commit, best-effort)

**Tecnología:** FalkorDB (Redis 8.6.3 + módulo grafo, Cypher, AOF persistence)

#### Extracción de entidades

**Modelo:** Mistral API `mistral-small-latest` (temp=0.0, structured JSON output)

`src/entity_extractor.py` extrae por chunk:
- **Entidades**: `(type, value, confidence)` → tipos: PERSON, ORG, LOCATION, PRODUCT, PROTOCOL, ROLE, DATE
- **Claims** (triples): `(subject, predicate, value)` → p.ej. `("jornada laboral", "es", "35 horas semanales")`

Los claims se embeben (`"sujeto predicado valor"` → Ollama nomic 768d) para permitir búsqueda semántica en el grafo.

#### Modelo de grafo (Cypher)

```cypher
// Nodos
(Document  {id, tenant_id, space_id, status, source_type, filename})
(Chunk     {id, document_id, position, content_hash})
(Claim     {id, subject, predicate, value, embedding: [768d], tenant_id, space_id})
(Entity    {type, value, normalized_value, tenant_id})

// Aristas
(Document)-[:CONTAINS_CHUNK]->(Chunk)
(Chunk)-[:NEXT]->(Chunk)
(Chunk)-[:PREV]->(Chunk)
(Claim)-[:EXTRACTED_FROM]->(Chunk)
(Entity)-[:MENTIONED_IN]->(Chunk)
(Document)-[:CONTRADICTS]->(Document)  // 27 aristas en producción, sesión 14
```

#### Flujo sync

```
FASE 4 (post-commit ACID):
  graph_client.sync(claims con embeddings)
  ├─ OK:    emit GRAPH_SYNCED
  └─ ERROR: INSERT graph_sync_queue + emit GRAPH_SYNC_FAILED
             Workflow n8n reintenta cada ~5 min
```

**Módulos:** `src/graph_client.py` · `src/entity_extractor.py`

---

### 1.8 Detección y resolución de conflictos (gobernanza activa)

**Módulo:** `src/conflict_detector.py`

#### Cuándo se dispara

1. **En ingesta** (Fase 5 del pipeline): tras commit ACID, `detect_and_resolve()` busca similitud semántica entre el documento nuevo y los ya activos del mismo space.
2. **En query-time** (Phase v0.3): RPC `detect_silent_conflicts_among_chunks(ids, threshold=0.80)` — si la búsqueda recupera ≥2 chunks similares entre sí (sin que pasaran por ingesta juntos). Solo documentos del mismo space (migración 016).

#### Umbrales

| Umbral | Significado |
|---|---|
| ≥ 0.80 (query-time, same-space) | Conflicto silente potencial |
| > 0.85 (ingesta cross-doc) | Conflicto candidato a resolución |

#### Cadena de resolución (Arbitrator — orden fijo)

```
1. find_applicable_policy()          ← Regla 4 del E3 (prevalencia de políticas)
   │ ¿Existe policy con subject_pattern que match al contenido?
   │ SÍ → aplicar decisión policy directa. Incrementar times_applied.
   │ NO → siguiente paso
   │
2. _decide_by_authority()
   │ ¿Hay documentos de source con authority_weight diferente?
   │ (API ERP/CRM > Gmail > upload manual)
   │ SÍ → gana el de mayor autoridad
   │ NO → siguiente paso
   │
3. _decide_by_date()
   │ ¿Hay version_ts diferente?
   │ (src/version_extractor.py — 6 heurísticas: filename, contenido, created_at)
   │ SÍ → gana el más reciente
   │ NO → escalar a HITL
```

#### Estados de chunks tras resolución

| Estado | Significado | En RAG |
|---|---|---|
| `active` | Documento operativo | ✅ Incluido |
| `superseded` | Reemplazado por versión más nueva | ❌ Excluido |
| `disputed` | Conflicto detectado, sin resolver | ⚠️ Incluido con badge |
| `inconclusive` | Timeout HITL — excluido hasta admin | ⚠️ Incluido con badge |

(Nota: la Regla 2 del E3 exige cuarentena. En producción se incluyen con badge por decisión de UX; admin puede excluirlos manualmente.)

#### HITL email (Supervisor)

Si ninguna regla auto-resuelve → `conflict_reviews` row + webhook a n8n:

**Workflow n8n `#1 — HITL email`:**
- Recibe payload `{ conflict_id, doc_a, doc_b, similarity, tenant_admin_email }`
- Envía email con extractos lado a lado + **3 botones de acción** (links firmados con token HMAC)
- Acciones: `keep_a` / `keep_b` / `keep_both`
- Respuesta → `POST /review?token=...&action=...` en FastAPI

#### Escalada automática (Supervisor + cron)

**Workflow n8n `#2 — Cron escalada`:** Schedule Trigger diario 09:00 Madrid → `POST /escalate-reviews`

`src/escalation.py` — cadencia:
- Día 3: primer recordatorio email
- Día 7: segundo recordatorio
- Día 14: tercer recordatorio
- Día 21: **timeout → `inconclusive`** (Regla 5 del E3 — reactivación manual obligatoria)

**Módulo:** `src/escalation.py`

---

### 1.9 Sistema agéntico (roles lógicos en proceso FastAPI)

Los agentes son **clases Python dentro del mismo proceso FastAPI** (no microservicios). La comunicación entre roles ocurre mediante:
1. Llamadas directas (mismo proceso, 0ms overhead)
2. Bus de eventos `pipeline_events` (persistencia + observabilidad)
3. Webhook best-effort a n8n (fire-and-forget, timeout 500ms)

**Módulos:** `src/agents/{ingestor,detector,arbitrator,supervisor,curator,pipeline,events}.py`

Cada agente tiene docstring PEAS (Performance, Environment, Actuators, Sensors) — refleja el diseño del E3 del Máster.

| Agente | Módulo | Responsabilidad principal |
|---|---|---|
| **Ingestor** | `agents/ingestor.py` | Orquesta Fases 1-3: preprocesa, chunkea, embebe, llama RPC ACID |
| **Detector** | `agents/detector.py` | Fases 4-5: sync grafo + detección semántica de conflictos |
| **Arbitrator** | (en `conflict_detector.py`) | Aplica cadena policy → autoridad → fecha → escala a HITL |
| **Supervisor** | `agents/supervisor.py` | Gestiona HITL queue: envía emails, gestiona escalada, aplica timeout |
| **Curator** | `agents/curator.py` | Cierra ciclo: actualiza `chunk_status`, emite `CORPUS_UPDATED` |
| **Pipeline** | `agents/pipeline.py` | Fachada coordinadora del ciclo completo con `operation_id` |
| **System** | (implícito n8n) | Background tasks: sync incremental, retry grafo, escalada cron |

#### Bus de eventos (`pipeline_events`)

```python
# src/agents/events.py
emit(EventType.X, source_agent=Agent.Y, tenant_id=..., operation_id=...)
  ├─► INSERT pipeline_events (persistente, audit-trail)
  └─► POST best-effort a KORIO_EVENT_WEBHOOK_URL → n8n visualización
```

**Tipos de evento:**
- `DOCUMENT_INGESTED` · `GRAPH_SYNCED` · `GRAPH_SYNC_FAILED`
- `CONFLICT_DETECTED` · `DOCUMENT_CLEARED`
- `ARBITRATOR_DECISION` · `HITL_ESCALATION` · `CONFLICT_RESOLVED`
- `ESCALATION_TIMEOUT` · `CORPUS_UPDATED` · `INGEST_FAILED`

Reconstrucción de cualquier ciclo: `SELECT * FROM pipeline_events WHERE operation_id = ? ORDER BY created_at`

#### Las 6 reglas del Entregable 3 (cumplidas en producción)

| Regla | Mecanismo en Korio |
|---|---|
| R1 — Estado único por documento | `chunk_status` ∈ {active, superseded, disputed, inconclusive} + `documents.status` |
| R2 — Cuarentena de conflictos | `disputed`/`inconclusive` incluidos con badge ⚠️ (UX decision) |
| R3 — Inmutabilidad del log | `pipeline_events` + `audit_log` append-only, solo INSERT |
| R4 — Políticas prevalecen sobre reglas base | `policies` tabla; `find_applicable_policy()` llamado PRIMERO |
| R5 — Reactivación manual obligatoria | Timeout → `inconclusive`, excluido hasta intervención admin |
| R6 — Trazabilidad de toda resolución | Cada decisión en `pipeline_events` + `times_applied` en policies |

---

## FASE 2 — RETRIEVAL (RAG HÍBRIDO)

### 2.1 Entrada de la query

```jsonc
// POST /search
{
  "query": "¿Cuál es la jornada laboral del convenio?",
  "user_id": "uuid",
  "tenant_id": "uuid",
  "space_ids": [],           // vacío = todos los spaces del user
  "session_id": "uuid",     // conversación multi-turn
  "history": [              // mensajes previos para reformulación
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**RLS pre-query (early binding en `src/db.py`):**
1. `SELECT space_id FROM user_spaces WHERE user_id = ?` → `allowed_spaces`
2. `SELECT id FROM documents WHERE tenant_id = ? AND space_id IN (...)` → `allowed_doc_ids`

**Módulo:** `src/search.py`

---

### 2.2 Reformulación de query (multi-turn)

Si `history` tiene mensajes previos:

**Modelo:** Mistral API `mistral-small-latest`

`llm_client.reformulate_query(query, history)` → query contextualizada para el embedding.

Ejemplo:
- Turn 1: "¿Cuántas horas semanales trabajan?"
- Turn 2 (sin reformular): "¿Y en el periodo de verano?" → embedding pobre
- Turn 2 (reformulado): "¿Cuántas horas semanales en el periodo de verano según el convenio?" → mejor recall

**Módulo:** `src/llm_client.py` → `reformulate_query()`

---

### 2.3 Embedding de la query

**Mismo modelo que ingesta:** Ollama `nomic-embed-text` 768d

- Caché implícita: queries repetidas pasan por el mismo proceso (~0.8s)
- Latencia medida: **~0.8s en CPX32 AMD**

---

### 2.4 Búsqueda vectorial (pgvector)

```sql
-- RPC search_embeddings (migrations/002 + 005 + 020)
SELECT id, content, similarity, document_id, chunk_status
FROM embeddings
WHERE document_id = ANY($allowed_doc_ids)
  AND 1 - (embedding <=> $query_embedding) >= 0.35   -- threshold
ORDER BY embedding <=> $query_embedding
LIMIT $top_k;  -- default 8-10
```

- Devuelve chunks `active` + `disputed` + `inconclusive` (todos con su `chunk_status`)
- Threshold actual: **0.35** (cosine similarity mínima)
- Sin índice ivfflat actualmente (migración 019 lo eliminó — bug probes=1 con <100 chunks). Reintroducir HNSW cuando >1000 chunks.
- Latencia: **<0.1s**

---

### 2.5 Detección de conflictos silentes en query-time

```sql
-- RPC detect_silent_conflicts_among_chunks (migration/012)
-- Solo aplica entre chunks del MISMO space (migration/016)
SELECT pair_a, pair_b, similarity
FROM chunks_cross_join
WHERE 1 - (a.embedding <=> b.embedding) >= 0.80
  AND a.document_id != b.document_id
  AND a.space_id = b.space_id;
```

Si hay pares → `has_silent_conflict = true` en la respuesta → badge al usuario:
> ⚠️ Existen documentos potencialmente contradictorios sobre este tema. Verificar fuentes.

---

### 2.6 Búsqueda en grafo (FalkorDB — paralela)

`src/graph_client.py` ejecuta en paralelo con pgvector:

```cypher
// Búsqueda por predicado exacto
MATCH (c:Claim {tenant_id: $tid})
WHERE c.space_id IN $allowed_spaces
  AND c.predicate = $predicate
RETURN c

// Búsqueda semántica sobre claims embebidos
MATCH (c:Claim {tenant_id: $tid})
WHERE c.space_id IN $allowed_spaces
ORDER BY vector_distance(c.embedding, $query_embedding)
LIMIT 8
```

**Hito demostrado:** query "jornada mínima" → sin match vectorial en chunks → grafo encuentra claim `("jornada laboral", "es", "35 horas semanales")` vía similitud semántica → respuesta correcta.

---

### 2.7 Reciprocal Rank Fusion (RRF)

Combina resultados de pgvector (chunks) y FalkorDB (claims):

```python
# src/graph_client.py
# RRF k=60
score(d) = Σ 1 / (k + rank_i(d))
```

- Top-8 claims del grafo se fusionan con top-10 chunks vectoriales
- Output: lista unificada ordenada por score RRF
- `graph_contributed = True` si algún claim del grafo aparece en top resultados
- Latencia grafo: **~0.05s** (455 claims embebidos en producción)

---

### 2.8 Generación RAG (LLM)

**Modelo principal:** Mistral API `mistral-small-latest`
**Fallback local:** Ollama `mistral:7b-instruct-q4_K_M` (CPU, ~25s, sin coste marginal)

**Pre-LLM:** segunda pasada Presidio sobre el contexto RAG (`KORIO_REDACT_MISTRAL=1`) — evita enviar PII a Mistral cloud.

**System prompt:**
```
Eres el asistente de conocimiento de {company_name}.
Responde SOLO con la información del CONTEXTO proporcionado.
Si no hay información suficiente, dilo explícitamente.
Cita las fuentes con el formato [Fuente: {filename} | {fecha}].
Idioma de respuesta: español.

CONTEXTO:
{chunks_unificados_con_metadata}
{claims_grafo_si_contribuyen}
```

**Retry:** backoff exponencial ante 429 (rate limit Mistral) — `src/llm_client.py`

**Latencia LLM:** ~2.5s (Mistral API) | ~25s (Ollama fallback CPU)

---

### 2.9 Respuesta

```jsonc
// SearchResponse
{
  "answer": "Según el convenio colectivo, la jornada laboral es de 35 horas...",
  "sources": [
    {
      "document_id": "uuid",
      "filename": "convenio-2026.pdf",
      "chunk_id": "uuid",
      "similarity": 0.92,
      "chunk_status": "active",
      "space": "RRHH",
      "created_at": "2026-01-15"
    }
  ],
  "has_silent_conflict": false,
  "graph_contributed": true,
  "session_id": "uuid",
  "latency_ms": {
    "embedding": 820,
    "vector_search": 87,
    "graph_search": 52,
    "llm_generation": 2480,
    "total": 3439
  }
}
```

**Latencias reales (benchmark 50 iter, sesión 10):**
- p50: **1983 ms**
- p95: **3053 ms**

---

### 2.10 Canales de consulta

| Canal | Cómo llega al backend |
|---|---|
| **Chat web** (`/ui`) | `fetch POST /search` desde JS |
| **Slack `/korio`** | n8n Workflow #6: ACK inmediato + POST `/search` + thread reply |
| **Claude Desktop (MCP)** | FastMCP SSE en `/mcp/sse` → tool `search_knowledge_base` |
| **n8n (otros workflows)** | `HTTP Request` node → `POST /search` |
| **API directa** | `POST /search` con JWT |

---

## FASE 3 — LOG, EVENTOS Y OBSERVABILIDAD

### 3.1 Bus de eventos (`pipeline_events`)

**No es Kafka ni Redis Pub-Sub.** Es una tabla Supabase + webhook best-effort a n8n.

```sql
CREATE TABLE pipeline_events (
  id            BIGSERIAL PRIMARY KEY,
  operation_id  UUID NOT NULL,          -- correlaciona todo el ciclo de 1 documento
  event_type    TEXT NOT NULL,          -- ver tipos abajo
  source_agent  TEXT NOT NULL,          -- ingestor|detector|arbitrator|supervisor|curator|system
  tenant_id     UUID NOT NULL REFERENCES tenants(id),
  document_id   UUID REFERENCES documents(id),
  payload       JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

**Tipos de evento:**
| Evento | Agente emisor | Cuándo |
|---|---|---|
| `DOCUMENT_INGESTED` | ingestor | Commit ACID exitoso |
| `INGEST_FAILED` | ingestor | Error en cualquier fase (payload: phase, error) |
| `GRAPH_SYNCED` | detector | Sync FalkorDB OK |
| `GRAPH_SYNC_FAILED` | detector | FalkorDB KO → encolado en graph_sync_queue |
| `CONFLICT_DETECTED` | detector | Similitud > umbral entre docs |
| `DOCUMENT_CLEARED` | detector | Sin conflicto detectado |
| `ARBITRATOR_DECISION` | arbitrator | Auto-resolución (policy/autoridad/fecha) |
| `HITL_ESCALATION` | supervisor | Email enviado al admin |
| `CONFLICT_RESOLVED` | curator | Respuesta HITL recibida y aplicada |
| `ESCALATION_REMINDER` | supervisor | Recordatorio email (día 3/7/14) |
| `ESCALATION_TIMEOUT` | supervisor | Día 21 → inconclusive |
| `CORPUS_UPDATED` | curator | Cierre del ciclo |

**Workflow n8n `#3 — Pipeline event bus`:** recibe los webhooks de `emit()` y los visualiza en tiempo real (usado durante la defensa TFM).

---

### 3.2 Audit log (append-only)

```sql
CREATE TABLE audit_log (
  id            BIGSERIAL PRIMARY KEY,
  tenant_id     UUID NOT NULL,
  user_id       TEXT,
  action        TEXT,           -- SEARCH, UPLOAD, DELETE_DOCUMENT, RESOLVE_CONFLICT...
  resource_id   UUID,
  query         TEXT,           -- para SEARCH
  results_count INT,
  latency_ms    INT,
  ip_address    INET,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

**Garantías:** solo INSERT, nunca UPDATE/DELETE. RLS por tenant. Retención mínima: según compliance (RGPD — periodo a definir en DPA formal con Mistral, Phase 8).

---

### 3.3 Errores n8n (panel admin)

**Tabla:** `n8n_errors` (migración sesión 12+16)
```sql
n8n_errors (id, workflow_id, workflow_name, error_msg, node_name,
            created_at, reviewed_at, reviewed_by, notes)
```

**Workflow n8n `#8 — Gestión errores n8n`:** Error Trigger global en todos los workflows → INSERT en `n8n_errors` + Slack DM con botón "✅ Marcar reviewed" + throttling (alerta solo si `count===1 || count%10===0`).

**Panel:** `/ui/admin-errors.html` — `GET /admin/errors` + `POST /admin/errors/{id}/review`

**Firma Slack:** `POST /admin/errors/slack-action` con verificación HMAC `v0:ts:body` + anti-replay 5 min.

---

### 3.4 Observabilidad y métricas operativas

#### Métricas actuales (sin sistema de métricas formal — consultadas via Supabase SQL)

| Consulta | Resultado esperado |
|---|---|
| `SELECT COUNT(*) FROM pipeline_events WHERE event_type = 'DOCUMENT_INGESTED' AND created_at > now() - interval '7 days'` | Documentos ingestados esta semana |
| `SELECT COUNT(*) FROM conflict_reviews WHERE status = 'pending'` | Conflictos sin resolver |
| `SELECT policy_name, times_applied FROM policies ORDER BY times_applied DESC` | Políticas más usadas (aprendizaje del sistema) |
| `SELECT COUNT(*) FROM embeddings WHERE chunk_status = 'inconclusive'` | Chunks bloqueados por timeout HITL |

#### Benchmark formal (`scripts/benchmark.py`)

```bash
python scripts/benchmark.py --queries 50 --delay 1.0
```

Output: p50/p95/p99 por operación (embedding, vector, graph, LLM, total).

---

### 3.5 Health y despliegue

**Endpoints:**
```
GET /health     → status de FastAPI
GET /docs       → Swagger UI
GET /ui         → Chat web
GET /ui/graph.html       → Visualización grafo FalkorDB (vis-network)
GET /ui/admin-errors.html → Panel admin errores n8n
GET /mcp/sse    → MCP Server (FastMCP + MCPAuthASGI)
GET /legal/*    → Privacy Policy
```

**Infraestructura:**
```
Hetzner CPX32 AMD EPYC-Genoa (Frankfurt)
  4 vCPU / 8 GB / 160 GB SSD · €17.53/mes máx

  ┌─ nginx (TLS Let's Encrypt) ─────────────────────┐
  │  korio.es → FastAPI :8000 (systemd korio-api)   │
  │  n8n.korio.es → n8n Docker :5678               │
  └─────────────────────────────────────────────────┘

  Docker Compose:
    korio-ollama  :11434  (nomic-embed-text + mistral:7b fallback)
    korio-falkordb :6379  (Redis 8.6.3 + módulo grafo, AOF everysec)
    korio-n8n     :5678   (8 workflows en producción)

Supabase Pro (Frankfurt)
  PostgreSQL + pgvector · 20 migraciones · RLS
  Tablas: tenants, spaces, users, documents, embeddings,
          audit_log, conflict_reviews, policies,
          pipeline_events, graph_sync_queue, mcp_api_keys,
          n8n_errors, waitlist

Mistral AI (cloud · EU)
  mistral-small-latest · generación + extracción structured JSON
  PII redaction pre-envío (whitelist Presidio)
```

---

## ESTADO DE PHASES Y ROADMAP

### Cerrado (v0.3.12 · 18 jun 2026)

| Phase | Contenido |
|---|---|
| 1-2 | Núcleo RAG + multi-tenancy (RLS triple capa) |
| 3-4 | Docs + UI chat + benchmark |
| 5 | Producción VPS + gobernanza activa + HITL email |
| 6 | Cron escalada HITL (3/7/14/21 días) |
| 7.1 | Grafo FalkorDB + entity extractor + RRF |
| 7.2 | Ingesta automática multi-canal (8 workflows n8n) |
| 7.3 | MCP Server (FastMCP + MCPAuthASGI + mcp_api_keys) |
| v0.3.0 | 6 reglas E3 + ACID RPC + bus eventos + query-time conflicts + policies + inconclusive |
| v0.3.4 | Hardening seguridad (21 hallazgos auditados) |
| v0.3.8 | Compliance AI Act + GDPR (PII redaction Mistral + Privacy Policy) |
| v0.3.12 | Phase 9: panel admin errores n8n + Slack interactivity + throttling |

### Planificado post-TFM

| Phase | Bloques clave |
|---|---|
| **Phase 8** | Conectores OAuth multi-tenant (Drive, Slack, Gmail, Outlook, SharePoint); guardrails chat (Presidio egress + Lakera/Rebuff injection); MCP OAuth 2.1 + rate limit; reranker cross-encoder; query expansion; GDPR endpoints (`/export`, `/subject-access`); auth real (Supabase Auth) |
| **Phase 9 SaaS** | Auth + billing Stripe; UI admin conflictos; API keys por tenant; límites de plan; persistencia conversaciones; conectores configurables por UI |
| **Phase 10** | Ingesta multimodal (email body, hilos Slack/Teams, audio Voxtral→Whisper); GPU en Hetzner GEX44 (embed ~0.1s, LLM ~1s, objetivo p50 <1s) |

---

## RESUMEN SIMPLIFICADO (para diagramas)

### Fase 1 — Ingesta

```
FUENTES                    NORMALIZACIÓN              ALMACENAMIENTO
────────                   ─────────────              ──────────────
Upload UI                                             pgvector (Supabase)
Gmail adjuntos   →  MarkItDown+PyMuPDF  →  Presidio  +
Google Drive     →  → Markdown unif.   →  (PII)      FalkorDB (claims)
Slack file_shared →                    →  Chunking   +
                                       →  Ollama     pipeline_events (bus)
                                       →  768d embed →
                                             ↓
                                        RPC ACID (1 transacción)
                                             ↓
                                    Detección conflictos
                                    policy → autoridad → fecha → HITL
                                             ↓
                                    Email + cron escalada (n8n)
```

### Fase 2 — Retrieval

```
QUERY  →  Reformulación (Mistral)  →  Embed (Ollama nomic)
                                              ↓
               ┌──────────────────────────────┤
               ▼                             ▼
        pgvector cosine              FalkorDB Cypher
        (threshold 0.35)             (claims semánticos)
               └──────────── RRF k=60 ───────┘
                                      ↓
                           Detección conflictos silentes
                                      ↓
                           Presidio pre-LLM (redacción PII)
                                      ↓
                        Mistral API (fallback: Ollama local)
                                      ↓
                    Respuesta + fuentes citadas + badges conflictos
```

### Fase 3 — Observabilidad

```
pipeline_events (Supabase append-only)
  → n8n webhook visualización en vivo
  → audit trail por operation_id

audit_log (queries de usuario)
n8n_errors (panel admin + Slack DM + reviewed)
Benchmark (p50=1983ms / p95=3053ms)
```

---

## STACK TECNOLÓGICO (referencia rápida)

| Componente | Tecnología | Dónde corre |
|---|---|---|
| Embeddings | Ollama `nomic-embed-text` 768d | VPS local |
| LLM generación | Mistral API `mistral-small-latest` | Cloud EU |
| LLM extracción entidades | Mistral API `mistral-small-latest` (temp=0.0) | Cloud EU |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` | VPS local |
| Vector store | pgvector en Supabase Pro | Frankfurt EU |
| Graph store | FalkorDB (Redis + Cypher, AOF) | VPS Docker |
| PII detection | Presidio + spaCy `es_core_news_lg` | VPS proceso |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | VPS proceso |
| Doc conversion | MarkItDown + PyMuPDF | VPS proceso |
| Backend API | FastAPI + Uvicorn (Python 3.12) | VPS systemd |
| MCP Server | FastMCP + MCPAuthASGI | VPS (mismo proceso) |
| Automatización | n8n v1.x Docker | VPS Docker |
| Servidor VPS | Hetzner CPX32 AMD EPYC-Genoa | Frankfurt EU |

---

*Generado: 22 junio 2026 · basado en v0.3.12 (sesión 16) · corrige incongruencias del esquema preliminar (LLM=Mistral, embeddings=Ollama local, agentes=roles lógicos en proceso, sin Whisper/Voxtral hasta Phase 10, RRF no cross-encoder, pipeline_events no Kafka).*
