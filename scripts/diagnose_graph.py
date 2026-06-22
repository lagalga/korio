#!/usr/bin/env python3
"""Diagnóstico rápido del estado del grafo FalkorDB."""
import os
from falkordb import FalkorDB

URL = os.getenv("FALKORDB_URL", "redis://localhost:16379")
host_port = URL.replace("redis://", "")
host, port = (host_port.split(":") + ["6379"])[:2]
port = int(port)
graph_name = os.getenv("FALKORDB_GRAPH", "korio")

print(f"[conn] {host}:{port}  graph={graph_name}")
db = FalkorDB(host=host, port=port)

print("\n--- grafos disponibles ---")
try:
    print(db.list_graphs())
except Exception as e:
    print(f"err: {e}")

g = db.select_graph(graph_name)

queries = [
    ("nodos por label",          "MATCH (n) RETURN labels(n)[0] AS lbl, count(*) AS c"),
    ("aristas por tipo",         "MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS c"),
    ("CONTRADICTS sin filtro",   "MATCH (a:Claim)-[r:CONTRADICTS]->(b:Claim) RETURN count(*) AS c"),
    ("Documents por tenant",     "MATCH (d:Document) RETURN d.tenant_id AS t, count(*) AS c"),
    ("Claims por tenant",        "MATCH (c:Claim) RETURN c.tenant_id AS t, count(*) AS c"),
    ("muestra 5 Document.filename", "MATCH (d:Document) RETURN d.tenant_id AS t, d.filename AS fn LIMIT 5"),
    ("muestra 5 CONTRADICTS",       "MATCH (a:Claim)-[r:CONTRADICTS]->(b:Claim) RETURN a.tenant_id AS t, r.similarity AS sim LIMIT 5"),
]
for label, cy in queries:
    print(f"\n--- {label} ---")
    try:
        res = g.query(cy)
        for row in res.result_set:
            print(" ", row)
        if not res.result_set:
            print("  (vacío)")
    except Exception as e:
        print(f"  err: {e}")
