# Korio como servidor MCP — Phase 7.3

> Capítulo de la memoria TFM: "Korio como producto SaaS — exposición vía Model Context Protocol".

## Por qué un MCP server

Korio ya tiene tres puntos de entrada útiles:

1. **Chat UI propia** (`korio.es/ui`) — el demo "de cara".
2. **Workflows n8n** (Gmail, Drive, Slack `/korio`) — la ingesta y consulta automatizada.
3. **API REST + Swagger** — el contrato técnico.

Pero los tres son específicos: la UI es nuestra; los workflows son scripts cerrados; la API REST requiere que el cliente sepa montar embeddings + auth + RLS por su cuenta. **El Model Context Protocol (MCP) resuelve la última milla**: cualquier LLM con cliente MCP (Claude Desktop, ChatGPT, Cursor, n8n, agentes propios) puede descubrir las "tools" de Korio y llamarlas en lenguaje natural sin acoplarse a la API.

El mensaje TFM es directo: *Korio no es solo una app de chat — es **infraestructura RAG conectable** para el ecosistema agéntico.*

## Decisiones de diseño

| Punto | Decisión | Alternativas descartadas |
|---|---|---|
| Transporte | **HTTP + SSE** mediante `FastMCP.sse_app()` montado en FastAPI bajo `/mcp` | stdio (solo local), Streamable HTTP (más nuevo, menos clientes compatibles aún) |
| Auth | **API key por usuario** en header `X-Korio-MCP-Key`. SHA-256 en BD | OAuth 2.1 (Phase 8 — requiere flow de consent + tokens cortos) |
| Multi-tenancy | Una key = un `(user_id, tenant_id)`. Las tools propagan vía `ContextVar`. El RLS existente se reutiliza sin cambios | Pasar `user_id` como argumento de cada tool (el cliente podría falsearlo) |
| Tools expuestas | 3 mínimas y demostrables: `search_knowledge_base`, `list_pending_conflicts`, `list_spaces` | `ingest_document(url)` queda fuera — ya lo cubren Gmail/Drive con `source_metadata` |
| Librería | SDK oficial `mcp` (Anthropic), `FastMCP` para el azúcar | `fastmcp` third-party (otra capa más) |

## Arquitectura

```
Cliente MCP                  FastAPI (api/server.py)             Korio internals
─────────────                ──────────────────────             ─────────────────
                                                                 
Claude Desktop ──HTTP+SSE──►  Middleware                          
  o ChatGPT       (X-Korio-    mcp_auth_middleware  ──resolve──►  mcp_api_keys
  o n8n           MCP-Key)     │                       (BD)       (SHA-256)
                                ▼ set_current_principal           
                                                                  
                              app.mount('/mcp',                   
                                mcp_sse_app)        ──delegates──►  FastMCP tool
                                                                    │
                                                                    ├─ search_knowledge_base
                                                                    │   └─► src/search.py (RAG vector+grafo+RLS)
                                                                    ├─ list_pending_conflicts
                                                                    │   └─► supabase: conflict_reviews
                                                                    └─ list_spaces
                                                                        └─► supabase: user_spaces ⋈ spaces
```

### Flujo de auth

1. Cliente abre `GET /mcp/sse` con header `X-Korio-MCP-Key: korio_<token>`.
2. Middleware en `api/server.py` calcula SHA-256 → busca en `mcp_api_keys`.
3. Si existe y no está revocada: `set_current_principal(user_id, tenant_id)` en contextvars + refresca `last_used_at`.
4. El sub-app SSE de FastMCP procesa la conexión normalmente.
5. Cuando el cliente envía un mensaje en `POST /mcp/messages/`, el mismo middleware vuelve a validar (cada request lleva la key); la tool lee el principal del contextvar.
6. Las tools delegan en los módulos existentes (`search.py`, `db.py`) — la lógica de RLS no cambia.

## Esquema de la tabla `mcp_api_keys`

Ver `supabase/migrations/010_mcp_api_keys.sql`:

```sql
CREATE TABLE mcp_api_keys (
  key_hash      TEXT PRIMARY KEY,           -- SHA-256 hex; nunca guardamos plaintext
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,              -- alias humano ("Claude Desktop laptop berto")
  created_at    TIMESTAMPTZ DEFAULT now(),
  last_used_at  TIMESTAMPTZ,                -- best-effort touch en cada uso
  revoked_at    TIMESTAMPTZ                 -- soft delete
);
```

