# Korio — Roadmap

> Estado actual: **Phases 1–7.2 completadas · ingesta automática multi-canal + grafo en producción** · Demo TFM: 2 julio 2026 · Defensa: 9 julio 2026

---

## Estado actual (Phases 1–7.2 completadas)

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

### Phase 7.2 · Ingesta automática multi-canal ✅ CERRADA (10 jun · sesión 3 tarde)

#### Backend
| Feature | Estado |
|---|---|
| Migración 009: `documents.source_metadata` (JSONB) + índice parcial por `via` | ✅ |
| `ingest_document()` acepta `source_metadata: Optional[dict]` | ✅ |
| `/upload` acepta Form fields `source_type` y `source_metadata` (JSON string) | ✅ |
| `DELETE /document/{id}` (admin) — borra Postgres en cascada + FalkorDB | ✅ |
| `APIKeyHeader` + dependency `require_admin()` — botón Authorize en Swagger | ✅ |
| Fix crítico: Basic Auth en webhook HITL (`HITL_WEBHOOK_USER`/`PASS`) | ✅ |

#### Workflows n8n.korio.es
| Feature | Estado |
|---|---|
| **Gmail → /upload (Delos RRHH)** — label `korio/ingesta` cada 5 min | ✅ |
| **Drive → /upload (Delos RRHH)** — carpeta `Clínica Delos / input` cada 5 min | ✅ |
| **Slack /korio → /search (Delos admin)** — slash command → reply en thread | ✅ |

#### UI polish
| Feature | Estado |
|---|---|
| Filenames de fuentes sin truncar (`flex: 1 + min-width: 0`) | ✅ |
| Eliminado marcador `[grafo]` confuso del prompt + JS | ✅ |

#### Documentación
| Feature | Estado |
|---|---|
| `docs/MULTI-TENANT-INGESTION.md` — diseño Phase 8 SaaS multi-tenant configurable | ✅ |
| Memoria local Claude Code: `feedback_n8n_instance.md`, `project_hitl_webhook_auth.md` | ✅ |

---

## Pendiente antes del 2 julio 2026 (demo) y 9 julio 2026 (defensa)

### Críticos para la defensa
| Tarea | Prioridad | Estimación | Notas |
|---|---|---|---|
| QA end-to-end: 10+ queries en ambos tenants | 🔴 Alta | 2-3h | Manual con script |
| Benchmark formal p50/p95 | 🔴 Alta | 1h | `scripts/benchmark.py` listo |
| Vídeo demo del ciclo completo | 🔴 Alta | 3-4h | Gmail → ingesta → consulta → grafo |
| Presentation deck (10-15 slides) | 🔴 Alta | 6-8h | Para defensa |
| Memoria TFM (escritura) | 🔴 Alta | 20-30h | Incluye capítulos Phase 8 y guardrails |

### Mejoras en curso (sesión 4)
| Tarea | Estado | Notas |
|---|---|---|
| **Memoria de chat con query reformulation** | 🟡 En curso | UI guarda history, LLM reformula query autónoma antes del embed |
| **Doc de diseño `CHAT-PIPELINE-GUARDRAILS.md`** | 🟡 En curso | Capítulo memoria TFM: n8n + ingress/egress guardrails post-defensa |
| **Fix CONTRADICTS falsos positivos** | 🟡 En curso | Validación LLM par claim_a/claim_b antes de crear arista |

### Opcional para defensa
| Tarea | Prioridad | Notas |
|---|---|---|
| Phase 7.3 — MCP Server | 🟢 Baja | Bonus si queda tiempo después del contenido TFM |

---

## Fase 8 — Mitigaciones a limitaciones detectadas (post-defensa)

| Mejora | Impacto | Esfuerzo |
|---|---|---|
| **Ingesta multi-tenant configurable** (OAuth + vault tokens + onboarding) | Producto SaaS real | ~6 semanas + verificación Google CASA en paralelo. Diseñado en `docs/MULTI-TENANT-INGESTION.md`. |
| **Chat pipeline con guardrails** (n8n + Lakera/Rebuff) | Seguridad para producción | ~2 semanas. Diseñado en `docs/CHAT-PIPELINE-GUARDRAILS.md`. |
| Validación semántica en aristas CONTRADICTS | Reduce falsos positivos del backfill (parcheado pre-demo si hay tiempo) | 2-3h |
| Reranking cross-encoder | +20-30% calidad RAG en queries rephrasadas | 6-8h |
| Query expansion con LLM antes del embed | Más cobertura | 4-6h. Solapado con memoria de chat (query reformulation). |
| Fix Presidio anonymize parcial | Anonimización completa de PII | 3-5h. Bajo impacto en demo. |
| Bajar threshold default 0.4 → 0.35 | Mejora recall | 30 min + verificación |

---

## Fase 9 — Producto SaaS

| Feature | Descripción |
|---|---|
| Matriz de autoridad configurable en onboarding | UI para `authority_weight` por space y source_type |
| Panel admin de conflictos en `/ui/admin/conflicts` | Alternativa visual al email |
| Auth real | Supabase Auth (email/password, Google OAuth) |
| Billing | Stripe por tenant/mes |
| Conectores nativos configurables | Drive, Slack, Notion, Gmail con OAuth multi-tenant (ver Phase 8) |
| API keys por tenant | Para integrar Korio desde otras apps |
| Límites de plan | Chunks máximos, queries/mes, usuarios |
| **MCP Server** | Exponer Korio a Claude Desktop, n8n, ChatGPT (Phase 7.3) |
| Persistencia de chat por usuario | Conversaciones multi-sesión cross-device |
| Reflejo de chat Slack ↔ chat web | Identidad compartida, conversaciones cross-canal |

---

## Fase 10 — Escala y GPU

| Mejora | Impacto | Coste |
|---|---|---|
| GPU en Hetzner (GEX44) | Embed ~0.1s, LLM ~1s | ~€65/mes |
| Caché de embeddings (Redis) | Queries repetidas ~0s | ~€5/mes |
| Postgres dedicado vs Supabase | Más control, menor coste a escala | Variable |

**Objetivo latencia p50 con GPU:** <1s end-to-end.

---

*Actualizado: 10 junio 2026 (tarde · sesión 3) — Phases 1–7.2 completadas, ingesta multi-canal en producción, sesión 4 en curso (memoria de chat + guardrails design + fix CONTRADICTS)*
