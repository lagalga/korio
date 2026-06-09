-- Migración 007: Tabla waitlist para landing teaser de korio.es
--
-- Captura emails de la lista de espera del beta. Sin RLS — los inserts vienen
-- del FastAPI con service_role; la lectura es admin-only.

CREATE TABLE IF NOT EXISTS waitlist (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT NOT NULL,
  source      TEXT DEFAULT 'landing',  -- futuro: 'referral', 'event', etc.
  metadata    JSONB DEFAULT '{}'::jsonb,
  user_agent  TEXT,
  referer     TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT waitlist_email_unique UNIQUE(email)
);

CREATE INDEX idx_waitlist_created_at ON waitlist(created_at);
