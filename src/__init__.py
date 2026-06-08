"""
Korio — Company Brain TFM

Módulos principales:
- embedder: Ollama + nomic-embed-text
- chunker: RecursiveTextSplitter
- preprocessor: MarkItDown + Presidio (PII)
- db: Supabase + RLS
- ingest: Pipeline completo de ingesta
- utils: Funciones auxiliares
"""

__version__ = "0.1.0"
__author__ = "Heriberto Noguera"

from src.embedder import get_embedder
from src.chunker import get_chunker
from src.preprocessor import get_preprocessor
from src.db import get_supabase_client

__all__ = [
    "get_embedder",
    "get_chunker",
    "get_preprocessor",
    "get_supabase_client",
]
