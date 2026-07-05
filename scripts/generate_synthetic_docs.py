#!/usr/bin/env python3
"""
Genera documentos sintéticos para Clínica Delos usando Mistral.
Mide tiempos de generación e ingesta en batch.

Uso:
  python scripts/generate_synthetic_docs.py --count 50 --output data-synthetic/generated/
  python scripts/generate_synthetic_docs.py --count 10 --ingest --tenant-id a0000000-... --space-id a1000000-...
  python scripts/generate_synthetic_docs.py --list-topics   # ver todos los temas disponibles
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── proyecto ──────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from src.llm_client import LLMClient

# ── catálogo de documentos por espacio ────────────────────────────────────────
TOPICS = {
  "rrhh": [
    ("politica_vacaciones_verano",      "Política de vacaciones de verano y periodos preferentes"),
    ("politica_vacaciones_navidad",     "Política de vacaciones de Navidad y fiestas de guardar"),
    ("protocolo_bajas_it",              "Protocolo gestión de bajas por incapacidad temporal"),
    ("protocolo_accidente_laboral",     "Protocolo notificación y gestión de accidentes laborales"),
    ("politica_conciliacion",           "Política de conciliación familiar: reducciones de jornada y excedencias"),
    ("reglamento_guardias_medicos",     "Reglamento de guardias de presencia y localizadas para médicos"),
    ("politica_retribucion_variable",   "Política de retribución variable y bonus por objetivos"),
    ("protocolo_evaluacion_desempeno",  "Protocolo de evaluación del desempeño anual"),
    ("politica_formacion_continua",     "Política de formación continua y desarrollo profesional"),
    ("reglamento_vestuario_uniforme",   "Reglamento de vestuario e identificación del personal"),
    ("protocolo_acogida_nuevos",        "Protocolo de acogida e incorporación de nuevos empleados"),
    ("politica_teletrabajo_admin",      "Política de teletrabajo para personal administrativo"),
    ("protocolo_sancion_disciplinaria", "Protocolo de régimen disciplinario y sanciones"),
    ("politica_prevencion_riesgos",     "Política de prevención de riesgos laborales"),
    ("protocolo_igualdad_genero",       "Protocolo de igualdad de género y plan de igualdad"),
    ("reglamento_horas_extra",          "Reglamento de compensación de horas extraordinarias"),
    ("politica_movilidad_interna",      "Política de movilidad interna y cambios de servicio"),
    ("protocolo_jubilacion_parcial",    "Protocolo de jubilación parcial y contratos de relevo"),
  ],
  "medico": [
    ("protocolo_triaje_urgencias",       "Protocolo de triaje en urgencias: niveles Manchester"),
    ("protocolo_consentimiento_info",    "Protocolo de consentimiento informado para procedimientos"),
    ("protocolo_cirugia_segura",         "Protocolo de cirugía segura: lista de verificación OMS"),
    ("politica_prescripcion_antibioticos","Política de prescripción racional de antibióticos"),
    ("protocolo_higiene_manos",          "Protocolo de higiene de manos y prevención de infecciones"),
    ("protocolo_manejo_caidas",          "Protocolo de prevención y manejo de caídas en pacientes"),
    ("politica_donacion_organos",        "Política de detección de potenciales donantes de órganos"),
    ("protocolo_sepsis",                 "Protocolo de detección y manejo precoz de sepsis"),
    ("protocolo_via_clinica_ictus",      "Vía clínica de atención al ictus agudo"),
    ("protocolo_dolor_cronico",          "Protocolo de evaluación y tratamiento del dolor crónico"),
    ("politica_historia_clinica",        "Política de cumplimentación y custodia de historia clínica"),
    ("protocolo_traslado_paciente",      "Protocolo de traslado de pacientes entre servicios"),
    ("politica_medicacion_alto_riesgo",  "Política de medicación de alto riesgo en hospitalización"),
    ("protocolo_reanimacion_rcp",        "Protocolo de reanimación cardiopulmonar básica y avanzada"),
    ("protocolo_atencion_paliativos",    "Protocolo de atención paliativa y cuidados al final de la vida"),
    ("reglamento_uso_ecografo",          "Reglamento de uso y mantenimiento del ecógrafo portátil"),
    ("protocolo_alergia_latex",          "Protocolo de atención a pacientes con alergia al látex"),
    ("politica_segunda_opinion",         "Política de segunda opinión médica a petición del paciente"),
  ],
  "legal": [
    ("politica_proteccion_datos_lopd",   "Política de protección de datos personales (LOPD/RGPD)"),
    ("protocolo_breach_datos",           "Protocolo de notificación de brechas de seguridad de datos"),
    ("politica_videovigilancia",         "Política de videovigilancia en instalaciones de la clínica"),
    ("reglamento_acceso_historiales",    "Reglamento de acceso y cesión de historiales clínicos"),
    ("protocolo_atencion_menores",       "Protocolo legal de atención a menores: consentimiento y representación"),
    ("politica_reclamaciones_pacientes", "Política de gestión de reclamaciones y quejas de pacientes"),
    ("protocolo_voluntad_anticipada",    "Protocolo de registro de instrucciones previas/voluntad anticipada"),
    ("reglamento_contratos_proveedores", "Reglamento de contratación y gestión de proveedores externos"),
    ("politica_conflicto_intereses",     "Política de prevención de conflicto de intereses del personal"),
    ("protocolo_denuncia_irregularidades","Protocolo de canal de denuncias (whistleblowing)"),
    ("politica_propiedad_intelectual",   "Política de propiedad intelectual sobre investigaciones y publicaciones"),
    ("reglamento_publicidad_sanitaria",  "Reglamento de publicidad sanitaria y comunicación externa"),
  ],
  "admin": [
    ("politica_gestion_residuos",        "Política de gestión de residuos sanitarios y clasificación"),
    ("protocolo_mantenimiento_equipos",  "Protocolo de mantenimiento preventivo y correctivo de equipos"),
    ("politica_compras_suministros",     "Política de compras y gestión de suministros sanitarios"),
    ("reglamento_aparcamiento",          "Reglamento de uso del aparcamiento para personal y pacientes"),
    ("protocolo_visitas_familiares",     "Protocolo de visitas de familiares en hospitalización"),
    ("politica_ti_sistemas",             "Política de uso de sistemas de información y equipos informáticos"),
    ("protocolo_incendio_evacuacion",    "Protocolo de emergencia contra incendios y plan de evacuación"),
    ("politica_sostenibilidad",          "Política de sostenibilidad medioambiental y eficiencia energética"),
    ("reglamento_cafeteria_comedor",     "Reglamento de uso de cafetería y comedor del personal"),
    ("protocolo_gestion_llaves",         "Protocolo de gestión y control de llaves y accesos"),
  ],
}

# ── prompts ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un redactor experto en documentación interna corporativa para clínicas privadas españolas.
Generas documentos internos realistas: políticas, protocolos, reglamentos y actas.
Los documentos son para uso interno de Clínica Delos, una clínica privada en Madrid con 187 empleados.
Responde SOLO con el documento en markdown, sin explicaciones adicionales."""

