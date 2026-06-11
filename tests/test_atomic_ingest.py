"""
Tests de transaccionalidad ACID del pipeline de ingesta.

Estos tests verifican que la promesa del refactor de la sesión 6 se cumple:
si la escritura atómica falla a mitad, NADA queda persistido. Responde al
feedback del profesor en el Entregable 4 del TFM.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db import get_supabase_client
from agents.events import new_operation_id, trace, EventType
from ingest import ingest_document, DuplicateDocumentError


# Tenant + space de Delos (seed real en producción)
TENANT_ID = "a0000000-0000-0000-0000-000000000001"
SPACE_ID  = "a1000000-0000-0000-0000-000000000001"


@pytest.fixture
def db():
    return get_supabase_client()


@pytest.fixture
def small_doc(tmp_path):
    """
    Genera un .md sintético único por test. El content_hash será diferente
    cada vez, así que no choca con la deduplicación de Postgres ni con
    documentos sintéticos del corpus de producción.
    """
    p = tmp_path / "doc_atomico.md"
    p.write_text(
        f"# Documento de prueba {uuid.uuid4()}\n\n"
        "Esta es una política sintética de prueba para verificar la "
        "transaccionalidad del pipeline.\n\n"
        "Tiene varios párrafos para garantizar al menos un par de chunks. "
        + ("Lorem ipsum dolor sit amet. " * 30)
    )
    return str(p)


def _count_doc_chunks(db, document_id):
    rows = db.client.table("embeddings").select("id").eq("document_id", document_id).execute()
    return len(rows.data or [])


def _doc_exists(db, document_id):
    rows = db.client.table("documents").select("id").eq("id", document_id).execute()
    return bool(rows.data)


def test_ingesta_feliz_path_genera_eventos_y_persiste(db, small_doc):
    """
    Camino feliz: ingesta exitosa → documento + chunks + eventos
    DOCUMENT_INGESTED y CORPUS_UPDATED quedan persistidos. operation_id en
    el resultado coincide con los eventos.
    """
    operation_id = new_operation_id()
    result = ingest_document(
        file_path=small_doc,
        tenant_id=TENANT_ID,
        space_id=SPACE_ID,
        anonymize=False,           # acelera el test
        operation_id=operation_id,
    )
    assert result["status"] == "success"
    assert result["operation_id"] == operation_id
    assert result["chunks_created"] > 0

    document_id = result["document_id"]
    try:
        # Estado en Postgres
        assert _doc_exists(db, document_id)
        assert _count_doc_chunks(db, document_id) == result["chunks_created"]

        # Bus de eventos
        events = trace(operation_id)
        event_types = [e["event_type"] for e in events]
        assert EventType.DOCUMENT_INGESTED.value in event_types
        assert EventType.CORPUS_UPDATED.value    in event_types
        # Todos los eventos comparten operation_id y tenant_id
        assert all(e["operation_id"] == operation_id for e in events)
        assert all(e["tenant_id"]    == TENANT_ID    for e in events)
    finally:
        # Cleanup: borrar el doc deja chunks por cascada FK
        db.client.table("documents").delete().eq("id", document_id).execute()


def test_ingesta_duplicada_no_persiste_segunda_copia(db, small_doc):
    """
    Si el content_hash ya existe → DuplicateDocumentError ANTES de tocar SQL.
    La verificación de duplicados pasa por una SELECT, no por el RPC.
    """
    op1 = new_operation_id()
    res1 = ingest_document(file_path=small_doc, tenant_id=TENANT_ID, space_id=SPACE_ID,
                           anonymize=False, operation_id=op1)
    doc_id_1 = res1["document_id"]
    try:
        with pytest.raises(DuplicateDocumentError) as exc_info:
            ingest_document(file_path=small_doc, tenant_id=TENANT_ID, space_id=SPACE_ID,
                            anonymize=False, operation_id=new_operation_id())
        assert exc_info.value.document_id == doc_id_1
    finally:
        db.client.table("documents").delete().eq("id", doc_id_1).execute()


def test_rpc_atomico_rollback_si_falla_mid_transaction(db):
    """
    Verifica que el RPC `ingest_document_atomic` revierte TODO si algún
    INSERT falla a mitad. Forzamos el fallo enviando un chunk con vector
    de dimensión incorrecta — el cast a `vector(768)` fallará en el chunk
    inválido y la transacción debe revertirse, no dejar el documento
    insertado sin chunks.
    """
    fake_doc_id = str(uuid.uuid4())
    operation_id = new_operation_id()
    bad_payload_doc = {
        "id":               fake_doc_id,
        "tenant_id":        TENANT_ID,
        "space_id":         SPACE_ID,
        "filename":         "rollback_test.md",
        "content_hash":     "rollback-test-" + uuid.uuid4().hex,
        "source_type":      "manual",
        "authority_weight": 5,
        "version_ts":       datetime.now(timezone.utc).isoformat(),
        "status":           "active",
    }
    # Primer chunk OK (vector de 768 ceros), segundo chunk con vector inválido
    good_vec = "[" + ",".join(["0"] * 768) + "]"
    bad_vec  = "[1,2,3]"   # dimensión incorrecta → CAST falla
    bad_payload_chunks = [
        {"chunk_index": 0, "chunk_text": "chunk válido", "vector": good_vec, "chunk_status": "active"},
        {"chunk_index": 1, "chunk_text": "chunk inválido", "vector": bad_vec, "chunk_status": "active"},
    ]

    with pytest.raises(Exception):
        db.client.rpc(
            "ingest_document_atomic",
            {
                "p_doc":          bad_payload_doc,
                "p_chunks":       bad_payload_chunks,
                "p_operation_id": operation_id,
                "p_source_agent": "ingestor",
            },
        ).execute()

    # Tras el fallo del RPC, el documento NO debe existir, los chunks
    # tampoco, y NO debe haber evento DOCUMENT_INGESTED para este operation_id
    assert not _doc_exists(db, fake_doc_id), \
        "Rollback fallido: el documento quedó persistido pese al fallo del RPC"
    chunks = db.client.table("embeddings").select("id").eq("document_id", fake_doc_id).execute()
    assert not chunks.data, "Rollback fallido: quedaron chunks del documento revertido"
    events = trace(operation_id)
    event_types = [e["event_type"] for e in events]
    assert EventType.DOCUMENT_INGESTED.value not in event_types, \
        "Rollback fallido: el evento DOCUMENT_INGESTED quedó persistido pese al fallo"
