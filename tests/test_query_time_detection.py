"""
Tests de detección de conflictos silenciosos en query-time.

Reproduce el "Caso extremo" del Entregable 4 del TFM: dos documentos cargados
directamente en la base de datos SIN PASAR por el detector de ingesta, con
contenido contradictorio. El RAG los recupera juntos en una consulta y, sin
el detector query-time, elegiría uno sin avisar.

Para reproducir esto sin tocar `ingest_document()` (que ejecuta el detector
de ingesta), usamos el RPC `ingest_document_atomic` directamente: persiste
documento + embeddings + evento DOCUMENT_INGESTED de forma atómica, pero NO
ejecuta detección de conflictos. Es el equivalente exacto a la situación del
E4 donde dos `.txt` se cargaron por debajo del pipeline.
"""

import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db import get_supabase_client
from embedder import get_embedder
from chunker import get_chunker
from agents.events import trace, new_operation_id, EventType
from search import search as run_search


TENANT_ID = "a0000000-0000-0000-0000-000000000001"
SPACE_ID  = "a1000000-0000-0000-0000-000000000001"
ADMIN_ID  = "a1000000-0000-0000-0000-000000000001"  # admin Delos (ve RRHH)


def _insert_doc_bypassing_detector(db, *, content: str, filename: str,
                                   authority: int = 5):
    """
    Inserta un documento + sus chunks + embeddings vía el RPC atómico,
    SALTÁNDOSE el detector de ingesta. Reproduce el "Caso extremo" del E4:
    docs que entraron al corpus sin pasar por la validación.
    """
    embedder = get_embedder()
    chunker = get_chunker()
    doc_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    chunks = chunker.chunk_with_metadata(content, source_id=doc_id, document_title=filename)
    texts = [c[0] for c in chunks]
    embeddings = embedder.embed_batch(texts)

    chunk_payloads = [
        {
            "chunk_index":  i,
            "chunk_text":   texts[i],
            "vector":       "[" + ",".join(map(str, embeddings[i].tolist())) + "]",
            "chunk_status": "active",
        }
        for i in range(len(texts))
    ]
    doc_payload = {
        "id":               doc_id,
        "tenant_id":        TENANT_ID,
        "space_id":         SPACE_ID,
        "filename":         filename,
        "content_hash":     content_hash,
        "source_type":      "manual",
        "authority_weight": authority,
        "version_ts":       datetime.now(timezone.utc).isoformat(),
        "status":           "active",
    }
    db.client.rpc(
        "ingest_document_atomic",
        {
            "p_doc":          doc_payload,
            "p_chunks":       chunk_payloads,
            "p_operation_id": new_operation_id(),
            "p_source_agent": "system",   # destacamos que no fue el Ingestor real
        },
    ).execute()
    return doc_id


def _cleanup(db, doc_ids):
    for did in doc_ids:
        try:
            db.client.table("documents").delete().eq("id", did).execute()
        except Exception:
            pass


@pytest.fixture
def two_uncurated_docs():
    """
    Dos documentos con el MISMO párrafo central (alta similitud ≥0.85 en
    los chunks que lo contienen) pero envueltos en distinto relleno para
    que filenames y content_hash sean distintos. Son la versión sintética
    del 'teletrabajo_circular_rrhh_2023' vs 'teletrabajo_acuerdo_comite_2023'
    del Anexo 4 del Entregable 4.
    """
    nucleo = (
        "La política de validación de gasto establece que cualquier solicitud "
        "de aprobación superior a diez mil euros requiere validación previa por "
        "parte del comité financiero antes de cualquier compromiso contractual. "
        "Esta validación es obligatoria, no admite excepciones internas, y debe "
        "registrarse en el sistema de gobernanza. La omisión de este paso "
        "supone una infracción del protocolo interno."
    )
    relleno_a = "\n\nEsta circular fue emitida por el departamento RRHH en enero."
    relleno_b = "\n\nEste acuerdo fue ratificado por el comité de empresa en febrero."
    return (
        f"# Circular RRHH\n\n{nucleo}{relleno_a}\n",
        f"# Acuerdo del Comité\n\n{nucleo}{relleno_b}\n",
    )


def test_caso_extremo_e4_dos_docs_no_curados_disparan_silent_conflict(two_uncurated_docs):
    """
    Reproduce el "Caso extremo" del Entregable 4:
    - Dos docs cargados saltándose el detector de ingesta
    - Sus chunks quedan en estado `active`
    - Una query que toque su contenido común recupera chunks de ambos
    - El detector query-time emite el aviso (`has_silent_conflict=True`)
    - El bus de eventos registra `CONFLICT_DETECTED` con `triggered_by=query_time`
    """
    db = get_supabase_client()
    content_a, content_b = two_uncurated_docs
    doc_ids = []
    try:
        doc_a = _insert_doc_bypassing_detector(
            db, content=content_a, filename="circular_rrhh_validacion.md", authority=5
        )
        doc_b = _insert_doc_bypassing_detector(
            db, content=content_b, filename="acuerdo_comite_validacion.md", authority=5
        )
        doc_ids = [doc_a, doc_b]

        result = run_search(
            query="¿qué validación requieren los gastos superiores a 10.000 euros?",
            user_id=ADMIN_ID,
            tenant_id=TENANT_ID,
            limit=8,
        )

        # 1) Se detectó el conflicto silencioso
        assert result["has_silent_conflict"] is True, \
            f"Esperaba has_silent_conflict=True; got silent_conflicts={result.get('silent_conflicts')}"
        assert len(result["silent_conflicts"]) >= 1

        # 2) Los pares involucran los dos docs cargados (al menos uno de ellos)
        docs_in_pairs = set()
        for p in result["silent_conflicts"]:
            docs_in_pairs.update([str(p["doc_a_id"]), str(p["doc_b_id"])])
        assert doc_a in docs_in_pairs and doc_b in docs_in_pairs, \
            f"Esperaba ambos docs en pares; got {docs_in_pairs}"

        # 3) Evento CONFLICT_DETECTED triggered_by=query_time emitido
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        rows = db.client.table("pipeline_events") \
            .select("event_type, payload, source_agent, created_at") \
            .eq("event_type", EventType.CONFLICT_DETECTED.value) \
            .eq("source_agent", "detector") \
            .gte("created_at", cutoff) \
            .order("created_at", desc=True).limit(10).execute()
        triggers = [
            e for e in (rows.data or [])
            if isinstance(e.get("payload"), dict)
            and e["payload"].get("triggered_by") == "query_time"
        ]
        assert triggers, "Esperaba CONFLICT_DETECTED con triggered_by=query_time"
    finally:
        _cleanup(db, doc_ids)
