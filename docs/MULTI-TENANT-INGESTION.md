# Korio — Ingesta automática multi-tenant configurable

> Documento de diseño para la **Phase 8 (post-TFM)**. Describe la evolución desde la ingesta manual hardcodeada (Phase 7.2, demo TFM) hasta un sistema configurable por tenant con conectores OAuth a Gmail, Google Drive, Slack, Outlook, SharePoint, Dropbox, etc.
>
> Sirve dos propósitos:
> 1. **Guía técnica** para los workflows n8n de la Phase 7.2 (decidir qué hardcodear hoy sabiendo qué será dinámico mañana).
> 2. **Capítulo de la memoria del TFM** ("Arquitectura objetivo del producto SaaS · Roadmap post-defensa").

---

## 1. Contexto y objetivo

Korio en Phase 7.1 ingiere documentos por dos vías:

- **Manual UI**: usuario sube un fichero desde `/ui` → `POST /upload` con `tenant_id` + `space_id` derivados del usuario autenticado.
- **CLI**: `python src/ingest.py FILE --tenant-id ... --space-id ...` para back-office.

Una pyme real no quiere subir ficheros manualmente. Quiere que **Korio vigile sus canales** (correo, drive, chat) y vaya alimentando el cerebro continuamente. El reto: hacerlo **multi-tenant configurable** sin comprometer RLS ni la simplicidad operativa.

### Casos de uso objetivo

| Caso | Origen | Espacio destino |
|---|---|---|
| Despacho legal recibe contratos por Gmail | Label `korio/ingesta` en `legal@cliente.es` | Space "Casos" |
| Clínica sube actas a Drive | Carpeta `Korio/Actas` en Drive de RRHH | Space "RRHH" |
| Equipo comenta políticas en Slack | Canal `#politicas-rrhh` | Space "RRHH" |
| Operaciones recibe albaranes por Outlook | Carpeta "Albaranes" | Space "Operaciones" |

---

## 2. Estado actual (Phase 7.2 — demo TFM)

### Decisión para la demo del 2 julio

Los 3 workflows de la Phase 7.2 se construirán **hardcodeados** sobre el tenant Delos:

| Workflow | Trigger | Acción | Configuración |
|---|---|---|---|
| Gmail → Korio | Gmail Trigger (label `korio/ingesta`) | Descargar adjuntos → `POST /upload` | `tenant_id` y `space_id` literales en nodo Set |
| Drive → Korio | Google Drive Trigger (carpeta fija) | Descargar fichero nuevo → `POST /upload` | Carpeta ID en nodo, tenant/space literales |
| Slack `/korio` | Slash Command | `POST /search` → respuesta en thread | Bot token único, mapeo `channel_id → space_id` en Code node |

**Por qué hardcodeado para la demo:**

- El valor a demostrar es "Korio se alimenta solo", no "tenemos UI de conexiones".
- Cada conector OAuth en multi-tenant exige verificación de la app por parte del proveedor (Google, Slack), que tarda semanas. Para una demo de tribunal con tenants ficticios no aporta.
- El diseño multi-tenant queda **documentado aquí** y se referencia en la memoria como roadmap; el tribunal valora más una arquitectura razonada que un MVP a medias.

---

## 3. Estado objetivo (Phase 8 — Producto SaaS)

### 3.1. Modelo de datos nuevo

Tres tablas nuevas en Supabase, todas con RLS:

