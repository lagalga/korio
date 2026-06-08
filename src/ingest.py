"""
Ingest script — Pipeline completo de ingesta.

Pipeline:
1. Cargar documento (PDF/DOCX/TXT)
2. Convertir a Markdown
3. Anonimizar PII
4. Dividir en chunks
5. Generar embeddings
6. Guardar en Supabase (pgvector)

Uso:
    python src/ingest.py path/to/document.pdf
    python src/ingest.py path/to/document.pdf --document-id abc123 --space-id xyz789
"""

import sys
import argparse
import uuid
from pathlib import Path
from typing import Optional

from embedder import get_embedder
from chunker import get_chunker
from preprocessor import get_preprocessor
from db import get_supabase_client

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def ingest_document(
    file_path: str,
    tenant_id: str,
    space_id: str,
    document_id: Optional[str] = None,
    anonymize: bool = True
) -> dict:
    """
    Pipeline completo de ingesta de un documento.

    Args:
        file_path: Ruta del archivo a ingestar
        tenant_id: ID del tenant (UUID)
        space_id: ID del espacio (UUID)
        document_id: ID del documento (UUID). Si no se proporciona, se genera uno.
        anonymize: Si debe anonimizar PII (default: True)

    Returns:
        dict: Resultado con estadísticas de ingesta

    Raises:
        FileNotFoundError: Si el archivo no existe
        ValueError: Si hay error en algún paso
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    # Generar IDs si no se proporcionan
    document_id = document_id or str(uuid.uuid4())

    logger.info(f"Iniciando ingesta: {path.name}")

    # Step 1: Preprocesar (MarkItDown + Presidio)
    logger.info("Step 1/4: Preprocesando documento...")
    preprocessor = get_preprocessor()
    try:
        content, prep_meta = preprocessor.process_document(file_path, anonymize=anonymize)
        logger.info(f"  ✓ Documento procesado ({prep_meta['char_count']} chars)")
        if prep_meta['pii_found'] > 0:
            logger.info(f"  ✓ PII anonimizado: {prep_meta['pii_types']}")
    except Exception as e:
        logger.error(f"Error en preprocesamiento: {e}")
        raise

    # Step 2: Chunking
    logger.info("Step 2/4: Dividiendo en chunks...")
    chunker = get_chunker()
    try:
        chunks_with_meta = chunker.chunk_with_metadata(
            content,
            source_id=document_id,
            document_title=path.stem
        )
        stats = chunker.validate_chunks([c[0] for c in chunks_with_meta])
        logger.info(f"  ✓ {stats['total_chunks']} chunks generados")
        logger.info(f"    Avg size: {stats['avg_tokens']:.0f} tokens")
    except Exception as e:
        logger.error(f"Error en chunking: {e}")
        raise

    # Step 3: Embeddings
    logger.info("Step 3/4: Generando embeddings...")
    embedder = get_embedder()
    try:
        chunk_texts = [c[0] for c in chunks_with_meta]
        embeddings = embedder.embed_batch(chunk_texts)
        logger.info(f"  ✓ {len(embeddings)} embeddings generados")
        logger.info(f"    Dimensión: {embeddings[0].shape[0]} dims")
    except Exception as e:
        logger.error(f"Error en embeddings: {e}")
        raise

    # Step 4: Guardar en Supabase
    logger.info("Step 4/4: Guardando en Supabase...")
    supabase = get_supabase_client()
    try:
        # Calcular hash del contenido para deduplicación
        import hashlib
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Crear documento
        doc_response = supabase.table("documents").insert({
            "id": document_id,
            "tenant_id": tenant_id,
            "space_id": space_id,
            "filename": path.name,
            "source_type": "manual",
            "content_hash": content_hash,
            "status": "active"
        }).execute()

        if not doc_response.data:
            raise ValueError("Error creando documento en Supabase")

        logger.info(f"  ✓ Documento creado (ID: {document_id})")

        # Insertar chunks con embeddings
        chunk_records = []
        for i, (chunk_text, meta) in enumerate(chunks_with_meta):
            chunk_records.append({
                "document_id": document_id,
                "chunk_index": i,
                "chunk_text": chunk_text,
                "vector": embeddings[i].tolist(),  # pgvector acepta arrays Python
                "chunk_status": "active"
            })

        # Batch insert (Supabase permite hasta 1000 por request)
        batch_size = 100
        for batch_start in range(0, len(chunk_records), batch_size):
            batch = chunk_records[batch_start:batch_start + batch_size]
            chunk_response = supabase.table("embeddings").insert(batch).execute()
            logger.info(f"  ✓ Insertados chunks {batch_start + 1}-{min(batch_start + batch_size, len(chunk_records))}")

        logger.info(f"  ✓ Total de chunks almacenados: {len(chunk_records)}")

    except Exception as e:
        logger.error(f"Error guardando en Supabase: {e}")
        raise

    # Resultado
    result = {
        "document_id": document_id,
        "filename": path.name,
        "status": "success",
        "chunks_created": len(chunk_records),
        "embeddings_generated": len(embeddings),
        "pii_anonymized": prep_meta['pii_found'],
        "char_count": prep_meta['char_count']
    }

    logger.info(f"\n✅ Ingesta completada: {result}")
    return result


def main():
    """CLI para ingesta de documentos."""
    parser = argparse.ArgumentParser(
        description="Ingesta de documentos a Korio"
    )
    parser.add_argument("document", help="Ruta del documento a ingestar")
    parser.add_argument(
        "--tenant-id",
        default="a0000000-0000-0000-0000-000000000001",
        help="ID del tenant (default: Clínica Delos)"
    )
    parser.add_argument(
        "--space-id",
        default="a1000000-0000-0000-0000-000000000001",
        help="ID del espacio (default: RRHH)"
    )
    parser.add_argument(
        "--document-id",
        help="ID del documento (default: genera uno nuevo)"
    )
    parser.add_argument(
        "--no-anonymize",
        action="store_true",
        help="No anonimizar PII"
    )

    args = parser.parse_args()

    try:
        result = ingest_document(
            file_path=args.document,
            tenant_id=args.tenant_id,
            space_id=args.space_id,
            document_id=args.document_id,
            anonymize=not args.no_anonymize
        )
        print(f"\n✅ Éxito: {result}")
        return 0
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
