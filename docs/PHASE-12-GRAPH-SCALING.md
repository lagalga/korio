# Phase 12 · Escalado del grafo de conocimiento

**Estado:** diseño post-defensa. No bloqueante para el TFM.
**Ventana estimada:** ~12 meses tras Phase 11 (motor embeddings), condicionada a
carga real de clientes SaaS. Se dispara **por métrica, no por calendario**:
cuando `p95(enrich_with_graph) > 200ms` sostenido o `graph_claims` por tenant
supere ~10M filas.

---

## 1. Contexto y pregunta original

Durante la defensa del TFM (14 jul 2026) surgió la pregunta:

> *"¿Cómo escalaría el grafo frente a miles o millones de chunks? ¿Sería
> demasiado lento? ¿La solución es sharding por tenant, balancear a grafo solo
> cuando el vector vaya flojo, etc.?"*

Este documento formaliza la respuesta y la convierte en un roadmap ejecutable.

---

## 2. Tesis: el grafo **no** escala con chunks

Confusión frecuente: se piensa que 1M chunks → 1M nodos de grafo. Falso.

- El grafo Korio almacena **claims extraídos** (`subject, predicate, value`),
  no chunks.
- Ratio empírico observado en el corpus TFM: **1 chunk ≈ 2-5 claims**.
- Extrapolación:
  - 100k chunks → ~300k claims
  - 1M chunks → ~3-5M claims
  - 10M chunks → ~30-50M claims

Postgres con índices B-tree + GIN maneja decenas de millones de filas en
tablas indexadas sin degradación perceptible. El bottleneck real no es el
volumen total sino la **latencia de `enrich_with_graph()` por query**.

**Métrica de referencia (14 jul 2026):**
- p95 del enriquecimiento por grafo ≈ 40ms con ~5k claims (corpus TFM).
- Extrapolación lineal a 100k claims → ~200ms.
- Con particionado por tenant + índices compuestos → sub-lineal.

---

## 3. Router adaptativo (ya activo, no es Phase 12)

Korio no lanza el grafo en cada query. Patrón ya en producción:

1. **Vector-first** (barato, ~50ms).
2. **Grafo se dispara** solo si:
   - `top_k` vector < umbral de similitud (0.5), **o**
   - query factual detectada (patrones: quién / cuándo / cuánto / cuántos), **o**
   - usuario pide trazabilidad estructurada explícita.
3. Grafo **NO** en cada query → coste amortizado por naturaleza.

Phase 12 refuerza este router con métricas Prometheus + auto-tuning del umbral.

---

## 4. Roadmap incremental (orden estricto por coste/beneficio)

### 4.1 · Nivel 0 — Optimización Postgres (gratis, primeros ~10M claims)

- **Índices compuestos** `(tenant_id, subject)`, `(tenant_id, predicate)`.
- **GIN** en `predicate` y `value` (búsqueda por patrones parciales).
- **PARTITION BY LIST (tenant_id)** en `graph_claims` cuando cualquier tenant
  supere ~10M claims individualmente.
- **VACUUM ANALYZE** en cron semanal.
- Coste: 0€. Cambio: `ALTER TABLE` + migración.

### 4.2 · Nivel 1 — Cache de sub-grafos calientes

- Redis con TTL 1h para sub-grafos por `(tenant_id, subject)` de los N sujetos
  más consultados por tenant.
- Invalidación event-driven: al insertar/actualizar un claim de un subject
  cacheado, publish en `pipeline_events` → worker limpia la key.
- Coste: ~€5/mes Redis. Impacto: p95 grafo → <10ms en queries repetidas.

### 4.3 · Nivel 2 — Materialized views para agregaciones frecuentes

- Vistas materializadas por tenant para queries agregadas recurrentes (top
  entities, claim counts, disputed ratio).
- Refresh incremental disparado por `pipeline_events`.
- Coste: 0€. Impacto: dashboards y `/admin/errors` latencia <50ms.

### 4.4 · Nivel 3 — Sharding físico multi-tenant

Tres estrategias por escalón de carga:

