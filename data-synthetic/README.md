# Datos Sintéticos — Korio TFM

Documentos de prueba para testing del RAG sin datos reales.
**Todos los nombres, DNIs, NIFs, fechas y contactos son ficticios.**

## Inventario

### `demo-tfm/` — set canónico de la demo (19 docs en producción + variantes)

Documentos generados para la demo TFM del 2-jul-2026. Cada uno activa una casuística concreta del sistema. Los `.md` son fuente; los `.pdf`/`.docx` son las versiones que se ingestan (para probar el pipeline de conversión PyMuPDF + MarkItDown).

**Clínica Delos — 14 docs** (`tenant_id: a0000000-…-000000000001`)

| # | Doc | Space | Formato ingesta | Casuística |
|---|---|---|---|---|
| R1 | `R1_politica-vacaciones-2023.md/pdf` | RRHH | PDF | Superado por R2 (auto-resolución fecha) |
| R2 | `R2_politica-vacaciones-2025.md/pdf` | RRHH | PDF vía **Gmail** (label `korio/rrhh`) | Gana sobre R1 |
| R3 | `R3_protocolo-bajas-medicas.md/pdf` | RRHH | PDF | Silent conflict con R5 (query-time) |
| R4 | `R4_convenio-colectivo-sanitario-resumen.md` | RRHH | MD | Query rephrasada "¿cuánto se trabaja?" → grafo aporta 35h |
| R5 | `R5_circular-bajas-2024.md/pdf` | RRHH | PDF | Silent conflict query-time con R3 (12 vs 18 meses) |
| R6 | `R6_normativa-uniformes-personal-enfermeria.md` | RRHH | MD | HITL pending → policy `policy_new_wins` tras aprobación |
| R7 | `R7_nota-uniformes-personal-enfermeria.md` | RRHH | MD | Segundo par R6↔R7 auto-resuelto por policy reaplicada (Regla 4) |
| R7b | `R7b_nota-uniformes-personal-enfermeria.md/pdf` | RRHH | PDF | Variante para segunda toma / recuperación |
| M1 | `M1_protocolo-atencion-urgencias.md/pdf` | Médico | PDF | Superado por M2 |
| M2 | `M2_guia-clinica-urgencias-actualizada.md/pdf` | Médico | PDF vía **Drive** (`Clínica Delos / input/medico`) | Gana sobre M1 |
| M3 | `M3_ficha-medicamento-ibuprofeno.md` | Médico | MD | Presidio: nombre + DNI ficticios anonimizados |
| L1 | `L1_contrato-tipo-medico-residente.md/docx` | Legal | DOCX | Texto bilingüe ES/EN (multi-idioma) |
| L2 | `L2_circular-lopd-datos-pacientes-v1.md/pdf` | Legal | PDF | Cuestionado por L3, superseded tras promoción doc-level (≥2 aprobaciones HITL) |
| L3 | `L3_circular-lopd-datos-pacientes-v2.md/pdf` | Legal | PDF vía **Slack file_shared** | Gana sobre L2 tras HITL |

**Despacho García — 5 docs** (`tenant_id: b0000000-…-000000000002`)

| # | Doc | Space | Casuística |
|---|---|---|---|
| G1 | `G1_caso-despido-improcedente-cliente-acme.md` | Casos | Aislamiento RLS: no accesible desde tenant Delos |
| G2 | `G2_caso-reclamacion-cantidad-cliente-zenit.md` | Casos | Similar temática a G1 → validación semántica LLM filtra falso positivo (s19) |
| G3 | `G3_dictamen-fiscal-deducciones-irpf-2023.md` | Fiscal | Superado por G4 |
| G4 | `G4_dictamen-fiscal-deducciones-irpf-2025.md` | Fiscal | Gana sobre G3 |
| G5 | `G5_protocolo-onboarding-cliente-nuevo.md` | Casos | Aislamiento por role: `lawyer` sí lo ve, no accede a Fiscal |

