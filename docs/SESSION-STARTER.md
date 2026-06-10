# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Continuamos con **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Trabajamos siempre en el worktree:

```
/Users/berto/Claude Code/korio/.claude/worktrees/nifty-booth-0c25a5
```

Configurado para que `git push` (sin args) publique directamente en `main`.

## Estado actual (al cierre de la última sesión · 10 jun 2026 · tarde)

✅ **Phases 1–7.2 completadas**. En producción:

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

## Fuentes de verdad (léelas si necesitas contexto)

1. **`CLAUDE.md`** del repo — memoria técnica, stack, URLs, comandos VPS
2. **`docs/ROADMAP.md`** — phases pasadas y siguientes con checklist
3. **`docs/MULTI-TENANT-INGESTION.md`** — diseño Phase 8 (post-TFM) para ingesta SaaS configurable
4. **Notion · Estado técnico para TFM** — https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a
5. **Notion · Roadmap & Tareas** — https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533
6. **Notion · Historial de Desarrollo** (Troubleshooting) — https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1
7. **Notion · Company brain proceso completo** — https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6

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

## Próxima sesión — Phase 7.3 MCP Server

Exponer Korio como servidor MCP para que Claude Desktop / ChatGPT / n8n puedan llamar a las funciones del backend como herramientas. Tools previstas:

- `search_knowledge_base(query, user_id, tenant_id)`
- `ingest_document(file_url, tenant_id, space_id)`
- `list_pending_conflicts(tenant_id)`
- `list_spaces(user_id)`

Stack probable: FastAPI MCP endpoint (mantiene Python). Decisiones a cerrar al arrancar: auth (¿API key? ¿OAuth?), formato de tools (JSON Schema), si tener un MCP por tenant o uno global.

## Pendiente antes de la defensa (2 jul demo, 9 jul defensa)

- QA end-to-end: 10+ queries en ambos tenants
- Benchmark formal de latencias (`scripts/benchmark.py`)
- Slide deck (10–15 slides)
- Vídeo demo del ciclo completo: ingesta automática (Gmail/Drive/Slack) → gobernanza → grafo → consulta
- Memoria TFM: capítulo dedicado al diseño Phase 8 (multi-tenant ingest) basado en `docs/MULTI-TENANT-INGESTION.md`
