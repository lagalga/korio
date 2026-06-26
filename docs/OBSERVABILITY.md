# Observabilidad y Evaluación — Korio

> Capítulo de la memoria TFM: *"Observabilidad, trazabilidad y evaluación de un
> sistema RAG en producción"*. Documenta la sesión 18 (26 jun 2026, v0.3.15).

---

## 1. Motivación

Un sistema RAG en producción falla de formas que un test unitario no captura:
una respuesta puede ser *rápida pero incorrecta*, *correcta pero cara*, o *lenta
sin que se sepa en qué paso*. Antes de la sesión 18, Korio tenía visibilidad
parcial:

| Capa | Mecanismo previo | Limitación |
|---|---|---|
| Audit trail ingesta | `pipeline_events` + webhook n8n | Solo ingesta, no el path de búsqueda |
| Errores workflows | `n8n_errors` + Slack | Solo n8n, no la API |
| Latencia | `scripts/benchmark.py` | Medición puntual y manual |
| Logs | `journalctl` | No estructurados, sin correlación |
| **Coste LLM** | — | **0% de visibilidad** |
| **Trazas distribuidas** | — | **inexistentes** |
| **Calidad de respuesta** | — | **inexistente** |

La sesión 18 cierra estos tres últimos huecos con **tres capas
complementarias**, cada una respondiendo a una pregunta distinta:

1. **LangSmith** — *¿el RAG responde bien y cuánto cuesta?* (capa semántica)
2. **OpenTelemetry + Jaeger** — *¿dónde se va la latencia?* (capa de infraestructura)
3. **RAG eval (LLM-as-judge)** — *¿la calidad mejora o empeora con cada cambio?*

La decisión de diseño transversal: **toda la instrumentación degrada a no-op**.
Si falta la dependencia o la variable de entorno está desactivada, el sistema
funciona idéntico. Esto permite tests, CI y el fallback Ollama offline sin
acoplarlos a servicios de observabilidad.

---

## 2. Capa semántica — LangSmith

### 2.1 Decisión: `@traceable` sin LangChain

Korio **no usa LangChain** (el chunking usa `RecursiveCharacterTextSplitter`
pero la orquestación RAG es código propio). LangSmith, sin embargo, ofrece el
decorador `@traceable` que funciona sobre cualquier función Python sin framework.
Esto permite instrumentar el pipeline existente con cambios mínimos y sin añadir
una dependencia de orquestación pesada.

### 2.2 Implementación

Módulo `src/observability.py` — wrapper fino y no-op-safe:

```python
def traceable(*args, **kwargs):
    """Decorador @traceable seguro: identidad si langsmith no disponible."""
    if _LANGSMITH_AVAILABLE:
        return _ls_traceable(*args, **kwargs)
    # ... decorador identidad (soporta @traceable y @traceable(...))

def record_llm_usage(prompt_tokens, completion_tokens, model):
    """Adjunta usage_metadata al run LLM actual → coste €/tokens."""
```

Spans instrumentados (árbol por query):

```
rag-search (chain)                    ← search.py
├── reformulate-query (chain)         ← llm_client.py  [solo si hay history]
├── ollama-embed (embedding)          ← embedder.py
├── graph-retrieval (retriever)       ← search.py      [solo si GRAPH_ENABLED]
├── mistral-generate (llm)  ──► tokens + coste €
└── ollama-generate (llm)   ──► tokens + coste €
```

El número de spans varía (6–8) según el camino: reformulación añade una llamada
Mistral; el grafo añade la query a FalkorDB. La traza refleja fielmente la
ruta real ejecutada.

### 2.3 Token y coste

`record_llm_usage()` extrae el consumo de cada backend y lo adjunta al run:
- Mistral: `usage.prompt_tokens` / `usage.completion_tokens`
- Ollama: `prompt_eval_count` / `eval_count`

LangSmith calcula el coste € multiplicando tokens × precio del modelo. Requiere
registrar el precio de `mistral-small-latest` en *Settings → Model Pricing*
(no viene precargado para modelos no-OpenAI).

### 2.4 Residencia de datos (GDPR)

