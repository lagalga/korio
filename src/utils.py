"""
Utils module — Funciones auxiliares.

Utilidades para:
- Validación
- Logging
- Conversiones
- Helpers generales
"""

import uuid
import hashlib
import json
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def generate_uuid() -> str:
    """Genera un UUID v4."""
    return str(uuid.uuid4())


def generate_content_hash(content: str) -> str:
    """
    Genera un hash SHA256 del contenido para deduplicación.

    Args:
        content: Contenido a hashear

    Returns:
        str: Hash hexadecimal
    """
    return hashlib.sha256(content.encode()).hexdigest()


def validate_uuid(value: str) -> bool:
    """
    Valida que una cadena es un UUID válido.

    Args:
        value: Valor a validar

    Returns:
        bool: True si es UUID válido
    """
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def validate_email(email: str) -> bool:
    """
    Validación básica de email.

    Args:
        email: Email a validar

    Returns:
        bool: True si parece válido
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def file_exists(file_path: str) -> bool:
    """Verifica que un archivo existe."""
    return Path(file_path).exists()


def get_file_size(file_path: str) -> int:
    """Obtiene tamaño de archivo en bytes."""
    try:
        return Path(file_path).stat().st_size
    except Exception as e:
        logger.error(f"Error obteniendo tamaño de {file_path}: {e}")
        return 0


def format_size(bytes_size: int) -> str:
    """
    Formatea tamaño en bytes a legible.

    Args:
        bytes_size: Tamaño en bytes

    Returns:
        str: Tamaño formateado (ej: "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def estimate_tokens(text: str, model: str = "nomic-embed") -> int:
    """
    Estima tokens en un texto.

    Aproximación: 1 token ≈ 4 caracteres
    (Varía por modelo, pero es una buena aproximación)

    Args:
        text: Texto a estimar
        model: Modelo (para futuras mejoras)

    Returns:
        int: Tokens estimados
    """
    return len(text) // 4


def json_serializable(obj: Any) -> Any:
    """
    Convierte objetos a JSON-serializable.

    Args:
        obj: Objeto a convertir

    Returns:
        Any: Objeto convertible a JSON
    """
    import numpy as np

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, Path):
        return str(obj)
    return obj


def safe_json_dumps(obj: Dict, indent: int = 2) -> str:
    """
    Convierte objeto a JSON string de forma segura.

    Args:
        obj: Diccionario a serializar
        indent: Indentación

    Returns:
        str: JSON string
    """
    return json.dumps(obj, default=json_serializable, indent=indent)


def safe_json_loads(json_str: str) -> Optional[Dict]:
    """
    Parsea JSON string de forma segura.

    Args:
        json_str: JSON string

    Returns:
        Optional[Dict]: Diccionario o None si falla
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Error parseando JSON: {e}")
        return None


class Timer:
    """Context manager para medir tiempo."""

    def __init__(self, name: str = "Operation"):
        """
        Args:
            name: Nombre de la operación
        """
        self.name = name
        self.elapsed = 0
        self.start_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.elapsed = time.time() - self.start_time
        logger.info(f"{self.name} took {self.elapsed:.2f}s")


# Logging helper
def setup_logging(level: str = "INFO") -> None:
    """
    Configura logging global.

    Args:
        level: Nivel de log (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("korio.log")
        ]
    )


if __name__ == "__main__":
    # Test simple
    print(f"UUID: {generate_uuid()}")
    print(f"Email válido: {validate_email('test@example.com')}")
    print(f"Tamaño: {format_size(1024 * 1024 * 5)}")  # 5 MB
    print(f"Tokens (100 chars): {estimate_tokens('x' * 100)}")

    with Timer("Test operation"):
        import time
        time.sleep(0.5)
