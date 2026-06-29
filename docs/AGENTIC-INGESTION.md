# Ingesta agéntica y transaccional — sesión 6

> Capítulo de la memoria TFM: "Korio v0.2 — pipeline multi-agente con
> transaccionalidad ACID en respuesta al feedback del Entregable 4".

## Origen del cambio

En la evaluación del **Entregable 4** del módulo *Sistema Multiagente de
Validación de RAG* (Nuclio, Máster IA Business & Innovation), el profesor
señaló como siguiente paso profesional:

> *"Investiga la transaccionalidad SQL en el MCP custom. Si la llamada a la
> API de Gemini falla tras haber insertado la metadata, podrías tener
> inconsistencias. Envolver la inserción y el embedding en una transacción
> única te daría el 100% de fiabilidad ante fallos de red."*

Al revisar Korio en la sesión 6 se confirmó que **tenía exactamente el mismo
problema**. El flujo original de `ingest_document()` ejecutaba siete pasos:

```
1. supabase.table("documents").insert(doc)          ← escritura
2. ollama.embed(chunks)                             ← red externa (~10–30 s)
3. supabase.table("embeddings").insert(chunks)      ← escritura
4. mistral.extract_entities(chunks)                 ← red externa (~5 s)
5. graph_client.sync(claims)                        ← red externa (FalkorDB)
6. conflict_detector.detect(...)                    ← más llamadas
7. audit_log insert                                 ← cierre de traza
```

Si cualquiera de los pasos 2-7 fallaba, el corpus quedaba **parcialmente
escrito**: documento sin embeddings, o sin grafo, o sin audit. Ese es el
escenario contra el que advertía el profesor.

## Restricción específica de Korio

A diferencia de un sistema con acceso directo a Postgres (psycopg2 + `BEGIN/
COMMIT`), Korio consume Supabase vía **PostgREST**: cada llamada HTTP es
*stateless*, no se puede enlazar varias escrituras dentro de una misma
transacción cliente. Tres opciones:

| Patrón | Cómo | Pros | Contras |
|---|---|---|---|
| **A · RPC PL/pgSQL atómico** | Función Postgres que hace todos los `INSERT` en su transacción implícita | Mantiene PostgREST. Una sola llamada de red. ACID real | Hay que mover la lógica de escritura a SQL |
| B · psycopg2 directo | Saltarse PostgREST con conexión directa + `BEGIN/COMMIT/ROLLBACK` manual | Más cerca del código Python actual | Pool nuevo, gestión de secretos, dependencia más |
| C · Saga + compensación | Cada paso registra su intento; rollback ejecuta inversos | Funciona en sistemas distribuidos | Sobreingeniería para este alcance |

Elegimos **A**: una sola RPC `ingest_document_atomic(p_doc jsonb, p_chunks
jsonb, p_operation_id uuid, p_source_agent text)` que ejecuta los `INSERT`
de `documents`, `embeddings` y el evento `DOCUMENT_INGESTED` en `pipeline_events`
dentro de una sola transacción PL/pgSQL. Si cualquier paso falla, todo se
revierte automáticamente.

## Arquitectura agéntica como roles lógicos en un proceso

El **Entregable 3-4** diseñaba 5 agentes (Ingestor, Detector, Árbitro,
Supervisor HITL, Curador) comunicándose por mensajes JSON tipados con
`operation_id` compartido. La implementación del Entregable 4 los montaba como
**nodos LangFlow**, cada uno con su propio MCP y su salto HTTP.

En Korio se replica el patrón conceptual pero **manteniendo los agentes como
clases dentro del mismo proceso FastAPI**. La razón es tridimensional:

