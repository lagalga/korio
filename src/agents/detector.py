"""
Agente Detector de Conflictos — análisis semántico contra el corpus.

Compara el documento recién ingestado contra el corpus existente y identifica
fragmentos que se contradicen. Clasifica el tipo de conflicto (obsolescencia
temporal, autoridad, multidocumento) y decide si el conflicto tiene resolución
automática posible o requiere escalada al Árbitro.

PEAS (Entregable 3):
- Performance: recall en detección de conflictos reales, precisión (min. falsos positivos),
  clasificación correcta del tipo de conflicto.
- Environment: índice vectorial del corpus, base de metadatos, doc nuevo del Ingestor.
- Actuators: informe de conflicto, señal al Árbitro o Supervisor según resolución posible,
  escritura en `pipeline_events` (CONFLICT_DETECTED | DOCUMENT_CLEARED).
- Sensors: comparador semántico (cosine similarity) sobre `embeddings.vector`,
  lector de metadatos, clasificador del tipo de conflicto.

Arquetipo: Basado en modelo. Mantiene representación interna del corpus para
razonar sobre lo que ya existe.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from agents.base import BaseAgent
from agents.events import Agent, EventType


class Detector(BaseAgent):
    """Detecta conflictos del doc nuevo contra el corpus activo."""

    role: Agent = Agent.DETECTOR

    def detect(
        self,
        *,
        new_document_id: str,
        new_chunk_ids: List[int],
        new_chunk_texts: List[str],
        new_embeddings: List[list],
        space_id: str,
        new_doc_authority: int,
        new_doc_version_ts: datetime,
    ):
        """
        Ejecuta la detección de conflictos sobre los chunks del nuevo documento.
        Devuelve un `ConflictReport`. Si hay conflictos, emite CONFLICT_DETECTED;
        si no, emite DOCUMENT_CLEARED.

        Importante: la detección actual (en `src/conflict_detector.py`) ya emite
        sus propios eventos via el ingest pipeline. Este método se mantiene como
        fachada agéntica para invocarlo desde código externo (p.ej. detección
        retroactiva en query-time, Phase 8).
        """
        from conflict_detector import detect_conflicts
        from db import get_supabase_client

        report = detect_conflicts(
            new_document_id=new_document_id,
            new_chunk_ids=new_chunk_ids,
            new_chunk_texts=new_chunk_texts,
            new_embeddings=new_embeddings,
            space_id=space_id,
            tenant_id=self.tenant_id,
            new_doc_authority=new_doc_authority,
            new_doc_version_ts=new_doc_version_ts,
            db=get_supabase_client(),
        )
        if report.has_conflicts:
            self._emit(
                EventType.CONFLICT_DETECTED,
                document_id=new_document_id,
                payload={
                    "total":          report.total_conflicts,
                    "auto_resolved":  report.auto_resolved,
                    "pending_review": report.pending_review,
                },
            )
        else:
            self._emit(EventType.DOCUMENT_CLEARED, document_id=new_document_id)
        return report
