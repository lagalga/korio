-- Migración 018: service users por canal Slack del tenant Clínica Delos
--
-- Sesión 13b: el workflow Slack `/korio → /search` estaba hardcoded al
-- admin user (ve TODOS los spaces), lo que ocultaba el aislamiento RLS
-- cuando un canal sectorial preguntaba sobre otro departamento. Tras
-- abrir un canal Slack por departamento (#clinica-delos-{rrhh,medico,
-- legal,admin}), tiene más sentido que cada canal hable con Korio como
-- un "service account" cuyo scope coincide con su departamento.
--
-- Cuatro service users, uno por canal. El backend ya hace early-binding
-- de RLS por user_id (`db.get_user_spaces`) → preguntando desde
-- #clinica-delos-rrhh no devolverá nada de Legal aunque la pregunta lo
-- mencione expresamente. Mismo principio para los demás. El service
-- user `slack_admin@delos` ve los 4 spaces (RRHH+Médico+Legal+Admin) y
-- mantiene la experiencia de "consulta global" del admin.

INSERT INTO users (id, tenant_id, email, role) VALUES
  ('a4000000-0000-0000-0000-000000000001','a0000000-0000-0000-0000-000000000001','slack_rrhh@delos','user'),
  ('a4000000-0000-0000-0000-000000000002','a0000000-0000-0000-0000-000000000001','slack_medico@delos','user'),
  ('a4000000-0000-0000-0000-000000000003','a0000000-0000-0000-0000-000000000001','slack_legal@delos','user'),
  ('a4000000-0000-0000-0000-000000000004','a0000000-0000-0000-0000-000000000001','slack_admin@delos','admin')
ON CONFLICT (id) DO NOTHING;

-- Permisos: cada service user ve solo su space (admin ve los 4)
INSERT INTO user_spaces (user_id, space_id) VALUES
  -- slack_rrhh → RRHH
  ('a4000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000001'),
  -- slack_medico → Médico
  ('a4000000-0000-0000-0000-000000000002','a1000000-0000-0000-0000-000000000002'),
  -- slack_legal → Legal
  ('a4000000-0000-0000-0000-000000000003','a1000000-0000-0000-0000-000000000003'),
  -- slack_admin → todos
  ('a4000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000001'),
  ('a4000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000002'),
  ('a4000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000003'),
  ('a4000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000004')
ON CONFLICT (user_id, space_id) DO NOTHING;