| Criterio | Microservicios (E4) | Roles lógicos (Korio v0.2) |
|---|---|---|
| Latencia camino crítico | +1.5–3 s extra (5 saltos webhook × 200–500 ms) | 0 ms — todo en el mismo proceso |
| Transaccionalidad SQL | Imposible (cada nodo es una llamada HTTP separada) | Trivial — RPC en el mismo proceso |
| Observabilidad | Editor LangFlow con flow vivo, replay visual | **Bus de eventos** + dashboard n8n consumiendo eventos |
| Resiliencia ante fallo | Re-run del flow | Excepción Python + rollback ACID + evento `INGEST_FAILED` con phase |
| Demostrable en defensa | Diagrama estático LangFlow | n8n editor + `SELECT * FROM pipeline_events WHERE operation_id = …` |

El bus de eventos es el puente que combina lo mejor de los dos enfoques:

```
src/agents/events.py:
  emit(EventType.X, source_agent=Agent.Y, tenant_id=…, operation_id=…)
   ├─► 1) INSERT en pipeline_events  (audit persistente)
   └─► 2) POST best-effort a KORIO_EVENT_WEBHOOK_URL  (n8n observability)
```

`pipeline_events` es la fuente de verdad — cada ciclo se reconstruye con un
solo `SELECT … WHERE operation_id = ? ORDER BY created_at`. El webhook a n8n
es fire-and-forget con timeout 500 ms: si n8n cae, Korio sigue funcionando.

## Comparativa con el sistema E3/E4 (anexo memoria TFM)

| Aspecto | Diseño E3 | Implementación E4 (LangFlow) | Korio v0.2 |
|---|---|---|---|
| Plataforma | Conceptual | LangFlow Desktop | FastAPI + Supabase + FalkorDB en producción |
| Comunicación | JSON tipado con `operation_id` | Mensajes Langflow entre nodos | `pipeline_events` con `operation_id` UUID |
| Transaccionalidad | Mencionada como objetivo | No implementada (cada nodo es un INSERT separado) | **ACID real vía RPC PL/pgSQL** |
| HITL | Email bidireccional | Email + webhook FastAPI separado | Email + webhook FastAPI + cron de escalada |
| Curador | Un único agente | Dos nodos (auto + HITL) | Lógica unificada en `conflict_detector` + cierre con evento `CORPUS_UPDATED` |
| Monitor timeouts | Mecanismo interno del Supervisor | Flow Langflow separado disparado por cron externo | Workflow n8n Schedule Trigger 09:00 Madrid |
| Multi-tenancy | No especificada | Single-tenant | **Multi-tenant real con RLS Supabase + early binding** |
| Grafo de conocimiento | No incluido | No incluido | FalkorDB con claims y entidades, sync post-commit |
| Demo en producción | — | Local en Desktop | `korio.es` + `n8n.korio.es` + servidor MCP |

## Diseño detallado

### Migración 011

```sql
CREATE TABLE pipeline_events (
  id            BIGSERIAL PRIMARY KEY,
  operation_id  UUID NOT NULL,
  event_type    TEXT NOT NULL CHECK (event_type IN (…9 tipos…)),
  source_agent  TEXT NOT NULL CHECK (source_agent IN (
    'ingestor','detector','arbitrator','supervisor','curator','system'
  )),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_id   UUID REFERENCES documents(id) ON DELETE SET NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE graph_sync_queue (
  -- cola de retry para sync con FalkorDB post-commit
  …
);

CREATE FUNCTION ingest_document_atomic(
  p_doc JSONB, p_chunks JSONB, p_operation_id UUID, p_source_agent TEXT
) RETURNS JSONB LANGUAGE plpgsql AS $$ … $$;
```

### Fases del nuevo pipeline `ingest_document()`

