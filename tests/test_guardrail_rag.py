import json
from pathlib import Path
import jsonschema


def test_guardrail_rag_results_conform_to_schema():
    schema_path = Path("tests/benchmark_result_schema.json")
    results_path = Path("reports/scenarios/guardrail_rag_results.json")

    assert results_path.exists(), "Arquivo guardrail_rag_results.json não encontrado."

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Valida estrutura completa contra o contrato oficial
    jsonschema.validate(instance=data, schema=schema)

    assert data["scenario"] == "guardrail_rag"
    assert len(data["results"]) == 12

    # Verifica que ao menos uma pergunta (GS-12) foi bloqueada sem chamar o LLM
    blocked = [r for r in data["results"] if r["guardrail"]["decision"] == "blocked"]
    assert len(blocked) >= 1
    for item in blocked:
        assert item["guardrail"]["llm_called"] is False
        assert item["abstained"] is True
        assert item["input_tokens"] == 0
        assert item["output_tokens"] == 0
        assert item["generation_latency_ms"] is None