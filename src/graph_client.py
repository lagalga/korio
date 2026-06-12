"""
Cliente FalkorDB para Korio — Phase 7.1 (grafo de conocimiento).

Schema multi-tenant:

  (:Document {id, tenant_id, space_id, filename, version_ts, status})
      ↓ CONTAINS
  (:Chunk    {id, tenant_id, space_id, document_id, chunk_index, chunk_status})
      ↓ MENTIONS / HAS_CLAIM
  (:Entity   {id, tenant_id, name, kind})              ← kind: Persona|Organización|Lugar|Fecha|Concepto
  (:Claim    {id, tenant_id, subject, predicate, value, chunk_id, chunk_status})

  (Claim) -[:CONTRADICTS {similarity, review_id}]-> (Claim)
  (Claim) -[:ABOUT_ENTITY]->                       (Entity)

Aislamiento:
  - TODO nodo y arista lleva tenant_id como propiedad
  - Las queries SIEMPRE filtran por tenant_id (RLS-equivalente en grafo)
  - Una sola "graph instance" en FalkorDB ('korio') con todos los tenants
    mezclados pero aislados por la propiedad tenant_id

CRÍTICO: Cualquier query expuesta al usuario DEBE filtrar por tenant_id
(o lista de tenant_id permitidos según user).
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── Configuración ───────────────────────────────────────────────────────────

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "127.0.0.1")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_USER = os.getenv("FALKORDB_USER")  # opcional
FALKORDB_PASS = os.getenv("FALKORDB_PASS")  # opcional
GRAPH_NAME    = os.getenv("KORIO_GRAPH_NAME", "korio")


# ─── Cliente ──────────────────────────────────────────────────────────────────

class GraphClient:
    """
    Wrapper sobre FalkorDB para Korio.

    Convenciones:
      - Todos los CREATE incluyen tenant_id en propiedades.
      - Todas las queries de lectura filtran por tenant_id.
      - chunk_status replicado del estado en Supabase (active/superseded/disputed)
        para poder filtrar el grafo igual que el RAG.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        graph_name: Optional[str] = None,
    ):
        try:
            from falkordb import FalkorDB
        except ImportError as e:
            raise ImportError("Instala el driver: pip install falkordb") from e

        self.host = host or FALKORDB_HOST
        self.port = port or FALKORDB_PORT
        self.graph_name = graph_name or GRAPH_NAME

        kwargs = {"host": self.host, "port": self.port}
        if FALKORDB_USER:
            kwargs["username"] = FALKORDB_USER
        if FALKORDB_PASS:
            kwargs["password"] = FALKORDB_PASS

        self.db = FalkorDB(**kwargs)
        self.graph = self.db.select_graph(self.graph_name)
        logger.info(f"FalkorDB conectado: {self.host}:{self.port} · graph={self.graph_name}")

    # ─── Schema / Índices ─────────────────────────────────────────────────────

    def ensure_indexes(self) -> None:
        """
        Crea índices Cypher para queries rápidos. Idempotente (try/except).
        Aplica una sola vez al inicio o cuando se reinicia el grafo.
        """
        index_statements = [
            "CREATE INDEX FOR (d:Document) ON (d.tenant_id, d.id)",
            "CREATE INDEX FOR (d:Document) ON (d.tenant_id, d.space_id)",
            "CREATE INDEX FOR (c:Chunk)    ON (c.tenant_id, c.id)",
            "CREATE INDEX FOR (c:Chunk)    ON (c.tenant_id, c.chunk_status)",
            "CREATE INDEX FOR (e:Entity)   ON (e.tenant_id, e.name)",
            "CREATE INDEX FOR (e:Entity)   ON (e.tenant_id, e.kind)",
            "CREATE INDEX FOR (cl:Claim)   ON (cl.tenant_id, cl.subject)",
            "CREATE INDEX FOR (cl:Claim)   ON (cl.tenant_id, cl.chunk_status)",
        ]
        for stmt in index_statements:
            try:
                self.graph.query(stmt)
            except Exception as e:
                # FalkorDB devuelve error si el índice ya existe; lo ignoramos
                if "already" not in str(e).lower() and "exists" not in str(e).lower():
                    logger.warning(f"Index error ({stmt[:50]}…): {e}")

    # ─── Upserts ──────────────────────────────────────────────────────────────

    def upsert_document(
        self,
        document_id: str,
        tenant_id: str,
        space_id: str,
        filename: str,
        version_ts: Optional[str] = None,
        status: str = "active",
    ) -> None:
        """MERGE Document (idempotente por id+tenant_id)."""
        self.graph.query(
            """
            MERGE (d:Document {tenant_id: $tenant_id, id: $document_id})
            SET d.space_id   = $space_id,
                d.filename   = $filename,
                d.version_ts = $version_ts,
                d.status     = $status
            """,
            {
                "document_id": document_id,
                "tenant_id":   tenant_id,
                "space_id":    space_id,
                "filename":    filename,
                "version_ts":  version_ts or "",
                "status":      status,
            },
        )

    def upsert_chunk(
        self,
        chunk_id: int,
        document_id: str,
        tenant_id: str,
        space_id: str,
        chunk_index: int,
        chunk_status: str = "active",
    ) -> None:
        """MERGE Chunk + arista CONTAINS Document → Chunk."""
        self.graph.query(
            """
            MATCH (d:Document {tenant_id: $tenant_id, id: $document_id})
            MERGE (c:Chunk {tenant_id: $tenant_id, id: $chunk_id})
            SET c.document_id  = $document_id,
                c.space_id     = $space_id,
                c.chunk_index  = $chunk_index,
                c.chunk_status = $chunk_status
            MERGE (d)-[:CONTAINS]->(c)
            """,
            {
                "chunk_id":     chunk_id,
                "document_id":  document_id,
                "tenant_id":    tenant_id,
                "space_id":     space_id,
                "chunk_index":  chunk_index,
                "chunk_status": chunk_status,
            },
        )

    def upsert_entity(
        self,
        tenant_id: str,
        name: str,
        kind: str,
    ) -> None:
        """MERGE Entity por (tenant_id, name normalizado)."""
        self.graph.query(
            """
            MERGE (e:Entity {tenant_id: $tenant_id, name: $name})
            SET e.kind = $kind
            """,
            {"tenant_id": tenant_id, "name": name.strip().lower(), "kind": kind},
        )

    def link_chunk_to_entity(
        self,
        chunk_id: int,
        tenant_id: str,
        entity_name: str,
    ) -> None:
        """Crea arista Chunk -[MENTIONS]-> Entity."""
        self.graph.query(
            """
            MATCH (c:Chunk  {tenant_id: $tenant_id, id: $chunk_id}),
                  (e:Entity {tenant_id: $tenant_id, name: $entity_name})
            MERGE (c)-[:MENTIONS]->(e)
            """,
            {
                "chunk_id":    chunk_id,
                "tenant_id":   tenant_id,
                "entity_name": entity_name.strip().lower(),
            },
        )

    def upsert_claim(
        self,
        claim_id: str,
        tenant_id: str,
        chunk_id: int,
        subject: str,
        predicate: str,
        value: str,
        chunk_status: str = "active",
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        Crea Claim + arista Chunk -[HAS_CLAIM]-> Claim.
        Si la entidad sujeto existe como Entity, también crea Claim -[ABOUT_ENTITY]-> Entity.

        Si se proporciona `embedding` (vector 768 dims de nomic-embed-text sobre
        el texto "subject predicate value"), se guarda como propiedad del nodo
        Claim para habilitar el rerank semántico en query-time
        (ver `find_claims_semantic`).
        """
        # Crear Claim + relación con chunk. El embedding va como propiedad
        # opcional para no romper claims antiguos sin él.
        params = {
            "claim_id":     claim_id,
            "tenant_id":    tenant_id,
            "chunk_id":     chunk_id,
            "subject":      subject.strip().lower(),
            "predicate":    predicate.strip().lower(),
            "value":        value.strip(),
            "chunk_status": chunk_status,
        }
        if embedding is not None:
            params["embedding"] = list(embedding)
            self.graph.query(
                """
                MATCH (c:Chunk {tenant_id: $tenant_id, id: $chunk_id})
                MERGE (cl:Claim {tenant_id: $tenant_id, id: $claim_id})
                SET cl.subject      = $subject,
                    cl.predicate    = $predicate,
                    cl.value        = $value,
                    cl.chunk_id     = $chunk_id,
                    cl.chunk_status = $chunk_status,
                    cl.embedding    = $embedding
                MERGE (c)-[:HAS_CLAIM]->(cl)
                """,
                params,
            )
        else:
            self.graph.query(
                """
                MATCH (c:Chunk {tenant_id: $tenant_id, id: $chunk_id})
                MERGE (cl:Claim {tenant_id: $tenant_id, id: $claim_id})
                SET cl.subject      = $subject,
                    cl.predicate    = $predicate,
                    cl.value        = $value,
                    cl.chunk_id     = $chunk_id,
                    cl.chunk_status = $chunk_status
                MERGE (c)-[:HAS_CLAIM]->(cl)
                """,
                params,
            )

        # Si el sujeto del claim coincide con una Entity, enlazar
        self.graph.query(
            """
            MATCH (cl:Claim  {tenant_id: $tenant_id, id: $claim_id}),
                  (e:Entity  {tenant_id: $tenant_id, name: $subject})
            MERGE (cl)-[:ABOUT_ENTITY]->(e)
            """,
            {
                "claim_id":  claim_id,
                "tenant_id": tenant_id,
                "subject":   subject.strip().lower(),
            },
        )

    def link_contradiction(
        self,
        claim_a_id: str,
        claim_b_id: str,
        tenant_id: str,
        similarity: float,
        review_id: Optional[str] = None,
    ) -> None:
        """Arista CONTRADICTS bidireccional entre dos claims."""
        self.graph.query(
            """
            MATCH (a:Claim {tenant_id: $tenant_id, id: $claim_a_id}),
                  (b:Claim {tenant_id: $tenant_id, id: $claim_b_id})
            MERGE (a)-[r:CONTRADICTS]->(b)
            SET r.similarity = $similarity,
                r.review_id  = $review_id
            """,
            {
                "claim_a_id": claim_a_id,
                "claim_b_id": claim_b_id,
                "tenant_id":  tenant_id,
                "similarity": similarity,
                "review_id":  review_id or "",
            },
        )

    def link_contradictions_between_chunks(
        self,
        tenant_id: str,
        new_chunk_id: int,
        existing_chunk_id: int,
        similarity: float,
        review_id: Optional[str] = None,
    ) -> int:
        """
        Crea aristas CONTRADICTS entre claims de dos chunks con MISMO predicate
        y VALORES distintos, validando semánticamente con Mistral que sean
        incompatibles antes de crear la arista.

        El filtro de subject se eliminó: era demasiado estricto y bloqueaba
        pares reales como "política vacaciones" vs "política de vacaciones para
        empleados asalariados" (mismo concepto, nombre ligeramente distinto).
        La validación semántica actúa como filtro de calidad.

        Returns:
            Número de aristas CONTRADICTS creadas
        """
        try:
            from src.llm_client import get_llm_client  # desde raíz del proyecto
        except ModuleNotFoundError:
            from llm_client import get_llm_client  # desde scripts/ con src/ en sys.path
        llm = get_llm_client()

        try:
            # Recuperar todos los pares candidatos: mismo predicate, valor distinto
            candidates = self.graph.query(
                f"""
                MATCH (cA:Claim {{tenant_id: '{tenant_id}', chunk_id: {new_chunk_id}}}),
                      (cB:Claim {{tenant_id: '{tenant_id}', chunk_id: {existing_chunk_id}}})
                WHERE cA.predicate = cB.predicate
                  AND cA.value <> cB.value
                RETURN id(cA) AS idA, cA.subject, cA.predicate, cA.value,
                       id(cB) AS idB, cB.subject, cB.predicate, cB.value
                """
            )
            if not candidates.result_set:
                return 0

            added = 0
            for row in candidates.result_set:
                idA, sA, pA, vA, idB, sB, pB, vB = row
                if not llm.is_semantic_contradiction(sA, pA, vA, sB, pB, vB):
                    logger.debug(f"  ⬜ No contradicción semántica: [{sA}]--{pA}-->[{vA}] vs [{sB}]--{pB}-->[{vB}]")
                    continue
                # Crear arista
                self.graph.query(
                    f"""
                    MATCH (cA:Claim {{tenant_id: '{tenant_id}', chunk_id: {new_chunk_id}}}),
                          (cB:Claim {{tenant_id: '{tenant_id}', chunk_id: {existing_chunk_id}}})
                    WHERE id(cA) = {idA} AND id(cB) = {idB}
                    MERGE (cA)-[r:CONTRADICTS]->(cB)
                    SET r.similarity = {float(similarity)},
                        r.review_id  = '{review_id or ""}'
                    """
                )
                logger.info(f"  🔴 CONTRADICTS: [{sA}]--{pA}-->[{vA}] vs [{sB}]--{pB}-->[{vB}]")
                added += 1
            return added
        except Exception as e:
            logger.warning(f"Error vinculando contradicciones en grafo: {e}")
        return 0

    # ─── Update de estados (sincronización con Supabase) ──────────────────────

    def update_chunk_status(self, chunk_id: int, tenant_id: str, status: str) -> None:
        """Sincroniza el chunk_status del grafo con el de Supabase."""
        self.graph.query(
            """
            MATCH (c:Chunk {tenant_id: $tenant_id, id: $chunk_id})
            SET c.chunk_status = $status
            WITH c
            MATCH (c)-[:HAS_CLAIM]->(cl:Claim)
            SET cl.chunk_status = $status
            """,
            {"chunk_id": chunk_id, "tenant_id": tenant_id, "status": status},
        )

    # ─── Queries de lectura (RLS aplicada en el caller) ───────────────────────

    def find_claims_by_entity(
        self,
        tenant_id: str,
        entity_name: str,
        allowed_space_ids: Optional[List[str]] = None,
        only_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Busca todos los claims sobre una entidad dada (con filtros RLS).

        Args:
            tenant_id:          Aislamiento entre clientes
            entity_name:        Nombre normalizado (lowercase)
            allowed_space_ids:  Lista de spaces permitidos para el usuario (RLS)
            only_active:        Si True, solo chunks active (excluye superseded/disputed)
        """
        cypher = """
        MATCH (cl:Claim {tenant_id: $tenant_id})-[:ABOUT_ENTITY]->(e:Entity {tenant_id: $tenant_id, name: $entity_name})
        MATCH (c:Chunk {tenant_id: $tenant_id, id: cl.chunk_id})
        WHERE c.space_id IN $space_ids
        """
        if only_active:
            cypher += " AND cl.chunk_status = 'active'"

        cypher += """
        OPTIONAL MATCH (cl)-[con:CONTRADICTS]-(other:Claim)
        RETURN cl.subject AS subject,
               cl.predicate AS predicate,
               cl.value AS value,
               cl.chunk_status AS status,
               cl.chunk_id AS chunk_id,
               c.document_id AS document_id,
               count(other) AS contradictions
        """

        params = {
            "tenant_id":   tenant_id,
            "entity_name": entity_name.strip().lower(),
            "space_ids":   allowed_space_ids or [],
        }
        result = self.graph.query(cypher, params)
        return self._rows_to_dicts(result)

    def find_claims_by_predicate(
        self,
        tenant_id: str,
        predicate_keywords: List[str],
        allowed_space_ids: Optional[List[str]] = None,
        only_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Busca claims cuyo predicate o subject contengan alguna keyword.
        Usado por el search híbrido cuando no se identifica entidad específica.
        """
        cypher = """
        MATCH (cl:Claim {tenant_id: $tenant_id})
        MATCH (c:Chunk {tenant_id: $tenant_id, id: cl.chunk_id})
        WHERE c.space_id IN $space_ids
          AND (
        """
        like_clauses = []
        params: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "space_ids": allowed_space_ids or [],
        }
        for i, kw in enumerate(predicate_keywords):
            kw_param = f"kw_{i}"
            like_clauses.append(
                f"cl.predicate CONTAINS ${kw_param} OR cl.subject CONTAINS ${kw_param} OR cl.value CONTAINS ${kw_param}"
            )
            params[kw_param] = kw.strip().lower()
        cypher += " OR ".join(like_clauses) + " )"

        if only_active:
            cypher += " AND cl.chunk_status = 'active'"

        # Subimos el LIMIT a 50 para que el reranking en Python (ver
        # _graph_context en search.py) tenga material suficiente cuando una
        # keyword genérica como "política" satura el match por subject.
        cypher += """
        RETURN cl.subject AS subject,
               cl.predicate AS predicate,
               cl.value AS value,
               cl.chunk_status AS status,
               cl.chunk_id AS chunk_id,
               c.document_id AS document_id
        LIMIT 50
        """
        result = self.graph.query(cypher, params)
        return self._rows_to_dicts(result)

    def find_claims_semantic(
        self,
        tenant_id: str,
        query_embedding: List[float],
        allowed_space_ids: Optional[List[str]] = None,
        top_k: int = 10,
        only_active: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Rerank semántico de claims por cosine similarity contra el embedding
        de la query.

        FalkorDB no tiene índice vectorial nativo, así que hacemos scan +
        cálculo en Python. Con ~hundreds de claims por tenant es instantáneo
        (dot product de vectores 768 dims × ~250 claims = ~milisegundos).

        Args:
            tenant_id: tenant para RLS
            query_embedding: vector 768 dims de la query (nomic-embed-text)
            allowed_space_ids: lista de space_ids accesibles al usuario
            top_k: número de claims a devolver
            only_active: filtra por chunk_status='active'

        Returns:
            Lista de claims con campo extra `semantic_score` (cosine similarity).
            Solo incluye claims que tengan embedding guardado.
        """
        import math

        cypher = """
        MATCH (cl:Claim {tenant_id: $tenant_id})
        MATCH (c:Chunk {tenant_id: $tenant_id, id: cl.chunk_id})
        WHERE c.space_id IN $space_ids
          AND cl.embedding IS NOT NULL
        """
        if only_active:
            cypher += " AND cl.chunk_status = 'active'"
        cypher += """
        RETURN cl.subject AS subject,
               cl.predicate AS predicate,
               cl.value AS value,
               cl.chunk_status AS status,
               cl.chunk_id AS chunk_id,
               c.document_id AS document_id,
               cl.embedding AS embedding
        """
        params = {
            "tenant_id": tenant_id,
            "space_ids": allowed_space_ids or [],
        }
        result = self.graph.query(cypher, params)
        rows = self._rows_to_dicts(result)

        # Cosine similarity en Python — los embeddings ya están normalizados
        # por nomic-embed-text, así que basta con el dot product.
        def cosine(v1, v2):
            dot = sum(a * b for a, b in zip(v1, v2))
            n1 = math.sqrt(sum(a * a for a in v1))
            n2 = math.sqrt(sum(b * b for b in v2))
            if n1 == 0 or n2 == 0:
                return 0.0
            return dot / (n1 * n2)

        for r in rows:
            emb = r.pop("embedding", None) or []
            r["semantic_score"] = cosine(query_embedding, emb) if emb else 0.0

        rows.sort(key=lambda r: r["semantic_score"], reverse=True)
        return rows[:top_k]

    def get_contradictions(
        self,
        tenant_id: str,
        allowed_space_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Devuelve todas las contradicciones del tenant para vista admin.
        """
        cypher = """
        MATCH (a:Claim {tenant_id: $tenant_id})-[r:CONTRADICTS]->(b:Claim {tenant_id: $tenant_id})
        MATCH (ca:Chunk {tenant_id: $tenant_id, id: a.chunk_id}),
              (cb:Chunk {tenant_id: $tenant_id, id: b.chunk_id})
        WHERE ca.space_id IN $space_ids AND cb.space_id IN $space_ids
        RETURN a.subject AS subject,
               a.predicate AS predicate,
               a.value AS value_a,
               b.value AS value_b,
               r.similarity AS similarity,
               r.review_id AS review_id,
               a.chunk_status AS status_a,
               b.chunk_status AS status_b,
               id(a) AS node_a_id,
               id(b) AS node_b_id
        """
        params = {
            "tenant_id": tenant_id,
            "space_ids": allowed_space_ids or [],
        }
        result = self.graph.query(cypher, params)
        return self._rows_to_dicts(result)

    def get_tenant_subgraph(
        self,
        tenant_id: str,
        allowed_space_ids: Optional[List[str]] = None,
        limit: int = 200,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Devuelve nodos y aristas del grafo del tenant en formato apto para vis-network.
        Limita para evitar respuestas gigantes.
        """
        node_q = """
        MATCH (n)
        WHERE n.tenant_id = $tenant_id
          AND (NOT EXISTS(n.space_id) OR n.space_id IN $space_ids)
        RETURN labels(n)[0] AS kind, id(n) AS internal_id,
               n.id AS node_id, n.name AS name, n.subject AS subject,
               n.predicate AS predicate, n.value AS value,
               n.filename AS filename, n.chunk_status AS chunk_status,
               n.kind AS entity_kind
        LIMIT $limit
        """
        # Dos queries para las aristas: las CONTRADICTS SIEMPRE entran (son lo
        # más relevante visualmente y son pocas); el resto con LIMIT para no
        # saturar la respuesta.
        contradicts_q = """
        MATCH (a)-[r:CONTRADICTS]->(b)
        WHERE a.tenant_id = $tenant_id AND b.tenant_id = $tenant_id
        RETURN id(a) AS source, id(b) AS target, type(r) AS kind
        """
        other_edges_q = """
        MATCH (a)-[r]->(b)
        WHERE a.tenant_id = $tenant_id AND b.tenant_id = $tenant_id
          AND type(r) <> 'CONTRADICTS'
          AND (NOT EXISTS(a.space_id) OR a.space_id IN $space_ids)
          AND (NOT EXISTS(b.space_id) OR b.space_id IN $space_ids)
        RETURN id(a) AS source, id(b) AS target, type(r) AS kind
        LIMIT $limit
        """
        params = {
            "tenant_id": tenant_id,
            "space_ids": allowed_space_ids or [],
            "limit":     limit,
        }
        nodes = self._rows_to_dicts(self.graph.query(node_q, params))
        contradicts = self._rows_to_dicts(self.graph.query(contradicts_q, params))
        others      = self._rows_to_dicts(self.graph.query(other_edges_q, params))
        return {"nodes": nodes, "edges": contradicts + others}

    # ─── Mantenimiento ────────────────────────────────────────────────────────

    def delete_all(self) -> None:
        """Elimina todo el grafo (peligroso, usar solo en tests/backfill)."""
        try:
            self.graph.delete()
        except Exception as e:
            logger.warning(f"Error borrando grafo: {e}")

    def delete_document(self, document_id: str, tenant_id: str) -> None:
        """Borra un documento y sus chunks/claims asociados."""
        self.graph.query(
            """
            MATCH (d:Document {tenant_id: $tenant_id, id: $document_id})
            OPTIONAL MATCH (d)-[:CONTAINS]->(c:Chunk)
            OPTIONAL MATCH (c)-[:HAS_CLAIM]->(cl:Claim)
            DETACH DELETE d, c, cl
            """,
            {"document_id": document_id, "tenant_id": tenant_id},
        )

    # ─── Helpers internos ─────────────────────────────────────────────────────

    @staticmethod
    def _rows_to_dicts(result) -> List[Dict[str, Any]]:
        """Convierte el resultado de FalkorDB a lista de dicts.

        El header puede venir como objeto con .name (driver moderno) o como
        tupla [type_int, name] (formato antiguo).
        """
        if not hasattr(result, "result_set"):
            return []
        headers = []
        for h in (result.header or []):
            if hasattr(h, "name"):
                headers.append(h.name)
            elif isinstance(h, (list, tuple)) and len(h) >= 2:
                headers.append(str(h[1]))
            else:
                headers.append(str(h))
        rows = []
        for r in (result.result_set or []):
            rows.append(dict(zip(headers, r)))
        return rows


# ─── Singleton ───────────────────────────────────────────────────────────────

_graph_client: Optional[GraphClient] = None


def get_graph_client() -> GraphClient:
    """Devuelve la instancia global del cliente (la crea si no existe)."""
    global _graph_client
    if _graph_client is None:
        _graph_client = GraphClient()
        _graph_client.ensure_indexes()
    return _graph_client


if __name__ == "__main__":
    # Test de humo
    gc = get_graph_client()
    gc.upsert_document(
        document_id="test-doc-1",
        tenant_id="t1",
        space_id="s1",
        filename="test.pdf",
        version_ts="2026-06-09",
    )
    gc.upsert_chunk(
        chunk_id=1, document_id="test-doc-1",
        tenant_id="t1", space_id="s1",
        chunk_index=0, chunk_status="active",
    )
    gc.upsert_entity(tenant_id="t1", name="política PCA", kind="Concepto")
    gc.link_chunk_to_entity(chunk_id=1, tenant_id="t1", entity_name="política PCA")
    gc.upsert_claim(
        claim_id="cl-1", tenant_id="t1", chunk_id=1,
        subject="política PCA",
        predicate="jornada mínima",
        value="35 horas/semana",
    )
    print("✓ Test upsert OK")

    claims = gc.find_claims_by_entity(
        tenant_id="t1", entity_name="política PCA",
        allowed_space_ids=["s1"],
    )
    print(f"✓ Claims encontrados: {claims}")

    sg = gc.get_tenant_subgraph(tenant_id="t1", allowed_space_ids=["s1"])
    print(f"✓ Subgraph: {len(sg['nodes'])} nodos, {len(sg['edges'])} aristas")

    gc.delete_document("test-doc-1", "t1")
    print("✓ Cleanup OK")
