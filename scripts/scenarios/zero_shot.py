"""Baseline zero-shot independente; requer apenas Python 3.11 e Ollama."""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_queries(path):
    """Extrai somente ID e pergunta; nunca encaminha evidências ao modelo."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("queries") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "Golden Set deve ser uma lista não vazia ou objeto com queries"
        )
    queries = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Cada pergunta deve ser um objeto")
        query_id = row.get("query_id", row.get("id"))
        question = row.get("question", row.get("query"))
        if not isinstance(query_id, str) or not query_id.strip() or query_id in seen:
            raise ValueError("IDs devem ser strings não vazias e únicas")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Pergunta inválida: {query_id}")
        seen.add(query_id)
        queries.append((query_id, question))
    return queries


def generate(question, config):
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": question}],
        "stream": False,
        "options": config["options"],
    }
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config["timeout"]) as response:
        result = json.load(response)
    answer = result["message"]["content"]
    if (
        result.get("done") is not True
        or not isinstance(answer, str)
        or not answer.strip()
    ):
        raise ValueError("Ollama retornou resposta vazia ou incompleta")
    for key in ("prompt_eval_count", "eval_count"):
        value = result.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"Contagem de tokens inválida: {key}")
    return answer, result.get("prompt_eval_count"), result.get("eval_count")


def run(queries, config):
    results = []
    for query_id, question in queries:
        row = dict(
            query_id=query_id,
            scenario="zero_shot",
            model=config["model"],
            provider="ollama",
            answer=None,
            retrieved_chunks=[],
            sources=[],
            retrieval_scores=[],
            retrieval_latency_ms=0.0,
            generation_latency_ms=0.0,
            total_latency_ms=0.0,
            input_tokens=None,
            output_tokens=None,
            abstained=None,
            status="success",
            error=None,
        )
        start = time.perf_counter()
        try:
            row["answer"], row["input_tokens"], row["output_tokens"] = generate(
                question, config
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            row["status"] = "error"
            # Não registrar corpo HTTP, URLs ou credenciais do servidor.
            row["error"] = {
                "type": type(exc).__name__,
                "message": "Falha na inferência Ollama",
            }
        row["generation_latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
        row["total_latency_ms"] = row["generation_latency_ms"]
        results.append(row)
    return results


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden-set", type=Path, default=ROOT / "tests/benchmark_llm_rag_queries.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "reports/scenarios/zero_shot_results.json"
    )
    parser.add_argument("--provider", choices=["ollama"], default="ollama")
    parser.add_argument("--model", default=os.getenv("ZERO_SHOT_MODEL"))
    parser.add_argument(
        "--base-url", default=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if not args.model:
        parser.error("Informe --model ou ZERO_SHOT_MODEL com o modelo acordado")
    if (
        not math.isfinite(args.temperature)
        or args.temperature < 0
        or not math.isfinite(args.timeout)
        or args.timeout <= 0
        or args.max_tokens <= 0
    ):
        parser.error(
            "Temperatura deve ser finita e >= 0; timeout e max-tokens devem ser positivos"
        )
    try:
        queries = load_queries(args.golden_set)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    config = dict(
        model=args.model,
        base_url=args.base_url,
        timeout=args.timeout,
        options=dict(
            temperature=args.temperature, num_predict=args.max_tokens, seed=args.seed
        ),
    )
    results = run(queries, config)
    save_json(args.output, results)
    save_json(
        args.output.with_suffix(".metadata.json"),
        {
            "created_at": datetime.now(UTC).isoformat(),
            "provider": args.provider,
            "model": args.model,
            "options": config["options"],
            "timeout_seconds": args.timeout,
            "golden_set_sha256": hashlib.sha256(
                args.golden_set.read_bytes()
            ).hexdigest(),
            "query_count": len(queries),
            "scenario": "zero_shot",
            "contract": "preliminary-task-s3-01",
        },
    )
    failures = sum(row["status"] == "error" for row in results)
    print(f"{len(results)} perguntas; {failures} erros; resultados em {args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
