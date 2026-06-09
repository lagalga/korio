"""
API Server — FastAPI gateway para Korio.

Endpoints:
  POST /ingest   — Ingestar un documento en el knowledge base
  POST /search   — Buscar en el knowledge base (RAG)
  GET  /health   — Health check del sistema

Autenticación: user_id en el body (para TFM — en producción sería JWT).
"""

import sys
import os
import time
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

# Añadir src/ al path para importar los módulos del pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi import FastAPI, HTTPException, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, Field

from search import search as run_search
from ingest import ingest_document

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ─── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Korio API",
    description="Company Brain — RAG multi-tenant para pymes",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: lista de dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Modelos de Request / Response ──────────────────────────────────────────

class SearchRequest(BaseModel):
    """Petición de búsqueda RAG."""
    query: str = Field(..., min_length=1, max_length=2000, description="Pregunta en lenguaje natural")
    user_id: str = Field(..., description="UUID del usuario (define qué documentos puede ver)")
    tenant_id: Optional[str] = Field(None, description="UUID del tenant (para audit log)")
    limit: int = Field(5, ge=1, le=20, description="Número máximo de chunks a recuperar")
    threshold: float = Field(0.4, ge=0.0, le=1.0, description="Similitud mínima (0-1)")
    language: str = Field("es", pattern="^(es|en)$", description="Idioma de la respuesta")

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "¿Cuál es el protocolo de admisión de pacientes?",
                "user_id": "a2000000-0000-0000-0000-000000000001",
                "tenant_id": "a0000000-0000-0000-0000-000000000001"
            }
        }
    }


class SearchResponse(BaseModel):
    """Respuesta de búsqueda RAG."""
    answer: str
    sources: list
    chunks_used: int
    latency_ms: int
    has_context: bool
    model_used: str


class IngestRequest(BaseModel):
    """Petición de ingesta de documento."""
    file_path: str = Field(..., description="Ruta al fichero a ingestar")
    tenant_id: str = Field(..., description="UUID del tenant")
    space_id: str = Field(..., description="UUID del espacio al que pertenece el documento")
    source_type: str = Field("manual", description="Origen: manual, drive, slack, email, notion")
    anonymize: bool = Field(True, description="Si se debe anonimizar PII antes de ingestar")

    model_config = {
        "json_schema_extra": {
            "example": {
                "file_path": "/data/documento.pdf",
                "tenant_id": "a0000000-0000-0000-0000-000000000001",
                "space_id": "a1000000-0000-0000-0000-000000000002",
                "source_type": "manual"
            }
        }
    }


class ConflictItemOut(BaseModel):
    """Un conflicto individual en la respuesta de ingesta."""
    new_chunk_id:           int
    existing_chunk_id:      int
    existing_document_id:   str
    existing_filename:      str
    similarity:             float
    new_authority:          int
    existing_authority:     int
    resolution:             str
    resolution_reason:      str
    review_id:              Optional[str] = None


class ConflictReportOut(BaseModel):
    """Resumen de gobernanza activa devuelto tras la ingesta."""
    total_conflicts:  int
    auto_resolved:    int
    pending_review:   int
    has_conflicts:    bool
    has_pending:      bool
    conflicts:        list[ConflictItemOut]


class IngestResponse(BaseModel):
    """Respuesta de ingesta."""
    success:         bool
    document_id:     Optional[str]
    filename:        str
    chunks_created:  int
    pii_found:       int
    latency_ms:      int
    message:         str
    conflict_report: Optional[ConflictReportOut] = None


class ReviewResponse(BaseModel):
    """Respuesta de resolución de conflicto HITL."""
    success:    bool
    review_id:  str
    resolution: str
    message:    str


class HealthResponse(BaseModel):
    """Health check del sistema."""
    status: str
    timestamp: float
    services: dict


# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Sistema"])
async def health_check():
    """
    Verifica el estado del sistema.

    Comprueba conectividad con Supabase y disponibilidad del embedder.
    """
    services = {}
    overall_ok = True

    # Verificar Supabase
    try:
        from db import get_supabase_client
        db = get_supabase_client()
        db.table("tenants").select("id").limit(1).execute()
        services["supabase"] = "ok"
    except Exception as e:
        services["supabase"] = f"error: {str(e)[:100]}"
        overall_ok = False

    # Verificar embedder (Ollama)
    try:
        from embedder import get_embedder
        embedder = get_embedder()
        # Test embed rápido
        embedder.embed_text("test")
        services["embedder"] = "ok"
    except Exception as e:
        services["embedder"] = f"error: {str(e)[:100]}"
        overall_ok = False

    # Verificar LLM
    try:
        from llm_client import get_llm_client
        llm = get_llm_client()
        services["llm"] = f"ok ({llm.backend}/{llm.model})"
    except Exception as e:
        services["llm"] = f"error: {str(e)[:100]}"
        overall_ok = False

    return {
        "status": "ok" if overall_ok else "degraded",
        "timestamp": time.time(),
        "services": services
    }


