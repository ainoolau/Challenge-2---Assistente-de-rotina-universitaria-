"""Script de Avaliação Formal de Retrieval (Evaluation Benchmark Completo)."""

import json
import time
import warnings
from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "rotina_estudante_multimodal"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Limiar de similaridade para considerar uma resposta confiável (Confidence Threshold)
SIMILARITY_THRESHOLD = 0.50

EVAL_DATASET = [
    # --- BLOCO A: HOMOLOGAÇÃO FUNCIONAL MULTIMODAL ---
    {
        "query": "Quais são as regras de frequência e bolsa da residência?",
        "expected_source": "edital_residencia_02.pdf",
        "expected_keywords": ["responsabilidades", "bolsa", "frequência", "cumprir"],
        "category": "Regras Formais / Bolsa",
        "is_negative": False,
    },
    {
        "query": "Quais são as regras para retirada e devolução de equipamentos?",
        "expected_source": "edital_residencia_02.pdf",
        "expected_keywords": ["retirada", "devolução", "equipamento", "avaria"],
        "category": "Regras Formais / Equipamentos",
        "is_negative": False,
    },
    {
        "query": "Quantas advertências levam ao desligamento da residência?",
        "expected_source": "edital_residencia_02.pdf",
        "expected_keywords": ["advertências", "desligado", "limite"],
        "category": "Regras Formais / Sanções",
        "is_negative": False,
    },
    {
        "query": "Quando é a aula de Econometria?",
        "expected_source": "perfis_rotina_forms.txt",
        "expected_keywords": ["Econometria", "08h às 09h50", "Ter/Qui"],
        "category": "Horários / Disciplinas",
        "is_negative": False,
    },
    {
        "query": "Quais dias o aluno vai para a academia e pratica exercícios?",
        "expected_source": "audio_rotina_03.wav",
        "expected_keywords": ["academia", "noite", "rotina"],
        "category": "Rotina Pessoal / Áudio",
        "is_negative": False,
    },
    {
        "query": "Como o estudante divide a rotina matinal com a residência e tarefas?",
        "expected_source": "audio_rotina_01.ogg",
        "expected_keywords": ["seis horas", "manhã", "residência"],
        "category": "Rotina Pessoal / Áudio",
        "is_negative": False,
    },
    {
        "query": "Componentes curriculares do tipo atividade exigem dedicação integral?",
        "expected_source": "grade_aluno_06.jpg",
        "expected_keywords": ["dedicação", "período integral", "atividade"],
        "category": "Grades / Avisos / OCR",
        "is_negative": False,
    },
    {
        "query": "Como funciona o revezamento dos monitores nas aulas práticas?",
        "expected_source": "comunicado_monitoria_05.jpg",
        "expected_keywords": ["revezar", "aulas práticas", "monitores"],
        "category": "Grades / Avisos / OCR",
        "is_negative": False,
    },
    # --- BLOCO B: ROBUSTEZ, PARÁFRASE E CASO NEGATIVO (ANTI-OVERFITTING) ---
    {
        "query": (
            "Disciplinas classificadas como atividades precisam de dedicação "
            "integral mesmo sem horário fixo?"
        ),
        "expected_source": "grade_aluno_06.jpg",
        "expected_keywords": ["dedicação", "período integral"],
        "category": "Robustez / Paráfrase OCR",
        "is_negative": False,
    },
    {
        "query": "Em quais dias da semana tem treino de musculação ou esportes?",
        "expected_source": "audio_rotina_03.wav",
        "expected_keywords": ["academia", "noite"],
        "category": "Robustez / Paráfrase Áudio",
        "is_negative": False,
    },
    {
        "query": "Qual o maior gargalo relatado na gestão da rotina do aluno?",
        "expected_source": "perfis_rotina_forms.txt",
        "expected_keywords": ["gargalo", "conflito", "rotina"],
        "category": "Robustez / Formulários",
        "is_negative": False,
    },
    {
        "query": "Qual é a nota de corte do vestibular de Medicina da UnB?",
        "expected_source": None,
        "expected_keywords": [],
        "category": "Caso Negativo / Fora de Escopo",
        "is_negative": True,
    },
]


