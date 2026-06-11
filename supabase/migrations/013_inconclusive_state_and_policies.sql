-- Migración 013: estado terminal `inconclusive` + tabla `policies`
--
-- Cumple dos reglas explícitas del diseño multi-agéntico del Entregable 3:
--
--   Regla 5 — Reactivación manual obligatoria. Un documento que el sistema no
--   pudo resolver autónomamente y que tras los recordatorios HITL no recibió
--   respuesta del Supervisor queda en estado `inconclusive`. NO se reactiva
--   automáticamente. Excluido del RAG hasta que un admin intervenga.
--
--   Regla 4 — Prevalencia de políticas sobre reglas base. Las decisiones que
--   el Supervisor toma vía HITL se persisten como políticas reutilizables
--   que el Árbitro consulta ANTES de evaluar criterios cronológicos o de
--   autoridad. Cada match reduce intervención humana en conflictos similares
--   posteriores. Es el mecanismo de "aprendizaje" del sistema agéntico.

-- ─── 1. Estado `inconclusive` en `embeddings.chunk_status` ──────────────────

ALTER TABLE embeddings DROP CONSTRAINT IF EXISTS embeddings_chunk_status_check;
ALTER TABLE embeddings ADD CONSTRAINT embeddings_chunk_status_check
  CHECK (chunk_status IN ('active', 'superseded', 'disputed', 'inconclusive'));

COMMENT ON COLUMN embeddings.chunk_status IS
  'Estado del chunk dentro del corpus: active (en RAG) | superseded (sustituido) | disputed (en HITL) | inconclusive (timeout sin resolver, requiere reactivación manual)';

-- ─── 2. `timeout_inconclusive` en `conflict_reviews.resolution` ─────────────

ALTER TABLE conflict_reviews DROP CONSTRAINT IF EXISTS conflict_reviews_resolution_check;
ALTER TABLE conflict_reviews ADD CONSTRAINT conflict_reviews_resolution_check
  CHECK (resolution IN (
    'pending',
    'approved_new',
    'approved_existing',
    'kept_both',
    'auto_new_wins',
    'auto_existing_wins',
    'auto_inconclusive',
    'timeout_kept_both',
    'timeout_inconclusive',
    'policy_new_wins',
    'policy_existing_wins',
    'policy_kept_both',
    'policy_inconclusive'
  ));

-- ─── 3. Tabla `policies` ───────────────────────────────────────────────────
--
-- Cada decisión HITL del Supervisor se persiste como una política reutilizable
-- por tenant+space. Cuando llega un nuevo conflicto cuyo subject normalizado
-- matchea el `subject_pattern` (LIKE case-insensitive), el Árbitro aplica la
-- decisión guardada en lugar de razonar desde cero.
--
-- El "subject_pattern" se deriva del subject de los chunks en conflicto. Para
-- el MVP usamos un patrón simple basado en las primeras N keywords
-- relevantes; en Phase 8 esto puede sofisticarse con embeddings o regex.

CREATE TABLE IF NOT EXISTS policies (
  id                BIGSERIAL PRIMARY KEY,
  tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  space_id          UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  -- Patrón a buscar (case-insensitive LIKE) en el subject del nuevo chunk
  subject_pattern   TEXT NOT NULL,
  -- Decisión que aplicará el Árbitro cuando matchee:
  --   policy_new_wins      → marcar existing como superseded, new como active
  --   policy_existing_wins → marcar new como superseded
  --   policy_kept_both     → ambos como active (aviso al usuario en cada query)
  --   policy_inconclusive  → ambos como inconclusive (excluidos del RAG)
  decision          TEXT NOT NULL CHECK (decision IN (
    'policy_new_wins', 'policy_existing_wins',
    'policy_kept_both', 'policy_inconclusive'
  )),
  -- Trazabilidad: cuál fue la decisión HITL que generó esta política
  source_review_id  UUID REFERENCES conflict_reviews(id) ON DELETE SET NULL,
  reason            TEXT,
  -- Contadores para medir efectividad
  times_applied     INT NOT NULL DEFAULT 0,
  last_applied_at   TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  -- Política puede desactivarse manualmente sin perderla del historial
  active            BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_policies_tenant_space_active
  ON policies (tenant_id, space_id)
  WHERE active;

CREATE INDEX IF NOT EXISTS idx_policies_subject_pattern
  ON policies (subject_pattern text_pattern_ops)
  WHERE active;

COMMENT ON TABLE policies IS
  'Políticas reutilizables aprendidas de decisiones HITL. El Arbitrator las consulta antes de evaluar criterios cronológicos/autoridad. Cumple Regla 4 del Entregable 3 (prevalencia de políticas sobre reglas base) y materializa el mecanismo de aprendizaje del sistema multi-agéntico.';

COMMENT ON COLUMN policies.subject_pattern IS
  'Patrón LIKE case-insensitive sobre el subject del nuevo chunk. Match → aplicar `decision` sin razonamiento adicional.';
