# Korio — Roadmap

> Estado actual: **Phases 5 + 6 + 7.1 completadas · korio.es + grafo en producción** · Demo TFM: 2 julio 2026

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

### Phase 6 · Cron de escalada HITL ✅

| Feature | Estado |
|---|---|
| Migración 008: `reminders_sent`, `last_reminder_at`, `timeout_at` | ✅ |
| Enum resolution amplía con `timeout_kept_both` | ✅ |
| `src/escalation.py` con cadencia 3/7/14 + timeout 21 (parametrizable) | ✅ |
| `POST /escalate-reviews` con auth `X-Korio-Admin-Key` | ✅ |
| Workflow n8n Schedule Trigger diario 09:00 Madrid | ✅ |
| Email template adaptativo: initial / reminder / timeout | ✅ |
| Probado E2E con 5 reviews: cadencia 4/8/15/22 días | ✅ |

### Phase 7.1 · Grafo de conocimiento ✅ CERRADA

| Feature | Estado |
|---|---|
| FalkorDB (Redis + Cypher) en docker-compose | ✅ |
| Driver Python `falkordb>=1.0.10` | ✅ |
| `src/graph_client.py` con schema multi-tenant | ✅ |
| `src/entity_extractor.py` con Mistral structured JSON | ✅ |
| Integración opt-in en `ingest.py` (Step 6) | ✅ |
| `scripts/graph_backfill.py` — pobló 233 claims en 107s | ✅ |
| Search híbrido vector + grafo en `search.py` | ✅ |
| Endpoints `/graph/contradictions`, `/graph/entity`, `/graph/subgraph` | ✅ |
| UI `/ui/graph.html` con vis-network + panel contradicciones | ✅ |
| Query rephrase ("jornada mínima") resuelta por el grafo | ✅ |
| **3 puntos de acceso al grafo desde la app (banner / modal / sidebar)** | ✅ |
| **Sync en vivo del grafo desde conflict_detector + /review + escalation** | ✅ |
| **Polish visual: disputed rojo, superseded blanco outlined, CONTRADICTS rojo width 4** | ✅ |
| **Fix LIMIT que truncaba CONTRADICTS en /graph/subgraph** | ✅ |

---

## Pendiente antes del 2 julio 2026

| Tarea | Prioridad | Notas |
|---|---|---|
| QA end-to-end: 10+ queries en ambos tenants | 🔲 | Manual o test automatizado |
| Benchmark formal de latencias (p50, p95) | 🔲 | `scripts/benchmark.py` listo |
| Presentation deck (10–15 slides) | 🔲 | Para defensa del TFM |
| Vídeo demo: gobernanza + cron + grafo | 🔲 | Mostrar todo el ciclo HITL + grafo en acción |

---

## Fase 7.2 — n8n workflows de ingesta automática (próxima sesión)

| Workflow | Descripción |
|---|---|
| Gmail → Korio | Vigila carpeta de Gmail, extrae adjuntos PDF/DOCX → `POST /upload` |
| Google Drive monitor | Cambios en carpeta → `POST /upload` |
| Slack `/korio` | Comando → `POST /search` → respuesta en thread |
| Reporte semanal | Cron resumen del `audit_log` |

---

## Fase 8 — Mitigaciones a limitaciones detectadas

| Mejora | Impacto |
|---|---|
| Reranking cross-encoder | +20-30% calidad RAG en queries rephrasadas |
| Query expansion con LLM antes del embed | Más cobertura |
| Bajar threshold default 0.4 → 0.35 | Mejora recall |
| Validación semántica en aristas CONTRADICTS | Reduce falsos positivos del backfill |

---

## Fase 9 — Producto SaaS

| Feature | Descripción |
|---|---|
| Matriz de autoridad configurable en onboarding | UI para `authority_weight` por space y source_type |
| Panel admin de conflictos en `/ui/admin/conflicts` | Alternativa visual al email |
| Auth real | Supabase Auth (email/password, Google OAuth) |
| Billing | Stripe por tenant/mes |
| Conectores nativos | Drive, Slack, Notion, Gmail sin n8n |
| API keys por tenant | Para integrar Korio desde otras apps |
| Límites de plan | Chunks máximos, queries/mes, usuarios |
| **MCP Server** | Exponer Korio a Claude Desktop, n8n, ChatGPT |

---

## Fase 10 — Escala y GPU

| Mejora | Impacto | Coste |
|---|---|---|
| GPU en Hetzner (GEX44) | Embed ~0.1s, LLM ~1s | ~€65/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

---

*Actualizado: 9 junio 2026 (noche · sesión 2) — Phases 5 + 6 + 7.1 completadas, grafo en producción*
