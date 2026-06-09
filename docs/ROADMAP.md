# Korio — Roadmap

> Estado actual: **Phase 5 completada · korio.es en producción** · Demo TFM: 2 julio 2026

---

## Estado actual (Phases 1–5 completadas)

### Phase 1–2 · Núcleo RAG y multi-tenancy ✅

| Feature | Estado |
|---|---|
| Pipeline ingesta (MarkItDown → Presidio → Chunking → pgvector) | ✅ |
| Pipeline RAG (Query → Embed → RLS → pgvector → Mistral) | ✅ |
| FastAPI server (`/search`, `/ingest`, `/health`) | ✅ |
| Multi-tenancy real (RLS Supabase + early binding en aplicación) | ✅ |
| 2 tenants con datos sintéticos (Delos + García) | ✅ |
| Test suite 20/20 | ✅ |
| PII detection con Presidio + spaCy español | ✅ |
| Mistral API + Ollama fallback | ✅ |

### Phase 3 · Documentación técnica ✅

| Feature | Estado |
|---|---|
| `docs/ARCHITECTURE.md` | ✅ |
| `docs/DEPLOYMENT.md` | ✅ |
| `docs/ROADMAP.md` (este fichero) | ✅ |
| README con quickstart + métricas reales | ✅ |

### Phase 4 · Interfaz web ✅

| Feature | Estado |
|---|---|
| Chat UI web (`ui/`) — HTML/CSS/JS vanilla | ✅ |
| `POST /upload` — ingesta de ficheros desde el navegador | ✅ |
| Logo Korio integrado | ✅ |
| `scripts/benchmark.py` — medición de latencias | ✅ |
| API_BASE dinámico (localhost vs same-origin producción) | ✅ |

### Phase 5 · Producción + Gobernanza activa + HITL email ✅

#### Infraestructura
| Feature | Estado |
|---|---|
| VPS Hetzner (CX32, Frankfurt) | ✅ |
| nginx + Let's Encrypt SSL (renovación automática) | ✅ |
| FastAPI como systemd service (`korio-api`) | ✅ |
| n8n en Docker (`korio-n8n`) | ✅ |
| Dominio `korio.es` apuntando al VPS | ✅ |
| `n8n.korio.es` con editor accesible | ✅ |

#### Gobernanza activa (core value proposition)
| Feature | Estado |
|---|---|
| `conflict_reviews` table + `find_conflicting_chunks` RPC | ✅ |
| Detección de conflictos por similitud coseno (umbral 0.78) | ✅ |
| Auto-resolución por fecha (>30 días) | ✅ |
| Auto-resolución por autoridad (delta ≥3) | ✅ |
| Chunks en estado `active` / `superseded` / `disputed` | ✅ |
| Search incluye chunks `disputed` con flag de aviso | ✅ |
| LLM prompt inyecta instrucción especial en caso de disputa | ✅ |
| UI muestra banner ⚠️ + badge "EN DISPUTA" en source chips | ✅ |

#### HITL via email
| Feature | Estado |
|---|---|
| Tabla `conflict_reviews` con `review_token` firmado | ✅ |
| Endpoint `GET /review/{id}?action=&token=` | ✅ |
| Workflow n8n: Webhook → Code → Send Email (SMTP Gmail) | ✅ |
| Email HTML bulletproof (Gmail + Outlook + Airmail) | ✅ |
| Cuerpo del email incluye **textos reales de los 2 chunks en conflicto** | ✅ |
| 3 botones de acción: approved_new / approved_existing / kept_both | ✅ |
| Página HTML de confirmación tras clic | ✅ |
| `tenants.admin_email` (configurable por tenant) | ✅ |

#### Landing teaser
| Feature | Estado |
|---|---|
| `landing/` con HTML estático en `/` | ✅ |
| OG image 1200×630 generada (SVG + PNG) | ✅ |
| Form de waitlist con `POST /waitlist` | ✅ |
| Tabla `waitlist` en Supabase | ✅ |
| Script `deploy/refresh-landing.sh` para edits en producción | ✅ |

---

## Pendiente antes del 2 julio 2026