def make_user_prompt(topic: str, title: str, version: str, date_str: str, space: str) -> str:
  space_labels = {
    "rrhh": "Dirección de RRHH",
    "medico": "Dirección Médica",
    "legal": "Asesoría Jurídica",
    "admin": "Dirección de Administración",
  }
  responsible = space_labels.get(space, "Dirección General")
  return f"""Genera un documento interno titulado "{title}" para Clínica Delos.

Requisitos:
- Frontmatter YAML con: title, version ({version}), date ({date_str}), author (Clínica Delos), role ({responsible})
- Mínimo 600 palabras, máximo 900 palabras
- Mínimo 4 secciones numeradas con subsecciones
- Incluir tablas, listas numeradas y bullet points donde aplique
- Datos concretos: números, plazos, porcentajes, formularios internos (ej: FORM-{space.upper()}-01)
- Usar terminología técnica real del sector sanitario español
- Tono formal, imperativo institucional
- Al menos 2 referencias cruzadas a otros documentos internos de la clínica
- Sin disclaimers, sin meta-texto, sin "por supuesto", empieza directamente con el frontmatter YAML"""

# ── generador ─────────────────────────────────────────────────────────────────
def generate_doc(llm: LLMClient, topic: str, title: str, space: str, idx: int) -> tuple[str, float]:
  base_date = datetime(2024, 1, 1)
  doc_date = base_date + timedelta(days=idx * 17)  # fechas escalonadas, sin colisiones
  version = f"{(idx % 3) + 1}.{idx % 4}"
  date_str = doc_date.strftime("%d %B %Y")

  prompt = make_user_prompt(topic, title, version, date_str, space)

  t0 = time.monotonic()
  content = llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
  elapsed = time.monotonic() - t0

  filename = f"delos_{space}_{topic}.md"
  return filename, content, elapsed

def ingest_doc(filepath: Path, tenant_id: str, space_id: str) -> tuple[bool, float, str]:
  """Llama al pipeline de ingesta y mide tiempo."""
  import subprocess
  t0 = time.monotonic()
  result = subprocess.run(
    [sys.executable, "src/ingest.py", str(filepath),
     "--tenant-id", tenant_id, "--space-id", space_id],
    capture_output=True, text=True, cwd=Path(__file__).parent.parent
  )
  elapsed = time.monotonic() - t0
  ok = result.returncode == 0
  err = result.stderr.strip() if not ok else ""
  return ok, elapsed, err

# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args():
  parser = argparse.ArgumentParser(description="Generador de docs sintéticos Delos")
  parser.add_argument("--count", type=int, default=20, help="Número de docs a generar (default: 20)")
  parser.add_argument("--output", type=str, default="data-synthetic/generated", help="Directorio de salida")
  parser.add_argument("--space", choices=["rrhh", "medico", "legal", "admin", "all"], default="all")
  parser.add_argument("--ingest", action="store_true", help="Ingestar en Korio tras generar")
  parser.add_argument("--tenant-id", type=str, help="UUID del tenant (requerido con --ingest)")
  parser.add_argument("--space-id", type=str, help="UUID del space (requerido con --ingest)")
  parser.add_argument("--list-topics", action="store_true", help="Listar todos los temas disponibles")
  parser.add_argument("--results-json", type=str, help="Guardar métricas en JSON")
  return parser.parse_args()

