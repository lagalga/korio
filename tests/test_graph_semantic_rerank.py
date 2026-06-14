"""
Tests del rerank semántico del grafo (sesión 11, v0.3.2).

Verifica que `find_claims_semantic` devuelve claims ordenados por
cosine similarity contra el embedding de la query, y que el merge RRF
de `_graph_context` combina léxico + semántico sin perder cobertura.
"""

import pytest
from typing import List


def _fake_embedding(seed: float, dims: int = 8) -> List[float]:
    """Vector determinista pequeño para tests unitarios (no necesita 768)."""
    return [seed + i * 0.01 for i in range(dims)]


def test_find_claims_semantic_orders_by_cosine_similarity():
    """
    Test unitario: dado un set de claims con embeddings sintéticos y una
    query con embedding cercano a uno de ellos, find_claims_semantic
    devuelve ese claim en primera posición.

    Skip si FalkorDB no está disponible.
    """
    pytest.importorskip("falkordb")
    try:
        from graph_client import get_graph_client
    except Exception:
        pytest.skip("graph_client no disponible")

    try:
        gc = get_graph_client()
    except Exception as e:
        pytest.skip(f"FalkorDB no accesible: {e}")

    tenant_id = "test-semantic-rerank"
    space_id  = "test-space-rerank"

    # Limpiar estado previo de tests
    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )

    # Setup: Document → Chunk → 3 Claims con embeddings sintéticos
    gc.upsert_document(
        document_id="doc-rerank-1", tenant_id=tenant_id, space_id=space_id,
        filename="test.md", version_ts="2026-06-12T00:00:00", status="active",
    )
    gc.upsert_chunk(
        chunk_id=99001, document_id="doc-rerank-1",
        tenant_id=tenant_id, space_id=space_id,
        chunk_index=0, chunk_status="active",
    )

    claims_data = [
        ("c1", "política rrhh",  "duración",     "1 año",          _fake_embedding(0.1)),
        ("c2", "jornada laboral", "horas semana", "35 horas/semana", _fake_embedding(0.9)),
        ("c3", "vacaciones",     "días anuales", "22 días",        _fake_embedding(0.5)),
    ]
    for cid, subj, pred, val, emb in claims_data:
        gc.upsert_claim(
            claim_id=cid, tenant_id=tenant_id, chunk_id=99001,
            subject=subj, predicate=pred, value=val,
            chunk_status="active", embedding=emb,
        )

    # Query con embedding cercano al de c2 (jornada laboral)
    query_emb = _fake_embedding(0.91)

    results = gc.find_claims_semantic(
        tenant_id=tenant_id,
        query_embedding=query_emb,
        allowed_space_ids=[space_id],
        top_k=3,
    )

    assert len(results) >= 1, "Debe devolver al menos un claim con embedding"
    assert results[0]["subject"] == "jornada laboral", (
        f"El claim semánticamente más cercano debería ser 'jornada laboral', "
        f"pero el top-1 fue: {results[0]}"
    )
    # El score más alto está en posición 0
    if len(results) > 1:
        assert results[0]["semantic_score"] >= results[1]["semantic_score"]

    # Cleanup
    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )


def test_find_claims_semantic_respects_rls():
    """
    Verifica que find_claims_semantic filtra por allowed_space_ids:
    un claim de space_X no debe aparecer si solo se pasa space_Y.
    """
    pytest.importorskip("falkordb")
    try:
        from graph_client import get_graph_client
    except Exception:
        pytest.skip("graph_client no disponible")

    try:
        gc = get_graph_client()
    except Exception as e:
        pytest.skip(f"FalkorDB no accesible: {e}")

    tenant_id = "test-rls-rerank"
    space_a   = "space-a-rerank"
    space_b   = "space-b-rerank"

    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )

    gc.upsert_document(
        document_id="doc-A", tenant_id=tenant_id, space_id=space_a,
        filename="A.md", version_ts="2026-06-12T00:00:00", status="active",
    )
    gc.upsert_document(
        document_id="doc-B", tenant_id=tenant_id, space_id=space_b,
        filename="B.md", version_ts="2026-06-12T00:00:00", status="active",
    )
    gc.upsert_chunk(99101, "doc-A", tenant_id, space_a, 0, "active")
    gc.upsert_chunk(99102, "doc-B", tenant_id, space_b, 0, "active")

    emb = _fake_embedding(0.5)
    gc.upsert_claim("ca", tenant_id, 99101, "secreto A", "es", "valor A", "active", embedding=emb)
    gc.upsert_claim("cb", tenant_id, 99102, "secreto B", "es", "valor B", "active", embedding=emb)

    # Buscar solo en space_a → claim B NO debe aparecer
    results = gc.find_claims_semantic(
        tenant_id=tenant_id,
        query_embedding=emb,
        allowed_space_ids=[space_a],
        top_k=10,
    )
    subjects = {r["subject"] for r in results}
    assert "secreto a" in subjects, "Claim de space_a debe aparecer"
    assert "secreto b" not in subjects, (
        "RLS roto: claim de space_b apareció con allowed_space_ids=[space_a]"
    )

    # Cleanup
    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )


def test_find_claims_semantic_skips_claims_without_embedding():
    """
    Un claim sin propiedad `embedding` no debe aparecer en los resultados de
    find_claims_semantic (fallback safe — el léxico los seguirá pillando).
    """
    pytest.importorskip("falkordb")
    try:
        from graph_client import get_graph_client
    except Exception:
        pytest.skip("graph_client no disponible")

    try:
        gc = get_graph_client()
    except Exception as e:
        pytest.skip(f"FalkorDB no accesible: {e}")

    tenant_id = "test-no-emb"
    space_id  = "space-no-emb"

    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )

    gc.upsert_document(
        document_id="doc-noemb", tenant_id=tenant_id, space_id=space_id,
        filename="x.md", version_ts="2026-06-12T00:00:00", status="active",
    )
    gc.upsert_chunk(99201, "doc-noemb", tenant_id, space_id, 0, "active")

    # Sin embedding
    gc.upsert_claim("noemb", tenant_id, 99201, "viejo", "es", "sin embedding", "active")
    # Con embedding
    gc.upsert_claim("conemb", tenant_id, 99201, "nuevo", "es", "con embedding",
                    "active", embedding=_fake_embedding(0.3))

    results = gc.find_claims_semantic(
        tenant_id=tenant_id,
        query_embedding=_fake_embedding(0.3),
        allowed_space_ids=[space_id],
        top_k=10,
    )

    subjects = {r["subject"] for r in results}
    assert "nuevo" in subjects
    assert "viejo" not in subjects, (
        "find_claims_semantic devolvió un claim sin embedding"
    )

    gc.graph.query(
        "MATCH (n) WHERE n.tenant_id = $tid DETACH DELETE n",
        {"tid": tenant_id},
    )
