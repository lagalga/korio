"""
benchmark.py — Medición de latencias del pipeline RAG.

Ejecuta N queries sobre ambos tenants y calcula p50, p95, p99.
Requiere que el servidor FastAPI esté corriendo en API_BASE.

Uso:
    python scripts/benchmark.py
    python scripts/benchmark.py --iterations 10 --api http://localhost:8000
    python scripts/benchmark.py --output results.json
"""

import argparse
import json
import math
import sys
import time
from typing import Optional

try:
    import requests
except ImportError:
    print("❌ Instala requests: pip install requests")
    sys.exit(1)

# ─── Configuración ────────────────────────────────────────────────────────────

DEFAULT_API = 'http://localhost:8000'
DEFAULT_ITERATIONS = 5

SCENARIOS = [
    # (nombre, user_id, tenant_id, query)
    (
        'Delos/admin',
        'a1000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        '¿Cuántos días de vacaciones tienen los empleados?',
    ),
    (
        'Delos/doctor',
        'a2000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        '¿Cuál es el protocolo de admisión de pacientes?',
    ),
    (
        'Delos/staff (solo RRHH)',
        'a3000000-0000-0000-0000-000000000001',
        'a0000000-0000-0000-0000-000000000001',
        '¿Qué documentos de recursos humanos existen?',
    ),
    (
        'García/admin',
        'b1000000-0000-0000-0000-000000000002',
        'b0000000-0000-0000-0000-000000000002',
        '¿Qué dice el dictamen fiscal?',
    ),
    (
        'García/lawyer (solo Casos)',
        'b2000000-0000-0000-0000-000000000002',
        'b0000000-0000-0000-0000-000000000002',
        '¿Cuál es el estado del caso laboral?',
    ),
]

# ─── Estadísticas ─────────────────────────────────────────────────────────────

def percentile(data: list[float], p: float) -> float:
    sorted_data = sorted(data)
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return sorted_data[f] if f == c else sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def stats(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        'n':    len(values),
        'min':  round(min(values)),
        'max':  round(max(values)),
        'mean': round(sum(values) / len(values)),
        'p50':  round(percentile(values, 50)),
        'p95':  round(percentile(values, 95)),
        'p99':  round(percentile(values, 99)),
    }

# ─── Ejecución ────────────────────────────────────────────────────────────────

def run_query(api_base: str, user_id: str, tenant_id: str, query: str) -> tuple[dict, float]:
    """Ejecuta una query y devuelve (resultado, latencia_real_ms)."""
    t0 = time.perf_counter()
    res = requests.post(
        f'{api_base}/search',
        json={'query': query, 'user_id': user_id, 'tenant_id': tenant_id},
        timeout=60
    )
    wall_ms = (time.perf_counter() - t0) * 1000
    res.raise_for_status()
    return res.json(), wall_ms


