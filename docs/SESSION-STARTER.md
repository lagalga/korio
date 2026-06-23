# SESSION-STARTER · Korio TFM

> Cópialo al inicio de cada sesión nueva (Claude Code o Claude Projects) para retomar con contexto completo.

---

## Estado actual

**Versión**: v0.3.14
**Última sesión**: 17c (23 jun 2026) — promoción HITL chunk→doc + fixes restore demo + UI RLS-aware + MCP cita inline
**Estado global**: 🏁 **Implementación cerrada · Vídeo demo grabado**
**Defensa TFM**: 9 julio 2026 (Nuclio Digital School)

---

## Hecho hasta hoy (compactado por fase)

### Núcleo del producto

| Phase | Cierre | Hito |
|---|---|---|
| 1-2 | sesión inicial | Pipeline ingesta + RAG + multi-tenancy RLS + 2 tenants seed |
| 3-4 | sesión inicial | Docs (ARCHITECTURE / DEPLOYMENT / ROADMAP) + chat UI + benchmark |
| 5 | sesión 5 | Producción korio.es + gobernanza activa + HITL email + landing |
| 6 | sesión 5 | Cron escalada HITL (recordatorios 3/7/14 + timeout 21) |
| 7.1 | sesión 5 | Grafo FalkorDB + entity_extractor + UI graph.html |
| 7.2 | sesión 5 | Ingesta multi-canal (Gmail / Drive / Slack file_shared + /korio) |
| 7.3 | sesión 5 | MCP Server (`korio.es/mcp/sse` + 3 tools + auth API key) |
| v0.3.0 | sesiones 6-9 | **6 reglas E3 materializadas**: pipeline ACID, bus pipeline_events, fachada `src/agents/*`, query-time silent conflicts, estado `inconclusive`, policies reutilizables |
| v0.3.4 | sesión 13a | Hardening seguridad pre-demo (7 fixes CRIT/HIGH) |
| v0.3.5-6 | sesiones 13b-c | Multi-canal real verificado + Regla 4 demostrada en producción |
| v0.3.7 | sesión 14 | Cierre implementación + `scripts/demo_snapshot.py` |
| v0.3.8 | sesión 14b | Compliance AI Act + GDPR (Presidio fix, redaction Mistral, Privacy Policy) |
| v0.3.9 | sesión 14c | Fix restore grafo FalkorDB (`CREATE+SET` no inline) |
| v0.3.10-11 | sesiones 15-15b | Vídeo demo grabación inicial + reembed sin frontmatter |
| v0.3.12 | sesión 16 | **Phase 9 errores n8n cerrada**: throttling, panel `/admin/errors`, Slack interactivity HMAC, duplicate→thread |
| v0.3.13 | sesión 17-17b | Evaluación cuantitativa P/R/F1=1.0 (n=12) + fix detector frontmatter YAML |
| v0.3.14 | **sesión 17c (hoy)** | Promoción HITL chunk→doc + fix restore policies + nginx 300s + UI RLS-aware + MCP cita inline + refusal detection |

### Vídeo demo (3 escenas, ≈4 min)

| Escena | Contenido | Estado |
|---|---|---|
| 1 | Gobernanza activa E2E (L3 LOPD vía Slack → HITL email → resolución → RAG actualizado) | ✅ grabado s17c |
| 2 | RLS multi-tenant + multi-canal (Slack `#rrhh` vs `#admin` + Swagger Admin vs Staff + UI cross-tenant García) | ✅ grabado s17c |
| 3 | MCP en Claude Desktop (3 queries: horas semanales, baja IT con silent_conflict, list_pending_conflicts) | ✅ grabado s17c |

---

## Snapshots canónicos

| Snapshot | Estado | Para qué |
|---|---|---|
| `pre_demo_v039` | pre-conflicto (L2 todo `active`, L3 ausente, R3 active vía patch, 3 reviews R6/R7 uniformes pending) | Punto de partida re-grabaciones escena 1 |
| `pre_demo_v040` | post-resolución (L2 todo `superseded`, L3 active + 2 reviews approved + policy `policy_new_wins`) | Estado de referencia "después de" sin re-grabar el flujo |
| `pre_demo_v041` | verificación E2E con código v0.3.14 (snapshot defensivo backup) | Solo backup |

