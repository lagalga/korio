# Korio — CLAUDE.md

## Proyecto

**Korio** es un servicio SaaS multi-tenant de **RAG agéntico con grafo semántico temporal**, posicionado para pymes españolas (3–50 empleados). El cliente conecta sus fuentes de conocimiento (Drive, Slack, Salesforce, email, Notion) y obtiene un cerebro corporativo consultable.

**Nombre comercial:** Korio  
**Descripción técnica:** Company Brain  
**TFM:** Máster IA Business & Innovation (Nuclio Digital School)  
**Entrega:** 9 julio 2026  
**Demo:** 2 julio 2026  

---

## Stack tecnológico

### Infraestructura (self-hosted, EU)
- **VPS:** Hetzner CX32 (Frankfurt) — €8/mes
- **Vector DB:** Supabase pgvector (Frankfurt) — $25/mes Pro
- **Graph Store:** FalkorDB (self-hosted en Hetzner)
- **LLM Local:** Ollama + Mistral 7B (CPU, ~5-10s latencia)
- **Embeddings:** nomic-embed-text (384 dims, local)
- **Privacidad:** Microsoft Presidio (PII detection)

### Stack actual (LEAN TFM)
```
Ingesta:     Documento → MarkItDown → Presidio → Chunking → Embeddings
Almacenamiento: pgvector (Supabase) + RLS
Búsqueda:    Query → Vector search → LLM generación → Respuesta con cita
```

**Nota:** Sin grafo complejo, sin HITL, sin MCP Server (post-TFM).

---

## Estructura del proyecto

```
korio/
├── CLAUDE.md                    # Este fichero
├── README.md                    # Público: quickstart + arquitectura
├── .env.example                 # Variables de entorno
├── docker-compose.yml           # Ollama + FalkorDB + Postgres local
├── requirements.txt             # Python deps
├── .gitignore
│
├── supabase/
│   ├── migrations/
│   │   └── 001_initial_schema.sql    # Schema + RLS
│   └── seed.sql                      # Datos de prueba
│
├── src/
│   ├── ingest.py               # Script ingesta: documento → embeddings
│   ├── search.py               # Script búsqueda: query → respuesta
│   ├── embedder.py             # Wrapper Ollama + nomic-embed-text
│   ├── chunker.py              # RecursiveTextSplitter
│   ├── preprocessor.py         # MarkItDown + Presidio
│   ├── llm_client.py           # Wrapper Ollama Mistral 7B
│   ├── db.py                   # Conexión Supabase (RLS + auth)
│   └── utils.py                # Helpers
│
├── api/
│   └── server.py               # FastAPI: POST /search, POST /ingest
│
├── tests/
│   ├── test_rls.py            # RLS early binding verificado
│   ├── test_ingesta.py        # Ingesta funciona
│   ├── test_search.py         # Search + RLS
│   └── conftest.py            # Fixtures
│
├── data-synthetic/
│   ├── README.md              # Cómo generar datos sintéticos
│   └── (documentos de prueba)
│
└── docs/
    ├── ARCHITECTURE.md        # Diagrama + flujo
    ├── DEPLOYMENT.md          # Cómo levantar en Hetzner
    └── ROADMAP.md            # Post-TFM (grafo, HITL, MCP)
```

---

## Convenciones de código

### General
- **Idioma comentarios/docs:** ESPAÑOL
- **Idioma código:** INGLÉS (variables, funciones, clases)
- **Indentación:** 2 espacios
- **Comillas JS:** simples (`'`)
- **Comillas HTML:** dobles (`"`)

### Python
- `const` y `let` equivalentes: `from typing import Final`
- Type hints siempre
- Docstrings en español
- Linting: `black`, `flake8` (opcional para MVP)

### Git
- Commit message: "Feat: …" o "Fix: …" (en inglés)
- Descripción del cambio: español
- Ejemplo: `Feat: implement RAG search pipeline - Implementa búsqueda vectorial con pgvector`

---

## Primeros pasos (Fase 1: Setup + Ingesta)

### 1. Setup local
```bash
cd korio
cp .env.example .env
# Editar .env con credenciales Supabase

docker-compose up -d
# Espera a que Ollama, FalkorDB, Postgres estén healthy
```

### 2. Descargar modelos Ollama
```bash
curl http://localhost:11434/api/pull -d '{"name": "mistral:7b-instruct-q4_K_M"}'
curl http://localhost:11434/api/pull -d '{"name": "nomic-embed-text"}'
```

### 3. Schema Supabase
Ejecutar `supabase/migrations/001_initial_schema.sql` en Supabase dashboard (SQL editor).

### 4. Primeros scripts
```bash
python src/ingest.py data-synthetic/sample_01.md
python src/search.py "¿Qué dice el documento?"
```

---

## RLS (Row-Level Security) — CRÍTICO

**El early binding de RLS es el corazón del sistema.** Nunca lo saltes para "probar más rápido":

1. Toda query a pgvector pasa por `WHERE document_id IN (SELECT ... WHERE user_id = auth.uid())`
2. Las políticas RLS están activas desde `001_initial_schema.sql`
3. Los tests (`test_rls.py`) verifican que Usuario A NO ve datos de Usuario B
4. Si falla RLS, todo el modelo de seguridad se colapsa

---

## Modelos (FIJOS para el TFM)

| Modelo | Uso | Parámetro |
|--------|-----|-----------|
| **nomic-embed-text** | Embeddings (ingesta + query) | 384 dims — NUNCA cambiar |
| **Mistral 7B** | Generación (búsqueda + respuesta) | temp 0.2–0.4 |

Si necesitas cambiar el modelo de embeddings, hay que **re-ingestar TODO**.

---

## Decisiones de diseño

| Decisión | Razón |
|----------|-------|
| CPU sin GPU | Prototipo TFM; latencia aceptable 5-10s |
| pgvector + RLS | Multi-tenancy nativo; GDPR Frankfurt |
| Sin grafo | Reduce scope; MVP viable sin grafos |
| Sin HITL | Simplificar; resolución manual después |
| Sin MCP Server | Post-TFM; RAG + RLS es lo crítico |

---

## Testing

```bash
# Ingesta
python -m pytest tests/test_ingesta.py -v

# Búsqueda
python -m pytest tests/test_search.py -v

# RLS (MÁS IMPORTANTE)
python -m pytest tests/test_rls.py -v
```

---

## Reglas

1. **Siempre responder en español**
2. **Documentar decisiones en Notion**
3. **RLS verificado desde día 1**
4. **Datos sintéticos antes de queries**
5. **No agregar dependencias sin consultar**
6. **Commits atómicos + mensajes claros**

---

## URLs y acceso

| Recurso | URL/Info |
|---------|----------|
| Ollama local | http://localhost:11434 |
| FalkorDB local | redis://localhost:6379 |
| Postgres local | postgres://korio@localhost:5432/korio |
| Supabase | https://pkurvkdmoulfqnngjsjr.supabase.co |
| VPS Hetzner | 167.233.72.42 |

---

*Actualizado: 8 junio 2026*
