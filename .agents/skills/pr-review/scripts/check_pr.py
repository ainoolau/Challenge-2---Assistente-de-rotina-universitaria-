"""Helper local de pre-CI e inspecao de escopo para a skill pr-review."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

EXTENSOES_PESOS_MODELOS = (
    ".bin",
    ".pt",
    ".pth",
    ".gguf",
    ".safetensors",
    ".onnx",
)
EXTENSOES_MIDIA_LGPD = (
    ".tar.gz",
    ".zip",
    ".wav",
    ".mp3",
    ".m4a",
    ".pdf",
)
LIMITE_MB = 10.0

LIGHT_TEST_SUITE = [
    "tests/test_smoke.py",
    "tests/test_benchmark_golden_set.py",
    "tests/test_zero_shot.py",
    "tests/test_chunking_structural.py",
    "tests/test_planning_core.py",
    "tests/test_multiagents.py",
    "tests/test_api.py",
]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def show_diff_scope(base: str) -> None:
    print(f"=== ESCOPO DO PR ({base}...HEAD) ===")
    result = _run(["git", "diff", "--name-status", f"{base}...HEAD"])
    if result.returncode != 0:
        print(
            f"[AVISO] Nao foi possivel comparar com '{base}': {result.stderr.strip()}"
        )
        return
    output = result.stdout.strip()
    print(output if output else "(Nenhuma diferenca commitada em relacao a base)")
    print()


def check_guardrails() -> tuple[bool, list[str]]:
    violacoes: list[str] = []

    listed = _run(["git", "ls-files", "--cached", "--others", "--exclude-standard"])
    if listed.returncode == 0:
        candidate_paths = [
            ROOT / line.strip() for line in listed.stdout.splitlines() if line.strip()
        ]
    else:
        candidate_paths = [
            p
            for p in ROOT.rglob("*")
            if not any(
                ignored in [part.lower() for part in p.relative_to(ROOT).parts]
                for ignored in (
                    ".git",
                    ".venv",
                    "node_modules",
                    ".next",
                    "__pycache__",
                    "models",
                )
            )
        ]

    for path in candidate_paths:
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        nome = path.name.lower()
        tamanho_mb = path.stat().st_size / (1024 * 1024)
        caminho_posix = rel.as_posix().lower()

        if any(nome.endswith(ext) for ext in EXTENSOES_PESOS_MODELOS):
            violacoes.append(f"Peso de modelo detectado: {rel.as_posix()}")
            continue

        if caminho_posix.startswith("data/samples/"):
            continue

        if any(nome.endswith(ext) for ext in EXTENSOES_MIDIA_LGPD):
            violacoes.append(
                f"Extensao bloqueada fora de data/samples (LGPD/Midia): {rel.as_posix()}"
            )
        elif tamanho_mb > LIMITE_MB:
            violacoes.append(
                f"Arquivo excede limite seguro ({LIMITE_MB}MB): "
                f"{rel.as_posix()} ({tamanho_mb:.2f}MB)"
            )

    tracked = _run(["git", "ls-files"])
    if tracked.returncode == 0:
        for line in tracked.stdout.splitlines():
            posix = line.strip().lower()
            if posix == ".env" or (
                posix.startswith(".env.") and posix != ".env.example"
            ):
                violacoes.append(f"Arquivo de segredos versionado: {line}")
            if posix.startswith("reports/multiagents/"):
                violacoes.append(f"Trace privado versionado: {line}")
            if posix.startswith("data/qdrant/"):
                violacoes.append(f"Banco Qdrant local versionado: {line}")

    return (len(violacoes) == 0, violacoes)


def run_step(label: str, cmd: list[str]) -> bool:
    print(f"--- {label} ---")
    proc = _run(cmd)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    ok = proc.returncode == 0
    print(f"[{('PASS' if ok else 'FAIL')}] {label}\n")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="develop", help="Branch base para git diff")
    parser.add_argument(
        "--skip-diff", action="store_true", help="Omitir listagem de git diff"
    )
    args = parser.parse_args(argv)

    if not args.skip_diff:
        show_diff_scope(args.base)

    results: list[tuple[str, bool]] = []

    guardrails_ok, violacoes = check_guardrails()
    print("--- Guardrails LGPD / Binarios / Segredos ---")
    if guardrails_ok:
        print("Repositorio limpo: guardrails aprovados.")
    else:
        for item in violacoes:
            print(f"  - {item}")
    print(f"[{('PASS' if guardrails_ok else 'FAIL')}] Guardrails\n")
    results.append(("Guardrails LGPD/Binarios", guardrails_ok))

    py = sys.executable
    checks = [
        ("Ruff check", [py, "-m", "ruff", "check", "--no-cache", "."]),
        (
            "Ruff format --check",
            [py, "-m", "ruff", "format", "--no-cache", "--check", "."],
        ),
        (
            "MyPy (src/)",
            [
                py,
                "-m",
                "mypy",
                "src",
                "--ignore-missing-imports",
                "--no-warn-return-any",
            ],
        ),
        ("Pytest (suite leve CI)", [py, "-m", "pytest", *LIGHT_TEST_SUITE, "-v"]),
    ]

    for label, cmd in checks:
        results.append((label, run_step(label, cmd)))

    print("=== RESUMO PRE-CI ===")
    for label, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