@app.post("/search", response_model=SearchResponse, tags=["RAG"])
async def search_knowledge_base(request: SearchRequest):
    """
    Busca en el knowledge base del usuario con RAG.

    Pipeline:
    1. Embed la query (nomic-embed-text)
    2. RLS early binding — filtrar documentos según user_id
    3. Búsqueda vectorial (pgvector cosine similarity)
    4. Generación con LLM (Mistral API u Ollama)
    5. Respuesta con citas de fuente

    El usuario SOLO puede ver documentos de sus espacios asignados.
    """
    logger.info(f"POST /search — user: {request.user_id[:8]}... query: '{request.query[:50]}...'")

    try:
        result = run_search(
            query=request.query,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
            limit=request.limit,
            threshold=request.threshold,
            language=request.language
        )
        return result

    except ValueError as e:
        # Error de acceso (usuario sin espacios, etc.)
        raise HTTPException(status_code=403, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Error inesperado en /search")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.post("/ingest", response_model=IngestResponse, tags=["Ingesta"])
async def ingest(request: IngestRequest):
    """
    Ingestar un documento en el knowledge base.

    Pipeline:
    1. MarkItDown → Markdown
    2. Presidio → PII detection + pseudoanonimización
    3. Chunking (RecursiveTextSplitter, 500 tokens)
    4. Embedding (nomic-embed-text, 768 dims)
    5. Almacenamiento en pgvector (Supabase)

    El documento queda accesible SOLO para los usuarios del space indicado.
    """
    logger.info(f"POST /ingest — tenant: {request.tenant_id[:8]}... file: {request.file_path}")

    start_time = time.time()

    # Verificar que el fichero existe
    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=400,
            detail=f"Fichero no encontrado: {request.file_path}"
        )

    try:
        result = ingest_document(
            file_path=request.file_path,
            tenant_id=request.tenant_id,
            space_id=request.space_id,
            source_type=request.source_type,
            anonymize=request.anonymize
        )

        latency_ms = int((time.time() - start_time) * 1000)
        cr = result.get("conflict_report") or {}

        msg = f"Documento ingestado correctamente ({result.get('chunks_created', 0)} chunks)"
        if cr.get("total_conflicts", 0) > 0:
            msg += f" — {cr['total_conflicts']} conflictos ({cr['auto_resolved']} auto-resueltos, {cr['pending_review']} pendientes)"

        return {
            "success":         True,
            "document_id":     result.get("document_id"),
            "filename":        os.path.basename(request.file_path),
            "chunks_created":  result.get("chunks_created", 0),
            "pii_found":       result.get("pii_found", 0),
            "latency_ms":      latency_ms,
            "message":         msg,
            "conflict_report": cr if cr.get("has_conflicts") else None,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Error inesperado en /ingest")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.post("/upload", response_model=IngestResponse, tags=["Ingesta"])
async def upload_and_ingest(
    file: UploadFile,
    tenant_id: str = Form(...),
    space_id: str = Form(...),
    anonymize: bool = Form(True)
):
    """
    Sube un fichero y lo ingesta directamente en el knowledge base.

    Acepta multipart/form-data con el fichero + tenant_id + space_id.
    El fichero se guarda en un directorio temporal y se elimina tras la ingesta.
    """
    logger.info(f"POST /upload — tenant: {tenant_id[:8]}... file: {file.filename}")

    start_time = time.time()
    suffix = Path(file.filename).suffix if file.filename else ".tmp"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        result = ingest_document(
            file_path=tmp_path,
            tenant_id=tenant_id,
            space_id=space_id,
            anonymize=anonymize
        )
        latency_ms = int((time.time() - start_time) * 1000)
        cr = result.get("conflict_report") or {}

        msg = f"Documento ingestado ({result.get('chunks_created', 0)} chunks)"
        if cr.get("total_conflicts", 0) > 0:
            msg += f" — {cr['total_conflicts']} conflictos ({cr['auto_resolved']} auto-resueltos, {cr['pending_review']} pendientes)"

        return {
            "success":         True,
            "document_id":     result.get("document_id"),
            "filename":        file.filename or "documento",
            "chunks_created":  result.get("chunks_created", 0),
            "pii_found":       result.get("pii_found", 0),
            "latency_ms":      latency_ms,
            "message":         msg,
            "conflict_report": cr if cr.get("has_conflicts") else None,
        }
    except Exception as e:
        logger.exception("Error en /upload")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


# ─── Endpoint HITL: resolución de conflictos ─────────────────────────────────

VALID_REVIEW_ACTIONS = {"approved_new", "approved_existing", "kept_both"}


@app.get("/review/{review_id}", tags=["Gobernanza"])
async def review_conflict(
    review_id: str,
    action: str = Query(..., description="Acción: approved_new | approved_existing | kept_both"),
    token: str = Query(..., description="Token de autorización del email HITL"),
):
    """
    Resuelve un conflicto de gobernanza tras clic en email HITL.

    Llamado desde los links del email de revisión (generados por n8n).
    Verifica el token firmado, aplica la resolución y devuelve una página HTML
    de confirmación (para el revisor que abre el link en el navegador).

    Acciones válidas:
    - **approved_new**: El documento nuevo prevalece (el existente queda superseded)
    - **approved_existing**: El documento existente prevalece (el nuevo queda superseded)
    - **kept_both**: Se mantienen ambos documentos activos
    """
    if action not in VALID_REVIEW_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Acción inválida. Opciones: {', '.join(VALID_REVIEW_ACTIONS)}"
        )

    try:
        from db import get_supabase_client
        db = get_supabase_client()

        # Obtener el conflict_review y verificar token
        review = db.resolve_conflict_review(
            review_id=review_id,
            resolution=action,
            review_token=token,
        )

        if review is None:
            raise HTTPException(
                status_code=404,
                detail="Revisión no encontrada o token inválido"
            )

        # Aplicar efecto en base de datos según la acción
        review_data = review[0] if isinstance(review, list) else review

        if action == "approved_new":
            # El documento existente queda superseded
            existing_chunk_id = review_data.get("existing_chunk_id")
            if existing_chunk_id:
                db.update_chunk_status(int(existing_chunk_id), "superseded")
            msg_es = "✅ Documento nuevo aprobado. El contenido anterior ha sido archivado."

        elif action == "approved_existing":
            # El chunk nuevo queda superseded
            new_chunk_id = review_data.get("new_chunk_id")
            if new_chunk_id:
                db.update_chunk_status(int(new_chunk_id), "superseded")
            msg_es = "✅ Documento existente conservado. El contenido nuevo ha sido descartado."

        else:  # kept_both
            # Restaurar el chunk existente a active (estaba en disputed)
            existing_chunk_id = review_data.get("existing_chunk_id")
            if existing_chunk_id:
                db.update_chunk_status(int(existing_chunk_id), "active")
            msg_es = "✅ Ambos documentos se han conservado. El sistema mostrará los dos contenidos."

        logger.info(f"HITL resuelto: review_id={review_id} action={action}")

        # Respuesta HTML amigable para el revisor
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Korio — Conflicto resuelto</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; margin: 0; background: #f5f5f5; }}
    .card {{ background: white; border-radius: 12px; padding: 40px;
             max-width: 480px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,.1); }}
    .icon {{ font-size: 48px; margin-bottom: 16px; }}
    h1 {{ font-size: 22px; color: #161632; margin: 0 0 12px; }}
    p {{ color: #666; line-height: 1.6; margin: 0 0 24px; }}
    a {{ color: #5B6AF5; text-decoration: none; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h1>Conflicto resuelto</h1>
    <p>{msg_es}</p>
    <p style="font-size:13px;color:#999;">ID de revisión: {review_id[:8]}…</p>
    <a href="/">Volver a Korio</a>
  </div>
</body>
</html>"""
        return HTMLResponse(content=html, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en /review")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# ─── Static files (UI) ───────────────────────────────────────────────────────

_ui_dir = os.path.join(os.path.dirname(__file__), '..', 'ui')
if os.path.isdir(_ui_dir):
    app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/ui")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Hot-reload en desarrollo
        log_level="info"
    )
