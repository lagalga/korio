"""
Ingest pipeline de Korio — versión transaccional con bus de eventos.

Cambios respecto a la versión anterior (Phase 1-7.3):
  - Toda la IO externa (preprocess, chunking, embeddings, extracción de
    entidades) se hace ANTES de tocar SQL. Si Ollama o Mistral fallan, NADA
    queda persistido.
  - La escritura del documento + chunks + evento DOCUMENT_INGESTED se hace
    en una sola transacción PL/pgSQL vía `ingest_document_atomic` (migración
    011). Atomicidad ACID real: o todo o nada.
  - Cada transición lógica del pipeline emite un evento al bus
    (`pipeline_events`) con un `operation_id` UUID que correlaciona todo el
    ciclo. El bus también publica los eventos a n8n para observabilidad.
  - El sync con FalkorDB es POST-commit: si falla, se encola en
    `graph_sync_queue` para retry. El corpus Postgres queda siempre
    coherente; el grafo eventualmente alcanza el mismo estado.

Diseño multi-agente:
  Los roles (Ingestor, Detector, Arbitrator, Supervisor, Curator) son
  CLASES dentro de este proceso, no microservicios separados. El camino
  crítico no tiene saltos de red entre agentes. Ver src/agents/__init__.py
  para la justificación completa.

Uso CLI:
    python src/ingest.py path/to/document.pdf
    python src/ingest.py path/to/document.pdf --document-id abc123 --space-id xyz789
"""

import os
import sys
import argparse
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from embedder import get_embedder
from chunker import get_chunker
from preprocessor import get_preprocessor
from db import get_supabase_client
from conflict_detector import detect_conflicts, ConflictReport

# Bus de eventos del pipeline agéntico
from agents.events import emit, new_operation_id, EventType, Agent

# Grafo de conocimiento (opt-in vía KORIO_GRAPH_ENABLED=1)
GRAPH_ENABLED = os.getenv("KORIO_GRAPH_ENABLED", "0") == "1"

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DuplicateDocumentError(Exception):
    """
    Se intenta ingestar un documento cuyo content_hash ya existe en la base.
    No es un error en sentido estricto — es la deduplicación funcionando.
    """
    def __init__(self, document_id: str, filename: str, space_id: str, content_hash: str):
        self.document_id  = document_id
        self.filename     = filename
        self.space_id     = space_id
        self.content_hash = content_hash
        super().__init__(
            f"El documento ya estaba ingestado (id={document_id}, filename={filename})"
        )