Ver [`demo-tfm/README.md`](demo-tfm/README.md) para el guion detallado de la demo (fases 1–4, queries de prueba, cómo forzar `inconclusive`).

### Documentos históricos (sin prefijo `[letra][número]_`) — set inicial de sesiones 1-3

Docs originales de las primeras iteraciones. **No forman parte del set canónico de la demo** (no se ingestan por defecto), pero se conservan como material adicional para pruebas ad-hoc y para el "20º documento histórico" que se citó en algunas notas de sesión.

- `delos_politica_rrhh.md`
- `delos_protocolo_admision.md`
- `delos_acta_junta_directiva.md`
- `garcia_caso_laboral.md`
- `garcia_dictamen_fiscal.md`
- `garcia_protocolo_clientes.md`

### `eval-corpus/`

Set fijo para `scripts/rag_eval.py` — casos etiquetados (query esperada, respuesta objetivo, `retrieval_hit` objetivo). Se ejecuta como red de seguridad de calidad LLM-as-judge.

### `generated/` (opcional, no versionado)

Salida de `scripts/generate_synthetic_docs.py` — batch generado con LLM. Ignorado en git.

## Tenants y usuarios de prueba

### Clínica Delos (`a0000000-0000-0000-0000-000000000001`)

| Space | UUID |
|---|---|
| RRHH | `a1000000-0000-0000-0000-000000000001` |
| Médico | `a1000000-0000-0000-0000-000000000002` |
| Legal | `a1000000-0000-0000-0000-000000000003` |
| Administración | `a1000000-0000-0000-0000-000000000004` |

| Usuario | Rol | Spaces |
|---|---|---|
| admin | admin | todos |
| doctor | user | RRHH + Médico |
| staff | viewer | solo RRHH |

Service users Slack (uno por canal, RLS automático vía `user_spaces`):
`slack_rrhh@delos`, `slack_medico@delos`, `slack_legal@delos`, `slack_admin@delos`.

### Despacho García (`b0000000-0000-0000-0000-000000000002`)

| Space | UUID |
|---|---|
| Casos | `b1000000-0000-0000-0000-000000000001` |
| Fiscal | `b1000000-0000-0000-0000-000000000002` |

| Usuario | Rol | Spaces |
|---|---|---|
| admin | admin | Casos + Fiscal |
| lawyer | user | solo Casos |

## Ingesta manual

```bash
python src/ingest.py data-synthetic/demo-tfm/R4_convenio-colectivo-sanitario-resumen.md \
  --tenant-id a0000000-0000-0000-0000-000000000001 \
  --space-id a1000000-0000-0000-0000-000000000001
```

En producción la ingesta llega principalmente por los 3 canales automáticos (Gmail, Drive, Slack) — el manual se reserva para casos que quieren evitar los workflows n8n.

## Multi-tenant / RLS

Un usuario de Clínica NO debe ver documentos de Despacho. Un `lawyer` de Despacho NO debe ver contenido del space `Fiscal`.

```bash
# Query como staff@delos preguntando por García → 0 resultados
python src/search.py "¿Qué documentos tenemos?" \
  --user-id a3000000-0000-0000-0000-000000000001 \
  --tenant-id a0000000-0000-0000-0000-000000000001
```

## Reglas

- ✓ Datos completamente ficticios (nombres, DNIs, NIFs, direcciones)
- ✓ Formatos válidos para test (DNI `12345678Z`, IBAN sintético, etc.)
- ✓ Presidio (whitelist PII real: PERSON, EMAIL, PHONE, ES_NIF, ES_NIE, IBAN, MEDICAL_LICENSE) anonimiza el resto durante ingesta
- ✓ Redacción PII adicional antes de enviar contexto a Mistral cloud (Art. 5 minimización RGPD)
- ✗ **Nunca** usar datos reales de pacientes/clientes

---

*Actualizado: 5 julio 2026 — refleja set canónico demo TFM (19 docs producción, sesión 17c+, snapshot `pre_demo_v040`) + docs históricos como material adicional.*
