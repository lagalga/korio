# SESSION-STARTER · Pitch deck + defensa TFM

> Cópialo al inicio de la próxima sesión con Claude Code (o Claude Cowork) para retomar.

---

Hola. Sesión de **contenido TFM Korio**. Producto cerrado en producción (v0.3.12 + fix s17b). Defensa **9 julio 2026**. Quedan: deck visual, vídeo nuevo (3 escenas), memoria, banco Q&A, ensayos.

## Estado al cierre sesión 18 (2026-06-23)

### ✅ Cerrado en sesiones anteriores (no repetir)

- **Push GitHub** — los 3 commits (8c06b20, 62cae8f, 4d97cc3) ya estaban en `origin/main` al iniciar la sesión 18.
- **Slide 9** — maquetada a mano en Keynote. ✅
- **Deck pitch** — `Korio_pitch_deck_v4.pptx` (15 slides) + `Korio_anexo_inversor_v1.pptx` (6 slides Q&A). No regenerar.
- **Bug detector frontmatter** — fix commiteado `62cae8f`, en producción.
- **Evaluación reproducible** — P/R/F1 = 1.0, corpus en `data-synthetic/eval-corpus/`.

### ✅ Hecho en sesión 18

- **Guion de rodaje completo** (3 escenas) — en el chat de la sesión remota. Ver sección más abajo.
- **Fix dedupe case-insensitive** (`src/ingest.py`, commit `a7386c8` en rama `claude/starter-deck-review-yyos18`):
  - Bug: dedupe usaba `content_hash` pero PyMuPDF no es determinista → mismo PDF producía hashes distintos → se reingería y el detector lo marcaba conflicto consigo mismo.
  - Fix: primero comprueba `ILIKE filename` dentro del mismo space; fallback a `content_hash`.
  - **Pendiente aplicar en VPS y mergear a main.**
- **n8n timeout** — nodo `POST /upload Korio` del workflow Slack file_shared subido a 300 000 ms (5 min). Ya activo en producción.

### 🔲 Pendiente INMEDIATO antes de grabar

**1. Aplicar fix dedupe en VPS:**
```bash
ssh korio-vps
cd /root/korio
# El VPS tiene cambios locales no commiteados — no hacer git pull directo
# Opción A: cherry-pick
git stash
git fetch origin claude/starter-deck-review-yyos18
git cherry-pick a7386c8
systemctl restart korio-api

# Si cherry-pick falla, editar manualmente src/ingest.py:
# Sustituir el bloque de dedupe (busca ".eq("content_hash", content_hash)")
# por la versión con ILIKE. Ver diff en GitHub rama claude/starter-deck-review-yyos18.
```

**2. Mergear fix a main cuando el VPS esté verde:**
```bash
# En tu Mac local:
git checkout main
git merge claude/starter-deck-review-yyos18
git push origin main
```

**3. Reset limpio del estado demo antes de grabar:**
```bash
# En el VPS:
python3 scripts/demo_snapshot.py restore --name pre_demo_v038
# El snapshot trae R2 y L3 — hay que borrarlos a mano:
python3 -c "
from src.db import get_supabase_client
sb = get_supabase_client()
docs = sb.client.table('documents').select('id,filename').eq('tenant_id','a0000000-0000-0000-0000-000000000001').execute()
for d in docs.data:
    if any(x in d['filename'].lower() for x in ['r2_', 'l3_']):
        print(d['id'], d['filename'])
"
# Luego por cada ID:
curl -X DELETE "https://korio.es/document/<ID>" -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY"
```

**4. Gmail:** quitar label `korio/procesado` del email con R2 adjunto en `contacto@lagalga.es` (para que el workflow lo reprocese en la escena 1).

---

## Guion de rodaje — 3 escenas (~4 min editados)

**Base**: snapshot `pre_demo_v038` restaurado + R2 y L3 borrados.

### Escena 1 — Gobernanza activa E2E (~90 s editados)

1. Abrir `https://korio.es/ui`, user `a1000000-0000-0000-0000-000000000001` (admin Delos).
2. Query: *"¿Cuántos años se conservan los datos de los pacientes?"* → responde desde L2 (circular LOPD v1). Anotar el dato.
3. Cambiar a Slack, canal `#clinica-delos-legal`, subir `L3_circular-lopd-datos-pacientes-v2.pdf`.
4. Esperar ✅ en Slack (~3-4 s de ack, procesamiento en background ~2-3 min). **Corte de edición** durante la espera.
5. Mostrar n8n.korio.es → workflow Pipeline event bus → ejecución con `CONFLICT_DETECTED`.
6. Mostrar email HITL en `contacto@lagalga.es`.
7. Abrir `https://korio.es/docs` → `POST /review/{id}` → body `{"action":"approved_new","reviewer_note":"Versión v2 firmada por Dirección Legal"}` → ejecutar.
8. Volver al chat → misma query → ahora cita L3. Badge ⚠️ en L2.

**Obtener el review ID antes de grabar:**
```bash
# En el VPS tras ingestar L3:
python3 -c "
from src.db import get_supabase_client
sb = get_supabase_client()
r = sb.client.table('conflict_reviews').select('id,created_at').eq('status','pending').order('created_at', desc=True).limit(1).execute()
print(r.data)
"
```

### Escena 2 — RLS aislamiento (~60 s editados)

1. `https://korio.es/ui`, user `a3000000-0000-0000-0000-000000000001` (staff, solo RRHH).
2. Query: *"¿Qué dice la circular LOPD sobre conservación de datos de pacientes?"* → "No encuentro información".
3. Cambiar user a `a1000000-0000-0000-0000-000000000001` (admin, todos los espacios). Misma query → cita L3.
4. Mostrar JSON: `chunks_used: 0` vs `chunks_used: 2`.