Restore desde VPS:
```bash
ssh korio-vps
cd /root/korio && source .venv/bin/activate
echo y | python3 scripts/demo_snapshot.py restore --name pre_demo_v039
```

---

## Pendiente hasta defensa

| Tarea | Estado | Herramienta |
|---|---|---|
| Slide deck (15 slides) | 🔲 | Claude Projects (fuera de Claude Code) |
| Memoria TFM (negocio + técnico + research entrevistas) | 🔲 | Claude Projects |
| Banco Q&A defensa (20 preguntas) | 🔲 | Claude Projects |
| Ensayo cronometrado | 🔲 | — |
| Edición + cierre vídeo demo | 🔲 | DaVinci / iMovie |

**Plan operativo**: salir de Claude Code, subir repo a Claude Projects, trabajar memoria + slides + Q&A con contexto técnico cargado.

---

## Deuda técnica reconocida (Phase 9 post-TFM)

- Validación semántica LLM en detector ingesta (reducir FP entre docs estilo similar)
- Reintroducir índice vectorial cuando >1000 chunks (HNSW o `ivfflat lists=ceil(sqrt(N))`)
- Chunker excluir frontmatter YAML pre-embedding (parcial v0.3.13)
- OAuth multi-tenant + vault de tokens (diseño en `docs/MULTI-TENANT-INGESTION.md`)
- Guardrails chat: Presidio egress + Lakera/Rebuff ingress + rate limit (`docs/CHAT-PIPELINE-GUARDRAILS.md`)
- Bias audit + DPA formal Mistral + endpoints export/subject-access GDPR
- Reranking cross-encoder vectorial (+20-30% calidad RAG)

---

## Infraestructura producción

```
VPS:         Hetzner CPX32 AMD EPYC-Genoa · 4 vCPU / 8 GB / 160 GB · Frankfurt · €17.53/mes
SSH:         ssh korio-vps   (alias en ~/.ssh/config → 167.233.72.42)
Supabase:    https://pkurvkdmoulfqnngjsjr.supabase.co  (Pro, Frankfurt)
Ollama:      http://167.233.72.42:11434  (nomic-embed-text 768 dims fijo)
FalkorDB:    127.0.0.1:6379 (Redis 8.6.3 + módulo grafo)

URLs públicas:
  https://korio.es                → Landing teaser
  https://korio.es/ui             → App de chat
  https://korio.es/ui/graph.html  → Grafo de conocimiento (admin only)
  https://korio.es/ui/admin-errors.html → Panel errores n8n
  https://korio.es/docs           → Swagger UI
  https://korio.es/mcp/sse        → Servidor MCP
  https://korio.es/legal/privacy.html → Privacy Policy GDPR/LSSI
  https://n8n.korio.es            → Editor n8n (8 workflows activos)
```

### Workflows n8n en producción (8)

1. HITL emails (review tokens firmados Basic Auth)
2. Cron escalada diario 09:00 Madrid (recordatorios + timeout)
3. Pipeline event bus (visualización en vivo `pipeline_events`)
4. Gmail → /upload Delos multi-space (labels `korio/rrhh`, `korio/medico`, `korio/legal`, `korio/admin`)
5. Drive → /upload Delos multi-space (subcarpetas `input/{rrhh,medico,legal,admin}`)
6. Slack `/korio` → /search multi-canal (`channel_id → service user_id`)
7. Slack file_shared → /upload multi-space (duplicate → DM thread)
8. Gestión errores n8n (Error Trigger → Supabase `n8n_errors` + Slack DM con throttling + interactivity button)

### Tenants + users con IDs

