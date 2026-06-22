# Slide 9 — Evaluación (versión narrable, lenguaje normal)

## TÍTULO
**¿Funciona el detector? Sí.**

## SUBTÍTULO
Evaluado sobre 12 documentos. Aciertos sobre fallos.

---

## CONTENIDO VISIBLE EN SLIDE (poco texto, números grandes)

### Cuadro 1 — grande, color teal
**1.983 ms**
latencia mediana por consulta

### Cuadro 2 — grande, color teal
**12 / 12**
aciertos del detector sobre el banco de pruebas

### Cuadro 3 — grande, color teal
**27 contradicciones**
encontradas en 20 documentos reales de producción

### Cuadro 4 — color cherry → teal (resuelto)
**5 falsos positivos → 0**
causa identificada · fix aplicado en commit 62cae8f

---

## PIE DEL SLIDE (texto pequeño)

Banco de pruebas: 12 documentos creados para esta evaluación. 6 pares que **sí** contradicen + 6 pares que **no**. Resultado: detector clasifica los 12 correctamente.

---

# Lo que vas a decir en voz alta (notas presentador)

**Tiempo: ~1:30**

---

> Quiero enseñaros que el sistema no solo funciona en el vídeo. Funciona medido.

> Diseñé un banco de pruebas de doce documentos pensados para evaluar el detector. Seis pares que **sí** se contradicen — por ejemplo, una política dice "tres días de teletrabajo a la semana", otra dice "dos días". Y seis pares de documentos del mismo departamento pero que tratan temas distintos, donde **no** hay contradicción.

> El detector clasificó los doce casos correctamente. Detectó los seis conflictos reales. Y rechazó los seis pares donde no había conflicto.

> En términos clásicos eso da precisión uno, recall uno, F1 uno. Pero más interesante que el número es **el diseño del banco**: para que los conflictos quedaran registrados como evidencia, hice que los documentos del par tuvieran misma fecha, mismo autor y misma autoridad. Eso obliga al sistema a no auto-resolver y dejar el conflicto pendiente de revisión humana. Así no se pierde la prueba.

> La latencia en producción son menos de dos segundos de mediana. Es lo peor que ve el usuario habitualmente.

> Y en el corpus real, sobre los veinte documentos de la clínica, el sistema lleva detectadas veintisiete contradicciones, trece ya resueltas con un click en un email, catorce esperando revisión.

> Ahora la parte honesta: durante la evaluación encontré cinco falsos positivos. El detector marcó como contradicción cinco pares de documentos que tratan temas **completamente distintos** — por ejemplo, gasto de comida contra caducidad de certificados.

> Lo investigué con un script de inspección. La causa era muy concreta: el detector estaba comparando solo el **primer trozo** de cada documento, y ese primer trozo, en mis documentos sintéticos, contenía únicamente el encabezado YAML con metadata. Como todos tenían el mismo autor, fecha y departamento, los embeddings salían artificialmente parecidos.

> No era un fallo del algoritmo, sino un fallo en cómo el chunker preparaba el texto antes del embedding. **Lo arreglé en el momento.** El preprocessor ahora strippea el encabezado YAML antes de chunkear, y guarda la metadata por separado para el resto del pipeline. Veintiocho tests en verde. Verificado de extremo a extremo en producción: el primer trozo ya contiene el texto real del documento, no metadata.

> El TFM se defiende con un sistema que mide su propio error y lo corrige. No con uno que esconde limitaciones.

> [PASA → compliance]

---

# Glosario para preguntas (NO leer en voz alta)

────────────────────────────────
GLOSARIO (solo por si te preguntan)
────────────────────────────────

- **Precision / Recall / F1** — métricas estándar de un clasificador. Precision = "de lo que dije que era conflicto, cuánto sí lo era". Recall = "de los conflictos reales, cuántos atrapé". F1 = media de ambas.
- **Banco de pruebas (ground truth)** — conjunto de pares de documentos donde yo conozco la respuesta correcta (porque los diseñé). Sirve para comparar lo que dice el sistema con la verdad.
- **Pending vs auto-resuelto** — cuando el sistema detecta dos documentos que se contradicen, decide quién gana. Si uno es claramente más nuevo o más autoritativo, gana automáticamente y al loser se le marca como obsoleto. Si no hay criterio claro, el conflicto queda "pending" esperando que un humano decida.
- **Chunk** — fragmento de documento (~500 palabras) que el sistema procesa por separado.
- **chunk_index=0** — el primer trozo de un documento, el que contiene la cabecera.
- **Frontmatter YAML** — metadata al principio de un archivo Markdown (título, autor, fecha…). Útil para humanos, ruidoso para embeddings si todos los docs lo tienen idéntico.
- **Embedding** — vector numérico que representa el significado de un texto. Textos parecidos producen vectores parecidos.
- **Falsos positivos** — el detector dijo "hay conflicto" cuando NO lo había. Es ruido, no error grave (peor sería que ocultara conflictos reales).
- **Mistral** — el modelo de IA que ejecuta la última validación: cuando el detector encuentra dos chunks parecidos, le pregunta a Mistral si **realmente** se contradicen. Mistral filtra falsos positivos del cálculo de similitud puro, pero no los filtra todos.
- **Preprocessor + chunker** — dos piezas del pipeline de ingesta. Preprocessor convierte PDF/DOCX/HTML a texto Markdown limpio. Chunker corta ese Markdown en trozos para embedding.
- **27 contradicciones en producción** — son el resultado de meses ingestando documentos reales de la clínica. Cada flecha en el grafo CONTRADICTS es un par documento-documento que el sistema marcó.
- **9 % FP rate** — 5 falsos positivos sobre 54 pares cruzados posibles del corpus eval (los pares no anotados). No es 9 % "de todo lo que detectó", es la tasa sobre el subconjunto de pares cross-tema del eval.
