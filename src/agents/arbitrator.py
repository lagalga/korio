"""
Agente Árbitro Cronológico — resolución automática de conflictos.

Recibe los conflictos con resolución posible y aplica una jerarquía de criterios:
primero prevalencia temporal (doc más reciente), después jerarquía de autoridad
(authority_weight), después especificidad (norma más específica). Si ningún
criterio es concluyente, escala al Supervisor.

PEAS (Entregable 3):
- Performance: tasa de resoluciones correctas, umbral de confianza calibrado.
- Environment: informe del Detector, base de metadatos, reglas de jerarquía.
- Actuators: emisión de RESOLUTION_PROPOSED al Curador o al Supervisor según confianza.
- Sensors: lector del informe del Detector, acceso a metadatos (fecha, autoridad).

Arquetipo: Basado en objetivos. Razona sobre alternativas y elige la que cumple
el objetivo (resolver). Si nada cumple → escala.

Nota: en la implementación actual de Korio, la lógica de auto-resolución vive
embebida en `src/conflict_detector.py`. Esta clase es la fachada agéntica que
expone el rol; la separación física del código se podrá hacer en una iteración
posterior si interesa (refactor incremental).
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.events import Agent, EventType


class Arbitrator(BaseAgent):
    """Aplica reglas de resolución automática o escala al Supervisor."""

    role: Agent = Agent.ARBITRATOR

    def propose_resolution(
        self,
        *,
        document_id: str,
        conflict_summary: dict,
        escalate: bool,
        reason: str = "",
    ) -> None:
        """
        Emite RESOLUTION_PROPOSED indicando si la resolución va al Curador (auto)
        o al Supervisor (HITL).

        Esta señal se usa hoy implícitamente — `conflict_detector` aplica la
        resolución directamente. Exponemos el evento explícito para que el
        Supervisor pueda observar la traza en `pipeline_events`.
        """
        self._emit(
            EventType.RESOLUTION_PROPOSED,
            document_id=document_id,
            payload={
                "escalate":         escalate,
                "reason":           reason,
                "conflict_summary": conflict_summary,
            },
        )
