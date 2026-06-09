# Korio — Arquitectura del Sistema

> Company Brain · RAG multi-tenant para pymes españolas  
> Versión: Phase 2 completada · Junio 2026

---

## Visión general

Korio es un sistema de RAG (*Retrieval-Augmented Generation*) multi-tenant que permite a pequeñas empresas consultar en lenguaje natural el conocimiento acumulado en sus documentos internos, con aislamiento de datos garantizado entre tenants y entre departamentos.

```
USUARIO
  │
  │  POST /search {"query": "...", "user_id": "..."}
  ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI (api/server.py)                │
│            POST /search · POST /ingest · GET /health     │
└──────────────────┬───────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────┐
│                  PIPELINE DE BÚSQUEDA                    │
│                                                          │
│  1. Embed Query ──────► Ollama nomic-embed-text          │
│     (embedder.py)        768 dims · ~0.8s               │
│                                                          │
│  2. RLS Early Binding ► Supabase (user_spaces)           │
│     (db.py)              user → spaces → documents       │
│                                                          │
│  3. Vector Search ────► pgvector cosine similarity       │
│     (db.py RPC)          WHERE doc_id IN allowed_docs    │
│                                                          │
│  4. Context Assembly ─► top-5 chunks + metadata          │
│     (search.py)                                          │
│                                                          │
│  5. LLM Generation ───► Mistral API (primario)           │
│     (llm_client.py)      Ollama fallback (offline)       │
│                          ~3.3s total                     │
│                                                          │
│  6. Audit Log ────────► Supabase audit_log               │
│     (db.py)              tenant+user+query+latencia      │
└──────────────────────────────────────────────────────────┘
```

---

## Pipeline de ingesta

```
FICHERO (PDF / DOCX / XLSX / MD / TXT)
  │
  ▼
┌────────────────────────────────────────────────────────┐
│               PIPELINE DE INGESTA (ingest.py)          │
│                                                        │
│  1. MarkItDown ──────► Markdown normalizado            │
│     (preprocessor.py)  PDF/DOCX/XLSX → texto limpio   │
│                                                        │
│  2. Presidio ─────────► PII detection + pseudonimiz.  │
│     (preprocessor.py)  spaCy es_core_news_lg           │
│                        nombres, DNI, teléfonos, email  │
│                                                        │
│  3. Chunking ─────────► fragmentos de ~500 tokens      │
│     (chunker.py)        RecursiveCharacterTextSplitter │
│                         50 tokens de solapamiento      │
│                                                        │
│  4. Embedding ────────► vector de 768 dims por chunk   │
│     (embedder.py)       Ollama nomic-embed-text        │
│                                                        │
│  5. Almacenamiento ───► Supabase pgvector              │
│     (db.py)             tabla embeddings               │
│                         + metadata en tabla documents  │
└────────────────────────────────────────────────────────┘
  │
  ▼
pgvector: embeddings(id, document_id, content, embedding vector(768))
```

---

## Modelo de datos

### Tablas principales (Supabase / PostgreSQL + pgvector)

```sql
tenants          -- empresa cliente (multi-tenancy)
  id uuid PK
  name text
  plan text

spaces           -- departamento o área de conocimiento
  id uuid PK
  tenant_id uuid → tenants
  name text

users            -- usuario de la plataforma
  id uuid PK
  tenant_id uuid → tenants
  email text

user_spaces      -- control de acceso: qué espacios ve cada usuario
  user_id uuid → users
  space_id uuid → spaces

documents        -- documento ingestado
  id uuid PK
  tenant_id uuid → tenants
  space_id uuid → spaces
  filename text
  source_type text    -- manual | drive | slack | email | notion
  pii_found int
  created_at timestamptz

embeddings       -- chunk + vector
  id uuid PK
  document_id uuid → documents
  content text
  embedding vector(768)    -- nomic-embed-text, INMUTABLE
  chunk_index int

audit_log        -- trazabilidad de queries
  id uuid PK
  tenant_id uuid
  user_id uuid
  query text
  doc_ids_used uuid[]
  model_used text
  latency_ms int
  has_conflict bool
  created_at timestamptz
```

### Función RPC para vector search

```sql
-- supabase/migrations/002_search_function.sql
CREATE FUNCTION search_embeddings(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  allowed_doc_ids uuid[]
)
RETURNS TABLE (id uuid, content text, similarity float, document_id uuid)
LANGUAGE sql STABLE AS $$
  SELECT id, content,
    1 - (embedding <=> query_embedding) AS similarity,
    document_id
  FROM embeddings
  WHERE document_id = ANY(allowed_doc_ids)
    AND 1 - (embedding <=> query_embedding) > match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
```

---

## RLS — Modelo de seguridad

El aislamiento es doble: a nivel de aplicación (*early binding*) y a nivel de base de datos (RLS nativo de Supabase).

