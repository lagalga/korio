-- Korio Schema — Supabase
-- Multi-tenant RAG system with RLS
-- Created: 2026-06-08

-- ============================================================================
-- TENANTS & USERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT tenant_name_unique UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'user', 'viewer')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT user_email_tenant_unique UNIQUE(tenant_id, email)
);

-- ============================================================================
-- SPACES (RRHH, Dirección, Operaciones, Legal, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS spaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  authority_weight INT DEFAULT 5 CHECK (authority_weight >= 1 AND authority_weight <= 10),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT space_name_tenant_unique UNIQUE(tenant_id, name)
);

-- User → Space assignment (RLS)
CREATE TABLE IF NOT EXISTS user_spaces (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, space_id)
);

-- ============================================================================
-- DOCUMENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  source_url TEXT,
  content_hash TEXT UNIQUE,  -- For deduplication
  source_type TEXT CHECK (source_type IN ('drive', 'slack', 'email', 'manual', 'notion', 'salesforce')),
  authority_weight INT DEFAULT 5 CHECK (authority_weight >= 1 AND authority_weight <= 10),
  version_ts TIMESTAMPTZ DEFAULT NOW(),
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'superseded')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_documents_tenant_space ON documents(tenant_id, space_id);
CREATE INDEX idx_documents_content_hash ON documents(content_hash);

-- ============================================================================
-- EMBEDDINGS (Vector search)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS embeddings (
  id BIGSERIAL PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  chunk_text TEXT NOT NULL,
  vector vector(384),  -- nomic-embed-text fixed size
  chunk_status TEXT DEFAULT 'active' CHECK (chunk_status IN ('active', 'superseded', 'disputed')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT chunk_unique UNIQUE(document_id, chunk_index)
);

-- IVFFlat index for cosine similarity
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_embeddings_document ON embeddings(document_id);

-- ============================================================================
-- ACL (Access Control) — Document level
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_acl (
  id BIGSERIAL PRIMARY KEY,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
  permission TEXT DEFAULT 'read' CHECK (permission IN ('read', 'write', 'admin')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT document_space_acl_unique UNIQUE(document_id, space_id)
);

CREATE INDEX idx_document_acl_space ON document_acl(space_id);

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  doc_ids_used UUID[],
  model_used TEXT,
  latency_ms INT,
  has_conflict BOOLEAN DEFAULT FALSE,
  response_tokens INT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user ON audit_log(tenant_id, user_id, created_at);

-- ============================================================================
-- ROW-LEVEL SECURITY (RLS) — CRITICAL
-- ============================================================================

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Policy: documents — user can only see docs from their spaces
CREATE POLICY "documents_access_by_user_spaces" ON documents
  FOR SELECT
  USING (
    space_id IN (
      SELECT space_id FROM user_spaces WHERE user_id = auth.uid()
    )
  );

-- Policy: embeddings — early binding (check via document)
CREATE POLICY "embeddings_access_by_user_spaces" ON embeddings
  FOR SELECT
  USING (
    document_id IN (
      SELECT d.id FROM documents d
      WHERE d.space_id IN (
        SELECT space_id FROM user_spaces WHERE user_id = auth.uid()
      )
    )
  );

-- Policy: audit_log — user can only see their own logs
CREATE POLICY "audit_log_access_by_user" ON audit_log
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "audit_log_select_own" ON audit_log
  FOR SELECT
  USING (user_id = auth.uid());

-- ============================================================================
-- SEED DATA (for testing)
-- ============================================================================

-- Tenant 1: Hospital San Juan
INSERT INTO tenants (id, name) VALUES
  ('a0000000-0000-0000-0000-000000000001'::UUID, 'Hospital San Juan');

-- Tenant 2: Despacho Legal García
INSERT INTO tenants (id, name) VALUES
  ('b0000000-0000-0000-0000-000000000002'::UUID, 'Despacho Legal García');

-- Users for Tenant 1
INSERT INTO users (id, tenant_id, email, role) VALUES
  ('a1000000-0000-0000-0000-000000000001'::UUID, 'a0000000-0000-0000-0000-000000000001', 'admin@hospital.es', 'admin'),
  ('a2000000-0000-0000-0000-000000000001'::UUID, 'a0000000-0000-0000-0000-000000000001', 'doctor@hospital.es', 'user'),
  ('a3000000-0000-0000-0000-000000000001'::UUID, 'a0000000-0000-0000-0000-000000000001', 'staff@hospital.es', 'viewer');

-- Users for Tenant 2
INSERT INTO users (id, tenant_id, email, role) VALUES
  ('b1000000-0000-0000-0000-000000000002'::UUID, 'b0000000-0000-0000-0000-000000000002', 'admin@despacho.es', 'admin'),
  ('b2000000-0000-0000-0000-000000000002'::UUID, 'b0000000-0000-0000-0000-000000000002', 'lawyer@despacho.es', 'user');

-- Spaces for Tenant 1
INSERT INTO spaces (id, tenant_id, name, description, authority_weight) VALUES
  ('a1000000-0000-0000-0000-000000000001'::UUID, 'a0000000-0000-0000-0000-000000000001', 'RRHH', 'Recursos Humanos', 7),
  ('a1000000-0000-0000-0000-000000000002'::UUID, 'a0000000-0000-0000-0000-000000000001', 'Médico', 'Documentación Clínica', 9),
  ('a1000000-0000-0000-0000-000000000003'::UUID, 'a0000000-0000-0000-0000-000000000001', 'Legal', 'Asuntos Legales', 8);

-- Spaces for Tenant 2
INSERT INTO spaces (id, tenant_id, name, description, authority_weight) VALUES
  ('b1000000-0000-0000-0000-000000000001'::UUID, 'b0000000-0000-0000-0000-000000000002', 'Casos', 'Gestión de Casos Legales', 9),
  ('b1000000-0000-0000-0000-000000000002'::UUID, 'b0000000-0000-0000-0000-000000000002', 'Fiscal', 'Documentación Fiscal', 8);

-- User-Space assignments Tenant 1
INSERT INTO user_spaces (user_id, space_id) VALUES
  -- Admin can access all spaces
  ('a1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001'),
  ('a1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002'),
  ('a1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000003'),
  -- Doctor: RRHH + Médico
  ('a2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001'),
  ('a2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000002'),
  -- Staff: only RRHH
  ('a3000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001');

-- User-Space assignments Tenant 2
INSERT INTO user_spaces (user_id, space_id) VALUES
  -- Admin: all
  ('b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000001'),
  ('b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000002'),
  -- Lawyer: only Casos
  ('b2000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000001');

-- ACL for spaces
INSERT INTO document_acl (document_id, space_id, permission)
  SELECT d.id, d.space_id, 'read'
  FROM documents d
  WHERE d.status = 'active';

-- ============================================================================
-- NOTES
-- ============================================================================
/*
RLS FLOW:
1. User 'doctor@hospital.es' (a2000000...) queries via auth.uid() = a2000000...
2. Query hits embeddings table → RLS policy checks:
   - SELECT document_id FROM documents d
     WHERE d.space_id IN (
       SELECT space_id FROM user_spaces WHERE user_id = 'a2000000...'
     )
   - Result: spaces RRHH + Médico (not Legal)
3. Query returns only embeddings from RRHH + Médico documents
4. User from despacho.es (b2000000...) gets different result

KEY: RLS is enforced BEFORE the LLM sees anything.
The model never has access to rows it shouldn't see.
*/
