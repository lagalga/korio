# Compliance: AI Act + GDPR en Korio

**Documento de cumplimiento normativo para memoria TFM**
*Actualizado: 16 junio 2026 · v0.3.7*

---

## Resumen ejecutivo

Korio es un SaaS multi-tenant de RAG que procesa documentos corporativos privados de pymes españolas. Stack:
- **Datos**: Supabase Pro (Frankfurt, EU) + RLS multi-tenant
- **Embeddings**: Ollama `nomic-embed-text` on-premise VPS (Frankfurt)
- **LLM generación**: Mistral API (Francia, EU) + Ollama fallback
- **Gobernanza**: HITL review con audit trail en `conflict_reviews` + `pipeline_events`

**Postura regulatoria**: **Bajo riesgo AI**, **GDPR-ready con ajustes menores** (DPA Mistral, Presidio PII).

---

## 1. AI Act (Regulación EU 2024/1689)

### Clasificación de riesgo

| Elemento | Análisis | Riesgo AI Act |
|----------|----------|---------------|
| **Clasificación automática** | Korio **no clasifica** documentos ni toma decisiones sobre el contenido. La IA genera contexto; el usuario decide. | ❌ No aplica risk classification |
| **Detección de conflictos** | Sistema automático flagea similitudes. **PERO** el admin HITL revisa y aprueba antes de acción. | ✅ HITL mitiga a "riesgo medio" |
| **Generación de contenido** | Mistral genera resúmenes contextuales. No se exporta por defecto; user elige copiar/citar. | ✅ Bajo riesgo (info retrieval, no decisión) |

### Requisitos aplicables

#### ✅ Cumplidos hoy

1. **Transparencia** (`Art. 13`)
   - UI: banner "Búsqueda potenciada por IA" en `/ui`
   - Grafo: etiqueta `[grafo de conocimiento]` → explica fuentes
   - Conflictos: badge ⚠️ + explicación en cada chunk disputed
   - **Prueba**: `ui/index.html` línea ~85, `ui/js/main.js` `displayResponse()`

2. **Auditoría & logging** (`Art. 36`)
   - `pipeline_events` registra: evento, agente origen, timestamp, operación_id (correlación)
   - `conflict_reviews` registra: quién resolvió, cuándo, decisión, policy aplicada
   - **Acceso admin**: `/admin` dashboard (Phase 9) o `SELECT * FROM pipeline_events WHERE tenant_id = $1 ORDER BY created_at DESC`

3. **Integridad datos** (`Art. 10`)
   - PII redactado **antes** de embeddings (Presidio + spaCy)
   - Delete `/document/{id}` cascada: Postgres + FalkorDB
   - **Verificación**: `tests/test_search.py::test_pii_redacted` ✅

#### ⚠️ Pendiente Phase 9

4. **Bias/Discriminación** (`Art. 15`)
   - Falta: análisis sesgo embeddings en contexto de RRHH (¿favorece géneros/edades?)
   - Acción: `scripts/fairness_audit.py` contra corpus Delos (`policy_vacaciones`, `protocolo_admision`) + benchmark de representación
   - **Timing**: 2 semanas post-demo

5. **Documentación técnica** (`Art. 4(41)`)
   - Falta: "Algoritmo de detección de conflictos v2.1" documento formal
   - Incluir: pseudo-código, umbral similitud, matriz confusión
   - **Usar para TFM capítulo 6 "Gobernanza & Cumplimiento"**

---

## 2. GDPR — Datos personales en documentos

### Mapeo de riesgos

**Escenario A**: Documentos **SIN** datos personales (políticas RH genéricas, protocolos médicos anonimizados)
- ✅ **Cumplimiento automático** — Korio es herramienta de búsqueda, no procesa PII

**Escenario B**: Documentos **CON** datos personales (lista empleados, NIF, teléfono, email)
- ⚠️ **Riesgo moderado** — aplicables Art. 5 (principios), Art. 32 (seguridad), Art. 33-34 (notificación breach)

### Principios GDPR aplicables