| Tarea | Prioridad | Notas |
|---|---|---|
| QA end-to-end: 10+ queries en ambos tenants | 🔲 | Manual o test automatizado |
| Benchmark formal de latencias (p50, p95) | 🔲 | `scripts/benchmark.py` listo |
| Presentation deck (10–15 slides) | 🔲 | Para defensa del TFM |
| Vídeo demo de gobernanza activa | 🔲 | Mostrar email HITL en acción |

---

## Fase 6 — Cron de escalada + UX admin

Pendientes del diseño de gobernanza activa que aún no están en código.

### 6.1 Cron de escalada para conflictos sin resolver

Diseño Notion: *"Los conflictos sin resolver reciben recordatorios periódicos por cron (cada 3 días, cada semana). Si transcurre el tiempo máximo, ambos chunks permanecen activos con estado `en_disputa`."*

Implementación:
- Workflow n8n con Schedule Trigger (cron diario)
- Lee `conflict_reviews WHERE resolution='pending' AND created_at < now() - interval`
- Reenvía emails con prefijo "Recordatorio" + contador de días
- Si supera el máximo configurado (ej. 14 días) → marca como `kept_both` automáticamente

### 6.2 Matriz de autoridad configurable en onboarding

Actualmente `authority_weight` está fijo en 5 por defecto. Falta UI para:
- Configurar `authority_weight` por space (RRHH=7, Dirección=9, etc.)
- Configurar `authority_weight` por `source_type` (manual=8, slack=3, etc.)
- Wizard de onboarding cuando se crea un tenant

### 6.3 Panel admin de revisión de conflictos

Alternativa visual al email HITL:
- Vista en `/ui/admin/conflicts` con todos los `pending`
- Filtros por space, fecha, similitud
- Botones de resolución 1-clic (mismo backend que el email)
- Estadísticas: % auto-resueltos vs % HITL, tiempo medio de respuesta

---

## Fase 7 — Integración nativa + MCP

### 7.1 n8n workflows adicionales

Ya tenemos el workflow HITL. Pendientes:

| Workflow | Descripción |
|---|---|
| Webhook ingesta automática | Drive/Slack/email → `POST /upload` |
| Query desde Slack | `/korio ¿pregunta?` → `POST /search` → respuesta en thread |
| Ingesta automática desde Gmail | Extender "Email a Notion" para ingestar adjuntos |
| Reporte semanal | Cron que genera resumen del `audit_log` |

### 7.2 MCP Server

Exponer Korio como servidor MCP para que herramientas AI (Claude Desktop, n8n, ChatGPT) puedan usarlo directamente.

```
Tools a exponer:
  - search_knowledge_base(query, user_id, tenant_id)
  - ingest_document(file_url, tenant_id, space_id)
  - list_spaces(user_id)
  - get_audit_summary(tenant_id, days)
  - list_pending_conflicts(tenant_id)
```

Implementación: FastAPI MCP endpoint o servidor MCP independiente.

---

## Fase 8 — Escala y GPU

| Mejora | Impacto | Coste |
|---|---|---|
| GPU en Hetzner (GEX44) | Embed ~0.1s, LLM ~1s | ~€65/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Reranking (cross-encoder) | +20-30% calidad RAG | CPU overhead |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

---

## Fase 9 — Producto SaaS

Convertir el prototipo TFM en un producto real.

| Feature | Descripción |
|---|---|
| Auth real | Supabase Auth (email/password, Google OAuth) |
| Billing | Stripe por tenant/mes |
| Admin dashboard | Gestión de tenants, usuarios, spaces, documentos |
| Conectores nativos | Google Drive, Slack, Notion, Gmail (sin n8n) |
| API keys por tenant | Para integrar Korio desde otras apps |
| Límites de plan | Chunks máximos, queries/mes, usuarios |
| FalkorDB (grafo) | Representación de conflictos como aristas activas |

---

## Decisiones de arquitectura pendientes

| Decisión | Opciones | Estado |
|---|---|---|
| LLM primario post-TFM | Mistral API vs OpenAI vs Ollama GPU | Abierto |
| MCP Server lenguaje | Python (FastAPI) vs TypeScript | Abierto |
| Graph store | FalkorDB (en docker-compose) vs Neo4j | Abierto |
| Reranking | cross-encoder vs sin reranking | Abierto |

---

*Actualizado: 9 junio 2026 — Phase 5 completada, korio.es en producción*
