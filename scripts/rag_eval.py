"""
RAG eval — evaluación de CALIDAD del pipeline RAG con LLM-as-judge.

Complementa benchmark.py (que mide solo latencia). Aquí medimos si las
respuestas son buenas, no solo rápidas:

  - answer_relevance (1-5): ¿la respuesta aborda la pregunta?  [reference-free]
  - faithfulness     (1-5): ¿se apoya en las fuentes recuperadas, sin inventar?
  - correctness      (1-5): ¿contiene el hecho esperado?  [solo si expected_fact]
  - retrieval_hit    (bool): ¿el doc esperado está en sources?  [si expected_doc]
  - latency_ms       (int):  latencia end-to-end de search()

El juez es el propio LLM de Korio (Mistral, temp 0.0) reutilizando llm_client.
Los casos `expected_fact: "NO_ANSWER"` validan que el RAG declina correctamente
preguntas fuera de dominio (no alucina).

Uso:
    python scripts/rag_eval.py                       # set por defecto
    python scripts/rag_eval.py --set scripts/eval_set.json -o eval_out.json

Requiere los mismos servicios que search(): Ollama (embeddings), Supabase, y
Mistral (juez + generación). Pensado para correr en el VPS o con túnel.
"""

import os
import sys
import json
import argparse
import logging

# Permitir import de src/ tanto desde la raíz como desde scripts/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from search import search          # noqa: E402
from llm_client import get_llm_client  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Patrones de refusal (alineados con search.py) para evaluar casos NO_ANSWER.
_REFUSAL_PATTERNS = (
    "no encuentro información", "no tengo información", "no dispongo de información",
    "no hay información", "no se menciona", "no se especifica", "no se indica",
    "los documentos disponibles no", "no puedo responder",
)


def _is_refusal(answer: str) -> bool:
    a = (answer or "").strip().lower()
    return any(p in a for p in _REFUSAL_PATTERNS)


