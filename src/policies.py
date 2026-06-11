"""
Políticas reutilizables aprendidas de decisiones HITL del Supervisor.

Cumple la Regla 4 del diseño multi-agéntico del Entregable 3 del TFM:
"Prevalencia de políticas sobre reglas base. Las políticas generadas por
decisiones del Supervisor tienen mayor jerarquía que las reglas por defecto
del Árbitro. Si existe una política aplicable a un conflicto, el Árbitro la
aplica antes de evaluar los criterios cronológicos o de autoridad."

Flujo:
  1. Detector encuentra conflicto entre chunk nuevo y chunk existente.
  2. `find_applicable_policy()` busca en `policies` (activa) una entrada cuyo
     `subject_pattern` aparezca dentro del texto del chunk nuevo.
  3. Si hay match → Arbitrator devuelve esa decisión directamente, sin
     evaluar fecha ni autoridad. Se incrementa `times_applied`.
  4. Si no hay match → flujo clásico (`_decide_resolution`).
  5. Cada decisión HITL del admin se persiste como nueva policy vía
     `save_policy_from_review()` para que conflictos similares futuros se
     resuelvan automáticamente.

El "subject_pattern" para el MVP es un fragmento estable extraído del
chunk_text (primeras ~60 chars limpios, en minúsculas). Usar LIKE
case-insensitive para el match. En Phase 8 se podrá refinar con regex o
embeddings semánticos.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Mapeo entre acciones HITL y decisiones de política ────────────────────

_ACTION_TO_DECISION = {
    "approved_new":      "policy_new_wins",
    "approved_existing": "policy_existing_wins",
    "kept_both":         "policy_kept_both",
}


def _extract_subject_pattern(chunk_text: str, max_chars: int = 60) -> str:
    """
    Extrae un patrón estable del chunk para emparejarlo en queries futuras.
    Toma las primeras `max_chars` después de normalizar (lowercase, sin
    puntuación múltiple, sin saltos). Suficientemente largo para diferenciar
    temas, suficientemente corto para que matchee variaciones.
    """
    text = chunk_text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^[#\*\-\s•·\.\,\;\:]+", "", text)
    pattern = text[:max_chars].strip()
    return pattern


# ─── API pública ───────────────────────────────────────────────────────────

def find_applicable_policy(
    db,
    *,
    tenant_id: str,
    space_id: str,
    new_chunk_text: str,
) -> Optional[dict]:
    """
    Busca una política activa cuyo `subject_pattern` esté contenido en
    `new_chunk_text` (LIKE case-insensitive). Devuelve la primera coincidencia
    o None.

    Se filtran por tenant + space para que las políticas de Delos no afecten
    a García y viceversa.
    """
    try:
        rows = (
            db.client.table("policies")
            .select(
                "id, subject_pattern, decision, reason, "
                "source_review_id, times_applied"
            )
            .eq("tenant_id", tenant_id)
            .eq("space_id",  space_id)
            .eq("active",    True)
            .execute()
        )
    except Exception as e:
        logger.warning(f"Error consultando policies: {e}")
        return None

    haystack = (new_chunk_text or "").lower()
    if not haystack:
        return None
    for p in (rows.data or []):
        needle = (p.get("subject_pattern") or "").lower()
        if needle and needle in haystack:
            return p
    return None


def increment_policy_applied(db, policy_id: int) -> None:
    """Incrementa el contador y registra el último uso. Best-effort."""
    try:
        # Postgres no expone `count = count + 1` desde PostgREST con un solo
        # PATCH idempotente; usamos UPDATE ... RETURNING via rpc o leemos
        # y reescribimos. Para minimizar viajes, leemos primero.
        row = db.client.table("policies").select("times_applied").eq("id", policy_id).execute()
        prev = (row.data or [{}])[0].get("times_applied", 0)
        db.client.table("policies").update({
            "times_applied":   prev + 1,
            "last_applied_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", policy_id).execute()
    except Exception:
        logger.exception("No se pudo incrementar times_applied de policy %s", policy_id)


def save_policy_from_review(
    db,
    *,
    review_id: str,
    action: str,
    new_chunk_text: str,
    reason: str = "",
) -> Optional[int]:
    """
    Persiste una política reutilizable a partir de una decisión HITL.

    Si la acción ya existe como policy con el mismo subject_pattern + tenant +
    space + decision, no se duplica (idempotente).

    Args:
        review_id:       UUID de conflict_reviews (origen).
        action:          'approved_new' | 'approved_existing' | 'kept_both'.
        new_chunk_text:  texto del chunk nuevo (para derivar subject_pattern).
        reason:          motivo legible.

    Returns:
        ID de la policy creada o existente; None si no se pudo persistir.
    """
    decision = _ACTION_TO_DECISION.get(action)
    if not decision:
        return None

    try:
        review = db.client.table("conflict_reviews").select(
            "tenant_id, space_id"
        ).eq("id", review_id).execute()
        if not review.data:
            logger.warning(f"No se encontró conflict_review {review_id} para crear policy")
            return None
        tenant_id = review.data[0]["tenant_id"]
        space_id  = review.data[0]["space_id"]
    except Exception:
        logger.exception("Error leyendo conflict_review para crear policy")
        return None

    pattern = _extract_subject_pattern(new_chunk_text)
    if not pattern:
        logger.warning("subject_pattern vacío; no se crea policy")
        return None

    # Idempotencia: si ya hay policy activa con misma terna, no duplicar.
    try:
        existing = (
            db.client.table("policies")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("space_id",  space_id)
            .eq("subject_pattern", pattern)
            .eq("decision",  decision)
            .eq("active",    True)
            .execute()
        )
        if existing.data:
            return existing.data[0]["id"]
    except Exception:
        logger.exception("Error comprobando idempotencia de policy")

    try:
        ins = db.client.table("policies").insert({
            "tenant_id":        tenant_id,
            "space_id":         space_id,
            "subject_pattern":  pattern,
            "decision":         decision,
            "source_review_id": review_id,
            "reason":           reason or f"Aprendida del HITL {review_id[:8]}…",
            "times_applied":    0,
            "active":           True,
        }).execute()
        if ins.data:
            policy_id = ins.data[0].get("id")
            logger.info(
                f"📚 Policy creada (id={policy_id}, decision={decision}, "
                f"pattern='{pattern[:30]}…')"
            )
            return policy_id
    except Exception:
        logger.exception("Error insertando policy")
    return None
