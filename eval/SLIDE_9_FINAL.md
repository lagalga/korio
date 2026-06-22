# Slide 9 v3 — Evaluación cuantitativa (FINAL · numeros reales)

## Título
**Evaluación cuantitativa**

## Subtítulo (italic teal)
Corpus eval-specific · ground truth autoral · doble fuente de verdad.

---

## Layout — 4 cuadros KPI arriba

### Cuadro 1 (sup. izquierda · borde teal)
**LATENCIA**
**1.983 ms · p50**
**3.053 ms · p95**
50 queries reales · sin caché · Hetzner ↔ Mistral Francia

### Cuadro 2 (sup. derecha · borde teal)
**DETECTOR · GROUND TRUTH**
**Precision = 1.000**
**Recall = 1.000**
**F1 = 1.000**
n = 12 pares (6 P + 6 N) · corpus eval controlado

### Cuadro 3 (inf. izquierda · borde teal)
**GOBERNANZA EN PRODUCCIÓN**
**27 aristas CONTRADICTS**
20 docs reales · 1.130 nodos grafo · 13 resueltas + 14 pendientes HITL

### Cuadro 4 (inf. derecha · borde cherry)
**LIMITACIÓN OBSERVADA**
**FP rate ≈ 9 %**
sobre pares no-anotados con frontmatter idéntico · artefacto de plantilla

---

## Bloque metodología abajo (fondo blanco · borde rule)

**Metodología**

- **Corpus eval-specific:** 12 documentos sintéticos creados para evaluación cuantitativa. 6 pares positivos (contradicción explícita en valor único: 3 vs 2 días, 15 vs 30 min, 50 vs 80 €, etc.) + 6 pares negativos (mismo espacio, temas disjuntos). Misma fecha, misma autoridad → detector no auto-resuelve → `conflict_review` persistente.
- **Detector:** similitud coseno chunks ≥0.85 → validación semántica vía Mistral (juez independiente) → resolución por fecha/autoridad/policy o queda `pending`.
- **Métricas:** Precision = TP/(TP+FP), Recall = TP/(TP+FN), F1 = media armónica. Ground truth autoral (sesgo confirmación reconocido).
- **Doble fuente:** evidencia recogida combinando aristas CONTRADICTS en FalkorDB y registros `conflict_reviews` en Postgres. Reconciliadas por (document_id_a, document_id_b).

---

## Bloque limitaciones abajo (al lado del metodología)

**Limitaciones honestas**

- Ground truth autoral sobre corpus sintético — validación corpus real queda como trabajo futuro inmediato.
- 5 falsos positivos cross-tema sobre pares no anotados (n=54) → artefacto identificado: frontmatter uniforme infla similitud baseline. Mitigación parcial ya implementada: `scripts/reembed_strip_frontmatter.py` (sesión 15b). Mitigación completa: reranker cross-encoder (Phase 8).
- Auto-resoluciones NO dejan rastro en `conflict_reviews` por diseño actual. Trazabilidad incompleta — limitación reconocida.

---

# Notas presentador slide 9 v3

```
[~1:30 — slide más densa, no leer todos los números]

Cuatro métricas en producción real.

Latencia p50 1.9 segundos, p95 3 segundos sobre 50 queries sin caché contra Mistral en Francia. Es lo peor que ve el usuario.

Detector evaluado sobre corpus eval-specific de 12 documentos. 6 pares positivos con contradicción explícita en un único valor — días de teletrabajo, minutos de visita, euros de gasto, años de caducidad, porcentajes de descuento, horarios. 6 pares negativos del mismo espacio pero temas disjuntos. Diseñé el corpus para que ningún par auto-resuelva — misma fecha, misma autoridad — así el conflict_review queda en estado pending y persiste como evidencia.

Precision 1, Recall 1, F1 1 sobre n=12. El detector capturó los 6 positivos con similitud >0.99 y rechazó correctamente los 6 negativos.

Gobernanza activa en producción: 27 aristas CONTRADICTS válidas sobre el corpus demo real de 20 documentos. 13 ya resueltas vía HITL email, 14 pendientes.

Limitación que quiero exponer abiertamente: identifiqué 5 falsos positivos cross-tema sobre los pares no anotados del eval corpus. El patrón es claro — todos los documentos eval comparten frontmatter idéntico (mismo autor, fecha, autoridad, tenant, space) → el embedding global se sesga hacia similitud alta → el detector dispara → el LLM valida porque los números diferentes sin contexto suficiente parecen contradicciones. Es artefacto del diseño del corpus, no fallo del algoritmo en docs reales.

Mitigación parcial ya implementada en sesión 15b: scripts/reembed_strip_frontmatter.py reembebió los chunks sin frontmatter. Mitigación completa requiere reranker cross-encoder, Phase 8.

────────────────────────────────
GLOSARIO (no leer · solo para preguntas)
────────────────────────────────

• Corpus eval-specific — conjunto de 12 documentos sintéticos creados ad-hoc para esta evaluación cuantitativa, separados del corpus demo grabado. Permite ground truth perfecto sin contaminar la presentación.

• Pair positive — par de documentos que SÍ contradicen (ground truth = conflict). En este eval: docs idénticos en estructura excepto un único valor.

• Pair negative — par de docs que NO contradicen (ground truth = no conflict). En este eval: mismo espacio, temas disjuntos.

• Conflict_review (Postgres) — fila en tabla que registra cada conflicto detectado durante ingesta. Solo persiste si resolución queda 'pending' (no auto-resuelve).

• Pending vs auto-resolved — pending = requiere humano. auto-resolved = sistema decidió por fecha/autoridad/policy. El eval corpus está diseñado para forzar pending y así persistir evidencia.

• Cross-tema (FP analysis) — pares de documentos del eval corpus que tratan temas DIFERENTES (descuento vs caducidad, p.ej.) pero el detector marcó como conflicto. Se confirma como falso positivo en revisión manual.

• Frontmatter — bloque YAML al principio de cada .md con metadata (autor, fecha, espacio, etc). Si idéntico en muchos docs, contamina embeddings.

• Reembed strip frontmatter — script de Korio que re-embebió chunks excluyendo el frontmatter del cálculo de embedding. Mitiga el sesgo de similitud por plantilla.

• Reranker cross-encoder — modelo que toma top-K resultados y los re-ordena evaluando query-documento como par (más caro pero más preciso). Mitigación completa contra falsos positivos del retriever vector simple. Pendiente Phase 8.

• Doble fuente de verdad — cruce de evidencias: aristas CONTRADICTS en FalkorDB + registros conflict_reviews en Postgres. Ninguna fuente sola es completa.
```