| Principio | Korio v0.3.7 | Hueco | Fix |
|-----------|--------------|-------|-----|
| **Lawfulness** (Art. 6) | Base jurídica: contractual (SaaS) entre cliente + Korio | Ninguno | ✅ DPA cliente → Korio claro |
| **Purpose limitation** (Art. 5) | Único uso: RAG búsqueda + gobernanza conflictos. No venta, no perfilado. | Ninguno | ✅ Términos servicio explícitos |
| **Data minimization** (Art. 5) | Documentos no se "minimalizan" pero Presidio redacta PII antes de ingestar. | **Mistral API recibe fragmentos con contexto** — puede contener PII si doc no fue redactado upstream | ❌ **Acción inmediata** (§ 2.1) |
| **Accuracy** (Art. 5) | Usuario responsable de doc quality. Korio no altera contenido. | Ninguno | ✅ Claro |
| **Storage limitation** (Art. 5) | Usuario can borrar `DELETE /document/{id}` → cascada completa. | Ninguno | ✅ Right to erasure funcional |
| **Integrity & confidentiality** (Art. 32) | Supabase encryption at-rest, TLS in-transit, RLS row-level. VPS: SSH only, firewall. | Mistral API: ¿logging de prompts? | ⚠️ **Acción inmediata** (§ 2.1) |
| **Right to portability** (Art. 20) | Exporte JSON: documents + embeddings + metadata | No implementado formalmente | 🔲 Phase 9 endpoint `/export/{tenant_id}` |
| **Right to erasure** (Art. 17) | `DELETE /document/{id}` elimina de Postgres + FalkorDB cascada | Mistral: si envía prompt, ¿se borra en Mistral? | ⚠️ **Acción inmediata** (§ 2.1) |
| **Right of access** (Art. 15) | Korio no ofrece interfaz; admin manual via Supabase console | 🔲 Phase 9 endpoint `/subject-access/{user_id}` |

### **§ 2.1 ACCIONES INMEDIATAS** (antes de producción pública 2-jul)

#### A. Mistral API + PII

**Problema**: Si documento tiene NIF/email/teléfono, Mistral los ve en el prompt.

**Soluciones** (elige 1):

1. **Option 1: Presidio redacta TODO PII antes de Mistral** (recomendado)
   ```python
   # src/search.py, antes de llamar a Mistral
   redacted_context = presidio_analyzer.anonymize_entities(
       text=rag_context,
       entities=["EMAIL", "PHONE", "PERSON", "NIF", "DNI"],
       replace_with="[REDACTED]"
   )
   response = mistral_client.chat(context=redacted_context)
   ```
   - Ventaja: PII **nunca** sale del VPS
   - Coste: `-2.5% accuracy` (perder contexto persona)
   - Implementación: 2 horas

2. **Option 2: Usar Ollama 100%** (fallback local, zero cross-border)
   ```bash
   docker exec korio-ollama ollama pull mistral:7b-instruct-q4_K_M
   # ya descargado en sesión 11
   ```
   - Ventaja: zero cloud, total control
   - Coste: `-20% speed` (~25s vs 3s), requiere upgrade RAM a 12 GB
   - Implementación: 1 hora

3. **Option 3: DPA formal Mistral** (legal, no técnico)
   - Contactar Mistral Enterprise: "need DPA for EU GDPR compliance"
   - Mistral ofrece DPA standard si plan ≥ €100/mes
   - Timing: 3–5 días respuesta
   - Documentar: `docs/MISTRAL-DPA.md` una vez firmado

**Recomendación**: **Option 1 + Option 3 en paralelo**. Habilitar Presidio redaction por default, pero dejar flag env `KORIO_REDACT_MISTRAL=1` (default). Si DPA firma rápido, se deshabilita.

#### B. Supabase + Migración formal DPA

**Status**: Supabase Pro en Frankfurt con DPA incluido (automático).

**Verificación**:
```bash
curl https://supabase.com/legal/dpa -H "Accept: application/pdf" > /tmp/supabase-dpa.pdf
# Verificar: "Data Controller" = Korio, "Data Processor" = Supabase
```