```
operation_id ← new_operation_id()         # UUID que correlaciona todo el ciclo

FASE 1 — IO externa (fuera de cualquier transacción SQL)
  1.1 preprocesar (MarkItDown + Presidio)
  1.2 chunking (LangChain RecursiveTextSplitter)
  1.3 embeddings (Ollama nomic-embed-text)
  └─ si falla: emit INGEST_FAILED(phase=preprocess|chunking|embeddings)

FASE 2 — Dedupe (SELECT, no escritura)
  └─ si content_hash existe: raise DuplicateDocumentError

FASE 3 — Escritura ACID (1 sola llamada de red)
  rpc('ingest_document_atomic', { p_doc, p_chunks, p_operation_id, p_source_agent })
  ├─ INSERT documents
  ├─ INSERT embeddings × N
  └─ INSERT pipeline_events (DOCUMENT_INGESTED)
  Si cualquiera falla → TODO se revierte (transacción implícita PL/pgSQL)

FASE 4 — Post-commit: grafo de conocimiento (best-effort + cola)
  intenta sync con FalkorDB
  ├─ si OK:  emit GRAPH_SYNCED
  └─ si KO:  INSERT graph_sync_queue + emit GRAPH_SYNC_FAILED
              (un worker n8n reintenta cada 5 min)

FASE 5 — Post-commit: detección de conflictos
  conflict_detector.detect(...)
  ├─ si hay: emit CONFLICT_DETECTED (Detector → Arbitrator)
  └─ si no:  emit DOCUMENT_CLEARED  (Detector → Curator)

CIERRE — emit CORPUS_UPDATED (Curator)
```

## Tests automáticos de la promesa ACID

`tests/test_atomic_ingest.py` con 3 tests:

1. **`test_ingesta_feliz_path_genera_eventos_y_persiste`** — happy path
   completo. Documento y chunks persisten. Eventos `DOCUMENT_INGESTED` +
   `CORPUS_UPDATED` aparecen en `pipeline_events` con el mismo `operation_id`.
2. **`test_ingesta_duplicada_no_persiste_segunda_copia`** — verificación
   de deduplicación previa al RPC.
3. **`test_rpc_atomico_rollback_si_falla_mid_transaction`** — fuerza un
   fallo a mitad enviando un chunk con vector de dimensión incorrecta. Tras
   la excepción del RPC: `documents` no tiene el row, `embeddings` no tiene
   chunks del doc, `pipeline_events` no tiene `DOCUMENT_INGESTED`. **Rollback
   demostrado**.

Salida real:

```
tests/test_atomic_ingest.py::test_ingesta_feliz_path_genera_eventos_y_persiste     PASSED
tests/test_atomic_ingest.py::test_ingesta_duplicada_no_persiste_segunda_copia      PASSED
tests/test_atomic_ingest.py::test_rpc_atomico_rollback_si_falla_mid_transaction    PASSED
======================== 3 passed, 2 warnings in 7.26s ========================
```

## Lo que viene en sesiones siguientes (Phase 8 candidatos)

1. **Detección de conflictos en query-time** — cuando `/search` recupera ≥2
   chunks con similitud >0.85 entre sí de documents distintos, disparar el
   detector retroactivo. Cubre el escenario "Caso extremo" del Entregable 4
   donde dos docs ya activos quedaban en silencio si la similitud entre ellos
   nunca pasaba por el detector de ingesta. **6–8 h**.
2. **Estado `inconclusive`** terminal post-timeout — más conservador que
   `kept_both`. Excluye del RAG hasta intervención manual. **2 h**.
3. **Políticas reutilizables** (`policies` tabla) — cada decisión HITL del
   admin se persiste como política reutilizable que el Arbitrator aplica
   antes de razonar. Inspirado directamente en el E3. **4–6 h**.
4. **Reorganización en `src/agents/{ingestor,detector,arbitrator,supervisor,curator}.py`**
   — refactor cosmético para que el código refleje 1:1 los roles del diseño
   E3. La lógica no cambia; solo se reordena. **2–3 h**.
5. **Workflow n8n `korio:event-bus`** consumiendo los webhooks de `emit()`
   para visualización en vivo durante la defensa. **1–2 h**.

## Cumplimiento de las 6 reglas del Entregable 3 (Korio v0.3.0)

