"""
Search script — Pipeline completo de búsqueda RAG.

Pipeline:
1. Embed la query (mismo modelo que ingesta: nomic-embed-text)
2. RLS early binding: obtener documentos permitidos para el usuario
3. Búsqueda vectorial (pgvector cosine similarity)
4. Ensamblar contexto (top-k chunks)
5. Generar respuesta con LLM (Mistral API u Ollama)
6. Registrar en audit_log
7. Retornar respuesta con citas de fuente

Uso:
    python src/search.py "¿Cuál es el protocolo de admisión?" --user-id <uuid>
    python src/search.py "¿Cuál es el protocolo de admisión?" --user-id <uuid> --tenant-id <uuid>
"""

import os
import re
import sys
import time
import argparse
import logging
from typing import Optional, List

from embedder import get_embedder
from db import get_supabase_client
from llm_client import get_llm_client

# Grafo de conocimiento (opt-in)
GRAPH_ENABLED = os.getenv("KORIO_GRAPH_ENABLED", "0") == "1"

# Stopwords castellano (mínimas, suficientes para queries cortas tipo RAG)
_QUERY_STOPWORDS = {
    "cuál", "cual", "cuáles", "cuales", "qué", "que", "cómo", "como",
    "cuándo", "cuando", "dónde", "donde", "cuántos", "cuantos", "cuántas", "cuantas",
    "para", "según", "segun", "están", "estan", "esta", "esto", "estos", "estas",
    "tiene", "tienen", "hay", "son", "ser", "es", "del", "los", "las",
    "una", "uno", "unos", "unas", "con", "por", "más", "mas", "menos", "todos", "todas",
    "que", "quien", "quién", "quienes", "quiénes",
}


def _extract_query_keywords(query: str, max_keywords: int = 6) -> List[str]:
    """Tokeniza la query a keywords útiles para buscar en el grafo."""
    tokens = re.findall(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ0-9_]+", query.lower())
    keywords = [t for t in tokens if len(t) >= 4 and t not in _QUERY_STOPWORDS]
    # Quitar duplicados conservando orden
    seen = set()
    out = []
    for k in keywords:
        if k not in seen:
            out.append(k)
            seen.add(k)
    return out[:max_keywords]


