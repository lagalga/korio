"""
Módulo de escalada de revisiones HITL — Phase 6 de gobernanza activa.

Diseño según Notion (sección "Gestión de conflictos · Ciclo de escalada"):

    "Los conflictos sin resolver reciben recordatorios periódicos por cron
     (configurable: cada 3 días, cada semana). Si transcurre el tiempo
     máximo configurado sin resolución, ambos chunks permanecen activos
     con estado en_disputa."

Cadencia por defecto (parametrizable vía env):

  Día 0   →  Email inicial (ya se envió en la ingesta)
  Día 3   →  Recordatorio #1
  Día 7   →  Recordatorio #2
  Día 14  →  Recordatorio #3 (urgente)
  Día 21  →  Auto-cierre como 'timeout_kept_both' + email de cierre

Para evitar dobles envíos, cada review tiene:
  - reminders_sent: contador de recordatorios enviados (0..3)
  - last_reminder_at: fecha del último envío
  - timeout_at: fecha del auto-cierre (NULL si activa)
"""

import os
import logging
import requests
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ─── Configuración por defecto (sobreescribible via env) ─────────────────────

REMINDER_DAYS = sorted([
    int(d.strip())
    for d in os.getenv("ESCALATION_REMINDER_DAYS", "3,7,14").split(",")
    if d.strip()
])

TIMEOUT_DAYS = int(os.getenv("ESCALATION_TIMEOUT_DAYS", "21"))

HITL_WEBHOOK_URL  = os.getenv("HITL_WEBHOOK_URL", "")
HITL_WEBHOOK_USER = os.getenv("HITL_WEBHOOK_USER", "")
HITL_WEBHOOK_PASS = os.getenv("HITL_WEBHOOK_PASS", "")
KORIO_BASE_URL    = os.getenv("KORIO_BASE_URL", "https://korio.es")


def _hitl_auth():
    """Basic Auth tuple para el webhook HITL si está configurado, None si no."""
    if HITL_WEBHOOK_USER and HITL_WEBHOOK_PASS:
        return (HITL_WEBHOOK_USER, HITL_WEBHOOK_PASS)
    return None


# ─── Resultado ──────────────────────────────────────────────────────────────

@dataclass
class EscalationResult:
    """
    Resumen del paso de escalada para devolver al cron caller.

    Attributes:
        checked:      Reviews pending evaluadas
        reminded:     Reviews que recibieron un nuevo recordatorio
        timed_out:    Reviews cerradas automáticamente por timeout
        skipped:      Reviews que no tocaba notificar todavía
        errors:       Errores no bloqueantes (no impiden continuar)
    """
    checked:   int = 0
    reminded:  int = 0
    timed_out: int = 0
    skipped:   int = 0
    errors:    List[str] = field(default_factory=list)
    details:   List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checked":   self.checked,
            "reminded":  self.reminded,
            "timed_out": self.timed_out,
            "skipped":   self.skipped,
            "errors":    self.errors,
            "details":   self.details,
            "config": {
                "reminder_days": REMINDER_DAYS,
                "timeout_days":  TIMEOUT_DAYS,
            },
        }


# ─── Helpers ────────────────────────────────────────────────────────────────

