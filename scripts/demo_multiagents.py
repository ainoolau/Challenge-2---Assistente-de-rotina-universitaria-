"""CLI multiagentes; padrão simulado, sem chamadas externas."""

import argparse
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pydantic import ValidationError  # noqa: E402

from scripts.scenarios.zero_shot import load_api_key  # noqa: E402
from src.agents.analysis_planning_agent import AnalysisPlanningAgent  # noqa: E402
from src.agents.demo import QUESTIONS, SimulatedLLM, SimulatedRetriever, demo_request  # noqa: E402
from src.agents.llm import GroqLLM, LLMConfig  # noqa: E402
from src.agents.orchestrator import MultiAgentOrchestrator  # noqa: E402
from src.agents.research_agent import QdrantRetriever, ResearchAgent  # noqa: E402
from src.agents.schemas import AgentRequest  # noqa: E402
from src.agents.validation_agent import ValidationAgent  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["simulated", "live"], default="simulated")
    parser.add_argument("--scenario", choices=["all", *QUESTIONS], default="all")
    parser.add_argument(
        "--request", type=Path, help="AgentRequest JSON; substitui os cenários"
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--qdrant-path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/multiagents")
    parser.add_argument("--model", default="openai/gpt-oss-20b")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument(
        "--min-call-interval",
        type=float,
        default=15.0,
        help="Segundos entre chamadas LLM; pacing para cotas da API",
    )
    parser.add_argument("--threshold", type=float, default=0.50)
    args = parser.parse_args(argv)
    if (
        args.max_tokens < 1
        or not -1 <= args.threshold <= 1
        or not math.isfinite(args.min_call_interval)
        or not 0 <= args.min_call_interval <= 60
    ):
        parser.error(
            "max-tokens deve ser positivo; threshold em [-1,1]; intervalo finito em [0,60]"
        )
    try:
        if args.request:
            requests = [
                ("custom", AgentRequest.model_validate_json(args.request.read_text()))
            ]
        else:
            requests = [
                (name, demo_request(name))
                for name in QUESTIONS
                if args.scenario in ("all", name)
            ]
        if args.env_file:
            load_api_key(args.env_file)
    except (OSError, ValueError, ValidationError, KeyError):
        parser.error(
            "Entrada ou arquivo de configuração inválido; confira formato e caminhos"
        )
    if (
        args.mode == "live"
        and any(name != "correcao" for name, _ in requests)
        and not os.environ.get("GROQ_API_KEY")
    ):
        parser.error("GROQ_API_KEY ausente; use --env-file ou configure o ambiente")
    live_llm = GroqLLM(
        LLMConfig(
            model=args.model,
            max_tokens=args.max_tokens,
            min_call_interval=args.min_call_interval,
        )
    )
    live_retriever = None
    results = []
    try:
        for name, request in requests:
            mode = "simulated" if name == "correcao" else args.mode
            if mode == "live":
                if live_retriever is None:
                    live_retriever = QdrantRetriever(args.qdrant_path)
                llm = live_llm
                retriever = live_retriever
            else:
                llm, retriever = (
                    SimulatedLLM(force_correction=name == "correcao"),
                    SimulatedRetriever(),
                )
            runner = MultiAgentOrchestrator(
                ResearchAgent(retriever, llm, args.threshold),
                AnalysisPlanningAgent(llm),
                ValidationAgent(llm),
                llm,
                mode=mode,
                config={
                    "scenario": name,
                    "data_classification": "fictional_demo"
                    if name != "custom"
                    else "user_supplied",
                    "agenda_persisted": False,
                    "retrieval_collection": "rotina_estudante_multimodal"
                    if mode == "live"
                    else None,
                    "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                    if mode == "live"
                    else None,
                },
            )
            result = runner.run(request)
            destination = args.output_dir / mode / request.run_id / f"{name}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result.model_dump_json(indent=2) + "\n")
            results.append(result)
            print(
                f"{name}: {mode}, {result.status}, {result.metrics.llm_calls} chamadas; {destination}"
            )
    except Exception as exc:
        print(
            f"Falha ao preparar ambiente: {type(exc).__name__}. Confira configuração local.",
            file=sys.stderr,
        )
        return 2
    finally:
        if live_retriever:
            live_retriever.close()
    return 1 if any(r.status == "error" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