```
Clínica Delos:
  tenant a0000000-0000-0000-0000-000000000001
  spaces:
    RRHH    a1000000-0000-0000-0000-000000000001
    Médico  a1000000-0000-0000-0000-000000000002
    Legal   a1000000-0000-0000-0000-000000000003
    Admin   a1000000-0000-0000-0000-000000000004
  users:
    admin   a1000000-0000-0000-0000-000000000001  (RRHH+Médico+Legal+Admin)
    doctor  a2000000-0000-0000-0000-000000000001  (RRHH+Médico)
    staff   a3000000-0000-0000-0000-000000000001  (solo RRHH)

Despacho García:
  tenant b0000000-0000-0000-0000-000000000002
  users:
    admin   b1000000-0000-0000-0000-000000000002  (Casos+Fiscal)
    lawyer  b2000000-0000-0000-0000-000000000002  (solo Casos)
```

---

## Comandos de arranque

```bash
# 1) SSH al VPS
ssh korio-vps

# 2) Activar venv local (en Mac)
cd "/Users/berto/Claude Code/korio"
source .venv/bin/activate

# 3) Restore canónico
ssh korio-vps "cd /root/korio && source .venv/bin/activate && \
  echo y | python3 scripts/demo_snapshot.py restore --name pre_demo_v039"

# 4) Operaciones VPS frecuentes
systemctl restart korio-api
journalctl -u korio-api -f
docker logs korio-falkordb --tail 50
curl https://korio.es/health

# 5) Save snapshot tras una sesión limpia
ssh korio-vps "cd /root/korio && source .venv/bin/activate && \
  python3 scripts/demo_snapshot.py save --name pre_demo_v0XX"
```

---

## Convenciones críticas (BLOCKING — nunca saltar)

1. **RLS early binding**: `db.py` obtiene `space_ids` ANTES del vector search → filtra `document_ids` → vector search restringe a esos docs. Doble capa: app + policies RLS Supabase.
2. **Embedding inmutable**: `nomic-embed-text` 768 dims. Cambiarlo requiere re-ingestar todos los docs.
3. **n8n korio.es ≠ lagalga.es**: el `n8n-mcp` del entorno apunta a lagalga. Para Korio usar `N8N_KORIO_API_KEY` + `N8N_KORIO_BASE_URL` del `.env` del VPS contra la API REST.
4. **HITL webhook Basic Auth**: cualquier llamada backend debe ir con `HITL_WEBHOOK_USER` + `HITL_WEBHOOK_PASS`.
5. **Snapshots policies bigint PK**: `scripts/demo_snapshot.py` usa fallback `int PK` para `policies` (no UUID). Fix v0.3.14.
6. **Idioma**: comentarios y docs en **español**, código (variables/funciones/clases) en **inglés**.
7. **Commits**: `Tipo(scope): título en español` con co-author Claude.

---

## Decisiones de diseño activas

| Decisión | Variable / Lugar | Por qué |
|---|---|---|
| Chunk-level governance + promoción doc-level | `KORIO_DOC_REPLACEMENT_MIN_APPROVALS=2` | Respeta E3 para patches, sube a doc-level con evidencia HITL repetida (Regla 4) |
| Refusal detection vacía sources | `src/search.py` patterns | Si LLM declina, no listar fuentes ruido |
| Filtro útil para presentación | `KORIO_USEFUL_SIM_THRESHOLD=0.55` | Oculta fuentes con sim marginal de la presentación (siguen alimentando al LLM) |
| Banner conflict admin-only | `ui/js/main.js` rol check | Gobernanza es vista administrativa |
| Threshold disputed banner | `KORIO_DISPUTED_BANNER_MIN_SIM=0.7` | Disputed con sim baja es ruido, no contradicción real |
| Threshold silent_conflict | `KORIO_QUERY_TIME_CONFLICT_THRESHOLD=0.82` | 0.80 disparaba R3↔R4 benigno; 0.82 conserva R3↔R5 (relevante) |
| nginx proxy timeout | 300s | Ingesta con extracción Mistral por chunk excede 120s |
| PII redaction whitelist | `_PII_TYPES` en `preprocessor.py` y `llm_client.py` | ORG/LOC/MISC NO son PII; Presidio default garbla texto |

---

## Documentación clave

