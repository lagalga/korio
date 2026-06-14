-- Migración 015: RLS sobre mcp_api_keys
--
-- La tabla 010_mcp_api_keys.sql se creó SIN Row Level Security. Esto significa
-- que cualquier rol con acceso al schema (anon, authenticated) podía hacer
-- SELECT * y leer hashes + (user_id, tenant_id) de TODAS las keys del sistema,
-- incluyendo las de otros tenants. Los hashes son SHA-256 (no reversibles a
-- plaintext) pero filtran metadatos de inventario.
--
-- Esta migración:
--   1. Habilita RLS en la tabla.
--   2. Crea policy de lectura propia: un usuario solo ve sus propias keys.
--   3. Crea policy permisiva para service_role (el backend de Korio,
--      `scripts/mcp_create_key.py` y los CLI admin siguen funcionando).
--
-- En Phase 8 (OAuth 2.1) esta tabla se retira y la política se elimina con ella.

ALTER TABLE mcp_api_keys ENABLE ROW LEVEL SECURITY;

-- Usuario autenticado vía Supabase Auth: solo ve sus propias keys.
DROP POLICY IF EXISTS mcp_keys_self_read ON mcp_api_keys;
CREATE POLICY mcp_keys_self_read ON mcp_api_keys
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS mcp_keys_self_update ON mcp_api_keys;
CREATE POLICY mcp_keys_self_update ON mcp_api_keys
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- service_role: acceso completo. Lo usa el backend FastAPI (`resolve_mcp_key`,
-- `last_used_at`) y el CLI `scripts/mcp_create_key.py`.
DROP POLICY IF EXISTS mcp_keys_service_role_all ON mcp_api_keys;
CREATE POLICY mcp_keys_service_role_all ON mcp_api_keys
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

COMMENT ON POLICY mcp_keys_self_read ON mcp_api_keys IS
  'Aislamiento multi-tenant: un usuario autenticado solo lee sus propias MCP keys.';
COMMENT ON POLICY mcp_keys_service_role_all ON mcp_api_keys IS
  'Backend Korio (service_role) gestiona create/revoke/lookup. RLS no aplica.';
