"""Testes sem LLM, rede ou dependências RAG."""

import json
import sys
from unittest.mock import patch

import pytest

from scripts.scenarios import zero_shot as zs


@pytest.fixture
def config():
    return dict(
        model="test-model",
        base_url="http://localhost:11434",
        timeout=1,
        options=dict(temperature=0, num_predict=32, seed=42),
    )


def test_only_question_is_sent(tmp_path, config):
    source = tmp_path / "queries.json"
    source.write_text(
        json.dumps(
            [
                dict(
                    query_id="q1",
                    question="Pergunta?",
                    expected_answer="SEGREDO",
                    evidence="DOCUMENTO",
                )
            ]
        )
    )
    queries = zs.load_queries(source)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return json.dumps(
                dict(
                    done=True,
                    message=dict(content="Resposta"),
                    prompt_eval_count=5,
                    eval_count=2,
                )
            ).encode()

    with patch.object(zs.urllib.request, "urlopen", return_value=Response()) as request:
        rows = zs.run(queries, config)
    payload = json.loads(request.call_args.args[0].data)
    assert payload["messages"] == [dict(role="user", content="Pergunta?")]
    assert payload["options"] == config["options"]
    assert rows[0]["answer"] == "Resposta"
    assert rows[0]["input_tokens"] == 5
    assert rows[0]["retrieved_chunks"] == rows[0]["sources"] == []
    assert rows[0]["retrieval_latency_ms"] is None
    assert rows[0]["abstained"] is False
    assert not any(
        name.startswith(("qdrant_client", "data_pipeline")) for name in sys.modules
    )


def test_failure_continues_and_tokens_can_be_missing(config):
    with patch.object(zs, "generate", side_effect=[TimeoutError(), ("ok", None, None)]):
        rows = zs.run([("q1", "a"), ("q2", "b")], config)
    assert [r["status"] for r in rows] == ["timeout", "success"]
    assert rows[0]["answer"] is None
    assert rows[0]["error"]["type"] == "TimeoutError"
    assert all(r["total_latency_ms"] >= 0 for r in rows)


@pytest.mark.parametrize(
    "data",
    [[], [{"query_id": "q", "question": ""}], [{"query_id": "q", "question": "a"}] * 2],
)
def test_invalid_golden_set(tmp_path, data):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        zs.load_queries(path)


def test_cli_exports_all_twelve(tmp_path):
    output = tmp_path / "results.json"
    with patch.object(zs, "generate", return_value=("Resposta", 10, 20)):
        code = zs.main(
            [
                "--model",
                "test",
                "--golden-set",
                str(zs.ROOT / "tests/benchmark_llm_rag_queries.json"),
                "--output",
                str(output),
            ]
        )
    report = json.loads(output.read_text())
    rows = report["results"]
    assert report["golden_set_version"] == "1.0.0"
    assert code == 0
    assert len(rows) == 12
    assert len({r["query_id"] for r in rows}) == 12
    assert set(rows[0]) == set(
        "query_id scenario model provider answer retrieved_chunks sources retrieval_scores retrieval_latency_ms generation_latency_ms total_latency_ms input_tokens output_tokens abstained status error".split()
    )
    assert report["config"]["golden_set_sha256"]
    assert report["config"]["qdrant_collection"] is None


def test_cli_failure_exit(tmp_path):
    with patch.object(zs, "generate", side_effect=TimeoutError()):
        code = zs.main(
            [
                "--model",
                "test",
                "--golden-set",
                str(zs.ROOT / "tests/benchmark_llm_rag_queries.json"),
                "--output",
                str(tmp_path / "errors.json"),
            ]
        )
    assert code == 1


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("Não sei a resposta.", True),
        ("Não tenho acesso às informações necessárias.", True),
        ("Não posso confirmar esse horário.", True),
        ("A aula começa às 8h.", False),
    ],
)
def test_abstention_heuristic(answer, expected):
    assert zs.detects_abstention(answer) is expected


def test_invalid_contract_before_inference(tmp_path):
    golden = tmp_path / "invalid.json"
    golden.write_text('{"queries": []}')
    with patch.object(zs, "generate") as generate, pytest.raises(SystemExit) as error:
        zs.main(
            [
                "--model",
                "test",
                "--golden-set",
                str(golden),
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
    assert error.value.code == 2
    generate.assert_not_called()
