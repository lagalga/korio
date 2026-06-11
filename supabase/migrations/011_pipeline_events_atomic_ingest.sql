-- Migración 011: bus de eventos del pipeline + RPC atómico de ingesta
--
-- Esta migración responde a dos objetivos relacionados:
--
-- (a) Transaccionalidad ACID en la ingesta — el feedback del profesor en el
--     Entregable 4 del TFM: si la llamada a la API de Gemini fallaba tras
--     insertar la metadata, el sistema quedaba en estado inconsistente.
--     Aquí movemos TODAS las escrituras (documents + embeddings + evento
--     DOCUMENT_INGESTED) a una sola función PL/pgSQL: como las funciones
--     PL/pgSQL ejecutan toda su lógica en una sola transacción implícita,
--     cualquier excepción revierte todo. Las llamadas externas (Ollama,
--     Mistral) se hacen ANTES de invocar la función, así no atan
--     conexiones de la pool y tampoco pueden corromper el estado.
--
-- (b) Observabilidad agéntica — `pipeline_events` es el bus que captura
--     cada transición del pipeline multi-agente (Ingestor, Detector,
--     Arbitrator, Supervisor, Curator). Cada evento lleva un `operation_id`
--     UUID que correlaciona toda la cadena de un ciclo (ingesta → detección
--     → resolución HITL → cierre). Reconstruir un ciclo completo se hace
--     con un solo SELECT por operation_id.
--
-- Notas:
--  - La tabla audit_log existente sigue siendo el log de QUERIES del RAG
--    (otra preocupación). NO se mezcla con pipeline_events.
--  - Las nuevas columnas son aditivas: el código existente sigue funcionando.

