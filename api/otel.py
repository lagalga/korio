"""
OpenTelemetry — trazas distribuidas de la API exportadas a Jaeger (OTLP).

Complementa a LangSmith (src/observability.py): mientras LangSmith traza el
pipeline RAG a nivel semántico (embed → grafo → LLM, con tokens/coste), OTel
traza la capa de infraestructura HTTP — request entrante en FastAPI + llamadas
salientes con `requests` (Mistral, Ollama, Supabase REST). Permite ver en Jaeger
dónde se va la latencia de cada endpoint.

Opt-in y degradado seguro:
- Si KORIO_OTEL_ENABLED != "1"           → setup_otel() es no-op.
- Si los paquetes opentelemetry faltan   → no-op con warning (no rompe arranque).

Sesión 18 (Observabilidad y Evaluación).
"""

import os
import logging

logger = logging.getLogger(__name__)

OTEL_ENABLED = os.getenv("KORIO_OTEL_ENABLED", "0") == "1"
# Endpoint del colector OTLP (Jaeger all-in-one con COLLECTOR_OTLP_ENABLED).
# El daemon korio-api corre en el host vía systemd; Jaeger publica el puerto
# 4317 en 127.0.0.1, así que el host lo alcanza en localhost.
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "korio-api")


def setup_otel(app) -> bool:
    """
    Configura el TracerProvider + exporter OTLP e instrumenta FastAPI y requests.

    Args:
        app: instancia FastAPI a instrumentar.

    Returns:
        bool: True si OTel quedó activo, False si no-op (desactivado o sin deps).
    """
    if not OTEL_ENABLED:
        logger.info("OTel desactivado (KORIO_OTEL_ENABLED != 1)")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
    except Exception as e:
        logger.warning(f"OTel deps no instaladas, tracing OTLP desactivado: {e}")
        return False

    try:
        resource = Resource.create({"service.name": SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
        )
        trace.set_tracer_provider(provider)

        # Instrumentación automática: cada request a FastAPI abre un span raíz;
        # cada llamada saliente con `requests` (Mistral/Ollama/Supabase) cuelga
        # como span hijo → traza HTTP end-to-end en Jaeger.
        FastAPIInstrumentor.instrument_app(app)
        RequestsInstrumentor().instrument()

        logger.info(f"✓ OTel activo — exportando a {OTLP_ENDPOINT} (service={SERVICE_NAME})")
        return True
    except Exception as e:
        logger.warning(f"OTel setup falló (no crítico): {e}")
        return False
