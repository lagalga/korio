-- Migración 002: Función de búsqueda vectorial con RLS
--
-- Esta función se llama desde db.py via Supabase RPC.
-- Recibe una lista de document_ids ya filtrados por RLS (early binding)
-- y devuelve los chunks más similares al vector de la query.
--
-- IMPORTANTE: El filtrado por permisos se hace ANTES de llamar a esta función
-- (en db.py → search_embeddings_rls). Esta función solo busca dentro
-- de los documentos permitidos.

CREATE OR REPLACE FUNCTION search_embeddings(
  query_embedding vector(384),
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 5,
  allowed_doc_ids uuid[] DEFAULT '{}'
)
RETURNS TABLE (
  id bigint,
  document_id uuid,
  chunk_index int,
  chunk_text text,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    e.id,
    e.document_id,
    e.chunk_index,
    e.chunk_text,
    1 - (e.vector <=> query_embedding) AS similarity
  FROM embeddings e
  WHERE
    e.document_id = ANY(allowed_doc_ids)
    AND e.chunk_status = 'active'
    AND 1 - (e.vector <=> query_embedding) > match_threshold
  ORDER BY e.vector <=> query_embedding  -- orden ascendente por distancia = desc por similitud
  LIMIT match_count;
$$;

-- Conceder permisos de ejecución
GRANT EXECUTE ON FUNCTION search_embeddings TO service_role;
GRANT EXECUTE ON FUNCTION search_embeddings TO anon;
GRANT EXECUTE ON FUNCTION search_embeddings TO authenticated;

-- Verificar que la extensión pgvector está activa
-- (ya debería estar del migration 001, pero por seguridad)
-- CREATE EXTENSION IF NOT EXISTS vector;
