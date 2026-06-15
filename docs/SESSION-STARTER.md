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
- **Webhook HITL con Basic Auth**: `HITL_WEBHOOK_USER=HITL_USER_REDACTED` + `HITL_WEBHOOK_PASS=HITL_PASS_REDACTED`.

## Acceso al VPS y servicios

```bash
ssh korio-vps                                    # alias → 167.233.72.42
systemctl status korio-api                        # FastAPI service
journalctl -u korio-api -f                        # logs tiempo real
curl https://korio.es/health                      # health check
```

## Estado al cierre de sesión 13b · 15 jun 2026 · v0.3.5 · multi-canal real + ivfflat fix

✅ **Sesión 13b (15 jun) — QA E2E con multi-canal real + ivfflat fix**:
- **18 docs en producción** (13 Delos + 5 García). Auto-resoluciones limpias en 5 pares por fecha extraída del contenido.
- **R6/R7 nuevos** (normativa uniformes RRHH sin fecha) → conflict pending → `/escalate-reviews` → chunks `inconclusive` ✅ regla 5 cubierta.
- **García 5 docs nuevos** (G1-G5) con conflict fiscal IRPF 2023↔2025 auto-resuelto.
- **Multi-canal real** verificado E2E:
  - Gmail label `korio/rrhh` → R2 → space RRHH ✅
  - Drive `input/medico` → M2 → space Médico ✅
  - Slack `#clinica-delos-legal` → L3 → space Legal ✅
- **4 service users Slack** (`slack_{rrhh,medico,legal,admin}@delos`) con scope por user_spaces. Workflow `/korio` mapea `channel_id → user_id` → RLS automático.
- **Fixes raíz aplicados** (5 commits):
  - `e5ea543` — `src/version_extractor.py` extrae fecha del documento (filename + content)
  - `68760ff` — R6/R7 + migración 016 silent conflict same-space (evita falsos cross-departamento)
  - `be13a45` — García 5 docs + migración 017 space Admin + 018 service users Slack + **019 DROP ivfflat** (causa raíz RPC=0)
- **Bug crítico ivfflat resuelto**: índice `lists=100` con 19 chunks → cada chunk en su propia lista → `ivfflat.probes=1` solo encontraba self-match. DROP del índice. Sin índice el seq scan es trivial con decenas de chunks. Reintroducir en Phase 9 con `lists=sqrt(N)` o HNSW.
- **Workflows n8n parametrizados**:
  - Slack: `channel_id → space_id` mapping (4 canales `#clinica-delos-{rrhh,medico,legal,admin}`)
  - Drive: 4 triggers paralelos (uno por subcarpeta `input/{rrhh,medico,legal,admin}`)
  - Gmail: filtro por label (`korio/{rrhh,medico,legal,admin}`) en lugar de `unread`, idempotencia vía `korio/procesado`
- **Notion troubleshooting actualizado**: 6 entradas (4 resoluciones, 2 problemas Phase 9, 1 aprendizaje).

🔲 **Pendientes Phase 9 (no bloqueantes para vídeo)**:
- Detector ingesta: falsos positivos entre docs temáticamente similares pero no contradictorios (G1↔G2 caso despacho). Fix: validación semántica LLM antes de declarar conflict.
- Workflow Slack: doc-ya-existe → DM al usuario en lugar de disparar errorWorkflow.
- Regla 4 (políticas reutilizables): no se cubrió aún, requiere admin resolviendo HITL vía email antes del timeout para que policy se persista.
- Reintroducir índice vectorial cuando volumen > 1000 chunks (ivfflat con `lists=sqrt(N)` o HNSW).

---

## Próxima sesión — **sesión 13c · Demo Regla 4 (políticas) + retoques UI HITL + commit final**

