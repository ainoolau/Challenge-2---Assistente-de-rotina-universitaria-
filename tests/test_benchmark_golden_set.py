"""Integridade do Golden Set e do contrato de resultados (TASK-S3-01).

Os testes estruturais não têm dependências externas. A validação contra o
JSON Schema usa `jsonschema` e é pulada se o pacote não estiver instalado.
"""

import copy
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET_PATH = ROOT / "tests" / "benchmark_llm_rag_queries.json"
SCHEMA_PATH = ROOT / "tests" / "benchmark_result_schema.json"
SAMPLES_DIR = ROOT / "data" / "samples"
CATALOG_PATH = SAMPLES_DIR / "README.md"

SCENARIOS = ("zero_shot", "retrieval_only", "naive_rag", "guardrail_rag")


@pytest.fixture(scope="module")
def golden_set() -> dict:
    return json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog() -> dict[str, str]:
    """Mapeia arquivo -> DOC-XX a partir do catálogo de data/samples."""
    text = CATALOG_PATH.read_text(encoding="utf-8")
    pairs = re.findall(r"`(DOC-\d{2})`\s*\|\s*`([^`]+)`", text)
    return {file: doc_id for doc_id, file in pairs}


# --------------------------------------------------------------------------
# Golden Set — checagens estruturais (sem dependências)
# --------------------------------------------------------------------------


def test_golden_set_has_12_queries_with_unique_sequential_ids(golden_set):
    ids = [q["query_id"] for q in golden_set["queries"]]
    assert ids == [f"GS-{i:02d}" for i in range(1, 13)]


def test_golden_set_has_11_factual_and_1_out_of_domain(golden_set):
    queries = golden_set["queries"]
    ood = [q for q in queries if q["out_of_domain"]]
    assert len(queries) - len(ood) == 11
    assert len(ood) == 1
    negative = ood[0]
    assert negative["expected_behavior"] == "abstain"
    assert negative["source_type"] == "none"
    assert negative["primary_source"] is None
    assert negative["accepted_sources"] == []
    assert negative["evidence"] == []


def test_golden_set_covers_pdf_whisper_and_ocr(golden_set):
    types = {q["source_type"] for q in golden_set["queries"] if not q["out_of_domain"]}
    assert {"pdf", "audio_whisper", "image_ocr"} <= types


def test_factual_queries_are_fully_documented(golden_set):
    for q in golden_set["queries"]:
        if q["out_of_domain"]:
            continue
        qid = q["query_id"]
        assert q["expected_behavior"] == "answer", qid
        assert q["expected_answer"].strip(), qid
        assert q["key_facts"], qid
        assert q["evidence"], qid
        assert q["expected_keywords"], qid
        assert q["behavior_if_no_evidence"].strip(), qid
        assert q["primary_source"]["file"] in q["accepted_sources"], qid


def test_source_type_matches_primary_file_extension(golden_set):
    ext_by_type = {
        "pdf": {".pdf"},
        "image_ocr": {".png", ".jpg", ".jpeg"},
        "audio_whisper": {".ogg", ".mp3", ".wav"},
    }
    for q in golden_set["queries"]:
        if q["out_of_domain"]:
            continue
        suffix = Path(q["primary_source"]["file"]).suffix.lower()
        assert suffix in ext_by_type[q["source_type"]], q["query_id"]


def test_referenced_files_exist_and_match_catalog(golden_set, catalog):
    for q in golden_set["queries"]:
        files = set(q["accepted_sources"]) | {e["file"] for e in q["evidence"]}
        for f in files:
            assert (SAMPLES_DIR / f).is_file(), f"{q['query_id']}: {f} ausente"
            assert f in catalog, f"{q['query_id']}: {f} fora do catálogo"
        if q["primary_source"]:
            ps = q["primary_source"]
            assert catalog[ps["file"]] == ps["doc_id"], q["query_id"]


def test_evidence_files_are_accepted_sources(golden_set):
    for q in golden_set["queries"]:
        for e in q["evidence"]:
            assert e["file"] in q["accepted_sources"], q["query_id"]


def test_abstention_message_is_defined(golden_set):
    assert golden_set["abstention_message"].startswith("Não encontrei")


# --------------------------------------------------------------------------
# Contrato de resultados — exemplos por cenário
# --------------------------------------------------------------------------

CHUNK = {
    "rank": 1,
    "point_id": "a1",
    "source": "edital_residencia_02.pdf",
    "chunk_index": 7,
    "task_type": "texto",
    "score": 0.71,
    "text": "O residente que acumular 3 (três) advertências será desligado do Programa.",
}

BASE_CONFIG = {
    "llm_model": "modelo-x",
    "llm_provider": "provedor-y",
    "temperature": 0.0,
    "max_output_tokens": 512,
    "prompt_template_id": "rag_v1",
    "qdrant_collection": "rotina_estudante_multimodal",
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "top_k": 3,
    "guardrail_threshold": None,
}


def _result(scenario: str, **overrides) -> dict:
    base = {
        "query_id": "GS-03",
        "scenario": scenario,
        "model": "modelo-x",
        "provider": "provedor-y",
        "answer": "Três advertências levam ao desligamento.",
        "retrieved_chunks": [CHUNK],
        "sources": ["edital_residencia_02.pdf"],
        "retrieval_scores": [0.71],
        "retrieval_latency_ms": 42.0,
        "generation_latency_ms": 800.0,
        "total_latency_ms": 850.0,
        "input_tokens": 600,
        "output_tokens": 40,
        "abstained": False,
        "guardrail": None,
        "status": "success",
        "error": None,
    }
    base.update(overrides)
    return base


