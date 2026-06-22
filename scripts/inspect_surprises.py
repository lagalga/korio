#!/usr/bin/env python3
"""
Inspecciona los 5 pares 'sorpresa' del eval corpus para confirmar FP.
Muestra chunks comparados + similitud + resolución del conflict_review.
"""
import os, sys, requests, json

SB = os.getenv("SUPABASE_URL"); KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

SURPRISES = [
    ("eval_prot_primera_visita_a", "eval_pol_teletrabajo_b"),
    ("eval_prot_primera_visita_b", "eval_pol_gasto_comida_a"),
    ("eval_pol_gasto_comida_b",    "eval_pol_caducidad_cert_a"),
    ("eval_pol_caducidad_cert_b",  "eval_pol_descuento_a"),
    ("eval_pol_descuento_b",       "eval_pol_horario_atencion_a"),
]

def find_pair_in_reviews(stem_a: str, stem_b: str) -> list[dict]:
    """Busca conflict_reviews que mencionen este par de filenames."""
    docs = requests.get(f"{SB}/rest/v1/documents",
        params={"filename": f"like.{stem_a}*", "select": "id"},
        headers=H, timeout=15).json()
    docs_b = requests.get(f"{SB}/rest/v1/documents",
        params={"filename": f"like.{stem_b}*", "select": "id"},
        headers=H, timeout=15).json()
    if not docs or not docs_b: return []
    da, db = docs[0]["id"], docs_b[0]["id"]
    # buscar en ambos sentidos
    r1 = requests.get(f"{SB}/rest/v1/conflict_reviews",
        params={"new_document_id": f"eq.{da}", "existing_document_id": f"eq.{db}",
                "select": "id,similarity,resolution,resolution_reason,new_chunk_id,existing_chunk_id"},
        headers=H, timeout=15).json()
    r2 = requests.get(f"{SB}/rest/v1/conflict_reviews",
        params={"new_document_id": f"eq.{db}", "existing_document_id": f"eq.{da}",
                "select": "id,similarity,resolution,resolution_reason,new_chunk_id,existing_chunk_id"},
        headers=H, timeout=15).json()
    return r1 + r2

def get_chunk_text(chunk_id: int) -> str:
    r = requests.get(f"{SB}/rest/v1/embeddings",
        params={"id": f"eq.{chunk_id}", "select": "chunk_text"},
        headers=H, timeout=15).json()
    return r[0]["chunk_text"] if r else "(no encontrado)"

print(f"{'='*90}")
print(f"INSPECCIÓN DE 5 PARES SORPRESA DEL EVAL CORPUS")
print(f"{'='*90}\n")

for i, (a, b) in enumerate(SURPRISES, 1):
    print(f"--- SORPRESA {i}: {a}  ↔  {b} ---")
    reviews = find_pair_in_reviews(a, b)
    if not reviews:
        print("  (no encontrado en conflict_reviews)")
        print()
        continue
    for r in reviews:
        print(f"  similarity: {r['similarity']:.3f}  ·  resolution: {r['resolution']}")
        if r.get('resolution_reason'):
            print(f"  reason: {r['resolution_reason'][:200]}")
        ca = get_chunk_text(r['new_chunk_id'])[:300]
        cb = get_chunk_text(r['existing_chunk_id'])[:300]
        print(f"\n  CHUNK NUEVO (new_chunk_id={r['new_chunk_id']}):")
        print(f"  {ca}")
        print(f"\n  CHUNK EXISTENTE (existing_chunk_id={r['existing_chunk_id']}):")
        print(f"  {cb}")
        print()
    print()
