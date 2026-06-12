# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Arrancamos sesión nueva de **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Trabajamos siempre en el worktree:

```
/Users/berto/Claude Code/korio/.claude/worktrees/dreamy-bose-cd8a36
```

Configurado para que `git push` (sin args) publique directamente en `main`.

## Lo primero que quiero que hagas (smoke check de 30s)

Antes de discutir qué atacamos hoy, verifica que producción sigue viva tras lo que cerramos ayer:

```bash
ssh korio-vps "systemctl is-active korio-api && docker ps --format '{{.Names}}' | grep -E 'ollama|n8n|falkordb' && curl -s https://korio.es/health"
```

Si todo OK, dímelo en una línea. Si algo está raro, antes de tocar nada cuéntame qué ves.

## Pasos manuales que pueden haber quedado pendientes de ayer

Sesión 10 (12 jun) quedó **todo desplegado y verificado** — no hay pendientes operativos.

Worktrees obsoletos pendientes de limpieza manual (el clasificador de auto-mode los bloqueó):
```bash
cd "/Users/berto/Claude Code/korio"
git worktree remove .claude/worktrees/great-elbakyan-832d81
git worktree remove .claude/worktrees/nifty-booth-0c25a5
git worktree remove --force .claude/worktrees/silly-hofstadter-5e49c0
```

## Estado actual (al cierre de sesión 10 · 12 jun 2026 · v0.3.0+fixes)

✅ **Phases 1–7.3 + v0.3.0 con las 6 reglas del Entregable 3 cumplidas**. En producción:

- `https://korio.es` — landing teaser
- `https://korio.es/ui` — chat RAG multi-tenant con gobernanza activa, banner ⚠️ de contradicciones y 3 puntos de acceso al grafo
- `https://korio.es/ui/graph.html` — grafo de conocimiento vivo (FalkorDB) con vis-network, panel de contradicciones rojas en tiempo real
- `https://korio.es/docs` — Swagger (con botón Authorize para los endpoints admin)
- `https://korio.es/mcp/sse` — **servidor MCP HTTP+SSE (Phase 7.3)**: 3 tools (`search_knowledge_base`, `list_pending_conflicts`, `list_spaces`). Auth con header `X-Korio-MCP-Key`. Conectado a Claude Desktop vía `mcp-remote` por npx (Node 20+ requerido).
- `https://n8n.korio.es` — **6 workflows activos**:
  - HITL email (gobernanza) — webhook protegido con Basic Auth
  - Cron escalada diaria 09:00 Madrid
  - **Gmail → /upload** (Phase 7.2): vigila label `korio/ingesta` en `contacto@lagalga.es`, ingiere adjuntos PDF/DOCX
  - **Drive → /upload** (Phase 7.2): vigila carpeta `Clínica Delos / input` (`1rlBEmkqLHvidWEPv64LaMpzBh9bMDGF4`)
  - **Slack `/korio` → /search** (Phase 7.2): comando que consulta Korio y responde en thread con fuentes

✅ **Sesión 10 (12 jun) — QA E2E 10/10 + Benchmark + fixes encadenados**:

**QA E2E completo (10/10 ✅)**:
- E1 directa vectorial, E2 grafo (35h/semana), E3 multi-turn con reformulación, E4 aislamiento RLS, E5 chunk disputed badge, E6 query-time silent_conflict, E7 MCP Claude Desktop, E8 MCP list_pending_conflicts, E9 ingesta Gmail, E10 bus de eventos n8n.

**Fixes aplicados en sesión 10**:
- **FalkorDB AOF persistencia** — `REDIS_ARGS=--appendonly yes --appendfsync everysec` en `docker-compose.yml`. El grafo sobrevivirá reinicios del contenedor sin pérdida de datos.
- **Benchmark `--delay` flag** — `scripts/benchmark.py` acepta `-d <segundos>` entre iteraciones para evitar rate-limit de Mistral en runs largos.
- **Retry Mistral 429** — `_generate_mistral()` en `llm_client.py` reintenta hasta 3 veces con backoff exponencial (1s/2s/4s) en 429.
- **Threshold búsqueda 0.4→0.35** — `src/search.py` y `api/server.py` bajaron el umbral por defecto para mejor recall en queries abiertas.
- **Threshold query-time conflict 0.85→0.80** — `KORIO_QUERY_TIME_CONFLICT_THRESHOLD=0.80` en VPS `.env`. Fix para el E6 (similitud máxima real era 0.8253).
- **Validación semántica CONTRADICTS** — `src/llm_client.py` nuevo método `is_semantic_contradiction()`. `src/graph_client.py` reescrito `link_contradictions_between_chunks()`: elimina filtro CONTAINS de subject (demasiado estricto → 0 aristas), recupera candidatos por predicate + valor distinto, valida par a par con Mistral (temp=0, max_tokens=5). `scripts/graph_backfill.py` delega al mismo método. Resultado: 2 aristas CONTRADICTS válidas en Delos vs 0 previas.

**Benchmark formal (`-n 10 --delay 1.5s`)**:
- Global p50 1983ms, p95 3053ms — dentro del rango defendible para el TFM.
- 50/50 queries sin errores (0 rate-limit hits con el delay + retry).

