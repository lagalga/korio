-- Migración 006: admin_email por tenant
--
-- Para el HITL email de gobernanza. Por defecto NULL → el workflow n8n usa
-- el email global definido en su configuración. Cuando un tenant tenga
-- admin_email asignado, el workflow lo respetará.
--
-- Esto deja la puerta abierta a la mejora "admin_email configurable por tenant"
-- sin tocar el schema más adelante: solo añadimos UI de onboarding.

ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS admin_email TEXT;

COMMENT ON COLUMN tenants.admin_email IS
  'Email del administrador del tenant para notificaciones HITL de gobernanza. '
  'NULL = usar el destino por defecto del workflow n8n.';