### Plan
1. **Demo regla 4 (políticas reutilizables)** (30 min): crear par de docs sintéticos R8/R9 sin fecha extraíble (mismo espacio), conflict pending, admin resuelve vía email HITL ANTES del timeout. Verificar que se persiste policy en tabla `policies`. Ingestar R10 similar → policy se aplica automáticamente (logs `📚 Policy`).
2. **Retoque UI email HITL** (en curso): mejoras al template del email enviado al admin para que sea más legible y refleje el branding Korio.
3. **Sesión cierre**: actualizar CHANGELOG con v0.3.5, etiquetar release, mover SESSION-STARTER a la siguiente fase.

---

## (Histórico) sesión 13b original · Dry-run de la demo con docs nuevos

Faltan **~18 días para demo (2 jul)** y **~25 días para defensa (9 jul)**. Programación cerrada en sesión 11. Hardening seguridad cerrado en 13a. Toca probar el flujo real con un set de documentos pensado para activar TODAS las casuísticas a demostrar.

### Set de documentos para la demo

11 ficheros generados en `data-synthetic/demo-tfm/` (tenant **Clínica Delos**). Markdown originales convertidos a PDF/DOCX donde aplica. README dentro de esa carpeta tiene el detalle de asignación, conversión y plan de ingesta. Resumen:

| # | Fichero | Space | Canal de ingesta | Casuística |
|---|---|---|---|---|
| R1 | `R1_politica-vacaciones-2023.pdf` | RRHH | manual | base disputed |
| R2 | `R2_politica-vacaciones-2025.pdf` | RRHH | **Gmail** | auto-resuelve sobre R1 |
| R3 | `R3_protocolo-bajas-medicas.pdf` | RRHH | manual | 12 meses IT |
| R4 | `R4_convenio-colectivo-sanitario-resumen.md` | RRHH | manual | grafo "35h/semana" rephrase |
| R5 | `R5_circular-bajas-2024.pdf` | RRHH | manual | silent conflict E4 con R3 (18 vs 12) |
| M1 | `M1_protocolo-atencion-urgencias.pdf` | Médico | manual | base disputed |
| M2 | `M2_guia-clinica-urgencias-actualizada.pdf` | Médico | **Drive** | auto-resuelve sobre M1 (Dr. jefe) |
| M3 | `M3_ficha-medicamento-ibuprofeno.md` | Médico | manual | PII anonimización Presidio |
| L1 | `L1_contrato-tipo-medico-residente.docx` | Legal | manual | bilingüe ES+EN |
| L2 | `L2_circular-lopd-datos-pacientes-v1.pdf` | Legal | manual | 5 años retención |
| L3 | `L3_circular-lopd-datos-pacientes-v2.pdf` | Legal | **Slack** | HITL → timeout → `inconclusive` |

### Plan de sesión 13b

1. **Reset del tenant Delos** (10 min). El grafo está actualmente fuera de sync (chunks disputed en Postgres, 0 nodos en FalkorDB) — antes de la nueva ingesta, borrar todos los docs Delos vía `DELETE /document/{id}` y confirmar `count(n)==0` en FalkorDB para `tenant_id=a0000000-...001`. Comando completo en `data-synthetic/demo-tfm/README.md` §Reset.
2. **Ingesta secuencial controlada** (45 min) siguiendo el orden del README (R1→R2 Gmail→R3→R4→R5→M1→M2 Drive→M3→L1→L2→L3 Slack). Cada paso debe disparar la casuística esperada (auto-resolución, silent conflict, HITL).
3. **Forzar `inconclusive` en L2↔L3** (10 min) — bajar `ESCALATION_TIMEOUT_DAYS=0` temporalmente, disparar `/escalate-reviews`, restaurar a 21.
4. **Backfill grafo si la sync online falla** (10 min) — `scripts/graph_backfill.py` + `scripts/graph_embed_claims.py` con `--tenant-id` Delos.
5. **QA con las 8 queries** del README §Fase 4 (15 min). Si todas pasan, dejar el estado tal cual hasta el día de grabación del vídeo.
6. **Notas para vídeo + slides** (10 min) — capturar timing de cada caso (Gmail llega → 30s después aparece, etc.) y screenshots de grafo + banner ⚠️.

