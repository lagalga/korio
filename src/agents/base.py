"""
Clase base para los agentes del pipeline de Korio.

Cada agente:
  - Tiene un rol (de `Agent`) que identifica su emisor en `pipeline_events`.
  - Recibe siempre `operation_id` y `tenant_id` para propagar la traza.
  - Encapsula la emisión de eventos vía `self._emit(...)`.

La lógica concreta de cada agente vive en los módulos `src/conflict_detector.py`,
`src/escalation.py`, `src/ingest.py`, etc. Las clases son la **fachada agéntica**
que refleja el diseño del Entregable 3 — no una reimplementación.
"""

from __future__ import annotations

from typing import Optional

from agents.events import emit, EventType, Agent


class BaseAgent:
    """
    Agente base. Subclasear especificando el rol.

    Subclases típicas:
      - Ingestor:   procesa un documento nuevo → DOCUMENT_INGESTED
      - Detector:   compara contra corpus → CONFLICT_DETECTED | DOCUMENT_CLEARED
      - Arbitrator: resuelve auto-conflictos → RESOLUTION_PROPOSED
      - Supervisor: gestiona HITL → USER_DECISION
      - Curator:    aplica decisiones → CORPUS_UPDATED
    """

    role: Agent = Agent.SYSTEM

    def __init__(self, *, tenant_id: str, operation_id: str) -> None:
        self.tenant_id    = tenant_id
        self.operation_id = operation_id

    def _emit(
        self,
        event_type: EventType,
        *,
        document_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Envoltorio para que cada agente emita eventos con su propio rol."""
        emit(
            event_type,
            source_agent=self.role,
            tenant_id=self.tenant_id,
            operation_id=self.operation_id,
            document_id=document_id,
            payload=payload or {},
        )
