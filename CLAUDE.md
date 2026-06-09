# Korio — CLAUDE.md

## Proyecto

**Korio** (nombre comercial) / **Company Brain** (técnico) — SaaS multi-tenant de RAG para pymes españolas. Permite ingestar documentos internos y consultarlos en lenguaje natural, con control de acceso por departamento (RLS) y multi-tenancy real.

**TFM:** Máster IA Business & Innovation — Nuclio Digital School  
**Demo funcional:** 2 julio 2026  
**Defensa TFM:** 9 julio 2026  
**Repo:** https://github.com/lagalga/korio  

---

## Estado actual (9 junio 2026)

### ✅ Completado — Phases 1–3
- Pipeline ingesta: Documento → MarkItDown → Presidio → Chunking → Embeddings → pgvector
- Pipeline búsqueda RAG: Query → embed → RLS early binding → pgvector → Mistral API → respuesta
- FastAPI server: `POST /search`, `POST /ingest`, `POST /upload`, `GET /health`
- Tests: 20/20 ✅ (test_rls.py × 10 + test_search.py × 10)
- 2 tenants activos con datos sintéticos: Clínica Delos + Despacho García
- RLS verificado: 0 fugas entre tenants y entre espacios
- `docs/ARCHITECTURE.md`, `DEPLOYMENT.md`, `ROADMAP.md` — documentación técnica completa
- README actualizado con quickstart, métricas reales y estructura

### ✅ Phase 4 arrancada (9 junio)
- Chat UI web (`ui/`) — HTML/CSS/JS vanilla, toggle de fuentes, markdown rendering
- Endpoint `POST /upload` — ingesta de ficheros desde el navegador (multipart)
- `scripts/benchmark.py` — medición p50/p95 de latencias RAG por escenario

### 🔲 Pendiente (antes del 2 julio)
- QA end-to-end: 10+ queries en ambos tenants con la UI
- Benchmark formal de latencias (ejecutar scripts/benchmark.py)
- n8n workflows: webhook ingesta + query desde Slack
- MCP Server: exponer Korio como tool para Claude/n8n
- Presentation deck (10–15 slides)

---

## Stack tecnológico

| Componente | Tecnología | Notas |
|---|---|---|
| Embeddings | `nomic-embed-text` via Ollama en VPS | **768 dims — FIJO, no cambiar nunca** |
| Vector store | pgvector en Supabase (Frankfurt) | RLS nativo, GDPR |
| LLM generación | Mistral API `mistral-small-latest` | ~3s latencia |
| LLM fallback | Ollama `mistral:7b-instruct-q4_K_M` en VPS | ~25s CPU, offline |
| Backend API | FastAPI + Uvicorn, Python 3.12 | Swagger en `/docs` |
| PII detection | Presidio + spaCy `es_core_news_lg` | Antes de ingestar |
| Chunking | LangChain `RecursiveCharacterTextSplitter` | 500 tok / 50 overlap |
| Conversión docs | MarkItDown | PDF/DOCX/XLSX → Markdown |
| Servidor | Hetzner CX32, Frankfurt, 4vCPU/8GB | `ssh korio-vps` |
| Base de datos | Supabase Pro, Frankfurt | `pkurvkdmoulfqnngjsjr.supabase.co` |

---

## Infraestructura

```
SSH:        ssh korio-vps   (alias en ~/.ssh/config → 167.233.72.42)
Supabase:   https://pkurvkdmoulfqnngjsjr.supabase.co
Ollama VPS: http://167.233.72.42:11434
Docker:     docker exec korio-ollama ollama list
```

### VPS — comandos útiles
```bash
ssh korio-vps
docker ps                                    # ver contenedores
docker exec korio-ollama ollama list         # modelos cargados
docker logs korio-ollama --tail 50           # logs Ollama
```

---

## Estructura del proyecto

```
korio/
├── CLAUDE.md                    # Este fichero (memoria del proyecto)
├── README.md
├── .env                         # Credenciales reales (no en git)
├── .env.example                 # Template
├── docker-compose.yml           # Ollama en VPS
├── requirements.txt
│
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql   # Schema + RLS + seed data
│       ├── 002_search_function.sql  # search_embeddings(vector(768))
│       └── 003_fix_vector_dims.sql  # Corrección 384→768 dims
│
├── src/
│   ├── ingest.py        # CLI ingesta: doc → chunks → pgvector
│   ├── search.py        # CLI búsqueda: query → RAG → respuesta
│   ├── embedder.py      # Wrapper Ollama nomic-embed-text, 768 dims
│   ├── chunker.py       # RecursiveTextSplitter
│   ├── preprocessor.py  # MarkItDown + Presidio
│   ├── llm_client.py    # Mistral API + Ollama fallback
│   ├── db.py            # Supabase client, RLS early binding, audit log
│   └── utils.py
│
├── api/
│   ├── __init__.py
│   └── server.py        # FastAPI: /search, /ingest, /upload, /health
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # Fixtures: UUIDs seed (tenants, users, spaces)
│   ├── test_rls.py      # 10 tests aislamiento (10/10 ✅)
│   └── test_search.py   # 10 tests RAG (10/10 ✅)
│
├── data-synthetic/      # Documentos de prueba (en .gitignore)
│   ├── delos_politica_rrhh.md
│   ├── delos_protocolo_admision.md
│   ├── delos_acta_junta_directiva.md
│   ├── garcia_caso_laboral.md
│   ├── garcia_dictamen_fiscal.md
│   └── garcia_protocolo_clientes.md
│
├── ui/                  # Chat UI web (Phase 4)
│   ├── index.html
│   ├── css/styles.css
│   └── js/main.js
│
├── scripts/
│   └── benchmark.py     # Medición latencias p50/p95 por escenario
│
└── docs/
    ├── ARCHITECTURE.md  # Diagrama del sistema, modelo de datos, RLS
    ├── DEPLOYMENT.md    # Setup en Hetzner desde cero
    └── ROADMAP.md       # Fases post-TFM detalladas
```

