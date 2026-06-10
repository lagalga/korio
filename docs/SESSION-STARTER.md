# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Continuamos con **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Trabajamos siempre en el worktree:

```
/Users/berto/Claude Code/korio/.claude/worktrees/nifty-booth-0c25a5
```

Configurado para que `git push` (sin args) publique directamente en `main`.

## Estado actual (al cierre de la última sesión)

✅ **Phases 1–7.1 completadas**. En producción:
- `https://korio.es` — landing teaser
- `https://korio.es/ui` — chat RAG multi-tenant con gobernanza activa, banner ⚠️ de contradicciones y 3 puntos de acceso al grafo
- `https://korio.es/ui/graph.html` — grafo de conocimiento vivo (FalkorDB) con vis-network, panel de contradicciones rojas en tiempo real
- `https://korio.es/docs` — Swagger
- `https://n8n.korio.es` — 2 workflows activos: HITL email + cron escalada diario

✅ El RAG es **híbrido vector + grafo**: cuando la query está semánticamente rephrasada respecto al texto, el grafo recupera el dato por entidades/predicates. Caso TFM: *"¿Cuántas horas semanales mínimas exige la política?"* → *"más de 35 horas/semana"* en ~1s.

✅ Gobernanza activa **al nivel de chunk**: chunks `active` / `superseded` / `disputed`. Auto-resolución por fecha/autoridad. HITL email con 3 botones de acción. Cron de escalada (3/7/14/21 días). Sincronización con grafo en tiempo real.

## Fuentes de verdad (léelas si necesitas contexto)

1. **`CLAUDE.md`** del repo — memoria técnica, stack, URLs, comandos VPS
2. **`docs/ROADMAP.md`** — phases pasadas y siguientes con checklist
3. **Notion · Estado técnico para TFM** — https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a — síntesis para la memoria del TFM, decisiones de diseño justificadas
4. **Notion · Roadmap & Tareas** — https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533
5. **Notion · Historial de Desarrollo** (Troubleshooting) — https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1 — bugs y resoluciones registradas (~35 entradas)
6. **Notion · Company brain proceso completo** — https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6 — descripción funcional y de negocio (incluye sección de gobernanza activa que es el diseño que implementamos)

## Reglas críticas que NUNCA debes saltar

- **Embeddings `nomic-embed-text`, 768 dims FIJOS**. Cambiar el modelo requiere re-ingestar TODA la BD.
- **RLS en dos capas siempre**: aplicación (`db.py` early binding) + PostgreSQL (Supabase policies). El grafo añade tercera capa filtrando por `tenant_id + allowed_space_ids`.
- **Comentarios y commits en español**, código (variables, funciones, clases) en inglés.
- **No agregar dependencias sin consultar**.

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
- `KORIO_GRAPH_ENABLED=1`, `FALKORDB_HOST=127.0.0.1`, `FALKORDB_PORT=6379`
- `ESCALATION_REMINDER_DAYS=3,7,14`, `ESCALATION_TIMEOUT_DAYS=21`

## n8n.korio.es — credenciales y workflows existentes

- API key n8n (válida hasta abril 2027) la tenemos guardada y se reutiliza
- Credenciales configuradas: **SMTP Gmail App Password** (id `Q22eV5wvxgFQzbOz`, puerto 587 STARTTLS — el 465 está bloqueado por Hetzner)
- 2 workflows activos:
  - `Yr4Sfw7AXlucXpmJ` — HITL email (Webhook → Code → Send Email)
  - `8yURb0pZRumuRdW8` — Cron escalada (Schedule Trigger daily 09:00 Madrid)

## Hoy queremos atacar

**Phase 7.2 — n8n workflows de ingesta automática**:

1. **Gmail → Korio**: vigilar una carpeta de Gmail, extraer adjuntos PDF/DOCX de correos nuevos y llamarlos a `POST /upload` con tenant/space configurables.
2. **Google Drive monitor**: vigilar una carpeta de Drive, ingerir cambios automáticamente.
3. **Slack `/korio`**: comando que dispara `POST /search` y devuelve la respuesta en el thread.

Después (si da tiempo) **Phase 7.3 — MCP Server** para exponer Korio a Claude Desktop / ChatGPT / n8n.

## Empezamos por…

Sugerencia: empezar por el workflow Gmail (más demo-friendly para el TFM). Antes de tirar código, plantearme:
- ¿Cuenta Gmail dedicada o reutilizamos contacto@lagalga.es con filtro por etiqueta?
- ¿Mapping de remitente → tenant/space (ej. ingest@delos.com → tenant Delos / space RRHH)?
- ¿Notificación al usuario tras ingesta exitosa?

Empieza preguntándome qué prefiero para esas 3 decisiones.
