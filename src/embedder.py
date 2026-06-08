"""
Embedder module — Wrapper para Ollama + nomic-embed-text.

Este módulo proporciona una interfaz simple para generar embeddings
usando nomic-embed-text a través de Ollama (local).

El modelo es FIJO: nomic-embed-text (384 dims)
Nunca cambiar el modelo sin re-ingestar todo.
"""

import os
import requests
import numpy as np
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
EMBED_DIMS = 384


class Embedder:
    """
    Wrapper para Ollama embeddings.

    Attributes:
        base_url (str): URL base de Ollama
        model (str): Nombre del modelo (fijo: nomic-embed-text)
        dims (int): Dimensionalidad del embedding (384)
    """

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = EMBED_MODEL):
        """
        Inicializa el embedder.

        Args:
            base_url: URL de Ollama (default: http://localhost:11434)
            model: Modelo a usar (default: nomic-embed-text)

        Raises:
            ConnectionError: Si Ollama no responde
        """
        self.base_url = base_url
        self.model = model
        self.dims = EMBED_DIMS

        # Verificar que Ollama está accesible
        self._check_connection()

    def _check_connection(self) -> None:
        """Verifica que Ollama está corriendo y el modelo existe."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()

            # Verificar que el modelo existe
            tags = response.json().get("models", [])
            model_names = [m.get("name", "") for m in tags]

            if not any(self.model in name for name in model_names):
                raise ValueError(
                    f"Modelo '{self.model}' no encontrado en Ollama. "
                    f"Modelos disponibles: {model_names}"
                )

            print(f"✓ Ollama conexión OK ({self.model})")

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"No se puede conectar a Ollama en {self.base_url}. "
                f"¿Está levantado? (docker-compose up -d)"
            ) from e

    def embed_text(self, text: str) -> np.ndarray:
        """
        Genera un embedding para un texto.

        Args:
            text: Texto a embedear

        Returns:
            np.ndarray: Vector de embedding (384 dims)

        Raises:
            RuntimeError: Si Ollama falla
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=30
            )
            response.raise_for_status()

            embeddings = response.json().get("embeddings", [])
            if not embeddings:
                raise RuntimeError("Ollama no retornó embeddings")

            # Primer embedding (input es string, no lista)
            embedding = embeddings[0]
            return np.array(embedding, dtype=np.float32)

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error en Ollama embed: {e}") from e

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Genera embeddings para múltiples textos (batch).

        Args:
            texts: Lista de textos a embedear

        Returns:
            List[np.ndarray]: Lista de vectores (384 dims cada uno)

        Raises:
            RuntimeError: Si Ollama falla
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=60
            )
            response.raise_for_status()

            embeddings_list = response.json().get("embeddings", [])
            if not embeddings_list:
                raise RuntimeError("Ollama no retornó embeddings")

            return [np.array(emb, dtype=np.float32) for emb in embeddings_list]

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error en Ollama embed batch: {e}") from e

    def validate_embedding(self, embedding: np.ndarray) -> bool:
        """
        Valida que un embedding tiene la dimensión correcta.

        Args:
            embedding: Vector a validar

        Returns:
            bool: True si la dimensión es correcta (384)
        """
        return len(embedding) == self.dims

    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """
        Calcula similitud coseno entre dos embeddings.

        Args:
            v1: Primer vector
            v2: Segundo vector

        Returns:
            float: Similitud (0-1)
        """
        # Normalizar
        v1_norm = v1 / (np.linalg.norm(v1) + 1e-10)
        v2_norm = v2 / (np.linalg.norm(v2) + 1e-10)

        # Cosine similarity = dot product of normalized vectors
        return float(np.dot(v1_norm, v2_norm))


# Instancia global (singleton)
_embedder = None


def get_embedder() -> Embedder:
    """
    Obtiene o crea la instancia global del Embedder.

    Returns:
        Embedder: Instancia del embedder
    """
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


if __name__ == "__main__":
    # Test simple
    embedder = get_embedder()

    # Single embedding
    text = "Este es un documento de prueba para Korio."
    vec = embedder.embed_text(text)
    print(f"Embedding shape: {vec.shape}")
    print(f"Primeros 5 dims: {vec[:5]}")

    # Batch embeddings
    texts = [
        "Hospital San Juan",
        "Documentación clínica",
        "Protocolo de admisión"
    ]
    vecs = embedder.embed_batch(texts)
    print(f"\nBatch: {len(vecs)} embeddings generados")

    # Similitud
    sim = embedder.cosine_similarity(vecs[0], vecs[1])
    print(f"Similitud entre textos 0 y 1: {sim:.4f}")
