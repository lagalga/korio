# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Arrancamos sesión nueva de **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Trabajamos siempre en el worktree:

```
/Users/berto/Claude Code/korio/.claude/worktrees/dreamy-bose-cd8a36
```

Configurado para que `git push` (sin args) publique directamente en `main`.

## Lo primero que quiero que hagas (smoke check de 30s)

Antes de discutir qué atacamos hoy, verifica que producción sigue viva:

```bash
ssh korio-vps "systemctl is-active korio-api && docker ps --format '{{.Names}}' | grep -E 'ollama|n8n|falkordb' && curl -s https://korio.es/health"
```

Si todo OK, dímelo en una línea. Si algo está raro, antes de tocar nada cuéntame qué ves.

## Pasos manuales pendientes

**Pendiente operativo de sesión 11 — configurar Slack Event Subscriptions** (paso UI que requiere acceso a https://api.slack.com/apps):

1. Abrir la Slack app "Korio-Delos" (el bot que ya responde a `/korio`).
2. Menú lateral **OAuth & Permissions** → añadir Bot Token Scopes:
   - `files:read` (leer metadatos de archivos)
   - `reactions:write` (poner ✅ en mensajes)
   - `chat:write` (mensaje ephemeral)
3. Menú lateral **Event Subscriptions**:
   - Activar el toggle "Enable Events".
   - **Request URL**: `https://n8n.korio.es/webhook/korio-slack-events`
   - **Subscribe to bot events** → añadir `file_shared`.
4. **Install App** o **Reinstall to Workspace** para aplicar los nuevos scopes.
5. Invitar al bot al canal donde se subirán archivos: `/invite @Korio-Delos`.

Worktrees obsoletos pendientes de limpieza manual:
```bash
cd "/Users/berto/Claude Code/korio"
git worktree remove .claude/worktrees/great-elbakyan-832d81
git worktree remove .claude/worktrees/nifty-booth-0c25a5
git worktree remove --force .claude/worktrees/silly-hofstadter-5e49c0
```

## Estado al cierre de sesión 13a · 14 jun 2026 · v0.3.4 · hardening seguridad

✅ **Sesión 13a (14 jun · noche) — Auditoría completa + hardening pre-demo**:
- Tres pasadas con agentes Explore (seguridad / diseño / bugs) sobre v0.3.3. 21 hallazgos catalogados (4 CRIT, 3 HIGH, 8 MED, 6 LOW).
- **7 fixes cerrados** (issues nuevos bloqueantes para demo pública):
  - **N1 CORS** whitelist `korio.es` (+ `localhost` opcional con `KORIO_ENV=dev`)
  - **N2** `hmac.compare_digest` sobre `KORIO_ADMIN_API_KEY`
  - **N3** tenant check en `DELETE /document/{id}` con `KORIO_ADMIN_TENANT_ID`
  - **N4** RLS sobre `mcp_api_keys` (migración `015_mcp_api_keys_rls.sql`)
  - **N5** assert dim 768 al arranque del embedder
  - **N6** cleanup blindado tempfile en `/upload`
  - **C2** Cypher parametrizado en `tests/test_graph_semantic_rerank.py`
- **14 issues diferidos** con destino justificado (Phase 8/9 o ya planeados): `docs/AUDIT-2026-06-14.md`.
- **5 commits atómicos a `main`** push verificado.
- **Pendiente operativo manual** (antes de redeploy en VPS):
  1. Aplicar migración `015_mcp_api_keys_rls.sql` en Supabase prod (CLI o SQL editor).
  2. Setear en `/root/korio/.env`: `KORIO_ENV=prod`, `KORIO_ADMIN_TENANT_ID=<uuid del admin>`, opcional `KORIO_EXTRA_CORS_ORIGINS=`.
  3. `git pull` en VPS + `systemctl restart korio-api`.
  4. QA: `curl -i -H "Origin: https://evil.test" https://korio.es/health` → sin `Access-Control-Allow-Origin: *`.

---

## Estado al cierre de sesión 12 · 12 jun 2026 · v0.3.3 · programación cerrada

✅ **Todo el sistema está en producción y verificado**:

- `https://korio.es` — landing teaser
- `https://korio.es/ui` — chat RAG multi-tenant con gobernanza activa, banner ⚠️, fuentes con %relevancia
- `https://korio.es/ui/graph.html` — grafo de conocimiento vivo con panel de contradicciones, hover/click resalta arista CONTRADICTS
- `https://korio.es/docs` — Swagger con botón Authorize
- `https://korio.es/mcp/sse` — servidor MCP HTTP+SSE (Phase 7.3): 3 tools. Conectado a Claude Desktop.
- `https://n8n.korio.es` — **8 workflows activos**:
  - HITL email (gobernanza) — webhook con Basic Auth
  - Cron escalada diaria 09:00 Madrid
  - Pipeline event bus (observabilidad agéntica)
  - Gmail → /upload (Delos RRHH)
  - Drive → /upload (Delos RRHH)
  - Slack `/korio` → /search (Delos admin)
  - Slack file_shared → /upload (sesión 11)
  - **Gestión de errores n8n** (`KeUTpIk0ycbW1f3g`) — Error Trigger → Supabase `n8n_errors` + Slack DM

✅ **Sesión 12 (12 jun · noche) — Visualización grafo + captura de errores**:
- **Grafo UI**: banner disputed calibrado (threshold 0.6), aristas CONTRADICTS siempre visibles (priority node rescue), hover/click en sidebar resalta la arista correspondiente, fix definitivo del scale "enganchado" con `DataSet.clear()+add()`.
- **`supabase/migrations/014_n8n_errors.sql`** — tabla `n8n_errors` aplicada en producción.
- **Workflow captura de errores** verificado E2E: 2 filas en Supabase, error real de Slack `/korio` capturado (`channel_not_found`).
- **`errorWorkflow: "KeUTpIk0ycbW1f3g"`** configurado en los 7 workflows de producción.
- **Mejoras Phase 9 (anotadas para la semana que viene, no urgentes)**:
  - Throttling anti-spam: 1 DM por ≥10 errores del mismo workflow
  - Panel `/admin/errors` en la UI de Korio
  - Botón "reviewed" en el propio Slack message (interactivity webhook)

✅ **Métricas finales** (sesión 10):
- Benchmark: global p50=1983ms, p95=3053ms. 50/50 sin errores.
- Tests: 28/28 verdes.
- Datos en producción: 10+ docs, 29+ chunks, 158 entidades, 455 claims con embedding, 2 contradicciones válidas.

---

## Estado al cierre de sesión 11 · 12 jun 2026 · v0.3.2

✅ **Sesión 11 (12 jun · tarde) — Rerank semántico del grafo + cierre programación**:
- RAG híbrido con Reciprocal Rank Fusion (k=60): léxico + semántico (cosine sobre embeddings de claims).
- 455 claims embedidos en 23s. Verificado: query muy rephrasada *"¿cuánto se trabaja a la semana como mínimo?"* → "35 horas/semana" en 1384ms.
- Specs VPS corregidas: Hetzner CPX32 AMD EPYC-Genoa, €17.53/mes max, 160 GB SSD.
- Workflow Slack file_shared → /upload verificado con PDF real.

---

## Fuentes de verdad

1. **`CLAUDE.md`** del repo — memoria técnica completa, stack, URLs, comandos VPS
2. **`docs/ROADMAP.md`** — phases pasadas y siguientes con checklist
3. **Notion · Estado técnico (síntesis TFM)** — https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a
4. **Notion · Roadmap & Tareas** — https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533
5. **Notion · Historial de Desarrollo** — https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1

## Reglas críticas que NUNCA debes saltar

- **Embeddings `nomic-embed-text`, 768 dims FIJOS**. Cambiar el modelo requiere re-ingestar TODA la BD.
- **RLS en dos capas siempre**: aplicación (`db.py` early binding) + PostgreSQL (Supabase policies).
- **Comentarios y commits en español**, código (variables, funciones, clases) en inglés.
- **n8n: la instancia de Korio es `n8n.korio.es`, NO `n8n.lagalga.es`**. El `n8n-mcp` de Claude Code apunta a lagalga; usar `N8N_KORIO_API_KEY` del `.env` del VPS con curl contra la API REST de korio.
- **Webhook HITL con Basic Auth**: `HITL_WEBHOOK_USER=B3rt0` + `HITL_WEBHOOK_PASS=13-K0rio-14!`.

## Acceso al VPS y servicios

```bash
ssh korio-vps                                    # alias → 167.233.72.42
systemctl status korio-api                        # FastAPI service
journalctl -u korio-api -f                        # logs tiempo real
curl https://korio.es/health                      # health check
```

## Próxima sesión — **sesión 13 · Vídeo demo + Slide deck + Memoria TFM**

Faltan **~20 días para demo (2 jul)** y **~27 días para defensa (9 jul)**. Programación cerrada en sesión 11 (v0.3.2). La sesión 13 arranca el contenido de defensa.

**Agenda (en este orden)**

### 1. Vídeo demo (3-4h)

Guión del ciclo completo en ~3-4 minutos:
1. Gmail llega con adjunto → label `korio/ingesta` → 30s después aparece en `/search`
2. Bus de eventos en n8n.korio.es: 3-4 ejecuciones visibles con emojis
3. Chat en `korio.es/ui`: query que activa el grafo (35h/semana), respuesta con fuente citada
4. Chunk disputed → badge ⚠️ en source chips
5. Detección query-time: aviso de la gobernanza
6. Claude Desktop con MCP: misma query, respuesta equivalente
7. `graph.html`: nodos, aristas CONTRADICTS rojas, hover/click en sidebar

### 2. Slide deck (6-8h)

10-15 slides para el tribunal:
- Problema + oportunidad de mercado
- Arquitectura del sistema (diagrama con las 7 phases)
- Demo en vivo (clips del vídeo)
- Las 6 reglas del E3 materializadas
- Métricas: p50=1983ms/p95=3053ms, datos en producción
- Phase 8: roadmap post-TFM
- Conclusiones

### 3. Memoria TFM (20-30h — trabajo de fondo)

Capítulos clave:
- **Capítulo 4**: Arquitectura RAG multi-tenant (pipeline ingesta, gobernanza ACID, RLS)
- **Capítulo 5**: Grafo de conocimiento (FalkorDB, CONTRADICTS semántico, hybrid RAG con RRF)
- **Capítulo 6**: Sistema agéntico (las 6 reglas del E3, pipeline ACID, bus de eventos)
- **Capítulo 7**: MCP Server (Phase 7.3) + Ingesta multi-canal (Phase 7.2)
- **Capítulo 8** (diseño futuro): `docs/MULTI-TENANT-INGESTION.md` + `docs/CHAT-PIPELINE-GUARDRAILS.md` + `docs/PHASE-10-MULTIMODAL-INGESTION.md`

## Pendiente antes de la defensa

| Tarea | Estimación | Estado |
|---|---|---|
| ~~QA E2E (10+ queries, ambos tenants, MCP, bus eventos)~~ | ~~2-3h~~ | ✅ Sesión 10 |
| ~~Benchmark formal `scripts/benchmark.py` (p50=1983ms/p95=3053ms)~~ | ~~1h~~ | ✅ Sesión 10 |
| ~~Validación semántica CONTRADICTS (2 aristas válidas)~~ | ~~2-3h~~ | ✅ Sesión 10 |
| ~~Rerank semántico del grafo con RRF~~ | ~~2-3h~~ | ✅ Sesión 11 |
| ~~Specs VPS corregidas (CPX32 AMD, €17.53/mes)~~ | ~~30min~~ | ✅ Sesión 11 |
| ~~Diseño Phase 10 ingesta multimodal~~ | ~~1-2h~~ | ✅ Sesión 11 |
| ~~Grafo UI: highlight aristas CONTRADICTS + fix scale~~ | ~~2-3h~~ | ✅ Sesión 12 |
| ~~Captura errores n8n (tabla Supabase + Slack DM)~~ | ~~1-2h~~ | ✅ Sesión 12 |
| **Vídeo demo** (3-4 min): ciclo completo con n8n event bus | 3-4h | 🔲 Sesión 13 |
| **Slide deck** (10-15 slides) + ensayo | 6-8h | 🔲 Sesión 13 |
| **Memoria TFM** (capítulos 4-7) | 20-30h | 🔲 Sesiones 13-16 |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque**.
- Si tocas algo en n8n, recuerda: **n8n.korio.es ≠ n8n.lagalga.es**.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:`.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** al cierre.
