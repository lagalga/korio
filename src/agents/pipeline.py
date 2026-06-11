"""
Orquestador del pipeline multi-agente.

`Pipeline.run_ingest()` es el punto de entrada de alto nivel que instancia los
agentes con un `operation_id` compartido y ejecuta el ciclo completo. Útil para
tests, scripts y para usar el sistema agéntico desde Python sin tocar los
módulos internos.

Para uso interno del backend, `ingest_document()` (en `src/ingest.py`) es
equivalente: ya implementa internamente las 5 fases y emite todos los eventos.
La diferencia es que `Pipeline` expone explícitamente los 5 roles del diseño
del Entregable 3 como objetos manipulables.
"""

from __future__ import annotations

from typing import Optional

from agents.events import new_operation_id
from agents.ingestor   import Ingestor
from agents.detector   import Detector
from agents.arbitrator import Arbitrator
from agents.supervisor import Supervisor
from agents.curator    import Curator


class Pipeline:
    """Instancia los 5 agentes con un operation_id común."""

    def __init__(self, *, tenant_id: str, operation_id: Optional[str] = None) -> None:
        self.tenant_id    = tenant_id
        self.operation_id = operation_id or new_operation_id()

        # Construcción explícita de los 5 roles — refleja el diseño del E3.
        self.ingestor   = Ingestor(tenant_id=tenant_id,   operation_id=self.operation_id)
        self.detector   = Detector(tenant_id=tenant_id,   operation_id=self.operation_id)
        self.arbitrator = Arbitrator(tenant_id=tenant_id, operation_id=self.operation_id)
        self.supervisor = Supervisor(tenant_id=tenant_id, operation_id=self.operation_id)
        self.curator    = Curator(tenant_id=tenant_id,    operation_id=self.operation_id)

    def run_ingest(
        self,
        *,
        file_path: str,
        space_id: str,
        **kwargs,
    ) -> dict:
        """
        Ejecuta el pipeline de ingesta completo. Delega en el Ingestor; el
        propio Ingestor invoca internamente al Detector y al Curator vía
        `ingest_document()`. Devuelve el dict de resultado con `operation_id`
        para inspección.
        """
        return self.ingestor.ingest(file_path=file_path, space_id=space_id, **kwargs)
