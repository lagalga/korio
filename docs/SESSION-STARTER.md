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

1. **Despliegue en VPS** de los commits de ayer tarde (cierre Phase 7.2 + sesión 4):
   ```bash
   ssh korio-vps "cd /root/korio && git pull && systemctl restart korio-api"
   ```
2. **Cleanup de aristas CONTRADICTS falsas** en el grafo (one-off, solo si no lo hice ayer):
   ```bash
   ssh korio-vps "cd /root/korio && .venv/bin/python -c \"from src.graph_client import get_graph_client; get_graph_client().graph.query('MATCH ()-[r:CONTRADICTS]->() DELETE r')\""
   ssh korio-vps "cd /root/korio && .venv/bin/python scripts/graph_backfill.py"
   ```
3. **Verificar memoria de chat** en `korio.es/ui` con dos preguntas encadenadas (ej: vacaciones con 10 años → y si llevo 15). Si la 2ª no usa contexto, hay que mirar logs del backend.

Si todo eso está hecho, lo confirmo y pasamos a contenido. Si no, lo hacemos primero antes de cualquier otra cosa.

## Estado actual (al cierre de la última sesión · 10 jun 2026 · tarde · sesión 4)

✅ **Phases 1–7.2 completadas + memoria de chat + fix CONTRADICTS**. En producción:

- `https://korio.es` — landing teaser
- `https://korio.es/ui` — chat RAG multi-tenant con gobernanza activa, banner ⚠️ de contradicciones y 3 puntos de acceso al grafo
- `https://korio.es/ui/graph.html` — grafo de conocimiento vivo (FalkorDB) con vis-network, panel de contradicciones rojas en tiempo real
- `https://korio.es/docs` — Swagger (con botón Authorize para los endpoints admin)
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
- `HITL_WEBHOOK_USER=B3rt0`, `HITL_WEBHOOK_PASS=13-K0rio-14!` (basic auth del webhook)
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

## Hoy quiero atacar — contenido TFM o Phase 7.3

Faltan **~22 días para demo (2 jul)** y **~29 días para defensa (9 jul)**. El esfuerzo crítico es contenido TFM (memoria + slides + vídeo + QA). El código en producción ya cubre todo lo que necesitamos demostrar.

Tienes dos caminos prioritarios y un opcional:

**Camino A · Contenido TFM (recomendado, lo crítico)**
- QA E2E: ronda de 10+ queries en ambos tenants vía `korio.es/ui` (algunas usando memoria de chat para demostrar el multi-turn)
- Ejecutar `scripts/benchmark.py` para sacar p50/p95 formales
- Grabar vídeo demo (2-3 min): correo llega → ~30s después consultable → multi-turn → conflicto → email HITL → grafo
- Empezar slide deck (10-15 slides)

**Camino B · Memoria TFM**
- Escribir capítulos con los docs de diseño ya listos: `MULTI-TENANT-INGESTION.md` (post-TFM) y `CHAT-PIPELINE-GUARDRAILS.md` (post-TFM)
- Sección de decisiones de diseño (graf+RAG híbrido, FalkorDB vs Neo4j, query reformulation vs context-in-prompt, etc.)

**Camino C · Phase 7.3 MCP Server (opcional, bonus)**
- Exponer Korio como servidor MCP para Claude Desktop / ChatGPT / n8n
- Tools: `search_knowledge_base`, `ingest_document`, `list_pending_conflicts`, `list_spaces`
- Stack probable: FastAPI MCP endpoint

## Pendiente antes de la defensa (2 jul demo, 9 jul defensa)

| Tarea | Estimación | Prioridad |
|---|---|---|
| QA end-to-end: 10+ queries en ambos tenants (con casos multi-turn) | 2-3h | 🔴 Alta |
| Benchmark formal `scripts/benchmark.py` (p50/p95) | 1h | 🔴 Alta |
| Vídeo demo del ciclo completo (ingesta Gmail/Drive/Slack → gobernanza → grafo → consulta multi-turn) | 3-4h | 🔴 Alta |
| Slide deck (10-15 slides) + ensayo | 6-8h | 🔴 Alta |
| Memoria TFM (capítulos Phase 8 ya en `docs/MULTI-TENANT-INGESTION.md` + `docs/CHAT-PIPELINE-GUARDRAILS.md`) | 20-30h | 🔴 Alta |
| Phase 7.3 MCP Server | 1 sesión (~4h) | 🟢 Opcional |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código (variables, funciones, clases) en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque** — no implementes 4h de código sin checkpoint.
- Si tocas algo en n8n, recuerda: **n8n.korio.es no es n8n.lagalga.es**. Lee la memoria local `feedback_n8n_instance.md` si dudas.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:` en inglés + descripción en español.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** y los docs locales al cierre para que mañana arranque limpio.
