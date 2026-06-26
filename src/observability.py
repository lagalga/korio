"""
Observabilidad — wrapper fino sobre LangSmith (@traceable).

Objetivo: instrumentar el pipeline RAG (búsqueda, embedding, generación LLM)
con trazas distribuidas en LangSmith SIN añadir una dependencia dura ni romper
entornos sin la API key.

Comportamiento degradado seguro:
- Si `langsmith` no está instalado          → `traceable` es el decorador identidad.
- Si LANGCHAIN_TRACING_V2 != "true"          → langsmith no envía nada (no-op interno).
- `record_llm_usage()` adjunta tokens al run → habilita el cálculo de coste €/tokens.

Esto permite que tests, CI y el fallback Ollama offline funcionen igual con o
sin observabilidad activa. Sesión 18 (Observabilidad y Evaluación).
"""

import logging

# IMPORTANTE: cargar el .env ANTES de importar langsmith. Este módulo es de los
# primeros en importarse en el árbol (embedder/llm_client/search lo importan al
# tope), y langsmith decide si el tracing está activo leyendo LANGCHAIN_TRACING_V2
# en el import. Si load_dotenv() corre después, langsmith ve la var ausente y
# deja el tracing apagado aunque esté en el .env. Cargar aquí elimina ese race.
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable as _ls_traceable
    from langsmith.run_helpers import get_current_run_tree
    _LANGSMITH_AVAILABLE = True
except Exception:  # langsmith no instalado
    _LANGSMITH_AVAILABLE = False


def traceable(*decorator_args, **decorator_kwargs):
    """
    Decorador @traceable seguro.

    Si langsmith está disponible, delega en el real. Si no, devuelve un
    decorador identidad. Soporta las dos formas de uso:
        @traceable                      (sin paréntesis)
        @traceable(name=..., run_type=) (con argumentos)
    """
    if _LANGSMITH_AVAILABLE:
        return _ls_traceable(*decorator_args, **decorator_kwargs)

    # Uso sin paréntesis: @traceable
    if len(decorator_args) == 1 and callable(decorator_args[0]) and not decorator_kwargs:
        return decorator_args[0]

    # Uso con argumentos: @traceable(...)
    def _identity(func):
        return func
    return _identity


def record_llm_usage(prompt_tokens: int = 0, completion_tokens: int = 0,
                     model: str = None, provider: str = None) -> None:
    """
    Adjunta el consumo de tokens al run LLM actual de LangSmith.

    LangSmith usa `usage_metadata` en los outputs de un run `run_type="llm"`
    para calcular coste (€) y agregados de tokens. El cálculo de coste hace match
    por `ls_model_name` y, si la regla de pricing lo exige, por `ls_provider`.
    No-op si langsmith no está activo o no hay run en curso.
    """
    if not _LANGSMITH_AVAILABLE:
        return
    try:
        rt = get_current_run_tree()
        if rt is None:
            return
        usage = {
            "input_tokens": int(prompt_tokens or 0),
            "output_tokens": int(completion_tokens or 0),
            "total_tokens": int(prompt_tokens or 0) + int(completion_tokens or 0),
        }
        rt.add_outputs({"usage_metadata": usage})
        meta = {}
        if model:
            meta["ls_model_name"] = model
        if provider:
            meta["ls_provider"] = provider
        if meta:
            rt.add_metadata(meta)
    except Exception as e:
        logger.debug(f"record_llm_usage no-op ({e})")