def _graph_context(query: str, tenant_id: str, allowed_space_ids: List[str]) -> str:
    """
    Consulta el grafo de conocimiento con las keywords de la query y
    devuelve un bloque de contexto formateado para inyectar al LLM.
    Devuelve string vacío si no hay grafo o no hay matches.
    """
    if not GRAPH_ENABLED or not tenant_id or not allowed_space_ids:
        return ""
    try:
        from graph_client import get_graph_client
        gc = get_graph_client()
        keywords = _extract_query_keywords(query)
        if not keywords:
            return ""
        claims = gc.find_claims_by_predicate(
            tenant_id=tenant_id,
            predicate_keywords=keywords,
            allowed_space_ids=allowed_space_ids,
            only_active=True,
        )
        if not claims:
            return ""
        lines = []
        seen_keys = set()
        for c in claims:
            key = (c.get("subject", ""), c.get("predicate", ""), c.get("value", ""))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            lines.append(
                f"  • {c['subject']} → {c['predicate']}: {c['value']}"
            )
            if len(lines) >= 8:
                break
        if not lines:
            return ""
        return (
            "[CONOCIMIENTO ESTRUCTURADO DEL GRAFO]\n"
            "Estas afirmaciones provienen del grafo de conocimiento del tenant "
            "(extraídas previamente por análisis semántico). Úsalas como fuente "
            "complementaria al contexto de chunks. No incluyas marcadores ni "
            "citas literales sobre el origen — responde de forma natural:\n"
            + "\n".join(lines)
        )
    except Exception as e:
        logger.warning(f"Error consultando grafo: {e}")
        return ""

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def search(
    query: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    limit: int = 5,
    threshold: float = 0.4,
    language: str = "es"
) -> dict:
    """
    Pipeline completo de búsqueda RAG con RLS.

    Args:
        query: Pregunta del usuario en lenguaje natural
        user_id: ID del usuario (para RLS — define qué documentos puede ver)
        tenant_id: ID del tenant (para audit log)
        limit: Número máximo de chunks a recuperar (default: 5)
        threshold: Similitud mínima para incluir un chunk (0-1, default: 0.4)
        language: Idioma de la respuesta ("es" o "en")

    Returns:
        dict: {
            "answer": str,           # Respuesta generada
            "sources": list,         # Documentos usados con similitud
            "chunks_used": int,      # Número de chunks recuperados
            "latency_ms": int,       # Latencia total en ms
            "has_context": bool,     # Si se encontró contexto relevante
            "model_used": str        # Modelo LLM usado
        }

    Raises:
        ValueError: Si el usuario no tiene acceso a ningún documento
        RuntimeError: Si falla algún paso del pipeline
    """
    start_time = time.time()
    logger.info(f"Búsqueda iniciada: '{query[:80]}...' (user: {user_id[:8]}...)")

    # Step 1: Embed la query
    logger.info("Step 1/4: Generando embedding de la query...")
    embedder = get_embedder()
    try:
        query_vector = embedder.embed_text(query)
        logger.info(f"  ✓ Query embebida ({len(query_vector)} dims)")
    except Exception as e:
        raise RuntimeError(f"Error al embeber query: {e}") from e

    # Step 2 + 3: RLS early binding + búsqueda vectorial
    # (db.py se encarga de: obtener espacios → filtrar docs → buscar vectores)
    logger.info("Step 2/4: RLS early binding + búsqueda vectorial...")
    db = get_supabase_client()
    try:
        raw_chunks = db.search_embeddings_rls(
            query_vector=query_vector.tolist(),
            user_id=user_id,
            limit=limit,
            threshold=threshold
        )
        logger.info(f"  ✓ {len(raw_chunks)} chunks recuperados")

        if not raw_chunks:
            logger.warning("  ⚠ Sin resultados. Umbral demasiado alto o sin documentos.")
    except ValueError as e:
        # Usuario sin espacios asignados — error de configuración
        raise
    except Exception as e:
        raise RuntimeError(f"Error en búsqueda vectorial: {e}") from e

    # Detectar conflictos en los chunks recuperados (gobernanza activa)
    # Si algún chunk tiene chunk_status='disputed', la respuesta debe presentar
    # ambas versiones y avisar al usuario explícitamente.
    disputed_chunks = [c for c in raw_chunks if c.get("chunk_status") == "disputed"]
    has_conflict = len(disputed_chunks) > 0
    if has_conflict:
        logger.warning(
            f"  ⚠️ {len(disputed_chunks)} chunk(s) en estado 'disputed' — "
            f"se presentarán ambas versiones del contenido en conflicto"
        )

    # Enriquecer cada chunk con el filename del documento (para citas legibles en el LLM)
    if raw_chunks:
        unique_doc_ids = set(c["document_id"] for c in raw_chunks)
        filename_lookup = {}
        for did in unique_doc_ids:
            doc = db.get_document_by_id(did)
            filename_lookup[did] = doc.get("filename", "") if doc else ""
        for c in raw_chunks:
            c["filename"] = filename_lookup.get(c["document_id"], "")

    # Step 3.5: Consulta paralela al grafo de conocimiento (Phase 7.1)
    graph_block = ""
    if GRAPH_ENABLED:
        # Reusar los space_ids ya calculados durante el RLS early binding
        # En db.search_embeddings_rls los obtenemos pero no los devolvemos; los recalculamos aquí
        try:
            user_spaces = db.client.table("user_spaces").select("space_id").eq("user_id", user_id).execute()
            space_ids = [row["space_id"] for row in (user_spaces.data or [])]
            graph_block = _graph_context(query, tenant_id, space_ids)
            if graph_block:
                logger.info(f"  ✓ Grafo contribuyó con contexto adicional ({graph_block.count(chr(10).join(['', '']))} líneas)")
        except Exception as e:
            logger.warning(f"Error obteniendo contexto del grafo: {e}")

    # Step 4: Ensamblado de contexto + generación LLM
    logger.info("Step 3/4: Generando respuesta con LLM...")
    llm = get_llm_client()
    try:
        system_prompt, user_prompt = llm.build_rag_prompt(
            query=query,
            context_chunks=raw_chunks,
            language=language
        )
        # Inyectar contexto del grafo al user_prompt
        if graph_block:
            user_prompt = graph_block + "\n\n---\n\n" + user_prompt

        # Inyectar aviso de conflicto en el prompt cuando proceda
        if has_conflict:
            conflict_notice = (
                "\n\nIMPORTANTE: Algunas de las fuentes que vas a citar contienen "
                "información contradictoria sobre el tema preguntado y están marcadas "
                "como 'en disputa' pendientes de revisión humana. NO elijas una versión "
                "como cierta; presenta ambas afirmaciones citando sus fuentes y avisa "
                "explícitamente al usuario de que existe una contradicción pendiente "
                "de resolución por el administrador."
                if language == "es" else
                "\n\nIMPORTANT: Some of the sources you will cite contain contradictory "
                "information about the topic and are flagged as 'disputed' pending human "
                "review. Do NOT pick one version as true; present both claims with their "
                "sources and explicitly warn the user that a contradiction is pending "
                "resolution by the administrator."
            )
            system_prompt = system_prompt + conflict_notice

        answer = llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2
        )
        logger.info(f"  ✓ Respuesta generada ({len(answer)} chars)")
    except Exception as e:
        raise RuntimeError(f"Error en generación LLM: {e}") from e

    # Step 5: Calcular latencia y preparar respuesta
    latency_ms = int((time.time() - start_time) * 1000)

    # Extraer IDs de documentos usados (sin duplicados)
    doc_ids_used = list(set(
        chunk["document_id"] for chunk in raw_chunks
    )) if raw_chunks else []

    # Reutilizar el lookup ya hecho arriba para las citas en sources
    filename_map = locals().get("filename_lookup", {})

    # Formatear fuentes para la respuesta
    sources = _format_sources(raw_chunks, filename_map)

    # Step 6: Audit log (incluye flag has_conflict si la respuesta tocó chunks disputed)
    if tenant_id:
        try:
            db.log_audit(
                tenant_id=tenant_id,
                user_id=user_id,
                query=query,
                doc_ids_used=doc_ids_used,
                model_used=llm.model,
                latency_ms=latency_ms,
                has_conflict=has_conflict,
            )
        except Exception as e:
            # El audit log no debe interrumpir la respuesta
            logger.warning(f"  ⚠ Error en audit log: {e}")

    result = {
        "answer": answer,
        "sources": sources,
        "chunks_used": len(raw_chunks),
        "doc_ids_used": doc_ids_used,
        "latency_ms": latency_ms,
        "has_context": len(raw_chunks) > 0 or bool(graph_block),
        "has_conflict": has_conflict,
        "disputed_chunks": len(disputed_chunks),
        "graph_contributed": bool(graph_block),
        "model_used": llm.model
    }

    logger.info(f"✅ Búsqueda completada en {latency_ms}ms")
    return result


