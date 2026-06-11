"""
Agente Curador — ejecutor de resoluciones, responsable de la integridad del corpus.

Aplica los cambios decididos por el Árbitro o por el Supervisor: archiva
documentos desplazados, actualiza estados de chunks en el índice vectorial,
sincroniza el grafo de conocimiento y registra cada operación en el log de
auditoría. Es el único agente que **modifica el estado del corpus**.

PEAS (Entregable 3):
- Performance: integridad del corpus tras cada operación, trazabilidad completa.
- Environment: índice vectorial, base de metadatos, almacén de documentos archivados, log.
- Actuators: archivo de documentos desplazados, actualización de metadatos de vigencia,
  reindexación de fragmentos afectados, escritura del evento CORPUS_UPDATED.
- Sensors: receptor de decisiones del Árbitro y del Supervisor.

Arquetipo: Basado en utilidad. Optimiza el estado del corpus según la resolución
recibida, minimizando el riesgo de inconsistencia transitoria.

Nota: la mayor parte de la lógica de aplicación de cambios vive en
`src/conflict_detector._apply_resolution()` y en el cierre del ciclo de
ingesta. Esta clase expone la emisión explícita de CORPUS_UPDATED para cerrar
cualquier ciclo de forma trazable.
"""

from __future__ import annotations

from typing import Optional

from agents.base import BaseAgent
from agents.events import Agent, EventType


class Curator(BaseAgent):
    """Ejecutor de resoluciones, garantía de integridad del corpus."""

    role: Agent = Agent.CURATOR

    def close_cycle(
        self,
        *,
        document_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """
        Emite CORPUS_UPDATED para cerrar un ciclo y dejar constancia de que el
        corpus quedó en estado consistente tras esta operación.
        """
        self._emit(
            EventType.CORPUS_UPDATED,
            document_id=document_id,
            payload=payload or {},
        )
