# Korio — Prompt de arranque para nueva sesión

> Cópialo tal cual al inicio de una sesión nueva con Claude Code.

---

Hola. Arrancamos sesión nueva de **Korio** (mi TFM del Máster IA Business & Innovation de Nuclio). El repo es `lagalga/korio`, branch `main`. Claude Code crea su propio worktree por sesión bajo `/Users/berto/Claude Code/korio/.claude/worktrees/<nombre-aleatorio>` — verifícalo con `git worktree list`. Trabaja contra el path del worktree de esta sesión.

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

Si quedan worktrees obsoletos de sesiones anteriores, limpiarlos al inicio:
```bash
cd "/Users/berto/Claude Code/korio"
git worktree list                                     # ver los activos
git worktree remove --force .claude/worktrees/<NAME>  # borrar los que ya no se usan
git branch -d claude/<NAME>                           # borrar branch local mergeada en main
git push origin --delete claude/<NAME>                # borrar en remoto
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

## Estado al cierre de sesión 13c · 16 jun 2026 · v0.3.6 · Regla 4 demostrada + inconclusive en RAG

✅ **Sesión 13c (16 jun) — Regla 4 (políticas reutilizables) demostrada + fix inconclusive en RAG**:
- **Regla 4 verificada** — ciclo completo: admin resolvió R6↔R7 → policy `policy_new_wins` creada → re-ingesta R6+R7 → chunk 242↔240 (sim=0.98) auto-resuelto por policy sin HITL. `times_applied=1`.
- **Las 6 reglas del E3 cerradas con evidencia de producción**.
- **Migración 020** — `search_embeddings` RPC incluye `inconclusive`. Chunks `inconclusive` ahora visibles en RAG con badge ⚠️.
- **`src/search.py`** — `inconclusive` tratado igual que `disputed` (badge + aviso).
- **`src/db.py`** — `resolve_conflict_review()` acepta `timeout_inconclusive` → admin puede overridear decisiones de timeout.
- **Fix PyMuPDF** — `pymupdf.open()` para extracción de PDFs (mejor calidad que MarkItDown).
- **18 docs expandidos** a 550-950 palabras para mayor riqueza semántica.
- **3 commits a `main`**: `544e75f`, `0ac0d72`, `7ee4c57`.

🔲 **Pendientes Phase 9 (no bloqueantes para vídeo)**:
- Validación semántica LLM en detector ingesta (falsos positivos G1↔G2).
- Workflow Slack: doc-ya-existe → DM en lugar de errorWorkflow.
- Reintroducir índice vectorial con volumen >1000 chunks.

---

## Estado al cierre de sesión 14 · 16 jun 2026 · v0.3.7 · 🏁 Implementación cerrada

✅ **Sesión 14 (16 jun) — Cierre implementación + herramientas de demo**:
- **27 aristas CONTRADICTS** en grafo: 13 (242↔240 resuelto) + 14 (243↔241 pendiente). Claims manuales para chunk 241 (LLM truncaba JSON).
- **`scripts/demo_snapshot.py`** — save/restore de Supabase + FalkorDB. Snapshot `pre_demo_v036` guardado (18 docs, 63 chunks, 925 nodos, 1475 aristas).
- **Fix test** `test_busqueda_sin_contexto` — adaptado a RAG híbrido. **31/31 tests verdes**.
- **1 commit a `main`**: `d4a23e3`.

**🏁 Implementación cerrada.** A partir de aquí: contenido (vídeo, slides, memoria con parte de negocio).

Uso del snapshot:
```bash
ssh korio-vps
cd /root/korio && source .venv/bin/activate

# Antes de grabar: verificar que el snapshot existe
python scripts/demo_snapshot.py list

