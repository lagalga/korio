-- Migración 010: Tabla mcp_api_keys
--
-- API keys por usuario para el endpoint MCP (Phase 7.3). Cada key se asocia a
-- un (user_id, tenant_id) concreto, así el servidor MCP propaga la identidad
-- a las tools y el early binding de RLS sigue funcionando.
--
-- Modelo de seguridad:
--   - El servidor solo persiste el SHA-256 de la key (key_hash), nunca el
--     texto plano. Si el usuario la pierde se revoca y se emite otra.
--   - Una key puede revocarse (soft-delete) marcando revoked_at.
--   - last_used_at permite auditoría básica y detectar keys huérfanas.
--
-- En Phase 8 esta tabla se sustituye por OAuth 2.1 con tokens de corta vida.

CREATE TABLE IF NOT EXISTS mcp_api_keys (
  key_hash      TEXT PRIMARY KEY,
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at  TIMESTAMPTZ,
  revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_user
  ON mcp_api_keys (user_id)
  WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_tenant
  ON mcp_api_keys (tenant_id)
  WHERE revoked_at IS NULL;

COMMENT ON TABLE  mcp_api_keys IS
  'API keys (SHA-256) que autorizan llamadas al servidor MCP. Una key = un usuario.';
COMMENT ON COLUMN mcp_api_keys.key_hash IS
  'SHA-256 hex de la key en texto plano. El plaintext nunca se almacena.';
COMMENT ON COLUMN mcp_api_keys.name IS
  'Alias humano para distinguir keys del mismo usuario (ej. "Claude Desktop laptop").';
