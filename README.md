# Korio — Company Brain TFM

> **RAG agéntico multi-tenant con grafo semántico temporal** para pymes españolas.

Korio es un prototipo de sistema de IA que permite a pequeñas empresas construir su "cerebro corporativo" conectando múltiples fuentes de datos (Drive, Slack, Salesforce, email, Notion) y realizando búsquedas inteligentes sobre todo el conocimiento acumulado.

**Status:** Fase 1 (Setup + Ingesta) — Demo 2 julio 2026

---

## 🚀 Quickstart

### Requisitos
- Docker + Docker Compose
- Python 3.10+
- Supabase account (Pro, $25/mes)
- Hetzner VPS (CX32, €8/mes)

### 1. Clonar y setup
```bash
git clone https://github.com/lagalga/korio.git
cd korio

cp .env.example .env
# Editar .env con credenciales Supabase

docker-compose up -d
# Espera healthchecks

pip install -r requirements.txt
```

### 2. Descargar modelos LLM
```bash
# Mistral 7B (generación)
curl http://localhost:11434/api/pull -d '{"name": "mistral:7b-instruct-q4_K_M"}'

# nomic-embed-text (embeddings)
curl http://localhost:11434/api/pull -d '{"name": "nomic-embed-text"}'
```

### 3. Supabase schema
Abre [Supabase SQL Editor](https://supabase.com) y ejecuta:
```sql
-- Leer contenido de supabase/migrations/001_initial_schema.sql
```

### 4. Test end-to-end
```bash
python src/ingest.py data-synthetic/sample_01.md
python src/search.py "¿Qué documento ingresté?"
```

---

## 🏗️ Arquitectura (LEAN)

```
USUARIO QUERY
    ↓
[RLS Early Binding] ← Verificar permiso
    ↓
[Embed Query] (nomic-embed-text)
    ↓
[Vector Search] (pgvector cosine similarity, top-5)
    ↓
[Assemble Context] (chunks + metadata)
    ↓
[LLM Generation] (Ollama Mistral 7B, temp 0.2)
    ↓
RESPUESTA + CITA
```

**Sin grafo, sin HITL, sin MCP Server (post-TFM).**

---

## 📁 Estructura

```
korio/
├── src/              # Código principal Python
│   ├── ingest.py    # Documento → chunks → embeddings
│   ├── search.py    # Query → respuesta
│   ├── embedder.py  # Wrapper Ollama
│   └── ...
├── tests/            # Test suite
│   ├── test_rls.py  # ⚠️ CRÍTICO: RLS verification
│   └── ...
├── supabase/        # Schema + seed data
├── docs/            # Documentación técnica
└── data-synthetic/  # Datos de prueba (clínica/despacho)
```

---

## 🔐 Seguridad: RLS desde día 1

**Row-Level Security (RLS) es fundamental.** No puedes:
- Saltarte la verificación de permisos
- Ver datos de otros tenants/usuarios
- Cambiar modelos de embeddings mid-project

Cada query verifica:
```sql
-- Pseudocódigo
SELECT * FROM embeddings
WHERE document_id IN (
  SELECT id FROM documents
  WHERE space_id IN (
    SELECT space_id FROM user_spaces
    WHERE user_id = auth.uid()  ← Early binding
  )
)
```

---

## 📊 Stack

| Componente | Tecnología | Rol |
|-----------|-----------|-----|
| **Vector Store** | pgvector (Supabase) | Búsqueda + RLS |
| **LLM** | Mistral 7B (Ollama) | Generación |
| **Embeddings** | nomic-embed-text | 384 dims |
| **Privacidad** | Presidio + Ollama local | PII detection, sin llamadas externas |
| **Infraestructura** | Hetzner (EU) | GDPR compliant |

---

## 🧪 Testing

```bash
# Todo
pytest tests/ -v

# Solo RLS (más importante)
pytest tests/test_rls.py -v

# Ingesta
pytest tests/test_ingesta.py -v
```

---

## 🗺️ Roadmap POST-TFM

- [ ] Grafo temporal (Graphiti)
- [ ] Detección de conflictos + resolución por autoridad
- [ ] HITL básico (alerta email + resolución manual)
- [ ] MCP Server (TypeScript)
- [ ] GPU en Hetzner (latency < 1s)
- [ ] Slack bot (Bolt)

---

## 📚 Documentación

- **`CLAUDE.md`** — Instrucciones para Claude Code
- **`docs/ARCHITECTURE.md`** — Flujo detallado + diagramas
- **`docs/DEPLOYMENT.md`** — Setup en producción (Hetzner)
- **`docs/ROADMAP.md`** — Post-TFM features

---

## 📝 Licencia

TFM — Máster IA Business & Innovation (Nuclio Digital School)

---

## 👨‍💼 Contacto

- **Autor:** Berto (@lagalga)
- **Email:** contacto@lagalga.es
- **GitHub:** https://github.com/lagalga/korio

---

*Construyendo el cerebro corporativo de las pymes españolas.*