def _judge(llm, query: str, answer: str, sources: list, expected_fact) -> dict:
    """LLM-as-judge: puntúa relevancia, fidelidad y (si aplica) correctness."""
    sources_txt = "\n".join(
        f"  - {s.get('filename') or s.get('document_id')} (sim {s.get('similarity', 0):.2f})"
        for s in sources
    ) or "  (sin fuentes recuperadas)"

    correctness_block = ""
    if expected_fact and expected_fact != "NO_ANSWER":
        correctness_block = (
            f"\nHECHO ESPERADO (para correctness): \"{expected_fact}\"\n"
            "correctness = 5 si la respuesta contiene ese hecho de forma equivalente, "
            "1 si lo contradice o lo omite. Si no aplica, usa null."
        )

    system_prompt = (
        "Eres un evaluador riguroso de sistemas RAG. Puntúas respuestas de 1 a 5. "
        "Respondes SOLO con un objeto JSON válido, sin texto adicional, sin markdown."
    )
    user_prompt = (
        f"PREGUNTA:\n{query}\n\n"
        f"RESPUESTA DEL SISTEMA:\n{answer}\n\n"
        f"FUENTES RECUPERADAS:\n{sources_txt}\n"
        f"{correctness_block}\n\n"
        "Evalúa y devuelve EXACTAMENTE este JSON:\n"
        "{\n"
        '  "answer_relevance": <1-5: la respuesta aborda directamente la pregunta>,\n'
        '  "faithfulness": <1-5: la respuesta se apoya en las fuentes sin inventar datos>,\n'
        '  "correctness": <1-5 o null según el hecho esperado>,\n'
        '  "reasoning": "<una frase justificando las notas>"\n'
        "}"
    )
    try:
        raw = llm.generate(prompt=user_prompt, system_prompt=system_prompt,
                           temperature=0.0, max_tokens=300).strip()
        # Sanear posibles fences ```json
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{"):]
        raw = raw[raw.find("{"): raw.rfind("}") + 1]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Juez falló: {e}")
        return {"answer_relevance": None, "faithfulness": None,
                "correctness": None, "reasoning": f"judge_error: {e}"}


def run_eval(eval_set: dict) -> dict:
    """Ejecuta todos los casos y devuelve resultados + agregados."""
    llm = get_llm_client()
    user_id = eval_set.get("default_user_id")
    tenant_id = eval_set.get("default_tenant_id")
    results = []

    for case in eval_set["cases"]:
        cid = case["id"]
        query = case["query"]
        expected_fact = case.get("expected_fact")
        expected_doc = case.get("expected_doc")
        print(f"▶ {cid}: {query[:60]}...")

        res = search(query=query,
                     user_id=case.get("user_id", user_id),
                     tenant_id=case.get("tenant_id", tenant_id))
        answer = res["answer"]
        sources = res.get("sources", [])

        # Métricas objetivas
        retrieval_hit = None
        if expected_doc:
            retrieval_hit = any(expected_doc in (s.get("filename") or "") for s in sources)

        # Caso fuera de dominio: éxito = el sistema declina (no alucina)
        if expected_fact == "NO_ANSWER":
            scores = {
                "answer_relevance": None, "faithfulness": None,
                "correctness": 5 if _is_refusal(answer) else 1,
                "reasoning": "NO_ANSWER: pass si declina, fail si responde algo.",
            }
        else:
            scores = _judge(llm, query, answer, sources, expected_fact)

        row = {
            "id": cid, "query": query, "answer": answer,
            "latency_ms": res.get("latency_ms"),
            "chunks_used": res.get("chunks_used"),
            "graph_contributed": res.get("graph_contributed"),
            "retrieval_hit": retrieval_hit,
            **{k: scores.get(k) for k in ("answer_relevance", "faithfulness", "correctness")},
            "reasoning": scores.get("reasoning"),
        }
        results.append(row)

    # Agregados
    def _avg(key):
        vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    hits = [r["retrieval_hit"] for r in results if r["retrieval_hit"] is not None]
    summary = {
        "n_cases": len(results),
        "avg_answer_relevance": _avg("answer_relevance"),
        "avg_faithfulness": _avg("faithfulness"),
        "avg_correctness": _avg("correctness"),
        "retrieval_hit_rate": round(sum(hits) / len(hits), 2) if hits else None,
        "avg_latency_ms": _avg("latency_ms"),
    }
    return {"summary": summary, "results": results}


def _print_table(out: dict) -> None:
    print("\n" + "─" * 78)
    print(f"{'caso':<26}{'relev':>6}{'faith':>6}{'corr':>6}{'hit':>6}{'lat(ms)':>9}")
    print("─" * 78)
    for r in out["results"]:
        def f(v): return "—" if v is None else (f"{v}" if not isinstance(v, bool) else ("✓" if v else "✗"))
        print(f"{r['id'][:25]:<26}{f(r['answer_relevance']):>6}{f(r['faithfulness']):>6}"
              f"{f(r['correctness']):>6}{f(r['retrieval_hit']):>6}{r['latency_ms']:>9}")
    print("─" * 78)
    s = out["summary"]
    print(f"Relevancia media: {s['avg_answer_relevance']} | Fidelidad: {s['avg_faithfulness']} | "
          f"Correctness: {s['avg_correctness']} | Retrieval-hit: {s['retrieval_hit_rate']} | "
          f"Latencia media: {s['avg_latency_ms']}ms")
    print("─" * 78)


def main():
    parser = argparse.ArgumentParser(description="Evaluación de calidad RAG (LLM-as-judge)")
    parser.add_argument("--set", default=os.path.join(os.path.dirname(__file__), "eval_set.json"),
                        help="Ruta al JSON con los casos (default: scripts/eval_set.json)")
    parser.add_argument("-o", "--output", default=None, help="Guardar resultados en JSON")
    args = parser.parse_args()

    with open(args.set, encoding="utf-8") as f:
        eval_set = json.load(f)

    out = run_eval(eval_set)
    _print_table(out)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Resultados guardados en {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
