-- Migración 016: restringir detección query-time de conflictos silenciosos a same-space
--
-- Sesión 13b detectó falsos positivos en la regla del E4 ("Caso extremo"). Tras
-- la ingesta limpia de los 11 docs demo, queries no relacionadas levantaban
-- avisos `has_silent_conflict=true` entre R4_convenio-sanitario.md (RRHH) y
-- M3_ficha-ibuprofeno.md (Médico) con sim 0.85, pese a ser temáticamente
-- disjuntos. Causa: chunks cortos (1 párrafo) producen embeddings con menor
-- varianza y se acercan artificialmente en el espacio vectorial, incluso entre
-- documentos de departamentos completamente independientes.
--
-- Funcionalmente, un conflicto silencioso CROSS-space no tiene sentido en
-- Korio: cada space es un departamento aislado con su propio gobierno (RLS),
-- sus propias políticas y sus propios reviewers. Si dos áreas distintas
-- "se contradicen" tematicamente, no es un conflicto a resolver — son dos
-- realidades que conviven (un médico habla de fármacos, un convenio habla de
-- horarios laborales: que se parezcan en el embedding es ruido).
--
-- Fix: añadir restricción `d1.space_id = d2.space_id` al RPC. La detección
-- pasa a ser SAME-space only.

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
    AND d1.space_id = d2.space_id              -- SAME-space only (migración 016)
    AND (1 - (e1.vector <=> e2.vector)) >= p_threshold
  ORDER BY similarity DESC;
$$;

COMMENT ON FUNCTION detect_silent_conflicts_among_chunks(BIGINT[], FLOAT) IS
  'Detección de conflictos silenciosos en query-time SAME-space: dado un conjunto de chunks recuperados por el RAG, devuelve los pares con similitud coseno >= p_threshold entre documentos distintos del MISMO space (excluyendo chunks ya disputed). Migración 016 añadió la restricción same-space para evitar falsos positivos cross-departamento por chunks cortos.';