def _parse_ts(value) -> Optional[datetime]:
    """Parsea un ISO-8601 o devuelve el datetime si ya lo es."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _next_reminder_threshold(reminders_sent: int) -> Optional[int]:
    """
    Devuelve el siguiente hito (en días) que toca, o None si ya se enviaron todos.
    Ejemplo con [3,7,14]:
      reminders_sent=0 → 3
      reminders_sent=1 → 7
      reminders_sent=2 → 14
      reminders_sent=3 → None (ya no quedan)
    """
    if reminders_sent >= len(REMINDER_DAYS):
        return None
    return REMINDER_DAYS[reminders_sent]


# ─── Función principal ──────────────────────────────────────────────────────

def run_escalation(db) -> EscalationResult:
    """
    Ejecuta un ciclo de escalada sobre todas las revisiones pending.

    Args:
        db: instancia de SupabaseClient

    Returns:
        EscalationResult con estadísticas del ciclo
    """
    result = EscalationResult()
    now = datetime.now(timezone.utc)

    # Cargar todas las reviews pending con su contexto
    try:
        rows = db.client.table("conflict_reviews").select(
            "id, tenant_id, space_id, review_token, new_document_id, "
            "new_chunk_id, existing_chunk_id, existing_filename, "
            "similarity, resolution_reason, new_doc_authority, "
            "existing_doc_authority, reminders_sent, last_reminder_at, "
            "created_at"
        ).eq("resolution", "pending").execute()
    except Exception as e:
        result.errors.append(f"Error listando reviews pending: {e}")
        return result

    pending = rows.data or []
    result.checked = len(pending)
    logger.info(f"Escalada: {result.checked} reviews pending para evaluar")

    # Agrupar por tenant para mandar 1 webhook call por tenant (más eficiente)
    by_tenant: Dict[str, list] = {}

    for r in pending:
        created_at = _parse_ts(r.get("created_at"))
        if not created_at:
            result.errors.append(f"Review {r['id']}: created_at inválido")
            continue

        days_pending = (now - created_at).days

        # ¿Toca timeout?
        if days_pending >= TIMEOUT_DAYS:
            try:
                _apply_timeout(db, r, now)
                result.timed_out += 1
                result.details.append({
                    "review_id":    r["id"],
                    "action":       "timed_out",
                    "days_pending": days_pending,
                })
                # Notificar al admin de que se cerró por timeout
                by_tenant.setdefault(r["tenant_id"], []).append({
                    "review":       r,
                    "days_pending": days_pending,
                    "kind":         "timeout",
                    "reminders_sent_new": (r.get("reminders_sent") or 0),
                })
            except Exception as e:
                result.errors.append(f"Review {r['id']}: error aplicando timeout: {e}")
            continue

        # ¿Toca recordatorio?
        threshold = _next_reminder_threshold(r.get("reminders_sent") or 0)
        if threshold is None:
            # Ya se enviaron todos los recordatorios y aún no llegó timeout
            result.skipped += 1
            continue

        if days_pending < threshold:
            result.skipped += 1
            continue

        # Pasó el hito: programar envío
        new_count = (r.get("reminders_sent") or 0) + 1
        by_tenant.setdefault(r["tenant_id"], []).append({
            "review":       r,
            "days_pending": days_pending,
            "kind":         "reminder",
            "reminders_sent_new": new_count,
        })

    # Disparar webhook por tenant (agrupando reminders + timeouts del mismo tenant)
    for tenant_id, items in by_tenant.items():
        try:
            _dispatch_tenant_batch(db, tenant_id, items, now, result)
        except Exception as e:
            result.errors.append(f"Tenant {tenant_id}: error disparando webhook: {e}")
            logger.exception(f"Error en dispatch tenant {tenant_id}")

    logger.info(
        f"Escalada terminada: checked={result.checked} reminded={result.reminded} "
        f"timed_out={result.timed_out} skipped={result.skipped} errors={len(result.errors)}"
    )
    return result


# ─── Acciones internas ──────────────────────────────────────────────────────

def _apply_timeout(db, review: dict, now: datetime) -> None:
    """
    Aplica el auto-cierre por timeout: ambos chunks pasan a estado
    `inconclusive` (excluidos del RAG hasta intervención manual). Cumple la
    Regla 5 del Entregable 3 — "Reactivación manual obligatoria": el sistema
    NO toma decisiones por inacción del Supervisor.

    Resolution queda como `timeout_inconclusive`. Comparado con la versión
    previa (`timeout_kept_both` que dejaba ambos en `active` y el RAG seguía
    presentando ambas versiones), este comportamiento es más conservador:
    si el humano no responde en 21 días, el contenido controvertido sale
    del corpus consultable hasta que un admin lo reactive.

    Comportamiento opcional via env (KORIO_TIMEOUT_KEEP_BOTH=1) para
    mantener la lógica antigua si algún tenant lo necesita.
    """
    keep_both_legacy = os.getenv("KORIO_TIMEOUT_KEEP_BOTH", "0") == "1"
    resolution = "timeout_kept_both" if keep_both_legacy else "timeout_inconclusive"
    new_status = "active"            if keep_both_legacy else "inconclusive"

    db.client.table("conflict_reviews").update({
        "resolution": resolution,
        "timeout_at": now.isoformat(),
        "reviewed_at": now.isoformat(),
    }).eq("id", review["id"]).execute()

    existing_chunk_id = review.get("existing_chunk_id")
    new_chunk_id      = review.get("new_chunk_id")
    tenant_id         = review.get("tenant_id")
    if existing_chunk_id:
        db.update_chunk_status(int(existing_chunk_id), new_status)
    if new_chunk_id:
        db.update_chunk_status(int(new_chunk_id), new_status)

    # Sincronizar el grafo (opt-in via env)
    if os.getenv("KORIO_GRAPH_ENABLED", "0") == "1":
        try:
            from graph_client import get_graph_client
            gc = get_graph_client()
            if existing_chunk_id:
                gc.update_chunk_status(int(existing_chunk_id), tenant_id, new_status)
            if new_chunk_id:
                gc.update_chunk_status(int(new_chunk_id), tenant_id, new_status)
        except Exception as e:
            logger.warning(f"Grafo: error sincronizando timeout {review['id']}: {e}")

    # Emitir evento al bus de eventos (Supervisor → Curator)
    try:
        from agents.events import emit, EventType, Agent, new_operation_id
        emit(
            EventType.USER_DECISION,
            source_agent=Agent.SUPERVISOR,
            tenant_id=tenant_id,
            operation_id=new_operation_id(),
            document_id=str(review.get("new_document_id") or "") or None,
            payload={
                "review_id":   str(review["id"]),
                "resolution":  resolution,
                "applied_by":  "timeout",
                "timeout_days": TIMEOUT_DAYS,
            },
        )
    except Exception:
        pass

    logger.info(
        f"Review {review['id']} cerrada por timeout ({TIMEOUT_DAYS} días) → "
        f"resolution={resolution}, chunks→{new_status}"
    )


def _dispatch_tenant_batch(
    db,
    tenant_id: str,
    items: List[Dict[str, Any]],
    now: datetime,
    result: EscalationResult,
) -> None:
    """
    Envía al webhook HITL un payload agrupado por tenant con todos los items
    (reminders + timeouts). El email muestra badge "Recordatorio Nº X" o
    "Cerrado por timeout" según corresponda.
    """
    if not HITL_WEBHOOK_URL:
        result.errors.append("HITL_WEBHOOK_URL no configurado — no se envía email")
        return

    # Tenant info
    tenant_admin_email = None
    tenant_name = ""
    try:
        t = db.client.table("tenants").select("name, admin_email").eq(
            "id", tenant_id
        ).single().execute()
        if t.data:
            tenant_name        = t.data.get("name", "")
            tenant_admin_email = t.data.get("admin_email")
    except Exception as e:
        logger.warning(f"No se pudo obtener tenant {tenant_id}: {e}")

    conflicts_payload = []
    for item in items:
        r            = item["review"]
        days_pending = item["days_pending"]
        kind         = item["kind"]
        token        = r.get("review_token")
        review_id    = r["id"]
        existing_chunk_id = r.get("existing_chunk_id")
        new_chunk_id      = r.get("new_chunk_id")

        # Cargar los textos de los chunks (puede haber cambiado el estado pero el texto no)
        new_chunk_text = ""
        existing_chunk_text = ""
        new_filename = ""
        try:
            if r.get("new_document_id"):
                fr = db.client.table("documents").select("filename").eq(
                    "id", r["new_document_id"]
                ).single().execute()
                if fr.data:
                    new_filename = fr.data.get("filename", "")
            if new_chunk_id:
                ct = db.client.table("embeddings").select("chunk_text").eq(
                    "id", int(new_chunk_id)
                ).single().execute()
                if ct.data:
                    new_chunk_text = ct.data["chunk_text"]
            if existing_chunk_id:
                ct = db.client.table("embeddings").select("chunk_text").eq(
                    "id", int(existing_chunk_id)
                ).single().execute()
                if ct.data:
                    existing_chunk_text = ct.data["chunk_text"]
        except Exception as e:
            logger.warning(f"No se pudieron cargar chunks de review {review_id}: {e}")

        conflicts_payload.append({
            "review_id":            review_id,
            "new_filename":         new_filename,
            "existing_filename":    r.get("existing_filename", ""),
            "similarity_pct":       int((r.get("similarity") or 0) * 100),
            "resolution_reason":    r.get("resolution_reason", ""),
            "new_authority":        r.get("new_doc_authority", 5),
            "existing_authority":   r.get("existing_doc_authority", 5),
            "new_chunk_text":       new_chunk_text,
            "existing_chunk_text":  existing_chunk_text,
            "is_reminder":          (kind == "reminder"),
            "is_timeout":           (kind == "timeout"),
            "days_pending":         days_pending,
            "reminder_number":      item["reminders_sent_new"] if kind == "reminder" else None,
            # Links de acción (no aplicables para timeout, pero los incluimos por consistencia)
            "action_approve_new":    f"{KORIO_BASE_URL}/review/{review_id}?action=approved_new&token={token}",
            "action_keep_existing":  f"{KORIO_BASE_URL}/review/{review_id}?action=approved_existing&token={token}",
            "action_keep_both":      f"{KORIO_BASE_URL}/review/{review_id}?action=kept_both&token={token}",
        })

    if not conflicts_payload:
        return

    payload = {
        "tenant_id":          tenant_id,
        "tenant_name":        tenant_name,
        "tenant_admin_email": tenant_admin_email,
        "korio_base_url":     KORIO_BASE_URL,
        "conflict_count":     len(conflicts_payload),
        # Flag para que el workflow n8n sepa que es escalada (no ingesta inicial)
        "is_escalation":      True,
        "conflicts":          conflicts_payload,
    }

    try:
        resp = requests.post(HITL_WEBHOOK_URL, json=payload, timeout=30, auth=_hitl_auth())
        resp.raise_for_status()
        logger.info(
            f"Tenant {tenant_name}: {len(conflicts_payload)} items disparados "
            f"(status {resp.status_code})"
        )

        # Marcar los reminders como enviados (los timeouts ya están marcados en BD)
        for item in items:
            if item["kind"] == "reminder":
                try:
                    db.client.table("conflict_reviews").update({
                        "reminders_sent":   item["reminders_sent_new"],
                        "last_reminder_at": now.isoformat(),
                    }).eq("id", item["review"]["id"]).execute()
                    result.reminded += 1
                    result.details.append({
                        "review_id":      item["review"]["id"],
                        "action":         "reminded",
                        "reminder_number": item["reminders_sent_new"],
                        "days_pending":   item["days_pending"],
                    })
                except Exception as e:
                    result.errors.append(
                        f"Review {item['review']['id']}: error actualizando reminders_sent: {e}"
                    )
    except Exception as e:
        result.errors.append(f"Tenant {tenant_name}: error en webhook HITL: {e}")
        raise
