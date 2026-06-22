#!/usr/bin/env python3
"""
Evaluación del detector de contradicciones de Korio.

Compara:
  - aristas CONTRADICTS en FalkorDB (detector ingesta)
  - ground truth declarado en eval/ground_truth.yaml

Calcula precision / recall / F1 sobre detector ingesta.
Reporta query_time silent conflicts aparte (cualitativo).

Uso:
    python3 scripts/evaluate_detector.py
    python3 scripts/evaluate_detector.py --json out.json
    python3 scripts/evaluate_detector.py --tenant delos

Requisitos:
    pip install pyyaml falkordb

Variables env:
    FALKORDB_URL=redis://localhost:6379   (o IP del VPS)
    FALKORDB_GRAPH=korio                  (opcional, default 'korio')
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
GT_PATH = REPO_ROOT / "eval" / "ground_truth.yaml"


@dataclass
class Pair:
    id: str
    tenant_uuid: str
    tenant_key: str
    doc_a: str
    doc_b: str
    space: str
    detector: str
    label: str            # "positive" | "negative"
    rationale: str
    detected: Optional[bool] = None       # True/False/None (None = no aplica)
    edge_similarity: Optional[float] = None


def normalize(s: str) -> str:
    """Normalize filename para matching (basename sin extensión, lowercase)."""
    return Path(s).stem.lower()


def load_ground_truth(path: Path) -> tuple[dict, list[Pair]]:
    with open(path) as f:
        gt = yaml.safe_load(f)
    tenants_map = gt["tenants"]
    pairs: list[Pair] = []
    for label_key, items in [("positive", gt.get("positives", [])),
                             ("negative", gt.get("negatives", []))]:
        for it in items:
            pairs.append(Pair(
                id=it["id"],
                tenant_key=it["tenant"],
                tenant_uuid=tenants_map[it["tenant"]],
                doc_a=it["doc_a"],
                doc_b=it["doc_b"],
                space=it.get("space", "?"),
                detector=it.get("detector", "ingest"),
                label=label_key,
                rationale=it.get("rationale", "") or it.get("contradiction", ""),
            ))
    return tenants_map, pairs


def fetch_supabase_pairs(tenant_uuid: str) -> dict[frozenset, dict]:
    """
    Devuelve pares de documentos con registro en conflict_reviews (Postgres).
    Cubre TODAS las detecciones de ingesta, incluso las auto-resueltas
    (cuyas aristas CONTRADICTS en grafo pueden haberse limpiado).
    """
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("[warn] SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY no definidos; salto conflict_reviews")
        return {}
    sb = create_client(url, key)

    rows = sb.table("conflict_reviews").select(
        "new_document_id,existing_document_id,similarity,resolution,tenant_id"
    ).eq("tenant_id", tenant_uuid).execute().data

    if not rows:
        return {}

    # Resolver document_id → filename
    doc_ids = set()
    for r in rows:
        doc_ids.add(r["new_document_id"])
        doc_ids.add(r["existing_document_id"])
    docs = sb.table("documents").select("id,filename").in_("id", list(doc_ids)).execute().data
    id_to_fn = {d["id"]: d["filename"] for d in docs}

    pairs: dict[frozenset, dict] = {}
    for r in rows:
        fa = id_to_fn.get(r["new_document_id"], "?")
        fb = id_to_fn.get(r["existing_document_id"], "?")
        key = frozenset({normalize(fa), normalize(fb)})
        existing = pairs.get(key, {"similarity": 0.0, "resolution": r["resolution"]})
        sim = float(r["similarity"]) if r["similarity"] is not None else 0.0
        if sim > existing["similarity"]:
            existing["similarity"] = sim
        existing["resolution"] = r["resolution"]
        pairs[key] = existing
    return pairs


def fetch_graph_pairs(graph_url: str, graph_name: str, tenant_uuid: str) -> set[frozenset]:
    """
    Devuelve set de frozenset({filename_a_norm, filename_b_norm}) con los
    pares de documentos que tienen al menos UNA arista CONTRADICTS entre
    sus claims, para el tenant indicado.
    """
    from falkordb import FalkorDB

    # Parse redis URL
    if graph_url.startswith("redis://"):
        host_port = graph_url[len("redis://"):]
    else:
        host_port = graph_url
    if ":" in host_port:
        host, port = host_port.split(":", 1)
        port = int(port)
    else:
        host, port = host_port, 6379

    db = FalkorDB(host=host, port=port)
    graph = db.select_graph(graph_name)

    cypher = """
    MATCH (da:Document {tenant_id: $tenant})-[:CONTAINS]->(:Chunk)
          -[:HAS_CLAIM]->(:Claim)-[r:CONTRADICTS]->(:Claim)
          <-[:HAS_CLAIM]-(:Chunk)<-[:CONTAINS]-(db:Document {tenant_id: $tenant})
    WHERE da.id <> db.id
    RETURN DISTINCT da.filename AS fa, db.filename AS fb, r.similarity AS sim
    """
    result = graph.query(cypher, {"tenant": tenant_uuid})

    pairs: dict[frozenset, float] = {}
    for row in result.result_set:
        fa, fb, sim = row[0], row[1], row[2]
        key = frozenset({normalize(fa), normalize(fb)})
        # Si misma arista aparece más veces (varios claims pares), nos quedamos
        # con la similitud máxima.
        if key not in pairs or (sim is not None and sim > pairs[key]):
            pairs[key] = sim if sim is not None else 0.0
    return pairs


def evaluate(pairs: list[Pair], detected_pairs: dict[str, dict[frozenset, float]]):
    """
    pairs: lista ground truth
    detected_pairs: por tenant_uuid -> dict {frozenset(a,b) -> similarity}
    Solo evaluamos pares con detector='ingest'. query_time se reporta aparte.
    """
    by_label = {"positive": [], "negative": []}
    qt_pairs: list[Pair] = []

    for p in pairs:
        if p.detector == "query_time":
            qt_pairs.append(p)
            continue
        key = frozenset({normalize(p.doc_a), normalize(p.doc_b)})
        det = detected_pairs.get(p.tenant_uuid, {})
        if key in det:
            p.detected = True
            p.edge_similarity = det[key]
        else:
            p.detected = False
        by_label[p.label].append(p)

    tp = sum(1 for p in by_label["positive"] if p.detected)
    fn = sum(1 for p in by_label["positive"] if not p.detected)
    fp = sum(1 for p in by_label["negative"] if p.detected)
    tn = sum(1 for p in by_label["negative"] if not p.detected)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Detectados que NO están en ground truth (sorpresas)
    gt_keys: dict[str, set[frozenset]] = defaultdict(set)
    for p in pairs:
        if p.detector != "ingest":
            continue
        gt_keys[p.tenant_uuid].add(frozenset({normalize(p.doc_a), normalize(p.doc_b)}))

    surprises: list[dict] = []
    self_pairs: list[dict] = []
    for tenant_uuid, dpairs in detected_pairs.items():
        for k, sim in dpairs.items():
            if len(k) < 2:
                # CONTRADICTS dentro del mismo documento (chunks intra-doc)
                a = next(iter(k))
                self_pairs.append({
                    "tenant_uuid": tenant_uuid,
                    "doc": a,
                    "similarity": sim,
                })
                continue
            if k not in gt_keys[tenant_uuid]:
                a, b = tuple(k)
                surprises.append({
                    "tenant_uuid": tenant_uuid,
                    "doc_a": a,
                    "doc_b": b,
                    "similarity": sim,
                })

    return {
        "metrics": {
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(precision, 4),
            "recall":    round(recall, 4),
            "F1":        round(f1, 4),
            "n_positives": tp + fn,
            "n_negatives": fp + tn,
            "n_total":     tp + fp + fn + tn,
        },
        "positives": [asdict(p) for p in by_label["positive"]],
        "negatives": [asdict(p) for p in by_label["negative"]],
        "query_time_pairs": [asdict(p) for p in qt_pairs],
        "surprises_not_in_ground_truth": surprises,
        "intra_document_pairs": self_pairs,
    }


def print_report(report: dict):
    m = report["metrics"]
    print()
    print("=" * 72)
    print("EVALUACIÓN DETECTOR DE CONTRADICCIONES · Korio TFM")
    print("=" * 72)
    print()
    print(f"Total pares evaluados (ingesta):  n = {m['n_total']}")
    print(f"  · positivos esperados:          {m['n_positives']}")
    print(f"  · negativos esperados:          {m['n_negatives']}")
    print()
    print(f"  TP (acierto positivo):          {m['TP']}")
    print(f"  FP (falsa alarma):              {m['FP']}")
    print(f"  FN (escape):                    {m['FN']}")
    print(f"  TN (correcto rechazo):          {m['TN']}")
    print()
    print(f"  Precision = TP/(TP+FP)        = {m['precision']:.4f}")
    print(f"  Recall    = TP/(TP+FN)        = {m['recall']:.4f}")
    print(f"  F1        = 2·P·R/(P+R)       = {m['F1']:.4f}")
    print()

    print("-" * 72)
    print("POSITIVOS · resultado por par")
    print("-" * 72)
    for p in report["positives"]:
        flag = "✓ TP" if p["detected"] else "✗ FN"
        sim  = f"sim={p['edge_similarity']:.3f}" if p["edge_similarity"] is not None else ""
        print(f"  [{flag}] {p['id']:5s} {p['doc_a'][:42]:42s} ↔ {p['doc_b'][:42]:42s} {sim}")

    print()
    print("-" * 72)
    print("NEGATIVOS · resultado por par")
    print("-" * 72)
    for p in report["negatives"]:
        flag = "✗ FP" if p["detected"] else "✓ TN"
        sim  = f"sim={p['edge_similarity']:.3f}" if p["edge_similarity"] is not None else ""
        print(f"  [{flag}] {p['id']:5s} {p['doc_a'][:42]:42s} ↔ {p['doc_b'][:42]:42s} {sim}")

    if report["query_time_pairs"]:
        print()
        print("-" * 72)
        print("PARES QUERY-TIME · evaluación cualitativa (NO incluidos en P/R)")
        print("-" * 72)
        for p in report["query_time_pairs"]:
            print(f"  {p['id']:5s} {p['doc_a']} ↔ {p['doc_b']}")
            print(f"        rationale: {p['rationale']}")
            print(f"        validar manualmente lanzando query relevante con flag silent.")

    if report.get("intra_document_pairs"):
        print()
        print("-" * 72)
        print("INTRA-DOCUMENTO · CONTRADICTS dentro del mismo doc (raro)")
        print("-" * 72)
        for s in report["intra_document_pairs"]:
            print(f"  {s['doc']}  sim={s['similarity']:.3f}  tenant={s['tenant_uuid'][:8]}…")

    if report["surprises_not_in_ground_truth"]:
        print()
        print("-" * 72)
        print("SORPRESAS · CONTRADICTS detectados NO etiquetados en ground truth")
        print("-" * 72)
        for s in report["surprises_not_in_ground_truth"]:
            print(f"  {s['doc_a']} ↔ {s['doc_b']}  sim={s['similarity']:.3f}  tenant={s['tenant_uuid'][:8]}…")
        print()
        print("  Revisar manualmente: ¿son contradicciones legítimas no anotadas")
        print("  (recall sería mejor) o falsos positivos (precision sería peor)?")

    print()
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="Escribir reporte completo a fichero JSON")
    parser.add_argument("--tenant", help="Filtrar a un tenant_key (delos|garcia)")
    parser.add_argument("--gt", default=str(GT_PATH), help="Ruta YAML ground truth")
    parser.add_argument("--graph-url", default=os.getenv("FALKORDB_URL", "redis://localhost:6379"))
    parser.add_argument("--graph-name", default=os.getenv("FALKORDB_GRAPH", "korio"))
    args = parser.parse_args()

    tenants_map, pairs = load_ground_truth(Path(args.gt))
    if args.tenant:
        if args.tenant not in tenants_map:
            print(f"ERROR: tenant '{args.tenant}' no en {list(tenants_map)}", file=sys.stderr)
            sys.exit(2)
        pairs = [p for p in pairs if p.tenant_key == args.tenant]

    tenants_to_query = {p.tenant_uuid for p in pairs if p.detector == "ingest"}

    print(f"[info] graph={args.graph_url} graph_name={args.graph_name}")
    print(f"[info] tenants a consultar: {len(tenants_to_query)}")
    detected: dict[str, dict[frozenset, float]] = {}
    for tuuid in tenants_to_query:
        graph_pairs = fetch_graph_pairs(args.graph_url, args.graph_name, tuuid)
        sb_pairs = fetch_supabase_pairs(tuuid)
        # Combinar ambas fuentes
        combined: dict[frozenset, float] = dict(graph_pairs)
        for k, info in sb_pairs.items():
            sim = info["similarity"]
            if k not in combined or sim > combined[k]:
                combined[k] = sim
        detected[tuuid] = combined
        print(f"[info] tenant {tuuid[:8]}… → grafo={len(graph_pairs)} · conflict_reviews={len(sb_pairs)} · combinado={len(combined)} pares")

    report = evaluate(pairs, detected)
    print_report(report)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"[info] reporte JSON guardado en {args.json}")


if __name__ == "__main__":
    main()
