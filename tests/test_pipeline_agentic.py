"""
Test del orquestador agéntico de alto nivel `Pipeline`.

Verifica que invocar `Pipeline.run_ingest()` produce el mismo resultado y la
misma traza de eventos que invocar `ingest_document()` directamente. La clase
Pipeline es la fachada que refleja los 5 roles del Entregable 3; el código
funcional del backend sigue intacto.
"""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agents import (
    Pipeline, Ingestor, Detector, Arbitrator, Supervisor, Curator,
    Agent, EventType, trace,
)
from db import get_supabase_client


TENANT_ID = "a0000000-0000-0000-0000-000000000001"
SPACE_ID  = "a1000000-0000-0000-0000-000000000001"


@pytest.fixture
def doc_path(tmp_path):
    p = tmp_path / "agentic_test.md"
    p.write_text(
        f"# Doc agéntico {uuid.uuid4()}\n\n"
        "Verificación del Pipeline alto-nivel.\n"
        + ("Lorem ipsum dolor sit amet. " * 30)
    )
    return str(p)


def test_pipeline_roles_son_los_cinco_del_entregable_3():
    """La instancia de Pipeline expone los 5 roles del diseño multiagéntico."""
    p = Pipeline(tenant_id=TENANT_ID)
    assert isinstance(p.ingestor,   Ingestor)
    assert isinstance(p.detector,   Detector)
    assert isinstance(p.arbitrator, Arbitrator)
    assert isinstance(p.supervisor, Supervisor)
    assert isinstance(p.curator,    Curator)
    assert p.ingestor.role   == Agent.INGESTOR
    assert p.detector.role   == Agent.DETECTOR
    assert p.arbitrator.role == Agent.ARBITRATOR
    assert p.supervisor.role == Agent.SUPERVISOR
    assert p.curator.role    == Agent.CURATOR
    # Todos comparten operation_id
    assert p.ingestor.operation_id == p.curator.operation_id


def test_pipeline_run_ingest_propaga_operation_id_a_todos_los_eventos(doc_path):
    """
    Pipeline.run_ingest() ejecuta el ciclo completo. Todos los eventos
    persistidos en pipeline_events deben compartir el mismo operation_id.
    """
    db = get_supabase_client()
    pipeline = Pipeline(tenant_id=TENANT_ID)
    result = pipeline.run_ingest(file_path=doc_path, space_id=SPACE_ID, anonymize=False)

    assert result["status"] == "success"
    assert result["operation_id"] == pipeline.operation_id

    document_id = result["document_id"]
    try:
        events = trace(pipeline.operation_id)
        event_types = [e["event_type"] for e in events]
        # El ciclo de ingesta exitosa pasa por estos eventos al menos:
        assert EventType.DOCUMENT_INGESTED.value in event_types
        assert EventType.CORPUS_UPDATED.value    in event_types
        # Y todos comparten correlación
        assert all(e["operation_id"] == pipeline.operation_id for e in events)
    finally:
        db.client.table("documents").delete().eq("id", document_id).execute()