def main():
  args = parse_args()

  if args.list_topics:
    total = 0
    for space, topics in TOPICS.items():
      print(f"\n[{space.upper()}] — {len(topics)} documentos")
      for slug, title in topics:
        print(f"  {slug:<45} {title}")
        total += 1
    print(f"\nTotal: {total} documentos disponibles")
    return

  if args.ingest and (not args.tenant_id or not args.space_id):
    print("ERROR: --ingest requiere --tenant-id y --space-id")
    sys.exit(1)

  output_dir = Path(args.output)
  output_dir.mkdir(parents=True, exist_ok=True)

  # selección de topics
  if args.space == "all":
    all_topics = [(space, slug, title) for space, items in TOPICS.items() for slug, title in items]
  else:
    all_topics = [(args.space, slug, title) for slug, title in TOPICS[args.space]]

  selected = all_topics[:args.count]
  total = len(selected)

  print(f"\n{'='*60}")
  print(f"  Clínica Delos — Generador de documentos sintéticos")
  print(f"{'='*60}")
  print(f"  Documentos a generar : {total}")
  print(f"  Directorio salida    : {output_dir}")
  print(f"  Ingesta automática   : {'SÍ' if args.ingest else 'NO'}")
  print(f"{'='*60}\n")

  llm = LLMClient()
  results = []
  gen_times = []
  ingest_times = []
  errors = 0

  for i, (space, slug, title) in enumerate(selected, 1):
    prefix = f"[{i:02d}/{total}]"
    print(f"{prefix} Generando: {title[:55]}...", end="", flush=True)

    try:
      filename, content, gen_time = generate_doc(llm, slug, title, space, i)
      gen_times.append(gen_time)

      filepath = output_dir / filename
      filepath.write_text(content, encoding="utf-8")
      chars = len(content)
      print(f" ✓ {gen_time:.1f}s ({chars} chars)")

      result = {
        "index": i,
        "space": space,
        "slug": slug,
        "title": title,
        "filename": filename,
        "chars": chars,
        "gen_time_s": round(gen_time, 2),
        "ingest_ok": None,
        "ingest_time_s": None,
        "error": None,
      }

      if args.ingest:
        print(f"{'':12} Ingestando...", end="", flush=True)
        ok, ingest_time, err = ingest_doc(filepath, args.tenant_id, args.space_id)
        ingest_times.append(ingest_time)
        result["ingest_ok"] = ok
        result["ingest_time_s"] = round(ingest_time, 2)
        if ok:
          print(f" ✓ {ingest_time:.1f}s")
        else:
          result["error"] = err[:120]
          errors += 1
          print(f" ✗ {ingest_time:.1f}s — {err[:80]}")

      results.append(result)

    except Exception as e:
      errors += 1
      print(f" ✗ ERROR: {e}")
      results.append({"index": i, "slug": slug, "error": str(e)})

  # ── resumen de métricas ───────────────────────────────────────────────────
  print(f"\n{'='*60}")
  print(f"  RESUMEN")
  print(f"{'='*60}")
  print(f"  Generados    : {len(gen_times)}/{total}")
  if gen_times:
    print(f"  Gen p50      : {sorted(gen_times)[len(gen_times)//2]:.1f}s")
    print(f"  Gen p95      : {sorted(gen_times)[int(len(gen_times)*0.95)]:.1f}s")
    print(f"  Gen total    : {sum(gen_times):.0f}s")
    avg_chars = sum(r.get("chars", 0) for r in results if r.get("chars")) / max(len(gen_times), 1)
    print(f"  Chars medio  : {avg_chars:.0f}")
  if ingest_times:
    print(f"  Ingest p50   : {sorted(ingest_times)[len(ingest_times)//2]:.1f}s")
    print(f"  Ingest p95   : {sorted(ingest_times)[int(len(ingest_times)*0.95)]:.1f}s")
    print(f"  Ingest total : {sum(ingest_times):.0f}s")
  if errors:
    print(f"  Errores      : {errors}")
  print(f"{'='*60}\n")

  if args.results_json:
    out = {
      "generated_at": datetime.now().isoformat(),
      "total": total,
      "errors": errors,
      "gen_p50_s": round(sorted(gen_times)[len(gen_times)//2], 2) if gen_times else None,
      "gen_p95_s": round(sorted(gen_times)[int(len(gen_times)*0.95)], 2) if gen_times else None,
      "ingest_p50_s": round(sorted(ingest_times)[len(ingest_times)//2], 2) if ingest_times else None,
      "ingest_p95_s": round(sorted(ingest_times)[int(len(ingest_times)*0.95)], 2) if ingest_times else None,
      "docs": results,
    }
    Path(args.results_json).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Métricas guardadas en: {args.results_json}")

if __name__ == "__main__":
  main()
