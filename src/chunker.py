"""
Chunker module — Divide documentos en chunks para embeddings.

Usa LangChain RecursiveTextSplitter para dividir documentos de forma inteligente
(por párrafos, oraciones, palabras) manteniendo contexto.

Configuración:
- chunk_size: 400-500 tokens (aprox. 2000-2500 caracteres)
- chunk_overlap: 50 tokens (para contexto)
"""

from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Tuple
import re


class DocumentChunker:
    """
    Divide documentos en chunks manteniendo contexto.

    Attributes:
        chunk_size (int): Tamaño del chunk en caracteres (~400-500 tokens)
        chunk_overlap (int): Solapamiento entre chunks
        separators (List[str]): Separadores para dividir (párrafo, línea, palabra)
    """

    def __init__(
        self,
        chunk_size: int = 2000,  # ~400-500 tokens
        chunk_overlap: int = 200  # ~50 tokens solapamiento
    ):
        """
        Inicializa el chunker.

        Args:
            chunk_size: Tamaño del chunk en caracteres (default: 2000)
            chunk_overlap: Solapamiento en caracteres (default: 200)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Separadores: párrafo → línea → palabra → carácter
        self.separators = [
            "\n\n",  # Párrafos
            "\n",    # Líneas
            ". ",    # Oraciones
            " ",     # Palabras
            ""       # Caracteres
        ]

        self.splitter = RecursiveCharacterTextSplitter(
            separators=self.separators,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len
        )

    def chunk_text(self, text: str) -> List[str]:
        """
        Divide un texto en chunks.

        Args:
            text: Texto a dividir

        Returns:
            List[str]: Lista de chunks
        """
        if not text or not text.strip():
            return []

        chunks = self.splitter.split_text(text)
        return chunks

    def chunk_with_metadata(
        self,
        text: str,
        source_id: str,
        document_title: str
    ) -> List[Tuple[str, dict]]:
        """
        Divide un texto en chunks manteniendo metadata.

        Args:
            text: Texto a dividir
            source_id: ID del documento (UUID)
            document_title: Título del documento

        Returns:
            List[Tuple[str, dict]]: Lista de (chunk_text, metadata)
        """
        chunks = self.chunk_text(text)

        chunks_with_meta = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source_id": source_id,
                "chunk_index": i,
                "document_title": document_title,
                "total_chunks": len(chunks),
                "chunk_size": len(chunk)
            }
            chunks_with_meta.append((chunk, metadata))

        return chunks_with_meta

    def estimate_tokens(self, text: str) -> int:
        """
        Estima el número de tokens en un texto.

        Aproximación simple: 1 token ≈ 4 caracteres
        (En realidad depende del modelo, pero para nomic-embed es cercano)

        Args:
            text: Texto a estimar

        Returns:
            int: Número estimado de tokens
        """
        return len(text) // 4

    def validate_chunks(self, chunks: List[str]) -> dict:
        """
        Valida los chunks generados.

        Args:
            chunks: Lista de chunks

        Returns:
            dict: Estadísticas de validación
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "valid": False,
                "message": "Sin chunks generados"
            }

        sizes = [len(chunk) for chunk in chunks]
        tokens = [self.estimate_tokens(chunk) for chunk in chunks]

        return {
            "total_chunks": len(chunks),
            "min_size": min(sizes),
            "max_size": max(sizes),
            "avg_size": sum(sizes) / len(sizes),
            "min_tokens": min(tokens),
            "max_tokens": max(tokens),
            "avg_tokens": sum(tokens) / len(tokens),
            "valid": all(size > 0 for size in sizes),
            "within_limits": all(
                self.chunk_size * 0.5 <= size <= self.chunk_size * 1.5
                for size in sizes[:-1]  # Except last chunk which may be smaller
            )
        }


# Singleton
_chunker = None


def get_chunker() -> DocumentChunker:
    """
    Obtiene o crea la instancia global del Chunker.

    Returns:
        DocumentChunker: Instancia del chunker
    """
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker


if __name__ == "__main__":
    # Test simple
    chunker = get_chunker()

    # Documento de prueba
    sample_text = """
    Hospital San Juan

    Protocolo de Admisión de Pacientes

    1. Información General
    Los pacientes que ingresan al hospital deben proporcionar información de contacto completa.
    Se requiere documento de identidad y número de seguridad social.

    2. Procedimientos Iniciales
    - Registro de datos personales
    - Evaluación médica inicial
    - Asignación de habitación

    3. Derechos del Paciente
    El paciente tiene derecho a recibir atención médica de calidad, información clara sobre su
    tratamiento y confidencialidad de sus datos médicos.

    Este es un documento extenso que será dividido en chunks de tamaño manejable.
    Cada chunk mantendrá contexto suficiente para embeddings de calidad.
    """

    # Chunking simple
    chunks = chunker.chunk_text(sample_text)
    print(f"Chunks generados: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i} ({len(chunk)} chars) ---")
        print(chunk[:100] + "...")

    # Con metadata
    chunks_meta = chunker.chunk_with_metadata(
        sample_text,
        source_id="doc-001",
        document_title="Protocolo Hospital San Juan"
    )
    print(f"\n\nChunks con metadata: {len(chunks_meta)}")
    for chunk, meta in chunks_meta[:2]:
        print(f"Chunk {meta['chunk_index']}: {meta}")

    # Validación
    stats = chunker.validate_chunks(chunks)
    print(f"\n\nValidación: {stats}")