def run_evaluation():
    print("=" * 75)
    print("   BENCHMARK FORMAL DE RETRIEVAL — HOMOLOGAÇÃO & ROBUSTEZ")
    print(f"   Coleção: {COLLECTION_NAME} | Modelo: {MODEL_NAME}")
    print("=" * 75)

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    model = SentenceTransformer(MODEL_NAME)

    latencies = []
    reciprocal_ranks = []
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    keyword_hits = 0
    negative_abstained = 0

    valid_queries_count = sum(1 for q in EVAL_DATASET if not q["is_negative"])
    negative_queries_count = sum(1 for q in EVAL_DATASET if q["is_negative"])

    print(
        f"[*] Executando {len(EVAL_DATASET)} queries "
        f"({valid_queries_count} factuais + {negative_queries_count} fora de escopo)...\n"
    )

    for idx, item in enumerate(EVAL_DATASET, start=1):
        query = item["query"]
        expected_src = item["expected_source"]
        expected_kws = item["expected_keywords"]
        category = item["category"]
        is_negative = item["is_negative"]

        t0 = time.perf_counter()
        query_vector = model.encode(query).tolist()

        try:
            response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=5,
                with_payload=True,
            )
            points = response.points
        except AttributeError:
            points = client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=5,
                with_payload=True,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        top_score = points[0].score if points else 0.0

        if is_negative:
            status = (
                "ABSTENÇÃO CORRETA" if top_score < SIMILARITY_THRESHOLD else "ALERTA: SCORE ELEVADO"
            )
            if top_score < SIMILARITY_THRESHOLD:
                negative_abstained += 1
            top1_source = Path(points[0].payload.get("source", "")).name if points else "Nenhum"
            print(f"[{idx}] {category}")
            print(f"    Query: '{query}'")
            print(
                f"    Top Score: {top_score:.3f} | Status: {status} | Latência: {elapsed_ms:.1f}ms"
            )
            print(f"    Top-1 Recuperado: {top1_source}\n")
            continue

        found_rank = None
        retrieved_summary = []
        found_relevant_keyword = False

        for rank, p in enumerate(points, start=1):
            src = Path(p.payload.get("source", "")).name
            chunk_idx = p.payload.get("chunk_index", p.payload.get("chunk_id", "?"))
            score = p.score
            text = p.payload.get("text", "")

            retrieved_summary.append(f"#{rank} {src}[c{chunk_idx}] ({score:.3f})")

            if expected_src in src and found_rank is None:
                found_rank = rank
                if rank <= 3 and any(kw.lower() in text.lower() for kw in expected_kws):
                    found_relevant_keyword = True

        rr = 1.0 / found_rank if found_rank else 0.0
        reciprocal_ranks.append(rr)

        if found_rank == 1:
            hits_at_1 += 1
        if found_rank and found_rank <= 3:
            hits_at_3 += 1
        if found_rank and found_rank <= 5:
            hits_at_5 += 1
        if found_relevant_keyword:
            keyword_hits += 1

        status = f"HIT (Rank #{found_rank})" if found_rank else "MISS"
        print(f"[{idx}] {category}")
        print(f"    Query: '{query}'")
        print(f"    Esperado: {expected_src} | Status: {status} | Latência: {elapsed_ms:.1f}ms")
        print(f"    Top-5: {', '.join(retrieved_summary)}")
        match_flag = "SIM" if found_relevant_keyword else "NÃO"
        print(f"    Termo Chave no Chunk Correto (Top-3): {match_flag}\n")

    mrr = sum(reciprocal_ranks) / valid_queries_count
    hit_rate_1 = (hits_at_1 / valid_queries_count) * 100
    hit_rate_3 = (hits_at_3 / valid_queries_count) * 100
    hit_rate_5 = (hits_at_5 / valid_queries_count) * 100
    keyword_match_rate = (keyword_hits / valid_queries_count) * 100
    avg_latency = sum(latencies) / len(EVAL_DATASET)

    print("=" * 75)
    print("   RESULTADOS CONSOLIDADOS DO BENCHMARK (HOMOLOGAÇÃO + ROBUSTEZ)")
    print("=" * 75)
    print(f"   • Total de Queries Factuais:                  {valid_queries_count}")
    print(
        f"   • Hit Rate @ 1:                               "
        f"{hit_rate_1:.1f}% ({hits_at_1}/{valid_queries_count})"
    )
    print(
        f"   • Hit Rate @ 3 (Top-K padrão):                "
        f"{hit_rate_3:.1f}% ({hits_at_3}/{valid_queries_count})"
    )
    print(
        f"   • Hit Rate @ 5:                               "
        f"{hit_rate_5:.1f}% ({hits_at_5}/{valid_queries_count})"
    )
    print(
        f"   • Taxa de Match de Termos Chave no Top-3:     "
        f"{keyword_match_rate:.1f}% ({keyword_hits}/{valid_queries_count})"
    )
    print(f"   • MRR (Mean Reciprocal Rank):                 {mrr:.4f}")
    print(
        f"   • Queries Negativas (Abstenção):              "
        f"{negative_abstained}/{negative_queries_count}"
    )
    print(f"   • Latência Média Geral de Retrieval:          {avg_latency:.1f} ms")
    print("=" * 75)

    Path("reports").mkdir(exist_ok=True)
    with open("reports/evaluation_summary.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_factual_queries": valid_queries_count,
                "hit_rate_at_1": hit_rate_1,
                "hit_rate_at_3": hit_rate_3,
                "hit_rate_at_5": hit_rate_5,
                "keyword_match_rate_at_3": keyword_match_rate,
                "mrr": round(mrr, 4),
                "negative_cases_tested": negative_queries_count,
                "avg_latency_ms": round(avg_latency, 2),
                "collection": COLLECTION_NAME,
                "model": MODEL_NAME,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print("[✓] Relatório consolidado exportado: reports/evaluation_summary.json\n")


if __name__ == "__main__":
    run_evaluation()
