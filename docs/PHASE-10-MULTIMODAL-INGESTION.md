# Phase 10 — Ingesta multimodal (post-TFM)

> Capítulo de la memoria TFM: "El conocimiento no vive solo en documentos".
> Post-defensa · Diseño funcional + de arquitectura.

---

## 1. Motivación

Korio v0.3.2 ingesta documentos estructurados (PDF, DOCX, XLSX, Markdown) vía:
- Upload manual desde la UI
- Gmail (label vigilada, adjuntos)
- Drive (carpeta vigilada)
- Slack (slash command para consultar **+** file_shared event para subir PDF/DOCX desde sesión 11)

Pero el **conocimiento operativo real de una pyme** vive también en:

| Canal | Forma del conocimiento | Ejemplo concreto |
|---|---|---|
| Email **cuerpo** | Texto plano + hilo | El gerente cierra un acuerdo de proveedor en un thread de respuestas. El PDF adjunto solo contiene el contrato firmado. |
| Hilos **Slack** | Mensajes cortos + reactions + threading | El equipo médico debate cómo aplicar un protocolo nuevo; el acuerdo final queda en una thread. |
| Hilos **MS Teams** | Igual que Slack pero distinto API/permisos | Empresas que viven en M365. |
| **Audio** (reuniones, notas de voz) | Sin texto previo, requiere ASR | Reunión semanal de coordinación; nota de voz del comercial al volver de visita. |
| **Vídeo** | Audio + frame OCR | Formación interna grabada. Phase 11+. |

Sin estos canales, Korio queda como **buscador de documentos**, no como **cerebro corporativo**.

---

## 2. Objetivo Phase 10

Extender el pipeline de ingesta para aceptar **3 nuevos tipos de input** sin tocar el resto del sistema (RLS, grafo, gobernanza, MCP):

1. **Texto plano de canal** (email body, Slack/Teams thread) → Markdown sintético.
2. **Audio** (MP3/WAV/OGG/M4A) → texto transcrito → Markdown.
3. **Metadatos enriquecidos de origen** en `source_metadata` (autor, fecha, participantes, idioma detectado).

El resto del pipeline (chunking → embeddings → pgvector + grafo + gobernanza + RLS) es agnóstico al origen porque opera ya sobre Markdown.

---

## 3. Arquitectura propuesta

```
                           ┌─ MarkItDown (ya) ──── PDF/DOCX/XLSX
                           │
[POST /upload]  →  Adapter ─── Plain-text adapter ── Email body, Slack/Teams threads
                           │
                           └─ ASR adapter ──────── Audio → texto (Whisper / Voxtral)
                                     │
                                     ▼
                             Markdown unificado
                                     │
                                     ▼
                             Pipeline existente
                       (chunk → embed → pgvector + grafo)
```

### 3.1 Email body adapter

- **Input**: header (from/to/subject/date), cuerpo texto (`text/plain` preferred, fallback `text/html` → stripped), thread_id, lista de mensajes previos en la thread.
- **Output**: Markdown estructurado:
  ```markdown
  # Asunto: {subject}
  **De:** {from} → {to} · **Fecha:** {date}
  **Thread:** {thread_id}

  ## Mensaje original
  {first_message_body}

  ## Respuesta 1 — {author} · {date}
  {reply_1}

  ## Respuesta 2 — {author} · {date}
  ...
  ```
- **Implementación**: librería `email` stdlib + `BeautifulSoup` para HTML stripping. Sin LLM.
- **`source_metadata`**:
  ```json
  {
    "via": "email_body",
    "thread_id": "...", "message_id": "...",
    "from": "...", "to": ["..."],
    "participants": ["..."]
  }
  ```

### 3.2 Slack / Teams thread adapter

- **Input**: lista de mensajes de una thread (channel/thread_ts en Slack, conversationId/messageId en Teams), incluyendo `user_id`, `text`, `ts`, `reactions`.
- **Output**: Markdown con un mensaje por sección, en orden cronológico, con reactions agregadas como anotación (`👍 ×3 desde @alice, @bob, @carlos`).
- **Diferencia con email**: hilos Slack/Teams son **conversacionales**, no "documentos" — chunking se ajusta a un overlap mayor (100 vs 50 actual) porque el contexto entre mensajes es crítico.
- **Trigger**:
  - **Slack**: Event Subscriptions del bot → workflow n8n que llama a `/upload` cuando se añade reaction `📥 korio` a un mensaje, ingerirá la thread completa hasta ese punto.
  - **Teams**: Graph API + webhook. Mismo patrón.
- **`source_metadata`**:
  ```json
  {
    "via": "slack_thread",
    "channel": "...", "thread_ts": "...",
    "participants": ["U123...", "U456..."],
    "first_message_ts": "..."
  }
  ```

### 3.3 Audio adapter (ASR)

Dos opciones realistas, ambas EU-friendly:

| Opción | Modelo | Pros | Contras |
|---|---|---|---|
| **A — Voxtral (Mistral)** | `voxtral-small-latest` API | Mistral API ya integrado. EU. Latencia baja. Cuenta dentro del free tier hasta ciertos minutos. | Coste real para volumen alto. |
| **B — Whisper local** | `faster-whisper` (CTranslate2) en Ollama VPS | €0 marginal. Funciona offline. Soporta ES nativo. | CPU lento (~0.5× realtime con `small` en 4 vCPU). Necesita modelo extra en disco (~250 MB para `small`). |

**Recomendación**: arrancar con **Voxtral API** (zero infra extra, cierra la demo en 10 minutos de código). Migrar a Whisper local cuando aparezca primer cliente real con audio recurrente (>100 min/mes).