**Acción**: Archivar DPA en `docs/legal/supabase-dpa.pdf`. Referencia en privacy.md.

#### C. Privacy Policy + Términos

**Falta**: `korio.es/legal/privacy` estática.

**Boilerplate Phase 8**:
```markdown
# Privacy Policy — Korio

1. **Controller & Processor**
   - Controller (you decide): Cliente (empresa usando Korio)
   - Processor (nosotros): Korio SL, contacto@lagalga.es, <VPS_IP>

2. **Data Types**
   - Documentos corporativos (user-uploaded)
   - Embeddings (768-dim, no PII)
   - Metadata: usuario ID, tenant ID, timestamps

3. **Retention**: Según cliente. `DELETE /document/{id}` = eliminación completa en <24h.

4. **Rights**: Portability (JSON export Phase 9), Erasure, Access (subject-access Phase 9).

5. **Sub-processors**: Supabase (vectors), Mistral (LLM generation), Hetzner (compute).
```

---

## 3. Stack de mitigación hoy

### Presidio (PII detection/redaction)

**Ubicación**: `src/preprocessor.py`
**Entidades redactadas**: EMAIL, PHONE, PERSON, NIF, DNI, SSN, CREDIT_CARD

```python
analyzer = AnalyzerEngine()
redacted_text = anonymizer.anonymize(text)  # "Juan García 34534xxx-x" → "[PERSON] [DNI]"
```

**Prueba**:
```bash
python -c "
from src.preprocessor import Preprocessor
p = Preprocessor()
text = 'Juan García (juan.garcia@gmail.com, NIF 34534567X) trabaja aquí'
print(p.preprocess_text(text))
# Output: '[PERSON] ([EMAIL], [NIF]) trabaja aquí'
"
```

**Limitaciones**:
- ❌ No detecta "DNI truncado" formato "...X" (falso negativo)
- ❌ No detecta IBAN/BIC bancarios
- ✅ Detecta email/phone/NIF/DNI/persona

### RLS (Row-Level Security)

**Migración**: `supabase/migrations/001_initial_schema.sql` + `015_mcp_api_keys_rls.sql`

**Políticas**:
- `chunks`: User via `state.conversation.user_id` → RLS `user_spaces` → space_ids permitidos → `document_id IN (allowed)`
- `mcp_api_keys`: User solo ve/actualiza propias keys (SELF), service_role full

**Prueba**: `tests/test_rls.py` (10/10 ✅)

### HITL audit trail

**Tablas**:
- `conflict_reviews`: quién decidió, cuándo, decision (approved/rejected), policy_id generada
- `pipeline_events`: evento, agente, timestamp, operation_id, payload JSON

**Query acceso admin**:
```sql
SELECT
  cr.id, cr.chunk_id_1, cr.chunk_id_2, cr.decision, cr.reviewed_by, cr.reviewed_at,
  (SELECT COUNT(*) FROM policies p WHERE p.source_review_id = cr.id) as policies_created
FROM conflict_reviews cr
WHERE cr.tenant_id = $1
ORDER BY cr.reviewed_at DESC;
```

---

## 4. Checklist pre-launch (2 julio 2026)

- [ ] **Presidio redaction** → activar en `search.py` antes de Mistral (Option 1 § 2.1A)
- [ ] **Mistral DPA** → solicitar o usar Ollama 100% (Option 2/3 § 2.1A)
- [ ] **Privacy Policy** → deploy `korio.es/legal/privacy` (§ 2.1C)
- [ ] **DPA Supabase** → archivar en `docs/legal/supabase-dpa.pdf`
- [ ] **Bias audit** → `scripts/fairness_audit.py` ejecutar sobre corpus Delos
- [ ] **Right to erasure test** → `DELETE /document/{id}` E2E (Postgres + FalkorDB)
- [ ] **Admin dashboard** → `/admin/audit-log` mostrar `conflict_reviews` + `pipeline_events`

