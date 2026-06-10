-- Migración 009: Metadatos de origen en documents
--
-- Añade source_metadata (JSONB) para registrar el contexto del canal por el que
-- entró un documento ingerido automáticamente desde n8n u otros conectores.
--
-- Ejemplos de payload:
--   { "via": "n8n_gmail",
--     "message_id": "189a3b2c4...",
--     "from": "abogado@delos.es",
--     "subject": "Contrato actualizado",
--     "label": "korio/ingesta",
--     "received_at": "2026-06-10T14:32:00Z" }
--
--   { "via": "n8n_gdrive",
--     "file_id": "1AbC...",
--     "folder_id": "0AFx...",
--     "modified_at": "2026-06-10T14:32:00Z" }
--
-- Compatible con documentos existentes (NULL = ingesta manual o anterior a esta migración).
-- En Phase 8 se complementará con source_connection_id y source_rule_id (FK).

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS source_metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_documents_source_via
  ON documents ((source_metadata->>'via'))
  WHERE source_metadata IS NOT NULL;

COMMENT ON COLUMN documents.source_metadata IS
  'Contexto del origen de ingesta (canal n8n, message_id, file_id, etc.). NULL para ingesta manual.';
