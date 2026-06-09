"""
Módulo de detección y resolución de conflictos — Gobernanza activa.

Detecta cuando un chunk nuevo tiene contenido semánticamente similar (y potencialmente
contradictorio) a chunks existentes en el mismo espacio. Aplica resolución automática
cuando las diferencias de fecha o autoridad son claras; en caso contrario, crea una
tarea de revisión humana (HITL via email).

Umbrales de decisión:
  CONFLICT_THRESHOLD      = 0.85  — similitud coseno mínima para declarar conflicto
  AUTO_DATE_DAYS          = 30    — diferencia en días para resolver por fecha
  AUTO_AUTHORITY_DELTA    = 3     — diferencia en authority_weight para resolver por autoridad
"""

import os
import secrets
import logging
import requests
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ─── Umbrales ────────────────────────────────────────────────────────────────

CONFLICT_THRESHOLD     = 0.85  # Similitud mínima para considerar conflicto
AUTO_DATE_DAYS         = 30    # Días de diferencia para auto-resolución por fecha
AUTO_AUTHORITY_DELTA   = 3     # Puntos de diferencia para auto-resolución por autoridad

# URL del webhook n8n para disparar emails HITL (opcional)
HITL_WEBHOOK_URL = os.getenv("HITL_WEBHOOK_URL", "")
KORIO_BASE_URL   = os.getenv("KORIO_BASE_URL", "https://korio.es")


# ─── Dataclasses de resultado ────────────────────────────────────────────────

@dataclass
class ConflictItem:
    """
    Un conflicto individual entre un chunk nuevo y un chunk existente.

    Attributes:
        new_chunk_id:          ID del chunk recién ingestado
        existing_chunk_id:     ID del chunk existente con el que hay conflicto
        existing_document_id:  UUID del documento existente
        existing_filename:     Nombre del fichero existente
        similarity:            Similitud coseno (0.85–1.0)
        new_authority:         authority_weight del documento nuevo
        existing_authority:    authority_weight del documento existente
        new_version_ts:        Fecha del documento nuevo
        existing_version_ts:   Fecha del documento existente
        resolution:            Decisión: auto_new_wins|auto_existing_wins|pending
        resolution_reason:     Explicación legible de la decisión
        review_id:             UUID en conflict_reviews (si se creó)
        review_token:          Token para links email HITL (si está pendiente)
    """
    new_chunk_id:           int
    existing_chunk_id:      int
    existing_document_id:   str
    existing_filename:      str
    similarity:             float
    new_authority:          int
    existing_authority:     int
    new_version_ts:         datetime
    existing_version_ts:    datetime
    resolution:             str
    resolution_reason:      str
    review_id:              Optional[str] = None
    review_token:           Optional[str] = None


@dataclass
class ConflictReport:
    """
    Resumen de todos los conflictos detectados en una operación de ingesta.

    Attributes:
        total_conflicts:  Número total de conflictos detectados
        auto_resolved:    Conflictos resueltos automáticamente
        pending_review:   Conflictos que requieren revisión humana (HITL)
        conflicts:        Lista de conflictos individuales
    """
    total_conflicts:  int = 0
    auto_resolved:    int = 0
    pending_review:   int = 0
    conflicts:        List[ConflictItem] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Devuelve True si se detectó al menos un conflicto."""
        return self.total_conflicts > 0

    @property
    def has_pending(self) -> bool:
        """Devuelve True si hay conflictos pendientes de revisión humana."""
        return self.pending_review > 0

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el report a dict (para la respuesta de la API)."""
        return {
            "total_conflicts": self.total_conflicts,
            "auto_resolved":   self.auto_resolved,
            "pending_review":  self.pending_review,
            "has_conflicts":   self.has_conflicts,
            "has_pending":     self.has_pending,
            "conflicts": [
                {
                    "new_chunk_id":          c.new_chunk_id,
                    "existing_chunk_id":     c.existing_chunk_id,
                    "existing_document_id":  c.existing_document_id,
                    "existing_filename":     c.existing_filename,
                    "similarity":            round(c.similarity, 3),
                    "new_authority":         c.new_authority,
                    "existing_authority":    c.existing_authority,
                    "resolution":            c.resolution,
                    "resolution_reason":     c.resolution_reason,
                    "review_id":             c.review_id,
                }
                for c in self.conflicts
            ],
        }


# ─── Lógica de resolución ────────────────────────────────────────────────────

