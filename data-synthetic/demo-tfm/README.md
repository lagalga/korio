# Documentos ficticios para la demo TFM · Clínica Delos

Set de 11 documentos generados para la demo del 2-jul-2026. Todos son ficticios. Los nombres de personas, fechas y cifras se han elegido para activar de forma controlada las casuísticas del sistema (gobernanza activa, grafo, RLS, detección query-time, anonimización PII).

## Asignación tenant/space

| Tenant | UUID |
|---|---|
| Clínica Delos | `a0000000-0000-0000-0000-000000000001` |

| Space | UUID |
|---|---|
| RRHH | `a1000000-0000-0000-0000-000000000001` |
| Médico | `a1000000-0000-0000-0000-000000000002` |
| Legal | `a1000000-0000-0000-0000-000000000003` |

## Documentos

| # | Markdown | Convertir a | Canal sugerido | Casuística activada |
|---|---|---|---|---|
| R1 | `R1_politica-vacaciones-2023.md` | **PDF** | manual | Será superado por R2 (auto-resolución) |
| R2 | `R2_politica-vacaciones-2025.md` | **PDF** | **Gmail** (label `korio/ingesta`) | Gana sobre R1 por fecha + autoridad |
| R3 | `R3_protocolo-bajas-medicas.md` | **PDF** | manual | Silent conflict con R5 (similitud ~0.80) |
| R4 | `R4_convenio-colectivo-sanitario-resumen.md` | **MD** (sin convertir) | manual | Query rephrasada "¿cuánto se trabaja?" → grafo aporta 35h |
| R5 | `R5_circular-bajas-2024.md` | **PDF** | manual | Silent conflict query-time con R3 (12 vs 18 meses, phrasing distinto) |
| M1 | `M1_protocolo-atencion-urgencias.md` | **PDF** | manual | Será superado por M2 (auto-resolución) |
| M2 | `M2_guia-clinica-urgencias-actualizada.md` | **PDF** | **Drive** (`Clínica Delos / input`) | Gana sobre M1 por autoridad alta + fecha reciente |
| M3 | `M3_ficha-medicamento-ibuprofeno.md` | **MD** (sin convertir) | manual | PII: contiene nombre + DNI ficticio → Presidio anonimiza |
| L1 | `L1_contrato-tipo-medico-residente.md` | **DOCX** | manual | Texto bilingüe español + inglés (prueba multi-idioma) |
| L2 | `L2_circular-lopd-datos-pacientes-v1.md` | **PDF** | manual | Será cuestionado por L3 |
| L3 | `L3_circular-lopd-datos-pacientes-v2.md` | **PDF** | **Slack file_shared** | Sin firma → HITL abierto, sin respuesta → timeout → `inconclusive` |

## Conversión

### Markdown → PDF (con pandoc + texlive)

```bash
brew install pandoc
brew install --cask basictex   # o mactex completo si quieres tablas/CJK

# Por fichero
pandoc R1_politica-vacaciones-2023.md \
  -o R1_politica-vacaciones-2023.pdf \
  --pdf-engine=xelatex \
  -V mainfont="Helvetica" -V geometry:margin=2.5cm

# En lote (todos los marcados PDF arriba)
for f in R1 R2 R3 R5 M1 M2 L2 L3; do
  src=$(ls ${f}_*.md)
  out="${src%.md}.pdf"
  pandoc "$src" -o "$out" --pdf-engine=xelatex \
    -V mainfont="Helvetica" -V geometry:margin=2.5cm
done
```

Si no quieres instalar LaTeX: abre el `.md` en Pages/Word/Typora y exporta a PDF. O usa `https://md2pdf.netlify.app`.

### Markdown → DOCX

```bash
pandoc L1_contrato-tipo-medico-residente.md \
  -o L1_contrato-tipo-medico-residente.docx
```

### Markdown se ingesta directo

R4 y M3 quedan en `.md`. El pipeline (MarkItDown + chunker) los procesa sin pasar por conversión.

## Plan de ingesta y demo

### Fase 1 — Reset (antes de ingestar nada nuevo)

Borra los docs antiguos del tenant Delos (ver instrucciones en el chat). Verifica grafo vacío.

