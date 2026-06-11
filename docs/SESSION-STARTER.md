# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Arrancamos sesión nueva de **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Trabajamos siempre en el worktree:

```
/Users/berto/Claude Code/korio/.claude/worktrees/nifty-booth-0c25a5
```

Configurado para que `git push` (sin args) publique directamente en `main`.

## Lo primero que quiero que hagas (smoke check de 30s)

Antes de discutir qué atacamos hoy, verifica que producción sigue viva tras lo que cerramos ayer:

```bash
ssh korio-vps "systemctl is-active korio-api && docker ps --format '{{.Names}}' | grep -E 'ollama|n8n|falkordb' && curl -s https://korio.es/health"
```

Si todo OK, dímelo en una línea. Si algo está raro, antes de tocar nada cuéntame qué ves.

## Pasos manuales que pueden haber quedado pendientes de ayer

Sesión 5 (11 jun) quedó **todo desplegado y verificado** — no hay pendientes operativos. Si quieres ir sobre seguro antes de tocar contenido:

1. **Smoke check del MCP en Claude Desktop** con la query del hito:
   `usa korio para responder: ¿cuántas horas semanales mínimas exige la política de RRHH?`
   Debe responder *"35 horas semanales"* con fuentes citadas y el aviso ⚠️ de contradicciones pendientes en los PDFs antiguos.
2. **MCP key**: las keys viven en Supabase (`mcp_api_keys`). La de Claude Desktop laptop de berto está activa. Para crear una nueva:
   ```bash
   ssh korio-vps "cd /root/korio && .venv/bin/python scripts/mcp_create_key.py create --user-id <uuid> --tenant-id <uuid> --name '<alias>'"
   ```

## Estado actual (al cierre de la última sesión · 11 jun 2026 · sesión 5)

✅ **Phases 1–7.3 completadas + 4 fixes encadenados del RAG híbrido**. En producción:

- `https://korio.es` — landing teaser
- `https://korio.es/ui` — chat RAG multi-tenant con gobernanza activa, banner ⚠️ de contradicciones y 3 puntos de acceso al grafo
- `https://korio.es/ui/graph.html` — grafo de conocimiento vivo (FalkorDB) con vis-network, panel de contradicciones rojas en tiempo real
- `https://korio.es/docs` — Swagger (con botón Authorize para los endpoints admin)
- `https://korio.es/mcp/sse` — **servidor MCP HTTP+SSE (Phase 7.3)**: 3 tools (`search_knowledge_base`, `list_pending_conflicts`, `list_spaces`). Auth con header `X-Korio-MCP-Key`. Conectado a Claude Desktop vía `mcp-remote` por npx (Node 20+ requerido).
- `https://n8n.korio.es` — **5 workflows activos**:
  - HITL email (gobernanza) — webhook protegido con Basic Auth
  - Cron escalada diaria 09:00 Madrid
  - **Gmail → /upload** (Phase 7.2): vigila label `korio/ingesta` en `contacto@lagalga.es`, ingiere adjuntos PDF/DOCX
  - **Drive → /upload** (Phase 7.2): vigila carpeta `Clínica Delos / input` (`1rlBEmkqLHvidWEPv64LaMpzBh9bMDGF4`)
  - **Slack `/korio` → /search** (Phase 7.2): comando que consulta Korio y responde en thread con fuentes

✅ El RAG es **híbrido vector + grafo**: cuando la query está semánticamente rephrasada respecto al texto, el grafo recupera el dato por entidades/predicates. Caso TFM: *"¿Cuántas horas semanales mínimas exige la política?"* → *"más de 35 horas/semana"* en ~1s.

✅ Gobernanza activa **al nivel de chunk**: chunks `active` / `superseded` / `disputed`. Auto-resolución por fecha/autoridad. HITL email con 3 botones de acción. Cron de escalada (3/7/14/21 días). Sincronización con grafo en tiempo real.

✅ **Ingesta multi-canal** (Phase 7.2): cualquier doc que entra por Gmail, Drive o Slack lleva `source_metadata` JSONB con el contexto del canal (message_id, file_id, owner, etc.). Migración 009 + `/upload` y `ingest_document()` propagados. Documento de diseño Phase 8 (`docs/MULTI-TENANT-INGESTION.md`) con OAuth multi-tenant + vault de tokens + onboarding UX listo para defender en la memoria del TFM.

✅ **Endpoint admin** `DELETE /document/{id}` para "desingerir" (limpia Postgres + FalkorDB en cascada). Autenticación via `APIKeyHeader` X-Korio-Admin-Key — visible en Swagger con botón Authorize.

✅ **UI polish**: filenames de fuentes ya no se truncan; eliminado el marcador `[grafo]` confuso (los accesos al grafo siguen disponibles desde el banner ⚠️, sidebar y conflict report).

