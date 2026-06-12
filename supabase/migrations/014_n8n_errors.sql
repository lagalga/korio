-- ════════════════════════════════════════════════════════════════════════
-- Migración 014 — Tabla de errores de workflows n8n
-- ════════════════════════════════════════════════════════════════════════
-- Sesión 12 (12 jun 2026) · Korio v0.3.3
--
-- Captura los errores de ejecuciones de n8n.korio.es para diagnóstico
-- y trazabilidad. Alimentada por el workflow `Korio - Gestión de errores
-- n8n` que se dispara con el Error Trigger ante cualquier fallo de
-- workflow activo del proyecto.
--
-- También se notifica el error en Slack (#korio-alerts) en el mismo
-- workflow para alertar al admin sin esperar a revisar n8n.
-- ════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS n8n_errors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    captured_at       TIMESTAMPTZ      DEFAULT NOW() NOT NULL,

    -- Identificadores del workflow fallido (de $execution / $workflow del trigger)
    workflow_id       TEXT             NOT NULL,
    workflow_name     TEXT,
    execution_id      TEXT,
    execution_mode    TEXT,                          -- manual | trigger | webhook | cli | retry

    -- Detalle del error
    error_message     TEXT,
    error_node_name   TEXT,
    error_node_type   TEXT,
    error_stack       TEXT,

    -- Payload completo del error trigger (debug / inspección)
    raw_payload       JSONB,

    -- Estado de revisión por el admin (Phase 8: panel /admin/errors)
    reviewed_at       TIMESTAMPTZ,
    reviewed_by       TEXT,
    notes             TEXT
);

-- Índices para queries típicas del panel admin:
CREATE INDEX IF NOT EXISTS idx_n8n_errors_captured_at
    ON n8n_errors (captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_n8n_errors_workflow_id
    ON n8n_errors (workflow_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_n8n_errors_unresolved
    ON n8n_errors (captured_at DESC)
    WHERE reviewed_at IS NULL;

-- Esta tabla NO es multi-tenant: errores de n8n son operativos del sistema,
-- no de ningún tenant específico. Sin RLS — accesible solo via service_role.

COMMENT ON TABLE  n8n_errors                 IS 'Errores capturados de ejecuciones de workflows n8n.korio.es (sesión 12, migración 014)';
COMMENT ON COLUMN n8n_errors.workflow_id     IS 'ID del workflow n8n que falló';
COMMENT ON COLUMN n8n_errors.execution_id    IS 'ID de la ejecución concreta (para linkar a n8n.korio.es/execution/{id})';
COMMENT ON COLUMN n8n_errors.execution_mode  IS 'Cómo se disparó: manual, trigger, webhook, cli, retry';
COMMENT ON COLUMN n8n_errors.raw_payload     IS 'JSON completo del error trigger para debugging post-mortem';
