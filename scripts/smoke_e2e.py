"""Smoke test ponta a ponta da stack integrada do Vezo (TASK-F5-02).

Valida, usando apenas biblioteca padrão do Python (sem exibir segredos ou tokens):
1. Saúde da API FastAPI (/health), Qdrant (/readyz), MLflow (/health) e conectividade real API -> Qdrant
2. Criação de sessão persistente com cookie HttpOnly verificado no cabeçalho Set-Cookie
3. CRUD de agenda (POST /schedule) + trava determinística de sono protegido (HTTP 409)
4. Geração e rejeição explícita de proposta de otimização (requires_confirmation=True)
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_api_port_from_env_file(env_file: Path) -> str | None:
    """Lê apenas `API_PORT` de um arquivo `.env`, sem carregar nem expor segredos."""
    if not env_file.is_file():
        return None
    for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep and key.strip() == "API_PORT":
            port = value.strip().strip("\"'")
            if port.isdigit():
                return port
    return None


def _resolve_default_api_url(env_file: Path | None = None) -> str:
    """Resolve URL padrão da API respeitando `API_PORT` (ambiente ou `.env`)."""
    env_port = os.getenv("API_PORT", "").strip()
    if env_port.isdigit():
        return f"http://localhost:{env_port}"
    target_env = env_file if env_file is not None else PROJECT_ROOT / ".env"
    file_port = _read_api_port_from_env_file(target_env)
    port = file_port or "8000"
    return f"http://localhost:{port}"


def _has_httponly_cookie(
    set_cookie_headers: list[str], cookie_name: str = "vezo_session"
) -> bool:
    """Confirma no cabeçalho Set-Cookie que o cookie existe e declara o atributo HttpOnly."""
    prefix = f"{cookie_name}="
    for header in set_cookie_headers:
        parts = [part.strip() for part in header.split(";") if part.strip()]
        if not parts or not parts[0].startswith(prefix):
            continue
        attrs = {part.lower() for part in parts[1:]}
        if "httponly" in attrs:
            return True
    return False


def _request_json(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any, list[str]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "vezo-smoke-test/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            set_cookies = resp.headers.get_all("Set-Cookie") or []
            return resp.status, json.loads(raw) if raw.strip() else None, set_cookies
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        set_cookies = exc.headers.get_all("Set-Cookie") if exc.headers else []
        try:
            body: Any = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return exc.code, body, set_cookies


def _check_http_ok(url: str, timeout: float = 5.0) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "vezo-smoke-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def run_smoke(
    api_url: str,
    qdrant_url: str | None = None,
    mlflow_url: str | None = None,
) -> int:
    base = api_url.rstrip("/")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    checks: list[tuple[str, bool, str]] = []

    if qdrant_url:
        ok = _check_http_ok(f"{qdrant_url.rstrip('/')}/readyz")
        checks.append(("Qdrant /readyz", ok, qdrant_url))

    if mlflow_url:
        ok = _check_http_ok(f"{mlflow_url.rstrip('/')}/health")
        checks.append(("MLflow /health", ok, mlflow_url))

    # 1. Health da API + conectividade real da API com o Qdrant
    try:
        code, body, _ = _request_json(opener, "GET", f"{base}/health")
    except Exception as exc:
        print(f"[FAIL] API inacessível em {base}: {type(exc).__name__}")
        return 1

    health_ok = code == 200 and isinstance(body, dict) and body.get("db_ok") is True
    checks.append(
        (
            "API GET /health",
            health_ok,
            f"status={code}, db_ok={body.get('db_ok') if isinstance(body, dict) else None}",
        )
    )

    if qdrant_url:
        api_qdrant_ok = (
            isinstance(body, dict)
            and body.get("qdrant_configured") is True
            and body.get("qdrant_ok") is True
        )
        checks.append(
            (
                "API -> Qdrant conectividade (/health)",
                api_qdrant_ok,
                (
                    f"qdrant_configured={body.get('qdrant_configured') if isinstance(body, dict) else None}, "
                    f"qdrant_ok={body.get('qdrant_ok') if isinstance(body, dict) else None}"
                ),
            )
        )

    # 2. Sessão com cookie HttpOnly validado no Set-Cookie
    code, session_body, set_cookies = _request_json(
        opener,
        "POST",
        f"{base}/sessions",
        {
            "timezone": "America/Sao_Paulo",
            "sleep_start": "22:00:00",
            "sleep_end": "06:00:00",
            "consent_accepted": True,
        },
    )
    has_cookie = any(c.name == "vezo_session" for c in jar)
    has_httponly = _has_httponly_cookie(set_cookies, "vezo_session")
    session_ok = (
        code == 201 and has_cookie and has_httponly and isinstance(session_body, dict)
    )
    checks.append(
        (
            "Sessão POST /sessions (cookie HttpOnly)",
            session_ok,
            f"status={code}, cookie={has_cookie}, httponly={has_httponly}",
        )
    )

    code, _me_body, _ = _request_json(opener, "GET", f"{base}/sessions/me")
    checks.append(("Sessão GET /sessions/me", code == 200, f"status={code}"))

    # 3. Criar compromisso fixo válido
    code, _item_body, _ = _request_json(
        opener,
        "POST",
        f"{base}/schedule",
        {
            "start": "2026-12-01T08:00:00-03:00",
            "end": "2026-12-01T12:00:00-03:00",
            "label": "Residência em IA (Smoke Test)",
            "kind": "work",
            "fixed": True,
        },
    )
    checks.append(("CRUD POST /schedule (fixo)", code == 201, f"status={code}"))

    # 4. Validar proteção de sono (HTTP 409 obrigatório)
    code, _, _ = _request_json(
        opener,
        "POST",
        f"{base}/schedule",
        {
            "start": "2026-12-01T23:00:00-03:00",
            "end": "2026-12-02T01:00:00-03:00",
            "label": "Invasão de sono (deve bloquear)",
            "kind": "study",
            "fixed": False,
        },
    )
    checks.append(("Trava sono protegido (409)", code == 409, f"status={code}"))

    # 5. Otimizar agenda e rejeitar proposta (sem efeitos colaterais)
    code, prop_body, _ = _request_json(
        opener,
        "POST",
        f"{base}/schedule/optimize",
        {
            "horizon": {
                "start": "2026-12-01T06:00:00-03:00",
                "end": "2026-12-01T22:00:00-03:00",
            },
            "study_goals": [
                {
                    "goal_id": "smoke-goal-1",
                    "title": "Revisão Econometria",
                    "duration_minutes": 60,
                    "deadline": "2026-12-01T20:00:00-03:00",
                    "priority": 4,
                }
            ],
        },
    )
    proposal_id = prop_body.get("proposal_id") if isinstance(prop_body, dict) else None
    opt_ok = (
        code == 200
        and isinstance(prop_body, dict)
        and prop_body.get("requires_confirmation") is True
        and bool(proposal_id)
    )
    checks.append(("Planejador POST /schedule/optimize", opt_ok, f"status={code}"))

    if proposal_id:
        code, rej_body, _ = _request_json(
            opener, "POST", f"{base}/schedule/proposals/{proposal_id}/reject"
        )
        rej_ok = (
            code == 200
            and isinstance(rej_body, dict)
            and rej_body.get("status") == "rejected"
        )
        checks.append(
            ("Confirmação/Rejeição /proposals/.../reject", rej_ok, f"status={code}")
        )

    print("=== VEZO SMOKE TEST E2E ===")
    all_ok = True
    for label, ok, info in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label} ({info})")
        all_ok = all_ok and ok

    return 0 if all_ok else 1


def main(argv: list[str] | None = None) -> int:
    default_api_url = _resolve_default_api_url()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=default_api_url,
        help=(
            "URL base da API FastAPI "
            f"(padrão detectado via API_PORT/.env: {default_api_url})."
        ),
    )
    parser.add_argument(
        "--qdrant-url",
        default="http://localhost:6333",
        help="URL do Qdrant para checagem /readyz e conectividade via API (use '' para pular).",
    )
    parser.add_argument(
        "--mlflow-url",
        default="http://localhost:5000",
        help="URL do MLflow para checagem /health.",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Valida apenas a API FastAPI (pula checagens de Qdrant e MLflow).",
    )
    args = parser.parse_args(argv)
    return run_smoke(
        api_url=args.api_url,
        qdrant_url=None if args.api_only else (args.qdrant_url or None),
        mlflow_url=None if args.api_only else (args.mlflow_url or None),
    )


if __name__ == "__main__":
    raise SystemExit(main())
