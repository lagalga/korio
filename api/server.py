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
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

# Añadir src/ al path para importar los módulos del pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fastapi import FastAPI, HTTPException, UploadFile, Form, Query, Request, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from pydantic import BaseModel, Field, EmailStr

from search import search as run_search
from ingest import ingest_document, DuplicateDocumentError
from escalation import run_escalation

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
    answer:           str
    sources:          list
    chunks_used:      int
    latency_ms:       int
    has_context:      bool
    model_used:       str
    has_conflict:     bool = False    # True si la respuesta tocó chunks en disputa
    disputed_chunks:  int  = 0        # Número de chunks 'disputed' usados
    graph_contributed: bool = False   # True si el grafo de conocimiento aportó contexto


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

    except DuplicateDocumentError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Este documento ya estaba ingestado (filename existente: {e.filename})"
        )
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
    anonymize: bool = Form(True),
    source_type: str = Form("manual"),
    source_metadata: Optional[str] = Form(None),
):
    """
    Sube un fichero y lo ingesta directamente en el knowledge base.

    Acepta multipart/form-data con el fichero + tenant_id + space_id.
    El fichero se guarda en un directorio temporal y se elimina tras la ingesta.

    Para ingestas automáticas desde n8n u otros conectores se pueden enviar:
      - source_type: 'email' | 'drive' | 'slack' | 'notion' | 'manual'
      - source_metadata: JSON string con contexto del canal (message_id, from, etc.)
    """
    logger.info(f"POST /upload — tenant: {tenant_id[:8]}... file: {file.filename} src: {source_type}")

    # Parsear source_metadata si llega (n8n lo enviará como string JSON en multipart)
    parsed_metadata: Optional[dict] = None
    if source_metadata:
        try:
            parsed_metadata = json.loads(source_metadata)
            if not isinstance(parsed_metadata, dict):
                raise ValueError("source_metadata debe ser un objeto JSON")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"source_metadata no es JSON válido: {e}"
            )

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
            anonymize=anonymize,
            display_filename=file.filename,  # nombre real del fichero subido
            source_type=source_type,
            source_metadata=parsed_metadata,
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
    except DuplicateDocumentError as e:
        # Documento ya estaba ingestado (deduplicación por content_hash)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este documento ya estaba en el knowledge base "
                f"(filename: {e.filename}). Para forzar la re-ingesta, "
                f"elimínalo primero o sube una versión modificada."
            )
        )
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

        new_chunk_id      = review_data.get("new_chunk_id")
        existing_chunk_id = review_data.get("existing_chunk_id")
        tenant_id         = review_data.get("tenant_id")

        # Helper para sincronizar el grafo si está activado
        def _sync_graph_chunk(chunk_id, status):
            if not GRAPH_ENABLED or not chunk_id or not tenant_id:
                return
            try:
                from graph_client import get_graph_client
                gc = get_graph_client()
                gc.update_chunk_status(int(chunk_id), tenant_id, status)
            except Exception as e:
                logger.warning(f"Grafo: no se pudo sincronizar chunk {chunk_id}→{status}: {e}")

        if action == "approved_new":
            # El documento existente queda superseded (el nuevo prevalece)
            if existing_chunk_id:
                db.update_chunk_status(int(existing_chunk_id), "superseded")
                _sync_graph_chunk(existing_chunk_id, "superseded")
            msg_es = "✅ Documento nuevo aprobado. El contenido anterior ha sido archivado."

        elif action == "approved_existing":
            # El chunk nuevo queda superseded; el existente vuelve a active
            # (durante la detección se había marcado como disputed)
            if new_chunk_id:
                db.update_chunk_status(int(new_chunk_id), "superseded")
                _sync_graph_chunk(new_chunk_id, "superseded")
            if existing_chunk_id:
                db.update_chunk_status(int(existing_chunk_id), "active")
                _sync_graph_chunk(existing_chunk_id, "active")
            msg_es = "✅ Documento existente conservado. El contenido nuevo ha sido descartado."

        else:  # kept_both
            # Ambos chunks vuelven a active (los dos quedarán visibles en búsqueda
            # y el RAG presentará ambas afirmaciones como complementarias)
            if existing_chunk_id:
                db.update_chunk_status(int(existing_chunk_id), "active")
                _sync_graph_chunk(existing_chunk_id, "active")
            if new_chunk_id:
                db.update_chunk_status(int(new_chunk_id), "active")
                _sync_graph_chunk(new_chunk_id, "active")
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