✅ **Memoria de chat multi-turn (sesión 4)**: el chat guarda los últimos 6 turnos en `state.conversation` del frontend y los envía a `/search`. Si llega `history`, `search.py` reformula la query como pregunta autónoma vía LLM (`llm_client.reformulate_query()`) antes del embedding. Así: turno 1 "¿cuántos días con 10 años?" → respuesta; turno 2 "¿y si llevo 15?" → se reformula a "¿cuántos días con 15 años?" y el RAG funciona. Reset automático al cambiar tenant/usuario. La respuesta incluye `original_query`, `embedded_query` y `query_reformulated` para trazabilidad.

✅ **Fix CONTRADICTS falsos positivos (sesión 4)**: el grafo creaba aristas rojas entre claims con mismo `predicate` pero `subject` totalmente distinto (ej. "responsable" de RRHH vs de limpieza). Ahora el Cypher exige `subject` igual o substring containment en cualquier dirección. Aplicado en `graph_client.link_contradictions_between_chunks` (live) y `scripts/graph_backfill.py` (batch). Para limpiar las aristas falsas existentes: `MATCH ()-[r:CONTRADICTS]->() DELETE r` + relanzar backfill.

✅ **Documento de seguridad** `docs/CHAT-PIPELINE-GUARDRAILS.md` (sesión 4) — diseño Phase 8 para n8n + ingress/egress guardrails (Lakera/Rebuff + Presidio + rate limit). Capítulo de la memoria TFM "Seguridad del chat como producto SaaS".

✅ **Phase 7.3 MCP Server (sesión 5)** — Korio expuesto como servidor MCP HTTP+SSE para Claude Desktop / ChatGPT / n8n. 3 tools (`search_knowledge_base`, `list_pending_conflicts`, `list_spaces`). API key por usuario (SHA-256 en `mcp_api_keys`). Auth via `MCPAuthASGI` puro (NO BaseHTTPMiddleware: rompe streams SSE). Doc completo en `docs/MCP-SERVER.md`. Conectado a Claude Desktop vía `mcp-remote` por npx (Node 20+).

✅ **Fix encadenado del RAG híbrido (sesión 5)** — cuando el grafo debía aportar la respuesta (caso TFM "35 horas semanales mínimas"):
  1. **Prompt RAG ignoraba el grafo**: el bloque `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]` iba FUERA del `CONTEXTO:`. Mistral, literal, lo descartaba. Solución: `build_rag_prompt(graph_context=...)` lo inyecta DENTRO + system_prompt declara que ambas fuentes son válidas.
  2. **Retrieval saturado por subject genérico**: keyword "política" capturaba `LIMIT 20` de claims con subject "política vacaciones", expulsando los claims con value "35 horas/semana". Solución: LIMIT 50 + rerank en Python (`score = 3·predicate + 2·value + 1·subject` por keyword).
  3. **Citación de fuentes en MCP**: docstring + `instructions` del FastMCP server obligan al cliente a citar `filename` y avisar de `is_disputed`.
  4. **list_spaces -32602**: añadido parámetro `include_inactive` dummy para que FastMCP serialice el schema con ≥1 param.

## Fuentes de verdad (léelas si necesitas contexto)

1. **`CLAUDE.md`** del repo — memoria técnica, stack, URLs, comandos VPS
2. **`docs/ROADMAP.md`** — phases pasadas y siguientes con checklist
3. **`docs/MULTI-TENANT-INGESTION.md`** — diseño Phase 8 (post-TFM) para ingesta SaaS configurable
4. **`docs/CHAT-PIPELINE-GUARDRAILS.md`** — diseño Phase 8 (post-TFM) para chat con guardrails n8n
5. **Notion · Estado técnico para TFM** — https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a
6. **Notion · Roadmap & Tareas** — https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533
7. **Notion · Historial de Desarrollo** (Troubleshooting) — https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1
8. **Notion · Company brain proceso completo** — https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6

## Reglas críticas que NUNCA debes saltar

- **Embeddings `nomic-embed-text`, 768 dims FIJOS**. Cambiar el modelo requiere re-ingestar TODA la BD.
- **RLS en dos capas siempre**: aplicación (`db.py` early binding) + PostgreSQL (Supabase policies). El grafo añade tercera capa filtrando por `tenant_id + allowed_space_ids`.
- **Comentarios y commits en español**, código (variables, funciones, clases) en inglés.
- **No agregar dependencias sin consultar**.
- **n8n: la instancia de Korio es `n8n.korio.es`, NO `n8n.lagalga.es`**. El `n8n-mcp` de Claude Code apunta a lagalga; los workflows hay que crearlos ahí y exportar/importar a korio, O usar `N8N_KORIO_API_KEY` del `.env` del VPS con curl contra la API REST de korio. (Ver memoria local `feedback_n8n_instance.md`.)
- **Webhook HITL protegido con Basic Auth**: cualquier llamada desde el backend debe ir con `HITL_WEBHOOK_USER` + `HITL_WEBHOOK_PASS` (ya parcheado en `conflict_detector.py` y `escalation.py`).

## Acceso al VPS y servicios

