# Korio — Company Brain

> SaaS multi-tenant de RAG para pymes españolas, con **gobernanza activa** del conocimiento.
> TFM · Máster IA Business & Innovation · Nuclio Digital School

Korio permite a una organización consultar en lenguaje natural el conocimiento acumulado en sus documentos internos (PDFs, Word, Excel, Markdown), con:

- **Aislamiento real** entre clientes (multi-tenancy con RLS de Supabase + early binding en aplicación).
- **Aislamiento por departamento** dentro de cada cliente (un médico no ve documentos del departamento Legal).
- **Detección automática de contradicciones** entre documentos al ingestar (auto-resolución por autoridad/fecha, HITL via email para casos ambiguos).

**Estado:** Phase 5 completada · Producción en [korio.es](https://korio.es) · Demo TFM 2 julio 2026

---

## URLs en producción

| URL | Servicio |
|---|---|
| [korio.es](https://korio.es) | Landing teaser de la marca |
| [korio.es/ui](https://korio.es/ui) | App de chat (RAG + ingesta + gobernanza) |
| [korio.es/docs](https://korio.es/docs) | Swagger UI (FastAPI) |
| [n8n.korio.es](https://n8n.korio.es) | Editor de workflows (automatizaciones) |

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
supabase/migrations/004_conflict_reviews.sql  ← Gobernanza activa
supabase/migrations/005_search_with_disputed.sql  ← Search incluye 'disputed'
supabase/migrations/006_tenant_admin_email.sql  ← admin_email por tenant
supabase/migrations/007_waitlist.sql  ← Landing waitlist
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

---

## Stack

| Componente | Tecnología | Notas |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama | **768 dims — fijo** |
| Vector store | pgvector en Supabase | RLS nativo, Frankfurt (GDPR) |
| LLM generación | Mistral API `mistral-small-latest` | ~3s latencia, temp 0.2 |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` | offline en VPS |
| Backend API | FastAPI + Uvicorn, Python 3.12 | systemd service |
| PII detection | Presidio + spaCy `es_core_news_lg` | configurado en español |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Doc parsing | MarkItDown `[pdf,docx,xlsx,pptx]` | |
| Automatización | n8n v1.x (Docker en VPS) | Workflow HITL email |
| Servidor | Hetzner CX32, Frankfurt | 4vCPU/8GB, Ubuntu 24.04 |
| Reverse proxy | nginx + Let's Encrypt (certbot) | renovación automática |

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
python -m pytest tests/ -v                  # 20/20 ✅ (~21s)
python -m pytest tests/test_rls.py -v       # 10/10 RLS ✅ (~1s)
python -m pytest tests/test_search.py -v    # 10/10 RAG ✅ (~20s)
```

---

## Documentación

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Sistema, modelo de datos, RLS
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Setup en Hetzner desde cero
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — Fases pasadas + futuras
- [`CLAUDE.md`](CLAUDE.md) — Memoria del proyecto para Claude Code

---

## Métricas (9 junio 2026)

| Métrica | Valor |
|---|---|
| Tests | 20/20 ✅ |
| Latencia RAG (manual) | ~1.0–3.3s |
| Latencia embedding | ~0.8s |
| Phases completadas | 1 · 2 · 3 · 4 · 5 |
| Producción | korio.es en vivo |

---

## Estructura del proyecto

```
korio/
├── api/
│   └── server.py             # FastAPI: /search, /ingest, /upload, /review, /waitlist, /health
├── src/
│   ├── search.py             # Orquestador RAG
│   ├── ingest.py             # Orquestador ingesta + dedup por content_hash
│   ├── conflict_detector.py  # Detección + auto-resolución + HITL
│   ├── embedder.py           # Wrapper Ollama nomic-embed-text
│   ├── chunker.py            # RecursiveTextSplitter
│   ├── preprocessor.py       # MarkItDown + Presidio (es_core_news_lg)
│   ├── llm_client.py         # Mistral API + Ollama fallback + prompt RAG
│   └── db.py                 # Supabase client + RLS + conflict_reviews
├── ui/                       # App chat (HTML/CSS/JS vanilla)
│   ├── index.html
│   ├── css/styles.css
│   └── js/main.js
├── landing/                  # Landing teaser de korio.es
│   ├── index.html
│   └── assets/               # Logo, favicon, OG image
├── tests/
│   ├── test_rls.py           # 10 tests RLS ✅
│   └── test_search.py        # 10 tests RAG ✅
├── supabase/migrations/      # 7 migraciones SQL
├── docs/                     # ARCHITECTURE, DEPLOYMENT, ROADMAP
├── deploy/                   # systemd, nginx, setup.sh, refresh-landing.sh
├── scripts/                  # benchmark.py
└── data-synthetic/           # Documentos de prueba (en .gitignore)
```

---

## Licencia

TFM — Máster IA Business & Innovation (Nuclio Digital School)

## Autor

**Heriberto Noguera** · [@lagalga](https://github.com/lagalga) · contacto@lagalga.es