✅ **RAG híbrido**: vector + grafo. Caso TFM verificado: *"¿Cuántas horas semanales mínimas?"* → *"35 horas/semana"* en ~1.3s con `graph_contributed: True`.

✅ **Gobernanza activa**: chunks `active/disputed/inconclusive`. Auto-resolución + HITL email. Cron escalada. Policies reutilizables. 8/8 tests verdes (sesiones 6-9).

✅ **Phase 7.3 MCP Server**: `korio.es/mcp/sse` en producción. Claude Desktop conectado y verificado con query del hito.

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
- `KORIO_QUERY_TIME_CONFLICT_ENABLED=1`, `KORIO_QUERY_TIME_CONFLICT_THRESHOLD=0.80`
- `ESCALATION_REMINDER_DAYS=3,7,14`, `ESCALATION_TIMEOUT_DAYS=21`
- `N8N_KORIO_API_KEY`, `N8N_KORIO_BASE_URL=https://n8n.korio.es` (para crear workflows directos sin pasar por lagalga)

## n8n.korio.es — credenciales y workflows existentes

- API key n8n.korio.es disponible en `/root/korio/.env` como `N8N_KORIO_API_KEY` — usar con curl contra `https://n8n.korio.es/api/v1/workflows`
- Credenciales configuradas:
  - **SMTP Gmail App Password** (`Q22eV5wvxgFQzbOz`) — puerto 587 STARTTLS
  - **Gmail OAuth2** (lectura) — para Gmail Trigger del workflow de ingesta
  - **Google Drive OAuth2** — para Drive Trigger del workflow de ingesta
  - **Slack API** (bot token `xoxb-...`) — para el bot `Korio-Delos`
- 6 workflows activos (detalles arriba)

## Próxima sesión — **sesión 11 · Vídeo demo + Slide deck + Memoria TFM**

Faltan **~20 días para demo (2 jul)** y **~27 días para defensa (9 jul)**. El código y la funcionalidad están completos. La sesión 11 es de contenido de defensa.

**Agenda de la sesión (en este orden)**

### 1. Vídeo demo (3-4h)

Guión: ciclo completo en ~3-4 minutos:
1. Gmail llega con adjunto → label `korio/ingesta` → 30s después aparece en `/search`
2. Bus de eventos en n8n.korio.es: 3-4 ejecuciones visibles con emojis
3. Chat en `korio.es/ui`: query que activa el grafo (35h/semana), respuesta con fuente citada
4. Chunk disputed → badge ⚠️ en source chips
5. Detección query-time: aviso de la gobernanza
6. Claude Desktop con MCP: misma query, respuesta equivalente
7. `graph.html`: nodos, aristas CONTRADICTS rojas

### 2. Slide deck (6-8h)

10-15 slides para el tribunal. Estructura propuesta:
- Problema + oportunidad de mercado
- Arquitectura del sistema (diagrama con las 7 phases)
- Demo en vivo (clips del vídeo)
- Las 6 reglas del E3 materializadas
- Métricas: p50/p95 benchmark, latencias, datos en producción
- Phase 8: roadmap post-TFM
- Conclusiones

### 3. Memoria TFM (20-30h — trabajo de fondo)

Capítulos clave a redactar:
- **Capítulo 4**: Arquitectura RAG multi-tenant (pipeline ingesta, gobernanza ACID, RLS)
- **Capítulo 5**: Grafo de conocimiento (FalkorDB, CONTRADICTS semántico, hybrid RAG)
- **Capítulo 6**: Sistema agéntico (las 6 reglas del E3, pipeline ACID, bus de eventos)
- **Capítulo 7**: MCP Server (Phase 7.3) + Ingesta multi-canal (Phase 7.2)
- **Capítulo 8** (diseño futuro): `docs/MULTI-TENANT-INGESTION.md` + `docs/CHAT-PIPELINE-GUARDRAILS.md`

## Pendiente antes de la defensa (2 jul demo, 9 jul defensa)

| Tarea | Estimación | Estado |
|---|---|---|
| ~~**QA E2E** (10+ queries, ambos tenants, MCP, bus eventos)~~ | ~~2-3h~~ | ✅ Sesión 10 |
| ~~**Benchmark formal** `scripts/benchmark.py` (p50/p95 = 1983ms/3053ms)~~ | ~~1h~~ | ✅ Sesión 10 |
| ~~**Validación semántica CONTRADICTS** (2 aristas válidas en Delos)~~ | ~~2-3h~~ | ✅ Sesión 10 |
| ~~**Bajar threshold** recall 0.4 → 0.35 + conflict 0.85 → 0.80~~ | ~~30 min~~ | ✅ Sesión 10 |
| **Vídeo demo** (3-4 min): ciclo completo con n8n event bus en vivo | 3-4h | 🔲 Sesión 11 |
| **Slide deck** (10-15 slides) + ensayo | 6-8h | 🔲 Sesión 11 |
| **Memoria TFM** (capítulos 4-7) | 20-30h | 🔲 Sesiones 11-14 |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código (variables, funciones, clases) en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque** — no implementes 4h de código sin checkpoint.
- Si tocas algo en n8n, recuerda: **n8n.korio.es no es n8n.lagalga.es**. Lee la memoria local `feedback_n8n_instance.md` si dudas.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:` en inglés + descripción en español.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** y los docs locales al cierre para que mañana arranque limpio.
