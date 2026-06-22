# SESSION-STARTER · Pitch deck + defensa TFM

> Cópialo al inicio de la próxima sesión con Claude Code (o Claude Cowork) para retomar.

---

Hola. Sesión de **contenido TFM Korio**. Producto cerrado en producción (v0.3.12 + fix s17b). Defensa **9 julio 2026**. Quedan: deck visual, vídeo nuevo (3 escenas), memoria, banco Q&A, ensayos.

## Estado al cierre sesiones 17 + 17b (2026-06-22)

### ✅ Deck pitch generado

- `~/Documents/Claude/Projects/Presentación TFM/Korio_pitch_deck_v4.pptx` — 15 slides, arquitectura B académica, paleta Berry Ocean, notas presentador con glosarios.
- `~/Documents/Claude/Projects/Presentación TFM/Korio_anexo_inversor_v1.pptx` — 6 slides para Q&A si tribunal pregunta NRR / LTV:CAC / ask / burn / equipo.
- Visual lo maqueto **yo a mano en Keynote**. No regenerar los .pptx salvo orden expresa.

### ✅ Slide 9 — Evaluación cuantitativa

- Resultados sobre corpus eval-specific 12 docs: **Precision 1.000 · Recall 1.000 · F1 1.000**.
- Texto + notas presentador (lenguaje narrable) en Keynote (texto efímero ya volcado) ← **USAR ESTE para narrar**.
- Versión técnica densa de referencia en Keynote · slide 9 directa.
- Cierre del slide: *"El TFM se defiende con un sistema que mide su propio error y lo corrige. No con uno que esconde limitaciones."*

### ✅ Bug detector FIXED (commit `62cae8f`)

- Causa: `chunk_index=0` capturaba solo frontmatter YAML → embedding sin contenido → 5 FP cross-tema en eval.
- Fix: `src/preprocessor.py` strippea frontmatter pre-chunking + parsea YAML a metadata. `src/version_extractor.py` prioriza `signed_date` estructurado. `src/ingest.py` propaga.
- 28/28 tests verdes. E2E verificado en producción + snapshot baseline restaurado tras test.
- **Defensa: ya no es "deuda Phase 9", es "fix aplicado y verificado".**

### ✅ Evaluación reproducible commiteada

- `data-synthetic/eval-corpus/` — 12 docs sintéticos (6 pares positivos + 6 negativos), misma fecha+autoridad para forzar `pending`.
- `eval/ground_truth_eval_corpus.yaml` — anotaciones.
- `eval/results_eval_corpus.json` — métricas crudas.
- `eval/surprises_analysis.txt` — inspección manual de los 5 FP previos al fix.
- `scripts/{evaluate,ingest,inspect,diagnose,reingest}_*.py` — pipeline reproducible.

### ✅ Notion sincronizado

- *Historial de Desarrollo*:
  - "Evaluación cuantitativa detector — P/R/F1 = 1.0" (Done · Éxito)
  - "Bug detector frontmatter YAML — RESUELTO commit 62cae8f" (Done · Bug)
- *Roadmap & Tareas*: bloques "Sesión 17" + "Sesión 17b" al final.

### 🔲 Único pendiente operativo inmediato

**Push 3 commits locales a GitHub** (acción ~30 s):

```bash
gh auth refresh -h github.com -s repo
cd "/Users/berto/Claude Code/korio"
git push -u origin main
```

Commits pendientes:
- `8c06b20` — Eval cuantitativa
- `62cae8f` — Fix preprocessor frontmatter
- `4d97cc3` — Docs session-starter + slide 9

---

## 🔲 Pendientes orden de prioridad (17 días hasta defensa)

### 1. Push GitHub (5 min)
Acción de arriba. Después `git status` debe mostrar `Your branch is up to date with 'origin/main'`.

### 2. Maquetar slide 9 v3 en Keynote (1 h)
Texto + cuadros KPI + notas presentador desde Keynote (texto efímero ya volcado). Cuatro cuadros grandes:
- `1.983 ms` latencia mediana
- `12 / 12` aciertos detector
- `27 contradicciones` en producción
- `5 → 0` falsos positivos · fix aplicado commit `62cae8f`

Notas presentador van en panel de Keynote, no en slide visible.

### 3. Capítulo Evaluación memoria TFM (2-3 h)
Va en Claude Projects (memoria), NO en Claude Code. 2-3 páginas:
- Metodología (corpus controlado, ground truth autoral, fuerza pending)
- Tabla resultados P/R/F1
- Análisis FP cross-tema → identificación bug → fix → verificación E2E
- Reproducibilidad: paths exactos a `eval/`, `data-synthetic/eval-corpus/`, scripts, commits.

### 4. Vídeo demo nuevo · 3 escenas (3-4 h grabación + edición)
Alineadas con slide 8 del deck. Snapshot `pre_demo_v038` ya listo.

- **Escena 1 — Silent conflict E2E** (~90 s): subir 2 docs contradictorios → detección automática → email HITL al admin → click resolución → estado superseded → query antes/después con cambio visible.
- **Escena 2 — RLS aislamiento** (~60 s): mismo query desde dos usuarios distintos (RRHH vs Finanzas) → respuestas diferentes → log SQL mostrando `set_config` + RLS policy.
- **Escena 3 — MCP Claude Desktop** (~90 s): Claude consulta Korio → respuesta con fuentes citadas + similitud → flag `has_silent_conflict: true` → aviso gobernanza en respuesta final.

Total editado: ~4 min. Reservar 1 min para reacciones tribunal.

### 5. Banco Q&A 20 preguntas (2 h)
Documento aparte, NO en deck. Cronometradas (30-60 s respuesta cada una):
- 10 académicas/metodológicas (por qué pgvector, baseline, precision/recall, hallucinations, reproducibilidad, bias audit, etc.)
- 5 técnicas (escalado RLS, prompt injection MCP, ACID rollback, etc.)
- 5 negocio (por qué pyme, plan si Mistral cierra API, AI Act riesgo nivel, etc.)

Categorías ya esbozadas en Keynote · slide 9 directa glosario + design doc original.

### 6. Ensayos cronometrados (2 sesiones · 1.5 h cada una)
- **Ensayo 1 — solo, cronómetro.** Detecta partes lentas, palabras donde te trabes, transiciones que no funcionan.
- **Ensayo 2 — con audiencia hostil simulada.** Alguien hace 10 preguntas duras del banco Q&A. Practica silencio, "tengo anexo dedicado", "no lo sé pero esto sí lo sé".

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

## Línea de tiempo restante (17 días)

| Día | Tarea |
|---|---|
| 22 jun (hoy) | ✅ Eval cerrada + bug fix aplicado + Notion + commits locales |
| 23 jun | Push GitHub · maquetar slide 9 en Keynote |
| 23-26 jun | Capítulo Evaluación memoria TFM + resto capítulos `docs/` |
| 27-30 jun | Banco Q&A 20 preguntas |
| 1-4 jul | Vídeo demo nuevo (3 escenas) + edición |
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
