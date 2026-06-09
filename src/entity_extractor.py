"""
Extractor de entidades y claims para el grafo de conocimiento — Phase 7.1.

Por cada chunk de un documento, este módulo:

1. Llama al LLM (Mistral API) con un prompt structured JSON output
2. Extrae:
   - **Entidades**: personas, organizaciones, lugares, fechas, conceptos
   - **Claims**: afirmaciones tipo sujeto-predicado-valor (ej. "política PCA -
                 jornada_minima - 35 horas/semana")
3. Devuelve un dict listo para insertar en FalkorDB

Diseñado para ser robusto frente a respuestas LLM malformadas (try/except
abundante; si falla, devuelve listas vacías para no romper la ingesta).
"""

import os
import json
import logging
import hashlib
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Importación condicional: usamos el LLM client de Korio para reutilizar Mistral API
try:
    from llm_client import get_llm_client
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


# ─── Resultado ───────────────────────────────────────────────────────────────

@dataclass
class ExtractedEntity:
    """Una entidad mencionada en el chunk."""
    name: str    # normalizada (lowercase, trim)
    kind: str    # Persona | Organización | Lugar | Fecha | Cantidad | Concepto


@dataclass
class ExtractedClaim:
    """Una afirmación atomica subject-predicate-value."""
    subject:   str
    predicate: str
    value:     str
    claim_id:  str = ""  # hash determinista, se calcula al construirlo

    def __post_init__(self):
        if not self.claim_id:
            payload = f"{self.subject}|{self.predicate}|{self.value}".lower()
            self.claim_id = "cl_" + hashlib.sha1(payload.encode()).hexdigest()[:16]


@dataclass
class ExtractionResult:
    entities: List[ExtractedEntity] = field(default_factory=list)
    claims:   List[ExtractedClaim]  = field(default_factory=list)
    errors:   List[str]             = field(default_factory=list)


# ─── Prompt ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres un extractor de conocimiento estructurado para una base de
conocimiento corporativa. Tu trabajo es extraer entidades y afirmaciones
atómicas de un fragmento de texto.

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:

{
  "entities": [
    {"name": "<nombre canónico>", "kind": "Persona|Organización|Lugar|Fecha|Cantidad|Concepto"}
  ],
  "claims": [
    {"subject": "<entidad o concepto>", "predicate": "<propiedad>", "value": "<valor literal>"}
  ]
}

REGLAS ESTRICTAS:
1. SOLO extrae afirmaciones que aparezcan EXPLÍCITAMENTE en el texto. No inventes.
2. Cada claim debe ser ATÓMICO: una sola afirmación, un solo dato. Divide
   afirmaciones complejas en varias claims.
3. El "subject" del claim debe coincidir con el "name" de una entidad declarada
   en "entities" siempre que sea posible.
4. Los nombres de entidades en MINÚSCULAS y sin artículos: "política pca"
   (no "La Política PCA"); "empleados asalariados" (no "Los empleados").
5. Los "predicate" deben ser propiedades cortas en MINÚSCULAS y singular:
   "jornada_minima", "vacaciones_anuales", "responsable", "fecha_aprobacion",
   "tipo_documento", etc. Usa snake_case.
6. Los "value" son LITERALES del texto, incluyendo unidades cuando aplique:
   "35 horas/semana", "5 semanas", "12 mayo 2026", "Dirección de RRHH".
7. Si el texto no contiene afirmaciones claras (chunk de introducción, header,
   página numerada, footer), devuelve ambos arrays vacíos.
8. Máximo 8 entidades y 12 claims por chunk para no saturar el grafo.
9. NUNCA incluyas claims sobre el LLM, sobre la extracción, ni meta-comentarios.
10. Si una afirmación expresa un umbral ("más de X", "menos de Y", "al menos Z"),
    refleja eso en el predicate: "umbral_minimo", "umbral_maximo", etc.

Respuesta SOLO con el JSON, sin texto adicional, sin markdown."""


USER_PROMPT_TEMPLATE = """Extrae entidades y claims del siguiente fragmento del
documento "{filename}":

---
{chunk_text}
---

JSON:"""


# ─── Funciones ──────────────────────────────────────────────────────────────

def _safe_parse_json(raw: str) -> Optional[dict]:
    """Intenta parsear JSON con fallback a regex si el LLM añadió texto."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Buscar el primer { ... } más externo
    m = re.search(r"\{[\s\S]+\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def extract_from_chunk(
    chunk_text: str,
    filename: str = "documento",
    llm_client=None,
) -> ExtractionResult:
    """
    Extrae entidades y claims de un único chunk.

    Args:
        chunk_text: Texto del chunk
        filename:   Nombre del fichero (solo para contexto en el prompt)
        llm_client: Cliente LLM (opcional, si no se pasa usa get_llm_client())

    Returns:
        ExtractionResult con entities, claims y errors
    """
    result = ExtractionResult()

    if not chunk_text or not chunk_text.strip():
        return result

    if not LLM_AVAILABLE:
        result.errors.append("LLM client no disponible")
        return result

    llm = llm_client or get_llm_client()

    user_prompt = USER_PROMPT_TEMPLATE.format(
        filename=filename[:60],
        chunk_text=chunk_text[:3500],  # truncar para no agotar contexto
    )

    try:
        raw = llm.generate(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.0,  # extracción estructurada, no creatividad
        )
    except Exception as e:
        result.errors.append(f"LLM error: {e}")
        logger.warning(f"Error en LLM extract: {e}")
        return result

    parsed = _safe_parse_json(raw)
    if not parsed:
        result.errors.append("JSON inválido del LLM")
        logger.warning(f"JSON inválido del LLM: {raw[:200]}")
        return result

    # Entities
    for ent in (parsed.get("entities") or [])[:8]:
        name = (ent.get("name") or "").strip()
        kind = (ent.get("kind") or "Concepto").strip()
        if not name:
            continue
        result.entities.append(ExtractedEntity(name=name.lower(), kind=kind))

    # Claims
    for cl in (parsed.get("claims") or [])[:12]:
        subj = (cl.get("subject") or "").strip()
        pred = (cl.get("predicate") or "").strip()
        val  = (cl.get("value") or "").strip()
        if not subj or not pred or not val:
            continue
        result.claims.append(ExtractedClaim(
            subject=subj.lower(),
            predicate=pred.lower(),
            value=val,
        ))

    return result


if __name__ == "__main__":
    # Test rápido con un texto de ejemplo
    logging.basicConfig(level=logging.INFO)
    sample = """Política de vacaciones — Packaging Corporation of America
    Versión 3.0, revisión interna mayo 2026.
    Esta política rige para todos los empleados asalariados de tiempo completo
    que trabajan regularmente más de 35 horas a la semana. La tabla de
    vacaciones aplicable es: Menos de 5 años → 4 semanas, 5 a 14 años → 5
    semanas, 15 a 19 años → 6 semanas, 20 años o más → 7 semanas.
    El cómputo proporcional en primer año parcial se calcula a razón de 1.5
    días al mes."""

    r = extract_from_chunk(sample, "pca_politica_vacaciones.md")
    print(f"\n=== {len(r.entities)} entidades ===")
    for e in r.entities:
        print(f"  · {e.name} [{e.kind}]")
    print(f"\n=== {len(r.claims)} claims ===")
    for c in r.claims:
        print(f"  · {c.subject} -- {c.predicate} --> {c.value}  ({c.claim_id})")
    if r.errors:
        print(f"\n!! Errores: {r.errors}")