# ─── Endpoints del grafo de conocimiento (Phase 7.1) ────────────────────────

GRAPH_ENABLED = os.getenv("KORIO_GRAPH_ENABLED", "0") == "1"


def _get_allowed_spaces(user_id: str) -> list:
    """RLS: obtiene los space_ids permitidos para el usuario."""
    from db import get_supabase_client
    db = get_supabase_client()
    rows = db.client.table("user_spaces").select("space_id").eq("user_id", user_id).execute()
    return [r["space_id"] for r in (rows.data or [])]


@app.get("/graph/contradictions", tags=["Grafo"])
async def graph_contradictions(tenant_id: str, user_id: str):
    """
    Lista todas las contradicciones (claims) del tenant para el usuario.
    Aplica RLS por allowed_space_ids.
    """
    if not GRAPH_ENABLED:
        raise HTTPException(status_code=503, detail="Grafo de conocimiento no activado")
    try:
        from graph_client import get_graph_client
        gc = get_graph_client()
        spaces = _get_allowed_spaces(user_id)
        if not spaces:
            raise HTTPException(status_code=403, detail="Usuario sin espacios asignados")
        contradictions = gc.get_contradictions(tenant_id=tenant_id, allowed_space_ids=spaces)
        return {
            "tenant_id":    tenant_id,
            "user_id":      user_id,
            "count":        len(contradictions),
            "contradictions": contradictions,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en /graph/contradictions")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/entity/{entity_name}", tags=["Grafo"])
async def graph_entity(entity_name: str, tenant_id: str, user_id: str, only_active: bool = True):
    """Devuelve todos los claims sobre una entidad concreta."""
    if not GRAPH_ENABLED:
        raise HTTPException(status_code=503, detail="Grafo de conocimiento no activado")
    try:
        from graph_client import get_graph_client
        gc = get_graph_client()
        spaces = _get_allowed_spaces(user_id)
        if not spaces:
            raise HTTPException(status_code=403, detail="Usuario sin espacios asignados")
        claims = gc.find_claims_by_entity(
            tenant_id=tenant_id,
            entity_name=entity_name,
            allowed_space_ids=spaces,
            only_active=only_active,
        )
        return {"entity": entity_name, "count": len(claims), "claims": claims}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en /graph/entity")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/subgraph", tags=["Grafo"])