def _decide_resolution(
    new_authority: int,
    existing_authority: int,
    new_version_ts: datetime,
    existing_version_ts: datetime,
) -> tuple[str, str]:
    """
    Determina la resolución automática de un conflicto.

    Orden de decisión:
    1. Diferencia de fecha > AUTO_DATE_DAYS → el más reciente gana
    2. Diferencia de autoridad >= AUTO_AUTHORITY_DELTA → mayor autoridad gana
    3. En otro caso → pending (HITL)

    Returns:
        Tupla (resolution, reason) donde resolution es uno de:
        'auto_new_wins' | 'auto_existing_wins' | 'pending'
    """
    # Normalizar timezones para comparación
    if new_version_ts.tzinfo is None:
        new_version_ts = new_version_ts.replace(tzinfo=timezone.utc)
    if existing_version_ts.tzinfo is None:
        existing_version_ts = existing_version_ts.replace(tzinfo=timezone.utc)

    date_diff_days = abs((new_version_ts - existing_version_ts).days)

    if date_diff_days > AUTO_DATE_DAYS:
        if new_version_ts > existing_version_ts:
            return (
                "auto_new_wins",
                f"Documento nuevo es {date_diff_days} días más reciente (auto-resolución por fecha)"
            )
        else:
            return (
                "auto_existing_wins",
                f"Documento existente es {date_diff_days} días más reciente (auto-resolución por fecha)"
            )

    authority_diff = new_authority - existing_authority
    if abs(authority_diff) >= AUTO_AUTHORITY_DELTA:
        if authority_diff > 0:
            return (
                "auto_new_wins",
                f"Documento nuevo tiene mayor autoridad ({new_authority} vs {existing_authority}, delta={authority_diff})"
            )
        else:
            return (
                "auto_existing_wins",
                f"Documento existente tiene mayor autoridad ({existing_authority} vs {new_authority}, delta={abs(authority_diff)})"
            )

    return (
        "pending",
        f"Sin criterio claro de resolución automática "
        f"(autoridad: {new_authority} vs {existing_authority}, "
        f"fecha: {date_diff_days} días de diferencia) — requiere revisión humana"
    )


# ─── Función principal ────────────────────────────────────────────────────────

