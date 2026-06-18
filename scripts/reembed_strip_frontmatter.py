"""Re-embed chunks quitando frontmatter YAML (mejora ranking semántico)."""
import re
import sys
sys.path.insert(0, '/root/korio/src')

from db import get_supabase_client
from embedder import get_embedder

FRONTMATTER_RE = re.compile(r'^---\s*\n.*?\n---\s*\n', re.DOTALL)

def strip_frontmatter(text: str) -> str:
    cleaned = FRONTMATTER_RE.sub('', text).lstrip()
    return cleaned

sb = get_supabase_client()
emb = get_embedder()

# Buscar todos los chunks que empiezan con frontmatter YAML
rows = sb.client.table('embeddings').select('id,chunk_text,chunk_status').eq('chunk_status','active').execute().data
candidates = [r for r in rows if r['chunk_text'].lstrip().startswith('---')]
print(f'{len(candidates)} chunks activos con frontmatter YAML')

updated = 0
for r in candidates:
    cleaned = strip_frontmatter(r['chunk_text'])
    if cleaned == r['chunk_text'] or len(cleaned) < 50:
        continue
    new_emb = emb.embed_text(cleaned).tolist()
    sb.client.table('embeddings').update({
        'chunk_text': cleaned,
        'vector': new_emb,
    }).eq('id', r['id']).execute()
    updated += 1
    print(f"  ✓ id={r['id']}: {len(r['chunk_text'])} → {len(cleaned)} chars")

print(f'\n{updated}/{len(candidates)} chunks re-embebidos')