# Si algo sale mal durante la grabación:
python scripts/demo_snapshot.py restore --name pre_demo_v036 -y
systemctl restart korio-api
```

---

## Estado al cierre de sesión 15 · 18 jun 2026 · v0.3.10 · Fixes pre-vídeo

✅ **Sesión 15 (18 jun) — Correcciones críticas para demo**:
- **Fix MCP `search_knowledge_base`** — era bug de `mcp-remote@0.1.38` (timing al iniciar SSE). Upgrade a `mcp-remote@latest` en Claude Desktop resolvió. El servidor ejecutaba correctamente desde el principio.
- **Fix R4 chunks `superseded`** — falso positivo del detector: R4 chunk 0 (35h para asalariados, id=185) y R4 chunk 1 (id=186) marcados como `superseded` por similitud con L1 chunk 0 (35h para médicos residentes, distinto sujeto). Restaurados a `active` en Supabase + FalkorDB.
- **Fix PII redaction garblaba filenames** (`src/llm_client.py`) — `_redact_for_mistral` usaba spaCy para redactar TODOS los tipos de entidad. El modelo `es_core_news_lg` etiquetaba "sanitario" como entidad → `[R4_<REDACTED>]`. Fix: whitelist `_PII_ENTITY_TYPES` con solo PERSON, EMAIL_ADDRESS, PHONE_NUMBER, NRP, CREDIT_CARD, IBAN_CODE, MEDICAL_LICENSE, etc. Filenames y términos técnicos conservados.
- **Fix header grafo echoed por Mistral** (`src/search.py`) — `_graph_context()` generaba bloque con header literal `[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]` que Mistral copiaba en la respuesta. Eliminado el header; texto instructivo simplificado.
- **Snapshot `pre_demo_v037`** guardado — 20 docs, 74 chunks, 1130 nodos, 1818 aristas.
- **Demo query verificada**: "¿cuántas horas semanales mínimas?" → "35 horas semanales para el personal asalariado **[R4_convenio-colectivo-sanitario-resumen.md]**" con `graph_contributed: True`. ✅
- **1 commit a `main`**: `6dcd804`.

Uso del snapshot actualizado:
```bash
ssh korio-vps
cd /root/korio && source .venv/bin/activate
python scripts/demo_snapshot.py list     # pre_demo_v037 + pre_demo_v036
python scripts/demo_snapshot.py restore --name pre_demo_v037 -y
systemctl restart korio-api
```

---

## Estado al cierre de sesión 15b · 18 jun 2026 · v0.3.11 · Vídeo grabado

✅ **Sesión 15b (18 jun · tarde) — Recovery durante grabación + ranking fix**:
- **Bug ranking detectado en directo**: M3_ibuprofeno top 0.620 para query de "horas semanales" por ruido lexical. R4 (doc correcto) 3º.
- **Fix**: `scripts/reembed_strip_frontmatter.py` — re-embeber 4 chunks `idx=0` sin frontmatter YAML. R4 sube de 3º (0.607) a 1º (0.632). Query vaga "cuántas horas hay que trabajar" pasa de "No encuentro" a respuesta correcta.
- **Bug Presidio ingesta**: chunks con `Dpto. <REDACTED>`, `Clínica Delos · <REDACTED>` visible en preview HITL. Aplicada misma whitelist `_PII_TYPES` en `src/preprocessor.py`. Ingestas nuevas limpias.
- **Snapshot `pre_demo_v038`** guardado (20 docs, 74 chunks, 1130 nodos, 1818 aristas).
- **Reset post-grabación** ejecutado: restore v038 + borrado R2 + L3 (Postgres + grafo). Próxima toma re-ingestará por Gmail/Drive con PII fix activo (sin `<REDACTED>` cosmético).
- **3 commits a `main`**: `87a75fc`, `753e75b`, `<docs>`.

🔲 **Aprendizaje Phase 9**: el chunker debería excluir frontmatter YAML del embedding (mantener en metadata). Evita reembed post-hoc.

---

## Próxima sesión — **sesión 16 · Slide deck (10–15 slides)**

Vídeo demo grabado en s15+15b. Sistema listo para empezar contenido.

### Plan sesión 16 (estimación ~6-8 h)

1. **Outline slide deck** (estructura clásica TFM):
   - Portada + cover (Korio, autor, máster, fechas)
   - Problema (~2 slides): caos documental en pymes, RAG vainilla insuficiente
   - Estado del arte (~2 slides): vector RAG, multi-tenant, gobernanza
   - Arquitectura (~3 slides): pipeline ingesta, RLS dos capas, RAG híbrido
   - Las 6 reglas del E3 (1 slide cada una con micro-demo): ACID, detección, auto-resolución, policies, inconclusive, silent conflict
   - Resultados (~2 slides): métricas p50/p95, casos demostrados
   - Compliance (~1 slide): AI Act + GDPR
   - Limitaciones y futuro (~1 slide): Phase 8 multi-tenant OAuth, Phase 9 ranking/bias
   - Cierre (~1 slide): demo en vivo (vídeo)

2. **Generar slides** (Keynote/PowerPoint/`pptx` skill).

3. **Ensayo cronometrado** (~20 min defensa).

### Sesiones posteriores

| Sesión | Objetivo | Estimación | Herramienta |
|---|---|---|---|
| **16** | **Slide deck** (10-15 slides) | 6-8h | Claude Code |
| **17+** | **Memoria TFM** (negocio + técnico) | 20-30h | Claude Projects |
| **18** | **Ensayo defensa** (9 jul) | 2-3h | — |

### Casuística cubierta (las 6 reglas del E3)

| Regla | Sesión cerrada |
|---|---|
| 1 ACID | 13b ✅ |
| 2 Detección | 13b ✅ |
| 3 Auto-resolución por fecha/autoridad | 13b ✅ |
| 4 Políticas reutilizables | 13c ✅ |
| 5 Inconclusive por timeout | 13b ✅ + 13c fix RAG |
| 6 Silent conflict same-space | 13b ✅ |

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
| ~~Dry-run demo con docs nuevos~~ | ~~2-2.5h~~ | ✅ Sesión 13b |
| ~~Regla 4 (políticas reutilizables) demo~~ | ~~1h~~ | ✅ Sesión 13c |
| ~~Inconclusive visible en RAG~~ | ~~30min~~ | ✅ Sesión 13c |
| **Grabación vídeo demo** (3-4 min) | 3-4h | 🔲 Sesión 13d |
| **Slide deck** (10-15 slides) | 6-8h | 🔲 Sesión 14 |
| **Memoria TFM** (capítulos 4-9) | 20-30h | 🔲 Sesiones 15-16 |
| **Ensayo defensa** | 2-3h | 🔲 Sesión 17 |

## Convenciones de la sesión

- Responde **en español**. Comentarios y commits en español; código en inglés.
- Antes de cambios grandes, **valida conmigo el enfoque**.
- Si tocas algo en n8n, recuerda: **n8n.korio.es ≠ n8n.lagalga.es**.
- Cuando cierres una sub-tarea, **commitea atómicamente** con `Feat:` / `Fix:` / `Docs:`.
- Si la sesión se va a alargar, **actualiza este `SESSION-STARTER.md`** al cierre.