def ingest_document(
    file_path: str,
    tenant_id: str,
    space_id: str,
    document_id: Optional[str] = None,
    source_type: str = "manual",
    authority_weight: int = 5,
    anonymize: bool = True,
    display_filename: Optional[str] = None,
    source_metadata: Optional[dict] = None,
    operation_id: Optional[str] = None,
) -> dict:
    """
    Pipeline transaccional de ingesta de un documento.

    Args:
        file_path:        Ruta del archivo a ingestar.
        tenant_id:        UUID del tenant.
        space_id:         UUID del espacio.
        document_id:      UUID del documento (default: se genera).
        source_type:      Origen del documento (manual / drive / slack / email / notion).
        authority_weight: Peso de autoridad (1-10, default 5).
        anonymize:        Si anonimizar PII (default True).
        display_filename: Nombre real del fichero (cuando viene como tempfile).
        source_metadata:  Contexto del canal (message_id, file_id, …).
        operation_id:     UUID de correlación de eventos. Si se omite, se genera uno.

    Returns:
        dict con estadísticas + operation_id para trazabilidad en `pipeline_events`.

    Raises:
        FileNotFoundError: si el archivo no existe.
        DuplicateDocumentError: si ya existe un doc con el mismo content_hash.
        ValueError / RuntimeError: si la escritura atómica falla.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    document_id  = document_id or str(uuid.uuid4())
    operation_id = operation_id or new_operation_id()
    filename     = display_filename or path.name
    # version_ts se decide tras preprocesar (mira filename + content). Si no
    # se puede extraer ninguna fecha, fallback a now() abajo.
    version_ts: Optional[datetime] = None
    version_ts_source: str = "fallback:now"

    logger.info(f"▶ Ingesta iniciada — filename={filename} operation_id={operation_id}")

    # ════════════════════════════════════════════════════════════════════════
    #  FASE 1 — IO EXTERNA (preprocess + chunking + embeddings)
    #
    #  Toda la IO contra Ollama / MarkItDown / Presidio ocurre AQUÍ, fuera de
    #  cualquier transacción SQL. Si algo falla, no hay estado a revertir
    #  porque aún no hemos tocado la base de datos.
    # ════════════════════════════════════════════════════════════════════════

    # Step 1: Preprocesar (MarkItDown + Presidio)
    logger.info("Step 1/5 — Preprocesando documento...")
    try:
        preprocessor = get_preprocessor()
        content, prep_meta = preprocessor.process_document(file_path, anonymize=anonymize)
        logger.info(f"  ✓ {prep_meta['char_count']} chars; PII: {prep_meta['pii_found']} hits")
        # Extraer fecha de versión del documento (filename + contenido + frontmatter).
        # El frontmatter (parseado por preprocessor) tiene prioridad si trae
        # signed_date — más fiable que regex sobre body. Para fallback al regex
        # de body, usamos el texto original-con-frontmatter (preservado en
        # prep_meta) por compatibilidad histórica con docs sin signed_date.
        from version_extractor import extract_version_ts
        extracted_ts, version_ts_source = extract_version_ts(
            filename,
            prep_meta.get("original_with_frontmatter", content),
            frontmatter=prep_meta.get("frontmatter"),
        )
        if extracted_ts is not None:
            version_ts = extracted_ts
            logger.info(f"  📅 version_ts={version_ts.date().isoformat()} ({version_ts_source})")
        else:
            version_ts = datetime.now(timezone.utc)
            logger.info(f"  📅 version_ts=now() (no_match en filename ni contenido)")
    except Exception as e:
        emit(EventType.INGEST_FAILED, source_agent=Agent.INGESTOR,
             tenant_id=tenant_id, operation_id=operation_id,
             payload={"phase": "preprocess", "error": str(e), "filename": filename})
        logger.error(f"Error en preprocesamiento: {e}")
        raise

    # Step 2: Chunking
    logger.info("Step 2/5 — Dividiendo en chunks...")
    try:
        chunker = get_chunker()
        chunks_with_meta = chunker.chunk_with_metadata(
            content, source_id=document_id, document_title=Path(filename).stem
        )
        chunk_texts = [c[0] for c in chunks_with_meta]
        stats = chunker.validate_chunks(chunk_texts)
        logger.info(f"  ✓ {stats['total_chunks']} chunks (avg {stats['avg_tokens']:.0f} tok)")
    except Exception as e:
        emit(EventType.INGEST_FAILED, source_agent=Agent.INGESTOR,
             tenant_id=tenant_id, operation_id=operation_id,
             payload={"phase": "chunking", "error": str(e), "filename": filename})
        logger.error(f"Error en chunking: {e}")
        raise

    # Step 3: Embeddings
    logger.info("Step 3/5 — Generando embeddings...")
    try:
        embedder = get_embedder()
        embeddings = embedder.embed_batch(chunk_texts)
        logger.info(f"  ✓ {len(embeddings)} embeddings @ {embeddings[0].shape[0]} dims")
    except Exception as e:
        emit(EventType.INGEST_FAILED, source_agent=Agent.INGESTOR,
             tenant_id=tenant_id, operation_id=operation_id,
             payload={"phase": "embeddings", "error": str(e), "filename": filename})
        logger.error(f"Error en embeddings: {e}")
        raise

    # ════════════════════════════════════════════════════════════════════════
    #  FASE 2 — DEDUPE (lectura, no escritura)
    # ════════════════════════════════════════════════════════════════════════

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    supabase = get_supabase_client()
    # Primero por filename (case-insensitive) dentro del mismo space — cubre PDFs
    # cuyo hash varía entre extracciones aunque sean el mismo fichero.
    existing = supabase.table("documents").select(
        "id, filename, space_id, content_hash"
    ).eq("tenant_id", tenant_id).eq("space_id", space_id).ilike(
        "filename", filename
    ).execute()
    if not existing.data:
        # Fallback: mismo content_hash en cualquier space del tenant
        existing = supabase.table("documents").select(
            "id, filename, space_id, content_hash"
        ).eq("content_hash", content_hash).execute()
    if existing.data:
        dup = existing.data[0]
        logger.info(f"  ⚠️ Documento duplicado detectado (existing id={dup['id']})")
        raise DuplicateDocumentError(
            document_id=dup["id"], filename=dup["filename"],
            space_id=dup["space_id"], content_hash=content_hash,
        )

    # ════════════════════════════════════════════════════════════════════════
    #  FASE 3 — ESCRITURA ATÓMICA (RPC PL/pgSQL)
    #
    #  Toda la escritura — documents + embeddings + evento DOCUMENT_INGESTED
    #  — sucede en una sola transacción dentro de `ingest_document_atomic`.
    #  Si cualquier paso falla, todo se revierte.
    # ════════════════════════════════════════════════════════════════════════

    logger.info("Step 4/5 — Escritura atómica (RPC ingest_document_atomic)...")
    doc_payload = {
        "id":               document_id,
        "tenant_id":        tenant_id,
        "space_id":         space_id,
        "filename":         filename,
        "content_hash":     content_hash,
        "source_type":      source_type,
        "authority_weight": authority_weight,
        "version_ts":       version_ts.isoformat(),
        "status":           "active",
    }
    # Trazabilidad de la extracción de fecha (auditoría)
    sm = dict(source_metadata) if source_metadata else {}
    sm["version_ts_source"] = version_ts_source
    doc_payload["source_metadata"] = sm

    chunk_payloads = [
        {
            "chunk_index": i,
            "chunk_text":  chunk_texts[i],
            # pgvector acepta el formato textual "[0.1,0.2,...]"
            "vector":      "[" + ",".join(map(str, embeddings[i].tolist())) + "]",
            "chunk_status": "active",
        }
        for i in range(len(chunk_texts))
    ]

    try:
        rpc_response = supabase.client.rpc(
            "ingest_document_atomic",
            {
                "p_doc":          doc_payload,
                "p_chunks":       chunk_payloads,
                "p_operation_id": operation_id,
                "p_source_agent": Agent.INGESTOR.value,
            },
        ).execute()
        rpc_data = rpc_response.data or {}
        # Normalizar el resultado del RPC: puede venir como dict o como string JSON
        if isinstance(rpc_data, str):
            import json as _json
            rpc_data = _json.loads(rpc_data)
        chunk_ids = rpc_data.get("chunk_ids") or []
        logger.info(
            f"  ✓ Transacción OK — doc_id={document_id} chunks_persisted={len(chunk_ids)}"
        )
    except Exception as e:
        # NO hay estado parcial que limpiar: la transacción se revirtió.
        # No pasamos document_id porque el documento no llegó a persistirse
        # (la FK de pipeline_events.document_id fallaría).
        emit(EventType.INGEST_FAILED, source_agent=Agent.INGESTOR,
             tenant_id=tenant_id, operation_id=operation_id,
             payload={
                 "phase":          "atomic_write",
                 "error":          str(e),
                 "filename":       filename,
                 "attempted_doc_id": document_id,
             })
        logger.error(f"Error en escritura atómica (transacción revertida): {e}")
        raise

    # ════════════════════════════════════════════════════════════════════════
    #  FASE 4 — POST-COMMIT: grafo de conocimiento (best-effort + cola)
    #
    #  FalkorDB no participa en la transacción Postgres. Si el sync falla,
    #  encolamos el job en `graph_sync_queue` para retry asíncrono.
    # ════════════════════════════════════════════════════════════════════════

    graph_stats = {"entities": 0, "claims": 0, "chunks_processed": 0}
    if GRAPH_ENABLED and chunk_ids:
        logger.info("Step 5/5 — Sync con grafo de conocimiento (post-commit)...")
        try:
            from graph_client import get_graph_client
            from entity_extractor import extract_from_chunk

            gc = get_graph_client()
            gc.upsert_document(
                document_id=document_id, tenant_id=tenant_id, space_id=space_id,
                filename=filename, version_ts=version_ts.isoformat(), status="active",
            )
            for idx, (chunk_id, (chunk_text, _meta)) in enumerate(zip(chunk_ids, chunks_with_meta)):
                gc.upsert_chunk(
                    chunk_id=chunk_id, document_id=document_id,
                    tenant_id=tenant_id, space_id=space_id,
                    chunk_index=idx, chunk_status="active",
                )
                extraction = extract_from_chunk(chunk_text, filename=filename)
                for ent in extraction.entities:
                    gc.upsert_entity(tenant_id=tenant_id, name=ent.name, kind=ent.kind)
                    gc.link_chunk_to_entity(chunk_id=chunk_id, tenant_id=tenant_id, entity_name=ent.name)
                    graph_stats["entities"] += 1

                # Embeber los claims en batch (1 llamada Ollama por chunk)
                # para que el rerank semántico del grafo funcione en query-time.
                claim_embeddings = []
                if extraction.claims:
                    try:
                        claim_texts = [
                            f"{cl.subject} {cl.predicate} {cl.value}"
                            for cl in extraction.claims
                        ]
                        claim_embeddings = embedder.embed_batch(claim_texts)
                    except Exception as e:
                        logger.warning(f"  Fallo embedding claims (sigo sin rerank semántico): {e}")
                        claim_embeddings = [None] * len(extraction.claims)

                for cl, emb in zip(extraction.claims, claim_embeddings):
                    emb_list = emb.tolist() if emb is not None else None
                    gc.upsert_claim(
                        claim_id=cl.claim_id, tenant_id=tenant_id, chunk_id=chunk_id,
                        subject=cl.subject, predicate=cl.predicate, value=cl.value,
                        chunk_status="active", embedding=emb_list,
                    )
                    graph_stats["claims"] += 1
                graph_stats["chunks_processed"] += 1

            logger.info(
                f"  ✓ Grafo: {graph_stats['chunks_processed']} chunks → "
                f"{graph_stats['entities']} ent, {graph_stats['claims']} claims"
            )
            emit(EventType.GRAPH_SYNCED, source_agent=Agent.INGESTOR,
                 tenant_id=tenant_id, operation_id=operation_id,
                 document_id=document_id, payload=graph_stats)
        except Exception as e:
            # Encolamos para retry — el corpus Postgres está consistente, el
            # grafo se rellena cuando un worker procese la cola.
            logger.warning(f"Sync grafo falló — encolando para retry: {e}")
            try:
                supabase.table("graph_sync_queue").insert({
                    "operation_id": operation_id,
                    "document_id":  document_id,
                    "tenant_id":    tenant_id,
                    "payload":      {
                        "chunk_ids":   chunk_ids,
                        "filename":    filename,
                        "version_ts":  version_ts.isoformat(),
                    },
                    "attempts":   1,
                    "last_error": str(e)[:500],
                    "last_attempt_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as e2:
                logger.exception("No se pudo encolar el job de sync grafo: %s", e2)
            emit(EventType.GRAPH_SYNC_FAILED, source_agent=Agent.INGESTOR,
                 tenant_id=tenant_id, operation_id=operation_id,
                 document_id=document_id,
                 payload={"error": str(e)[:500]})

    # ════════════════════════════════════════════════════════════════════════
    #  FASE 5 — POST-COMMIT: detección de conflictos (gobernanza)
    # ════════════════════════════════════════════════════════════════════════

    conflict_report = ConflictReport()
    if chunk_ids:
        try:
            embeddings_list = [emb.tolist() for emb in embeddings]
            conflict_report = detect_conflicts(
                new_document_id=document_id,
                new_chunk_ids=chunk_ids,
                new_chunk_texts=chunk_texts,
                new_embeddings=embeddings_list,
                space_id=space_id, tenant_id=tenant_id,
                new_doc_authority=authority_weight,
                new_doc_version_ts=version_ts,
                db=supabase,
                new_filename=filename,
            )
            if conflict_report.has_conflicts:
                logger.info(
                    f"  ⚠️ {conflict_report.total_conflicts} conflictos: "
                    f"{conflict_report.auto_resolved} auto-resueltos, "
                    f"{conflict_report.pending_review} pendientes HITL"
                )
                emit(EventType.CONFLICT_DETECTED, source_agent=Agent.DETECTOR,
                     tenant_id=tenant_id, operation_id=operation_id,
                     document_id=document_id,
                     payload={
                         "total":          conflict_report.total_conflicts,
                         "auto_resolved":  conflict_report.auto_resolved,
                         "pending_review": conflict_report.pending_review,
                     })
            else:
                emit(EventType.DOCUMENT_CLEARED, source_agent=Agent.DETECTOR,
                     tenant_id=tenant_id, operation_id=operation_id,
                     document_id=document_id, payload={"filename": filename})
                logger.info("  ✓ Sin conflictos detectados")
        except Exception as e:
            logger.warning(f"Detección de conflictos falló (ingesta queda OK): {e}")

    # Cierre de ciclo — emitir CORPUS_UPDATED desde el Curator
    emit(EventType.CORPUS_UPDATED, source_agent=Agent.CURATOR,
         tenant_id=tenant_id, operation_id=operation_id,
         document_id=document_id,
         payload={
             "filename":         filename,
             "chunk_count":      len(chunk_ids),
             "graph_stats":      graph_stats,
             "conflict_summary": conflict_report.to_dict(),
         })

    result = {
        "document_id":          document_id,
        "operation_id":         operation_id,
        "filename":             filename,
        "status":               "success",
        "chunks_created":       len(chunk_ids),
        "embeddings_generated": len(embeddings),
        "pii_found":            prep_meta['pii_found'],
        "char_count":           prep_meta['char_count'],
        "conflict_report":      conflict_report.to_dict(),
        "graph_stats":          graph_stats,
    }
    logger.info(f"✅ Ingesta completada — operation_id={operation_id}")
    return result


def main():
    """CLI para ingesta de documentos."""
    parser = argparse.ArgumentParser(description="Ingesta de documentos a Korio")
    parser.add_argument("document", help="Ruta del documento a ingestar")
    parser.add_argument("--tenant-id", default="a0000000-0000-0000-0000-000000000001",
                        help="ID del tenant (default: Clínica Delos)")
    parser.add_argument("--space-id", default="a1000000-0000-0000-0000-000000000001",
                        help="ID del espacio (default: RRHH)")
    parser.add_argument("--document-id", help="ID del documento (default: nuevo)")
    parser.add_argument("--no-anonymize", action="store_true", help="No anonimizar PII")
    args = parser.parse_args()

    try:
        result = ingest_document(
            file_path=args.document,
            tenant_id=args.tenant_id,
            space_id=args.space_id,
            document_id=args.document_id,
            anonymize=not args.no_anonymize,
        )
        print(f"\n✅ Éxito: {result}")
        return 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
