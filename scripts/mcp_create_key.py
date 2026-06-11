#!/usr/bin/env python
"""
Genera una API key para el servidor MCP de Korio (Phase 7.3).

La key en texto plano se imprime UNA SOLA VEZ; en BD solo guardamos su SHA-256.
Si el usuario la pierde, se revoca con --revoke <prefijo> y se emite otra.

Ejemplos:
  # Crear key para admin de Delos, alias "Claude Desktop laptop":
  python scripts/mcp_create_key.py create \\
    --user-id   a1000000-0000-0000-0000-000000000001 \\
    --tenant-id a0000000-0000-0000-0000-000000000001 \\
    --name "Claude Desktop laptop berto"

  # Listar keys (no muestra el plaintext, solo metadatos):
  python scripts/mcp_create_key.py list --user-id <uuid>

  # Revocar por prefijo de hash (6 primeros chars):
  python scripts/mcp_create_key.py revoke --hash-prefix a1b2c3
"""

import argparse
import os
import secrets
import sys
from datetime import datetime, timezone

# Permitir importar src/ y api/ aunque el script se ejecute desde otro cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, _ROOT)

from api.mcp_server import hash_key  # noqa: E402
from db import get_supabase_client     # noqa: E402


def cmd_create(args: argparse.Namespace) -> int:
    # 32 bytes (~256 bits) en urlsafe base64 → ~43 chars. Prefijo `korio_` para
    # distinguir visualmente las MCP keys de otros secretos en logs.
    plaintext = "korio_" + secrets.token_urlsafe(32)
    key_hash  = hash_key(plaintext)

    db = get_supabase_client()
    db.client.table("mcp_api_keys").insert({
        "key_hash":  key_hash,
        "user_id":   args.user_id,
        "tenant_id": args.tenant_id,
        "name":      args.name,
    }).execute()

    print("=" * 72)
    print("MCP API key creada — GUÁRDALA AHORA, no se mostrará otra vez.")
    print("=" * 72)
    print(f"  user_id    : {args.user_id}")
    print(f"  tenant_id  : {args.tenant_id}")
    print(f"  alias      : {args.name}")
    print(f"  hash       : {key_hash[:12]}...")
    print()
    print(f"  X-Korio-MCP-Key: {plaintext}")
    print()
    print("Configuración cliente (Claude Desktop / n8n / curl):")
    print(f"  curl -H 'X-Korio-MCP-Key: {plaintext}' https://korio.es/mcp/sse")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    db = get_supabase_client()
    q = db.client.table("mcp_api_keys").select(
        "key_hash, user_id, tenant_id, name, created_at, last_used_at, revoked_at"
    )
    if args.user_id:
        q = q.eq("user_id", args.user_id)
    if args.tenant_id:
        q = q.eq("tenant_id", args.tenant_id)
    rows = q.order("created_at", desc=True).execute().data or []

    if not rows:
        print("Sin keys.")
        return 0

    print(f"{'hash':14} {'name':30} {'user_id':38} {'estado'}")
    print("-" * 100)
    for r in rows:
        estado = "REVOCADA" if r.get("revoked_at") else "activa"
        last = r.get("last_used_at") or "—"
        print(
            f"{r['key_hash'][:12]}.. {r['name'][:30]:30} {r['user_id']:38} {estado}  last={last}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    db = get_supabase_client()
    candidates = db.client.table("mcp_api_keys").select("key_hash, name, revoked_at").execute().data or []
    matches = [c for c in candidates if c["key_hash"].startswith(args.hash_prefix)]
    if not matches:
        print(f"Ninguna key empieza por {args.hash_prefix!r}.")
        return 1
    if len(matches) > 1:
        print(f"Prefijo ambiguo, {len(matches)} matches. Usa más caracteres.")
        for m in matches:
            print(f"  {m['key_hash'][:16]}.. {m['name']}")
        return 1
    target = matches[0]
    if target.get("revoked_at"):
        print(f"Ya estaba revocada: {target['name']}")
        return 0
    db.client.table("mcp_api_keys").update(
        {"revoked_at": datetime.now(timezone.utc).isoformat()}
    ).eq("key_hash", target["key_hash"]).execute()
    print(f"Revocada: {target['name']} ({target['key_hash'][:12]}..)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestión de API keys del MCP server de Korio")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Crear una key nueva")
    p_create.add_argument("--user-id",   required=True, help="UUID del usuario al que se ata la key")
    p_create.add_argument("--tenant-id", required=True, help="UUID del tenant del usuario")
    p_create.add_argument("--name",      required=True, help="Alias humano (ej. 'Claude Desktop laptop')")
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="Listar keys (sin plaintext)")
    p_list.add_argument("--user-id",   default=None)
    p_list.add_argument("--tenant-id", default=None)
    p_list.set_defaults(func=cmd_list)

    p_revoke = sub.add_parser("revoke", help="Revocar una key por prefijo de su hash")
    p_revoke.add_argument("--hash-prefix", required=True, help="Primeros chars del SHA-256")
    p_revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