El Entregable 3 enumera 6 "leyes físicas y reglas del entorno" que el sistema
multiagente debe respetar. La siguiente tabla mapea cada una a su mecanismo
en Korio en producción:

| Regla del E3 | Mecanismo en Korio (v0.3.0) | Evidencia |
|---|---|---|
| **R1 — Estado único por documento** (entrada / en_revisión / activo / archivado / no_concluyente) | Korio diferencia estado a nivel **chunk** (más granular): `active` / `superseded` / `disputed` / `inconclusive`. El documento agregado tiene `active` / `archived` / `superseded`. Combinado cubre los 5 estados del E3 | `embeddings.chunk_status` (migración 013), `documents.status` |
| **R2 — Cuarentena de fragmentos en conflicto** | Chunks en `disputed` y `inconclusive` se **excluyen del RAG** automáticamente | RPC `search_with_disputed` filtra; sesión 9 añade `inconclusive` |
| **R3 — Inmutabilidad del log de auditoría** | `audit_log` (queries) y `pipeline_events` (transiciones agénticas) son **append-only por diseño** — solo se hacen INSERT, nunca UPDATE ni DELETE | `pipeline_events` (sesión 6) reconstruye cualquier ciclo con `SELECT … WHERE operation_id = ?` |
| **R4 — Prevalencia de políticas sobre reglas base** | Tabla `policies` con `subject_pattern` + `decision`. El Detector llama `find_applicable_policy()` **antes** de `_decide_resolution`. Si match → decisión policy directa, sin fecha ni autoridad. **Nuevo v0.3.16:** paso 0 previo con validación semántica LLM (`is_chunk_contradiction`) filtra falsos positivos antes de evaluar policies | `src/policies.py` (sesión 9), `src/conflict_detector.py` paso 0 (sesión 19) |
| **R5 — Reactivación manual obligatoria** | Tras `ESCALATION_TIMEOUT_DAYS` sin respuesta HITL, `_apply_timeout` marca chunks como `inconclusive` (no `active`). Quedan excluidos del RAG hasta que un admin los reactive manualmente | `src/escalation.py` (sesión 9), test `test_timeout_pasa_chunks_a_inconclusive` |
| **R6 — Trazabilidad de toda resolución** | Cada decisión (auto, policy, HITL, timeout) emite un evento con `operation_id` que se persiste en `pipeline_events` y se difunde por webhook a `n8n.korio.es`. `times_applied` por policy mide cuántas intervenciones humanas se ahorraron | Sesión 6 + 7, workflow `Korio · Pipeline event bus` |

**De las 6 reglas, las 6 están materializadas en producción.**

## Mensaje para la memoria TFM

> Korio v0.3.0 cierra explícitamente:
> - el **feedback del profesor en el Entregable 4** sobre transaccionalidad SQL
>   (sesión 6 — RPC PL/pgSQL atómico con test de rollback);
> - el **"Caso extremo"** que el propio Entregable 4 dejaba como línea futura
>   en su §4 — detección de conflictos silenciosos en query-time
>   (sesión 8 — RPC `detect_silent_conflicts_among_chunks` + aviso al usuario);
> - las **6 reglas del Entregable 3** en producción, incluida la regla 4
>   (prevalencia de políticas sobre reglas base, con `times_applied` como
>   métrica de aprendizaje del sistema) y la regla 5 (reactivación manual
>   obligatoria tras timeout, con estado terminal `inconclusive`).
>
> El patrón "agentes como roles lógicos en un proceso con bus de eventos"
> mantiene la latencia del camino crítico (sin saltos de red entre nodos)
> y, sobre todo, **hace posible la transaccionalidad ACID que era imposible
> en LangFlow** (allí cada nodo era un microservicio con su propio canal de
> escritura). La observabilidad equivalente al editor LangFlow se obtiene
> consumiendo `pipeline_events` desde un workflow n8n que se enseña en vivo
> durante la defensa.
