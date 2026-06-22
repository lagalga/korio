#!/usr/bin/env python3
"""
Re-ingestar pares de evaluación para forzar al detector de contradicciones
a generar conflict_reviews completos en el snapshot pre_demo_v038.

Estrategia:
  1. Para cada doc "winner" (R2, M2, L3, G4): localizar document_id actual.
  2. DELETE /document/{id} con admin key → cascada limpia conflicts existentes.
  3. POST /upload con el .md local → re-ingesta dispara detector contra el "loser"
     (R1, M1, L2, G3) que sigue en BD → crea conflict_review.
  4. Imprimir conflict_report devuelto por /upload por cada par.

Uso:
    export KORIO_API_URL=https://korio.es
    export KORIO_ADMIN_API_KEY=...
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_ROLE_KEY=...
    python3 scripts/reingest_eval_pairs.py
"""

import os
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO / "data-synthetic" / "demo-tfm"

API_URL = os.getenv("KORIO_API_URL", "https://korio.es").rstrip("/")
ADMIN_KEY = os.getenv("KORIO_ADMIN_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not ADMIN_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: faltan KORIO_ADMIN_API_KEY · SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(2)

# (filename_winner.md, tenant_id, space_id, loser_filename)
PAIRS = [
    {
        "winner_file": "R2_politica-vacaciones-2025.md",
        "tenant_id":   "a0000000-0000-0000-0000-000000000001",
        "space_id":    "a1000000-0000-0000-0000-000000000001",  # RRHH Delos
        "loser_doc":   "R1_politica-vacaciones-2023",
    },
    {
        "winner_file": "M2_guia-clinica-urgencias-actualizada.md",
        "tenant_id":   "a0000000-0000-0000-0000-000000000001",
        "space_id":    "a1000000-0000-0000-0000-000000000002",  # Médico Delos
        "loser_doc":   "M1_protocolo-atencion-urgencias",
    },
    {
        "winner_file": "L3_circular-lopd-datos-pacientes-v2.md",
        "tenant_id":   "a0000000-0000-0000-0000-000000000001",
        "space_id":    "a1000000-0000-0000-0000-000000000003",  # Legal Delos
        "loser_doc":   "L2_circular-lopd-datos-pacientes-v1",
    },
    {
        "winner_file": "G4_dictamen-fiscal-deducciones-irpf-2025.md",
        "tenant_id":   "b0000000-0000-0000-0000-000000000002",
        "space_id":    "b1000000-0000-0000-0000-000000000002",  # Fiscal García
        "loser_doc":   "G3_dictamen-fiscal-deducciones-irpf-2023",
    },
]


def supabase_get_doc_id(tenant_id: str, filename_stem: str) -> str | None:
    """Busca document_id en Supabase por filename que empiece por stem."""
    url = f"{SUPABASE_URL}/rest/v1/documents"
    params = {
        "tenant_id": f"eq.{tenant_id}",
        "filename":  f"like.{filename_stem}*",
        "select":    "id,filename",
    }
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    r = requests.get(url, params=params, headers=headers, timeout=15)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        return None
    if len(rows) > 1:
        print(f"  [warn] {filename_stem} → {len(rows)} matches, tomando 1º: {rows[0]['filename']}")
    return rows[0]["id"]


def delete_doc(tenant_id: str, document_id: str) -> bool:
    url = f"{API_URL}/document/{document_id}"
    headers = {
        "X-Korio-Admin-Key":   ADMIN_KEY,
        "X-Korio-Tenant-Id":   tenant_id,
    }
    r = requests.delete(url, headers=headers, timeout=30)
    if r.status_code in (200, 204):
        return True
    print(f"  [delete err {r.status_code}] {r.text[:200]}")
    return False


def upload_doc(filepath: Path, tenant_id: str, space_id: str) -> dict:
    url = f"{API_URL}/upload"
    with open(filepath, "rb") as fh:
        files = {"file": (filepath.name, fh, "text/markdown")}
        data = {
            "tenant_id":   tenant_id,
            "space_id":    space_id,
            "anonymize":   "true",
            "source_type": "manual",
        }
        r = requests.post(url, files=files, data=data, timeout=300)
    if r.status_code == 409:
        return {"_status": 409, "_msg": r.text[:300]}
    if r.status_code != 200:
        return {"_status": r.status_code, "_msg": r.text[:300]}
    return r.json()


def main():
    print(f"[info] API: {API_URL}")
    print(f"[info] {len(PAIRS)} pares a re-ingestar\n")

    for i, p in enumerate(PAIRS, 1):
        filepath = DEMO_DIR / p["winner_file"]
        if not filepath.exists():
            print(f"[{i}/{len(PAIRS)}] {p['winner_file']} — NO existe, saltado")
            continue

        stem = filepath.stem
        print(f"[{i}/{len(PAIRS)}] {stem}  vs  {p['loser_doc']}")

        # 1. Buscar document_id actual (puede no existir si ya fue borrado)
        doc_id = supabase_get_doc_id(p["tenant_id"], stem)
        if doc_id:
            print(f"   1. DELETE {doc_id[:8]}...", end=" ", flush=True)
            ok = delete_doc(p["tenant_id"], doc_id)
            print("OK" if ok else "FAIL")
            time.sleep(1)
        else:
            print(f"   1. (no existe en BD, saltando DELETE)")

        # 2. Verificar que loser SIGUE en BD
        loser_id = supabase_get_doc_id(p["tenant_id"], p["loser_doc"])
        if not loser_id:
            print(f"   [warn] loser '{p['loser_doc']}' NO existe en BD — detector no podrá comparar")
        else:
            print(f"   2. loser '{p['loser_doc'][:30]}…' presente OK")

        # 3. Upload winner
        print(f"   3. POST /upload {p['winner_file']}...", end=" ", flush=True)
        result = upload_doc(filepath, p["tenant_id"], p["space_id"])
        if "_status" in result:
            print(f"FAIL {result['_status']}: {result['_msg']}")
            continue
        print(f"OK · {result.get('chunks_created', 0)} chunks · {result.get('latency_ms', 0)}ms")

        cr = result.get("conflict_report") or {}
        if cr:
            print(f"   ✅ CONFLICTO DETECTADO: total={cr.get('total_conflicts', 0)} "
                  f"auto={cr.get('auto_resolved', 0)} pending={cr.get('pending_review', 0)}")
        else:
            print(f"   ⚠️  Sin conflicto reportado — detector NO disparó vs {p['loser_doc']}")
        print()

        time.sleep(2)

    print("[info] Hecho. Re-corre evaluate_detector.py para ver métricas actualizadas.")


if __name__ == "__main__":
    main()
