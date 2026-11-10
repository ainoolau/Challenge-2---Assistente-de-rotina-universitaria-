"""Treino de Adaptação de Domínio com Triplet Loss / Hard Negatives (v2)."""

import json
from pathlib import Path

from sentence_transformers import (
    InputExample,
    SentenceTransformer,
    losses,
)
from torch.utils.data import DataLoader

BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
OUTPUT_PATH = "models/MiniLM-L12-rotina-v2"
TRIPLETS_FILE = "data/finetuning/triplets_train.json"


def carregar_triplas(caminho: str) -> list[InputExample]:
    with open(caminho, encoding="utf-8") as f:
        data = json.load(f)

    exemplos = []
    for item in data:
        exemplos.append(
            InputExample(
                texts=[
                    item["anchor"],
                    item["positive"],
                    item["negative"],
                ]
            )
        )
    return exemplos


def treinar():
    print(f"[*] A carregar modelo baseline: {BASE_MODEL}...")
    model = SentenceTransformer(BASE_MODEL)

    print(f"[*] A carregar dataset de triplas de {TRIPLETS_FILE}...")
    train_examples = carregar_triplas(TRIPLETS_FILE)
    print(f"[+] Total de triplas carregadas: {len(train_examples)}")

    # DataLoader com batch size moderado para permitir bons in-batch negatives
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=8)

    # MultipleNegativesRankingLoss com triplas explícitas:
    # O modelo maximiza a similaridade com o positive e minimiza tanto com o negative
    # explícito quanto com todos os outros positivos/negativos do mesmo batch.
    train_loss = losses.MultipleNegativesRankingLoss(model=model)

    print("[*] A iniciar treino com taxa de aprendizagem controlada...")
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=3,  # 2 a 3 épocas são suficientes para evitar overfitting
        warmup_steps=int(len(train_dataloader) * 0.1),
        optimizer_params={"lr": 2e-5},  # LR baixa para não esquecer conhecimento prévio
        show_progress_bar=True,
    )

    Path(OUTPUT_PATH).mkdir(parents=True, exist_ok=True)
    model.save(OUTPUT_PATH)
    print(f"[✓] Novo modelo guardado com sucesso em: '{OUTPUT_PATH}'")


if __name__ == "__main__":
    treinar()