### Fase 2 — Ingesta secuencial controlada

1. **R1** (manual, UI) — `space=RRHH`. Solo.
2. **R3** (manual, UI) — `space=RRHH`. Solo.
3. **R2** desde **Gmail** (label `korio/ingesta`) → ingesta automática en 5 min → **dispara conflicto con R1, auto-resuelto por fecha+autoridad** → R1 marcado disputed.
4. **R4** (manual, UI) — `space=RRHH`. Sin conflicto. Activa el grafo.
5. **R5** (manual, UI) — `space=RRHH`. La similitud con R3 está en zona gris (~0.80) → conflicto silencioso query-time.
6. **M1** (manual, UI) — `space=Médico`.
7. **M2** desde **Drive** (`Clínica Delos / input`) → ingesta automática → **conflicto con M1 auto-resuelto** por autoridad alta (Dr. jefe).
8. **M3** (manual, UI) — `space=Médico`. Activa Presidio para PII.
9. **L1** (manual, UI) — `space=Legal`. Sin conflicto.
10. **L2** (manual, UI) — `space=Legal`.
11. **L3** desde **Slack** (file_shared en el canal vigilado) → ingesta automática → **conflicto con L2 ambiguo** → HITL abierto.

### Fase 3 — Forzar `inconclusive` en L2/L3

Para el cron de escalada no esperes 21 días reales. Opciones:

**Opción A — env temporal:**
```bash
ssh korio-vps
# editar /root/korio/.env
ESCALATION_TIMEOUT_DAYS=0
systemctl restart korio-api
curl -X POST -H "X-Korio-Admin-Key: $KORIO_ADMIN_API_KEY" https://korio.es/escalate-reviews
# restaurar:
ESCALATION_TIMEOUT_DAYS=21
systemctl restart korio-api
```

**Opción B — SQL:**
```sql
UPDATE conflict_reviews
SET created_at = now() - interval '22 days'
WHERE id = '<review-id-de-L2-L3>';
-- luego: curl -X POST ... /escalate-reviews
```

Después de la escalación, los chunks de L2 y L3 deben quedar con `chunk_status='inconclusive'`.

### Fase 4 — Queries de demo

| Query | Espacio caller | Qué demuestra |
|---|---|---|
| "¿Cuántos días de vacaciones tengo?" | RRHH | Auto-resolución: responde 23 (R2), cita R1 disputed |
| "¿Cuánto se trabaja a la semana como mínimo?" | RRHH | Grafo aporta "35h/semana" desde R4 |
| "¿Cuánto dura la baja por IT como máximo?" | RRHH | Banner ⚠️ silent conflict R3 vs R5 |
| "¿En cuánto tiempo se atiende un nivel 2 en urgencias?" | Médico | Auto-resolución: responde 10 min (M2), cita M1 disputed |
| "¿Qué medicación se usa para cefalea tensional?" | Médico | M3 con PII anonimizada en logs |
| "¿Cuántos años se conservan los datos de paciente?" | Legal | Estado inconclusive → respuesta cauta |
| "¿Cuántos años de baja máxima?" | RRHH | Doctor llamando a Legal → 0 results (RLS) |
| "¿Qué dice el contrato del residente?" | Legal | L1 multilingüe |

## Reglas del E3 cubiertas

| Regla | Documentos | Verificable en demo |
|---|---|---|
| 1 — Pipeline ACID | Todos | Logs `pipeline_events` en n8n |
| 2 — Detección de conflictos en ingesta | R1↔R2, M1↔M2, L2↔L3 | Tres conflictos disparados |
| 3 — Auto-resolución | R1↔R2, M1↔M2 | Resoluciones sin HITL |
| 4 — Políticas reutilizables | L2↔L3 si lo resuelves HITL primero | Misma decisión cacheada |
| 5 — Estado terminal inconclusive | L2↔L3 con timeout | `chunk_status='inconclusive'` |
| 6 — Query-time silent conflict | R3↔R5 | Banner ⚠️ aviso gobernanza |

---

Generado en sesión 13b previa a la grabación del vídeo demo (objetivo: 2-jul-2026).
