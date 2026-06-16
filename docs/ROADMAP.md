# Korio — Roadmap

> Estado actual: **v0.3.7 · Phases 1–7.3 + las 6 reglas del Entregable 3 cumplidas · 🏁 Implementación cerrada** · Demo TFM: 2 julio 2026 · Defensa: 9 julio 2026

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
| VPS Hetzner (**CPX32** AMD, Frankfurt) · €17.53/mes max | ✅ |
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

### Implementación técnica ✅ CERRADA (sesión 14, v0.3.7)
| Tarea | Estado |
|---|---|
| QA end-to-end: 10+ queries en ambos tenants | ✅ sesión 10 (10/10) |
| Benchmark formal p50/p95 | ✅ sesión 10 (p50=1983ms, p95=3053ms) |
| 31/31 tests verdes | ✅ sesión 14 |
| Snapshot de seguridad para demo | ✅ sesión 14 (`pre_demo_v036`) |

### Contenido para defensa
| Tarea | Prioridad | Estimación | Herramienta |
|---|---|---|---|
| Vídeo demo del ciclo completo | 🔴 Alta | 3-4h | Claude Code (sesión 15) |
| Presentation deck (10-15 slides) | 🔴 Alta | 6-8h | Claude Code (sesión 16) |
| Memoria TFM (negocio + técnico + research) | 🔴 Alta | 20-30h | Claude Projects |

### Mejoras de sesión 4 (10 jun 2026 tarde) ✅ CERRADAS
| Tarea | Estado | Notas |
|---|---|---|
| **Memoria de chat con query reformulation** | ✅ | `state.conversation` en frontend, `llm_client.reformulate_query()` antes del embed. Reset al cambiar tenant/usuario. Trazabilidad en `original_query`/`embedded_query`/`query_reformulated`. |
| **Doc de diseño `CHAT-PIPELINE-GUARDRAILS.md`** | ✅ | Capítulo memoria TFM: n8n + Lakera/Rebuff/Presidio + rate limit + compliance por tenant. |
| **Fix CONTRADICTS falsos positivos** | ✅ | Cypher exige `subject` igual o substring containment + diff `value` para crear arista. Aplicado en `graph_client` (live) y `graph_backfill.py` (batch). Limpiar aristas falsas existentes con `MATCH ()-[r:CONTRADICTS]->() DELETE r` + relink. |
| **Sync local docs** | ✅ | CLAUDE.md, ROADMAP.md, ARCHITECTURE.md, DEPLOYMENT.md, README.md actualizados. |

### Phase 7.3 — MCP Server (sesión 5, 11 jun 2026) ✅ CERRADA

| Feature | Estado |
|---|---|
| Migración 010 `mcp_api_keys` (SHA-256, FK users+tenants, soft revoke) | ✅ |
| `api/mcp_server.py` FastMCP con 3 tools | ✅ |
| `MCPAuthASGI` puro (NO BaseHTTPMiddleware, compat con SSE) | ✅ |
| `TransportSecuritySettings` con `allowed_hosts=[korio.es,...]` | ✅ |
| `scripts/mcp_create_key.py` CLI create/list/revoke | ✅ |
| `docs/MCP-SERVER.md` (capítulo memoria TFM) | ✅ |
| Despliegue con `--workers 1` (sessions SSE in-memory por proceso) | ✅ |
| Conectado Claude Desktop vía `mcp-remote` por npx (Node 20+) | ✅ |
| Caso TFM "35 horas semanales" verificado vía MCP | ✅ |

### Fixes encadenados del RAG híbrido (sesión 5) ✅ CERRADOS
| Fix | Estado | Notas |
|---|---|---|
| **Grafo dentro del CONTEXTO del prompt** | ✅ | El bloque `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]` se inyectaba FUERA y Mistral lo descartaba. `build_rag_prompt(graph_context=...)` lo mete DENTRO; system_prompt actualizado para reconocer ambas fuentes. |
| **Rerank de claims por relevancia** | ✅ | `find_claims_by_predicate` LIMIT 20 → 50 + rerank en Python (`3·predicate + 2·value + 1·subject` por keyword). Evita que keywords genéricas saturen el top-8. |
| **Citación de fuentes en MCP** | ✅ | Docstring + `instructions` del FastMCP obligan al cliente a citar `filename` y avisar de `is_disputed`. |
| **list_spaces -32602** | ✅ | Param `include_inactive` dummy para que FastMCP serialice el schema. |

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
| **MCP Server OAuth + rate limit + audit** | Sustituir API keys (Phase 7.3) por OAuth 2.1 + token bucket por key + `mcp_audit_log` con PII-redaction |
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

### Sesiones 6-9 (11 jun · v0.3.0) ✅ CERRADAS — Cumplimiento E3/E4 completo
| Sesión | Cierre principal | Tests |
|---|---|---|
| Sesión 6 | Transaccionalidad ACID — RPC `ingest_document_atomic` (migr. 011). Bus de eventos `pipeline_events` con `operation_id` UUID y webhook a n8n. **Cierra feedback profesor E4** | 3/3 atomicidad |
| Sesión 7 | Workflow n8n `Korio · Pipeline event bus` + fachada agéntica `src/agents/{base,ingestor,detector,arbitrator,supervisor,curator,pipeline}.py` con docstring PEAS de los 5 roles del E3 | 2/2 agentic |
| Sesión 8 | Migr. 012: RPC `detect_silent_conflicts_among_chunks`. search.py Step 2.5 con aviso al usuario y emisión de `CONFLICT_DETECTED triggered_by=query_time`. **Cierra Caso extremo del E4** | 1/1 query-time |
| Sesión 9 | Migr. 013: estado `inconclusive` + tabla `policies`. `_apply_timeout` → `inconclusive` (Regla 5). `find_applicable_policy()` antes de `_decide_resolution` (Regla 4). Persistencia de policy desde `/review`. | 2/2 inconclusive+policies |

**Las 6 reglas del Entregable 3 están materializadas en producción** (tabla detallada en `docs/AGENTIC-INGESTION.md` §"Cumplimiento de las 6 Reglas del E3").

---

*Actualizado: 16 junio 2026 (sesión 14, v0.3.7) — 🏁 Implementación cerrada. 31/31 tests, 20 migraciones, 8 workflows n8n, 18 docs producción, snapshot demo guardado. Próximo: vídeo (sesión 15), slides (sesión 16), memoria TFM (Claude Projects).*