```sql
-- Conector instalado por un tenant
CREATE TABLE tenant_connections (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  provider      text NOT NULL,        -- 'gmail' | 'gdrive' | 'slack' | 'outlook' | 'sharepoint' | 'dropbox'
  display_name  text NOT NULL,        -- "Gmail de legal@delos.es"
  account_email text,                 -- email/identificador de la cuenta conectada
  status        text NOT NULL DEFAULT 'active', -- 'active' | 'paused' | 'revoked' | 'error'
  created_at    timestamptz DEFAULT now(),
  created_by    uuid REFERENCES users(id),
  last_sync_at  timestamptz,
  last_error    text
);

-- Credenciales OAuth cifradas (separadas para poder rotar/revocar sin tocar la fila padre)
CREATE TABLE tenant_connection_secrets (
  connection_id    uuid PRIMARY KEY REFERENCES tenant_connections(id) ON DELETE CASCADE,
  access_token     bytea NOT NULL,    -- cifrado con pgcrypto + key del vault
  refresh_token    bytea,             -- cifrado
  token_expires_at timestamptz,
  scopes           text[] NOT NULL,
  updated_at       timestamptz DEFAULT now()
);

-- Regla de ingesta: "de esta conexión, esto va a este space"
CREATE TABLE ingestion_rules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id   uuid NOT NULL REFERENCES tenant_connections(id) ON DELETE CASCADE,
  space_id        uuid NOT NULL REFERENCES spaces(id),
  source_selector jsonb NOT NULL,     -- { "type": "gmail_label", "value": "korio/ingesta" }
                                       -- { "type": "gdrive_folder", "value": "0AFx...", "recursive": true }
                                       -- { "type": "slack_channel", "value": "C0123456" }
  filters         jsonb,              -- { "min_size_kb": 5, "mime_whitelist": ["pdf","docx"], "from_domains": ["delos.es"] }
  enabled         boolean DEFAULT true,
  created_at      timestamptz DEFAULT now()
);

-- Cursor de sincronización (para no reingerir lo ya procesado)
CREATE TABLE ingestion_cursors (
  rule_id          uuid PRIMARY KEY REFERENCES ingestion_rules(id) ON DELETE CASCADE,
  cursor_value     text,              -- historyId (Gmail), pageToken (Drive), channel ts (Slack)
  last_run_at      timestamptz,
  last_items_seen  int DEFAULT 0
);
```

RLS: todas las tablas con política `tenant_id = current_tenant()`. Los secretos jamás se exponen al cliente — solo el backend con `service_role` los descifra para usarlos.

### 3.2. Cifrado de tokens

- **Key management**: clave maestra en variable de entorno (`KORIO_VAULT_KEY`), backupeada en gestor de secretos (1Password / AWS Secrets Manager en producción).
- **Cifrado**: `pgcrypto` con `pgp_sym_encrypt(token, key)`. Alternativa: cifrar en aplicación con `cryptography.fernet` para no exponer la key al servidor de BD.
- **Rotación**: vista materializada que recifra con nueva key; refresh tokens se renuevan en cada `refresh_grant`.

### 3.3. Flujo de OAuth (ejemplo: Google)

```
1. Usuario admin del tenant entra en /ui/connections
2. Click "Conectar Gmail" → abre popup OAuth Google
   GET https://accounts.google.com/o/oauth2/v2/auth
       ?client_id=<KORIO_GOOGLE_CLIENT_ID>
       &redirect_uri=https://korio.es/oauth/google/callback
       &response_type=code
       &access_type=offline       ← clave para obtener refresh_token
       &prompt=consent             ← fuerza refresh_token aunque ya hubiera consentido
       &scope=https://www.googleapis.com/auth/gmail.readonly
              https://www.googleapis.com/auth/drive.readonly
       &state=<jwt firmado con tenant_id + user_id + nonce>
3. Google → callback con ?code=...
4. Backend canjea code por (access_token, refresh_token, expires_in)
5. Inserta en tenant_connections + tenant_connection_secrets (cifrado)
6. Lanza primera sincronización (full backfill o desde cursor inicial)
```

**Verificación de la app:** para usar scopes sensibles (Gmail readonly es "restricted"), Google exige:
- Pantalla de consentimiento publicada
- Política de privacidad pública en korio.es
- Verificación de dominio
- Auditoría CASA (anual, ~$15k para tier 2) si quieres salir de "test users" (límite 100)

Plan realista: **lanzar en "test users" para los primeros 10-20 clientes piloto**, iniciar verificación en paralelo (3-6 meses), después abrir.

