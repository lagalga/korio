#!/usr/bin/env python3
"""
Snapshot y restore del estado de datos para la demo del TFM.

Uso:
  python scripts/demo_snapshot.py save [--name <etiqueta>]
  python scripts/demo_snapshot.py restore [--name <etiqueta>]
  python scripts/demo_snapshot.py list

Captura:
  - Supabase: documents, embeddings, conflict_reviews, policies, pipeline_events
  - FalkorDB: grafo completo (nodos + aristas exportados vía Cypher)

NO captura (datos de config inmutables durante demo):
  tenants, spaces, users, user_spaces, mcp_api_keys, audit_log, n8n_errors, waitlist
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db import get_supabase_client
from graph_client import get_graph_client

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"

CONTENT_TABLES = [
    "documents",
    "embeddings",
    "conflict_reviews",
    "policies",
    "pipeline_events",
]

RESTORE_ORDER = [
    "documents",
    "embeddings",
    "conflict_reviews",
    "policies",
    "pipeline_events",
]

DELETE_ORDER = list(reversed(RESTORE_ORDER))


def _snapshot_path(name: str) -> Path:
    return SNAPSHOT_DIR / name


def _save_supabase(sb, dest: Path) -> dict:
    """Exporta tablas de contenido a JSON."""
    stats = {}
    for table in CONTENT_TABLES:
        rows = sb.table(table).select("*").execute().data or []
        (dest / f"{table}.json").write_text(
            json.dumps(rows, default=str, ensure_ascii=False, indent=2)
        )
        stats[table] = len(rows)
    return stats


def _save_falkordb(gc, dest: Path) -> dict:
    """Exporta todos los nodos y aristas del grafo."""
    nodes_result = gc.graph.query(
        "MATCH (n) RETURN labels(n) AS labels, properties(n) AS props"
    )
    nodes = []
    for row in nodes_result.result_set:
        nodes.append({"labels": row[0], "props": row[1]})

    edges_result = gc.graph.query(
        "MATCH (a)-[r]->(b) "
        "RETURN labels(a) AS a_labels, properties(a) AS a_props, "
        "       type(r) AS r_type, properties(r) AS r_props, "
        "       labels(b) AS b_labels, properties(b) AS b_props"
    )
    edges = []
    for row in edges_result.result_set:
        edges.append({
            "a_labels": row[0], "a_props": row[1],
            "r_type": row[2], "r_props": row[3],
            "b_labels": row[4], "b_props": row[5],
        })

    (dest / "graph_nodes.json").write_text(
        json.dumps(nodes, default=str, ensure_ascii=False, indent=2)
    )
    (dest / "graph_edges.json").write_text(
        json.dumps(edges, default=str, ensure_ascii=False, indent=2)
    )
    return {"nodes": len(nodes), "edges": len(edges)}


def cmd_save(args):
    name = args.name or datetime.now().strftime("snap_%Y%m%d_%H%M%S")
    dest = _snapshot_path(name)
    dest.mkdir(parents=True, exist_ok=True)

    print(f"💾 Guardando snapshot '{name}'...")

    sb = get_supabase_client()
    pg_stats = _save_supabase(sb, dest)
    for table, count in pg_stats.items():
        print(f"  ✓ {table}: {count} rows")

    gc = get_graph_client()
    graph_stats = _save_falkordb(gc, dest)
    print(f"  ✓ grafo: {graph_stats['nodes']} nodos, {graph_stats['edges']} aristas")

    meta = {
        "name": name,
        "created_at": datetime.now().isoformat(),
        "postgres": pg_stats,
        "falkordb": graph_stats,
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"\n✅ Snapshot guardado en {dest}")


def cmd_restore(args):
    name = args.name
    if not name:
        snapshots = sorted(SNAPSHOT_DIR.iterdir()) if SNAPSHOT_DIR.exists() else []
        snapshots = [s for s in snapshots if s.is_dir() and (s / "meta.json").exists()]
        if not snapshots:
            print("❌ No hay snapshots guardados")
            return
        name = snapshots[-1].name
        print(f"📌 Usando snapshot más reciente: {name}")

    src = _snapshot_path(name)
    if not src.exists():
        print(f"❌ Snapshot '{name}' no encontrado en {SNAPSHOT_DIR}")
        return

    meta = json.loads((src / "meta.json").read_text())
    print(f"🔄 Restaurando snapshot '{name}' (creado: {meta['created_at']})...")

    if not args.yes:
        confirm = input("⚠️  ESTO BORRARÁ TODOS LOS DATOS ACTUALES. ¿Continuar? [y/N] ")
        if confirm.lower() not in ("y", "yes", "s", "si", "sí"):
            print("Cancelado.")
            return

    sb = get_supabase_client()

    print("  Limpiando tablas...")
    for table in DELETE_ORDER:
        try:
            sb.client.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print(f"    ✓ {table} vaciada")
        except Exception as e:
            if "embeddings" in table or "pipeline_events" in table or "policies" in table:
                sb.client.table(table).delete().gte("id", 0).execute()
                print(f"    ✓ {table} vaciada (int PK)")
            else:
                print(f"    ⚠ {table}: {e}")

    print("  Restaurando tablas...")
    for table in RESTORE_ORDER:
        data_file = src / f"{table}.json"
        if not data_file.exists():
            print(f"    ⚠ {table}: archivo no encontrado, saltando")
            continue
        rows = json.loads(data_file.read_text())
        if not rows:
            print(f"    - {table}: 0 rows (vacía)")
            continue
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            sb.client.table(table).upsert(batch).execute()
        print(f"    ✓ {table}: {len(rows)} rows")

    print("  Restaurando grafo FalkorDB...")
    gc = get_graph_client()

    gc.graph.query("MATCH (n) DETACH DELETE n")
    print("    ✓ Grafo limpiado")

    nodes_file = src / "graph_nodes.json"
    if nodes_file.exists():
        nodes = json.loads(nodes_file.read_text())
        created_nodes = 0
        failed_nodes = 0
        for node in nodes:
            labels_str = ":".join(node["labels"])
            props = node["props"]
            props_clean = {}
            for k, v in props.items():
                # Filtrar embeddings (768 dims) y otras listas grandes
                if isinstance(v, list) and len(v) > 100:
                    continue
                # Filtrar nulls y tipos no soportados por inline properties
                if v is None or isinstance(v, dict):
                    continue
                props_clean[k] = v
            try:
                # IMPORTANTE: FalkorDB no acepta `CREATE (n:L $props)` con
                # parámetros — falla con "Encountered unhandled type in
                # inlined properties". Hay que usar SET sobre el nodo recién
                # creado, que sí acepta el map de parámetros.
                gc.graph.query(
                    f"CREATE (n:{labels_str}) SET n = $props",
                    {"props": props_clean},
                )
                created_nodes += 1
            except Exception as e:
                failed_nodes += 1
                if failed_nodes <= 3:
                    print(f"    ⚠ Nodo {created_nodes+failed_nodes} falló ({labels_str}): {e}")
        print(f"    ✓ {created_nodes}/{len(nodes)} nodos creados ({failed_nodes} saltados)")

    edges_file = src / "graph_edges.json"
    if edges_file.exists():
        edges = json.loads(edges_file.read_text())
        created = 0
        skipped = 0
        for edge in edges:
            a_label = edge["a_labels"][0]
            b_label = edge["b_labels"][0]
            r_type = edge["r_type"]

            a_match = _node_match_clause(a_label, edge["a_props"], "a")
            b_match = _node_match_clause(b_label, edge["b_props"], "b")

            if not a_match or not b_match:
                skipped += 1
                continue

            a_clause, a_params = a_match
            b_clause, b_params = b_match

            r_props = {k: v for k, v in (edge.get("r_props") or {}).items()
                       if not isinstance(v, list) or len(v) <= 100}

            params = {**a_params, **b_params, "r_props": r_props}

            try:
                # Mismo bug en aristas: el inline `[:R $props]` falla con
                # parámetros. Solución: crear la arista y luego SET props.
                if r_props:
                    gc.graph.query(
                        f"MATCH {a_clause}, {b_clause} "
                        f"CREATE (a)-[r:{r_type}]->(b) SET r = $r_props",
                        params,
                    )
                else:
                    gc.graph.query(
                        f"MATCH {a_clause}, {b_clause} "
                        f"CREATE (a)-[:{r_type}]->(b)",
                        params,
                    )
                created += 1
            except Exception:
                skipped += 1
        print(f"    ✓ {created}/{len(edges)} aristas creadas ({skipped} saltadas)")

    print(f"\n✅ Restore completado desde '{name}'")


def _node_match_clause(label: str, props: dict, alias: str):
    """Genera (clause_string, params_dict) para MATCH de un nodo."""
    if label in ("Chunk", "Claim") and "id" in props:
        return (
            f"({alias}:{label} {{id: ${alias}_id}})",
            {f"{alias}_id": props["id"]},
        )
    if label == "Entity" and "name" in props and "tenant_id" in props:
        return (
            f"({alias}:{label} {{tenant_id: ${alias}_tid, name: ${alias}_name}})",
            {f"{alias}_tid": props["tenant_id"], f"{alias}_name": props["name"]},
        )
    if "id" in props:
        return (
            f"({alias}:{label} {{id: ${alias}_id}})",
            {f"{alias}_id": props["id"]},
        )
    return None


def cmd_list(args):
    if not SNAPSHOT_DIR.exists():
        print("No hay snapshots.")
        return
    snapshots = sorted(SNAPSHOT_DIR.iterdir())
    snapshots = [s for s in snapshots if s.is_dir() and (s / "meta.json").exists()]
    if not snapshots:
        print("No hay snapshots.")
        return
    print(f"{'Nombre':<30} {'Fecha':<22} {'Docs':>5} {'Chunks':>7} {'Nodos':>6} {'Aristas':>8}")
    print("-" * 85)
    for s in snapshots:
        meta = json.loads((s / "meta.json").read_text())
        pg = meta.get("postgres", {})
        gr = meta.get("falkordb", {})
        print(
            f"{meta['name']:<30} "
            f"{meta['created_at'][:19]:<22} "
            f"{pg.get('documents', '?'):>5} "
            f"{pg.get('embeddings', '?'):>7} "
            f"{gr.get('nodes', '?'):>6} "
            f"{gr.get('edges', '?'):>8}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot/restore datos demo Korio")
    sub = parser.add_subparsers(dest="command")

    p_save = sub.add_parser("save", help="Guardar snapshot")
    p_save.add_argument("--name", help="Nombre del snapshot (default: timestamp)")
    p_save.set_defaults(func=cmd_save)

    p_restore = sub.add_parser("restore", help="Restaurar snapshot")
    p_restore.add_argument("--name", help="Nombre del snapshot (default: más reciente)")
    p_restore.add_argument("-y", "--yes", action="store_true", help="Sin confirmación")
    p_restore.set_defaults(func=cmd_restore)

    p_list = sub.add_parser("list", help="Listar snapshots")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
    else:
        args.func(args)