Tiempo estimado: **2-2.5h**.

### Sesiones posteriores (después de la 13b)

| Sesión | Objetivo | Estimación |
|---|---|---|
| **13c** | Reset + ingesta limpia + **grabación vídeo demo** (3-4 min) con el guion del README §Fase 4 | 3-4h |
| **14** | **Slide deck** (10-15 slides) | 6-8h |
| **15-16** | **Memoria TFM** (capítulos 4-7 + anexo seguridad de `docs/AUDIT-2026-06-14.md`) | 20-30h |
| **17** | **Ensayo defensa** ante el tribunal (9 jul) | 2-3h |

### Guion del vídeo (a fijar en 13c)

~3-4 minutos cubriendo:
1. Gmail (R2) llega → label `korio/ingesta` → 30s después aparece en `/search`
2. Bus de eventos en `n8n.korio.es`: 3-4 ejecuciones visibles
3. Chat en `korio.es/ui`: "¿Cuánto se trabaja a la semana?" → grafo aporta 35h
4. Query "¿Cuántos días de vacaciones?" → R2 gana, R1 disputed (badge ⚠️)
5. Query "¿Cuánto dura la baja?" → silent conflict R3↔R5, aviso gobernanza
6. Claude Desktop con MCP: misma query, respuesta equivalente con citas
7. `graph.html`: nodos por persona/concepto, arista CONTRADICTS roja, hover en sidebar

### Slide deck (esquema sesión 14)

10-15 slides para el tribunal:
- Problema + oportunidad de mercado pyme española
- Arquitectura del sistema (diagrama 7 phases)
- Demo en vivo (clips del vídeo)
- Las 6 reglas del E3 materializadas (tabla `docs/AGENTIC-INGESTION.md` §Cumplimiento)
- Métricas: p50=1983ms / p95=3053ms / 28/28 tests / 8 workflows n8n
- Seguridad: auditoría 21 hallazgos · 7 cerrados · 14 mapeados a Phase 8/9 (`docs/AUDIT-2026-06-14.md`)
- Phase 8 (post-TFM): OAuth multi-tenant + guardrails LLM + ingesta multimodal
- Conclusiones + cierre

### Memoria TFM (sesiones 15-16)

Capítulos clave:
- **Capítulo 4** — Arquitectura RAG multi-tenant (pipeline ingesta, gobernanza ACID, RLS).
- **Capítulo 5** — Grafo de conocimiento (FalkorDB, CONTRADICTS semántico, hybrid RAG con RRF).
- **Capítulo 6** — Sistema agéntico (las 6 reglas del E3, pipeline ACID, bus de eventos).
- **Capítulo 7** — MCP Server (Phase 7.3) + Ingesta multi-canal (Phase 7.2).
- **Capítulo 8** — Seguridad y deuda técnica reconocida (`docs/AUDIT-2026-06-14.md` como anexo).
- **Capítulo 9** (diseño futuro) — `MULTI-TENANT-INGESTION.md` + `CHAT-PIPELINE-GUARDRAILS.md` + `PHASE-10-MULTIMODAL-INGESTION.md`.

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
| ~~Hardening seguridad (auditoría 21 hallazgos, 7 cerrados)~~ | ~~3h~~ | ✅ Sesión 13a |
| **Dry-run demo con docs nuevos** | 2-2.5h | 🔲 Sesión 13b (mañana) |
| **Grabación vídeo demo** (3-4 min) | 3-4h | 🔲 Sesión 13c |
| **Slide deck** (10-15 slides) | 6-8h | 🔲 Sesión 14 |
| **Memoria TFM** (capítulos 4-9) | 20-30h | 🔲 Sesiones 15-16 |
| **Ensayo defensa** | 2-3h | 🔲 Sesión 17 |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque**.
- Si tocas algo en n8n, recuerda: **n8n.korio.es ≠ n8n.lagalga.es**.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:`.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** al cierre.
