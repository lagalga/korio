"""
Script de backfill — pobla el grafo de conocimiento con todos los chunks
existentes en Supabase.

Uso:
    # Desde el VPS (o vía SSH tunnel a Supabase + FalkorDB)
    python scripts/graph_backfill.py
    python scripts/graph_backfill.py --tenant a0000000-... --limit 50
    python scripts/graph_backfill.py --reset   # borra y reconstruye

Variables de entorno necesarias:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, MISTRAL_API_KEY,
    FALKORDB_HOST (default 127.0.0.1), FALKORDB_PORT (default 6379)
"""

import sys
import os
import argparse
import logging
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db import get_supabase_client
from graph_client import get_graph_client
from entity_extractor import extract_from_chunk
from conflict_detector import CONFLICT_THRESHOLD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s · %(levelname)s · %(message)s",
)
logger = logging.getLogger("backfill")


def backfill(
    tenant_filter: Optional[str] = None,
    limit: Optional[int] = None,
    reset: bool = False,
) -> None:
    db = get_supabase_client()
    gc = get_graph_client()

    if reset:
        logger.warning("⚠️  RESET solicitado — borrando todo el grafo")
        gc.delete_all()
        gc = get_graph_client()  # recrear client (singleton)

    # 1. Documentos
    docs_q = db.client.table("documents").select(
        "id, tenant_id, space_id, filename, version_ts, status"
    )
    if tenant_filter:
        docs_q = docs_q.eq("tenant_id", tenant_filter)
    if limit:
        docs_q = docs_q.limit(limit)
    docs = docs_q.execute().data or []

    logger.info(f"📚 {len(docs)} documentos a procesar")

    stats = {"chunks": 0, "entities": 0, "claims": 0, "errors": 0, "skipped": 0}
    t0 = time.time()

    for d in docs:
        doc_id = d["id"]
        logger.info(f"📄 {d['filename']} ({doc_id[:8]}…)")

        # Upsert documento
        try:
            gc.upsert_document(
                document_id=doc_id,
                tenant_id=d["tenant_id"],
                space_id=d["space_id"],
                filename=d.get("filename", ""),
                version_ts=d.get("version_ts", ""),
                status=d.get("status", "active"),
            )
        except Exception as e:
            logger.error(f"  Error upsert doc: {e}")
            stats["errors"] += 1
            continue

        # 2. Chunks del documento
        chunks = db.client.table("embeddings").select(
            "id, chunk_index, chunk_text, chunk_status"
        ).eq("document_id", doc_id).order("chunk_index").execute().data or []

        for ch in chunks:
            chunk_id = ch["id"]
            text     = ch.get("chunk_text", "")
            status   = ch.get("chunk_status", "active")

            try:
                gc.upsert_chunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    tenant_id=d["tenant_id"],
                    space_id=d["space_id"],
                    chunk_index=ch.get("chunk_index", 0),
                    chunk_status=status,
                )
            except Exception as e:
                logger.error(f"  Error upsert chunk {chunk_id}: {e}")
                stats["errors"] += 1
                continue

            # 3. Extraer entidades + claims
            try:
                extr = extract_from_chunk(text, filename=d.get("filename", ""))
            except Exception as e:
                logger.error(f"  Error extracción chunk {chunk_id}: {e}")
                stats["errors"] += 1
                continue

            for ent in extr.entities:
                gc.upsert_entity(tenant_id=d["tenant_id"], name=ent.name, kind=ent.kind)
                gc.link_chunk_to_entity(
                    chunk_id=chunk_id, tenant_id=d["tenant_id"], entity_name=ent.name
                )
                stats["entities"] += 1

            for cl in extr.claims:
                gc.upsert_claim(
                    claim_id=cl.claim_id,
                    tenant_id=d["tenant_id"],
                    chunk_id=chunk_id,
                    subject=cl.subject,
                    predicate=cl.predicate,
                    value=cl.value,
                    chunk_status=status,
                )
                stats["claims"] += 1

            stats["chunks"] += 1
            logger.info(
                f"  chunk {chunk_id} [{status}] → {len(extr.entities)} ent, {len(extr.claims)} claims"
            )

    # 4. Conflictos conocidos → aristas CONTRADICTS
    logger.info("\n🔗 Backfilling contradicciones desde conflict_reviews...")
    reviews_q = db.client.table("conflict_reviews").select(
        "id, tenant_id, new_chunk_id, existing_chunk_id, similarity, resolution"
    )
    if tenant_filter:
        reviews_q = reviews_q.eq("tenant_id", tenant_filter)
    reviews = reviews_q.execute().data or []

    contradictions_added = 0
    for r in reviews:
        try:
            # Crear arista CONTRADICTS solo entre claims con MISMO predicate +
            # MISMO subject (o uno contiene al otro) + valores distintos.
            # El filtro de subject evita falsos positivos del tipo:
            #   (subject="política RRHH",   predicate="responsable", value="director")
            #   (subject="protocolo limpieza", predicate="responsable", value="proveedor")
            # — comparten predicate "responsable" pero hablan de cosas distintas.
            cypher = """
            MATCH (cA:Claim {tenant_id: $tenant_id, chunk_id: $new_id}),
                  (cB:Claim {tenant_id: $tenant_id, chunk_id: $existing_id})
            WHERE cA.predicate = cB.predicate
              AND cA.value <> cB.value
              AND (cA.subject = cB.subject
                   OR cA.subject CONTAINS cB.subject
                   OR cB.subject CONTAINS cA.subject)
            MERGE (cA)-[r:CONTRADICTS]->(cB)
            SET r.similarity = $similarity, r.review_id = $review_id
            RETURN count(r) AS added
            """
            result = gc.graph.query(cypher, {
                "tenant_id":   r["tenant_id"],
                "new_id":      r["new_chunk_id"],
                "existing_id": r["existing_chunk_id"],
                "similarity":  float(r.get("similarity") or 0),
                "review_id":   r["id"],
            })
            if result.result_set and result.result_set[0]:
                added = result.result_set[0][0]
                contradictions_added += added
        except Exception as e:
            logger.warning(f"  Review {r['id'][:8]}…: {e}")

    elapsed = time.time() - t0
    logger.info(f"\n=== ✅ Backfill completado en {elapsed:.1f}s ===")
    logger.info(f"  📄 Documentos:       {len(docs)}")
    logger.info(f"  📦 Chunks:           {stats['chunks']}")
    logger.info(f"  🏷  Entidades:       {stats['entities']}")
    logger.info(f"  💬 Claims:           {stats['claims']}")
    logger.info(f"  ⚡ Contradicciones: {contradictions_added}")
    logger.info(f"  ⚠️  Errores:         {stats['errors']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tenant", help="Filtrar por tenant_id (UUID)")
    p.add_argument("--limit",  type=int, help="Limitar a N documentos (para pruebas)")
    p.add_argument("--reset",  action="store_true", help="Borrar grafo antes de reconstruir")
    args = p.parse_args()
    backfill(tenant_filter=args.tenant, limit=args.limit, reset=args.reset)


if __name__ == "__main__":
    main()
