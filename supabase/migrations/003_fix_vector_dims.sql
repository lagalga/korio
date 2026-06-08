-- Migración 003: Corregir dimensiones del vector
--
-- nomic-embed-text en Ollama genera vectores de 768 dims, no 384.
-- Corregimos el schema para que coincida con el modelo real.
--
-- IMPORTANTE: Ejecutar ANTES de ingestar cualquier documento.
-- Si ya hay embeddings, hay que borrarlos primero:
--   DELETE FROM embeddings;

-- Eliminar el índice ivfflat existente (depende del tipo de columna)
DROP INDEX IF EXISTS idx_embeddings_vector;

-- Cambiar la dimensión del vector
ALTER TABLE embeddings
  ALTER COLUMN vector TYPE vector(768);

-- Recrear el índice con las dimensiones correctas
CREATE INDEX idx_embeddings_vector
  ON embeddings USING ivfflat (vector vector_cosine_ops)
  WITH (lists = 100);

-- Actualizar también la función de búsqueda
CREATE OR REPLACE FUNCTION search_embeddings(
  query_embedding vector(768),
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
  ORDER BY e.vector <=> query_embedding
  LIMIT match_count;
$$;
