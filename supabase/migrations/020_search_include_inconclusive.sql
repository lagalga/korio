-- Migración 020: Incluir chunks 'inconclusive' en la búsqueda vectorial
--
-- Fix: la RPC search_embeddings solo devolvía 'active' y 'disputed',
-- excluyendo 'inconclusive'. Pero el diseño de gobernanza (timeout HITL)
-- dice "conservar ambos documentos como información complementaria" y
-- "el RAG seguirá mostrando ambas versiones con aviso de contradicción".
--
-- Ahora: chunk_status IN ('active', 'disputed', 'inconclusive').
-- El caller (search.py) trata 'inconclusive' igual que 'disputed':
-- presenta ambas versiones y avisa de la contradicción pendiente.

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
  chunk_status  text   -- 'active' | 'disputed' | 'inconclusive' (nunca 'superseded')
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
    AND e.chunk_status IN ('active', 'disputed', 'inconclusive')
    AND 1 - (e.vector <=> query_embedding) > match_threshold
  ORDER BY e.vector <=> query_embedding
  LIMIT match_count;
$$;

GRANT EXECUTE ON FUNCTION search_embeddings TO service_role;
GRANT EXECUTE ON FUNCTION search_embeddings TO anon;
GRANT EXECUTE ON FUNCTION search_embeddings TO authenticated;
