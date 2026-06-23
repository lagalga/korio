"""
Servidor MCP de Korio — Phase 7.3.

Expone Korio como servidor MCP sobre HTTP+SSE para que clientes como Claude
Desktop, ChatGPT o n8n puedan invocar el RAG, listar conflictos pendientes y
descubrir espacios accesibles. La identidad multi-tenant se resuelve desde una
API key (header `X-Korio-MCP-Key`) y se propaga a las tools vía contextvars
para que el early binding de RLS siga funcionando sin cambios.

Tools expuestas:
  - search_knowledge_base(query, limit)  — RAG híbrido vector+grafo
  - list_pending_conflicts()             — gobernanza activa, HITL pendiente
  - list_spaces()                        — espacios del usuario autenticado

Diseño:
  - Una API key = un (user_id, tenant_id). Se guarda solo SHA-256 en BD.
  - Toda la lógica delega en los módulos existentes (`search`, `db`) — no se
    duplica nada, solo se reexpone vía MCP.
  - El servidor se monta en FastAPI bajo `/mcp` (ver api/server.py).

Phase 8: sustituir API keys por OAuth 2.1 con tokens de corta vida.
"""

import os
import sys
import hashlib
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional, Tuple

# Reaprovecha el path setup que api/server.py hace al arrancar, pero lo
# repetimos por si este módulo se importa en aislamiento (tests, scripts).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

logger = logging.getLogger(__name__)


# Hosts permitidos en el header `Host` del request HTTP. El SDK MCP trae
# protección anti-DNS-rebinding que por defecto solo acepta localhost; en
# producción detrás de nginx el Host llega como `korio.es`, así que hay que
# declararlo. Se puede ampliar vía env `KORIO_MCP_ALLOWED_HOSTS` (coma-separado).
_default_allowed_hosts = ["korio.es", "www.korio.es", "127.0.0.1", "localhost"]
_env_hosts = os.getenv("KORIO_MCP_ALLOWED_HOSTS", "")
_allowed_hosts = [h.strip() for h in _env_hosts.split(",") if h.strip()] or _default_allowed_hosts

# `allowed_origins` aplica solo si el cliente envía `Origin` (navegadores).
# Para Claude Desktop / curl no es relevante, pero lo dejamos coherente.
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=_allowed_hosts,
    allowed_origins=[f"https://{h}" for h in _allowed_hosts if "." in h],
)


# ─── Identidad del request (contextvars) ────────────────────────────────────
#
# El middleware HTTP de FastAPI resuelve la API key → (user_id, tenant_id) y
# rellena estos contextvars para la duración del request. Las tools los leen.
# ContextVars son aislados por Task de asyncio, así que requests concurrentes
# no se pisan.

_current_user_id:   ContextVar[Optional[str]] = ContextVar("korio_mcp_user_id",   default=None)
_current_tenant_id: ContextVar[Optional[str]] = ContextVar("korio_mcp_tenant_id", default=None)


def set_current_principal(user_id: str, tenant_id: str) -> None:
    """Llamar desde el middleware una vez resuelta la key."""
    _current_user_id.set(user_id)
    _current_tenant_id.set(tenant_id)


def _require_principal() -> Tuple[str, str]:
    uid = _current_user_id.get()
    tid = _current_tenant_id.get()
    if not uid or not tid:
        # No debería ocurrir: el middleware corta antes con 401. Si llega aquí
        # es bug, no input del usuario, así que lanzamos RuntimeError.
        raise RuntimeError(
            "Tool MCP invocada sin principal autenticado — falta el middleware "
            "de auth o se invocó la tool fuera del request"
        )
    return uid, tid


# ─── Hashing y resolución de keys ───────────────────────────────────────────