### 3.4. Mecanismos de ingesta

| Proveedor | Mecanismo preferido | Alternativa | Notas |
|---|---|---|---|
| Gmail | `users.watch` + Pub/Sub | Polling `users.history.list` cada 5 min | Watch caduca a 7 días, hay que renovar |
| Google Drive | `changes.watch` (webhook) | Polling `changes.list` cada 10 min | Webhook caduca a 7 días |
| Slack | Events API (webhook) | — | Necesita endpoint público + signing secret |
| Outlook / M365 | Microsoft Graph subscriptions (webhook) | Polling delta queries | Subscription caduca a 3 días |
| SharePoint | Graph subscriptions | Polling | Idem |
| Dropbox | Webhooks | Polling `list_folder/continue` | — |

**Decisión por defecto:** webhooks cuando el proveedor los ofrece, polling como fallback. Cron de renovación de subscriptions diario.

### 3.5. Arquitectura de procesamiento

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Provider events │ ──> │  Webhook     │ ──> │  Job queue      │
│ (Gmail/Drive/…) │     │  endpoints   │     │  (Redis/PG)     │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                       │
                              ┌────────────────────────┴────────┐
                              │  Worker pool (Python/Celery)    │
                              │  1. Descarga fichero            │
                              │  2. Resuelve rule → space       │
                              │  3. Llama POST /upload interno  │
                              │  4. Update cursor               │
                              └─────────────────────────────────┘
