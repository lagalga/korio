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
from agents.events import emit, new_operation_id, EventType, Agent
from observability import traceable

# Grafo de conocimiento (opt-in)
GRAPH_ENABLED = os.getenv("KORIO_GRAPH_ENABLED", "0") == "1"

# Detección de conflictos silenciosos en query-time (Phase 8 candidate cerrado
# en sesión 7: cubre el "Caso extremo" del Entregable 4 del TFM).
QUERY_TIME_CONFLICT_ENABLED   = os.getenv("KORIO_QUERY_TIME_CONFLICT_ENABLED", "1") == "1"
QUERY_TIME_CONFLICT_THRESHOLD = float(os.getenv("KORIO_QUERY_TIME_CONFLICT_THRESHOLD", "0.85"))

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


@traceable(name="graph-retrieval", run_type="retriever")
def _graph_context(
    query: str,
    tenant_id: str,
    allowed_space_ids: List[str],
    query_embedding: Optional[List[float]] = None,
) -> str:
    """
    Consulta el grafo de conocimiento con dos paths en paralelo:

    1. **Léxico**: keywords de la query → CONTAINS sobre predicate/subject/value
       (cubre matches exactos cuando la query usa el vocabulario del corpus).
    2. **Semántico**: embedding de la query × embedding del claim, cosine
       similarity (cubre queries rephrasadas que el léxico no atrapa).

    Merge dedupe + top-8 ordenados por score combinado (lexical_rank +
    semantic_rank en RRF — Reciprocal Rank Fusion). Si solo uno de los dos
    paths devuelve resultados, se usa ese.

    Devuelve string vacío si no hay grafo, no hay matches o falla.
    """
    if not GRAPH_ENABLED or not tenant_id or not allowed_space_ids:
        return ""
    try:
        from graph_client import get_graph_client
        gc = get_graph_client()

        # Path 1: léxico (con rerank ponderado existente)
        lexical_ranked: List[dict] = []
        keywords = _extract_query_keywords(query)
        if keywords:
            lexical_claims = gc.find_claims_by_predicate(
                tenant_id=tenant_id,
                predicate_keywords=keywords,
                allowed_space_ids=allowed_space_ids,
                only_active=True,
            )

            def _lexical_score(c):
                score = 0
                pred = (c.get("predicate") or "").lower()
                subj = (c.get("subject") or "").lower()
                val  = (c.get("value") or "").lower()
                for kw in keywords:
                    if kw in pred: score += 3
                    if kw in val:  score += 2
                    if kw in subj: score += 1
                return score

            lexical_claims.sort(key=_lexical_score, reverse=True)
            lexical_ranked = lexical_claims[:15]

        # Path 2: semántico (sobre claims con embedding guardado)
        semantic_ranked: List[dict] = []
        if query_embedding:
            try:
                semantic_ranked = gc.find_claims_semantic(
                    tenant_id=tenant_id,
                    query_embedding=query_embedding,
                    allowed_space_ids=allowed_space_ids,
                    top_k=15,
                    only_active=True,
                )
            except Exception as e:
                logger.warning(f"Rerank semántico del grafo falló (sigo con léxico): {e}")
                semantic_ranked = []

        if not lexical_ranked and not semantic_ranked:
            return ""

        # Merge por Reciprocal Rank Fusion: score = sum(1/(k+rank)) para cada
        # path donde aparece el claim. k=60 es el valor estándar de RRF.
        K = 60
        scores: dict = {}
        meta: dict = {}

        for rank, c in enumerate(lexical_ranked):
            key = (c.get("subject", ""), c.get("predicate", ""), c.get("value", ""))
            scores[key] = scores.get(key, 0.0) + 1.0 / (K + rank + 1)
            meta.setdefault(key, c)

        for rank, c in enumerate(semantic_ranked):
            key = (c.get("subject", ""), c.get("predicate", ""), c.get("value", ""))
            scores[key] = scores.get(key, 0.0) + 1.0 / (K + rank + 1)
            meta.setdefault(key, c)

        # Top-8 final por RRF score
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:8]
        lines = [
            f"  • {meta[k]['subject']} → {meta[k]['predicate']}: {meta[k]['value']}"
            for k, _ in top
        ]
        if not lines:
            return ""
        return (
            "Afirmaciones del grafo de conocimiento del tenant "
            "(extraídas por análisis semántico, tan válidas como los chunks):\n"
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


@traceable(name="rag-search", run_type="chain")
def search(
    query: str,
    user_id: str,
    tenant_id: Optional[str] = None,
    limit: int = 5,
    threshold: float = 0.35,
    language: str = "es",
    history: Optional[List[dict]] = None
) -> dict:
    """
    Pipeline completo de búsqueda RAG con RLS.

    Args:
        query: Pregunta del usuario en lenguaje natural
        user_id: ID del usuario (para RLS — define qué documentos puede ver)
        tenant_id: ID del tenant (para audit log)
        limit: Número máximo de chunks a recuperar (default: 5)
        threshold: Similitud mínima para incluir un chunk (0-1, default: 0.35)
        language: Idioma de la respuesta ("es" o "en")
        history: Historial conversacional opcional (lista de turnos previos).
                 Si se proporciona, la query se reformula como pregunta autónoma
                 antes del embedding (chat multi-turn). Formato:
                 [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        dict: {
            "answer": str,             # Respuesta generada
            "sources": list,           # Documentos usados con similitud
            "chunks_used": int,        # Número de chunks recuperados
            "latency_ms": int,         # Latencia total en ms
            "has_context": bool,       # Si se encontró contexto relevante
            "model_used": str,         # Modelo LLM usado
            "original_query": str,     # Query tal como llegó del usuario
            "embedded_query": str,     # Query usada para el embed (reformulada o igual)
            "query_reformulated": bool # True si se reformuló
        }

    Raises:
        ValueError: Si el usuario no tiene acceso a ningún documento
        RuntimeError: Si falla algún paso del pipeline
    """
    start_time = time.time()
    logger.info(f"Búsqueda iniciada: '{query[:80]}...' (user: {user_id[:8]}...)")

    original_query = query
    query_reformulated = False

    # Step 0.5: Reformulación si hay historial (chat multi-turn)
    # Sin esto, queries como "¿y si llevo 15?" no recuperan chunks porque su
    # embedding no captura el contexto de la pregunta anterior.
    if history:
        logger.info(f"Step 0/4: Reformulando query con historial ({len(history)} turnos)...")
        llm = get_llm_client()
        reformulated = llm.reformulate_query(query, history, language=language)
        if reformulated and reformulated != query:
            logger.info(f"  ✓ Query reformulada: '{reformulated[:80]}...'")
            query = reformulated
            query_reformulated = True
        else:
            logger.info("  ✓ Query ya era autónoma (sin reformulación)")

    # Step 1: Embed la query (potencialmente reformulada)
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

    # Detectar conflictos en los chunks recuperados (gobernanza activa).
    # Solo consideramos 'disputed' los chunks que aparte de tener ese estado
    # son REALMENTE relevantes para la query (similarity >= DISPUTED_BANNER_MIN_SIM).
    # Sin este filtro, queries vagas recuperaban chunks `disputed` de docs no
    # relacionados y disparaban el banner sin justificación visible al usuario.
    DISPUTED_BANNER_MIN_SIM = float(os.getenv("KORIO_DISPUTED_BANNER_MIN_SIM", "0.6"))
    disputed_chunks = [
        c for c in raw_chunks
        if c.get("chunk_status") in ("disputed", "inconclusive")
        and float(c.get("similarity") or 0) >= DISPUTED_BANNER_MIN_SIM
    ]
    has_conflict = len(disputed_chunks) > 0
    if has_conflict:
        logger.warning(
            f"  ⚠️ {len(disputed_chunks)} chunk(s) en estado 'disputed'/'inconclusive' con sim>={DISPUTED_BANNER_MIN_SIM} — "
            f"se presentarán ambas versiones del contenido en conflicto"
        )


    # Step 2.5: Detección de conflictos silenciosos en query-time (Phase 8 / sesión 7)
    # Cubre el "Caso extremo" del Entregable 4: dos docs activos sin disputa
    # que el RAG recupera juntos para una misma query. Si el par tiene
    # similitud entre sí >= QUERY_TIME_CONFLICT_THRESHOLD, hay sospecha de
    # conflicto silencioso → avisamos al usuario y emitimos CONFLICT_DETECTED.
    silent_conflicts: list = []
    if QUERY_TIME_CONFLICT_ENABLED and tenant_id and len(raw_chunks) >= 2:
        try:
            # search_embeddings_rls devuelve la PK del chunk como "id", no "chunk_id"
            chunk_ids = [c["id"] for c in raw_chunks if c.get("id") is not None]
            unique_doc_ids = {c["document_id"] for c in raw_chunks}
            if len(chunk_ids) >= 2 and len(unique_doc_ids) >= 2:
                rpc = db.client.rpc(
                    "detect_silent_conflicts_among_chunks",
                    {
                        "p_chunk_ids": chunk_ids,
                        "p_threshold": QUERY_TIME_CONFLICT_THRESHOLD,
                    },
                ).execute()
                silent_conflicts = rpc.data or []
                if silent_conflicts:
                    logger.warning(
                        f"  ⚠️ {len(silent_conflicts)} conflicto(s) silencioso(s) "
                        f"detectado(s) en query-time (umbral {QUERY_TIME_CONFLICT_THRESHOLD})"
                    )
                    # Emisión al bus de eventos: el Detector actúa retroactivamente.
                    # Generamos un operation_id propio para este ciclo de query-time.
                    op_id = new_operation_id()
                    emit(
                        EventType.CONFLICT_DETECTED,
                        source_agent=Agent.DETECTOR,
                        tenant_id=tenant_id,
                        operation_id=op_id,
                        payload={
                            "triggered_by":          "query_time",
                            "query":                 query[:200],
                            "threshold":             QUERY_TIME_CONFLICT_THRESHOLD,
                            "pairs":                 len(silent_conflicts),
                            "max_similarity":        max(
                                float(p["similarity"]) for p in silent_conflicts
                            ),
                            "documents_involved":    list({
                                str(p["doc_a_id"]) for p in silent_conflicts
                            } | {
                                str(p["doc_b_id"]) for p in silent_conflicts
                            }),
                        },
                    )
        except Exception as e:
            # Detección silenciosa es best-effort: no debe romper la query.
            logger.warning(f"Detección query-time falló (no crítico): {e}")
            silent_conflicts = []

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
            # Pasamos el embedding de la query (calculado en step 2) para
            # habilitar el rerank semántico del grafo (find_claims_semantic).
            graph_block = _graph_context(
                query, tenant_id, space_ids,
                query_embedding=query_vector.tolist() if query_vector is not None else None,
            )
            if graph_block:
                logger.info(f"  ✓ Grafo contribuyó con contexto adicional ({graph_block.count(chr(10).join(['', '']))} líneas)")
        except Exception as e:
            logger.warning(f"Error obteniendo contexto del grafo: {e}")

    # Step 4: Ensamblado de contexto + generación LLM
    logger.info("Step 3/4: Generando respuesta con LLM...")
    llm = get_llm_client()
    try:
        # El grafo se inyecta DENTRO del CONTEXTO (como fuente equivalente a
        # los chunks vectoriales). Si va fuera, el LLM lo descarta porque el
        # system_prompt obliga a responder solo desde el CONTEXTO.
        system_prompt, user_prompt = llm.build_rag_prompt(
            query=query,
            context_chunks=raw_chunks,
            language=language,
            graph_context=graph_block,
        )

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

        # Aviso adicional: conflicto silencioso detectado en query-time.
        # Sucede cuando ≥2 chunks recuperados, de documentos distintos, tienen
        # similitud entre sí >= umbral (default 0.85). Indica que en su día NO
        # se identificó el conflicto en ingesta pero el RAG los está usando
        # juntos ahora.
        if silent_conflicts:
            pairs_lines = "\n".join(
                f"  - {p['filename_a']} vs {p['filename_b']} (similitud {float(p['similarity']):.2f})"
                for p in silent_conflicts[:5]
            )
            silent_notice = (
                f"\n\nIMPORTANTE: La gobernanza activa ha detectado que entre las "
                f"fuentes que vas a usar hay documentos con contenido muy similar "
                f"(≥{QUERY_TIME_CONFLICT_THRESHOLD:.2f}) que NO han sido revisados como "
                f"conflicto. Es posible que la respuesta dependa de cuál de ellos "
                f"prevalezca. Avisa explícitamente al usuario al final de tu respuesta "
                f"con un párrafo que comience por '⚠️ Aviso de la gobernanza:' indicando "
                f"que existen documentos potencialmente contradictorios pendientes de "
                f"revisión, y lista los pares siguientes:\n{pairs_lines}\n"
                "Si las dos fuentes coinciden en la respuesta concreta a la pregunta, "
                "puedes responderla con seguridad pero igualmente avisa de la potencial "
                "contradicción para revisión administrativa."
                if language == "es" else
                f"\n\nIMPORTANT: Active governance has detected that two or more of the "
                f"sources you are about to use are highly similar (≥{QUERY_TIME_CONFLICT_THRESHOLD:.2f}) "
                f"and were not flagged as conflict in ingestion. Warn the user at the end "
                f"of your answer with a paragraph starting with '⚠️ Governance notice:' "
                f"and list the pairs:\n{pairs_lines}"
            )
            system_prompt = system_prompt + silent_notice

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

    # Filtro de "utilidad para presentación": las fuentes con similitud
    # marginal (por debajo de KORIO_USEFUL_SIM_THRESHOLD, default 0.55) no
    # se citan al usuario aunque hayan pasado el threshold de recuperación
    # más permisivo (0.35). Evita listar como "fuente" chunks que el LLM
    # descartó porque eran ruido temático.
    USEFUL_SIM_THRESHOLD = float(os.getenv("KORIO_USEFUL_SIM_THRESHOLD", "0.55"))
    sources = [s for s in sources if s.get("similarity", 0) >= USEFUL_SIM_THRESHOLD]

    # Detección de refusal: si el LLM declinó responder porque los chunks
    # recuperados no son temáticamente relevantes, no tiene sentido listar
    # esos chunks como "fuentes" — el LLM acaba de decir que no le valieron.
    # Vaciamos sources + disputed_chunks + has_conflict para que la UI muestre
    # un "no encuentro" limpio sin la trazabilidad confusa.
    refusal_patterns = (
        "no encuentro información",
        "no tengo información",
        "no dispongo de información",
        "no hay información",
        "no se menciona",
        "no se especifica",
        "no se indica",
        "los documentos disponibles no",
        "no puedo responder",
    )
    answer_lower = (answer or "").strip().lower()
    is_refusal = any(p in answer_lower for p in refusal_patterns)
    if is_refusal:
        sources = []
        disputed_chunks = []
        has_conflict = False
        logger.info("  ↳ Respuesta detectada como refusal — sources/disputed_chunks vaciados")

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
        "model_used": llm.model,
        # Trazabilidad de la reformulación (útil para debug y memoria TFM)
        "original_query": original_query,
        "embedded_query": query,
        "query_reformulated": query_reformulated,
        # Detección query-time (Caso extremo del E4 cerrado)
        "silent_conflicts":           silent_conflicts,
        "has_silent_conflict":        bool(silent_conflicts),
        "query_time_threshold":       QUERY_TIME_CONFLICT_THRESHOLD,
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
        is_disputed = chunk.get("chunk_status") in ("disputed", "inconclusive")

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
