# Korio — Roadmap

> Estado actual: Phase 2 completada (junio 2026) · Demo TFM: 2 julio 2026

---

## Estado actual (Phase 2)

| Feature | Estado |
|---|---|
| Pipeline ingesta (MarkItDown → Presidio → Chunking → pgvector) | ✅ |
| Pipeline RAG (Query → Embed → RLS → pgvector → Mistral) | ✅ |
| FastAPI server (`/search`, `/ingest`, `/health`) | ✅ |
| Multi-tenancy real (RLS + early binding) | ✅ |
| 2 tenants con datos sintéticos (Delos + García) | ✅ |
| Test suite 20/20 | ✅ |
| PII detection con Presidio | ✅ |
| Mistral API + Ollama fallback | ✅ |

---

## Phase 3 — TFM (antes 2 julio 2026)

Objetivo: demo funcional para la presentación del TFM.

| Tarea | Prioridad |
|---|---|
| `docs/ARCHITECTURE.md` | ✅ |
| `docs/DEPLOYMENT.md` | ✅ |
| `docs/ROADMAP.md` (este fichero) | ✅ |
| README final con quickstart actualizado | ✅ |
| QA end-to-end: 10+ queries en ambos tenants | 🔲 |
| Medición formal de latencias (p50, p95) | 🔲 |
| Presentation deck (10–15 slides) | 🔲 |

---

## Fase 4 — Post-TFM: Integración n8n + Interfaz web

Conectar Korio con el ecosistema de automatización y construir una UI básica.

### 4.1 n8n workflows

| Feature | Descripción |
|---|---|
| **Webhook trigger de ingesta** | n8n recibe un fichero (desde Drive, email, Slack) y llama a `POST /ingest` |
| **Query desde Slack/email** | Workflow n8n que acepta preguntas y devuelve respuestas RAG |
| **Ingesta automática desde Gmail** | Extiende el workflow "Email a Notion" para ingestar adjuntos |
| **Notificación de ingesta** | n8n notifica en Slack/Notion cuando se ingesta un nuevo documento |
| **Reporte semanal** | Workflow cron que genera un resumen de queries del audit_log |

### 4.2 MCP Server

Exponer Korio como servidor MCP para que herramientas AI (Claude, n8n) puedan usar el knowledge base directamente.

```
Tools a exponer:
  - search_knowledge_base(query, user_id, tenant_id)
  - ingest_document(file_url, tenant_id, space_id)
  - list_spaces(user_id)
  - get_audit_summary(tenant_id, days)
```

Implementación: FastAPI MCP endpoint o servidor MCP independiente (TypeScript/Python).

### 4.3 Interfaz web básica

Chat UI mínima para demo y uso interno.

```
Features mínimas:
  - Input de pregunta + selector de tenant/user
  - Respuesta con citas de fuente (filename + chunk)
  - Historial de queries de la sesión
  - Upload de documento para ingestar

Stack: HTML + CSS + JavaScript vanilla (sin frameworks)
       o Next.js si se quiere más funcionalidad
```

---

## Fase 5 — Agentes y HITL

Añadir inteligencia sobre el RAG básico.

### 5.1 HITL (Human-in-the-Loop) básico

Cuando el sistema detecta baja confianza o conflicto entre fuentes:

```
Flujo HITL:
  query → RAG → similarity < threshold → marcar como "pending review"
       → notificar por email/Slack al admin del tenant
       → admin revisa y responde
       → respuesta se guarda para futuras queries similares
```

Implementación:
- Campo `review_status` en `audit_log`
- Endpoint `POST /review` para que el admin confirme/corrija
- Workflow n8n para notificaciones

### 5.2 Detección de conflictos

Cuando dos documentos dan respuestas contradictorias:

```python
# Pseudocódigo
if has_conflicting_sources(chunks):
    flag_for_review(query, conflicting_doc_ids)
    return answer_with_conflict_warning()
```

### 5.3 Agente de ingesta

Agente que monitorea fuentes y decide si hay documentos nuevos para ingestar:

```
Fuentes monitoreadas:
  - Google Drive (cambios en carpetas)
  - Gmail (adjuntos de remitentes conocidos)
  - Slack (mensajes con ficheros en canales)
  - Notion (páginas actualizadas)
```

---

## Fase 6 — Escala y GPU

Para reducir latencias y soportar más usuarios concurrentes.

| Mejora | Impacto | Coste |
|---|---|---|
| GPU en Hetzner (GEX44) | Embed ~0.1s, LLM ~1s | ~€65/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |
| Reranking (cross-encoder) | +20-30% calidad RAG | CPU overhead |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

---

## Fase 7 — Producto SaaS

Convertir el prototipo TFM en un producto real.

| Feature | Descripción |
|---|---|
| Auth real | Supabase Auth (email/password, Google OAuth) |
| Billing | Stripe por tenant/mes |
| Admin dashboard | Gestión de tenants, usuarios, spaces, documentos |
| Conectores nativos | Google Drive, Slack, Notion, Gmail (sin n8n) |
| API keys por tenant | Para integrar Korio desde otras apps |
| Límites de plan | Chunks máximos, queries/mes, usuarios |

---

## Decisiones de arquitectura pendientes

| Decisión | Opciones | Estado |
|---|---|---|
| LLM primario post-TFM | Mistral API vs OpenAI vs Ollama GPU | Abierto |
| Interfaz web | HTML vanilla vs Next.js vs Streamlit | Abierto |
| MCP Server idioma | Python (FastAPI) vs TypeScript | Abierto |
| Graph store | FalkorDB (en docker-compose) vs Neo4j | Abierto |
| Reranking | cross-encoder vs sin reranking | Abierto |

---

*Actualizado: junio 2026*
