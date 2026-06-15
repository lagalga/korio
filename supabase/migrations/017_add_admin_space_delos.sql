-- Migración 017: añadir space "Administración" al tenant Clínica Delos
--
-- Sesión 13b extendió la ingesta multi-canal a 4 departamentos (sesión 12
-- venía con 3: RRHH, Médico, Legal). El cuarto departamento es
-- Administración, donde caen circulares de dirección, comunicados internos
-- corporativos, documentación financiera, etc.
--
-- El admin user del tenant Delos hereda acceso al nuevo space (rol admin
-- ve todos los spaces del tenant). El staff y el doctor mantienen su scope
-- actual sin tocar.

INSERT INTO spaces (id, tenant_id, name, description)
VALUES (
  'a1000000-0000-0000-0000-000000000004',
  'a0000000-0000-0000-0000-000000000001',
  'Administración',
  'Circulares de dirección, comunicaciones corporativas, documentación financiera y administrativa de Clínica Delos.'
)
ON CONFLICT (id) DO NOTHING;

-- Dar acceso al admin user de Delos al nuevo space
INSERT INTO user_spaces (user_id, space_id)
VALUES (
  'a1000000-0000-0000-0000-000000000001',  -- admin Delos
  'a1000000-0000-0000-0000-000000000004'   -- space Administración
)
ON CONFLICT (user_id, space_id) DO NOTHING;