```

n8n puede ser el sustrato de los workers en la fase inicial (rápido, visual), pero a escala conviene worker propio en Python para tener trazabilidad, retries con backoff exponencial y observabilidad fina.

### 3.6. Onboarding UX

Pantalla `/ui/connections` por tenant admin:

```
┌────────────────────────────────────────────────────┐
│ Conexiones de Delos                                │
├────────────────────────────────────────────────────┤
│ 🟢 Gmail · legal@delos.es        [Reglas] [Pausar] │
│    └─ Label "korio/ingesta" → Space Legal          │
│                                                    │
│ 🟢 Google Drive · admin@delos.es                   │
│    └─ Carpeta "Actas" → Space RRHH                 │
│    └─ Carpeta "Contratos" → Space Legal            │
│                                                    │
│ ⚪ Slack                          [+ Conectar]      │
│ ⚪ Outlook                        [+ Conectar]      │
│ ⚪ Dropbox                        [+ Conectar]      │
└────────────────────────────────────────────────────┘
```

Cada regla es: "desde esta fuente (label/carpeta/canal), envía a este space, con estos filtros".

### 3.7. RLS extendido

El sistema actual tiene 2 capas (aplicación + Postgres) sobre `tenant_id + space_id`. Con conectores añadimos:

- **Tercera capa de origen**: cada `document` tendrá `source_connection_id` y `source_rule_id` opcional. Permite auditar "¿de dónde vino este documento?" y revocar masivamente al desconectar (`DELETE FROM documents WHERE source_connection_id = ?` o marcarlos como huérfanos según preferencia del cliente).
- **Aislamiento de secretos**: `tenant_connection_secrets` solo accesible vía `service_role` (no API pública).

---

## 4. ¿MCP server entrante o saliente?

Importante separar dos cosas que el SESSION-STARTER mezcla:

| Dirección | Qué es | Estado |
|---|---|---|
| **MCP saliente (Korio como server)** | Exponer Korio a Claude Desktop / ChatGPT / n8n como tools (`search_knowledge_base`, `ingest_document`, …) | Es la **Phase 7.3** prevista. No resuelve ingesta entrante. |
| **MCP entrante (Korio como client)** | Que Korio use MCP servers de Gmail/Drive/Slack para leer datos | **No es la solución a multi-tenant**. Los MCP servers existentes (incluido el de Anthropic) son single-user; el OAuth lo gestiona el cliente MCP, no escala a N tenants compartiendo una instancia. |

**Conclusión:** para ingesta multi-tenant configurable, **MCP no es el camino**. Hay que implementar OAuth nativo por proveedor. MCP saliente sigue siendo valioso para la Phase 7.3 (distribución de Korio a power-users con Claude Desktop).

---

## 5. Seguridad y cumplimiento

- **Scopes mínimos**: solo `readonly` salvo que el cliente quiera "respond from Korio" (no en Phase 8).
- **Logs de acceso**: cada llamada a API externa con `connection_id` registrada en `audit_log`.
- **Revocación**: botón "Desconectar" → revoca refresh_token contra el proveedor + soft-delete de la conexión + decisión del cliente sobre los docs ya ingeridos (mantener/borrar).
- **GDPR**: docs siguen alojados en Frankfurt (Supabase EU). Los proveedores acceden vía OAuth, no replicamos buzones enteros — solo lo que la regla permite.
- **Token leak**: si se compromete `KORIO_VAULT_KEY`, todos los tokens deben rotarse. Plan: las conexiones marcan `status='revoked'` y se fuerza reconexión.

---

## 6. Coste y plazos estimados (Phase 8)

| Bloque | Esfuerzo | Notas |
|---|---|---|
| Modelo de datos + migraciones + RLS | 3-4 días | Diseño + tests aislamiento |
| OAuth Google (Gmail + Drive) | 1 semana | Incluye UI conexión, callback, refresh, primer sync |
| OAuth Slack | 4 días | Más simple (no necesita verificación tan estricta para tier inicial) |
| OAuth Microsoft (Outlook + SharePoint) | 1 semana | Graph API tiene curva propia |
| Worker pool + retries + observabilidad | 1 semana | Saltar n8n y montar Celery/RQ |
| UI de conexiones y reglas | 1 semana | Pantalla `/ui/connections` + tests |
| Verificación Google CASA tier 2 | 3-6 meses | Externo, en paralelo |
| Pen-test / revisión seguridad | 1 semana | Antes de salir de beta |

**Total ingeniería: ~6 semanas de trabajo concentrado** + 3-6 meses de verificación Google en paralelo. Razonable para el primer trimestre post-defensa si Korio se convierte en proyecto real.

---

## 7. Qué hacemos hoy (Phase 7.2) sabiendo todo esto

1. Los workflows n8n hardcodean tenant + space — pero **estructuran la llamada a `/upload` igual que lo haría el worker futuro** (mismo payload, mismos headers, mismo error handling).
2. Añadimos campo opcional `source_metadata` en `documents` (JSON) — los workflows n8n ya rellenan `{ "via": "n8n_gmail", "label": "korio/ingesta", "message_id": "..." }`. Cuando llegue Phase 8 los workers nativos meten lo mismo.
3. La demo del TFM muestra el flujo entero (correo llega → 30s después está consultable en `/ui` con respuesta del RAG). El tribunal no nota que tenant/space están hardcodeados.
4. En la memoria del TFM, este documento es el capítulo "Arquitectura objetivo · Producto SaaS post-defensa".

---

## 8. Decisiones abiertas (a cerrar antes de Phase 8)

- [ ] ¿`pgcrypto` o cifrado en aplicación con Fernet? Probable: aplicación, por separation of concerns.
- [ ] ¿Worker propio (Celery) o seguir con n8n para casos simples? Probable: ambos — n8n para integraciones rápidas de cliente, worker propio para los conectores oficiales.
- [ ] ¿Cómo se cobra? Por conexión activa, por GB ingerido, por consulta. Probable: tier flat con límites por SKU.
- [ ] ¿Se permite que un mismo documento entre por dos rules a dos spaces distintos? Probable: sí, deduplicar por hash y materializar en ambos spaces con doble RLS.
- [ ] ¿Qué pasa cuando se desconecta? ¿Borrar docs, marcar huérfanos, archivar? Probable: opción del cliente al desconectar.

---

*Documento vivo · iteración inicial 10 junio 2026 · revisar antes de arrancar Phase 8 post-defensa TFM*
