# Datos Sintéticos — Korio TFM

Documentos de prueba para testing del RAG sin datos reales.

## Verticales

Elige **UNA** vertical para el MVP (después agregar más):

### Opción A: Clínica Privada (Clínica Delos)
Documentos de ejemplo:
- `clinica_protocolo_admision.md` — Protocolo de admisión
- `clinica_acta_junta_directiva.md` — Acta de reunión junta directiva
- `clinica_contrato_proveedor.md` — Contrato con proveedor

**Usuarios de prueba:**
- admin@clinicadelos.es (admin, acceso a RRHH + Médico + Legal)
- doctor@clinicadelos.es (user, acceso a RRHH + Médico)
- staff@clinicadelos.es (viewer, acceso solo a RRHH)

### Opción B: Despacho de Abogados (Despacho García)
Documentos de ejemplo:
- `despacho_plantilla_contrato.md` — Plantilla de contrato
- `despacho_resolucion_fiscal.md` — Resolución fiscal
- `despacho_comunicado_legal.md` — Comunicado legal

**Usuarios de prueba:**
- admin@despacho.es (admin, acceso a Casos + Fiscal)
- lawyer@despacho.es (user, acceso solo a Casos)

## Cómo crear documentos sintéticos

### 1. Crear documento Markdown

```markdown
# Clínica Delos

## Protocolo de Admisión

Sección 1: Información general del paciente
- Nombre: [REDACTED]
- Documento: [REDACTED]
- Fecha de admisión: 2026-06-08

Procedimientos:
1. Registro de datos
2. Evaluación médica
3. Asignación de cama

...
```

### 2. Guardar como `.md`
```bash
echo "# Mi Documento" > data-synthetic/sample_01.md
```

### 3. Ingestar
```bash
python src/ingest.py data-synthetic/sample_01.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001
```

## Testing multi-tenant

**Verificar RLS:** Un usuario de Clínica NO debe ver documentos de Despacho.

```bash
# Ingestar para clínica
python src/ingest.py data-synthetic/clinica_*.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001

# Ingestar para despacho
python src/ingest.py data-synthetic/despacho_*.md \
  --tenant-id b0000000-0000-0000-0000-000000000002 \
  --space-id b1000000-0000-0000-0000-000000000001

# Query como usuario de clínica
python src/search.py "¿Qué documentos legales tenemos?" \
  --user-id a2000000-0000-0000-0000-000000000001

# Resultado: Solo documentos de clínica, NO del despacho ✓
```

## Contenido sugerido

### Para Clínica:
- Protocolos médicos
- Actas de junta directiva
- Contratos con proveedores
- Documentación de pacientes (datos sintéticos, sin PII real)

### Para Despacho:
- Plantillas de contratos
- Resoluciones fiscales
- Comunicados legales
- Documentación de casos (datos sintéticos)

## Importante

**Nunca** usar datos reales de pacientes/clientes, incluso para testing.
Siempre:
- ✓ Datos completamente ficticios
- ✓ Nombres y contactos inventados
- ✓ Sin PII real (DNI, teléfono, email reales)
- ✓ Presidio anonimiza el resto

---

*Actualizado: 8 junio 2026*