def _file(scenario: str, results: list[dict], **config) -> dict:
    return {
        "contract_version": "1.0.0",
        "golden_set_version": "1.0.0",
        "scenario": scenario,
        "run_id": f"{scenario}-teste",
        "generated_at": "2026-11-12T10:00:00-03:00",
        "config": {**BASE_CONFIG, **config},
        "results": results,
    }


VALID_FILES = {
    "zero_shot": _file(
        "zero_shot",
        [
            _result(
                "zero_shot",
                retrieved_chunks=[],
                sources=[],
                retrieval_scores=[],
                retrieval_latency_ms=None,
            )
        ],
        qdrant_collection=None,
        embedding_model=None,
        top_k=None,
        prompt_template_id="zero_shot_v1",
    ),
    "retrieval_only": _file(
        "retrieval_only",
        [
            _result(
                "retrieval_only",
                model=None,
                provider=None,
                answer=None,
                generation_latency_ms=None,
                total_latency_ms=42.0,
                input_tokens=None,
                output_tokens=None,
                abstained=None,
            )
        ],
        llm_model=None,
        llm_provider=None,
        temperature=None,
        max_output_tokens=None,
        prompt_template_id=None,
    ),
    "naive_rag": _file("naive_rag", [_result("naive_rag")]),
    "guardrail_rag": _file(
        "guardrail_rag",
        [
            _result(
                "guardrail_rag",
                guardrail={
                    "threshold": 0.5,
                    "top_score": 0.71,
                    "decision": "allowed",
                    "llm_called": True,
                    "reason": None,
                },
            ),
            _result(
                "guardrail_rag",
                query_id="GS-12",
                answer=(
                    "Não encontrei informações suficientes nos documentos "
                    "disponíveis para responder a essa pergunta com segurança."
                ),
                retrieved_chunks=[{**CHUNK, "score": 0.31}],
                retrieval_scores=[0.31],
                sources=[],
                generation_latency_ms=None,
                total_latency_ms=45.0,
                input_tokens=0,
                output_tokens=0,
                abstained=True,
                guardrail={
                    "threshold": 0.5,
                    "top_score": 0.31,
                    "decision": "blocked",
                    "llm_called": False,
                    "reason": "top_score < threshold",
                },
            ),
        ],
        guardrail_threshold=0.5,
    ),
}


def test_valid_examples_respect_required_fields_and_alignment(schema):
    required = set(schema["$defs"]["result"]["required"])
    for scenario, payload in VALID_FILES.items():
        assert payload["scenario"] in SCENARIOS
        for r in payload["results"]:
            assert required <= r.keys(), scenario
            assert len(r["retrieval_scores"]) == len(r["retrieved_chunks"])


@pytest.fixture(scope="module")
def validator(schema):
    jsonschema = pytest.importorskip("jsonschema")
    cls = jsonschema.Draft202012Validator
    cls.check_schema(schema)
    return cls(schema)


@pytest.fixture(scope="module")
def golden_validator(schema):
    jsonschema = pytest.importorskip("jsonschema")
    sub = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/golden_set",
    }
    return jsonschema.Draft202012Validator(sub)


def test_golden_set_validates_against_schema(golden_validator, golden_set):
    errors = list(golden_validator.iter_errors(golden_set))
    assert not errors, [e.message for e in errors]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_valid_scenario_file_is_accepted(validator, scenario):
    errors = list(validator.iter_errors(VALID_FILES[scenario]))
    assert not errors, [e.message for e in errors]


def _mutate(base_scenario: str, index: int = 0, **changes) -> dict:
    payload = copy.deepcopy(VALID_FILES[base_scenario])
    payload["results"][index].update(changes)
    return payload


INVALID_CASES = {
    "retrieval_only_com_resposta": _mutate("retrieval_only", answer="texto"),
    "retrieval_only_com_tokens": _mutate("retrieval_only", input_tokens=10),
    "zero_shot_com_chunks": _mutate("zero_shot", retrieved_chunks=[CHUNK]),
    "naive_rag_com_4_chunks": _mutate(
        "naive_rag", retrieved_chunks=[CHUNK] * 4, retrieval_scores=[0.7] * 4
    ),
    "guardrail_sem_objeto": _mutate("guardrail_rag", guardrail=None),
    "guardrail_bloqueado_com_tokens": _mutate("guardrail_rag", 1, input_tokens=100),
    "guardrail_bloqueado_sem_abstencao": _mutate("guardrail_rag", 1, abstained=False),
    "erro_sem_detalhe": _mutate("naive_rag", status="error", answer=None),
    "erro_com_resposta": _mutate(
        "naive_rag", status="error", error={"type": "X", "message": "y"}
    ),
    "cenario_divergente": _mutate("naive_rag", scenario="zero_shot"),
    "query_id_invalido": _mutate("naive_rag", query_id="Q1"),
    "campo_faltando": {
        **VALID_FILES["naive_rag"],
        "results": [
            {
                k: v
                for k, v in VALID_FILES["naive_rag"]["results"][0].items()
                if k != "abstained"
            }
        ],
    },
}


@pytest.mark.parametrize("case", sorted(INVALID_CASES))
def test_invalid_results_are_rejected(validator, case):
    assert list(validator.iter_errors(INVALID_CASES[case])), case
