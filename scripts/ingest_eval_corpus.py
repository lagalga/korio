#!/usr/bin/env python3
"""
Crear space Eval + ingestar 12 docs del corpus eval-specific.
Diseño: misma fecha, mismo autor, misma autoridad → detector NO auto-resuelve
→ conflict_review pending → métricas limpias.

Uso:
    export KORIO_API_URL=https://korio.es
    export SUPABASE_URL=...
    export SUPABASE_SERVICE_ROLE_KEY=...
    python3 scripts/ingest_eval_corpus.py
"""

import os
import sys
import time
from pathlib import Path
import requests

REPO = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO / "data-synthetic" / "eval-corpus"

API_URL = os.getenv("KORIO_API_URL", "https://korio.es").rstrip("/")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: faltan SUPABASE_URL · SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
    sys.exit(2)

TENANT_DELOS = "a0000000-0000-0000-0000-000000000001"
SPACE_EVAL   = "a1000000-0000-0000-0000-000000000099"

DOCS = [
    "eval_pol_teletrabajo_a.md",
    "eval_pol_teletrabajo_b.md",
    "eval_prot_primera_visita_a.md",
    "eval_prot_primera_visita_b.md",
    "eval_pol_gasto_comida_a.md",
    "eval_pol_gasto_comida_b.md",
    "eval_pol_caducidad_cert_a.md",
    "eval_pol_caducidad_cert_b.md",
    "eval_pol_descuento_a.md",
    "eval_pol_descuento_b.md",
    "eval_pol_horario_atencion_a.md",
    "eval_pol_horario_atencion_b.md",
]


def ensure_space():
    """Crear space Eval si no existe."""
    H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates,return=representation"}
    payload = {
        "id":            SPACE_EVAL,
        "tenant_id":     TENANT_DELOS,
        "name":          "Eval",
        "description":   "Espacio sintético para evaluación cuantitativa del detector (TFM)",
        "authority_weight": 5,
    }
    r = requests.post(f"{SUPABASE_URL}/rest/v1/spaces", headers=H, json=payload, timeout=15)
    if r.status_code in (201, 200, 409):
        print(f"  ✓ space Eval listo ({r.status_code})")
    else:
        print(f"  ✗ space Eval error {r.status_code}: {r.text[:200]}")
        return False

    # Vincular admin (un user de Delos) al space para acceso RLS
    user_admin = "a2000000-0000-0000-0000-000000000001"   # admin Delos típico
    link_payload = {"user_id": user_admin, "space_id": SPACE_EVAL}
    r2 = requests.post(f"{SUPABASE_URL}/rest/v1/user_spaces", headers=H, json=link_payload, timeout=15)
    if r2.status_code in (201, 200, 409):
        print(f"  ✓ user_spaces admin↔Eval ({r2.status_code})")
    else:
        print(f"  ⚠ user_spaces error {r2.status_code}: {r2.text[:200]}")
    return True


def upload(filepath: Path) -> dict:
    url = f"{API_URL}/upload"
    with open(filepath, "rb") as fh:
        files = {"file": (filepath.name, fh, "text/markdown")}
        data = {
            "tenant_id":   TENANT_DELOS,
            "space_id":    SPACE_EVAL,
            "anonymize":   "true",
            "source_type": "manual",
        }
        r = requests.post(url, files=files, data=data, timeout=300)
    if r.status_code != 200:
        return {"_status": r.status_code, "_msg": r.text[:300]}
    return r.json()


def main():
    print(f"[info] API: {API_URL}")
    print(f"[info] tenant Delos: {TENANT_DELOS}")
    print(f"[info] space Eval:   {SPACE_EVAL}\n")

    print("=== 1. Crear space Eval ===")
    if not ensure_space():
        sys.exit(2)
    print()

    print("=== 2. Ingesta secuencial 12 docs ===")
    detected = 0
    for i, fn in enumerate(DOCS, 1):
        fp = CORPUS_DIR / fn
        if not fp.exists():
            print(f"[{i:2d}/{len(DOCS)}] {fn} — NO existe, saltado")
            continue
        print(f"[{i:2d}/{len(DOCS)}] {fn}...", end=" ", flush=True)
        result = upload(fp)
        if "_status" in result:
            print(f"FAIL {result['_status']}: {result['_msg']}")
            continue
        chunks = result.get("chunks_created", 0)
        latency = result.get("latency_ms", 0)
        cr = result.get("conflict_report") or {}
        if cr:
            total = cr.get("total_conflicts", 0)
            auto = cr.get("auto_resolved", 0)
            pend = cr.get("pending_review", 0)
            detected += 1
            print(f"OK · {chunks} chunks · {latency}ms · CONFLICTO total={total} auto={auto} pend={pend}")
        else:
            print(f"OK · {chunks} chunks · {latency}ms")
        time.sleep(2)

    print(f"\n[info] Hecho. {detected} ingestas con conflicto reportado.")
    print(f"[info] Ejecuta: python3 scripts/evaluate_detector.py --gt eval/ground_truth_eval_corpus.yaml")


if __name__ == "__main__":
    main()