| Archivo | Contenido |
|---|---|
| `CLAUDE.md` | Memoria de sesiones (bloque por sesión al final) |
| `README.md` | Visión general + quickstart |
| `CHANGELOG.md` | Keep a Changelog versionado SemVer |
| `docs/ROADMAP.md` | Plan + hitos + backlog Phase 9 |
| `docs/ARCHITECTURE.md` | Diagrama, modelo de datos, RLS |
| `docs/DEPLOYMENT.md` | Setup VPS desde cero |
| `docs/AGENTIC-INGESTION.md` | Las 6 reglas del E3 + comparativa microservicios |
| `docs/MCP-SERVER.md` | Phase 7.3 — Korio como servidor MCP HTTP+SSE |
| `docs/MULTI-TENANT-INGESTION.md` | Diseño Phase 8 OAuth multi-tenant |
| `docs/CHAT-PIPELINE-GUARDRAILS.md` | Diseño Phase 8 guardrails chat |
| `docs/PHASE-10-MULTIMODAL-INGESTION.md` | Diseño Phase 10 email body/Slack/audio |
| `docs/COMPLIANCE-AI-ACT-GDPR.md` | Capítulo §6 memoria TFM |
| `docs/AUDIT-2026-06-14.md` | Auditoría sesión 13a — 21 hallazgos catalogados |
| `docs/SESSION-STARTER.md` | **este archivo** |

---

## Páginas Notion del proyecto

| Página | URL | Uso |
|---|---|---|
| Estado técnico — Síntesis TFM | https://app.notion.com/p/3792e8533b4481719aeddd9d2eb94b8a | Fuente de verdad técnica para Claude Chat |
| Roadmap & Tareas — Korio TFM | https://app.notion.com/p/3792e8533b44814b8fa9cdc8de668533 | Checklist phases + hitos por sesión |
| Historial de Desarrollo (DB) | https://app.notion.com/p/3782e8533b4480a98142c8fedb52c9e1 | Entradas Problema/Resolución/Bug/Éxito/Aprendizaje |
| Company Brain proceso completo | https://app.notion.com/p/3782e8533b448012bf1ecd77aee3c9c6 | Descripción funcional |
| Stack, costes e infraestructura | https://app.notion.com/p/3782e8533b4481f6a98ed9b46877d170 | Detalle costes (CPX32 €17.53/mes) |

---

## Checklist de cierre de sesión

Cuando el usuario diga "cierra sesión" / "actualiza todo":

1. **Notion · Roadmap & Tareas**: añadir sección `## ✅ Sesión <N> (<fecha>)` al final
2. **Notion · Historial de Desarrollo**: una entrada por hallazgo (causa raíz + fix + verificación)
3. **Notion · Estado técnico**: bloque `## Hitos sesión <N> (<fecha>, vY.Y.Y)` solo si hay cambios arquitectónicos
4. **Notion · Stack y costes**: solo si cambian costes o aparecen servicios facturables
5. **Repo · `docs/ROADMAP.md`**: marcar `[x]` lo cerrado, mover Pendientes
6. **Repo · `docs/SESSION-STARTER.md`** (este): refrescar versión + última sesión + snapshots
7. **Repo · `CLAUDE.md`**: añadir bloque `**Sesión <N> (<fecha>)**` al final
8. **Repo · `CHANGELOG.md`**: entrada `[vX.Y.Z] — YYYY-MM-DD · sesión <N>` con Added/Changed/Fixed/Security/Operational
9. **Repo · `MEMORY.md` auto-memory**: añadir/actualizar `feedback_*` / `project_*` / `reference_*` solo si aplica a futuras sesiones
10. **Git**: commits atómicos + push a `main`

Orden: GitHub → CLAUDE.md → SESSION-STARTER → CHANGELOG → Notion (4 páginas) → MEMORY auto si hubo aprendizajes.

---

## Reglas globales

1. Responder siempre en **español**
2. RLS verificado desde día 1 — nunca saltarlo
3. Modelo embeddings `nomic-embed-text` **768 dims** — nunca cambiar
4. No agregar dependencias sin consultar
5. Documentar decisiones en Notion después de cada sesión
6. Commits atómicos con mensaje claro
7. n8n korio.es NO lagalga.es
8. Webhook HITL Basic Auth obligatorio

---

*Actualizado: 23 junio 2026 (sesión 17c) — v0.3.14. Implementación cerrada. Vídeo demo grabado. Próximo: contenido TFM en Claude Projects.*