### Escena 3 — MCP Claude Desktop (~90 s editados)

1. Claude Desktop, chat nuevo.
2. Query: *"Usando la base de conocimiento de Korio, ¿cuántas horas semanales mínimas tiene que trabajar el personal?"* → llama `search_knowledge_base` → responde con R4 + `graph_contributed: true`.
3. Query: *"¿Cuánto tiempo máximo puede durar una baja por IT?"* → `has_silent_conflict: true` → aviso gobernanza (R3 vs R5).
4. Query: *"¿Cuántos conflictos pendientes hay?"* → llama `list_pending_conflicts` → lista reviews.

---

## 🔲 Pendientes orden de prioridad (16 días hasta defensa)

### 1. Grabar vídeo demo (3-4 h) ← PRÓXIMA ACCIÓN
Guion arriba. Snapshot listo. Fix dedupe aplicar primero.

### 2. Capítulo Evaluación memoria TFM (2-3 h)
En Claude Projects (memoria), NO en Claude Code. 2-3 páginas con metodología, P/R/F1, análisis FP→fix, reproducibilidad.

### 3. Banco Q&A 20 preguntas (2 h)
- 10 académicas (pgvector, baseline, precision/recall, hallucinations, reproducibilidad, bias audit…)
- 5 técnicas (escalado RLS, prompt injection MCP, ACID rollback…)
- 5 negocio (por qué pyme, plan si Mistral cierra API, AI Act nivel riesgo…)

### 4. Ensayos cronometrados (2 × 1.5 h)
- Ensayo 1: solo + cronómetro.
- Ensayo 2: audiencia hostil con 10 preguntas del banco Q&A.

---

## Lo que NO se va a hacer antes defensa

- Re-implementar más código. Producto + bug fix cerrados.
- Bias audit (Phase 9 post-TFM).
- Validación corpus real cliente piloto (Phase 8).
- Comentar `eval/ground_truth.yaml` original (corpus demo · ya no se re-evalúa con el nuevo corpus eval-specific).

---

## Archivos clave

```
/Users/berto/Claude Code/korio/
├── eval/
│   ├── ground_truth_eval_corpus.yaml
│   ├── results_eval_corpus.json
│   ├── surprises_analysis.txt
│   ├── results_final.json          # eval previa (histórica, antes corpus-specific)
│   └── ground_truth.yaml           # eval corpus demo (histórica)
├── data-synthetic/eval-corpus/     # 12 docs reproducibles (sintéticos)
├── data-synthetic/demo-tfm/        # 20 docs corpus demo grabado (no tocar)
├── scripts/
│   ├── evaluate_detector.py        # métricas P/R/F1 doble fuente
│   ├── ingest_eval_corpus.py       # orquestador corpus eval
│   ├── inspect_surprises.py        # análisis FP
│   ├── diagnose_graph.py           # diag grafo FalkorDB
│   ├── reingest_eval_pairs.py      # utilidad histórica
│   └── reembed_strip_frontmatter.py # útil para chunks viejos pre-fix
├── src/
│   ├── preprocessor.py             # MODIFICADO s17b · strippea frontmatter
│   ├── version_extractor.py        # MODIFICADO s17b · prioriza signed_date
│   └── ingest.py                   # MODIFICADO s17b · propaga frontmatter
└── docs/SESSION-STARTER_DECK.md    # este archivo

/Users/berto/Documents/Claude/Projects/Presentación TFM/
├── Korio_pitch_deck_v4.pptx        # deck principal 15 slides
├── Korio_anexo_inversor_v1.pptx    # anexo 6 slides para Q&A
├── build_v4.js                     # generador deck (referencia)
└── build_annex_investor.js         # generador anexo (referencia)
```

---

## Smoke check producción (30 s)

```bash
ssh korio-vps "systemctl is-active korio-api && docker ps --format '{{.Names}}' | grep -E 'ollama|n8n|falkordb' && curl -s https://korio.es/health"
```

Esperado: `active` + 3 contenedores + `{"status":"ok",...}`. Si algo falla, antes de tocar nada, dime qué ves.

---

## Línea de tiempo restante (16 días)

| Día | Tarea |
|---|---|
| 22 jun | ✅ Eval + bug fix frontmatter + Notion + commits |
| 23 jun | ✅ Push GitHub · ✅ Slide 9 Keynote · Fix dedupe VPS · Inicio grabación vídeo |
| 23-26 jun | Vídeo demo (3 escenas) + edición · Capítulo Evaluación memoria TFM |
| 27-30 jun | Banco Q&A 20 preguntas |
| 1-4 jul | Resto capítulos memoria TFM |
| 5-7 jul | 2 ensayos cronometrados |
| 8 jul | Buffer + descanso. **NO toques nada.** Repasa notas. Duerme. |
| **9 jul** | **Defensa** |

---

## Voz para esta sesión

- Hablo claro, sin jergas si voy a decirlo en voz alta.
- Si propongo algo técnico denso, dame también versión narrable.
- Honestidad sobre limitaciones siempre. Si algo se arregló, dilo. Si no, también.
- Caveman mode si arranco con `/caveman`, prosa normal si no.
- Memoria TFM = Claude Projects, no Claude Code. Si te pido capítulo, dame markdown copy-pasteable.

---

## Frase de cierre defensa (memorizar)

> *"El TFM se defiende con un sistema que mide su propio error y lo corrige. No con uno que esconde limitaciones."*

Esa es la frase que gana el tribunal académico.
