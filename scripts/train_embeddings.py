"""Pipeline de fine-tuning para Bi-Encoder com Sentence Transformers."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import torch
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
)
from sentence_transformers.losses import MultipleNegativesRankingLoss
from sentence_transformers.training_args import BatchSamplers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Configurações de caminhos e infraestrutura
BASE_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
TRIPLETS_PATH = Path("data/finetuning/triplets_train.json")
OUTPUT_DIR = Path("models/MiniLM-L12-rotina-v1")
TRAIN_RATIO = 0.85
SEED = 42


def load_dataset(
    file_path: Path, train_ratio: float, seed: int
) -> tuple[Dataset, Dataset]:
    """Carrega os trios JSON e faz o split determinístico treino/validação."""
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo de trios não encontrado em: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    anchors = [str(item["anchor"]).strip() for item in data]
    positives = [str(item["positive"]).strip() for item in data]
    negatives = [str(item["negative"]).strip() for item in data]

    raw_dataset = Dataset.from_dict(
        {
            "anchor": anchors,
            "positive": positives,
            "negative": negatives,
        }
    )

    split_dataset = raw_dataset.train_test_split(
        test_size=(1.0 - train_ratio),
        shuffle=True,
        seed=seed,
    )
    return split_dataset["train"], split_dataset["test"]


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Dispositivo selecionado: %s", device)
    if device == "cuda":
        logger.info("GPU detectada: %s", torch.cuda.get_device_name(0))

    logger.info("Carregando trios de: %s", TRIPLETS_PATH)
    train_dataset, val_dataset = load_dataset(
        file_path=TRIPLETS_PATH,
        train_ratio=TRAIN_RATIO,
        seed=SEED,
    )
    logger.info(
        "Amostras separadas com sucesso | Treino: %d | Validação: %d",
        len(train_dataset),
        len(val_dataset),
    )

    logger.info("Carregando modelo base: %s", BASE_MODEL_NAME)
    model = SentenceTransformer(BASE_MODEL_NAME, device=device)

    # Loss: MultipleNegativesRankingLoss avalia os pares positivos contra negativos do trio e in-batch
    loss = MultipleNegativesRankingLoss(model)

    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temp_checkpoint_dir = OUTPUT_DIR / "_checkpoints"

    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(temp_checkpoint_dir),
        num_train_epochs=5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=2e-5,
        warmup_ratio=0.10,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=1,
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=SEED,
        report_to="none",
    )

    trainer = SentenceTransformerTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        loss=loss,
    )

    logger.info("Iniciando treinamento...")
    trainer.train()

    logger.info("Salvando modelo final afinado em: %s", OUTPUT_DIR)
    model.save_pretrained(str(OUTPUT_DIR))
    logger.info("Treinamento finalizado com sucesso!")


if __name__ == "__main__":
    main()