```bash
ssh korio-vps                                    # alias en ~/.ssh/config → 167.233.72.42
docker ps                                         # contenedores: korio-ollama, korio-n8n, korio-falkordb
systemctl status korio-api                        # FastAPI service
journalctl -u korio-api -f                        # logs tiempo real
curl https://korio.es/health                      # health check
```

Variables clave del `.env` del VPS (no las pongas en código, ya están en `/root/korio/.env`):
- `MISTRAL_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `KORIO_ADMIN_API_KEY`
- `HITL_WEBHOOK_URL=https://n8n.korio.es/webhook/korio-hitl`
- `HITL_WEBHOOK_USER=HITL_USER_REDACTED`, `HITL_WEBHOOK_PASS=HITL_PASS_REDACTED` (basic auth del webhook)
- `KORIO_GRAPH_ENABLED=1`, `FALKORDB_HOST=127.0.0.1`, `FALKORDB_PORT=6379`
- `ESCALATION_REMINDER_DAYS=3,7,14`, `ESCALATION_TIMEOUT_DAYS=21`
- `N8N_KORIO_API_KEY`, `N8N_KORIO_BASE_URL=https://n8n.korio.es` (para crear workflows directos sin pasar por lagalga)

## n8n.korio.es — credenciales y workflows existentes

- API key n8n.korio.es disponible en `/root/korio/.env` como `N8N_KORIO_API_KEY` — usar con curl contra `https://n8n.korio.es/api/v1/workflows`
- Credenciales configuradas:
  - **SMTP Gmail App Password** (`Q22eV5wvxgFQzbOz`) — puerto 587 STARTTLS
  - **Gmail OAuth2** (lectura) — para Gmail Trigger del workflow de ingesta
  - **Google Drive OAuth2** — para Drive Trigger del workflow de ingesta
  - **Slack API** (bot token `xoxb-...`) — para el bot `Korio-Delos`
- 5 workflows activos (detalles arriba)

## Hoy quiero atacar — contenido TFM

Faltan **~21 días para demo (2 jul)** y **~28 días para defensa (9 jul)**. El esfuerzo crítico ahora es contenido TFM. El código en producción está al 100% del scope demostrable (Phases 1–7.3 cerradas).

**Camino A · Contenido TFM (recomendado, lo crítico)**
- QA E2E: ronda de 10+ queries en ambos tenants vía `korio.es/ui` Y vía MCP en Claude Desktop (demuestra que el RAG es conectable al ecosistema agéntico)
- Ejecutar `scripts/benchmark.py` para sacar p50/p95 formales
- Grabar vídeo demo (3-4 min): correo llega → 30s después consultable → multi-turn → conflicto → email HITL → grafo → cierra con la query del hito desde Claude Desktop (MCP)
- Empezar slide deck (10-15 slides)

**Camino B · Memoria TFM**
- Escribir capítulos con los docs de diseño ya listos: `MULTI-TENANT-INGESTION.md`, `CHAT-PIPELINE-GUARDRAILS.md`, `MCP-SERVER.md` (todos = capítulos Phase 8 / 7.3)
- Sección de decisiones de diseño: grafo+RAG híbrido, FalkorDB vs Neo4j, query reformulation vs context-in-prompt, **MCP HTTP+SSE vs OAuth (Phase 8)**, **ASGI puro vs BaseHTTPMiddleware** (anécdota del bug de SSE)

**Camino C · Mejoras opcionales del RAG** (post-defensa o si sobra tiempo)
- Rerank semántico del grafo con embedding de la query (en lugar del scoring lexical actual)
- Sistema agéntico de inmunidad de conocimiento (5 agentes + cron) que tengo pendiente de contar — aplicación a la ingesta con HITL

## Pendiente antes de la defensa (2 jul demo, 9 jul defensa)

| Tarea | Estimación | Prioridad |
|---|---|---|
| QA end-to-end: 10+ queries en ambos tenants (multi-turn + MCP en Claude Desktop) | 2-3h | 🔴 Alta |
| Benchmark formal `scripts/benchmark.py` (p50/p95 + comparativa con MCP) | 1h | 🔴 Alta |
| Vídeo demo del ciclo completo (Gmail/Drive/Slack → gobernanza → grafo → MCP en Claude Desktop) | 3-4h | 🔴 Alta |
| Slide deck (10-15 slides) + ensayo | 6-8h | 🔴 Alta |
| Memoria TFM (capítulos Phase 7.3 `MCP-SERVER.md` + Phase 8 `MULTI-TENANT-INGESTION.md` + `CHAT-PIPELINE-GUARDRAILS.md`) | 20-30h | 🔴 Alta |
| ~~Phase 7.3 MCP Server~~ | ✅ Hecho sesión 5 |   |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código (variables, funciones, clases) en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque** — no implementes 4h de código sin checkpoint.
- Si tocas algo en n8n, recuerda: **n8n.korio.es no es n8n.lagalga.es**. Lee la memoria local `feedback_n8n_instance.md` si dudas.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:` en inglés + descripción en español.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** y los docs locales al cierre para que mañana arranque limpio.
