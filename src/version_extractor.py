"""
Extractor de fecha de versión de un documento.

Deduce la fecha "real" del documento a partir del filename y del contenido
(post-MarkItDown). Si no encuentra ninguna pista, devuelve None y el caller
debe usar `datetime.now(timezone.utc)` como fallback.

Prioridad (descendente):
  1. Fecha textual completa día+mes+año en contenido (más confiable).
  2. Fecha ISO en contenido.
  3. Año aislado en filename (`R1_politica-vacaciones-2023.pdf`).
  4. Marcador de versión `v(N)` en filename → now() + N días (ordena versiones).
  5. Marcador léxico "actualizada"/"nueva"/"revisada" → now() (posterior por defecto).
  6. Año aislado en contenido (último recurso, p.ej. "versión 2025").

Sin extracción ≠ fecha hoy: devolvemos None para que el caller use now()
y la auto-resolución haga lo correcto (mismo timestamp → HITL honesto).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_MONTHS_RE = "|".join(_MONTHS.keys())

_RE_TEXTDATE_SPACED = re.compile(
    rf"\b(\d{{1,2}})\s*de\s*({_MONTHS_RE})\s*de\s*(20\d{{2}})\b",
    re.IGNORECASE,
)
_RE_TEXTDATE_NOSPACE = re.compile(
    rf"(\d{{1,2}})de({_MONTHS_RE})de(20\d{{2}})",
    re.IGNORECASE,
)
_RE_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_RE_FILE_YEAR = re.compile(r"[_\-\s](20\d{2})(?:\D|$)")
_RE_FILE_VERSION = re.compile(r"[_\-\s.]v(\d+)\b", re.IGNORECASE)
_RE_LEXICAL_NEWER = re.compile(
    r"\b(actualizad[oa]s?|nuevas?|nuevos?|revisad[oa]s?|vigente|en\s+vigor)\b",
    re.IGNORECASE,
)
_RE_YEAR_ANY = re.compile(r"\b(20\d{2})\b")

_CONTENT_HEAD_CHARS = 3000


def extract_version_ts(
    filename: str,
    content: Optional[str] = None,
) -> Tuple[Optional[datetime], str]:
    """Devuelve (fecha, source) o (None, 'no_match')."""
    head = (content or "")[:_CONTENT_HEAD_CHARS]
    now = datetime.now(timezone.utc)

    # 1) Fecha textual día+mes+año en contenido
    for regex, label in (
        (_RE_TEXTDATE_SPACED, "content:textdate_spaced"),
        (_RE_TEXTDATE_NOSPACE, "content:textdate_nospace"),
    ):
        m = regex.search(head)
        if m:
            try:
                return datetime(
                    int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)),
                    tzinfo=timezone.utc,
                ), label
            except ValueError:
                pass

    # 2) ISO en contenido
    m = _RE_ISO.search(head)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                            tzinfo=timezone.utc), "content:iso"
        except ValueError:
            pass

    # 3) Año en filename (R1_..._2023.pdf → 2023-01-01)
    m = _RE_FILE_YEAR.search(filename)
    if m:
        return datetime(int(m.group(1)), 1, 1, tzinfo=timezone.utc), "filename:year"

    # 4) Marcador de versión vN → now + N días (vN > v(N-1) cronológicamente)
    m = _RE_FILE_VERSION.search(filename)
    if m:
        n = int(m.group(1))
        return now + timedelta(days=n), f"filename:version=v{n}"

    # 5) Marcador léxico "actualizada/nueva/revisada" → now()
    if _RE_LEXICAL_NEWER.search(head) or _RE_LEXICAL_NEWER.search(filename):
        return now, "lexical:newer_marker"

    # 6) Año aislado en contenido (último recurso)
    m = _RE_YEAR_ANY.search(head)
    if m:
        return datetime(int(m.group(1)), 1, 1, tzinfo=timezone.utc), "content:year"

    return None, "no_match"
