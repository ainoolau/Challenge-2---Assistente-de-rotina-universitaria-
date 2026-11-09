"""Demonstração de recuperação na base vetorial (RAG – etapa de busca).

Uso:
    python scripts/demo_retrieval.py                          # modo interativo
    python scripts/demo_retrieval.py "Quais aulas tenho na quarta-feira?"
    python scripts/demo_retrieval.py --ensaio                 # roda as perguntas de ensaio
    python scripts/demo_retrieval.py --offline ...            # sem internet (modelo em cache)

Para cada pergunta: gera o embedding com all-MiniLM-L6-v2, busca os 3 trechos
mais próximos no Qdrant e imprime score, arquivo de origem e trecho exato.
O tempo exibido é o da consulta (embedding + busca), com o modelo já carregado.

Pré-requisito: base populada pela ingestão (TASK-03):
    python -m src.data_pipeline.ingestion
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

INGEST_HINT = "Rode a ingestão primeiro (TASK-03):\n    python -m src.data_pipeline.ingestion"

DEFAULT_ENSAIO_FILE = Path(__file__).with_name("demo_questions.json")
LATENCY_TARGET_S = 1.0
WIDTH = 88


def _configure_env(offline: bool) -> None:
    # Precisa acontecer antes de importar transformers/sentence-transformers.
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _wrap(text: str, indent: str = "    ") -> str:
    lines = []
    for line in text.splitlines() or [""]:
        lines.append(
            textwrap.fill(line, width=WIDTH, initial_indent=indent, subsequent_indent=indent)
            if line.strip()
            else indent.rstrip()
        )
    return "\n".join(lines)


def print_results(question: str, hits, elapsed_s: float) -> None:
    print("=" * WIDTH)
    print(f"PERGUNTA: {question}")
    status = "ok" if elapsed_s < LATENCY_TARGET_S else "ACIMA DA META"
    print(
        f"Tempo da consulta: {elapsed_s * 1000:.0f} ms ({status}, meta < {LATENCY_TARGET_S:.0f} s)"
    )
    print("=" * WIDTH)
    if not hits:
        print(f"Nenhum trecho encontrado. A collection está vazia? {INGEST_HINT}")
        return
    for rank, hit in enumerate(hits, start=1):
        details = [f"tipo: {hit.task_type}"] if hit.task_type else []
        if hit.chunk_index is not None:
            details.append(f"trecho nº {hit.chunk_index}")
        location = hit.source + (f" ({', '.join(details)})" if details else "")
        print(f"\n#{rank}  Similaridade (cosseno): {hit.score:.4f}")
        print(f"    Fonte: {location}")
        print("    Trecho:")
        print(_wrap(hit.text, indent="      | "))
    print()


def run_query(client, model, question: str, top_k: int, collection: str):
    from data_pipeline.retrieval import search

    start = time.perf_counter()
    hits = search(client, model, question, top_k=top_k, collection=collection)
    return hits, time.perf_counter() - start


def run_ensaio(client, model, path: Path, top_k: int, collection: str) -> int:
    """Roda as perguntas de ensaio e confere se a fonte esperada aparece no top-k."""
    from data_pipeline.retrieval import expected_rank

    if not path.exists():
        print(f"Arquivo de ensaio não encontrado: {path}", file=sys.stderr)
        return 1
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        question = case["pergunta"]
        expected = case.get("fonte_esperada")
        expected_text = case.get("trecho_esperado")
        hits, elapsed = run_query(client, model, question, top_k, collection)
        print_results(question, hits, elapsed)

        rank = expected_rank(hits, expected, expected_text)
        results.append((question, rank, elapsed))

    print("=" * WIDTH)
    print("RESUMO DO ENSAIO")
    print("=" * WIDTH)
    passed = 0
    for question, rank, elapsed in results:
        ok = rank is not None and elapsed < LATENCY_TARGET_S
        passed += ok
        found = f"esperado em #{rank}" if rank else "esperado NÃO recuperado"
        label = "OK   " if ok else "FALHA"
        print(f"  [{label}] {elapsed * 1000:5.0f} ms  {found:24}  {question}")
    criterion = f"trecho esperado no top-{top_k} e < {LATENCY_TARGET_S:.0f} s"
    print(f"\n{passed}/{len(results)} perguntas aprovadas ({criterion}).")
    return 0 if passed == len(results) else 2


def interactive(client, model, top_k: int, collection: str) -> None:
    print("Digite uma pergunta (Enter vazio ou 'sair' para encerrar).\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question or question.lower() in {"sair", "exit", "quit"}:
            return
        hits, elapsed = run_query(client, model, question, top_k, collection)
        print_results(question, hits, elapsed)


def main() -> int:
    # Acentos corretos no terminal do Windows, inclusive no --help.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "pergunta",
        nargs="*",
        help="pergunta em linguagem natural (sem ela, abre o modo interativo)",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--collection",
        default=None,
        help="padrão: QDRANT_COLLECTION ou 'rotina_estudante_multimodal'",
    )
    parser.add_argument(
        "--ensaio",
        nargs="?",
        const=DEFAULT_ENSAIO_FILE,
        type=Path,
        help="roda as perguntas de ensaio",
    )
    parser.add_argument(
        "--offline", action="store_true", help="usa só o modelo em cache, sem acessar a internet"
    )
    args = parser.parse_args()

    _configure_env(args.offline)
    print("Carregando modelo de embeddings e base vetorial...", flush=True)
    load_start = time.perf_counter()
    from data_pipeline.retrieval import DEFAULT_COLLECTION, get_client, load_embedder

    collection = args.collection or DEFAULT_COLLECTION
    try:
        client = get_client()
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1
    except RuntimeError as err:  # modo local: pasta aberta por outro processo
        print(f"Não foi possível abrir a base: {err}", file=sys.stderr)
        return 1
    if not client.collection_exists(collection):
        print(f"Collection '{collection}' não existe. {INGEST_HINT}", file=sys.stderr)
        client.close()
        return 1
    model = load_embedder()
    count = client.count(collection).count
    model.encode(["aquecimento"], normalize_embeddings=True)  # primeira chamada é mais lenta
    load_s = time.perf_counter() - load_start
    print(f"Pronto em {load_s:.1f}s. Collection '{collection}': {count} trechos.\n")

    try:
        if args.ensaio:
            return run_ensaio(client, model, args.ensaio, args.top_k, collection)
        if args.pergunta:
            question = " ".join(args.pergunta)
            hits, elapsed = run_query(client, model, question, args.top_k, collection)
            print_results(question, hits, elapsed)
            return 0
        interactive(client, model, args.top_k, collection)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