LangSmith captura inputs/outputs completos, que pueden contener PII del contexto
RAG. Korio usa la **región UE** (`eu.api.smith.langchain.com`) para que las
trazas no salgan del territorio europeo — coherente con el capítulo de compliance
(ver `COMPLIANCE-AI-ACT-GDPR.md`). Además, la redacción PII pre-Mistral
(`KORIO_REDACT_MISTRAL=1`) ya minimiza el PII que llega al prompt trazado.

### 2.5 Configuración

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_sk_...                       # Service Key (no PAT)
LANGCHAIN_PROJECT=korio
LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com   # OBLIGATORIO si cuenta UE
```

---

## 3. Capa de infraestructura — OpenTelemetry + Jaeger

### 3.1 Decisión: self-hosted vs SaaS

Mientras LangSmith traza la semántica RAG en cloud, la capa HTTP se traza
**self-hosted** con Jaeger en el propio VPS. Razones:
- **GDPR total**: las trazas de infraestructura no salen del servidor.
- **Coste cero**: Jaeger all-in-one en Docker, sin SaaS.
- **Estándar abierto**: OTLP/OpenTelemetry evita lock-in; mañana se puede
  exportar a Grafana Tempo, Datadog, etc. sin tocar el código.

### 3.2 Implementación

Módulo `api/otel.py` — `setup_otel(app)` opt-in:

```python
FastAPIInstrumentor.instrument_app(app)   # span raíz por request
RequestsInstrumentor().instrument()       # spans hijos: Mistral/Ollama/Supabase
```

Korio usa `requests` (no `httpx`) para las llamadas salientes, por eso se
instrumenta `RequestsInstrumentor`. Cada `POST /search` genera un span raíz con
hijos por cada llamada HTTP saliente, visibles como *waterfall* en Jaeger.

Jaeger corre como contenedor (`docker-compose.yml`, servicio `jaeger`,
`jaegertracing/all-in-one` con `COLLECTOR_OTLP_ENABLED=true`). `korio-api` corre
en el host (systemd) y exporta a `127.0.0.1:4317` (OTLP gRPC). La UI
(`127.0.0.1:16686`) se accede vía túnel SSH — nunca expuesta a internet.

### 3.3 Configuración

```bash
KORIO_OTEL_ENABLED=1
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=korio-api
```

### 3.4 Limitación reconocida

Jaeger all-in-one almacena trazas **en memoria** (se pierden al reiniciar el
contenedor). Suficiente para debug y demo; para histórico persistente, Phase 9
migraría a Jaeger con backend Elasticsearch/Cassandra o a Grafana Tempo.

---

## 4. Capa de evaluación — RAG eval (LLM-as-judge)

### 4.1 Decisión: LLM-judge propio vs RAGAS

[RAGAS](https://github.com/explodinggradients/ragas) es el estándar de eval RAG,
pero arrastra `langchain` + un proveedor LLM (OpenAI por defecto) como
dependencias. Para Korio se optó por un **juez LLM propio** que reutiliza el
`llm_client` existente (Mistral, temp 0.0), sin dependencias nuevas. El concepto
es el mismo que RAGAS (métricas reference-free puntuadas por un LLM), adaptado al
stack.

### 4.2 Métricas

`scripts/rag_eval.py` ejecuta cada caso de `scripts/eval_set.json` contra
`search()` y puntúa:

| Métrica | Rango | Necesita | Qué mide |
|---|---|---|---|
| `answer_relevance` | 1-5 | — | ¿La respuesta aborda la pregunta? |
| `faithfulness` | 1-5 | — | ¿Se apoya en las fuentes sin inventar? |
| `correctness` | 1-5 | `expected_fact` | ¿Contiene el hecho esperado? |
| `retrieval_hit` | bool | `expected_doc` | ¿El doc esperado está en `sources`? |
| `latency_ms` | int | — | Latencia end-to-end |

Los casos `expected_fact: "NO_ANSWER"` validan que el RAG **declina** preguntas
fuera de dominio en lugar de alucinar (anti-alucinación).

### 4.3 Uso como red de seguridad

`benchmark.py` mide velocidad; `rag_eval.py` mide calidad. Flujo de trabajo:

```bash
python scripts/rag_eval.py -o eval_antes.json     # baseline
# ... cambio en prompt / threshold / reranking ...
python scripts/rag_eval.py -o eval_despues.json   # comparar medias
```

Si `avg_faithfulness` o `retrieval_hit_rate` bajan, el cambio empeoró la calidad
aunque la latencia mejore. Esto convierte decisiones antes intuitivas
(¿subo el threshold? ¿cambio el prompt?) en decisiones medibles.

---

## 5. Comparativa de las tres capas

| | LangSmith | OTel + Jaeger | rag_eval.py |
|---|---|---|---|
| **Capa** | semántica (RAG) | infraestructura (HTTP) | calidad (offline) |
| **Pregunta** | ¿responde bien? ¿coste? | ¿dónde la latencia? | ¿mejora con mi cambio? |
| **Spans/métricas** | embed, grafo, LLM, tokens, € | request, llamadas salientes, red | relevancia, fidelidad, correctness |
| **Hosting** | cloud UE (SaaS) | self-hosted (VPS) | local (script) |
| **Tiempo real** | sí | sí | no (on-demand) |
| **Overhead** | mínimo (background) | mínimo (background) | n/a (offline) |

Juntas demuestran que Korio no es un prototipo sino un sistema **observable y
evaluable**: trazabilidad semántica + análisis de latencia + evaluación
cuantitativa de calidad.

---

## 6. Troubleshooting (registro real de la sesión 18)

El despliegue de LangSmith encadenó cuatro causas — útil como caso de estudio
de depuración de observabilidad:

1. **Vars ausentes / proceso sin reiniciar** → proyecto vacío. El daemon no
   recogía el `.env` editado hasta `systemctl restart`.
2. **Endpoint US con cuenta UE** → `403 Forbidden` en `/runs/multipart`. El
   endpoint por defecto (`api.smith.langchain.com`) rechaza el ingest de una key
   UE. Fix: `LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com`.
3. **API key malformada** → `403` persistente. La key tenía un carácter sobrante
   (`.`) al final. `Client().info` devolvía OK porque ese endpoint es metadata
   sin auth — nunca validó la key de verdad. Fix: regenerar Service Key limpia.
4. **Código instrumentado nunca desplegado** ← *causa raíz real*. Los decoradores
   `@traceable` vivían sin commitear en el worktree local; el VPS corría la
   versión vieja. `grep @traceable` en el VPS lo habría detectado en el minuto
   uno.

**Aprendizaje**: ante "la observabilidad no aparece", verificar de fuera hacia
dentro en este orden: (1) ¿el código instrumentado está realmente desplegado?
(2) ¿el proceso se reinició tras editar la config? (3) ¿auth/endpoint correctos
para la región? (4) ¿flush del exportador antes de que el proceso muera? El
modo síncrono (`LANGCHAIN_CALLBACKS_BACKGROUND=false`) hace visibles los errores
de ingest que el modo background traga en silencio.

---

## 7. Trabajo futuro (Phase 9+)

- **Model Pricing** de `mistral-small-latest` en LangSmith → poblar columna Cost.
- **Jaeger persistente** (Elasticsearch/Tempo) para histórico más allá de reinicios.
- **Métricas agregadas** (Prometheus + Grafana): tasa de errores, p50/p95 por
  endpoint, tokens/€ por día, % queries con grafo, ratio `has_context`.
- **Eval continua en CI**: correr `rag_eval.py` en cada PR y bloquear si la
  calidad media cae bajo un umbral (gate de regresión de calidad).
- **Dataset LangSmith**: subir el eval set como dataset versionado y usar
  Experiments para comparar versiones del prompt con la UI de LangSmith.

---

*Sesión 18 (26 jun 2026, v0.3.15). Archivos: `src/observability.py`,
`api/otel.py`, decoradores en `src/{search,llm_client,embedder}.py`,
`scripts/rag_eval.py`, `scripts/eval_set.json`, servicio `jaeger` en
`docker-compose.yml`.*
