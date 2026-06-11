-- Migración 012: detección de conflictos silenciosos en query-time
--
-- Cierra el "Caso extremo" descrito al final del Entregable 4 del TFM: dos
-- documentos ya activos con información contradictoria pero que en su día NO
-- llegaron a dispararse mutuamente en el detector de ingesta (porque su
-- similitud cruzada quedó por debajo del umbral 0.82 o porque uno de ellos se
-- cargó directamente en BD sin pasar por el pipeline). El RAG los recupera
-- juntos en una consulta y elige uno sin avisar.
--
-- Esta función se invoca DESDE search.py tras recuperar los chunks que va a
-- usar el LLM. Recibe los chunk_ids candidatos y devuelve los pares de
-- chunks que (a) pertenecen a documentos distintos y (b) tienen similitud
-- coseno >= p_threshold. La detección es O(N²/2) pero N es pequeño
-- (típicamente 5-10 chunks), así que el coste real es despreciable y la
-- alternativa (traer 768 floats × N a Python) es mucho peor.
--
-- Por qué SOLO chunks active: si los chunks ya están marcados como
-- `disputed` significa que la gobernanza ya identificó el conflicto en
-- ingesta y hay un `conflict_review` en curso. No queremos duplicar el aviso.

CREATE OR REPLACE FUNCTION detect_silent_conflicts_among_chunks(
  p_chunk_ids BIGINT[],
  p_threshold FLOAT DEFAULT 0.85
)
RETURNS TABLE (
  chunk_a_id  BIGINT,
  chunk_b_id  BIGINT,
  doc_a_id    UUID,
  doc_b_id    UUID,
  filename_a  TEXT,
  filename_b  TEXT,
  similarity  FLOAT
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    e1.id           AS chunk_a_id,
    e2.id           AS chunk_b_id,
    e1.document_id  AS doc_a_id,
    e2.document_id  AS doc_b_id,
    d1.filename     AS filename_a,
    d2.filename     AS filename_b,
    1 - (e1.vector <=> e2.vector) AS similarity
  FROM embeddings e1
  JOIN embeddings e2
    ON e2.id > e1.id                           -- evita pares duplicados (a,b)/(b,a)
   AND e1.document_id <> e2.document_id        -- solo entre documentos distintos
  JOIN documents d1 ON d1.id = e1.document_id
  JOIN documents d2 ON d2.id = e2.document_id
  WHERE e1.id = ANY(p_chunk_ids)
    AND e2.id = ANY(p_chunk_ids)
    AND e1.chunk_status = 'active'
    AND e2.chunk_status = 'active'
    AND d1.status = 'active'
    AND d2.status = 'active'
    AND (1 - (e1.vector <=> e2.vector)) >= p_threshold
  ORDER BY similarity DESC;
$$;

COMMENT ON FUNCTION detect_silent_conflicts_among_chunks(BIGINT[], FLOAT) IS
  'Detección de conflictos silenciosos en query-time: dado un conjunto de chunks recuperados por el RAG, devuelve los pares con similitud coseno >= p_threshold entre documentos distintos (excluyendo chunks ya disputed). Cierra el "Caso extremo" del Entregable 4 del TFM.';