-- ─── pipeline_events ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pipeline_events (
  id            BIGSERIAL PRIMARY KEY,
  operation_id  UUID NOT NULL,
  event_type    TEXT NOT NULL CHECK (event_type IN (
    'DOCUMENT_INGESTED',     -- Ingestor → Detector: doc + chunks listos
    'DOCUMENT_CLEARED',      -- Detector → Curator: sin conflictos
    'CONFLICT_DETECTED',     -- Detector → Arbitrator: hay conflicto
    'RESOLUTION_PROPOSED',   -- Arbitrator → Curator (auto) o Supervisor (HITL)
    'USER_DECISION',         -- Supervisor → Curator: decisión humana recibida
    'CORPUS_UPDATED',        -- Curator: cierre de ciclo, corpus consistente
    'GRAPH_SYNCED',          -- Sync FalkorDB ok post-commit
    'GRAPH_SYNC_FAILED',     -- Sync FalkorDB fallo → encolado para retry
    'INGEST_FAILED'          -- Cualquier fallo capturado del pipeline
  )),
  source_agent  TEXT NOT NULL CHECK (source_agent IN (
    'ingestor', 'detector', 'arbitrator', 'supervisor', 'curator', 'system'
  )),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  document_id   UUID REFERENCES documents(id) ON DELETE SET NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_operation
  ON pipeline_events (operation_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_tenant_created
  ON pipeline_events (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_type
  ON pipeline_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_document
  ON pipeline_events (document_id)
  WHERE document_id IS NOT NULL;

COMMENT ON TABLE pipeline_events IS
  'Bus de eventos del pipeline multi-agente. operation_id correlaciona todos los eventos de un ciclo (ingesta→detección→resolución→cierre).';
COMMENT ON COLUMN pipeline_events.operation_id IS
  'UUID que enlaza todos los eventos del mismo ciclo. Generado por el orquestador (Ingestor) y propagado a Detector/Arbitrator/Supervisor/Curator.';
COMMENT ON COLUMN pipeline_events.source_agent IS
  'Rol agéntico emisor. Se mantiene incluso si los agentes viven como clases dentro de un mismo proceso Python.';

-- ─── ingest_document_atomic — RPC transaccional ─────────────────────────────
--
-- Toda la escritura de un nuevo documento (metadata + chunks + evento de
-- INGESTED) sucede en una sola transacción implícita PL/pgSQL. Si cualquier
-- INSERT falla, todo se revierte y el corpus queda como antes.
--
-- Las llamadas a APIs externas (Ollama para embeddings, Mistral para
-- extracción de entidades) se hacen en Python ANTES de invocar esta función:
-- así no atan conexiones de la pool ni pueden corromper el estado.
--
-- Devuelve un JSONB con { document_id, chunk_ids[], chunk_count } para que
-- los siguientes pasos del pipeline (grafo, detector de conflictos) puedan
-- operar.

CREATE OR REPLACE FUNCTION ingest_document_atomic(
  p_doc          JSONB,   -- { id, tenant_id, space_id, filename, content_hash,
                          --   source_type, authority_weight, version_ts,
                          --   status, source_metadata }
  p_chunks       JSONB,   -- array [{ chunk_index, chunk_text, vector }, ...]
  p_operation_id UUID,
  p_source_agent TEXT DEFAULT 'ingestor'
) RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
  v_document_id UUID;
  v_chunk_ids   BIGINT[];
  v_chunk_id    BIGINT;
  v_chunk       JSONB;
BEGIN
  -- 1) INSERT documents — si content_hash duplicado, fallará el UNIQUE y se
  --    revierte automáticamente. La deduplicación se comprueba en Python
  --    ANTES de invocar este RPC para no consumir cuota de transacciones.
  INSERT INTO documents (
    id, tenant_id, space_id, filename, content_hash, source_type,
    authority_weight, version_ts, status, source_metadata
  ) VALUES (
    COALESCE((p_doc->>'id')::UUID, gen_random_uuid()),
    (p_doc->>'tenant_id')::UUID,
    (p_doc->>'space_id')::UUID,
    p_doc->>'filename',
    p_doc->>'content_hash',
    p_doc->>'source_type',
    COALESCE((p_doc->>'authority_weight')::INT, 5),
    COALESCE((p_doc->>'version_ts')::TIMESTAMPTZ, NOW()),
    COALESCE(p_doc->>'status', 'active'),
    p_doc->'source_metadata'
  )
  RETURNING id INTO v_document_id;

  -- 2) INSERT embeddings — todos los chunks o ninguno
  v_chunk_ids := ARRAY[]::BIGINT[];
  FOR v_chunk IN SELECT jsonb_array_elements(p_chunks)
  LOOP
    INSERT INTO embeddings (
      document_id, chunk_index, chunk_text, vector, chunk_status
    ) VALUES (
      v_document_id,
      (v_chunk->>'chunk_index')::INT,
      v_chunk->>'chunk_text',
      (v_chunk->>'vector')::vector,
      COALESCE(v_chunk->>'chunk_status', 'active')
    )
    RETURNING id INTO v_chunk_id;
    v_chunk_ids := array_append(v_chunk_ids, v_chunk_id);
  END LOOP;

  -- 3) Evento DOCUMENT_INGESTED dentro de la misma transacción → si falla
  --    algo aquí, también se revierte todo lo anterior.
  INSERT INTO pipeline_events (
    operation_id, event_type, source_agent, tenant_id, document_id, payload
  ) VALUES (
    p_operation_id,
    'DOCUMENT_INGESTED',
    p_source_agent,
    (p_doc->>'tenant_id')::UUID,
    v_document_id,
    jsonb_build_object(
      'filename',         p_doc->>'filename',
      'chunk_count',      jsonb_array_length(p_chunks),
      'authority_weight', COALESCE((p_doc->>'authority_weight')::INT, 5),
      'source_type',      p_doc->>'source_type'
    )
  );

  RETURN jsonb_build_object(
    'document_id', v_document_id,
    'chunk_ids',   to_jsonb(v_chunk_ids),
    'chunk_count', jsonb_array_length(p_chunks)
  );
END;
$$;

COMMENT ON FUNCTION ingest_document_atomic(JSONB, JSONB, UUID, TEXT) IS
  'Inserta documento + embeddings + evento DOCUMENT_INGESTED en una sola transacción PL/pgSQL. Si cualquier paso falla, todo se revierte. Las llamadas externas (Ollama, Mistral) se hacen ANTES de invocar esta función.';

-- ─── graph_sync_queue — sync FalkorDB diferido con retry ────────────────────
--
-- El sync con FalkorDB es post-commit (FalkorDB no participa en la transacción
-- Postgres). Si falla, encolamos el job para que un worker lo reintente.
-- Esto preserva la consistencia: el corpus Postgres siempre está coherente;
-- el grafo eventualmente alcanza el mismo estado.

CREATE TABLE IF NOT EXISTS graph_sync_queue (
  id            BIGSERIAL PRIMARY KEY,
  operation_id  UUID NOT NULL,
  document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  payload       JSONB NOT NULL,        -- { chunk_ids, filename, version_ts, ... }
  attempts      INT NOT NULL DEFAULT 0,
  last_error    TEXT,
  last_attempt_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_graph_sync_queue_pending
  ON graph_sync_queue (created_at)
  WHERE completed_at IS NULL;

COMMENT ON TABLE graph_sync_queue IS
  'Cola de sync con FalkorDB. El sync es post-commit; si falla, se reintenta vía n8n worker.';