def _format_sources(chunks: list, filename_map: dict = None) -> list:
    """
    Formatea los chunks recuperados como fuentes citables.

    Args:
        chunks: Lista de chunks de la búsqueda vectorial
        filename_map: Mapa doc_id → filename para enriquecer las citas

    Returns:
        list: Fuentes formateadas con document_id, filename, índice y similitud
    """
    if not chunks:
        return []

    filename_map = filename_map or {}

    # Agrupar por documento y tomar la similitud máxima
    docs_seen = {}
    for chunk in chunks:
        doc_id = chunk.get("document_id", "")
        similarity = chunk.get("similarity", 0)
        is_disputed = chunk.get("chunk_status") == "disputed"

        if doc_id not in docs_seen or similarity > docs_seen[doc_id]["similarity"]:
            docs_seen[doc_id] = {
                "document_id":    doc_id,
                "filename":       filename_map.get(doc_id, ""),
                "similarity":     round(similarity, 3),
                "chunk_index":    chunk.get("chunk_index", 0),
                "is_disputed":    is_disputed,
            }
        elif is_disputed:
            # Si ya estaba el doc pero un chunk suyo está disputed, marcarlo
            docs_seen[doc_id]["is_disputed"] = True

    # Ordenar por similitud descendente
    return sorted(docs_seen.values(), key=lambda x: x["similarity"], reverse=True)


def format_response(result: dict) -> str:
    """
    Formatea el resultado para mostrar en terminal.

    Args:
        result: Resultado de search()

    Returns:
        str: Texto formateado para mostrar al usuario
    """
    lines = [
        "─" * 60,
        "📖 RESPUESTA",
        "─" * 60,
        result["answer"],
        "",
        "─" * 60,
        f"📌 FUENTES ({len(result['sources'])} documento(s))",
        "─" * 60,
    ]

    for i, source in enumerate(result["sources"], 1):
        lines.append(
            f"  [{i}] Doc: {source['document_id'][:16]}... "
            f"| Relevancia: {source['similarity']:.0%}"
        )

    lines += [
        "",
        f"⏱  Latencia: {result['latency_ms']}ms  "
        f"| Modelo: {result['model_used']}  "
        f"| Chunks usados: {result['chunks_used']}",
        "─" * 60,
    ]

    return "\n".join(lines)


def main():
    """CLI para búsqueda RAG."""
    parser = argparse.ArgumentParser(
        description="Búsqueda RAG en Korio"
    )
    parser.add_argument("query", help="Pregunta en lenguaje natural")
    parser.add_argument(
        "--user-id",
        required=True,
        help="ID del usuario (UUID) — define qué documentos puede ver"
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="ID del tenant (para audit log)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Número máximo de chunks a recuperar (default: 5)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.4,
        help="Similitud mínima 0-1 (default: 0.4)"
    )
    parser.add_argument(
        "--lang",
        default="es",
        choices=["es", "en"],
        help="Idioma de la respuesta (default: es)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Mostrar resultado en JSON en lugar de formato legible"
    )

    args = parser.parse_args()

    try:
        result = search(
            query=args.query,
            user_id=args.user_id,
            tenant_id=args.tenant_id,
            limit=args.limit,
            threshold=args.threshold,
            language=args.lang
        )

        if args.json:
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(format_response(result))

        return 0

    except ValueError as e:
        logger.error(f"❌ Error de acceso: {e}")
        return 1
    except RuntimeError as e:
        logger.error(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
