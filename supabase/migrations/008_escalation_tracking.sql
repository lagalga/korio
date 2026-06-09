-- Migración 008: Tracking de escalada en conflict_reviews
--
-- Añade campos para que el cron de escalada sepa qué recordatorios ya
-- envió a cada revisión, evite duplicados, y registre cuándo se aplicó
-- el timeout automático.
--
-- Campos:
--   reminders_sent       — número de recordatorios enviados (0, 1, 2, 3 = post-timeout)
--   last_reminder_at     — fecha del último email recordatorio
--   timeout_at           — fecha en que se forzó auto-resolución por timeout (NULL si no)
--
-- Compatible con registros existentes (NULL en los nuevos campos).

ALTER TABLE conflict_reviews
  ADD COLUMN IF NOT EXISTS reminders_sent    INT         DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_reminder_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS timeout_at        TIMESTAMPTZ;

-- Permitir 'timeout_kept_both' en resolution (auto-cierre por escalada)
ALTER TABLE conflict_reviews DROP CONSTRAINT IF EXISTS conflict_reviews_resolution_check;
ALTER TABLE conflict_reviews ADD CONSTRAINT conflict_reviews_resolution_check
  CHECK (resolution IN (
    'pending',
    'auto_new_wins',
    'auto_existing_wins',
    'approved_new',
    'approved_existing',
    'kept_both',
    'timeout_kept_both'  -- nuevo: cerrado automáticamente por timeout
  ));

COMMENT ON COLUMN conflict_reviews.reminders_sent IS
  'Número de recordatorios HITL enviados. 0=solo el inicial, 1-3=tras hitos de escalada.';
COMMENT ON COLUMN conflict_reviews.timeout_at IS
  'Si no NULL: la revisión fue cerrada automáticamente por escalada al superar ESCALATION_TIMEOUT_DAYS.';
