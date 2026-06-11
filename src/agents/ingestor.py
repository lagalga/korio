"""
Agente Ingestor — punto de entrada del pipeline.

Recibe un documento nuevo, extrae sus metadatos, lo vectoriza y lo persiste
atómicamente en el corpus (vía RPC `ingest_document_atomic`). No toma decisiones
sobre el contenido — cataloga y delega al Detector.

PEAS (Entregable 3):
- Performance: precisión en extracción de metadatos, latencia de procesamiento.
- Environment: filesystem entrada, base de metadatos, índice vectorial.
- Actuators: escritura en BD, generación/almacenamiento de embeddings, señal al Detector.
- Sensors: monitor de directorio, parser multiformat (PDF/DOCX/TXT), extractor de metadatos.

Arquetipo: Reactivo basado en modelo. No planifica; reacciona a la llegada de un doc.
"""

from __future__ import annotations

from typing import Optional

from agents.base import BaseAgent
from agents.events import Agent


class Ingestor(BaseAgent):
    """Procesa un documento nuevo y lo persiste atómicamente."""

    role: Agent = Agent.INGESTOR

    def ingest(
        self,
        file_path: str,
        space_id: str,
        document_id: Optional[str] = None,
        source_type: str = "manual",
        authority_weight: int = 5,
        anonymize: bool = True,
        display_filename: Optional[str] = None,
        source_metadata: Optional[dict] = None,
    ) -> dict:
        """
        Ejecuta el pipeline completo de ingesta. Delega en `ingest_document()`
        que ya orquesta las 5 fases (IO externa → dedupe → RPC atómico → grafo
        post-commit → detección de conflictos).

        El `operation_id` del agente se propaga al pipeline para que todos los
        eventos del ciclo compartan correlación.
        """
        from ingest import ingest_document
        return ingest_document(
            file_path=file_path,
            tenant_id=self.tenant_id,
            space_id=space_id,
            document_id=document_id,
            source_type=source_type,
            authority_weight=authority_weight,
            anonymize=anonymize,
            display_filename=display_filename,
            source_metadata=source_metadata,
            operation_id=self.operation_id,
        )