def benchmark(
    api_base: str = DEFAULT_API,
    iterations: int = DEFAULT_ITERATIONS,
    output: Optional[str] = None,
    warmup: bool = True,
):
    print(f'\n{"═" * 64}')
    print(f'  Korio — Benchmark de latencias RAG')
    print(f'  API: {api_base} · Iteraciones por escenario: {iterations}')
    print(f'{"═" * 64}\n')

    # Verificar que la API está activa
    try:
        health = requests.get(f'{api_base}/health', timeout=5).json()
        if health.get('status') != 'ok':
            print(f'⚠️  API degradada: {health.get("services")}')
        else:
            print(f'✅ API OK · LLM: {health.get("services", {}).get("llm", "?")}')
    except Exception as e:
        print(f'❌ No se puede conectar a la API: {e}')
        sys.exit(1)

    all_results = []
    all_wall_latencies = []
    all_api_latencies = []

    for name, user_id, tenant_id, query in SCENARIOS:
        print(f'\n▶  {name}')
        print(f'   Query: {query[:70]}')

        wall_times = []
        api_times  = []
        chunks_list = []
        errors = 0

        # Warmup (1 query descartada del cómputo)
        if warmup:
            try:
                run_query(api_base, user_id, tenant_id, query)
            except Exception:
                pass

        for i in range(iterations):
            try:
                result, wall_ms = run_query(api_base, user_id, tenant_id, query)
                wall_times.append(wall_ms)
                api_times.append(result.get('latency_ms', 0))
                chunks_list.append(result.get('chunks_used', 0))
                sys.stdout.write(f'   [{i+1}/{iterations}] wall: {wall_ms:.0f}ms  api: {result["latency_ms"]}ms  chunks: {result["chunks_used"]}\n')
                sys.stdout.flush()
            except Exception as e:
                errors += 1
                print(f'   [{i+1}/{iterations}] ERROR: {e}')

        if not wall_times:
            print('   ❌ Todos los intentos fallaron')
            continue

        s_wall = stats(wall_times)
        s_api  = stats(api_times)
        avg_chunks = round(sum(chunks_list) / len(chunks_list), 1) if chunks_list else 0

        print(f'\n   ┌── Latencia wall-clock (HTTP round-trip)')
        print(f'   │  p50: {s_wall["p50"]}ms  p95: {s_wall["p95"]}ms  p99: {s_wall["p99"]}ms')
        print(f'   │  min: {s_wall["min"]}ms  max: {s_wall["max"]}ms  mean: {s_wall["mean"]}ms')
        print(f'   ├── Latencia API (reportada por el servidor)')
        print(f'   │  p50: {s_api["p50"]}ms  p95: {s_api["p95"]}ms  p99: {s_api["p99"]}ms')
        print(f'   └── Chunks promedio: {avg_chunks}  Errores: {errors}')

        all_wall_latencies.extend(wall_times)
        all_api_latencies.extend(api_times)

        all_results.append({
            'scenario': name,
            'query': query,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'iterations': iterations,
            'errors': errors,
            'avg_chunks': avg_chunks,
            'wall_ms': s_wall,
            'api_ms': s_api,
            'raw_wall_ms': [round(x) for x in wall_times],
            'raw_api_ms':  api_times,
        })

    # Resumen global
    if all_wall_latencies:
        gs_wall = stats(all_wall_latencies)
        gs_api  = stats(all_api_latencies)
        print(f'\n{"═" * 64}')
        print(f'  RESUMEN GLOBAL ({len(all_wall_latencies)} queries)')
        print(f'  Wall-clock  p50: {gs_wall["p50"]}ms  p95: {gs_wall["p95"]}ms  p99: {gs_wall["p99"]}ms')
        print(f'  API interna p50: {gs_api["p50"]}ms   p95: {gs_api["p95"]}ms   p99: {gs_api["p99"]}ms')
        print(f'{"═" * 64}\n')

    # Guardar JSON
    report = {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'api_base': api_base,
        'iterations_per_scenario': iterations,
        'warmup': warmup,
        'scenarios': all_results,
        'global': {
            'wall_ms': stats(all_wall_latencies),
            'api_ms':  stats(all_api_latencies),
        }
    }

    if output:
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'📄 Resultados guardados en: {output}')

    return report


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Benchmark de latencias Korio RAG')
    parser.add_argument('--api', default=DEFAULT_API, help=f'URL de la API (default: {DEFAULT_API})')
    parser.add_argument('--iterations', '-n', type=int, default=DEFAULT_ITERATIONS,
                        help=f'Iteraciones por escenario (default: {DEFAULT_ITERATIONS})')
    parser.add_argument('--output', '-o', help='Guardar resultados en JSON')
    parser.add_argument('--no-warmup', action='store_true', help='No hacer warmup')
    args = parser.parse_args()

    benchmark(
        api_base=args.api,
        iterations=args.iterations,
        output=args.output,
        warmup=not args.no_warmup,
    )


if __name__ == '__main__':
    main()
