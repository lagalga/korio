-- Migration 004: Conflict Reviews — Gobernanza activa
-- Tabla para registrar conflictos detectados durante la ingesta y gestionar HITL.
-- Permite resolución automática (por fecha/autoridad) y revisión humana (email HITL).
--
-- Creado: 2026-06-09

-- ============================================================================
-- TABLA conflict_reviews
-- ============================================================================

CREATE TABLE IF NOT EXISTS conflict_reviews (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  space_id              UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,

  -- Documento nuevo (recién ingestado)
  new_document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  new_chunk_id          BIGINT NOT NULL REFERENCES embeddings(id) ON DELETE CASCADE,
  new_doc_authority     INT,
  new_doc_version_ts    TIMESTAMPTZ,

  -- Documento existente (con el que hay conflicto)
  existing_document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  existing_chunk_id     BIGINT NOT NULL REFERENCES embeddings(id) ON DELETE CASCADE,
  existing_doc_authority INT,
  existing_doc_version_ts TIMESTAMPTZ,
  existing_filename     TEXT,

  -- Similitud coseno detectada (0.85–1.0 indica conflicto)
  similarity            FLOAT NOT NULL,

  -- Resolución
  -- pending:             requiere revisión humana (HITL)
  -- auto_new_wins:       nuevo documento supersede al existente (por fecha o autoridad)
  -- auto_existing_wins:  documento existente más autoritativo, nuevo queda superseded
  -- approved_new:        revisor humano aprobó que el nuevo prevalece
  -- approved_existing:   revisor humano mantuvo el existente
  -- kept_both:           revisor humano decidió mantener ambos
  resolution            TEXT DEFAULT 'pending' CHECK (
    resolution IN (
      'pending',
      'auto_new_wins',
      'auto_existing_wins',
      'approved_new',
      'approved_existing',
      'kept_both'
    )
  ),
  resolution_reason     TEXT,

  -- Token firmado para links de email HITL (approve/reject/keep_both)
  review_token          TEXT UNIQUE,

  -- Metadatos
  reviewed_at           TIMESTAMPTZ,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conflict_reviews_tenant  ON conflict_reviews(tenant_id);
CREATE INDEX idx_conflict_reviews_space   ON conflict_reviews(space_id);
CREATE INDEX idx_conflict_reviews_token   ON conflict_reviews(review_token);
CREATE INDEX idx_conflict_reviews_pending ON conflict_reviews(resolution) WHERE resolution = 'pending';


-- ============================================================================
-- FUNCIÓN find_conflicting_chunks
-- ============================================================================
-- Busca chunks existentes en el mismo espacio con similitud coseno alta
-- respecto al chunk nuevo. Excluye el documento recién ingestado y los
-- chunks ya superseded/disputados.
--
-- Parámetros:
--   query_embedding:     Vector del chunk nuevo (768 dims)
--   space_uuid:          Espacio donde buscar
--   exclude_doc_id:      Documento nuevo (excluir del resultado)
--   similarity_threshold: Umbral mínimo para considerar conflicto (default 0.85)
--   max_results:         Máximo de resultados por chunk (default 10)

CREATE OR REPLACE FUNCTION find_conflicting_chunks(
  query_embedding       vector(768),
  space_uuid            UUID,
  exclude_doc_id        UUID,
  similarity_threshold  FLOAT DEFAULT 0.85,
  max_results           INT DEFAULT 10
)
RETURNS TABLE (
  chunk_id              BIGINT,
  document_id           UUID,
  chunk_text            TEXT,
  similarity            FLOAT,
  authority_weight      INT,
  version_ts            TIMESTAMPTZ,
  filename              TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER  -- Puede leer aunque RLS esté activo (función admin)
AS $$
BEGIN
  RETURN QUERY
  SELECT
    e.id                                    AS chunk_id,
    e.document_id,
    e.chunk_text,
    1 - (e.vector <=> query_embedding)      AS similarity,
    d.authority_weight,
    d.version_ts,
    d.filename
  FROM embeddings e
  JOIN documents d ON e.document_id = d.id
  WHERE
    d.space_id = space_uuid
    AND e.document_id != exclude_doc_id
    AND e.chunk_status = 'active'
    AND d.status = 'active'
    AND 1 - (e.vector <=> query_embedding) >= similarity_threshold
  ORDER BY similarity DESC
  LIMIT max_results;
END;
$$;


-- ============================================================================
-- NOTAS
-- ============================================================================
/*
FLUJO DE GOBERNANZA:

1. Se ingesta un nuevo documento → se generan sus chunks + embeddings
2. conflict_detector.py llama a find_conflicting_chunks() para cada nuevo chunk
3. Por cada conflicto detectado:
   a. Si new_version_ts - existing_version_ts > 30 días → auto_new_wins
      - existing chunk.chunk_status → 'superseded'
      - conflict_review.resolution → 'auto_new_wins'
   b. Si new_authority - existing_authority >= 3 → auto_new_wins
      - mismo efecto que (a)
   c. Si existing_authority - new_authority >= 3 → auto_existing_wins
      - new chunk.chunk_status → 'superseded'
      - conflict_review.resolution → 'auto_existing_wins'
   d. En otro caso → pending (HITL)
      - existing chunk.chunk_status → 'disputed'
      - conflict_review.resolution → 'pending'
      - Se envía email via n8n con links de acción

4. El revisor hace clic en el link de email → POST /review/{id}?action=…&token=…
5. Korio resuelve: actualiza chunk_statuses + conflict_review.resolution
*/
