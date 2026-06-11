"""
Agente Supervisor (Human-in-the-Loop) — gestión de conflictos que el Árbitro
no puede resolver autónomamente.

Notifica al administrador del tenant vía email (workflow n8n `Korio — HITL email`
ya en producción), recoge la decisión humana, la codifica como política
reutilizable (Phase 8) y la envía al Curador como USER_DECISION.

PEAS (Entregable 3):
- Performance: claridad de presentación del conflicto al usuario, tasa de
  decisiones sin posterior corrección.
- Environment: informe ambiguo del Árbitro, canal email con el usuario, base de
  políticas (futuro).
- Actuators: envío de notificación al usuario, recepción y validación de su
  decisión, emisión de USER_DECISION al Curador.
- Sensors: receptor de señales del Árbitro, canal de entrada del usuario, reloj
  para timeouts (gestionado por `src/escalation.py`).

Arquetipo: Reactivo orientado a comunicación. La inteligencia vive en el usuario,
no en el agente — el Supervisor es mediador.
"""

from __future__ import annotations

from typing import Optional

from agents.base import BaseAgent
from agents.events import Agent, EventType


class Supervisor(BaseAgent):
    """Mediador entre el sistema y el administrador humano del tenant."""

    role: Agent = Agent.SUPERVISOR

    def record_user_decision(
        self,
        *,
        review_id: str,
        document_id: Optional[str],
        resolution: str,
        applied_by: str = "human",
    ) -> None:
        """
        Emite USER_DECISION cuando el administrador responde al email HITL.

        La gestión de timeouts (recordatorios cada 3/7/14 días + auto-cierre a 21)
        vive en `src/escalation.py` y se dispara desde el workflow n8n
        `Korio — Cron de escalada HITL`. Cada paso de escalada también podría
        emitir un evento (Phase 8) para visibilidad granular.
        """
        self._emit(
            EventType.USER_DECISION,
            document_id=document_id,
            payload={
                "review_id":  review_id,
                "resolution": resolution,
                "applied_by": applied_by,
            },
        )