**Output Markdown**:
```markdown
# Transcripción — {audio_filename}
**Duración:** 12m 34s · **Idioma detectado:** es · **Hablantes detectados:** 2

## Hablante 1 [00:00]
Buenos días, vamos a empezar la reunión de coordinación...

## Hablante 2 [00:42]
Antes de nada, recordad que el protocolo de admisión se ha actualizado...

...
```

**Diarización** (separación de hablantes) es opcional. Voxtral soporta speaker labels nativos; con Whisper se necesita `pyannote.audio` extra.

**`source_metadata`**:
```json
{
  "via": "audio",
  "duration_sec": 754,
  "language": "es",
  "asr_model": "voxtral-small-latest",
  "speakers_detected": 2,
  "original_filename": "reunion_coordinacion_2026-09-15.m4a"
}
```

---

## 4. Cambios concretos en el código

### 4.1 Nuevo endpoint `/ingest/{kind}`

Sustituye/complementa `/upload` con un router por tipo:

```
POST /ingest/document    → MarkItDown (actual /upload)
POST /ingest/email       → email body adapter
POST /ingest/slack       → Slack thread adapter
POST /ingest/audio       → ASR adapter
```

Cada uno acepta un payload distinto (multipart para audio, JSON para texto), genera Markdown internamente, y delega en `ingest_document_atomic` con el `source_metadata` apropiado.

### 4.2 Nuevo módulo `src/adapters/`

```
src/adapters/
├── __init__.py
├── email_adapter.py     # email body + thread → markdown
├── slack_adapter.py     # Slack thread → markdown
├── teams_adapter.py     # Teams thread → markdown
├── audio_adapter.py     # audio file → transcript markdown
└── base.py              # interfaz común: to_markdown() + source_metadata()
```

### 4.3 Workflows n8n nuevos

- **Gmail body → /ingest/email** (sin adjuntos, vigila label `korio/email-body`).
- **Slack reaction `📥 korio` → /ingest/slack** (Event Subscription + workflow que recupera la thread completa).
- **Teams webhook → /ingest/teams** (Graph API subscription).
- **Audio drop → /ingest/audio** (carpeta Drive vigilada o canal Slack de notas de voz).

### 4.4 Frontend (UI)

Añadir tres botones de upload en la UI:
- 📎 Documento (actual)
- 📧 Pegar email
- 🎤 Subir audio

Form con campos contextuales por tipo.

---

## 5. Coste estimado

| Canal | Coste marginal por unidad | Cuello de botella |
|---|---|---|
| Email body | €0 (parsing local) | — |
| Slack/Teams thread | €0 (parsing local) | API rate limit de Slack/Teams |
| Audio Voxtral | ~€0.0015 por minuto transcrito | API Mistral free tier para demo |
| Audio Whisper local | €0 marginal | CPU del VPS (1 min audio ≈ 2 min wall en CX32) |

Con la **media de uso real esperada para una pyme de 50 personas** (~200 emails/día, ~50 mensajes Slack/día, ~10 min audio/día):
- Email + Slack: €0/mes
- Audio Voxtral: ~10 min × 30 días × €0.0015 = **€0.45/mes**
- Audio Whisper local: €0 (~10 min audio/día ≈ 20 min CPU/día, despreciable)

Compatible con tier Starter (~€31/mes COGS — el coste de la ingesta multimodal es ruido).

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Privacidad de audio reuniones**: contenido sensible RGPD | Presidio post-transcripción (mismo paso que docs). Marcar audio como `confidential` por defecto en source_metadata; admin debe aprobar antes de indexar. |
| **Slack/Teams threads infinitas**: chunking explota | Cap de 200 mensajes por thread, fallback a chunking por sub-ventanas temporales (1h) si excede. |
| **Email con quoted-reply duplicado**: chunks duplicados que rompen dedupe | Stripping de quoted lines (`>` o `On {date}, {author} wrote:`) antes de chunkear. |
| **Audio en idiomas mezclados** (ES + EN) | Voxtral detecta automáticamente; Whisper requiere `language="auto"` y puede degradarse. Marcar `language` en metadata. |
| **Confusión de gobernanza con info de canal**: dos mensajes Slack contradictorios entre sí son comunes y NO son conflictos editoriales | Marcar `chunks` de origen `slack_thread`/`email_body` con `is_conversational=True` y excluirlos del detector de conflictos. Solo los documentos formales (vía `document`/`audio` con `is_formal=True`) entran en gobernanza. |

---

## 7. Hito demostrable

Ingerir esto en una sesión:

1. Adjunto un PDF de protocolo médico → ingesta normal.
2. Reenvío un email donde se discute la aplicación práctica del protocolo → ingesta del **body**.
3. Pego un thread de Slack con 8 mensajes donde el equipo aclara dudas operativas → ingesta del **thread**.
4. Subo el audio de una reunión de 10 min donde se acordó la versión final → ingesta de **audio transcrito**.

Y luego una **única query**: *"¿Cómo aplicamos el protocolo de admisión cuando llega un paciente fuera de horario?"* — la respuesta debe combinar info de **los 4 canales**, citando cada uno con su `via`.

---

## 8. Alineación con la propuesta de valor

> *"El conocimiento operativo de las pymes vive en documentos dispersos, en la memoria de personas clave o en correos."*

La versión 0.3.2 demuestra el caso del **documento disperso**. Phase 10 demuestra que Korio captura **también** los otros dos vectores: la conversación operativa (Slack/Teams/email body) y la palabra hablada (audio). Es el cierre natural del pitch comercial: *"todo lo que pasa por la organización, queda."*

---

*Diseño Phase 10 · 12 junio 2026 · post-defensa TFM*