| Escalón | Estrategia | Trigger |
|---|---|---|
| Bajo (<100 tenants) | RLS lógico (ya activo) | — |
| Medio (100-1000 tenants) | `PARTITION BY LIST (tenant_id)` físico | Cualquier tenant >10M claims |
| Alto (enterprise) | **DB dedicada por tenant** (SLA separado) | Cliente pide aislamiento contractual |

RLS **no se elimina** en ningún caso — sharding físico es capa adicional, no
sustituto.

### 4.5 · Nivel 4 — Migrar a motor de grafo nativo (Kùzu / Neo4j)

**Solo si** después de los niveles 0-3:
- `p95(enrich_with_graph) > 200ms` sostenido durante 2 semanas, **o**
- queries multi-hop (>3 saltos) se vuelven caso de uso real (hoy no lo son).

Candidatos:

| Motor | Licencia | Fortaleza | Debilidad |
|---|---|---|---|
| **Kùzu** | MIT | Embebido, Cypher, columnar OLAP-friendly | Ecosistema joven |
| **Neo4j Community** | GPLv3 | Cypher maduro, tooling | Licencia contamina, HA solo Enterprise |
| **Apache AGE** (extensión Postgres) | Apache 2.0 | Cypher dentro de Postgres, no migra datos | Rendimiento inferior a nativos |

**Recomendación provisional:** Apache AGE primero (cero migración de datos),
Kùzu si AGE también satura.

---

## 5. Anti-patrones a evitar

- ❌ **No migrar a Neo4j "por si acaso"** antes de agotar índices Postgres.
- ❌ **No hacer grafo en cada query** — mata latencia sin ganancia.
- ❌ **No sharding físico por tenant** hasta que un tenant justifique el coste
  operativo (backups separados, monitoring separado, migrations coordinadas).
- ❌ **No cachear sub-grafos sin invalidación event-driven** — stale data en
  grafo contamina governance activa.

---

## 6. Métricas de decisión

Panel Grafana dedicado (Phase 12.1):

- `korio_graph_enrich_latency_seconds{quantile="0.95"}` por tenant.
- `korio_graph_claims_total{tenant_id}` — gauge.
- `korio_graph_cache_hit_ratio` — histograma.
- `korio_router_graph_dispatched_ratio` — % queries que activan grafo.

Umbrales de alerta:

| Métrica | Warn | Critical | Acción |
|---|---|---|---|
| p95 enrich | >150ms | >200ms | Subir nivel (0→1→2→3→4) |
| Claims por tenant | >5M | >10M | Activar partitioning físico |
| Cache hit ratio | <60% | <40% | Revisar TTL / tamaño Redis |
| Router dispatch | >70% | >85% | Revisar umbral similitud vector |

---

## 7. Coste estimado por escalón

| Nivel | Infra extra | Ingeniería |
|---|---|---|
| 0 (índices) | 0€ | 1-2 días |
| 1 (Redis cache) | ~€5/mes | 3-5 días |
| 2 (materialized views) | 0€ | 2-3 días |
| 3 (partitioning físico) | 0€ (mismo Postgres) | 1 semana |
| 3 bis (DB dedicada enterprise) | €50-200/mes por tenant | 2 semanas + billing separado |
| 4 (motor nativo AGE/Kùzu) | 0-€100/mes | 3-4 semanas (migración datos) |

---

## 8. Relación con otras phases

- **Phase 8-9 (SaaS):** el volumen de tenants dispara Phase 12. Sin clientes
  reales, este roadmap queda en estudio.
- **Phase 11 (embeddings):** BGE-M3 con sparse nativo reduce dependencia del
  grafo para queries de recall — impacta el ratio router dispatch.
- **Bloques transversales:** el bias audit (AI Act Art. 15) requiere queries
  agregadas sobre el grafo — beneficia de nivel 2 (materialized views).

---

## 9. Frase-resumen para stakeholders

> *"El grafo no crece con el número de chunks, sino con los hechos extraídos.
> El sharding lógico ya está activo vía RLS desde Phase 2. El sharding físico
> y la migración a un motor de grafo nativo son incrementales, se disparan
> cuando las métricas de latencia lo pidan, no antes."*
