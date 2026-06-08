"""
Tests del pipeline de búsqueda RAG.

Verifica:
- La búsqueda devuelve resultados relevantes
- Las respuestas incluyen cita de fuente
- Los thresholds funcionan correctamente
- Las latencias se miden
- El pipeline completo funciona end-to-end

Nota: Estos son tests de integración — requieren Supabase + Ollama activos
y al menos 1 documento ingestado.
"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from search import search


class TestSearchBasico:
    """Tests básicos del pipeline de búsqueda."""

    def test_search_retorna_respuesta(self, user_delos_doctor, tenant_delos):
        """La búsqueda debe retornar un diccionario con las claves esperadas."""
        result = search(
            query="¿Cuáles son los beneficios para empleados?",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos
        )

        assert isinstance(result, dict), "El resultado debe ser un dict"
        assert "answer" in result, "Debe incluir 'answer'"
        assert "sources" in result, "Debe incluir 'sources'"
        assert "chunks_used" in result, "Debe incluir 'chunks_used'"
        assert "latency_ms" in result, "Debe incluir 'latency_ms'"
        assert "has_context" in result, "Debe incluir 'has_context'"
        assert "model_used" in result, "Debe incluir 'model_used'"

    def test_search_mide_latencia(self, user_delos_doctor, tenant_delos):
        """La latencia debe medirse y ser un número positivo."""
        result = search(
            query="¿Cuántos empleados tiene la clínica?",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos
        )

        assert isinstance(result["latency_ms"], int), "Latencia debe ser int"
        assert result["latency_ms"] > 0, "Latencia debe ser positiva"
        # Alerta si excede 30s (umbral generoso para CPU)
        assert result["latency_ms"] < 30000, \
            f"Latencia demasiado alta: {result['latency_ms']}ms"

    def test_search_incluye_modelo(self, user_delos_doctor, tenant_delos):
        """El resultado debe indicar qué modelo LLM se usó."""
        result = search(
            query="¿Qué departamentos hay?",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos
        )

        assert isinstance(result["model_used"], str), "model_used debe ser string"
        assert len(result["model_used"]) > 0, "model_used no debe estar vacío"

    def test_search_respuesta_es_string(self, user_delos_doctor, tenant_delos):
        """La respuesta debe ser un string no vacío."""
        result = search(
            query="¿Cuál es el proceso de evaluación de empleados?",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos
        )

        assert isinstance(result["answer"], str), "answer debe ser string"
        assert len(result["answer"]) > 0, "answer no debe estar vacío"


class TestSearchRLSEnBusqueda:
    """Verifica que la búsqueda respeta RLS."""

    def test_staff_busca_solo_en_rrhh(
        self,
        user_delos_staff,
        user_delos_doctor,
        tenant_delos
    ):
        """
        Staff solo ve contenido de RRHH, doctor ve RRHH + Médico.
        Una query sobre datos clínicos debería dar más chunks al doctor.
        """
        # Doctor busca sobre datos clínicos
        result_doctor = search(
            query="protocolo de admisión pacientes",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos,
            threshold=0.3
        )

        # Staff busca lo mismo (pero solo tiene RRHH)
        result_staff = search(
            query="protocolo de admisión pacientes",
            user_id=user_delos_staff,
            tenant_id=tenant_delos,
            threshold=0.3
        )

        # El doctor debería recuperar igual o más chunks que el staff
        # (porque tiene acceso a más documentos)
        assert result_doctor["chunks_used"] >= result_staff["chunks_used"], \
            f"Doctor debería tener >= chunks que staff. Doctor: {result_doctor['chunks_used']}, Staff: {result_staff['chunks_used']}"

    def test_aislamiento_entre_tenants_en_busqueda(
        self,
        user_delos_admin,
        user_garcia_admin,
        tenant_delos,
        tenant_garcia
    ):
        """
        Admin de Delos no debería ver resultados del tenant García y viceversa.

        Usa una query genérica que podría encontrar resultados en ambos tenants.
        Verifica que los document_ids devueltos son solo del tenant correcto.
        """
        # Búsqueda desde Delos
        result_delos = search(
            query="contrato servicios profesionales",
            user_id=user_delos_admin,
            tenant_id=tenant_delos,
            threshold=0.3
        )

        # Búsqueda desde García
        result_garcia = search(
            query="contrato servicios profesionales",
            user_id=user_garcia_admin,
            tenant_id=tenant_garcia,
            threshold=0.3
        )

        # Los doc_ids no deben solaparse entre tenants
        delos_docs = set(result_delos.get("doc_ids_used", []))
        garcia_docs = set(result_garcia.get("doc_ids_used", []))

        overlap = delos_docs & garcia_docs
        assert len(overlap) == 0, \
            f"¡FUGA entre tenants! Documentos compartidos: {overlap}"


class TestSearchConContexto:
    """Tests que verifican la calidad de la búsqueda con contexto."""

    def test_busqueda_con_umbral_alto_retorna_menos(
        self,
        user_delos_admin,
        tenant_delos
    ):
        """Con threshold más alto, se deberían recuperar menos chunks."""
        result_bajo = search(
            query="beneficios empleados clínica",
            user_id=user_delos_admin,
            tenant_id=tenant_delos,
            threshold=0.3
        )

        result_alto = search(
            query="beneficios empleados clínica",
            user_id=user_delos_admin,
            tenant_id=tenant_delos,
            threshold=0.9
        )

        assert result_bajo["chunks_used"] >= result_alto["chunks_used"], \
            "Umbral bajo debería dar >= chunks que umbral alto"

    def test_busqueda_sin_contexto_responde_honestamente(
        self,
        user_delos_doctor,
        tenant_delos
    ):
        """
        Si la query no tiene contexto relevante, la respuesta debería
        indicarlo (no alucinar). Verificamos que has_context es False
        con un umbral muy alto.
        """
        result = search(
            query="receta de cocina para hacer paella",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos,
            threshold=0.99  # Umbral imposible de alcanzar
        )

        # Con threshold imposible, no debería haber contexto
        assert result["has_context"] == False, \
            f"No debería haber contexto para query irrelevante con threshold 0.99"
        assert result["chunks_used"] == 0, "No debería haber chunks usados"

    def test_fuentes_tienen_estructura_correcta(
        self,
        user_delos_admin,
        tenant_delos
    ):
        """Las fuentes deben tener estructura coherente."""
        result = search(
            query="política de recursos humanos",
            user_id=user_delos_admin,
            tenant_id=tenant_delos,
            threshold=0.3
        )

        for source in result["sources"]:
            assert "document_id" in source, "Fuente debe tener document_id"
            assert "similarity" in source, "Fuente debe tener similarity"
            assert 0 <= source["similarity"] <= 1, \
                f"Similitud fuera de rango: {source['similarity']}"


class TestSearchLatencia:
    """Tests de performance."""

    def test_latencia_razonable_para_cpu(
        self,
        user_delos_doctor,
        tenant_delos
    ):
        """
        En CPU sin GPU, esperamos latencia < 30s.
        Documentar la latencia real para el informe de TFM.
        """
        start = time.time()
        result = search(
            query="¿Cuáles son los horarios del servicio de urgencias?",
            user_id=user_delos_doctor,
            tenant_id=tenant_delos
        )
        elapsed = time.time() - start

        # Para CPU sin GPU: hasta 30s es aceptable
        assert elapsed < 30, f"Latencia {elapsed:.1f}s excede límite de 30s en CPU"

        # Imprimir latencia para el informe de TFM
        print(f"\n⏱  Latencia de búsqueda RAG: {result['latency_ms']}ms")
        print(f"   Modelo: {result['model_used']}")
        print(f"   Chunks: {result['chunks_used']}")
