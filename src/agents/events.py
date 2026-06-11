"""
Bus de eventos del pipeline multi-agente de Korio.

Cada transición lógica del pipeline (Ingestor → Detector → Arbitrator →
Supervisor → Curator) emite un evento estructurado vía `emit()`:

  1) INSERT en `pipeline_events` — audit trail síncrono, garantía persistente.
     Esta tabla es la fuente de verdad: reconstruir cualquier ciclo se hace
     con `SELECT * FROM pipeline_events WHERE operation_id = ? ORDER BY created_at`.

  2) POST best-effort a un webhook n8n (env `KORIO_EVENT_WEBHOOK_URL`) para
     observabilidad en vivo. Timeout corto (500 ms). Si n8n cae el sistema
     sigue funcionando — el webhook es fire-and-forget.

El `operation_id` es un UUID que se genera al inicio de cada ciclo (típicamente
en el Ingestor cuando llega un documento nuevo o el Detector cuando detecta un
conflicto en query-time) y se propaga a todos los agentes que participan en
ese ciclo.

Diseño:
- `emit()` NO debe lanzar excepciones que rompan el pipeline. Cualquier error
  se loguea y se traga: la traza es importante, pero no debe ser un punto de
  fallo crítico.
- El audit en BD es síncrono (en el mismo proceso, ~50 ms). Aceptable.
- El webhook es asíncrono best-effort (timeout 500 ms). Si tarda más, se corta.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ─── Tipos de evento y agentes ──────────────────────────────────────────────

class EventType(str, Enum):
    """
    Tipos de evento del pipeline. Cualquier nuevo tipo debe añadirse también
    al CHECK constraint de `pipeline_events.event_type` (migración SQL).
    """
    DOCUMENT_INGESTED   = "DOCUMENT_INGESTED"
    DOCUMENT_CLEARED    = "DOCUMENT_CLEARED"
    CONFLICT_DETECTED   = "CONFLICT_DETECTED"
    RESOLUTION_PROPOSED = "RESOLUTION_PROPOSED"
    USER_DECISION       = "USER_DECISION"
    CORPUS_UPDATED      = "CORPUS_UPDATED"
    GRAPH_SYNCED        = "GRAPH_SYNCED"
    GRAPH_SYNC_FAILED   = "GRAPH_SYNC_FAILED"
    INGEST_FAILED       = "INGEST_FAILED"


class Agent(str, Enum):
    """Rol agéntico emisor del evento."""
    INGESTOR   = "ingestor"
    DETECTOR   = "detector"
    ARBITRATOR = "arbitrator"
    SUPERVISOR = "supervisor"
    CURATOR    = "curator"
    SYSTEM     = "system"


# ─── Configuración del webhook a n8n ────────────────────────────────────────

KORIO_EVENT_WEBHOOK_URL = os.getenv("KORIO_EVENT_WEBHOOK_URL", "")
KORIO_EVENT_WEBHOOK_TIMEOUT_S = float(os.getenv("KORIO_EVENT_WEBHOOK_TIMEOUT_S", "0.5"))


# ─── API pública ────────────────────────────────────────────────────────────

def new_operation_id() -> str:
    """
    Genera un UUID nuevo para correlacionar todos los eventos de un ciclo.
    Llamar UNA vez al inicio del ciclo (típicamente en el Ingestor) y propagar.
    """
    return str(uuid.uuid4())


def emit(
    event_type: EventType,
    *,
    source_agent: Agent,
    tenant_id: str,
    operation_id: str,
    document_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    """
    Emite un evento al bus del pipeline.

    Args:
        event_type:   tipo de evento del enum EventType.
        source_agent: rol del agente que lo emite.
        tenant_id:    UUID del tenant (RLS).
        operation_id: UUID del ciclo (correlaciona todos sus eventos).
        document_id:  UUID del documento implicado (opcional).
        payload:      JSON con datos específicos del evento (opcional).

    Esta función:
      1) Inserta el evento en `pipeline_events` (audit persistente).
      2) Hace POST best-effort al webhook de n8n si está configurado.

    NUNCA lanza excepciones al caller: cualquier error se loguea. La emisión
    de eventos es observabilidad, no parte del camino crítico del pipeline.
    """
    payload = payload or {}
    event_value  = event_type.value  if isinstance(event_type, Enum)  else event_type
    agent_value  = source_agent.value if isinstance(source_agent, Enum) else source_agent

    # 1) Audit persistente en pipeline_events
    try:
        # Import perezoso: evita ciclo con db.py al cargar el módulo
        from db import get_supabase_client
        db = get_supabase_client()
        db.client.table("pipeline_events").insert({
            "operation_id": operation_id,
            "event_type":   event_value,
            "source_agent": agent_value,
            "tenant_id":    tenant_id,
            "document_id":  document_id,
            "payload":      payload,
        }).execute()
    except Exception:
        logger.exception(
            "Error persistiendo evento %s/%s en pipeline_events (operation_id=%s)",
            agent_value, event_value, operation_id,
        )

    # 2) Webhook best-effort a n8n
    if not KORIO_EVENT_WEBHOOK_URL:
        return
    body = {
        "operation_id": operation_id,
        "event_type":   event_value,
        "source_agent": agent_value,
        "tenant_id":    tenant_id,
        "document_id":  document_id,
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "payload":      payload,
    }
    try:
        requests.post(
            KORIO_EVENT_WEBHOOK_URL,
            json=body,
            timeout=KORIO_EVENT_WEBHOOK_TIMEOUT_S,
        )
    except Exception:
        # Fire-and-forget: no romper el pipeline si n8n no responde
        logger.debug(
            "Webhook n8n no respondió para evento %s (operation_id=%s) — sigo",
            event_value, operation_id,
        )


def trace(operation_id: str) -> list[dict]:
    """
    Devuelve todos los eventos de un ciclo ordenados cronológicamente.
    Útil para reconstruir el flujo completo de un documento o conflicto.
    """
    from db import get_supabase_client
    db = get_supabase_client()
    rows = (
        db.client.table("pipeline_events")
        .select("*")
        .eq("operation_id", operation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return rows.data or []