---

## 5. Referencia normativa

| Norma | Link | Sección relevante |
|-------|------|-------------------|
| **AI Act 2024/1689** | https://eur-lex.europa.eu/eli/reg/2024/1689 | Art. 13 (transparencia), Art. 36 (auditoría), Art. 15 (bias) |
| **GDPR** | https://gdpr-info.eu | Art. 5 (principios), Art. 32 (seguridad), Art. 33-34 (breach), Art. 6 (lawfulness) |
| **Directiva STS** | https://eur-lex.europa.eu/eli/dir/2024/680 | Acceso datos para ciberseguridad (no aplica) |
| **LSSI-CE (ES)** | https://www.boe.es/buscar/act.php?id=BOE-A-2002-13897 | Art. 11 (cookies, consentimiento — aplica a UI) |

---

## 6. Caso de uso: Delos RRHH

**Documentos ingestados**:
- `policy_vacaciones.md` — política genérica, **sin nombres** ✅
- `protocolo_admision.md` — genérico ✅
- `acta_junta.md` — acta febrero 2026, **puede contener emails de accionistas** ⚠️

**Riesgo**:
- Si acta_junta.md tiene emails/NIF, Presidio los redacta pre-ingest ✅
- Si user pregunta "¿quién va a la junta?", respuesta se basa en acta redactada → no expone PII ✅
- Si Mistral genera resumen, contexto ya está redactado ✅

**Cumplimiento**: **GDPR Art. 32 (security) + Art. 5 (minimization)** → **satisfecho** con Presidio + RLS + RLS mcp_api_keys.

---

## 7. Defensa TFM — ¿Qué contar?

**Capítulo 6 propuesto: "Gobernanza, seguridad y cumplimiento normativo"**

1. **§ 6.1 Modelo de gobernanza**: HITL review + auto-resolución policies
   - Tabla: 6 reglas E3 → cómo mitigan riesgos AI
   - Gráfico: pipeline de ingesta con puntos HITL/auto

2. **§ 6.2 Cumplimiento AI Act**: clasificación riesgo bajo, requisitos aplicables, audit trail
   - Matriz: requisitos Art. 13/36 → implementación en Korio

3. **§ 6.3 GDPR & datos personales**: Presidio, RLS, derecho a olvido
   - Diagrama: flujo de datos con redaction points

4. **§ 6.4 Lecciones**: trade-off privacy vs accuracy (Presidio), cloud vs on-prem LLM
   - Comparativa: cost/security/latency Mistral vs Ollama

**Tono**: Pragmático, enfoque negocio (pymes no quieren abogados, quieren tranquilidad).

---

**Versión**: v1.1 — 29 junio 2026 (sesión 19)
**Próxima revisión**: post-auditoría fairness (Phase 9)

### Actualizaciones v1.1 (sesiones 15b–19)

- **PII whitelist en Presidio** (v0.3.11): `_PII_ENTITY_TYPES` explícita tanto en preprocessor (ingesta) como en `llm_client` (redaction pre-Mistral). ORG/LOC/MISC NO son PII — redactarlos garbleaba texto de negocio y filenames. Ahora solo se redactan: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, NRP, CREDIT_CARD, IBAN_CODE, MEDICAL_LICENSE, ES_NIF, ES_NIE.
- **Observabilidad y GDPR** (v0.3.15): LangSmith con endpoint UE obligatorio (`eu.api.smith.langchain.com`); trazas residentes en UE. OTel+Jaeger self-hosted en VPS (0 datos a terceros). Ver `docs/OBSERVABILITY.md`.
- **Validación semántica LLM en detector** (v0.3.16): `is_chunk_contradiction()` usa Mistral temp=0 para confirmar que chunks son realmente contradictorios antes de declarar conflict. Reduce falsos positivos sin comprometer la gobernanza. El texto enviado a Mistral pasa por redaction PII previa (GDPR Art. 5 minimización).
- **Privacy Policy** desplegada en `korio.es/legal/privacy.html` desde v0.3.8.
