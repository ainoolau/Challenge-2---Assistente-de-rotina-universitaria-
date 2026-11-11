"""Baseline zero-shot independente; requer Python 3.11, jsonschema e Groq/Ollama."""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import jsonschema

ROOT = Path(__file__).resolve().parents[2]


class IncompleteGenerationError(ValueError):
    """Resposta rejeitada por término incompleto, sem registrar conteúdo remoto."""


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


def generate_ollama(question, config):
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


def generate_groq(question, config):
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": question}],
        "temperature": config["options"]["temperature"],
        "seed": config["options"]["seed"],
        "max_completion_tokens": config["options"]["num_predict"],
        "reasoning_effort": config["reasoning_effort"],
        "include_reasoning": False,
        "stream": False,
        "tool_choice": "none",
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
            "User-Agent": "vezo-benchmark/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config["timeout"]) as response:
        result = json.load(response)
    choice = result["choices"][0]
    answer = choice["message"]["content"]
    if choice.get("finish_reason") != "stop":
        raise IncompleteGenerationError(
            "Groq retornou geração incompleta ou chamada de ferramenta"
        )
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Groq retornou resposta vazia")
    usage = result.get("usage") or {}
    for key in ("prompt_tokens", "completion_tokens"):
        value = usage.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Groq retornou contagem de tokens inválida")
    return answer, usage.get("prompt_tokens"), usage.get("completion_tokens")


def generate(question, config):
    if config.get("provider", "ollama") == "groq":
        return generate_groq(question, config)
    return generate_ollama(question, config)


def load_api_key(path):
    """Carrega somente GROQ_API_KEY de arquivo explicitamente indicado."""
    if os.environ.get("GROQ_API_KEY"):
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key == "GROQ_API_KEY":
            os.environ[key] = value.strip().strip("\"'")
            return


def run(queries, config):
    results = []
    for query_id, question in queries:
        row = dict(
            query_id=query_id,
            scenario="zero_shot",
            model=config["model"],
            provider=config.get("provider", "ollama"),
            answer=None,
            retrieved_chunks=[],
            sources=[],
            retrieval_scores=[],
            retrieval_latency_ms=None,
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
            row["abstained"] = detects_abstention(row["answer"])
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ) as exc:
            row["status"] = (
                "timeout"
                if isinstance(exc, TimeoutError)
                or isinstance(getattr(exc, "reason", None), TimeoutError)
                else "error"
            )
            # Não registrar corpo HTTP, URLs ou credenciais do servidor.
            row["error"] = {
                "type": type(exc).__name__,
                "message": (
                    "Geração incompleta; confira o limite de tokens. "
                    if isinstance(exc, IncompleteGenerationError)
                    else ""
                )
                + "Falha na inferência "
                + config.get("provider", "ollama")
                + (
                    f" (HTTP {exc.code})"
                    if isinstance(exc, urllib.error.HTTPError)
                    else ""
                ),
            }
        row["generation_latency_ms"] = round((time.perf_counter() - start) * 1000, 3)
        row["total_latency_ms"] = row["generation_latency_ms"]
        results.append(row)
    return results


def detects_abstention(answer):
    """Heurística conservadora, revisável na avaliação; não consulta gabaritos."""
    return bool(
        re.search(
            r"\b(não (?:sei|tenho (?:acesso|informações|conhecimento)|posso (?:confirmar|responder))"
            r"|não (?:encontrei|disponho de) informações|i (?:do not|don't) know)\b",
            answer,
            re.IGNORECASE,
        )
    )


def build_report(results, golden_set, config, schema):
    report = {
        "contract_version": schema["x-contract-version"],
        "golden_set_version": golden_set["version"],
        "scenario": "zero_shot",
        "run_id": "zero_shot-" + uuid4().hex,
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "llm_model": config["model"],
            "llm_provider": config.get("provider", "ollama"),
            "reasoning_effort": config.get("reasoning_effort")
            if config.get("provider") == "groq"
            else None,
            "tools_enabled": False,
            "retries": 0,
            "temperature": config["options"]["temperature"],
            "max_output_tokens": config["options"]["num_predict"],
            "prompt_template_id": "zero_shot-question-only-v1",
            "qdrant_collection": None,
            "embedding_model": None,
            "top_k": None,
            "guardrail_threshold": None,
            "seed": config["options"]["seed"],
            "timeout_seconds": config["timeout"],
            "golden_set_status": golden_set["status"],
            "golden_set_sha256": config["golden_set_sha256"],
            "abstention_detection": "explicit-refusal-heuristic-v1; manual review required",
        },
        "results": results,
    }
    jsonschema.validate(report, schema)
    return report


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
    parser.add_argument(
        "--schema", type=Path, default=ROOT / "tests/benchmark_result_schema.json"
    )
    parser.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    parser.add_argument("--model", default=os.getenv("ZERO_SHOT_MODEL"))
    parser.add_argument(
        "--base-url", default=os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    parser.add_argument("--env-file", type=Path, help="Arquivo local com GROQ_API_KEY")
    parser.add_argument(
        "--reasoning-effort", choices=["low", "medium", "high"], default="low"
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args(argv)
    if args.provider == "groq":
        args.model = args.model or "openai/gpt-oss-20b"
        if args.base_url != "http://localhost:11434":
            parser.error("--base-url/OLLAMA_HOST aplica-se apenas ao Ollama")
        if args.env_file:
            try:
                load_api_key(args.env_file)
            except OSError:
                parser.error("Não foi possível ler --env-file")
        if not os.environ.get("GROQ_API_KEY", "").strip():
            parser.error("Configure GROQ_API_KEY no ambiente ou --env-file local")
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
        if args.output.resolve() in (args.golden_set.resolve(), args.schema.resolve()):
            parser.error("A saída não pode substituir o Golden Set ou schema")
        raw_golden = args.golden_set.read_bytes()
        golden_set = json.loads(raw_golden)
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(
            golden_set, {"$ref": "#/$defs/golden_set", "$defs": schema["$defs"]}
        )
        queries = load_queries(args.golden_set)
        if len(queries) != 12:
            raise ValueError("O Golden Set oficial deve conter 12 perguntas")
    except (
        OSError,
        ValueError,
        jsonschema.ValidationError,
        jsonschema.SchemaError,
    ) as exc:
        parser.error(str(exc))
    config = dict(
        golden_set_sha256=hashlib.sha256(raw_golden).hexdigest(),
        provider=args.provider,
        reasoning_effort=args.reasoning_effort,
        model=args.model,
        base_url=args.base_url,
        timeout=args.timeout,
        options=dict(
            temperature=args.temperature, num_predict=args.max_tokens, seed=args.seed
        ),
    )
    results = run(queries, config)
    report = build_report(results, golden_set, config, schema)
    save_json(args.output, report)
    failures = sum(row["status"] != "success" for row in results)
    print(f"{len(results)} perguntas; {failures} erros; resultados em {args.output}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