---

## Entorno de desarrollo

```bash
# Activar venv (siempre antes de ejecutar)
cd "/Users/berto/Claude Code/korio"
source .venv/bin/activate

# Tests
python -m pytest tests/test_rls.py -v        # RLS (10 tests, ~1s)
python -m pytest tests/test_search.py -v     # RAG (10 tests, ~20s)
python -m pytest tests/ -v                   # Todos (20/20)

# Ingesta
python src/ingest.py data-synthetic/FILE.md \
  --tenant-id <uuid> --space-id <uuid>

# Búsqueda
python src/search.py "¿pregunta?" --user-id <uuid> --tenant-id <uuid>

# Servidor FastAPI (arrancar desde el directorio del proyecto/worktree)
python -m uvicorn api.server:app --reload --port 8000
# Swagger: http://localhost:8000/docs
# UI:      http://localhost:8000/ui

# UI (servidor estático alternativo, sin FastAPI)
python -m http.server 3000 --directory ui

# Benchmark de latencias (requiere servidor en :8000)
python scripts/benchmark.py                     # 5 iter por escenario
python scripts/benchmark.py -n 10 -o out.json  # 10 iter + JSON
```

---

## Datos de prueba (Supabase — producción real)

### Tenant 1: Clínica Delos
```
tenant_id:  a0000000-0000-0000-0000-000000000001

Spaces:
  RRHH:    a1000000-0000-0000-0000-000000000001
  Médico:  a1000000-0000-0000-0000-000000000002
  Legal:   a1000000-0000-0000-0000-000000000003

Users:
  admin:   a1000000-0000-0000-0000-000000000001  (RRHH + Médico + Legal)
  doctor:  a2000000-0000-0000-0000-000000000001  (RRHH + Médico)
  staff:   a3000000-0000-0000-0000-000000000001  (solo RRHH)
```

### Tenant 2: Despacho Legal García
```
tenant_id:  b0000000-0000-0000-0000-000000000002

Spaces:
  Casos:   b1000000-0000-0000-0000-000000000001
  Fiscal:  b1000000-0000-0000-0000-000000000002

Users:
  admin:   b1000000-0000-0000-0000-000000000002  (Casos + Fiscal)
  lawyer:  b2000000-0000-0000-0000-000000000002  (solo Casos)
```

---

## RLS — CRÍTICO

El early binding es el corazón del sistema. Nunca saltarlo:

1. `db.py` obtiene `space_ids` del usuario ANTES del vector search
2. Filtra `document_ids` permitidos para esos spaces
3. El vector search usa `WHERE document_id = ANY(allowed_doc_ids)`
4. Doble capa: aplicación + políticas RLS de Supabase

**Si falla RLS, todo el modelo de seguridad se colapsa.**

---

## Modelos — FIJOS para el TFM

| Modelo | Uso | Dimensiones |
|--------|-----|-------------|
| `nomic-embed-text` | Embeddings ingesta + query | **768 dims — INMUTABLE** |
| `mistral-small-latest` | Generación (Mistral API) | temp 0.2 |
| `mistral:7b-instruct-q4_K_M` | Fallback Ollama | temp 0.2 |

**Cambiar el modelo de embeddings requiere re-ingestar TODOS los documentos.**

---

## Convenciones de código

- **Comentarios y docs:** ESPAÑOL
- **Código (variables, funciones, clases):** INGLÉS
- **Indentación:** 2 espacios (pero Python usa 4 por convención, respetar)
- **Type hints:** siempre en funciones Python
- **Docstrings:** en español
- **Commits:** `Feat: título en inglés` + descripción en español

---

## Métricas reales (9 junio 2026)

- Latencia RAG con Mistral API: **~3.3s** (p50 manual, pendiente benchmark.py formal)
- Latencia embedding (Ollama CPU): **~0.8s**
- Tests completos (20): **~20s**
- Chunks en producción: **~27** (6 docs × ~4.5 chunks/doc promedio)

---

## Notion — Páginas clave del proyecto

| Página | URL | Uso |
|--------|-----|-----|
| Estado técnico (síntesis TFM) | https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a | Fuente de verdad técnica para Claude Chat |
| Historial de Desarrollo | dentro de Log y Troubleshooting | 12 entradas con fechas y hitos reales |
| Roadmap & Tareas | https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533 | Checklist phases |
| Company Brain proceso completo | https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6 | Descripción funcional |
| Stack, costes e infraestructura | https://app.notion.com/p/3782e8533b4481f6a98ed9b46877d170 | Detalle costes |

---

## Reglas

1. Responder siempre en **español**
2. RLS verificado desde el día 1 — nunca saltarlo
3. Modelo embeddings `nomic-embed-text` **768 dims** — nunca cambiar
4. No agregar dependencias sin consultar
5. Documentar decisiones en Notion después de cada sesión
6. Commits atómicos con mensaje claro

---

*Actualizado: 9 junio 2026 — Phase 3 completada · Phase 4 en progreso*
