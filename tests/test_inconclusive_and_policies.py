"""
Tests del estado terminal `inconclusive` (Regla 5 del E3) y de las políticas
reutilizables (Regla 4 del E3).

Regla 5 — Reactivación manual obligatoria: tras timeout sin resolución HITL,
los chunks pasan a `inconclusive` y NO se reactivan automáticamente.

Regla 4 — Prevalencia de políticas sobre reglas base: una decisión HITL
previa que se persistió como `policy` se aplica automáticamente cuando un
conflicto futuro matchea su `subject_pattern`, sin volver a crear HITL.
"""

import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db import get_supabase_client
from embedder import get_embedder
from chunker import get_chunker
from agents.events import new_operation_id
from policies import save_policy_from_review, find_applicable_policy
from escalation import _apply_timeout


TENANT_ID = "a0000000-0000-0000-0000-000000000001"
SPACE_ID  = "a1000000-0000-0000-0000-000000000001"


def _atomic_insert(db, content: str, filename: str, authority: int = 5):
    """Inserta un doc + chunks via el RPC atómico (saltando detector)."""
    embedder = get_embedder()
    chunker  = get_chunker()
    doc_id   = str(uuid.uuid4())
    chunks   = chunker.chunk_with_metadata(content, source_id=doc_id, document_title=filename)
    texts    = [c[0] for c in chunks]
    vecs     = embedder.embed_batch(texts)
    payload  = [
        {
            "chunk_index": i, "chunk_text": texts[i],
            "vector": "[" + ",".join(map(str, vecs[i].tolist())) + "]",
            "chunk_status": "active",
        }
        for i in range(len(texts))
    ]
    db.client.rpc("ingest_document_atomic", {
        "p_doc": {
            "id":               doc_id,
            "tenant_id":        TENANT_ID,
            "space_id":         SPACE_ID,
            "filename":         filename,
            "content_hash":     hashlib.sha256(content.encode()).hexdigest(),
            "source_type":      "manual",
            "authority_weight": authority,
            "version_ts":       datetime.now(timezone.utc).isoformat(),
            "status":           "active",
        },
        "p_chunks":       payload,
        "p_operation_id": new_operation_id(),
        "p_source_agent": "system",
    }).execute()
    chunk_rows = db.client.table("embeddings").select("id").eq("document_id", doc_id).execute()
    return doc_id, [r["id"] for r in chunk_rows.data]


def _cleanup(db, doc_ids):
    for did in doc_ids:
        try:
            db.client.table("documents").delete().eq("id", did).execute()
        except Exception:
            pass


# ─── Regla 5 — Inconclusive post-timeout ───────────────────────────────────

def test_timeout_pasa_chunks_a_inconclusive():
    """
    Simula una conflict_review en timeout (>21 días pendiente). Tras
    `_apply_timeout`, los chunks asociados quedan en `inconclusive` y la
    review tiene resolution=`timeout_inconclusive`.
    """
    db = get_supabase_client()
    doc_a_id, chunks_a = _atomic_insert(db, "Texto base A para inconclusive test " + uuid.uuid4().hex, "incl_a.md")
    doc_b_id, chunks_b = _atomic_insert(db, "Texto base B para inconclusive test " + uuid.uuid4().hex, "incl_b.md")
    chunk_a, chunk_b = chunks_a[0], chunks_b[0]

    # Crear la conflict_review pendiente con timestamps antiguos
    review_id = str(uuid.uuid4())
    long_ago  = (datetime.now(timezone.utc) - timedelta(days=22)).isoformat()
    db.client.table("conflict_reviews").insert({
        "id":                     review_id,
        "tenant_id":              TENANT_ID,
        "space_id":               SPACE_ID,
        "new_document_id":        doc_a_id,
        "new_chunk_id":           chunk_a,
        "existing_document_id":   doc_b_id,
        "existing_chunk_id":      chunk_b,
        "similarity":             0.9,
        "resolution":             "pending",
        "review_token":           uuid.uuid4().hex,
        "created_at":             long_ago,
    }).execute()

    try:
        now = datetime.now(timezone.utc)
        _apply_timeout(db, {
            "id": review_id, "tenant_id": TENANT_ID,
            "new_document_id": doc_a_id, "new_chunk_id": chunk_a,
            "existing_chunk_id": chunk_b,
        }, now)

        # Estado de la review
        r = db.client.table("conflict_reviews").select("resolution, timeout_at") \
            .eq("id", review_id).execute()
        assert r.data[0]["resolution"] == "timeout_inconclusive"
        assert r.data[0]["timeout_at"] is not None

        # Estado de los chunks: ambos inconclusive
        for cid in (chunk_a, chunk_b):
            row = db.client.table("embeddings").select("chunk_status") \
                .eq("id", cid).execute()
            assert row.data[0]["chunk_status"] == "inconclusive", \
                f"chunk {cid} debería ser inconclusive, es {row.data[0]['chunk_status']}"
    finally:
        db.client.table("conflict_reviews").delete().eq("id", review_id).execute()
        _cleanup(db, [doc_a_id, doc_b_id])


