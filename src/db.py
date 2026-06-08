"""
Database module — Conexión a Supabase con RLS.

Maneja:
- Conexión a Supabase (pgvector)
- Autenticación con JWT
- RLS early binding (verificar permiso antes de query)

RLS CRÍTICO:
Las queries NUNCA deben acceder directamente a datos sin verificar
que el usuario tiene permiso. El early binding se hace en la applicación
(no solo en BD) para mayor seguridad.
"""

import os
from typing import Optional, List, Dict
from dotenv import load_dotenv

try:
    from supabase import create_client
    from supabase.client import Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase no instalado. Instalalo con: pip install supabase")

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


class SupabaseClient:
    """
    Cliente Supabase con soporte para RLS.

    Attributes:
        client: Cliente Supabase (service_role para administración)
        anon_client: Cliente con permiso anon (respeta RLS)
    """

    def __init__(
        self,
        url: Optional[str] = None,
        service_role_key: Optional[str] = None,
        anon_key: Optional[str] = None
    ):
        """
        Inicializa el cliente Supabase.

        Args:
            url: URL de Supabase (default: env var)
            service_role_key: Service role key para admin (default: env var)
            anon_key: Anon key para RLS (default: env var)

        Raises:
            ImportError: Si Supabase no está instalado
            ValueError: Si faltan variables de entorno
        """
        if not SUPABASE_AVAILABLE:
            raise ImportError("Supabase no instalado. pip install supabase")

        self.url = url or SUPABASE_URL
        self.service_role_key = service_role_key or SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = anon_key or SUPABASE_ANON_KEY

        if not all([self.url, self.service_role_key, self.anon_key]):
            raise ValueError(
                "Faltan variables de entorno: SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY"
            )

        # Cliente con service_role (bypass RLS para admin)
        self.client = create_client(self.url, self.service_role_key)

        # Cliente anon (respeta RLS)
        self.anon_client = create_client(self.url, self.anon_key)

        self._check_connection()

    def _check_connection(self) -> None:
        """Verifica que la conexión a Supabase funciona."""
        try:
            # Intentar una query simple
            self.client.table("tenants").select("id").limit(1).execute()
            print("✓ Supabase conexión OK")
        except Exception as e:
            raise ConnectionError(f"Error conectando a Supabase: {e}") from e

    def table(self, table_name: str):
        """
        Delegación directa al cliente Supabase (service_role).
        Permite usar supabase.table(...) en lugar de supabase.client.table(...)
        """
        return self.client.table(table_name)

    def insert_documents(self, documents: List[Dict]) -> dict:
        """
        Inserta documentos (bypass RLS, admin only).

        Args:
            documents: Lista de documentos a insertar

        Returns:
            dict: Respuesta de Supabase

        Raises:
            Exception: Si falla la inserción
        """
        try:
            response = self.client.table("documents").insert(documents).execute()
            return response.data
        except Exception as e:
            raise RuntimeError(f"Error insertando documentos: {e}") from e

    def insert_embeddings(self, embeddings: List[Dict]) -> dict:
        """
        Inserta embeddings (chunks con vectores).

        Args:
            embeddings: Lista de embeddings a insertar

        Returns:
            dict: Respuesta de Supabase

        Raises:
            Exception: Si falla la inserción
        """
        try:
            response = self.client.table("embeddings").insert(embeddings).execute()
            return response.data
        except Exception as e:
            raise RuntimeError(f"Error insertando embeddings: {e}") from e

    def search_embeddings_rls(
        self,
        query_vector: List[float],
        user_id: str,
        limit: int = 5,
        threshold: float = 0.5
    ) -> List[Dict]:
        """
        Busca embeddings respetando RLS (early binding).

        CRÍTICO: Esta función verifica RLS ANTES de buscar:
        1. Obtener espacios permitidos del usuario
        2. Obtener documentos en esos espacios
        3. Buscar vectores en esos documentos

        Args:
            query_vector: Vector de la query (384 dims)
            user_id: ID del usuario (para RLS)
            limit: Número de resultados (default: 5)
            threshold: Similitud mínima (0-1, default: 0.5)

        Returns:
            List[Dict]: Chunks similares

        Raises:
            ValueError: Si RLS falla o usuario no tiene acceso
        """
        try:
            # Step 1: Obtener espacios permitidos del usuario
            user_spaces = self.client.table("user_spaces").select("space_id").eq(
                "user_id", user_id
            ).execute()

            if not user_spaces.data:
                raise ValueError(f"Usuario {user_id} no tiene espacios asignados")

            space_ids = [row["space_id"] for row in user_spaces.data]

            # Step 2: Obtener documentos en esos espacios
            docs = self.client.table("documents").select("id").in_(
                "space_id", space_ids
            ).execute()

            if not docs.data:
                return []  # No hay documentos en los espacios del usuario

            document_ids = [row["id"] for row in docs.data]

            # Step 3: Buscar embeddings en esos documentos
            # Supabase puede hacer vector search con pgvector
            # Usando similitud coseno
            response = self.client.rpc(
                "search_embeddings",
                {
                    "query_embedding": query_vector,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "allowed_doc_ids": document_ids
                }
            ).execute()

            return response.data or []

        except Exception as e:
            raise RuntimeError(f"Error en búsqueda RLS: {e}") from e

    def log_audit(
        self,
        tenant_id: str,
        user_id: str,
        query: str,
        doc_ids_used: List[str],
        model_used: str,
        latency_ms: int,
        has_conflict: bool = False
    ) -> dict:
        """
        Registra una query en el audit log.

        Args:
            tenant_id: ID del tenant
            user_id: ID del usuario
            query: Texto de la query
            doc_ids_used: Documentos usados
            model_used: Modelo LLM usado
            latency_ms: Latencia en ms
            has_conflict: Si hay conflicto en resultados

        Returns:
            dict: Registro creado
        """
        try:
            response = self.client.table("audit_log").insert({
                "tenant_id": tenant_id,
                "user_id": user_id,
                "query": query,
                "doc_ids_used": doc_ids_used,
                "model_used": model_used,
                "latency_ms": latency_ms,
                "has_conflict": has_conflict
            }).execute()
            return response.data
        except Exception as e:
            print(f"⚠️ Error en audit log: {e}")
            return {}

    def get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """
        Obtiene un documento por ID (admin).

        Args:
            document_id: ID del documento

        Returns:
            Optional[Dict]: Documento o None si no existe
        """
        try:
            response = self.client.table("documents").select("*").eq(
                "id", document_id
            ).single().execute()
            return response.data
        except Exception:
            return None

    def verify_user_access(
        self,
        user_id: str,
        document_id: str
    ) -> bool:
        """
        Verifica que un usuario tiene acceso a un documento (RLS).

        Args:
            user_id: ID del usuario
            document_id: ID del documento

        Returns:
            bool: True si tiene acceso, False si no

        Raises:
            Exception: Si hay error en verificación
        """
        try:
            # Obtener espacios del usuario
            user_spaces = self.client.table("user_spaces").select("space_id").eq(
                "user_id", user_id
            ).execute()

            space_ids = [row["space_id"] for row in user_spaces.data]

            # Verificar que el documento está en uno de esos espacios
            doc = self.client.table("documents").select("space_id").eq(
                "id", document_id
            ).single().execute()

            return doc.data["space_id"] in space_ids if doc.data else False

        except Exception as e:
            raise RuntimeError(f"Error verificando acceso: {e}") from e


# Singleton
_db_client = None


def get_supabase_client() -> SupabaseClient:
    """
    Obtiene o crea la instancia global del cliente Supabase.

    Returns:
        SupabaseClient: Instancia del cliente

    Raises:
        ValueError: Si faltan variables de entorno
    """
    global _db_client
    if _db_client is None:
        _db_client = SupabaseClient()
    return _db_client


if __name__ == "__main__":
    # Test simple
    try:
        db = get_supabase_client()

        # Verificar acceso
        user_id = "a2000000-0000-0000-0000-000000000001"  # Doctor
        doc_id = "doc-test-001"

        has_access = db.verify_user_access(user_id, doc_id)
        print(f"Usuario {user_id} tiene acceso a {doc_id}: {has_access}")

    except Exception as e:
        print(f"❌ Error: {e}")
