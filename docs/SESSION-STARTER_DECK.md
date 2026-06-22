# SESSION-STARTER · Pitch deck + defensa TFM

> Cópialo al inicio de la próxima sesión con Claude Code (o Claude Cowork) para retomar.

---

Hola. Sesión de **contenido TFM Korio**, no de código. Estoy preparando la defensa del 9 de julio 2026. El producto está cerrado en producción (v0.3.12). Quedan: deck, vídeo opcional, memoria, banco Q&A, ensayos.

## Estado al cierre sesión 17 (2026-06-22)

### ✅ Deck pitch
- **v4 generado** en arquitectura B (académica): `~/Documents/Claude/Projects/Presentación TFM/Korio_pitch_deck_v4.pptx` (15 slides, paleta Berry Ocean, notas presentador con glosarios)
- **Anexo inversor v1**: `Korio_anexo_inversor_v1.pptx` (6 slides — NRR/LTV:CAC/ask/burn/equipo)
- **Slide 9 v3 narrable**: `~/Claude Code/korio/eval/SLIDE_9_NARRABLE.md` (lenguaje normal, sin jergas en el slide visible)
- v3 original conservado como referencia: `eval/SLIDE_9_FINAL.md`
- **Visual lo retoco yo a mano en Keynote**, ya no toques el .pptx generado salvo orden expresa.

### ✅ Evaluación cuantitativa cerrada
- Corpus eval-specific 12 docs sintéticos en `data-synthetic/eval-corpus/`
- Resultados: **Precision 1.000 · Recall 1.000 · F1 1.000** (n=12)
- 5 FP cross-tema identificados, causa: `chunk_index=0` solo captura frontmatter YAML — bug `src/preprocessor.py` localizado, fix <1h pendiente Phase 9
- Artefactos: `eval/ground_truth_eval_corpus.yaml`, `eval/results_eval_corpus.json`, `eval/surprises_analysis.txt`
- Scripts reusables: `scripts/{evaluate,ingest,inspect,diagnose,reingest}_*.py`
- Commit `8c06b20` en `main` local. **🔲 Push GitHub bloqueado:** token `lagalga` sin write. Refrescar con `gh auth refresh -h github.com -s repo` y `git push -u origin main`.
- VPS sincronizado vía rsync. Restore `pre_eval_20260622` ejecutado — producción intacta.

### ✅ Notion actualizado
- 2 entradas en *Historial de Desarrollo* (Done + In Progress)
- Roadmap & Tareas con bloque "Sesión 17" al final

### 🔲 Pendientes orden de prioridad

1. **Push commits `8c06b20` + `62cae8f` a GitHub** (acción ~30 s tras `gh auth refresh -s repo`).
2. **Maquetar slide 9 v3 en Keynote** usando texto de `eval/SLIDE_9_NARRABLE.md`. Notas presentador van en panel de Keynote.
3. **Anexo memoria TFM — capítulo Evaluación** citando los artifacts de `eval/`. NO en Claude Code; va en Claude Projects o el editor de memoria que uses. Output esperado: 2-3 páginas con metodología + tabla resultados + análisis FP + reproducibilidad.
4. **Banco Q&A 20 preguntas** cronometradas (30-60 s respuesta). Categorías: académicas/metodológicas (10) + técnicas (5) + negocio (5). Documento aparte, no en deck.
5. **2 ensayos cronometrados.** Primer ensayo solo. Segundo con audiencia hostil simulada (alguien hace preguntas duras Q&A).
6. **Vídeo demo nuevo · 3 escenas alineadas con slide 8:**
   - Escena 1 — Silent conflict E2E: subir 2 docs contradictorios → detección automática → email HITL → click resolución → estado superseded → query antes/después con cambio visible.
   - Escena 2 — RLS aislamiento: mismo query desde dos usuarios distintos (RRHH vs Finanzas) → respuestas distintas → log SQL mostrando `set_config` y RLS policy.
   - Escena 3 — MCP Claude Desktop: Claude consulta Korio → respuesta con fuentes citadas + similitud → flag `has_silent_conflict: true` → aviso gobernanza.
   - Snapshot `pre_demo_v038` listo. Estimado 3-4 h grabación + edición.

### ✅ Bug FIXED en sesión 17b (commit `62cae8f`)

`src/preprocessor.py` strippea ahora frontmatter YAML pre-chunking. `extract_frontmatter()` parsea con pyyaml, guarda dict en metadata, devuelve body limpio. `version_extractor` prioriza `signed_date` del frontmatter. 28/28 tests verdes. E2E verificado en producción + restore baseline. Slide 9 v3 actualizable de "limitación pendiente" a "fix aplicado". Detalle en Notion *Historial de Desarrollo* entrada actualizada.

## Lo que NO se va a hacer antes defensa

- Re-implementar nada en código. Producto cerrado.
- Bias audit completo (Phase 9 post-TFM).
- Validación corpus real cliente piloto (Phase 8).
- Comentar/limpiar `eval/ground_truth.yaml` original (corpus demo, no se re-evalúa salvo re-grabe).

## Archivos clave

```
/Users/berto/Claude Code/korio/
├── eval/
│   ├── SLIDE_9_FINAL.md            # versión técnica densa (ref)
│   ├── SLIDE_9_NARRABLE.md         # versión que vas a leer en voz alta ← USA ESTA
│   ├── ground_truth_eval_corpus.yaml
│   ├── results_eval_corpus.json
│   ├── surprises_analysis.txt
│   └── results_final.json          # eval previa antes corpus-specific (histórica)
├── data-synthetic/eval-corpus/     # 12 docs reproducibles
├── scripts/{evaluate,ingest,inspect,diagnose,reingest}_*.py
└── docs/SESSION-STARTER_DECK.md    # este archivo

/Users/berto/Documents/Claude/Projects/Presentación TFM/
├── Korio_pitch_deck_v4.pptx        # deck principal 15 slides
├── Korio_anexo_inversor_v1.pptx    # anexo 6 slides para Q&A
├── build_v4.js                     # generador deck
└── build_annex_investor.js         # generador anexo
```

## Smoke check producción

Antes de discutir lo que sea, verifica que VPS sigue vivo:

```bash
ssh korio-vps "systemctl is-active korio-api && docker ps --format '{{.Names}}' | grep -E 'ollama|n8n|falkordb' && curl -s https://korio.es/health"
```

Esperado: `active` + 3 contenedores + `{"status":"ok",...}`.

## Línea de tiempo restante (17 días hasta defensa)

| Día | Tarea |
|---|---|
| 22-25 jun | Maquetar slide 9 + anexo memoria capítulo evaluación |
| 25-28 jun | Banco Q&A 20 preguntas + decisión vídeo |
| 28 jun-1 jul | Resto memoria TFM ensamblar capítulos `docs/` |
| 2-5 jul | Si re-grabas vídeo, esta ventana |
| 5-7 jul | 2 ensayos cronometrados |
| 8 jul | Buffer + descanso. NO toques nada. |
| **9 jul** | **Defensa** |

## Voz para esta sesión

- Hablo claro, sin jergas si voy a decirlo en voz alta.
- Si propongo algo técnico denso, dame también la versión narrable.
- Honestidad sobre limitaciones siempre. El tribunal premia transparencia.
- Caveman mode si arranco con `/caveman`, prosa normal si no.