## Gestión operativa

Crear, listar y revocar keys desde el VPS:

```bash
ssh korio-vps
cd /root/korio && source .venv/bin/activate

# Crear key para el admin de Delos
python scripts/mcp_create_key.py create \
  --user-id   a1000000-0000-0000-0000-000000000001 \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --name "Claude Desktop laptop berto"

# Salida (UNA SOLA VEZ):
#   X-Korio-MCP-Key: korio_xRq8...long_token...

# Listar
python scripts/mcp_create_key.py list --tenant-id a0000000-...

# Revocar por prefijo del hash
python scripts/mcp_create_key.py revoke --hash-prefix a1b2c3
```

## Cómo conectar Claude Desktop

Claude Desktop (a fecha de junio 2026) **no soporta MCP por SSE/HTTP directamente** en su `claude_desktop_config.json` — solo stdio. Para conectar un servidor remoto se usa el puente `mcp-remote` (npm), que arranca un proceso local stdio y traduce a SSE contra `korio.es`.

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "korio": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://korio.es/mcp/sse",
        "--header",
        "X-Korio-MCP-Key:korio_<tu_token>"
      ]
    }
  }
}
```

Detalles:
- El header va **sin espacio** tras los dos puntos: `X-Korio-MCP-Key:korio_...`. Si se pone con espacio, npx puede partirlo mal al parsear `argv`.
- Requiere Node.js instalado en el equipo.
- La primera vez `npx` descarga `mcp-remote` (~5 s).

Reiniciar Claude Desktop completamente (⌘Q en macOS). En *Settings → Developer → Local MCP servers* debe aparecer `korio` con estado verde, y en el chat las tools `search_knowledge_base`, `list_pending_conflicts` y `list_spaces` quedan disponibles como botones.

Cuando Claude Desktop publique soporte nativo de remote MCP servers (vía Connectors con OAuth), Phase 8 sustituirá `mcp-remote` por el flow OAuth 2.1 sin necesidad de proceso local.

## Cómo invocar desde curl (debug)

```bash
# Abre el stream SSE (queda colgado mostrando eventos)
curl -N -H "X-Korio-MCP-Key: korio_..." https://korio.es/mcp/sse

# En otra terminal, los mensajes JSON-RPC del protocolo MCP van por POST.
# El framework FastMCP los gestiona; no es habitual debuggearlos a mano.
```

## Tools expuestas

### `search_knowledge_base(query: str, limit: int = 5) → dict`

Pregunta al RAG híbrido (vector + grafo) con la identidad del principal.

Respuesta:
```jsonc
{
  "answer":      "La política de RRHH exige jornadas mínimas de 35 horas/semana...",
  "sources":     [{"filename": "delos_politica_rrhh.md", "similarity": 0.82}, ...],
  "chunks_used": 4,
  "has_context": true,
  "latency_ms":  1037,
  "model_used":  "mistral_api/mistral-small-latest"
}
```

### `list_pending_conflicts() → dict`

Conflictos del tenant pendientes de revisión humana (HITL no resuelto). Útil para que un agente externo proponga acciones de cierre.

### `list_spaces() → dict`

Devuelve los espacios accesibles al usuario actual. Es el "índice" que un agente puede usar para razonar sobre dominios antes de buscar.

## Limitaciones actuales y plan Phase 8

| Limitación | Mitigación Phase 8 |
|---|---|
| Auth por API key (no caducan automáticamente) | OAuth 2.1 con tokens de corta vida + refresh |
| `ingest_document` no expuesta como tool | Endpoint dedicado con flow de subida + cuotas |
| No hay rate limit por key | Token bucket en middleware + telemetría |
| Auditoría limitada (`last_used_at` y nada más) | Tabla `mcp_audit_log` con cada llamada + parámetros (PII-redacted) |
| No hay descubrimiento de catálogo (qué tenants/spaces) | Tool `whoami` que devuelva el perfil completo del principal |

## Mensaje para la memoria TFM

> Phase 7.3 cierra el ciclo "Korio como producto SaaS conectable": el mismo RAG multi-tenant que sirve la UI de korio.es se expone vía MCP al ecosistema agéntico (Claude Desktop, ChatGPT, n8n, agentes propios). La autenticación por API key con SHA-256 + ContextVar reaprovecha el early binding de RLS sin duplicar código. La capa de seguridad realmente productizable (OAuth 2.1, rate limit, auditoría) queda diseñada como Phase 8 en este mismo documento.
