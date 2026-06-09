# Korio — Company Brain

> RAG multi-tenant para pymes españolas  
> TFM · Máster IA Business & Innovation · Nuclio Digital School

Korio permite a pequeñas empresas consultar en lenguaje natural el conocimiento acumulado en sus documentos internos (PDFs, Word, Excel, Markdown), con aislamiento de datos real entre departamentos y entre clientes.

**Estado:** Phase 2 completada · Demo 2 julio 2026

---

## Quickstart

### Requisitos

- Python 3.12+
- Docker + Docker Compose
- Cuenta Supabase (Pro, $25/mes — Frankfurt)
- API key de Mistral AI

### 1. Clonar y configurar

```bash
git clone https://github.com/lagalga/korio.git
cd korio

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# spaCy model (necesario para Presidio)
python -m spacy download es_core_news_lg

cp .env.example .env
# Editar .env con credenciales Supabase y Mistral API key
```

### 2. Levantar Ollama

```bash
docker compose up -d ollama

# Descargar modelos
docker exec korio-ollama ollama pull nomic-embed-text
docker exec korio-ollama ollama pull mistral:7b-instruct-q4_K_M
```

### 3. Schema en Supabase

En el SQL Editor de Supabase, ejecutar en orden:
1. `supabase/migrations/001_initial_schema.sql`
2. `supabase/migrations/002_search_function.sql`
3. `supabase/migrations/003_fix_vector_dims.sql`

### 4. Tests

```bash
python -m pytest tests/ -v
# Esperado: 20/20 tests ✅
```

### 5. Levantar API

```bash
python -m uvicorn api.server:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
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

```
USUARIO QUERY
    │
    ▼
[FastAPI /search]
    │
    ├── 1. Embed Query ──────────► nomic-embed-text (768 dims, ~0.8s)
    │
    ├── 2. RLS Early Binding ────► user → spaces → documents
    │
    ├── 3. Vector Search ────────► pgvector cosine similarity (top-5)
    │
    ├── 4. Context Assembly ─────► chunks + metadata de fuente
    │
    └── 5. LLM Generation ───────► Mistral API (~2.5s) | Ollama fallback
    │
    ▼
RESPUESTA + CITAS DE FUENTE
```

**RLS en dos capas:** early binding en aplicación + políticas RLS de Supabase. Un usuario del Despacho García nunca puede ver datos de la Clínica Delos, ni un médico puede ver documentos del departamento Legal.

---

## Stack

| Componente | Tecnología |
|---|---|
| Embeddings | `nomic-embed-text` via Ollama · **768 dims** |
| Vector store | pgvector en Supabase · RLS nativo · Frankfurt (GDPR) |
| LLM generación | Mistral API `mistral-small-latest` · ~3.3s |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` · offline |
| Backend | FastAPI + Uvicorn · Python 3.12 |
| PII | Presidio + spaCy `es_core_news_lg` |
| Chunking | LangChain `RecursiveCharacterTextSplitter` · 500 tok/50 overlap |
| Doc parsing | MarkItDown · PDF/DOCX/XLSX → Markdown |
| VPS | Hetzner CX32 · Frankfurt · 4vCPU/8GB |

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
# Todos los tests
python -m pytest tests/ -v                  # 20/20 ✅ (~20s)

# RLS — aislamiento entre tenants y usuarios
python -m pytest tests/test_rls.py -v       # 10/10 ✅ (~1s)

# RAG — calidad de búsqueda y respuesta
python -m pytest tests/test_search.py -v    # 10/10 ✅ (~20s)
```

---

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Diagrama del sistema, modelo de datos, RLS
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Setup completo en Hetzner desde cero
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Fases post-TFM: n8n, MCP Server, interfaz web
- [`CLAUDE.md`](CLAUDE.md) — Instrucciones de desarrollo para Claude Code

---

## Métricas (junio 2026)

| Métrica | Valor |
|---|---|
| Tests | 20/20 ✅ |
| Latencia RAG (p50) | ~3.3s |
| Latencia embedding | ~0.8s |
| Chunks en producción | ~27 (6 docs) |
| Tenants activos | 2 |

---

## Estructura del proyecto

```
korio/
├── api/
│   └── server.py        # FastAPI: /search, /ingest, /health
├── src/
│   ├── search.py        # Orquestador RAG
│   ├── ingest.py        # Orquestador ingesta
│   ├── embedder.py      # Wrapper Ollama nomic-embed-text
│   ├── chunker.py       # RecursiveTextSplitter
│   ├── preprocessor.py  # MarkItDown + Presidio
│   ├── llm_client.py    # Mistral API + Ollama fallback
│   └── db.py            # Supabase client + RLS
├── tests/
│   ├── test_rls.py      # 10 tests RLS ✅
│   └── test_search.py   # 10 tests RAG ✅
├── supabase/
│   └── migrations/      # Schema + RLS + función pgvector
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── ROADMAP.md
└── data-synthetic/      # Documentos de prueba (en .gitignore)
```

---

## Licencia

TFM — Máster IA Business & Innovation (Nuclio Digital School)

## Autor

**Heriberto Noguera** · [@lagalga](https://github.com/lagalga) · contacto@lagalga.es
