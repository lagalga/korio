"""
Backfill de embeddings para los Claims existentes en el grafo FalkorDB.

Recorre todos los Claims sin propiedad `embedding`, embeda el texto
"subject predicate value" con nomic-embed-text (Ollama) en batches y lo
guarda como propiedad del nodo. Habilita el rerank semántico del grafo
en `_graph_context` (ver src/search.py).

Uso:
    python scripts/graph_embed_claims.py             # todos los tenants
    python scripts/graph_embed_claims.py --tenant a0000000-...
    python scripts/graph_embed_claims.py --batch 16  # batch para Ollama
    python scripts/graph_embed_claims.py --reembed   # re-embeder incluso si ya hay
"""

import sys
import os
import argparse
import logging
import time
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from graph_client import get_graph_client
from embedder import get_embedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s · %(levelname)s · %(message)s",
)
logger = logging.getLogger("embed-claims")


def backfill(
    tenant_filter: Optional[str] = None,
    batch_size: int = 16,
    reembed: bool = False,
) -> None:
    gc = get_graph_client()
    embedder = get_embedder()

    # Buscar claims a procesar
    if reembed:
        where_clause = "1=1"
    else:
        where_clause = "cl.embedding IS NULL"

    if tenant_filter:
        tenant_clause = f"AND cl.tenant_id = '{tenant_filter}'"
    else:
        tenant_clause = ""

    cypher = f"""
    MATCH (cl:Claim)
    WHERE {where_clause}
      {tenant_clause}
    RETURN cl.id AS id, cl.tenant_id AS tenant_id,
           cl.subject AS subject, cl.predicate AS predicate, cl.value AS value
    """
    result = gc.graph.query(cypher)
    rows = gc._rows_to_dicts(result)

    if not rows:
        logger.info("✓ No hay claims pendientes de embedding.")
        return

    logger.info(f"📊 {len(rows)} claims a embedear (batch={batch_size})")
    t0 = time.time()
    processed = 0
    failed = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        texts = [f"{r['subject']} {r['predicate']} {r['value']}" for r in batch]
        try:
            vectors = embedder.embed_batch(texts)
        except Exception as e:
            logger.error(f"  Fallo batch {i}-{i+len(batch)}: {e}")
            failed += len(batch)
            continue

        for r, v in zip(batch, vectors):
            try:
                gc.graph.query(
                    """
                    MATCH (cl:Claim {tenant_id: $tenant_id, id: $claim_id})
                    SET cl.embedding = $embedding
                    """,
                    {
                        "tenant_id": r["tenant_id"],
                        "claim_id":  r["id"],
                        "embedding": v.tolist(),
                    },
                )
                processed += 1
            except Exception as e:
                logger.error(f"  Fallo SET embedding claim {r['id']}: {e}")
                failed += 1

        elapsed = time.time() - t0
        rate = processed / elapsed if elapsed > 0 else 0
        logger.info(f"  [{processed}/{len(rows)}] {rate:.1f} claims/s")

    elapsed = time.time() - t0
    logger.info(f"\n=== ✅ Backfill embeddings completado en {elapsed:.1f}s ===")
    logger.info(f"  ✓ Procesados: {processed}")
    if failed:
        logger.info(f"  ⚠️  Errores:   {failed}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tenant", help="Filtrar por tenant_id (UUID)")
    p.add_argument("--batch", type=int, default=16, help="Tamaño de batch para Ollama (default: 16)")
    p.add_argument("--reembed", action="store_true",
                   help="Re-embeder incluso si el claim ya tiene embedding")
    args = p.parse_args()
    backfill(tenant_filter=args.tenant, batch_size=args.batch, reembed=args.reembed)


if __name__ == "__main__":
    main()
