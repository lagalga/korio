# Embeddings en Korio — dossier para defensa TFM

> Documento de referencia para responder preguntas del tribunal sobre la elección
> del modelo de embeddings, sus fortalezas, debilidades y roadmap de sustitución
> post-MVP en un escenario SaaS de producción.

---

## 1. Qué usa Korio hoy y por qué

**Modelo actual**: `nomic-embed-text v1.5` servido por Ollama en el VPS Hetzner CPX32.

**Rol en el pipeline**: convertir cada chunk de texto (producido por LangChain
`RecursiveCharacterTextSplitter`) en un vector de **768 dimensiones** que se
persiste en pgvector (Supabase) y se compara por similitud coseno en cada query.

**Independencia respecto al LLM generador**: el embedder (nomic) y el LLM de
generación (Mistral cloud + Ollama fallback) son piezas desacopladas de
proveedores distintos. Nomic AI es una empresa independiente; Ollama es solo el
runtime local que sirve ambos modelos (no implica parentesco). Cambiar el LLM no
obliga a cambiar el embedder ni viceversa.

---

## 2. Fortalezas de nomic-embed-text

1. **Open source real + self-hosted**. Licencia Apache 2.0, pesos descargables.
   Los chunks (que pueden contener datos sensibles incluso tras Presidio) nunca
   salen del VPS Frankfurt. Alineado con GDPR (Art. 44-49, transferencias
   internacionales) y con el discurso de soberanía de Korio.
2. **Coste marginal cero**. Los 74 chunks y 925 claims del grafo se han embedido
   sin coste. OpenAI `text-embedding-3-small` cuesta $0.02 / 1M tokens, barato
   pero acumulativo al re-embebir o al escalar tenants.
3. **Multilingüe con español decente**. Entrenado con corpus multilingües;
   funciona sobre los tres dominios del proyecto (RRHH, médico, legal).
4. **Latencia local predecible**. ~0.8s por query embedding en CPU CPX32. Sin
   red, sin rate limits, sin caídas de API externas (contraste con el retry
   exponencial que tuvimos que añadir para Mistral 429).
5. **Dimensión moderada (768)**. Sweet spot entre expresividad y coste de
   almacenamiento/cómputo. Soporta Matryoshka representation learning (truncable
   a 512/256 si fuera necesario comprimir).
6. **MTEB competitivo**. En el benchmark estándar de retrieval está al nivel
   de modelos cerrados de su clase.

---

## 3. Debilidades reconocidas

