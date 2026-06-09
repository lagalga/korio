-- Migración 005: Búsqueda que incluye chunks 'disputed' con aviso de conflicto
--
-- Según el diseño de gobernanza:
--   "Cuando una consulta recupera chunks en estado 'en_disputa', la respuesta
--    no puede dar una sola versión: debe presentar ambas afirmaciones con sus
--    fuentes e indicar explícitamente que hay una contradicción pendiente."
--
-- Cambio respecto a 002_search_function.sql:
--   - Incluye chunks con status 'active' OR 'disputed'
--   - Devuelve el campo chunk_status para que el caller pueda flagear conflictos
--   - Sigue excluyendo 'superseded' (ya resueltos como obsoletos)
--
-- IMPORTANTE: el filtrado por allowed_doc_ids (RLS early binding) se mantiene
-- íntegro en el caller (db.py → search_embeddings_rls).
--
-- Nota: PostgreSQL no permite cambiar el RETURNS TABLE con CREATE OR REPLACE
-- cuando se añaden columnas, por eso hacemos DROP antes.

DROP FUNCTION IF EXISTS search_embeddings(vector, float, int, uuid[]);

CREATE OR REPLACE FUNCTION search_embeddings(
  query_embedding vector(768),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 5,
  allowed_doc_ids uuid[] DEFAULT '{}'
)
RETURNS TABLE (
  id            bigint,
  document_id   uuid,
  chunk_index   int,
  chunk_text    text,
  similarity    float,
  chunk_status  text   -- 'active' | 'disputed' (nunca 'superseded')
)
LANGUAGE sql STABLE
AS $$
  SELECT
    e.id,
    e.document_id,
    e.chunk_index,
    e.chunk_text,
    1 - (e.vector <=> query_embedding) AS similarity,
    e.chunk_status
  FROM embeddings e
  WHERE
    e.document_id = ANY(allowed_doc_ids)
    AND e.chunk_status IN ('active', 'disputed')
    AND 1 - (e.vector <=> query_embedding) > match_threshold
  ORDER BY e.vector <=> query_embedding
  LIMIT match_count;
$$;

GRANT EXECUTE ON FUNCTION search_embeddings TO service_role;
GRANT EXECUTE ON FUNCTION search_embeddings TO anon;
GRANT EXECUTE ON FUNCTION search_embeddings TO authenticated;
