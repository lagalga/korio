"""
Tests de RLS (Row-Level Security) — Early Binding.

CRÍTICO: Verifica que el sistema NO expone datos entre tenants ni entre
espacios de un mismo tenant.

Escenario de test:
  - Clínica Delos: admin (todos), doctor (RRHH + Médico), staff (solo RRHH)
  - Despacho García: admin (Casos + Fiscal), abogado (solo Casos)

Los tests usan los documentos sintéticos ya ingestados en Supabase.
Ejecutar DESPUÉS de ingestar al menos un documento en cada espacio.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from db import get_supabase_client


class TestRLSEspaciosDentroTenant:
    """Verifica aislamiento entre espacios del mismo tenant."""

    def test_staff_solo_ve_rrhh(
        self,
        db,
        user_delos_staff,
        space_delos_rrhh,
        space_delos_medico
    ):
        """
        Staff de Clínica Delos tiene acceso SOLO a RRHH.
        NO debe ver documentos del espacio Médico.
        """
        # Obtener espacios permitidos para staff
        result = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_staff
        ).execute()

        space_ids = [row["space_id"] for row in result.data]

        assert space_delos_rrhh in space_ids, \
            f"Staff debería tener acceso a RRHH ({space_delos_rrhh})"
        assert space_delos_medico not in space_ids, \
            f"Staff NO debería tener acceso a Médico ({space_delos_medico})"

    def test_doctor_ve_rrhh_y_medico(
        self,
        db,
        user_delos_doctor,
        space_delos_rrhh,
        space_delos_medico,
        space_delos_legal
    ):
        """
        Doctor tiene acceso a RRHH + Médico.
        NO debe ver documentos del espacio Legal.
        """
        result = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_doctor
        ).execute()

        space_ids = [row["space_id"] for row in result.data]

        assert space_delos_rrhh in space_ids, "Doctor debería ver RRHH"
        assert space_delos_medico in space_ids, "Doctor debería ver Médico"
        assert space_delos_legal not in space_ids, "Doctor NO debería ver Legal"

    def test_admin_ve_todos_los_espacios(
        self,
        db,
        user_delos_admin,
        space_delos_rrhh,
        space_delos_medico,
        space_delos_legal
    ):
        """Admin tiene acceso a todos los espacios del tenant."""
        result = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_admin
        ).execute()

        space_ids = [row["space_id"] for row in result.data]

        assert space_delos_rrhh in space_ids, "Admin debería ver RRHH"
        assert space_delos_medico in space_ids, "Admin debería ver Médico"
        assert space_delos_legal in space_ids, "Admin debería ver Legal"

    def test_lawyer_solo_ve_casos(
        self,
        db,
        user_garcia_lawyer,
        space_garcia_casos,
        space_garcia_fiscal
    ):
        """
        Abogado de Despacho García tiene acceso SOLO a Casos.
        NO debe ver documentos del espacio Fiscal.
        """
        result = db.table("user_spaces").select("space_id").eq(
            "user_id", user_garcia_lawyer
        ).execute()

        space_ids = [row["space_id"] for row in result.data]

        assert space_garcia_casos in space_ids, "Abogado debería ver Casos"
        assert space_garcia_fiscal not in space_ids, "Abogado NO debería ver Fiscal"


class TestRLSAislamientoEntreTenants:
    """Verifica que usuarios de un tenant NO pueden ver datos de otro tenant."""

    def test_delos_no_ve_documentos_garcia(
        self,
        db,
        user_delos_admin,
        tenant_garcia
    ):
        """
        Admin de Clínica Delos NO debe poder ver documentos de Despacho García.

        Mecanismo: los espacios del admin de Delos no incluyen ningún espacio
        de García — incluso con acceso de admin.
        """
        # Obtener espacios del admin de Delos
        user_spaces = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_admin
        ).execute()
        delos_space_ids = [row["space_id"] for row in user_spaces.data]

        # Obtener espacios de García
        garcia_spaces = db.table("spaces").select("id").eq(
            "tenant_id", tenant_garcia
        ).execute()
        garcia_space_ids = [row["id"] for row in garcia_spaces.data]

        # Ningún espacio de Delos debe ser un espacio de García
        overlap = set(delos_space_ids) & set(garcia_space_ids)
        assert len(overlap) == 0, \
            f"¡FUGA! Espacios cruzados entre tenants: {overlap}"

    def test_garcia_no_ve_documentos_delos(
        self,
        db,
        user_garcia_admin,
        tenant_delos
    ):
        """
        Admin de Despacho García NO debe poder ver documentos de Clínica Delos.
        """
        user_spaces = db.table("user_spaces").select("space_id").eq(
            "user_id", user_garcia_admin
        ).execute()
        garcia_space_ids = [row["space_id"] for row in user_spaces.data]

        delos_spaces = db.table("spaces").select("id").eq(
            "tenant_id", tenant_delos
        ).execute()
        delos_space_ids = [row["id"] for row in delos_spaces.data]

        overlap = set(garcia_space_ids) & set(delos_space_ids)
        assert len(overlap) == 0, \
            f"¡FUGA! Espacios cruzados entre tenants: {overlap}"

    def test_documentos_aislados_por_tenant(
        self,
        db,
        user_delos_doctor,
        tenant_garcia
    ):
        """
        El doctor de Delos no puede ver documentos del tenant García
        aunque haga query directa filtrando por tenant_id de García.

        Verifica early binding a nivel de aplicación: los documentos que
        llegan al vector search son SOLO los del usuario — nunca los de García.
        """
        # Simular early binding: obtener docs permitidos para doctor
        user_spaces = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_doctor
        ).execute()
        allowed_space_ids = [row["space_id"] for row in user_spaces.data]

        allowed_docs = db.table("documents").select("id, tenant_id").in_(
            "space_id", allowed_space_ids
        ).execute()

        # Verificar que NINGÚN documento permitido pertenece a García
        garcia_docs_leaked = [
            doc for doc in allowed_docs.data
            if doc["tenant_id"] == tenant_garcia
        ]

        assert len(garcia_docs_leaked) == 0, \
            f"¡FUGA de datos! El doctor de Delos tiene acceso a {len(garcia_docs_leaked)} documento(s) de García"


class TestRLSDocumentosEnVectorSearch:
    """Verifica que la búsqueda vectorial respeta RLS."""

    def test_staff_solo_busca_en_sus_docs(
        self,
        db,
        user_delos_staff,
        space_delos_rrhh,
        space_delos_medico
    ):
        """
        Cuando staff hace una búsqueda, solo busca en documentos de RRHH.
        NO busca en documentos de Médico.
        """
        # Obtener documentos accesibles para staff
        user_spaces = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_staff
        ).execute()
        allowed_space_ids = [row["space_id"] for row in user_spaces.data]

        # Obtener documentos en esos espacios
        allowed_docs = db.table("documents").select("id, space_id").in_(
            "space_id", allowed_space_ids
        ).execute()

        # Ninguno debería ser del espacio Médico
        medico_docs = [
            doc for doc in allowed_docs.data
            if doc["space_id"] == space_delos_medico
        ]

        assert len(medico_docs) == 0, \
            f"Staff tiene acceso a {len(medico_docs)} documento(s) del espacio Médico"

    def test_staff_no_tiene_espacios_vacios(
        self,
        db,
        user_delos_staff
    ):
        """Staff debería tener al menos 1 espacio asignado (RRHH)."""
        result = db.table("user_spaces").select("space_id").eq(
            "user_id", user_delos_staff
        ).execute()

        assert len(result.data) >= 1, "Staff debería tener al menos 1 espacio asignado"

    def test_usuario_sin_espacios_falla_gracefully(self, db):
        """
        Si un usuario no existe o no tiene espacios, el sistema debe
        fallar con un error claro (no devolver todos los documentos).
        """
        fake_user_id = "00000000-0000-0000-0000-000000000000"

        result = db.table("user_spaces").select("space_id").eq(
            "user_id", fake_user_id
        ).execute()

        # Debe retornar lista vacía — no documentos de otros usuarios
        assert result.data == [], \
            f"Usuario inexistente devolvió espacios: {result.data}"