1. **Calidad inferior al SOTA comercial**. `voyage-3-large`,
   `text-embedding-3-large`, `Cohere embed-v3` superan a nomic en retrieval
   fino, especialmente en queries ambiguas o multi-hop.
   → Evidencia empírica en Korio: queries vagas ("¿cuántas horas hay que
   trabajar?") ranqueaban mal (sesión 15b). Se compensó re-embebiendo sin
   frontmatter YAML + añadiendo Reciprocal Rank Fusion vector + grafo.
2. **No especializado en español**. Es multilingüe generalista, no fine-tuned
   para castellano administrativo/jurídico.
3. **Ollama en CPU limita el throughput**. 0.8s por embedding es aceptable para
   el MVP, insuficiente para centenares de queries/segundo.
4. **Sin reranker dedicado**. Cohere y Voyage venden `rerank-3` como componente
   separado; con nomic el reranking es código propio (score léxico ponderado +
   RRF con grafo).
5. **Context window ~8k tokens**. Suficiente para chunks de 500 tokens,
   insuficiente para long-context retrieval estilo ColBERT.
6. **Sin prompts asimétricos nativos**. Modelos modernos (e5, bge-m3)
   distinguen `"query: ..."` vs `"passage: ..."` mejorando retrieval ~5-8%.

---

## 4. Justificación defensiva (párrafo para memoria y defensa oral)

> Se eligió `nomic-embed-text` frente a alternativas comerciales (OpenAI
> text-embedding-3, Voyage AI, Cohere) por tres razones alineadas con el caso
> de negocio de Korio: (1) cumplimiento GDPR sin transferencias internacionales,
> al procesarse localmente en el VPS Frankfurt; (2) coste marginal cero,
> compatible con un MVP de pyme; (3) latencia predecible sin dependencia de APIs
> externas. Se reconoce una pérdida de calidad de retrieval frente al SOTA
> cerrado, que se compensa parcialmente mediante RAG híbrido vector + grafo
> (FalkorDB), reranking semántico con Reciprocal Rank Fusion, y reformulación
> multi-turn de la query vía Mistral.

---

## 5. Preguntas anticipadas del tribunal y respuestas

### P1. ¿Por qué no usar OpenAI / Cohere / Voyage si son mejores?
Cumplimiento normativo y coste. Enviar chunks con posibles datos sensibles a un
proveedor extra-UE exige DPA formal + evaluación de impacto (RGPD Art. 35 +
AI Act Art. 10) — desproporcionado para un MVP y contradice el discurso comercial
de Korio ("tu conocimiento no sale de tu VPS"). El coste, aunque bajo unitariamente,
escala mal con re-ingestas y crecimiento de tenants.

### P2. ¿Qué pierdes por no usar el SOTA?
Retrieval fino en queries ambiguas. Se cuantificó: la query "¿cuántas horas
hay que trabajar?" fallaba con nomic hasta que se re-embedieron chunks sin
frontmatter YAML y se activó el RRF con el grafo (sesión 15b, v0.3.11). Un
embedder superior probablemente habría resuelto la query sin esa gimnasia.

### P3. ¿Es nomic de Mistral?
No. Nomic AI es una empresa independiente de Nueva York especializada en
embeddings open source y visualización de espacios latentes. Comparte runtime
(Ollama) con el fallback local de Mistral, pero son proveedores distintos.

### P4. ¿Cambiar el LLM te obliga a cambiar el embedder?
No. Son piezas desacopladas. El LLM (Mistral hoy) recibe el contexto ya
recuperado y produce la respuesta final. Nomic vive en la fase de ingesta y en
el embedding de la query. Se puede cambiar cualquiera de los dos sin tocar el
otro.

### P5. ¿Cambiar el embedder obliga a re-embebir todo?
Sí, siempre. Aunque el nuevo modelo produzca vectores de la misma dimensión
(768), los vectores viven en espacios geométricos distintos: la dirección que
nomic asigna a *vacaciones* no coincide con la que le asigna otro embedder.
Mezclar vectores de modelos distintos en la misma tabla produce similitudes
coseno sin sentido. La migración es un corte total y limpio.

### P6. ¿Y si cambias el número de dimensiones?
Migración SQL trivial (`ALTER TABLE embeddings ALTER COLUMN embedding TYPE
vector(N)`), pero el coste real está en re-embebir chunks (74 hoy, potencialmente
miles en producción) y claims del grafo (925 hoy). En Korio el schema declara
`vector(768)` y hay un assert en `Embedder._check_connection` que aborta el
arranque si Ollama devuelve una dimensión distinta (defensa añadida en s13a).

---

## 6. Roadmap de sustitución post-MVP (SaaS Phase 11+)

Restricciones asumidas: **soberanía** (self-host), **coste asumible** (~€200/mes
adicional máximo), **latencia mejor que 0.8s CPU**, escalabilidad a decenas de
tenants.

### 6.1 Comparativa de candidatos

| Criterio | nomic (actual) | multilingual-e5-large-instruct | BGE-M3 | Jina embeddings v3 |
|---|---|---|---|---|
| Dimensión | 768 | 1024 | 1024 (dense) + sparse + multi-vector | 1024 (Matryoshka) |
| Licencia | Apache 2.0 | MIT | MIT | CC-BY-NC 4.0 ⚠️ (comercial = pago) |
| Origen | Nomic AI (EEUU) | Microsoft Research | BAAI (China) | Jina AI (🇩🇪 Berlín) |
| Soberanía self-host | ✅ | ✅ | ✅ | ⚠️ requiere licencia comercial |
| Multilingüe español | Bueno | Muy bueno (MTEB top-tier) | Muy bueno (100+ idiomas) | Muy bueno |
| Context window | ~2k | 512 tok efectivo | 8192 tok | 8192 tok |
| Prompts asimétricos | ❌ | ✅ (query/passage) | ✅ | ✅ |
| Retrieval híbrido nativo | ❌ | ❌ solo dense | ✅ dense + sparse + ColBERT | Solo dense |
| Latencia GPU (T4/A10) | ~800ms CPU | ~50ms | 30-80ms | 30-80ms |
| Latencia CPU decente | 800ms | 1-1.5s | ~300ms | GPU obligada |
| Madurez producción | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Cambio en pipeline Korio | — | Trivial (añadir prefijos) | Medio (aprovechar sparse) | Bajo |

### 6.2 Camino recomendado

**Fase corta (3 meses post-MVP)** → migrar a `multilingual-e5-large-instruct`:
- Cambio mínimo en código: añadir prefijos `"query: "` / `"passage: "` en
  `src/embedder.py`.
- Upgrade real de calidad de retrieval en español.
- Latencia ~50ms en GPU modesta; ~1s en CPU si aún no hay GPU.
- Mantiene la arquitectura RRF + grafo intacta.
- Retira la deuda técnica de nomic sin reescribir el RAG.
- Migración: 1024d requiere `ALTER TABLE` + re-embed total (chunks + claims).

**Fase larga (6-12 meses, con clientes de pago)** → salto a `BGE-M3`:
- Aprovecha la migración para refactorizar el retrieval con **dense + sparse
  nativo** en el mismo modelo.
- Permite retirar parte del RRF léxico manual (el sparse output de bge-m3 ya
  cubre ese rol léxico); el grafo sigue como tercer canal.
- Requiere GPU dedicada (~€185/mes en Hetzner GEX44, RTX 4000 Ada 20GB) o
  Runpod por horas.
- Context window de 8k tokens facilita ingesta de threads Slack/Teams largos
  (Phase 10).

### 6.3 Modelos descartados y por qué

- **Voyage-3 / OpenAI text-embedding-3 / Cohere embed-v3**: contradicen el
  discurso de soberanía y transferencia internacional. Riesgo regulatorio
  AI Act + RGPD que choca con el propio pitch de venta.
- **Qwen embeddings / BAAI hosted vía API**: mismos problemas que arriba.
  Los pesos de BAAI (BGE-M3) sí son válidos self-host.
- **stella / gte-large**: SOTA en MTEB inglés pero soporte español débil.
- **Jina embeddings v3 (self-host)**: técnicamente excelente y origen europeo
  (encaja con narrativa Korio), pero licencia CC-BY-NC obliga a contrato
  comercial de pago para uso SaaS. Evaluable si el pricing es razonable.

### 6.4 Coste estimado del salto a producción

| Concepto | Coste mensual |
|---|---|
| VPS actual CPX32 (FastAPI + Mistral fallback + n8n) | €17.53 |
| Hetzner GEX44 GPU dedicada (RTX 4000 Ada 20GB) para embedder + Ollama | ~€185 |
| Supabase Pro | ya presupuestado |
| **Δ total mensual sobre el MVP** | **~€185** |

Punto de equilibrio: **5-6 clientes a €40/mes** cubren el upgrade. Asumible.

---

## 7. Aprendizaje para el TFM (capítulo de reflexión)

La elección del embedder es una decisión con **alto coste de reversión**: cada
cambio obliga a re-embebir el corpus completo y a validar de nuevo los
umbrales de similitud (búsqueda 0.35, conflict 0.80, banner disputed 0.60,
CONTRADICTS 0.85, silent_conflict query-time 0.80). Por eso el CLAUDE.md
declara nomic-embed-text como **inmutable durante el TFM** — no por convicción
técnica de que sea el mejor, sino por gestión de riesgo del alcance del
proyecto. La migración se planifica como Phase 11 explícita, con presupuesto
y calendario dedicados.

---

*Documento generado en sesión 17 (junio-julio 2026) como material de apoyo para
la defensa TFM. Fuente: conversación técnica sobre embeddings alternativos,
consolidando decisiones de sesiones anteriores (13a, 15b) y proyección SaaS
post-defensa.*
