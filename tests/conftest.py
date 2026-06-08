"""
Fixtures de pytest para tests de Korio.

Contiene los IDs de los usuarios y tenants del seed (001_initial_schema.sql)
para que los tests sean reproducibles y consistentes.

IDs definidos en supabase/migrations/001_initial_schema.sql:
  - Tenant 1: Clínica Delos
  - Tenant 2: Despacho Legal García
"""

import sys
import os
import pytest

# Añadir src/ al path para importar los módulos del pipeline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ─── Tenants ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tenant_delos():
    """Tenant 1: Clínica Delos."""
    return "a0000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def tenant_garcia():
    """Tenant 2: Despacho Legal García."""
    return "b0000000-0000-0000-0000-000000000002"


# ─── Espacios ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def space_delos_rrhh():
    """Espacio RRHH de Clínica Delos."""
    return "a1000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def space_delos_medico():
    """Espacio Médico de Clínica Delos."""
    return "a1000000-0000-0000-0000-000000000002"


@pytest.fixture(scope="session")
def space_delos_legal():
    """Espacio Legal de Clínica Delos."""
    return "a1000000-0000-0000-0000-000000000003"


@pytest.fixture(scope="session")
def space_garcia_casos():
    """Espacio Casos de Despacho García."""
    return "b1000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def space_garcia_fiscal():
    """Espacio Fiscal de Despacho García."""
    return "b1000000-0000-0000-0000-000000000002"


# ─── Usuarios ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def user_delos_admin():
    """Admin de Clínica Delos — acceso a todos los espacios (RRHH, Médico, Legal)."""
    return "a1000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def user_delos_doctor():
    """Doctor de Clínica Delos — acceso a RRHH + Médico."""
    return "a2000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def user_delos_staff():
    """Staff de Clínica Delos — acceso SOLO a RRHH."""
    return "a3000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def user_garcia_admin():
    """Admin de Despacho García — acceso a Casos + Fiscal."""
    return "b1000000-0000-0000-0000-000000000002"


@pytest.fixture(scope="session")
def user_garcia_lawyer():
    """Abogado de Despacho García — acceso SOLO a Casos."""
    return "b2000000-0000-0000-0000-000000000002"


# ─── Cliente Supabase ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db():
    """Conexión a Supabase (singleton para todos los tests)."""
    from db import get_supabase_client
    return get_supabase_client()