def detect_conflicts(
    new_document_id: str,
    new_chunk_ids: List[int],
    new_embeddings: List[List[float]],
    space_id: str,
    tenant_id: str,
    new_doc_authority: int,
    new_doc_version_ts: datetime,
    db,
) -> ConflictReport:
    """
    Detecta y resuelve conflictos entre los nuevos chunks y los existentes en el espacio.

    Para cada chunk nuevo, busca en el mismo espacio chunks existentes con
    similitud coseno >= CONFLICT_THRESHOLD. Aplica resolución automática cuando
    es posible, o crea registros de revisión HITL en caso contrario.

    Args:
        new_document_id:     UUID del documento recién ingestado
        new_chunk_ids:       Lista de IDs de los chunks insertados
        new_embeddings:      Lista de vectores (float[768]) de los nuevos chunks
        space_id:            UUID del espacio al que pertenece el documento
        tenant_id:           UUID del tenant
        new_doc_authority:   authority_weight del nuevo documento
        new_doc_version_ts:  Fecha del nuevo documento (version_ts)
        db:                  Instancia de SupabaseClient

    Returns:
        ConflictReport con todos los conflictos encontrados y sus resoluciones
    """
    report = ConflictReport()

    # Llevar registro de conflictos ya procesados (evitar duplicados por chunk existente)
    seen_existing_chunks: set = set()

    for i, (chunk_id, embedding) in enumerate(zip(new_chunk_ids, new_embeddings)):
        try:
            # Buscar chunks similares en el mismo espacio (excluye el nuevo documento)
            conflicts_raw = db.find_conflicting_chunks(
                query_embedding=embedding,
                space_id=space_id,
                exclude_document_id=new_document_id,
                threshold=CONFLICT_THRESHOLD,
            )
        except Exception as e:
            logger.warning(f"Error buscando conflictos para chunk {chunk_id}: {e}")
            continue

        for row in conflicts_raw:
            existing_chunk_id = row["chunk_id"]

            # Evitar procesar el mismo chunk existente múltiples veces
            if existing_chunk_id in seen_existing_chunks:
                continue
            seen_existing_chunks.add(existing_chunk_id)

            existing_doc_id        = row["document_id"]
            existing_filename      = row.get("filename", "desconocido")
            similarity             = float(row["similarity"])
            existing_authority     = int(row.get("authority_weight") or 5)
            existing_version_ts_raw = row.get("version_ts")

            # Parsear timestamp
            if isinstance(existing_version_ts_raw, str):
                from datetime import datetime
                try:
                    existing_version_ts = datetime.fromisoformat(existing_version_ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    existing_version_ts = datetime.now(timezone.utc)
            elif isinstance(existing_version_ts_raw, datetime):
                existing_version_ts = existing_version_ts_raw
            else:
                existing_version_ts = datetime.now(timezone.utc)

            # Decidir resolución
            resolution, reason = _decide_resolution(
                new_authority=new_doc_authority,
                existing_authority=existing_authority,
                new_version_ts=new_doc_version_ts,
                existing_version_ts=existing_version_ts,
            )

            review_id    = None
            review_token = None

            # Aplicar resolución en base de datos
            try:
                if resolution == "auto_new_wins":
                    # El chunk existente queda superseded
                    db.update_chunk_status(existing_chunk_id, "superseded")
                    logger.info(
                        f"  ⚡ Auto-resolución: chunk {existing_chunk_id} superseded "
                        f"por {chunk_id} (sim={similarity:.2f}) — {reason}"
                    )

                elif resolution == "auto_existing_wins":
                    # El nuevo chunk queda superseded
                    db.update_chunk_status(chunk_id, "superseded")
                    logger.info(
                        f"  ⚡ Auto-resolución: nuevo chunk {chunk_id} superseded "
                        f"(sim={similarity:.2f}) — {reason}"
                    )

                else:
                    # pending → marcar existente como disputed, crear revisión
                    db.update_chunk_status(existing_chunk_id, "disputed")
                    review_token = secrets.token_urlsafe(32)
                    review_record = db.create_conflict_review({
                        "tenant_id":             tenant_id,
                        "space_id":              space_id,
                        "new_document_id":       new_document_id,
                        "new_chunk_id":          chunk_id,
                        "new_doc_authority":     new_doc_authority,
                        "new_doc_version_ts":    new_doc_version_ts.isoformat(),
                        "existing_document_id":  existing_doc_id,
                        "existing_chunk_id":     existing_chunk_id,
                        "existing_doc_authority": existing_authority,
                        "existing_doc_version_ts": existing_version_ts.isoformat(),
                        "existing_filename":     existing_filename,
                        "similarity":            similarity,
                        "resolution":            "pending",
                        "resolution_reason":     reason,
                        "review_token":          review_token,
                    })
                    if review_record:
                        review_id = review_record[0].get("id") if isinstance(review_record, list) else review_record.get("id")

                    logger.info(
                        f"  ⚠️  Conflicto pendiente: chunk {chunk_id} vs {existing_chunk_id} "
                        f"(sim={similarity:.2f}) — review_id={review_id}"
                    )

            except Exception as e:
                logger.error(f"Error aplicando resolución de conflicto: {e}")
                # No interrumpir la ingesta — continuar sin resolución aplicada
                resolution = "pending"
                reason     = f"Error al aplicar resolución: {e}"

            # Crear ConflictItem
            conflict = ConflictItem(
                new_chunk_id=chunk_id,
                existing_chunk_id=existing_chunk_id,
                existing_document_id=existing_doc_id,
                existing_filename=existing_filename,
                similarity=similarity,
                new_authority=new_doc_authority,
                existing_authority=existing_authority,
                new_version_ts=new_doc_version_ts,
                existing_version_ts=existing_version_ts,
                resolution=resolution,
                resolution_reason=reason,
                review_id=review_id,
                review_token=review_token,
            )
            report.conflicts.append(conflict)
            report.total_conflicts += 1
            if resolution == "pending":
                report.pending_review += 1
            else:
                report.auto_resolved += 1

    # Si hay conflictos pendientes → disparar email HITL via n8n
    if report.has_pending and HITL_WEBHOOK_URL:
        _trigger_hitl_email(report, tenant_id, space_id, new_document_id)

    if report.has_conflicts:
        logger.info(
            f"Gobernanza: {report.total_conflicts} conflictos — "
            f"{report.auto_resolved} auto-resueltos, "
            f"{report.pending_review} pendientes HITL"
        )

    return report


# ─── HITL email via n8n ──────────────────────────────────────────────────────

def _trigger_hitl_email(
    report: ConflictReport,
    tenant_id: str,
    space_id: str,
    new_document_id: str,
) -> None:
    """
    Dispara el webhook de n8n para enviar emails HITL con links de acción.

    El webhook de n8n recibe los datos del conflicto y envía un email HTML
    con tres botones: Aprobar nuevo | Mantener existente | Conservar ambos.
    Cada botón llama a POST /review/{id}?action=…&token=…

    Args:
        report:             ConflictReport con los conflictos pendientes
        tenant_id:          UUID del tenant
        space_id:           UUID del espacio
        new_document_id:    UUID del documento nuevo
    """
    pending_items = [c for c in report.conflicts if c.resolution == "pending"]
    if not pending_items:
        return

    # Construir payload para n8n
    payload = {
        "tenant_id":         tenant_id,
        "space_id":          space_id,
        "new_document_id":   new_document_id,
        "conflict_count":    len(pending_items),
        "korio_base_url":    KORIO_BASE_URL,
        "conflicts": [
            {
                "review_id":            c.review_id,
                "existing_filename":    c.existing_filename,
                "similarity_pct":       int(c.similarity * 100),
                "resolution_reason":    c.resolution_reason,
                "new_authority":        c.new_authority,
                "existing_authority":   c.existing_authority,
                # Links de acción para los botones del email
                "action_approve_new":    f"{KORIO_BASE_URL}/review/{c.review_id}?action=approved_new&token={c.review_token}",
                "action_keep_existing":  f"{KORIO_BASE_URL}/review/{c.review_id}?action=approved_existing&token={c.review_token}",
                "action_keep_both":      f"{KORIO_BASE_URL}/review/{c.review_id}?action=kept_both&token={c.review_token}",
            }
            for c in pending_items
            if c.review_id and c.review_token
        ],
    }

    try:
        resp = requests.post(
            HITL_WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        resp.raise_for_status()
        logger.info(f"✉️  HITL email disparado via n8n (webhook status: {resp.status_code})")
    except Exception as e:
        # No interrumpir la ingesta si falla el email
        logger.warning(f"⚠️  Error disparando email HITL: {e} — conflictos guardados, email no enviado")
