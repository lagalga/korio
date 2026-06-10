"""
LLM Client — Wrapper para generación de texto.

Soporta dos backends (en orden de prioridad):
1. Mistral API (La Plateforme) — si MISTRAL_API_KEY está configurado
2. Ollama local — fallback si no hay API key

El modelo de generación es independiente del de embeddings.
Los embeddings SIEMPRE usan nomic-embed-text via Ollama.
"""

import os
import json
import time
import logging
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuración
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modelos por defecto
MISTRAL_MODEL = "mistral-small-latest"      # Rápido y barato, suficiente para RAG
OLLAMA_MODEL = "mistral:7b-instruct-q4_K_M" # Modelo local (descargado en VPS)

# Parámetros de generación
DEFAULT_TEMPERATURE = 0.2   # Baja para RAG (menos alucinaciones)
DEFAULT_MAX_TOKENS = 1024   # Respuestas concisas


class LLMClient:
    """
    Cliente LLM con soporte para Mistral API y Ollama.

    Detecta automáticamente qué backend usar según
    la disponibilidad de MISTRAL_API_KEY.
    """

    def __init__(self):
        """Inicializa el cliente y detecta el backend disponible."""
        if MISTRAL_API_KEY and MISTRAL_API_KEY not in ("optional", "your_mistral_api_key_here", ""):
            self.backend = "mistral_api"
            self.model = MISTRAL_MODEL
            logger.info(f"✓ LLM backend: Mistral API ({MISTRAL_MODEL})")
        else:
            self.backend = "ollama"
            self.model = OLLAMA_MODEL
            logger.info(f"✓ LLM backend: Ollama local ({OLLAMA_MODEL})")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> str:
        """
        Genera texto a partir de un prompt.

        Args:
            prompt: Mensaje del usuario
            system_prompt: Instrucciones del sistema (comportamiento del LLM)
            temperature: Creatividad (0.0–1.0). Usar 0.1–0.3 para RAG
            max_tokens: Máximo de tokens en la respuesta

        Returns:
            str: Texto generado

        Raises:
            RuntimeError: Si falla la generación
        """
        if self.backend == "mistral_api":
            return self._generate_mistral(prompt, system_prompt, temperature, max_tokens)
        else:
            return self._generate_ollama(prompt, system_prompt, temperature, max_tokens)

    def _generate_mistral(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Genera texto usando Mistral API (La Plateforme)."""
        url = "https://api.mistral.ai/v1/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        headers = {
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Error en Mistral API: {e.response.text}") from e
        except Exception as e:
            raise RuntimeError(f"Error generando con Mistral API: {e}") from e

    def _generate_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Genera texto usando Ollama local."""
        url = f"{OLLAMA_BASE_URL}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=120)  # CPU puede ser lento
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"].strip()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Ollama no disponible en {OLLAMA_BASE_URL}. "
                "¿Está corriendo? Ejecuta: docker compose up ollama"
            )
        except Exception as e:
            raise RuntimeError(f"Error generando con Ollama: {e}") from e

    def reformulate_query(
        self,
        query: str,
        history: list,
        language: str = "es"
    ) -> str:
        """
        Reformula una pregunta conversacional en una pregunta autónoma usando el historial.

        Se usa antes del embedding RAG cuando el usuario hace preguntas que dependen
        del contexto previo del chat. Ejemplo: tras preguntar "¿Cuántas vacaciones tengo
        con 10 años?", la segunda pregunta "¿Y si llevo 15?" sería reformulada como
        "¿Cuántas vacaciones tengo con 15 años de antigüedad?".

        Args:
            query: Pregunta actual del usuario (potencialmente dependiente del contexto)
            history: Lista de turnos previos, formato [{"role": "user"|"assistant", "content": str}]
            language: Idioma de la reformulación ("es" o "en")

        Returns:
            str: Pregunta autónoma. Si el LLM falla o el historial es vacío, devuelve la query original.
        """
        if not history:
            return query

        # Formatear historial — solo los últimos 6 turnos para mantener prompt corto
        history_lines = []
        for turn in history[-6:]:
            role = turn.get("role", "user")
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            label = "Usuario" if role == "user" else "Asistente"
            history_lines.append(f"{label}: {content}")
        history_text = "\n".join(history_lines)

        system_prompt = (
            "Eres un asistente que reformula preguntas conversacionales en preguntas autónomas. "
            "Si la nueva pregunta depende del contexto anterior (usa pronombres, elipsis, "
            "o referencias a turnos previos), reescríbela incluyendo todo el contexto necesario. "
            "Si la nueva pregunta ya es autónoma, devuélvela sin cambios. "
            "Responde SOLO con la pregunta reformulada, sin explicaciones, sin comillas, sin prefijos."
        )
        user_prompt = (
            f"Historial de la conversación:\n{history_text}\n\n"
            f"Nueva pregunta: {query}\n\n"
            f"Pregunta autónoma:"
        )

        try:
            reformulated = self.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=200
            )
            # Sanity check: si por algún motivo devuelve algo vacío o demasiado raro, usar la original
            reformulated = reformulated.strip().strip('"').strip("'")
            if not reformulated or len(reformulated) > 1000:
                logger.warning(f"Reformulación inválida (vacía o demasiado larga), uso query original")
                return query
            return reformulated
        except Exception as e:
            # No bloquear la búsqueda si falla la reformulación
            logger.warning(f"Error reformulando query: {e} — uso query original")
            return query

    def build_rag_prompt(
        self,
        query: str,
        context_chunks: list,
        language: str = "es"
    ) -> tuple[str, str]:
        """
        Construye el prompt RAG con contexto y la query del usuario.

        Args:
            query: Pregunta del usuario
            context_chunks: Lista de chunks recuperados (dicts con chunk_text, document_id, similarity)
            language: Idioma de la respuesta ("es" o "en")

        Returns:
            tuple[str, str]: (system_prompt, user_prompt)
        """
        # System prompt RAG — crítico para evitar alucinaciones
        system_prompt = (
            "Eres un asistente corporativo especializado. "
            "RESPONDE ÚNICAMENTE con información que aparezca en el CONTEXTO proporcionado. "
            "Si la respuesta no está en el contexto, di exactamente: "
            "'No encuentro información sobre esto en los documentos disponibles.' "
            "NUNCA inventes datos, fechas, nombres o cifras. "
            "Cita la fuente al final de cada afirmación relevante usando el nombre del documento "
            "entre corchetes tal como aparece en el contexto (por ejemplo: [politica_vacaciones.pdf]). "
            f"Responde en {'español' if language == 'es' else 'inglés'}."
        )

        # Formatear contexto — preferir filename real para que las citas sean legibles
        if not context_chunks:
            context_text = "No hay documentos disponibles para responder esta pregunta."
        else:
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                doc_id     = chunk.get("document_id", "desconocido")
                filename   = chunk.get("filename") or f"Documento {i}"
                similarity = chunk.get("similarity", 0)
                text       = chunk.get("chunk_text", "")
                status     = chunk.get("chunk_status", "active")
                # Marcar visualmente los chunks en disputa para que el LLM sepa tratarlos así
                status_tag = " · ⚠️ EN DISPUTA" if status == "disputed" else ""
                context_parts.append(
                    f"[{filename}{status_tag} · relevancia {similarity:.2f}]\n{text}"
                )
            context_text = "\n\n---\n\n".join(context_parts)

        # User prompt con contexto
        user_prompt = (
            f"CONTEXTO:\n{context_text}\n\n"
            f"PREGUNTA: {query}\n\n"
            "RESPUESTA (cita las fuentes entre corchetes):"
        )

        return system_prompt, user_prompt

    def get_backend_info(self) -> dict:
        """Devuelve información del backend activo."""
        return {
            "backend": self.backend,
            "model": self.model,
            "api_configured": bool(MISTRAL_API_KEY and MISTRAL_API_KEY not in ("optional", ""))
        }


# Singleton
_llm_client = None


def get_llm_client() -> LLMClient:
    """
    Obtiene o crea la instancia global del LLM client.

    Returns:
        LLMClient: Instancia del cliente
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


if __name__ == "__main__":
    # Test simple
    logging.basicConfig(level=logging.INFO)

    llm = get_llm_client()
    print(f"Backend: {llm.get_backend_info()}")

    # Test básico de generación
    response = llm.generate(
        prompt="¿Cuál es la capital de España? Responde en una frase.",
        temperature=0.1
    )
    print(f"Respuesta: {response}")