async def graph_subgraph(tenant_id: str, user_id: str, limit: int = 200):
    """
    Devuelve el subgrafo del tenant (nodos + aristas) en formato vis-network.
    Útil para la visualización en /ui/graph.
    """
    if not GRAPH_ENABLED:
        raise HTTPException(status_code=503, detail="Grafo de conocimiento no activado")
    try:
        from graph_client import get_graph_client
        gc = get_graph_client()
        spaces = _get_allowed_spaces(user_id)
        if not spaces:
            raise HTTPException(status_code=403, detail="Usuario sin espacios asignados")
        sg = gc.get_tenant_subgraph(
            tenant_id=tenant_id,
            allowed_space_ids=spaces,
            limit=limit,
        )
        # Transformar al formato esperado por vis-network
        # Paleta:
        #   Documento → azul oscuro (#161632)
        #   Chunk     → gris medio (#94a3b8) [active], blanco+borde gris [superseded], rojo [disputed]
        #   Entidad   → azul Korio (#5B6AF5)
        #   Claim     → ámbar (#f59e0b) [active], blanco+borde gris [superseded], rojo [disputed]
        #   Arista CONTRADICTS → rojo grueso
        BASE_COLORS = {
            "Document": "#161632",
            "Chunk":    "#94a3b8",
            "Entity":   "#5B6AF5",
            "Claim":    "#f59e0b",
        }
        DISPUTED_COLOR    = {"background": "#dc2626", "border": "#991b1b"}  # rojo
        SUPERSEDED_COLOR  = {"background": "#ffffff", "border": "#cbd5e1"}  # blanco con borde gris

        vis_nodes = []
        for n in sg["nodes"]:
            label = (
                n.get("name")
                or n.get("subject")
                or n.get("filename")
                or str(n.get("node_id", ""))[:8]
            )
            kind = n.get("kind") or "Unknown"
            chunk_status = n.get("chunk_status")

            # Decidir color según tipo y estado
            if kind in ("Chunk", "Claim"):
                if chunk_status == "disputed":
                    color = DISPUTED_COLOR
                elif chunk_status == "superseded":
                    color = SUPERSEDED_COLOR
                else:
                    color = BASE_COLORS[kind]
            else:
                color = BASE_COLORS.get(kind, "#cbd5e1")

            vis_nodes.append({
                "id":    n["internal_id"],
                "label": str(label)[:40],
                "title": f"{kind}: {label}",
                "group": kind,
                "color": color,
            })
        vis_edges = []
        for e in sg["edges"]:
            ekind = e.get("kind", "")
            is_contradiction = (ekind == "CONTRADICTS")
            color = "#dc2626" if is_contradiction else "#cbd5e1"
            width = 4 if is_contradiction else 1
            vis_edges.append({
                "from":  e["source"],
                "to":    e["target"],
                "label": ekind,
                "color": {"color": color, "highlight": "#dc2626"},
                "width": width,
                "arrows": "to",
            })
        return {
            "tenant_id": tenant_id,
            "nodes":     vis_nodes,
            "edges":     vis_edges,
            "stats":     {"nodes": len(vis_nodes), "edges": len(vis_edges)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en /graph/subgraph")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Endpoint escalada de HITL (cron) ────────────────────────────────────────

KORIO_ADMIN_API_KEY = os.getenv("KORIO_ADMIN_API_KEY", "")

# Esquema de seguridad para que Swagger UI muestre el botón "Authorize"
# y un campo donde pegar la admin key. Auto-error desactivado: lo gestionamos
# nosotros para devolver mensajes consistentes con el resto de la API.
admin_key_header = APIKeyHeader(name="X-Korio-Admin-Key", auto_error=False)


def require_admin(key: Optional[str] = Security(admin_key_header)) -> None:
    """Dependency: valida la admin key del header X-Korio-Admin-Key."""
    if not KORIO_ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="KORIO_ADMIN_API_KEY no configurada en el servidor")
    if key != KORIO_ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Admin key inválida")


@app.post("/escalate-reviews", tags=["Gobernanza"], dependencies=[Depends(require_admin)])
async def escalate_reviews():
    """
    Ejecuta un ciclo de escalada sobre las revisiones HITL pendientes.

    Lógica:
    - Reviews pending desde >= 3 días → enviar email recordatorio (hasta 3 recordatorios)
    - Reviews pending desde >= 21 días → auto-resolución 'timeout_kept_both' + email final

    Auth: header `X-Korio-Admin-Key` debe coincidir con KORIO_ADMIN_API_KEY en .env.

    Diseñado para ser llamado por un workflow n8n Schedule Trigger (cron diario).
    """
    try:
        from db import get_supabase_client
        db = get_supabase_client()
        result = run_escalation(db)
        logger.info(f"Escalada ejecutada: {result.to_dict()}")
        return result.to_dict()
    except Exception as e:
        logger.exception("Error en /escalate-reviews")
        raise HTTPException(status_code=500, detail=f"Error en escalada: {str(e)}")


# ─── Endpoint admin: borrar documento ────────────────────────────────────────


@app.delete("/document/{document_id}", tags=["Admin"], dependencies=[Depends(require_admin)])
async def delete_document(document_id: str):
    """
    Elimina un documento del knowledge base.

    Borra en cascada: chunks + embeddings (FK ON DELETE CASCADE en Postgres)
    y nodos/aristas asociados en el grafo (FalkorDB) si KORIO_GRAPH_ENABLED.

    Auth: header `X-Korio-Admin-Key` debe coincidir con KORIO_ADMIN_API_KEY.

    Útil para:
    - Limpiar pruebas de ingesta automática (Gmail/Drive) que entran en el
      space equivocado.
    - "Desingerir" un documento sin tener que abrir Supabase.
    """
    from db import get_supabase_client
    db = get_supabase_client()

    # Comprobar que existe y recuperar contexto para limpiar el grafo
    existing = db.client.table("documents").select(
        "id, filename, tenant_id, space_id"
    ).eq("id", document_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")

    doc = existing.data[0]

    # Borrar del grafo primero (si está habilitado). Si falla, no abortamos el
    # borrado de Postgres — preferible un grafo levemente inconsistente a un
    # documento huérfano en BD.
    graph_deleted = False
    if os.getenv("KORIO_GRAPH_ENABLED", "0") == "1":
        try:
            from graph_client import get_graph_client
            get_graph_client().delete_document(document_id, doc["tenant_id"])
            graph_deleted = True
        except Exception as e:
            logger.warning(f"Error borrando documento del grafo: {e}")

    # Borrar en Postgres (cascade limpia embeddings, chunks, conflict_reviews)
    try:
        db.client.table("documents").delete().eq("id", document_id).execute()
    except Exception as e:
        logger.exception("Error borrando documento en Supabase")
        raise HTTPException(status_code=500, detail=f"Error borrando en BD: {str(e)}")

    logger.info(f"🗑️  Documento borrado: {document_id} ({doc['filename']})")

    return {
        "success":       True,
        "document_id":   document_id,
        "filename":      doc["filename"],
        "tenant_id":     doc["tenant_id"],
        "space_id":      doc["space_id"],
        "graph_deleted": graph_deleted,
    }


# ─── Endpoint waitlist (landing teaser) ─────────────────────────────────────

class WaitlistRequest(BaseModel):
    """Petición de alta en la lista de espera del beta."""
    email:   EmailStr = Field(..., description="Email del interesado en el beta")
    referer: Optional[str] = Field(None, description="Página de origen (opcional)")
    source:  str = Field("landing", description="Origen del lead")


@app.post("/waitlist", tags=["Landing"])
async def waitlist_signup(payload: WaitlistRequest, request: Request):
    """
    Guarda un email en la tabla de waitlist (lista de espera del beta).
    Idempotente: si el email ya existe, devuelve 409 sin error.
    """
    try:
        from db import get_supabase_client
        db = get_supabase_client()

        ua = request.headers.get("user-agent", "")[:500]

        result = db.client.table("waitlist").insert({
            "email":      str(payload.email).lower().strip(),
            "source":     payload.source,
            "user_agent": ua,
            "referer":    payload.referer,
        }).execute()

        logger.info(f"Waitlist signup: {payload.email}")
        return {"success": True, "message": "Email registrado en la lista de espera"}

    except Exception as e:
        # Unique constraint → email ya registrado (idempotente)
        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail="Este email ya estaba en la lista de espera"
            )
        logger.exception("Error en /waitlist")
        raise HTTPException(status_code=500, detail="No pudimos registrar el email")


# ─── Static files: Landing (raíz) + UI app (/ui) ────────────────────────────

_landing_dir = os.path.join(os.path.dirname(__file__), '..', 'landing')
_ui_dir      = os.path.join(os.path.dirname(__file__), '..', 'ui')

# UI app sigue en /ui (no cambia)
if os.path.isdir(_ui_dir):
    app.mount("/ui", StaticFiles(directory=_ui_dir, html=True), name="ui")

# Landing en raíz: sirve /assets/* y / como index.html
if os.path.isdir(_landing_dir):
    _landing_assets = os.path.join(_landing_dir, 'assets')
    if os.path.isdir(_landing_assets):
        app.mount("/assets", StaticFiles(directory=_landing_assets), name="landing-assets")

    @app.get("/", include_in_schema=False)
    async def landing_root():
        """Sirve la landing teaser de korio.es"""
        return FileResponse(os.path.join(_landing_dir, "index.html"))
elif os.path.isdir(_ui_dir):
    # Fallback: si no hay landing, raíz redirige a la app
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