# ─── Regla 4 — Políticas reutilizables ─────────────────────────────────────

def test_policy_reutilizable_evita_hitl_segundo_conflicto():
    """
    1) Insertamos directamente una policy activa con subject_pattern.
    2) Insertamos un doc base que servirá de 'existing' en el conflicto.
    3) Ingestamos un doc nuevo con **contradicción semántica real** (mismo
       sujeto, valor distinto). El detector v0.3.16 aplica validación
       semántica LLM como paso 0 antes de policies, por lo que necesitamos
       un par con contradicción real (no solo similitud léxica).
    4) `detect_conflicts` debe aplicar la policy en lugar de crear HITL pending.
       El report debe contar el conflicto como `policy_resolved`.
    """
    from ingest import ingest_document
    db = get_supabase_client()

    # Núcleos con contradicción semántica real: 5 vs 10 días hábiles.
    nucleo_existing = (
        "El plazo de aprobación interno será de cinco días hábiles para todas "
        "las solicitudes formales del comité de cumplimiento normativo."
    )
    nucleo_new = (
        "El plazo de aprobación interno será de diez días hábiles para todas "
        "las solicitudes formales del comité de cumplimiento normativo."
    )
    # 1) Policy con pattern genérico que matchea ambos núcleos (5 y 10 días).
    policy_pattern = "el plazo de aprobación interno"
    pol = db.client.table("policies").insert({
        "tenant_id":       TENANT_ID,
        "space_id":        SPACE_ID,
        "subject_pattern": policy_pattern,
        "decision":        "policy_existing_wins",
        "reason":          "Test: aprendido manualmente",
        "active":          True,
    }).execute()
    policy_id = pol.data[0]["id"]

    # 2) Doc existente (vía RPC atómico para que no dispare detector)
    doc_existing_id, _ = _atomic_insert(
        db, f"# Política base\n\n{nucleo_existing}\n\nVigente desde enero.\n", "pol_existing.md"
    )

    # 3) Doc nuevo ingestado vía pipeline completo (DISPARA detector)
    import tempfile, pathlib
    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False)
    tmp.write(f"# Política revisada\n\n{nucleo_new}\n\nActualizada en marzo.\n".encode())
    tmp.flush()
    tmp.close()

    try:
        result = ingest_document(
            file_path=tmp.name, tenant_id=TENANT_ID, space_id=SPACE_ID,
            anonymize=False, authority_weight=5,
            display_filename="pol_revisada_test.md",
        )
        cr = result["conflict_report"]

        # El conflicto debe haberse resuelto por policy, no por HITL
        assert cr["total_conflicts"] >= 1, f"Esperaba al menos 1 conflicto: {cr}"
        assert cr["policy_resolved"] >= 1, \
            f"Esperaba policy_resolved>=1; got {cr}"
        # Y NO debe haber HITL pending para este doc
        assert cr["pending_review"] == 0, \
            f"Esperaba 0 pendientes (cubiertos por policy); got {cr}"

        # times_applied de la policy debe haberse incrementado
        check = db.client.table("policies").select("times_applied") \
            .eq("id", policy_id).execute()
        assert check.data[0]["times_applied"] >= 1, \
            f"times_applied debería ser >=1, got {check.data[0]['times_applied']}"
    finally:
        os.unlink(tmp.name)
        try:
            db.client.table("policies").delete().eq("id", policy_id).execute()
        except Exception:
            pass
        _cleanup(db, [doc_existing_id, result["document_id"]] if "result" in dir() else [doc_existing_id])