def hash_key(plaintext: str) -> str:
    """SHA-256 hex de la API key en texto plano. Es lo único que guardamos."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def resolve_mcp_key(plaintext: str) -> Optional[Tuple[str, str]]:
    """
    Resuelve `X-Korio-MCP-Key` a `(user_id, tenant_id)`.
    Devuelve None si la key es inválida o está revocada.
    Actualiza `last_used_at` de forma best-effort.
    """
    if not plaintext:
        return None
    # Import perezoso: evita inicializar el cliente de Supabase al importar el
    # módulo (rompería tests que no quieran tocar la BD).
    from db import get_supabase_client

    db = get_supabase_client()
    key_hash = hash_key(plaintext)
    try:
        rows = (
            db.client.table("mcp_api_keys")
            .select("user_id, tenant_id, revoked_at")
            .eq("key_hash", key_hash)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Error consultando mcp_api_keys")
        return None

    if not rows.data:
        return None
    row = rows.data[0]
    if row.get("revoked_at"):
        return None

    # Sello de uso — fallo silencioso si Supabase responde mal, no queremos
    # tirar el request por esto.
    try:
        db.client.table("mcp_api_keys").update(
            {"last_used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("key_hash", key_hash).execute()
    except Exception:
        logger.warning("No se pudo actualizar last_used_at de la MCP key")

    return row["user_id"], row["tenant_id"]


# ─── Servidor MCP + tools ───────────────────────────────────────────────────

mcp = FastMCP(
    name="Korio",
    transport_security=_transport_security,
    instructions=(
        "Korio es el cerebro corporativo (RAG multi-tenant) de la empresa. "
        "Usa `search_knowledge_base` para responder preguntas en lenguaje "
        "natural sobre los documentos internos del usuario. Usa "
        "`list_pending_conflicts` para inspeccionar contradicciones "
        "detectadas por la gobernanza activa pendientes de revisión humana. "
        "Usa `list_spaces` para descubrir qué áreas de conocimiento "
        "(departamentos) están disponibles. Todas las llamadas heredan el "
        "(user_id, tenant_id) de la API key del cliente — el aislamiento "
        "multi-tenant y por departamento (RLS) se aplica automáticamente.\n\n"
        "FORMATO DE RESPUESTA OBLIGATORIO para `search_knowledge_base`:\n"
        "  1. Compón UNA frase de respuesta que termine con la cita INLINE "
        "de la fuente PRIMARIA (la de mayor `similarity` en `sources`) en "
        "el formato exacto `[<filename>, similitud <X.XX>]`. Ejemplo: "
        "\"Según la política de RRHH, el personal asalariado tiene una "
        "jornada mínima de 35 horas semanales [R4_convenio.md, similitud "
        "0.63].\"\n"
        "  2. Si el campo `graph_contributed` es `true`, añade al final "
        "una frase breve: \"Esta información proviene del grafo de "
        "conocimiento estructurado (graph_contributed: true).\"\n"
        "  3. Si la fuente primaria tiene `is_disputed: true`, añade "
        "un párrafo `⚠️` indicando que la gobernanza activa detectó una "
        "contradicción sin resolver en esa fuente.\n"
        "  4. Si `has_silent_conflict` es `true`, añade un párrafo final "
        "que empiece por `⚠️ Aviso de la gobernanza:` listando los pares "
        "de `silent_conflicts` con su similitud.\n"
        "La trazabilidad inline es un requisito del producto, no un extra. "
        "NO uses una sección `**Fuentes:**` al final — la cita va inline "
        "junto a la afirmación."
    ),
)


@mcp.tool()
def search_knowledge_base(query: str, limit: int = 5) -> dict:
    """
    Pregunta al knowledge base de la empresa en lenguaje natural.

    Devuelve `answer` sintetizado por el LLM y `sources` con los documentos
    consultados (filename + similitud + is_disputed). El RLS por departamento
    se aplica al user_id autenticado.

    TRAZABILIDAD OBLIGATORIA — Cuando muestres la respuesta al usuario, cita
    SIEMPRE los `sources` al final usando los nombres de fichero. Si alguna
    fuente tiene `is_disputed: true`, indícalo expresamente: significa que la
    gobernanza activa detectó una contradicción aún no resuelta en ese chunk.

    Args:
        query: pregunta en español o inglés.
        limit: número máximo de chunks de contexto (1-10, default 5).
    """
    user_id, tenant_id = _require_principal()
    if limit < 1 or limit > 10:
        limit = 5
    from search import search as run_search

    result = run_search(
        query=query, user_id=user_id, tenant_id=tenant_id, limit=limit
    )
    # Filtramos campos pesados/internos para no inflar la respuesta MCP.
    return {
        "answer":             result.get("answer"),
        "sources":            result.get("sources", []),
        "chunks_used":        result.get("chunks_used", 0),
        "has_context":        result.get("has_context", False),
        "latency_ms":         result.get("latency_ms"),
        "model_used":         result.get("model_used"),
        # Señal explícita de RAG híbrido (vector + grafo). El cliente MCP
        # debe mencionarlo en la respuesta cuando es true (ver instructions).
        "graph_contributed":    result.get("graph_contributed", False),
        # Avisos de gobernanza para que el cliente MCP los muestre al usuario
        "has_conflict":         result.get("has_conflict", False),
        "has_silent_conflict":  result.get("has_silent_conflict", False),
        "silent_conflicts":     result.get("silent_conflicts", []),
    }


@mcp.tool()
def list_pending_conflicts() -> dict:
    """
    Lista contradicciones del knowledge base pendientes de revisión humana
    (HITL). Útil para que un agente externo proponga acciones de gobernanza.
    """
    user_id, tenant_id = _require_principal()
    from db import get_supabase_client

    db = get_supabase_client()
    rows = (
        db.client.table("conflict_reviews")
        .select(
            "id, similarity, resolution, created_at, "
            "new_chunk_id, existing_chunk_id"
        )
        .eq("tenant_id", tenant_id)
        .is_("resolution", "null")
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    items = rows.data or []
    return {"tenant_id": tenant_id, "count": len(items), "conflicts": items}


@mcp.tool()
def list_spaces(include_inactive: bool = False) -> dict:
    """
    Devuelve los espacios (departamentos) accesibles al usuario autenticado.
    Es el "índice" que el cliente puede usar para razonar sobre qué dominios
    puede consultar antes de llamar a search_knowledge_base.

    Args:
        include_inactive: reservado para futuras versiones (Phase 8). Actualmente
            ignorado — solo está declarado para que el schema MCP tenga al menos
            un parámetro y validate `arguments: {}` sin error -32602.
    """
    _ = include_inactive  # silenciar linter; ver docstring
    user_id, tenant_id = _require_principal()
    from db import get_supabase_client

    db = get_supabase_client()
    # JOIN implícito vía PostgREST: trae el space embebido como subrecurso.
    rows = (
        db.client.table("user_spaces")
        .select("space_id, spaces(id, name, tenant_id)")
        .eq("user_id", user_id)
        .execute()
    )
    spaces = []
    for r in rows.data or []:
        s = r.get("spaces") or {}
        # Defensa en profundidad: aunque user_spaces no debería cruzar tenants,
        # filtramos por tenant_id para evitar leaks si hubiera datos sucios.
        if s.get("tenant_id") == tenant_id:
            spaces.append({"id": s["id"], "name": s.get("name")})
    return {
        "user_id":   user_id,
        "tenant_id": tenant_id,
        "count":     len(spaces),
        "spaces":    spaces,
    }


# ASGI app que se monta en FastAPI bajo /mcp (ver api/server.py).
# Expone GET /mcp/sse y POST /mcp/messages/ siguiendo el protocolo MCP SSE.
mcp_sse_app = mcp.sse_app()