```
query("¿vacaciones?", user_id="doctor-uuid")
  │
  ├─ 1. App: user_spaces WHERE user_id = 'doctor-uuid'
  │         → [space_rrhh, space_medico]
  │
  ├─ 2. App: documents WHERE space_id IN [rrhh, medico]
  │         → [doc-001, doc-003, doc-005]
  │
  ├─ 3. pgvector: SELECT ... FROM embeddings
  │               WHERE document_id = ANY([doc-001, doc-003, doc-005])
  │
  └─ resultado: SOLO documentos del doctor, NUNCA datos de Legal ni de García
```

**Por qué doble capa:** las políticas RLS de Supabase son el backstop; el early binding en aplicación es la primera línea y permite construir el contexto RAG sin depender de los policies PostgreSQL en el hot path.

---

## Tenants de prueba

### Clínica Delos (`a0000000-0000-0000-0000-000000000001`)

| Usuario | Espacios visibles | Documentos |
|---------|-------------------|-----------|
| admin   | RRHH + Médico + Legal | todos |
| doctor  | RRHH + Médico | política RRHH, protocolo admisión |
| staff   | solo RRHH | solo política RRHH |

### Despacho Legal García (`b0000000-0000-0000-0000-000000000002`)

| Usuario | Espacios visibles | Documentos |
|---------|-------------------|-----------|
| admin   | Casos + Fiscal | todos |
| lawyer  | solo Casos | solo casos laborales |

---

## Stack tecnológico

| Componente | Tecnología | Decisión |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama | 768 dims, multilingüe, self-hosted |
| Vector store | pgvector en Supabase | RLS nativo, GDPR (Frankfurt) |
| LLM generación | Mistral API `mistral-small-latest` | ~3.3s, buena calidad en español |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` | ~25s CPU, funciona offline |
| Backend API | FastAPI + Uvicorn | Swagger en `/docs`, async |
| PII detection | Presidio + spaCy `es_core_news_lg` | Antes de ingestar, local |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Conversión docs | MarkItDown | PDF/DOCX/XLSX/HTML → Markdown |
| Servidor VPS | Hetzner CX32, Frankfurt | 4vCPU/8GB, €8/mes |

---

## Latencias reales (junio 2026)

| Operación | Mediana | Notas |
|---|---|---|
| Embedding query | ~0.8s | Ollama CPU en Hetzner CX32 |
| Vector search pgvector | <0.1s | top-5, ~27 chunks en BD |
| LLM generation (Mistral API) | ~2.5s | `mistral-small-latest` |
| **Total RAG end-to-end** | **~3.3s** | p50 con Mistral API |
| Ingesta documento (~4 chunks) | ~4s | embed 4 chunks + insert |

---

## Diagrama de despliegue

```
┌─── Cliente ───────────────────────────────────────────────┐
│  Browser / curl / n8n webhook                             │
└──────────────────────┬────────────────────────────────────┘
                       │ HTTPS
                       ▼
┌─── Hetzner CX32 (Frankfurt) ─────────────────────────────┐
│                                                           │
│  ┌─────────────────────────────────┐                      │
│  │  FastAPI + Uvicorn :8000        │                      │
│  │  (proceso systemd: korio-api)   │                      │
│  └────────────────┬────────────────┘                      │
│                   │                                       │
│  ┌────────────────▼────────────────┐                      │
│  │  Docker: korio-ollama :11434    │                      │
│  │  nomic-embed-text (768 dims)    │                      │
│  │  mistral:7b-instruct-q4_K_M     │                      │
│  └─────────────────────────────────┘                      │
│                                                           │
└───────────────────────────────────────────────────────────┘
                       │
                       │ Supabase REST API + pgvector
                       ▼
┌─── Supabase Pro (Frankfurt) ─────────────────────────────┐
│  PostgreSQL + pgvector                                    │
│  RLS policies                                             │
│  Tablas: tenants, spaces, users, documents, embeddings   │
│  Función RPC: search_embeddings(vector(768), ...)        │
└───────────────────────────────────────────────────────────┘
                       │
                       │ Mistral API
                       ▼
┌─── Mistral AI (cloud) ───────────────────────────────────┐
│  mistral-small-latest                                     │
│  Generación de respuesta final (~2.5s)                   │
└───────────────────────────────────────────────────────────┘
```

---

## Módulos del código fuente

| Fichero | Responsabilidad |
|---|---|
| `api/server.py` | FastAPI: endpoints `/search`, `/ingest`, `/health` |
| `src/search.py` | Orquestador del pipeline RAG |
| `src/ingest.py` | Orquestador del pipeline de ingesta |
| `src/embedder.py` | Wrapper Ollama `nomic-embed-text` |
| `src/chunker.py` | `RecursiveCharacterTextSplitter` |
| `src/preprocessor.py` | MarkItDown + Presidio |
| `src/llm_client.py` | Mistral API + fallback Ollama |
| `src/db.py` | Supabase client, RLS early binding, audit log |
| `tests/test_rls.py` | 10 tests de aislamiento RLS ✅ |
| `tests/test_search.py` | 10 tests de calidad RAG ✅ |

---

*Actualizado: junio 2026 — Phase 2 completada*
